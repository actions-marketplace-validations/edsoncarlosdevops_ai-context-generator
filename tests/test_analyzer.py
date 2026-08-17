from pathlib import Path

from ai_context_generator.analyzer import ProjectAnalyzer, _matches
from ai_context_generator.scanner import CodebaseScanner


def _profile(tmp_path: Path, files: dict[str, str]):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    scan = CodebaseScanner(tmp_path, [".git", "node_modules"], 100).scan()
    return ProjectAnalyzer().analyze(scan)


def test_boundary_matching():
    assert _matches("react-dom", "react")
    assert _matches("@react/native", "react")
    assert _matches("django-money", "money")
    assert not _matches("pyreact", "react")
    assert not _matches("twecho", "echo")
    assert not _matches("moneygram", "money")


def test_detects_frameworks_and_domain(tmp_path):
    profile = _profile(tmp_path, {"requirements.txt": "fastapi\npydantic\npytest\n"})

    assert "FastAPI" in profile.frameworks
    assert profile.domain == "web"


def test_web_wins_over_data_engineering_when_react_present(tmp_path):
    profile = _profile(tmp_path, {"requirements.txt": "pandas\nreact\nnext\n"})

    assert profile.domain == "web"


def test_detects_infra_and_cicd(tmp_path):
    profile = _profile(
        tmp_path,
        {
            "Dockerfile": "FROM python:3.12\n",
            "main.tf": 'resource "null_resource" "x" {}\n',
            ".github/workflows/ci.yml": "on: push\n",
        },
    )

    assert "Docker" in profile.infra_tools
    assert "Terraform" in profile.infra_tools
    assert "GitHub Actions" in profile.cicd_platforms


def test_ignores_yaml_for_primary_language(tmp_path):
    profile = _profile(
        tmp_path,
        {
            "a.py": "x",
            "b.py": "y",
            "c.yml": "on: push\n",
        },
    )

    assert profile.primary_language == "Python"
