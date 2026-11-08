# CAG to GABM Refactor Plan

**Status:** agreed direction; implementation not started.
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
behaviour, consult the [configuration guide](docs/Simulation_Configuration_Guide.md),
[code tour](docs/Code_Tour.md), and source code. The
[model design log](docs/Model_Design.md) contains historical decisions and is not an
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
| Published 0.3.0 compatibility | Not started |
| Generic network extraction and CAG wiring | Proposed first upstream extraction |
| LLM transport adaptation | Pending network slice; boundary review required |
| Memory and further extractions | Candidates; scope not yet committed |

Update statuses only with the relevant test and comparison evidence. Record
scope decisions here rather than relying on chat history.
