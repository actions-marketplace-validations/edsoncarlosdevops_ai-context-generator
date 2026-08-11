import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeneratorConfig:
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    language: str = "english"
    max_lines: int = 150


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


def load_config(workspace_path: Path, config_path: Path | None = None) -> AppConfig:
    if config_path is None:
        config_path = workspace_path / ".ai_context.toml"

    if not config_path.exists():
        return AppConfig()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        gen_data = data.get("generator", {})
        out_data = data.get("output", {})
        scan_data = data.get("scan", {})

        return AppConfig(
            generator=GeneratorConfig(**gen_data),
            output=OutputConfig(**out_data),
            scan=ScanConfig(**scan_data),
        )
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}")
        return AppConfig()
