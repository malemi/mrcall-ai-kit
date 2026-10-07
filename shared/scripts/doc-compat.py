#!/usr/bin/env python3
"""Prepare, collect, and report explicit v9 client compatibility evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile

SCRIPT = Path(__file__).resolve()
SCOPES = {"startup", "documentation"}
RAW_KEYS = ("stdout", "stderr", "events", "diff", "untracked", "gitdir", "gitdir_diff")
LIMIT = (
    "Compatibility is a finite observed configuration policy plus caller attestation; "
    "artifact hashes do not authenticate runtime behavior. Whole-lifecycle bypass remains possible."
)


class Refusal(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: Path | str) -> Path:
    p = Path(path).absolute()
    for item in (p, *p.parents):
        if item.is_symlink():
            raise Refusal(f"symlink path refused: {item}")
    if p.exists() and not (p.is_file() or p.is_dir()):
        raise Refusal(f"file collision: {p}")
    return p


def _load_doc_check():
    if "doc_check" in sys.modules:
        return sys.modules["doc_check"]
    check_path = SCRIPT.with_name("doc-check.py")
    if not check_path.is_file():
        kit_home = os.environ.get("MRCALL_KIT_HOME")
        if kit_home and (Path(kit_home) / "doc-check.py").is_file():
            check_path = Path(kit_home) / "doc-check.py"
    if not check_path.is_file():
        raise Refusal(f"doc-check.py not found next to {SCRIPT}")
    spec = importlib.util.spec_from_file_location("doc_check", check_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["doc_check"] = module
    spec.loader.exec_module(module)
    return module


def _load_doc_migrate():
    if "doc_migrate" in sys.modules:
        return sys.modules["doc_migrate"]
    migrate_path = SCRIPT.with_name("doc-migrate.py")
    if not migrate_path.is_file():
        kit_home = os.environ.get("MRCALL_KIT_HOME")
        if kit_home and (Path(kit_home) / "doc-migrate.py").is_file():
            migrate_path = Path(kit_home) / "doc-migrate.py"
    if not migrate_path.is_file():
        raise Refusal(f"doc-migrate.py not found next to {SCRIPT}")
    spec = importlib.util.spec_from_file_location("doc_migrate", migrate_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["doc_migrate"] = module
    spec.loader.exec_module(module)
    return module


def check_environment_overrides(root: Path) -> None:
    if "OPENCODE_CONFIG_CONTENT" in os.environ:
        raise Refusal("unsupported OPENCODE_CONFIG_CONTENT environment override")
    if "OPENCODE_CONFIG_DIR" in os.environ:
        raise Refusal("unsupported OPENCODE_CONFIG_DIR environment override")
    for p in [root, *root.parents]:
        opencode_dir = p / ".opencode"
        if opencode_dir.exists() or opencode_dir.is_symlink():
            raise Refusal(f"unsupported target/ancestor .opencode override: {opencode_dir}")


def environment_files(root: Path | str) -> list[dict[str, str]]:
    root_path = safe_path(root).resolve()
    check_environment_overrides(root_path)

    candidates: set[Path] = set()
    for p in [root_path, *root_path.parents]:
        candidates.add(p / "AGENTS.md")
        candidates.add(p / "CLAUDE.md")
        candidates.add(p / "CLAUDE.local.md")
        for name in ("opencode.json", "opencode.jsonc"):
            config = p / name
            if config.exists() or config.is_symlink():
                raise Refusal(f"unsupported target/ancestor OpenCode configuration (relative includes unknown): {config}")

    home = Path.home()
    candidates.add(home / ".claude" / "CLAUDE.md")
    candidates.add(home / ".codex" / "AGENTS.md")
    candidates.add(home / ".config" / "opencode" / "AGENTS.md")
    candidates.add(home / ".config" / "opencode" / "opencode.json")
    candidates.add(home / ".config" / "opencode" / "opencode.jsonc")

    opencode_config = os.environ.get("OPENCODE_CONFIG")
    if opencode_config:
        candidates.add(Path(opencode_config).expanduser())

    result = []
    for path in sorted(candidates, key=lambda p: str(p.resolve())):
        if path.exists() or path.is_symlink():
            if not path.is_file():
                raise Refusal(f"unreadable environment file: {path}")
            safe_path(path)
            data = path.read_bytes()
            result.append({"path": str(path.resolve()), "sha256": digest(data)})
    result.sort(key=lambda item: item["path"])
    return result


def get_kit_bound_inputs() -> list[dict[str, str]]:
    check_mod = _load_doc_check()
    block_template = check_mod.find_harness_template()
    if block_template is None or not block_template.is_file():
        raise Refusal("canonical AGENTS.block.md is not installed")

    migrate_path = SCRIPT.with_name("doc-migrate.py")
    if not migrate_path.is_file():
        kit_home = os.environ.get("MRCALL_KIT_HOME")
        if kit_home and (Path(kit_home) / "doc-migrate.py").is_file():
            migrate_path = Path(kit_home) / "doc-migrate.py"
    if not migrate_path.is_file():
        raise Refusal("doc-migrate.py not found")

    checker_path = SCRIPT.with_name("doc-check.py")
    if not checker_path.is_file():
        kit_home = os.environ.get("MRCALL_KIT_HOME")
        if kit_home and (Path(kit_home) / "doc-check.py").is_file():
            checker_path = Path(kit_home) / "doc-check.py"
    if not checker_path.is_file():
        raise Refusal("doc-check.py not found")

    items = {
        "collector": SCRIPT,
        "migrate": migrate_path,
        "checker": checker_path,
        "block": block_template,
    }

    repo_shared = SCRIPT.parents[1]
    kit_dir = os.environ.get("MRCALL_KIT_DIR")
    home = Path.home()

    def resolve_workflow(name: str, rel_path: str, fallback_paths: list[Path]) -> Path:
        candidates = []
        if kit_dir and (Path(kit_dir) / "shared" / rel_path).is_file():
            candidates.append(Path(kit_dir) / "shared" / rel_path)
        if (repo_shared / rel_path).is_file():
            candidates.append(repo_shared / rel_path)
        for fb in fallback_paths:
            if fb.is_file():
                candidates.append(fb)
        if not candidates:
            raise Refusal(f"kit bound workflow {name} not found")
        return candidates[0]

    items["doc-create"] = resolve_workflow(
        "doc-create",
        "commands/doc-create.md",
        [
            home / ".config/opencode/commands/doc-create.md",
            home / ".claude/commands/doc-create.md",
            home / ".agents/skills/doc-create/WORKFLOW.md",
        ],
    )
    items["doc-start"] = resolve_workflow(
        "doc-start",
        "commands/doc-start.md",
        [
            home / ".config/opencode/commands/doc-start.md",
            home / ".claude/commands/doc-start.md",
            home / ".agents/skills/doc-start/WORKFLOW.md",
        ],
    )
    items["doc-end"] = resolve_workflow(
        "doc-end",
        "commands/doc-end.md",
        [
            home / ".config/opencode/commands/doc-end.md",
            home / ".claude/commands/doc-end.md",
            home / ".agents/skills/doc-end/WORKFLOW.md",
        ],
    )
    items["doc-critic"] = resolve_workflow(
        "doc-critic",
        "skills/doc-critic/SKILL.md",
        [
            home / ".config/opencode/skills/doc-critic/SKILL.md",
            home / ".claude/skills/doc-critic/SKILL.md",
            home / ".agents/skills/doc-critic/SKILL.md",
        ],
    )

    result = []
    for key in sorted(items.keys()):
        p = items[key].resolve()
        safe_path(p)
        result.append({"path": str(p), "sha256": digest(p.read_bytes())})
    result.sort(key=lambda item: item["path"])
    return result


def validate_output_path(output: Path, root: Path, git_directory: str, is_prepare: bool = False) -> Path:
    out = Path(output).absolute()
    safe_path(out)
    git_dir = Path(git_directory).resolve()
    resolved_root = root.resolve()
    resolved_out = out.resolve() if out.exists() else out

    if resolved_out == resolved_root or resolved_out.is_relative_to(resolved_root):
        raise Refusal("output directory must be outside target content")
    if resolved_out == git_dir or resolved_out.is_relative_to(git_dir):
        raise Refusal("output directory must be outside git directory")

    if is_prepare:
        if out.exists() and any(out.iterdir()):
            raise Refusal(f"output directory already exists and is not empty: {out}")
    else:
        if not out.is_dir():
            raise Refusal(f"output directory does not exist: {out}")
    return out


def snapshot_tree(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        info = path.lstat()
        mode = str(stat.S_IMODE(info.st_mode))
        if path.is_symlink():
            hashes[rel] = "symlink:" + mode + ":" + os.readlink(path)
        elif path.is_file():
            hashes[rel] = "file:" + mode + ":" + digest(path.read_bytes())
        elif path.is_dir():
            hashes[rel] = "directory:" + mode
        else:
            raise Refusal(f"unsupported tree entry: {path}")
    return hashes


def target_digest(root: Path, git_directory: str) -> str:
    return digest(json.dumps({"content": snapshot_tree(root), "gitdir": snapshot_tree(Path(git_directory))}, sort_keys=True).encode())


def read_preparation(output: Path) -> tuple[dict, Path]:
    prep_file = safe_path(output / "preparation.json")
    hash_file = safe_path(output / "preparation.sha256")
    if digest(prep_file.read_bytes()) != hash_file.read_text().strip():
        raise Refusal("preparation manifest hash mismatch")
    prep = json.loads(prep_file.read_bytes())
    if not isinstance(prep, dict) or prep.get("schema_version") != 1:
        raise Refusal("malformed preparation manifest")
    return prep, prep_file


def raw_artifacts(manifest: dict, output: Path) -> dict[str, str]:
    trials = manifest.get("trials")
    if not isinstance(trials, dict) or set(trials) != SCOPES:
        raise Refusal("collection must contain startup and documentation trials")
    artifacts = {}
    for trial in trials.values():
        if not isinstance(trial, dict) or trial.get("completed") is not True or trial.get("timed_out") is not False or type(trial.get("returncode")) is not int or trial["returncode"] != 0:
            raise Refusal("collection requires completed startup and documentation trials")
        for key in RAW_KEYS:
            path = safe_path(trial[f"{key}_path"])
            expected = trial[f"{key}_sha256"]
            if not path.is_relative_to(output / "raw") or not path.is_file() or digest(path.read_bytes()) != expected:
                raise Refusal(f"collected log modified or missing: {path}")
            artifacts[str(path)] = expected
    actual = {str(safe_path(p)) for p in (output / "raw").rglob("*") if p.is_file() or p.is_symlink()}
    if set(artifacts) != actual:
        raise Refusal("raw artifact inventory differs from collection")
    return artifacts


def prepare(root: Path, output: Path, client: str = "opencode") -> dict:
    if client == "codex":
        raise Refusal("Codex collection requires dedicated native-app-server mode; codex exec is not supported as native-app-server")
    if client != "opencode":
        raise Refusal(f"unsupported client: {client}")

    doc_migrate = _load_doc_migrate()
    check_mod = _load_doc_check()

    git_directory = doc_migrate.gitdir(root)
    validate_output_path(output, root, git_directory, is_prepare=True)

    doc_migrate.proposed(root, None)
    original_target_digest = target_digest(root, git_directory)

    orig_env = environment_files(root)
    orig_inst = doc_migrate.instruction_files(root)
    kit_inputs = get_kit_bound_inputs()

    output.mkdir(parents=True, exist_ok=True)
    fixtures_base = output / "fixtures"

    canonical_block = check_mod.find_harness_template().read_bytes().rstrip(b"\n")
    checker_script = SCRIPT.with_name("doc-check.py")
    if not checker_script.is_file():
        kit_home = os.environ.get("MRCALL_KIT_HOME")
        if kit_home and (Path(kit_home) / "doc-check.py").is_file():
            checker_script = Path(kit_home) / "doc-check.py"

    fixtures_info = {}
    root_rel = root.relative_to(root.anchor)

    for trial in ("startup", "documentation"):
        trial_base = fixtures_base / trial
        for parent in reversed(root.parents):
            if parent == root.anchor:
                continue
            p_rel = parent.relative_to(root.anchor)
            mirror_p = trial_base / p_rel
            for fname in ("AGENTS.md", "CLAUDE.md", "CLAUDE.local.md"):
                src_file = parent / fname
                if src_file.is_file():
                    safe_path(src_file)
                    mirror_p.mkdir(parents=True, exist_ok=True)
                    try:
                        (mirror_p / fname).write_bytes(src_file.read_bytes())
                    except OSError as exc:
                        raise Refusal(f"cannot reproduce instruction environment: {exc}")

        fixture_root = trial_base / root_rel
        fixture_root.mkdir(parents=True, exist_ok=True)
        docs_dir = fixture_root / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        guidance = b""
        if (root / "AGENTS.md").is_file():
            raw_agents = (root / "AGENTS.md").read_bytes()
            span = check_mod.managed_block_span(raw_agents)
            if span:
                raw_agents = raw_agents[:span[0]] + raw_agents[span[1]:]
            old_span = check_mod.managed_block_span(raw_agents, b"codex-agents")
            if old_span:
                raw_agents = raw_agents[:old_span[0]] + raw_agents[old_span[1]:]
            guidance = raw_agents.strip()

        if not guidance:
            guidance = b"# Project operating rules\n\n<!-- doc-scope:start -->\nScope: Fixture project routing and operating rules.\n<!-- doc-scope:end -->\n\nOrient on this repository and obey the project rules."
        elif b"<!-- doc-scope:start -->" not in guidance:
            guidance = b"<!-- doc-scope:start -->\nScope: Fixture project operating rules.\n<!-- doc-scope:end -->\n\n" + guidance

        fixture_agents = canonical_block + b"\n\n" + guidance + b"\n"
        (fixture_root / "AGENTS.md").write_bytes(fixture_agents)
        if (root / "CLAUDE.local.md").is_file():
            (fixture_root / "CLAUDE.local.md").write_bytes(safe_path(root / "CLAUDE.local.md").read_bytes())

        profile_bytes_content = b"harness_version = 9\nschema_version = 1\nmode = leaf\nindex_file = AGENTS.md\n"
        if (root / "docs/.doc-profile").is_file():
            source_profile = (root / "docs/.doc-profile").read_bytes()
            lines = []
            for line in source_profile.splitlines(keepends=True):
                key = line.split(b"=", 1)[0].strip()
                if key == b"harness_file":
                    continue
                if key == b"harness_version":
                    ending = b"\r\n" if line.endswith(b"\r\n") else b"\n" if line.endswith(b"\n") else b""
                    line = b"harness_version = 9" + ending
                lines.append(line)
            profile_bytes_content = b"".join(lines)
        (docs_dir / ".doc-profile").write_bytes(profile_bytes_content)

        if (root / "docs/README.md").is_file():
            (docs_dir / "README.md").write_bytes((root / "docs/README.md").read_bytes())
        else:
            (docs_dir / "README.md").write_bytes(b"# Fixture\n\n<!-- doc-scope:start -->\nScope: Fixture project routing.\n<!-- doc-scope:end -->\n\nIndex.\n")

        if (root / "app.py").is_file():
            (fixture_root / "app.py").write_bytes((root / "app.py").read_bytes())
        else:
            (fixture_root / "app.py").write_bytes(b'def main():\n    print("fixture app")\n\nif __name__ == "__main__":\n    main()\n')

        if trial == "startup":
            active_context_body = (
                b"# Active Context\n\n"
                b"<!-- doc-scope:start -->\nScope: Volatile state for fixture verification.\n<!-- doc-scope:end -->\n\n"
                b"## State now\nBaseline clean state ready for startup probe.\n\n"
                b"## Unresolved\nNone.\n\n"
                b"## Next\nRun read-only startup check.\n"
            )
        else:
            active_context_body = (
                b"# Active Context\n\n"
                b"<!-- doc-scope:start -->\nScope: Volatile state for fixture verification.\n<!-- doc-scope:end -->\n\n"
                b"## State now\nStale fixture state: status=pending_reconciliation.\n"
                b"Historical narrative: initial setup completed, historical details to archive.\n\n"
                b"## Unresolved\nHistorical narrative from setup remains to be archived.\n\n"
                b"## Next\nReconcile documentation and archive narrative.\n"
            )

        (docs_dir / "active-context.md").write_bytes(active_context_body)

        git_c = ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]
        subprocess.run(["git", "init", "-b", "main"], cwd=fixture_root, check=True, capture_output=True)
        subprocess.run([*git_c, "add", "."], cwd=fixture_root, check=True, capture_output=True)
        subprocess.run([*git_c, "commit", "-m", "fixture baseline commit"], cwd=fixture_root, check=True, capture_output=True)

        rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=fixture_root, check=True, capture_output=True, text=True)
        baseline_sha = rev.stdout.strip()

        final_active_context = f"---\ndoc_baseline_commit: {baseline_sha}\n---\n".encode("utf-8") + active_context_body
        (docs_dir / "active-context.md").write_bytes(final_active_context)
        subprocess.run([*git_c, "add", "docs/active-context.md"], cwd=fixture_root, check=True, capture_output=True)
        subprocess.run([*git_c, "commit", "-m", "record baseline commit"], cwd=fixture_root, check=True, capture_output=True)

        env = dict(os.environ, MRCALL_DOC_HARNESS_TEMPLATE=str(check_mod.find_harness_template()))
        check_res = subprocess.run(
            [sys.executable, str(checker_script), "--repo", str(fixture_root), "--startup", "--json"],
            capture_output=True,
            text=True,
            env=env,
        )
        if check_res.returncode != 0:
            raise Refusal(f"fixture v9 mechanical check failed: {check_res.stdout} {check_res.stderr}")

        fixtures_info[trial] = {
            "path": str(fixture_root.resolve()),
            "baseline_commit": baseline_sha,
            "initial_hashes": snapshot_tree(fixture_root),
        }

    prep_data = {
        "schema_version": 1,
        "target_digest": original_target_digest,
        "fixture_tree": snapshot_tree(fixtures_base),
        "repo": str(root.resolve()),
        "output": str(output.resolve()),
        "client": client,
        "environment_files": orig_env,
        "instruction_files": orig_inst,
        "kit_inputs": kit_inputs,
        "fixtures": fixtures_info,
        "scope_note": "Minimal fixture test of startup read-only and documentation-closure paths; application behavior and universal compliance are not measured.",
    }
    prep_file = output / "preparation.json"
    prep_file.write_text(json.dumps(prep_data, indent=2) + "\n")
    (output / "preparation.sha256").write_text(digest(prep_file.read_bytes()) + "\n")

    return {
        "action": "prepare",
        "ready": True,
        "repo": str(root.resolve()),
        "output": str(output.resolve()),
        "client": client,
        "preparation_file": str(prep_file.resolve()),
        "fixtures": {k: v["path"] for k, v in fixtures_info.items()},
    }


def collect(root: Path, output: Path, client: str = "opencode") -> dict:
    if client == "codex":
        raise Refusal("Codex collection requires dedicated native-app-server mode; codex exec is not supported as native-app-server")
    if client != "opencode":
        raise Refusal(f"unsupported client: {client}")

    doc_migrate = _load_doc_migrate()
    git_directory = doc_migrate.gitdir(root)
    validate_output_path(output, root, git_directory, is_prepare=False)

    for name in ("raw", "collection_manifest.json", "compatibility.json"):
        candidate = output / name
        if candidate.exists() or candidate.is_symlink():
            raise Refusal(f"existing collection artifact refused: {candidate}")
    prep, prep_file = read_preparation(output)
    if snapshot_tree(output / "fixtures") != prep.get("fixture_tree"):
        raise Refusal("initial fixture hashes differ from preparation")
    before_target = target_digest(root, git_directory)
    if before_target != prep.get("target_digest"):
        raise Refusal("target changed since preparation")

    if prep.get("repo") != str(root.resolve()):
        raise Refusal("preparation repository binding mismatch")
    if prep.get("client") != client:
        raise Refusal("preparation client mismatch")

    current_env = environment_files(root)
    if current_env != prep.get("environment_files"):
        raise Refusal("target environment changed since preparation")

    current_kit = get_kit_bound_inputs()
    if current_kit != prep.get("kit_inputs"):
        raise Refusal("kit bound inputs changed since preparation")

    opencode_bin = shutil.which("opencode")
    if not opencode_bin:
        raise Refusal("opencode executable not found in PATH")

    ver_res = subprocess.run([opencode_bin, "--version"], capture_output=True, text=True)
    if ver_res.returncode != 0:
        raise Refusal(f"failed to obtain opencode version: {ver_res.stderr.strip()}")
    raw_version = ver_res.stdout.strip()
    match = re.search(r"\b(\d+\.\d+\.\d+)\b", raw_version)
    collected_version = match.group(1) if match else raw_version

    timeout_sec = float(os.environ.get("MRCALL_DOC_COMPAT_TIMEOUT", "180"))
    if not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise Refusal("collection timeout must be finite and greater than zero")
    raw_dir = output / "raw"
    raw_dir.mkdir()

    messages = {
        "startup": "Orient on this repository: read docs/active-context.md and report current state. Do not modify any files.",
        "documentation": "Reconcile documentation: update docs/active-context.md to reflect current state and archive historical narrative to docs/active-context-archive.md according to the documentation lifecycle.",
    }

    trials_info = {}
    all_completed = True

    for trial in ("startup", "documentation"):
        fixture_path = Path(prep["fixtures"][trial]["path"])
        if not fixture_path.is_dir():
            raise Refusal(f"fixture directory missing: {fixture_path}")

        safe_path(fixture_path)
        before_hashes = snapshot_tree(fixture_path)
        if before_hashes != prep["fixtures"][trial]["initial_hashes"]:
            raise Refusal("initial fixture hashes differ from preparation")
        before_gitdir = snapshot_tree(fixture_path / ".git")
        msg = messages[trial]
        cmd = [opencode_bin, "run", "--dir", str(fixture_path), "--format", "json", msg]

        stdout_file = raw_dir / f"{trial}_stdout.log"
        stderr_file = raw_dir / f"{trial}_stderr.log"
        events_file = raw_dir / f"{trial}_events.jsonl"
        diff_file = raw_dir / f"{trial}_diff.patch"

        timed_out = False
        returncode = None
        stdout_bytes = b""
        stderr_bytes = b""

        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout_sec,
            )
            returncode = proc.returncode
            stdout_bytes = proc.stdout
            stderr_bytes = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            all_completed = False
            stdout_bytes = exc.stdout or b""
            stderr_bytes = exc.stderr or b""
            returncode = -1

        if returncode != 0:
            all_completed = False

        stdout_file.write_bytes(stdout_bytes)
        stderr_file.write_bytes(stderr_bytes)

        events_lines = []
        for line in stdout_bytes.splitlines():
            line_str = line.strip()
            if line_str.startswith(b"{") and line_str.endswith(b"}"):
                events_lines.append(line_str)
        events_file.write_bytes(b"\n".join(events_lines) + (b"\n" if events_lines else b""))

        after_hashes = snapshot_tree(fixture_path)

        diff_res = subprocess.run(["git", "diff", "--binary", "HEAD"], cwd=fixture_path, capture_output=True, check=True)
        diff_file.write_bytes(diff_res.stdout)
        untracked_file = raw_dir / f"{trial}_untracked.tar"
        untracked = subprocess.run(["git", "ls-files", "--others", "-z"], cwd=fixture_path, capture_output=True, check=True).stdout
        with tarfile.open(untracked_file, "w") as archive:
            for name in untracked.split(b"\0"):
                if name:
                    rel = os.fsdecode(name)
                    archive.add(fixture_path / rel, arcname=rel, recursive=False)
        gitdir_file = raw_dir / f"{trial}_gitdir.tar"
        with tarfile.open(gitdir_file, "w") as archive:
            archive.add(fixture_path / ".git", arcname=".git")
        gitdir_diff_file = raw_dir / f"{trial}_gitdir_diff.json"
        gitdir_diff_file.write_text(json.dumps({"before": before_gitdir, "after": snapshot_tree(fixture_path / ".git")}, indent=2) + "\n")

        trials_info[trial] = {
            "command": cmd,
            "returncode": returncode,
            "timed_out": timed_out,
            "completed": (not timed_out and returncode == 0),
            "stdout_path": str(stdout_file.resolve()),
            "stdout_sha256": digest(stdout_bytes),
            "stderr_path": str(stderr_file.resolve()),
            "stderr_sha256": digest(stderr_bytes),
            "events_path": str(events_file.resolve()),
            "events_sha256": digest(events_file.read_bytes()),
            "diff_path": str(diff_file.resolve()),
            "diff_sha256": digest(diff_file.read_bytes()),
            **{f"{key}_{field}": str(path) if field == "path" else digest(path.read_bytes())
               for key, path in (("untracked", untracked_file), ("gitdir", gitdir_file), ("gitdir_diff", gitdir_diff_file))
               for field in ("path", "sha256")},
            "before_hashes": before_hashes,
            "after_hashes": after_hashes,
        }

    after_target = target_digest(root, git_directory)
    if after_target != before_target:
        all_completed = False
    status = "awaiting-review" if all_completed else "failed"

    manifest_data = {
        "schema_version": 1,
        "repo": str(root.resolve()),
        "client": client,
        "version": collected_version,
        "mode": "run-explicit-dir",
        "status": status,
        "target_before_sha256": before_target,
        "target_after_sha256": after_target,
        "preparation": {"path": str(prep_file), "sha256": digest(prep_file.read_bytes())},
        "environment_files": prep["environment_files"],
        "instruction_files": prep["instruction_files"],
        "kit_inputs": prep["kit_inputs"],
        "trials": trials_info,
        "limit": LIMIT,
    }

    manifest_file = output / "collection_manifest.json"
    manifest_bytes = (json.dumps(manifest_data, indent=2) + "\n").encode("utf-8")
    manifest_file.write_bytes(manifest_bytes)
    collection_sha = digest(manifest_bytes)

    return {
        "action": "collect",
        "ready": all_completed,
        "repo": str(root.resolve()),
        "output": str(output.resolve()),
        "client": client,
        "version": collected_version,
        "status": status,
        "collection_manifest": str(manifest_file.resolve()),
        "collection_sha256": collection_sha,
        "trials": {t: {"completed": trials_info[t]["completed"], "timed_out": trials_info[t]["timed_out"]} for t in trials_info},
    }


def report(root: Path, output: Path, review_path_str: str | None, client: str = "opencode") -> dict:
    if client == "codex":
        raise Refusal("Codex collection requires dedicated native-app-server mode; codex exec is not supported as native-app-server")
    if client != "opencode":
        raise Refusal(f"unsupported client: {client}")

    doc_migrate = _load_doc_migrate()
    git_directory = doc_migrate.gitdir(root)
    validate_output_path(output, root, git_directory, is_prepare=False)

    if (output / "compatibility.json").exists() or (output / "compatibility.json").is_symlink():
        raise Refusal("existing compatibility report refused")
    manifest_file = safe_path(output / "collection_manifest.json")
    if not manifest_file.is_file():
        raise Refusal(f"collection manifest missing: {manifest_file}")
    manifest_bytes = manifest_file.read_bytes()
    collection_sha = digest(manifest_bytes)
    manifest = json.loads(manifest_bytes.decode("utf-8"))

    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise Refusal("malformed collection manifest")
    if manifest.get("client") != client or manifest.get("mode") != "run-explicit-dir":
        raise Refusal("collection client/mode mismatch")
    artifacts = raw_artifacts(manifest, output)
    artifacts[str(manifest_file)] = collection_sha
    if manifest.get("repo") != str(root.resolve()):
        raise Refusal("collection manifest repository binding mismatch")
    if manifest.get("status") != "awaiting-review":
        raise Refusal(f"collection status is not awaiting-review: {manifest.get('status')}")

    if not review_path_str:
        raise Refusal("--review argument is required for report")
    review_path = safe_path(review_path_str).resolve()
    if not review_path.is_file():
        raise Refusal(f"review file not found: {review_path}")

    review = json.loads(review_path.read_text())
    if not isinstance(review, dict):
        raise Refusal("review file must be a JSON object")

    if review.get("schema_version") != 1:
        raise Refusal("review schema_version must be 1")
    if review.get("outcome") != "APPROVED":
        raise Refusal(f"review outcome is not APPROVED: {review.get('outcome')}")
    if review.get("repo") != str(root.resolve()):
        raise Refusal(f"review repository mismatch: {review.get('repo')} != {root.resolve()}")
    if review.get("collection_sha256") != collection_sha:
        raise Refusal("review collection_sha256 does not match collection manifest")
    if review.get("client") != manifest.get("client"):
        raise Refusal("review client mismatch")
    if review.get("version") != manifest.get("version"):
        raise Refusal("review version mismatch")
    if review.get("mode") != "run-explicit-dir":
        raise Refusal("review mode mismatch")

    scopes = review.get("reviewed_scopes")
    if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
        raise Refusal("reviewed_scopes must be a list of strings")
    reviewed_scopes = set(scopes)
    if not SCOPES.issubset(reviewed_scopes):
        raise Refusal(f"review must cover {sorted(SCOPES)} scopes; got {sorted(reviewed_scopes)}")

    observed = review.get("observed", {})
    if not isinstance(observed, dict):
        raise Refusal("observed must be an object")
    if observed.get("instruction_loading") != "observed" or observed.get("lifecycle") != "pass":
        raise Refusal("review observed instruction_loading must be 'observed' and lifecycle must be 'pass'")

    raw_report_str = review.get("raw_report")
    if not raw_report_str:
        raise Refusal("review raw_report path is required")
    raw_report_path = safe_path(raw_report_str).resolve()
    if not raw_report_path.is_file():
        raise Refusal(f"raw review report not found: {raw_report_path}")
    if digest(raw_report_path.read_bytes()) != review.get("raw_report_sha256"):
        raise Refusal("raw review report sha256 does not match review envelope")

    bindings = review.get("artifact_hash_binding")
    if not isinstance(bindings, dict) or not bindings:
        raise Refusal("artifact_hash_binding must be a nonempty object of absolute path to SHA-256")
    for path_str, expected in bindings.items():
        if not isinstance(path_str, str) or not Path(path_str).is_absolute() or not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            raise Refusal("malformed artifact_hash_binding entry")
        path = safe_path(path_str)
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise Refusal(f"artifact hash binding mismatch: {path}")
    if not artifacts.items() <= bindings.items():
        raise Refusal("artifact_hash_binding must cover all raw artifacts and collection manifest")

    current_env = environment_files(root)
    if current_env != manifest.get("environment_files"):
        raise Refusal("current environment_files differ from collection observation")

    current_inst = doc_migrate.instruction_files(root)
    if current_inst != manifest.get("instruction_files"):
        raise Refusal("current instruction_files differ from collection observation")

    current_kit = get_kit_bound_inputs()
    if current_kit != manifest.get("kit_inputs"):
        raise Refusal("current kit bound inputs differ from collection observation")

    current_target = target_digest(root, git_directory)
    if current_target != manifest.get("target_before_sha256") or current_target != manifest.get("target_after_sha256"):
        raise Refusal("target digest differs from collection observation")
    prep, prep_file = read_preparation(output)
    if manifest.get("preparation") != {"path": str(prep_file), "sha256": digest(prep_file.read_bytes())}:
        raise Refusal("preparation changed since collection")

    evidence_paths: set[Path] = set()
    for item in manifest.get("environment_files", []):
        evidence_paths.add(Path(item["path"]))
    for item in manifest.get("kit_inputs", []):
        evidence_paths.add(Path(item["path"]))
    for trial_data in manifest.get("trials", {}).values():
        for log_key in RAW_KEYS:
            evidence_paths.add(Path(trial_data[f"{log_key}_path"]))
    evidence_paths.update(Path(p) for p in bindings)
    evidence_paths.add(prep_file)
    evidence_paths.add(output / "preparation.sha256")
    evidence_paths.add(manifest_file)
    evidence_paths.add(review_path)
    evidence_paths.add(raw_report_path)

    evidence_list = []
    for ep in sorted(evidence_paths, key=lambda p: str(p.resolve())):
        ep_res = safe_path(ep).resolve()
        if not ep_res.is_file():
            raise Refusal(f"missing evidence artifact: {ep_res}")
        evidence_list.append({"path": str(ep_res), "sha256": digest(ep_res.read_bytes())})
    evidence_list.sort(key=lambda item: item["path"])

    compat_data = {
        "schema_version": 1,
        "repo": str(root.resolve()),
        "instruction_files": manifest["instruction_files"],
        "environment_files": manifest["environment_files"],
        "required_scopes": sorted(SCOPES),
        "clients": [
            {
                "client": manifest["client"],
                "version": manifest["version"],
                "mode": manifest["mode"],
                "scopes": sorted(SCOPES),
                "instruction_loading": "observed",
                "lifecycle": "pass",
                "configuration": {
                    "ambient": "tested",
                    "explicit_dir": True,
                },
                "evidence": evidence_list,
            }
        ],
        "limit": LIMIT,
    }

    compat_file = output / "compatibility.json"
    compat_file.write_text(json.dumps(compat_data, indent=2) + "\n")

    return {
        "action": "report",
        "ready": True,
        "repo": str(root.resolve()),
        "output": str(output.resolve()),
        "compatibility_report": str(compat_file.resolve()),
        "sha256": digest(compat_file.read_bytes()),
        "evidence_count": len(evidence_list),
    }


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
        epilog=(
            "prepare creates minimal v9 startup and documentation fixtures outside target content, "
            "mirrors parent instruction hierarchy, and records initial inventories. "
            "collect runs client native trial commands on the fixtures without model or guard overrides, "
            "saving complete logs and diffs with awaiting-review status. "
            "report requires an APPROVED semantic review bound to collection manifest sha256 and emits "
            "a schema-1 compatibility report.\n\n"
            'Review JSON schema (all fields required):\n'
            '{"schema_version":1,"outcome":"APPROVED","repo":"ABS_TARGET",\n'
            ' "collection_sha256":"SHA256_COLLECTION_MANIFEST","client":"opencode",\n'
            ' "version":"EXACT_COLLECTED_VERSION","mode":"run-explicit-dir",\n'
            ' "reviewed_scopes":["startup","documentation"],\n'
            ' "observed":{"instruction_loading":"observed","lifecycle":"pass"},\n'
            ' "raw_report":"ABS_FULL_SEMANTIC_REVIEW","raw_report_sha256":"SHA256",\n'
            ' "artifact_hash_binding":{"ABS_COLLECTION_MANIFEST":"SHA256",\n'
            '                          "EVERY_ABS_RAW_ARTIFACT":"SHA256"}}\n'
            'Bindings must cover every raw artifact and collection manifest. Review complete stdout, stderr, '
            'events, binary diff, untracked archive, gitdir archive and gitdir before/after hashes. '
            'Judge instruction loading, orientation before source, startup writes, documentation '
            'reconciliation, critic, mechanical and completion evidence, and application preservation. '
            'Exit status alone cannot establish semantic success. Target digests detect changes; '
            'collection is not a sandbox. Existing raw collections/reports are never overwritten.\n' + LIMIT
        ),
    )
    parser.add_argument("action", choices=("prepare", "collect", "report"))
    parser.add_argument("--repo", required=True, help="target Git repository root")
    parser.add_argument("--output", required=True, help="external output directory")
    parser.add_argument("--client", default="opencode", help="client identifier (default: opencode)")
    parser.add_argument("--review", help="semantic review JSON file path (required for report)")
    parser.add_argument("--json", action="store_true", help="emit JSON output")

    args = parser.parse_args()
    root = Path(args.repo).absolute()
    output = Path(args.output).absolute()

    result = {
        "action": args.action,
        "repo": str(root),
        "output": str(output),
        "ready": False,
        "reasons": [],
        "limit": LIMIT,
    }

    try:
        migrate_refusal = _load_doc_migrate().Refusal
    except Exception:
        migrate_refusal = Refusal

    try:
        root = safe_path(root).resolve()
        result["repo"] = str(root)

        if args.action == "prepare":
            result.update(prepare(root, output, client=args.client))
        elif args.action == "collect":
            result.update(collect(root, output, client=args.client))
        elif args.action == "report":
            result.update(report(root, output, review_path_str=args.review, client=args.client))
    except (Refusal, migrate_refusal, ValueError, OSError, KeyError, TypeError) as exc:
        result["ready"] = False
        result["reasons"].append(str(exc))

    if args.json:
        print(json.dumps(result, sort_keys=True, indent=2))
    else:
        print(f"doc-compat: {args.action.upper()} {'READY' if result['ready'] else 'REFUSED'}")
        for key, value in result.items():
            if key not in {"action", "ready"}:
                print(f"{key}: {json.dumps(value, ensure_ascii=False)}")

    return 0 if result["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
