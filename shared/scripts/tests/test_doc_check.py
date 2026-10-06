"""End-to-end stdlib tests for doc-check.py."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).parents[1] / "doc-check.py"
COMMANDS = Path(__file__).parents[2] / "commands"
HARNESS_DOC = Path(__file__).parents[3] / "docs" / "documentation-harness.md"
HARNESS_TEMPLATE = Path(__file__).parents[2] / "templates" / "AGENTS.block.md"
SCOPE = (
    "<!-- doc-scope:start -->\n"
    "Scope: Test routing document.\n"
    "<!-- doc-scope:end -->\n"
)


def harness_rules() -> str:
    return HARNESS_TEMPLATE.read_text(encoding="utf-8")


def flowed(path: Path) -> str:
    """A document's prose with all whitespace collapsed.

    Contract and command prose wrap at the margin, so a substring assertion on a
    sentence would break the moment an untouched paragraph is reflowed. Matching
    on collapsed whitespace pins the rule and not the line breaks.
    """
    return " ".join(path.read_text(encoding="utf-8").split())


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
        (self.root / "AGENTS.md").write_text(harness_rules() + "# Index\n\n" + SCOPE, encoding="utf-8")
        (self.root / "docs" / "README.md").write_text(
            "# Docs\n\n" + SCOPE, encoding="utf-8"
        )
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\n"
            "inventory_ignore =\n",
            encoding="utf-8",
        )
        self.git("init")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Tests")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "docs" / "active-context.md").write_text(
            f"---\ndoc_baseline_commit: {baseline}\n---\n# Context\n\n{SCOPE}", encoding="utf-8"
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
        self.assertIn("harness v9", result.stdout)

    def test_all_commands_embed_the_checker_harness_version(self) -> None:
        checker_source = CHECKER.read_text(encoding="utf-8")
        self.assertIn("HARNESS_VERSION = 9", checker_source)
        for name in ("doc-create.md", "doc-start.md", "doc-end.md"):
            command = (COMMANDS / name).read_text(encoding="utf-8")
            expected = "This workflow is v9" if name == "doc-start.md" else "implements `harness_version = 9`"
            self.assertIn(expected, command, name)

    def test_doc_create_calls_explicit_migration_helper(self) -> None:
        create = flowed(COMMANDS / "doc-create.md")
        self.assertIn("doc-migrate.py", create)
        self.assertIn("dry-run", create)
        self.assertIn("compatibility", create)

    def test_doc_critic_semantically_checks_scope_declarations(self) -> None:
        critic = flowed(Path(__file__).parents[2] / "skills" / "doc-critic" / "SKILL.md")
        self.assertIn("Scope declarations — validate meaning, not only syntax", critic)
        self.assertIn("misleading or over-broad declaration", critic)
        self.assertIn("do not invent a replacement", critic)

    def test_required_routing_docs_each_need_one_valid_scope(self) -> None:
        for rel in (
            "AGENTS.md",
            "docs/README.md",
            "docs/active-context.md",
        ):
            path = self.root / rel
            original = path.read_text(encoding="utf-8")
            start = original.index("<!-- doc-scope:start -->")
            end = original.index("<!-- doc-scope:end -->", start) + len(
                "<!-- doc-scope:end -->"
            )
            path.write_text(original[:start] + original[end:], encoding="utf-8")
            result = self.check()
            self.assertEqual(result.returncode, 1, rel)
            self.assertIn("[DOC SCOPE]", result.stdout)
            self.assertIn(f"{rel}: missing required doc-scope block", result.stdout)
            path.write_text(original, encoding="utf-8")

    def test_optional_scope_is_validated_when_present(self) -> None:
        doc = self.root / "docs" / "optional.md"
        doc.write_text("# Optional\n", encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)
        doc.write_text(
            "# Optional\n\n<!-- doc-scope:start -->\nScope: \n<!-- doc-scope:end -->\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("`Scope:` text must not be empty", result.stdout)

    def test_scope_rejects_duplicate_partial_reversed_and_wrong_prefix(self) -> None:
        doc = self.root / "docs" / "optional.md"
        cases = (
            (SCOPE + SCOPE, "found 2 start, 2 end"),
            ("<!-- doc-scope:start -->\nScope: partial\n", "found 1 start, 0 end"),
            (
                "<!-- doc-scope:end -->\nScope: reversed\n<!-- doc-scope:start -->\n",
                "delimiters are out of order",
            ),
            (
                "<!-- doc-scope:start -->\nPurpose: one\n<!-- doc-scope:end -->\n",
                "content must begin with `Scope:`",
            ),
        )
        for body, expected in cases:
            with self.subTest(expected=expected):
                doc.write_text(body, encoding="utf-8")
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stdout)

    def test_scope_text_may_continue_across_lines(self) -> None:
        (self.root / "docs" / "optional.md").write_text(
            "<!-- doc-scope:start -->\n"
            "Scope: This document owns current state; it does\n"
            "not own durable design.\n"
            "<!-- doc-scope:end -->\n",
            encoding="utf-8",
        )
        self.assertEqual(self.check().returncode, 0, self.check().stdout)

    def test_scope_markers_in_code_examples_are_not_declarations(self) -> None:
        (self.root / "docs" / "example.md").write_text(
            "# Example\n\n```markdown\n" + SCOPE + "```\n", encoding="utf-8"
        )
        self.assertEqual(self.check().returncode, 0, self.check().stdout)

    def test_external_index_scope_is_obsolete(self) -> None:
        index = self.root / "AGENTS.md"
        index.write_text(
            index.read_text(encoding="utf-8")
            + "\n<!-- doc-index-scope:start -->\nIndex: AGENTS.md\n"
            + "Scope: obsolete\n<!-- doc-index-scope:end -->\n",
            encoding="utf-8",
        )
        self.assertIn("obsolete external index-scope", self.check().stdout)

    def test_configured_index_owns_inline_scope_and_full_line_budget(self) -> None:
        (self.root / "AGENTS.md").write_text(harness_rules() + SCOPE + ("repository owned\n" * (197 - len(harness_rules().splitlines()))), encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("doc-scope", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_managed_harness_must_match_installed_template(self) -> None:
        (self.root / "CLAUDE.md").write_text(harness_rules() + "project rule\n", encoding="utf-8")
        result = self.check()
        self.assertIn("[HARNESS TEMPLATE]", result.stdout)
        self.assertIn("single-entry compatibility unresolved", result.stdout)

    def test_managed_harness_comparison_does_not_normalize_crlf(self) -> None:
        (self.root / "AGENTS.md").write_bytes(
            HARNESS_TEMPLATE.read_bytes().replace(b"\n", b"\r\n")
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[HARNESS TEMPLATE]", result.stdout)
        self.assertIn("differs from canonical template", result.stdout)

    def test_obsolete_v5_sidecar_is_rejected(self) -> None:
        sidecar = self.root / ".claude" / "rules" / "doc-harness.md"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text("# Obsolete\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("single-entry compatibility unresolved", result.stdout)

    def test_dead_links_are_checked_recursively(self) -> None:
        nested = self.root / "docs" / "briefs" / "nested"
        nested.mkdir(parents=True)
        (nested / "brief.md").write_text("[missing](nope.md)\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/briefs/nested/brief.md", result.stdout)
        self.assertIn("[DEAD LINKS]", result.stdout)

    def test_code_is_not_scanned_for_links(self) -> None:
        """Source that looks like a link is not a link.

        `MD_LINK` is `[...](...)`, which a great deal of ordinary code matches:
        `Array.fill[Byte](packetSize)` reads as a link to `packetSize`. Running
        the gate over starchat's docs produced 19 such findings against 1 real
        one, which puts a clean gate out of reach for any repository that
        documents code. Both forms must be blanked — a fenced block and a
        backtick span inside a sentence.
        """
        (self.root / "docs" / "code.md").write_text(
            "# Code\n\n"
            "```scala\n"
            "val buf = Array.fill[Byte](packetSize)(0)\n"
            "```\n\n"
            'Inline, mid-sentence: `get[String]("from")` is a field read.\n'
            "~~~python\n"
            "d = payload[\"k\"](arg)\n"
            "~~~\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("dead link", result.stdout)

    def test_a_real_dead_link_still_fails_beside_code(self) -> None:
        """Blanking code must not blank the document — the check still works."""
        (self.root / "docs" / "mixed.md").write_text(
            "# Mixed\n\n"
            "```scala\n"
            "Array.fill[Byte](packetSize)\n"
            "```\n\n"
            "[gone](nowhere.md)\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("dead link: (nowhere.md)", result.stdout)
        self.assertNotIn("packetSize", result.stdout)

    def test_profile_schema_rejects_unknown_invalid_and_empty_values(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = other\nindex_file = missing.md\n"
            "build =\nunknown = yes\nindex_max_lines = no\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertIn("[PROFILE]", result.stdout)
        self.assertIn("unknown key `unknown`", result.stdout)
        self.assertIn("must be `leaf` or `meta`", result.stdout)
        self.assertIn("`build` must not be empty", result.stdout)
        self.assertIn("non-negative integer", result.stdout)

    def test_release_key_is_optional_and_must_not_be_empty(self) -> None:
        profile = self.root / "docs" / ".doc-profile"
        base = "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\n"
        profile.write_text(base, encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)  # absent: the release phase is not configured
        profile.write_text(base + "release = scripts/release.sh\n", encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)
        profile.write_text(base + "release =\n", encoding="utf-8")
        self.assertIn("`release` must not be empty", self.check().stdout)

    def test_index_file_must_be_markdown(self) -> None:
        (self.root / "INDEX.txt").write_text("index\n", encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = INDEX.txt\n", encoding="utf-8"
        )
        self.assertIn("must be a Markdown (`.md`) file", self.check().stdout)

    def test_schema_version_one_is_supported_and_optional(self) -> None:
        profile = self.root / "docs" / ".doc-profile"
        self.assertEqual(self.check().returncode, 0)  # schema_version is independent and optional
        profile.write_text(
            "harness_version = 9\nschema_version = 1\nmode = leaf\nindex_file = AGENTS.md\n",
            encoding="utf-8",
        )
        self.assertEqual(self.check().returncode, 0)
        profile.write_text(
            "harness_version = 9\nschema_version = 2\nmode = leaf\nindex_file = AGENTS.md\n",
            encoding="utf-8",
        )
        self.assertIn("`schema_version` must be `1`", self.check().stdout)

    def test_harness_file_is_removed_in_v9(self) -> None:
        profile = self.root / "docs/.doc-profile"
        profile.write_text(profile.read_text() + "harness_file = CLAUDE.md\n")
        self.assertIn("removes `harness_file`", self.check().stdout)

    def test_v6_profile_paths_are_fixed_by_ownership_contract(self) -> None:
        (self.root / "PROJECT.md").write_text("# Project\n\n" + SCOPE, encoding="utf-8")
        (self.root / "HARNESS.md").write_text(harness_rules(), encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = PROJECT.md\n"
            "harness_file = HARNESS.md\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertIn("requires `index_file = AGENTS.md`", result.stdout)
        self.assertIn("removes `harness_file`", result.stdout)

    def test_thin_index_limit_is_configurable_and_zero_disables_it(self) -> None:
        (self.root / "AGENTS.md").write_text(harness_rules() + SCOPE, encoding="utf-8")
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text("harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\nindex_max_lines = 2\n", encoding="utf-8")
        self.assertIn("[THIN INDEX]", self.check().stdout)
        profile.write_text("harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\nindex_max_lines = 0\n", encoding="utf-8")
        self.assertEqual(self.check().returncode, 0)

    def test_missing_harness_version_is_unsupported_legacy(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "mode = leaf\nindex_file = AGENTS.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing `harness_version`", result.stdout)
        self.assertIn("doc-create cannot migrate", result.stdout)
        self.assertNotIn("migrate docs/ with", result.stdout)

    def test_non_positive_harness_version_is_rejected(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 0\nmode = leaf\nindex_file = AGENTS.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertIn("positive integer", result.stdout)

    def test_newer_harness_version_requires_command_upgrade(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 10\nmode = leaf\nindex_file = AGENTS.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("newer than installed version 9", result.stdout)
        self.assertIn("upgrade the installed", result.stdout)

    def test_older_harness_version_requires_docs_upgrade(self) -> None:
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 7\nmode = leaf\nindex_file = AGENTS.md\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("docs harness version 7 is older than installed version 9", result.stdout)
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
            f"---\ndoc_baseline_commit: {baseline}\n---\n\n# Active Context\n\n{SCOPE}{body}",
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
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertIn(
            "status.md: 150 lines, 1,050 bytes, ~262 tokens (advisory limit: 100 lines)",
            result.stdout,
        )
        self.assertNotIn("small.md", result.stdout)
        profile.write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = 0\n",
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
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = abc\n",
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
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = 100\n",
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
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        self.assertIn("feed.md: 102 lines", self.check().stdout)

    def test_size_report_carries_bytes_and_a_token_estimate(self) -> None:
        """Lines describe the file; bytes and tokens describe what opening it costs.

        The limits count lines and the context window is billed in bytes, and the
        two do not track each other — so the advisory has to carry the quantity
        that is actually paid, or every argument built on it is unmeasurable.
        `filler\\n` is 7 bytes, so 150 lines is 1,050 bytes and 262 tokens at the
        stated bytes/4 convention.
        """
        docs = self.root / "docs"
        (docs / "long.md").write_text("filler\n" * 150, encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "docs/long.md: 150 lines, 1,050 bytes, ~262 tokens (advisory limit: 100 lines)",
            result.stdout,
        )

    def test_token_estimate_is_bytes_over_four(self) -> None:
        """The divisor is a stated convention, not a tokenizer, and is pinned here.

        Changing it silently would move every number the harness reports while
        every other test still passed.
        """
        checker = load_checker()
        self.assertEqual(checker.BYTES_PER_TOKEN, 4)
        doc = self.root / "docs" / "exact.md"
        doc.write_bytes(b"x" * 4001)
        self.assertEqual(checker.size_note(doc, ""), "4,001 bytes, ~1,000 tokens")

    def test_size_report_counts_bytes_the_way_wc_does(self) -> None:
        """Bytes are `stat`, not `len(text.encode())`.

        `read_text` translates CRLF to LF, so re-encoding the text it returns
        under-reports a CRLF file by one byte per line — 1,050 instead of the
        1,200 `wc -c` prints. The operator has to be able to reproduce the number
        without opening the file, which is the same standard the line count meets.
        """
        (self.root / "docs" / "crlf.md").write_bytes(b"filler\r\n" * 150)
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = 100\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertIn(
            "docs/crlf.md: 150 lines, 1,200 bytes, ~300 tokens (advisory limit: 100 lines)",
            result.stdout,
        )
        self.assertNotIn("1,050 bytes", result.stdout)

    def test_thin_index_failure_carries_bytes_and_a_token_estimate(self) -> None:
        """The thin-index failure is where the line/byte divergence bites hardest.

        A dense table index passes a 200-line limit while being the single most
        expensive item a session loads, so the failure message reports the same
        three numbers as the advisory.
        """
        (self.root / "AGENTS.md").write_text(harness_rules() + SCOPE, encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\nindex_max_lines = 2\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("[THIN INDEX]", result.stdout)
        self.assertIn(
            f"AGENTS.md has {len(harness_rules().splitlines()) + 3} lines, ",
            result.stdout,
        )

    def test_contract_records_the_token_figure_as_a_convention(self) -> None:
        """The estimate must never be presentable as a tokenizer result.

        The contract must label bytes/4 as an estimate and distinguish usage
        totals from actual context occupancy.
        """
        contract = flowed(HARNESS_DOC)
        self.assertIn("Bytes divided by four are only a token estimate.", contract)
        self.assertIn("Cumulative billed tokens and visible text totals are not actual context occupancy.", contract)

    def test_oversized_docs_have_a_recorded_consumer(self) -> None:
        """The advisory's actuator is prose, so a future edit must not drop it.

        A sensor with no actuator is how a document grows from 26 KB to 71 KB
        while being reported at every session: `doc-end` owns the verdict,
        `doc-start` deliberately owns nothing, and the contract records both.
        """
        contract = flowed(HARNESS_DOC)
        self.assertIn("`Oversized docs — reviewed` ledger in `docs/harness-backlog.md`", contract)
        self.assertIn("`doc-start` reports size advisories without editing files. During `doc-end`", contract)
        end = flowed(COMMANDS / "doc-end.md")
        self.assertIn("## Oversized docs — reviewed", end)
        self.assertIn("`docs/harness-backlog.md`", end)

    def test_split_is_deletion_and_never_relocation(self) -> None:
        """The rule exists because the opposite was done, and it cost real work.

        An oversized index was "split" by moving 107 lines of prose into that
        repository's architecture document — which is generated from a template
        and states so in its own header, so the moved text was scheduled for
        destruction on arrival. Nothing was decided, one file shrank, and the
        repository got bigger. A future edit must not quietly drop this.
        """
        end = flowed(COMMANDS / "doc-end.md")
        self.assertIn("`split` means deletion, never relocation.", end)
        self.assertIn("Never move text into a generated file.", end)
        self.assertIn("A durable document is never an append target.", end)
        self.assertIn("belongs in the template that produces the file", end)
        # The contract records that the rule exists; the command file states it.
        contract = flowed(HARNESS_DOC)
        self.assertIn("deletion-first split rules in the closure workflow", contract)
        self.assertIn("do not relocate redundant prose into existing or generated documents", contract)
        self.assertIn("keep whole", end)
        self.assertIn("split logs, never split indexes", end)
        start = flowed(COMMANDS / "doc-start.md")
        self.assertNotIn("Oversized docs — reviewed", start)

    def test_size_report_orders_largest_first_then_alphabetically(self) -> None:
        docs = self.root / "docs"
        (docs / "big.md").write_text("filler\n" * 300, encoding="utf-8")
        (docs / "beta.md").write_text("filler\n" * 200, encoding="utf-8")
        (docs / "alpha.md").write_text("filler\n" * 200, encoding="utf-8")
        profile = self.root / "docs" / ".doc-profile"
        profile.write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = 100\n",
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
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ndoc_max_lines = -1\n",
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
        warnings = checker.check_doc_sizes(
            self.root, "AGENTS.md", "missing-harness.md", 10
        )
        # the unreadable doc is skipped, and the scan carries on past it
        self.assertEqual(
            [w for w in warnings if not w.startswith("AGENTS.md:")],
            ["docs/fine.md: 50 lines, 350 bytes, ~87 tokens (advisory limit: 10 lines)"],
        )

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
        warnings = checker.check_doc_sizes(
            self.root, str(alias / "long.md"), "missing-harness.md", 10
        )
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
        command = (COMMANDS / "doc-start.md").read_text(encoding="utf-8")
        self.assertIn("docs/projects/**", command)
        self.assertIn("docs/sessions/**", command)
        self.assertIn("--startup", command)

    # --- ORIENTATION HEADS (meta mode, advisory) ---

    def _meta_with_sub_repo(self, index_body: str, *, profile: str | None = None) -> None:
        """A meta-repo whose `## Services` table names one sub-repo.

        `index_body` is that sub-repo's index; `profile` gives it a profile of its
        own, which is the case the fallback to `AGENTS.md` must not swallow.
        """
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = meta\nindex_file = AGENTS.md\ninventory_ignore =\n",
            encoding="utf-8",
        )
        (self.root / "AGENTS.md").write_text(
            harness_rules() + "# Index\n\n" + SCOPE + "\n## Services\n\n"
            "| Service | Path | Role |\n"
            "|---------|------|------|\n"
            "| sub | `sub/` | a sub-repo |\n",
            encoding="utf-8",
        )
        sub = self.root / "sub"
        sub.mkdir()
        if profile is None:
            (sub / "AGENTS.md").write_text(index_body, encoding="utf-8")
        else:
            (sub / "docs").mkdir()
            (sub / "docs" / ".doc-profile").write_text(profile, encoding="utf-8")
            (sub / "CLAUDE.md").write_text("# Decoy\n", encoding="utf-8")
            (sub / "AGENTS.md").write_text(index_body, encoding="utf-8")

    def test_sub_repo_index_without_an_orientation_head_is_reported(self) -> None:
        self._meta_with_sub_repo("# Sub\n\n## Docs\n\nsee docs/\n")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MECHANICAL GATE CLEAN", result.stdout)
        self.assertIn("1 sub-repo index(es) without an orientation head", result.stdout)
        self.assertIn("sub/AGENTS.md: no orientation head", result.stdout)

    def test_orientation_marker_silences_the_advisory(self) -> None:
        self._meta_with_sub_repo(
            "# Sub\n\n**Stack**: Python\n\n<!-- orientation ends -->\n\n## Docs\n"
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("orientation head", result.stdout)

    def test_orientation_advisory_does_not_run_in_leaf_mode(self) -> None:
        """A leaf repo has no sub-repos, so the check has nothing to say."""
        self._meta_with_sub_repo("# Sub\n\n## Docs\n")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ninventory_ignore =\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("orientation head", result.stdout)

    def test_sub_repo_profile_names_the_index_that_is_checked(self) -> None:
        """A sub-repo with its own profile is judged on the index it declares."""
        self._meta_with_sub_repo(
            "# Sub\n\n## Docs\n",
            profile="harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\n",
        )
        result = self.check()
        self.assertIn("sub/AGENTS.md: no orientation head", result.stdout)
        self.assertNotIn("sub/CLAUDE.md", result.stdout)

    def test_orientation_advisory_never_fails_the_gate(self) -> None:
        """It rides alongside a real failure without changing the exit code's cause."""
        self._meta_with_sub_repo("# Sub\n\n## Docs\n")
        (self.root / "docs" / "execution-plans" / "p.md").write_text(
            "---\nstatus: nonsense\n---\n# Plan\n", encoding="utf-8"
        )
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[PLAN STATUS]", result.stdout)
        self.assertIn("sub/AGENTS.md: no orientation head", result.stdout)

    def startup(self, structured=True):
        args = ["python3", str(CHECKER), "--repo", str(self.root), "--startup"]
        if structured:
            args.append("--json")
        result = subprocess.run(args, text=True, capture_output=True)
        return result, json.loads(result.stdout) if structured else result.stdout

    def test_startup_text_json_share_every_fact_and_diagnostic(self):
        (self.root / "docs/known-issues").mkdir()
        (self.root / "docs/known-issues/open.md").write_text("---\nstatus: open\n---\n")
        (self.root / "docs/known-issues/missing.md").write_text("No status\n")
        (self.root / "docs/execution-plans/invalid.md").write_text("---\nstatus: invalid\n---\n[bad](missing.md)\n")
        (self.root / "docs/large.md").write_text("filler\n" * 401)
        json_result, facts = self.startup()
        text_result, output = self.startup(False)
        self.assertEqual(json_result.returncode, 1)
        self.assertEqual(text_result.returncode, 1)
        parsed = {line.split(": ", 1)[0]: json.loads(line.split(": ", 1)[1]) for line in output.splitlines()[1:]}
        for key in facts.keys() - {"harness_version", "indexed_docs", "mechanical_gate"}:
            self.assertEqual(parsed[key], facts[key], key)
        self.assertIn("DEAD LINKS", facts["violations"])
        self.assertIn("PLAN STATUS", facts["violations"])
        self.assertIn("oversized", facts["advisories"])
        self.assertIn("unstated_issues", facts["advisories"])
        self.assertEqual(facts["open_plans"][0]["status"], "unknown")
        self.assertEqual(len(facts["open_issues"]), 2)

    def test_startup_duplicate_closed_statuses_remain_unknown_and_visible(self):
        (self.root / "docs/known-issues").mkdir()
        (self.root / "docs/known-issues/duplicate.md").write_text("---\nstatus: open\nstatus: fixed\n---\n")
        (self.root / "docs/execution-plans/duplicate.md").write_text("---\nstatus: active\nstatus: completed\n---\n")
        _, facts = self.startup()
        self.assertEqual(facts["open_issues"][0]["status"], "unknown")
        self.assertEqual(facts["open_plans"][0]["status"], "unknown")
        self.assertIn("duplicate", facts["advisories"]["unstated_issues"][0])

    def test_startup_separates_staged_unstaged_and_untracked(self):
        self.git("add", ".")
        self.git("commit", "-m", "context")
        (self.root / "README.md").write_text("# Staged\n")
        self.git("add", "README.md")
        (self.root / "README.md").write_text("# Also unstaged\n")
        (self.root / "untracked.txt").write_text("new\n")
        _, facts = self.startup()
        self.assertEqual(facts["working_tree"], {"dirty": True, "staged": 1, "unstaged": 1, "untracked": 1})
        self.assertEqual(facts["baseline"]["content_drift_commits"], 0)

    def test_startup_drift_covers_merged_content_history_without_docs_only_commits(self):
        self.git("add", ".")
        self.git("commit", "-m", "context")
        branch = self.git("branch", "--show-current").stdout.strip()
        self.git("checkout", "-b", "feature")
        (self.root / "feature.py").write_text("print(1)\n")
        self.git("add", ".")
        self.git("commit", "-m", "feature")
        self.git("checkout", branch)
        (self.root / "docs/note.md").write_text("# Docs only\n")
        self.git("add", ".")
        self.git("commit", "-m", "docs only")
        self.git("merge", "--no-ff", "feature", "-m", "merge feature")
        _, facts = self.startup()
        self.assertTrue(facts["baseline"]["valid"])
        self.assertEqual(facts["baseline"]["content_drift_commits"], 2)

    def test_startup_irrelevant_bodies_do_not_enter_orientation_output(self):
        self.git("add", ".")
        self.git("commit", "-m", "context")
        _, initial = self.startup()
        (self.root / "docs/projects").mkdir()
        for number in range(15):
            (self.root / f"docs/projects/{number}.md").write_text("PRIVATE_SENTINEL\n" * 10)
        self.git("add", ".")
        self.git("commit", "-m", "project documents")
        _, grown = self.startup()
        initial.pop("indexed_docs")
        grown.pop("indexed_docs")
        self.assertEqual(initial, grown)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(grown))

    def test_managed_block_rejects_duplicate_partial_malformed_and_fenced_markers(self):
        index = self.root / "AGENTS.md"
        canonical = index.read_bytes()
        cases = [canonical + HARNESS_TEMPLATE.read_bytes(), canonical.replace(b"delivery:end", b"delivery:broken"), b"```\n" + canonical + b"```\n", canonical.replace(b"<!-- mrcall-ai-kit:delivery:start -->", b" <!-- mrcall-ai-kit:delivery:start -->")]
        for data in cases:
            index.write_bytes(data)
            self.assertIn("[HARNESS TEMPLATE]", self.check().stdout)

    def test_v8_is_rejected_without_silent_reinterpretation(self):
        profile = self.root / "docs/.doc-profile"
        profile.write_text(profile.read_text().replace("harness_version = 9", "harness_version = 8"))
        _, facts = self.startup()
        self.assertEqual(facts["profile_version"], "8")
        self.assertIn("older than installed version 9", facts["violations"]["PROFILE"][0])

    def test_status_only_reader_does_not_read_body(self):
        checker = load_checker()
        from unittest.mock import mock_open, patch
        stream = mock_open(read_data="---\nstatus: active\n---\nDO NOT READ BODY\n")
        with patch.object(Path, "open", stream):
            self.assertEqual(checker.read_frontmatter(Path("plan.md")), ({"status": "active"}, set()))
            self.assertEqual(stream().read.call_count, 0)
            self.assertEqual(stream().readline.call_count, 1)



