# AI Context Generator

<p align="center">
  <img src="assets/banner.jpg" alt="AI Context Generator — Universal Project Context for Every AI Tool" width="680" />
</p>

<p align="center">
  <a href="https://pypi.org/project/ai-context-generator/"><img src="https://img.shields.io/pypi/v/ai-context-generator?style=for-the-badge&color=6C3FB5&logo=pypi&logoColor=white" alt="PyPI Package"></a>
  <a href="https://github.com/edsoncarlosdevops/ai-context-generator/releases"><img src="https://img.shields.io/github/v/release/edsoncarlosdevops/ai-context-generator?style=for-the-badge&color=2E86AB" alt="GitHub release"></a>
  <a href="https://github.com/marketplace/actions/ai-context-generator"><img src="https://img.shields.io/badge/Marketplace-AI%20Context%20Generator-blue?style=for-the-badge&logo=github" alt="GitHub Marketplace"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License MIT"></a>
  <a href="https://github.com/edsoncarlosdevops/ai-context-generator/stargazers"><img src="https://img.shields.io/github/stars/edsoncarlosdevops/ai-context-generator?style=for-the-badge&color=gold" alt="GitHub Stars"></a>
</p>

Scan any repository and automatically generate AI context files — `AGENTS.md`, `.cursorrules`, `CLAUDE.md`, `.windsurfrules`, `.clinerules`, and more. The universal governance layer that makes every AI coding assistant understand your project's architecture, standards, and conventions.

> Works with Cursor, Windsurf, Claude Code, GitHub Copilot, Cline, Amazon Q, Continue.dev, Zed AI, Aider, Antigravity, and any LLM-based tool that reads project context files.

---

## The Problem

Every AI coding assistant reads a different context file:

| Tool | File it reads |
|------|--------------|
| Cursor | `.cursorrules` |
| Windsurf (Codeium) | `.windsurfrules` |
| Claude Code | `CLAUDE.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cline | `.clinerules` |
| Amazon Q Developer | `.amazonq/rules/project-rules.md` |
| Continue.dev | `.continue/rules.md` |
| Zed AI | `.rules` |
| Aider | `CONVENTIONS.md` |
| Antigravity / AI PR Reviewer | `AGENTS.md` |

Maintaining all of them by hand is redundant, error-prone, and quickly becomes outdated as your project evolves.

---

## The Solution

`ai-context-generator` scans your codebase once, generates a single `AGENTS.md` as the **source of truth**, and automatically creates lightweight pointer files for every AI tool your team uses — with zero duplication.

```
Your Codebase
     │
     ▼
ai-context-generator (scan + LLM analysis)
     │
     ▼
AGENTS.md ─── Single Source of Truth
     │
     ├──► .cursorrules          (Cursor)
     ├──► .windsurfrules        (Windsurf)
     ├──► CLAUDE.md             (Claude Code)
     ├──► .github/copilot-instructions.md  (GitHub Copilot)
     ├──► .clinerules           (Cline)
     ├──► .amazonq/rules/       (Amazon Q)
     ├──► .continue/rules.md    (Continue.dev)
     ├──► .rules                (Zed AI)
     └──► CONVENTIONS.md        (Aider)
```

**Opt-in bridge model:** When you have a `[output]` section in `.ai_context.toml`, only the bridges you explicitly list are generated — keeping your repo clean. With no config at all, the tool generates all bridges on first run (maximum compatibility). This means your project root stays minimal: if you only use Cursor and Claude, only `.cursorrules` and `CLAUDE.md` are created.

**Smart updates (cost-saving):** The tool stores a lightweight `.ai-context.sig` signature file in your repo. When the detected project profile is unchanged, the paid LLM call is **skipped entirely** and the existing `AGENTS.md` is kept. When the profile does change, the generated content is compared with the current file — if the architecture hasn't changed significantly (less than 10% diff), no files are written, keeping your git history clean. Commit `.ai-context.sig` alongside `AGENTS.md` to benefit in CI.

---

## Ecosystem

```
ai-context-generator  ──generates──►  AGENTS.md  ──consumed by──►  ai-pr-reviewer
                                           │
                       All AI IDEs and assistants read the same source of truth
