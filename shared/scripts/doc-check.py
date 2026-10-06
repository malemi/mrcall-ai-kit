#!/usr/bin/env python3
"""
Documentation integrity gate for harness v9: project routing and the canonical
managed delivery block share AGENTS.md. Existing link, scope, inventory, size,
status, baseline, and living-context checks remain mechanical checks only.
--startup adds compact Git and lifecycle facts; --json emits all diagnostics.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# An inline code span: a run of backticks, its content, the same run again.
INLINE_CODE = re.compile(r"(`+)[^`]*?\1")
HARNESS_VERSION = 9
# Bytes per token: a stated convention for English prose, NOT a tokenizer result.
# It carries none of the argument — every size comparison is a ratio between two
# numbers produced by this divisor, so a wrong divisor cancels out.
BYTES_PER_TOKEN = 4
KNOWN_PROFILE_KEYS = {
    "harness_version", "schema_version", "mode", "index_file", "harness_file",
    "inventory_ignore", "build", "smoke", "release", "index_max_lines", "doc_max_lines",
}
PLAN_STATUSES = {"planned", "active", "blocked", "completed", "superseded"}
SESSION_STATUSES = {"open", "closed"}
CONTEXT_SECTIONS = {"state now", "unresolved", "next"}
# Cold storage that grows by design — exempt from the advisory size report.
SIZE_EXEMPT = {"docs/active-context-archive.md"}
# Work traces (briefs and execution plans) are dated so they sort by workstream.
TRACE_DIRS = ("docs/briefs", "docs/execution-plans")
# Closes the orientation head of a sub-repo index. An HTML comment rather than a
# heading: it vanishes from the rendered document but stays greppable, and unlike
# "everything above the first `##`" it gives this gate something to actually test.
ORIENTATION_MARKER = "<!-- orientation ends -->"
# Repo convention is the hyphenated ISO date (`2026-08-14-slug.md`); the old
# `^\d{8}` form never matched it and flagged every dated trace as undated.
TRACE_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
DOC_SCOPE_START = "<!-- doc-scope:start -->"
DOC_SCOPE_END = "<!-- doc-scope:end -->"


def repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except Exception:
        return Path.cwd()


def read_profile(root: Path) -> tuple[dict[str, str], list[str], bool]:
    prof = root / "docs" / ".doc-profile"
    profile_exists = prof.exists()
    values: dict[str, str] = {
        "mode": "leaf", "index_file": "AGENTS.md", "inventory_ignore": "",
        "index_max_lines": "200", "doc_max_lines": "400",
    }
    errors: list[str] = []
    if prof.exists():
        seen: set[str] = set()
        for number, line in enumerate(prof.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                errors.append(f"docs/.doc-profile:{number}: expected `key = value`")
                continue
            k, _, v = line.partition("=")
            key, value = k.strip(), v.strip()
            if key not in KNOWN_PROFILE_KEYS:
                errors.append(f"docs/.doc-profile:{number}: unknown key `{key}`")
            elif key in seen:
                errors.append(f"docs/.doc-profile:{number}: duplicate key `{key}`")
            else:
                seen.add(key)
                values[key] = value
    if values["mode"].lower() not in {"leaf", "meta"}:
        errors.append("docs/.doc-profile: `mode` must be `leaf` or `meta`")
    if "schema_version" in values and values["schema_version"] != "1":
        errors.append("docs/.doc-profile: `schema_version` must be `1`")
    for key, label in (("index_file", "index"),):
        path = root / values[key]
        if profile_exists and (not values[key] or not path.is_file()):
            errors.append(f"docs/.doc-profile: {label} file `{values[key]}` does not exist")
        elif profile_exists:
            if path.suffix.lower() != ".md":
                errors.append(f"docs/.doc-profile: `{key}` must be a Markdown (`.md`) file")
            try:
                path.resolve().relative_to(root.resolve())
            except ValueError:
                errors.append(f"docs/.doc-profile: `{key}` must stay inside the repo")
    for key in ("build", "smoke", "release"):
        if key in values and not values[key]:
            errors.append(f"docs/.doc-profile: `{key}` must not be empty when present")
    for key in ("index_max_lines", "doc_max_lines"):
        try:
            if int(values[key]) < 0:
                raise ValueError
        except ValueError:
            errors.append(f"docs/.doc-profile: `{key}` must be a non-negative integer")
    if profile_exists:
        raw_version = values.get("harness_version")
        if raw_version is None:
            errors.append(
                "docs/.doc-profile: missing `harness_version`; repository docs use a "
                "legacy harness that doc-create cannot migrate (it migrates only v6-v8 profiles); "
                "this layout is unsupported until it is converted outside the kit"
            )
        else:
            try:
                profile_version = int(raw_version)
                if profile_version < 1:
                    raise ValueError
            except ValueError:
                errors.append("docs/.doc-profile: `harness_version` must be a positive integer")
            else:
                if profile_version < 6:
                    errors.append(
                        f"docs harness version {profile_version} is older than installed version "
                        f"{HARNESS_VERSION}; doc-create migrates only v6-v8 profiles, so this "
                        "layout is unsupported until it is converted outside the kit"
                    )
                elif profile_version < HARNESS_VERSION:
                    errors.append(
                        f"docs harness version {profile_version} is older than installed version "
                        f"{HARNESS_VERSION}; explicitly migrate docs/ with doc-create"
                    )
                elif profile_version > HARNESS_VERSION:
                    errors.append(
                        f"docs harness version {profile_version} is newer than installed version "
                        f"{HARNESS_VERSION}; upgrade the installed mrcall-ai-kit commands"
                    )
                else:
                    if values["index_file"] != "AGENTS.md":
                        errors.append("docs/.doc-profile: harness v9 requires `index_file = AGENTS.md`")
                    if "harness_file" in seen:
                        errors.append("docs/.doc-profile: harness v9 removes `harness_file`; migrate explicitly")
    if not profile_exists:
        errors.append("docs/.doc-profile: missing profile; run doc-create")
    return values, errors, profile_exists


def index_docs(root: Path, index_file: str, harness_file: str) -> list[Path]:
    docs = [root / "README.md", root / index_file]
    docs_dir = root / "docs"
    if docs_dir.exists():
        docs += sorted(docs_dir.rglob("*.md"))
    seen, out = set(), []
    for p in docs:
        if p.exists() and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def canonical_repo_dirs(root: Path, index_file: str) -> set[str]:
    """Bare dir names from the `Path` column of the index's `## Services` table."""
    idx = root / index_file
    if not idx.exists():
        return set()
    lines = idx.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "## Services")
    except StopIteration:
        return set()
    names: set[str] = set()
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        if not ln.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("Service", "---") or set(cells[0]) <= {"-", ":"}:
            continue
        m = re.search(r"`([^`]+)`", cells[1])
        if m:
            names.add(m.group(1).strip().strip("/").split("/")[0])
    return names


