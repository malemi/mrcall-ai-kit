#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# mrcall-ai-kit installer
#
# Installs reusable AI-tool config into your GLOBAL Claude Code, Codex, and/or OpenCode
# config. Interactive by default; pass flags for non-interactive / CI use.
#
# Content is routed by tool-compatibility:
#   shared/    cross-tool  — the doc-harness (doc-* commands, doc-critic skill)
#              + doc-check.py and the managed CLAUDE.md template
#                (installed once to ~/.config/mrcall-ai-kit/)
#              + ai-help (installed with doc-harness; introspects whatever is
#                actually installed rather than a list that goes stale)
#   claude/    Claude Code-only — worker agents with pinned models, which the
#              doc-* commands delegate to (part of doc-harness, not optional);
#              plus the opt-in model router (feature: router — hook script,
#              /router command, worker-fable)
#   opencode/  OpenCode-only — orchestrator, worker agents, migrate-from-cc
#   llms.md    OpenCode-only — model metadata table the orchestrator reads at
#              startup (ships to ~/.config/opencode/ with the orchestration feature)
#
# Flags (any provided value skips its prompt):
#   --environment claude|codex|opencode|all|both
#   --features    doc-harness,orchestration,workers,migrate,router,scope-guard,shortcuts (or: all)
#   --activate-scope-guard claude|codex|opencode|all (explicit hook opt-in)
#   --mode        symlink|copy
#   --on-exist    skip|overwrite|backup
#   --yes         skip the final confirmation
#   --dry-run     show the plan, write nothing
#   --help
# ──────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC_DIR="$HOME/.claude"
OC_DIR="$HOME/.config/opencode"
CODEX_SKILLS_DIR="$HOME/.agents/skills"
KIT_GLOBAL="$HOME/.config/mrcall-ai-kit"   # tool-independent home for doc-check.py
MANIFEST="$KIT_GLOBAL/installed.tsv"       # append-only install log, read by ./uninstall.sh

ENVIRONMENT="" ; FEATURES="" ; MODE="" ; ON_EXIST="" ; ACTIVATE_SCOPE=""
ASSUME_YES=false ; DRY_RUN=false

