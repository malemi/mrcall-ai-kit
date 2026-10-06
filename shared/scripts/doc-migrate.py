#!/usr/bin/env python3
"""Inspect, stage, apply, or roll back an explicit AGENTS-only v9 migration."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid

SCRIPT = Path(__file__).resolve()
SPEC = importlib.util.spec_from_file_location("doc_check", SCRIPT.with_name("doc-check.py"))
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
OWNED = ("AGENTS.md", "CLAUDE.md", "docs/.doc-profile")
SCOPES = {"explanation", "development", "documentation", "brief", "review", "fastpath", "startup"}
LIMIT = "Compatibility is a finite observed configuration policy plus caller attestation; artifact hashes do not authenticate runtime behavior. Whole-lifecycle bypass remains possible."


class Refusal(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(path):
    for item in (path, *path.parents):
        if item.is_symlink():
            raise Refusal(f"symlink path refused: {item}")
    if path.exists() and not path.is_file():
        raise Refusal(f"file collision: {path}")


def snapshot(path):
    safe_path(path)
    if not path.exists():
        return None
    data = path.read_bytes()
    return {"base64": base64.b64encode(data).decode("ascii"), "mode": stat.S_IMODE(path.stat().st_mode), "sha256": digest(data)}


def encoded(data, mode=0o644):
    return {"base64": base64.b64encode(data).decode("ascii"), "mode": mode, "sha256": digest(data)}


def gitdir(root):
    result = CHECK.run_git(root, "rev-parse", "--absolute-git-dir")
    if result.returncode:
        raise Refusal("a Git worktree with an existing commit is required")
    if CHECK.run_git(root, "rev-parse", "--verify", "HEAD").returncode:
        raise Refusal("a Git worktree with an existing commit is required")
    top = CHECK.run_git(root, "rev-parse", "--show-toplevel")
    if top.returncode or Path(top.stdout.strip()).resolve() != root:
        raise Refusal("--repo must name the Git worktree root")
    return str(Path(result.stdout.strip()).resolve())


def instruction_files(root):
    candidates = {Path.home() / ".claude/CLAUDE.md", root / "CLAUDE.local.md"}
    for parent in root.parents:
        candidates.update((parent / "CLAUDE.md", parent / "CLAUDE.local.md"))
    result = []
    for path in sorted(candidates):
        if path.exists() or path.is_symlink():
            if not path.is_file():
                raise Refusal(f"unreadable instruction file: {path}")
            result.append({"path": str(path), "sha256": digest(path.read_bytes())})
    return result


def compatibility(root, filename, observed):
    if not filename:
        raise Refusal("compatibility evidence is required; inspect reports current instruction_files for the attestation")
    path = Path(filename)
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("repo") != str(root):
        raise Refusal("compatibility evidence schema or repository binding does not match")
    if data.get("instruction_files") != observed:
        raise Refusal("compatibility instruction_files differ from current ancestor/local/user observations")
    requested = data.get("required_scopes", ["startup", "documentation"])
    if not isinstance(requested, list) or not requested or any(s not in SCOPES for s in requested):
        raise Refusal("invalid compatibility required_scopes")
    required = set(requested) | {"startup", "documentation"}
    clients = data.get("clients")
    if not isinstance(clients, list) or not clients:
        raise Refusal("compatibility requires evidence for every intended client")
    outcomes = []
    for client in clients:
        if not isinstance(client, dict):
            raise Refusal("each compatibility client must be an object")
        identity = (client.get("client"), client.get("version"), client.get("mode"))
        config = client.get("configuration")
        if identity == ("codex", "0.160.0", "native-app-server"):
            allowed = SCOPES
            expected = {"ambient": "tested"}
        elif identity == ("opencode", "1.18.32", "run-explicit-dir"):
            allowed = SCOPES - {"development", "fastpath"}
            expected = {"ambient": "tested", "explicit_dir": True}
        elif client.get("client") == "claude":
            raise Refusal("Claude 2.1.280 print migration unsupported: observed startup/closure failed under ambient guard/router; ancestor CLAUDE and ancestor/same-directory CLAUDE.local suppress default AGENTS; combined instruction setting is loading-only tested; DISABLE_TELEMETRY=1 lost AGENTS. User CLAUDE presence alone does not establish suppression.")
        else:
            raise Refusal(f"unsupported or untested client/version/mode: {identity}")
        scopes = client.get("scopes")
        if config != expected or client.get("instruction_loading") != "observed" or client.get("lifecycle") != "pass":
            raise Refusal(f"missing or failing measured configuration evidence: {identity}")
        if not isinstance(scopes, list) or any(s not in allowed for s in scopes) or not required <= set(scopes):
            raise Refusal(f"unsupported or missing required scopes for {identity}; supported scopes: {', '.join(sorted(allowed))}; other paths are untested")
        evidence = client.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise Refusal(f"missing result artifacts for {identity}")
        for item in evidence:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise Refusal("each evidence reference must contain an absolute path and sha256")
            artifact = Path(item["path"])
            if not artifact.is_absolute() or not artifact.is_file() or digest(artifact.read_bytes()) != item.get("sha256"):
                raise Refusal(f"missing or changed compatibility result artifact: {artifact}")
        outcomes.append({"client": identity[0], "version": identity[1], "mode": identity[2], "scopes": sorted(set(scopes)), "untested_scopes": sorted(SCOPES - allowed)})
    return {"sha256": digest(path.read_bytes()), "clients": outcomes, "required_scopes": sorted(required), "limit": LIMIT}


def profile_bytes(root, mode):
    path = root / "docs/.doc-profile"
    safe_path(path)
    if not path.exists():
        if mode is None:
            raise Refusal("fresh bootstrap requires --mode leaf|meta and prepared scoped AGENTS/docs routing files")
        return None, f"harness_version = 9\nschema_version = 1\nmode = {mode}\nindex_file = AGENTS.md\n".encode()
    source = path.read_bytes()
    values = {}
    for line in source.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or key in values or key not in CHECK.KNOWN_PROFILE_KEYS:
            raise Refusal("malformed, duplicate, or unknown profile key")
        values[key] = value
    version = values.get("harness_version")
    if version not in {"6", "7", "8", "9"}:
        raise Refusal("only exact known v6/v7/v8 layouts or v9 reapplication are supported")
    if values.get("index_file") != "AGENTS.md" or (version != "9" and values.get("harness_file") != "CLAUDE.md"):
        raise Refusal("unsupported legacy ownership collision; expected project AGENTS.md and managed CLAUDE.md")
    if values.get("mode") not in {"leaf", "meta"} or (mode and mode != values["mode"]):
        raise Refusal("--mode must agree with the existing valid profile mode")
    if version == "9" and "harness_file" in values:
        raise Refusal("v9 profile must not contain harness_file")
    lines = []
    for line in source.splitlines(keepends=True):
        key = line.split(b"=", 1)[0].strip()
        if key == b"harness_file":
            continue
        if key == b"harness_version":
            ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
            line = b"harness_version = 9" + ending
        lines.append(line)
    return int(version), b"".join(lines)


def proposed(root, mode):
    for rel in OWNED:
        safe_path(root / rel)
    for rel in ("docs/README.md", "docs/active-context.md"):
        safe_path(root / rel)
        if not (root / rel).is_file():
            raise Refusal(f"prepare required scoped routing document before bootstrap: {rel}")
    for path in (root / "docs").rglob("*"):
        if path.is_symlink():
            raise Refusal(f"symlink documentation path refused: {path}")
    for rel in ("CLAUDE.local.md", ".claude/rules/doc-harness.md"):
        if (root / rel).exists() or (root / rel).is_symlink():
            raise Refusal(f"foreign or obsolete instruction collision preserved: {rel}")
    version, profile = profile_bytes(root, mode)
    template = CHECK.find_harness_template()
    if template is None:
        raise Refusal("canonical AGENTS.block.md is not installed")
    legacy = template.parent / "legacy"
    before = {rel: snapshot(root / rel) for rel in OWNED}
    if before["AGENTS.md"] is None:
        raise Refusal("prepare project AGENTS.md with its scope before bootstrap")
    agents = (root / "AGENTS.md").read_bytes()
    if version in {6, 7, 8}:
        known = list((legacy / f"v{version}").glob("CLAUDE*.md"))
        if before["CLAUDE.md"] is None or not any((root / "CLAUDE.md").read_bytes() == p.read_bytes() for p in known):
            raise Refusal("customized or unrecognized legacy CLAUDE.md preserved; no migration writes")
    elif before["CLAUDE.md"] is not None:
        raise Refusal("foreign CLAUDE.md preserved; single-entry compatibility conflict")
    old = CHECK.managed_block_span(agents, b"codex-agents")
    if old:
        legacy_block = legacy / "codex-agents.block.md"
        if not legacy_block.is_file() or agents[old[0]:old[1]] != legacy_block.read_bytes().rstrip(b"\n"):
            raise Refusal("customized legacy Codex block preserved")
        agents = agents[:old[0]] + agents[old[1]:]
    span = CHECK.managed_block_span(agents)
    block = template.read_bytes()
    if span:
        if agents[span[0]:span[1]] != block.rstrip(b"\n"):
            raise Refusal("customized or stale managed delivery block preserved")
    else:
        agents = block + b"\n" + agents
    after = {"AGENTS.md": encoded(agents, before["AGENTS.md"]["mode"]), "CLAUDE.md": None,
             "docs/.doc-profile": encoded(profile, before["docs/.doc-profile"]["mode"] if before["docs/.doc-profile"] else 0o644)}
    changes = [{"path": rel, "before": before[rel], "after": after[rel]} for rel in OWNED if before[rel] != after[rel]]
    return version, changes


def publication_preflight(root, changes):
    for change in changes:
        path = root / change["path"]
        parent = path.parent
        if not os.access(parent, os.W_OK | os.X_OK, effective_ids=True):
            raise Refusal(f"publication requires write and search access to directory: {parent}")
        if os.statvfs(parent).f_flag & os.ST_RDONLY:
            raise Refusal(f"publication requires a writable filesystem: {parent}")
        directory = parent.stat()
        if directory.st_mode & stat.S_ISVTX and path.exists() and os.geteuid() not in {0, directory.st_uid, path.stat().st_uid}:
            raise Refusal(f"publication cannot replace another owner's file in sticky directory: {path}")


def validate_stage(root, changes, git_directory):
    with tempfile.TemporaryDirectory(prefix="doc-migrate-stage-") as temp:
        stage = Path(temp) / "repo"
        shutil.copytree(root, stage, symlinks=True, ignore=lambda directory, names: [".git"] if Path(directory) == root else [])
        (stage / ".git").write_text(f"gitdir: {git_directory}\n")
        for change in changes:
            path = stage / change["path"]
            if change["after"] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(base64.b64decode(change["after"]["base64"]))
        env = dict(os.environ, MRCALL_DOC_HARNESS_TEMPLATE=str(CHECK.find_harness_template()))
        result = subprocess.run([sys.executable, str(SCRIPT.with_name("doc-check.py")), "--repo", str(stage), "--json"], capture_output=True, text=True, env=env)
        if result.returncode:
            raise Refusal(f"staged v9 mechanical validation failed: {result.stdout.strip()} {result.stderr.strip()}")
        return json.loads(result.stdout)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path, data, mode, temporary=None):
    safe_path(path)
    if temporary is None:
        fd, temporary = tempfile.mkstemp(prefix=".doc-migrate-", dir=path.parent)
    else:
        safe_path(temporary)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            if os.environ.get("MRCALL_DOC_MIGRATE_TEST_CRASH_DURING") == path.name:
                handle.write(data[:max(1, len(data) // 2)])
                handle.flush()
                os.fsync(handle.fileno())
                os._exit(87)
            handle.write(data)
            os.fchmod(handle.fileno(), mode)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish(path, state, temporary=None):
    if state is None:
        safe_path(path)
        path.unlink(missing_ok=True)
        sync_dir(path.parent)
    else:
        atomic_write(path, base64.b64decode(state["base64"]), state["mode"], temporary)


def manifest_write(transaction, manifest):
    atomic_write(transaction / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode(), 0o600)


def transaction_path(root, git_directory, value):
    if not value:
        raise Refusal("apply and rollback require --transaction outside the repository or under its worktree Git directory")
    path = Path(value).absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise Refusal(f"symlink transaction path refused: {item}")
    path = path.resolve()
    if path == Path(git_directory) or path == root or (path.is_relative_to(root) and not path.is_relative_to(Path(git_directory))):
        raise Refusal("transaction must be outside repository content or below its worktree Git directory")
    if not path.parent.is_dir():
        raise Refusal("transaction parent must already exist")
    return path


def rollback(root, transaction, git_directory):
    safe_path(transaction / "manifest.json")
    manifest = json.loads((transaction / "manifest.json").read_text())
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("repo") != str(root) or manifest.get("git_dir") != git_directory:
        raise Refusal("transaction schema/repository/worktree mismatch")
    paths = []
    for change in manifest["changes"]:
        rel = change["path"]
        if rel not in OWNED or rel in paths:
            raise Refusal("invalid transaction path")
        paths.append(rel)
        temporary = Path(change.get("temporary", ""))
        if temporary.parent != Path(rel).parent or not temporary.name.startswith(".doc-migrate-") or len(temporary.name) != len(".doc-migrate-") + 32:
            raise Refusal("invalid transaction temporary path")
        if any(c not in "0123456789abcdef" for c in temporary.name[len(".doc-migrate-"):]):
            raise Refusal("invalid transaction temporary name")
        safe_path(root / temporary)
        for key in ("before", "after"):
            value = change[key]
            if value is not None:
                data = base64.b64decode(value["base64"], validate=True)
                if digest(data) != value["sha256"] or not isinstance(value["mode"], int) or not 0 <= value["mode"] <= 0o7777:
                    raise Refusal("invalid transaction snapshot")
        try:
            current = snapshot(root / rel)
        except OSError:
            continue
        if current not in (change["before"], change["after"]):
            raise Refusal(f"rollback refuses unrelated post-transaction edit: {rel}")
    failures = []
    restored = []
    manifest["state"] = "rolling_back"
    try:
        manifest_write(transaction, manifest)
    except OSError as exc:
        failures.append(f"transaction journal: {exc}")
    for change in reversed(manifest["changes"]):
        path = root / change["path"]
        temporary = root / change["temporary"]
        try:
            current = snapshot(path)
            if current not in (change["before"], change["after"]):
                raise Refusal(f"rollback refuses unrelated post-transaction edit: {change['path']}")
            if temporary.exists():
                temporary.unlink()
                sync_dir(temporary.parent)
            if current != change["before"]:
                publish(path, change["before"], temporary)
            restored.append(change["path"])
        except (OSError, Refusal) as exc:
            failures.append(f"{change['path']}: {exc}")
    manifest["state"] = "rollback_incomplete" if failures else "rolled_back"
    manifest["rollback_errors"] = failures.copy()
    try:
        manifest_write(transaction, manifest)
    except OSError as exc:
        failures.append(f"transaction journal: {exc}")
    if failures:
        raise Refusal("rollback incomplete; recoverable paths restored: " + ", ".join(restored) + "; remaining failures: " + "; ".join(failures))
    return {"state": "rolled_back", "transaction": str(transaction), "restored": paths}


def apply(root, transaction, git_directory, changes, compat):
    if not changes:
        return {"state": "unchanged", "changes": []}
    if transaction.exists():
        raise Refusal("transaction already exists; inspect its manifest or explicitly roll back")
    publication_preflight(root, changes)
    for change in changes:
        if snapshot(root / change["path"]) != change["before"]:
            raise Refusal(f"file changed during preflight: {change['path']}")
    for change in changes:
        change["temporary"] = str(Path(change["path"]).with_name(".doc-migrate-" + uuid.uuid4().hex))
        if (root / change["temporary"]).exists():
            raise Refusal("temporary path collision")
    transaction.mkdir(mode=0o700)
    manifest = {"schema_version": 1, "repo": str(root), "git_dir": git_directory, "state": "prepared", "compatibility": compat, "changes": changes, "completed_steps": [], "created_directories": []}
    manifest_write(transaction, manifest)
    try:
        for change in changes:
            if snapshot(root / change["path"]) != change["before"]:
                raise Refusal(f"file changed during migration: {change['path']}")
            publish(root / change["path"], change["after"], root / change["temporary"])
            manifest["completed_steps"].append(change["path"])
            manifest["state"] = "applying"
            manifest_write(transaction, manifest)
            if os.environ.get("MRCALL_DOC_MIGRATE_TEST_CRASH_AFTER") == change["path"]:
                os._exit(86)
            if os.environ.get("MRCALL_DOC_MIGRATE_TEST_FAIL_AFTER") == change["path"]:
                raise Refusal("injected migration write failure")
        manifest["state"] = "applied"
        manifest_write(transaction, manifest)
    except Exception as original:
        try:
            rollback(root, transaction, git_directory)
        except Exception as recovery:
            raise Refusal(f"migration failed: {original}; recovery failed: {recovery}") from original
        raise
    return {"state": "applied", "transaction": str(transaction), "changes": [c["path"] for c in changes]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "inspect and dry-run never write repository content or save transactions. "
        "inspect without evidence reports ready=false and current instruction_files. "
        "Fresh bootstrap requires prepared scoped AGENTS.md, docs/README.md, and "
        "docs/active-context.md plus --mode. Existing v6/v7/v8 profiles preserve mode "
        "and optional settings. apply requires a new external (or worktree Gitdir) "
        "transaction directory and publishes the v9 profile last. rollback restores "
        "exact bytes/modes, skips unchanged files, and refuses later edits. Publication "
        "requires writable/searchable parent directories; rollback attempts all recoverable "
        "paths and reports any remaining I/O failures. Compatibility schema 1 requires "
        "repo realpath, instruction_files [{path,sha256}], optional required_scopes "
        "(default startup+documentation), and clients [{client,version,mode,scopes," 
        "instruction_loading:'observed',lifecycle:'pass',configuration,evidence:[{path,sha256}]}]. "
        "Every client must cover startup+documentation and required_scopes. Observed policy: "
        "Codex 0.160.0 native-app-server configuration {ambient:'tested'}; "
        "OpenCode 1.18.32 run-explicit-dir {ambient:'tested',explicit_dir:true}, "
        "development/fastpath untested. Claude 2.1.280 print startup/closure unsupported; "
        "combined-setting loading alone is insufficient. " + LIMIT))
    parser.add_argument("action", choices=("inspect", "dry-run", "apply", "rollback"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--mode", choices=("leaf", "meta"))
    parser.add_argument("--compatibility", help="schema 1 scoped compatibility evidence and configuration attestation JSON")
    parser.add_argument("--transaction", help="new saved transaction directory outside repository content")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo).absolute()
    result = {"action": args.action, "repo": str(root), "ready": False, "reasons": [], "limit": LIMIT}
    try:
        for item in (root, *root.parents):
            if item.is_symlink():
                raise Refusal(f"symlink repository path refused: {item}")
        root = root.resolve()
        result["repo"] = str(root)
        directory = gitdir(root)
        if args.action == "rollback":
            result.update(rollback(root, transaction_path(root, directory, args.transaction), directory))
            result["ready"] = True
        else:
            observed = instruction_files(root)
            result["instruction_files"] = observed
            result["existing_paths"] = [rel for rel in OWNED if (root / rel).exists() or (root / rel).is_symlink()]
            version, changes = proposed(root, args.mode)
            result["from_version"] = version
            result["to_version"] = 9
            result["changes"] = [c["path"] for c in changes]
            compat = compatibility(root, args.compatibility, observed)
            result["compatibility"] = compat
            publication_preflight(root, changes)
            result["mechanical_validation"] = validate_stage(root, changes, directory)
            result["ready"] = True
            if args.action == "apply":
                result.update(apply(root, transaction_path(root, directory, args.transaction), directory, changes, compat))
    except (Refusal, ValueError, OSError, KeyError, TypeError) as exc:
        result["ready"] = False
        result["reasons"].append(str(exc))
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"doc-migrate: {args.action.upper()} {'READY' if result['ready'] else 'REFUSED'}")
        for key, value in result.items():
            if key not in {"action", "ready"}:
                print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
