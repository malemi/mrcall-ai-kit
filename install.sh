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
#              + ai-help / ai-tutorial (installed with doc-harness; introspect whatever is
#                actually installed rather than a list that goes stale)
#   claude/    Claude Code-only — the role agents (execute, verify, reviewer)
#              the doc-* commands delegate to (part of doc-harness, not
#              optional); plus the opt-in model router (feature: router — hook
#              script, /router command)
#   opencode/  OpenCode-only — orchestrator and its leads, the role agents,
#              migrate-from-cc
#
# Flags (any provided value skips its prompt):
#   --environment claude|codex|opencode|all|both
#   --features    doc-harness,orchestration,workers,migrate,router,reread,scope-guard,shortcuts (or: all)
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
BACKUPS="$KIT_GLOBAL/backups"              # --on-exist backup of a directory, outside every scan path
RETIRED_LIST="$SCRIPT_DIR/shared/roles/retired.txt"  # files the kit shipped under names it has retired
CC_ROLES="execute verify reviewer"          # Claude Code role agents (claude/agents/<budget>/)
OC_ROLES="execute verify"                   # OpenCode role agents the leads delegate to
BUDGETS="low medium high"                   # one rendering of every agent per budget
BUDGET_FILE="$KIT_GLOBAL/budget"            # this machine's budget; medium when absent
AGENT_HOME="$KIT_GLOBAL/agents"             # every budget's rendering, installed: <runtime>/<budget>/<name>.md

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

  --environment: which AI tools to install for. claude, codex, opencode, or a
              shorthand: both = Claude Code + OpenCode, all = all three. A
              runtime you do not have installed is harmless — the files land in
              its config directory and nothing reads them until it exists.
              Features that only make sense elsewhere are skipped with a note.
  --features: doc-harness, orchestration, workers, migrate, router, reread, scope-guard,
              shortcuts (comma list, or: all). Each is described below.
  --activate-scope-guard: explicitly register scope-guard hooks/plugins for a
              comma-separated subset of claude,codex,opencode (or: all).
              --yes and --features scope-guard alone leave it dormant.
  --mode:     symlink = the installed file points at this checkout, so editing
              the kit edits your live config — and moving or deleting the
              checkout breaks it. copy = a frozen snapshot, unaffected by the
              checkout afterwards; re-run the installer to pick up changes.
  --on-exist: what to do when a target file already exists.
              skip      = leave the existing file alone and install nothing
                          over it. Updating an existing install does nothing.
              overwrite = replace it. This is what you want when updating.
              backup    = move it aside, then install. A file moves to
                          <file>.bak. A directory, such as a skill, moves to
                          ~/.config/mrcall-ai-kit/backups/<its path under ~>,
                          where no runtime loads it. Only one generation is
                          kept: a second run replaces the backup.
              The same choice applies to the files the kit once installed
              under names it has retired (shared/roles/retired.txt), in a run
              that installs the role agents replacing them: doc-harness or
              router for Claude Code, workers for OpenCode. overwrite deletes
              them, backup moves them aside, and skip leaves them and lists
              them. A run that installs other things for that runtime only
              lists them. A file there is the kit's when it is what the
              install log records the kit putting there, or when its bytes
              match a version this checkout's git history shipped at that
              path. Anything else stays, and the installer lists it.
  --yes:      skip the final confirmation prompt. It never enables a hook or
              chooses a feature for you — everything else must still be a flag.
  --dry-run:  print exactly what would be written, and write nothing.
  --help:     this text.

