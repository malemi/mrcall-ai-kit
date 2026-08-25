#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, help='Input file path, stdin if omitted')
    parser.add_argument('--expect-files', type=str, help='Comma-separated paths that must exist')
    parser.add_argument('--run', type=str, help='Shell command to run')
    parser.add_argument('--require-done', action='store_true', help='Require ## Done (not used in logic yet)')
    parser.add_argument('--budget-lines', type=int, default=20,
                        help='Max non-empty lines in a report; 0 disables the budget check')

    args = parser.parse_args()
    
    # Read input
    content = ''
    if args.input:
        try:
            with open(args.input, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f'INVALID: Cannot read input file: {e}', file=sys.stderr)
            sys.exit(2)
    else:
        content = sys.stdin.read()
    
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    
    # Check for empty
    if not lines:
        print('INVALID: Empty report', file=sys.stderr)
        sys.exit(2)
    
    # Check for Done/Blocked
    has_done = any(line.startswith('## Done') for line in lines)
    has_blocked = any(line.startswith('## Blocked') for line in lines)
    
    # Detect tracebacks or errors
    traceback_patterns = [
        'Traceback (most recent call last)',
        'ModuleNotFoundError',
        'Error:'
    ]
    error_lines = []
    for line in lines:
        if any(pattern in line for pattern in traceback_patterns):
            error_lines.append(line)
    
    # Count repeated error lines
    from collections import Counter
    if error_lines:
        line_counts = Counter(error_lines)
        repeated = any(count >= 3 for count in line_counts.values())
        if repeated and not has_done:
            print('INVALID: Repeated error lines without ## Done', file=sys.stderr)
            sys.exit(2)
    
    # If Blocked -> FAIL
    if has_blocked and not has_done:  # If both, Done wins
        print('FAIL: Worker reported ## Blocked', file=sys.stderr)
        sys.exit(1)
    
    # If no Done and no Blocked but has error patterns -> INVALID
    if not has_done and not has_blocked:
        if any(pattern in content for pattern in traceback_patterns):
            print('INVALID: Traceback or error pattern found without ## Done or ## Blocked', file=sys.stderr)
            sys.exit(2)
        else:
            print('INVALID: No ## Done or ## Blocked header', file=sys.stderr)
            sys.exit(2)
    
    # If no Done -> already failed or invalid, so exit 1 or 2 already
    if not has_done:
        sys.exit(1)  # Should not reach here due to above, but safety

    # Report budget. A worker exists to keep work out of the caller's context,
    # and a report that pastes a diff back in defeats the delegation it just did.
    # Enforced rather than warned: a warning here would be the same
    # sensor-without-actuator that let the advisories be ignored for months.
    if args.budget_lines:
        if len(lines) > args.budget_lines:
            print(f'FAIL: Report is {len(lines)} lines, budget is {args.budget_lines}. '
                  f'Write long evidence to $TMPDIR/mrcall-ai-kit/<task-id>/ and cite the path.',
                  file=sys.stderr)
            sys.exit(1)
        diff_markers = ('diff --git', '@@ ', '+++ ', '--- ')
        pasted = [ln for ln in lines if ln.startswith(diff_markers)]
        if pasted:
            print(f'FAIL: Report contains a pasted diff ({pasted[0][:40]!r}). '
                  f'Cite an evidence path instead.', file=sys.stderr)
            sys.exit(1)
        if 'Traceback (most recent call last)' in content:
            print('FAIL: Report contains a stack trace. Cite an evidence path instead.',
                  file=sys.stderr)
            sys.exit(1)
        if not any(ln.startswith('- Unverified:') for ln in lines):
            print('FAIL: Report has no `- Unverified:` line. It is never dropped for '
                  'brevity — it is what keeps a short report from being a confident lie.',
                  file=sys.stderr)
            sys.exit(1)

    # Check expected files
    if args.expect_files:
        file_paths = [p.strip() for p in args.expect_files.split(',')]
        missing = []
        for path in file_paths:
            if not os.path.exists(path):
                missing.append(path)
        if missing:
            print(f'FAIL: Expected files not found: {missing}', file=sys.stderr)
            sys.exit(1)

    # Run command
    if args.run:
        result = subprocess.run(args.run, shell=True)
        if result.returncode != 0:
            print(f'FAIL: Command failed: {args.run}', file=sys.stderr)
            sys.exit(1)

    print('PASS: Worker completed successfully')
    sys.exit(0)

if __name__ == "__main__":
    main()