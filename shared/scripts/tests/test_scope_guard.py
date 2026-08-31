"""Behavioral tests for the shared scope-guard engine."""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ENGINE = Path(__file__).parents[1] / "scope_guard.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("scope_guard", ENGINE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sg = load_engine()


def scoped(scope: str = "Scope: Only current repository state belongs here.", body: str = "Body\n") -> str:
    return f"{sg.SCOPE_START}\n{scope}\n{sg.SCOPE_END}\n\n{body}"


class ScopeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.handoff = self.root / "handoff"
        self.old_state = os.environ.get("SCOPE_GUARD_STATE")
        self.old_handoff = os.environ.get("SCOPE_GUARD_HANDOFF")
        os.environ["SCOPE_GUARD_STATE"] = str(self.state)
        os.environ["SCOPE_GUARD_HANDOFF"] = str(self.handoff)
        self.doc = self.root / "active-context.md"
        self.doc.write_text(scoped(), encoding="utf-8")

    def tearDown(self) -> None:
        if self.old_state is None:
            os.environ.pop("SCOPE_GUARD_STATE", None)
        else:
            os.environ["SCOPE_GUARD_STATE"] = self.old_state
        if self.old_handoff is None:
            os.environ.pop("SCOPE_GUARD_HANDOFF", None)
        else:
            os.environ["SCOPE_GUARD_HANDOFF"] = self.old_handoff
        self.temp.cleanup()

    def mutation(self, content: str | None = None, action: str = "write"):
        return sg.Mutation(self.doc, action, content if content is not None else scoped(body="Changed\n"))

    def test_scope_parser_requires_one_complete_nonempty_block(self) -> None:
        self.assertEqual(sg.parse_scope("plain\n").status, "absent")
        parsed = sg.parse_scope(scoped())
        self.assertEqual(parsed.status, "valid")
        self.assertTrue(parsed.text.startswith("Scope:"))
        for text in (
            f"{sg.SCOPE_START}\n{sg.SCOPE_END}\n",
            f"{sg.SCOPE_START}\nScope: x\n",
            f"{sg.SCOPE_END}\nScope: x\n{sg.SCOPE_START}\n",
            scoped() + scoped("Scope: duplicate"),
            f"{sg.SCOPE_START}\nnot a Scope line\n{sg.SCOPE_END}\n",
        ):
            self.assertEqual(sg.parse_scope(text).status, "malformed", text)
        example = f"```markdown\n{sg.SCOPE_START}\nScope: example\n{sg.SCOPE_END}\n```\n"
        self.assertEqual(sg.parse_scope(example).status, "absent")

    def test_unmarked_file_is_silent(self) -> None:
        self.doc.write_text("ordinary\n", encoding="utf-8")
        decision = sg.decide("codex", "s1", self.mutation("changed\n"))
        self.assertEqual(decision.action, "ignore")

    def test_marker_example_in_non_markdown_source_is_silent(self) -> None:
        source = self.root / "checker.py"
        source.write_text(
            '"""\n<!-- doc-scope:start -->\nScope: example only\n'
            '<!-- doc-scope:end -->\n"""\n',
            encoding="utf-8",
        )
        decision = sg.decide(
            "codex",
            "source-example",
            sg.Mutation(source, "update", source.read_text(encoding="utf-8") + "# edit\n"),
        )
        self.assertEqual(decision.action, "ignore")

    def test_claude_and_agents_each_use_their_own_inline_scope(self) -> None:
        repo = self.root / "repo"
        repo.mkdir()
        documents = {
            "CLAUDE.md": "Scope: Managed documentation-harness entry point only.",
            "AGENTS.md": "Scope: Thin repository index and project guidance only.",
        }
        for number, (name, scope) in enumerate(documents.items(), 1):
            with self.subTest(name=name):
                document = repo / name
                document.write_text(scoped(scope, "Current\n"), encoding="utf-8")
                mutation = sg.Mutation(document, "update", scoped(scope, "Changed\n"))
                session = f"inline-{number}"
                first = sg.decide("codex", session, mutation, turn_id="t1")
                self.assertEqual(first.action, "deny")
                self.assertIn(scope.removeprefix("Scope: "), first.message)
                second = sg.decide("codex", session, mutation, turn_id="t2")
                self.assertEqual(second.action, "allow")

    def test_legacy_external_index_marker_does_not_mark_a_file(self) -> None:
        legacy = (
            "<!-- doc-index-scope:start -->\n"
            "Index: AGENTS.md\n"
            "Scope: Legacy external index scope.\n"
            "<!-- doc-index-scope:end -->\n"
        )
        self.doc.write_text(legacy, encoding="utf-8")
        self.assertEqual(sg.parse_scope(legacy).status, "absent")
        decision = sg.decide("codex", "legacy-external", self.mutation("changed\n"))
        self.assertEqual(decision.action, "ignore")

    def test_degraded_runtime_denies_once_then_allows_exact_retry(self) -> None:
        proposed = scoped(body="Changed\n")
        first = sg.decide("codex", "s1", self.mutation(proposed), turn_id="t1")
        self.assertEqual(first.action, "deny")
        self.assertIn("Do not ask the operator", first.message)
        second = sg.decide("codex", "s1", self.mutation(proposed), turn_id="t2")
        self.assertEqual(second.action, "allow")
        self.assertEqual(second.capability, "degraded")

    def test_codex_same_turn_retry_opens_after_visible_reason_window(self) -> None:
        proposed = scoped(body="Changed\n")
        with mock.patch.object(sg.time, "time", return_value=100.0):
            first = sg.decide("codex", "same-turn", self.mutation(proposed), turn_id="turn")
        with mock.patch.object(sg.time, "time", return_value=100.1):
            too_soon = sg.decide("codex", "same-turn", self.mutation(proposed), turn_id="turn")
        with mock.patch.object(sg.time, "time", return_value=100.3):
            retry = sg.decide("codex", "same-turn", self.mutation(proposed), turn_id="turn")
        self.assertEqual(first.action, "deny")
        self.assertEqual(too_soon.action, "deny")
        self.assertEqual(retry.action, "allow")

    def test_changed_retry_gets_a_new_challenge(self) -> None:
        first = sg.decide("codex", "s1", self.mutation(scoped(body="One\n")), turn_id="t1")
        second = sg.decide("codex", "s1", self.mutation(scoped(body="Two\n")), turn_id="t2")
        self.assertEqual(second.action, "deny")
        self.assertNotEqual(first.nonce, second.nonce)

    def test_full_runtime_requires_visible_nonce_attestation(self) -> None:
        proposed = scoped(body="Changed\n")
        first = sg.decide("claude", "s1", self.mutation(proposed), full_attestation=True)
        self.assertEqual(first.action, "deny")
        retry = sg.decide("claude", "s1", self.mutation(proposed), full_attestation=True)
        self.assertEqual(retry.action, "deny")
        self.assertEqual(sg.attest("claude", "s1", "unrelated text"), 0)
        message = f"Scope reason {first.nonce}: this updates current repository state."
        self.assertEqual(sg.attest("claude", "s1", message), 1)
        allowed = sg.decide("claude", "s1", self.mutation(proposed), full_attestation=True)
        self.assertEqual(allowed.action, "allow")
        self.assertEqual(allowed.capability, "full")

    def test_open_path_still_rejects_marker_removal_and_malformation(self) -> None:
        proposed = scoped(body="Changed\n")
        sg.decide("codex", "s1", self.mutation(proposed), turn_id="t1")
        self.assertEqual(sg.decide("codex", "s1", self.mutation(proposed), turn_id="t2").action, "allow")
        self.doc.write_text(proposed, encoding="utf-8")
        removal = sg.decide("codex", "s1", self.mutation("no marker\n"))
        self.assertEqual(removal.action, "deny")
        malformed = sg.decide(
            "codex",
            "s1",
            self.mutation(f"{sg.SCOPE_START}\nScope: broken\n"),
        )
        self.assertEqual(malformed.action, "deny")
        self.assertIn("malformed", malformed.message)

    def test_unmark_requires_explicit_second_agent_action(self) -> None:
        removal = sg.decide("opencode", "s1", self.mutation("plain\n"))
        self.assertEqual(removal.action, "deny")
        self.assertFalse(sg.authorize_unmark("opencode", "s1", "wrong"))
        self.assertTrue(sg.authorize_unmark_any(removal.nonce))
        allowed = sg.decide("opencode", "s1", self.mutation("plain\n"))
        self.assertEqual(allowed.action, "allow")

    def test_sandbox_handoff_authorizes_one_exact_unmark_retry(self) -> None:
        removal = sg.decide("codex", "sandbox", self.mutation("plain\n"))
        sg.queue_unmark(removal.nonce)
        allowed = sg.decide("codex", "sandbox", self.mutation("plain\n"))
        replay = sg.decide("codex", "sandbox", self.mutation("plain\n"))
        self.assertEqual(allowed.action, "allow")
        self.assertEqual(replay.action, "deny")
        self.assertFalse(any(self.handoff.glob("*.unmark")))

    def test_cli_queues_unmark_when_state_is_outside_sandbox(self) -> None:
        nonce = "abcdefghijklmnop"
        with mock.patch.object(sg, "authorize_unmark_any", side_effect=PermissionError):
            self.assertEqual(sg.cli(["scope_guard.py", "unmark", nonce]), 0)
        self.assertEqual((self.handoff / f"{sg.digest(nonce)}.unmark").read_text(), nonce + "\n")

    def test_scope_change_is_bound_to_exact_postimage(self) -> None:
        changed = scoped("Scope: Only durable architecture belongs here.", "New\n")
        first = sg.decide("codex", "s1", self.mutation(changed), turn_id="t1")
        self.assertEqual(first.action, "deny")
        wrong = scoped("Scope: Only durable architecture belongs here.", "Different\n")
        self.assertEqual(sg.decide("codex", "s1", self.mutation(wrong), turn_id="t2").action, "deny")
        # Retry the newly challenged exact postimage, not the stale first one.
        self.assertEqual(sg.decide("codex", "s1", self.mutation(wrong), turn_id="t3").action, "allow")

    def test_delete_and_move_of_scoped_files_are_denied(self) -> None:
        for action in ("delete", "move"):
            decision = sg.decide("codex", f"s-{action}", self.mutation(None, action))
            self.assertEqual(decision.action, "deny")

    def test_edit_reconstruction_rejects_missing_and_ambiguous_preimage(self) -> None:
        self.assertEqual(sg.apply_edit("a b", "a", "x"), "x b")
        with self.assertRaises(sg.ScopeGuardError):
            sg.apply_edit("a a", "a", "x")
        self.assertEqual(sg.apply_edit("a a", "a", "x", True), "x x")
        with self.assertRaises(sg.ScopeGuardError):
            sg.apply_edit("a", "z", "x")

    def test_apply_patch_reconstructs_scoped_postimage_and_all_targets(self) -> None:
        other = self.root / "other.md"
        other.write_text("old\n", encoding="utf-8")
        command = (
            "*** Begin Patch\n"
            f"*** Update File: {self.doc}\n"
            "@@\n"
            " Body\n"
            "-old\n"
            "+new\n"
            f"*** Update File: {other}\n"
            "@@\n"
            "-old\n"
            "+new\n"
            "*** End Patch"
        )
        self.doc.write_text(scoped(body="Body\nold\n"), encoding="utf-8")
        mutations = sg.parse_apply_patch(command, self.root)
        self.assertEqual([m.path for m in mutations], [self.doc.resolve(), other.resolve()])
        self.assertIn("Body\nnew", mutations[0].postimage or "")
        self.assertEqual(mutations[1].postimage, "new\n")

    def test_parallel_first_calls_never_allow(self) -> None:
        proposed = scoped(body="Parallel\n")
        actions: list[str] = []
        barrier = threading.Barrier(3)

        def run() -> None:
            barrier.wait()
            actions.append(
                sg.decide("codex", "parallel", self.mutation(proposed), turn_id="same-turn").action
            )

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        self.assertEqual(actions.count("deny"), 2)
        self.assertEqual(actions.count("allow"), 0)

    def test_state_root_symlink_is_rejected(self) -> None:
        target = self.root / "outside"
        target.mkdir()
        self.state.symlink_to(target, target_is_directory=True)
        with self.assertRaises(sg.ScopeGuardError):
            sg.decide("codex", "s1", self.mutation(), turn_id="t1")
        self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
