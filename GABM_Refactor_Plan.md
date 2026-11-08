# CAG to GABM Refactor Plan

**Status:** integration baseline and published 0.3.0 compatibility validated;
generic framework extraction not started.

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

**Audit date:** 2026-11-08.

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
- Offline message-pool cursors are not restored: resumed broadcasts restart
  their rotation. Package and single-policy offline continuation equivalence
  tests are marked **strict expected failures** for this known limitation.
  Unexpected success requires updating the tests; unrelated exceptions do not
  satisfy the expected assertion-failure condition.

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

### 5. Evaluate further extractions

Consider checkpoint infrastructure and experiment provenance/comparison helpers
after the earlier slices demonstrate a useful pattern. Retain CAG-specific
schemas and analysis. Do not generalise speculatively or relocate HPC scripts
merely to match a framework example.

## Two-repository development and release workflow

1. Keep CAG as the active application workspace and GABM as the framework
   development/reference checkout. Use separate, focused changes in each.
2. For each extraction, document the API boundary and acceptance evidence.
   Add generic tests in GABM and keep domain/integration tests in CAG.
3. Test CAG against an isolated editable GABM checkout while developing new
   APIs. Record the GABM commit; an editable checkout is not release evidence.
4. Validate the built GABM wheel with CAG before publishing a new release.
5. Release GABM, then pin CAG to that published version and rerun the gates
   without source-path overrides. GABM 0.3.0 cannot supply APIs added later.
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
| Golden real-nation integration fixture | Implemented and validated, 2026-11-08; 6 passing tests and 2 strict expected failures characterize offline continuation limitations |
| Published 0.3.0 compatibility | Implemented and independently validated, 2026-11-08; 693 passed, 1 skipped, 2 expected failures; original golden reference unchanged |
| Generic network extraction and CAG wiring | Proposed first upstream extraction |
| LLM transport adaptation | Pending network slice; boundary review required |
| Memory and further extractions | Candidates; scope not yet committed |

Update statuses only with the relevant test and comparison evidence. Record
scope decisions here rather than relying on chat history.
