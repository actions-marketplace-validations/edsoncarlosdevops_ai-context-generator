import os
from pathlib import Path

from core.cli import _load_env_file, main


def test_missing_workspace_returns_error(tmp_path: Path, capsys):
    rc = main(["generate", "--workspace", str(tmp_path / "does-not-exist")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Workspace not found" in err


def test_dry_run_no_config_writes_nothing(tmp_path: Path, capsys):
    (tmp_path / "hello.py").write_text("def main():\n    print('hi')\n")
    rc = main(["generate", "--workspace", str(tmp_path), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Dry Run Preview" in out
    assert "No files were written" in out
    assert not (tmp_path / "AGENTS.md").exists()


def test_dry_run_respects_custom_config(tmp_path: Path, capsys):
    (tmp_path / "main.py").write_text("print('x')\n")
    (tmp_path / ".ai_context.toml").write_text("[generator]\nmodel = 'gpt-4o'\n")
    rc = main(["generate", "--workspace", str(tmp_path), "--dry-run"])
    assert rc == 0


def test_generate_requires_api_key(tmp_path: Path, capsys, monkeypatch):
    (tmp_path / "main.py").write_text("print('x')\n")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rc = main(["generate", "--workspace", str(tmp_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "API key required" in err


def test_env_file_is_loaded(tmp_path: Path, monkeypatch):
    (tmp_path / ".env").write_text("AI_API_KEY=sk-from-dotenv\n")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    _load_env_file(tmp_path)
    assert os.environ.get("AI_API_KEY") == "sk-from-dotenv"


def test_env_file_does_not_override_existing_env(tmp_path: Path, monkeypatch):
    (tmp_path / ".env").write_text("AI_API_KEY=sk-from-dotenv\n")
    monkeypatch.setenv("AI_API_KEY", "sk-from-env")
    _load_env_file(tmp_path)
    assert os.environ["AI_API_KEY"] == "sk-from-env"


def test_cli_module_runs_dry_run(tmp_path: Path, capsys):
    """The entry point used by the GitHub Action (`python -m core.cli`)."""
    (tmp_path / "app.py").write_text("print('x')\n")
    rc = main(["generate", "--workspace", str(tmp_path), "--dry-run"])
    assert rc == 0
