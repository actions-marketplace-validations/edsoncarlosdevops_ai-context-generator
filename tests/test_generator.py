from pathlib import Path

from core.config import AppConfig
from core.generator import ContextGenerator


class FakeLLM:
    def __init__(self, output: str = "New content\n"):
        self.output = output
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return self.output


def test_skips_llm_when_signature_unchanged(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# v1\n")
    (tmp_path / ".ai-context.sig").write_text("dummy\n")

    config = AppConfig()
    llm = FakeLLM()
    generator = ContextGenerator(tmp_path, config, llm)

    first = generator.generate()
    assert llm.calls == 1
    assert first.agents_md_written is True

    llm.calls = 0
    second = generator.generate()
    assert llm.calls == 0
    assert second.agents_md_written is False
    assert "up-to-date" in second.message


def test_creates_bridges_even_when_agents_skipped(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# v1\n")

    config = AppConfig()
    llm = FakeLLM("almost same\n# v1\n")
    generator = ContextGenerator(tmp_path, config, llm)

    generator.generate()

    # Bridges are independent of the AGENTS.md write decision.
    assert (tmp_path / ".cursorrules").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".github/copilot-instructions.md").exists()


def test_explicit_config_disables_bridge_despite_detection(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# claude\n")
    (tmp_path / "AGENTS.md").write_text("# v1\n")

    config = AppConfig()
    config.output.clinerules = False  # explicit user choice
    config.explicit_output_keys.add("clinerules")
    llm = FakeLLM("completely different content for enrichment\n")
    generator = ContextGenerator(tmp_path, config, llm)

    generator.generate()

    assert not (tmp_path / ".clinerules").exists()
    assert (tmp_path / "CLAUDE.md").exists()


def test_antigravity_does_not_suppress_bridges(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# hand written\n")

    config = AppConfig()
    llm = FakeLLM("generated content that is totally different from the hand written file\n")
    generator = ContextGenerator(tmp_path, config, llm)

    generator.generate()

    # Even though only AGENTS.md exists, all default bridges are generated.
    assert (tmp_path / ".cursorrules").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".windsurfrules").exists()


def test_never_overwrites_user_bridge_files(tmp_path: Path):
    user_cursorrules = "# my hand-written rules\n- keep it simple\n"
    (tmp_path / ".cursorrules").write_text(user_cursorrules)

    config = AppConfig()
    llm = FakeLLM("generated content that differs a lot from nothing here\n")
    generator = ContextGenerator(tmp_path, config, llm)

    generator.generate()

    assert (tmp_path / ".cursorrules").read_text() == user_cursorrules
