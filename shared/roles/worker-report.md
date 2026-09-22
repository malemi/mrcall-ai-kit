## Report budget

Your report is read by the session that delegated to you, and every line of it
lands in a context window you exist to protect. At most **twenty lines**.

Never put in a report: a diff, a file listing, a stack trace, or more than three
consecutive lines of command output. When the evidence is longer than that,
write it to `$TMPDIR/mrcall-ai-kit/<task-id>/<your-agent-name>.log` and put that
path on the `Evidence:` line. Create the directory if it does not exist. It is
outside the repository on purpose — a worker's scratch output is not repository
knowledge and must never be one missing `.gitignore` line away from a commit.

The `Unverified:` line is never dropped for brevity. A short report that quietly
omits what you did not check is worse than a long one, and that line is the only
thing standing between a twenty-line budget and a confident-sounding lie.

## When you're done

```
## Done
- Changed: <repo-relative paths, or "none">
- What: <summary of the change, or the findings>
- Verified: <command + its real output, or why a claim stayed unverifiable>
- Unverified: <what you did NOT check — "nothing" only if that is true>
- Evidence: <path under $TMPDIR/mrcall-ai-kit/<task-id>/, or "none">
```

If you could not complete the task:

```
## Blocked
- Reason: <why>
- What I tried: <steps>
- Suggestion: <what the delegating session should do>
```

Return one of these two headers exactly. Anything else is treated as a failure.
