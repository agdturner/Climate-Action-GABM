"""Contracts for root-authored documentation staging and cleanup."""

import subprocess
import sys
from pathlib import Path

import pytest

import docs
from docs_assets import DOC_FILES, GITHUB_DOC_FILES, STAGED_NAMES


@pytest.mark.parametrize("target,expected", [
    ("README.md#overview", "project_readme.md#overview"),
    ("./GABM_Refactor_Plan.md", "GABM_Refactor_Plan.md"),
    ("docs/Code_Tour.md", "Code_Tour.md"),
    ("src/cag/abm/attributes/politics.py", docs.REPOSITORY_URL + "src/cag/abm/attributes/politics.py"),
    ("tests/test_gabm_compatibility.py", docs.REPOSITORY_URL + "tests/test_gabm_compatibility.py"),
    ("requirements-dev.txt", docs.REPOSITORY_URL + "requirements-dev.txt"),
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
        (root / name).write_text(f"# {name}\n\n[project](README.md)\n")
    for name in GITHUB_DOC_FILES:
        (root / ".github" / name).write_text(f"# {name}\n")
    monkeypatch.setattr(docs, "ROOT", str(root))
    monkeypatch.setattr(docs, "DOCS", str(staged))
    before = {p: p.read_bytes() for p in root.iterdir() if p.is_file()}
    docs.main()
    assert index.read_text() == "Authored documentation index\n"
    assert (staged / STAGED_NAMES["README.md"]).exists()
    assert (staged / "DEV_GUIDE.md").exists()
    assert "[project](project_readme.md)" in (staged / "GABM_Refactor_Plan.md").read_text()

    script = Path(docs.__file__).with_name("docs-clean.py").read_text()
    script = script.replace(
        'ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))',
        f"ROOT = {str(root)!r}",
    )
    subprocess.run([sys.executable, "-c", script], check=True)
    assert index.read_text() == "Authored documentation index\n"
    assert all(not (staged / STAGED_NAMES.get(name, name)).exists() for name in DOC_FILES)
    assert all(path.read_bytes() == content for path, content in before.items())
