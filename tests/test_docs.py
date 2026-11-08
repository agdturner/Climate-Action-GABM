"""Contracts for root-authored documentation staging and cleanup."""

import subprocess
import os
import sys
from pathlib import Path

import pytest

import docs
from docs_assets import DOC_FILES, GITHUB_DOC_FILES, STAGED_NAMES, GENERATED_DOC_FILES


@pytest.mark.parametrize("target,expected", [
    ("README.md#overview", "project_readme.md#overview"),
    ("./GABM_Refactor_Plan.md", "GABM_Refactor_Plan.md"),
    ("documentation/guides/Code_Tour.md", "Code_Tour.md"),
    ("documentation/guides/AIRE_Quickstart.md", "AIRE_Quickstart.md"),
    ("src/cag/abm/attributes/politics.py", docs.REPOSITORY_URL + "src/cag/abm/attributes/politics.py"),
    ("tests/test_gabm_compatibility.py", docs.REPOSITORY_URL + "tests/test_gabm_compatibility.py"),
    ("requirements-dev.txt", "requirements-dev.txt"),
    ("#overview", "#overview"),
    ("https://example.org/README.md", "https://example.org/README.md"),
    ("missing-guide.md", "missing-guide.md"),
])
def test_staged_links(target, expected):
    assert docs.update_links(f"[link]({target})") == f"[link]({expected})"


def test_copy_and_cleanup_preserve_authored_sources(tmp_path, monkeypatch):
    root = tmp_path
    staged = root / "docs"
    staged.mkdir()
    index = staged / "README.md"
    index.write_text("Authored documentation index\n")
    (root / ".github").mkdir()
    for name in DOC_FILES:
        source = root / name
        source.parent.mkdir(parents=True, exist_ok=True)
        project_link = os.path.relpath(root / "README.md", source.parent).replace(os.sep, "/")
        source.write_text(
            "<!DOCTYPE html><html><body>Handover</body></html>\n"
            if name.endswith(".html") else f"# {name}\n\n[project]({project_link})\n"
        )
    for name in GITHUB_DOC_FILES:
        (root / ".github" / name).write_text(f"# {name}\n")
    monkeypatch.setattr(docs, "ROOT", str(root))
    monkeypatch.setattr(docs, "DOCS", str(staged))
    before = {root / name: (root / name).read_bytes() for name in DOC_FILES}
    docs.main()
    assert index.read_text() == "Authored documentation index\n"
    assert (staged / STAGED_NAMES["README.md"]).exists()
    assert (staged / "DEV_GUIDE.md").exists()
    assert "[project](project_readme.md)" in (staged / "AIRE_Quickstart.md").read_text()
    assert "[project](project_readme.md)" in (staged / "GABM_Refactor_Plan.md").read_text()
    for name in ("requirements.txt", "requirements-dev.txt"):
        mirror = (staged / name.replace(".txt", ".md")).read_text()
        assert "```text\n" + before[root / name].decode() + "\n```" in mirror
    for name in DOC_FILES:
        if name.startswith("documentation/"):
            if name.endswith(".html"):
                assert (staged / STAGED_NAMES[name]).read_bytes() == before[root / name]
                continue
            relative = os.path.relpath(
                staged / STAGED_NAMES["README.md"],
                (staged / STAGED_NAMES[name]).parent,
            ).replace(os.sep, "/")
            assert f"[project]({relative})" in (
                staged / STAGED_NAMES[name]
            ).read_text()

    script = Path(docs.__file__).with_name("docs-clean.py").read_text()
    script = script.replace(
        'ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
        f"ROOT = {str(root)!r}",
    )
    subprocess.run([sys.executable, "-c", script], check=True)
    assert index.read_text() == "Authored documentation index\n"
    assert all(not (staged / STAGED_NAMES.get(name, name)).exists() for name in DOC_FILES)
    assert all(not (staged / name).exists() for name in GENERATED_DOC_FILES)
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize("target,expected", [
    ("AIRE_HPC_repo_primer.md", "AIRE_HPC_repo_primer.md"),
    ("../../DEV_QUICKSTART.md#setup", "DEV_QUICKSTART.md#setup"),
    ("../../scripts/aire/run.sh", docs.REPOSITORY_URL + "scripts/aire/run.sh"),
    ("Code_Tour.md", "Code_Tour.md"),
    ("Simulation_Configuration_Guide.md#layer-2", "Simulation_Configuration_Guide.md#layer-2"),
    ("../research/Model_Design.md", "Model_Design.md"),
    ("../../../outside.md", "../../../outside.md"),
])
def test_nested_authored_links(target, expected):
    assert docs.update_links(
        f"[link]({target})", "documentation/guides/AIRE_Quickstart.md",
    ) == f"[link]({expected})"


def test_staged_guide_names_are_unique():
    names = [STAGED_NAMES.get(name, name) for name in DOC_FILES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("target,expected", [
    ("research_notes.md", "research_notes.md"),
    ("../guides/Run_Output_Guide.md", "Run_Output_Guide.md"),
    ("../../data/fixtures/cag_integration_baseline.json",
     docs.REPOSITORY_URL + "data/fixtures/cag_integration_baseline.json"),
    ("../../USER_GUIDE.md", "USER_GUIDE.md"),
    ("Climate%20Policy%20Research%20for%20Agent-Based%20Model.md",
     "supplementary_docs/Climate%20Policy%20Research%20for%20Agent-Based%20Model.md"),
])
def test_research_source_links(target, expected):
    assert docs.update_links(
        f"[link]({target})", "documentation/research/result_report.md",
    ) == f"[link]({expected})"


@pytest.mark.parametrize("target,expected", [
    ("../research/Model_Design.md#history", "../Model_Design.md#history"),
    ("../guides/Code_Tour.md", "../Code_Tour.md"),
    ("github_issues_v2.md", "github_issues_v2.md"),
    ("../research/Literature_Political_Exposure.md", "Literature_Political_Exposure.md"),
    ("../../src/cag/abm/agent.py", docs.REPOSITORY_URL + "src/cag/abm/agent.py"),
])
def test_nested_staged_archive_links(target, expected):
    assert docs.update_links(
        f"[link]({target})", "documentation/archive/github_issues.md",
    ) == f"[link]({expected})"