class ProtocolReleaseInvariantTests(unittest.TestCase):
    """Kit-self invariant: HARNESS_VERSION equals the newest release tag's major.

    The fixture is a complete clean leaf harness repo plus the kit marker
    (shared/scripts/doc-check.py with a HARNESS_VERSION line), so CLI exit
    codes reflect only this check.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "shared" / "scripts").mkdir(parents=True)
        (self.root / "AGENTS.md").write_text(harness_rules() + "# Index\n\n" + SCOPE, encoding="utf-8")
        (self.root / "docs" / "README.md").write_text("# Docs\n\n" + SCOPE, encoding="utf-8")
        (self.root / "docs" / ".doc-profile").write_text(
            "harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\ninventory_ignore =\n",
            encoding="utf-8",
        )
        self.git("init", "-b", "main")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Tests")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "docs" / "active-context.md").write_text(
            f"---\ndoc_baseline_commit: {baseline}\n---\n# Context\n\n{SCOPE}", encoding="utf-8"
        )
        self.set_constant(9)
        self.git("add", ".")
        self.git("commit", "-m", "kit marker and living context")

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def set_constant(self, value: int) -> None:
        (self.root / "shared" / "scripts" / "doc-check.py").write_text(
            f'"""Fixture stub."""\n\nHARNESS_VERSION = {value}\n', encoding="utf-8"
        )

    def check(self, kit_home: str | None = None) -> tuple[subprocess.CompletedProcess[str], dict]:
        env = dict(os.environ)
        if kit_home is not None:
            env["MRCALL_KIT_HOME"] = kit_home
        result = subprocess.run(
            ["python3", str(CHECKER), "--repo", str(self.root), "--json"],
            text=True, capture_output=True, env=env,
        )
        return result, json.loads(result.stdout)

    def violations(self, payload: dict) -> list[str]:
        return payload["violations"].get("PROTOCOL RELEASE", [])

    def advisories(self, payload: dict) -> list[str]:
        return payload["advisories"].get("protocol_release", [])

    def with_kit_home(self):
        """An MRCALL_KIT_HOME whose doc-check.py resolves inside the fixture:
        the fixture is the installed checkout."""
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        (Path(home.name) / "doc-check.py").symlink_to(self.root / "shared" / "scripts" / "doc-check.py")
        return home.name

    def with_foreign_kit_home(self):
        """An MRCALL_KIT_HOME that resolves nowhere near the fixture."""
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        (Path(home.name) / "doc-check.py").write_text("HARNESS_VERSION = 9\n", encoding="utf-8")
        return home.name

    def test_equal_protocol_and_tag_is_clean(self) -> None:
        self.git("tag", "v9.0.0")
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.violations(payload), [])
        self.assertEqual(self.advisories(payload), [])

    def test_ahead_without_changelog_section_blocks(self) -> None:
        self.git("tag", "v8.2.0")
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 1)
        errors = self.violations(payload)
        self.assertEqual(len(errors), 1)
        self.assertIn("ahead of the newest release tag v8.2.0", errors[0])
        self.assertIn("revert the bump", errors[0])
        self.assertIn("git fetch --tags", errors[0])

    def test_ahead_with_version_heading_is_advisory(self) -> None:
        self.git("tag", "v8.2.0")
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## Unreleased\n\n## v9.0.0 — 2026-10-06\n\n- notes\n", encoding="utf-8"
        )
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.violations(payload), [])
        advisories = self.advisories(payload)
        self.assertEqual(len(advisories), 1)
        self.assertIn("release pending", advisories[0])

    def test_version_heading_of_other_major_does_not_exempt(self) -> None:
        self.git("tag", "v8.2.0")
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## Unreleased\n\n## v10.0.0 — 2026-10-06\n\n- notes\n", encoding="utf-8"
        )
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.violations(payload)), 1)

    def test_behind_newest_tag_blocks(self) -> None:
        self.set_constant(8)
        self.git("tag", "v9.0.0")
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 1)
        errors = self.violations(payload)
        self.assertEqual(len(errors), 1)
        self.assertIn("behind the newest release tag v9.0.0", errors[0])
        self.assertIn("revert the downgrade", errors[0])

    def test_non_kit_repository_is_silent(self) -> None:
        (self.root / "shared" / "scripts" / "doc-check.py").unlink()
        self.git("tag", "v3.4.5")
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("PROTOCOL RELEASE", payload["violations"])
        self.assertEqual(self.advisories(payload), [])

    def test_no_visible_tag_is_advisory(self) -> None:
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.violations(payload), [])
        advisories = self.advisories(payload)
        self.assertEqual(len(advisories), 1)
        self.assertIn("no release tag is visible", advisories[0])

    def test_highest_semver_wins_over_newest_created(self) -> None:
        self.git("tag", "v9.0.0")
        self.git("tag", "v8.9.0")  # created last, but lower
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.violations(payload), [])
        self.assertEqual(self.advisories(payload), [])

    def test_non_main_branch_silent_outside_installed_checkout(self) -> None:
        self.git("tag", "v8.2.0")
        self.git("checkout", "-b", "protocol-v10")
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.violations(payload), [])

    def test_detached_head_silent_outside_installed_checkout(self) -> None:
        self.git("tag", "v8.2.0")
        self.git("checkout", "--detach")
        result, payload = self.check(self.with_foreign_kit_home())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.violations(payload), [])

    def test_installed_checkout_enforces_every_branch(self) -> None:
        self.git("tag", "v8.2.0")
        self.git("checkout", "-b", "protocol-v10")
        result, payload = self.check(self.with_kit_home())
        self.assertEqual(result.returncode, 1)
        errors = self.violations(payload)
        self.assertEqual(len(errors), 1)
        self.assertIn("ahead of the newest release tag v8.2.0", errors[0])

    def test_installed_checkout_enforces_detached_head(self) -> None:
        self.git("tag", "v8.2.0")
        self.git("checkout", "--detach")
        result, payload = self.check(self.with_kit_home())
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(self.violations(payload)), 1)


if __name__ == "__main__":
    unittest.main()
