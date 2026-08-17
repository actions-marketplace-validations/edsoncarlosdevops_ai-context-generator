# Architecture

`ai-context-generator` is a small, dependency-light Python package. It scans a
repository, builds a structured profile, turns that profile into a domain-aware LLM
prompt, and writes the result as `AGENTS.md` plus lightweight bridge files.

```
Your Codebase
     │
     ▼
CodebaseScanner ──► ScanResult ──► ProjectAnalyzer ──► ProjectProfile
                                                        │
                                                        ▼
                                                PromptBuilder ──► prompt
                                                                     │
                                                                     ▼
                                                                LLMClient
                                                                     │
                                                             (AGENTS.md content)
                                                                     │
                              ┌──────────────────────────────────────┤
                              ▼                                      ▼
                        AGENTS.md (source of truth)          BridgeWriter
                                                                     │
                                                             .cursorrules
                                                             CLAUDE.md
                                                             .windsurfrules
                                                             ...
```

---

## Pipeline Stages

### 1. `CodebaseScanner` (`ai_context_generator/scanner.py`)

Walks the repository and collects raw facts:

- **Language counts** — by file extension (Python, TypeScript, Go, Rust, Terraform, ...)
- **Dependencies** — parsed from `package.json`, `requirements.txt`, `pyproject.toml`,
  `go.mod`, `Cargo.toml`, `Gemfile`, `pom.xml`, `build.gradle`, `composer.json`
