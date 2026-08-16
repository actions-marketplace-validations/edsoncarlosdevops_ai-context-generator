# Getting Started

This guide walks you through installing `ai-context-generator` and generating your
first `AGENTS.md` — the single source of truth for every AI coding assistant.

---

## 1. Prerequisites

- Python **3.11+** (for the pip route) — or just `uv`/`pipx` for the zero-install route
- An LLM API key (DeepSeek, OpenAI, Anthropic, Ollama local, or any OpenAI-compatible endpoint)

## 2. Quick Start

### Zero-Install (uvx / pipx)

```bash
# Run instantly with uvx — no installation required
uvx ai-context-generator generate --workspace . --api-key $AI_API_KEY

# Or with pipx
pipx run ai-context-generator generate --workspace . --api-key $AI_API_KEY

# Dry-run preview without writing any files
uvx ai-context-generator generate --workspace . --dry-run
```

### Standard Pip Install

```bash
pip install ai-context-generator

# Run in your project root
ai-context-generator generate --workspace . --api-key $AI_API_KEY
```

### Local LLM (Ollama)

```bash
ai-context-generator generate \
  --workspace . \
  --api-key dummy \
  --base-url http://localhost:11434/v1 \
  --model llama3
```

---

## 3. Security: How to Handle API Keys

**Never** pass your key as a literal command-line argument in production. The CLI
accepts `--api-key`, but the recommended and safe approaches are:

### Option A — Environment Variable (recommended)

```bash
export AI_API_KEY="sk-..."     # DeepSeek / OpenAI
# or
export OPENAI_API_KEY="sk-..."
ai-context-generator generate --workspace .
```

### Option B — `.env` File

The tool automatically loads a `.env` file from your workspace root (via
`python-dotenv`). Add it to your `.gitignore` and never commit it:

```bash
# .env  (never commit this file!)
AI_API_KEY=sk-...
```

```bash
ai-context-generator generate --workspace .
```

> ⚠️ **Security rules of thumb**
> - `.env` is already in the project's `.gitignore` — keep it that way.
> - In CI, use GitHub **secrets**, not inline keys.
> - A key passed via `--api-key` can end up in your shell history
>   (`~/.bash_history`) — prefer environment variables.

---

## 4. Verify Without Calling the LLM: `--dry-run`

Dry-run scans your repository, shows the detected profile, and previews the prompt
that would be sent to the LLM — without writing any files or spending tokens:

```bash
ai-context-generator generate --workspace . --dry-run
```

Output includes:

- Files scanned and language breakdown
- Detected frameworks, infrastructure tools and CI/CD platforms
- Detected domain and security risk level
- AI tool config files already present in the repo
- Preview of the generated prompt (first 30 lines)

---

## 5. What Gets Generated

| File | Purpose |
|------|---------|
| `AGENTS.md` | Master governance file — the single source of truth |
| `.cursorrules` | Cursor IDE context |
| `.windsurfrules` | Windsurf (Codeium) context |
| `.clinerules` | Cline (VS Code) context |
| `.rules` | Zed AI context |
| `CONVENTIONS.md` | Aider conventions |
| `CLAUDE.md` | Claude Code context (imports `@AGENTS.md`) |
| `.github/copilot-instructions.md` | GitHub Copilot instructions |
| `.amazonq/rules/project-rules.md` | Amazon Q Developer rules |
| `.continue/rules.md` | Continue.dev rules |
| `.ai-context.sig` | Signature cache (skip paid LLM call when profile is unchanged) |
| `.gitattributes` | Marks all generated files as `linguist-generated` |

---

## Next Steps

- [Configuration Reference](./configuration-reference.md) — every option in `.ai_context.toml`
- [CI/CD Integration](./ci-cd-integration.md) — GitHub Actions, pre-commit, Azure DevOps, GitLab CI
- [Architecture](./architecture.md) — how the scanner → analyzer → prompt → LLM pipeline works
- [Contributing](./contributing.md) — how to build, test and submit PRs
