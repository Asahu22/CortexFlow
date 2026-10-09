#!/bin/bash
# Scripted walkthrough used to record the README demo GIF.
#
# The agent fixes a two-bug word-frequency library end to end: it plans with
# the todo tool, reads the failing test, patches both source files with
# replace_in_file, lints, and re-runs pytest to green — every tool call shown
# as the JSON the model actually emits.
#
# Requires an Anthropic key, either as ANTHROPIC_API_KEY in the environment or
# stored via `mini-extra config set ANTHROPIC_API_KEY ...` (checked, never printed).
# Record with:
#   asciinema rec --window-size 110x30 --overwrite -c ./scripts/local/record_demo.sh demo.cast
#   agg --idle-time-limit 2 --speed 1.4 --font-size 16 demo.cast docs/demo.gif

set -uo pipefail
export TERM="${TERM:-xterm-256color}"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="$REPO_ROOT/.venv/bin:$PATH"   # mini + pytest from the project venv
export MSWEA_VISUAL_MODE_DEFAULT=false      # force the REPL UI (prints every step)
export MSWEA_CONFIGURED=true                # skip the first-run wizard

command -v mini >/dev/null || { echo "ERROR: 'mini' not found — run 'uv sync --extra dev' first"; exit 1; }

# Key must exist in the env or in the mini config store; never print either.
# MSWEA_SILENT_STARTUP keeps the import banner out of the captured path.
CONFIG_ENV="$(MSWEA_SILENT_STARTUP=true python -c 'from minisweagent import global_config_file; print(global_config_file)' 2>/dev/null | tail -1 || true)"
if [ -z "${ANTHROPIC_API_KEY:-}" ] && ! { [ -n "$CONFIG_ENV" ] && [ -f "$CONFIG_ENV" ] && grep -q '^ANTHROPIC_API_KEY=' "$CONFIG_ENV"; }; then
    echo "ERROR: no Anthropic key found (set ANTHROPIC_API_KEY or use 'mini-extra config set')"
    exit 1
fi

DEMO_MODEL="${MSWEA_DEMO_MODEL:-anthropic/claude-sonnet-4-5-20250929}"

C_HEAD='\033[1;36m'; C_PROMPT='\033[1;32m'; C_OFF='\033[0m'
say() { printf "\n${C_HEAD}# %s${C_OFF}\n" "$*"; sleep 1.2; }
run() { printf "${C_PROMPT}\$${C_OFF} %s\n" "$1"; sleep 0.6; eval "$1"; sleep 1.2; }

WORK="$(mktemp -d /tmp/agent-demo.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT
cp "$REPO_ROOT"/scripts/local/demo_task/{wordstats.py,report.py,test_report.py} "$WORK/"
cd "$WORK"

clear
printf "\n${C_HEAD}  CortexFlow — coding agent with structured tool calls${C_OFF}\n"
printf "  todo planning · read_file · replace_in_file · lint_file · pytest, end to end\n"
sleep 3

say "A tiny library with a failing test suite"
run "ls"
run "pytest -q 2>&1 | tail -12"

TASK=$(cat <<'EOF'
The pytest suite in this directory fails. First plan your work with the todo tool.
Then use the structured tools (read_file, search_dir, replace_in_file, lint_file)
rather than shell commands for inspecting and editing files; use bash only to run
pytest. Fix the bugs in the source files (do not modify test_report.py), re-run
pytest until it passes, mark your todos complete, then finish.
EOF
)

say "Hand it to the agent (yolo mode, cost-capped)"
run "mini -y --exit-immediately -l 1.50 -m \"$DEMO_MODEL\" -o \"$WORK/demo.traj.json\" -t \"\$TASK\""

say "Proof: the suite is green"
run "pytest -q 2>&1 | tail -3"

printf "\n${C_HEAD}  github.com/Asahu22/CortexFlow${C_OFF}\n"
sleep 3
