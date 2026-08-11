import argparse
import json
import os
import sys
from pathlib import Path

from core.config import load_config
from core.llm_client import LLMClient
from core.generator import ContextGenerator
from core.scanner import CodebaseScanner
from core.analyzer import ProjectAnalyzer
from core.prompt_builder import PromptBuilder


def _print_ok(msg: str) -> None:
    print(f"  \033[32m✓\033[0m {msg}")


def _print_skip(msg: str) -> None:
    print(f"  \033[33m⊘\033[0m {msg}")


def _print_err(msg: str) -> None:
    # GitHub Actions annotation
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::error::{msg}")
    print(f"  \033[31m✗\033[0m {msg}", file=sys.stderr)


def _github_notice(msg: str) -> None:
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::notice::{msg}")


def _github_summary(text: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(text + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ai-context-generator",
        description="Scan a repository and generate AGENTS.md and AI context bridge files.",
    )
    subparsers = parser.add_subparsers(dest="command")
    gen = subparsers.add_parser("generate", help="Generate AI context files")

    gen.add_argument("--workspace", default=".", help="Path to the repository root (default: current directory)")
    gen.add_argument("--config", help="Path to .ai_context.toml")
    gen.add_argument("--api-key", help="LLM API key (or env var AI_API_KEY / OPENAI_API_KEY)")
    gen.add_argument("--base-url", help="Custom LLM base URL (e.g. http://localhost:11434/v1 for Ollama)")
    gen.add_argument("--model", help="LLM model override (e.g. gpt-4o, deepseek-chat, llama3)")
    gen.add_argument("--language", help="Output language: english, portuguese, spanish, french, german")
    gen.add_argument("--replace", action="store_true", help="Replace existing AGENTS.md instead of enriching")
    gen.add_argument("--dry-run", action="store_true", help="Preview scan results and generated prompt without writing any files")
    gen.add_argument("--no-bridge", action="store_true", help="Skip generating all AI tool bridge files (.cursorrules, CLAUDE.md, etc.)")

    args = parser.parse_args()

    if args.command != "generate":
        parser.print_help()
        return 0

    workspace_path = Path(args.workspace).resolve()
    if not workspace_path.is_dir():
        _print_err(f"Workspace not found: {workspace_path}")
        return 1

    config_path = Path(args.config).resolve() if args.config else None
    config = load_config(workspace_path, config_path)

    # CLI overrides
    if args.model:
        config.generator.model = args.model
    if args.language:
        config.generator.language = args.language
    if args.base_url:
        config.generator.base_url = args.base_url

    if args.no_bridge:
        config.output.cursorrules = False
        config.output.windsurfrules = False
        config.output.clinerules = False
        config.output.zed_rules = False
        config.output.aider_conventions = False
        config.output.claude_md = False
        config.output.copilot_instructions = False
        config.output.amazonq_rules = False
        config.output.continue_rules = False

    # --- DRY RUN MODE ---
    if args.dry_run:
        print("\n\033[1mai-context-generator — Dry Run Preview\033[0m")
        print("=" * 50)

        scanner = CodebaseScanner(workspace_path, config.scan.exclude_dirs, config.scan.max_file_size_kb)
        scan = scanner.scan()
        analyzer = ProjectAnalyzer()
        profile = analyzer.analyze(scan)

        total = sum(scan.language_counts.values()) or 1
        top_langs = sorted(scan.language_counts.items(), key=lambda x: x[1], reverse=True)[:4]
        lang_str = ", ".join(f"{l} ({int(c/total*100)}%)" for l, c in top_langs)

        print(f"\n\033[1mScan Results\033[0m")
        print(f"  Files scanned   : {scan.total_files}")
        print(f"  Languages       : {lang_str}")
        print(f"  Frameworks      : {', '.join(profile.frameworks) or 'None detected'}")
        print(f"  Infra tools     : {', '.join(profile.infra_tools) or 'None detected'}")
        print(f"  CI/CD           : {', '.join(profile.cicd_platforms) or 'None detected'}")
        print(f"  Domain          : {profile.domain}")
        print(f"  Security risk   : {profile.security_risk_level}")
        print(f"  AI tools found  : {', '.join(scan.detected_ai_tools) or 'None (all bridges would be generated)'}")
        print(f"  Existing AGENTS : {'Yes — enrich mode' if scan.existing_agents_md else 'No — create from scratch'}")

        builder = PromptBuilder(config)
        prompt = builder.build(profile)
        print(f"\n\033[1mPrompt Preview\033[0m ({len(prompt.splitlines())} lines, {len(prompt)} chars)")
        print("-" * 50)
        for line in prompt.splitlines()[:30]:
            print(f"  {line}")
        if len(prompt.splitlines()) > 30:
            print(f"  ... ({len(prompt.splitlines()) - 30} more lines)")
        print("\n\033[33m[dry-run] No files were written.\033[0m\n")
        return 0

    # --- GENERATE MODE ---
    api_key = args.api_key or os.environ.get("AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        _print_err("API key required. Pass --api-key or set AI_API_KEY environment variable.")
        _print_err("Supported providers: DeepSeek, OpenAI, Anthropic, Ollama (local)")
        return 1

    print("\n\033[1mai-context-generator\033[0m")
    print(f"  Workspace: {workspace_path}")
    print(f"  Model    : {config.generator.model}")
    print(f"  Language : {config.generator.language}\n")

    try:
        llm = LLMClient(api_key, config.generator.model, config.generator.base_url)
        generator = ContextGenerator(workspace_path, config, llm)
        result = generator.generate(force_replace=args.replace)
    except Exception as e:
        _print_err(str(e))
        return 1

    # Print results
    _print_ok(f"Scanned {result.scanned_files} files — {result.language_percentages}")

    detected = [*result.frameworks, *result.cicd]
    if detected:
        _print_ok(f"Detected: {', '.join(detected)}")

    if result.agents_md_written:
        _print_ok(f"AGENTS.md written ({result.agents_md_lines} lines)")
        _github_notice(f"AGENTS.md generated: {result.agents_md_lines} lines")
    else:
        _print_skip(f"AGENTS.md: {result.message}")

    for bf in result.bridge_files_written:
        _print_ok(f"{bf} → created")

    # GitHub Step Summary
    summary_lines = [
        "## ai-context-generator Results",
        f"| Key | Value |",
        f"|-----|-------|",
        f"| Files scanned | {result.scanned_files} |",
        f"| Languages | {result.language_percentages} |",
        f"| Frameworks | {', '.join(result.frameworks) or 'None'} |",
        f"| AGENTS.md | {'✅ Written (' + str(result.agents_md_lines) + ' lines)' if result.agents_md_written else '⊘ ' + result.message} |",
        f"| Bridge files | {', '.join(result.bridge_files_written) or 'None'} |",
    ]
    _github_summary("\n".join(summary_lines))

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
