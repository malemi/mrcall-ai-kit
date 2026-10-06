#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# mrcall-ai-kit uninstaller — manifest-driven.
# Removes EXACTLY what ./install.sh recorded in the install log; no guessing.
#   log: ~/.config/mrcall-ai-kit/installed.tsv  (timestamp, mode, dest, src, backup, optional copy digest)
#
# Flags:
#   --dry-run           show what would be removed, change nothing
#   --yes               skip the confirmation
#   --restore-backups   move each recorded backup back into place after removal:
#                       a <file>.bak, or a directory under
#                       ~/.config/mrcall-ai-kit/backups/. A file the install
#                       retired comes back the same way.
#   --help
# ──────────────────────────────────────────────────────────────────────────

KIT_GLOBAL="$HOME/.config/mrcall-ai-kit"
MANIFEST="$KIT_GLOBAL/installed.tsv"
DRY_RUN=false ; ASSUME_YES=false ; RESTORE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)          DRY_RUN=true ;    shift ;;
    --yes|-y)           ASSUME_YES=true ; shift ;;
    --restore-backups)  RESTORE=true ;    shift ;;
    --help|-h)
      echo "Usage: ./uninstall.sh [--dry-run] [--yes] [--restore-backups]"
      echo "Removes unchanged kit-owned assets recorded in $MANIFEST; preserves modified or foreign content."
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -f "$MANIFEST" ]] || { echo "No install manifest at $MANIFEST — nothing to uninstall."; exit 0; }

# Unique destinations, last line wins (re-installs append duplicate lines).
declare -A MODE_OF SRC_OF BAK_OF HASH_OF
order=()
while IFS= read -r line || [[ -n "${line:-}" ]]; do
  IFS=$'\x1f' read -r ts mode dest src bak content_hash <<< "${line//$'\t'/$'\x1f'}"
  [[ -n "${dest:-}" ]] || continue
  [[ -v MODE_OF["$dest"] ]] || order+=("$dest")
  MODE_OF["$dest"]="$mode" ; SRC_OF["$dest"]="$src" ; BAK_OF["$dest"]="${bak:-}" ; HASH_OF["$dest"]="${content_hash:-}"
done < "$MANIFEST"

