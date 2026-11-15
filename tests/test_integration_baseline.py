"""Real-nation characterization tests for the CAG to GABM refactor."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from unittest.mock import patch

import networkx as nx
import pandas as pd
import pytest

from gabm.abm.attributes.gender import GenderID, GenderMap

from cag.abm.agent import SurveyedCitizen
from cag.abm.attributes.education import EducationID, SurveyEducationMap
from cag.abm.attributes.ethnicity import EthnicityID, SurveyEthnicityMap
from cag.abm.attributes.family import FamilyID, SurveyFamilyMap
from cag.abm.attributes.income import IncomeID, SurveyIncomeMap
from cag.abm.attributes.narratives import (
    HIGH, LOW, MODERATE, ConformTradMap, EDOMap, OpennessMap, RWAMap,
    SDOMap, SelfenhMap, SelftranscMap,
)
from cag.abm.attributes.opinion import (
    ALL_CLIMATE_POLICIES, ClimatePolicyID, SURVEY_COLUMN_MAP,
    PRO_CLIMATE_INDEX_COLUMN,
)
from cag.abm.attributes.politics import PoliticsID, SurveyPoliticsMap
from cag.abm.attributes.region import RegionID, UKRegionMap
from cag.abm.democracy.elections.brexit import BrexitVoteID, BrexitVoteMap
from cag.abm.democracy.elections.ukge2019 import UKGE2019VoteID, UKGE2019VoteMap
from cag.abm.environment import SurveyedNation
from cag.abm.sim import SIM_CONFIG, run_simulation
from cag.io.checkpoint import _load_checkpoint, _load_checkpoint_meta
from cag.io.results import _serialise_config, save_results


GOLDEN_PATH = (
    Path(__file__).resolve().parents[1]
    / "data" / "fixtures" / "cag_integration_baseline.json"
)
AGENT_IDS = list(range(8))


class _FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 8)


def _digest(value):
    encoded = json.dumps(
        value, sort_keys=True, ensure_ascii=True, allow_nan=False, default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _make_nation():
    nation = SurveyedNation(
        year=2026, place="UK",
        gender_map=GenderMap(), region_map=UKRegionMap(),
        education_map=SurveyEducationMap(), ethnicity_map=SurveyEthnicityMap(),
        income_map=SurveyIncomeMap(), politics_map=SurveyPoliticsMap(),
        family_map=SurveyFamilyMap(),
        ukge2019_vote_map=UKGE2019VoteMap(0), brexit_vote_map=BrexitVoteMap(1),
        selftransc_map=SelftranscMap, selfenh_map=SelfenhMap,
        openness_map=OpennessMap, conformtrad_map=ConformTradMap,
        sdo_map=SDOMap, edo_map=EDOMap, rwa_map=RWAMap,
    )
    for aid in AGENT_IDS:
        pro = aid % 2 == 0
        survey_data = {
            SURVEY_COLUMN_MAP[pid]: (aid + index) % 7 + 1
            for index, pid in enumerate(ALL_CLIMATE_POLICIES)
        }
        survey_data[PRO_CLIMATE_INDEX_COLUMN] = sum(survey_data.values()) / 6
        citizen = SurveyedCitizen(
            agent_id=aid, environment=nation, year_of_birth=1970 + aid * 4,
            gender_id=GenderID.FEMALE if pro else GenderID.MALE,
            region_id=RegionID.LONDON if pro else RegionID.NORTH_EAST,
            education_id=EducationID.NO_FORMAL_QUALIFICATIONS,
            ethnicity_id=EthnicityID.WHITE,
            income_id=IncomeID.BETWEEN_40000_AND_44999,
            politics_id=(
                PoliticsID.FAIRLY_LEFT_WING if pro else PoliticsID.FAIRLY_RIGHT_WING
            ),
            family_id=FamilyID.PARENT if aid < 4 else FamilyID.NOT_PARENT,
            ukge2019_vote_id=(
                UKGE2019VoteID.GREEN if pro else UKGE2019VoteID.CONSERVATIVE
            ),
            brexit_vote_id=BrexitVoteID.REMAIN if pro else BrexitVoteID.LEAVE,
            selftransc_id=HIGH if pro else LOW, selfenh_id=MODERATE,
            openness_id=HIGH if pro else LOW, conformtrad_id=LOW if pro else HIGH,
            sdo_id=LOW if pro else HIGH, edo_id=LOW if pro else HIGH,
            rwa_id=LOW if pro else HIGH,
            original_survey_data=survey_data,
        )
        nation.agents_active[aid] = citizen
    return nation


def _config(mode):
    cfg = deepcopy(SIM_CONFIG)
    cfg.update(
        n_citizens=len(AGENT_IDS), communication_mode=mode,
        llm_model="deterministic-test-model", llm_provider="local",
        llm_temperature=0.0, random_seed=42,
        political_exposure_targets={
            "A-only": 0.25, "B-only": 0.25, "both": 0.25, "neither": 0.25,
        },
        reach_a=0.75, reach_b=0.5, k_peers_per_day=2,
        timeline_sample_size=len(AGENT_IDS), timeline_sample_agent_ids=AGENT_IDS,
        diagnostics_timeout_s=None,
        days=[
            {"phases": ["P-A", "P-B", "C"]},
            {"phases": ["P-B", "P-A", "C"]},
            {"phases": ["P-A", "C", "P-B"]},
        ],
    )
    if mode == "single_policy":
        for day in cfg["days"]:
            day["policy"] = ClimatePolicyID.CARBON_TAX
    return cfg


@contextmanager
def _runtime():
    requests = []

    def send(system_prompt, user_prompt, **options):
        request = {
            "system_prompt": system_prompt, "user_prompt": user_prompt,
            "options": options,
        }
        fingerprint = _digest(request)
        if "Respond with a single letter A-G" in user_prompt:
            response = "ABCDEFG"[int(fingerprint[:8], 16) % 7]
        else:
            response = f"Synthetic response {fingerprint[:16]}."
        requests.append({**request, "response": response})
        return response

    previous_state = random.getstate()
    random.seed(42)
    try:
        with patch("cag.abm.agent.date", _FixedDate), \
             patch("cag.abm.agent.send_chat", side_effect=send), \
             patch("cag.abm.sim.configure_local"), \
             patch("cag.abm.sim.ping_local", return_value={"model": "test"}):
            yield requests
    finally:
        random.setstate(previous_state)


def _agent_state(nation):
    state = []
    for agent in nation.agents_active.values():
        state.append({
            "id": agent.id, "persona": agent.get_persona(),
            "neighbors": [neighbor.id for neighbor in agent.network_neighbors],
            "exposure": agent.political_exposure,
            "reflections": agent.reflections,
            "daily_summaries": [
                [day, str(pid), text]
                for (day, pid), text in sorted(
                    agent.daily_summaries.items(), key=lambda item: str(item[0]),
                )
            ],
            **{
                field: {str(pid): entries for pid, entries in getattr(agent, field).items()}
                for field in (
                    "opinion_history", "survey_reasoning", "survey_raw_response",
                    "survey_assembled_context",
                )
            },
        })
    return state


def _snapshot(nation, results, requests, output_dir):
    # NetworkX's categorical reduction order varies with Python's hash seed.
    diagnostics = {
        key: value for key, value in results["network_diagnostics"].items()
        if key != "elapsed_s"
    }
    diagnostics["assortativity_political_exposure"] = round(
        diagnostics["assortativity_political_exposure"], 12,
    )
    stable_results = {
        **results,
        "network_diagnostics": diagnostics,
    }
    saved = save_results(stable_results, output_dir=output_dir)
    files = {path.name: path.read_text() for path in sorted(saved.iterdir())}
    return {
        "config": _serialise_config(results["config"]),
        "tables": {
            name: {"rows": len(frame), "sha256": _digest(frame.to_csv(index=False))}
            for name, frame in results.items() if isinstance(frame, pd.DataFrame)
        },
        "requests": {"count": len(requests), "sha256": _digest(requests)},
        "agent_state_sha256": _digest(_agent_state(nation)),
        "network_snapshot": results["network_snapshot"],
        "network_diagnostics": stable_results["network_diagnostics"],
        "saved_files": list(files),
        "saved_files_sha256": _digest(files),
        "sim_step": nation._sim_step,
    }


def _run_scenario(mode, output_dir):
    with _runtime() as requests:
        nation = _make_nation()
        results = run_simulation(_config(mode), nation)
        snapshot = _snapshot(nation, results, requests, output_dir)
    return snapshot


@pytest.mark.parametrize("mode", ["package", "single_policy"])
def test_real_nation_matches_golden_and_repeats(mode, tmp_path):
    golden = json.loads(GOLDEN_PATH.read_text())
    assert golden["schema_version"] == 1
    previous_rng = random.getstate()
    first = _run_scenario(mode, tmp_path / "first")
    second = _run_scenario(mode, tmp_path / "second")
    assert random.getstate() == previous_rng
    assert first == second
    expected = golden["scenarios"][mode]
    assert first.keys() == expected.keys()
    for surface in first:
        assert first[surface] == expected[surface], surface
    policies = 6 if mode == "package" else 1
    assert first["tables"]["opinion_trajectories"]["rows"] == 8 * policies * 4
    assert first["tables"]["daily_summaries"]["rows"] == 8
    assert first["tables"]["messages"]["rows"] > 0
    assert first["tables"]["agent_prompts"]["rows"] > 0
    assert first["network_diagnostics"]["auto_connected_edges"] > 0


@pytest.mark.parametrize("mode", ["package", "single_policy"])
def test_real_checkpoint_roundtrip(mode, tmp_path):
    with _runtime():
        original = _make_nation()
        config = _config(mode)
        results = run_simulation(
            config, original, checkpoint_dir=tmp_path, checkpoint_every_day=True,
        )
        restored = _make_nation()
        # No further days: run_simulation rebuilds structure, then hydrates state.
        loaded_results = run_simulation(config, restored, checkpoint_dir=tmp_path, resume=True)
        assert _load_checkpoint_meta(tmp_path)["last_completed_day"] == 3
        assert _digest(_agent_state(original)) == _digest(_agent_state(restored))
        assert original._sim_step == restored._sim_step
        assert results["network_snapshot"] == loaded_results["network_snapshot"]
        assert nx.is_connected(restored.network)
        for name in (
            "opinion_trajectories", "reflections", "messages", "daily_summaries",
            "survey_reasoning", "survey_raw_response", "survey_assembled_context",
            "agent_attributes", "package_index_trajectories", "ground_truth",
            "package_ground_truth", "persona_map",
        ):
            assert results[name].to_csv(index=False) == loaded_results[name].to_csv(index=False)
        assert loaded_results["agent_prompts"].empty
        # Resumed timelines now match the original fresh-run baseline.
        golden = json.loads(GOLDEN_PATH.read_text())
        timeline = loaded_results["agent_timeline"]
        assert {"rows": len(timeline), "sha256": _digest(timeline.to_csv(index=False))} == (
            golden["scenarios"][mode]["tables"]["agent_timeline"]
        )
        # Hydration must also be idempotent.
        before = _digest(_agent_state(restored))
        assert _load_checkpoint(restored, tmp_path) == 3
        assert _digest(_agent_state(restored)) == before


@pytest.mark.parametrize("mode", ["package", "single_policy"])
def test_checkpoint_output_hydration_preserves_timeline_but_not_prompt_logs(
    mode, tmp_path,
):
    with _runtime():
        config = _config(mode)
        original = _make_nation()
        original_results = run_simulation(
            config, original, checkpoint_dir=tmp_path, checkpoint_every_day=True,
        )
        assert not (tmp_path / "agent_prompts.csv").exists()
        assert not (tmp_path / "agent_timeline.csv").exists()

        restored = _make_nation()
        loaded_results = run_simulation(
            config, restored, checkpoint_dir=tmp_path, resume=True,
        )
        assert not original_results["agent_prompts"].empty
        assert loaded_results["agent_prompts"].empty
        original_logs = {
            aid: deepcopy(agent.prompt_log)
            for aid, agent in original.agents_active.items()
        }
        _load_checkpoint(original, tmp_path)
        assert {
            aid: agent.prompt_log for aid, agent in original.agents_active.items()
        } == original_logs
        assert original_results["messages"].to_csv(index=False) == (
            loaded_results["messages"].to_csv(index=False)
        )

        original_messages = original_results["messages"]
        loaded_messages = loaded_results["messages"]
        original_peer_senders = original_messages.loc[
            original_messages["message_type"] == "peer_message", "sender_id"
        ].tolist()
        loaded_peer_senders = loaded_messages.loc[
            loaded_messages["message_type"] == "peer_message", "sender_id"
        ].tolist()
        assert original_peer_senders
        assert all(type(sender) is int for sender in original_peer_senders)
        assert all(type(sender) is int for sender in loaded_peer_senders)
        assert original_peer_senders == loaded_peer_senders

        original_timeline = original_results["agent_timeline"]
        loaded_timeline = loaded_results["agent_timeline"]
        assert original_timeline.to_csv(index=False) == loaded_timeline.to_csv(index=False)
        sent = loaded_timeline["event_type"] == "peer_message_sent"
        assert sent.any()
        assert all(type(agent_id) is int for agent_id in loaded_timeline.loc[sent, "agent_id"])
        assert all(type(agent_id) is int for agent_id in original_timeline["agent_id"])


@pytest.mark.parametrize("mode", ["package", "single_policy"])
def test_resumed_prompt_log_contains_only_new_calls_and_restarts_sequence(mode, tmp_path):
    with _runtime():
        config = _config(mode)
        partial_config = deepcopy(config)
        partial_config["days"] = partial_config["days"][:2]
        partial = _make_nation()
        before = run_simulation(
            partial_config, partial, checkpoint_dir=tmp_path, checkpoint_every_day=True,
        )
        assert not before["agent_prompts"].empty
        resumed = _make_nation()
        after = run_simulation(config, resumed, checkpoint_dir=tmp_path, resume=True)
        prompts = after["agent_prompts"]
        assert not prompts.empty
        assert set(prompts["day"]) == {3}
        assert set(before["agent_prompts"]["day"]).isdisjoint(set(prompts["day"]))
        for _, group in prompts.groupby("agent_id"):
            assert group["prompt_seq"].tolist() == list(range(len(group)))


@pytest.mark.parametrize("mode", ["package", "single_policy"])
@pytest.mark.parametrize("source", ["llm", "offline"])
def test_real_checkpoint_continuation_restores_rng(mode, source, tmp_path):
    with _runtime() as requests:
        config = _config(mode)
        config["political_message_source"] = source
        uninterrupted = _make_nation()
        expected = run_simulation(config, uninterrupted)
        expected_requests = list(requests)

        requests.clear()
        random.seed(42)
        partial_config = deepcopy(config)
        partial_config["days"] = partial_config["days"][:2]
        partial = _make_nation()
        run_simulation(
            partial_config, partial, checkpoint_dir=tmp_path, checkpoint_every_day=True,
        )
        restored = _make_nation()
        random.seed(123456)
        actual = run_simulation(config, restored, checkpoint_dir=tmp_path, resume=True)

        assert requests == expected_requests
        assert _digest(_agent_state(restored)) == _digest(_agent_state(uninterrupted))
        assert restored._sim_step == uninterrupted._sim_step
        assert actual["network_snapshot"] == expected["network_snapshot"]
        for name in (
            "opinion_trajectories", "package_index_trajectories", "messages",
            "reflections", "daily_summaries", "survey_reasoning",
            "survey_raw_response", "survey_assembled_context",
        ):
            assert actual[name].to_csv(index=False) == expected[name].to_csv(index=False)


@pytest.mark.parametrize("mode", ["package", "single_policy"])
@pytest.mark.parametrize("source", ["llm", "offline"])
def test_checkpoint_continuation_in_fresh_process(mode, source, tmp_path):
    with _runtime() as requests:
        config = _config(mode)
        config["political_message_source"] = source
        uninterrupted = _make_nation()
        expected = run_simulation(config, uninterrupted)
        expected_requests = list(requests)
        requests.clear()
        random.seed(42)
        partial = deepcopy(config)
        partial["days"] = partial["days"][:2]
        run_simulation(partial, _make_nation(), checkpoint_dir=tmp_path,
                       checkpoint_every_day=True)
        partial_requests = list(requests)
        assert partial_requests == expected_requests[:len(partial_requests)]

        script = """
