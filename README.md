# AI Context Generator

<p align="center">
  <img src="assets/banner.jpg" alt="AI Context Generator — Universal Project Context for Every AI Tool" width="680" />
</p>

<p align="center">
  <a href="https://github.com/edsoncarlosdevops/ai-context-generator/releases"><img src="https://img.shields.io/github/v/release/edsoncarlosdevops/ai-context-generator?style=for-the-badge&color=6C3FB5" alt="GitHub release"></a>
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

**Smart detection:** The tool detects which AI tools are already configured in your project and only generates bridge files for those. On a first run with no existing files, it generates all of them.

**Smart updates:** On re-runs, if your architecture hasn't changed significantly (less than 10% diff), no files are written — keeping your git history clean.

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

### GitHub Actions

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

### GitLab CI

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/edsoncarlosdevops/ai-context-generator/main/wrappers/gitlab-ci/.ai-context.yml'

variables:
  AI_API_KEY: $AI_API_KEY
  MODEL: "deepseek-chat"
```

### Azure DevOps

```yaml
resources:
  repositories:
    - repository: aicontext
      type: github
      name: edsoncarlosdevops/ai-context-generator
      endpoint: myServiceConnection

jobs:
  - template: wrappers/azure-devops/template.yml@aicontext
    parameters:
      aiApiKey: $(AI_API_KEY)
```

### CLI

```bash
pip install ai-context-generator

# Run in your project root
ai-context-generator generate --workspace . --api-key $AI_API_KEY

# Preview without writing files
ai-context-generator generate --dry-run

# Replace existing AGENTS.md entirely instead of enriching
ai-context-generator generate --replace
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

# Bridge files — auto-detected by default. Set false to disable specific tools.
cursorrules = true          # Cursor
windsurfrules = true        # Windsurf
clinerules = true           # Cline
zed_rules = true            # Zed AI
aider_conventions = true    # Aider
claude_md = true            # Claude Code
copilot_instructions = true # GitHub Copilot
amazonq_rules = true        # Amazon Q Developer
continue_rules = true       # Continue.dev

create_pr = false           # Open a PR automatically on CI runs

[scan]
exclude_dirs = [".git", "node_modules", ".venv", "dist", "build"]
max_file_size_kb = 100
```

| Key | Default | Description |
|-----|---------|-------------|
| `model` | `deepseek-chat` | LLM model to use for generation |
| `language` | `english` | Output language for generated rules |
| `max_lines` | `150` | Token budget for AGENTS.md (prevents bloat) |
| `create_pr` | `false` | Automatically open a PR with generated files |

---

## What Gets Generated

### `AGENTS.md` — Master Context File

Project-specific, actionable governance rules organized by technology domain. Not generic boilerplate — the LLM analyzes your actual dependencies, directory structure, CI/CD config, and infers your architecture to generate rules that are checkable during code review.

Example sections for a FastAPI + PostgreSQL + Docker project:
- `## 1. API Design & Input Validation` — Pydantic models, HTTP status codes, OpenAPI docs
- `## 2. Database & Migration Safety` — Alembic migrations, transaction handling, index strategy
- `## 3. Container & CI/CD Standards` — Multi-stage builds, health checks, secrets management

### Bridge Files

Lightweight 3-line pointer files for each AI tool. All point to `AGENTS.md`. Zero content duplication. If you update `AGENTS.md`, every tool automatically gets the updated context.

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

## Supported Languages & Frameworks

Automatically detected: Python, TypeScript, JavaScript, Go, Rust, C++, Java, Ruby, C#, HCL/Terraform.

Frameworks inferred from dependencies: FastAPI, Django, Flask, Express, Next.js, React, Vue, Spring Boot, Ruby on Rails, ROS 2, Terraform, Pulumi, and more.

---

## Related Projects

- [ai-pr-reviewer](https://github.com/edsoncarlosdevops/ai-pr-reviewer) — Automated PR code reviewer that reads your `AGENTS.md` and enforces project-specific governance rules on every Pull Request. Works with GitHub Actions, GitLab CI, and Azure DevOps.

---

## Keywords

`AGENTS.md generator` · `cursorrules generator` · `CLAUDE.md` · `copilot instructions` · `ai context file` · `llm context` · `cursor rules` · `windsurf rules` · `cline rules` · `ai coding assistant` · `code review automation` · `github actions ai` · `deepseek` · `openai` · `agnostic ai context` · `project governance` · `developer tooling`

---

## License

MIT — [edsoncarlosdevops](https://github.com/edsoncarlosdevops)
