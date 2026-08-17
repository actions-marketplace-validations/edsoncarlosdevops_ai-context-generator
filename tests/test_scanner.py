from pathlib import Path

from ai_context_generator.config import DEFAULT_EXCLUDE_DIRS
from ai_context_generator.scanner import CodebaseScanner, _gitignore_dirs


def _scan(tmp_path: Path, files: dict[str, str], **kwargs):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return CodebaseScanner(tmp_path, list(DEFAULT_EXCLUDE_DIRS), 100, **kwargs).scan()


# --------------------------------------------------------------- test detection


def test_tests_directory_is_detected(tmp_path: Path):
    """`tests/foo.py` used to be missed: the check compared the literal 'test'
    against path parts, so the plural directory name never matched."""
    scan = _scan(tmp_path, {"tests/foo.py": "x = 1\n"})
    assert scan.has_tests is True


def test_spec_directory_is_detected(tmp_path: Path):
    scan = _scan(tmp_path, {"spec/models_spec.rb": "describe\n"})
    assert scan.has_tests is True


def test_test_filename_conventions_are_detected(tmp_path: Path):
    for name in ("test_api.py", "api_test.go", "api.test.ts", "api.spec.ts"):
        scan = _scan(tmp_path, {f"src/{name}": "x\n"})
        assert scan.has_tests is True, name


def test_latest_is_not_a_test_file(tmp_path: Path):
    """Substring matching flagged 'latest_release.py' and 'contest.py' as tests."""
    scan = _scan(tmp_path, {"src/latest_release.py": "x\n", "src/contest.py": "y\n"})
    assert scan.has_tests is False


# ------------------------------------------------------------- directory pruning


def test_default_excludes_cover_common_build_dirs(tmp_path: Path):
    files = {"src/app.py": "x\n"}
    for noisy in ("venv", "target", "vendor", ".next", "coverage", "node_modules"):
        files[f"{noisy}/junk.py"] = "y\n"
    scan = _scan(tmp_path, files)
    assert scan.total_files == 1
    assert scan.directory_tree == ["src"]


def test_gitignore_directories_are_skipped(tmp_path: Path):
    scan = _scan(
        tmp_path,
        {".gitignore": "artifacts/\ngenerated\n", "artifacts/a.py": "x\n", "generated/b.py": "y\n"},
    )
    # Only .gitignore itself remains.
    assert scan.total_files == 1


def test_gitignore_can_be_disabled(tmp_path: Path):
    scan = _scan(
        tmp_path, {".gitignore": "artifacts/\n", "artifacts/a.py": "x\n"}, use_gitignore=False
    )
    assert scan.total_files == 2


def test_gitignore_parser_ignores_globs_and_negations(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("*.log\n!keep\n# comment\n\nbuild/\nsub/dir\nout\n")
    assert _gitignore_dirs(tmp_path) == {"build", "out"}


# ------------------------------------------------------------ structural evidence


def test_collects_structure_entry_points_and_config(tmp_path: Path):
    scan = _scan(
        tmp_path,
        {
            "src/main.py": "print(1)\n",
            "src/domain/user.py": "x\n",
            "pyproject.toml": "[project]\nname='x'\ndependencies=['httpx']\n",
            "Makefile": "test:\n\tpytest\nbuild:\n\techo\n",
        },
    )
    assert "src" in scan.directory_tree
    assert "src/domain" in scan.directory_tree
    assert scan.entry_points == ["src/main.py"]
    assert set(scan.config_files) == {"pyproject.toml", "Makefile"}
    assert "make test" in scan.test_commands
    assert "make build" in scan.build_commands
    assert "httpx" in scan.dependencies


def test_generated_artifacts_never_enter_the_profile(tmp_path: Path):
    """The tool's own output must not change the profile, or every run would
    invalidate the cached signature and trigger a new paid LLM call."""
    scan = _scan(
        tmp_path,
        {
            "src/app.py": "x\n",
            "CLAUDE.md": "generated\n",
            ".github/copilot-instructions.md": "generated\n",
            ".continue/rules.md": "generated\n",
            ".amazonq/rules/project-rules.md": "generated\n",
        },
    )
    assert scan.directory_tree == ["src"]
    assert scan.config_files == []


def test_max_files_cap_marks_result_truncated(tmp_path: Path):
    files = {f"src/m{i}.py": "x\n" for i in range(10)}
    scan = _scan(tmp_path, files, max_files=3)
    assert scan.truncated is True
    assert scan.total_files == 4  # cap + the file that tripped it


def test_untruncated_scan_is_not_flagged(tmp_path: Path):
    scan = _scan(tmp_path, {"a.py": "x\n"})
    assert scan.truncated is False


# ------------------------------------------------------------- manifest parsing


def test_parses_package_json(tmp_path: Path):
    scan = _scan(
        tmp_path,
        {
            "package.json": (
                '{"dependencies":{"react":"18"},"devDependencies":{"vitest":"1"},'
                '"scripts":{"test":"vitest","build":"tsc"}}'
            )
        },
    )
    assert {"react", "vitest"} <= set(scan.dependencies)
    assert "npm run test" in scan.test_commands
    assert "npm run build" in scan.build_commands


def test_parses_poetry_dependencies(tmp_path: Path):
    scan = _scan(
        tmp_path,
        {
            "pyproject.toml": (
                "[tool.poetry.dependencies]\npython='^3.11'\nfastapi='^0.110'\n"
                "[tool.poetry.group.dev.dependencies]\npytest='^8'\n"
            )
        },
    )
    assert {"fastapi", "pytest"} <= set(scan.dependencies)
    assert "python" not in scan.dependencies


def test_parses_go_mod_and_cargo(tmp_path: Path):
    scan = _scan(
        tmp_path,
        {
            "go.mod": "module example.com/app\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n)\n",
            "Cargo.toml": '[dependencies]\naxum = "0.7"\n',
        },
    )
    assert "github.com/gin-gonic/gin" in scan.dependencies
    assert "axum" in scan.dependencies


def test_malformed_manifest_does_not_crash(tmp_path: Path):
    scan = _scan(tmp_path, {"package.json": "{ not json", "Cargo.toml": "[[[["})
    assert scan.dependencies == []


def test_detects_existing_ai_tools(tmp_path: Path):
    scan = _scan(tmp_path, {".cursorrules": "x\n", "CLAUDE.md": "y\n"})
    assert set(scan.detected_ai_tools) == {"cursor", "claude"}


def test_oversized_files_are_skipped(tmp_path: Path):
    (tmp_path / "big.py").write_text("x" * 5000)
    (tmp_path / "small.py").write_text("x\n")
    scan = CodebaseScanner(tmp_path, list(DEFAULT_EXCLUDE_DIRS), max_file_size_kb=1).scan()
    assert scan.total_files == 1
