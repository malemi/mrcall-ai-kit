"""Focused deterministic upgrade acceptance; no native clients or runtime claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "shared/scripts"
SCOPE = "<!-- doc-scope:start -->\nScope: Disposable upgrade acceptance fixture.\n<!-- doc-scope:end -->\n"


class UpgradeCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="doc-upgrade-cli-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        (self.root / "docs/execution-plans").mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Project\n" + SCOPE + "Keep every operating rule.\n")
        (self.root / "docs/README.md").write_text(SCOPE)
        (self.root / "app.py").write_text("print('application unchanged')\n")
        self.git("init", "-b", "main")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "docs/active-context.md").write_text(f"---\ndoc_baseline_commit: {head}\n---\n" + SCOPE + "## State now\nFixture.\n## Unresolved\nNone.\n## Next\nNone.\n")
        (self.root / "CLAUDE.md").write_bytes((ROOT / "shared/templates/legacy/v8/CLAUDE.md").read_bytes())
        (self.root / "docs/.doc-profile").write_text("harness_version = 8\nmode = leaf\nindex_file = AGENTS.md\nharness_file = CLAUDE.md\n")
        self.transaction = self.base / "transaction"

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, check=True)

    def tree(self):
        result = {}
        for base, directories, files in os.walk(self.root):
            if Path(base) == self.root:
                directories.remove(".git")
            for name in directories + files:
                path = Path(base) / name
                mode = path.lstat().st_mode
                payload = os.readlink(path) if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest() if stat.S_ISREG(mode) else ""
                result[str(path.relative_to(self.root))] = [mode, payload]
        return result

    def invoke(self, action, *args, expected=0):
        argv = [sys.executable, str(SCRIPTS / "doc-migrate.py"), action, "--repo", str(self.root), "--json", *map(str, args)]
        started = time.monotonic()
        proc = subprocess.run(argv, text=True, capture_output=True, timeout=20)
        log = os.environ.get("MRCALL_UPGRADE_CLI_LOG")
        if log:
            with open(log, "a") as stream:
                stream.write(json.dumps({"test": self.id(), "argv": argv, "seconds": time.monotonic() - started, "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}) + "\n")
        self.assertEqual(proc.returncode, expected, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_default_upgrade_and_exact_rollback(self):
        before = self.tree()
        index_before = (self.root / ".git/index").read_bytes()
        for action in ("inspect", "dry-run"):
            result = self.invoke(action)
            self.assertTrue(result["ready"])
            self.assertEqual(result["compatibility"]["status"], "not-evaluated")
            self.assertEqual(before, self.tree())
            self.assertFalse(self.transaction.exists())
        self.assertEqual(self.invoke("apply", "--transaction", self.transaction)["state"], "applied")
        check = subprocess.run([sys.executable, str(SCRIPTS / "doc-check.py"), "--repo", str(self.root), "--json"], capture_output=True, text=True, timeout=20)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertEqual(json.loads(check.stdout)["mechanical_gate"], "clean")
        manifest = json.loads((self.transaction / "manifest.json").read_text())
        self.assertEqual(manifest["compatibility"]["status"], "not-evaluated")
        self.assertEqual(self.invoke("inspect")["changes"], [])
        self.assertEqual(self.invoke("rollback", "--transaction", self.transaction)["state"], "rolled_back")
        self.assertEqual(before, self.tree())
        self.assertEqual(index_before, (self.root / ".git/index").read_bytes())

    def test_mechanical_repair_and_retry(self):
        plan = self.root / "docs/execution-plans/2026-10-08-fixture.md"
        plan.write_text("---\nstatus: done\n---\n# Finished fixture\nAll work finished.\n")
        (self.root / "README.md").write_text("[Instructions](CLAUDE.md)\n")
        before = self.tree()
        result = self.invoke("apply", "--transaction", self.transaction, expected=1)
        self.assertEqual(result["next_action"]["operation"], "repair-target-documentation")
        self.assertIn("PLAN STATUS", result["mechanical_validation"]["violations"])
        self.assertIn("DEAD LINKS", result["mechanical_validation"]["violations"])
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())
        plan.write_text("---\nstatus: completed\n---\n# Finished fixture\nAll work finished.\n")
        (self.root / "README.md").write_text("[Instructions](AGENTS.md)\n")
        self.assertTrue(self.invoke("inspect")["ready"])

    def test_supplied_invalid_report_and_foreign_ownership_refuse(self):
        report = self.base / "bad-report.json"
        report.write_text('{"schema_version":1,"repo":"/wrong-target"}')
        before = self.tree()
        result = self.invoke("apply", "--compatibility", report, "--transaction", self.transaction, expected=1)
        self.assertEqual(result["next_action"]["operation"], "review-supplied-compatibility")
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())
        (self.root / "CLAUDE.md").write_text("Foreign instructions; preserve me.\n")
        before = self.tree()
        result = self.invoke("apply", "--transaction", self.transaction, expected=1)
        self.assertEqual(result["next_action"]["operation"], "request-claude-adoption")
        self.assertEqual(result["state"], "awaiting-authorization")
        self.assertTrue(result["next_action"]["approval_required"])
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())

    def test_custom_claude_consent_apply_and_exact_rollback(self):
        custom = self.root / "CLAUDE.md"
        custom.write_text("# Project rules\nKeep the invoice rounding rule.\n")
        custom.chmod(0o640)
        before_consent = self.tree()
        request = self.invoke("inspect", expected=1)
        approved = request["next_action"]["sha256"]
        self.assertEqual(approved, hashlib.sha256(custom.read_bytes()).hexdigest())
        self.assertEqual(before_consent, self.tree())
        self.assertFalse(self.transaction.exists())
        # Simulate the operator-approved preservation proposal, outside the
        # helper transaction; managed rollback preserves this separate repair.
        with (self.root / "AGENTS.md").open("a") as stream:
            stream.write("\nKeep the invoice rounding rule.\n")
        prepared = self.tree()
        for action in ("inspect", "dry-run"):
            result = self.invoke(action, "--adopt-claude-sha256", approved)
            self.assertTrue(result["ready"])
            self.assertEqual(prepared, self.tree())
        result = self.invoke("apply", "--adopt-claude-sha256", approved, "--transaction", self.transaction)
        self.assertEqual(result["state"], "applied")
        self.assertFalse(custom.exists())
        self.assertIn("Keep the invoice rounding rule.", (self.root / "AGENTS.md").read_text())
        manifest = json.loads((self.transaction / "manifest.json").read_text())
        self.assertEqual(manifest["claude_adoption"]["sha256"], approved)
        check = subprocess.run([sys.executable, str(SCRIPTS / "doc-check.py"), "--repo", str(self.root), "--json"], capture_output=True, text=True, timeout=20)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.invoke("rollback", "--transaction", self.transaction)
        self.assertEqual(prepared, self.tree())

    def test_adoption_cannot_bypass_stale_absent_symlink_or_sidecar(self):
        custom = self.root / "CLAUDE.md"
        custom.write_text("Custom project instructions.\n")
        approved = self.invoke("inspect", expected=1)["next_action"]["sha256"]
        custom.write_text("Changed after proposal.\n")
        before = self.tree()
        result = self.invoke("apply", "--adopt-claude-sha256", approved, "--transaction", self.transaction, expected=1)
        self.assertIn("stale", result["reasons"][0])
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())
        custom.unlink()
        before = self.tree()
        self.invoke("apply", "--adopt-claude-sha256", approved, "--transaction", self.transaction, expected=1)
        self.assertEqual(before, self.tree())
        custom.symlink_to("AGENTS.md")
        before = self.tree()
        self.invoke("apply", "--adopt-claude-sha256", approved, "--transaction", self.transaction, expected=1)
        self.assertEqual(before, self.tree())
        custom.unlink()
        custom.write_text("Custom project instructions.\n")
        (self.root / "CLAUDE.local.md").write_text("Preserve this unrelated file.\n")
        before = self.tree()
        self.invoke("apply", "--adopt-claude-sha256", approved, "--transaction", self.transaction, expected=1)
        self.assertEqual(before, self.tree())
        self.assertFalse(self.transaction.exists())

    def test_meta_child_data_remains_opaque(self):
        child = self.root / "child"
        child.mkdir()
        (child / ".git").mkdir()
        os.mkfifo(child / "runtime.pipe")
        with (self.root / "AGENTS.md").open("a") as stream:
            stream.write("\n## Services\n\n| Service | Path |\n|---|---|\n| Child | `child/` |\n")
        (self.root / "docs/.doc-profile").write_text("harness_version = 8\nmode = meta\nindex_file = AGENTS.md\nharness_file = CLAUDE.md\n")
        before = self.tree()
        self.assertTrue(self.invoke("inspect")["ready"])
        self.assertTrue(self.invoke("dry-run")["ready"])
        self.assertEqual(self.invoke("apply", "--transaction", self.transaction)["state"], "applied")
        check = subprocess.run([sys.executable, str(SCRIPTS / "doc-check.py"), "--repo", str(self.root), "--json"], capture_output=True, text=True, timeout=20)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertEqual(self.invoke("rollback", "--transaction", self.transaction)["state"], "rolled_back")
        self.assertEqual(before, self.tree())

    def test_existing_root_alias_cannot_hide_retired_claude(self):
        (self.root / "alias.md").symlink_to("CLAUDE.md")
        (self.root / "README.md").write_text("[Instructions](alias.md)\n")
        result = self.invoke("inspect", expected=1)
        self.assertIn("DEAD LINKS", result["mechanical_validation"]["violations"])
        self.assertEqual(os.readlink(self.root / "alias.md"), "CLAUDE.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--installed", action="store_true")
    options, remaining = parser.parse_known_args()
    if options.installed:
        SCRIPTS = Path(os.environ.get("MRCALL_KIT_HOME", str(Path.home() / ".config/mrcall-ai-kit")))
    unittest.main(argv=[sys.argv[0], *remaining])
