# CAG to GABM Refactor Plan

**Status:** network integration and offline cursor restoration merged into
CAG main; generic network follow-up tests merged. Survey-execution extraction
is merged in both repositories. GABM 0.5.0 is published; CAG dependency pins
are updated and published-wheel acceptance passes.

## Resume here: checkpoint (2026-11-10)

- **CAG baseline:** `main` at `a731626`, synchronized after PR #114.
  Survey execution, the published GABM dependency update, the population
  factory, and survey-ingestion reliability work are all merged. No outstanding
  feature branch is needed to continue.
- **GABM baseline:** the two-stage executor and string-contract guards are
  merged into main and published as **0.5.0**. CAG runtime, development, and
  Conda manifests all pin `gabm==0.5.0`. No new GABM release is needed for
  the next CAG-only slice.
- **Latest validation:** installed both runtime and development requirements
  from scratch in `/tmp/cag-clean-install`; full CAG suite: **792 passed,
  1 skipped, 6 existing warnings, 50 subtests**. The clean environment uses
  the published GABM 0.5.0 dependency and its own `site-packages`, with no
  local GABM source override. The original integration golden fixture remains
  unchanged. The temporary environment has been removed.
- **Latest completed slice:** survey-ingestion reliability was merged in
  `7379b9f` (PR #112). Custom `required_columns` must include all mandatory
  eligibility-filter fields; filter failures return a logged load failure;
  CLI load errors and insufficient eligible counts are reported before
  sampling. Full validation against published GABM 0.5.0: **792 passed,
  1 skipped, 6 existing warnings, 50 subtests**. Successful filter predicates
  and seeded sampling remain unchanged.
- **Next priority:** continue tidying CAG and, where a clear reusable
  capability exists, increase its use of GABM without changing research
  behaviour. No real second consumer currently needs the same survey
  population reconstruction. Survey-to-population construction may be a
  common framework need, but keep the current row-to-citizen mapping CAG-local
  until the generic responsibilities and extension points are clear. A
  sensible future GABM layer could own neutral ordered-record iteration and
  factory/registration mechanics while callers own survey schema, filtering,
  sampling, and domain-specific conversion. Validate that boundary with
  another credible consumer or a clearly specified neutral API contract before
  implementing it; do not create an artificial consumer just to justify
  abstraction. Duplicate-ID and strict numeric validation policies remain
  separate decisions.
- **Latest cleanup:** survey region, education, and income ID isolation was
  merged as `5e22571` (PR #113). Full validation: **797 passed, 1 skipped,
  6 existing warnings, 50 subtests**; original golden fixture unchanged.
- **Latest memory extraction:** daily compression input formatting was merged
  as `a731626` (PR #114), including characterization commit `9226331`.
  Full validation: **808 passed, 1 skipped, 6 existing warnings, 50 subtests**.
- **Active review:** `refactor/context-rendering-review` adds exact-output
  context characterization tests and review findings only. Focused context/
  memory/config/golden suite: **109 passed**. No runtime changes or new GABM
  API are introduced.

On resuming, check `git status --short --branch` in both repositories before
changing anything. The `cag-integration` environment may use editable GABM;
verify import origin rather than treating its results as published-wheel
acceptance. Normal CAG tests use `PYTHONPATH=src:scripts python -m pytest -q`
with published GABM 0.5.0 installed. See
[the development workflow](DEV_GUIDE.md#cross-repository-refactoring).
Leave the unrelated tracked deletions under GABM's `venv-build-test/`
untouched.

The dated sections below retain historical development checkpoints; their
then-pending merge/release statements are superseded by this checkpoint.

### Context-section rendering review (2026-11-10)

Reviewed `assemble_context` and the seven section renderers against existing
memory/configuration tests. Added `tests/test_context_rendering.py` with exact
whole-context assertions, stage-override and non-mutation checks, package
anchor ordering, and the empty-persona separator contract.

Important details for any subsequent extraction:

- Assembly order is persona, anchor, summaries, reflections, own reasoning,
  optional trajectory, today-so-far. `MEMORY_SECTIONS` lists the last two in
  a different order; do not use that tuple to silently reorder the prompt.
- Persona text is appended even when empty. Other empty sections are omitted.
  An enabled empty persona can therefore produce a leading double newline.
- Package context selects package-scoped summaries/reflections, not all policy
  entries. This differs deliberately from package compression input, which
  gathers all same-day reflections. `None` context scope includes all scopes.
- Anchor and own-reasoning text is stripped; reflection and summary text is
  not. Section separators are exactly two newlines.
- Target anchor uses the first Day-0 entry; package anchors use canonical
  survey-question order. Reflections, own reasoning, and trajectory retain
  history order, not chronological sorting. Within-day answers use the last
  same-day numeric/reasoning entries and string-sorted policy keys.
- Trajectory includes history up to the requested day independently of the
  verbatim window. Stage overrides select sections without mutating global
  configuration. Preserve existing day/window/TTL boundaries.

Recommended next implementation: move only recent-reflection and recent-own-
reasoning filtering/rendering into pure CAG-local functions in the existing
`cag.abm.memory` module. Keep agent section methods as thin compatibility
wrappers. Leave assembly, stage resolution, anchors, trajectory, and within-day
answers untouched for this first rendering slice. These two renderers share
the existing verbatim-window helper but have different scope and whitespace
rules; do not force them through a configurable generic rendering engine.
The framework comparison from the prior review still applies: no equivalent
GABM episodic-memory renderer was found, and no GABM change is proposed.

Validation with published GABM 0.5.0 in `cag`: focused context/memory/config/
golden suite **109 passed**. No full-suite rerun is claimed for this
test/documentation-only slice. Runtime code and golden fixtures are unchanged.
Changes remain uncommitted for review.

### Agent memory/context boundary review (2026-11-10)

Reviewed `SurveyedCitizen.assemble_context`, its section renderers,
`compress_memories`, `compress_daily_memory`, `manage_memory`, the shared
memory configuration, and the simulation's end-of-day ordering.

Observed contracts to preserve:

- The simulation runs memory management after message phases and before
  end-of-day surveys. The compression target uses the global verbatim window;
  section inclusion uses stage-resolved configuration. Preserve this distinction.
- Context scope selects summaries/reflections; target policy selects Day-0
  rationale, own reasoning, trajectory, and within-day answers. Actual assembly
  places optional opinion trajectory before today-so-far, irrespective of the
  order of names in `MEMORY_SECTIONS`.
- Package compression keeps all same-day reflections in insertion order,
  then adds reasoning in policy-key string order (not canonical survey order).
  Duplicate same-day reasoning entries are retained. The package sentinel's
  own reasoning bucket is excluded.
- Compression sends exact CAG-owned system/user strings through `send_chat`,
  not the prompt-capturing `_chat` wrapper. Transport options pass through
  unchanged. Do not silently add logging records, retries, or normalization.
- Successful raw summaries are stored before allocating their event step.
  Transport failure leaves summary/step state unchanged; a failure allocating
  the step would occur after summary storage. No rollback is currently provided.
- No matching input returns an empty string without transport or recording.
  Existing summary keys prevent recompression even if their text is empty.
  `manage_memory` targets just the day leaving the window; it does not backfill
  skipped days or prune retained source histories.

GABM comparison: the inspected framework source contains agent demographic/
trait/opinion profiles and survey execution, but no equivalent tiered episodic
memory store, day-window scheduler, or compression pipeline. The LLM utilities
are transport/model-management utilities, not a memory abstraction. Replacing
CAG's pipeline with those APIs is not an equivalent reuse opportunity.

Added four tests to `tests/test_memory.py` for exact package compression
input/prompt/options/call order/raw-result/event recording, transport failure,
no-input behavior, and lack of skipped-day backfill. Existing tests already
cover context sections, scope, toggles, TTL, and bounded/unbounded windows.
Focused memory/config/golden suite with published GABM 0.5.0:
**105 passed**. No full-suite rerun is claimed for this test/documentation-only
review. Runtime files and golden fixtures are unchanged.

Recommended next implementation: extract pure selection/formatting of a day's
compression input into a CAG-local memory module, leaving existing agent
methods as compatibility entry points and retaining transport, summary state,
step recording, and simulation scheduling where they are. Add exact helper
tests and delegation checks, then rerun the golden baseline. Evaluate context
rendering separately rather than moving all memory responsibilities at once.
Do not introduce a generic workflow engine or GABM memory API at this stage.
Notebook modernization remains deferred for collaborator discussion.

#### Daily compression input extraction (2026-11-10)

After committing characterization as `9226331`, extracted
`build_daily_memory_input` into `src/cag/abm/memory.py`. It takes reflections,
survey reasoning, day, and policy scope, returning the exact compression input
without mutating histories or making transport calls. The agent's existing
`compress_daily_memory` entry point delegates selection/formatting only.
Transport, prompt template, summary storage, event-step allocation, and
`manage_memory` scheduling remain unchanged.

Direct tests cover package/single-policy scope, exact text, duplicate entries,
whitespace, source non-mutation, unknown-policy labels, empty histories, and
reflections-only/reasoning-only inputs. A delegation test checks the original
history objects and transport options. Existing characterization and golden
tests remain unchanged. Focused helper/memory/config/golden suite:
**112 passed**. Pylance reports no diagnostics in the new helper module.
Full suite against published GABM 0.5.0 in `cag`: **808 passed, 1 skipped,
6 existing warnings, 50 subtests**. The original golden fixture is unchanged.
Implementation remains uncommitted for review.

### Survey codebook isolation (2026-11-10)

The bounded attribute-map review found that CAG imported GABM's generic
`RegionID`, `EducationID`, and `IncomeID` classes and assigned survey constants
directly onto those shared classes. Region names overlapped with different
codes: importing CAG changed generic `RegionID.NORTH_WEST` from 1 to 2,
and could change subsequent generic map construction in the same process.
The map machinery itself was already reused appropriately; no new generic
GABM helper or framework release is needed.

With the user's approval, these three survey ID classes now derive directly
from GABM's `GABMAttributeID`, following CAG's existing family/politics pattern.
Attribute objects and `GABMAttributeMap` continue to come from GABM. Survey
codes, descriptions, entry order, ID string representations, and constructor
keyword names are retained. The intentional compatibility change is that
generic GABM IDs are no longer survey IDs: callers must import the latter
from `cag.abm.attributes.region`, `.education`, and `.income`. Updated the
affected tests, imports in three notebooks, quickstart, and code tour.

Before editing the maps, captured fingerprints of their complete ordered
code/description entries. New tests assert those exact fingerprints,
cross-codebook inequality and lookup separation, and generic-map/constants
preservation in fresh processes for both import orders. Focused
codebook/agent/persona/population/golden suite: **73 passed, 2 subtests**.
Full suite with published GABM 0.5.0 in `cag`: **797 passed, 1 skipped,
6 existing warnings, 50 subtests**. The original golden fixture is unchanged.
No GABM source files were modified.

Notebook follow-up is deferred for discussion with collaborators. Manual
execution of the agent-profile notebook exposed a pre-existing call to the
removed `get_narrative()` method. Its display cell now prints the combined
`get_persona()` once; this cell was executed with five synthetic citizens,
without LLM calls. The notebook's saved 1086-row output is historical:
current and pre-ingestion-change loaders both return identical 1483-row
dataframes for the current local survey file. Full notebook execution has
not been validated; no live external LLM calls were made for this review.
Do not treat historical notebook outputs as acceptance criteria or broaden
this PR into notebook modernization. Keep manual execution outputs separate
from the intended source changes when preparing the commit.

### Survey-ingestion reliability follow-up (2026-11-10)

Implemented on `fix/survey-ingestion-reliability`:

- Custom `required_columns` must include education, ethnicity, and referendum
  fields used by the mandatory eligibility filters. The loader reports missing
  filter columns and returns `None`; it does not silently disable filters or
  append hidden columns.
- Filter exceptions are logged with traceback and return `None`, avoiding the
  prior path that could reference unassigned `df4`.
- The CLI checks for usable loaded data before sampling and exits with an
  explicit error. If the eligible population is smaller than requested, the
  error reports both counts. Sufficient populations retain the exact pandas
  seeded sampling operation and reset-index behavior.
- Synthetic tests cover the chosen custom-column contract, filter failures,
  load failure, insufficient counts, and unchanged successful sample order.

At the start of this slice, the existing `cag` environment still had GABM
0.4.0 and could not import the merged survey executor. Initial validation used
a temporary environment with published GABM 0.5.0: focused population/CLI/
golden suite **69 passed**; full suite **792 passed, 1 skipped, 6 warnings,
50 subtests**. The `cag` environment has since been upgraded to GABM 0.5.0;
its package import was verified from the environment's `site-packages`.
After upgrading, the full suite passed: **792 passed, 1 skipped, 6 warnings,
50 subtests**. The CLI load-failure message and assertion were included.
No golden fixture, sampling algorithm, or successful filter predicate
changed.

**Documentation ownership checkpoint (2026-11-08):** before generic extraction,
the Aire quickstart and primer were moved to `documentation/guides/`.
The five maintained usage/code/configuration guides were subsequently moved
to the same authored location. Their Sphinx pages retain the same names
through explicit staging mappings.
Nested-source link resolution and cleanup are covered by 19 documentation
tests; a fresh build after the maintained-guide slice succeeds with 339
remaining warnings (393 after Aire alone). The moves preserve guide content
except relocation-related links and one sentence clarifying link locations.
The design history, research notes, experiment report, and survey documentation
were subsequently moved to `documentation/research/`, retaining historical
content and page names. The combined migration now has 23 documentation tests;
full suite: 716 passed, 1 skipped, 2 expected failures, with the same 6 warnings.
A fresh build after research migration succeeds with 272 warnings, and all
eleven migrated pages, cross-links, and source-preserving cleanup were verified.
Independent developer `make docs` succeeded with 161 warnings; that separate
build count does not replace the fresh-build warning baseline.
Seven supplementary sources were subsequently moved: literature and policy
parameterisation drafts to `documentation/research/`, and historical guides,
Aire article notes, and issue-planning snapshots to `documentation/archive/`.
Their bodies are preserved except links, and original nested Sphinx page paths
are retained. A fresh build succeeds with 225 warnings; all eighteen authored
pages, cross-links, and source-preserving cleanup were verified.
Combined migration validation: 29 documentation tests; full suite 722 passed,
1 skipped, 2 expected failures, with the same 6 warnings. Parallel building
and nested staged-copy cleanup also pass.
The HTML deck now lives in `documentation/presentations/` and publishes
verbatim as a standalone page; the authored index is `documentation/README.md`.
Both dependency mirrors are now generated from root manifests and cleaned
after building. Content consolidation and remaining tracked API stub ownership
are separate follow-ups. See the ownership conventions in
[DEV_GUIDE.md](DEV_GUIDE.md#authored-sources-and-sphinx-staging).

Final ownership validation: fresh Sphinx build succeeds with 221 warnings;
full suite 722 passed, 1 skipped, 2 expected failures, same 6 warnings.
Published presentation bytes match the original exactly, the documentation
index renders, dependency mirrors match their root manifests, and cleanup
preserves authored sources. Remaining warnings are not suppressed.

**Aire content checkpoint (2026-11-08):** the quickstart is now the maintained
setup/submission recipe, and the primer is a concrete CAG launcher reference
with cited Leeds guidance and explicit verification limits. Duplicated flag
tables now defer to the configuration guide and CLI. Output day/row counts,
dynamic ports, startup limits, scratch logs, sweep parsing, credential handling,
and account-access assumptions were corrected against local sources/public
documentation. The older article retains its body and credits below a
historical-use warning; its distinct distributed-inference/socket/cache/flash/
energy topics remain follow-ups. No launcher behaviour changed.
Local documentation/CLI tests pass; a scheduled cluster smoke job, compatible
cached image/model, data approval, and service-binding/access advice are still
deployment gates. This is not fresh evidence of checkpoint replay equivalence.

**Audit date:** 2026-11-09.

## Purpose

Move reusable capabilities from Climate-Action-GABM (CAG) into the GABM
framework, then make CAG a thinner consumer of those capabilities. This is a
two-repository refactor, not just a dependency upgrade or a replacement of CAG
with GABM's chat examples.

Preserve CAG's research behaviour while improving framework reuse. Intentional
behaviour changes require a separate decision, explicit documentation, and
appropriate tests; they must not be hidden inside an extraction.

This document is the maintained implementation reference. The
[roadmap](ROADMAP.md) records the strategic goal, and the
[developer guide](DEV_GUIDE.md) links contributors here. For current model
behaviour, consult the [configuration guide](documentation/guides/Simulation_Configuration_Guide.md),
[code tour](documentation/guides/Code_Tour.md), and source code. The
[model design log](documentation/research/Model_Design.md) contains historical decisions and is not an
authoritative current specification.

## Verified starting point

The audit used published PyPI packages in an isolated Python 3.12 environment,
not the adjacent GABM source checkout.

| Check | Published GABM 0.2.18 | Published GABM 0.3.0 |
|---|---|---|
| Unchanged CAG full test suite | 680 passed, 1 skipped; 23 subtests passed; 6 warnings | Blocked by 9 collection errors |
| `python -m cag --preset smoke --dry-run` | Passed | Failed on the missing `politics` import |

Commands, with the isolated environment activated:

```bash
PYTHONPATH=src:scripts MPLBACKEND=Agg python -m pytest -q
PYTHONPATH=src python -m cag --preset smoke --dry-run
```

These are dated audit results, not a permanently current test count. A dry-run
only previews configuration: it is not an executed simulation or evidence of
pre/post output equivalence. The existing suite is valuable, but several
simulation and checkpoint tests mock the nation and agent internals.

Known compatibility breaks:

- GABM 0.3.0 has no `gabm.abm.attributes.politics`, `ethnicity`, or `family`
  modules. CAG source, tests, and 27 notebooks contain affected imports.
- The published `Nation` constructor accepts `name` rather than `place`, and
  no longer accepts `ethnicity_map`.
- CAG's runtime, development, and Conda manifests still pin `gabm==0.2.18`.

No CAG runtime code or dependency pins were changed during the audit.

## Ownership boundaries

Extract mechanisms, not entire domain-bearing modules. Reuse existing GABM
APIs before adding new ones; keep a new API small and supported by a concrete
CAG use case.

| Capability | Generic responsibility in GABM | Responsibility retained in CAG |
|---|---|---|
| Attributes | Identifiers, attribute objects, and maps | YouGov categories, coding, and descriptions |
| Networks | Seeded graph builders and structural diagnostics | Political-exposure grouping, affinity rules, and research defaults |
| LLM access | Transport, request options, retries, response metadata, and explicit cache controls | Climate prompts, debiasing, and survey-answer interpretation |
| Memory | Reusable event storage, retention, and summarisation mechanisms | Context wording, policy scopes, anchors, and research presets |
| Checkpoints | Reusable persistence and compatibility mechanisms | CAG state schema, state hydration, and resume rules |
| Experiments | Seed sweeps, provenance, and comparison utilities | Climate outcomes, calibration, and scientific analyses |

Networks, LLM access, memory, checkpoints, and experiments are extraction
candidates, not commitments to build a general abstraction for every row.
In particular:

- [Network code](src/cag/abm/networks.py) mixes generic graph algorithms
  with political-exposure grouping.
- [Memory configuration](src/cag/abm/config/memory.py) mixes retention
  mechanics with the survey design.
- [LLM access](src/cag/io/llm.py) returns text from system/user prompts.
  GABM's existing LLM service contract returns response objects and enables
  caching by default. Direct substitution could change prompts, calls, or
  failures and needs a deliberate adapter.

Do not introduce GABM-generated traits, names, values, or age sampling into
survey-grounded CAG citizens as an incidental consequence of inheritance.
Do not replace the CAG daily phase loop with a generic chat example.

## Sequence and acceptance gates

### 1. Establish a golden integration fixture

Before runtime edits, execute a small seeded scenario with real CAG citizens
and a real `SurveyedNation`, mocking only LLM transport and external services
as needed. Record the input data, complete configuration, dependency versions,
and deterministic response strategy.

Capture personas and exact prompts, agent IDs, graph nodes and edges, exposure
and reach assignments, ordered messages and reflections, surveys, memory, and
saved outputs. Include package-mode communication and peer exchange; cover
single-policy behaviour and checkpoint/resume in companion checks.

**Gate:** the fixture repeats exactly against 0.2.18 and provides reusable
pre/post comparison evidence. Keep synthetic fixtures in tests; do not commit
credentials, private survey records, or large generated run directories.

#### Baseline implementation and evidence (2026-11-08)

[tests/test_integration_baseline.py](tests/test_integration_baseline.py) now runs
eight real synthetic citizens in a real nation for three days, in both
six-policy package mode and single-policy carbon-tax mode. The scenarios use
the real offline political-message set, all four exposure buckets, asymmetric
reach, peer exchange, seeded stochastic-block graph generation and connectivity
repair, ground-truth Day-0 rationale, two-step surveys, and Day-1 memory
compression on Day 3. Citizen/nation logic is not mocked.

The versioned reference is
[data/fixtures/cag_integration_baseline.json](data/fixtures/cag_integration_baseline.json).
It records dependency provenance, the complete serialized configurations,
explicit graph snapshots and diagnostics, per-table row counts and SHA-256
fingerprints, ordered transport-request fingerprints, agent-state fingerprints,
and final saved-file manifests and fingerprints. Table fingerprints include
CSV headers, row order, values, and exact text. Large prompt/run outputs are
created only in temporary test directories. This tests CSV/JSON output, not
plot image equivalence.

Only LLM transport, local-server setup/health checks, and the persona clock are
replaced. Responses are deterministic functions of exact prompts and request
options, rather than a constant answer or an invocation counter. The persona
date is fixed to 2026-11-08; Python's process-wide random state is seeded and
restored around each scenario. Elapsed diagnostic time and the timestamped
output-directory name are excluded. Political-exposure assortativity is rounded
to 12 decimal places to remove sub-picounit categorical reduction-order noise
across Python hash seeds; no other compared numerical or text fields are
normalized.

Run in an environment installed from the pinned runtime requirements:

```bash
PYTHONPATH=src:scripts MPLBACKEND=Agg python -m pytest -q tests/test_integration_baseline.py
PYTHONPATH=src:scripts MPLBACKEND=Agg python -m pytest -q
```

Validation against published GABM 0.2.18:

- Targeted tests: **6 passed, 2 expected failures**, independently verified
  with `PYTHONHASHSEED=0` and `PYTHONHASHSEED=17`.
- Full suite: **686 passed, 1 skipped, 2 expected failures**, 23 subtests passed,
  and the same 6 warnings observed in the initial full baseline.
- Independent developer validation (2026-11-08): `make test` in the `cag`
  Conda environment, Python 3.12.12 and pytest 9.0.2, reported **686 passed,
  1 skipped, 2 expected failures, 6 warnings** in 11.43 seconds. This matches
  the isolated-environment result; the supplied output did not report the
  installed GABM version.
- Repeated fresh scenarios match the fixed reference, not just each other:
  package mode has 192 opinion rows and 406 transport calls; single-policy
  mode has 32 opinion rows and 126 transport calls. Both have 51 message rows
  and 8 daily summaries.

#### Characterized checkpoint limitations

Completed-checkpoint hydration restores the core citizen state, event counter,
graph, and core CSV serialization, and repeated hydration is idempotent.
However, existing behaviour is not full fresh-process replay:

- Full prompt logs are final-output-only and are not hydrated.
- CSV hydration stringifies mixed sender IDs; their CSV text remains equal,
  but timeline JSON metadata changes type. Separate fixed timeline fingerprints
  characterize the restored output rather than concealing that difference.
- Peer selection uses process-wide Python random state, which the checkpoint
  does not save. The passing continuation tests explicitly preserve that state
  outside the checkpoint and use stateless mocked LLM political broadcasts.
- At the original baseline, offline message-pool cursors were not restored:
  resumed broadcasts restarted their rotation. This was fixed in the separate
  offline checkpoint slice below on 2026-11-09; both expected-failure markers
  have been removed.

No runtime fixes or dependency upgrades are part of this checkpoint. Address
resume reproducibility in a separate, explicitly tested slice before claiming
uninterrupted-versus-resumed equivalence for production offline runs.
Do not refresh golden fingerprints merely to make a refactor pass: inspect the
changed surface, compare actual temporary outputs, and obtain a separate
decision for any intentional behaviour change.

### 2. Resolve published 0.3.0 compatibility

- Define CAG survey attribute types using GABM's generic attribute primitives,
  preserving existing ID ordinals, labels, lookups, and serialization.
- Update imports across source, tests, and affected notebook code cells.
- Adapt the `SurveyedNation` constructor, retaining its public CAG arguments
  and explicitly storing the CAG ethnicity map.
- Update [runtime requirements](requirements.txt),
  [development requirements](requirements-dev.txt),
  [Conda environment](environment.yaml), and directly related docs together.

**Gate:** the existing suite, CLI smoke dry-run, and golden comparisons pass
against the published 0.3.0 wheel. Do not leave a version-only upgrade that
cannot import or run.

#### Compatibility implementation and evidence (2026-11-08)

Runtime, development, and Conda manifests now pin `gabm==0.3.0`.
[Politics](src/cag/abm/attributes/politics.py),
[ethnicity](src/cag/abm/attributes/ethnicity.py), and
[family](src/cag/abm/attributes/family.py) identifiers and attribute objects
are CAG-owned subclasses of GABM's generic attribute primitives. Their class
names, constructor keyword names, ID ordinals, descriptions, equality/hash
semantics, and string representations are retained. Existing survey mappings
and persona text are unchanged; no new framework API or GABM source edit was
needed.

Source/test consumers and the affected sandbox script now import these types
from `cag.abm.attributes`. Code-cell imports in 27 notebooks were updated;
all other notebook content, including historical outputs and metadata, was
verified unchanged. Old `gabm.abm.attributes.politics`, `ethnicity`, and `family`
imports are no longer supported by this application.

`SurveyedNation` passes its historical `place` argument to GABM's `name`
parameter. The public `place` property is a read/write alias for `name`.
Explicitly supplied ethnicity, politics, and family maps are preserved.
When `ethnicity_map` is omitted, CAG now constructs `SurveyEthnicityMap`
instead of the removed framework's generic ethnicity map. This is an explicit
default-map alignment with the CAG survey vocabulary; it is covered by a
contract test and does not affect the fully mapped golden scenarios.

Validation used the published PyPI wheel in the isolated test environment:

- Full suite: **693 passed, 1 skipped, 2 expected failures**, 23 subtests passed,
  and the same 6 existing warnings.
- Independent developer validation (2026-11-08): installation succeeded in the
  `cag` environment; `make test` reported **693 passed, 1 skipped, 2 expected
  failures, 6 warnings in 11.95s**, matching the isolated-environment result.
- [Compatibility contracts](tests/test_gabm_compatibility.py) and integration
  baseline together: **13 passed, 2 expected failures**.
- Package and single-policy scenarios match the original 0.2.18 golden
  reference without refreshing any fingerprints, including a run with
  `PYTHONHASHSEED=17`.
- Canonical CLI smoke dry-run succeeds; `pip check` reports no broken
  requirements.
- All 38 source/test GABM import statements resolve against the installed
  wheel; notebook migration was checked structurally without executing their
  live research runs.

This is compatibility work only. Existing checkpoint limitations and expected
failures are unchanged. The next planned slice is generic network extraction.
Independent developer documentation build (2026-11-08): `make docs` completed
and generated HTML, but reported **752 warnings**. The supplied log tail
includes unresolved source-file links and a Python highlighting error in the
historical code tour. The full warning set has not yet been classified, so
this is a successful build, not a warning-clean documentation validation.
The bounded staging follow-up separated the copied project README from the
authored documentation index, enabled section anchors, rewrote root-document
links during staging, and included the root user/developer guides in the
existing navigation. Cleanup is ordered after building, including parallel
Make invocations. Existing autosummary stubs are no longer overwritten.

A final fresh Sphinx rebuild after these changes succeeded with **397 warnings**
instead of 752. No warnings remain for this plan, the roadmap, or the developer
quickstart; the change log's remaining links refer to historical experiment
output paths. Other legacy source links, API duplication/docstring formatting,
unlisted documents, and historical highlighting failures remain follow-up work.
These warnings are not globally suppressed. The authored documentation index
and existing tracked autosummary stub were restored after the first build and
verified unchanged by the subsequent build. Staging/cleanup regression tests
are in [tests/test_docs.py](tests/test_docs.py).
Default pytest discovery now targets `tests/`, preventing the HTML build's
downloaded test examples from being collected as duplicate application tests.
Two repeated `make -j2 docs` runs verified build/cleanup ordering and preserved
the authored index and tracked stubs. Rendered HTML was checked for the three
CAG-owned attribute types and the rewritten regression-test link. Full suite
after documentation generation: **703 passed, 1 skipped, 2 expected failures**,
23 subtests passed, with the same 6 existing warnings; the 10 additional passes
are the staging/cleanup regression tests.

### 3. Extract seeded networks and diagnostics first

Move a bounded set of generic graph builders and diagnostics into GABM.
CAG supplies agent IDs, its block membership or similarity inputs, and its
research defaults. Preserve node ordering, random-number usage, edge results,
diagnostic output, and existing connectivity-repair behaviour.

**Gate:** GABM tests exercise the generic API independently of CAG, while CAG
tests and golden comparisons demonstrate unchanged graphs and downstream
behaviour through the new API.

#### Implementation and evidence (2026-11-09)

`gabm.abm.networks` now owns the seeded graph builders, structural diagnostics,
and deterministic component repair. Its API accepts caller-owned node IDs,
block membership/order, and similarity feature rows; it does not select or
interpret CAG attributes. GABM declares the NumPy and NetworkX runtime
dependencies, includes independent API tests, and documents the module in its
developer guide and API navigation.

CAG retains political-exposure-to-block assignment, survey homophily fields,
small-population defaults, network metadata, and result serialization. Its
existing `cag.abm.networks` signatures now adapt those inputs to the generic
API, while `network_repair` delegates graph repair. The adapter explicitly
retains both SBM blocks, including an empty block, so seeded NetworkX draws
remain unchanged for one-sided populations.

Validation on 2026-11-09:

- GABM network API tests: **11 passed**.
- GABM full default suite: **210 passed, 10 deselected**.
- CAG network tests: **32 passed, 17 subtests**.
- CAG full suite: **744 passed, 1 skipped, 2 xfailed, 6 warnings, 30
  subtests**. The committed golden fixture was not refreshed and its graph,
  state, transport, and output fingerprints pass.
- Compared the prior CAG implementation with the adapter for all five network
  types, diagnostics (excluding elapsed time), and seeded component repair;
  node order, edges, and diagnostic values matched. Added graph
  fingerprints now cover exact node order and edges for every builder, and the
  repair test asserts the exact seeded bridging edges.
- A GABM 0.3.0 wheel built successfully and contains
  `gabm/abm/networks.py`.
- `make docs` succeeds and renders the new API module; it reports 77 warnings.
  Generated dependency mirrors and autosummary stubs are build outputs, not
  authored changes.

Merge follow-up on 2026-11-09: GABM main at `c62c060` contains the generic
network branch and the documentation follow-up. The merged network API tests
pass (**11 passed**), and CAG's network and golden integration baseline tests
pass against that main checkout (**38 passed, 2 xfailed, 17 subtests**).
Validation used the `gabm` and `cag` Conda environments respectively, with
GABM's source directory on `PYTHONPATH`.

Published-package follow-up on 2026-11-09: PyPI provides GABM **0.4.0** as a
wheel and source distribution. Runtime, development, and Conda manifests now
pin `gabm==0.4.0`, and the development/Aire setup guides reflect that version.
The downloaded PyPI wheel was installed in an isolated virtual environment
using the `cag` Conda environment's existing scientific/test dependencies
(`--system-site-packages`); the Conda environment itself was not modified.
The imported network module was verified to come from that installed wheel.
With only CAG's `src:scripts` on `PYTHONPATH` (no GABM source override), the
full suite passed: **744 passed, 1 skipped, 2 xfailed, 6 warnings, 30 subtests**.
The retained golden reference and exact seeded graph fingerprints pass.
CAG's adapter and dependency changes are committed as `73fc9a7` on
`refactor/gabm-network-consumer`; the published-package acceptance gate is
satisfied and merge remains pending.

#### Network follow-up (2026-11-09)

CAG retains explicit NetworkX requirements because its environment, plotting,
analysis, and integration tests still use NetworkX directly. GABM owns the
reusable algorithms, not every use of the graph library.

GABM's generic test suite now additionally covers similarity groups, missing
features, default weights, exact diagnostic metrics and largest-component
behaviour, disabled timeouts, the installed POSIX alarm handler and cleanup,
size-cap boundaries, and exact seeded repair bridges. These tests use neutral
nodes/features rather than CAG survey attributes. Focused API suite:
**23 passed** in the `gabm` environment. No framework implementation changed.

`scripts/estimate_connectivity_threshold.py` now uses GABM's builder with
explicit two-block membership/order. CAG retains the research sweep and
outputs. A main guard prevents import-time computation/output; the unnecessary
global NumPy reseed was removed because graph generation uses an explicit
seed. Regression tests compare exact nodes/edges for odd, even, and single-node
populations across three seeds, compare trial connectivity rates, and exercise
CSV/PNG generation in a reduced sweep. Analysis, network, and golden-baseline
tests against installed PyPI GABM 0.4.0: **56 passed, 2 xfailed, 17 subtests**
using `PYTHONPATH=src:scripts` in `cag`. Existing CAG adapter/integration tests
remain in place to guard application behaviour. CAG's analysis follow-up is
included in `73fc9a7`; GABM's test-only follow-up is committed as `6dd5168` on
`test/network-regressions`. These do not imply a CAG merge or another GABM release.

#### Offline checkpoint correctness slice (2026-11-09)

Running both offline continuation cases with `--runxfail` confirmed divergence
in the resumed request sequence. Checkpoints now include JSON-safe per-cell
rotation state with the message-set ID, seed, state version, and a fingerprint
of ordered message records. Resume validates content, complete cell coverage,
and integer cursor bounds before changing the pool. State validation is atomic:
invalid input leaves existing cursors unchanged.

The approved legacy policy rejects offline checkpoints missing rotation state
with a clear fresh-run error. LLM-only checkpoints do not require that field.
Checkpoint schema version 1 remains readable for state hydration and LLM
resumes; the offline runtime enforces its additional state requirement.

Both offline continuation equivalence cases now pass without `xfail`, for
package and single-policy modes. Added tests cover JSON roundtrips,
wraparound, repeated restoration, content/identity mismatch, malformed cursors,
and the legacy offline/LLM compatibility policy. Focused pool, checkpoint,
and integration suite: **49 passed, 18 subtests**. Full CAG suite against
installed PyPI GABM 0.4.0: **769 passed, 1 skipped, 6 warnings, 48 subtests**,
with no expected failures. The original golden fixture is unchanged.

Python random state is still manually preserved in the continuation tests;
its persistence and prompt-log/timeline hydration remain out of scope.
This fix does not establish exact fresh-process replay. The fix is committed
as `9119488` on `refactor/gabm-network-consumer`; merge remains pending.

### 4. Adapt LLM transport, then evaluate memory extraction

Inventory and reuse GABM's existing services before moving CAG transport code
upstream. Explicitly preserve system/user message roles, generation options,
local endpoint support, model-specific options, timeout and retry behaviour,
error propagation, and cache policy. Keep survey parsing in CAG.

Only then identify the smallest reusable memory boundary. Preserve context
section order and exact text, retention/compression timing, policy-versus-
question scope, and checkpoint state.

**Gate:** transport tests verify request shapes and failure paths; integration
comparisons verify prompts, call order, memory, and outputs. Any intentional
difference is separately approved and tested.

#### Survey-execution boundary review (2026-11-09)

Reviewed CAG main `17111e3` and GABM main `fab60b9`. The network and offline
cursor changes are merged; GABM's expanded network tests are also merged.
The initial review changed documentation only. The API below was subsequently
implemented in the local feature-branch follow-up; it is not yet published.

**Scope adjustment:** use survey execution as the next concrete reuse case.
It can initially accept an injected chat callable backed by CAG's existing
transport. This does not migrate transport or establish provider parity.
Compare and adapt GABM transport separately before replacing CAG's provider
implementations; memory extraction remains later work.

##### Observed call flow and ownership

The reference path is
`sim._run_baseline_surveys` or `SurveyedNation.run_end_of_day_survey` ->
`SurveyedCitizen.administer_survey` -> `_chat` -> `cag.io.llm.send_chat`.
Day-0 ground-truth and ground-truth-with-rationale paths are separate and must
remain unchanged.

For each question, `administer_survey` currently:

1. Selects memory context using `context_policy_id`, while retaining the
   question's `policy_id` as the target for anchors/reasoning.
2. Builds and records the exact system context, consuming an event step.
3. Formats the anti-sycophancy reasoning prompt and calls `_chat`.
4. Stores reasoning and consumes another event step **before** the answer call.
5. Appends reasoning to the system context using the existing exact separator,
   formats the answer prompt/options, and calls `_chat` again.
6. Stores raw answer text and its event step, parses/scales the answer, and
   appends opinion history.

`_chat` records sampled-agent prompt/response pairs immediately after successful
transport calls. `send_chat` owns provider dispatch, request roles/options,
local configuration/model defaults, and resilient request handling.
The environment owns agent iteration, previous-versus-current opinion shifts,
and survey scheduling. These responsibilities are not one generic operation.

| Responsibility | Proposed owner |
|---|---|
| Execute reasoning then answer, passing exact strings through a supplied chat callable | GABM |
| Return the two raw response strings in a typed result | GABM |
| Question text, anti-sycophancy instructions, response options, and reasoning-to-context formatting | CAG supplies these inputs |
| Policy/package context selection and context-history recording | CAG |
| Stage/day/phase/policy metadata, prompt logging, and event-step allocation | CAG |
| Parsing A-G responses, numeric scale, opinion history, and output/checkpoint schemas | CAG |
| Provider SDKs, retries, local-server options, error and cache policy | Existing CAG transport initially; separate GABM parity review |

##### Existing GABM facilities and gaps

- [`gabm.abm.survey`](../GABM/src/gabm/abm/survey.py) already provides `Answer`,
  `Question`, `Survey`, and `SurveyConversation`. Extend this module additively
  rather than introduce a second survey subsystem or replace existing APIs.
- `Question.get_prompt()` supplies its own prose. CAG must not use that formatter
  for this slice because it would change research prompts.
- `SurveyConversation.conduct()` reads `person.profile`, concatenates that with
  question text, and calls `send` with a single context argument plus keywords.
  It does not implement CAG's separate system/user prompts, two-stage protocol,
  parsing, or intermediate recording.
- `SurveyConversation.__init__` assumes service methods `get_api_key` and
  `get_default_model`, which the `LLMService` base does not define.
  `_build_context` refers to `self.person_profile`, `question.options`, and
  `question.metadata`, which the inspected constructors do not establish.
  These are compatibility gaps to characterize separately, not silently fix
  while extracting CAG behaviour.
- [`LLMService.send`](../GABM/src/gabm/io/llm/llm_service.py) takes
  `(api_key, message, model, request_options)`, rather than CAG's chat signature.
  Its error helper can return error dictionaries. The inspected OpenAI service
  builds a user-role message, enables shared response caching by default through
  the base class, and returns provider/cache results. Direct substitution is not
  demonstrated to preserve CAG's roles, text return type, errors, or cache policy.
- No survey-named Python test files were found under GABM's test directory.
  This is not evidence that no indirect coverage exists; add focused independent
  tests for the proposed API.

##### Proposed first implementation slice

Add a small opt-in two-stage question executor in `gabm.abm.survey`.
Illustrative contract (names to be confirmed during implementation):

```python
@dataclass(frozen=True)
class TwoStageSurveyResult:
    reasoning: str
    answer: str

def execute_two_stage_question(
    *,
    system_prompt: str,
    reasoning_prompt: str,
    answer_prompt: str,
    send: Callable[[str, str, str], str],
    build_answer_system: Callable[[str, str], str],
    on_reasoning: Callable[[str], None],
) -> TwoStageSurveyResult:
    ...
```

`send(system, user, stage)` uses neutral stage names `reasoning` and `answer`;
CAG's closure translates them to its existing audit stages and delegates to
`self._chat` with unchanged model/provider/options and day/phase/policy metadata.
`build_answer_system(system, reasoning)` is supplied by CAG so the framework
does not embed policy wording or assume a particular prompt separator.
`on_reasoning(reasoning)` runs immediately after the first successful call and
before constructing/sending the answer; CAG uses it to append reasoning and
allocate the existing event step. It is necessary to preserve intermediate
state if the answer call fails, not a general-purpose plugin/event framework.
The executor must not catch transport/recording errors or turn them into
successful-looking survey results.

The resulting CAG flow is:

1. Build/record context exactly as today.
2. Supply the existing prompt templates, chat closure, reasoning recorder,
   and answer-context formatter to the GABM executor.
3. Record the returned raw answer, parse/score it, and append opinion history
   exactly as today. Retain the public method signature and return tuple.

This is deliberately an optional two-stage protocol, not the definition of all
GABM surveying. Do not force existing `SurveyConversation` users, one-stage
surveys, or ground-truth anchoring through it. Do not add a general workflow
engine, change agent inheritance/IDs, or move population loading in this slice.

##### Acceptance gates and implementation order

1. Add neutral mocked-chat tests in GABM for exact prompts/stages, call order,
   answer-context construction, intermediate callback order, and typed raw
   results. Cover errors in the first call, recorder, and second call:
   subsequent work must not run and errors must propagate.
2. Add/retain focused CAG checks for exact templates, package context versus
   target question, identical options on both calls, and audit/event ordering.
   Explicitly test second-call failure: context and reasoning remain recorded,
   but no answer/raw-response/history entry is fabricated.
3. Wire only `administer_survey` through the new API. Compare deterministic
   real-nation request/response sequences, state, CSV/output fingerprints, and
   checkpoint continuation in both modes. Keep the original golden fixture;
   do not regenerate it to accommodate differences.
4. Add a tiny neutral example/test with in-memory questions and mocked chat.
   No credentials, real respondent data, or live LLM is required.
5. Run focused suites, then the full CAG suite and relevant GABM suites.
   Build/test the new GABM wheel, release it, then update CAG's pin and repeat
   acceptance without a GABM source-path override.

**Later, separate slice:** trace CAG's `__main__.build_nation` and `io.survey`
to assess reusable respondent-to-agent mapping/validation against GABM's
existing population constructors. Preserve CAG codebooks, missing-data policy,
respondent IDs, row selection/order, and factory behaviour. Do not invent
sampling/weighting machinery without a demonstrated requirement.

##### Implementation and validation follow-up (2026-11-09)

Implemented the proposed `execute_two_stage_question` and immutable
`TwoStageSurveyResult` additively in GABM's existing survey module on
`feature/two-stage-survey`. CAG's `refactor/gabm-survey-consumer` delegates only
the two-call execution; context/prompt formatting, the intermediate reasoning
recorder, transport options, scoring, and histories remain application-owned.
Existing `SurveyConversation` and provider implementations were not changed.

GABM has six focused tests, including a neutral library-visitor example,
exact execution order/raw strings, result immutability, and propagation from
both calls, the recorder, and the answer-context formatter. New CAG tests
verify exact templates/options, package context versus target question,
prompt audit stages, event steps, and partial state after first/second-call
failure.

- GABM focused survey suite: **6 passed**.
- GABM full default suite: **228 passed, 10 deselected**.
- CAG agent, golden integration, and transport suites against local GABM
  source: **75 passed, 2 subtests**.
- Built a development wheel and installed it without dependency changes in
  an isolated virtual environment using the `cag` scientific/test stack.
  Verified that the survey module was imported from that installed wheel.
  CAG full suite with only `PYTHONPATH=src:scripts`: **771 passed, 1 skipped,
  6 warnings, 50 subtests**. The retained golden fixture was not changed.

At the initial implementation checkpoint, the development wheel still carried
version 0.4.0; it was **not** the published PyPI 0.4.0 artifact and was not
suitable for publication under that version. Published-wheel acceptance was
then pending. Subsequent commits: GABM `af446a1` on
`feature/two-stage-survey`, CAG `b49d711` on `refactor/gabm-survey-consumer`;
CAG developer workflow/documentation guidance is committed as `bf5b241`.

Published-package follow-up (2026-11-09): the executor and string-contract
guards are merged into GABM main, and the CAG adapter is merged into CAG main
`9100172`. PyPI now provides GABM **0.5.0**. Runtime, development, and Conda
manifests pin that version; no GABM source override is required.

Installed the published wheel in a temporary `--system-site-packages` virtual
environment over the existing `cag` scientific/test stack. Verified version
0.5.0 and the import location inside that environment's `site-packages`.
With only `PYTHONPATH=src:scripts`, the full CAG suite passes:
**771 passed, 1 skipped, 6 warnings, 50 subtests**. The original golden
fixture is unchanged. This validates the published GABM artifact against
the existing CAG stack, not a fully fresh resolution of all dependencies.
The temporary environment was removed after validation.

#### Survey-derived population review (2026-11-09)

**Review/test slice only:** branch `refactor/survey-population-review` is based
on CAG `bf5b241`, including the unreleased survey adapter. No runtime changes,
new framework API, dependency changes, or respondent data are introduced.
Synthetic characterization lives in
[`tests/test_survey_population.py`](tests/test_survey_population.py).

##### Existing path and observed contracts

1. [`io.survey.load`](src/cag/io/survey.py) reads CSV and selects an ordered
   application-owned column list. It drops a whole respondent if any selected
   value is missing, including outcome responses. It then tries to cast `ID`
   to integer, warning but retaining original values if conversion fails.
   Education `<=18`, ethnicity `<=5`, and referendum vote `<4` are literal
   filter predicates, not general codebook membership validation.
   Surviving row order and original DataFrame indices are retained; unrelated
   CSV columns are discarded. Missing files/columns and an empty retained
   dataset return `None` with logging where implemented.
2. [`__main__.main`](src/cag/__main__.py) samples with
   `data.sample(n=..., random_state=seed).reset_index(drop=True)`.
   Sampling is outside the loader and population constructor. Changing to
   another sampling algorithm or RNG would change respondent selection/order.
3. `build_nation` constructs a `SurveyedNation` with CAG maps and walks rows
   positionally with `iloc`, not by DataFrame index labels. Each citizen retains
   the original row as a pandas Series, including its name and outcome values.
   IDs come from that row without wrapping in a GABM agent-ID type; pandas
   row coercion can affect their scalar type even after the column was cast.
4. The builder owns field translation: year minus integer age; binary flags
   true only when their integer value is 1; typed codebook IDs; integer
   truncation before narrative rescaling (including the existing RWA 1-6 rule).
   Absent columns receive existing zero/default values, but present missing or
   malformed age values raise conversion errors if the loader is bypassed.
5. Registration is `nation.agents_active[citizen.id] = citizen`. Duplicate IDs
   replace the earlier citizen without moving the key's original position.
   An empty input creates an empty nation. Neither is an approved future
   validation policy merely because it is characterized here.

The new tests cover column selection, missing/out-of-codebook filtering,
survivor indices, logged ID-conversion failure, seeded selection order, mapped
agent attributes, original response retention, source-frame non-mutation,
default and malformed input paths, duplicate-ID replacement, score truncation,
and initial empty histories/neighbours. They use no real survey data.
Focused population, CLI, and golden-integration suites:
**61 passed**, using the `cag` environment with
`PYTHONPATH=src:scripts:../GABM/src` and GABM `af446a1`.
No full-suite rerun is claimed for this test/documentation-only slice.

##### GABM comparison and recommended next implementation

[`Environment.create_random_people`](../GABM/src/gabm/abm/environment.py)
generates `Person` objects, sequential wrapped IDs, sampled ages/genders,
and seeded traits/interests. It is not a respondent-driven constructor:
reusing it here would change IDs, persona state, and random draws.
[`GABMAttributeMap`](../GABM/src/gabm/abm/attribute.py) already provides typed
attribute lookup; CAG's `SurveyEducationMap` and related codebooks correctly
reuse it. Move neither the survey codes nor their descriptions into GABM.
The source search found no `read_csv`/row-iteration/record-factory equivalent
for surveyed populations in GABM; its survey module concerns asking questions,
not loading respondent populations.

**Recommendation:** first extract a CAG-local
`citizen_from_survey_row(row, *, environment, year)` in a focused population
module, leaving `build_nation` as a compatibility entry point and preserving
its nation/map construction and registration order. This removes field
translation from the CLI without immediately designing a mapping framework.
Tests above should pass unchanged; also compare exact factory arguments,
Series retention, personas, and the original deterministic simulation outputs.
Keep loading/filtering and sampling untouched in that implementation.

After that seam exists, evaluate a small additive GABM population function
using an ordered record iterable, caller-supplied record-to-agent factory,
and an environment registry. Any helper must earn its abstraction: prove
the same mechanism with a second neutral in-memory population and independent
tests before adding it. A helper that merely replaces a three-line loop
without useful validation or reuse is not sufficient. Avoid a declarative
converter/plugin system, new pandas runtime dependency, or mandatory agent
inheritance without demonstrated need.

| Mechanism | Ownership |
|---|---|
| CSV schema, codebooks, complete-case rules, respondent selection and sampling | CAG |
| Field conversion and survey-specific citizen construction | CAG row factory initially |
| Original outcomes, survey provenance and persona interpretation | CAG |
| Generic ordered factory/registration machinery, if justified by independent use | Candidate GABM API |
| Existing attribute-map base and environment registry | Reuse GABM as already done |

##### Decisions and defects to keep separate

Do not silently fix behaviour while relocating code. Duplicate-ID rejection,
missing/invalid ID policy, truncation versus strict numeric validation, and
loader defaults versus explicit schema validation need separate decisions.
The inspected loader also catches filter errors and can then reference
unassigned `df4`; custom `required_columns` still interacts with hard-coded
filter columns. The CLI calls `.sample` without handling the loader's `None`
result and relies on pandas for insufficient-population errors.
These are observed error-path gaps, not fixed or validated as desirable by
this slice; address them explicitly before advertising generic ingestion.
Population construction and survey execution are separate capabilities, even
when demonstrated by one eventual end-to-end example.

##### Row-factory implementation follow-up (2026-11-09)

Committed the characterization baseline as `b485dad`, then extracted
`citizen_from_survey_row(row, *, environment, year)` into
[`cag.abm.population`](src/cag/abm/population.py) on the same stacked
`refactor/survey-population-review` branch. `__main__.build_nation` retains its
public entry point, map construction, positional iteration and registration.
The factory retains the supplied Series without registering the citizen;
field conversions and all characterized defaults are unchanged.

Added direct row-identity/non-mutation/persona checks and a delegation-order
test. Original characterization tests remain unchanged. No ingestion error
policy, duplicate handling, sampling, or GABM runtime code changed.
Using `cag` with GABM `af446a1` on
`PYTHONPATH=src:scripts:../GABM/src`: focused population/CLI/golden suite
**63 passed**; full CAG suite **786 passed, 1 skipped, 6 warnings, 50 subtests**.
The original golden fixture is unchanged. The factory implementation is tracked
on this feature branch. Its survey-executor dependency is now supplied by
published GABM 0.5.0; population-branch published-wheel acceptance follows.

After merging main's dependency update into this branch, installed PyPI GABM
0.5.0 in a temporary virtual environment over the existing `cag` stack and
verified its `site-packages` import origin. With only `PYTHONPATH=src:scripts`,
the full population-branch suite passes: **786 passed, 1 skipped, 6 warnings,
50 subtests**. No GABM source override or golden-fixture change was needed.
The temporary environment was removed after validation. The population PR was
subsequently merged into CAG main as `6d2bbe3`; local main, upstream/main,
and origin/main were synchronized at the end-of-day checkpoint above.

The ingestion reliability PR was subsequently merged into CAG main as
`7379b9f` (PR #112); local main, upstream/main, and origin/main were
synchronized. See the current checkpoint at the top of this document.

### 5. Evaluate further extractions

Consider checkpoint infrastructure and experiment provenance/comparison helpers
after the earlier slices demonstrate a useful pattern. Retain CAG-specific
schemas and analysis. Do not generalise speculatively or relocate HPC scripts
merely to match a framework example.

## Two-repository development and release workflow

The maintained operational instructions are in
[Cross-Repository Refactoring](DEV_GUIDE.md#cross-repository-refactoring).
Use a fast integration loop and batch releases at coherent milestones; the
following gates do not require a separate release for every extraction.

1. Keep CAG as the active application workspace and GABM as the framework
   development/reference checkout. Use separate, focused changes in each.
2. For each extraction, document the API boundary and acceptance evidence.
   Add generic tests in GABM and keep domain/integration tests in CAG.
3. Test CAG against an isolated editable GABM checkout while developing new
   APIs. Record both commits and dirty state; use exact Git revisions for
   reproducible CI/collaborator integration. Apply these overrides separately
   from the incompatible published requirement.
4. Review small PRs independently; stable backward-compatible GABM additions
   can merge without immediate publication. Keep CAG code requiring unreleased
   APIs on integration branches. Validate built GABM wheels at milestones.
5. Batch related validated capabilities into a GABM release, then pin CAG to
   that published version and rerun the gates without source-path overrides.
   Merge dependent CAG changes only when declared dependencies supply the API.
   Editable/Git/local-wheel evidence is not published-package acceptance.
6. Update this plan's progress, the change log, and affected usage/API docs.
   Follow each repository's contribution and release process.

Exact comparisons apply to deterministic fixture data and mocked transport.
Exclude only declared volatile fields such as wall-clock timestamps, not
scientifically meaningful differences. Live hosted/HPC runs are a separate
validation layer: a fixed application seed does not guarantee identical LLM
responses. Record model/server settings, request seeds where supported, cache
policy, and backend fingerprints where available; assess live variation
separately from structural refactor regressions.

## Progress

| Checkpoint | Status |
|---|---|
| Published-package audit and unchanged 0.2.18 baseline | Complete, 2026-11-08 |
| Golden real-nation integration fixture | Original golden reference retained; both offline continuation expected failures resolved in the separate 2026-11-09 cursor slice |
| Published 0.3.0 compatibility | Implemented and independently validated, 2026-11-08; 693 passed, 1 skipped, 2 expected failures; original golden reference unchanged |
| Generic network extraction and CAG wiring | Merged into CAG main `17111e3`; GABM 0.4.0 published and released-wheel acceptance recorded above |
| Offline checkpoint cursor restoration | Merged into CAG main `17111e3`; full suite 769 passed, 1 skipped, no xfails before merge; random-state persistence remains separate |
| Survey-execution extraction | Merged in both repositories; GABM 0.5.0 published and pinned; published-wheel CAG validation: 771 passed, 1 skipped, 50 subtests, 2026-11-09 |
| Survey-derived population construction | Merged into CAG main `6d2bbe3`; published GABM 0.5.0 validation: 786 passed, 1 skipped, 50 subtests; generic GABM API deferred pending a second neutral use case |
| LLM transport adaptation | Existing service gaps identified; provider parity and migration remain separate from the first survey-execution slice |
| Memory and further extractions | Candidates; scope not yet committed |

Update statuses only with the relevant test and comparison evidence. Record
scope decisions here rather than relying on chat history.
