#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
# mrcall-opencode-kit install script
# Symlinks (or copies) skills, commands, and agents into
# ~/.config/opencode/ so OpenCode can discover them.
# ──────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/opencode"

MODE="copy"
FORCE=false
DRY_RUN=false

# ── Parse flags ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --symlink) MODE="symlink" ; shift ;;
    --force)   FORCE=true     ; shift ;;
    --dry-run) DRY_RUN=true   ; shift ;;
    --help|-h)
      echo "Usage: $(basename "$0") [--symlink] [--force] [--dry-run]"
      echo ""
      echo "  --symlink  Symlink files instead of copying (edit repo = edit config)"
      echo "  --force    Overwrite existing files"
      echo "  --dry-run  Show what would be done without doing it"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $(basename "$0") [--symlink] [--force] [--dry-run]"
      exit 1
      ;;
  esac
done

# ── Directories to create ────────────────────────────────────
TARGET_DIRS=(
  "$CONFIG_DIR/skills"
  "$CONFIG_DIR/commands"
  "$CONFIG_DIR/agents"
)

# ── Source directories ───────────────────────────────────────
SOURCE_SKILLS="$SCRIPT_DIR/skills"
SOURCE_COMMANDS="$SCRIPT_DIR/commands"
SOURCE_AGENTS="$SCRIPT_DIR/agents"

# ── Helpers ──────────────────────────────────────────────────
do_link() {
  local src="$1"
  local dst="$2"
  if $DRY_RUN; then
    echo "  [dry-run] ln -s \"$src\" \"$dst\""
    return
  fi
  ln -s "$src" "$dst"
  echo "  symlink  $dst → $src"
}

do_copy() {
  local src="$1"
  local dst="$2"
  if $DRY_RUN; then
    echo "  [dry-run] cp -r \"$src\" \"$dst\""
    return
  fi
  cp -r "$src" "$dst"
  echo "  copy     $src → $dst"
}

install_item() {
  local src="$1"
  local dst="$2"

  if [[ -e "$dst" || -L "$dst" ]]; then
    if $FORCE; then
      if $DRY_RUN; then
        echo "  [dry-run] rm -rf \"$dst\" (would overwrite)"
        return
      fi
      rm -rf "$dst"
      echo "  remove   $dst (overwrite)"
    else
      echo "  skip     $dst (exists, use --force to overwrite)"
      return
    fi
  fi

  if [[ "$MODE" == "symlink" ]]; then
    do_link "$src" "$dst"
  else
    do_copy "$src" "$dst"
  fi
}

install_dir_contents() {
  local src_dir="$1"
  local dst_dir="$2"
  local label="$3"

  if [[ ! -d "$src_dir" ]]; then
    echo "  [skip]  $label source missing: $src_dir"
    return
  fi

  echo ""
  echo "── $label ──"

  # Use find to get all entries (files + dirs) one level deep
  # We handle both flat files and subdirectories
  while IFS= read -r -d '' entry; do
    local name
    name="$(basename "$entry")"
    install_item "$entry" "$dst_dir/$name"
  done < <(find "$src_dir" -mindepth 1 -maxdepth 1 -print0)
}

# ── Main ─────────────────────────────────────────────────────
echo "mrcall-opencode-kit installer"
echo "  Kit dir:  $SCRIPT_DIR"
echo "  Target:   $CONFIG_DIR"
echo "  Mode:     $MODE"
echo "  Force:    $FORCE"
echo ""

# Create target directories
for d in "${TARGET_DIRS[@]}"; do
  if $DRY_RUN; then
    echo "  [dry-run] mkdir -p \"$d\""
  else
    mkdir -p "$d"
  fi
done

# Install each category
install_dir_contents "$SOURCE_SKILLS"   "$CONFIG_DIR/skills"   "skills"
install_dir_contents "$SOURCE_COMMANDS" "$CONFIG_DIR/commands" "commands"
install_dir_contents "$SOURCE_AGENTS"   "$CONFIG_DIR/agents"   "agents"

echo ""
echo "── Done ──"
echo "Restart your OpenCode sessions to pick up the new skills, commands, and agents."
