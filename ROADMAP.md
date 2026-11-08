# Roadmap

## Table of Contents
- [Purpose](#purpose)
- [CAG to GABM refactor track](#cag-to-gabm-refactor-track)
- [Documentation and data organisation](#documentation-and-data-organisation)
- [Research validation backlog](#research-validation-backlog)
- [Operational validation backlog](#operational-validation-backlog)
- [Longer-term goals toward 1.0](#longer-term-goals-toward-10)

## Purpose

This is the forward-looking record of priorities, intended outcomes, and
unfinished work. It is not a release log or a promise that every candidate will
ship in 1.0. Detailed implementation plans hold acceptance gates and progress
evidence; link to them rather than duplicating their contents here.

Delivered changes and historical release milestones belong in
[CHANGE_LOG.md](CHANGE_LOG.md). Dated development context belongs in
[DEVELOPMENT_HISTORY.md](DEVELOPMENT_HISTORY.md). See the documentation
ownership rules in [DEV_GUIDE.md](DEV_GUIDE.md#root-documents).

For current model behaviour, consult the
[configuration guide](documentation/guides/Simulation_Configuration_Guide.md),
[code tour](documentation/guides/Code_Tour.md), and source code. The
[model design log](documentation/research/Model_Design.md) is a historical reference, not an
authoritative current specification. Experiment evidence is maintained in
[docs/result_report.md](documentation/research/result_report.md).

## CAG to GABM refactor track

**Immediate priority:** move reusable mechanisms into GABM while retaining CAG's
climate-policy research logic and existing behaviour. Follow the sequence and
validation gates in [GABM_Refactor_Plan.md](GABM_Refactor_Plan.md).

- Independently validate the implemented published GABM 0.3.0 compatibility
  slice and merge it before upstream extraction; retain the original golden
  integration reference to guard subsequent behaviour.
- Extract generic seeded graph generation and diagnostics into GABM, then
  wire CAG to the tested framework API.
- Review existing GABM LLM services before adapting CAG transport. Preserve
  prompt roles, request options, cache policy, and explicit failure behaviour.
- Evaluate reusable memory, checkpoint, and experiment infrastructure only
  after the preceding bounded slices demonstrate a useful API boundary.
- Resolve checkpoint reproducibility limitations in an explicit separate
  slice: offline message-pool cursor persistence, peer-selection random state,
  and the documented prompt-log/timeline hydration differences. Do not claim
  exact fresh-process replay until the relevant equivalence tests pass.

## Documentation and data organisation

- Author new prose outside `docs/`; use `docs/` for staged documentation and
  intentional Sphinx configuration/navigation inputs.
- Migrate existing authored guides incrementally, updating source links,
  copy/cleanup registration, and rendered navigation together.
  Use `documentation/guides/`, `research/`, `archive/`, and `presentations/`
  for authored material, retaining root project entry points. Continue with
  ownership of the remaining tracked generated API stubs deliberately;
  authored guides, research/archive material, index, and presentation sources
  now follow the agreed structure.
- Reconcile archived issue-planning snapshots against actual delivered work
  and open issues before consolidating unfinished items into the roadmap.
  Verify supplementary research citations and preserve historical evidence;
  relocation alone does not validate their claims.
- Review and consolidate the AIRE quickstart, generic primer, and older
  operational notes, preserving unique information and checking current
  commands against the launcher and cluster guidance. Ownership migration
  alone does not establish that historical instructions are current.
- Reduce legacy Sphinx warnings in bounded slices: unresolved guide/source
  links, duplicate API descriptions and docstring formatting, missing
  navigation entries, and historical code-block highlighting. Preserve
  historical content and validate each slice with a fresh build rather than
  globally suppressing warnings.
- Inventory data embedded in source files. Extract one coherent resource at
  a time into versioned data, with documented schema/provenance, validated
  loading, packaging coverage where required, and characterization tests.
  Keep algorithms, types, and structural constants in code.
- Reconcile the output/configuration guides against the implemented schemas
  and settings, including persona mapping, prompt capture, reached flags, and
  timeline sampling. Earlier releases carried deep guide rewrites forward;
  inspect the current guides before deciding which gaps remain.

## Research validation backlog

These items were carried forward from earlier development cycles. Verify the
existing notebooks and result reports before scheduling runs or treating an
old task as still open.

- Reconcile Tier-P persona-null production sweep evidence (real/shuffled/
  neutral, three seeds per arm) and provide or update its demonstration
  notebook once the corresponding AIRE run directories are available.
- Re-measure Condition B bias on the unified first-person debias chain
  (partial rerun of [NB 13](notebooks/13_bias_mitigation_experiment.ipynb);
  historical estimate: about 120 API calls).
- Run or reconcile 30-50-agent Qwen3 and seed-sweep evidence for per-agent
  Spearman correlation stability, following the persona-signal question from
  NB 24/25.
- Re-run or update [NB 27](notebooks/27_affinity_exposure_demo.ipynb) against
  the shipped affinity-weight ladder; its original agreement percentages are
  historical.
- Author bespoke package-level political messages for message set v2 rather
  than relying on concatenated single-policy placeholders.
- Evaluate larger-N, multi-seed reach-asymmetry experiments and longer
  campaigns (10+ days) for equilibrium and oscillation.

## Operational validation backlog

- Reconcile real-LLM AIRE evidence for the v2 memory architecture over a
  multi-day horizon (earlier proposed smoke population: 30-100 agents).
- Reconcile production validation of output bundles, network repair, and
  bucket-asymmetric persuasion at 50-100 agents. Existing Run-14 results may
  cover part of this; do not repeat work without reviewing the evidence.
- Extend model comparison where useful, including the earlier Qwen3
  14B 4-bit / 4B 2507 / 32B HPC candidates.
- Implement async/parallel dispatch only after defining ordering, random-state,
  checkpoint, and request-provenance contracts. The historical design proposal
  is in [docs/Model_Design.md](documentation/research/Model_Design.md), section 16.

Earlier backlog entries for source-version alignment, release-tag cleanup,
README status updates, and an end-to-end committed-minority run were followed
by recorded work in later releases. Reconcile any residual gaps against the
change log rather than carrying those original tasks forward unchanged.

## Longer-term goals toward 1.0

These are candidates beyond the immediate compatibility/refactor work, not an
approved implementation sequence:

- True peer-to-peer dialogue rather than one-way message exchange.
- Dynamic network rewiring based on opinion distance.
- Calibration against longitudinal survey panel data.
- Additional LLM providers and scientifically useful model comparisons.
- Publication-ready analysis and visualisation, building on the existing
  per-exposure-group tooling rather than treating it as a new feature.

When work lands, update or remove its planned item and record delivery in the
change log. Keep unfinished acceptance criteria visible without copying release
tables back into this document.
