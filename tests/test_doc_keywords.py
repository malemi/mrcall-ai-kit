"""CLI behavior of the keyword check on real temporary Git repositories."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "shared/scripts/doc-keywords.py"


class DocKeywordsCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "docs").mkdir()
        (self.repo / "README.md").write_text("Beacon guide.\n")
        self.active = self.repo / "docs/active-context.md"
        self.active.write_text("# Active Context\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Seed beacon guide")
        self.baseline = self.git("rev-parse", "HEAD").stdout.strip()
        self.active.write_text(f"---\ndoc_baseline_commit: {self.baseline}\n---\n\n# Active Context\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Add signal report")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True, capture_output=True, text=True,
        )

    def check_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo), "--json", *args],
            capture_output=True, text=True,
        )

    def test_baseline_and_missing_baseline_fallback(self):
        result = self.check_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["range"], f"{self.baseline}..HEAD")
        self.assertIn("signal", data["keywords"])
        self.assertNotIn("beacon", data["keywords"])

        self.active.write_text("---\ndoc_baseline_commit: invalid-baseline\n---\n\n# Active Context\n")
        result = self.check_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["range"], "HEAD")
        self.assertIn("beacon", data["keywords"])
        self.assertFalse(any(token in data["keywords"] for token in (self.baseline[:7], self.git("rev-parse", "HEAD").stdout.strip()[:7])))

        tree = self.git("write-tree").stdout.strip()
        unrelated = self.git("commit-tree", tree, "-m", "Unrelated branch").stdout.strip()
        self.active.write_text(f"---\ndoc_baseline_commit: {unrelated}\n---\n\n# Active Context\n")
        non_ancestor = self.check_cli()
        self.assertEqual(non_ancestor.returncode, 0, non_ancestor.stderr)
        self.assertEqual(json.loads(non_ancestor.stdout)["range"], "HEAD")

        docs_only = self.check_cli("--docs-only")
        self.assertEqual(docs_only.returncode, 0, docs_only.stderr)
        self.assertEqual(json.loads(docs_only.stdout)["coverage"]["beacon"], [])

    def test_invalid_explicit_range_is_an_error(self):
        result = self.check_cli("--range", "not-a-commit..HEAD")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("doc-keywords: Git command failed", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_recent_ten_commits_in_long_history(self):
        self.active.write_text("# Active Context\n")
        for number in range(10):
            (self.repo / f"change-{number}.txt").write_text(str(number))
            self.git("add", ".")
            self.git("commit", "-qm", f"Record topic{number}")
        result = self.check_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["range"], "HEAD~10..HEAD")
        self.assertNotIn("beacon", data["keywords"])
        self.assertNotIn("signal", data["keywords"])


if __name__ == "__main__":
    unittest.main()
