# AI Context Generator

<img src="assets/banner.jpg" alt="AI Context Generator" width="680" />

[![GitHub release](https://img.shields.io/github/v/release/edsoncarlosdevops/ai-context-generator)](https://github.com/edsoncarlosdevops/ai-context-generator/releases)
[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-AI%20Context%20Generator-blue)](https://github.com/marketplace/actions/ai-context-generator)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/edsoncarlosdevops/ai-context-generator)](https://github.com/edsoncarlosdevops/ai-context-generator/stargazers)

Scan any repository and automatically generate AI context files (`AGENTS.md`, `.cursorrules`, `CLAUDE.md`) — the universal governance layer for every AI coding tool.

## Ecosystem

```text
ai-context-generator  ──generates──►  AGENTS.md  ──consumed by──►  ai-pr-reviewer
                                           │
                           .cursorrules, CLAUDE.md, copilot-instructions.md
                           (Cursor, Claude Code, GitHub Copilot, Antigravity...)
```

## Quick Start

You can integrate AI Context Generator into your workflow using various platforms.

### GitHub Actions

Add this to your `.github/workflows/ai-context.yml`:

```yaml
name: Generate AI Context
on:
  schedule:
    - cron: '0 0 * * 0' # Weekly
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: edsoncarlosdevops/ai-context-generator@v1
        with:
          ai_api_key: ${{ secrets.DEEPSEEK_API_KEY }}
          model: deepseek-chat
```

### GitLab CI

Include the template in your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/edsoncarlosdevops/ai-context-generator/main/wrappers/gitlab-ci/.ai-context.yml'
```

### Azure DevOps

Reference the template in your pipeline:

```yaml
resources:
  repositories:
    - repository: aicontext
      type: github
      name: edsoncarlosdevops/ai-context-generator
      endpoint: myServiceConnection

jobs:
  - template: wrappers/azure-devops/template.yml@aicontext
```

### CLI

Install and run locally:

```bash
pip install ai-context-generator
ai-context-generator generate --workspace . --api-key $AI_API_KEY
```

## Configuration

Place an `.ai_context.toml` file in the root of your repository to customize behavior.

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `[generator]` | `model` | `"deepseek-chat"` | The LLM to use for generation. |
| `[generator]` | `language` | `"english"` | The language for the generated rules. |
| `[generator]` | `max_lines` | `150` | Maximum length of the generated file. |
| `[output]` | `agents_md` | `true` | Generate `AGENTS.md`. |
| `[output]` | `cursorrules` | `true` | Generate `.cursorrules`. |
| `[output]` | `claude_md` | `true` | Generate `CLAUDE.md`. |
| `[output]` | `copilot_instructions` | `true` | Generate GitHub Copilot instructions. |
| `[output]` | `create_pr` | `false` | Open a PR if changes are detected. |
| `[scan]` | `exclude_dirs` | `[".git", "node_modules", ".venv", "dist", "build"]` | Directories to ignore during scanning. |
| `[scan]` | `max_file_size_kb` | `100` | Maximum file size to analyze. |

## What gets generated

1. **`AGENTS.md`**: The master context file containing architectural rules, technology stack details, and governance policies.
2. **`.cursorrules`**: Formatted specifically for Cursor IDE integration.
3. **`CLAUDE.md`**: Tailored for Claude Code and Anthropic ecosystem.
4. **Copilot Instructions**: Bridged context for GitHub Copilot.

## BYOM (Bring Your Own Model)

Configure any supported LLM by passing the appropriate API key and base URL (if needed).

| Provider | Model Name | Base URL (if custom) |
|----------|------------|----------------------|
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com` |
| OpenAI | `gpt-4o` | `https://api.openai.com/v1` |
| Anthropic| `claude-3-5-sonnet-20240620`| N/A |
| Ollama (Local)| `llama3` | `http://localhost:11434/v1` |

## Related Projects

- [ai-pr-reviewer](https://github.com/edsoncarlosdevops/ai-pr-reviewer): An automated PR review system that reads your `AGENTS.md` file to enforce project-specific coding standards during code review.

## License

MIT
