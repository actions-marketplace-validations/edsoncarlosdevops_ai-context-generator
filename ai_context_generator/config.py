import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Environment variables that override generator defaults. Documented in .env.example.
ENV_OVERRIDES: dict[str, str] = {
    "AI_CONTEXT_MODEL": "model",
    "AI_CONTEXT_BASE_URL": "base_url",
    "AI_CONTEXT_LANGUAGE": "language",
}

DEFAULT_EXCLUDE_DIRS: list[str] = [
    # VCS & editors
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    # Python
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "site-packages",
    "htmlcov",
    "*.egg-info",
    # JavaScript / TypeScript
    "node_modules",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    ".parcel-cache",
    "bower_components",
    # Build output
    "dist",
    "build",
    "out",
    "target",
    "bin",
    "obj",
    "coverage",
    ".gradle",
    # Go / PHP / Rust vendoring
    "vendor",
    # Infrastructure caches
    ".terraform",
    ".serverless",
    # Misc
    ".cache",
    ".DS_Store",
]


@dataclass
class GeneratorConfig:
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    language: str = "english"
    max_lines: int = 150
    max_tokens: int = 4096
    timeout: float = 120.0  # seconds for each LLM API call
    max_retries: int = 3


@dataclass
class OutputConfig:
    """Controls which bridge files are generated. All default to True for maximum compatibility."""

    agents_md: bool = True

    # IDE / AI coding assistants
    cursorrules: bool = True  # Cursor IDE
    windsurfrules: bool = True  # Windsurf (Codeium)
    clinerules: bool = True  # Cline (VS Code)
    zed_rules: bool = True  # Zed AI
    aider_conventions: bool = True  # Aider CLI
    claude_md: bool = True  # Claude Code (Anthropic)
    copilot_instructions: bool = True  # GitHub Copilot
    amazonq_rules: bool = True  # Amazon Q Developer
    continue_rules: bool = True  # Continue.dev

    # CI/CD integration
    create_pr: bool = False
    # Write linguist-generated markers so bridge files collapse in GitHub diffs.
    gitattributes: bool = True


# Maps each bridge flag to the tool name reported by the scanner. Used to
# auto-select bridge files for tools actually present in a repository.
BRIDGE_FLAG_TO_TOOL: dict[str, str] = {
    "cursorrules": "cursor",
    "windsurfrules": "windsurf",
    "clinerules": "cline",
    "zed_rules": "zed",
    "aider_conventions": "aider",
    "claude_md": "claude",
    "copilot_instructions": "copilot",
    "amazonq_rules": "amazonq",
    "continue_rules": "continue",
}


@dataclass
class ScanConfig:
    exclude_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE_DIRS))
    max_file_size_kb: int = 100
    max_files: int = 100000  # hard cap to keep scanning predictable on huge monorepos
    use_gitignore: bool = True  # also skip plain directory names listed in .gitignore


@dataclass
class AppConfig:
    generator: GeneratorConfig = field(default_factory=GeneratorConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    scan: ScanConfig = field(default_factory=ScanConfig)
    # Keys the user set explicitly (via .ai_context.toml / CLI flags) so that
    # auto-detection never overrides an intentional configuration.
    explicit_output_keys: set[str] = field(default_factory=set)


def _filter_known(section: str, data: dict, fields: set[str]) -> dict:
    """Keep known keys, warn loudly on typos instead of silently dropping the section."""
    unknown = set(data) - fields
    for key in sorted(unknown):
        print(f"Warning: unknown option '{key}' in [{section}] of the config — ignoring it.")
    return {k: v for k, v in data.items() if k in fields}


def apply_env_overrides(config: AppConfig) -> AppConfig:
    """Apply AI_CONTEXT_* environment variables on top of the file config.

    Precedence is env < CLI flags: the CLI applies its own overrides afterwards.
    """
    for env_name, attr in ENV_OVERRIDES.items():
        value = os.environ.get(env_name)
        if value:
            setattr(config.generator, attr, value)
    return config


def load_config(workspace_path: Path, config_path: Path | None = None) -> AppConfig:
    if config_path is None:
        config_path = workspace_path / ".ai_context.toml"

    if not config_path.exists():
        return AppConfig()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        gen_fields = set(GeneratorConfig.__dataclass_fields__)
        out_fields = set(OutputConfig.__dataclass_fields__)
        scan_fields = set(ScanConfig.__dataclass_fields__)

        gen_data = _filter_known("generator", data.get("generator", {}), gen_fields)
        out_data = data.get("output", {})
        scan_data = _filter_known("scan", data.get("scan", {}), scan_fields)

        # Sanity-clamp numeric values so a broken config can't hang the tool.
        if "timeout" in gen_data and gen_data["timeout"] <= 0:
            gen_data["timeout"] = GeneratorConfig.timeout
        if "max_tokens" in gen_data and gen_data["max_tokens"] <= 0:
            gen_data["max_tokens"] = GeneratorConfig.max_tokens
        if "max_lines" in gen_data and gen_data["max_lines"] <= 0:
            gen_data["max_lines"] = GeneratorConfig.max_lines
        if "max_retries" in gen_data and gen_data["max_retries"] < 1:
            gen_data["max_retries"] = GeneratorConfig.max_retries
        if "max_files" in scan_data and scan_data["max_files"] <= 0:
            scan_data["max_files"] = ScanConfig.max_files
        if "max_file_size_kb" in scan_data and scan_data["max_file_size_kb"] <= 0:
            scan_data["max_file_size_kb"] = ScanConfig.max_file_size_kb

        # `exclude_dirs` extends the defaults instead of replacing them, so a user
        # who adds one directory does not silently start scanning node_modules.
        if "exclude_dirs" in scan_data:
            extra = scan_data["exclude_dirs"]
            if isinstance(extra, list):
                scan_data["exclude_dirs"] = sorted({*DEFAULT_EXCLUDE_DIRS, *map(str, extra)})
            else:
                print("Warning: [scan] exclude_dirs must be a list — ignoring it.")
                scan_data.pop("exclude_dirs")

        # Bridge semantics: if [output] section exists, any bridge flag
        # the user did NOT list is treated as disabled (opt-in model).
        # This prevents generating 9 files when the user only wanted 3.
        bridge_flags = set(BRIDGE_FLAG_TO_TOOL.keys())
        if out_data:
            defaults_off = {flag: False for flag in bridge_flags if flag not in out_data}
            merged_out = {**defaults_off, **_filter_known("output", out_data, out_fields)}
        else:
            merged_out = {}

        return AppConfig(
            generator=GeneratorConfig(**gen_data),
            output=OutputConfig(**merged_out),
            scan=ScanConfig(**scan_data),
            explicit_output_keys=set(out_data) & out_fields,
        )
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        return AppConfig()
