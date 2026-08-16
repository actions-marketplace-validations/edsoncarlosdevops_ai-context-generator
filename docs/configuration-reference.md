# Configuration Reference

All configuration lives in a `.ai_context.toml` file at your repository root.
Every option has a sensible default — the file is entirely optional.

---

## Full Reference

```toml
[generator]
model = "deepseek-chat"    # LLM model (DeepSeek, OpenAI, Anthropic, Ollama, ...)
base_url = "https://api.deepseek.com"  # Any OpenAI-compatible endpoint
language = "english"       # english, portuguese, spanish, french, german
max_lines = 150            # Target line budget for the generated AGENTS.md
max_tokens = 4096          # Max tokens per LLM response
timeout = 120.0            # Seconds to wait per LLM API call before timing out

[output]
agents_md = true           # Generate AGENTS.md

# Bridge files — opt-in model: only tools you list here are generated.
# If you omit [output] entirely, ALL bridges are generated (first-run default).
cursorrules = true          # Cursor
claude_md = true            # Claude Code
copilot_instructions = true # GitHub Copilot
windsurfrules = true        # Windsurf (Codeium)
clinerules = true           # Cline
zed_rules = true            # Zed AI
aider_conventions = true    # Aider
amazonq_rules = true        # Amazon Q Developer
continue_rules = true       # Continue.dev

create_pr = false           # Open a PR automatically on CI runs

[scan]
exclude_dirs = [".git", "node_modules", ".venv", "dist", "build", "__pycache__"]
max_file_size_kb = 100      # Skip files larger than this
max_files = 100000          # Hard cap on files scanned (protects huge monorepos)
```

---

## Option Details

### `[generator]`

| Option | Default | Description |
|--------|---------|-------------|
| `model` | `deepseek-chat` | The LLM model name. |
| `base_url` | `https://api.deepseek.com` | Base URL of an OpenAI-compatible API. |
| `language` | `english` | Output language of `AGENTS.md`. |
| `max_lines` | `150` | Target line budget. The LLM is instructed to stay under it. |
| `max_tokens` | `4096` | Max tokens per response. Increase if output is truncated. |
| `timeout` | `120.0` | Per-call timeout in seconds. Raise for slow models / big prompts. |

### `[output]`

Bridge flags follow an **opt-in model**:

- If `[output]` **exists**, only the bridges you explicitly list are generated.
- If `[output]` is **absent**, the tool auto-detects: tools already configured in the
  repo get bridges; if none are detected (first run), **all** bridges are generated
  for maximum compatibility.

| Option | Tool |
|--------|------|
| `cursorrules` | Cursor |
| `windsurfrules` | Windsurf (Codeium) |
| `clinerules` | Cline |
| `zed_rules` | Zed AI |
| `aider_conventions` | Aider |
| `claude_md` | Claude Code |
| `copilot_instructions` | GitHub Copilot |
| `amazonq_rules` | Amazon Q Developer |
| `continue_rules` | Continue.dev |
| `create_pr` | Open a PR automatically on CI runs (used by GitHub Action) |

> **Tip:** keep your repo root clean. If you only use Cursor and Claude, only
> `.cursorrules` and `CLAUDE.md` are created.

### `[scan]`

| Option | Default | Description |
|--------|---------|-------------|
| `exclude_dirs` | `[".git", "node_modules", ".venv", "dist", "build", "__pycache__"]` | Directories skipped during the scan. |
| `max_file_size_kb` | `100` | Files larger than this are skipped. |
| `max_files` | `100000` | Hard cap on files scanned. Prevents hangs on gigantic monorepos. |

---

## CLI Flags

All `[generator]` and `[scan]` options can be overridden from the command line:

```bash
ai-context-generator generate \
  --workspace . \
  --model gpt-4o \
  --base-url https://api.openai.com/v1 \
  --language portuguese \
  --max-files 50000 \
  --timeout 180 \
  --replace \
  --no-bridge
```

| Flag | Overrides |
|------|-----------|
| `--workspace` | Repository root path (default `.`) |
| `--config` | Custom config file path |
| `--api-key` | LLM API key (prefer env var `AI_API_KEY` / `OPENAI_API_KEY` / `.env`) |
| `--base-url` | `generator.base_url` |
| `--model` | `generator.model` |
| `--language` | `generator.language` |
| `--max-files` | `scan.max_files` |
| `--timeout` | `generator.timeout` |
| `--replace` | Force a full rewrite instead of enriching existing `AGENTS.md` |
| `--dry-run` | Preview scan + prompt without writing files |
| `--no-bridge` | Skip all bridge files (only write `AGENTS.md`) |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `AI_API_KEY` | Primary API key (DeepSeek, OpenAI, ...) |
| `OPENAI_API_KEY` | Fallback API key if `AI_API_KEY` is unset |
| `GITHUB_ACTIONS` | Enables `::error::` / `::notice::` annotations |
| `GITHUB_STEP_SUMMARY` | Enables the GitHub Step Summary table |

A `.env` file in the workspace root is loaded automatically if present
(requires `python-dotenv`, installed by default).
