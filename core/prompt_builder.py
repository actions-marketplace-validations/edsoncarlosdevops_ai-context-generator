import json
from dataclasses import asdict
from importlib.resources import files

from core.analyzer import ProjectProfile
from core.config import AppConfig

# Template ships inside the `core` package so it works when installed from PyPI.
PROMPT_TEMPLATE_RESOURCE = "prompts/generate_agents.md"


# Domain-specific security and architecture context injected into the prompt
DOMAIN_PLAYBOOKS: dict[str, str] = {
    "robotics": (
        "DOMAIN CONTEXT — Robotics / Real-Time Systems:\n"
        "- Callbacks at ≥10 Hz must NEVER allocate heap memory (no new/malloc, no dynamic containers)\n"
        "- All inter-node message schemas must maintain backwards compatibility (no field removal/rename without versioning)\n"
        "- C++ nodes must use RAII and smart pointers; raw owning pointers are a blocking finding\n"
        "- All kinematic math (speed, distance, acceleration) must guard against dt==0 and NaN/Inf before serialisation\n"
        "- Graceful shutdown signals must be implemented to prevent CI/CD runner hangs"
    ),
    "fintech": (
        "DOMAIN CONTEXT — Financial / Payments:\n"
        "- Apply OWASP Top 10 2021 and PCI-DSS v4 constraints throughout\n"
        "- Payment API calls must be idempotent (idempotency key required on every mutating request)\n"
        "- No secrets, PII, card data, or tokens may appear in logs, error messages, or stack traces\n"
        "- All financial arithmetic must use Decimal (not float) to prevent rounding errors\n"
        "- Every state-changing operation must produce an immutable, append-only audit log entry"
    ),
    "data-engineering": (
        "DOMAIN CONTEXT — Data Engineering / ETL:\n"
        "- Pipeline runs must be idempotent: re-running on same input must produce identical output\n"
        "- Schema evolution in Parquet/Avro must maintain backwards compatibility (no column removal without migration)\n"
        "- All numerical transforms must guard against NaN, Inf, and ZeroDivisionError before writing to storage\n"
        "- Partition strategies must be documented; changing partition keys is a breaking schema change\n"
        "- Intermediate datasets must be versioned; overwriting production tables without a backup is a Critical finding"
    ),
    "devops": (
        "DOMAIN CONTEXT — DevOps / Infrastructure as Code:\n"
        "- Terraform: all modules must pin provider versions; no floating `~>` without upper bound\n"
        "- Terraform remote state must use locking (DynamoDB or GCS); local state is a Critical finding in CI\n"
        "- No hardcoded credentials, API keys, or IPs in IaC files — use variables with sensitive=true\n"
        "- IAM policies must follow least-privilege; wildcard (*) actions require justification comment\n"
        "- Docker images must use multi-stage builds; no secrets in ENV or ARG in final stage"
    ),
    "web": (
        "DOMAIN CONTEXT — Web Application:\n"
        "- All user input must be validated at the API boundary using the framework's schema library (Pydantic, Zod, Joi)\n"
        "- SQL queries must use parameterised statements; string interpolation in queries is a Critical finding\n"
        "- JWT tokens must have explicit expiry (exp claim); tokens without expiry are a Critical security finding\n"
        "- CORS policy must allowlist specific origins; wildcard (*) in production is a High finding\n"
        "- Sensitive operations must have rate limiting; authentication endpoints must have brute-force protection"
    ),
    "embedded": (
        "DOMAIN CONTEXT — Embedded Systems:\n"
        "- No heap allocation (malloc/new) in ISR or time-critical paths\n"
        "- Stack usage must be profiled; unbounded recursion is a Critical finding\n"
        "- All hardware register accesses must be wrapped in platform abstraction layer (PAL)\n"
        "- Watchdog timer must be refreshed in the main loop; any code path that could block indefinitely must be reviewed\n"
        "- Floating point operations in ISR require explicit FPU save/restore"
    ),
    "general": (
        "DOMAIN CONTEXT — General Software Engineering:\n"
        "- Apply SOLID principles; single responsibility violations should be flagged as Medium findings\n"
        "- All external I/O (HTTP, DB, filesystem) must have explicit timeout and error handling\n"
        "- Secrets must never be committed to source control; use environment variables or secret managers\n"
        "- Dependencies must be pinned to exact versions in lock files; floating versions are a Medium finding"
    ),
}


class PromptBuilder:
    """Builds a highly specific, domain-aware LLM prompt for AGENTS.md generation."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._template = (
            files("core").joinpath(PROMPT_TEMPLATE_RESOURCE).read_text(encoding="utf-8")
        )

    def build(self, profile: ProjectProfile) -> str:
        profile_dict = asdict(profile)
        # Remove existing_agents_md from JSON to keep profile compact (handled separately)
        profile_dict.pop("existing_agents_md", None)
        profile_json = json.dumps(profile_dict, indent=2)

        domain_playbook = DOMAIN_PLAYBOOKS.get(profile.domain, DOMAIN_PLAYBOOKS["general"])

        if profile.existing_agents_md:
            enrich_instruction = (
                "An existing AGENTS.md was found (shown below). "
                "Enrich it by ADDING only rules that are missing, relevant, and non-redundant. "
                "Do NOT duplicate any existing rule — read the entire file before adding anything. "
                "Do NOT restructure the file unless a section is clearly wrong or missing. "
                "Return the COMPLETE enriched file (not just the additions).\n\n"
                f"Existing AGENTS.md:\n```\n{profile.existing_agents_md}\n```"
            )
        else:
            enrich_instruction = "No existing AGENTS.md found. Generate the file from scratch."

        prompt = self._template
        prompt = prompt.replace("{{PROJECT_PROFILE_JSON}}", profile_json)
        prompt = prompt.replace("{{MAX_LINES}}", str(self.config.generator.max_lines))
        prompt = prompt.replace("{{LANGUAGE}}", self.config.generator.language)
        prompt = prompt.replace("{{ENRICH_INSTRUCTION}}", enrich_instruction)

        # Inject domain playbook at the end for maximum LLM attention
        prompt += f"\n\n---\n\n## Additional Domain-Specific Context\n\n{domain_playbook}\n"

        return prompt
