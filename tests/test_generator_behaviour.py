from pathlib import Path

from ai_context_generator.config import AppConfig
from ai_context_generator.generator import GITATTRIBUTES_START, ContextGenerator


class FakeLLM:
    def __init__(self, output: str = "New content\n"):
        self.output = output
        self.calls = 0
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return self.output


def test_second_run_on_unchanged_repo_makes_no_llm_call(tmp_path: Path):
    """Regression: bridge files and directories created by the first run used to
    change the profile, invalidating the signature and re-billing every run."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('x')\n")

    llm = FakeLLM("# Governance\n- rule one\n- rule two\n")
    generator = ContextGenerator(tmp_path, AppConfig(), llm)

    first = generator.generate()
    assert first.agents_md_written is True
    assert llm.calls == 1

    second = ContextGenerator(tmp_path, AppConfig(), llm).generate()
    assert llm.calls == 1, "signature must stay stable across runs"
    assert second.llm_called is False


def test_third_run_is_also_stable(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('x')\n")
    llm = FakeLLM("# Governance\n- rule\n")
    for _ in range(3):
        ContextGenerator(tmp_path, AppConfig(), llm).generate()
    assert llm.calls == 1


def test_structural_change_triggers_regeneration(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('x')\n")
    llm = FakeLLM("# Governance\n- rule\n")
    ContextGenerator(tmp_path, AppConfig(), llm).generate()
    assert llm.calls == 1

    # A new dependency is a real change in the project profile.
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    ContextGenerator(tmp_path, AppConfig(), llm).generate()
    assert llm.calls == 2


def test_hand_written_bridge_is_reported_as_skipped(tmp_path: Path):
    (tmp_path / ".cursorrules").write_text("# mine\n")
    result = ContextGenerator(tmp_path, AppConfig(), FakeLLM()).generate()

    assert ".cursorrules" in result.bridge_files_skipped
    assert ".cursorrules" not in result.bridge_files_written
    assert (tmp_path / ".cursorrules").read_text() == "# mine\n"


def test_gitattributes_block_is_written_once(tmp_path: Path):
    (tmp_path / "app.py").write_text("x\n")
    ContextGenerator(tmp_path, AppConfig(), FakeLLM()).generate()
    ContextGenerator(tmp_path, AppConfig(), FakeLLM()).generate()

    content = (tmp_path / ".gitattributes").read_text()
    assert content.count(GITATTRIBUTES_START) == 1


def test_gitattributes_preserves_user_content(tmp_path: Path):
    (tmp_path / ".gitattributes").write_text("*.png binary\n")
    ContextGenerator(tmp_path, AppConfig(), FakeLLM()).generate()

    content = (tmp_path / ".gitattributes").read_text()
    assert "*.png binary" in content
    assert GITATTRIBUTES_START in content


def test_gitattributes_can_be_disabled(tmp_path: Path):
    config = AppConfig()
    config.output.gitattributes = False
    ContextGenerator(tmp_path, config, FakeLLM()).generate()

    assert not (tmp_path / ".gitattributes").exists()


def test_replace_forces_regeneration(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# existing\n")
    llm = FakeLLM("# existing\n")  # identical output → normally skipped
    result = ContextGenerator(tmp_path, AppConfig(), llm).generate(force_replace=True)

    assert result.agents_md_written is True


def test_result_serialises_to_json_dict(tmp_path: Path):
    result = ContextGenerator(tmp_path, AppConfig(), FakeLLM()).generate()
    data = result.to_dict()

    assert data["agents_md_written"] is True
    assert isinstance(data["bridge_files_written"], list)
    assert "domain" in data


def test_prompt_receives_repository_evidence(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)\n")
    (tmp_path / "requirements.txt").write_text("fastapi\n")

    llm = FakeLLM()
    ContextGenerator(tmp_path, AppConfig(), llm).generate()

    prompt = llm.prompts[0]
    assert "src/main.py" in prompt
    assert "fastapi" in prompt
