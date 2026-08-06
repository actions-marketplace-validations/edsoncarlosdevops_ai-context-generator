import json
from dataclasses import asdict
from core.analyzer import ProjectProfile
from core.config import AppConfig

class PromptBuilder:
    def __init__(self, config: AppConfig):
        self.config = config

    def build(self, profile: ProjectProfile) -> str:
        profile_json = json.dumps(asdict(profile), indent=2)
        
        base_prompt = f"""
You are an expert software architect and technical lead.
Your task is to generate a project governance file called AGENTS.md based on the provided project profile.

Language for output: {self.config.generator.language}
Maximum lines: {self.config.generator.max_lines}

The file MUST follow these constraints:
1. Open with "# {{domain-specific title}} — Agent Governance Guidelines"
2. Have a short 1-paragraph description of what the project does (inferred from tech stack)
3. Organize rules by detected domains (e.g. API Design, Database Safety, CI/CD Standards)
4. Each rule MUST BE actionable and checkable during a code review, avoiding generic platitudes.
5. Stay strictly under {self.config.generator.max_lines} lines.
6. Use markdown formatting.

Project Profile:
{profile_json}
"""
        if profile.existing_agents_md:
            enrich_prompt = f"""
An existing AGENTS.md was found. Analyse it and enrich it by adding only rules that are missing, relevant, and non-redundant. Do NOT duplicate existing rules. Do NOT change the overall structure unless it is clearly wrong. Keep the file under {self.config.generator.max_lines} lines.

Existing AGENTS.md:
{profile.existing_agents_md}
"""
            return base_prompt + "\n" + enrich_prompt
            
        return base_prompt
