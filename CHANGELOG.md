# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
