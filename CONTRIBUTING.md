# Contributing

This repository is a personal adaptation of `mini-swe-agent`, not the upstream project.

## Scope

Contributions here should be limited to:

- Documentation and setup clarity.
- Tests for this adaptation.
- Fixes to the project-specific tool, memory, and SWE-bench runner integration code.
- Cleanup that preserves upstream attribution.

For upstream `mini-swe-agent` bugs or feature requests, use the upstream repository: https://github.com/SWE-agent/mini-swe-agent

For SWE-bench harness issues, use the upstream SWE-bench repository: https://github.com/SWE-bench/SWE-bench

## Do Not Add

- Generated trajectories, benchmark predictions, evaluation JSON, status YAML, or logs.
- API keys, `.env` files, model credentials, or private machine paths.
- Vendored copies of upstream benchmark repositories.

## Local Checks

Run the same checks CI runs before opening changes:

```bash
uv run pytest tests -m "not slow" -q
uv run ruff check .
uv run ruff format --check .
```
