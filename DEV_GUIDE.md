# Developer Guide


## Table of Contents
- [Overview](#overview)
- [Contributing and Communicating](#contributing-and-communicating)
- [Project Directories](#project-directories)
- [Testing](#testing)
- [Cross-Repository Refactoring](#cross-repository-refactoring)
- [Python Package Entry Point](#python-package-entry-point)
- [Makefile Targets](#makefile-targets)
- [Developing Documentation](#developing-documentation)
- [Packaging and Deployment](#packaging-and-deployment)
- [Branch Protection](#branch-protection)
- [Maintainer Guide](#maintainer-guide)
- [Branch and Documentation Deployment](#branch-and-documentation-deployment)
- [GitHub Copilot](#github-copilot)
- [Managing Logs and Caches](#managing-logs-and-caches)
- [Files and Directories Excluded from Version Control](#files-and-directories-excluded-from-version-control)


## Overview
The Climate-Action-GABM developer guide provides guidance for developers some of which are also maintainers.

Please follow the [Developer Quick Start Guide](DEV_QUICKSTART.md) to get set up to contribute as a developer.

In the rest of the document "you" means you as a Climate-Action-GABM developer.


## Contributing and Communicating
Please follow the [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

For the time being, please communicate by commenting on or raising new [Climate-Action-GABM Repository Issues](https://github.com/compolis/Climate-Action-GABM/issues).

You should have forked the [Climate-Action-GABM Repository](https://github.com/compolis/Climate-Action-GABM) to your own GitHub account.

The general workflow for contributing is to:
- Create and check out a new local branch:

```bash
git branch my_feature
git checkout my_feature
```

- Make changes:
  - For each Python file edited, please adjust the Metadata at the top of the file by:
    - Adding your details to the `__author__` list
    - Incrementing the `__version__`
  - Update the [Change Log](CHANGE_LOG.md) with a summary of your changes.
- Commit changes with a clear message. For example:

```bash
git add .
git commit -m "Clear message that explains changes." 
```

- Ensure tests pass and documentation builds before submitting a PR:

```bash
make test
make docs
```

- Push to your Fork, For example:

```bash
git push origin my_feature
```

- Open a PR on GitHub to merge your `my_feature` branch into the the `main` branch of the upstream Climate-Action-GABM Repository.
  - Please refer to any related issues in the PR comments.
- The PR will be reviewed and once the review is complete, the changes will be merged.


## Project Directories
The root project directory contains documentation and files needed for building and deploying. The sub-diretories include: 
- `data/`: For data including log files
- `dist/`: Output directory for built distributions.
- `docs/`: Documentation
- `scripts/`: Utility scripts
- `src/`: Python source code
- `tests/`: Test suite for src
- `venv-build-test/`: For temporary virtual environments created for testing.


## Testing

Climate-Action-GABM uses [pytest](https://docs.pytest.org/) for unit and integration tests. The unit test suite is located in the `tests/` directory, mirroring the module structure.

### Running Tests

Run most tests with:
  ```bash
  make test
  ```
or:
  ```bash
  pytest
  ```

### Adding Tests

Please add or update tests when modifying or adding features. Aim for high test coverage to catch regressions and ensure code reliability.

### Test Workflow

- PRs should pass the test workflow before being merged.
- See `.github/workflows/test.yml` for Continuous Integration (CI) details.


## Cross-Repository Refactoring

For work that moves reusable CAG capabilities into GABM, follow the
[CAG to GABM Refactor Plan](GABM_Refactor_Plan.md). It records the published
dependency audit, ownership boundaries, implementation sequence, and validation
gates; the [roadmap](ROADMAP.md#cag-to-gabm-refactor-track) records the strategic
goal.

Establish deterministic integration evidence before runtime edits. Develop
generic APIs and tests in GABM, retain CAG-specific research logic and tests
here, and wire one bounded extraction at a time. An isolated editable GABM
checkout is appropriate for development, but validate CAG against the built
wheel and the subsequent published release before updating production pins.
Do not change prompts, random-number usage, cache policy, output schemas, or
checkpoint/resume behaviour incidentally during extraction.

Update the plan's progress with test and comparison evidence after each slice.


## Python Package Entry Point

The main entry point for the Climate-Action-GABM package is `src/cag/__main__.py`. This allows the application to be run using:

	python3 -m cag

This approach is preferred over directly running a script (like `run.py`) as:
  - It enables Python to treat `cag` as a package, ensuring imports work correctly.
  - It is the standard way to provide a command-line entry point for Python packages.
  - It makes the project ready for distribution and installation.

The `__main__.py` file is executed when you run `python3 -m cag` from the project root (with `src` on the Python path). If you need to add or change the main application logic, edit `src/cag/__main__.py`.

Please see the [Python Packaging documentation](https://docs.python.org/3/library/__main__.html) for information about Python packaging.


## Makefile Targets

The root directory contains a [Makefile](https://www.gnu.org/software/make/manual/make.html#Introduction). This is set up to automate tasks using [GNU Make](https://www.gnu.org/software/make). This section explains the rules or targets in the Makefile. Please ensure any changes to the Makefile are platform agnostic.


### Target Chaining, DRY, and Consistency

For maintainability, all Makefile targets that depend on other build steps should use Make's built-in dependency chaining (e.g., `gh-pages-deploy: docs`) rather than manually invoking `$(MAKE)` or shelling out to `make` within a target. This ensures:
- Each target is only responsible for its own logic.
- Consistency: all targets use the same build steps, and changes to one target (like `docs`) automatically propagate to dependents (like `gh-pages-deploy`). The following is a presentation of the Makefile rules/targets:

| Target         | Usage/Description                                                                 |
|--------------- |----------------------------------------------------------------------------------|
| `make help`    | Show available Makefile commands                                                  |
| `make test`    | Run all tests (pytest)                                                            |
| `make docs`    | Build documentation (Sphinx) and clean auto-copied docs assets                    |
| `make docs-build` | Build documentation (Sphinx)                                                      |
| `make docs-clean` | Remove auto-copied documentation files from docs/                              |
| `make gh-pages-deploy` | Build and deploy documentation to GitHub Pages (runs scripts/gh-pages-deploy.py) |
| `make clean`   | Remove build/test artifacts and Python caches                                     |
| `make clear-caches` | Delete all LLM caches and model lists (for a clean slate)                    |
| `make git-clean` | Clean up merged local branches and prune deleted remotes                        |
| `make sync`    | Sync main branch with upstream                                                    |
| `make sync-feature BRANCH=release/0.2.0` | Sync and rebase a feature/release branch onto main     |
| `make release VERSION=x.y.z BRANCH=release/x.y.z` | Tag and push a release (platform-agnostic)     |
| `make delete-release VERSION=x.y.z` | Delete a release tag locally and on remotes (origin, upstream) |
| `make build`    | Build a distribution package for PyPI (python -m build)                            |
| `make build-test` | Build and test install the package in a fresh venv                               |
| `make pypi-release` | Upload the built package to PyPI (twine upload dist/*)                         |
| `make testpypi-release` | Upload the built package to TestPyPI (twine upload --repository testpypi dist/*) |
| `make bump-version` | Bump the project version everywhere (patch by default; use `make bump-version part=minor` or `part=major` for other bumps). Uses bump2version and updates all relevant files. |
| `make run-local` | Run cag using local source (PYTHONPATH=src) |
| `make run-installed` | Run cag using installed package |


All Python scripts used by Makefile targets are in the `scripts/` directory and are named consistently with their Makefile targets (e.g., `make docs-clean` runs `scripts/docs-clean.py`).

The `delete-release` target automates deleting a release tag locally and on both remotes (origin, upstream).

Please refer to the Makefile for full details.


## Developing Documentation

### Authored sources and Sphinx staging

Create and maintain prose documentation outside `docs/`. Keep project
entry points, contributor guides, the roadmap, and change history in the
repository root. Longer-form authored material belongs in `documentation/`:

- `documentation/guides/`: maintained usage, code, configuration, and HPC guides.
- `documentation/research/`: design history, research notes, result reports,
  survey documentation, and literature notes.
- `documentation/archive/`: superseded guides and historical planning snapshots.
- `documentation/presentations/`: authored presentation assets such as the
  standalone HTML handover deck.

Create each category as its first source is migrated; empty placeholder
directories are unnecessary. `docs/` is the staging directory where
documentation is copied and pre-processed for Sphinx, not a second place to
author guides or plans.

The exceptions are Sphinx configuration and navigation sources, such as
`docs/conf.py`, `docs/index.md`, and API directives in `docs/api.rst`; these
belong in `docs/` and may be edited directly. Generated documentation copies,
autosummary files, and rendered output are not authoritative sources.

Some existing authored guides still live in `docs/`. Until each is migrated,
edit its existing source rather than deleting it or creating a second copy.
Move these guides incrementally, updating links, staging, navigation, and
cleanup together; no bulk relocation is required.

The AIRE guides, code tour, local LLM setup, prompts/personas V2, output guide,
and configuration guide now have authoritative sources in
`documentation/guides/`. Their original filenames under `docs/` are temporary
staging copies only. The design history, research notes, results report, and
survey documentation now live in `documentation/research/` and are staged
under their original page names. Preserve their research provenance and
historical claims during ownership moves; the design history is not a current
model specification. Supplementary literature/parameterisation notes also live
in `documentation/research/`. Superseded prompts/code tours, older AIRE article
notes, and issue-planning snapshots live in `documentation/archive/`.
Archive placement preserves context; it does not establish that all planned
items were completed or that older cluster advice remains valid.
Their existing `supplementary_docs/` site paths are retained by staging.
The documentation index is authored in `documentation/README.md` and staged as
`docs/documentation_index.md`. Runtime and developer dependency pages are
generated from the root requirement manifests and cleaned after the build;
never edit or commit those mirrors.

The handover deck lives in `documentation/presentations/`. Staging copies its
HTML bytes to `docs/_extra/`; Sphinx's `html_extra_path` publishes it at
`cag_handover_deck.html` beside the built index. Cleanup removes the staged
asset, not its authored source or published output. It is a standalone
presentation, not a generated API page; its external Google Fonts dependency
is retained.

For a new authored Markdown document intended for the Sphinx site:

1. Create the authoritative file in its agreed source location and link it from an
   appropriate entry-point document.
2. Add its repository-relative path to `DOC_FILES` in
   [scripts/docs_assets.py](scripts/docs_assets.py), the shared copy/cleanup
   manifest. Do not register an authored file that exists only in `docs/`:
   cleanup would delete it. For a nested source, add a `STAGED_NAMES` entry
   mapping its source path to the desired filename under `docs/`. Keep staged
   filenames unique. The AIRE guides demonstrate this mapping while retaining
   their existing Sphinx page names.
   Staged paths may include subdirectories; staging creates their parents,
   link rewriting resolves relative to the staged document, and cleanup
   removes only registered files, never authored directories.
3. Add the staged filename to the Project Documents toctree in
   [docs/index.md](docs/index.md).
4. Check links in both the authored source and the rendered site. Paths valid
   at the repository root may need adjustment during staging.
5. Run `make docs` in the development environment. Confirm the source remains
   intact and cleanup removes its staged copy after a successful build.

Only authoritative sources and intentional Sphinx inputs should be committed,
not generated copies or `docs/_build/`.

The project README is staged as `docs/project_readme.md`, using `STAGED_NAMES`
in the shared manifest. The separate authored documentation index lives in
`documentation/README.md`. Sphinx uses `docs/index.md`;
the historical `docs/index.rst` placeholder is excluded from the build.

Staging resolves links relative to each authored source, including nested
guides. Links to other staged documents
stay local, links to existing guides under `docs/` lose that prefix, and links
to repository code, tests, or data point to the upstream GitHub `main` branch.
Unresolved paths remain unchanged so Sphinx can report them. These repository
links describe the current branch on GitHub, not a versioned documentation snapshot.
Markdown heading anchors are enabled for local section links.

When an unmigrated legacy guide in `docs/` references a migrated source, use
its upstream repository URL until that guide is migrated too. This keeps the
link usable both on GitHub and in Sphinx without creating a second authored
copy. Links from migrated sources should be relative to those sources and
are rewritten for Sphinx during staging. The AIRE migration changes ownership
and links only; consolidation and cluster-policy/command verification remain
separate work.

Autosummary does not overwrite existing stubs during ordinary builds. New
generated stubs are ignored by Git; explicit API directives in `docs/api.rst`
remain the maintained API reference. Some stubs are still tracked legacy
generated files; avoid incidental changes to them and migrate their ownership
deliberately. Requirement mirrors are temporary generated files.

Default pytest discovery is limited to `tests/` by `pytest.ini`. This prevents
Python test examples downloaded into Sphinx's HTML output from being collected
as a second test suite after a documentation build.

### Root documents

Keep planning and history separate:

- [ROADMAP.md](ROADMAP.md) is forward-looking: priorities, intended outcomes,
  unfinished work, and dependencies. It is not a release log. When work lands,
  remove or update the relevant planned item and record the delivered change
  in the change log. Keep inherited tasks with uncertain completion explicitly
  marked for evidence reconciliation, rather than silently dropping them or
  treating them as confirmed open work.
- [CHANGE_LOG.md](CHANGE_LOG.md) records delivered changes by release, with an
  Unreleased section for changes awaiting release. Preserve unique historical
  details when moving material from the roadmap; do not duplicate entries.
- [DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md) records dated milestones,
  development context, and reflections, rather than duplicating the release
  log or acting as the current plan.
- Detailed implementation plans, such as
  [GABM_Refactor_Plan.md](GABM_Refactor_Plan.md), hold scope, acceptance gates,
  and progress evidence. Link them from the roadmap instead of repeating them.

Markdown files in the root directory, each serving a specific purpose:
  - [README.md](README.md): A general [README](https://en.wikipedia.org/wiki/README) that links to much of the documentation outlined below including the developer and user guides. It is included in the Sphinx documentation and forms the basis for the main Sphinx documentation page.
  - [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md): Provides details on expected behavior of developers and reporting procedures.
  - [USER_GUIDE.md](USER_GUIDE.md): Provides step-by-step instructions for users to get set, and should provide guidance for using GABM.
  - [DEV_QUICKSTART.md](DEV_QUICKSTART.md) Provides step-by-step instructions for developers to get set up for contributing to GABM development.
  - [DEV_GUIDE.md](DEV_GUIDE.md): Explains how to contribute to GABM as a developer. It provides details about project structure, and workflow guidance.
  - [API_KEYS.md](API_KEYS.md): Explains how to create a file containing API keys for communicating with LLMs.
  - [ROADMAP.md](ROADMAP.md): Forward-looking priorities, planned features, and unfinished development goals.
  - [GABM_Refactor_Plan.md](GABM_Refactor_Plan.md): Maintained plan and acceptance gates for extracting reusable CAG capabilities into GABM.
  - [CHANGE_LOG.md](CHANGE_LOG.md): Delivered changes and updates organised by release.
  - [DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md): Dated development milestones, context, and reflections.

- Add API docs via `docs/index.md` or `docs/api.rst`.


### Sphinx Documentation

To build run:

```bash
make docs
```

- This effectively runs `scripts/docs.py` to copy key documentation files from the project root to the `docs/` directory, pre-processes them for building the Sphinx documentation, then delete those copied files once the build completes.

**Note on Sphinx/MyST Documentation Warnings:**

When building the documentation with [Sphinx](https://www.sphinx-doc.org/) and [MyST](https://mystmd.org/), you may see warnings like:

  Document headings start at H2, not H1 [myst.header]
  document isn't included in any toctree [toc.not_included]
  duplicate object description ... use :no-index: for one of them
  WARNING: Field list ends without a blank line; unexpected unindent. [docutils]
  'myst' cross-reference target not found: ... [myst.xref_missing]

Warnings do not necessarily stop HTML generation, but a successful build is
not a warning-clean validation. In particular, `myst.xref_missing` means a
link or cross-reference could not be resolved and may be broken in the site.
Fix warnings introduced by a change and record remaining historical warnings
as explicit follow-up work; do not suppress them globally or assume that all
are harmless.

For a complete warning audit, rather than an incremental build, stage the
sources and force Sphinx to reread all documents:

```bash
make docs-make
sphinx-build -E -a -b html docs docs/_build/html > /tmp/cag-docs-build.log 2>&1
make docs-clean
```

Check the Sphinx command's exit status and log before cleanup; cleanup success
does not prove that the build succeeded. Normal `make docs` runs cleanup only
after a successful build, including with `make -j`.


Preview the Sphinx documentation by opening `docs/_build/html/index.html` in a [Web browser](https://en.wikipedia.org/wiki/Web_browser).

To deploy the Sphinx Documentation run:

```bash
make gh-pages-deploy
```

This should deploy/update the `gh-pages` branch on your origin Fork. If your Fork uses the `gh-pages` branch for [GitHub Pages](https://docs.github.com/en/pages), then the documentation should update there.

If it all looks good. Please submit a PR to incorporate documentation changes into main. A maintainer will subsequently update the upstream repository gh-pages branch.

#### Sphinx API Documentation and Autosummary


Climate-Action-GABM uses Sphinx with the autosummary extension to generate API documentation for all major modules. To document new modules:

- Import the new module in the appropriate `__init__.py` file so Sphinx can discover it (e.g., add `from .my_module import *`).
- Add the module to the API Reference toctree in `docs/index.md` (as an `_autosummary/` entry) to ensure it appears in the documentation navigation.
- You do not need to manually maintain individual `.rst` files for each module; autosummary will generate them automatically during `make docs`.
- If you remove or rename modules, update both the `__init__.py` imports and the API Reference list in `docs/index.md`.
- You may delete stale `.rst` files in `_autosummary` if they are no longer referenced.

Preview the Sphinx documentation by opening `docs/_build/html/index.html` in a web browser.


## Packaging and Deployment

The following files and directories are essential for building, testing, and distributing the Climate-Action-GABM package:
- **pyproject.toml**: Declares build system requirements and project metadata. Required for modern Python packaging (PEP 517/518).
- **setup.cfg**: Contains static package metadata and configuration for setuptools, such as:
	- Package name, version, author, and description
	- Python version requirements
	- Entry points (e.g., console_scripts)
	- Classifiers and other options
	This file is preferred over setup.py for static, declarative configuration.
- **MANIFEST.in**: Informs setuptools which additional files (beyond Python modules) to include in the source distribution (sdist). This should be updated so users who install from source get all necessary files.
- **requirements.txt**: Lists pinned dependencies for end users (used by pip install -r requirements.txt).
- **requirements-dev.txt**: Lists development dependencies (testing, linting, docs) with version ranges for contributors.
- **requirements-local.txt**: Optional dependencies for the `provider="local"` LLM backend (e.g. `mlx-lm` on Apple Silicon). Not required for cloud-only runs; see [docs/Local_LLM_Setup_Guide.md](documentation/guides/Local_LLM_Setup_Guide.md).
- **dist/**: Output directory for built distributions (.tar.gz and .whl files) after running the build process.
- **src/cag.egg-info/**: Metadata directory created by setuptools during build. Contains information about the package (version, dependencies, etc.). Safe to delete; will be recreated as needed.
- **venv-build-test/**: Temporary virtual environment created by `make build-test` for testing the built package in isolation. This can be safely deleted after testing.


## Branch Protection
[GitHub Actions](https://github.com/features/actions) workflows are used to help manage Pull Requests (PRs):
- `.github/workflows/test.yml` automatically runs `make test` on PRs to the main branch.
- `.github/workflows/gh-pages-deploy.yml` builds documentation for the gh-pages branch and is for automated docs deployment.

PRs to the [Climate-Action-GAB Repository main branch](https://github.com/compolis/Climate-Action-GABM/tree/main) must pass the test workflow before merging.

The gh-pages branch is protected from deletion.


## Maintainer Guide

This section is aimed at developers that are maintainers. Developers that are not maintainers are requested to refrain from publishing releases to PyPI so maintainers can ensure project integrity and security.


### PyPI Release Process
To release a new version of Climate-Action-GABM to [PyPI](https://pypi.org/), follow these steps:

1. **Update Version**: Run `make bump-version` to update the version everywhere (including setup.cfg, pyproject.toml, src/cag/__init__.py, requirements-dev.txt, and all occurrences in [User Guide](USER_GUIDE.md)). Use `make bump-version part=minor` or `part=major` for non-patch bumps. Commit and push the changes before continuing.
2. **Build the Package**:
	```sh
	make build
	```
	This creates .tar.gz and .whl files in the dist/ directory.
3. **Test the Build**:
	```sh
	make build-test
	```
	This installs the built package in a clean environment and runs the test suite.
4. **Upload to TestPyPI (optional but recommended):**
	```sh
	make testpypi-release
	```
	This uploads the package to TestPyPI. Test installation from TestPyPI in a clean environment:
	```sh
	pip install --index-url https://test.pypi.org/simple/ gabm
	```
	You will need to have an account on https://test.pypi.org and have created an API key for this to work.
5. **Upload to PyPI:**
	```sh
	make pypi-release
	```
	This uploads the package to the official PyPI repository.
	You will need to have an account on https://pypi.org and have created an API key for this to work.
6. **Verify Release:**
	- Check the PyPI page and test installation as a user ensuring the instructions in the [User Guide](USER_GUIDE.md) work.

For more details, see the [Python Packaging User Guide](https://packaging.python.org/).


### Branch and Documentation Deployment

Sphinx documentation is built and deployed using `make gh-pages-deploy`. If the upstream `gh-pages` branch is out of sync or needs to be replaced, use `git push --force upstream gh-pages` to overwrite it with the correct local version. This should be done with care, as it replaces the branch history. 

When deploying documentation with `make gh-pages-deploy`, you may encounter an error like:

```
fatal: 'gh-pages' is already used by worktree at '/tmp/gh-pages-xxxx...'
```

This occurs if a previous deployment left a lingering worktree directory for the `gh-pages` branch. The deployment script should automatically check for and removes any existing worktree before adding a new one. If you encounter this error, manually remove the worktree:

```
git worktree remove /tmp/gh-pages-xxxx...
```

For more details, see the comments in the Makefile and the deployment script.


## GitHub Copilot

Using [GitHub Copilot](https://github.com/features/copilot)) for [vibe coding](https://en.wikipedia.org/wiki/Vibe_coding), can help with understanding workflows and developing documentation, code and tests.

GitHub Copilot uses limited context and the chat context does not currently persist between sessions. As a result, it is good to develop/update documentation along with changes. GitHub Copilot can be asked to read the [README](README.md) and [Developer Guide](DEV_GUIDE.md) at the start of a session so as to be more context aware and provide better support.


## Managing Logs and Caches

Logs and caches (including prompt/response caches for LLM services) are generated during development and use. These files can become large. Typically they are not committed to the repository.

Project Python scripts use Python logging and write logs to:

	data/logs/docs/

Each Python script has its own log file to help:
- Debug issues with documentation builds or asset copying
- Review script actions and errors

Logging levels can be adjusted as needed.

If you encounter problems, please check relevant log files for details.


## Files and Directories Excluded from Version Control

Certain files and directories are intentionally excluded from the repository via `.gitignore` to keep the project clean and secure:

- `data/logs/` — All log files generated by scripts and modules (can be large and environment-specific)
- `data/io/llm/*/prompt_response_cache.pkl` — LLM response cache files
- `data/api_key.csv` — API keys (never commit secrets)