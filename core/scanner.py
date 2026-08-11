import os
import re
from collections import Counter
from dataclasses import dataclass
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


class CodebaseScanner:
    def __init__(self, workspace_path: Path, exclude_dirs: list[str], max_file_size_kb: int):
        self.workspace_path = workspace_path
        self.exclude_dirs = set(exclude_dirs)
        self.max_file_size_bytes = max_file_size_kb * 1024

        self.lang_exts = {
            ".py": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript React",
            ".js": "JavaScript",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".tf": "Terraform",
            ".java": "Java",
            ".rb": "Ruby",
            ".cs": "C#",
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
        lang_counter: Counter[str] = Counter()
        dependencies: set[str] = set()
        cicd_files: list[str] = []
        infra_files: list[str] = []
        existing_agents_md: str | None = None
        has_tests = False
        test_commands: list[str] = []
        build_commands: list[str] = []
        detected_ai_tools: set[str] = set()

        # Check top-level AI tool config files
        for rel_path, tool_name in AI_TOOL_SIGNATURES.items():
            if (self.workspace_path / rel_path).exists():
                detected_ai_tools.add(tool_name)

        for root, dirs, files in os.walk(self.workspace_path):
            # Exclude directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            rel_root = Path(root).relative_to(self.workspace_path)

            for file in files:
                file_path = Path(root) / file
                try:
                    if file_path.stat().st_size > self.max_file_size_bytes:
                        continue
                except OSError:
                    continue

                total_files += 1

                # Language detection
                ext = file_path.suffix
                if ext in self.lang_exts:
                    lang_counter[self.lang_exts[ext]] += 1

                # Dependencies & Manifests
                if file in self.manifest_files:
                    deps, tc, bc = self._parse_manifest(file_path, file)
                    dependencies.update(deps)
                    test_commands.extend(tc)
                    build_commands.extend(bc)

                # CI/CD detection
                if file.endswith(".yml") or file.endswith(".yaml"):
                    if "github/workflows" in str(file_path).lower():
                        cicd_files.append(str(file_path.relative_to(self.workspace_path)))
                    elif file in [".gitlab-ci.yml", "azure-pipelines.yml"]:
                        cicd_files.append(str(file_path.relative_to(self.workspace_path)))
                elif file == "Jenkinsfile":
                    cicd_files.append(str(file_path.relative_to(self.workspace_path)))

                # Infra detection
                if file == "Dockerfile" or file.startswith("docker-compose"):
                    infra_files.append(str(file_path.relative_to(self.workspace_path)))
                elif ext in [".tf", ".tfvars"]:
                    infra_files.append(str(file_path.relative_to(self.workspace_path)))
                elif "helm" in rel_root.parts or "k8s" in rel_root.parts:
                    infra_files.append(str(file_path.relative_to(self.workspace_path)))

                # Existing contexts
                if file == "AGENTS.md" and root == str(self.workspace_path):
                    try:
                        existing_agents_md = file_path.read_text(encoding="utf-8")
                    except Exception:
                        pass

                # Tests
                if "test" in file.lower() or "test" in rel_root.parts:
                    has_tests = True

                # Makefile commands
                if file == "Makefile":
                    tc, bc = self._parse_makefile(file_path)
                    test_commands.extend(tc)
                    build_commands.extend(bc)

        return ScanResult(
            total_files=total_files,
            language_counts=dict(lang_counter),
            dependencies=list(dependencies),
            cicd_files=cicd_files,
            infra_files=infra_files,
            existing_agents_md=existing_agents_md,
            has_tests=has_tests,
            test_commands=list(set(test_commands)),
            build_commands=list(set(build_commands)),
            detected_ai_tools=sorted(detected_ai_tools),
        )

    def _parse_manifest(
        self, file_path: Path, filename: str
    ) -> tuple[list[str], list[str], list[str]]:
        deps = []
        tc = []
        bc = []
        try:
            content = file_path.read_text(encoding="utf-8")
            if filename == "package.json":
                import json

                try:
                    data = json.loads(content)
                    deps.extend(data.get("dependencies", {}).keys())
                    deps.extend(data.get("devDependencies", {}).keys())
                    scripts = data.get("scripts", {})
                    if "test" in scripts:
                        tc.append("npm run test")
                    if "build" in scripts:
                        bc.append("npm run build")
                except json.JSONDecodeError:
                    pass
            elif filename == "requirements.txt":
                for line in content.splitlines():
                    line = line.split("#")[0].strip()
                    if line:
                        dep = re.split(r"[=<>~]", line)[0]
                        if dep:
                            deps.append(dep)
        except Exception:
            pass
        return deps, tc, bc

    def _parse_makefile(self, file_path: Path) -> tuple[list[str], list[str]]:
        tc = []
        bc = []
        try:
            content = file_path.read_text(encoding="utf-8")
            if re.search(r"^test:", content, re.MULTILINE):
                tc.append("make test")
            if re.search(r"^build:", content, re.MULTILINE):
                bc.append("make build")
        except Exception:
            pass
        return tc, bc