def is_independent_repo(d: Path) -> bool:
    return d.is_dir() and (d / ".git").exists()


def strip_code(text: str) -> str:
    """Markdown with fenced blocks and inline code spans blanked out.

    The link check must never see code. `MD_LINK` is `[...](...)`, and a great
    deal of ordinary source matches it exactly: `Array.fill[Byte](packetSize)`
    and `get[String]("from")` are both read as links to `packetSize` and
    `"from"`. Reporting those as dead links puts a clean gate out of reach for
    any repository that documents code, which is every repository — starchat's
    docs produced 19 of them against 1 real finding.

    Inline spans are stripped as well as fenced blocks, because the pattern
    fires on a single backticked snippet in a sentence, not only inside a fence.

    Line structure is preserved: blanked lines stay as empty lines, so a line
    number taken from this text still refers to the same line of the original.
    """
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else INLINE_CODE.sub("", line))
    return "\n".join(out)


def check_dead_links(root: Path, index_file: str, harness_file: str) -> list[str]:
    errors: list[str] = []
    for doc in index_docs(root, index_file, harness_file):
        base = doc.parent
        for m in MD_LINK.finditer(strip_code(doc.read_text(encoding="utf-8"))):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0].strip()
            if not target:
                continue
            if not (base / target).exists():
                errors.append(f"{doc.relative_to(root)} → dead link: ({m.group(1)})")
    return errors


def check_doc_scopes(root: Path, index_file: str, harness_file: str) -> list[str]:
    """Validate v6 inline scope declarations on routing documents.

    A declaration is intentionally tiny and rigid so both the gate and runtime
    guards agree on one representation::

        <!-- doc-scope:start -->
        Scope: non-empty purpose and boundary, optionally continued
        <!-- doc-scope:end -->

    The managed harness entry point, project-owned index, docs router, and living
    snapshot require exactly one block. Other indexed Markdown may omit it, but
    a partial, duplicate, or malformed declaration is never treated as absent.
    Harness v8 has no external index-scope form.
    """
    required = {
        Path(index_file).as_posix(),
        "docs/README.md",
        "docs/active-context.md",
    }
    errors: list[str] = []
    for doc in index_docs(root, index_file, harness_file):
        rel = doc.relative_to(root).as_posix()
        lines = doc.read_text(encoding="utf-8").splitlines()
        visible: list[tuple[int, str]] = []
        fenced = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
                continue
            if not fenced:
                visible.append((i, line))
        starts = [i for i, line in visible if line == DOC_SCOPE_START]
        ends = [i for i, line in visible if line == DOC_SCOPE_END]
        marker_like = [
            (i, line) for i, line in visible
            if line.strip().startswith("<!-- doc-scope:")
            and line not in {DOC_SCOPE_START, DOC_SCOPE_END}
        ]
        legacy_external = [
            (i, line) for i, line in visible
            if line.strip().startswith("<!-- doc-index-scope:")
        ]
        for number, line in legacy_external:
            errors.append(
                f"{rel}:{number + 1}: obsolete external index-scope delimiter "
                f"`{line.strip()}`; harness v8 requires inline scope"
            )

        if not starts and not ends and not marker_like:
            if rel in required:
                errors.append(f"{rel}: missing required doc-scope block")
            continue
        if marker_like:
            for number, line in marker_like:
                errors.append(
                    f"{rel}:{number + 1}: malformed doc-scope delimiter `{line.strip()}`"
                )
        if len(starts) != 1 or len(ends) != 1:
            errors.append(
                f"{rel}: expected exactly one `{DOC_SCOPE_START}` and one "
                f"`{DOC_SCOPE_END}` (found {len(starts)} start, {len(ends)} end)"
            )
            continue
        start, end = starts[0], ends[0]
        if start >= end:
            errors.append(f"{rel}: doc-scope delimiters are out of order")
            continue
        body = "\n".join(lines[start + 1:end]).strip()
        if not body.startswith("Scope:"):
            errors.append(f"{rel}: doc-scope content must begin with `Scope:`")
        elif not body[len("Scope:"):].strip():
            errors.append(f"{rel}: doc-scope `Scope:` text must not be empty")
    for rel in sorted(required):
        if not (root / rel).is_file():
            errors.append(f"{rel}: required doc-scope routing document does not exist")
    return errors