list_entries() { # $1=dir → comma-joined basenames (strip .md), or (none)
  local d="$1" out="" f
  [[ -d "$d" ]] || { echo "(none)"; return; }
  for f in "$d"/*; do [[ -e "$f" ]] || continue; out+="${out:+, }$(basename "$f" .md)"; done
  echo "${out:-(none)}"
}

print_help() {
  cat <<'EOF'
mrcall-ai-kit installer — global AI-tool config for Claude Code, Codex, and/or OpenCode.
Interactive by default; pass flags for non-interactive / CI use.

Usage: ./install.sh [--environment claude|codex|opencode|all|both] [--features LIST|all]
                    [--mode symlink|copy] [--on-exist skip|overwrite|backup]
                    [--activate-scope-guard RUNTIMES|all]
                    [--yes] [--dry-run] [--help]

  --features: doc-harness, orchestration, workers, migrate, router, scope-guard,
              shortcuts (comma list, or: all)
  --activate-scope-guard: explicitly register scope-guard hooks/plugins for a
              comma-separated subset of claude,codex,opencode (or: all).
              --yes and --features scope-guard alone leave it dormant.
  --mode:     symlink = edit the kit = edit your config; copy = frozen snapshot.
  --on-exist: what to do when a target file already exists.

What gets installed
───────────────────
EOF
  echo "  doc-harness    [cross-tool → Claude Code + Codex + OpenCode]"
  echo "     commands:   $(list_entries "$SCRIPT_DIR/shared/commands")"
  echo "     skills:     $(list_entries "$SCRIPT_DIR/shared/skills")"
  echo "     scripts:    doc-check.py + CLAUDE.template.md  (-> ~/.config/mrcall-ai-kit/)"
  echo "     agents:     $(list_entries "$SCRIPT_DIR/claude/agents")  [Claude Code only — pinned-model"
  echo "                 workers the doc-* commands delegate to; installed with doc-harness]"
  echo
  echo "  shortcuts      [cross-tool -> Claude Code + OpenCode as typed commands; Codex differs, see below]"
  echo "     commands:   nr, av  (-> ~/.claude/commands/, ~/.config/opencode/commands/)"
  echo "     nr:         answer one question now — no tools, subagents, work trace, or review gates, for that turn"
  echo "     av:         restate the engineering-lead stance on demand"
  echo "     Codex:      nr, av install as model-invoked skills (-> ~/.agents/skills/), not typed commands —"
  echo "                 Codex has no operator-typed prompt directory; each still runs only when the"
  echo "                 operator explicitly asks for it by name, which is a weaker guarantee than a typed command"
  echo
  echo "  orchestration  [OpenCode only]"
  echo "     command:    orchestrator     agents: build, plan, reviewer, orchestrator     skill: orchestrator"
  echo "     metadata:   llms.md  (-> ~/.config/opencode/, the model table the orchestrator reads)"
  echo
  echo "  workers        [OpenCode only]"
  local n; n=$(find "$SCRIPT_DIR/opencode/agents" -maxdepth 1 -name 'worker-*.md' 2>/dev/null | wc -l | tr -d ' ')
  local names=""; for w in "$SCRIPT_DIR"/opencode/agents/worker-*.md; do [[ -e "$w" ]] && names+="$(basename "$w" .md | sed 's/^worker-//') "; done
  echo "     agents:     $n worker models — ${names:-(none)}"
  echo
  echo "  migrate        [OpenCode only]"
  echo "     command:    migrate-check     skill: migrate-from-cc"
  echo
  echo "  router         [Claude Code only]"
  echo "     command:    router  (on/off/status/sweep/unregister — opt-in, dormant until /router on)"
  echo "     agent:      worker-fable  (installed with doc-harness too, if selected)"
  echo "     script:     router-hook.py  (-> ~/.config/mrcall-ai-kit/, a dormant UserPromptSubmit hook)"
  echo
  echo "  scope-guard    [cross-tool -> every selected runtime; opt-in hook/plugin]"
  echo "     installs:   common engine, registration helper, runtime adapter, command/skill"
  echo "     activation: dormant by default; interactive prompt or --activate-scope-guard"
  echo
  echo "Destinations: Claude Code -> ~/.claude/{commands,skills,agents}/ ; Codex -> ~/.agents/skills/ ; OpenCode -> ~/.config/opencode/{commands,skills,agents}/"
  echo "Environment alias: both = Claude Code + OpenCode; all = all three tools."
  echo "Global install only. A repo's own docs/ is bootstrapped separately by invoking the doc-create workflow."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
    --features)    FEATURES="${2:-}";    shift 2 ;;
    --mode)        MODE="${2:-}";        shift 2 ;;
    --on-exist)    ON_EXIST="${2:-}";    shift 2 ;;
    --activate-scope-guard) ACTIVATE_SCOPE="${2:-}"; shift 2 ;;
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
echo -n "  Codex:       "; [[ -d "$HOME/.codex" || -d "$CODEX_SKILLS_DIR" ]] && echo "found ($CODEX_SKILLS_DIR)" || echo "not found"
echo

# ── Resolve environment(s) ─────────────────────────────────────────────────
WANT_CC=false ; WANT_CODEX=false ; WANT_OC=false
if [[ -n "$ENVIRONMENT" ]]; then
  case "$ENVIRONMENT" in
    claude)   WANT_CC=true ;;
    codex)    WANT_CODEX=true ;;
    opencode) WANT_OC=true ;;
    both)     WANT_CC=true; WANT_OC=true ;;
    all)      WANT_CC=true; WANT_CODEX=true; WANT_OC=true ;;
    *) echo "--environment must be claude|codex|opencode|all|both" >&2; exit 1 ;;
  esac
else
  need_tty_or_flag "--environment"
  ask_yn "Install for Claude Code?" "$([[ -d $CC_DIR ]] && echo y || echo n)" && WANT_CC=true
  ask_yn "Install for Codex?"       "$([[ -d $HOME/.codex || -d $CODEX_SKILLS_DIR ]] && echo y || echo n)" && WANT_CODEX=true
  ask_yn "Install for OpenCode?"    "$([[ -d $OC_DIR ]] && echo y || echo n)" && WANT_OC=true
fi
$WANT_CC || $WANT_CODEX || $WANT_OC || { echo "Nothing selected. Exiting." >&2; exit 1; }

# ── Resolve features (offer OC-only content only if OpenCode is selected) ───
want_feature() { [[ ",$FEATURES," == *",$1,"* || "$FEATURES" == all ]]; }
DO_DOC=false ; DO_ORCH=false ; DO_WORKERS=false ; DO_MIGRATE=false ; DO_ROUTER=false ; DO_SCOPE=false ; DO_SHORTCUTS=false
if [[ -n "$FEATURES" ]]; then
  want_feature doc-harness  && DO_DOC=true
  want_feature orchestration && DO_ORCH=true
  want_feature workers       && DO_WORKERS=true
  want_feature migrate       && DO_MIGRATE=true
  want_feature router       && DO_ROUTER=true
  want_feature scope-guard  && DO_SCOPE=true
  want_feature shortcuts    && DO_SHORTCUTS=true
else
  need_tty_or_flag "--features"
  ask_yn "Install doc-harness (doc-create/start/end + doc-check + doc-critic)? [GLOBAL, cross-tool]" y && DO_DOC=true
  if $WANT_OC; then
    ask_yn "Install orchestration (orchestrator + build/plan/reviewer)? [OpenCode only]" n && DO_ORCH=true
    ask_yn "Install worker agents (16 models)? [OpenCode only]" n && DO_WORKERS=true
    ask_yn "Install migrate-from-cc (skill + /migrate-check)? [OpenCode only]" n && DO_MIGRATE=true
  fi
  if $WANT_CC; then
    ask_yn "Install the opt-in model router (Haiku session as classifier + pinned workers)? [Claude Code only, dormant until /router on]" n && DO_ROUTER=true
  fi
  ask_yn "Install scope guard (dormant unless activated separately)? [GLOBAL, cross-tool]" n && DO_SCOPE=true
  ask_yn "Install shortcuts (nr, av — on-demand instruction overrides; typed commands on Claude Code/OpenCode, a model-invoked skill on Codex)? [GLOBAL, cross-tool]" n && DO_SHORTCUTS=true
fi
# OC-only features are meaningless without OpenCode selected.
if ! $WANT_OC && { $DO_ORCH || $DO_WORKERS || $DO_MIGRATE; }; then
  echo "orchestration/workers/migrate are OpenCode-only; ignoring them (OpenCode not selected)." >&2
  DO_ORCH=false ; DO_WORKERS=false ; DO_MIGRATE=false
fi
# router is Claude Code-only.
if ! $WANT_CC && $DO_ROUTER; then
  echo "router is Claude Code-only; ignoring it (Claude Code not selected)." >&2
  DO_ROUTER=false
fi

# Scope-guard activation is always a separate opt-in. `--yes` only skips the
# final installer confirmation and never enables a hook by itself.
ACTIVATE_CC=false ; ACTIVATE_CODEX=false ; ACTIVATE_OC=false
activate_requested() { [[ ",$ACTIVATE_SCOPE," == *",$1,"* || "$ACTIVATE_SCOPE" == all ]]; }
if $DO_SCOPE; then
  if [[ -n "$ACTIVATE_SCOPE" ]]; then
    IFS=',' read -r -a requested_scope_runtimes <<< "$ACTIVATE_SCOPE"
    for runtime in "${requested_scope_runtimes[@]}"; do
      case "$runtime" in claude|codex|opencode|all) ;; *) echo "--activate-scope-guard must be claude,codex,opencode or all" >&2; exit 1 ;; esac
    done
    if [[ "$ACTIVATE_SCOPE" == all ]]; then
      ACTIVATE_CC=$WANT_CC ; ACTIVATE_CODEX=$WANT_CODEX ; ACTIVATE_OC=$WANT_OC
    else
      activate_requested claude   && ACTIVATE_CC=true
      activate_requested codex    && ACTIVATE_CODEX=true
      activate_requested opencode && ACTIVATE_OC=true
    fi
  elif is_tty; then
    $WANT_CC && ask_yn "Activate scope guard for claude now (it adds a hook)?" n && ACTIVATE_CC=true
    $WANT_CODEX && ask_yn "Activate scope guard for codex now (it adds a hook)?" n && ACTIVATE_CODEX=true
    $WANT_OC && ask_yn "Activate scope guard for opencode now (it adds a hook)?" n && ACTIVATE_OC=true
  fi
else
  [[ -z "$ACTIVATE_SCOPE" ]] || { echo "--activate-scope-guard requires --features scope-guard (or all)" >&2; exit 1; }
fi
$ACTIVATE_CC && ! $WANT_CC && { echo "cannot activate scope guard for unselected runtime: claude" >&2; exit 1; }
$ACTIVATE_CODEX && ! $WANT_CODEX && { echo "cannot activate scope guard for unselected runtime: codex" >&2; exit 1; }
$ACTIVATE_OC && ! $WANT_OC && { echo "cannot activate scope guard for unselected runtime: opencode" >&2; exit 1; }
$WANT_CC || ACTIVATE_CC=false
$WANT_CODEX || ACTIVATE_CODEX=false
$WANT_OC || ACTIVATE_OC=false

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
add_one() { # $1=source item $2=destination — required sources fail before writes
  [[ -e "$1" ]] || { echo "Missing install source: $1" >&2; exit 1; }
  PLAN_SRC+=("$1"); PLAN_DST+=("$2")
}

if $DO_DOC; then
  # doc-check.py → kit-global, once (the commands call it from here)
  add_one "$SCRIPT_DIR/shared/scripts/doc-check.py" "$KIT_GLOBAL/doc-check.py"
  # One source for the harness-managed repository CLAUDE.md. doc-create and the
  # gate both read this installed artifact; project guidance lives in AGENTS.md.
  add_one "$SCRIPT_DIR/shared/templates/CLAUDE.md" "$KIT_GLOBAL/CLAUDE.template.md"
  # ai-help emits its own listing from here rather than inline in the command:
  # Claude Code delimits an injected shell block with backticks, and the script
  # needs backticks of its own to format a model column.
  add_one "$SCRIPT_DIR/shared/scripts/ai-help.sh" "$KIT_GLOBAL/ai-help.sh"
  # The doc-* commands delegate to the pinned-model workers, so those agents are
  # part of doc-harness rather than an opt-out: without them the delegation dies.
  $WANT_CC && { add_dir "$SCRIPT_DIR/shared/commands" "$CC_DIR/commands"; add_dir "$SCRIPT_DIR/shared/skills" "$CC_DIR/skills"; add_dir "$SCRIPT_DIR/claude/agents" "$CC_DIR/agents"; }
  if $WANT_CODEX; then
    for command in doc-create doc-start doc-end; do
      # Codex discovers a symlinked skill directory, but not a real directory
      # containing symlinked SKILL.md/WORKFLOW.md files. Install atomically.
      add_one "$SCRIPT_DIR/codex/skills/$command" "$CODEX_SKILLS_DIR/$command"
    done
    add_one "$SCRIPT_DIR/shared/skills/doc-critic" "$CODEX_SKILLS_DIR/doc-critic"
  fi
  $WANT_OC && { add_dir "$SCRIPT_DIR/shared/commands" "$OC_DIR/commands"; add_dir "$SCRIPT_DIR/shared/skills" "$OC_DIR/skills"; }
fi
if $DO_ROUTER; then
  # Claude Code-only (gated above); dormant until `/router on` creates the flag.
  add_one "$SCRIPT_DIR/claude/scripts/router-hook.py" "$KIT_GLOBAL/router-hook.py"
  add_dir "$SCRIPT_DIR/claude/commands" "$CC_DIR/commands"
  # worker-fable rides with doc-harness's claude/agents sweep when both are
  # selected; add it alone only when doc-harness was skipped.
  $DO_DOC || add_one "$SCRIPT_DIR/claude/agents/worker-fable.md" "$CC_DIR/agents/worker-fable.md"
fi
if $DO_SCOPE; then
  add_one "$SCRIPT_DIR/shared/scripts/scope_guard.py" "$KIT_GLOBAL/scope-guard/scope_guard.py"
  add_one "$SCRIPT_DIR/shared/scripts/scope_guard_register.py" "$KIT_GLOBAL/scope-guard/scope_guard_register.py"
  if $WANT_CC; then
    add_one "$SCRIPT_DIR/claude/scripts/scope-guard-hook.py" "$KIT_GLOBAL/scope-guard/claude/scope-guard.py"
    add_one "$SCRIPT_DIR/claude/commands/scope-guard.md" "$CC_DIR/commands/scope-guard.md"
  fi
  if $WANT_CODEX; then
    add_one "$SCRIPT_DIR/codex/scripts/scope-guard-hook.py" "$KIT_GLOBAL/scope-guard/codex/scope-guard.py"
    add_one "$SCRIPT_DIR/codex/skills/scope-guard" "$CODEX_SKILLS_DIR/scope-guard"
  fi
  if $WANT_OC; then
    add_one "$SCRIPT_DIR/opencode/plugins/scope-guard.ts" "$KIT_GLOBAL/scope-guard/opencode/scope-guard.ts"
    add_one "$SCRIPT_DIR/opencode/commands/scope-guard.md" "$OC_DIR/commands/scope-guard.md"
  fi
fi
if $WANT_OC; then
  if $DO_ORCH; then
    add_one "$SCRIPT_DIR/opencode/commands/orchestrator.md" "$OC_DIR/commands/orchestrator.md"
    add_one "$SCRIPT_DIR/opencode/skills/orchestrator" "$OC_DIR/skills/orchestrator"
    # The orchestrator agent and skill both read ~/.config/opencode/llms.md at
    # startup and at every worker pick, so the model metadata ships with them.
    add_one "$SCRIPT_DIR/llms.md" "$OC_DIR/llms.md"
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
if $DO_SHORTCUTS; then
  # On-demand instruction overrides (nr, av). Sources live in shared/shortcuts/,
  # kept out of the shared/commands/ sweep above (doc-harness, :283,292) so this
  # explicit add can never collide with it under --on-exist backup.
  if $WANT_CC; then
    add_one "$SCRIPT_DIR/shared/shortcuts/nr.md" "$CC_DIR/commands/nr.md"
    add_one "$SCRIPT_DIR/shared/shortcuts/av.md" "$CC_DIR/commands/av.md"
  fi
  if $WANT_OC; then
    add_one "$SCRIPT_DIR/shared/shortcuts/nr.md" "$OC_DIR/commands/nr.md"
    add_one "$SCRIPT_DIR/shared/shortcuts/av.md" "$OC_DIR/commands/av.md"
  fi
  if $WANT_CODEX; then
    # Codex discovers a symlinked skill directory, but not a real directory
    # containing symlinked SKILL.md files. Install atomically, same as
    # doc-harness's Codex skills above.
    add_one "$SCRIPT_DIR/codex/skills/nr" "$CODEX_SKILLS_DIR/nr"
    add_one "$SCRIPT_DIR/codex/skills/av" "$CODEX_SKILLS_DIR/av"
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
$ACTIVATE_CC && printf "  %-8s %s\n" "activate" "Claude scope guard -> $CC_DIR/settings.json"
$ACTIVATE_CODEX && printf "  %-8s %s\n" "activate" "Codex scope guard -> $HOME/.codex/hooks.json"
$ACTIVATE_OC && printf "  %-8s %s\n" "activate" "OpenCode scope guard -> $OC_DIR/plugins/mrcall-scope-guard.ts"
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
  if [[ -e "$dst" || -L "$dst" ]]; then
    case "$ON_EXIST" in
      skip)      echo "  skip     $dst (exists)"; return ;;
      backup)    bak="$dst.bak"; $DRY_RUN || mv "$dst" "$bak"; echo "  backup   $dst -> $bak" ;;
      overwrite) $DRY_RUN || rm -rf "$dst"; echo "  remove   $dst (overwrite)" ;;
    esac
  fi
  if $DRY_RUN; then echo "  [dry]    $MODE $dst"; return; fi
  mkdir -p "$(dirname "$dst")"
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

if $DO_SCOPE; then
  register_scope_guard() { # $1=runtime $2=registry path
    local runtime="$1" registry="$2"
    if $DRY_RUN; then
      echo "  [dry]    register scope guard for $runtime in $registry"
    else
      python3 "$KIT_GLOBAL/scope-guard/scope_guard_register.py" "$runtime" on
    fi
  }
  $ACTIVATE_CC && register_scope_guard claude "$CC_DIR/settings.json"
  $ACTIVATE_CODEX && register_scope_guard codex "$HOME/.codex/hooks.json"
  $ACTIVATE_OC && register_scope_guard opencode "$OC_DIR/plugins/mrcall-scope-guard.ts"
fi

# ── Summary ────────────────────────────────────────────────────────────────
echo
echo "── Done ──"
$DRY_RUN && echo "(dry-run — nothing was written)"
$WANT_CC && echo "  Claude Code: restart sessions to pick up new commands/skills/agents."
$WANT_CODEX && echo "  Codex:       restart sessions to discover skills under ~/.agents/skills."
$WANT_OC && echo "  OpenCode:    restart sessions to pick up new commands/skills/agents."
$DO_DOC  && echo "  Next: inside a repo, invoke the doc-create workflow to bootstrap its docs/."
$DO_ROUTER && echo "  Router installed but dormant: run /router on to activate (then restart and switch to Haiku)."
if $DO_SCOPE; then
  if $WANT_CC && ! $ACTIVATE_CC; then echo "  Claude scope guard installed but dormant: run /scope-guard on to activate."; fi
  if $WANT_CODEX && ! $ACTIVATE_CODEX; then echo "  Codex scope guard installed but dormant: invoke the scope-guard skill to activate."; fi
  if $WANT_OC && ! $ACTIVATE_OC; then echo "  OpenCode scope guard installed but dormant: run /scope-guard on to activate."; fi
fi
$DO_SHORTCUTS && echo "  Shortcuts installed: /nr and /av on Claude Code/OpenCode; on Codex, ask for the nr or av skill by name."
$DRY_RUN || echo "  Install log: $MANIFEST  (run ./uninstall.sh to undo exactly these)."
