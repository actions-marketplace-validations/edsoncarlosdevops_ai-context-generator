# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Releases never reached PyPI.** The CI release job pushes the version tag with
  the default `GITHUB_TOKEN`, and GitHub deliberately does not let such a push
  trigger another workflow — so `publish-pypi.yml`'s `on: push: tags:` trigger
  never fired. v1.3.0 and v2.0.0 were tagged but never published, leaving PyPI on
  1.2.0. The release job now calls the publish workflow directly
  (`workflow_call`), so cutting a release actually ships it.
- **Floating major tag was hardcoded to `v1`.** The moment the major version was
  bumped, `v1` was force-moved onto a 2.x release, silently serving v2 to everyone
  pinned to `@v1`. The tag is now derived from the version (`2.0.0` → `v2`), `v2`
  has been created, and `v1` has been restored to the last 1.x release (v1.3.0).
  README and CI/CD docs now reference `@v2`.
- **Release job hardening**, per AI PR review on #2: the version read from
  `pyproject.toml` is now validated against `X.Y.Z` before any tag is cut, the
  floating major tag is checked against `^v[0-9]+$` before it is force-pushed,
  `secrets: inherit` on the PyPI publish call was replaced with passing only
  `PYPI_API_TOKEN` explicitly (`publish-pypi.yml` now declares it under
  `workflow_call: secrets:`), and both release-related jobs got a
  `timeout-minutes` cap.

## [2.0.0] — 2026-08-17

### Breaking

- **Package renamed `core` → `ai_context_generator`.** Installing this project no
  longer places a generic top-level `core` package in site-packages, where it could
  shadow or be shadowed by an unrelated module. The CLI, the `.ai_context.toml`
  format and the GitHub Action inputs are unchanged; only direct Python imports and
  `python -m core.cli` need updating.

### Fixed

- **`tests/` directories were not detected.** The check compared the literal string
  `test` against path components, so a plural `tests/` directory never matched,
  while a substring match on filenames flagged `latest_release.py` as a test file.
  Detection now uses a dedicated set of test directory names plus per-ecosystem
  filename conventions (`test_*.py`, `*_test.go`, `*.spec.ts`, …).
- **Phantom infrastructure detection.** Infra tools were matched by substring
  against the joined file list, so any repository with a `samples/` directory was
  reported as using AWS SAM. Matching is now anchored to exact filenames, file
  extensions and directory names.
- **Dead infra signals.** `serverless.yml`, `Chart.yaml`, `values.yaml`, `cdk.json`
  and SAM templates were listed as detectable but could never reach the analyzer,
  because the scanner never collected them. They are now detected, along with
  Kustomize, Skaffold, Bicep and Vagrant.
- **Build output was scanned as source.** The default `exclude_dirs` missed `venv`,
  `env`, `target`, `vendor`, `out`, `bin`, `obj`, `coverage`, `.next`, `.nuxt`,
  `.tox`, `.gradle`, `.terraform` and more, skewing language statistics on most
  real projects. Plain directory names from the repository `.gitignore` are now
  skipped as well (`scan.use_gitignore`, `--no-gitignore`).
- **`[scan] exclude_dirs` replaced the defaults** instead of extending them, so
  adding a single directory silently re-enabled scanning of `node_modules`.
- **Undocumented-but-advertised environment variables.** `.env.example` documented
  `AI_CONTEXT_MODEL`, `AI_CONTEXT_BASE_URL` and `AI_CONTEXT_LANGUAGE`, which no code
  read. They are now implemented, with precedence CLI > env > config > defaults.
- **`--timeout 0` and `--max-files 0` were silently ignored** because the flags were
  tested for truthiness rather than for being set.
- **ANSI colour codes leaked into non-terminal output**, garbling piped output and
  CI logs. Colour now honours `NO_COLOR`, `FORCE_COLOR` and TTY detection.
- **Pointless sleep after the final LLM retry** — the client no longer backs off
  after its last attempt.
- **Unreachable error handling in `action.yml`** — `EXIT_CODE=$?` could never run
  under the `set -e` that composite `shell: bash` steps use.
- Typos in the `[output]` config section counted as explicit user choices and
  suppressed bridge auto-detection; unknown keys are now ignored for that purpose.
- `max_tokens`, `max_lines`, `max_retries` and `max_file_size_kb` are now clamped to
  sane values when a config supplies zero or negative numbers.

### Added

- **Repository evidence in the prompt.** The LLM now receives the real directory
  layout, entry points, root config files, direct dependencies and the verified
  build/test commands — and is instructed never to reference a path, command or
  library that is not in that evidence. Previously it saw only a dozen summary
  fields and was asked to be specific anyway.
- **Prompt-injection hardening.** An existing `AGENTS.md` is fenced as untrusted
  repository content, injected copies of the fence markers are stripped, oversized
  files are truncated, and both the template and the system prompt instruct the
  model to treat the block as inert data.
- **`--json`** — machine-readable summary for both dry runs and real runs.
- **`--max-retries`** / `generator.max_retries`, and **`--no-gitignore`**.
- **`output.gitattributes`** to opt out of the managed `.gitattributes` block.
- Token usage is reported after each run.
- New analyzer signals: `machine-learning` domain, architecture hints derived from
  the real directory layout, a 10%-bucketed language breakdown, and additional
  frameworks (Litestar, Remix, Astro, Quarkus, Laravel, Symfony, PyTorch,
  TensorFlow, LangChain, …). More languages are recognised (C, Elixir, Lua, SQL, …).
