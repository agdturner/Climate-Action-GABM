"""
Tests for cag.abm.sim checkpoint + resume functionality.

Reuses the mock-nation fixtures from tests/test_sim.py.
Run with: python -m pytest tests/test_checkpoint.py -v
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import cag.io.checkpoint as checkpoint
import cag.io.results as results
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from cag.abm.attributes.opinion import ClimatePolicyID
from cag.io.checkpoint import _checkpoint_random_state, _resolve_checkpoint_dir
from cag.abm.sim import (
    CHECKPOINT_SCHEMA_VERSION,
    _load_checkpoint,
    _load_checkpoint_meta,
    _validate_resume_config,
    _write_checkpoint,
    run_simulation,
)

from test_sim import _make_mock_agent, _make_mock_nation


def _base_config(tmp_dir):
    return {
        "n_citizens": 3,
        "days": [
            {"policy": ClimatePolicyID.CARBON_TAX, "phases": ["P-A", "P-B", "C"]},
            {"policy": ClimatePolicyID.CARBON_TAX, "phases": ["P-A", "P-B", "C"]},
            {"policy": ClimatePolicyID.CARBON_TAX, "phases": ["P-A", "P-B", "C"]},
        ],
        "k_peers_per_day": 1,
        "p_intra": 0.15,
        "p_inter": 0.02,
        "random_seed": 42,
        "communication_mode": "single_policy",
        "llm_model": "mock-model",
        "llm_provider": "openai",
    }


def test_random_state_json_roundtrip_preserves_cached_gaussian():
    rng = random.Random(42)
    rng.gauss(0, 1)
    state = rng.getstate()
    decoded = json.loads(json.dumps({"random_state": state}))
    restored = random.Random()
    restored.setstate(_checkpoint_random_state(decoded))
    assert restored.getstate() == state
    assert restored.gauss(0, 1) == rng.gauss(0, 1)


@pytest.mark.parametrize("cut", [0, 1, 3, 5, "before_meta", "before_pointer", "after_pointer"])
def test_interrupted_generation_preserves_complete_resume(cut, tmp_path):
    class Interrupted(Exception):
        pass

    cfg = _base_config(tmp_path)
    cfg["days"] = cfg["days"][:2]
    first = dict(cfg, days=cfg["days"][:1])
    csv_writer = results._atomic_write_csv
    json_writer = checkpoint._atomic_write_json
    count = 0

    def interrupt_csv(df, path):
        nonlocal count
        if cut == count:
            raise Interrupted()
        csv_writer(df, path)
        count += 1

    def interrupt_json(obj, path):
        if cut == "before_meta" and path.name == "checkpoint_meta.json":
            raise Interrupted()
        if cut == "before_pointer" and path.name == "checkpoint_current.json":
            raise Interrupted()
        json_writer(obj, path)
        if cut == "after_pointer" and path.name == "checkpoint_current.json":
            raise Interrupted()

    with patch("cag.abm.sim.load_api_key", return_value="mock-key"), \
         patch("cag.abm.sim.PoliticalAgent"):
        run_simulation(first, _make_mock_nation(3), checkpoint_dir=tmp_path,
                       checkpoint_every_day=True)
        original_dir = _resolve_checkpoint_dir(tmp_path)
        with patch.object(results, "_atomic_write_csv", side_effect=interrupt_csv), \
             patch.object(checkpoint, "_atomic_write_json", side_effect=interrupt_json), \
             pytest.raises(Interrupted):
            run_simulation(cfg, _make_mock_nation(3), checkpoint_dir=tmp_path,
                           resume=True, checkpoint_every_day=True)

        committed = _resolve_checkpoint_dir(tmp_path)
        assert (committed == original_dir) is (cut != "after_pointer")
        restored = _make_mock_nation(3)
        loaded_day = _load_checkpoint(restored, tmp_path)
        assert loaded_day == (2 if cut == "after_pointer" else 1)
        assert max(day for day, _ in restored.agents_active[0.0].opinion_history[
            ClimatePolicyID.CARBON_TAX
        ]) == loaded_day
        resumed = _make_mock_nation(3)
        run_simulation(cfg, resumed, checkpoint_dir=tmp_path, resume=True)
        assert resumed.agents_active[0.0].opinion_history[
            ClimatePolicyID.CARBON_TAX
        ] == [(0, 2), (1, 1), (2, 1)]
        if cut == "after_pointer":
            assert original_dir.is_dir()


def test_checkpoint_retains_previous_generation_and_rejects_missing_file(tmp_path):
    nation = _make_mock_nation(1)
    cfg = _base_config(tmp_path)
    _write_checkpoint(nation, cfg, 0, tmp_path)
    first = _resolve_checkpoint_dir(tmp_path)
    _write_checkpoint(nation, cfg, 1, tmp_path)
    second = _resolve_checkpoint_dir(tmp_path)
    assert first.is_dir()
    _write_checkpoint(nation, cfg, 2, tmp_path)
    assert not first.exists()
    assert second.is_dir()
    current = _resolve_checkpoint_dir(tmp_path)
    (current / "messages.csv").unlink()
    with pytest.raises(ValueError, match="generation is missing files"):
        _load_checkpoint(_make_mock_nation(1), tmp_path)


@pytest.mark.parametrize("cut", ["csv", "pointer"])
def test_process_exit_during_checkpoint_write(cut, tmp_path):
    cfg = _base_config(tmp_path)
    cfg["days"] = cfg["days"][:2]
    with patch("cag.abm.sim.load_api_key", return_value="mock-key"), \
         patch("cag.abm.sim.PoliticalAgent"):
        run_simulation(dict(cfg, days=cfg["days"][:1]), _make_mock_nation(3),
                       checkpoint_dir=tmp_path, checkpoint_every_day=True)
        original_dir = _resolve_checkpoint_dir(tmp_path)
        script = """
