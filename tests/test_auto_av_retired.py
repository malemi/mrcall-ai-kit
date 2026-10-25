"""Exercise cached retired hook commands through the actual CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'shared/scripts/auto_av.py'


class RetiredAutoAvTests(unittest.TestCase):
    def test_cached_callbacks_are_quiet_without_state_or_selector(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / 'bin'
            binaries.mkdir()
            marker = root / 'selector-called'
            for name in ('codex', 'claude', 'opencode'):
                binary = binaries / name
                binary.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\nraise SystemExit(99)\n')
                binary.chmod(0o700)
            env = dict(os.environ, HOME=str(root), MRCALL_KIT_HOME=str(root / 'kit'),
                       PATH=str(binaries) + os.pathsep + os.environ['PATH'])
            for runtime in ('codex', 'claude', 'opencode'):
                for event in ('UserPromptSubmit', 'Stop', 'SessionEnd'):
                    payload = {'hook_event_name': event, 'session_id': 'cached-session',
                               'turn_id': 'cached-turn', 'prompt': 'Finish the work.',
                               'last_assistant_message': 'A result with unfinished work. ' * 30}
                    for stdin in ('', 'invalid JSON', json.dumps(payload)):
                        with self.subTest(runtime=runtime, event=event, stdin=stdin):
                            result = subprocess.run([sys.executable, str(SCRIPT), 'hook', '--runtime', runtime],
                                                    input=stdin, capture_output=True, text=True, env=env, timeout=3)
                            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '{}\n', ''))
            self.assertFalse(marker.exists())
            self.assertFalse((root / 'kit').exists())

    def test_cached_hook_does_not_wait_for_stdin(self):
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'hook', '--runtime', 'codex'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(process.stdout.read(), '{}\n')
            self.assertEqual(process.stderr.read(), '')
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()


if __name__ == '__main__':
    unittest.main()