- Poetry-style dependencies (`[tool.poetry.*]`) are now parsed from `pyproject.toml`;
  CircleCI and Bitbucket Pipelines are recognised as CI platforms.
- Hand-written bridge files that are left untouched are now reported explicitly
  instead of being silently skipped.
- `action.yml` gained `timeout`, `max_files` and `config` inputs, plus a new
  `agents_md_updated` output (true only when `AGENTS.md` itself was rewritten).
- CI now verifies the packaged wheel ships the prompt template and that the CLI
  runs end-to-end.

### Changed

- **Re-running on an unchanged repository no longer costs a second LLM call.** The
  files this tool generates (and hidden directories) used to feed back into the
  project profile, invalidating the cached signature on every run. They are now
  excluded, and a regression test asserts three consecutive runs make one call.
- The `openai` SDK's internal retry layer is disabled so backoff and error
  classification live in one place; HTTP 404 now fails fast with a message naming
  the model and base URL.
- Test suite grown from 30 to 114 tests; coverage gate raised from 70% to 85%
  (currently 91%).

## [1.3.0] - 2025-08-17

### Added

- **`.env` support** — API keys can now live in a `.env` file at the workspace root
  (loaded automatically via `python-dotenv`); see `.env.example`.
- **Performance limits** — new `--max-files` CLI flag and `scan.max_files` config
  option (hard cap on files scanned), plus `--timeout` flag / `generator.timeout`
  for LLM API calls.
- **CI hardening** — the CI workflow now runs `mypy` type checks, a `bandit` security
  scan, and pytest coverage (with Codecov upload).
- **Developer tooling** — `[project.optional-dependencies] dev` group with pytest,
  pytest-cov, ruff, mypy and bandit; `tool.mypy`, `tool.bandit` and `tool.coverage`
  configs in `pyproject.toml`.
- **Structured documentation** — new `docs/` folder (getting-started, configuration
  reference, CI/CD integration, architecture, contributing) and a slimmer README
  with CI/coverage badges.
- **`CODE_OF_CONDUCT.md`** — contributor covenant.

### Changed

- `CodebaseScanner` accepts an optional `max_files` parameter; `LLMClient` accepts an
  optional `timeout` parameter.
- `core.cli.main` now accepts an optional `argv` list, enabling proper CLI unit tests.

## [1.2.0] - 2025-08-11

### Fixed

- **GitHub Action no longer crashes with `ModuleNotFoundError`** — the action now
  runs the CLI as a module (`python -m core.cli`) with `PYTHONPATH` pointing at the
  action path instead of executing `core/cli.py` directly.
- **GitHub Action now detects brand-new (untracked) files** — switched the
  "did anything change?" check from `git diff --quiet` to `git status --porcelain`,
  so the first run actually opens a Pull Request.
- **LLM output validation** — markdown code fences are stripped, empty responses
  are rejected, and truncated responses (`finish_reason == "length"`) raise a clear
  error instead of writing a half-finished `AGENTS.md`.
- **Bridge files no longer overwrite user files** — `.cursorrules`, `CLAUDE.md`,
  etc. are only (re)written when they are missing, identical, or already generated
  by this tool.
- **`AGENTS.md` alone no longer suppresses bridge generation** — auto-detection no
  longer treats the tool's own output file as a signal to skip every bridge.
- **Explicit config now wins over auto-detection** — options set in `.ai_context.toml`
  or via `--no-bridge` are never overridden by detected AI tool signatures.
- **Bridges are regenerated even when `AGENTS.md` is up-to-date** — a missing bridge
  file is re-created regardless of the `AGENTS.md` write decision.
- Removed the stale, conflicting `setup.py` (wrong version 0.1.0) and the dead
  `tomli` dependency from `requirements.txt`.
- Removed the broken duplicate action under `wrappers/github-action/`.

### Added

- **`.ai-context.sig` signature cache** — when the detected project profile is
  unchanged since the last run, the paid LLM call is skipped entirely.
- **More languages detected** — Kotlin, Swift, PHP, Scala, Dart, Shell, React JS
  (`.jsx`), `.mjs`, `.cjs`.
- **More manifests parsed** — `pyproject.toml`, `go.mod`, `Cargo.toml`,
  `composer.json`, `Gemfile`, `pom.xml`, `build.gradle`.
- **Domain scoring** — the most-voted domain wins instead of first-match, reducing
  false positives (e.g. React + pandas now correctly detects `web`).
- **Boundary-aware dependency matching** — `react` no longer matches `pyreact`.
- **`--version` flag** and a configurable `max_tokens` (default 4096).
- **`CHANGELOG.md`** and expanded test suite (21 tests covering scanner, analyzer,
  generator, LLM client and config).

### Changed

- `CLAUDE.md` now uses the native `@AGENTS.md` import syntax instead of a markdown link.
- Pointer bridges use explicit instructions instead of the unsupported `@import` directive.
- GitHub Action passes the API key via `AI_API_KEY` environment variable (not the
  command line) and uses a bash array instead of `eval`.
- GitLab CI and Azure DevOps wrappers pass the API key via environment variables.
- CI release job creates the version tag and only force-pushes the floating `v1` tag.
- Pre-commit hook now runs on every commit (`always_run`) and documents the
  `AI_API_KEY` requirement.
- Config loader warns loudly about unknown keys instead of silently reverting to defaults.

[1.1.0]: https://github.com/edsoncarlosdevops/ai-context-generator/releases/tag/v1.1.0
[1.2.0]: https://github.com/edsoncarlosdevops/ai-context-generator/releases/tag/v1.2.0
