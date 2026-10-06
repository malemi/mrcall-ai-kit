"""Completion CLI mechanics with fixture attestations, not model-judgment proof."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
CHECKER = SCRIPTS / "doc-check.py"
SHARED = SCRIPTS.parent
SCOPE = "<!-- doc-scope:start -->\nScope: Fixture routing and current state.\n<!-- doc-scope:end -->\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        (self.root / "docs/execution-plans").mkdir(parents=True)
        (self.root / "docs/briefs").mkdir()
        (self.root / "src").mkdir()
        (self.root / "src/tool.py").write_text("print('real fixture CLI')\n")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "initial source")
        initial = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "AGENTS.md").write_bytes((SHARED / "templates/AGENTS.block.md").read_bytes() + SCOPE.encode())
        (self.root / "docs/.doc-profile").write_text("harness_version = 9\nmode = leaf\nindex_file = AGENTS.md\n")
        (self.root / "docs/README.md").write_text(SCOPE + "[Contract](contract.md)\n")
        (self.root / "docs/active-context.md").write_text(f"---\ndoc_baseline_commit: {initial}\ndoc_baseline_date: 2026-01-01\n---\n" + SCOPE + "## State now\nWorking fixture.\n## Unresolved\nNone.\n## Next\nNone.\n")
        (self.root / "docs/contract.md").write_text("# Contract\nThe tool prints real fixture CLI.\n")
        (self.root / "docs/briefs/task.md").write_text("# Brief\nPreserve the fixture CLI.\n")
        (self.root / "docs/execution-plans/task.md").write_text("---\nstatus: active\n---\n# Plan\nM1: Verify fixture.\n")
        self.git("add", ".")
        self.git("commit", "-m", "fixture documentation")
        self.task = "fixture-task"
        self.context = "lead-context-1"
        self.sequence = 0
        self.workflows = {}
        for key, source in {"doc_start": SHARED / "commands/doc-start.md", "doc_end": SHARED / "commands/doc-end.md", "doc_critic": SHARED / "skills/doc-critic/SKILL.md"}.items():
            path = self.base / (key + ".md")
            shutil.copyfile(source, path)
            self.workflows[key] = str(path)
        self.config = {"kind": "documentation", "scope": ["src", "docs", "AGENTS.md"], "base": self.git("rev-parse", "HEAD").stdout.strip(), "workflows": self.workflows}
        self.documents = ["AGENTS.md", "docs/README.md", "docs/active-context.md", "docs/.doc-profile", "docs/contract.md"]

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, text=True, capture_output=True, check=True)

    def input_file(self, data):
        self.sequence += 1
        path = self.base / f"input-{self.sequence}.json"
        path.write_text(json.dumps(data))
        return path

    def command(self, action, data=None, *, context=True, phase=None):
        argv = [sys.executable, str(CHECKER), "--repo", str(self.root), "--completion", action, "--task", self.task, "--json"]
        if data is not None:
            argv += ["--input", str(self.input_file(data))]
        if context:
            argv += ["--context-id", self.context]
        if phase:
            argv += ["--phase", phase]
        return argv

    def call(self, action, data=None, *, expected=0, context=True, phase=None, env=None, timeout=None):
        argv = self.command(action, data, context=context, phase=phase)
        result = subprocess.run(argv, text=True, capture_output=True, env=env, timeout=timeout)
        log = os.environ.get("MRCALL_COMPLETION_TEST_LOG")
        if log:
            with open(log, "a") as handle:
                handle.write(json.dumps({"test": self.id(), "argv": argv, "exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}) + "\n")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def initialize(self, kind="documentation", transition=False):
        self.config["kind"] = kind
        if kind == "development":
            self.config["reviews"] = {"brief": "docs/briefs/task.md", "plan": "docs/execution-plans/task.md", "milestones": {"M1": "docs/execution-plans/task.md"}}
        if transition:
            self.config["plan_transition"] = {"path": "docs/execution-plans/task.md", "from": "active", "to": "completed"}
        return self.call("init", self.config)

    def orient(self):
        return self.call("attest", {"obligation": "startup", "producer": "lead", "documents": self.documents, "context_id": self.context, "available": True})

    def lead_closure(self, impact=True):
        self.orient()
        self.call("attest", {"obligation": "impact", "producer": "lead", "doc_impact": impact, "affected_docs": ["docs/contract.md"] if impact else [], "reason": "Fixture impact decision; no real model judgment claimed.", "work_trace": "fixture brief and plan"})
        if self.config["kind"] != "fastpath" or impact:
            self.call("attest", {"obligation": "reconciliation", "producer": "lead", "reason": "Fixture content reconciled."})

    def record(self):
        directory = Path(self.git("rev-parse", "--absolute-git-dir").stdout.strip())
        return directory / "doc-completion" / (self.task + ".json")

    def envelope(self, gate="critic", outcome="APPROVED", shape="pass", deferrals=None):
        current = self.call("snapshot")
        self.sequence += 1
        report = self.base / f"fixture-report-{self.sequence}.txt"
        report.write_text(f"Fixture-only {gate} result {outcome}; simulated judgment for gate mechanics.\n")
        value = {"schema_version": 1, **current["binding"], "snapshot": current["snapshot"], "producer": "fixture-" + gate,
                 "gate_kind": gate, "outcome": outcome, "reviewed_docs": ["docs/contract.md", "docs/active-context.md"],
                 "shape": shape, "deferrals": deferrals or [], "report": str(report)}
        if gate == "critic":
            value["skill"] = "doc-critic"
        if gate == "final-review":
            value["evidence_digest"] = current["evidence_digest"]
            record = json.loads(self.record().read_text())
            value["approved_versions"] = [
                {"gate_key": key, "source": previous["source"], "approved_sha256": previous["artifact"]["sha256"],
                 "current_sha256": sha(self.root / previous["source"]), "scope_preserved": True,
                 "substantive_changes": False, "comparison_reason": "Fixture comparison of approved scope and current progress."}
                for key, previous in record["results"].items() if "artifact" in previous]
        return value

    def prior_reviews(self):
        current = self.call("snapshot")
        for gate, gate_id, source in (("brief-review", "brief", "docs/briefs/task.md"), ("plan-review", "plan", "docs/execution-plans/task.md"), ("milestone-review", "M1", "docs/execution-plans/task.md")):
            self.sequence += 1
            approved = self.base / f"approved-{self.sequence}.md"
            shutil.copyfile(self.root / source, approved)
            report = self.base / f"prior-report-{self.sequence}.txt"
            report.write_text("Fixture approved-version review; no real semantic evidence.\n")
            self.call("result", {"schema_version": 1, **current["binding"], "scope_digest": current["scope_digest"], "gate_kind": gate,
                                 "gate_id": gate_id, "source": source, "artifact": {"path": str(approved), "sha256": sha(approved)},
                                 "producer": "fixture-reviewer", "outcome": "APPROVED", "deferrals": [], "report": str(report)})

    def close(self, initialize=True, kind="documentation", impact=True, final=True, transition=False):
        if initialize:
            self.initialize(kind, transition)
            if kind == "development":
                self.prior_reviews()
        self.lead_closure(impact)
        if kind in {"development", "fastpath"}:
            self.call("focused", {"argv": [sys.executable, "src/tool.py"]})
        if kind != "fastpath" or impact:
            self.call("mechanical")
            self.call("result", self.envelope())
        if kind == "development" and final:
            self.call("check", phase="pre-review")
            self.call("result", self.envelope("final-review"))
        return self.call("check") if kind != "development" or final else self.call("check", expected=1)

    def test_documentation_completion_and_metadata_only_finalization(self):
        self.close()
        record = json.loads(self.record().read_text())
        self.assertEqual(record["results"]["mechanical"]["exit_status"], 0)
        self.assertNotIn("stdout", record["results"]["mechanical"])
        self.assertNotIn("Fixture-only", self.record().read_text())
        result = self.call("finalize")
        self.assertEqual(result["state"], "finalized")
        self.assertEqual(result["baseline"], self.git("rev-parse", "HEAD").stdout.strip())
        self.call("check")
        self.assertEqual(self.call("finalize")["state"], "already-finalized")
        with (self.root / "docs/active-context.md").open("a") as handle:
            handle.write("Changed body after review.\n")
        self.assertIn("stale", " ".join(self.call("check", expected=1)["reasons"]))

    def test_missing_critic_refuses_then_real_registration_retry_passes(self):
        self.initialize()
        self.lead_closure()
        self.call("mechanical")
        failed = self.call("check", expected=1)
        self.assertIn("critic", failed["pending"])
        self.call("result", self.envelope())
        self.call("check")

    def test_development_requires_prior_gates_final_review_and_comparison(self):
        self.initialize("development", True)
        self.lead_closure()
        self.call("focused", {"argv": [sys.executable, "src/tool.py"]})
        self.call("mechanical")
        self.call("result", self.envelope())
        missing = self.call("check", phase="pre-review", expected=1)
        self.assertIn("brief-review", missing["pending"])
        self.assertIn("plan-review", missing["pending"])
        self.assertIn("milestone-review:M1", missing["pending"])
        self.prior_reviews()
        with (self.root / "docs/execution-plans/task.md").open("a") as handle:
            handle.write("\nProgress: M1 fixture command passed.\n")
        self.close(initialize=False, kind="development", final=False)
        prereview = self.call("check", phase="pre-review")
        self.assertNotIn("final-review", prereview["required"])
        wrong = self.envelope("final-review")
        wrong["approved_versions"][0]["scope_preserved"] = False
        self.call("result", wrong, expected=1)
        self.call("result", self.envelope("final-review"))
        self.call("check")
        self.call("finalize")
        self.assertIn("status: completed", (self.root / "docs/execution-plans/task.md").read_text())
        self.call("check")

    def test_replaced_supporting_result_requires_fresh_final_review(self):
        self.close(kind="development")
        previous = self.envelope("final-review")
        self.call("result", self.envelope())
        result = self.call("check", expected=1)
        self.assertIn("supporting evidence changed", " ".join(result["reasons"]))
        self.call("result", previous, expected=1)
        self.call("result", self.envelope("final-review"))
        self.call("check")
        self.context = "reloaded-context"
        self.orient()
        self.call("check")

    def test_unborn_repository_refuses_initialization_without_creating_record(self):
        self.git("checkout", "--orphan", "unborn")
        result = self.call("init", self.config, expected=1)
        self.assertIn("existing committed HEAD", " ".join(result["reasons"]))
        self.assertFalse(self.record().parent.exists())

    def test_altered_approved_version_refuses_completion(self):
        self.close(kind="development")
        record = json.loads(self.record().read_text())
        approved = Path(record["results"]["plan-review"]["artifact"]["path"])
        approved.write_bytes(approved.read_bytes() + b"Changed approved version.\n")
        self.assertIn("approved artifact/version changed", " ".join(self.call("check", expected=1)["reasons"]))

    def test_stale_reviews_changed_untracked_paths_and_fresh_repair(self):
        self.config["scope"] = ["src"]
        self.close()
        with (self.root / "src/tool.py").open("a") as handle:
            handle.write("print('changed')\n")
        result = self.call("check", expected=1)
        self.assertIn("startup", result["completed"])
        self.assertIn("critic", result["pending"])
        self.close(initialize=False)
        (self.root / "outside-recorded-scope.txt").write_text("new untracked content\n")
        self.assertIn("critic", self.call("check", expected=1)["pending"])
        self.close(initialize=False)
        self.git("add", "outside-recorded-scope.txt")
        self.call("check", expected=1)

    def test_snapshot_keeps_both_paths_of_staged_rename(self):
        self.close()
        self.git("mv", "src/tool.py", "src/renamed.py")
        current = self.call("snapshot")
        self.assertIn("src/tool.py", current["changed_paths"])
        self.assertIn("src/renamed.py", current["changed_paths"])
        self.call("check", expected=1)

    def test_successful_command_that_changes_content_is_not_passing_evidence(self):
        self.initialize("fastpath")
        self.lead_closure(False)
        result = self.call("focused", {"argv": [sys.executable, "-c", "from pathlib import Path; Path('src/tool.py').write_text('print(42)\\n')"]}, expected=1)
        self.assertEqual(result["command"]["exit_status"], 0)
        self.assertFalse(result["command"]["content_unchanged"])
        self.call("check", expected=1)

    def test_unchanged_affected_doc_changes_invalidate_review(self):
        self.close()
        (self.root / "docs/contract.md").write_text("# Contract\nUnreviewed behavior.\n")
        result = self.call("check", expected=1)
        self.assertIn("critic", result["pending"])
        self.assertIn("startup", result["pending"])

    def test_symlink_target_content_mode_and_resolved_identity_require_fresh_review(self):
        doc = self.root / "docs/contract.md"
        target = self.base / "external-contract.md"
        target.write_bytes(doc.read_bytes())
        intermediate = self.base / "contract-link"
        intermediate.symlink_to(target)
        doc.unlink()
        doc.symlink_to(intermediate)
        self.close()
        before = self.call("snapshot")["snapshot"]
        target.write_text("# Contract\nChanged external documentation.\n")
        self.assertNotEqual(before, self.call("snapshot")["snapshot"])
        failed = self.call("check", expected=1)
        self.assertIn("critic", failed["pending"])
        self.assertIn("startup", failed["pending"])
        self.close(initialize=False)
        target.chmod(0o600)
        self.call("check", expected=1)
        self.close(initialize=False)
        replacement = self.base / "replacement-contract.md"
        replacement.write_bytes(target.read_bytes())
        replacement.chmod(0o600)
        intermediate.unlink()
        intermediate.symlink_to(replacement)
        self.call("check", expected=1)
        self.close(initialize=False)
        self.call("finalize")
        self.call("check")

    def test_missing_symlink_target_refuses_without_evidence_mutation(self):
        self.close()
        record = self.record().read_bytes()
        doc = self.root / "docs/contract.md"
        doc.unlink()
        doc.symlink_to(self.base / "missing-target.md")
        result = self.call("check", expected=1)
        self.assertIn("cannot bind symlink target", " ".join(result["reasons"]))
        self.assertEqual(record, self.record().read_bytes())

    def test_altered_report_and_review_envelope_refuse(self):
        self.close()
        record = json.loads(self.record().read_text())
        for name in ("report", "envelope"):
            path = Path(record["results"]["critic"][name]["path"])
            original = path.read_bytes()
            path.write_bytes(original + b"Altered\n")
            self.assertIn("altered", " ".join(self.call("check", expected=1)["reasons"]))
            path.write_bytes(original)
        self.call("check")

    def test_stale_unverifiable_and_invalid_shape_refuse_then_repair(self):
        self.close()
        for outcome, shape in (("STALE", "pass"), ("UNVERIFIABLE", "pass"), ("APPROVED", "fail")):
            self.call("result", self.envelope(outcome=outcome, shape=shape))
            self.assertIn("critic", self.call("check", expected=1)["pending"])
        self.call("result", self.envelope())
        self.call("check")
        deferrals = [{"claim": "Untested host mode", "reason": "No host trial in fixture", "nonblocking": True}]
        self.call("result", self.envelope(deferrals=deferrals))
        result = self.call("check")
        self.assertEqual(result["verification"], "qualified")
        self.assertEqual(result["deferrals"], deferrals)

    def test_missing_shape_and_affected_document_coverage_are_blocking(self):
        self.close()
        value = self.envelope()
        value.pop("shape")
        value["reviewed_docs"] = ["docs/contract.md"]
        self.call("result", value)
        self.assertIn("critic", self.call("check", expected=1)["pending"])

    def test_index_stat_cache_is_ignored_but_staged_content_is_bound(self):
        self.close()
        record_before = self.call("snapshot")["snapshot"]
        os.utime(self.root / ".git/index", None)
        self.git("update-index", "--refresh")
        self.assertEqual(record_before, self.call("snapshot")["snapshot"])
        self.call("check")
        tool = self.root / "src/tool.py"
        original = tool.read_bytes()
        tool.write_bytes(original + b"print('staged')\n")
        self.git("add", "src/tool.py")
        tool.write_bytes(original)
        self.call("check", expected=1)

    def test_workflow_change_and_scope_record_tampering_refuse(self):
        self.close()
        path = Path(self.workflows["doc_end"])
        original = path.read_bytes()
        path.write_bytes(original + b"Changed workflow\n")
        self.assertIn("workflow versions changed", " ".join(self.call("check", expected=1)["reasons"]))
        path.write_bytes(original)
        record = json.loads(self.record().read_text())
        record["config"]["scope"] = ["elsewhere"]
        self.record().write_text(json.dumps(record))
        self.assertIn("scope/configuration binding changed", self.call("check", expected=1)["reasons"][0])

    def test_restart_recovery_requires_available_lead_context(self):
        self.close()
        before = self.record().read_bytes()
        result = self.call("recover", context=False, expected=1)
        self.assertIn("startup", result["pending"])
        self.assertEqual(before, self.record().read_bytes())
        self.context = "fresh-context-after-compaction"
        self.call("check", expected=1)
        self.orient()
        self.call("recover")
        self.call("check")

    def test_record_and_envelope_cannot_cross_task_or_worktree(self):
        self.close()
        original_task = self.task
        self.task = "other-task"
        foreign_record = self.record()
        shutil.copyfile(foreign_record.with_name(original_task + ".json"), foreign_record)
        self.assertIn("worktree mismatch", self.call("check", expected=1)["reasons"][0])
        self.task = original_task
        old_root = self.root
        old_record = self.record()
        child = self.base / "worktree"
        self.git("worktree", "add", "-b", "child", str(child))
        self.root = child
        new_record = self.record()
        new_record.parent.mkdir()
        shutil.copyfile(old_record, new_record)
        self.assertIn("worktree mismatch", self.call("check", expected=1)["reasons"][0])
        new_record.unlink()
        self.close()
        self.call("check")
        self.root = old_root

    def test_readonly_kinds_cannot_create_records_and_fastpath_none_is_proportional(self):
        for kind in ("explanation", "brief", "review", "startup"):
            self.config["kind"] = kind
            self.call("init", self.config, expected=1)
            self.assertFalse(self.record().parent.exists())
        self.close(kind="fastpath", impact=False)
        record = json.loads(self.record().read_text())
        self.assertNotIn("critic", record["results"])
        self.assertNotIn("reconciliation", record["attestations"])
        self.call("finalize", expected=1)

    def test_mechanical_and_focused_results_are_actual_failures(self):
        self.initialize("fastpath")
        self.lead_closure(False)
        result = self.call("focused", {"argv": [sys.executable, "-c", "raise SystemExit(7)"]}, expected=1)
        self.assertEqual(result["command"]["exit_status"], 7)
        self.call("check", expected=1)
        self.call("focused", {"argv": [sys.executable, "src/tool.py"]})
        self.call("check")
        (self.root / "docs/contract.md").write_text("[broken](missing.md)\n")
        result = self.call("mechanical", expected=1)
        self.assertEqual(result["command"]["exit_status"], 1)
        self.assertIn("DEAD LINKS", result["command"]["stdout"])

    def test_finalization_serializes_every_task_mutation_and_allows_other_tasks(self):
        self.close()
        record_before = self.record().read_bytes()
        barrier = self.base / "record-barrier"
        barrier.mkdir()
        os.mkfifo(barrier / "continue")
        process = subprocess.Popen(self.command("finalize"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=dict(os.environ, MRCALL_DOC_COMPLETION_TEST_BARRIER=str(barrier)))
        try:
            deadline = time.monotonic() + 10
            while not (barrier / "published").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((barrier / "published").exists())
            revised = self.envelope(outcome="REVISE")
            for action, data in (("init", self.config), ("attest", {"obligation": "reconciliation", "producer": "lead", "reason": "Concurrent reconciliation"}),
                                 ("mechanical", None), ("focused", {"argv": [sys.executable, "-c", "raise SystemExit(9)"]}),
                                 ("result", revised), ("finalize", None)):
                result = self.call(action, data, expected=1, timeout=5)
                self.assertIn("task mutation already in progress", " ".join(result["reasons"]))
                self.assertEqual(self.record().read_bytes(), record_before)
            original_task = self.task
            self.task = "independent-task"
            try:
                self.call("init", self.config, timeout=5)
                self.assertTrue(self.record().is_file())
            finally:
                self.task = original_task
            with (barrier / "continue").open("wb") as handle:
                handle.write(b"1")
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.call("result", revised, timeout=5)
            current = json.loads(self.record().read_bytes())
            self.assertEqual(current["results"]["critic"]["outcome"], "REVISE")
            self.assertNotIn("finalized", current)
            self.call("check", expected=1)
            self.close(initialize=False)
            self.call("finalize")
            self.call("check")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_finalization_artifact_change_rolls_back_metadata_before_record_publication(self):
        baseline = self.root / "docs/active-context.md"
        plan = self.root / "docs/execution-plans/task.md"
        baseline.chmod(0o640)
        plan.chmod(0o600)
        self.close(kind="development", transition=True)
        old_baseline, old_plan = baseline.read_bytes(), plan.read_bytes()
        old_record = self.record().read_bytes()
        report = Path(json.loads(old_record)["results"]["critic"]["report"]["path"])
        barrier = self.base / "artifact-barrier"
        barrier.mkdir()
        os.mkfifo(barrier / "continue")
        process = subprocess.Popen(self.command("finalize"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=dict(os.environ, MRCALL_DOC_COMPLETION_TEST_BARRIER=str(barrier)))
        try:
            deadline = time.monotonic() + 10
            while not (barrier / "published").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((barrier / "published").exists())
            report.write_text("Concurrent changed critic report must survive.\n")
            with (barrier / "continue").open("wb") as handle:
                handle.write(b"1")
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, stdout + stderr)
            self.assertIn("finalization evidence changed", stdout)
            self.assertIn("altered report artifact", stdout)
            self.assertEqual(baseline.read_bytes(), old_baseline)
            self.assertEqual(plan.read_bytes(), old_plan)
            self.assertEqual(stat.S_IMODE(baseline.stat().st_mode), 0o640)
            self.assertEqual(stat.S_IMODE(plan.stat().st_mode), 0o600)
            self.assertEqual(self.record().read_bytes(), old_record)
            self.assertNotIn("finalized", json.loads(self.record().read_bytes()))
            self.assertEqual(report.read_text(), "Concurrent changed critic report must survive.\n")
            self.call("check", expected=1)
            self.close(initialize=False, kind="development")
            self.call("finalize")
            self.call("check")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_finalization_metadata_ownership_conflict_preserves_concurrent_value(self):
        self.close()
        barrier = self.base / "metadata-barrier"
        barrier.mkdir()
        os.mkfifo(barrier / "continue")
        process = subprocess.Popen(self.command("finalize"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=dict(os.environ, MRCALL_DOC_COMPLETION_TEST_BARRIER=str(barrier)))
        try:
            deadline = time.monotonic() + 10
            while not (barrier / "published").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((barrier / "published").exists())
            path = self.root / "docs/active-context.md"
            current = path.read_text()
            changed = "\n".join("doc_baseline_date: 2099-12-31" if line.startswith("doc_baseline_date:") else line for line in current.split("\n"))
            path.write_text(changed)
            with (barrier / "continue").open("wb") as handle:
                handle.write(b"1")
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, stdout + stderr)
            self.assertIn("metadata ownership conflict", stdout)
            self.assertEqual(path.read_text(), changed)
            self.call("check", expected=1)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_finalization_detects_concurrent_body_edit_and_preserves_it(self):
        self.close()
        before = (self.root / "docs/active-context.md").read_bytes()
        barrier = self.base / "barrier"
        barrier.mkdir()
        os.mkfifo(barrier / "continue")
        process = subprocess.Popen(self.command("finalize"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=dict(os.environ, MRCALL_DOC_COMPLETION_TEST_BARRIER=str(barrier)))
        try:
            deadline = time.monotonic() + 10
            while not (barrier / "published").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((barrier / "published").exists())
            path = self.root / "docs/active-context.md"
            with path.open("ab") as handle:
                handle.write(b"Concurrent body change must survive.\n")
            with (barrier / "continue").open("wb") as handle:
                handle.write(b"1")
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, stdout + stderr)
            self.assertIn("non-metadata content changed", stdout)
            self.assertEqual(path.read_bytes(), before + b"Concurrent body change must survive.\n")
            self.call("check", expected=1)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
