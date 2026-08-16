import re
from dataclasses import dataclass

from core.scanner import ScanResult


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


def _matches(dep: str, keyword: str) -> bool:
    """Boundary-aware, case-insensitive substring match.

    'react' matches 'react-dom' and '@react/native', but not 'pyreact'.
    This avoids the false positives produced by plain ``in`` matching.
    """
    needle = re.escape(keyword.lower())
    return bool(re.search(rf"(?:^|[^a-z0-9]){needle}(?:[^a-z0-9]|$)", dep))


# Maps dependency keyword → human-readable framework name
FRAMEWORK_SIGNALS: dict[str, str] = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "tornado": "Tornado",
    "starlette": "Starlette",
    "express": "Express",
    "koa": "Koa",
    "hapi": "Hapi.js",
    "nestjs": "NestJS",
    "@nestjs": "NestJS",
    "next": "Next.js",
    "nuxt": "Nuxt.js",
    "react": "React",
    "vue": "Vue.js",
    "@angular": "Angular",
    "angular": "Angular",
    "svelte": "Svelte",
    "spring": "Spring Boot",
    "rails": "Ruby on Rails",
    "sinatra": "Sinatra",
    "gin": "Gin",
    "fiber": "Fiber",
    "echo": "Echo",
    "actix": "Actix-Web",
    "axum": "Axum",
    "rocket": "Rocket",
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
    "terraform": "devops",
    "pulumi": "devops",
    "ansible": "devops",
    "zephyr": "embedded",
    "freertos": "embedded",
    "cmsis": "embedded",
}

# Infra detection
INFRA_SIGNALS: dict[str, str] = {
    "dockerfile": "Docker",
    "docker-compose": "Docker Compose",
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    "helm": "Helm",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "chart.yaml": "Helm",
    "values.yaml": "Helm",
    "serverless.yml": "Serverless Framework",
    "cdk": "AWS CDK",
    "sam": "AWS SAM",
}


class ProjectAnalyzer:
    """Converts raw ScanResult into a structured ProjectProfile for prompt construction."""

    def analyze(self, scan_result: ScanResult) -> ProjectProfile:
        # Language ranking: exclude YAML from primary if Python/C++ are present
        sorted_langs = sorted(scan_result.language_counts.items(), key=lambda x: x[1], reverse=True)
        code_langs = [(lang, c) for lang, c in sorted_langs if lang not in ("YAML",)]
        primary_lang = (
            code_langs[0][0] if code_langs else (sorted_langs[0][0] if sorted_langs else "Unknown")
        )
        secondary_langs = [lang for lang, _ in (code_langs[1:] if code_langs else sorted_langs[1:])]

        # Framework detection
        deps_lower = [d.lower() for d in scan_result.dependencies]
        frameworks: list[str] = []
        for keyword, label in FRAMEWORK_SIGNALS.items():
            if label not in frameworks and any(_matches(dep, keyword) for dep in deps_lower):
                frameworks.append(label)

        # Infra detection
        infra_tools: list[str] = []
        all_infra = " ".join(scan_result.infra_files).lower()
        for signal, label in INFRA_SIGNALS.items():
            if signal in all_infra and label not in infra_tools:
                infra_tools.append(label)

        # CI/CD detection
        cicd_platforms: list[str] = []
        for cicd in scan_result.cicd_files:
            cicd_l = cicd.lower()
            if "github" in cicd_l and "GitHub Actions" not in cicd_platforms:
                cicd_platforms.append("GitHub Actions")
            elif "gitlab" in cicd_l and "GitLab CI" not in cicd_platforms:
                cicd_platforms.append("GitLab CI")
            elif "azure" in cicd_l and "Azure DevOps" not in cicd_platforms:
                cicd_platforms.append("Azure DevOps")
            elif "jenkins" in cicd_l and "Jenkins" not in cicd_platforms:
                cicd_platforms.append("Jenkins")

        # Architecture hints from directory names
        arch_hints: list[str] = []
        infra_str = " ".join(scan_result.infra_files + scan_result.cicd_files).lower()
        if "microservice" in infra_str:
            arch_hints.append("microservices")
        if any("service" in d for d in deps_lower):
            arch_hints.append("service-oriented")
        if "pipeline" in " ".join(scan_result.cicd_files).lower():
            arch_hints.append("data-pipeline")
        if "mono" in infra_str:
            arch_hints.append("monorepo")

        # Domain detection — most-voted domain wins; ties broken by priority
        domain_scores: dict[str, int] = {}
        for keyword, detected_domain in DOMAIN_SIGNALS.items():
            if any(_matches(dep, keyword) for dep in deps_lower):
                domain_scores[detected_domain] = domain_scores.get(detected_domain, 0) + 1

        if domain_scores:
            # More specific domains first (used as the tie-breaker)
            domain_priority = [
                "robotics",
                "fintech",
                "embedded",
                "data-engineering",
                "devops",
                "web",
                "general",
            ]
            domain = max(
                domain_scores,
                key=lambda d: (
                    domain_scores[d],
                    -domain_priority.index(d) if d in domain_priority else 0,
                ),
            )
        else:
            domain = "general"

        # Override domain from infra if IaC-heavy
        if not any(f in frameworks for f in ["FastAPI", "Django", "React", "Next.js"]) and (
            "Terraform" in infra_tools or "Pulumi" in infra_tools
        ):
            domain = "devops"

        # Security risk level
        high_risk_domains = {"fintech", "robotics", "devops", "embedded"}
        high_risk_deps = {"jwt", "oauth", "stripe", "plaid", "braintree", "crypto", "ssl", "tls"}
        if domain in high_risk_domains or any(
            _matches(dep, k) for dep in deps_lower for k in high_risk_deps
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
        )
