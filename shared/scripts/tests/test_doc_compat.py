"""Real CLI tests for doc-compat.py using disposable repositories and safely controlled fake executables."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
COMPAT = SCRIPTS / "doc-compat.py"
MIGRATE = SCRIPTS / "doc-migrate.py"
CHECKER = SCRIPTS / "doc-check.py"
TEMPLATES = SCRIPTS.parent / "templates"
SCOPE = b"<!-- doc-scope:start -->\nScope: Fixture project routing.\n<!-- doc-scope:end -->\n"


class DocCompatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

        # Hierarchy: self.base / "parent" / "repo"
        # This allows testing ancestor instruction mirroring.
        self.parent = self.base / "parent"
        self.parent.mkdir()
        self.ancestor_claude = self.parent / "CLAUDE.md"
        self.ancestor_claude.write_text("Ancestor instructions for testing.\n")

        self.root = self.parent / "repo"
        self.root.mkdir()
        (self.root / "docs").mkdir()
        (self.root / "AGENTS.md").write_bytes(b"# Project\r\n\r\n" + SCOPE + b"Keep project guidance.\r\n")
        (self.root / "AGENTS.md").chmod(0o640)
        (self.root / "docs/README.md").write_bytes(SCOPE)
        (self.root / "app.py").write_text("print('fixture app')\n")

        # Initialize git using git -c rather than config editing
        git_c = ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid"]
        subprocess.run(["git", "init", "-b", "main"], cwd=self.root, check=True, capture_output=True)
        subprocess.run([*git_c, "add", "."], cwd=self.root, check=True, capture_output=True)
        subprocess.run([*git_c, "commit", "-m", "fixture baseline"], cwd=self.root, check=True, capture_output=True)

        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()
        (self.root / "docs/active-context.md").write_bytes(
            f"---\ndoc_baseline_commit: {sha}\n---\n".encode("utf-8")
            + SCOPE
            + b"## State now\nFixture baseline.\n## Unresolved\nNone.\n## Next\nNone.\n"
        )
        subprocess.run([*git_c, "add", "."], cwd=self.root, check=True, capture_output=True)
        subprocess.run([*git_c, "commit", "-m", "record baseline commit"], cwd=self.root, check=True, capture_output=True)

        # Legacy v8 profile and CLAUDE.md
        (self.root / "CLAUDE.md").write_bytes((TEMPLATES / "legacy/v8/CLAUDE.md").read_bytes())
        (self.root / "docs/.doc-profile").write_bytes(
            b"harness_version = 8\nschema_version = 1\nmode = leaf\nindex_file = AGENTS.md\nharness_file = CLAUDE.md\n"
        )

        self.output = self.base / "compat-output"

        # Setup fake opencode executable
        self.fake_bin = self.base / "fake_bin"
        self.fake_bin.mkdir()
        self.fake_opencode = self.fake_bin / "opencode"
        self.fake_opencode.write_text(
            """#!/usr/bin/env python3
import os
import sys
import time

if "--version" in sys.argv:
    ver = os.environ.get("FAKE_OPENCODE_VERSION", "1.18.34")
    print(f"opencode {ver}")
    sys.exit(0)

if "run" in sys.argv:
    if "FAKE_OPENCODE_SLEEP" in os.environ:
        time.sleep(float(os.environ["FAKE_OPENCODE_SLEEP"]))
    if "FAKE_OPENCODE_EXIT" in os.environ:
        sys.exit(int(os.environ["FAKE_OPENCODE_EXIT"]))
    print('{"event": "start", "simulated": true, "note": "SIMULATED FIXTURE RUN FOR UNIT TESTS ONLY"}')
    print('{"event": "finish", "simulated": true, "note": "SIMULATED FIXTURE RUN FOR UNIT TESTS ONLY"}')
    sys.exit(0)

