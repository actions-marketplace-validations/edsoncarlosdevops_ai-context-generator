import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from ai_context_generator.scanner import (
    INFRA_DIRNAMES,
    INFRA_EXTENSIONS,
    INFRA_FILENAMES,
    MAX_KEY_DEPENDENCIES,
    ScanResult,
)


@dataclass
class ProjectProfile:
    primary_language: str
    secondary_languages: list[str]
    frameworks: list[str]
    infra_tools: list[str]
    cicd_platforms: list[str]
    architecture_hints: list[str]
    domain: str
    security_risk_level: str
    existing_agents_md: str | None
    has_tests: bool
    test_commands: list[str]
    build_commands: list[str]
    # Structural evidence used to keep generated rules project-specific.
    language_breakdown: dict[str, int] = field(default_factory=dict)
    key_dependencies: list[str] = field(default_factory=list)
    directory_tree: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)


def _matches(dep: str, keyword: str) -> bool:
    """Boundary-aware, case-insensitive substring match.

    'react' matches 'react-dom' and '@react/native', but not 'pyreact'.
    This avoids the false positives produced by plain ``in`` matching.
    """
    needle = re.escape(keyword.lower())
    return bool(re.search(rf"(?:^|[^a-z0-9]){needle}(?:[^a-z0-9]|$)", dep.lower()))


# Maps dependency keyword → human-readable framework name
FRAMEWORK_SIGNALS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "tornado": "Tornado",
    "starlette": "Starlette",
    "litestar": "Litestar",
    "express": "Express",
    "koa": "Koa",
    "hapi": "Hapi.js",
    "nestjs": "NestJS",
    "@nestjs": "NestJS",
    "next": "Next.js",
    "nuxt": "Nuxt.js",
    "remix": "Remix",
    "astro": "Astro",
    "react": "React",
    "vue": "Vue.js",
    "@angular": "Angular",
    "angular": "Angular",
    "svelte": "Svelte",
    "spring": "Spring Boot",
    "quarkus": "Quarkus",
    "rails": "Ruby on Rails",
    "sinatra": "Sinatra",
    "laravel": "Laravel",
    "symfony": "Symfony",
    "gin": "Gin",
    "fiber": "Fiber",
    "echo": "Echo",
    "actix": "Actix-Web",
    "axum": "Axum",
    "rocket": "Rocket",
    "tokio": "Tokio",
    "ros2": "ROS 2",
    "rclpy": "ROS 2",
    "rclcpp": "ROS 2",
    "mcap": "MCAP",
    "duckdb": "DuckDB",
    "apache-airflow": "Apache Airflow",
    "airflow": "Apache Airflow",
    "prefect": "Prefect",
    "dagster": "Dagster",
    "dbt": "dbt",
    "pyspark": "Apache Spark",
    "kafka": "Apache Kafka",
    "confluent": "Confluent Kafka",
    "celery": "Celery",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "prisma": "Prisma",
    "mongoose": "Mongoose",
    "typeorm": "TypeORM",
    "redis": "Redis",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "transformers": "Hugging Face Transformers",
    "langchain": "LangChain",
    "openai": "OpenAI SDK",
    "anthropic": "Anthropic SDK",
    "stripe": "Stripe",
    "plaid": "Plaid",
    "braintree": "Braintree",
    "paypal": "PayPal",
    "terraform": "Terraform",
    "pulumi": "Pulumi",
    "ansible": "Ansible",
    "pytest": "pytest",
    "jest": "Jest",
    "vitest": "Vitest",
    "cypress": "Cypress",
    "playwright": "Playwright",
}

