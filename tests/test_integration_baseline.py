"""Real-nation characterization tests for the CAG to GABM refactor."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import random
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
        # CSV hydration stringifies mixed sender IDs; timeline JSON retains that type.
        golden = json.loads(GOLDEN_PATH.read_text())
        timeline = loaded_results["agent_timeline"]
        assert {"rows": len(timeline), "sha256": _digest(timeline.to_csv(index=False))} == (
            golden["checkpoint_timelines"][mode]
        )
        # Hydration must also be idempotent.
        before = _digest(_agent_state(restored))
        assert _load_checkpoint(restored, tmp_path) == 3
        assert _digest(_agent_state(restored)) == before


@pytest.mark.parametrize("mode", ["package", "single_policy"])
@pytest.mark.parametrize("source", ["llm", "offline"])
def test_real_checkpoint_continuation_with_preserved_rng(mode, source, tmp_path):
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
        rng_at_checkpoint = random.getstate()
        restored = _make_nation()
        random.setstate(rng_at_checkpoint)
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
