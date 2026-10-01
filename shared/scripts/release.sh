#!/usr/bin/env bash
# Cut a release of mrcall-ai-kit: shared/scripts/release.sh vX.Y.Z [--dry-run]
#
# The version's major is the harness protocol (HARNESS_VERSION in
# shared/scripts/doc-check.py); the rule is in docs/documentation-harness.md,
# section "Releasing". Every check below runs and prints one PASS/FAIL line,
# so a single run shows everything that is wrong; any FAIL stops before the
# tag. All green: annotated tag, push, GitHub Release whose body is the
# version's CHANGELOG.md section. --dry-run runs the same checks and prints
# the three commands instead of running them.
#
# RELEASE_REMOTE (default origin), RELEASE_BRANCH (default main) and GH_REPO
# exist so the test can point the script at a throwaway remote.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
REMOTE="${RELEASE_REMOTE:-origin}"
BRANCH="${RELEASE_BRANCH:-main}"
GATE="shared/scripts/doc-check.py"
CHANGELOG="CHANGELOG.md"

VERSION=""
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) VERSION="$arg" ;;
  esac
done
if [[ -z "$VERSION" ]]; then
  echo "usage: $0 vX.Y.Z [--dry-run]" >&2
  exit 2
fi

FAILED=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; FAILED=1; }

# 1. Version shape. Nothing else can be judged without a major, so this is
#    the one check that stops the run on its own.
if [[ "$VERSION" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  MAJOR="${BASH_REMATCH[1]}"
  pass "version shape: $VERSION"
else
  fail "version shape: '$VERSION' is not vMAJOR.MINOR.PATCH"
  exit 1
fi

# 2. Major equals the harness protocol.
HARNESS="$(sed -nE 's/^HARNESS_VERSION = ([0-9]+)$/\1/p' "$GATE" | head -1)"
if [[ -z "$HARNESS" ]]; then
  fail "harness version: no 'HARNESS_VERSION = N' line in $GATE"
elif [[ "$MAJOR" == "$HARNESS" ]]; then
  pass "major $MAJOR equals HARNESS_VERSION $HARNESS"
else
  fail "major $MAJOR differs from HARNESS_VERSION $HARNESS: a release of this protocol is v$HARNESS.x.y"
fi

# 3. The tag does not exist, locally or on the remote. An unreachable remote
#    is a FAIL, never a PASS: a tag the script cannot see may still exist.
REMOTE_OK=1
if ! git fetch --quiet --tags "$REMOTE" 2>/dev/null; then
  REMOTE_OK=0
  fail "cannot reach remote '$REMOTE' (git fetch failed)"
elif git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  fail "tag $VERSION already exists locally"
else
  REMOTE_TAGS="$(git ls-remote --tags "$REMOTE" "refs/tags/$VERSION" 2>/dev/null)"; LS_RC=$?
  if (( LS_RC != 0 )); then
    REMOTE_OK=0
    fail "cannot reach remote '$REMOTE' (git ls-remote failed)"
  elif [[ -n "$REMOTE_TAGS" ]]; then
    fail "tag $VERSION already exists on $REMOTE"
  else
    pass "tag $VERSION does not exist yet"
  fi
fi

# 4. CHANGELOG.md has a non-empty section for this version.
NOTES_FILE="$(mktemp)"
trap 'rm -f "$NOTES_FILE"' EXIT
if [[ -f "$CHANGELOG" ]]; then
  # A section ends at the next version heading, not at any '## ' line: the
  # notes themselves use '## Added'-style headings at the same level.
  awk -v v="$VERSION" '
    /^## (v[0-9]+\.[0-9]+\.[0-9]+|Unreleased)( |$)/ { if (found) exit; if ($2 == v) { found = 1; next } }
    found && !started && /^[[:space:]]*$/ { next }
    found { started = 1; print }
  ' "$CHANGELOG" | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}' > "$NOTES_FILE"
  if [[ -s "$NOTES_FILE" ]] && grep -q '[^[:space:]]' "$NOTES_FILE"; then
    pass "$CHANGELOG has a '## $VERSION' section with notes"
  else
    fail "$CHANGELOG has no '## $VERSION' section with notes (add '## $VERSION — $(date +%F)' and its notes)"
  fi
else
  fail "$CHANGELOG is missing"
fi

# 5. No modified tracked files. Untracked files are not released and do not
#    count.
if [[ -z "$(git status --porcelain --untracked-files=no)" ]]; then
  pass "no modified tracked files"
else
  fail "modified tracked files: commit or discard them first"
fi

# 6. On the release branch, at the remote's tip.
CURRENT="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT" != "$BRANCH" ]]; then
  fail "branch is '$CURRENT', releases are cut from '$BRANCH'"