sys.exit(1)
"""
        )
        self.fake_opencode.chmod(0o755)

        self.env = dict(
            os.environ,
            PATH=f"{self.fake_bin}:{os.environ.get('PATH', '')}",
            MRCALL_DOC_HARNESS_TEMPLATE=str(TEMPLATES / "AGENTS.block.md"),
        )

    def tree(self) -> dict[str, tuple[bytes, int]]:
        result = {}
        for path in self.root.rglob("*"):
            rel = path.relative_to(self.root).as_posix()
            if rel.startswith(".git/") or rel == ".git":
                continue
            if path.is_file():
                result[rel] = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        return result

    def invoke(self, action: str, *args, expected: int = 0, env: dict | None = None) -> dict:
        use_env = self.env if env is None else env
        argv = [sys.executable, str(COMPAT), action, "--repo", str(self.root), "--output", str(self.output), "--json", *map(str, args)]
        proc = subprocess.run(argv, text=True, capture_output=True, env=use_env)
        self.assertEqual(proc.returncode, expected, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}")
        return json.loads(proc.stdout) if proc.stdout else {}

    def artifact_bindings(self):
        paths = [self.output / "collection_manifest.json", *(self.output / "raw").iterdir()]
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    def test_environment_files_function_and_overrides(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("doc_compat", COMPAT)
        doc_compat = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doc_compat)

        env_list = doc_compat.environment_files(self.root)
        paths = [item["path"] for item in env_list]
        self.assertIn(str(self.ancestor_claude.resolve()), paths)
        self.assertIn(str((self.root / "AGENTS.md").resolve()), paths)
        self.assertIn(str((self.root / "CLAUDE.md").resolve()), paths)

        config_path = self.root / "opencode.json"
        config_path.write_text('{"secret_token": "SHOULD_NEVER_BE_EXPOSED"}\n')
        with self.assertRaises(doc_compat.Refusal):
            doc_compat.environment_files(self.root)
        config_path.unlink()

        # Reject OPENCODE_CONFIG_CONTENT
        with self.subTest("reject OPENCODE_CONFIG_CONTENT"):
            os.environ["OPENCODE_CONFIG_CONTENT"] = "foo"
            try:
                with self.assertRaises(doc_compat.Refusal) as ctx:
                    doc_compat.environment_files(self.root)
                self.assertIn("OPENCODE_CONFIG_CONTENT", str(ctx.exception))
            finally:
                del os.environ["OPENCODE_CONFIG_CONTENT"]

        # Reject OPENCODE_CONFIG_DIR
        with self.subTest("reject OPENCODE_CONFIG_DIR"):
            os.environ["OPENCODE_CONFIG_DIR"] = "/tmp/fake"
            try:
                with self.assertRaises(doc_compat.Refusal) as ctx:
                    doc_compat.environment_files(self.root)
                self.assertIn("OPENCODE_CONFIG_DIR", str(ctx.exception))
            finally:
                del os.environ["OPENCODE_CONFIG_DIR"]

        # Reject ancestor .opencode directory override
        with self.subTest("reject ancestor .opencode"):
            opencode_dir = self.parent / ".opencode"
            opencode_dir.mkdir()
            try:
                with self.assertRaises(doc_compat.Refusal) as ctx:
                    doc_compat.environment_files(self.root)
                self.assertIn(".opencode override", str(ctx.exception))
            finally:
                opencode_dir.rmdir()

    def test_prepare_refusals_leave_target_untouched(self):
        before = self.tree()

        # Output inside target
        res = self.invoke("prepare", "--output", self.root / "bad_out", expected=1)
        self.assertIn("outside target content", res["reasons"][0])
        self.assertEqual(before, self.tree())

        # Bad repository layout (custom CLAUDE.md)
        (self.root / "CLAUDE.md").write_text("Custom rule not in legacy v8.\n")
        res = self.invoke("prepare", expected=1)
        self.assertIn("customized or unrecognized legacy CLAUDE.md", res["reasons"][0])
        (self.root / "CLAUDE.md").write_bytes((TEMPLATES / "legacy/v8/CLAUDE.md").read_bytes())
        self.assertEqual(before, self.tree())

        # Unsupported client: codex requires native-app-server
        res = self.invoke("prepare", "--client", "codex", expected=1)
        self.assertIn("native-app-server", res["reasons"][0])
        self.assertEqual(before, self.tree())

    def test_prepare_collect_report_lifecycle(self):
        before = self.tree()

        # 1. Prepare
        prep_res = self.invoke("prepare")
        self.assertTrue(prep_res["ready"])
        self.assertEqual(before, self.tree())  # Target is untouched!

        prep_file = self.output / "preparation.json"
        self.assertTrue(prep_file.is_file())
        prep_data = json.loads(prep_file.read_text())
        self.assertEqual(prep_data["client"], "opencode")
        self.assertIn("startup", prep_data["fixtures"])
        self.assertIn("documentation", prep_data["fixtures"])

        # Check ancestor hierarchy mirrored in fixture
        startup_fixture = Path(prep_data["fixtures"]["startup"]["path"])
        doc_fixture = Path(prep_data["fixtures"]["documentation"]["path"])
        ancestor_in_fixture = startup_fixture.parent / "CLAUDE.md"
        self.assertTrue(ancestor_in_fixture.is_file())
        self.assertEqual(ancestor_in_fixture.read_bytes(), self.ancestor_claude.read_bytes())

        # Check target root CLAUDE.md is REMOVED in fixture
        self.assertFalse((startup_fixture / "CLAUDE.md").exists())
        self.assertFalse((doc_fixture / "CLAUDE.md").exists())

        # Check fixture mechanically valid v9
        check_proc = subprocess.run(
            [sys.executable, str(CHECKER), "--repo", str(startup_fixture), "--startup", "--json"],
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(check_proc.returncode, 0, check_proc.stdout + check_proc.stderr)

        # Overwrite protection: running prepare again on non-empty output refuses!
        self.invoke("prepare", expected=1)

        # 2. Collect
        collect_res = self.invoke("collect")
        self.assertTrue(collect_res["ready"])
        self.assertEqual(collect_res["status"], "awaiting-review")
        self.assertEqual(collect_res["version"], "1.18.34")
        self.assertEqual(before, self.tree())  # Target remains untouched!

        manifest_file = self.output / "collection_manifest.json"
        self.assertTrue(manifest_file.is_file())
        manifest = json.loads(manifest_file.read_text())
        self.assertEqual(manifest["status"], "awaiting-review")
        self.assertIn("startup", manifest["trials"])
        self.assertIn("documentation", manifest["trials"])

        # Verify raw logs exist
        for trial in ("startup", "documentation"):
            stdout_path = Path(manifest["trials"][trial]["stdout_path"])
            self.assertTrue(stdout_path.is_file())
            self.assertIn(b"SIMULATED FIXTURE RUN", stdout_path.read_bytes())

        # 3. Report
        # Missing review refuses
        self.invoke("report", expected=1)

        # Create raw review report and envelope
        raw_report = self.base / "review_report.md"
        raw_report.write_text("# Semantic Review Report\nTrial results verified: orientation clean, lifecycle pass.\n")

        review_file = self.base / "review.json"
        review_data = {
            "schema_version": 1,
            "outcome": "APPROVED",
            "repo": str(self.root),
            "collection_sha256": collect_res["collection_sha256"],
            "client": "opencode",
            "version": "1.18.34",
            "mode": "run-explicit-dir",
            "reviewed_scopes": ["startup", "documentation"],
            "observed": {
                "instruction_loading": "observed",
                "lifecycle": "pass",
            },
            "raw_report": str(raw_report.resolve()),
            "raw_report_sha256": hashlib.sha256(raw_report.read_bytes()).hexdigest(),
            "artifact_hash_binding": self.artifact_bindings(),
        }
        review_file.write_text(json.dumps(review_data))

        # Successful report
        report_res = self.invoke("report", "--review", review_file)
        self.assertTrue(report_res["ready"])
        self.assertEqual(before, self.tree())  # Target remains untouched!

        compat_file = Path(report_res["compatibility_report"])
        self.assertTrue(compat_file.is_file())
        compat = json.loads(compat_file.read_text())
        self.assertEqual(compat["schema_version"], 1)
        self.assertEqual(compat["repo"], str(self.root))
        self.assertEqual(compat["required_scopes"], ["documentation", "startup"])
        client_entry = compat["clients"][0]
        self.assertEqual(client_entry["client"], "opencode")
        self.assertEqual(client_entry["version"], "1.18.34")
        self.assertEqual(client_entry["mode"], "run-explicit-dir")
        self.assertEqual(client_entry["scopes"], ["documentation", "startup"])
        self.assertEqual(client_entry["configuration"], {"ambient": "tested", "explicit_dir": True})

        # Check every evidence item exists and matches digest
        self.assertGreater(len(client_entry["evidence"]), 10)
        for item in client_entry["evidence"]:
            p = Path(item["path"])
            self.assertTrue(p.is_absolute())
            self.assertTrue(p.is_file(), f"evidence artifact missing: {p}")
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), item["sha256"])

    def test_collect_timeout_and_nonzero_failures(self):
        self.invoke("prepare")
        before = self.tree()

        # Nonzero exit code from client
        env_nonzero = dict(self.env, FAKE_OPENCODE_EXIT="2")
        collect_res = self.invoke("collect", env=env_nonzero, expected=1)
        self.assertFalse(collect_res["ready"])
        self.assertEqual(collect_res["status"], "failed")
        self.assertEqual(before, self.tree())

        self.output = self.base / "timeout-output"
        self.invoke("prepare")

        # Timeout from client
        env_timeout = dict(self.env, FAKE_OPENCODE_SLEEP="2.0", MRCALL_DOC_COMPAT_TIMEOUT="0.1")
        collect_res = self.invoke("collect", env=env_timeout, expected=1)
        self.assertFalse(collect_res["ready"])
        self.assertEqual(collect_res["status"], "failed")
        self.assertTrue(collect_res["trials"]["startup"]["timed_out"])
        self.assertEqual(before, self.tree())

    def test_report_refusals_on_invalidation_and_stale_reviews(self):
        self.invoke("prepare")
        collect_res = self.invoke("collect")
        collection_sha = collect_res["collection_sha256"]

        raw_report = self.base / "review_report.md"
        raw_report.write_text("# Review Report\n")
        review_file = self.base / "review.json"

        def write_review(**overrides):
            data = {
                "schema_version": 1,
                "outcome": "APPROVED",
                "repo": str(self.root),
                "collection_sha256": collection_sha,
                "client": "opencode",
                "version": "1.18.34",
                "mode": "run-explicit-dir",
                "reviewed_scopes": ["startup", "documentation"],
                "observed": {"instruction_loading": "observed", "lifecycle": "pass"},
                "raw_report": str(raw_report.resolve()),
                "raw_report_sha256": hashlib.sha256(raw_report.read_bytes()).hexdigest(),
            "artifact_hash_binding": self.artifact_bindings(),
            }
            data.update(overrides)
            review_file.write_text(json.dumps(data))

        # Outcome not APPROVED
        write_review(outcome="REVISE")
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("outcome is not APPROVED", res["reasons"][0])

        # Wrong repo binding
        write_review(repo="/tmp/other_repo")
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("repository mismatch", res["reasons"][0])

        # Stale collection_sha256
        write_review(collection_sha256="0" * 64)
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("collection_sha256 does not match", res["reasons"][0])

        # Missing required scope in review
        write_review(reviewed_scopes=["startup"])
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("must cover", res["reasons"][0])

        # Raw review report file modified
        write_review()
        raw_report.write_text("# Tampered Review Report\n")
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("raw review report sha256 does not match", res["reasons"][0])
        raw_report.write_text("# Review Report\n")

        # Collected raw log modified
        manifest = json.loads((self.output / "collection_manifest.json").read_text())
        startup_stdout = Path(manifest["trials"]["startup"]["stdout_path"])
        original_stdout_bytes = startup_stdout.read_bytes()
        startup_stdout.write_text("Tampered log\n")
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("collected log modified", res["reasons"][0])
        startup_stdout.write_bytes(original_stdout_bytes)

        # Target environment changed: adding a file
        new_local = self.root / "CLAUDE.local.md"
        new_local.write_text("Local rule.\n")
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("environment_files differ", res["reasons"][0])
        new_local.unlink()

        # Target environment changed: removing a file
        self.ancestor_claude.unlink()
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("environment_files differ", res["reasons"][0])
        self.ancestor_claude.write_text("Ancestor instructions for testing.\n")

        # Target environment changed: modifying a file
        self.ancestor_claude.write_text("Modified ancestor instructions.\n")
        res = self.invoke("report", "--review", review_file, expected=1)
        self.assertIn("environment_files differ", res["reasons"][0])
        self.ancestor_claude.write_text("Ancestor instructions for testing.\n")

        # Now clean review passes!
        res = self.invoke("report", "--review", review_file)
        self.assertTrue(res["ready"])

    def test_kit_input_tampering_refuses_report(self):
        # Use a temporary kit directory with custom workflows
        custom_kit = self.base / "custom_kit"
        shared_dir = custom_kit / "shared"
        commands_dir = shared_dir / "commands"
        skills_dir = shared_dir / "skills" / "doc-critic"
        commands_dir.mkdir(parents=True)
        skills_dir.mkdir(parents=True)

        for cmd in ("doc-create.md", "doc-start.md", "doc-end.md"):
            (commands_dir / cmd).write_text(f"# {cmd}\n")
        (skills_dir / "SKILL.md").write_text("# critic\n")

        custom_env = dict(self.env, MRCALL_KIT_DIR=str(custom_kit))

        self.invoke("prepare", env=custom_env)
        collect_res = self.invoke("collect", env=custom_env)

        raw_report = self.base / "review_report.md"
        raw_report.write_text("# Review Report\n")
        review_file = self.base / "review.json"
        review_data = {
            "schema_version": 1,
            "outcome": "APPROVED",
            "repo": str(self.root),
            "collection_sha256": collect_res["collection_sha256"],
            "client": "opencode",
            "version": "1.18.34",
            "mode": "run-explicit-dir",
            "reviewed_scopes": ["startup", "documentation"],
            "observed": {"instruction_loading": "observed", "lifecycle": "pass"},
            "raw_report": str(raw_report.resolve()),
            "raw_report_sha256": hashlib.sha256(raw_report.read_bytes()).hexdigest(),
            "artifact_hash_binding": self.artifact_bindings(),
        }
        review_file.write_text(json.dumps(review_data))

        # Tamper with one of the kit workflows
        (commands_dir / "doc-create.md").write_text("# Tampered doc-create\n")
        res = self.invoke("report", "--review", review_file, env=custom_env, expected=1)
        self.assertIn("kit bound inputs differ", res["reasons"][0])

    def test_doc_migrate_consumes_generated_compatibility_report_for_1_18_32(self):
        # Test full pipeline with version 1.18.32, which doc-migrate currently accepts
        env_32 = dict(self.env, FAKE_OPENCODE_VERSION="1.18.32")
        self.invoke("prepare", env=env_32)
        collect_res = self.invoke("collect", env=env_32)

        raw_report = self.base / "review_report.md"
        raw_report.write_text("# Review Report for 1.18.32\n")
        review_file = self.base / "review.json"
        review_data = {
            "schema_version": 1,
            "outcome": "APPROVED",
            "repo": str(self.root),
            "collection_sha256": collect_res["collection_sha256"],
            "client": "opencode",
            "version": "1.18.32",
            "mode": "run-explicit-dir",
            "reviewed_scopes": ["startup", "documentation"],
            "observed": {"instruction_loading": "observed", "lifecycle": "pass"},
            "raw_report": str(raw_report.resolve()),
            "raw_report_sha256": hashlib.sha256(raw_report.read_bytes()).hexdigest(),
            "artifact_hash_binding": self.artifact_bindings(),
        }
        review_file.write_text(json.dumps(review_data))

        report_res = self.invoke("report", "--review", review_file, env=env_32)
        self.assertTrue(report_res["ready"])
        compat_path = report_res["compatibility_report"]

        # Run doc-migrate dry-run using this compatibility report
        migrate_proc = subprocess.run(
            [sys.executable, str(MIGRATE), "dry-run", "--repo", str(self.root), "--mode", "leaf", "--compatibility", compat_path, "--json"],
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(migrate_proc.returncode, 0, f"STDOUT: {migrate_proc.stdout}\nSTDERR: {migrate_proc.stderr}")
        migrate_data = json.loads(migrate_proc.stdout)
        self.assertTrue(migrate_data["ready"])
        self.assertEqual(migrate_data["to_version"], 9)


if __name__ == "__main__":
    unittest.main()