What gets installed
───────────────────
EOF
  echo "  doc-harness    [cross-tool → Claude Code + Codex + OpenCode]"
  echo "     commands:   $(list_entries "$SCRIPT_DIR/shared/commands")"
  echo "     skills:     $(list_entries "$SCRIPT_DIR/shared/skills")"
  echo "     scripts:    doc-check.py + CLAUDE.template.md, and the scripts of ai-help, ai-tutorial and"
  echo "                 ai-budget  (-> ~/.config/mrcall-ai-kit/)"
  echo "     agents:     $(list_entries "$SCRIPT_DIR/claude/agents/medium")  [Claude Code only — the role"
  echo "                 agents the doc-* commands delegate to; installed with doc-harness]"
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
  echo
  echo "  workers        [OpenCode only]"
  echo "     agents:     $OC_ROLES  (the roles the leads delegate to)"
  echo
  echo "  migrate        [OpenCode only]"
  echo "     command:    migrate-check     skill: migrate-from-cc"
  echo
  echo "  router         [Claude Code only]"
  echo "     command:    router  (on/off/status/sweep/unregister — opt-in, dormant until /router on)"
  echo "     agents:     $CC_ROLES + the kit-role-rules skill  (installed with doc-harness too, if selected)"
  echo "     script:     router-hook.py  (-> ~/.config/mrcall-ai-kit/, a dormant UserPromptSubmit hook)"
  echo
  echo "  reread         [cross-tool; guarantee differs by runtime]
     Claude Code: /sc <question> uses a Stop hook before delivery; /sc on/off
                 controls every answer. Answers under SC_MIN_CHARS (500 by default)
                 skip the pass.
     OpenCode:   /sc <question> instructs one in-turn pass, even on short answers.
     Codex:      \$sc <question> is a model-invoked skill for the same in-turn pass.
     checklist:  reread-checklist.md  (-> ~/.config/mrcall-ai-kit/, edit to taste)
     limit:      OpenCode and Codex have no enforced pre-delivery interception
                 or always-on mode. Their pass depends on the model following
                 the instruction.

  scope-guard    [cross-tool -> every selected runtime; opt-in hook/plugin]"
  echo "     installs:   common engine, registration helper, runtime adapter, command/skill"
  echo "     activation: dormant by default; interactive prompt or --activate-scope-guard"
  echo
  echo "Destinations: Claude Code -> ~/.claude/{commands,skills,agents}/ ; Codex -> ~/.agents/skills/ ; OpenCode -> ~/.config/opencode/{commands,skills,agents}/"
  echo "Agents: every kit agent is rendered once per budget (low, medium, high), each with the"
  echo "        models the kit resolved for it. All three renderings go to ~/.config/mrcall-ai-kit/agents/;"
  echo "        the runtime gets the one for this machine's budget, read from ~/.config/mrcall-ai-kit/budget"
  echo "        (medium when that file is absent). /ai-budget low|medium|high, installed with doc-harness,"
  echo "        switches them without the checkout."
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
DO_DOC=false ; DO_ORCH=false ; DO_WORKERS=false ; DO_MIGRATE=false ; DO_ROUTER=false ; DO_SCOPE=false ; DO_SHORTCUTS=false ; DO_REREAD=false
if [[ -n "$FEATURES" ]]; then
  want_feature doc-harness  && DO_DOC=true
  want_feature orchestration && DO_ORCH=true
  want_feature workers       && DO_WORKERS=true
  want_feature migrate       && DO_MIGRATE=true
  want_feature router       && DO_ROUTER=true
  want_feature scope-guard  && DO_SCOPE=true
  want_feature shortcuts    && DO_SHORTCUTS=true
  want_feature reread       && DO_REREAD=true
else
  need_tty_or_flag "--features"
  ask_yn "Install doc-harness (doc-create/start/end + doc-check + doc-critic)? [GLOBAL, cross-tool]" y && DO_DOC=true
  if $WANT_OC; then
    ask_yn "Install orchestration (orchestrator + build/plan/reviewer)? [OpenCode only]" n && DO_ORCH=true
    ask_yn "Install the role agents ($OC_ROLES)? [OpenCode only]" n && DO_WORKERS=true
    ask_yn "Install migrate-from-cc (skill + /migrate-check)? [OpenCode only]" n && DO_MIGRATE=true
  fi
  if $WANT_CC; then
    ask_yn "Install the opt-in model router (Haiku session as classifier + the role agents)? [Claude Code only, dormant until /router on]" n && DO_ROUTER=true
  fi
  ask_yn "Install the re-read pass (Claude Stop hook; OpenCode /sc; Codex \$sc skill)? [GLOBAL, cross-tool]" n && DO_REREAD=true
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

# ── Budget: which rendering of each agent the runtimes read ────────────────
# Checked where an agent is planned, so a run that places no agent does not
# depend on it.
BUDGET=medium ; BUDGET_FROM="the default, $BUDGET_FILE is absent"
if [[ -f "$BUDGET_FILE" ]]; then
  BUDGET="$(tr -d '[:space:]' < "$BUDGET_FILE")" ; BUDGET_FROM="$BUDGET_FILE"