elif (( ! REMOTE_OK )) || ! git fetch --quiet "$REMOTE" "$BRANCH" 2>/dev/null; then
  fail "cannot compare HEAD with $REMOTE/$BRANCH: the remote is unreachable"
else
  REMOTE_TIP="$(git rev-parse -q --verify "refs/remotes/$REMOTE/$BRANCH" 2>/dev/null)"
  if [[ -z "$REMOTE_TIP" ]]; then
    fail "$REMOTE/$BRANCH is unknown: the branch was never pushed"
  elif [[ "$(git rev-parse HEAD)" == "$REMOTE_TIP" ]]; then
    pass "HEAD is $BRANCH at $REMOTE/$BRANCH"
  else
    fail "HEAD differs from $REMOTE/$BRANCH: push (or pull) first"
  fi
fi

# 7. The mechanical gate.
LOG_DIR="$(mktemp -d)"
if python3 "$GATE" --repo . > "$LOG_DIR/gate.log" 2>&1; then
  pass "gate: $GATE --repo ."
else
  fail "gate: $GATE --repo . (output: $LOG_DIR/gate.log)"
fi

# 8. Shell tests.
SHELL_FAILED=()
SHELL_COUNT=0
for t in tests/test_*.sh; do
  [[ -e "$t" ]] || continue
  SHELL_COUNT=$((SHELL_COUNT + 1))
  if ! bash "$t" > "$LOG_DIR/$(basename "$t").log" 2>&1; then
    SHELL_FAILED+=("$t")
  fi
done
if (( SHELL_COUNT == 0 )); then
  fail "shell tests: no tests/test_*.sh found"
elif (( ${#SHELL_FAILED[@]} == 0 )); then
  pass "shell tests: $SHELL_COUNT passed"
else
  fail "shell tests: ${SHELL_FAILED[*]} (logs: $LOG_DIR)"
fi

# 9. Python tests.
PY_DIRS=()
for d in tests shared/scripts/tests; do [[ -d "$d" ]] && PY_DIRS+=("$d"); done
if (( ${#PY_DIRS[@]} == 0 )); then
  fail "python tests: no test directory found"
elif python3 -m pytest -q "${PY_DIRS[@]}" > "$LOG_DIR/pytest.log" 2>&1; then
  pass "python tests: $(tail -1 "$LOG_DIR/pytest.log")"
else
  fail "python tests: $(tail -1 "$LOG_DIR/pytest.log") (log: $LOG_DIR/pytest.log)"
fi

if (( FAILED )); then
  echo "not releasing $VERSION: fix every FAIL above and run again" >&2
  exit 1
fi
rm -rf "$LOG_DIR"

# GH_REPO is only set by the test; the operator's gh resolves the repository
# from the checkout. The `[@]+` expansion keeps `set -u` quiet on an empty
# array under bash older than 4.4.
GH_REPO_ARGS=()
[[ -n "${GH_REPO:-}" ]] && GH_REPO_ARGS=(--repo "$GH_REPO")
TITLE="mrcall-ai-kit $VERSION"

if (( DRY_RUN )); then
  echo "dry run: every check passed; a real run would execute"
  echo "  git tag -a $VERSION -m \"$TITLE\""
  echo "  git push $REMOTE $VERSION"
  echo "  gh release create $VERSION ${GH_REPO_ARGS[@]+"${GH_REPO_ARGS[@]}"} --title \"$TITLE\" --notes-file <the '## $VERSION' section of $CHANGELOG>"
  exit 0
fi

git tag -a "$VERSION" -m "$TITLE" || exit 1
if ! git push "$REMOTE" "$VERSION"; then
  # Leave no half-release behind: a stray local tag would make every later
  # run refuse with "already exists locally".
  git tag -d "$VERSION" >/dev/null
  echo "push of $VERSION failed; the local tag was removed, nothing was released" >&2
  exit 1
fi
gh release create "$VERSION" ${GH_REPO_ARGS[@]+"${GH_REPO_ARGS[@]}"} --title "$TITLE" --notes-file "$NOTES_FILE" || exit 1
echo "released $TITLE"