import os
import sys
from pathlib import Path
from unittest.mock import patch
import cag.io.checkpoint as checkpoint
import cag.io.results as results
from cag.abm.sim import run_simulation
from test_checkpoint import _base_config
from test_sim import _make_mock_nation
root = Path(sys.argv[1])
cut = sys.argv[2]
cfg = _base_config(root)
cfg["days"] = cfg["days"][:2]
csv = results._atomic_write_csv
write_json = checkpoint._atomic_write_json
def csv_writer(df, path):
    csv(df, path)
    if cut == "csv":
        os._exit(73)
def json_writer(obj, path):
    write_json(obj, path)
    if cut == "pointer" and path.name == "checkpoint_current.json":
        os._exit(73)
with patch("cag.abm.sim.load_api_key", return_value="mock-key"), \\
     patch("cag.abm.sim.PoliticalAgent"), \\
     patch.object(results, "_atomic_write_csv", side_effect=csv_writer), \\
     patch.object(checkpoint, "_atomic_write_json", side_effect=json_writer):
    run_simulation(cfg, _make_mock_nation(3), checkpoint_dir=root,
                   resume=True, checkpoint_every_day=True)
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([
            str(Path(__file__).parent), str(Path(__file__).parent.parent / "src"),
            env.get("PYTHONPATH", ""),
        ])
        process = subprocess.run([sys.executable, "-c", script, str(tmp_path), cut],
                                 env=env, capture_output=True, text=True)
        assert process.returncode == 73, process.stderr
        assert (_resolve_checkpoint_dir(tmp_path) == original_dir) is (cut == "csv")
        restored = _make_mock_nation(3)
        run_simulation(cfg, restored, checkpoint_dir=tmp_path, resume=True)
        assert restored.agents_active[0.0].opinion_history[
            ClimatePolicyID.CARBON_TAX
        ] == [(0, 2), (1, 1), (2, 1)]


def test_legacy_checkpoint_requires_opt_in_and_migrates(tmp_path, caplog):
    cfg = _base_config(tmp_path)
    cfg["days"] = cfg["days"][:2]
    first = dict(cfg, days=cfg["days"][:1])
    with patch("cag.abm.sim.load_api_key", return_value="mock-key"), \
         patch("cag.abm.sim.PoliticalAgent"):
        run_simulation(first, _make_mock_nation(3), checkpoint_dir=tmp_path,
                       checkpoint_every_day=True)
        generation = _resolve_checkpoint_dir(tmp_path)
        for path in generation.iterdir():
            if path.is_file():
                shutil.copy2(path, tmp_path / path.name)
        legacy_meta = tmp_path / "checkpoint_meta.json"
        data = json.loads(legacy_meta.read_text())
        del data["checkpoint_files"]
        legacy_meta.write_text(json.dumps(data))
        (tmp_path / "checkpoint_current.json").unlink()
        with pytest.raises(ValueError, match="Legacy checkpoint"):
            run_simulation(cfg, _make_mock_nation(3), checkpoint_dir=tmp_path, resume=True)
        run_simulation(cfg, _make_mock_nation(3), checkpoint_dir=tmp_path,
                       resume=True, allow_legacy_checkpoint=True,
                       checkpoint_every_day=True)
        assert "files may contain mixed days" in caplog.text
        assert _load_checkpoint_meta(tmp_path)["last_completed_day"] == 2
        assert _resolve_checkpoint_dir(tmp_path) != tmp_path


