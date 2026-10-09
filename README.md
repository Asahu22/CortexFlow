# CortexFlow — AI Coding Agent with Structured Tools and Memory

[![CI](https://github.com/Asahu22/CortexFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/Asahu22/CortexFlow/actions/workflows/ci.yml)

A compact Python coding agent that loops **model → action → observation** until the task is done. It extends the upstream bash-only agent loop with a registry of 15 structured tools (file reads/edits, search, lint, todo planning), optional memory (history compression, session persistence, trajectory replay), execution environments from local shell to Docker and Singularity, and a SWE-bench batch runner — plus a deterministic offline model that makes the whole loop testable without API keys.

Maintained by Aman Sahu. Based on [Sean Kraemer's adaptation](https://github.com/SeanKraemer/ai-agent) (originally a UIUC CS 427 course project), built on [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) (MIT) — see [ATTRIBUTION.md](ATTRIBUTION.md).

![Demo: the agent plans with todo, fixes two bugs via replace_in_file, lints, and turns pytest green](docs/demo.gif)

*One take, no cuts: given a failing test suite, the agent plans with the `todo` tool, reads the code with `read_file`/`read_many_files`, patches two bugs with `replace_in_file`, checks syntax with `lint_file`, and re-runs pytest to green — every tool call shown as the JSON the model actually emits, with per-step cost tracking. Total spend: $0.08.*

## Architecture

```
            ┌─────────────────────────────┐
            │            Model            │  litellm (any provider) · Anthropic
            │   (completion + cost/step)  │  multi-key · OpenRouter · Deterministic
            └──────────────┬──────────────┘
                           │  THOUGHT + exactly one ```bash``` or ```tool``` block
                           ▼
            ┌─────────────────────────────┐
            │     Agent (parse_action)    │
            └───────┬─────────────┬───────┘
        bash block  │             │  {"name": ..., "args": ...}
                    ▼             ▼
        ┌───────────────┐   ┌───────────────────┐
        │  Environment  │   │   Tool registry   │  read_file · replace_in_file
        │ local/docker/ │   │ (15 typed tools)  │  edit_block · lint_file · todo …
        │  singularity  │   └─────────┬─────────┘
        └───────┬───────┘             │
                └──────────┬──────────┘
                           ▼  observation {output, returncode}
            ┌─────────────────────────────┐
            │ message history (+ optional │
            │ compression / session save) │ ──▶ back to Model
            └─────────────────────────────┘
```

The control flow is deliberately simple: each step the model must emit exactly one action — a bash block or a JSON tool block — and gets back a single observation. Termination, cost limits, and submission are handled with typed exceptions rather than flags threaded through the loop.

## Core Subsystems

- **Tool registry** (`src/minisweagent/tools/`) — 15 dataclass-based tools with JSON-schema parameters: `read_file`, `write_file`, `search_file`, `list_files`, `read_many_files`, `append_to_file`, `replace_in_file`, `insert_lines`, `create_directory`, `todo`, `cleanup_before_submit`, `edit_block`, `lint_file`, `search_dir`, `validation_script`. Edit tools enforce safety guards (`replace_in_file` requires a unique exact match; `edit_block`/`insert_lines` bounds-check). Each tool has dual execution paths: direct host-filesystem access locally, or a base64-piped script when the agent runs inside a container.
- **Agents** (`src/minisweagent/agents/`) — the core loop parses one bash/tool action per response; interactive modes (`human`, `confirm`, `yolo`) gate execution with action whitelists; a Textual-based pager UI (`mini -v`) is available alongside the REPL.
- **Memory** (`src/minisweagent/memory/`) — opt-in via `mini --memory`: history compression keeps the system prompt plus the most recent N messages, sessions persist to JSON and reload across runs, and saved trajectories can be replayed deterministically.
- **Models** (`src/minisweagent/models/`) — litellm-backed access to any provider with per-step cost tracking and a global cost/call kill-switch; Anthropic support adds prompt-caching and key rotation across `ANTHROPIC_API_KEYS` for parallel runs; an OpenRouter REST client with mandatory cost accounting; and a `DeterministicModel` that powers the no-key test suite.
- **SWE-bench runner** (`src/minisweagent/run/extra/swebench.py`) — batch and single-instance generation against SWE-bench tasks in Docker-backed environments, with curated `verified-40/45/50` subsets pinned by instance id, threaded workers, and `preds.json`/trajectory outputs for external scoring.

## Quickstart

```bash
git clone https://github.com/Asahu22/CortexFlow.git
cd CortexFlow
uv sync --extra dev            # or: uv venv && uv pip install -e ".[dev]"
```

Configure a model and key (any litellm-supported provider):

```bash
uv run mini-extra config set MSWEA_MODEL_NAME "anthropic/claude-sonnet-4-5-20250929"
uv run mini-extra config set ANTHROPIC_API_KEY "sk-ant-..."
```

Run the agent on a task in the current directory:

```bash
uv run mini -y -t "Fix the failing test in this directory" --exit-immediately
```

`mini -v` opens the pager UI, `mini --memory` enables session memory, and `./scripts/local/record_demo.sh` reproduces the demo above (requires an Anthropic key; the script checks for one without printing it).

## Testing

The suite collects 404 tests and runs without any API key — model behavior is covered through mocked providers and the deterministic offline model:

```bash
uv run pytest tests -m "not slow" -q   # what CI runs (~330 tests; slow/Docker tests deselect)
uv run ruff check .
uv run ruff format --check .
```

The full `uv run pytest tests` additionally exercises Docker-backed environment tests when a Docker daemon is available.

## SWE-bench Evaluation

The repo includes the agent-side harness, not the benchmark itself, and **publishes no benchmark scores**:

```bash
uv run mini-extra swebench \
  --model "anthropic/claude-sonnet-4-5-20250929" \
  --subset verified-40 \
  --split test \
  --workers 2 \
  --output runs/verified-40
```

This writes trajectories, `preds.json`, and per-instance status for scoring with the external [SWE-bench](https://github.com/SWE-bench/SWE-bench) harness or `sb-cli`. Course-time evaluation used small Verified subsets (40–50 instances) to bound API cost; generated predictions and results are intentionally not committed — run the harness to produce your own.

## Project Structure

```
src/minisweagent/
├── agents/         # core loop, interactive REPL, Textual UI
├── tools/          # 15-tool structured registry
├── memory/         # history compression, sessions, replay
├── models/         # litellm, Anthropic (multi-key), OpenRouter, deterministic
├── environments/   # local shell, Docker, Singularity
├── run/            # mini / mini-extra CLIs, SWE-bench runner
└── config/         # YAML agent configs and prompt templates
tests/              # 404 tests, no API key required
scripts/local/      # demo task fixture + GIF recording script
```

## Design Notes & Limitations

- Each bash action runs in a fresh subshell: no persistent `cd`, environment variables, or background processes between steps. The system prompt tells the model this; it costs some token overhead in exchange for a much simpler execution model.
- `replace_in_file` refuses ambiguous edits by design — the old text must match exactly once. The agent learns to include more context rather than the tool guessing.
- Memory compression is recency-based truncation, not semantic summarization: cheap and predictable, but long tasks lose early context.
- Structured tools execute in-process with the agent's privileges and trust the model's JSON. For untrusted tasks, run in the Docker environment or use `confirm` mode instead of `-y`.
- `lint_file` is a syntax check (`ast.parse`/`py_compile`), not a style linter — it catches broken edits, not bad taste.
- The protocol allows exactly one action per step. That makes parsing and replay trivial but spends more round-trips than multi-action agents.
- The SWE-bench runner produces predictions only; resolution scoring requires the external harness.

## What I Learned

- Structured edit tools with a lint gate beat raw shell edits for reliability: exact-match replacement plus an immediate syntax check catches most broken patches before the test suite ever runs.
- A deterministic fake model makes an agent loop unit-testable end to end — 404 tests run in CI with zero API keys, including full agent-loop and SWE-bench workflow tests.
- Observation shaping matters as much as prompting: output truncation and per-step cost display keep context (and spend) bounded on long tasks.
- A benchmark can be integrated without vendoring it: pin instance subsets in code, generate predictions locally, score externally.

## Acknowledgments & License

Adapted from [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) by Kilian A. Lieret, Carlos E. Jimenez, and contributors; the upstream MIT license and copyright are preserved in [LICENSE.md](LICENSE.md), with modifications under the same license. [SWE-bench](https://github.com/SWE-bench/SWE-bench) (MIT) is used as an external evaluation benchmark. Full details in [ATTRIBUTION.md](ATTRIBUTION.md).
