import contextlib
import json
import os
import re
import tomllib
import xml.etree.ElementTree as ET  # nosec B405 — local manifests only, never network input
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Maps known AI tool config files to a tool name
AI_TOOL_SIGNATURES: dict[str, str] = {
    ".cursorrules": "cursor",
    ".windsurfrules": "windsurf",
    ".clinerules": "cline",
    ".rules": "zed",
    "CONVENTIONS.md": "aider",
    "CLAUDE.md": "claude",
    ".github/copilot-instructions.md": "copilot",
    ".amazonq/rules/project-rules.md": "amazonq",
    ".continue/rules.md": "continue",
    ".continue/config.json": "continue",
    "AGENTS.md": "antigravity",
}

# Filenames that mark a repository-level infrastructure definition. Detection is
# exact (or prefix, for the docker-compose family) so that an unrelated path such
# as `samples/` can never be mistaken for AWS SAM.
INFRA_FILENAMES: dict[str, str] = {
    "dockerfile": "Docker",
    "containerfile": "Docker",
    "chart.yaml": "Helm",
    "values.yaml": "Helm",
    "serverless.yml": "Serverless Framework",
    "serverless.yaml": "Serverless Framework",
    "cdk.json": "AWS CDK",
    "samconfig.toml": "AWS SAM",
    "template.yaml": "AWS SAM",
    "skaffold.yaml": "Skaffold",
    "kustomization.yaml": "Kustomize",
    "pulumi.yaml": "Pulumi",
    "vagrantfile": "Vagrant",
    "ansible.cfg": "Ansible",
}

# Directories whose *name* identifies an infrastructure stack.
INFRA_DIRNAMES: dict[str, str] = {
    "helm": "Helm",
    "charts": "Helm",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "manifests": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
}

# File extensions that identify an infrastructure stack.
INFRA_EXTENSIONS: dict[str, str] = {
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    ".bicep": "Azure Bicep",
}

# Root-level files worth surfacing to the LLM as project configuration evidence.
NOTABLE_CONFIG_FILES: frozenset[str] = frozenset(
    {
        "Makefile",
        "Justfile",
        "Taskfile.yml",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "tox.ini",
        "requirements.txt",
        "requirements-dev.txt",
        "Pipfile",
        "poetry.lock",
        "package.json",
        "tsconfig.json",
        "go.mod",
        "Cargo.toml",
        "Gemfile",
        "pom.xml",
        "build.gradle",
        "composer.json",
        ".pre-commit-config.yaml",
        ".editorconfig",
        ".eslintrc.json",
        ".prettierrc",
        "ruff.toml",
        ".golangci.yml",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Dockerfile",
    }
)

# Files that typically start an application.
ENTRY_POINT_NAMES: frozenset[str] = frozenset(
    {
        "main.py",
        "__main__.py",
        "app.py",
        "wsgi.py",
        "asgi.py",
        "manage.py",
        "main.go",
        "main.rs",
        "lib.rs",
        "index.ts",
        "index.js",
        "main.ts",
        "server.ts",
        "server.js",
        "main.cpp",
        "Program.cs",
        "Application.java",
    }
)

# Directory names that always indicate a test suite, regardless of file naming.
TEST_DIR_NAMES: frozenset[str] = frozenset(
    {"test", "tests", "spec", "specs", "__tests__", "testing", "e2e", "it"}
)

# Files this tool writes itself. They must never feed back into the project
# profile — otherwise the first run changes the profile, which invalidates the
# cached signature, which triggers a fresh paid LLM call on every subsequent run.
GENERATED_ARTIFACTS: frozenset[str] = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        "CONVENTIONS.md",
        ".cursorrules",
        ".windsurfrules",
        ".clinerules",
        ".rules",
        ".ai-context.sig",
        ".gitattributes",
        ".github/copilot-instructions.md",
        ".amazonq/rules/project-rules.md",
        ".continue/rules.md",
    }
)

_TEST_FILE_RE = re.compile(
    r"(?:^test_|_test\.|^tests?\.|\.test\.|\.spec\.|_spec\.|Test[A-Z]|Tests?\.(?:java|cs|kt)$)"
)

MAX_TREE_ENTRIES = 60
MAX_TREE_DEPTH = 3
MAX_KEY_DEPENDENCIES = 40