[[ ${#order[@]} -gt 0 ]] || { echo "Manifest is empty — nothing to uninstall."; exit 0; }

# A backup that is a moved symlink may dangle, and still is one.
has_backup() { [[ -n "${BAK_OF[$1]}" ]] && [[ -e "${BAK_OF[$1]}" || -L "${BAK_OF[$1]}" ]]; }

# Once an entry is handled, a file the kit did not put there may still sit at
# its path. No backup goes back onto an occupied foreign path.
item_digest() {
  python3 - "$1" <<'DIGEST'
from pathlib import Path
import hashlib, json, os, stat, sys
root = Path(sys.argv[1])
items = [root]
if root.is_dir() and not root.is_symlink():
    for base, directories, files in os.walk(root, followlinks=False):
        items.extend(Path(base) / name for name in directories + files)
records = []
for item in sorted(items):
    mode = item.lstat().st_mode
    payload = os.readlink(item) if item.is_symlink() else hashlib.sha256(item.read_bytes()).hexdigest() if item.is_file() else ''
    records.append([str(item.relative_to(root)), stat.S_IFMT(mode), stat.S_IMODE(mode), payload])
print(hashlib.sha256(json.dumps(records, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest())
DIGEST
}

owned_item() {
  local dest="$1" source="${SRC_OF[$1]}"
  if [[ -L "$dest" ]]; then
    [[ "${MODE_OF[$dest]}" == symlink && "$(readlink "$dest")" == "$source" ]]
  elif [[ "${MODE_OF[$dest]}" == copy && -n "${HASH_OF[$dest]}" && -e "$dest" ]]; then
    [[ "$(item_digest "$dest")" == "${HASH_OF[$dest]}" ]]
  elif [[ "${MODE_OF[$dest]}" == copy && -e "$source" ]]; then
    if [[ -d "$dest" && -d "$source" ]]; then diff -qr "$source" "$dest" > /dev/null
    else cmp -s "$source" "$dest"
    fi
  else
    return 1
  fi
}

stays_occupied() {
  [[ -e "$1" || -L "$1" ]] && ! owned_item "$1"
}

echo "Uninstall plan (from $MANIFEST):"
for d in "${order[@]}"; do
  if [[ "${MODE_OF[$d]}" == retired ]]; then
    # The install removed the kit's file here and put nothing in its place.
    printf "  retired %s\n" "$d  [nothing to remove]"
  else
    state="${MODE_OF[$d]}"; [[ -e "$d" || -L "$d" ]] || state="$state, already gone"
    if [[ -e "$d" || -L "$d" ]] && ! owned_item "$d"; then
      printf "  keep    %s\n" "$d  [modified, foreign, or ownership unavailable]"
    else
      printf "  remove  %s\n" "$d  [$state]"
    fi
  fi
  if $RESTORE && has_backup "$d"; then
    if stays_occupied "$d"; then
      echo "          backup stays at ${BAK_OF[$d]}: $d holds a file the kit did not put there"
    else
      echo "          then restore <- ${BAK_OF[$d]}"
    fi
  fi
done
echo

if ! $DRY_RUN && ! $ASSUME_YES; then
  read -r -p "Proceed? [y/N] " a || true
  [[ "${a:-}" =~ ^[Yy] ]] || { echo "Aborted."; exit 0; }
fi

if $DRY_RUN; then RM="would remove"; RS="would restore"; else RM="removed"; RS="restored"; fi

# Registrations live in runtime-owned settings/plugin locations and therefore
# are not manifest artifacts. Remove only entries identified by the shared
# structural helper before that helper itself is uninstalled.
SCOPE_REGISTER="$KIT_GLOBAL/scope-guard/scope_guard_register.py"
if [[ -f "$SCOPE_REGISTER" && -v SRC_OF["$SCOPE_REGISTER"] ]] && owned_item "$SCOPE_REGISTER"; then
  for runtime in claude codex opencode; do
    if $DRY_RUN; then
      python3 "$SCOPE_REGISTER" "$runtime" unregister --dry-run
    else
      python3 "$SCOPE_REGISTER" "$runtime" unregister
    fi
  done
fi
CODEX_ROSTER="$KIT_GLOBAL/codex-agent-roster.py"
CODEX_BLOCK="$KIT_GLOBAL/codex-AGENTS.block.md"
if [[ -f "$CODEX_ROSTER" && -f "$CODEX_BLOCK" && -v SRC_OF["$CODEX_ROSTER"] && -v SRC_OF["$CODEX_BLOCK"] ]] && owned_item "$CODEX_ROSTER" && owned_item "$CODEX_BLOCK"; then
  if $DRY_RUN; then
    python3 "$CODEX_ROSTER" off --home "$HOME" --block "$KIT_GLOBAL/codex-AGENTS.block.md" --dry-run
  else
    python3 "$CODEX_ROSTER" off --home "$HOME" --block "$KIT_GLOBAL/codex-AGENTS.block.md"
  fi
fi

removed=0
for d in "${order[@]}"; do
  if [[ "${MODE_OF[$d]}" == retired ]]; then
    :   # anything here now was put there after the retirement, and not by the kit
  elif [[ -L "$d" ]]; then
    tgt="$(readlink "$d" || true)"
    if owned_item "$d"; then
      $DRY_RUN || rm -f "$d"; echo "  $RM symlink  $d"; removed=$((removed + 1))
    else
      echo "  KEPT (symlink not ours -> $tgt)  $d"
    fi
  elif [[ -e "$d" ]]; then
    if owned_item "$d"; then
      $DRY_RUN || rm -rf "$d"; echo "  $RM  $d"; removed=$((removed + 1))
    else
      echo "  KEPT (modified, foreign, or ownership unavailable)  $d"
    fi
  else
    echo "  already gone  $d"
  fi
  if $RESTORE && has_backup "$d"; then
    if stays_occupied "$d"; then
      echo "  KEPT backup  ${BAK_OF[$d]}  ($d holds a file the kit did not put there)"
    else
      $DRY_RUN || mv "${BAK_OF[$d]}" "$d"; echo "  $RS backup  $d"
    fi
  fi
done

if ! $DRY_RUN; then
  remaining="$(mktemp "$KIT_GLOBAL/installed.XXXXXX")"
  for d in "${order[@]}"; do
    if stays_occupied "$d"; then
      D="$d" awk -F '\t' '$3 == ENVIRON["D"] { line = $0 } END { if (line != "") print line }' "$MANIFEST" >> "$remaining"
    fi
  done
  mv "$remaining" "$MANIFEST"
fi
echo
echo "Done. $removed item(s) removed.$($DRY_RUN && echo ' (dry-run — nothing changed)' || true)"