@pytest.mark.parametrize("pointer", [
    {}, {"version": 1, "current": "../evil", "previous": None},
    {"version": 1, "current": "a" * 32, "previous": "a" * 32},
])
def test_invalid_checkpoint_pointer_rejected(tmp_path, pointer):
    (tmp_path / "checkpoint_current.json").write_text(json.dumps(pointer))
    with pytest.raises(ValueError, match="Invalid checkpoint generation pointer"):
        _load_checkpoint_meta(tmp_path, allow_legacy=True)


@pytest.mark.parametrize("ids", [(1, 2), (1.0, 2.0), ("001", "02"), ("NA", "None"),
                                ("1", "2"), ("001", 1)])
def test_checkpoint_preserves_citizen_ids_and_political_sender(ids, tmp_path):
    def nation():
        result = _make_mock_nation(0)
        result.agents_active = {aid: _make_mock_agent(aid) for aid in ids}
        return result

    original = nation()
    original.agents_active[ids[0]].opinion_history = {
        ClimatePolicyID.CARBON_TAX: [(0, 3)],
    }
    original.message_log = [
        {"day": 1, "phase": "P-A", "message_type": "political_broadcast",
         "sender_type": "political_agent", "sender_id": str(ids[0]),
         "recipient_id": ids[1], "recipient_scope": "broadcast",
         "message_text": "broadcast"},
        {"day": 1, "phase": "C", "message_type": "peer_message",
         "sender_type": "citizen", "sender_id": ids[0],
         "recipient_id": ids[1], "recipient_scope": "direct",
         "message_text": "peer"},
    ]
    _write_checkpoint(original, _base_config(tmp_path), 1, tmp_path)
    restored = nation()
    _load_checkpoint(restored, tmp_path)
    assert restored.agents_active[ids[0]].opinion_history == (
        original.agents_active[ids[0]].opinion_history
    )
    political, peer = restored.message_log
    assert political["sender_id"] == str(ids[0])
    assert type(political["sender_id"]) is str
    assert peer["sender_id"] == ids[0] and type(peer["sender_id"]) is type(ids[0])
    for event in (political, peer):
        assert event["recipient_id"] == ids[1]
        assert type(event["recipient_id"]) is type(ids[1])
    _load_checkpoint(restored, tmp_path)
    assert restored.message_log[1]["sender_id"] == ids[0]


def test_checkpoint_rejects_colliding_string_forms_before_writing(tmp_path):
    nation = _make_mock_nation(0)
    nation.agents_active = {1: _make_mock_agent(1), "1": _make_mock_agent("1")}
    with pytest.raises(ValueError, match="Ambiguous checkpoint agent ID"):
        _write_checkpoint(nation, _base_config(tmp_path), 1, tmp_path)
    assert not (tmp_path / "checkpoint_meta.json").exists()


def test_checkpoint_rejects_collisions_before_hydrating(tmp_path):
    original = _make_mock_nation(1)
    _write_checkpoint(original, _base_config(tmp_path), 1, tmp_path)
    ambiguous = _make_mock_nation(0)
    ambiguous.agents_active = {
        1: _make_mock_agent(1), "1": _make_mock_agent("1"),
    }
    ambiguous.agents_active[1].opinion_history = {"sentinel": [(0, 2)]}
    with pytest.raises(ValueError, match="Ambiguous checkpoint agent ID"):
        _load_checkpoint(ambiguous, tmp_path)
    assert ambiguous.agents_active[1].opinion_history == {"sentinel": [(0, 2)]}


def test_checkpoint_rejects_duplicate_saved_ids(tmp_path):
    original = _make_mock_nation(1)
    _write_checkpoint(original, _base_config(tmp_path), 1, tmp_path)
    path = _resolve_checkpoint_dir(tmp_path) / "checkpoint_meta.json"
    meta = json.loads(path.read_text())
    meta["agent_ids"] *= 2
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="ambiguous duplicate agent IDs"):
        _load_checkpoint(_make_mock_nation(1), tmp_path)
    with pytest.raises(ValueError, match="ambiguous duplicate agent IDs"):
        _validate_resume_config(meta, _base_config(tmp_path), _make_mock_nation(1))


