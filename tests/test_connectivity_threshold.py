"""Regression tests for the CAG connectivity analysis using GABM."""

import csv
import runpy
from pathlib import Path

import networkx as nx
import pytest

import estimate_connectivity_threshold as analysis


def _legacy_graph(n_citizens, p_intra, p_inter, seed):
    block_size = n_citizens // 2
    return nx.stochastic_block_model(
        [block_size, n_citizens - block_size],
        [[p_intra, p_inter], [p_inter, p_intra]],
        seed=seed,
    )


@pytest.mark.parametrize("n_citizens", [1, 2, 9, 10, 21])
@pytest.mark.parametrize("seed", [0, 42, 123])
def test_sbm_matches_prior_seeded_nodes_and_edges(n_citizens, seed):
    expected = _legacy_graph(n_citizens, 0.4, 0.1, seed)

    graph = analysis.build_sbm(n_citizens, 0.4, 0.1, seed)

    assert list(graph.nodes) == list(expected.nodes)
    assert list(graph.edges) == list(expected.edges)


def test_connectivity_rate_matches_prior_trial_sequence():
    expected = sum(
        nx.is_connected(_legacy_graph(9, 0.4, 0.2, analysis.RANDOM_SEED + trial))
        for trial in range(20)
    ) / 20

    assert analysis.estimate_connectivity_rate(9, 0.2, 20, p_intra=0.4) == expected


def test_import_does_not_create_outputs_or_run_sweep(monkeypatch, capsys):
    def unexpected_side_effect(*args, **kwargs):
        pytest.fail("Importing the analysis must not write output or build networks")

    monkeypatch.setattr(Path, "mkdir", unexpected_side_effect)
    monkeypatch.setattr(nx, "stochastic_block_model", unexpected_side_effect)

    runpy.run_path(analysis.__file__, run_name="connectivity_import_test")

    assert capsys.readouterr().out == ""


def test_reduced_sweep_preserves_csv_plot_and_summary(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(analysis, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(analysis, "POPULATION_SIZES", [9, 10])
    monkeypatch.setattr(analysis, "P_INTER_VALUES", [0.1, 0.5])
    monkeypatch.setattr(analysis, "N_TRIALS", 4)

    analysis.main()

    with (analysis.OUTPUT_DIR / "connectivity_sweep.csv").open(newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["n_citizens", "p_inter", "connectivity_rate"]
        rows = list(reader)
    assert len(rows) == 4
    for row, (n_citizens, p_inter) in zip(
        rows, [(9, 0.1), (9, 0.5), (10, 0.1), (10, 0.5)],
    ):
        expected = sum(
            nx.is_connected(_legacy_graph(
                n_citizens, analysis.P_INTRA, p_inter, analysis.RANDOM_SEED + trial,
            ))
            for trial in range(4)
        ) / 4
        assert int(row["n_citizens"]) == n_citizens
        assert float(row["p_inter"]) == p_inter
        assert float(row["connectivity_rate"]) == expected
    assert (analysis.OUTPUT_DIR / "connectivity_threshold.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n"
    )
    output = capsys.readouterr().out
    assert "CONNECTIVITY SUMMARY (by population size)" in output
    assert "RECOMMENDED p_inter for 90% connectivity guarantee" in output