def find_harness_template() -> Path | None:
    configured = os.environ.get("MRCALL_DOC_HARNESS_TEMPLATE")
    kit_home = os.environ.get("MRCALL_KIT_HOME")
    candidates = [
        Path(configured) if configured else None,
        Path(kit_home) / "AGENTS.block.md" if kit_home else None,
        Path(__file__).resolve().parents[1] / "templates" / "AGENTS.block.md",
        Path(__file__).resolve().with_name("AGENTS.block.md"),
    ]
    return next((path for path in candidates if path is not None and path.is_file()), None)


def managed_block_span(data: bytes, name: bytes = b"delivery") -> tuple[int, int] | None:
    prefix = b"<!-- mrcall-ai-kit:" + name + b":"
    start, end = prefix + b"start -->", prefix + b"end -->"
    marker = prefix[:-1]
    if marker not in data:
        return None
    markers = []
    offset = 0
    fenced = False
    for line in data.splitlines(keepends=True):
        stripped = line.rstrip(b"\r\n")
        if stripped.lstrip().startswith((b"```", b"~~~")):
            fenced = not fenced
        if marker in line:
            if fenced or stripped not in (start, end):
                raise ValueError("malformed or fenced managed block delimiter")
            markers.append((stripped, offset, offset + len(stripped)))
        offset += len(line)
    if len(markers) != 2 or markers[0][0] != start or markers[1][0] != end:
        raise ValueError("expected exactly one ordered managed delivery block")
    return markers[0][1], markers[1][2]


def check_harness_template(root: Path, harness_file: str) -> list[str]:
    errors = []
    for rel in ("CLAUDE.md", "CLAUDE.local.md", ".claude/rules/doc-harness.md"):
        if (root / rel).exists() or (root / rel).is_symlink():
            errors.append(f"{rel}: legacy or foreign instruction file remains; single-entry compatibility unresolved")
    template = find_harness_template()
    if template is None:
        return errors + ["canonical AGENTS.md managed block is not installed"]
    target = root / "AGENTS.md"
    if not target.is_file():
        return errors + ["AGENTS.md: managed instruction entry is missing"]
    expected = template.read_bytes()
    actual = target.read_bytes()
    try:
        span = managed_block_span(actual)
    except ValueError as exc:
        return errors + [f"AGENTS.md: {exc}"]
    if span is None:
        return errors + ["AGENTS.md: expected exactly one managed delivery block"]
    first, last = span
    if actual[first:last] != expected.rstrip(b"\n"):
        errors.append("AGENTS.md: managed delivery block differs from canonical template")
    return errors


def size_note(doc: Path, text: str) -> str:
    """`<bytes> bytes, ~<tokens> tokens` — the quantity the limits do NOT measure.

    Both size limits count lines, and a context window is billed in bytes. The
    two do not track each other: 160 lines of dense tables outweigh 400 lines of
    prose, so a file can pass the thin-index check while being the single most
    expensive thing a session loads. Reporting only lines describes the file;
    reporting bytes and tokens describes what opening it does to the session,
    which is the number any decision here actually turns on.

    Bytes come from `stat` — the number `wc -c` prints, reproducible by hand
    without opening the file, which is the same standard the line count is held
    to. Not `len(text.encode())`: `read_text` translates CRLF, so re-encoding
    would under-report a file by one byte per line. `text` is only the fallback
    for a doc that was readable a moment ago and can no longer be stat'd.

    Tokens are bytes // BYTES_PER_TOKEN, a convention recorded as such in
    docs/documentation-harness.md, printed with a `~` because it is an estimate
    and never a tokenizer result.
    """
    try:
        size = doc.stat().st_size
    except OSError:
        size = len(text.encode("utf-8"))
    return f"{size:,} bytes, ~{size // BYTES_PER_TOKEN:,} tokens"


def check_index_thin(root: Path, index_file: str, maximum: int) -> list[str]:
    index = root / index_file
    if not maximum or not index.is_file():
        return []
    text = index.read_text(encoding="utf-8")
    count = len(text.splitlines())
    if count > maximum:
        return [
            f"{index_file} has {count} lines, {size_note(index, text)} "
            f"(thin-index limit: {maximum} lines; set `index_max_lines = 0` to disable)"
        ]
    return []