@pytest.mark.parametrize("column", ["sender_id", "recipient_id"])
def test_unknown_message_citizen_does_not_clear_existing_state(column, tmp_path):
    original = _make_mock_nation(1)
    original.message_log = [{
        "day": 1, "phase": "C", "message_type": "peer_message",
        "sender_type": "citizen", "sender_id": 0.0, "recipient_id": 0.0,
        "recipient_scope": "direct", "message_text": "hello",
    }]
    _write_checkpoint(original, _base_config(tmp_path), 1, tmp_path)
    path = _resolve_checkpoint_dir(tmp_path) / "messages.csv"
    messages = pd.read_csv(path, dtype={column: str})
    messages.loc[0, column] = "unknown"
    messages.to_csv(path, index=False)
    restored = _make_mock_nation(1)
    restored.agents_active[0.0].opinion_history = {"sentinel": [(0, 2)]}
    with pytest.raises(ValueError, match="unknown citizen ID 'unknown'"):
        _load_checkpoint(restored, tmp_path)
    assert restored.agents_active[0.0].opinion_history == {"sentinel": [(0, 2)]}


@patch("cag.abm.sim.load_api_key", return_value="mock-key")
@patch("cag.abm.sim.PoliticalAgent")
class TestCheckpointRoundtrip(unittest.TestCase):

    def test_checkpoint_write_and_load_roundtrip(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:2]

            nation = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            generation = _resolve_checkpoint_dir(ckpt)
            self.assertTrue((generation / "checkpoint_meta.json").exists())
            self.assertTrue((generation / "opinion_trajectories.csv").exists())
            self.assertTrue((generation / "reflections.csv").exists())
            self.assertTrue((generation / "messages.csv").exists())

            meta = _load_checkpoint_meta(ckpt)
            self.assertEqual(meta["last_completed_day"], 2)
            self.assertEqual(meta["schema_version"], CHECKPOINT_SCHEMA_VERSION)
            self.assertEqual(set(meta["agent_ids"]),
                             {str(aid) for aid in nation.agents_active.keys()})

            # Load into a fresh mock nation and assert state is restored.
            fresh = _make_mock_nation(n_agents=3)
            last_day = _load_checkpoint(fresh, ckpt)
            self.assertEqual(last_day, 2)

            # Compare the four agent state fields.
            for aid, original in nation.agents_active.items():
                restored = fresh.agents_active[aid]
                self.assertEqual(
                    restored.opinion_history, original.opinion_history,
                    f"opinion_history mismatch for agent {aid}",
                )
                # Reflections list compared by length + (day, phase, text).
                self.assertEqual(
                    len(restored.reflections), len(original.reflections),
                    f"reflections length mismatch for agent {aid}",
                )
                for r_orig, r_new in zip(original.reflections, restored.reflections):
                    self.assertEqual(r_orig["day"], r_new["day"])
                    self.assertEqual(r_orig["phase"], r_new["phase"])
                    self.assertEqual(r_orig["text"], r_new["text"])
                self.assertEqual(
                    restored.daily_summaries, original.daily_summaries,
                    f"daily_summaries mismatch for agent {aid}",
                )
                self.assertEqual(
                    restored.survey_reasoning, original.survey_reasoning,
                    f"survey_reasoning mismatch for agent {aid}",
                )
                self.assertEqual(
                    restored.survey_raw_response, original.survey_raw_response,
                    f"survey_raw_response mismatch for agent {aid}",
                )

            # nation.message_log restored.
            self.assertEqual(len(fresh.message_log), len(nation.message_log))

    def test_checkpoint_roundtrip_preserves_political_message_id(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            nation = _make_mock_nation(n_agents=1)

            nation.agents_active[0].opinion_history = {
                ClimatePolicyID.CARBON_TAX: [(0, 1)]
            }
            nation.message_log = [{
                "day": 1,
                "phase": "P-A",
                "message_type": "political_broadcast",
                "sender_type": "political_agent",
                "sender_id": "agent_a",
                "sender_side": "A",
                "recipient_id": 0.0,
                "recipient_scope": "citizen",
                "policy_id": ClimatePolicyID.CARBON_TAX,
                "package_scope": "",
                "policy_ids": [],
                "message_text": "hello",
                "political_message_id": "A_05_01",
            }]

            _write_checkpoint(nation, cfg, last_day=1, checkpoint_dir=ckpt)

            msgs = pd.read_csv(_resolve_checkpoint_dir(ckpt) / "messages.csv", keep_default_na=False)
            self.assertIn("political_message_id", msgs.columns)
            self.assertEqual(msgs.iloc[0]["political_message_id"], "A_05_01")

            fresh = _make_mock_nation(n_agents=1)
            _load_checkpoint(fresh, ckpt)
            self.assertEqual(
                fresh.message_log[0]["political_message_id"],
                "A_05_01",
            )


@patch("cag.abm.sim.load_api_key", return_value="mock-key")
@patch("cag.abm.sim.PoliticalAgent")
class TestResume(unittest.TestCase):

    def test_resume_continues_day_numbering(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:2]

            # Phase 1: run 2 days with checkpointing.
            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            # Phase 2: extend to 3 days, resume from checkpoint.
            cfg2 = _base_config(tmp)  # full 3-day config
            nation2 = _make_mock_nation(n_agents=3)
            results = run_simulation(cfg2, nation2, checkpoint_dir=ckpt,
                                     resume=True, checkpoint_every_day=True)

            traj = results["opinion_trajectories"]
            days_seen = sorted(traj["day"].unique().tolist())
            # Day 0 + 1 + 2 (restored) and 3 (newly run).
            self.assertEqual(days_seen, [0, 1, 2, 3])

    def test_resume_skips_day0(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:1]

            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            # Resume — track Day 0 LLM calls.
            nation2 = _make_mock_nation(n_agents=3)
            run_simulation(_base_config(tmp), nation2,
                           checkpoint_dir=ckpt, resume=True)

            for agent in nation2.agents_active.values():
                # administer_survey may be called for day>=1 (EOD survey),
                # but never for day=0 on resume.
                day0_calls = [
                    c for c in agent.administer_survey.call_args_list
                    if c.kwargs.get("day", 0) == 0
                ]
                self.assertEqual(
                    day0_calls, [],
                    f"Day 0 survey called on resume for agent {agent.id}",
                )
                self.assertEqual(
                    agent.seed_opinion_from_ground_truth.call_count, 0,
                )

    def test_resume_rejects_incompatible_config(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:1]

            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            # Change random_seed — must hard-fail.
            cfg_bad = _base_config(tmp)
            cfg_bad["random_seed"] = 999
            nation2 = _make_mock_nation(n_agents=3)
            with self.assertRaises(ValueError) as ctx:
                run_simulation(cfg_bad, nation2, checkpoint_dir=ckpt,
                               resume=True)
            self.assertIn("random_seed", str(ctx.exception))

    def test_resume_warns_on_model_change(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:1]

            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            cfg2 = _base_config(tmp)
            cfg2["llm_model"] = "different-model"
            nation2 = _make_mock_nation(n_agents=3)
            with self.assertLogs("root", level="WARNING") as logs:
                run_simulation(cfg2, nation2, checkpoint_dir=ckpt,
                               resume=True)
            self.assertTrue(
                any("llm_model" in m for m in logs.output),
                f"Expected llm_model warning, got: {logs.output}",
            )

    def test_resume_with_no_checkpoint_fails(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint_does_not_exist"
            nation = _make_mock_nation(n_agents=3)
            with self.assertRaises(FileNotFoundError):
                run_simulation(_base_config(tmp), nation,
                               checkpoint_dir=ckpt, resume=True)

    def test_resume_rejects_changed_agent_set(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:1]

            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            # Different number of agents.
            nation2 = _make_mock_nation(n_agents=5)
            with self.assertRaises(ValueError) as ctx:
                run_simulation(_base_config(tmp), nation2,
                               checkpoint_dir=ckpt, resume=True)
            self.assertIn("agent set", str(ctx.exception))


@patch("cag.abm.sim.load_api_key", return_value="mock-key")
@patch("cag.abm.sim.PoliticalAgent")
class TestResumeNaNHandling(unittest.TestCase):
    """Round-trip resume must not turn empty CSV cells into the literal 'nan'."""

    def _package_config(self, tmp_dir):
        cfg = _base_config(tmp_dir)
        cfg["communication_mode"] = "package"
        cfg["package_policies"] = [
            ClimatePolicyID.CARBON_TAX,
            ClimatePolicyID.RENEWABLE_ENERGY,
        ]
        return cfg

    def test_two_cycle_package_resume_does_not_propagate_nan(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = self._package_config(tmp)
            cfg["days"] = cfg["days"][:1]

            # Cycle 1: run day 1 in package mode and checkpoint.
            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            # Cycle 2: resume into a fresh nation, run day 2, checkpoint again.
            cfg2 = self._package_config(tmp)
            cfg2["days"] = cfg2["days"][:2]
            nation2 = _make_mock_nation(n_agents=3)
            run_simulation(cfg2, nation2, checkpoint_dir=ckpt,
                           resume=True, checkpoint_every_day=True)

            # Inspect the resulting messages.csv: no string column may contain
            # the literal 'nan' that str(np.nan) produces. This is the regression
            # this test guards against — without NaN normalisation in
            # _load_checkpoint, package-mode policy_id / package_scope round-trip
            # as the string 'nan' on the second checkpoint.
            import pandas as pd  # local import keeps top-level imports tidy
            msgs = pd.read_csv(_resolve_checkpoint_dir(ckpt) / "messages.csv", keep_default_na=False)
            for col in ("policy_id", "recipient_scope", "package_scope",
                        "policy_ids_json", "sender_side"):
                offending = msgs[msgs[col].astype(str).str.lower() == "nan"]
                self.assertTrue(
                    offending.empty,
                    f"messages.csv column {col!r} contains 'nan' strings "
                    f"after a two-cycle package-mode resume:\n{offending}",
                )


@patch("cag.abm.sim.load_api_key", return_value="mock-key")
@patch("cag.abm.sim.PoliticalAgent")
class TestResumeDaysValidation(unittest.TestCase):

    def test_resume_rejects_days_prefix_mismatch(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:2]

            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            # Mutate an already-completed day's policy and try to resume.
            cfg_bad = _base_config(tmp)
            cfg_bad["days"][0] = {
                "policy": ClimatePolicyID.RENEWABLE_ENERGY,
                "phases": ["P-A", "P-B", "C"],
            }
            nation2 = _make_mock_nation(n_agents=3)
            with self.assertRaises(ValueError) as ctx:
                run_simulation(cfg_bad, nation2, checkpoint_dir=ckpt,
                               resume=True)
            self.assertIn("days", str(ctx.exception).lower())

    def test_resume_rejects_shorter_days_than_checkpoint(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)  # 3 days

            nation1 = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation1, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            # New config declares fewer days than the checkpoint already ran.
            cfg_short = _base_config(tmp)
            cfg_short["days"] = cfg_short["days"][:1]
            nation2 = _make_mock_nation(n_agents=3)
            with self.assertRaises(ValueError) as ctx:
                run_simulation(cfg_short, nation2, checkpoint_dir=ckpt,
                               resume=True)
            self.assertIn("day", str(ctx.exception).lower())


class TestAtomicWrite(unittest.TestCase):

    @patch("cag.abm.sim.load_api_key", return_value="mock-key")
    @patch("cag.abm.sim.PoliticalAgent")
    def test_no_tmp_files_left_after_write(self, _pa, _key):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt = Path(tmp) / "checkpoint"
            cfg = _base_config(tmp)
            cfg["days"] = cfg["days"][:1]

            nation = _make_mock_nation(n_agents=3)
            run_simulation(cfg, nation, checkpoint_dir=ckpt,
                           checkpoint_every_day=True)

            tmp_files = list(ckpt.glob("*.tmp"))
            self.assertEqual(tmp_files, [],
                             f"Found leftover .tmp files: {tmp_files}")


class TestRequiredArgs(unittest.TestCase):

    @patch("cag.abm.sim.load_api_key", return_value="mock-key")
    @patch("cag.abm.sim.PoliticalAgent")
    def test_resume_without_checkpoint_dir_raises(self, _pa, _key):
        nation = _make_mock_nation(n_agents=3)
        with self.assertRaises(ValueError) as ctx:
            run_simulation({"days": []}, nation, resume=True)
        self.assertIn("checkpoint_dir", str(ctx.exception))

    @patch("cag.abm.sim.load_api_key", return_value="mock-key")
    @patch("cag.abm.sim.PoliticalAgent")
    def test_checkpoint_every_day_without_dir_raises(self, _pa, _key):
        nation = _make_mock_nation(n_agents=3)
        with self.assertRaises(ValueError) as ctx:
            run_simulation({"days": []}, nation, checkpoint_every_day=True)
        self.assertIn("checkpoint_dir", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
