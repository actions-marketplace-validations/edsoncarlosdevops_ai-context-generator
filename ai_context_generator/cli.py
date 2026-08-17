import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ai_context_generator import __version__
from ai_context_generator.analyzer import ProjectAnalyzer
from ai_context_generator.config import (
    BRIDGE_FLAG_TO_TOOL,
    AppConfig,
    apply_env_overrides,
    load_config,
)
from ai_context_generator.generator import ContextGenerator, GenerationResult
from ai_context_generator.llm_client import LLMClient
from ai_context_generator.prompt_builder import PromptBuilder
from ai_context_generator.scanner import CodebaseScanner

PROMPT_PREVIEW_LINES = 30


def _color_enabled(stream: object = None) -> bool:
    """Respect NO_COLOR, FORCE_COLOR and non-TTY output (CI logs, pipes)."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or os.environ.get("GITHUB_ACTIONS"):
        return True
    target = stream if stream is not None else sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def _c(code: str, text: str, stream: object = None) -> str:
    return f"\033[{code}m{text}\033[0m" if _color_enabled(stream) else text


def _load_env_file(workspace_path: Path) -> None:
    """Load API keys from a `.env` file next to the workspace (optional)."""
    env_path = workspace_path / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    # Also honour a `.env` in the current directory for convenience.
    load_dotenv(override=False)


def _print_ok(msg: str) -> None:
    print(f"  {_c('32', '✓')} {msg}")


def _print_skip(msg: str) -> None:
    print(f"  {_c('33', '⊘')} {msg}")


def _print_err(msg: str) -> None:
    # GitHub Actions annotation
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::error::{msg}")
    print(f"  {_c('31', '✗', sys.stderr)} {msg}", file=sys.stderr)


def _print_warn(msg: str) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning::{msg}")
    print(f"  {_c('33', '!')} {msg}")


def _github_notice(msg: str) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::notice::{msg}")


def _github_summary(text: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    try:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError as e:  # never fail the run because a summary could not be written
        print(f"  [warn] Could not write GitHub step summary: {e}")


def _github_output(key: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    try:
        with open(output_path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
    except OSError:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-context-generator",
        description="Scan a repository and generate AGENTS.md and AI context bridge files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    gen = subparsers.add_parser("generate", help="Generate AI context files")

    gen.add_argument(
        "--workspace", default=".", help="Path to the repository root (default: current directory)"
    )
    gen.add_argument("--config", help="Path to .ai_context.toml")
    gen.add_argument("--api-key", help="LLM API key (or env var AI_API_KEY / OPENAI_API_KEY)")
    gen.add_argument(
        "--base-url", help="Custom LLM base URL (e.g. http://localhost:11434/v1 for Ollama)"
    )
    gen.add_argument("--model", help="LLM model override (e.g. gpt-4o, deepseek-chat, llama3)")
    gen.add_argument(
        "--language", help="Output language: english, portuguese, spanish, french, german"
    )
    gen.add_argument(
        "--max-files",
        type=int,
        help="Hard cap on the number of files scanned (default from config: 100000)",
    )
    gen.add_argument(
        "--timeout",
        type=float,
        help="Timeout in seconds for each LLM API call (default from config: 120)",
    )
    gen.add_argument(
        "--max-retries",
        type=int,
        help="Attempts for retryable LLM errors (default from config: 3)",
    )
    gen.add_argument(
        "--replace", action="store_true", help="Replace existing AGENTS.md instead of enriching"
    )
    gen.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview scan results and generated prompt without writing any files",
    )
    gen.add_argument(
        "--no-bridge",
        action="store_true",
        help="Skip generating all AI tool bridge files (.cursorrules, CLAUDE.md, etc.)",
    )
    gen.add_argument(
        "--no-gitignore",
        action="store_true",
        help="Do not derive extra excluded directories from the repository .gitignore",
    )
    gen.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print a machine-readable JSON summary instead of the human report",
    )
    return parser


def _apply_cli_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    """CLI flags win over environment variables, which win over the config file."""
    if args.model:
        config.generator.model = args.model
    if args.language:
        config.generator.language = args.language
    if args.base_url:
        config.generator.base_url = args.base_url
    if args.timeout is not None:
        config.generator.timeout = args.timeout
    if args.max_retries is not None:
        config.generator.max_retries = args.max_retries
    if args.max_files is not None:
        config.scan.max_files = args.max_files
    if args.no_gitignore:
        config.scan.use_gitignore = False

    if args.no_bridge:
        for flag in BRIDGE_FLAG_TO_TOOL:
            setattr(config.output, flag, False)
        # Treat these as explicit user choices so auto-detection does not re-enable them.
        config.explicit_output_keys.update(BRIDGE_FLAG_TO_TOOL.keys())
    return config


def _run_dry_run(workspace_path: Path, config: AppConfig, as_json: bool) -> int:
    scanner = CodebaseScanner(
        workspace_path,
        config.scan.exclude_dirs,
        config.scan.max_file_size_kb,
        config.scan.max_files,
        config.scan.use_gitignore,
    )
    scan = scanner.scan()
    profile = ProjectAnalyzer().analyze(scan)
    prompt = PromptBuilder(config).build(profile)

    if as_json:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "scanned_files": scan.total_files,
                    "scan_truncated": scan.truncated,
                    "primary_language": profile.primary_language,
                    "language_breakdown": profile.language_breakdown,
                    "frameworks": profile.frameworks,
                    "infra_tools": profile.infra_tools,
                    "cicd_platforms": profile.cicd_platforms,
                    "domain": profile.domain,
                    "security_risk_level": profile.security_risk_level,
                    "architecture_hints": profile.architecture_hints,
                    "has_tests": profile.has_tests,
                    "test_commands": profile.test_commands,
                    "build_commands": profile.build_commands,
                    "entry_points": profile.entry_points,
                    "detected_ai_tools": scan.detected_ai_tools,
                    "prompt_chars": len(prompt),
                },
                indent=2,
            )
        )
        return 0

    total = sum(scan.language_counts.values()) or 1
    top_langs = sorted(scan.language_counts.items(), key=lambda x: (-x[1], x[0]))[:4]
    lang_str = ", ".join(f"{lang} ({int(c / total * 100)}%)" for lang, c in top_langs)

    print("\n" + _c("1", "ai-context-generator — Dry Run Preview"))
    print("=" * 50)
    print("\n" + _c("1", "Scan Results"))
    print(f"  Files scanned   : {scan.total_files}{' (truncated)' if scan.truncated else ''}")
    print(f"  Languages       : {lang_str or 'None detected'}")
    print(f"  Frameworks      : {', '.join(profile.frameworks) or 'None detected'}")
    print(f"  Infra tools     : {', '.join(profile.infra_tools) or 'None detected'}")
    print(f"  CI/CD           : {', '.join(profile.cicd_platforms) or 'None detected'}")
    print(f"  Architecture    : {', '.join(profile.architecture_hints) or 'None detected'}")
    print(f"  Domain          : {profile.domain}")
    print(f"  Security risk   : {profile.security_risk_level}")
    print(f"  Tests detected  : {'Yes' if profile.has_tests else 'No'}")
    print(f"  Test commands   : {', '.join(profile.test_commands) or 'None detected'}")
    print(f"  Entry points    : {', '.join(profile.entry_points) or 'None detected'}")
    print(
        f"  AI tools found  : {', '.join(scan.detected_ai_tools) or 'None (all bridges would be generated)'}"
    )
    print(
        f"  Existing AGENTS : {'Yes — enrich mode' if scan.existing_agents_md else 'No — create from scratch'}"
    )

    lines = prompt.splitlines()
    print("\n" + _c("1", "Prompt Preview") + f" ({len(lines)} lines, {len(prompt)} chars)")
    print("-" * 50)
    for line in lines[:PROMPT_PREVIEW_LINES]:
        print(f"  {line}")
    if len(lines) > PROMPT_PREVIEW_LINES:
        print(f"  ... ({len(lines) - PROMPT_PREVIEW_LINES} more lines)")
    print("\n" + _c("33", "[dry-run] No files were written.") + "\n")
    return 0


def _report(result: GenerationResult) -> None:
    _print_ok(f"Scanned {result.scanned_files} files — {result.language_percentages}")
    if result.scan_truncated:
        _print_warn("Scan hit the max_files limit — results are partial. Raise --max-files.")

    detected = [*result.frameworks, *result.infra_tools, *result.cicd]
    if detected:
        _print_ok(f"Detected: {', '.join(detected)}")

    if result.agents_md_written:
        _print_ok(f"AGENTS.md written ({result.agents_md_lines} lines)")
        _github_notice(f"AGENTS.md generated: {result.agents_md_lines} lines")
    else:
        _print_skip(f"AGENTS.md: {result.message}")

    for bf in result.bridge_files_written:
        _print_ok(f"{bf} → created")
    for bf in result.bridge_files_skipped:
        _print_skip(f"{bf} → kept (hand-written file, not overwritten)")

    if result.llm_called and result.prompt_tokens:
        _print_ok(
            f"Tokens used: {result.prompt_tokens} prompt + {result.completion_tokens} completion"
        )

    summary_lines = [
        "## ai-context-generator Results",
        "| Key | Value |",
        "|-----|-------|",
        f"| Files scanned | {result.scanned_files} |",
        f"| Languages | {result.language_percentages or 'None'} |",
        f"| Domain | {result.domain} |",
        f"| Frameworks | {', '.join(result.frameworks) or 'None'} |",
        f"| AGENTS.md | {'✅ Written (' + str(result.agents_md_lines) + ' lines)' if result.agents_md_written else '⊘ ' + result.message} |",
        f"| Bridge files | {', '.join(result.bridge_files_written) or 'None'} |",
        f"| Skipped (hand-written) | {', '.join(result.bridge_files_skipped) or 'None'} |",
    ]
    _github_summary("\n".join(summary_lines))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "generate":
        parser.print_help()
        return 0

    workspace_path = Path(args.workspace).resolve()
    if not workspace_path.is_dir():
        _print_err(f"Workspace not found: {workspace_path}")
        return 1

    # Environment is loaded before the config so AI_CONTEXT_* overrides apply to
    # both dry runs and real runs.
    _load_env_file(workspace_path)

    config_path = Path(args.config).resolve() if args.config else None
    if config_path is not None and not config_path.is_file():
        _print_err(f"Config file not found: {config_path}")
        return 1
    config = apply_env_overrides(load_config(workspace_path, config_path))
    config = _apply_cli_overrides(config, args)

    if args.dry_run:
        return _run_dry_run(workspace_path, config, args.as_json)

    api_key = args.api_key or os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        _print_err(
            "API key required. Pass --api-key, set AI_API_KEY / OPENAI_API_KEY, "
            "or add AI_API_KEY to a .env file in your workspace root."
        )
        _print_err("Supported providers: DeepSeek, OpenAI, Anthropic, Ollama (local)")
        return 1

    if not args.as_json:
        print("\n" + _c("1", "ai-context-generator"))
        print(f"  Workspace: {workspace_path}")
        print(f"  Model    : {config.generator.model}")
        print(f"  Language : {config.generator.language}")
        print(f"  Timeout  : {config.generator.timeout}s")
        print(f"  Max files: {config.scan.max_files}\n")

    try:
        llm = LLMClient(
            api_key,
            config.generator.model,
            config.generator.base_url,
            config.generator.max_tokens,
            config.generator.timeout,
            config.generator.max_retries,
        )
        generator = ContextGenerator(workspace_path, config, llm)
        result = generator.generate(force_replace=args.replace)
    except Exception as e:
        if args.as_json:
            print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        else:
            _print_err(str(e))
        return 1

    _github_output("agents_md_written", "true" if result.agents_md_written else "false")

    if args.as_json:
        print(json.dumps({"ok": True, **result.to_dict()}, indent=2))
        return 0

    _report(result)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
