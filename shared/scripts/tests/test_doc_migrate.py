"""Real helper CLI tests using disposable repositories and scoped fixture attestations."""
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
MIGRATE = SCRIPTS / "doc-migrate.py"
CHECKER = SCRIPTS / "doc-check.py"
TEMPLATES = SCRIPTS.parent / "templates"
SCOPE = b"<!-- doc-scope:start -->\nScope: Fixture project routing.\n<!-- doc-scope:end -->\n"


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        (self.root / "docs").mkdir()
        (self.root / "AGENTS.md").write_bytes(b"# Project\r\n\r\n" + SCOPE + b"Keep project bytes.\r\n")
        (self.root / "AGENTS.md").chmod(0o640)
        (self.root / "docs/README.md").write_bytes(SCOPE)
        (self.root / "code.py").write_text("print('fixture')\n")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "docs/active-context.md").write_bytes(f"---\ndoc_baseline_commit: {sha}\n---\n".encode() + SCOPE + b"## State now\nFixture.\n## Unresolved\nNone.\n## Next\nNone.\n")
        self.transaction = self.base / "transaction"
        inspected = self.invoke("inspect", "--mode", "leaf", expected=1)
        self.artifact = self.base / "observed-result.json"
        self.artifact.write_text('{"fixture":"simulated evidence for mechanical acceptance tests only"}\n')
        self.compat = self.base / "compatibility.json"
        self.evidence = {
            "schema_version": 1, "repo": str(self.root), "instruction_files": inspected["instruction_files"],
            "clients": [{"client": "codex", "version": "0.160.0", "mode": "native-app-server",
                         "scopes": ["startup", "documentation"], "instruction_loading": "observed", "lifecycle": "pass",
                         "configuration": {"ambient": "tested"},
                         "evidence": [{"path": str(self.artifact), "sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}]}],
        }
        self.save_evidence()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True)

    def save_evidence(self):
        self.compat.write_text(json.dumps(self.evidence))

    def invoke(self, action, *args, expected=0, env=None):
        argv = [sys.executable, str(MIGRATE), action, "--repo", str(self.root), "--json", *map(str, args)]
        result = subprocess.run(argv, text=True, capture_output=True, env=env)
        log = os.environ.get("MRCALL_MIGRATION_TEST_LOG")
        if log:
            with open(log, "a") as handle:
                handle.write(json.dumps({"test": self.id(), "argv": argv, "exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}) + "\n")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout else {}

    def run_action(self, action="apply", *args, **kwargs):
        return self.invoke(action, "--compatibility", self.compat, "--transaction", self.transaction, *args, **kwargs)

    def tree(self):
        result = {}
        for path in self.root.rglob("*"):
            rel = path.relative_to(self.root).as_posix()
            if rel.startswith(".git/") or rel == ".git":
                continue
            if path.is_symlink():
                result[rel] = ("symlink", os.readlink(path))
            elif path.is_file():
                result[rel] = (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            elif path.is_dir():
                result[rel] = ("directory", stat.S_IMODE(path.stat().st_mode))
        return result

    def legacy(self, version=8, variant="CLAUDE.md"):
        (self.root / "CLAUDE.md").write_bytes((TEMPLATES / "legacy" / f"v{version}" / variant).read_bytes())
        (self.root / "CLAUDE.md").chmod(0o604)
        (self.root / "docs/.doc-profile").write_bytes(
            f"# Keep settings exactly\r\nharness_version = {version}\r\nschema_version = 1\r\nmode = leaf\r\nindex_file = AGENTS.md\r\nharness_file = CLAUDE.md\r\nsmoke = python3 code.py\r\nindex_max_lines = 200\r\n".encode())
        (self.root / "docs/.doc-profile").chmod(0o600)

    def checker(self):
        result = subprocess.run([sys.executable, str(CHECKER), "--repo", str(self.root), "--startup", "--json"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_fresh_inspect_dry_run_apply_reapply_rollback(self):
        before = self.tree()
        self.run_action("inspect", "--mode", "leaf")
        self.run_action("dry-run", "--mode", "leaf")
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())
        result = self.run_action("apply", "--mode", "leaf")
        self.assertEqual(result["state"], "applied")
        self.assertTrue((self.root / "AGENTS.md").read_bytes().endswith(before["AGENTS.md"][0]))
        self.checker()
        after = self.tree()
        self.assertEqual(self.run_action()["state"], "unchanged")
        self.assertEqual(after, self.tree())
        self.invoke("rollback", "--transaction", self.transaction)
        self.assertEqual(before, self.tree())
        self.invoke("rollback", "--transaction", self.transaction)
        self.assertEqual(before, self.tree())

    def test_exact_v6_v7_v8_variants_preserve_project_profile_modes_and_git_index(self):
        for version, variant in ((6, "CLAUDE.md"), (7, "CLAUDE.md"), (8, "CLAUDE.md"), (8, "CLAUDE.initial.md"), (8, "CLAUDE.review.md")):
            with self.subTest(version=version, variant=variant):
                self.legacy(version, variant)
                before = self.tree()
                index = (self.root / ".git/index").read_bytes()
                self.run_action()
                self.assertFalse((self.root / "CLAUDE.md").exists())
                self.assertEqual((self.root / ".git/index").read_bytes(), index)
                self.assertTrue((self.root / "AGENTS.md").read_bytes().endswith(before["AGENTS.md"][0]))
                profile = before["docs/.doc-profile"][0].replace(f"harness_version = {version}".encode(), b"harness_version = 9").replace(b"harness_file = CLAUDE.md\r\n", b"")
                self.assertEqual((self.root / "docs/.doc-profile").read_bytes(), profile)
                self.checker()
                self.invoke("rollback", "--transaction", self.transaction)
                self.assertEqual(before, self.tree())
                import shutil
                shutil.rmtree(self.transaction)

    def test_known_codex_block_replacement_preserves_every_nonmanaged_byte(self):
        self.legacy()
        data = (self.root / "AGENTS.md").read_bytes()
        block = (TEMPLATES / "legacy/codex-agents.block.md").read_bytes().rstrip(b"\n")
        (self.root / "AGENTS.md").write_bytes(block + b"\n\n" + data)
        self.run_action()
        current = (self.root / "AGENTS.md").read_bytes()
        self.assertEqual(current, (TEMPLATES / "AGENTS.block.md").read_bytes() + b"\n\n\n" + data)

    def test_all_refusals_leave_repository_and_transaction_untouched(self):
        cases = ("custom-claude", "duplicate", "partial", "symlink-index", "symlink-profile", "legacy-collision", "missing-scope", "unsupported-client", "absent-evidence", "changed-evidence", "unknown-version", "mode-mismatch", "same-local")
        self.legacy()
        original = self.tree()
        for case in cases:
            with self.subTest(case=case):
                argv = []
                if case == "custom-claude":
                    with (self.root / "CLAUDE.md").open("ab") as handle:
                        handle.write(b"Custom rule.\n")
                elif case in {"duplicate", "partial"}:
                    block = (TEMPLATES / "AGENTS.block.md").read_bytes()
                    with (self.root / "AGENTS.md").open("ab") as handle:
                        handle.write(block * 2 if case == "duplicate" else b"<!-- mrcall-ai-kit:delivery:start -->\n")
                elif case.startswith("symlink-"):
                    path = self.root / ("AGENTS.md" if case.endswith("index") else "docs/.doc-profile")
                    other = self.base / "foreign"
                    other.write_bytes(path.read_bytes())
                    path.unlink()
                    path.symlink_to(other)
                elif case == "legacy-collision":
                    path = self.root / "docs/.doc-profile"
                    path.write_bytes(path.read_bytes().replace(b"index_file = AGENTS.md", b"index_file = CLAUDE.md"))
                elif case == "missing-scope":
                    (self.root / "docs/README.md").write_bytes(b"# Missing scope\n")
                elif case == "unsupported-client":
                    self.evidence["clients"][0]["version"] = "0.999.0"
                    self.save_evidence()
                elif case == "absent-evidence":
                    argv = ["--compatibility", self.base / "missing.json"]
                elif case == "changed-evidence":
                    self.artifact.write_text("changed")
                elif case == "unknown-version":
                    path = self.root / "docs/.doc-profile"
                    path.write_bytes(path.read_bytes().replace(b"harness_version = 8", b"harness_version = 5"))
                elif case == "mode-mismatch":
                    argv = ["--mode", "meta"]
                elif case == "same-local":
                    (self.root / "CLAUDE.local.md").write_text("Foreign local rules")
                before = self.tree()
                self.run_action("apply", *argv, expected=1)
                self.assertEqual(before, self.tree())
                self.assertFalse(self.transaction.exists())
                for rel in self.tree().keys() - original.keys():
                    (self.root / rel).unlink()
                for rel, value in original.items():
                    if value[0] != "directory":
                        path = self.root / rel
                        if path.is_symlink():
                            path.unlink()
                        path.write_bytes(value[0])
                        path.chmod(value[1])
                self.evidence["clients"][0]["version"] = "0.160.0"
                self.artifact.write_text('{"fixture":"simulated evidence for mechanical acceptance tests only"}\n')
                self.save_evidence()

    def test_failures_and_crashes_at_every_publish_step_restore_exact_original(self):
        self.legacy()
        before = self.tree()
        for variable, code in (("MRCALL_DOC_MIGRATE_TEST_FAIL_AFTER", 1), ("MRCALL_DOC_MIGRATE_TEST_CRASH_AFTER", 86)):
            for path in ("AGENTS.md", "CLAUDE.md", "docs/.doc-profile"):
                with self.subTest(variable=variable, path=path):
                    self.run_action(env=dict(os.environ, **{variable: path}), expected=code)
                    if code == 86:
                        manifest = json.loads((self.transaction / "manifest.json").read_text())
                        if path != "docs/.doc-profile":
                            self.assertEqual((self.root / "docs/.doc-profile").read_bytes(), before["docs/.doc-profile"][0])
                        self.assertEqual(manifest["completed_steps"][-1], path)
                        self.invoke("rollback", "--transaction", self.transaction)
                    self.assertEqual(before, self.tree())
                    import shutil
                    shutil.rmtree(self.transaction)

    def test_crash_during_partial_file_write_is_recoverable_without_residue(self):
        self.legacy()
        before = self.tree()
        for name in ("AGENTS.md", ".doc-profile"):
            with self.subTest(name=name):
                self.run_action(env=dict(os.environ, MRCALL_DOC_MIGRATE_TEST_CRASH_DURING=name), expected=87)
                manifest = json.loads((self.transaction / "manifest.json").read_text())
                self.assertTrue(any((self.root / change["temporary"]).exists() for change in manifest["changes"]))
                self.invoke("rollback", "--transaction", self.transaction)
                self.assertEqual(before, self.tree())
                import shutil
                shutil.rmtree(self.transaction)

    def test_thin_index_overflow_refuses_before_any_publish(self):
        self.legacy()
        with (self.root / "AGENTS.md").open("ab") as handle:
            handle.write(b"Project-owned line\n" * 180)
        before = self.tree()
        result = self.run_action(expected=1)
        self.assertIn("THIN INDEX", result["reasons"][0])
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())

    def test_stale_instruction_inventory_and_failed_attestation_refuse(self):
        self.legacy()
        before = self.tree()
        self.evidence["instruction_files"].append({"path": "/invented", "sha256": "0" * 64})
        self.save_evidence()
        self.assertIn("instruction_files differ", self.run_action(expected=1)["reasons"][0])
        self.evidence["instruction_files"].pop()
        self.evidence["clients"][0]["lifecycle"] = "failed"
        self.save_evidence()
        self.assertIn("failing measured configuration", self.run_action(expected=1)["reasons"][0])
        self.assertEqual(before, self.tree())

    def test_rollback_refuses_later_content_and_mode_changes(self):
        self.legacy()
        self.run_action()
        path = self.root / "AGENTS.md"
        after = path.read_bytes()
        path.write_bytes(after + b"Later change\n")
        before = self.tree()
        self.invoke("rollback", "--transaction", self.transaction, expected=1)
        self.assertEqual(before, self.tree())
        path.write_bytes(after)
        path.chmod(0o600)
        self.invoke("rollback", "--transaction", self.transaction, expected=1)

    def test_claude_and_untested_opencode_scopes_are_refused(self):
        self.legacy()
        client = self.evidence["clients"][0]
        client.update(client="claude", version="2.1.280", mode="print")
        self.save_evidence()
        self.assertIn("startup/closure failed", self.run_action(expected=1)["reasons"][0])
        client.update(client="opencode", version="1.18.32", mode="run-explicit-dir", configuration={"ambient": "tested", "explicit_dir": True})
        self.evidence["required_scopes"] = ["development"]
        self.save_evidence()
        self.assertIn("unsupported or missing required scopes", self.run_action(expected=1)["reasons"][0])
        self.evidence["required_scopes"] = ["documentation"]
        self.save_evidence()
        result = self.run_action("dry-run")
        self.assertEqual(result["compatibility"]["clients"][0]["untested_scopes"], ["development", "fastpath"])

    def test_missing_mode_and_unsafe_transaction_are_refused(self):
        before = self.tree()
        self.run_action(expected=1)
        self.run_action("apply", "--mode", "leaf", "--transaction", self.root / "transaction", expected=1)
        self.assertEqual(before, self.tree())

    def test_prerequisite_diagnostics_name_bounded_next_action(self):
        self.legacy()
        before = self.tree()
        result = self.invoke("dry-run", expected=1)
        self.assertEqual(result["next_action"]["steps"], ["prepare", "collect", "independent-review", "report"])
        for client, version, mode in (("opencode", "1.18.34", "run-explicit-dir"), ("codex", "0.160.1", "native-app-server")):
            self.evidence["clients"][0].update(client=client, version=version, mode=mode)
            self.save_evidence()
            result = self.run_action("dry-run", expected=1)
            self.assertIn("require extended environment_files evidence", result["reasons"][0])
            self.assertIn("Do not inspect or edit AI-kit", result["next_action"]["instruction"])
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())

    def test_extended_environment_inventory_detects_added_removed_changed_inputs(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("compat_inventory_test", SCRIPTS / "doc-compat.py")
        collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(collector)
        self.legacy()
        ancestor = self.base / "AGENTS.md"
        ancestor.write_text("Ancestor fixture instructions.\n")
        self.evidence["environment_files"] = collector.environment_files(self.root)
        self.save_evidence()
        self.run_action("dry-run")
        mutations = ((ancestor, None), (ancestor, "Changed instructions.\n"), (self.root / "AGENTS.md", "Changed target.\n"), (self.base / "CLAUDE.local.md", "Added instructions.\n"))
        for path, replacement in mutations:
            original = path.read_bytes() if path.exists() else None
            if replacement is None:
                path.unlink()
            else:
                path.write_text(replacement)
            before = self.tree()
            result = self.run_action("dry-run", expected=1)
            self.assertIn("environment_files differ", result["reasons"][0])
            self.assertEqual(before, self.tree())
            self.assertFalse(self.transaction.exists())
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    @unittest.skipIf(os.geteuid() == 0, "permission regression requires a nonprivileged process")
    def test_unwritable_profile_directory_refuses_before_mutation(self):
        self.legacy()
        directory = self.root / "docs"
        original_mode = stat.S_IMODE(directory.stat().st_mode)
        directory.chmod(0o555)
        try:
            before = self.tree()
            index = (self.root / ".git/index").read_bytes()
            self.assertTrue(os.access(self.root / "docs/.doc-profile", os.W_OK))
            for action in ("dry-run", "apply"):
                result = self.run_action(action, expected=1)
                self.assertIn("write and search access to directory", result["reasons"][0])
                self.assertEqual(self.tree(), before)
                self.assertEqual((self.root / ".git/index").read_bytes(), index)
                self.assertFalse(self.transaction.exists())
        finally:
            directory.chmod(original_mode)

    @unittest.skipIf(os.geteuid() == 0, "permission regression requires a nonprivileged process")
    def test_rollback_skips_unchanged_profile_in_unwritable_directory(self):
        self.legacy()
        before = self.tree()
        self.run_action(env=dict(os.environ, MRCALL_DOC_MIGRATE_TEST_CRASH_AFTER="CLAUDE.md"), expected=86)
        directory = self.root / "docs"
        original_mode = stat.S_IMODE(directory.stat().st_mode)
        directory.chmod(0o555)
        before["docs"] = ("directory", 0o555)
        try:
            result = self.invoke("rollback", "--transaction", self.transaction)
            self.assertEqual(result["state"], "rolled_back")
            self.assertEqual(self.tree(), before)
        finally:
            directory.chmod(original_mode)

    @unittest.skipIf(os.geteuid() == 0, "permission regression requires a nonprivileged process")
    def test_rollback_restores_recoverable_paths_and_reports_remaining_failure(self):
        self.legacy()
        before = self.tree()
        self.run_action()
        directory = self.root / "docs"
        original_mode = stat.S_IMODE(directory.stat().st_mode)
        directory.chmod(0o555)
        try:
            result = self.invoke("rollback", "--transaction", self.transaction, expected=1)
            self.assertIn("rollback incomplete", result["reasons"][0])
            self.assertIn("docs/.doc-profile", result["reasons"][0])
            current = self.tree()
            self.assertEqual(current["AGENTS.md"], before["AGENTS.md"])
            self.assertEqual(current["CLAUDE.md"], before["CLAUDE.md"])
            self.assertNotEqual(current["docs/.doc-profile"], before["docs/.doc-profile"])
            manifest = json.loads((self.transaction / "manifest.json").read_text())
            self.assertEqual(manifest["state"], "rollback_incomplete")
            self.assertEqual(len(manifest["rollback_errors"]), 1)
        finally:
            directory.chmod(original_mode)
        self.invoke("rollback", "--transaction", self.transaction)
        self.assertEqual(self.tree(), before)

    def test_worktree_gitfile_transaction_binding(self):
        self.legacy()
        self.git("add", ".")
        self.git("commit", "-m", "legacy fixture")
        child = self.base / "child"
        self.git("worktree", "add", "-b", "child", str(child))
        self.root = child
        self.evidence["repo"] = str(child)
        inspected = self.invoke("inspect", expected=1)
        self.evidence["instruction_files"] = inspected["instruction_files"]
        self.save_evidence()
        self.run_action()
        self.checker()
        self.invoke("rollback", "--transaction", self.transaction)


if __name__ == "__main__":
    unittest.main()
