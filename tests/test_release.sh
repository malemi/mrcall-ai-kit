#!/usr/bin/env bash
# shared/scripts/release.sh refuses every precondition the "Releasing" rule
# lists (docs/documentation-harness.md) and, when all of them hold, tags,
# pushes and publishes. Proven against a throwaway clone with a bare remote
# and a `gh` stub that records what it was asked to do; nothing here touches
# the real remote or GitHub.
set -uo pipefail
KIT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null

# --- fixture: bare remote + clone carrying a copy of the real script --------
git init --quiet --bare "$TEST_ROOT/remote.git"
git clone --quiet "$TEST_ROOT/remote.git" "$TEST_ROOT/work" 2>/dev/null
WORK="$TEST_ROOT/work"
cd "$WORK"
git checkout --quiet -b main
mkdir -p shared/scripts/tests tests
cp "$KIT_DIR/shared/scripts/release.sh" shared/scripts/release.sh
# The gate stub: the HARNESS_VERSION line the script reads, and an exit code
# the test controls through FAKE_GATE_EXIT.
cat > shared/scripts/doc-check.py <<'EOF'
import os, sys
HARNESS_VERSION = 8
sys.exit(int(os.environ.get("FAKE_GATE_EXIT", "0")))
EOF
printf '#!/usr/bin/env bash\nexit 0\n' > tests/test_ok.sh
printf 'def test_ok():\n    assert True\n' > tests/test_trivial.py
printf 'def test_ok():\n    assert True\n' > shared/scripts/tests/test_scripts_trivial.py
cat > CHANGELOG.md <<'EOF'
# Changelog

## Unreleased

- nothing yet

## v8.1.0 — 2026-09-29

## Added

- the thing

## Verification

Suites passed.

## v8.0.0 — 2026-09-28

First release.
EOF
git add -A
git commit --quiet -m "fixture"
git push --quiet -u origin main 2>/dev/null

# --- gh stub: records its arguments and a copy of the notes file ------------
mkdir -p "$TEST_ROOT/bin"
export GH_LOG="$TEST_ROOT/gh.log" GH_NOTES_COPY="$TEST_ROOT/gh.notes"
cat > "$TEST_ROOT/bin/gh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$GH_LOG"
while [ $# -gt 0 ]; do
  if [ "$1" = "--notes-file" ]; then cp "$2" "$GH_NOTES_COPY"; shift; fi
  shift
done
EOF
chmod +x "$TEST_ROOT/bin/gh"
export PATH="$TEST_ROOT/bin:$PATH"

release() { shared/scripts/release.sh "$@"; }

# expect_fail <substring of the FAIL line> <release args...>
expect_fail() {
  local needle="$1"; shift
  local out rc
  out="$(release "$@" 2>&1)"; rc=$?
  if (( rc != 1 )); then
    echo "FAIL: expected exit 1 for '$*', got $rc"; echo "$out"; exit 1
  fi
  if ! grep -q "^FAIL  .*$needle" <<<"$out"; then
    echo "FAIL: expected a FAIL line matching '$needle' for '$*'"; echo "$out"; exit 1
  fi
  if grep -q '^released\|^dry run' <<<"$out"; then
    echo "FAIL: '$*' refused yet reported a release"; echo "$out"; exit 1
  fi
}

# --- refusals ----------------------------------------------------------------
expect_fail "differs from HARNESS_VERSION 8" v7.0.0
expect_fail "not vMAJOR.MINOR.PATCH" 8.1.0
expect_fail "no '## v8.2.0' section" v8.2.0

echo "edit" >> CHANGELOG.md
expect_fail "modified tracked files" v8.1.0
git checkout --quiet -- CHANGELOG.md

git checkout --quiet -b feature
expect_fail "branch is 'feature'" v8.1.0
git checkout --quiet main
git branch --quiet -D feature

git commit --quiet --allow-empty -m "unpushed"
expect_fail "HEAD differs from origin/main" v8.1.0
git reset --quiet --hard origin/main

FAKE_GATE_EXIT=1 expect_fail "gate:" v8.1.0

printf '#!/usr/bin/env bash\nexit 1\n' > tests/test_fail.sh
expect_fail "shell tests: tests/test_fail.sh" v8.1.0
rm tests/test_fail.sh

printf 'def test_bad():\n    assert False\n' > tests/test_bad.py
expect_fail "python tests:" v8.1.0
rm tests/test_bad.py

# An unreachable remote is a refusal, not a PASS on checks it could not run.
RELEASE_REMOTE="$TEST_ROOT/nowhere.git" expect_fail "cannot reach remote" v8.1.0
out="$(RELEASE_REMOTE="$TEST_ROOT/nowhere.git" release v8.1.0 2>&1)"
if grep -q '^PASS  tag\|^PASS  HEAD' <<<"$out"; then
  echo "FAIL: an unreachable remote still passed a remote check"; echo "$out"; exit 1
fi

# A refused run leaves nothing behind: no tag, no gh call.
if git rev-parse -q --verify refs/tags/v8.1.0 >/dev/null || [[ -e "$GH_LOG" ]]; then
  echo "FAIL: a refused run created a tag or called gh"; exit 1
fi

# --- dry run on a green tree: every check passes, nothing is created ---------
out="$(release v8.1.0 --dry-run 2>&1)"; rc=$?
if (( rc != 0 )) || grep -q '^FAIL' <<<"$out"; then
  echo "FAIL: dry run on a green tree did not pass"; echo "$out"; exit 1
fi
for cmd in 'git tag -a v8.1.0 -m "mrcall-ai-kit v8.1.0"' 'git push origin v8.1.0' 'gh release create v8.1.0'; do
  grep -qF "$cmd" <<<"$out" || { echo "FAIL: dry run did not print: $cmd"; echo "$out"; exit 1; }
done
if git rev-parse -q --verify refs/tags/v8.1.0 >/dev/null || [[ -e "$GH_LOG" ]]; then
  echo "FAIL: dry run created a tag or called gh"; exit 1
fi

# --- the real thing ----------------------------------------------------------
out="$(GH_REPO=owner/kit release v8.1.0 2>&1)"; rc=$?
if (( rc != 0 )) || ! grep -q '^released mrcall-ai-kit v8.1.0$' <<<"$out"; then
  echo "FAIL: release on a green tree did not succeed"; echo "$out"; exit 1
fi
remote_tag="$(git --git-dir "$TEST_ROOT/remote.git" for-each-ref refs/tags/v8.1.0 --format='%(objecttype) %(contents:subject)')"
[[ "$remote_tag" == "tag mrcall-ai-kit v8.1.0" ]] \
  || { echo "FAIL: remote tag is '$remote_tag', expected an annotated tag with message 'mrcall-ai-kit v8.1.0'"; exit 1; }
grep -qF 'release create v8.1.0 --repo owner/kit --title mrcall-ai-kit v8.1.0 --notes-file' "$GH_LOG" \
  || { echo "FAIL: gh was not asked to create the release as specified"; cat "$GH_LOG"; exit 1; }
expected_notes="$(printf '## Added\n\n- the thing\n\n## Verification\n\nSuites passed.')"
[[ "$(cat "$GH_NOTES_COPY")" == "$expected_notes" ]] \
  || { echo "FAIL: release notes differ from the changelog section"; diff <(echo "$expected_notes") "$GH_NOTES_COPY"; exit 1; }

# The tag now exists: the same version is refused.
expect_fail "tag v8.1.0 already exists" v8.1.0

echo "release.sh refusals, dry run, and release path: PASS"