```

Used together with [ai-pr-reviewer](https://github.com/edsoncarlosdevops/ai-pr-reviewer), every Pull Request is reviewed by an AI that already understands your project's architecture, security requirements, and coding standards.

---

## Quick Start

### ⚡ Zero-Install CLI (Recommended for fast local testing)

No installation required using `uvx` or `pipx`:

```bash
# Run instantly with uvx
uvx ai-context-generator generate --workspace . --api-key $AI_API_KEY

# Or with pipx
pipx run ai-context-generator generate --workspace . --api-key $AI_API_KEY

# Dry-run preview without writing files
uvx ai-context-generator generate --dry-run
```

### 📦 Standard Pip Install

```bash
pip install ai-context-generator

# Run in your project root
ai-context-generator generate --workspace . --api-key $AI_API_KEY
```

### 🪝 Pre-Commit Hook Integration

Add `ai-context-generator` to your `.pre-commit-config.yaml` to keep context files updated before every commit:

> **Note:** the hook runs on every commit (`always_run`) and requires an API key via `AI_API_KEY` (or `OPENAI_API_KEY`) in the environment. It is cheap in practice — when the repository profile hasn't changed, the LLM call is skipped automatically.

```yaml
repos:
  - repo: https://github.com/edsoncarlosdevops/ai-context-generator
    rev: v1.2.0
    hooks:
      - id: ai-context-generator
```

### 🤖 GitHub Actions

Add to `.github/workflows/ai-context.yml`:

```yaml
name: Generate AI Context
on:
  workflow_dispatch:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday

jobs:
  generate:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: edsoncarlosdevops/ai-context-generator@v1
        with:
          ai_api_key: ${{ secrets.DEEPSEEK_API_KEY }}
          model: deepseek-chat
          create_pr: 'true'
```

---

## 🏷️ Add Badge to Your Project README

Show that your project maintains universal AI governance by adding this badge to your README:

[![AI Context: AGENTS.md](https://img.shields.io/badge/AI%20Context-AGENTS.md-6C3FB5?style=flat-square&logo=cpu)](https://github.com/edsoncarlosdevops/ai-context-generator)

```markdown
[![AI Context: AGENTS.md](https://img.shields.io/badge/AI%20Context-AGENTS.md-6C3FB5?style=flat-square&logo=cpu)](https://github.com/edsoncarlosdevops/ai-context-generator)
```

---

## Configuration

Place `.ai_context.toml` in your repository root:

```toml
[generator]
model = "deepseek-chat"
language = "english"      # english, portuguese, spanish, french, german
max_lines = 150

[output]
agents_md = true

# Bridge files — opt-in model: only tools you list here are generated.
# If you omit [output] entirely, ALL bridges are generated (first-run default).
cursorrules = true          # Cursor
claude_md = true            # Claude Code
copilot_instructions = true # GitHub Copilot
# windsurfrules = true      # Windsurf (uncomment to enable)
# clinerules = true         # Cline
# zed_rules = true          # Zed AI
# aider_conventions = true  # Aider
# amazonq_rules = true      # Amazon Q Developer
# continue_rules = true     # Continue.dev

create_pr = false           # Open a PR automatically on CI runs

[scan]
exclude_dirs = [".git", "node_modules", ".venv", "dist", "build"]
max_file_size_kb = 100
```

**Bridge files stay clean.** The tool automatically creates a `.gitattributes` file
marking all generated bridges as `linguist-generated`, so they:
- Collapse by default in GitHub PR diffs
- Don't count toward your language statistics

### Pipeline Integration

For automatic updates when your project structure changes, add path triggers:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'pyproject.toml'
      - 'package.json'
      - 'Dockerfile*'
      - '.github/workflows/*.yml'
      - '*.tf'
  workflow_dispatch:
  schedule:
    - cron: '0 9 * * 1'
```

---

## BYOM — Bring Your Own Model

| Provider | Model | Base URL |
|----------|-------|----------|
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com` |
| OpenAI | `gpt-4o`, `gpt-4-turbo` | `https://api.openai.com/v1` |
| Anthropic | `claude-3-5-sonnet-20241022` | `https://api.anthropic.com/v1` |
| Ollama (local) | `llama3`, `mistral`, `codestral` | `http://localhost:11434/v1` |
| Any OpenAI-compatible | any | custom `base_url` |

```bash
ai-context-generator generate \
  --api-key $MY_KEY \
  --model gpt-4o \
  --workspace .
```

---

## License

MIT — [edsoncarlosdevops](https://github.com/edsoncarlosdevops)
