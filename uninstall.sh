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

# A backup that is a moved symlink may dangle, and still is one.
has_backup() { [[ -n "${BAK_OF[$1]}" ]] && [[ -e "${BAK_OF[$1]}" || -L "${BAK_OF[$1]}" ]]; }

# Once an entry is handled, a file the kit did not put there may still sit at
# its path: whatever fills a retired path, or a link pointed away from the
# kit's source that --yes does not remove. No backup goes back onto it.
stays_occupied() { # $1=destination
  if [[ "${MODE_OF[$1]}" == retired ]]; then [[ -e "$1" || -L "$1" ]]
  elif [[ -L "$1" ]]; then ! $ASSUME_YES && [[ "$(readlink "$1" || true)" != "${SRC_OF[$1]}" ]]
  else return 1
  fi
}

echo "Uninstall plan (from $MANIFEST):"
for d in "${order[@]}"; do
  if [[ "${MODE_OF[$d]}" == retired ]]; then
    # The install removed the kit's file here and put nothing in its place.
    printf "  retired %s\n" "$d  [nothing to remove]"
  else
    state="${MODE_OF[$d]}"; [[ -e "$d" || -L "$d" ]] || state="$state, already gone"
    printf "  remove  %s\n" "$d  [$state]"
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
if [[ -f "$SCOPE_REGISTER" ]]; then
  for runtime in claude codex opencode; do
    if $DRY_RUN; then
      python3 "$SCOPE_REGISTER" "$runtime" unregister --dry-run
    else
      python3 "$SCOPE_REGISTER" "$runtime" unregister
    fi
  done
fi
CODEX_ROSTER="$KIT_GLOBAL/codex-agent-roster.py"
if [[ -f "$CODEX_ROSTER" ]]; then
  if $DRY_RUN; then
    echo "  [dry]    remove kit block from $HOME/.codex/AGENTS.md"
  else
    python3 "$CODEX_ROSTER" off --home "$HOME"
  fi
fi

removed=0
for d in "${order[@]}"; do
  if [[ "${MODE_OF[$d]}" == retired ]]; then
    :   # anything here now was put there after the retirement, and not by the kit
  elif [[ -L "$d" ]]; then
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
  if $RESTORE && has_backup "$d"; then
    if stays_occupied "$d"; then
      echo "  KEPT backup  ${BAK_OF[$d]}  ($d holds a file the kit did not put there)"
    else
      $DRY_RUN || mv "${BAK_OF[$d]}" "$d"; echo "  $RS backup  $d"
    fi
  fi
done

$DRY_RUN || : > "$MANIFEST"   # clear the log; everything in it is now removed
echo
echo "Done. $removed item(s) removed.$($DRY_RUN && echo ' (dry-run — nothing changed)' || true)"
