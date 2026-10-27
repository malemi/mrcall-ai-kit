import json
import importlib.metadata
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
import venv


SCRIPT = Path(__file__).resolve().parents[1] / 'shared/supervision/runtime.py'


class RuntimeTests(unittest.TestCase):
    def test_foreign_and_missing_runtime_refused_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'runtime'
            env = dict(os.environ, MRCALL_SUPERVISION_RUNTIME=str(root))
            missing = subprocess.run([sys.executable, str(SCRIPT), 'run', 'status'], env=env, capture_output=True, text=True)
            self.assertEqual(missing.returncode, 1)
            self.assertFalse(root.exists())
            root.mkdir(mode=0o700)
            (root / 'foreign').write_text('preserve')
            refused = subprocess.run([sys.executable, str(SCRIPT), 'setup'], env=env, capture_output=True, text=True)
            self.assertEqual(refused.returncode, 1)
            self.assertIn('foreign', json.loads(refused.stdout)['error'])
            self.assertEqual(list(root.iterdir()), [root / 'foreign'])

    def test_owned_environment_runs_actual_cli_and_repeated_setup_is_idle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'runtime'
            root.mkdir(mode=0o700)
            marker = root / '.ai-kit-owned'
            marker.write_text('supervision-runtime-v1\n')
            marker.chmod(0o600)
            # Fixture reuses the test dependency; actual isolated pip setup has
            # separate native acceptance evidence and is never a CI network call.
            venv.EnvBuilder(with_pip=False).create(root)
            site = Path(subprocess.check_output([str(root / 'bin/python'), '-I', '-c',
                                                'import sysconfig; print(sysconfig.get_paths()["purelib"])'], text=True).strip())
            distribution = importlib.metadata.distribution('websockets')
            shutil.copytree(distribution.locate_file('websockets'), site / 'websockets')
            metadata_path = next(p.parent for p in distribution.files if p.name == 'METADATA')
            shutil.copytree(distribution.locate_file(metadata_path), site / metadata_path.name)
            env = dict(os.environ, MRCALL_SUPERVISION_RUNTIME=str(root), XDG_STATE_HOME=str(Path(temporary) / 'state'))
            python_mtime = (root / 'pyvenv.cfg').stat().st_mtime_ns
            setup = subprocess.run([sys.executable, str(SCRIPT), 'setup'], env=env, capture_output=True, text=True)
            self.assertEqual(setup.returncode, 0, setup.stdout + setup.stderr)
            self.assertFalse(json.loads(setup.stdout)['cron_enabled'])
            self.assertEqual((root / 'pyvenv.cfg').stat().st_mtime_ns, python_mtime)
            status = subprocess.run([sys.executable, str(SCRIPT), 'run', 'status'], env=env, capture_output=True, text=True)
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            self.assertEqual(json.loads(status.stdout)['result']['tasks'], [])


if __name__ == '__main__':
    unittest.main()
