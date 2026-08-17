# Contributing to AI Context Generator

Thank you for your interest in contributing to **AI Context Generator**! We welcome contributions from developers of all skill levels to help build the universal context layer for AI coding tools.

---

## 🛠️ Local Development Setup

### Prerequisites
- Python 3.11 or higher
- `git`

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/edsoncarlosdevops/ai-context-generator.git
cd ai-context-generator

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### 2. Testing Your Changes Locally

Run dry-run mode on any repository without calling the LLM or writing files:

```bash
ai-context-generator generate --workspace . --dry-run
```

To test actual LLM generation using Ollama locally:

```bash
ai-context-generator generate \
  --workspace . \
  --api-key dummy \
  --base-url http://localhost:11434/v1 \
  --model llama3 \
  --dry-run
```

---

## 🧪 Running Tests & Quality Checks

Before submitting a Pull Request, please ensure all checks pass:

```bash
# Run unit tests
pytest tests/

# Run linter
ruff check ai_context_generator/

# Run format check
ruff format ai_context_generator/ --check
```

---

## 🚀 How to Add Support for a New AI Tool Bridge

1. Open `ai_context_generator/scanner.py` and add the tool's signature file to `AI_TOOL_SIGNATURES`.
2. Open `ai_context_generator/config.py` and add a boolean flag to `OutputConfig`.
3. Open `ai_context_generator/bridge_writer.py` and add the file generator method.
4. Update `examples/.ai_context.toml` and `README.md` to reflect the new tool.
5. Add unit test coverage in `tests/test_bridge_writer.py`.

---

## 📜 Pull Request Guidelines

1. **Keep PRs focused**: Solve one problem per PR.
2. **Include tests**: Add unit tests for any new features or bug fixes.
3. **Update docs**: Update `README.md` or `.ai_context.toml` examples if configuration options changed.
4. **Pass CI**: Ensure the GitHub Actions CI workflow passes completely.

---

## 📄 License
By contributing, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