fi

# ── Build the plan: arrays of "src|dst" ────────────────────────────────────
PLAN_SRC=() ; PLAN_DST=() ; AGENTS_PLANNED=false
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
add_agent() { # $1=runtime (claude|opencode) $2=agent name $3=the runtime's agents directory
  # The runtime reads the rendering for this machine's budget. Every budget's
  # rendering goes beside the kit, where a budget switch finds it without the
  # checkout.
  local b
  [[ " $BUDGETS " == *" $BUDGET "* ]] \
    || { echo "$BUDGET_FILE says '$BUDGET'; a budget is one of: $BUDGETS" >&2; exit 1; }
  add_one "$SCRIPT_DIR/$1/agents/$BUDGET/$2.md" "$3/$2.md"
  for b in $BUDGETS; do add_one "$SCRIPT_DIR/$1/agents/$b/$2.md" "$AGENT_HOME/$1/$b/$2.md"; done
  AGENTS_PLANNED=true
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
  # ai-tutorial does the same, and its prose ships beside it: the script prints
  # only the sections whose capability is installed, so the source has to travel
  # with it rather than be read out of a checkout that may not be there.
  add_one "$SCRIPT_DIR/shared/scripts/ai-tutorial.sh" "$KIT_GLOBAL/ai-tutorial.sh"
  add_one "$SCRIPT_DIR/shared/tutorial.md" "$KIT_GLOBAL/tutorial.md"
  # /ai-budget switches the installed agents between the renderings installed
  # beside the kit, so it needs neither the checkout nor a network.
  add_one "$SCRIPT_DIR/shared/scripts/ai-budget.py" "$KIT_GLOBAL/ai-budget.py"
  # The doc-* commands delegate to the role agents, so those agents are part of
  # doc-harness rather than an opt-out: without them the delegation dies.
  if $WANT_CC; then
    add_dir "$SCRIPT_DIR/shared/commands" "$CC_DIR/commands"; add_dir "$SCRIPT_DIR/shared/skills" "$CC_DIR/skills"
    for agent in "$SCRIPT_DIR/claude/agents/$BUDGET"/*.md; do add_agent claude "$(basename "$agent" .md)" "$CC_DIR/agents"; done
  fi
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
  # Only the router's own command. claude/commands also holds the commands of
  # the reread and scope-guard features, and each of those is installed by its
  # own feature: /sc registers a hook script only `--features reread` ships.
  add_one "$SCRIPT_DIR/claude/commands/router.md" "$CC_DIR/commands/router.md"
  # The role agents the router delegates to ride with doc-harness's
  # claude/agents/<budget> sweep when both are selected; add them alone only when
  # doc-harness was skipped. Their rules arrive through the preloaded
  # kit-role-rules skill, so that ships with them — without doc-harness nothing
  # else installs shared/skills.
  if ! $DO_DOC; then
    for r in $CC_ROLES; do add_agent claude "$r" "$CC_DIR/agents"; done
    add_one "$SCRIPT_DIR/shared/skills/kit-role-rules" "$CC_DIR/skills/kit-role-rules"
  fi
fi
if $DO_REREAD; then
  # Shared checklist and in-turn procedure belong to this feature, not to the
  # doc-harness directory sweep. Add each shared destination exactly once.
  add_one "$SCRIPT_DIR/shared/roles/reread-checklist.md" "$KIT_GLOBAL/reread-checklist.md"
  if $WANT_OC || $WANT_CODEX; then
    add_one "$SCRIPT_DIR/shared/shortcuts/sc-core.md" "$KIT_GLOBAL/sc-core.md"
  fi
  if $WANT_CC; then
    add_one "$SCRIPT_DIR/claude/scripts/reread-hook.py" "$KIT_GLOBAL/reread-hook.py"
    add_one "$SCRIPT_DIR/claude/commands/sc.md" "$CC_DIR/commands/sc.md"
  fi
  $WANT_OC && add_one "$SCRIPT_DIR/opencode/commands/sc.md" "$OC_DIR/commands/sc.md"
  $WANT_CODEX && add_one "$SCRIPT_DIR/codex/skills/sc" "$CODEX_SKILLS_DIR/sc"
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
    for a in build plan reviewer orchestrator; do add_agent opencode "$a" "$OC_DIR/agents"; done
  fi
  if $DO_WORKERS; then
    for r in $OC_ROLES; do add_agent opencode "$r" "$OC_DIR/agents"; done
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

# ── Retired names: find the kit's files under them ─────────────────────────
# retired.txt holds one file per line: the repository path, a tab, and the
# destination under $HOME. A file found at a destination is the kit's when the
# install log's last line for it is an install that still stands, or when its
# bytes equal a version the kit shipped at that repository path, which this
# checkout's history answers. The second test covers what was installed before
# the log existed. Anything else stays and is listed. A runtime this run does
# not install for is not looked at.
[[ -f "$RETIRED_LIST" ]] || { echo "Missing install source: $RETIRED_LIST" >&2; exit 1; }

recorded_by_kit() { # $1=destination → the log's last line for it is an install that still stands
  [[ -f "$MANIFEST" ]] || return 1
  local line mode src
  line="$(D="$1" awk -F'\t' '$3 == ENVIRON["D"] { m = $2; s = $4 } END { if (m != "") print m "\t" s }' "$MANIFEST")"
  [[ -n "$line" ]] || return 1
  mode="${line%%$'\t'*}" ; src="${line#*$'\t'}"
  case "$mode" in
    symlink) [[ -L "$1" && "$(readlink "$1")" == "$src" ]] ;;
    copy)    [[ -e "$1" && ! -L "$1" ]] ;;
    *)       return 1 ;;   # retired: the kit has put nothing there since
  esac
}

HISTORY=true ; HISTORY_NOTE=""
if [[ "$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" != "$(cd "$SCRIPT_DIR" && pwd -P)" ]]; then
  HISTORY=false
  HISTORY_NOTE="this kit is not a git checkout, so only the install log can show that a file is the kit's"
elif [[ "$(git -C "$SCRIPT_DIR" rev-parse --is-shallow-repository)" == true ]]; then
  HISTORY_NOTE="this checkout is a shallow clone, so a version older than its history is not recognised"
fi

shipped_in() { # $1=file $2=repository path → prints the newest commit holding these bytes there
  $HISTORY && [[ -f "$1" ]] || return 1   # a dangling link has no bytes to compare
  local blob commit
  blob="$(git -C "$SCRIPT_DIR" hash-object --stdin < "$1")" || return 1
  # --find-object also lists the commit that replaced the blob, so each hit is
  # checked for the blob actually being at that path.
  for commit in $(git -C "$SCRIPT_DIR" log --all --format=%h --find-object="$blob" -- "$2"); do
    if [[ "$(git -C "$SCRIPT_DIR" rev-parse -q --verify "$commit:$2" 2>/dev/null)" == "$blob" ]]; then
      echo "$commit" ; return 0
    fi
  done
  return 1
}

selected_for() { # $1=destination → this run installs for the runtime it belongs to
  case "$1" in
    "$CC_DIR"/*)           $WANT_CC ;;
    "$OC_DIR"/*)           $WANT_OC ;;
    "$CODEX_SKILLS_DIR"/*) $WANT_CODEX ;;
    *)                     true ;;
  esac
}

# A runtime's retired files go in a run that installs the role agents replacing
# them, so no run removes an old agent without putting its successor in place.
# A run that installs other things for that runtime lists them and leaves them.
installs_roles_for() { # $1=destination → this run installs role agents for its runtime
  local dir roles r i
  case "$1" in
    "$CC_DIR"/*) dir="$CC_DIR/agents" ; roles="$CC_ROLES" ;;
    "$OC_DIR"/*) dir="$OC_DIR/agents" ; roles="$OC_ROLES" ;;
    *)           return 0 ;;   # no role agents replace it
  esac
  i=0
  while [[ $i -lt ${#PLAN_DST[@]} ]]; do
    for r in $roles; do [[ "${PLAN_DST[$i]}" == "$dir/$r.md" ]] && return 0; done
    i=$((i+1))
  done
  return 1
}

backup_path() { # $1=destination → where --on-exist backup moves it
  # A directory, or a link to one, leaves the runtimes' scan paths: OpenCode
  # loads skills/<name>.bak/SKILL.md as the skill <name>, and with the new skill
  # beside it keeps one of the two at random.
  if [[ -d "$1" ]]; then echo "$BACKUPS/${1#"$HOME"/}"; else echo "$1.bak"; fi
}

RET_DST=() ; RET_SRC=() ; RET_WHY=() ; WAIT_DST=() ; WAIT_WHY=() ; KEEP_DST=()
while IFS=$'\t' read -r r_src r_rel || [[ -n "${r_src:-}" ]]; do
  [[ -z "$r_src" || "$r_src" == \#* ]] && continue
  r_dst="$HOME/$r_rel"
  { [[ -e "$r_dst" || -L "$r_dst" ]] && selected_for "$r_dst"; } || continue
  if recorded_by_kit "$r_dst"; then
    r_why="recorded in the install log"
  elif r_commit="$(shipped_in "$r_dst" "$r_src")"; then
    r_why="shipped in $r_commit"
  else
    KEEP_DST+=("$r_dst") ; continue
  fi
  if installs_roles_for "$r_dst"; then
    RET_DST+=("$r_dst") ; RET_SRC+=("$SCRIPT_DIR/$r_src") ; RET_WHY+=("$r_why")
  else
    WAIT_DST+=("$r_dst") ; WAIT_WHY+=("$r_why")
  fi
done < "$RETIRED_LIST"

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
if [[ ${#RET_DST[@]} -gt 0 || ${#WAIT_DST[@]} -gt 0 || ${#KEEP_DST[@]} -gt 0 ]]; then
  echo "── Retired names: files the kit once installed under a name it no longer ships ──"
  i=0
  while [[ $i -lt ${#RET_DST[@]} ]]; do
    case "$ON_EXIST" in
      overwrite) printf "  %-8s %s  (%s)\n" "remove" "${RET_DST[$i]}" "${RET_WHY[$i]}" ;;
      backup)    printf "  %-8s %s -> %s  (%s)\n" "backup" "${RET_DST[$i]}" "$(backup_path "${RET_DST[$i]}")" "${RET_WHY[$i]}" ;;
      skip)      printf "  %-8s %s  (%s)\n" "found" "${RET_DST[$i]}" "${RET_WHY[$i]}" ;;
    esac
    i=$((i+1))
  done
  i=0
  while [[ $i -lt ${#WAIT_DST[@]} ]]; do
    printf "  %-8s %s  (%s)\n" "found" "${WAIT_DST[$i]}" "${WAIT_WHY[$i]}"
    i=$((i+1))
  done
  i=0
  while [[ $i -lt ${#KEEP_DST[@]} ]]; do
    printf "  %-8s %s  (%s)\n" "keep" "${KEEP_DST[$i]}" "not the kit's: no install record, and no version the kit shipped matches"
    i=$((i+1))
  done
  [[ -z "$HISTORY_NOTE" ]] || echo "  note:    $HISTORY_NOTE."
  if [[ "$ON_EXIST" == skip && ${#RET_DST[@]} -gt 0 ]]; then
    echo "  --on-exist skip retires nothing: overwrite or backup completes the migration."
  fi
  if [[ ${#WAIT_DST[@]} -gt 0 ]]; then
    echo "  A runtime's retired files go only in a run that installs its role agents. Reinstall"
    echo "  what calls them in that same run: for Claude Code doc-harness, with router if"
    echo "  installed; for OpenCode workers, with orchestration if its leads are installed."
  fi
  echo
fi

# ── Confirm ────────────────────────────────────────────────────────────────
if ! $DRY_RUN && ! $ASSUME_YES; then
  ask_yn "Proceed?" n || { echo "Aborted."; exit 0; }
fi

# ── Execute ────────────────────────────────────────────────────────────────
record_install() { # $1=mode $2=dest $3=src $4=backup — append one manifest line
  mkdir -p "$KIT_GLOBAL"
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$1" "$2" "$3" "${4:-}" >> "$MANIFEST"
}

move_aside() { # $1=path $2=its backup — one generation: an older backup is replaced
  rm -rf "$2"
  mkdir -p "$(dirname "$2")"
  mv "$1" "$2"
}

install_item() { # $1=src $2=dst
  local src="$1" dst="$2" bak=""
  if [[ -e "$dst" || -L "$dst" ]]; then
    case "$ON_EXIST" in
      skip)      echo "  skip     $dst (exists)"; return ;;
      backup)    bak="$(backup_path "$dst")"; $DRY_RUN || move_aside "$dst" "$bak"; echo "  backup   $dst -> $bak" ;;
      overwrite) $DRY_RUN || rm -rf "$dst"; echo "  remove   $dst (overwrite)" ;;
    esac
  fi
  if $DRY_RUN; then echo "  [dry]    $MODE $dst"; return; fi
  mkdir -p "$(dirname "$dst")"
  if [[ "$MODE" == symlink ]]; then ln -s "$src" "$dst"; else cp -r "$src" "$dst"; fi
  record_install "$MODE" "$dst" "$src" "$bak"
  echo "  $MODE   $dst"
}

retire_item() { # $1=destination $2=the source the kit shipped it from — under skip, never called
  local dst="$1" bak=""
  case "$ON_EXIST" in
    backup)    bak="$(backup_path "$dst")"; $DRY_RUN || move_aside "$dst" "$bak"; echo "  backup   $dst -> $bak (retired)" ;;
    overwrite) $DRY_RUN || rm -rf "$dst"; echo "  remove   $dst (retired)" ;;
  esac
  # The log's last line for the path now says the kit put nothing there: a file
  # made there later is not taken for the kit's, and --restore-backups can put
  # this one back.
  $DRY_RUN || record_install retired "$dst" "$2" "$bak"
}

echo "── Installing ──"
i=0
while [[ $i -lt ${#PLAN_SRC[@]} ]]; do
  install_item "${PLAN_SRC[$i]}" "${PLAN_DST[$i]}"
  i=$((i+1))
done

# After the installs, so a failed install never leaves a runtime with neither
# the old files nor the new ones.
if [[ "$ON_EXIST" != skip && ${#RET_DST[@]} -gt 0 ]]; then
  echo "── Retiring ──"
  i=0
  while [[ $i -lt ${#RET_DST[@]} ]]; do
    retire_item "${RET_DST[$i]}" "${RET_SRC[$i]}"
    i=$((i+1))
  done
fi

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
still=${#WAIT_DST[@]} ; [[ "$ON_EXIST" != skip ]] || still=$((still + ${#RET_DST[@]}))
if [[ $still -gt 0 ]]; then
  echo "  Retired names: $still file(s) the kit once installed are still in place, listed above with what completes the migration."
fi
$WANT_CC && echo "  Claude Code: restart sessions to pick up new commands/skills/agents."
$WANT_CODEX && echo "  Codex:       restart sessions to discover skills under ~/.agents/skills."
$WANT_OC && echo "  OpenCode:    restart sessions to pick up new commands/skills/agents."
$AGENTS_PLANNED && echo "  Agents: the runtimes read the $BUDGET budget's renderings ($BUDGET_FROM)."
$DO_DOC  && echo "  Next: inside a repo, invoke the doc-create workflow to bootstrap its docs/."
$DO_ROUTER && echo "  Router installed but dormant: run /router on to activate (then restart and switch to Haiku)."
if $DO_REREAD; then
  $WANT_CC && echo "  Claude re-read guard installed but dormant: use /sc <question> or /sc on."
  $WANT_OC && echo "  OpenCode re-read pass installed: use /sc <question> (instruction-based)."
  $WANT_CODEX && echo "  Codex re-read pass installed: ask for the \$sc skill with a question (instruction-based)."
fi
if $DO_SCOPE; then
  if $WANT_CC && ! $ACTIVATE_CC; then echo "  Claude scope guard installed but dormant: run /scope-guard on to activate."; fi
  if $WANT_CODEX && ! $ACTIVATE_CODEX; then echo "  Codex scope guard installed but dormant: invoke the scope-guard skill to activate."; fi
  if $WANT_OC && ! $ACTIVATE_OC; then echo "  OpenCode scope guard installed but dormant: run /scope-guard on to activate."; fi
fi
$DO_SHORTCUTS && echo "  Shortcuts installed: /nr and /av on Claude Code/OpenCode; on Codex, ask for the nr or av skill by name."
$DRY_RUN || echo "  Install log: $MANIFEST  (run ./uninstall.sh to undo exactly these)."
