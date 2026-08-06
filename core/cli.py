import argparse
import os
from pathlib import Path

from core.config import load_config
from core.llm_client import LLMClient
from core.generator import ContextGenerator

def main():
    parser = argparse.ArgumentParser(prog="ai-context-generator", description="Generate AGENTS.md and context files automatically.")
    
    subparsers = parser.add_subparsers(dest="command")
    gen_parser = subparsers.add_parser("generate")
    
    gen_parser.add_argument("--workspace", type=str, default=".", help="Path to the repository root")
    gen_parser.add_argument("--config", type=str, help="Path to .ai_context.toml")
    gen_parser.add_argument("--api-key", type=str, help="LLM API key (or env var AI_API_KEY)")
    gen_parser.add_argument("--model", type=str, help="LLM model override")
    gen_parser.add_argument("--language", type=str, help="Output language")
    gen_parser.add_argument("--replace", action="store_true", help="Replace existing AGENTS.md instead of enriching")
    gen_parser.add_argument("--dry-run", action="store_true", help="Preview generated AGENTS.md without writing files")
    gen_parser.add_argument("--no-bridge", action="store_true", help="Skip generating bridge files")
    
    args = parser.parse_args()
    
    if args.command == "generate":
        workspace_path = Path(args.workspace).resolve()
        config_path = Path(args.config).resolve() if args.config else None
        
        config = load_config(workspace_path, config_path)
        
        if args.model:
            config.generator.model = args.model
        if args.language:
            config.generator.language = args.language
        if args.no_bridge:
            config.output.cursorrules = False
            config.output.claude_md = False
            config.output.copilot_instructions = False
            
        api_key = args.api_key or os.environ.get("AI_API_KEY")
        if not api_key:
            print("Error: API key is required via --api-key or AI_API_KEY env var.")
            return 1
            
        llm_client = LLMClient(api_key, config.generator.model, config.generator.base_url)
        
        generator = ContextGenerator(workspace_path, config, llm_client)
        
        if args.dry_run:
            print("Dry run not fully implemented in preview, but would skip writing.")
            return 0
            
        result = generator.generate(force_replace=args.replace)
        
        print(f"✓ Scanned {result.scanned_files} files — {result.language_percentages}")
        
        detected = []
        if result.frameworks: detected.extend(result.frameworks)
        if result.cicd: detected.extend(result.cicd)
        if detected:
            print(f"✓ Detected: {', '.join(detected)}")
            
        if result.agents_md_written:
            print(f"✓ AGENTS.md generated ({result.agents_md_lines} lines)")
        else:
            print(f"✓ AGENTS.md skipped: {result.message}")
            
        for bf in result.bridge_files_written:
            print(f"✓ {bf} → created")

if __name__ == "__main__":
    main()
