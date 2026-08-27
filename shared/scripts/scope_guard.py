#!/usr/bin/env python3
"""Shared scope-guard engine and runtime-neutral state machine.

The engine is intentionally stdlib-only. Runtime adapters normalize their hook
payloads into ``Mutation`` values and translate ``Decision`` back to the native
hook schema. It is a prompt-time mitigation, not a filesystem security boundary.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SCOPE_START = "<!-- doc-scope:start -->"
SCOPE_END = "<!-- doc-scope:end -->"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
REASON_LINE = re.compile(r"(?:^|\n)Scope reason ([A-Za-z0-9_-]{16,64}):\s*(\S[^\n]*)")
STATE_MAX_AGE_S = 30 * 24 * 60 * 60
LOCK_STALE_S = 30


@dataclass(frozen=True)
class Scope:
    status: str  # absent | valid | malformed
    text: str = ""
    error: str = ""


@dataclass(frozen=True)
class Mutation:
    path: Path
    action: str  # write | edit | update | add | delete | move
    postimage: str | None


@dataclass(frozen=True)
class Decision:
    action: str  # ignore | allow | deny
    message: str = ""
    context: str = ""
    capability: str = ""
    nonce: str = ""


class ScopeGuardError(ValueError):
    pass


def parse_scope(text: str) -> Scope:
    starts: list[tuple[int, int]] = []
    ends: list[tuple[int, int]] = []
    offset = 0
    fenced = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and stripped in {SCOPE_START, SCOPE_END}:
            position = offset + line.find(stripped)
            (starts if stripped == SCOPE_START else ends).append((position, position + len(stripped)))
        offset += len(line)
    if not starts and not ends:
        return Scope("absent")
    if len(starts) != 1 or len(ends) != 1:
        return Scope("malformed", error="scope block must contain exactly one start and end marker")
    start, body_start = starts[0]
    end, _ = ends[0]
    if end < start:
        return Scope("malformed", error="scope block end marker precedes its start marker")
    body = text[body_start:end].strip()
    if not body:
        return Scope("malformed", error="scope block is empty")
    if not body.startswith("Scope:") or not body[len("Scope:"):].strip():
        return Scope("malformed", error="scope block must begin with a non-empty `Scope:` line")
    return Scope("valid", text=body)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_path(raw: str | Path, cwd: str | Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path(cwd) / path
    return path.resolve(strict=False)


def state_root() -> Path:
    override = os.environ.get("SCOPE_GUARD_STATE")
    if override:
        return Path(override)
    return Path.home() / ".config" / "mrcall-ai-kit" / "scope-guard" / "state"


def _session_dir(runtime: str, session_id: str) -> Path:
    if runtime not in {"claude", "codex", "opencode"}:
        raise ScopeGuardError(f"unsupported runtime `{runtime}`")
    if not SAFE_ID.fullmatch(session_id):
        raise ScopeGuardError("invalid session id")
    return state_root() / runtime / session_id


def _ensure_safe_session(runtime: str, session_id: str) -> Path:
    root = state_root()
    if root.is_symlink():
        raise ScopeGuardError("scope-guard state root must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    runtime_dir = root / runtime
    if runtime_dir.is_symlink():
        raise ScopeGuardError("scope-guard runtime state directory must not be a symlink")
    runtime_dir.mkdir(exist_ok=True)
    session = _session_dir(runtime, session_id)
    if session.is_symlink():
        raise ScopeGuardError("scope-guard session state directory must not be a symlink")
    session.mkdir(exist_ok=True)
    return session


def _record_path(runtime: str, session_id: str, path: Path) -> Path:
    name = digest(str(path))
    return _ensure_safe_session(runtime, session_id) / f"{name}.json"


@contextmanager
def _locked(record: Path) -> Iterator[None]:
    record.parent.mkdir(parents=True, exist_ok=True)
    lock = record.with_suffix(".lock")
    deadline = time.monotonic() + 2.0
    while True:
        try:
            lock.mkdir()
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > LOCK_STALE_S:
                    shutil.rmtree(lock)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise ScopeGuardError("scope-guard state is busy")
            time.sleep(0.01)
    try:
        yield
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def _read_record(record: Path) -> dict[str, object]:
    try:
        value = json.loads(record.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ScopeGuardError(f"cannot read scope-guard state: {exc}") from exc
    if not isinstance(value, dict):
        raise ScopeGuardError("scope-guard state is not an object")
    return value


def _write_record(record: Path, value: dict[str, object]) -> None:
    value["updated_at"] = int(time.time())
    tmp = record.with_name(f".{record.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        tmp.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, record)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _challenge_message(scope: str, nonce: str, extra: str = "") -> str:
    detail = f"\n{extra.strip()}" if extra.strip() else ""
    return (
        "Scope guard stopped this first attempt.\n"
        f"{scope}{detail}\n"
        "Decide yourself whether the mutation belongs in that scope. Before retrying, "
        "state this exact visible prefix followed by your reason:\n"
        f"Scope reason {nonce}: <your reason>\n"
        "Do not ask the operator for permission. Retry only if you decide it belongs."
    )


def cleanup(max_entries: int = 32) -> None:
    root = state_root()
    if not root.is_dir() or root.is_symlink():
        return
    cutoff = time.time() - STATE_MAX_AGE_S
    checked = 0
    for runtime in sorted(root.iterdir()):
        if checked >= max_entries or not runtime.is_dir() or runtime.is_symlink():
            continue
        for session in sorted(runtime.iterdir()):
            if checked >= max_entries:
                break
            if not session.is_dir() or session.is_symlink():
                continue
            checked += 1
            try:
                if session.stat().st_mtime < cutoff:
                    shutil.rmtree(session)
            except OSError:
                continue


def _new_challenge(
    record: Path,
    *,
    runtime: str,
    session_id: str,
    path: Path,
    scope: Scope,
    proposed_scope: Scope,
    proposed_digest: str,
    kind: str,
    turn_id: str,
) -> Decision:
    nonce = secrets.token_urlsafe(18)
    value: dict[str, object] = {
        "runtime": runtime,
        "session_id": session_id,
        "path": str(path),
        "scope": scope.text,
        "scope_digest": digest(scope.text),
        "proposed_scope": proposed_scope.text,
        "proposed_scope_digest": digest(proposed_scope.text) if proposed_scope.status == "valid" else "",
        "proposed_digest": proposed_digest,
        "phase": kind,
        "nonce": nonce,
        "attempts": 1,
        "challenge_turn": turn_id,
    }
    _write_record(record, value)
    extra = ""
    if kind == "scope-change":
        extra = f"Proposed new scope:\n{proposed_scope.text}"
    elif kind == "unmark":
        extra = "This mutation removes the scope marker. Ordinary writes may not do that."
    return Decision(
        "deny",
        _challenge_message(scope.text, nonce, extra),
        context=scope.text,
        capability="full" if runtime == "claude" else "degraded",
        nonce=nonce,
    )


def decide(
    runtime: str,
    session_id: str,
    mutation: Mutation,
    *,
    full_attestation: bool = False,
    turn_id: str = "",
) -> Decision:
    """Evaluate one mutation. Adapters combine multi-target decisions deny-first."""
    cleanup()
    path = mutation.path.resolve(strict=False)
    record = _record_path(runtime, session_id, path)
    try:
        preimage = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Decision("ignore")
    except (OSError, UnicodeDecodeError) as exc:
        return Decision("deny", f"Scope guard could not read `{path}`: {exc}")
    current = parse_scope(preimage)

    with _locked(record):
        state = _read_record(record)
        if current.status == "absent":
            if state.get("scope_digest"):
                return Decision(
                    "deny",
                    f"Scope guard state says `{path}` was scoped, but its marker is now absent. "
                    "Restore the marker or explicitly clear scope-guard state.",
                )
            return Decision("ignore")
        if current.status == "malformed":
            return Decision("deny", f"Malformed scope block in `{path}`: {current.error}")

        if mutation.action in {"delete", "move"}:
            return Decision(
                "deny",
                f"Scoped document `{path}` cannot be {mutation.action}d by an ordinary file tool. "
                "Use the explicit scope-guard administrative transition.",
                context=current.text,
            )
        if mutation.postimage is None:
            return Decision("deny", f"Scope guard could not reconstruct the proposed content of `{path}`")

        proposed = parse_scope(mutation.postimage)
        proposed_digest = digest(mutation.postimage)
        capability = "full" if full_attestation else "degraded"
        current_scope_digest = digest(current.text)
        state_matches = (
            state.get("path") == str(path)
            and state.get("scope_digest") == current_scope_digest
            and state.get("proposed_digest") == proposed_digest
        )

        if proposed.status != "valid":
            if (
                proposed.status == "absent"
                and state_matches
                and state.get("phase") == "unmark-authorized"
            ):
                try:
                    record.unlink()
                except FileNotFoundError:
                    pass
                return Decision("allow", context=current.text, capability=capability)
            if proposed.status == "malformed":
                return Decision(
                    "deny",
                    f"Proposed mutation would leave `{path}` with a malformed scope block: {proposed.error}",
                    context=current.text,
                )
            if state_matches and state.get("phase") == "unmark":
                state["attempts"] = int(state.get("attempts", 1)) + 1
                _write_record(record, state)
                return Decision(
                    "deny",
                    f"Removing the scope marker requires `scope-guard unmark {state.get('nonce')}`. "
                    "This is an agent decision; do not ask the operator for permission.",
                    context=current.text,
                    capability=capability,
                    nonce=str(state.get("nonce", "")),
                )
            return _new_challenge(
                record,
                runtime=runtime,
                session_id=session_id,
                path=path,
                scope=current,
                proposed_scope=proposed,
                proposed_digest=proposed_digest,
                kind="unmark",
                turn_id=turn_id,
            )

        proposed_scope_digest = digest(proposed.text)
        kind = "open" if proposed_scope_digest == current_scope_digest else "scope-change"
        if (
            kind == "open"
            and state.get("phase") == "open"
            and state.get("scope_digest") == current_scope_digest
        ):
            return Decision("allow", context=current.text, capability=capability)

        if state_matches and state.get("proposed_scope_digest") == proposed_scope_digest:
            phase = str(state.get("phase", ""))
            later_turn = bool(turn_id) and state.get("challenge_turn") != turn_id
            if phase == "attested" or (
                not full_attestation
                and later_turn
                and phase in {"open-challenge", "scope-change"}
            ):
                _write_record(
                    record,
                    {
                        "runtime": runtime,
                        "session_id": session_id,
                        "path": str(path),
                        "scope": proposed.text,
                        "scope_digest": proposed_scope_digest,
                        "phase": "open",
                    },
                )
                return Decision("allow", context=current.text, capability=capability)
            state["attempts"] = int(state.get("attempts", 1)) + 1
            _write_record(record, state)
            return Decision(
                "deny",
                _challenge_message(current.text, str(state.get("nonce", ""))),
                context=current.text,
                capability=capability,
                nonce=str(state.get("nonce", "")),
            )

        return _new_challenge(
            record,
            runtime=runtime,
            session_id=session_id,
            path=path,
            scope=current,
            proposed_scope=proposed,
            proposed_digest=proposed_digest,
            kind="open-challenge" if kind == "open" else "scope-change",
            turn_id=turn_id,
        )


def attest(runtime: str, session_id: str, text: str) -> int:
    """Attest complete assistant-display text. Returns challenges opened."""
    session = _session_dir(runtime, session_id)
    matches = {m.group(1): m.group(2).strip() for m in REASON_LINE.finditer(text)}
    if not matches or not session.is_dir() or session.is_symlink():
        return 0
    opened = 0
    for record in sorted(session.glob("*.json")):
        if record.is_symlink():
            continue
        with _locked(record):
            state = _read_record(record)
            nonce = str(state.get("nonce", ""))
            if nonce in matches and state.get("phase") in {"open-challenge", "scope-change"}:
                state["phase"] = "attested"
                state["reason"] = matches[nonce]
                _write_record(record, state)
                opened += 1
    return opened


def authorize_unmark(runtime: str, session_id: str, nonce: str) -> bool:
    session = _session_dir(runtime, session_id)
    if not session.is_dir() or session.is_symlink():
        return False
    for record in sorted(session.glob("*.json")):
        if record.is_symlink():
            continue
        with _locked(record):
            state = _read_record(record)
            if state.get("phase") == "unmark" and secrets.compare_digest(str(state.get("nonce", "")), nonce):
                state["phase"] = "unmark-authorized"
                _write_record(record, state)
                return True
    return False


def authorize_unmark_any(nonce: str) -> bool:
    """Authorize a nonce without asking an agent to know its runtime session id."""
    root = state_root()
    if not root.is_dir() or root.is_symlink():
        return False
    for runtime_dir in sorted(root.iterdir()):
        if not runtime_dir.is_dir() or runtime_dir.is_symlink():
            continue
        for session in sorted(runtime_dir.iterdir()):
            if not session.is_dir() or session.is_symlink():
                continue
            if authorize_unmark(runtime_dir.name, session.name, nonce):
                return True
    return False


def close_session(runtime: str, session_id: str) -> None:
    session = _session_dir(runtime, session_id)
    if session.is_dir() and not session.is_symlink():
        shutil.rmtree(session)


def apply_edit(text: str, old: str, new: str, replace_all: bool = False) -> str:
    count = text.count(old)
    if count == 0:
        raise ScopeGuardError("Edit old_string does not occur in the preimage")
    if not replace_all and count != 1:
        raise ScopeGuardError("Edit old_string is ambiguous in the preimage")
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def _strip_patch_prefix(line: str) -> tuple[str, str]:
    if line and line[0] in {" ", "+", "-"}:
        return line[0], line[1:]
    raise ScopeGuardError(f"invalid patch hunk line: {line!r}")


def _apply_update(preimage: str, lines: list[str]) -> str:
    hunks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("@@"):
            if current:
                hunks.append(current)
            current = []
        else:
            current.append(line)
    if current:
        hunks.append(current)
    result = preimage
    cursor = 0
    for hunk in hunks:
        old_lines: list[str] = []
        new_lines: list[str] = []
        for raw in hunk:
            prefix, value = _strip_patch_prefix(raw)
            if prefix != "+":
                old_lines.append(value)
            if prefix != "-":
                new_lines.append(value)
        old = "\n".join(old_lines)
        new = "\n".join(new_lines)
        index = result.find(old, cursor)
        if index < 0:
            raise ScopeGuardError("patch hunk does not match the target preimage")
        result = result[:index] + new + result[index + len(old):]
        cursor = index + len(new)
    return result


def parse_apply_patch(command: str, cwd: str | Path) -> list[Mutation]:
    """Parse the structured apply_patch envelope and reconstruct each postimage."""
    lines = command.splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ScopeGuardError("invalid apply_patch envelope")
    mutations: list[Mutation] = []
    index = 1
    while index < len(lines) - 1:
        header = lines[index]
        index += 1
        action = ""
        raw_path = ""
        if header.startswith("*** Update File: "):
            action, raw_path = "update", header.removeprefix("*** Update File: ")
        elif header.startswith("*** Add File: "):
            action, raw_path = "add", header.removeprefix("*** Add File: ")
        elif header.startswith("*** Delete File: "):
            action, raw_path = "delete", header.removeprefix("*** Delete File: ")
        else:
            raise ScopeGuardError(f"unknown apply_patch section `{header}`")
        section: list[str] = []
        move_to = ""
        while index < len(lines) - 1 and not lines[index].startswith(("*** Update File: ", "*** Add File: ", "*** Delete File: ")):
            if lines[index].startswith("*** Move to: "):
                move_to = lines[index].removeprefix("*** Move to: ")
            else:
                section.append(lines[index])
            index += 1
        path = canonical_path(raw_path, cwd)
        if action == "delete":
            mutations.append(Mutation(path, "delete", None))
            continue
        if action == "add":
            content = "\n".join(line[1:] for line in section if line.startswith("+"))
            if section and section[-1].startswith("+"):
                content += "\n"
            mutations.append(Mutation(path, "add", content))
            continue
        try:
            preimage = path.read_text(encoding="utf-8")
            postimage = _apply_update(preimage, section)
        except (OSError, UnicodeDecodeError) as exc:
            raise ScopeGuardError(f"cannot reconstruct patch target `{path}`: {exc}") from exc
        mutations.append(Mutation(path, "move" if move_to else "update", postimage))
        if move_to:
            mutations.append(Mutation(canonical_path(move_to, cwd), "add", postimage))
    return mutations


def cli(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "unmark":
        ok = authorize_unmark_any(argv[2])
        print("Scope unmark authorized for one exact retry." if ok else "No matching unmark challenge.")
        return 0 if ok else 1
    if len(argv) >= 5 and argv[1] == "unmark":
        ok = authorize_unmark(argv[2], argv[3], argv[4])
        print("Scope unmark authorized for one exact retry." if ok else "No matching unmark challenge.")
        return 0 if ok else 1
    if len(argv) >= 4 and argv[1] == "close-session":
        close_session(argv[2], argv[3])
        return 0
    print("usage: scope_guard.py unmark <nonce>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(cli(sys.argv))
