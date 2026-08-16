import difflib
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from core.analyzer import ProjectAnalyzer, ProjectProfile
from core.bridge_writer import BridgeWriter
from core.config import BRIDGE_FLAG_TO_TOOL, AppConfig, OutputConfig
from core.llm_client import LLMClient
from core.prompt_builder import PromptBuilder
from core.scanner import CodebaseScanner, ScanResult

SIGNATURE_FILE = ".ai-context.sig"


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
        marker_start = "# >>> ai-context-generator (auto-managed) >>>"
        marker_end = "# <<< ai-context-generator <<<"

        managed_lines = [marker_start]
        # Always include the signature file
        managed_lines.append(f"{SIGNATURE_FILE} linguist-generated=true")
        for bf in sorted(bridge_files):
            managed_lines.append(f"{bf} linguist-generated=true")
        managed_lines.append(marker_end)
        managed_block = "\n".join(managed_lines) + "\n"

        if ga_path.exists():
            existing = ga_path.read_text(encoding="utf-8")
            # Replace existing managed block if present
            import re as _re

            pattern = _re.escape(marker_start) + r".*?" + _re.escape(marker_end) + r"\n?"
            if marker_start in existing:
                updated = _re.sub(pattern, managed_block, existing, flags=_re.DOTALL)
            else:
                updated = existing.rstrip("\n") + "\n\n" + managed_block
            ga_path.write_text(updated, encoding="utf-8")
        else:
            ga_path.write_text(managed_block, encoding="utf-8")

    def generate(self, force_replace: bool = False) -> GenerationResult:
        scanner = CodebaseScanner(
            self.workspace_path,
            self.config.scan.exclude_dirs,
            self.config.scan.max_file_size_kb,
            self.config.scan.max_files,
        )
        scan_result = scanner.scan()

        analyzer = ProjectAnalyzer()
        profile = analyzer.analyze(scan_result)

        prompt_builder = PromptBuilder(self.config)
        prompt = prompt_builder.build(profile)

        agents_md_path = self.workspace_path / "AGENTS.md"
        sig_path = self.workspace_path / SIGNATURE_FILE
        stored_sig = sig_path.read_text(encoding="utf-8").strip() if sig_path.exists() else ""
        current_sig = self._profile_signature(profile)

        agents_md_content = ""
        write_agents = False
        msg = ""

        if not self.config.output.agents_md:
            msg = "AGENTS.md generation disabled by config."
        elif not force_replace and profile.existing_agents_md and stored_sig == current_sig:
            # Nothing relevant changed since the last successful run — skip the paid LLM call.
            msg = "AGENTS.md already up-to-date, no changes needed."
        else:
            agents_md_content = self.llm_client.generate(prompt)
            if not force_replace and profile.existing_agents_md:
                delta = self._calculate_delta(profile.existing_agents_md, agents_md_content)
                if delta <= 0.10:
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
        if bridge_files:
            self._write_gitattributes(bridge_files)

        total = sum(scan_result.language_counts.values())
        lang_percs = ""
        if total > 0:
            top_langs = sorted(
                scan_result.language_counts.items(), key=lambda x: x[1], reverse=True
            )[:3]
            lang_percs = ", ".join(f"{lang} ({int(c / total * 100)}%)" for lang, c in top_langs)

        return GenerationResult(
            scanned_files=scan_result.total_files,
            primary_language=profile.primary_language,
            language_percentages=lang_percs,
            frameworks=profile.frameworks,
            cicd=profile.cicd_platforms,
            agents_md_written=write_agents and self.config.output.agents_md,
            agents_md_lines=len(agents_md_content.splitlines()),
            bridge_files_written=bridge_files,
            message=msg,
        )