import importlib.util
import json
import random
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("baseline", sys.argv[1])
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
with t._runtime() as requests:
    config = t._config(sys.argv[2])
    config["political_message_source"] = sys.argv[3]
    random.seed(123456)
    nation = t._make_nation()
    result = t.run_simulation(config, nation, checkpoint_dir=Path(sys.argv[4]), resume=True)
    names = ("opinion_trajectories", "package_index_trajectories", "messages",
             "reflections", "daily_summaries", "survey_reasoning",
             "survey_raw_response", "survey_assembled_context")
    output = {"requests": requests, "state": t._digest(t._agent_state(nation)),
              "step": nation._sim_step, "network": result["network_snapshot"],
              "tables": {name: result[name].to_csv(index=False) for name in names}}
    Path(sys.argv[5]).write_text(json.dumps(output))
"""
        output_path = tmp_path / "subprocess-result.json"
        subprocess.run(
            [sys.executable, "-c", script, str(Path(__file__).resolve()),
             mode, source, str(tmp_path), str(output_path)],
            check=True, capture_output=True, text=True,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
        actual = json.loads(output_path.read_text())
        assert partial_requests + actual["requests"] == expected_requests
        assert actual["state"] == _digest(_agent_state(uninterrupted))
        assert actual["step"] == uninterrupted._sim_step
        assert actual["network"] == expected["network_snapshot"]
        for name, csv in actual["tables"].items():
            assert csv == expected[name].to_csv(index=False)


@pytest.mark.parametrize("mode", ["package", "single_policy"])
@pytest.mark.parametrize("source", ["llm", "offline"])
def test_repeated_checkpoint_continuation_restores_rng(mode, source, tmp_path):
    with _runtime() as requests:
        config = _config(mode)
        config["political_message_source"] = source
        uninterrupted = _make_nation()
        expected = run_simulation(config, uninterrupted)
        expected_requests = list(requests)
        requests.clear()
        random.seed(42)
        first = deepcopy(config)
        first["days"] = first["days"][:1]
        run_simulation(first, _make_nation(), checkpoint_dir=tmp_path,
                       checkpoint_every_day=True)
        second = deepcopy(config)
        second["days"] = second["days"][:2]
        random.seed(100)
        run_simulation(second, _make_nation(), checkpoint_dir=tmp_path,
                       resume=True, checkpoint_every_day=True)
        random.seed(200)
        restored = _make_nation()
        actual = run_simulation(config, restored, checkpoint_dir=tmp_path, resume=True)

        assert requests == expected_requests
        assert _digest(_agent_state(restored)) == _digest(_agent_state(uninterrupted))
        assert restored._sim_step == uninterrupted._sim_step
        for name in ("messages", "reflections", "opinion_trajectories",
                     "daily_summaries", "survey_reasoning"):
            assert actual[name].to_csv(index=False) == expected[name].to_csv(index=False)


@pytest.mark.parametrize("source", ["offline", "llm"])
def test_checkpoint_without_random_state_rejects_continuation_but_loads_completed(
    source, tmp_path,
):
    with _runtime():
        config = _config("package")
        config["political_message_source"] = source
        partial = deepcopy(config)
        partial["days"] = partial["days"][:1]
        run_simulation(partial, _make_nation(), checkpoint_dir=tmp_path,
                       checkpoint_every_day=True)
        meta_path = tmp_path / "checkpoint_meta.json"
        meta = json.loads(meta_path.read_text())
        del meta["random_state"]
        meta_path.write_text(json.dumps(meta))

        before = random.getstate()
        with pytest.raises(ValueError, match="lacks Python random state"):
            run_simulation(config, _make_nation(), checkpoint_dir=tmp_path, resume=True)
        assert random.getstate() == before
        run_simulation(partial, _make_nation(), checkpoint_dir=tmp_path, resume=True)
        assert random.getstate() == before


@pytest.mark.parametrize("state", [None, [], [3, [], None], [3, [True], None],
                                    [3, [0], "invalid"], [999, [0], None]])
def test_checkpoint_rejects_invalid_random_state_without_changing_rng(state, tmp_path):
    with _runtime():
        config = _config("single_policy")
        partial = deepcopy(config)
        partial["days"] = partial["days"][:1]
        run_simulation(partial, _make_nation(), checkpoint_dir=tmp_path,
                       checkpoint_every_day=True)
        meta_path = tmp_path / "checkpoint_meta.json"
        meta = json.loads(meta_path.read_text())
        meta["random_state"] = state
        meta_path.write_text(json.dumps(meta))
        before = random.getstate()
        with pytest.raises(ValueError, match="Invalid Python random state"):
            run_simulation(config, _make_nation(), checkpoint_dir=tmp_path, resume=True)
        assert random.getstate() == before


@pytest.mark.parametrize("source", ["offline", "llm"])
def test_legacy_checkpoint_without_pool_state(source, tmp_path):
    with _runtime():
        config = _config("package")
        config["political_message_source"] = source
        partial_config = deepcopy(config)
        partial_config["days"] = partial_config["days"][:1]
        run_simulation(
            partial_config, _make_nation(), checkpoint_dir=tmp_path,
            checkpoint_every_day=True,
        )
        meta_path = tmp_path / "checkpoint_meta.json"
        meta = json.loads(meta_path.read_text())
        meta.pop("message_pool_state", None)
        meta_path.write_text(json.dumps(meta))

        if source == "offline":
            with pytest.raises(ValueError, match="lacks message-pool rotation state"):
                run_simulation(
                    config, _make_nation(), checkpoint_dir=tmp_path, resume=True,
                )
        else:
            run_simulation(config, _make_nation(), checkpoint_dir=tmp_path, resume=True)
