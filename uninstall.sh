#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# mrcall-ai-kit uninstaller — manifest-driven.
# Removes EXACTLY what ./install.sh recorded in the install log; no guessing.
#   log: ~/.config/mrcall-ai-kit/installed.tsv  (timestamp, mode, dest, src, backup)
#
# Flags:
#   --dry-run           show what would be removed, change nothing
#   --yes               skip the confirmation (also removes symlinks even if
#                       their target no longer matches what we installed)
#   --restore-backups   move each recorded *.bak back into place after removal
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
      echo "Removes exactly what install recorded in $MANIFEST."
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -f "$MANIFEST" ]] || { echo "No install manifest at $MANIFEST — nothing to uninstall."; exit 0; }

# Unique destinations, last line wins (re-installs append duplicate lines).
declare -A MODE_OF SRC_OF BAK_OF
order=()
while IFS=$'\t' read -r ts mode dest src bak || [[ -n "${dest:-}" ]]; do
  [[ -n "${dest:-}" ]] || continue
  [[ -v MODE_OF["$dest"] ]] || order+=("$dest")
  MODE_OF["$dest"]="$mode" ; SRC_OF["$dest"]="$src" ; BAK_OF["$dest"]="${bak:-}"
done < "$MANIFEST"

[[ ${#order[@]} -gt 0 ]] || { echo "Manifest is empty — nothing to uninstall."; exit 0; }

echo "Uninstall plan (from $MANIFEST):"
for d in "${order[@]}"; do
  state="${MODE_OF[$d]}"; [[ -e "$d" || -L "$d" ]] || state="$state, already gone"
  printf "  remove  %s\n" "$d  [$state]"
  if $RESTORE && [[ -n "${BAK_OF[$d]}" && -e "${BAK_OF[$d]}" ]]; then
    echo "          then restore <- ${BAK_OF[$d]}"
  fi
done
echo

if ! $DRY_RUN && ! $ASSUME_YES; then
  read -r -p "Proceed? [y/N] " a || true
  [[ "${a:-}" =~ ^[Yy] ]] || { echo "Aborted."; exit 0; }
fi

if $DRY_RUN; then RM="would remove"; RS="would restore"; else RM="removed"; RS="restored"; fi
removed=0
for d in "${order[@]}"; do
  if [[ -L "$d" ]]; then
    tgt="$(readlink "$d" || true)"
    if [[ "$tgt" == "${SRC_OF[$d]}" || "$ASSUME_YES" == true ]]; then
      $DRY_RUN || rm -f "$d"; echo "  $RM symlink  $d"; removed=$((removed + 1))
    else
      echo "  KEPT (symlink not ours -> $tgt)  $d"
    fi
  elif [[ -e "$d" ]]; then
    $DRY_RUN || rm -rf "$d"; echo "  $RM  $d"; removed=$((removed + 1))
  else
    echo "  already gone  $d"
  fi
  if $RESTORE && [[ -n "${BAK_OF[$d]}" && -e "${BAK_OF[$d]}" ]]; then
    $DRY_RUN || mv "${BAK_OF[$d]}" "$d"; echo "  $RS backup  $d"
  fi
done

$DRY_RUN || : > "$MANIFEST"   # clear the log; everything in it is now removed
echo
echo "Done. $removed item(s) removed.$($DRY_RUN && echo ' (dry-run — nothing changed)' || true)"