@dataclass
class ScanResult:
    total_files: int
    language_counts: dict[str, int]
    dependencies: list[str]
    cicd_files: list[str]
    infra_files: list[str]
    existing_agents_md: str | None
    has_tests: bool
    test_commands: list[str]
    build_commands: list[str]
    detected_ai_tools: list[str]  # Tools already configured in this repo
    # Structural evidence — this is what lets the LLM write project-specific rules
    # instead of generic advice.
    directory_tree: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    truncated: bool = False  # True when the max_files cap stopped the scan early


def _gitignore_dirs(workspace_path: Path) -> set[str]:
    """Extract plain directory names from the root .gitignore.

    Only unambiguous entries are honoured (`dist/`, `coverage`, `/target`) — full
    gitignore semantics (globs, negations, nested files) are deliberately out of
    scope, since the goal is just to skip obvious build output.
    """
    gitignore = workspace_path / ".gitignore"
    if not gitignore.is_file():
        return set()
    names: set[str] = set()
    try:
        content = gitignore.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return names
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        line = line.rstrip("/").lstrip("/")
        # Skip anything with glob syntax, path separators or an extension.
        if not line or any(ch in line for ch in "*?[]") or "/" in line or "." in line[1:]:
            continue
        names.add(line)
    return names


class CodebaseScanner:
    def __init__(
        self,
        workspace_path: Path,
        exclude_dirs: list[str],
        max_file_size_kb: int,
        max_files: int = 100000,
        use_gitignore: bool = True,
    ):
        self.workspace_path = workspace_path
        self.exclude_dirs = set(exclude_dirs)
        if use_gitignore:
            self.exclude_dirs |= _gitignore_dirs(workspace_path)
        self.max_file_size_bytes = max_file_size_kb * 1024
        self.max_files = max_files

        self.lang_exts = {
            ".py": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript React",
            ".js": "JavaScript",
            ".jsx": "React JS",
            ".mjs": "JavaScript",
            ".cjs": "JavaScript",
            ".go": "Go",
            ".rs": "Rust",
            ".c": "C",
            ".h": "C/C++ Header",
            ".cpp": "C++",
            ".cc": "C++",
            ".hpp": "C++ Header",
            ".tf": "Terraform",
            ".java": "Java",
            ".kt": "Kotlin",
            ".kts": "Kotlin",
            ".swift": "Swift",
            ".rb": "Ruby",
            ".cs": "C#",
            ".php": "PHP",
            ".scala": "Scala",
            ".sh": "Shell",
            ".bash": "Shell",
            ".dart": "Dart",
            ".ex": "Elixir",
            ".exs": "Elixir",
            ".lua": "Lua",
            ".sql": "SQL",
            ".yaml": "YAML",
            ".yml": "YAML",
        }
        self.manifest_files = {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "go.mod",
            "Cargo.toml",
            "Gemfile",
            "build.gradle",
            "pom.xml",
            "composer.json",
        }

    def scan(self) -> ScanResult:
        total_files = 0
        truncated = False
        lang_counter: Counter[str] = Counter()
        dependencies: set[str] = set()
        cicd_files: list[str] = []
        infra_files: list[str] = []
        existing_agents_md: str | None = None
        has_tests = False
        test_commands: list[str] = []
        build_commands: list[str] = []
        detected_ai_tools: set[str] = set()
        directories: set[str] = set()
        entry_points: list[str] = []
        config_files: list[str] = []

        # Check top-level AI tool config files
        for rel_path, tool_name in AI_TOOL_SIGNATURES.items():
            if (self.workspace_path / rel_path).exists():
                detected_ai_tools.add(tool_name)

        for root, dirs, files in os.walk(self.workspace_path):
            # Exclude directories (also skips hidden build/tool dirs by convention).
            dirs[:] = sorted(d for d in dirs if d not in self.exclude_dirs)
            rel_root = Path(root).relative_to(self.workspace_path)
            parts_lower = {p.lower() for p in rel_root.parts}
            is_root = rel_root == Path(".")

            # A directory named `tests/`, `spec/`, … is definitive proof of a suite.
            if parts_lower & TEST_DIR_NAMES:
                has_tests = True

            # Hidden directories (.github, .continue, .amazonq …) are tooling, not
            # project structure — and some of them are created by this very tool.
            if (
                not is_root
                and len(rel_root.parts) <= MAX_TREE_DEPTH
                and not any(p.startswith(".") for p in rel_root.parts)
            ):
                directories.add(rel_root.as_posix())

            for file in files:
                file_path = Path(root) / file
                try:
                    if file_path.stat().st_size > self.max_file_size_bytes:
                        continue
                except OSError:
                    continue

                total_files += 1
                if self.max_files and total_files > self.max_files:
                    # Hard cap: keep scanning predictable on huge monorepos.
                    print(f"  [scan] Reached max_files limit ({self.max_files}) — stopping scan.")
                    truncated = True
                    break

                # Language detection
                ext = file_path.suffix.lower()
                if ext in self.lang_exts:
                    lang_counter[self.lang_exts[ext]] += 1

                # Dependencies & Manifests
                if file in self.manifest_files:
                    deps, tc, bc = self._parse_manifest(file_path, file)
                    dependencies.update(deps)
                    test_commands.extend(tc)
                    build_commands.extend(bc)

                # Path-relative string with forward slashes (works on every OS)
                rel_file = file_path.relative_to(self.workspace_path)
                rel_posix = rel_file.as_posix()
                rel_lower = rel_posix.lower()
                file_lower = file.lower()

                # CI/CD detection
                is_pipeline_yaml = ext in (".yml", ".yaml") and (
                    ".github/workflows/" in rel_lower
                    or file_lower
                    in (".gitlab-ci.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml")
                )
                if (
                    is_pipeline_yaml
                    or file in ("Jenkinsfile", "Jenkinsfile.groovy")
                    or rel_lower.startswith(".circleci/config.")
                ):
                    cicd_files.append(rel_posix)

                # Infra detection — exact filename / extension / parent directory.
                if (
                    file_lower in INFRA_FILENAMES
                    or file_lower.startswith("docker-compose")
                    or file_lower.startswith("dockerfile.")
                    or ext in INFRA_EXTENSIONS
                    or parts_lower & set(INFRA_DIRNAMES)
                ):
                    infra_files.append(rel_posix)

                # Existing contexts
                if file == "AGENTS.md" and is_root:
                    with contextlib.suppress(Exception):  # unreadable file — treat as absent
                        existing_agents_md = file_path.read_text(encoding="utf-8")

                # Tests — filename conventions across ecosystems.
                if _TEST_FILE_RE.search(file):
                    has_tests = True

                # Entry points and root configuration evidence. Anything this tool
                # generates itself is excluded so the profile stays stable across runs.
                is_generated = rel_posix in GENERATED_ARTIFACTS
                if (
                    not is_generated
                    and file in ENTRY_POINT_NAMES
                    and len(rel_file.parts) <= MAX_TREE_DEPTH
                ):
                    entry_points.append(rel_posix)
                if not is_generated and is_root and file in NOTABLE_CONFIG_FILES:
                    config_files.append(rel_posix)

                # Makefile commands
                if file == "Makefile":
                    tc, bc = self._parse_makefile(file_path)
                    test_commands.extend(tc)
                    build_commands.extend(bc)

            if truncated:
                break

        return ScanResult(
            total_files=total_files,
            language_counts=dict(lang_counter),
            dependencies=sorted(dependencies),
            cicd_files=sorted(cicd_files),
            infra_files=sorted(infra_files),
            existing_agents_md=existing_agents_md,
            has_tests=has_tests,
            test_commands=sorted(set(test_commands)),
            build_commands=sorted(set(build_commands)),
            detected_ai_tools=sorted(detected_ai_tools),
            directory_tree=sorted(directories)[:MAX_TREE_ENTRIES],
            entry_points=sorted(set(entry_points))[:15],
            config_files=sorted(set(config_files)),
            truncated=truncated,
        )

    def _parse_manifest(
        self, file_path: Path, filename: str
    ) -> tuple[list[str], list[str], list[str]]:
        deps: list[str] = []
        tc: list[str] = []
        bc: list[str] = []
        try:
            content = file_path.read_text(encoding="utf-8")

            if filename == "package.json":
                try:
                    data = json.loads(content)
                    deps.extend(data.get("dependencies", {}).keys())
                    deps.extend(data.get("devDependencies", {}).keys())
                    scripts = data.get("scripts", {})
                    if "test" in scripts:
                        tc.append("npm run test")
                    if "build" in scripts:
                        bc.append("npm run build")
                    if "lint" in scripts:
                        bc.append("npm run lint")
                except (json.JSONDecodeError, AttributeError):
                    pass

            elif filename == "requirements.txt":
                for line in content.splitlines():
                    line = line.split("#")[0].strip()
                    if not line:
                        continue
                    dep = re.split(r"[=<>~!\[\];]", line)[0].strip()
                    if dep and not dep.startswith(("-", "http", "git+")):
                        deps.append(dep)

            elif filename == "pyproject.toml":
                try:
                    data = tomllib.loads(content)
                    project = data.get("project", {})
                    for spec in project.get("dependencies", []):
                        name = re.split(r"[=<>~!\[\];]", spec)[0].strip()
                        if name:
                            deps.append(name)
                    for extras in project.get("optional-dependencies", {}).values():
                        for spec in extras:
                            name = re.split(r"[=<>~!\[\];]", spec)[0].strip()
                            if name:
                                deps.append(name)
                    # Poetry-style projects keep dependencies elsewhere.
                    poetry = data.get("tool", {}).get("poetry", {})
                    for group in ("dependencies", "dev-dependencies"):
                        deps.extend(k for k in poetry.get(group, {}) if k != "python")
                    for group_cfg in poetry.get("group", {}).values():
                        deps.extend(k for k in group_cfg.get("dependencies", {}) if k != "python")
                except (tomllib.TOMLDecodeError, AttributeError, TypeError):
                    pass

            elif filename == "go.mod":
                in_require = False
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped == "require (":
                        in_require = True
                        continue
                    if in_require:
                        if stripped == ")":
                            in_require = False
                            continue
                        if stripped and not stripped.startswith("//"):
                            name = stripped.split()[0]
                            if "." in name:
                                deps.append(name)
                        continue
                    parts = stripped.split()
                    if len(parts) >= 2 and parts[0] in ("require", "module") and "." in parts[1]:
                        deps.append(parts[1])

            elif filename == "Cargo.toml":
                try:
                    data = tomllib.loads(content)
                    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
                        deps.extend(data.get(section, {}).keys())
                except (tomllib.TOMLDecodeError, AttributeError):
                    pass

            elif filename == "composer.json":
                try:
                    data = json.loads(content)
                    deps.extend(data.get("require", {}).keys())
                    deps.extend(data.get("require-dev", {}).keys())
                except (json.JSONDecodeError, AttributeError):
                    pass

            elif filename == "Gemfile":
                for m in re.finditer(r"gem\s+['\"]([^'\"]+)['\"]", content):
                    deps.append(m.group(1))

            elif filename == "pom.xml":
                try:
                    # pom.xml is a local manifest owned by the repository being
                    # scanned (not untrusted network input), so stdlib parsing is fine.
                    root = ET.fromstring(content)  # nosec B314
                    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
                    for dep in root.findall(".//m:dependencies/m:dependency", ns):
                        group = dep.findtext("m:groupId", default="", namespaces=ns)
                        art = dep.findtext("m:artifactId", default="", namespaces=ns)
                        if group and art:
                            deps.append(f"{group}:{art}")
                except ET.ParseError:
                    pass

            elif filename == "build.gradle":
                for m in re.finditer(
                    r"(?:implementation|api|compile|testImplementation)\s+['\"]([^'\"]+)['\"]",
                    content,
                ):
                    deps.append(m.group(1))

        except (OSError, UnicodeDecodeError):
            pass
        return deps, tc, bc

    def _parse_makefile(self, file_path: Path) -> tuple[list[str], list[str]]:
        tc: list[str] = []
        bc: list[str] = []
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return tc, bc
        for target in ("test", "tests", "check"):
            if re.search(rf"^{target}:", content, re.MULTILINE):
                tc.append(f"make {target}")
        for target in ("build", "lint", "fmt"):
            if re.search(rf"^{target}:", content, re.MULTILINE):
                bc.append(f"make {target}")
        return tc, bc
