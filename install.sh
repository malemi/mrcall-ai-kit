#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# mrcall-ai-kit installer
#
# Installs reusable AI-tool config into your GLOBAL Claude Code and/or OpenCode
# config. Interactive by default; pass flags for non-interactive / CI use.
#
# Content is routed by tool-compatibility:
#   shared/    cross-tool  — the doc-harness (doc-* commands, doc-critic skill)
#              + doc-check.py (installed once to ~/.config/mrcall-ai-kit/)
#   opencode/  OpenCode-only — orchestrator, worker agents, migrate-from-cc
#
# Flags (any provided value skips its prompt):
#   --environment claude|opencode|both
#   --features    doc-harness,orchestration,workers,migrate   (or: all)
#   --mode        symlink|copy
#   --on-exist    skip|overwrite|backup
#   --yes         skip the final confirmation
#   --dry-run     show the plan, write nothing
#   --help
# ──────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC_DIR="$HOME/.claude"
OC_DIR="$HOME/.config/opencode"
KIT_GLOBAL="$HOME/.config/mrcall-ai-kit"   # tool-independent home for doc-check.py
MANIFEST="$KIT_GLOBAL/installed.tsv"       # append-only install log, read by ./uninstall.sh

ENVIRONMENT="" ; FEATURES="" ; MODE="" ; ON_EXIST="" ; ASSUME_YES=false ; DRY_RUN=false

