#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# mrcall-opencode-kit uninstaller
# Removes symlinks pointing to the kit from ~/.config/opencode/
# ──────────────────────────────────────────────────────────────

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
OPENCODE_DIR="$HOME/.config/opencode"

DRY_RUN=false
FORCE=false

# ── Parse flags ──────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --force)   FORCE=true   ;;
    *)
      echo "Usage: $0 [--dry-run] [--force]" >&2
      exit 1
      ;;
  esac
done

if [ ! -d "$OPENCODE_DIR" ]; then
  echo "OpenCode config directory not found: $OPENCODE_DIR"
  exit 0
fi

# ── Collect kit-relative paths ───────────────────────────────
# We only care about files/dirs under: skills/, commands/, agents/
# plus top-level AGENTS.md and llms.md
kit_paths=()
while IFS= read -r -d '' f; do
  rel="${f#$KIT_DIR/}"
  kit_paths+=("$rel")
done < <(find "$KIT_DIR" \( -type f -o -type d \) \
  \( -path "*/skills/*" -o -path "*/commands/*" -o -path "*/agents/*" \
     -o -name "AGENTS.md" -o -name "llms.md" \) \
  -print0 2>/dev/null || true)

if [ ${#kit_paths[@]} -eq 0 ]; then
  echo "No kit-managed paths found in $KIT_DIR"
  exit 0
fi

# ── Resolve target in opencode config ────────────────────────
removed_symlinks=0
removed_files=0
skipped=0

remove_item() {
  local target="$1"
  local is_symlink="$2"

  if $DRY_RUN; then
    if [ "$is_symlink" = true ]; then
      echo "[dry-run] would remove symlink: $target"
    else
      echo "[dry-run] would remove file:     $target"
    fi
    return
  fi

  if [ "$is_symlink" = true ]; then
    rm "$target"
    echo "removed symlink: $target"
    removed_symlinks=$((removed_symlinks + 1))
  else
    rm -rf "$target"
    echo "removed file:     $target"
    removed_files=$((removed_files + 1))
  fi
}

# ── Walk each kit path and check the corresponding opencode path ──
for rel in "${kit_paths[@]}"; do
  opencode_path="$OPENCODE_DIR/$rel"

  # Safety: never touch the opencode root itself
  if [ "$opencode_path" = "$OPENCODE_DIR" ] || [ "$opencode_path" = "$OPENCODE_DIR/" ]; then
    continue
  fi

  if [ ! -e "$opencode_path" ]; then
    continue
  fi

  # ── Symlink handling ───────────────────────────────────────
  if [ -L "$opencode_path" ]; then
    link_target="$(readlink "$opencode_path")"
    # Normalize both to absolute paths for comparison
    case "$link_target" in
      /*) ;;
      *) link_target="$(dirname "$opencode_path")/$link_target" ;;
    esac
    link_target="$(cd "$(dirname "$link_target")" 2>/dev/null && pwd)/$(basename "$link_target")" || true
    kit_canonical="$(cd "$KIT_DIR" && pwd)/$rel"

    if [ "$link_target" = "$kit_canonical" ]; then
      remove_item "$opencode_path" true
    fi
    continue
  fi

  # ── Non-symlink (real file/dir) handling ───────────────────
  # Only act if --force was given
  if ! $FORCE; then
    skipped=$((skipped + 1))
    continue
  fi

  # Confirm unless --force (which implies yes)
  if $DRY_RUN; then
    remove_item "$opencode_path" false
    continue
  fi

  echo "WARNING: $opencode_path is a real file (not a symlink)."
  read -r -p "Remove it? [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS]) remove_item "$opencode_path" false ;;
    *) echo "  skipped"; skipped=$((skipped + 1)) ;;
  esac
done

# ── Summary ──────────────────────────────────────────────────
if $DRY_RUN; then
  echo ""
  echo "Dry-run complete. Pass no flags (or --force) to actually remove."
else
  echo ""
  echo "Done: $removed_symlinks symlinks removed, $removed_files files removed, $skipped skipped."
fi
