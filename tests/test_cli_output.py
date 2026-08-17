import json
from pathlib import Path

from ai_context_generator.cli import _color_enabled, build_parser, main
from ai_context_generator.config import AppConfig, apply_env_overrides


def test_dry_run_json_is_machine_readable(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)\n")
    (tmp_path / "requirements.txt").write_text("fastapi\n")

    rc = main(["generate", "--workspace", str(tmp_path), "--dry-run", "--json"])
    assert rc == 0

    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True
    assert data["primary_language"] == "Python"
    assert data["domain"] == "web"
    assert data["entry_points"] == ["src/main.py"]


def test_json_error_output_on_missing_key(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / "app.py").write_text("x\n")

    rc = main(["generate", "--workspace", str(tmp_path), "--json"])
    assert rc == 1


def test_missing_config_file_is_an_error(tmp_path: Path, capsys):
    rc = main(["generate", "--workspace", str(tmp_path), "--config", str(tmp_path / "nope.toml")])
    assert rc == 1
    assert "Config file not found" in capsys.readouterr().err


def test_no_color_env_disables_ansi(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    assert _color_enabled() is False


def test_force_color_env_enables_ansi(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    assert _color_enabled() is True


def test_non_tty_output_has_no_escape_codes(tmp_path: Path, capsys, monkeypatch):
    """CI logs and piped output must stay clean."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    (tmp_path / "app.py").write_text("x\n")

    main(["generate", "--workspace", str(tmp_path), "--dry-run"])
    assert "\033[" not in capsys.readouterr().out


def test_env_overrides_are_applied(monkeypatch):
    monkeypatch.setenv("AI_CONTEXT_MODEL", "gpt-4o")
    monkeypatch.setenv("AI_CONTEXT_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("AI_CONTEXT_LANGUAGE", "portuguese")

    config = apply_env_overrides(AppConfig())

    assert config.generator.model == "gpt-4o"
    assert config.generator.base_url == "http://localhost:11434/v1"
    assert config.generator.language == "portuguese"


def test_cli_flags_beat_env_overrides(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("AI_CONTEXT_MODEL", "from-env")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    (tmp_path / "app.py").write_text("x\n")

    main(["generate", "--workspace", str(tmp_path), "--dry-run", "--model", "from-flag"])
    # The model is not printed in dry-run, so assert via the parsed config path.
    from ai_context_generator.cli import _apply_cli_overrides
    from ai_context_generator.config import load_config

    args = build_parser().parse_args(["generate", "--model", "from-flag"])
    config = _apply_cli_overrides(apply_env_overrides(load_config(tmp_path)), args)
    assert config.generator.model == "from-flag"


def test_zero_valued_numeric_flags_are_honoured(tmp_path: Path):
    """`if args.timeout:` silently dropped an explicit 0."""
    from ai_context_generator.cli import _apply_cli_overrides

    args = build_parser().parse_args(["generate", "--max-files", "0", "--timeout", "0"])
    config = _apply_cli_overrides(AppConfig(), args)

    assert config.scan.max_files == 0
    assert config.generator.timeout == 0


def test_no_bridge_disables_every_bridge(tmp_path: Path):
    from ai_context_generator.cli import _apply_cli_overrides
    from ai_context_generator.config import BRIDGE_FLAG_TO_TOOL

    args = build_parser().parse_args(["generate", "--no-bridge"])
    config = _apply_cli_overrides(AppConfig(), args)

    assert all(getattr(config.output, flag) is False for flag in BRIDGE_FLAG_TO_TOOL)
    assert config.output.agents_md is True


def test_no_gitignore_flag(tmp_path: Path):
    from ai_context_generator.cli import _apply_cli_overrides

    args = build_parser().parse_args(["generate", "--no-gitignore"])
    assert _apply_cli_overrides(AppConfig(), args).scan.use_gitignore is False


def test_end_to_end_generate_writes_files(tmp_path: Path, capsys, monkeypatch):
    """Full CLI path with a stubbed LLM: report rendering, outputs, exit code."""
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)\n")
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    (tmp_path / ".cursorrules").write_text("# hand written\n")

    class StubLLM:
        last_usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5})()

        def __init__(self, *args, **kwargs):
            pass

        def generate(self, prompt: str) -> str:
            return "# Governance\n- rule\n"

    monkeypatch.setattr("ai_context_generator.cli.LLMClient", StubLLM)

    rc = main(["generate", "--workspace", str(tmp_path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert (tmp_path / "AGENTS.md").read_text() == "# Governance\n- rule\n"
    assert "AGENTS.md written" in out
    assert "hand-written file, not overwritten" in out
    assert "Tokens used: 10 prompt" in out
    # The user's own file is untouched.
    assert (tmp_path / ".cursorrules").read_text() == "# hand written\n"
    # Only Cursor is configured in this repo, so no other bridge is introduced.
    assert not (tmp_path / "CLAUDE.md").exists()


def test_first_run_on_clean_repo_generates_every_bridge(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    (tmp_path / "app.py").write_text("print(1)\n")

    class StubLLM:
        last_usage = None

        def __init__(self, *args, **kwargs):
            pass

        def generate(self, prompt: str) -> str:
            return "# Governance\n"

    monkeypatch.setattr("ai_context_generator.cli.LLMClient", StubLLM)

    assert main(["generate", "--workspace", str(tmp_path)]) == 0
    for bridge in (".cursorrules", "CLAUDE.md", ".github/copilot-instructions.md"):
        assert (tmp_path / bridge).exists(), bridge


def test_end_to_end_json_summary(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    (tmp_path / "app.py").write_text("print(1)\n")

    class StubLLM:
        last_usage = None

        def __init__(self, *args, **kwargs):
            pass

        def generate(self, prompt: str) -> str:
            return "# Governance\n"

    monkeypatch.setattr("ai_context_generator.cli.LLMClient", StubLLM)

    rc = main(["generate", "--workspace", str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["ok"] is True
    assert data["agents_md_written"] is True


def test_generate_failure_is_reported(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    (tmp_path / "app.py").write_text("x\n")

    class BoomLLM:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("provider unreachable")

    monkeypatch.setattr("ai_context_generator.cli.LLMClient", BoomLLM)

    assert main(["generate", "--workspace", str(tmp_path)]) == 1
    assert "provider unreachable" in capsys.readouterr().err


def test_github_outputs_and_summary_are_written(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    summary = tmp_path / "summary.md"
    output = tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "app.py").write_text("x\n")

    class StubLLM:
        last_usage = None

        def __init__(self, *args, **kwargs):
            pass

        def generate(self, prompt: str) -> str:
            return "# Governance\n"

    monkeypatch.setattr("ai_context_generator.cli.LLMClient", StubLLM)

    assert main(["generate", "--workspace", str(workspace)]) == 0
    assert "agents_md_written=true" in output.read_text()
    assert "ai-context-generator Results" in summary.read_text()
