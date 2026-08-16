# Contributing

Thank you for your interest in contributing to **AI Context Generator**! This guide
complements the [Contributing Guide](../CONTRIBUTING.md) at the repository root.

---

## Development Setup

### Prerequisites
- Python 3.11+
- `git`

### Clone & Install

```bash
git clone https://github.com/edsoncarlosdevops/ai-context-generator.git
cd ai-context-generator

python3 -m venv .venv
source .venv/bin/activate

# Install with all dev dependencies
pip install -e ".[dev]"
```

### Quick smoke test (no API key needed)

```bash
ai-context-generator generate --workspace . --dry-run
```

---

## Quality Checks

Every PR must pass all of these locally:

```bash
# Unit tests with coverage (70% threshold enforced)
pytest tests/

# Linter
ruff check core/ tests/

# Formatter
ruff format --check core/ tests/

# Type checker
mypy core/

# Security scan
bandit -r core/ -c pyproject.toml -q
```

These same checks run in CI on every push and pull request
(`.github/workflows/ci.yml`).

---

## Project Layout

```
core/
├── scanner.py       # Walk the repo: languages, deps, CI/CD, infra, AI tool files
├── analyzer.py      # ScanResult → ProjectProfile (frameworks, domain, security)
├── prompt_builder.py# ProjectProfile → domain-aware LLM prompt
├── llm_client.py    # OpenAI-compatible client with retries + validation
├── generator.py     # Orchestrator: signature skip, delta threshold, bridges
├── bridge_writer.py # Writes pointer files for every AI tool
├── config.py        # .ai_context.toml loading + CLI overrides
├── cli.py           # argparse CLI entry point
└── prompts/
    └── generate_agents.md  # LLM template shipped inside the package
docs/                # This documentation site
tests/               # pytest suite
wrappers/            # Azure DevOps / GitLab CI templates
```

---

## Adding a New AI Tool Bridge

1. **`core/scanner.py`** — add the tool's signature file to `AI_TOOL_SIGNATURES`.
2. **`core/config.py`** — add a boolean flag to `OutputConfig` and an entry in
   `BRIDGE_FLAG_TO_TOOL`.
3. **`core/bridge_writer.py`** — add the file-generation method.
4. **`docs/configuration-reference.md`** — document the new flag.
5. **`tests/`** — add unit test coverage in `tests/test_bridge_writer.py`.

---

## Adding a New Domain Playbook

1. **`core/analyzer.py`** — add signals to `DOMAIN_SIGNALS` and (optionally) a
   priority in the tie-breaker list.
2. **`core/prompt_builder.py`** — add a `DOMAIN_PLAYBOOKS` entry with concrete,
   reviewable rules.
3. Add tests in `tests/test_analyzer.py`.

---

## Pull Request Checklist

- [ ] Focused: one logical change per PR
- [ ] Tests added/updated
- [ ] `ruff check` + `ruff format --check` pass
- [ ] `mypy core/` passes
- [ ] `bandit -r core/ -c pyproject.toml -q` passes
- [ ] Docs updated if configuration or behaviour changed
- [ ] CI is green