# Maps dependency keyword → domain
DOMAIN_SIGNALS: dict[str, str] = {
    "rclpy": "robotics",
    "rclcpp": "robotics",
    "ros2": "robotics",
    "mcap": "robotics",
    "stripe": "fintech",
    "plaid": "fintech",
    "braintree": "fintech",
    "paypal": "fintech",
    "pydantic-money": "fintech",
    "money": "fintech",
    "torch": "machine-learning",
    "tensorflow": "machine-learning",
    "scikit-learn": "machine-learning",
    "transformers": "machine-learning",
    "langchain": "machine-learning",
    "mlflow": "machine-learning",
    "apache-airflow": "data-engineering",
    "airflow": "data-engineering",
    "pyspark": "data-engineering",
    "dbt": "data-engineering",
    "prefect": "data-engineering",
    "dagster": "data-engineering",
    "duckdb": "data-engineering",
    "pyarrow": "data-engineering",
    "pandas": "data-engineering",
    "polars": "data-engineering",
    "react": "web",
    "next": "web",
    "django": "web",
    "flask": "web",
    "fastapi": "web",
    "express": "web",
    "vue": "web",
    "@angular": "web",
    "svelte": "web",
    "rails": "web",
    "laravel": "web",
    "terraform": "devops",
    "pulumi": "devops",
    "ansible": "devops",
    "zephyr": "embedded",
    "freertos": "embedded",
    "cmsis": "embedded",
}

# More specific domains first — used as the tie-breaker when scores are equal.
DOMAIN_PRIORITY: list[str] = [
    "robotics",
    "fintech",
    "embedded",
    "machine-learning",
    "data-engineering",
    "devops",
    "web",
    "general",
]

HIGH_RISK_DOMAINS: frozenset[str] = frozenset({"fintech", "robotics", "devops", "embedded"})
HIGH_RISK_DEPS: frozenset[str] = frozenset(
    {"jwt", "oauth", "stripe", "plaid", "braintree", "crypto", "cryptography", "ssl", "tls"}
)
# Application frameworks strong enough to outrank an IaC-only classification.
APP_FRAMEWORKS: frozenset[str] = frozenset(
    {"FastAPI", "Django", "Flask", "React", "Next.js", "Express", "Ruby on Rails", "Spring Boot"}
)


def _infra_label(rel_path: str) -> str | None:
    """Map a scanned infrastructure path to a tool label using exact matching.

    Substring matching used to report 'AWS SAM' for any path containing 'sam'
    (e.g. `samples/`); every rule here is anchored to a full filename, a full
    directory name, or a file extension.
    """
    path = PurePosixPath(rel_path)
    name = path.name.lower()

    if name in INFRA_FILENAMES:
        return INFRA_FILENAMES[name]
    if name.startswith("docker-compose"):
        return "Docker Compose"
    if name.startswith("dockerfile"):
        return "Docker"
    suffix = path.suffix.lower()
    if suffix in INFRA_EXTENSIONS:
        return INFRA_EXTENSIONS[suffix]
    for part in path.parts[:-1]:
        if part.lower() in INFRA_DIRNAMES:
            return INFRA_DIRNAMES[part.lower()]
    return None


