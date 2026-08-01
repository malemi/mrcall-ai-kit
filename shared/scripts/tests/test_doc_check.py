"""End-to-end stdlib tests for doc-check.py."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).parents[1] / "doc-check.py"
COMMANDS = Path(__file__).parents[2] / "commands"


class DocCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs" / "execution-plans").mkdir(parents=True)
        (self.root / "README.md").write_text("# Readme\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 1\nmode = leaf\nindex_file = CLAUDE.md\ninventory_ignore =\n",
            encoding="utf-8",
        )
        self.git("init")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Tests")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "docs" / "active-context.md").write_text(
            f"---\ndoc_baseline_commit: {baseline}\n---\n# Context\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def check(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(CHECKER), "--repo", str(self.root)],
            text=True, capture_output=True,
        )

    def test_clean_repo_reports_mechanical_gate(self) -> None:
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MECHANICAL GATE CLEAN", result.stdout)
        self.assertIn("harness v1", result.stdout)

    def test_all_commands_embed_the_checker_harness_version(self) -> None:
        checker_source = CHECKER.read_text(encoding="utf-8")
        self.assertIn("HARNESS_VERSION = 1", checker_source)
        for name in ("doc-create.md", "doc-start.md", "doc-end.md"):
            command = (COMMANDS / name).read_text(encoding="utf-8")
            self.assertIn("implements `harness_version = 1`", command, name)

    def test_dead_links_are_checked_recursively(self) -> None:
        nested = self.root / "docs" / "briefs" / "nested"
        nested.mkdir(parents=True)
        (nested / "brief.md").write_text("[missing](nope.md)\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/briefs/nested/brief.md", result.stdout)
        self.assertIn("[DEAD LINKS]", result.stdout)

    def test_profile_schema_rejects_unknown_invalid_and_empty_values(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 1\nmode = other\nindex_file = missing.md\n"
            "build =\nunknown = yes\nindex_max_lines = no\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertIn("[PROFILE]", result.stdout)
        self.assertIn("unknown key `unknown`", result.stdout)
        self.assertIn("must be `leaf` or `meta`", result.stdout)
        self.assertIn("`build` must not be empty", result.stdout)
        self.assertIn("non-negative integer", result.stdout)

    def test_index_file_must_be_markdown(self) -> None:
        (self.root / "INDEX.txt").write_text("index\n", encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 1\nmode = leaf\nindex_file = INDEX.txt\n", encoding="utf-8"
        )
        self.assertIn("must be a Markdown (`.md`) file", self.check().stdout)

    def test_schema_version_one_is_supported_and_optional(self) -> None:
        profile = self.root / "docs" / ".doc-profile"
        self.assertEqual(self.check().returncode, 0)  # schema_version is independent and optional
        profile.write_text(
            "harness_version = 1\nschema_version = 1\nmode = leaf\nindex_file = CLAUDE.md\n",
            encoding="utf-8",
        )
        self.assertEqual(self.check().returncode, 0)
        profile.write_text(
            "harness_version = 1\nschema_version = 2\nmode = leaf\nindex_file = CLAUDE.md\n",
            encoding="utf-8",
        )
        self.assertIn("`schema_version` must be `1`", self.check().stdout)

    def test_thin_index_limit_is_configurable_and_zero_disables_it(self) -> None:
        (self.root / "CLAUDE.md").write_text("one\ntwo\nthree\n", encoding="utf-8")
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text("harness_version = 1\nmode = leaf\nindex_file = CLAUDE.md\nindex_max_lines = 2\n", encoding="utf-8")
        self.assertIn("[THIN INDEX]", self.check().stdout)
        profile.write_text("harness_version = 1\nmode = leaf\nindex_file = CLAUDE.md\nindex_max_lines = 0\n", encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)

    def test_missing_harness_version_requires_docs_migration(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "mode = leaf\nindex_file = CLAUDE.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing `harness_version`", result.stdout)
        self.assertIn("migrate docs/", result.stdout)

    def test_non_positive_harness_version_is_rejected(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 0\nmode = leaf\nindex_file = CLAUDE.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertIn("positive integer", result.stdout)

    def test_newer_harness_version_requires_command_upgrade(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 2\nmode = leaf\nindex_file = CLAUDE.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("newer than installed version 1", result.stdout)
        self.assertIn("upgrade the installed", result.stdout)

    def test_execution_plan_requires_enumerated_status(self) -> None:
        plan = self.root / "docs" / "execution-plans" / "work.md"
        plan.write_text("---\nstatus: doing\n---\n# Work\n", encoding="utf-8")
        result = self.check()
        self.assertIn("[PLAN STATUS]", result.stdout)
        self.assertIn("invalid status `doing`", result.stdout)
        plan.write_text("---\nstatus: active\n---\n# Work\n", encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)

    def test_execution_plan_rejects_duplicate_status(self) -> None:
        plan = self.root / "docs" / "execution-plans" / "work.md"
        plan.write_text(
            "---\nstatus: active\nstatus: completed\n---\n# Work\n", encoding="utf-8"
        )
        result = self.check()
        self.assertIn("exactly one `status`", result.stdout)

    def test_missing_baseline_commit_is_a_violation(self) -> None:
        (self.root / "docs" / "active-context.md").write_text(
            "---\ndoc_baseline_commit: deadbeef\n---\n", encoding="utf-8"
        )
        result = self.check()
        self.assertIn("[BASELINE]", result.stdout)
        self.assertIn("does not exist", result.stdout)

    def test_existing_non_ancestor_baseline_is_a_violation(self) -> None:
        main = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "--orphan", "detached-history")
        for path in self.root.iterdir():
            if path.name != ".git" and path.is_file():
                path.unlink()
        self.git("add", "-A")
        (self.root / "orphan.txt").write_text("orphan\n", encoding="utf-8")
        self.git("add", "orphan.txt")
        self.git("commit", "-m", "orphan")
        orphan = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", main)
        (self.root / "docs" / "active-context.md").write_text(
            f"---\ndoc_baseline_commit: {orphan}\n---\n", encoding="utf-8"
        )
        result = self.check()
        self.assertIn("not an ancestor of HEAD", result.stdout)


if __name__ == "__main__":
    unittest.main()
