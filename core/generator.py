import difflib
from dataclasses import dataclass
from pathlib import Path

from core.analyzer import ProjectAnalyzer
from core.bridge_writer import BridgeWriter
from core.config import AppConfig
from core.llm_client import LLMClient
from core.prompt_builder import PromptBuilder
from core.scanner import CodebaseScanner


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

    def generate(self, force_replace: bool = False) -> GenerationResult:
        scanner = CodebaseScanner(
            self.workspace_path, self.config.scan.exclude_dirs, self.config.scan.max_file_size_kb
        )
        scan_result = scanner.scan()

        analyzer = ProjectAnalyzer()
        profile = analyzer.analyze(scan_result)

        prompt_builder = PromptBuilder(self.config)
        prompt = prompt_builder.build(profile)

        agents_md_content = self.llm_client.generate(prompt)

        agents_md_path = self.workspace_path / "AGENTS.md"
        write_agents = True
        msg = ""

        if not force_replace and profile.existing_agents_md:
            delta = self._calculate_delta(profile.existing_agents_md, agents_md_content)
            if delta <= 0.10:
                write_agents = False
                msg = "AGENTS.md already up-to-date, no changes needed."
            else:
                msg = f"Enriched AGENTS.md (delta: {delta:.1%})"
        else:
            msg = "Created new AGENTS.md"

        if write_agents and self.config.output.agents_md:
            agents_md_path.write_text(agents_md_content, encoding="utf-8")

        bridge_files = []
        if write_agents:
            # Smart bridge selection: only generate bridges for tools already used in this project.
            # If no tools are detected, generate all bridges (first-time setup).
            effective_output = self.config.output
            if scan_result.detected_ai_tools:
                from dataclasses import replace as dc_replace

                effective_output = dc_replace(
                    self.config.output,
                    cursorrules="cursor" in scan_result.detected_ai_tools,
                    windsurfrules="windsurf" in scan_result.detected_ai_tools,
                    clinerules="cline" in scan_result.detected_ai_tools,
                    zed_rules="zed" in scan_result.detected_ai_tools,
                    aider_conventions="aider" in scan_result.detected_ai_tools,
                    claude_md="claude" in scan_result.detected_ai_tools,
                    copilot_instructions="copilot" in scan_result.detected_ai_tools,
                    amazonq_rules="amazonq" in scan_result.detected_ai_tools,
                    continue_rules="continue" in scan_result.detected_ai_tools,
                )
            bridge_writer = BridgeWriter(self.workspace_path, effective_output, profile)
            bridge_files = bridge_writer.write_all()

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
