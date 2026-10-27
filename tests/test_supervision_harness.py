import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.supervision.store import Store

spec = importlib.util.spec_from_file_location('supervision_completion_fixture', ROOT / 'shared/scripts/tests/test_doc_evidence.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.CompletionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.state = self.fixture.base / 'supervision'
        self.store = Store(self.state)
        self.addCleanup(self.store.close)
        self.store.bind({'id': 'supervisor', 'session_id': str(uuid.uuid4())})

    def task(self, harness=True):
        f = self.fixture
        binding = {'repo': str(f.root), 'git_dir': str(f.record().parent.parent), 'task_id': f.task} if harness else None
        return self.store.create_task({'id': 'task', 'supervisor_id': 'supervisor', 'instruction': 'inspect task',
                                      'scope': 'read-only fixture', 'acceptance': ['verified output'],
                                      'limits': {'provenance': 'fixture'}, 'harness': binding})

    def inspect(self):
        before = {str(p): p.read_bytes() for p in self.fixture.root.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, str(ROOT / 'shared/supervision/cli.py'), '--state-dir', str(self.state),
                                 'harness-inspect', '--id', 'task'], capture_output=True, text=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.fixture.root.rglob('*') if p.is_file()})
        return json.loads(result.stdout)['result']

    def test_operational_does_not_create_harness_record(self):
        self.task(False)
        result = self.inspect()
        self.assertEqual(result['status'], 'not-applicable')
        self.assertFalse(self.fixture.record().exists())

    def test_missing_then_valid_then_stale_receipt(self):
        self.task()
        self.assertIn('no record', self.inspect()['diagnostics'][0])
        self.assertFalse(self.fixture.record().exists())
        self.fixture.initialize('fastpath')
        self.fixture.lead_closure(False)
        result = self.inspect()
        self.assertIn('focused', result['completion']['pending'])
        self.fixture.call('focused', {'argv': [sys.executable, 'src/tool.py']})
        result = self.inspect()
        self.assertEqual(result['completion']['pending'], ['startup'])
        self.assertEqual(result['warnings']['diagnostics'], [])
        self.assertFalse(result['certifies_completion'])
        self.assertIn('unverified', result['lead_context'])
        (self.fixture.root / 'src/tool.py').write_text("print('changed')\n")
        result = self.inspect()
        self.assertIn('focused: stale content snapshot', result['diagnostics'])

    def test_finalized_record_still_checks_current_content(self):
        self.task()
        self.fixture.close()
        self.fixture.call('finalize')
        self.assertTrue(self.inspect()['finalized_current'])
        (self.fixture.root / 'src/tool.py').write_text("print('changed after finalization')\n")
        result = self.inspect()
        self.assertFalse(result['finalized_current'])
        self.assertIn('critic: stale content snapshot', result['diagnostics'])
        self.assertEqual(result['warnings']['diagnostics'], [])

    def test_wrong_worktree_and_unsupported_profile(self):
        self.task()
        other = self.fixture.base / 'worktree'
        self.fixture.git('worktree', 'add', '-b', 'other', str(other))
        old = self.store.task('task')['harness']
        self.store.update_task({'id': 'task', 'revision': 1, 'changes': {'harness': old | {'repo': str(other)}}})
        self.assertIn('identity mismatch', self.inspect()['diagnostics'][0])
        self.store.update_task({'id': 'task', 'revision': 2, 'changes': {'harness': old}})
        profile = self.fixture.root / 'docs/.doc-profile'
        profile.write_text(profile.read_text().replace('harness_version = 9', 'harness_version = 8'))
        self.assertIn('unsupported', self.inspect()['diagnostics'][0])


if __name__ == '__main__':
    unittest.main()
