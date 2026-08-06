from pathlib import Path
import difflib
from dataclasses import dataclass
from typing import List

from core.config import AppConfig
from core.scanner import CodebaseScanner
from core.analyzer import ProjectAnalyzer
from core.prompt_builder import PromptBuilder
from core.llm_client import LLMClient
from core.bridge_writer import BridgeWriter

@dataclass
class GenerationResult:
    scanned_files: int
    primary_language: str
    language_percentages: str
    frameworks: List[str]
    cicd: List[str]
    agents_md_written: bool
    agents_md_lines: int
    bridge_files_written: List[str]
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
            self.workspace_path, 
            self.config.scan.exclude_dirs, 
            self.config.scan.max_file_size_kb
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
            bridge_writer = BridgeWriter(self.workspace_path, self.config.output, profile)
            bridge_files = bridge_writer.write_all()
            
        total = sum(scan_result.language_counts.values())
        lang_percs = ""
        if total > 0:
            top_langs = sorted(scan_result.language_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            lang_percs = ", ".join(f"{l} ({int(c/total*100)}%)" for l, c in top_langs)
            
        return GenerationResult(
            scanned_files=scan_result.total_files,
            primary_language=profile.primary_language,
            language_percentages=lang_percs,
            frameworks=profile.frameworks,
            cicd=profile.cicd_platforms,
            agents_md_written=write_agents and self.config.output.agents_md,
            agents_md_lines=len(agents_md_content.splitlines()),
            bridge_files_written=bridge_files,
            message=msg
        )