list_entries() { # $1=dir → comma-joined basenames (strip .md), or (none)
  local d="$1" out="" f
  [[ -d "$d" ]] || { echo "(none)"; return; }
  for f in "$d"/*; do [[ -e "$f" ]] || continue; out+="${out:+, }$(basename "$f" .md)"; done
  echo "${out:-(none)}"
}

print_help() {
  cat <<'EOF'
mrcall-ai-kit installer — global AI-tool config for Claude Code and/or OpenCode.
Interactive by default; pass flags for non-interactive / CI use.

Usage: ./install.sh [--environment claude|opencode|both] [--features LIST|all]
                    [--mode symlink|copy] [--on-exist skip|overwrite|backup]
                    [--yes] [--dry-run] [--help]

  --features: doc-harness, orchestration, workers, migrate   (comma list, or: all)
  --mode:     symlink = edit the kit = edit your config; copy = frozen snapshot.
  --on-exist: what to do when a target file already exists.

What gets installed
───────────────────
EOF
  echo "  doc-harness    [cross-tool → Claude Code + OpenCode]"
  echo "     commands:   $(list_entries "$SCRIPT_DIR/shared/commands")"
  echo "     skills:     $(list_entries "$SCRIPT_DIR/shared/skills")"
  echo "     scripts:    doc-check.py  (-> ~/.config/mrcall-ai-kit/, the gate the commands call)"
  echo
  echo "  orchestration  [OpenCode only]"
  echo "     command:    orchestrator     agents: build, plan, reviewer, orchestrator     skill: orchestrator"
  echo
  echo "  workers        [OpenCode only]"
  local n; n=$(find "$SCRIPT_DIR/opencode/agents" -maxdepth 1 -name 'worker-*.md' 2>/dev/null | wc -l | tr -d ' ')
  local names=""; for w in "$SCRIPT_DIR"/opencode/agents/worker-*.md; do [[ -e "$w" ]] && names+="$(basename "$w" .md | sed 's/^worker-//') "; done
  echo "     agents:     $n worker models — ${names:-(none)}"
  echo
  echo "  migrate        [OpenCode only]"
  echo "     command:    migrate-check     skill: migrate-from-cc"
  echo
  echo "Destinations: Claude Code -> ~/.claude/{commands,skills}/ ;  OpenCode -> ~/.config/opencode/{commands,skills,agents}/"
  echo "Global install only. A repo's own docs/ is bootstrapped separately by /doc-create."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
    --features)    FEATURES="${2:-}";    shift 2 ;;
    --mode)        MODE="${2:-}";        shift 2 ;;
    --on-exist)    ON_EXIST="${2:-}";    shift 2 ;;
    --yes|-y)      ASSUME_YES=true;      shift ;;
    --dry-run)     DRY_RUN=true;         shift ;;
    --help|-h) print_help; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

is_tty() { [[ -t 0 && -t 1 ]]; }

# Fail loudly rather than hang when piped/CI with missing choices.
need_tty_or_flag() {
  if ! is_tty; then
    echo "Non-interactive (no TTY): provide $1 as a flag." >&2
    exit 2
  fi
}

ask_yn() { # $1=prompt $2=default(y/n)
  local ans def="$2"
  if ! is_tty; then [[ "$def" == y ]]; return; fi
  read -r -p "$1 [$( [[ $def == y ]] && echo 'Y/n' || echo 'y/N' )] " ans || true
  ans="${ans:-$def}"; [[ "$ans" =~ ^[Yy] ]]
}

ask_choice() { # $1=prompt $2=default $3..=options ; echoes the chosen value
  local prompt="$1" def="$2"; shift 2; local opts=("$@") ans
  if ! is_tty; then echo "$def"; return; fi
  read -r -p "$prompt ($(IFS=/; echo "${opts[*]}")) [$def] " ans || true
  ans="${ans:-$def}"
  local o; for o in "${opts[@]}"; do [[ "$ans" == "$o" ]] && { echo "$o"; return; }; done
  echo "$def"
}

# ── Detect environments already present ────────────────────────────────────
echo "mrcall-ai-kit installer"
echo "  kit:         $SCRIPT_DIR"
echo -n "  Claude Code: "; [[ -d "$CC_DIR" ]] && echo "found ($CC_DIR)" || echo "not found"
echo -n "  OpenCode:    "; [[ -d "$OC_DIR" ]] && echo "found ($OC_DIR)" || echo "not found"
echo

# ── Resolve environment(s) ─────────────────────────────────────────────────
WANT_CC=false ; WANT_OC=false
if [[ -n "$ENVIRONMENT" ]]; then
  case "$ENVIRONMENT" in
    claude)   WANT_CC=true ;;
    opencode) WANT_OC=true ;;
    both)     WANT_CC=true; WANT_OC=true ;;
    *) echo "--environment must be claude|opencode|both" >&2; exit 1 ;;
  esac
else
  need_tty_or_flag "--environment"
  ask_yn "Install for Claude Code?" "$([[ -d $CC_DIR ]] && echo y || echo n)" && WANT_CC=true
  ask_yn "Install for OpenCode?"    "$([[ -d $OC_DIR ]] && echo y || echo n)" && WANT_OC=true
fi
$WANT_CC || $WANT_OC || { echo "Nothing selected. Exiting." >&2; exit 1; }

# ── Resolve features (offer OC-only content only if OpenCode is selected) ───
want_feature() { [[ ",$FEATURES," == *",$1,"* || "$FEATURES" == all ]]; }
DO_DOC=false ; DO_ORCH=false ; DO_WORKERS=false ; DO_MIGRATE=false
if [[ -n "$FEATURES" ]]; then
  want_feature doc-harness  && DO_DOC=true
  want_feature orchestration && DO_ORCH=true
  want_feature workers       && DO_WORKERS=true
  want_feature migrate       && DO_MIGRATE=true
else
  need_tty_or_flag "--features"
  ask_yn "Install doc-harness (doc-create/start/end + doc-check + doc-critic)? [GLOBAL, cross-tool]" y && DO_DOC=true
  if $WANT_OC; then
    ask_yn "Install orchestration (orchestrator + build/plan/reviewer)? [OpenCode only]" n && DO_ORCH=true
    ask_yn "Install worker agents (15 models)? [OpenCode only]" n && DO_WORKERS=true
    ask_yn "Install migrate-from-cc (skill + /migrate-check)? [OpenCode only]" n && DO_MIGRATE=true
  fi
fi
# OC-only features are meaningless without OpenCode selected.
if ! $WANT_OC && { $DO_ORCH || $DO_WORKERS || $DO_MIGRATE; }; then
  echo "orchestration/workers/migrate are OpenCode-only; ignoring them (OpenCode not selected)." >&2
  DO_ORCH=false ; DO_WORKERS=false ; DO_MIGRATE=false
fi

# ── Mode + existing-file policy ────────────────────────────────────────────
[[ -n "$MODE" ]]     || { need_tty_or_flag "--mode";     MODE="$(ask_choice 'Symlink or copy? (symlink = edit kit = edit config)' symlink symlink copy)"; }
[[ -n "$ON_EXIST" ]] || { need_tty_or_flag "--on-exist"; ON_EXIST="$(ask_choice 'If a file already exists?' skip skip overwrite backup)"; }
case "$MODE" in symlink|copy) ;; *) echo "--mode must be symlink|copy" >&2; exit 1 ;; esac
case "$ON_EXIST" in skip|overwrite|backup) ;; *) echo "--on-exist must be skip|overwrite|backup" >&2; exit 1 ;; esac

# ── Build the plan: arrays of "src|dst" ────────────────────────────────────
PLAN_SRC=() ; PLAN_DST=()
add_dir() { # $1=src dir  $2=dst dir  — one entry per top-level item
  local src="$1" dst="$2" entry name
  [[ -d "$src" ]] || return 0
  for entry in "$src"/*; do
    [[ -e "$entry" ]] || continue
    name="$(basename "$entry")"
    PLAN_SRC+=("$entry"); PLAN_DST+=("$dst/$name")
  done
}
add_one() { PLAN_SRC+=("$1"); PLAN_DST+=("$2"); }

if $DO_DOC; then
  # doc-check.py → kit-global, once (the commands call it from here)
  add_one "$SCRIPT_DIR/shared/scripts/doc-check.py" "$KIT_GLOBAL/doc-check.py"
  $WANT_CC && { add_dir "$SCRIPT_DIR/shared/commands" "$CC_DIR/commands"; add_dir "$SCRIPT_DIR/shared/skills" "$CC_DIR/skills"; }
  $WANT_OC && { add_dir "$SCRIPT_DIR/shared/commands" "$OC_DIR/commands"; add_dir "$SCRIPT_DIR/shared/skills" "$OC_DIR/skills"; }
fi
if $WANT_OC; then
  if $DO_ORCH; then
    add_one "$SCRIPT_DIR/opencode/commands/orchestrator.md" "$OC_DIR/commands/orchestrator.md"
    add_one "$SCRIPT_DIR/opencode/skills/orchestrator" "$OC_DIR/skills/orchestrator"
    for a in build plan reviewer orchestrator; do
      add_one "$SCRIPT_DIR/opencode/agents/$a.md" "$OC_DIR/agents/$a.md"
    done
  fi
  if $DO_WORKERS; then
    for w in "$SCRIPT_DIR"/opencode/agents/worker-*.md; do
      [[ -e "$w" ]] && add_one "$w" "$OC_DIR/agents/$(basename "$w")"
    done
  fi
  if $DO_MIGRATE; then
    add_one "$SCRIPT_DIR/opencode/commands/migrate-check.md" "$OC_DIR/commands/migrate-check.md"
    add_one "$SCRIPT_DIR/opencode/skills/migrate-from-cc" "$OC_DIR/skills/migrate-from-cc"
  fi
fi
[[ ${#PLAN_SRC[@]} -gt 0 ]] || { echo "Nothing to install. Exiting." >&2; exit 1; }

# ── Preview ────────────────────────────────────────────────────────────────
echo "── Plan (mode: $MODE, on-exist: $ON_EXIST$($DRY_RUN && echo ', DRY-RUN' || true)) ──"
i=0
while [[ $i -lt ${#PLAN_SRC[@]} ]]; do
  printf "  %-8s %s\n" "$MODE" "${PLAN_DST[$i]}"
  i=$((i+1))
done
echo

# ── Confirm ────────────────────────────────────────────────────────────────
if ! $DRY_RUN && ! $ASSUME_YES; then
  ask_yn "Proceed?" n || { echo "Aborted."; exit 0; }
fi

# ── Execute ────────────────────────────────────────────────────────────────
record_install() { # $1=mode $2=dest $3=src $4=backup — append one manifest line
  mkdir -p "$KIT_GLOBAL"
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$1" "$2" "$3" "${4:-}" >> "$MANIFEST"
}

install_item() { # $1=src $2=dst
  local src="$1" dst="$2" bak=""
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" || -L "$dst" ]]; then
    case "$ON_EXIST" in
      skip)      echo "  skip     $dst (exists)"; return ;;
      backup)    bak="$dst.bak"; $DRY_RUN || mv "$dst" "$bak"; echo "  backup   $dst -> $bak" ;;
      overwrite) $DRY_RUN || rm -rf "$dst"; echo "  remove   $dst (overwrite)" ;;
    esac
  fi
  if $DRY_RUN; then echo "  [dry]    $MODE $dst"; return; fi
  if [[ "$MODE" == symlink ]]; then ln -s "$src" "$dst"; else cp -r "$src" "$dst"; fi
  record_install "$MODE" "$dst" "$src" "$bak"
  echo "  $MODE   $dst"
}

echo "── Installing ──"
i=0
while [[ $i -lt ${#PLAN_SRC[@]} ]]; do
  install_item "${PLAN_SRC[$i]}" "${PLAN_DST[$i]}"
  i=$((i+1))
done

# ── Summary ────────────────────────────────────────────────────────────────
echo
echo "── Done ──"
$DRY_RUN && echo "(dry-run — nothing was written)"
$WANT_CC && echo "  Claude Code: restart sessions to pick up new commands/skills."
$WANT_OC && echo "  OpenCode:    restart sessions to pick up new commands/skills/agents."
$DO_DOC  && echo "  Next: inside a repo, run /doc-create to bootstrap its docs/."
$DRY_RUN || echo "  Install log: $MANIFEST  (run ./uninstall.sh to undo exactly these)."