def check_doc_sizes(root: Path, index_file: str, harness_file: str, maximum: int) -> list[str]:
    """ADVISORY — name every doc that has grown past `doc_max_lines`.

    Never a gate failure. Whether a long document should be split, trimmed, or
    left alone is a judgement the operator makes with knowledge the harness does
    not have; the only thing worth automating is that nobody has to notice the
    growth by accident. So this reports and stops there.

    It deliberately reports the path, the line count, the byte size and a token
    estimate, and NOTHING else. That is what lets it cover `docs/projects/**`,
    which a session must never open at start-up: knowing `<project>/status.md` is
    900 lines and ~14,000 tokens costs a dozen tokens, while reading it to find
    out costs those fourteen thousand. The size is what makes the line
    actionable — see `size_note`.

    `docs/active-context-archive.md` is exempt — it is cold storage that grows
    forever by design, so flagging it every run would be noise, not signal.

    Defensive throughout: an advisory that raises would take the whole gate down
    with it, turning "your doc is long" into a blocked commit and a `/doc-end`
    that cannot advance its baseline. Anything it cannot measure, it skips —
    a doc that is genuinely unreadable is already the other checks' business.
    """
    if maximum <= 0:                      # 0 disables it; a negative value is invalid
        return []                         # and separately reported by read_profile
    oversized: list[tuple[int, str, str]] = []
    for doc in index_docs(root, index_file, harness_file):
        try:
            rel = doc.relative_to(root).as_posix()
        except ValueError:                # an index_file reached from outside the root
            rel = doc.as_posix()
        if rel in SIZE_EXEMPT:
            continue
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # `count("\n")` and not `splitlines()`: the latter also breaks on form
        # feeds and unicode separators, so it can report more lines than `wc -l`.
        # The number has to be one the operator can reproduce without opening it.
        count = text.count("\n")
        if count > maximum:
            oversized.append((count, rel, size_note(doc, text)))
    return [
        f"{rel}: {count} line{'' if count == 1 else 's'}, {note} "
        f"(advisory limit: {maximum} lines)"
        for count, rel, note in sorted(oversized, key=lambda item: (-item[0], item[1]))
    ]


def check_trace_naming(root: Path) -> list[str]:
    """ADVISORY — name every work-trace file whose filename lacks a date prefix.

    Briefs and execution plans are the durable trace of a workstream; the
    `YYYY-MM-DD-` prefix is what lets them sort chronologically and answer "when
    was this decided" without git archaeology. Advisory, not a failure:
    repositories predating the convention hold undated files whose renaming is
    the operator's call, and making the filename a gate failure would require a
    `harness_version` bump plus an explicit migration. A `README.md` inside
    either directory is routing, not a trace, and is exempt.
    """
    warnings: list[str] = []
    for rel_dir in TRACE_DIRS:
        base = root / rel_dir
        if not base.exists():
            continue
        for doc in sorted(base.rglob("*.md")):
            if doc.name.lower() == "readme.md":
                continue
            if not TRACE_NAME.match(doc.name):
                warnings.append(
                    f"{doc.relative_to(root).as_posix()}: work-trace file without "
                    "a `YYYY-MM-DD-` date prefix"
                )
    return warnings


def frontmatter(text: str) -> tuple[dict[str, str], set[str]] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    for line in lines[1:]:
        if line.strip() == "---":
            return values, duplicates
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            if key in values:
                duplicates.add(key)
            values[key] = value.strip().strip("\"'")
    return None


def read_frontmatter(path: Path) -> tuple[dict[str, str], set[str]] | None:
    with path.open(encoding="utf-8") as handle:
        first = handle.readline()
        if first.strip() != "---":
            return None
        lines = [first]
        for line in handle:
            lines.append(line)
            if line.strip() == "---":
                return frontmatter("".join(lines))
    return None


def check_plan_statuses(root: Path) -> list[str]:
    plans = root / "docs" / "execution-plans"
    if not plans.exists():
        return []
    errors: list[str] = []
    for plan in sorted(plans.rglob("*.md")):
        rel = plan.relative_to(root)
        parsed = read_frontmatter(plan)
        if parsed is None:
            errors.append(f"{rel}: missing YAML frontmatter with `status`")
            continue
        metadata, duplicates = parsed
        if "status" in duplicates:
            errors.append(f"{rel}: frontmatter must contain exactly one `status`")
        elif "status" not in metadata:
            errors.append(f"{rel}: frontmatter is missing `status`")
        elif metadata["status"].lower() not in PLAN_STATUSES:
            allowed = "|".join(sorted(PLAN_STATUSES))
            errors.append(f"{rel}: invalid status `{metadata['status']}` (expected {allowed})")
    return errors


