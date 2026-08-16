from pathlib import Path

from core.config import load_config


def test_unknown_keys_warn_but_keep_valid(tmp_path: Path, capsys):
    (tmp_path / ".ai_context.toml").write_text(
        "[generator]\nmodel = 'gpt-4o'\nmax_line = 500\n\n"
        "[output]\ncursorrules = false\n\n"
        "[scan]\nunknown_opt = 1\n"
    )

    config = load_config(tmp_path)

    assert config.generator.model == "gpt-4o"
    assert config.output.cursorrules is False
    assert config.explicit_output_keys == {"cursorrules"}
    warnings = capsys.readouterr().out
    assert "max_line" in warnings
    assert "unknown_opt" in warnings


def test_missing_config_returns_defaults(tmp_path: Path):
    config = load_config(tmp_path)

    assert config.generator.model == "deepseek-chat"
    assert config.generator.max_tokens == 4096
    assert config.explicit_output_keys == set()


def test_custom_config_file(tmp_path: Path):
    custom = tmp_path / "custom.toml"
    custom.write_text("[generator]\nmodel = 'claude-3-5-sonnet-20241022'\nmax_tokens = 8000\n")

    config = load_config(tmp_path, custom)

    assert config.generator.model == "claude-3-5-sonnet-20241022"
    assert config.generator.max_tokens == 8000


def test_timeout_and_max_files_parsing(tmp_path: Path):
    (tmp_path / ".ai_context.toml").write_text(
        "[generator]\ntimeout = 30\n\n[scan]\nmax_files = 5000\n"
    )

    config = load_config(tmp_path)

    assert config.generator.timeout == 30.0
    assert config.scan.max_files == 5000


def test_invalid_timeout_and_max_files_are_clamped(tmp_path: Path):
    (tmp_path / ".ai_context.toml").write_text(
        "[generator]\ntimeout = -5\n\n[scan]\nmax_files = -1\n"
    )

    config = load_config(tmp_path)

    assert config.generator.timeout == 120.0  # default restored
    assert config.scan.max_files == 100000  # default restored