class ProjectAnalyzer:
    """Converts raw ScanResult into a structured ProjectProfile for prompt construction."""

    def analyze(self, scan_result: ScanResult) -> ProjectProfile:
        # Language ranking: markup/config languages never win the "primary" slot
        # when real source code is present.
        non_code = {"YAML", "SQL", "C/C++ Header"}
        sorted_langs = sorted(scan_result.language_counts.items(), key=lambda x: (-x[1], x[0]))
        code_langs = [(lang, c) for lang, c in sorted_langs if lang not in non_code]
        ranked = code_langs or sorted_langs
        primary_lang = ranked[0][0] if ranked else "Unknown"
        secondary_langs = [lang for lang, _ in ranked[1:]]

        # Language breakdown as percentages, bucketed to 10% so that ordinary
        # day-to-day commits do not invalidate the cached generation signature.
        total = sum(scan_result.language_counts.values())
        language_breakdown: dict[str, int] = {}
        if total:
            for lang, count in ranked[:6]:
                bucket = round(count / total * 100 / 10) * 10
                language_breakdown[lang] = max(bucket, 10) if count else 0

        # Framework detection
        deps_lower = [d.lower() for d in scan_result.dependencies]
        frameworks: list[str] = []
        for keyword, label in FRAMEWORK_SIGNALS.items():
            if label not in frameworks and any(_matches(dep, keyword) for dep in deps_lower):
                frameworks.append(label)

        # Infra detection — exact matching on scanned infrastructure paths.
        infra_tools: list[str] = []
        for rel_path in scan_result.infra_files:
            infra_label = _infra_label(rel_path)
            if infra_label and infra_label not in infra_tools:
                infra_tools.append(infra_label)

        # CI/CD detection
        cicd_platforms: list[str] = []
        for cicd in scan_result.cicd_files:
            cicd_l = cicd.lower()
            if ".github/" in cicd_l:
                platform = "GitHub Actions"
            elif "gitlab" in cicd_l:
                platform = "GitLab CI"
            elif "azure" in cicd_l:
                platform = "Azure DevOps"
            elif "jenkins" in cicd_l:
                platform = "Jenkins"
            elif "circleci" in cicd_l:
                platform = "CircleCI"
            elif "bitbucket" in cicd_l:
                platform = "Bitbucket Pipelines"
            else:
                continue
            if platform not in cicd_platforms:
                cicd_platforms.append(platform)

        # Architecture hints from the real directory layout
        arch_hints = self._architecture_hints(scan_result, infra_tools)

        # Domain detection — most-voted domain wins; ties broken by specificity.
        domain_scores: dict[str, int] = {}
        for keyword, detected_domain in DOMAIN_SIGNALS.items():
            if any(_matches(dep, keyword) for dep in deps_lower):
                domain_scores[detected_domain] = domain_scores.get(detected_domain, 0) + 1

        if domain_scores:
            domain = max(
                domain_scores,
                key=lambda d: (
                    domain_scores[d],
                    -DOMAIN_PRIORITY.index(d) if d in DOMAIN_PRIORITY else -len(DOMAIN_PRIORITY),
                ),
            )
        else:
            domain = "general"

        # An IaC-heavy repository with no application framework is a DevOps repo.
        if not (APP_FRAMEWORKS & set(frameworks)) and (
            {"Terraform", "Pulumi", "Ansible"} & set(infra_tools)
        ):
            domain = "devops"

        # Security risk level
        if domain in HIGH_RISK_DOMAINS or any(
            _matches(dep, k) for dep in deps_lower for k in HIGH_RISK_DEPS
        ):
            security_risk_level = "high"
        elif len(scan_result.dependencies) > 30:
            security_risk_level = "medium"
        else:
            security_risk_level = "low"

        return ProjectProfile(
            primary_language=primary_lang,
            secondary_languages=secondary_langs,
            frameworks=frameworks,
            infra_tools=infra_tools,
            cicd_platforms=cicd_platforms,
            architecture_hints=arch_hints,
            domain=domain,
            security_risk_level=security_risk_level,
            existing_agents_md=scan_result.existing_agents_md,
            has_tests=scan_result.has_tests,
            test_commands=scan_result.test_commands,
            build_commands=scan_result.build_commands,
            language_breakdown=language_breakdown,
            key_dependencies=self._key_dependencies(scan_result.dependencies),
            directory_tree=scan_result.directory_tree,
            entry_points=scan_result.entry_points,
            config_files=scan_result.config_files,
        )

    @staticmethod
    def _key_dependencies(dependencies: list[str]) -> list[str]:
        """Direct dependencies, capped so the prompt stays focused."""
        return sorted(dependencies)[:MAX_KEY_DEPENDENCIES]

    @staticmethod
    def _architecture_hints(scan_result: ScanResult, infra_tools: list[str]) -> list[str]:
        hints: list[str] = []
        tree_parts = {
            part.lower() for entry in scan_result.directory_tree for part in entry.split("/")
        }

        if {"services", "microservices"} & tree_parts:
            hints.append("microservices")
        if {"packages", "apps", "libs", "workspaces"} & tree_parts:
            hints.append("monorepo")
        if {"dags", "pipelines", "flows"} & tree_parts:
            hints.append("data-pipeline")
        if {"domain", "entities", "usecases", "use_cases"} & tree_parts:
            hints.append("domain-driven-design")
        if {"handlers", "controllers", "routes", "api"} & tree_parts:
            hints.append("layered-api")
        if {"cmd", "internal", "pkg"} <= tree_parts:
            hints.append("go-standard-layout")
        if {"Kubernetes", "Helm"} & set(infra_tools):
            hints.append("container-orchestrated")
        if len(scan_result.cicd_files) > 3:
            hints.append("ci-heavy")
        return hints
