import importlib.util
from pathlib import Path

try:
    from .store import StoreError
except ImportError:
    from store import StoreError


def modules():
    directory = Path(__file__).resolve().parent
    candidates = [directory.parent / 'scripts/verification_warnings.py',
                  directory.parent / 'verification-warnings/verification_warnings.py']
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        raise StoreError('installed verification-warnings and harness helpers are unavailable')
    spec = importlib.util.spec_from_file_location('supervision_verification_warnings', source)
    warnings = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(warnings)
    checker, evidence = warnings.modules()
    return checker, evidence, warnings


def inspect(store, task_id):
    task = store.task(task_id)
    selected = task.get('harness')
    result = {'task_id': task_id, 'applicable': selected is not None,
              'read_only': True, 'certifies_completion': False, 'diagnostics': []}
    if selected is None:
        return result | {'status': 'not-applicable'}
    result['binding'] = selected
    try:
        checker, evidence, warnings = modules()
        root = Path(selected['repo']).resolve()
        actual = evidence.identity(root, selected['task_id'])
        if any(actual[key] != selected[key] for key in ('repo', 'git_dir', 'task_id')):
            raise StoreError('harness repository/worktree/task identity mismatch')
        profile, errors, exists = checker.read_profile(root)
        if not exists or profile.get('harness_version') != '9' or errors:
            raise StoreError('unsupported or invalid harness profile: ' + '; '.join(errors or ['harness version 9 required']))
        record = evidence.load(actual)
        result['record'] = str(evidence.record_path(actual))
        result['reviews'] = record['config'].get('reviews', {})
        result['completion'] = evidence.completion(record, checker, None)
        result['lead_context'] = 'unverified; only the responsible lead can attest current knowledge'
        result['warnings'] = warnings.check(actual['repo'], actual['task_id'])
        result['finalized_current'] = record.get('finalized', {}).get('after_digest') == result['completion']['snapshot']
        result['status'] = 'inspected'
        result['diagnostics'] = result['completion']['reasons']
    except Exception as error:
        result['status'] = 'unavailable'
        result['diagnostics'].append(str(error))
    return result
