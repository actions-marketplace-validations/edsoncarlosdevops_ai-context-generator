from core.analyzer import ProjectProfile
from core.config import AppConfig
from core.prompt_builder import PromptBuilder


def make_profile(existing: str | None = None) -> ProjectProfile:
    return ProjectProfile(
        primary_language="Python",
        secondary_languages=[],
        frameworks=["FastAPI"],
        infra_tools=["Docker"],
        cicd_platforms=["GitHub Actions"],
        architecture_hints=[],
        domain="web",
        security_risk_level="low",
        existing_agents_md=existing,
        has_tests=True,
        test_commands=["pytest"],
        build_commands=[],
    )


def test_build_replaces_all_placeholders():
    prompt = PromptBuilder(AppConfig()).build(make_profile())

    assert "{{PROJECT_PROFILE_JSON}}" not in prompt
    assert "{{MAX_LINES}}" not in prompt
    assert "{{LANGUAGE}}" not in prompt
    assert "{{ENRICH_INSTRUCTION}}" not in prompt
    assert "FastAPI" in prompt


def test_build_injects_domain_playbook():
    prompt = PromptBuilder(AppConfig()).build(make_profile())

    assert "Web Application" in prompt


def test_build_enrichment_mode_includes_existing_agents_md():
    prompt = PromptBuilder(AppConfig()).build(make_profile(existing="# old rules"))

    assert "# old rules" in prompt
    assert "Enrich" in prompt