- **CI/CD files** — GitHub workflows, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`
- **Infrastructure** — `Dockerfile`, `docker-compose*`, `*.tf`, Helm/K8s paths
- **AI tool configs** — existing `.cursorrules`, `CLAUDE.md`, etc. (via `AI_TOOL_SIGNATURES`)
- **Tests & build commands** — from manifests and `Makefile`
- **Structural evidence** — directory tree (depth ≤ 3), entry points, root config
  files. This is what lets the LLM name real paths instead of inventing them.

Configurable via `[scan]`: `exclude_dirs`, `max_file_size_kb`, `use_gitignore`, and a
hard `max_files` cap so huge monorepos can't hang the tool.

**Profile stability:** files this tool generates itself (`CLAUDE.md`,
`.cursorrules`, `.continue/`, …) are excluded from the structural evidence, and
hidden directories never enter the tree. Without that, the first run would change
the profile, invalidate the cached signature, and bill a fresh LLM call on every
subsequent run.

### 2. `ProjectAnalyzer` (`ai_context_generator/analyzer.py`)

Turns the raw `ScanResult` into a semantic `ProjectProfile`:

- Primary/secondary languages (YAML/SQL/headers excluded from the primary slot)
- **Language breakdown** — percentages bucketed to 10% so routine commits do not
  invalidate the cached signature
- **Framework detection** — boundary-aware keyword matching against `FRAMEWORK_SIGNALS`
  (`_matches()` avoids false positives like `pyreact` matching `react`)
- **Domain detection** — most-voted domain from `DOMAIN_SIGNALS` (robotics, fintech,
  data-engineering, devops, web, embedded, general), with IaC overrides
- **Security risk level** — `high` for risky domains/deps (JWT, OAuth, payments),
  `medium` above 30 dependencies, else `low`
- **Infra tools** — mapped by exact filename / extension / directory name
  (`_infra_label()`), never by substring, so `samples/` is not read as AWS SAM
- **CI/CD platforms and architecture hints** — hints are derived from the real
  directory layout (`services/`, `packages/`, `dags/`, `cmd`+`internal`+`pkg`, …)

### 3. `PromptBuilder` (`ai_context_generator/prompt_builder.py`)

- Loads the Markdown template from `ai_context_generator/prompts/generate_agents.md` (ships inside
  the package so it works from PyPI)
- Injects the `ProjectProfile` as JSON, plus a readable **Repository Evidence**
  section (layout, entry points, config files, dependencies, verified commands)
- Applies a **domain playbook** (security + architecture rules per domain)
- In **enrichment mode** (existing `AGENTS.md`), instructs the LLM to add only
  missing rules instead of duplicating
- **Prompt-injection hardening:** repository content is fenced between
  `<<<BEGIN_UNTRUSTED_REPOSITORY_CONTENT>>>` markers, any injected copies of those
  markers are stripped, oversized files are truncated, and both the template and
  the system prompt instruct the model to treat the block as inert data

### 4. `LLMClient` (`ai_context_generator/llm_client.py`)

- Calls any OpenAI-compatible endpoint (`openai` SDK)
- Smart retries: rate-limit, connection and timeout errors plus 5xx are retried
  with exponential backoff (1s, 2s, …) and never sleep after the final attempt;
  401/403/404 fail fast with an actionable message
- Reports token usage per call (`last_usage`)
- Validates output: strips markdown fences, rejects empty content, raises a clear
  error on truncated output (`finish_reason == "length"`)
- Per-call `timeout` configurable

### 5. `ContextGenerator` (`ai_context_generator/generator.py`) — the orchestrator

- Computes a **profile signature** (hash of profile + model + language + limits)
- If the stored `.ai-context.sig` matches and `AGENTS.md` exists → **skips the LLM call**
- If content changed by <10% (`difflib.SequenceMatcher`) → keeps the current file
- Writes `AGENTS.md`, persists the signature, and runs `BridgeWriter`

### 6. `BridgeWriter` (`ai_context_generator/bridge_writer.py`)

Writes lightweight pointer files so every AI tool reads the same `AGENTS.md`:

- `.cursorrules`, `.windsurfrules`, `.clinerules`, `.rules`, `CONVENTIONS.md`
- `CLAUDE.md` — uses `@AGENTS.md` (Claude Code native import) + quick commands
- `.github/copilot-instructions.md`, `.amazonq/rules/project-rules.md`, `.continue/rules.md`

**Safety:** a file is only (re)written when it is missing, identical, or already
marked as generated by this tool (`_is_managed`) — user files are never clobbered.

### 7. `cli.py` — entry point

- `argparse`-based CLI (`ai-context-generator generate`)
- Loads `.ai_context.toml`, merges CLI overrides
- Loads `.env` (via `python-dotenv`) for API keys
- `--dry-run` preview mode with no file writes
- `--json` machine-readable summary for both dry runs and real runs
- Colour respects `NO_COLOR` / `FORCE_COLOR` and is off when stdout is not a TTY
- GitHub Actions annotations (`::error::`, `::notice::`), step summary and
  `GITHUB_OUTPUT`

---

## Design Decisions

| Decision | Why |
|----------|-----|
| `AGENTS.md` as single source of truth | One file to maintain; bridges are pointers |
| Opt-in bridge model | Only generate the bridges you actually use |
| `.ai-context.sig` signature | Skip the paid LLM call when nothing changed |
| <10% diff threshold | Avoid noisy git history from trivial LLM variance |
| Domain playbooks | Produce verifiable, project-specific rules — not generic advice |
| `linguist-generated` in `.gitattributes` | Bridges collapse in PR diffs and don't skew language stats |
| `openai` SDK only | Works with any OpenAI-compatible endpoint (BYOM) |
| Untrusted-content fencing | A scanned repository must not be able to steer the generator |
| Generated files excluded from the profile | Keeps the signature stable so reruns stay free |

---

## Error Handling Strategy

- Config: unknown keys warn loudly; a malformed TOML falls back to defaults
- Scanner: unreadable files are skipped (never crashes the scan)
- LLM: retryable errors are retried; auth errors fail fast; truncation raises a
  clear `LLMError`
- Bridge writer: user-owned files are never overwritten

---

## Testing

See [Contributing](./contributing.md) for how to run tests, linting, type checks
and coverage locally. The test suite covers:

- Scanner & analyzer (language/domain/framework detection)
- Config loading (incl. unknown-key warnings and opt-in bridge semantics)
- Prompt building (enrichment vs from-scratch)
- LLM client (retries, sanitization, truncation errors)
- Generator (signature skip, delta threshold, bridge independence)
- Bridge writer (no-clobber guarantees)
- CLI (dry-run, `.env` loading, error paths)
