"""End-to-end stdlib tests for doc-check.py."""
from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).parents[1] / "doc-check.py"
COMMANDS = Path(__file__).parents[2] / "commands"


def load_checker():
    """Import doc-check.py as a module (its hyphen keeps it off the import path).

    Only for assertions about a single function in isolation; everything else
    goes through the CLI, which is how the harness actually invokes it.
    """
    spec = importlib.util.spec_from_file_location("doc_check", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs" / "execution-plans").mkdir(parents=True)
        (self.root / "README.md").write_text("# Readme\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ninventory_ignore =\n",
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
        self.assertIn("harness v3", result.stdout)

    def test_all_commands_embed_the_checker_harness_version(self) -> None:
        checker_source = CHECKER.read_text(encoding="utf-8")
        self.assertIn("HARNESS_VERSION = 3", checker_source)
        for name in ("doc-create.md", "doc-start.md", "doc-end.md"):
            command = (COMMANDS / name).read_text(encoding="utf-8")
            self.assertIn("implements `harness_version = 3`", command, name)

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
            "harness_version = 3\nmode = other\nindex_file = missing.md\n"
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
            "harness_version = 3\nmode = leaf\nindex_file = INDEX.txt\n", encoding="utf-8"
        )
        self.assertIn("must be a Markdown (`.md`) file", self.check().stdout)

    def test_schema_version_one_is_supported_and_optional(self) -> None:
        profile = self.root / "docs" / ".doc-profile"
        self.assertEqual(self.check().returncode, 0)  # schema_version is independent and optional
        profile.write_text(
            "harness_version = 3\nschema_version = 1\nmode = leaf\nindex_file = CLAUDE.md\n",
            encoding="utf-8",
        )
        self.assertEqual(self.check().returncode, 0)
        profile.write_text(
            "harness_version = 3\nschema_version = 2\nmode = leaf\nindex_file = CLAUDE.md\n",
            encoding="utf-8",
        )
        self.assertIn("`schema_version` must be `1`", self.check().stdout)

    def test_thin_index_limit_is_configurable_and_zero_disables_it(self) -> None:
        (self.root / "CLAUDE.md").write_text("one\ntwo\nthree\n", encoding="utf-8")
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text("harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\nindex_max_lines = 2\n", encoding="utf-8")
        self.assertIn("[THIN INDEX]", self.check().stdout)
        profile.write_text("harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\nindex_max_lines = 0\n", encoding="utf-8")
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
            "harness_version = 4\nmode = leaf\nindex_file = CLAUDE.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("newer than installed version 3", result.stdout)
        self.assertIn("upgrade the installed", result.stdout)

    def test_older_harness_version_requires_docs_upgrade(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 1\nmode = leaf\nindex_file = CLAUDE.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs harness version 1 is older than installed version 3", result.stdout)
        self.assertIn("migrate docs/", result.stdout)

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

    def _context(self, body: str) -> None:
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "docs" / "active-context.md").write_text(
            f"---\ndoc_baseline_commit: {baseline}\n---\n\n# Active Context\n{body}",
            encoding="utf-8",
        )

    def test_living_context_accepts_only_the_canonical_sections(self) -> None:
        self._context(
            "\n## State now\nfine\n\n## Unresolved\n- none\n\n## Next\n- ship\n"
        )
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        self._context(
            "\n## State now\nfine\n\n## 2026-05-28 — what we did\nnarrative\n\n## Next\n- ship\n"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[LIVING CONTEXT]", result.stdout)
        self.assertIn("2026-05-28 — what we did", result.stdout)
        self.assertIn("active-context-archive.md", result.stdout)

    def test_living_context_section_match_is_case_insensitive_and_allows_subsections(self) -> None:
        self._context(
            "\n## state now\nfine\n### a subsection is fine\ndetail\n\n## NEXT\n- ship\n"
        )
        self.assertEqual(self.check().returncode, 0, self.check().stdout)

    def test_living_context_ignores_headings_inside_code_fences(self) -> None:
        """A `## ...` line inside a fenced block is content, not a section."""
        self._context(
            "\n## State now\n\n```markdown\n## 2026-05-28 — this is an example, not a section\n```\n\n"
            "~~~\n## nor is this\n~~~\n\n## Next\n- ship\n"
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_living_context_check_is_skipped_when_the_file_is_absent(self) -> None:
        (self.root / "docs" / "active-context.md").unlink()
        result = self.check()
        self.assertNotIn("[LIVING CONTEXT]", result.stdout)

    def test_living_context_does_not_police_the_archive(self) -> None:
        """The archive is all dated sections by design; only active-context.md is shaped."""
        self._context("\n## State now\nfine\n\n## Next\n- ship\n")
        (self.root / "docs" / "active-context-archive.md").write_text(
            "# Active Context Archive\n\n## 2026-05-28 — old\nnarrative\n\n## 2026-05-01 — older\nmore\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_archive_file_is_indexed_like_any_other_doc(self) -> None:
        """docs/active-context-archive.md gets no special treatment: it is
        link-checked like any other file under docs/, and is not subject to
        the thin-index line limit (that only applies to index_file)."""
        archive = self.root / "docs" / "active-context-archive.md"
        archive.write_text(
            "# Active Context Archive\n\n" + ("## old — filler\ncontent\n" * 200)
            + "\n[missing](nope.md)\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/active-context-archive.md", result.stdout)
        self.assertIn("[DEAD LINKS]", result.stdout)
        self.assertNotIn("[THIN INDEX]", result.stdout)
    def test_oversized_docs_are_reported_without_failing_the_gate(self) -> None:
        """Advisory by construction: it names the file and changes nothing else.

        A doc under docs/projects/** is the case that matters — a session must
        never open those, so a path and a line count is the only way it can learn
        one has exploded.
        """
        project = self.root / "docs" / "projects" / "acme"
        project.mkdir(parents=True)
        (project / "status.md").write_text("filler\n" * 500, encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("MECHANICAL GATE CLEAN", result.stdout)
        self.assertIn("docs/projects/acme/status.md: 500 lines", result.stdout)
        self.assertIn("NOT a gate failure", result.stdout)

    def test_doc_size_limit_is_configurable_and_zero_disables_it(self) -> None:
        project = self.root / "docs" / "projects" / "acme"
        project.mkdir(parents=True)
        (project / "status.md").write_text("filler\n" * 150, encoding="utf-8")
        (project / "small.md").write_text("filler\n" * 50, encoding="utf-8")
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertIn("status.md: 150 lines (advisory limit: 100)", result.stdout)
        self.assertNotIn("small.md", result.stdout)
        profile.write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ndoc_max_lines = 0\n",
            encoding="utf-8",
        )
        self.assertNotIn("advisory", self.check().stdout)

    def test_oversized_archive_is_exempt_from_the_size_report(self) -> None:
        """Cold storage grows forever by design; flagging it every run is noise."""
        (self.root / "docs" / "active-context-archive.md").write_text(
            "filler\n" * 5000, encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("advisory", result.stdout)

    def test_size_advisory_accompanies_a_failing_gate_without_masking_it(self) -> None:
        project = self.root / "docs" / "projects" / "acme"
        project.mkdir(parents=True)
        (project / "status.md").write_text("filler\n" * 500, encoding="utf-8")
        (self.root / "docs" / "README.md").write_text("[missing](nope.md)\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("MECHANICAL GATE FAILED", result.stdout)
        self.assertIn("[DEAD LINKS]", result.stdout)
        self.assertIn("docs/projects/acme/status.md: 500 lines", result.stdout)

    def test_invalid_doc_max_lines_is_a_profile_error(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ndoc_max_lines = abc\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("`doc_max_lines` must be a non-negative integer", result.stdout)

    def test_size_report_boundary_is_strictly_greater_than_the_limit(self) -> None:
        """Exactly at the limit is fine; one line over is not.

        Without this the `>` could silently become `>=` and every fixture built
        on 500-vs-400 would still pass while the whole repo gained a warning.
        """
        doc = self.root / "docs" / "edge.md"
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        doc.write_text("filler\n" * 100, encoding="utf-8")
        self.assertNotIn("edge.md", self.check().stdout)
        doc.write_text("filler\n" * 101, encoding="utf-8")
        self.assertIn("edge.md: 101 lines", self.check().stdout)

    def test_size_report_counts_lines_the_way_wc_does(self) -> None:
        """The number must be reproducible without opening the file.

        `splitlines()` also breaks on form feeds and unicode separators, so it
        would report more lines than `wc -l` for a doc containing them.
        """
        (self.root / "docs" / "feed.md").write_text(
            "filler\n" * 101 + "a\x0cb\x0cc d\n", encoding="utf-8"
        )
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        self.assertIn("feed.md: 102 lines", self.check().stdout)

    def test_size_report_orders_largest_first_then_alphabetically(self) -> None:
        docs = self.root / "docs"
        (docs / "big.md").write_text("filler\n" * 300, encoding="utf-8")
        (docs / "beta.md").write_text("filler\n" * 200, encoding="utf-8")
        (docs / "alpha.md").write_text("filler\n" * 200, encoding="utf-8")
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        listed = [
            line.split(":")[0].strip().removeprefix("- ")
            for line in self.check().stdout.splitlines()
            if line.strip().startswith("- docs/")
        ]
        self.assertEqual(
            listed, ["docs/big.md", "docs/alpha.md", "docs/beta.md"]
        )

    def test_negative_doc_max_lines_reports_nothing_beyond_the_profile_error(self) -> None:
        """A negative limit must not make `count > maximum` true for every doc.

        The profile error is the real answer; dumping the whole repo underneath
        it would flood exactly the context this report exists to protect.
        """
        (self.root / "docs" / "any.md").write_text("filler\n" * 5, encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 3\nmode = leaf\nindex_file = CLAUDE.md\ndoc_max_lines = -1\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("`doc_max_lines` must be a non-negative integer", result.stdout)
        self.assertNotIn("advisory", result.stdout)

    def test_size_report_degrades_instead_of_raising(self) -> None:
        """The advisory must never raise: it reports on a run whose exit code is
        otherwise already decided, so an exception there would turn "this doc is
        long" into a blocked commit and a `/doc-end` that cannot advance.

        Driven directly rather than through the CLI on purpose. An undecodable
        `.md` already crashes `check_dead_links`, which runs first — a
        pre-existing defect this check neither causes nor is allowed to hide.
        """
        checker = load_checker()
        (self.root / "docs" / "binary.md").write_bytes(b"\xff\xfe\x00bad\n" * 500)
        (self.root / "docs" / "fine.md").write_text("filler\n" * 50, encoding="utf-8")
        warnings = checker.check_doc_sizes(self.root, "CLAUDE.md", 10)
        # the unreadable doc is skipped, and the scan carries on past it
        self.assertEqual(warnings, ["docs/fine.md: 50 lines (advisory limit: 10)"])

    def test_size_report_survives_a_doc_outside_the_repo_root(self) -> None:
        """`index_file` can resolve inside the repo while not being lexically under
        it — an absolute path reaching the root through a symlink alias. Profile
        validation accepts that (it compares resolved paths), so `relative_to`
        would raise here and take the whole gate down over a long document.

        Pinned because the guard is invisible: nothing in normal use reaches it,
        so a refactor can delete it and every other test still passes.
        """
        checker = load_checker()
        alias = Path(self.temp.name).parent / f"alias-{Path(self.temp.name).name}"
        alias.symlink_to(self.root, target_is_directory=True)
        self.addCleanup(alias.unlink)
        (self.root / "long.md").write_text("filler\n" * 50, encoding="utf-8")
        warnings = checker.check_doc_sizes(self.root, str(alias / "long.md"), 10)
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("long.md: 50 lines", warnings[0])

    def test_undated_trace_files_are_reported_without_failing_the_gate(self) -> None:
        """Work traces are dated by convention; the gate reports, never enforces.

        Blocking on a filename would break every repo predating the convention
        and require a harness version bump — advisory is the deliberate choice.
        """
        briefs = self.root / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "notes.md").write_text("# Notes\n", encoding="utf-8")
        plans = self.root / "docs" / "execution-plans"
        (plans / "work.md").write_text("---\nstatus: active\n---\n# W\n", encoding="utf-8")
        (plans / "2026-08-14-ok.md").write_text("---\nstatus: active\n---\n# OK\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("MECHANICAL GATE CLEAN", result.stdout)
        self.assertIn("2 undated work-trace file(s), NOT a gate failure", result.stdout)
        self.assertIn("docs/briefs/notes.md", result.stdout)
        self.assertIn("docs/execution-plans/work.md", result.stdout)
        self.assertNotIn("2026-08-14-ok.md", result.stdout)

    def test_trace_naming_exempts_readme(self) -> None:
        """A README inside a trace directory is routing, not a trace."""
        briefs = self.root / "docs" / "briefs"
        briefs.mkdir(parents=True)
        (briefs / "README.md").write_text("# Briefs\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("advisory", result.stdout)

    def test_commands_carry_the_work_trace_rule(self) -> None:
        """The creation rule is prose, so a future edit must not drop it.

        The gap this closes was exactly "the artifacts are defined but nothing
        says when to create them": doc-create must ship the briefs directory and
        the naming convention, and doc-end must own the retroactive creation.
        """
        create = (COMMANDS / "doc-create.md").read_text(encoding="utf-8")
        self.assertIn("`docs/briefs/`", create)
        self.assertIn("YYYY-MM-DD-<slug>.md", create)
        end = (COMMANDS / "doc-end.md").read_text(encoding="utf-8")
        self.assertIn("Work traces", end)

    def test_session_status_requires_open_or_closed(self) -> None:
        sessions = self.root / "docs" / "sessions"
        sessions.mkdir()
        session = sessions / "abc123.md"
        session.write_text("---\nstatus: doing\n---\n# Session\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[SESSION STATUS]", result.stdout)
        self.assertIn("invalid status `doing`", result.stdout)
        session.write_text("---\nstatus: open\n---\n# Session\n", encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)
        session.write_text("---\nstatus: closed\n---\n# Session\n", encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)

    def test_session_status_rejects_duplicate_and_missing_status(self) -> None:
        sessions = self.root / "docs" / "sessions"
        sessions.mkdir()
        session = sessions / "abc123.md"
        session.write_text(
            "---\nstatus: open\nstatus: closed\n---\n# Session\n", encoding="utf-8"
        )
        self.assertIn("exactly one `status`", self.check().stdout)
        session.write_text("---\nsession_id: abc123\n---\n# Session\n", encoding="utf-8")
        self.assertIn("frontmatter is missing `status`", self.check().stdout)
        session.write_text("no frontmatter here\n", encoding="utf-8")
        self.assertIn("missing YAML frontmatter with `status`", self.check().stdout)

    def test_open_sessions_are_reported_without_failing_the_gate(self) -> None:
        """Advisory by construction: open mid-session is normal, not drift.

        Whether an open file is stale is a judgment this check has no way to
        make (no PID, no lock) — it only counts, `/router sweep` decides.
        """
        sessions = self.root / "docs" / "sessions"
        sessions.mkdir()
        (sessions / "abc123.md").write_text(
            "---\nstatus: open\nsession_id: abc123\n---\n# Session\n", encoding="utf-8"
        )
        (sessions / "def456.md").write_text(
            "---\nstatus: closed\nsession_id: def456\n---\n# Session\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("MECHANICAL GATE CLEAN", result.stdout)
        self.assertIn("1 open session file(s)", result.stdout)
        self.assertIn("docs/sessions/abc123.md: session still open", result.stdout)
        self.assertNotIn("def456", result.stdout)

    def test_doc_start_never_opens_project_folders(self) -> None:
        """The read-scope rule is load-bearing, so a future edit must not drop it.

        `docs/projects/**` is per-customer working material: opening it at session
        start makes start-up cost scale with the number of customers, which is the
        one thing doc-start must never do.
        """
        command = (COMMANDS / "doc-start.md").read_text(encoding="utf-8")
        self.assertIn("## Read scope — `docs/projects/**` is never opened here", command)
        self.assertIn("`docs/execution-plans/**/*.md` and nothing else", command)
        self.assertIn("`docs/sessions/**`", command)


if __name__ == "__main__":
    unittest.main()
