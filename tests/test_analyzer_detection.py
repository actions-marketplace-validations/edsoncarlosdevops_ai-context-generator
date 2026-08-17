from pathlib import Path

from ai_context_generator.analyzer import ProjectAnalyzer, _infra_label
from ai_context_generator.config import DEFAULT_EXCLUDE_DIRS
from ai_context_generator.scanner import CodebaseScanner


def _profile(tmp_path: Path, files: dict[str, str]):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    scan = CodebaseScanner(tmp_path, list(DEFAULT_EXCLUDE_DIRS), 100).scan()
    return ProjectAnalyzer().analyze(scan)


# ----------------------------------------------------------- infra label mapping


def test_samples_directory_is_not_aws_sam(tmp_path: Path):
    """Substring matching reported 'AWS SAM' for any path containing 'sam'."""
    profile = _profile(tmp_path, {"samples/Dockerfile": "FROM alpine\n"})
    assert profile.infra_tools == ["Docker"]


def test_serverless_and_helm_are_detected(tmp_path: Path):
    profile = _profile(
        tmp_path,
        {
            "serverless.yml": "service: api\n",
            "charts/app/Chart.yaml": "name: app\n",
            "k8s/deploy.yaml": "kind: Deployment\n",
        },
    )
    assert "Serverless Framework" in profile.infra_tools
    assert "Helm" in profile.infra_tools
    assert "Kubernetes" in profile.infra_tools


def test_infra_label_is_exact():
    assert _infra_label("infra/main.tf") == "Terraform"
    assert _infra_label("docker-compose.prod.yml") == "Docker Compose"
    assert _infra_label("Dockerfile.dev") == "Docker"
    assert _infra_label("cdk.json") == "AWS CDK"
    assert _infra_label("samples/readme.txt") is None
    assert _infra_label("scandinavia/notes.md") is None


# -------------------------------------------------------------- CI/CD detection


def test_detects_multiple_ci_platforms(tmp_path: Path):
    profile = _profile(
        tmp_path,
        {
            ".github/workflows/ci.yml": "on: push\n",
            ".gitlab-ci.yml": "stages: [test]\n",
            ".circleci/config.yml": "version: 2.1\n",
            "Jenkinsfile": "pipeline {}\n",
        },
    )
    assert set(profile.cicd_platforms) == {
        "GitHub Actions",
        "GitLab CI",
        "CircleCI",
        "Jenkins",
    }


# ------------------------------------------------------------- domain resolution


def test_machine_learning_domain(tmp_path: Path):
    profile = _profile(tmp_path, {"requirements.txt": "torch\ntransformers\nmlflow\n"})
    assert profile.domain == "machine-learning"


def test_iac_only_repo_is_devops(tmp_path: Path):
    profile = _profile(tmp_path, {"infra/main.tf": 'provider "aws" {}\n'})
    assert profile.domain == "devops"
    assert profile.security_risk_level == "high"


def test_app_framework_outranks_iac(tmp_path: Path):
    profile = _profile(
        tmp_path,
        {"requirements.txt": "django\n", "infra/main.tf": 'provider "aws" {}\n'},
    )
    assert profile.domain == "web"


def test_low_risk_for_plain_project(tmp_path: Path):
    profile = _profile(tmp_path, {"src/app.py": "x\n"})
    assert profile.security_risk_level == "low"
    assert profile.domain == "general"


# ------------------------------------------------------------ structural profile


def test_architecture_hints_from_real_layout(tmp_path: Path):
    profile = _profile(
        tmp_path,
        {
            "services/auth/main.go": "package main\n",
            "packages/ui/index.ts": "export {}\n",
            "domain/user.go": "package domain\n",
        },
    )
    assert "microservices" in profile.architecture_hints
    assert "monorepo" in profile.architecture_hints
    assert "domain-driven-design" in profile.architecture_hints


def test_language_breakdown_is_bucketed(tmp_path: Path):
    profile = _profile(tmp_path, {f"src/m{i}.py": "x\n" for i in range(10)})
    assert profile.language_breakdown == {"Python": 100}


def test_key_dependencies_are_capped_and_sorted(tmp_path: Path):
    reqs = "\n".join(f"pkg{i:03d}" for i in range(60))
    profile = _profile(tmp_path, {"requirements.txt": reqs})
    assert len(profile.key_dependencies) == 40
    assert profile.key_dependencies == sorted(profile.key_dependencies)


def test_empty_repository_does_not_crash(tmp_path: Path):
    profile = _profile(tmp_path, {})
    assert profile.primary_language == "Unknown"
    assert profile.language_breakdown == {}