def check_session_statuses(root: Path) -> list[str]:
    """docs/sessions/*.md is the router's shared-memory blackboard: one file
    per Claude Code session, `status: open` until `/doc-end` promotes it into
    active-context.md and flips it to `closed`. Same enforcement shape as
    execution-plan status — a gate failure, not an advisory, because an
    invalid value here is a typo in a file the harness itself writes, not a
    judgment call.
    """
    sessions = root / "docs" / "sessions"
    if not sessions.exists():
        return []
    errors: list[str] = []
    for session in sorted(sessions.glob("*.md")):
        rel = session.relative_to(root)
        parsed = read_frontmatter(session)
        if parsed is None:
            errors.append(f"{rel}: missing YAML frontmatter with `status`")
            continue
        metadata, duplicates = parsed
        if "status" in duplicates:
            errors.append(f"{rel}: frontmatter must contain exactly one `status`")
        elif "status" not in metadata:
            errors.append(f"{rel}: frontmatter is missing `status`")
        elif metadata["status"].lower() not in SESSION_STATUSES:
            allowed = "|".join(sorted(SESSION_STATUSES))
            errors.append(f"{rel}: invalid status `{metadata['status']}` (expected {allowed})")
    return errors


def check_open_sessions(root: Path) -> list[str]:
    """ADVISORY — count docs/sessions/*.md still `status: open`.

    An open file mid-session is normal, not drift; only a stale one — its
    owning session long dead — is worth attention, and this check has no way
    to tell the two apart (no PID, no lock, just a transcript mtime that means
    nothing for a session left idle rather than closed). So it counts and
    stops: judging which open files are actually stale is `/router sweep`'s
    job, with the transcript timestamps this check does not have.
    """
    sessions = root / "docs" / "sessions"
    if not sessions.exists():
        return []
    open_files: list[str] = []
    for session in sorted(sessions.glob("*.md")):
        parsed = read_frontmatter(session)
        metadata = parsed[0] if parsed else {}
        if metadata.get("status", "").lower() == "open":
            open_files.append(session.relative_to(root).as_posix())
    return [f"{rel}: session still open" for rel in open_files]


VALID_ISSUE_STATUSES = {"open", "fixed", "unknown"}


def check_unstated_issues(root: Path) -> list[str]:
    """ADVISORY — name every docs/known-issues/*.md with no usable `status:`.

    `doc-start` counts open issues from this frontmatter, so a file without it
    is invisible to the count rather than merely untidy. It stays advisory and
    not a gate failure on purpose: the directory predates the field in every
    repository that has one, and a log of real incidents must not become a
    reason the gate refuses to run. README.md is the index, not an incident.
    """
    issues = root / "docs" / "known-issues"
    if not issues.exists():
        return []
    warnings: list[str] = []
    for issue in sorted(issues.glob("*.md")):
        if issue.name.lower() == "readme.md":
            continue
        parsed = read_frontmatter(issue)
        metadata = parsed[0] if parsed else {}
        status = str(metadata.get("status", "")).lower()
        if not status:
            warnings.append(f"{issue.relative_to(root).as_posix()}: no `status:` frontmatter")
        elif parsed and "status" in parsed[1]:
            warnings.append(f"{issue.relative_to(root).as_posix()}: duplicate `status:` frontmatter")
        elif status not in VALID_ISSUE_STATUSES:
            warnings.append(
                f"{issue.relative_to(root).as_posix()}: status `{status}` is not "
                f"one of {', '.join(sorted(VALID_ISSUE_STATUSES))}"
            )
    return warnings


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def check_protocol_release(root: Path) -> tuple[list[str], list[str]]:
    """Kit-self invariant: the enforced protocol equals the released protocol.

    Only the kit checkout carries `shared/scripts/doc-check.py` at its root, so
    this is silent in every other repository. The installed checkout — the one
    the machine's `${MRCALL_KIT_HOME:-~/.config/mrcall-ai-kit}/doc-check.py`
    resolves into — is enforced on every branch and detached HEAD, because
    symlinks expose its working tree machine-wide the moment it changes; any
    other checkout (linked worktree, clone, copy-mode install) is enforced
    only on `main`, the release source, so development worktrees legitimately
    precede a release. Ahead of the newest tag is a violation unless
    `CHANGELOG.md` carries a `## vN.x.y` heading — the state doc-end Phase 5
    stages before the release command runs — which downgrades to an advisory;
    behind the newest tag is always a violation. Highest semver among local
    tags wins; the gate never fetches, so every message names the staleness
    caveat.
    """
    gate = root / "shared" / "scripts" / "doc-check.py"
    if not gate.is_file():
        return [], []
    match = re.search(
        r"^HARNESS_VERSION = (\d+)$",
        gate.read_text(encoding="utf-8", errors="replace"),
        re.M,
    )
    if not match:
        return [], []
    protocol = int(match.group(1))
    kit_home = Path(os.environ.get("MRCALL_KIT_HOME") or (Path.home() / ".config" / "mrcall-ai-kit"))
    installed = kit_home / "doc-check.py"
    try:
        installed_checkout = installed.exists() and installed.resolve().is_relative_to(root.resolve())
    except OSError:
        installed_checkout = False
    branch = run_git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not installed_checkout and branch != "main":
        return [], []
    versions = []
    for name in run_git(root, "tag", "--list").stdout.split():
        parsed = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", name)
        if parsed:
            versions.append((tuple(int(part) for part in parsed.groups()), name))
    if not versions:
        return [], [
            f"HARNESS_VERSION {protocol} but no release tag is visible: the protocol/release "
            "invariant cannot be verified (fresh or shallow clone? run `git fetch --tags`)"
        ]
    newest_version, newest_tag = max(versions)
    if newest_version[0] == protocol:
        return [], []
    stale = " If local tags are stale, run `git fetch --tags`."
    if newest_version[0] > protocol:
        return [
            f"HARNESS_VERSION {protocol} is behind the newest release tag {newest_tag}: this "
            "checkout enforces a protocol older than its own release — restore the released "
            f"protocol with an ordinary commit (revert the downgrade).{stale}"
        ], []
    changelog = root / "CHANGELOG.md"
    pending = changelog.is_file() and re.search(
        rf"^## v{protocol}\.\d+\.\d+",
        changelog.read_text(encoding="utf-8", errors="replace"),
        re.M,
    )
    if pending:
        return [], [
            f"protocol v{protocol} release pending: CHANGELOG.md carries a v{protocol} section but no "
            f"v{protocol}.x tag exists — complete the authorized release (doc-end Phase 5 retry exit).{stale}"
        ]
    return [
        f"HARNESS_VERSION {protocol} is ahead of the newest release tag {newest_tag}: unreleased "
        "protocol — cut the authorized release via doc-end Phase 5, or revert the bump." + stale
    ], []


