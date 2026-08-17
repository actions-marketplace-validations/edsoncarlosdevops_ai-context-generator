from pathlib import Path

from ai_context_generator.analyzer import ProjectProfile
from ai_context_generator.bridge_writer import BridgeWriter
from ai_context_generator.config import OutputConfig


def test_bridge_writer_all_tools(tmp_path: Path):
    config = OutputConfig(
        agents_md=True,
        cursorrules=True,
        windsurfrules=True,
        clinerules=True,
        zed_rules=True,
        aider_conventions=True,
        claude_md=True,
        copilot_instructions=True,
        amazonq_rules=True,
        continue_rules=True,
    )
    profile = ProjectProfile(
        primary_language="Python",
        secondary_languages=[],
        frameworks=["FastAPI"],
        infra_tools=["Docker"],
        cicd_platforms=["GitHub Actions"],
        architecture_hints=[],
        domain="web",
        security_risk_level="low",
        existing_agents_md=None,
        has_tests=True,
        test_commands=["pytest"],
        build_commands=[],
    )

    writer = BridgeWriter(tmp_path, config, profile)
    written = writer.write_all()

    assert len(written) == 9
    assert (tmp_path / ".cursorrules").exists()
    assert (tmp_path / ".windsurfrules").exists()
    assert (tmp_path / "CLAUDE.md").exists()
    assert (tmp_path / ".github/copilot-instructions.md").exists()
    assert (tmp_path / ".amazonq/rules/project-rules.md").exists()
