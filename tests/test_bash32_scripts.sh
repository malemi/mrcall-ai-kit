#!/usr/bin/env bash
# The scripts an operator's machine runs with the `bash` first on its PATH run on
# the oldest bash it may have: /bin/bash on a Mac is GNU bash 3.2, which Apple
# ships and does not update. Before this gate, install.sh stopped under it on an
# empty array (`set -u` before bash 4.4) and uninstall.sh did not even parse
# (associative arrays, `[[ -v ]]`). See docs/briefs/2026-10-19-bash-3-2-installers.md.
#
# The bash under test is /bin/bash when it exists, else the first bash on PATH;
# the installers are run through it explicitly, so their shebang does not choose.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Resolved: on a Mac mktemp answers under /var, a symlink, and the verification
# warnings helper refuses a state path through a symlink (a HOME never is one).
TEST_ROOT="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$TEST_ROOT"' EXIT

if [[ -x /bin/bash ]]; then OLD_BASH=/bin/bash; else OLD_BASH="$(command -v bash)"; fi
echo "bash under test: $OLD_BASH ($("$OLD_BASH" -c 'echo "$BASH_VERSION"'))"

fail() { echo "FAIL: $*"; exit 1; }

for script in install.sh uninstall.sh shared/scripts/ai-help.sh shared/scripts/ai-tutorial.sh; do
  "$OLD_BASH" -n "$KIT_DIR/$script" || fail "$script does not parse"
done

# An install and its uninstall in a sandboxed HOME: once with no runtime to
# register verification warnings for (an empty array), once with all of them.
run() {
  local name="$1"; shift
  local home="$TEST_ROOT/$name"
  mkdir -p "$home"
  local flags=(--environment all --features all --mode symlink --on-exist overwrite "$@")
  (cd "$KIT_DIR" && HOME="$home" "$OLD_BASH" ./install.sh "${flags[@]}" --dry-run < /dev/null > /dev/null) \
    || fail "$name: install --dry-run"
  (cd "$KIT_DIR" && HOME="$home" "$OLD_BASH" ./install.sh "${flags[@]}" --yes < /dev/null > /dev/null) \
    || fail "$name: install"
  local manifest="$home/.config/mrcall-ai-kit/installed.tsv"
  [[ -s "$manifest" ]] || fail "$name: no manifest after install"
  local recorded; recorded="$(cut -f3 "$manifest" | sort -u)"
  # The installed helpers, run the way the /ai-help and /ai-tutorial commands run them.
  local helper arg
  for helper in ai-help.sh ai-tutorial.sh; do
    for arg in "" all; do
      HOME="$home" "$OLD_BASH" "$home/.config/mrcall-ai-kit/$helper" $arg > /dev/null \
        || fail "$name: installed $helper ${arg:-(no argument)} exits non-zero"
    done
  done
  # A reinstall over the first, keeping backups: every destination twice in the
  # manifest (last line wins), each with a backup; one kit file then modified, so
  # the uninstall keeps it and the manifest rewrite keeps its line.
  (cd "$KIT_DIR" && HOME="$home" "$OLD_BASH" ./install.sh "${flags[@]/overwrite/backup}" --yes < /dev/null > /dev/null) \
    || fail "$name: reinstall with backups"
  local modified="$home/.codex/agents/verify.toml"
  [[ -f "$modified" && ! -L "$modified" ]] || fail "$name: expected a copied file at $modified"
  echo "# modified" >> "$modified"
  (cd "$KIT_DIR" && HOME="$home" "$OLD_BASH" ./uninstall.sh --dry-run < /dev/null > /dev/null) \
    || fail "$name: uninstall --dry-run"
  (cd "$KIT_DIR" && HOME="$home" "$OLD_BASH" ./uninstall.sh --yes --restore-backups < /dev/null > /dev/null) \
    || fail "$name: uninstall"
  # Only the modified file stays, and the rewritten manifest keeps its one line.
  [[ "$(cut -f3 "$manifest")" == "$modified" ]] || fail "$name: the manifest does not keep exactly the modified file"
  grep -q '^# modified$' "$modified" || fail "$name: the modified file was not kept"
  # Every other backup went back into place; the modified file's stays beside it,
  # because its path holds a file the kit did not put there.
  local left; left="$(cd "$home" && find . -name '*.bak' -print)"
  [[ "$left" == "./.codex/agents/verify.toml.bak" ]] || fail "$name: backups left after restore: ${left:-none}"
  local dest
  while IFS= read -r dest; do
    [[ -z "$dest" ]] && continue
    [[ -e "$dest" || -L "$dest" ]] || fail "$name: $dest was not restored"
  done <<< "$recorded"
  echo "  $name: installed and uninstalled under $OLD_BASH"
}
run plain
run warnings --activate-verification-warnings all

echo "installers and helpers run on the oldest bash: PASS"
