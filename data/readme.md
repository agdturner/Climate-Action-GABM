## All data go here...

### Regression fixtures

[fixtures/cag_integration_baseline.json](fixtures/cag_integration_baseline.json)
is a versioned, compact reference for the real-nation refactor tests. It contains
synthetic-scenario configurations, graph data, dependency provenance, row counts,
and SHA-256 fingerprints, not private survey records or full generated runs.

The synthetic input rows and deterministic transport strategy are defined in
[tests/test_integration_baseline.py](../tests/test_integration_baseline.py).
See [GABM_Refactor_Plan.md](../GABM_Refactor_Plan.md) for validation commands,
normalization rules, and characterized checkpoint limitations. Review actual
behaviour differences before changing a golden reference.
