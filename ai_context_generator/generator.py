import difflib
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from ai_context_generator.analyzer import ProjectAnalyzer, ProjectProfile
from ai_context_generator.bridge_writer import BridgeWriter
from ai_context_generator.config import BRIDGE_FLAG_TO_TOOL, AppConfig, OutputConfig
from ai_context_generator.llm_client import LLMClient
from ai_context_generator.prompt_builder import PromptBuilder
from ai_context_generator.scanner import CodebaseScanner, ScanResult

SIGNATURE_FILE = ".ai-context.sig"

# Files never rewritten in place without the tool's own marker.
GITATTRIBUTES_START = "# >>> ai-context-generator (auto-managed) >>>"
GITATTRIBUTES_END = "# <<< ai-context-generator <<<"

# Below this ratio of changed lines, a regenerated AGENTS.md is considered
# equivalent to the existing one and is not written.
MIN_DELTA_TO_WRITE = 0.10


@dataclass
class GenerationResult:
    scanned_files: int
    primary_language: str
    language_percentages: str
    frameworks: list[str]
    cicd: list[str]
    agents_md_written: bool
    agents_md_lines: int
    bridge_files_written: list[str]
    message: str
    bridge_files_skipped: list[str] = field(default_factory=list)
    domain: str = "general"
    infra_tools: list[str] = field(default_factory=list)
    llm_called: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    scan_truncated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class ContextGenerator:
    def __init__(self, workspace_path: Path, config: AppConfig, llm_client: LLMClient):
        self.workspace_path = workspace_path
        self.config = config
        self.llm_client = llm_client

    def _calculate_delta(self, old_text: str, new_text: str) -> float:
        if not old_text:
            return 1.0
        matcher = difflib.SequenceMatcher(None, old_text.splitlines(), new_text.splitlines())
        return 1.0 - matcher.ratio()

    def _profile_signature(self, profile: ProjectProfile) -> str:
        """Hash of everything that affects the generated AGENTS.md content."""
        data = asdict(profile)
        data.pop("existing_agents_md", None)  # changes with every write — not a profile signal
        key = (
            json.dumps(data, sort_keys=True, default=str)
            + "|"
            + self.config.generator.model
            + "|"
            + self.config.generator.language
            + "|"
            + str(self.config.generator.max_lines)
            + "|"
            + str(self.config.generator.max_tokens)
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _bridge_config(self, scan_result: ScanResult) -> OutputConfig:
        """Resolve bridge flags.

        Priority order:
        1. Explicit user config in .ai_context.toml always wins.
        2. If user set NO output keys → auto-detect from existing AI tool files.
        3. If user set NO output keys AND no AI tools detected → generate all (first run).
        """
        explicit = self.config.explicit_output_keys
        # User explicitly configured output section → respect it fully.
        if explicit:
            return self.config.output

        # No explicit config: auto-detect from repository AI tool files.
        detected = set(scan_result.detected_ai_tools) - {"antigravity"}
        if not detected:
            # First run, no tools found → generate all bridges.
            return self.config.output

        # Only generate bridges for tools actually present in the repo.
        overrides = {flag: (tool in detected) for flag, tool in BRIDGE_FLAG_TO_TOOL.items()}
        return replace(self.config.output, **overrides)

    def _write_gitattributes(self, bridge_files: list[str]) -> None:
        """Add linguist-generated markers for bridge files in .gitattributes.

        This causes GitHub to:
        - Collapse these files by default in PR diffs
        - Exclude them from language statistics
        """
        ga_path = self.workspace_path / ".gitattributes"

        managed_lines = [GITATTRIBUTES_START, f"{SIGNATURE_FILE} linguist-generated=true"]
        managed_lines += [f"{bf} linguist-generated=true" for bf in sorted(bridge_files)]
        managed_lines.append(GITATTRIBUTES_END)
        managed_block = "\n".join(managed_lines) + "\n"

        if not ga_path.exists():
            ga_path.write_text(managed_block, encoding="utf-8")
            return

        try:
            existing = ga_path.read_text(encoding="utf-8")
        except OSError:
            return
        if GITATTRIBUTES_START in existing:
            pattern = (
                re.escape(GITATTRIBUTES_START) + r".*?" + re.escape(GITATTRIBUTES_END) + r"\n?"
            )
            updated = re.sub(pattern, managed_block, existing, flags=re.DOTALL)
        else:
            updated = existing.rstrip("\n") + "\n\n" + managed_block
        if updated != existing:
            ga_path.write_text(updated, encoding="utf-8")

    def generate(self, force_replace: bool = False) -> GenerationResult:
        scanner = CodebaseScanner(
            self.workspace_path,
            self.config.scan.exclude_dirs,
            self.config.scan.max_file_size_kb,
            self.config.scan.max_files,
            self.config.scan.use_gitignore,
        )
        scan_result = scanner.scan()

        analyzer = ProjectAnalyzer()
        profile = analyzer.analyze(scan_result)

        prompt_builder = PromptBuilder(self.config)
        prompt = prompt_builder.build(profile)

        agents_md_path = self.workspace_path / "AGENTS.md"
        sig_path = self.workspace_path / SIGNATURE_FILE
        stored_sig = ""
        if sig_path.exists():
            try:
                stored_sig = sig_path.read_text(encoding="utf-8").strip()
            except OSError:
                stored_sig = ""
        current_sig = self._profile_signature(profile)

        agents_md_content = ""
        write_agents = False
        llm_called = False
        msg = ""

        if not self.config.output.agents_md:
            msg = "AGENTS.md generation disabled by config."
        elif not force_replace and profile.existing_agents_md and stored_sig == current_sig:
            # Nothing relevant changed since the last successful run — skip the paid LLM call.
            msg = "AGENTS.md already up-to-date, no changes needed."
        else:
            agents_md_content = self.llm_client.generate(prompt)
            llm_called = True
            if not force_replace and profile.existing_agents_md:
                delta = self._calculate_delta(profile.existing_agents_md, agents_md_content)
                if delta <= MIN_DELTA_TO_WRITE:
                    msg = "AGENTS.md already up-to-date, no changes needed."
                else:
                    write_agents = True
                    msg = f"Enriched AGENTS.md (delta: {delta:.1%})"
            else:
                write_agents = True
                msg = "Created new AGENTS.md"

        if write_agents and self.config.output.agents_md:
            agents_md_path.write_text(agents_md_content, encoding="utf-8")

        # Persist the signature whenever this tool manages AGENTS.md, so unchanged
        # repositories skip the LLM call on subsequent runs.
        if self.config.output.agents_md and (write_agents or profile.existing_agents_md):
            sig_path.write_text(current_sig + "\n", encoding="utf-8")

        # Bridges are independent of the AGENTS.md write: regenerate when missing,
        # respecting explicit config and tool auto-detection.
        bridge_writer = BridgeWriter(self.workspace_path, self._bridge_config(scan_result), profile)
        bridge_files = bridge_writer.write_all()

        # Mark generated bridge files as machine-generated in .gitattributes
        # so they collapse in GitHub PR diffs and are clearly marked as auto-managed.
        if bridge_files and self.config.output.gitattributes:
            self._write_gitattributes(bridge_files)

        usage = getattr(self.llm_client, "last_usage", None)

        return GenerationResult(
            scanned_files=scan_result.total_files,
            primary_language=profile.primary_language,
            language_percentages=self._format_percentages(scan_result),
            frameworks=profile.frameworks,
            cicd=profile.cicd_platforms,
            agents_md_written=write_agents and self.config.output.agents_md,
            agents_md_lines=len(agents_md_content.splitlines()),
            bridge_files_written=bridge_files,
            message=msg,
            bridge_files_skipped=bridge_writer.skipped,
            domain=profile.domain,
            infra_tools=profile.infra_tools,
            llm_called=llm_called,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            scan_truncated=scan_result.truncated,
        )

    @staticmethod
    def _format_percentages(scan_result: ScanResult) -> str:
        total = sum(scan_result.language_counts.values())
        if not total:
            return ""
        top_langs = sorted(scan_result.language_counts.items(), key=lambda x: (-x[1], x[0]))[:3]
        return ", ".join(f"{lang} ({int(c / total * 100)}%)" for lang, c in top_langs)