def check_baseline(root: Path) -> list[str]:
    context = root / "docs" / "active-context.md"
    if not context.is_file():
        return []
    parsed = read_frontmatter(context)
    metadata = parsed[0] if parsed else {}
    baseline = metadata.get("doc_baseline_commit", "")
    if parsed and "doc_baseline_commit" in parsed[1]:
        return ["docs/active-context.md: duplicate frontmatter `doc_baseline_commit`"]
    if not baseline:
        return ["docs/active-context.md: missing frontmatter `doc_baseline_commit`"]
    if run_git(root, "rev-parse", "--is-inside-work-tree").returncode:
        return ["cannot validate doc baseline: repo is not a Git worktree"]
    if run_git(root, "cat-file", "-e", f"{baseline}^{{commit}}").returncode:
        return [f"docs/active-context.md: baseline commit `{baseline}` does not exist"]
    if run_git(root, "merge-base", "--is-ancestor", baseline, "HEAD").returncode:
        return [f"docs/active-context.md: baseline `{baseline}` is not an ancestor of HEAD"]
    return []


def check_living_context(root: Path) -> list[str]:
    """`docs/active-context.md` is a snapshot, so its only `##` sections are the
    canonical three. Any other one is the append-only-changelog drift the living
    context must never accumulate; the pruned narrative belongs in
    `docs/active-context-archive.md`, which this check deliberately ignores.

    Headings are the objective half of the shape contract. Narrative prose and
    "too long for what it says" need judgment and stay with the semantic critic.
    """
    context = root / "docs" / "active-context.md"
    if not context.is_file():
        return []
    errors: list[str] = []
    fenced = False
    for number, raw in enumerate(context.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            fenced = not fenced          # a `## ...` inside a code fence is content, not a heading
            continue
        if fenced or not line.startswith("## "):
            continue
        title = line[3:].strip()
        if title.lower() not in CONTEXT_SECTIONS:
            errors.append(
                f"docs/active-context.md:{number}: section `{title}` is not one of "
                "`State now` / `Unresolved` / `Next` — current material belongs folded "
                "into one of those, historical material in docs/active-context-archive.md"
            )
    return errors


def sub_repo_index(root: Path, name: str) -> Path | None:
    """A sub-repo's index file, honouring its own profile when it has one.

    Most sub-repos have no `docs/.doc-profile` at all, which is exactly why this
    advisory is enforced from the meta-repo: `AGENTS.md` is the v6 fallback.
    """
    base = root / name
    if not base.is_dir():
        return None
    index_name = "AGENTS.md"
    try:
        profile = (base / "docs" / ".doc-profile").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        profile = ""
    for raw in profile.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line.startswith("index_file") and "=" in line:
            candidate = line.split("=", 1)[1].strip()
            if candidate:
                index_name = candidate
    idx = base / index_name
    return idx if idx.is_file() else None


def check_orientation_heads(root: Path, index_file: str) -> list[str]:
    """ADVISORY — name every sub-repo index whose head is not marked.

    Defensive throughout, like the other advisories: it must never take the gate
    down. A sub-repo whose index is missing or unreadable is skipped in silence,
    because that is INVENTORY DRIFT's finding to report and saying it twice in
    two different vocabularies helps nobody.
    """
    missing: list[str] = []
    try:
        names = sorted(canonical_repo_dirs(root, index_file) - {"docs"})
    except (OSError, UnicodeDecodeError):
        return []
    for name in names:
        idx = sub_repo_index(root, name)
        if idx is None:
            continue
        try:
            text = idx.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if ORIENTATION_MARKER in text:
            continue
        missing.append(
            f"{idx.relative_to(root)}: no orientation head — a session must read "
            f"the whole index to learn the stack, the entry points and the build "
            f"command (close the head with `{ORIENTATION_MARKER}`)"
        )
    return missing


def check_inventory(root: Path, index_file: str, ignore: set[str]) -> list[str]:
    errors: list[str] = []
    canonical = canonical_repo_dirs(root, index_file)
    if not canonical:
        return [f"meta mode requires a non-empty `## Services` table in {index_file}"]
    on_disk = {d.name for d in root.iterdir() if is_independent_repo(d) and d.name not in ignore}
    for repo in sorted(on_disk - canonical):
        errors.append(
            f"repo `{repo}/` is checked out under the repo root but is MISSING from "
            f"{index_file}'s `## Services` table (add it, or list it in inventory_ignore)"
        )
    for name in sorted(canonical):
        if not (root / name).exists():
            errors.append(
                f"{index_file} `## Services` lists `{name}/` but that directory does not exist (stale row)"
            )
    return errors


def check_no_dup_index(root: Path, index_file: str) -> list[str]:
    """README.md / docs/README.md must not carry a repo-inventory TABLE."""
    errors: list[str] = []
    repos = canonical_repo_dirs(root, index_file) - {"docs"}
    if not repos:
        return errors
    for rel in ("README.md", "docs/README.md"):
        doc = root / rel
        if not doc.exists():
            continue
        block: list[str] = []

        def flush(block: list[str]) -> None:
            joined = "\n".join(block)
            hits = {r for r in repos if re.search(rf"\b{re.escape(r)}\b", joined)}
            if len(hits) >= 3:
                errors.append(
                    f"{rel}: a markdown table lists {len(hits)} repos "
                    f"({', '.join(sorted(hits))}) — the repo inventory belongs ONLY in "
                    f"{index_file}; replace with a pointer"
                )

        for ln in doc.read_text(encoding="utf-8").splitlines():
            if ln.lstrip().startswith("|"):
                block.append(ln)
            elif block:
                flush(block)
                block = []
        if block:
            flush(block)
    return errors


def startup_facts(root: Path, prof: dict[str, str]) -> dict:
    context = root / "docs/active-context.md"
    parsed = read_frontmatter(context) if context.is_file() else None
    baseline = (parsed[0] if parsed else {}).get("doc_baseline_commit", "")
    valid = bool(baseline) and not check_baseline(root)
    drift = None
    git_errors = []
    if valid:
        result = run_git(root, "rev-list", "--count", "--full-history", f"{baseline}..HEAD", "--", ".", ":(exclude)docs/**", f":(exclude){prof['index_file']}")
        if result.returncode:
            git_errors.append(result.stderr.strip())
        else:
            drift = int(result.stdout.strip())
    state = run_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    changes = []
    records = iter(state.stdout.split("\0"))
    for entry in records:
        if not entry:
            continue
        item = {"status": entry[:2], "path": entry[3:]}
        if "R" in entry[:2] or "C" in entry[:2]:
            item["from"] = next(records, "")
        changes.append(item)
    for result in (state,):
        if result.returncode:
            git_errors.append(result.stderr.strip())
    plans = []
    for path in sorted((root / "docs/execution-plans").rglob("*.md")):
        parsed = read_frontmatter(path)
        status = (parsed[0] if parsed else {}).get("status", "unknown").lower()
        if not parsed or "status" in parsed[1] or status not in PLAN_STATUSES:
            status = "unknown"
        if status not in {"completed", "superseded"}:
            plans.append({"path": path.relative_to(root).as_posix(), "status": status})
    issues = []
    for path in sorted((root / "docs/known-issues").glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        parsed = read_frontmatter(path)
        status = (parsed[0] if parsed else {}).get("status", "unknown").lower()
        if not parsed or "status" in parsed[1]:
            status = "unknown"
        if status != "fixed":
            issues.append({"path": path.relative_to(root).as_posix(), "status": status if status in VALID_ISSUE_STATUSES else "unknown"})
    return {
        "baseline": {"commit": baseline or None, "valid": valid, "content_drift_commits": drift},
        "working_tree": {"dirty": bool(changes), "staged": sum(c["status"][0] not in " ?" for c in changes), "unstaged": sum(c["status"][1] not in " ?" for c in changes), "untracked": sum(c["status"] == "??" for c in changes)},
        "open_plans": plans, "open_issues": issues,
        "git_errors": git_errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Documentation integrity gate (mrcall-ai-kit).")
    ap.add_argument("--repo", help="repo root (default: git toplevel, else cwd)")
    ap.add_argument("--startup", action="store_true", help="include compact startup facts")
    ap.add_argument("--json", action="store_true", help="emit structured diagnostics")
    ap.add_argument("--completion", choices=("init", "attest", "snapshot", "mechanical", "focused", "result", "check", "recover", "finalize"), help="explicit mutating-task evidence action; never required by startup alone")
    ap.add_argument("--task", help="worktree-local completion task ID")
    ap.add_argument("--input", help="JSON input or actual review envelope for completion action")
    ap.add_argument("--context-id", help="caller attestation identifying currently available lead context")
    ap.add_argument("--phase", choices=("pre-review",), help="check all obligations except final-review")
    args = ap.parse_args()
    if args.completion:
        if args.startup:
            ap.error("--startup and --completion are separate operations")
        import importlib.util
        spec = importlib.util.spec_from_file_location("doc_evidence", Path(__file__).resolve().with_name("doc-evidence.py"))
        evidence = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evidence)
        return evidence.main(args, sys.modules[__name__])

    root = repo_root(args.repo)
    prof, profile_errors, _ = read_profile(root)
    index_file = prof["index_file"]
    harness_file = prof["index_file"]
    meta = prof["mode"].lower() == "meta"
    ignore = {s.strip() for s in prof["inventory_ignore"].split(",") if s.strip()}

    try:
        index_max_lines = int(prof["index_max_lines"])
    except ValueError:
        index_max_lines = 0
    try:
        doc_max_lines = int(prof["doc_max_lines"])
    except ValueError:
        doc_max_lines = 0
    groups = [
        ("PROFILE", profile_errors),
        ("DEAD LINKS", check_dead_links(root, index_file, harness_file)),
        ("DOC SCOPE", check_doc_scopes(root, index_file, harness_file)),
        ("HARNESS TEMPLATE", check_harness_template(root, harness_file)),
        ("THIN INDEX", check_index_thin(root, index_file, index_max_lines)),
        ("PLAN STATUS", check_plan_statuses(root)),
        ("SESSION STATUS", check_session_statuses(root)),
        ("BASELINE", check_baseline(root)),
        ("LIVING CONTEXT", check_living_context(root)),
    ]
    protocol_errors, protocol_advisories = check_protocol_release(root)
    groups.append(("PROTOCOL RELEASE", protocol_errors))
    if meta:
        groups.append(("INVENTORY DRIFT", check_inventory(root, index_file, ignore)))
        groups.append(("DUPLICATE INDEX", check_no_dup_index(root, index_file)))

    # Advisories, deliberately outside `groups`: they must never change the exit code.
    oversized = check_doc_sizes(root, index_file, harness_file, doc_max_lines)
    undated = check_trace_naming(root)
    open_sessions = check_open_sessions(root)
    unstated_issues = check_unstated_issues(root)
    unoriented = check_orientation_heads(root, index_file) if meta else []

    facts = startup_facts(root, prof) if args.startup else {}
    if facts.get("git_errors"):
        groups.append(("STARTUP GIT", facts["git_errors"]))
    failed = [(name, errs) for name, errs in groups if errs]
    if args.json or args.startup:
        result = {
            "harness_version": HARNESS_VERSION,
            "profile_version": prof.get("harness_version"),
            "mode": prof["mode"],
            "indexed_docs": len(index_docs(root, index_file, harness_file)),
            "mechanical_gate": "failed" if failed else "clean",
            "violations": {name: errors for name, errors in failed},
            "advisories": {name: warnings for name, warnings in (("oversized", oversized), ("undated_traces", undated), ("open_sessions", open_sessions), ("unstated_issues", unstated_issues), ("unoriented_indexes", unoriented), ("protocol_release", protocol_advisories)) if warnings},
            **facts,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        else:
            print(f"doc-check: MECHANICAL GATE {result['mechanical_gate'].upper()} — harness v{HARNESS_VERSION}; {result['indexed_docs']} docs indexed")
            for key, value in result.items():
                if key not in {"harness_version", "indexed_docs", "mechanical_gate"}:
                    print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        return 1 if failed else 0
    if not failed:
        print(
            f"doc-check: MECHANICAL GATE CLEAN — {root.name} "
            f"({'meta' if meta else 'leaf'} mode, harness v{HARNESS_VERSION})"
        )
    else:
        print("doc-check: MECHANICAL GATE FAILED")
        print("violations:")
        for name, errs in failed:
            print(f"  [{name}]")
            for e in errs:
                print(f"    - {e}")
    if oversized:
        print(f"advisory — {len(oversized)} oversized doc(s), NOT a gate failure:")
        for warning in oversized:
            print(f"    - {warning}")
    if undated:
        print(f"advisory — {len(undated)} undated work-trace file(s), NOT a gate failure:")
        for warning in undated:
            print(f"    - {warning}")
    if open_sessions:
        print(f"advisory — {len(open_sessions)} open session file(s), NOT a gate failure:")
        for warning in open_sessions:
            print(f"    - {warning}")
    if unstated_issues:
        print(
            f"advisory — {len(unstated_issues)} known issue(s) without a usable "
            "`status:`, NOT a gate failure:"
        )
        for warning in unstated_issues:
            print(f"    - {warning}")
    if unoriented:
        print(
            f"advisory — {len(unoriented)} sub-repo index(es) without an "
            f"orientation head, NOT a gate failure:"
        )
        for warning in unoriented:
            print(f"    - {warning}")
    if protocol_advisories:
        print("advisory — protocol/release invariant, NOT a gate failure:")
        for warning in protocol_advisories:
            print(f"    - {warning}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
