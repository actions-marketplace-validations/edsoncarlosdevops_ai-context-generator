import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeneratorConfig:
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    language: str = "english"
    max_lines: int = 150
    max_tokens: int = 4096


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
    exclude_dirs: list[str] = field(
        default_factory=lambda: [
            ".git",
            "node_modules",
            ".venv",
            "dist",
            "build",
            "__pycache__",
            ".mypy_cache",
        ]
    )
    max_file_size_kb: int = 100


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
            explicit_output_keys=set(out_data),
        )
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        return AppConfig()
