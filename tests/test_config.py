from pathlib import Path

from ai_context_generator.config import DEFAULT_EXCLUDE_DIRS, load_config


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


def test_exclude_dirs_extends_defaults_instead_of_replacing(tmp_path: Path):
    """Replacing the list wholesale used to make a one-line config scan node_modules."""
    (tmp_path / ".ai_context.toml").write_text("[scan]\nexclude_dirs = ['my_generated']\n")

    config = load_config(tmp_path)

    assert "my_generated" in config.scan.exclude_dirs
    assert "node_modules" in config.scan.exclude_dirs
    assert ".git" in config.scan.exclude_dirs


def test_exclude_dirs_wrong_type_is_rejected(tmp_path: Path, capsys):
    (tmp_path / ".ai_context.toml").write_text("[scan]\nexclude_dirs = 'nope'\n")

    config = load_config(tmp_path)

    assert config.scan.exclude_dirs == DEFAULT_EXCLUDE_DIRS
    assert "must be a list" in capsys.readouterr().out


def test_invalid_generator_numbers_are_clamped(tmp_path: Path):
    (tmp_path / ".ai_context.toml").write_text(
        "[generator]\nmax_tokens = 0\nmax_lines = -3\nmax_retries = 0\n"
    )

    config = load_config(tmp_path)

    assert config.generator.max_tokens == 4096
    assert config.generator.max_lines == 150
    assert config.generator.max_retries == 3


def test_explicit_output_keys_ignore_typos(tmp_path: Path):
    """A typo must not count as an explicit choice that suppresses auto-detection."""
    (tmp_path / ".ai_context.toml").write_text("[output]\nclaude_md = true\nnot_a_flag = true\n")

    config = load_config(tmp_path)

    assert config.explicit_output_keys == {"claude_md"}


def test_output_section_is_opt_in(tmp_path: Path):
    (tmp_path / ".ai_context.toml").write_text("[output]\nclaude_md = true\n")

    config = load_config(tmp_path)

    assert config.output.claude_md is True
    assert config.output.cursorrules is False


def test_use_gitignore_defaults_on(tmp_path: Path):
    assert load_config(tmp_path).scan.use_gitignore is True
