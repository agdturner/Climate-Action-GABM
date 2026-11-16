"""
Per-day checkpoint write / resume validation / load for Climate-Action-GABM.

Owns the checkpoint schema version, the resume-key allow-lists, the
fingerprint hash, the writer, the metadata loader, the resume-validator,
and the agent-state hydrator. Extracted from ``cag.abm.sim`` in the
2026-06-22 refactor; all names are re-exported from ``cag.abm.sim`` for
backwards compatibility.
"""

__version__ = "0.9.0"

import hashlib
import json
import logging
import math
import random
from datetime import datetime
from pathlib import Path

import pandas as pd

from cag.abm.attributes.opinion import ALL_CLIMATE_POLICIES, PACKAGE_SCOPE
from cag.io.results import (
    _RESULT_CSV_SCHEMAS,
    _atomic_write_json,
    _collect_results,
    _safe_step,
    _serialise_config,
    _write_all_csvs,
)


CHECKPOINT_SCHEMA_VERSION = 1

# Config keys whose change must abort a resume (would silently corrupt
# the simulation if mismatched against the saved state).
# Note: ``p_intra`` and ``p_inter`` are *not* listed here — they are folded
# into the resolved ``network_params`` dict by ``_resolve_network_params``
# and compared in resolved form by ``_validate_resume_config`` so that
# upgrading a config from flat legacy keys to ``network_params={...}``
# (or vice versa) does not trigger a spurious resume mismatch.
_RESUME_HARD_KEYS = (
    "n_citizens", "random_seed", "network_type",
    "communication_mode", "package_policies", "day0_anchor",
    "reach_a", "reach_b", "reach_targeting_a", "reach_targeting_b", "audience_cap",
    "political_exposure_mode", "political_exposure_targets",
    "affinity_weights",
    "political_message_source", "political_message_set",
    # Persona ablation drives every agent's persona text (and thus every
    # prompt); switching mode mid-run would make the resumed prompts
    # inconsistent with the state built on Day 0.
    "persona_mode",
    # Memory config is hard: the verbatim window drives which days get
    # compressed into daily_summaries, so a mid-run change would make the
    # stored summaries inconsistent with the resumed config.
    "memory",
)
# Config keys we tolerate changing on resume but log a warning for.
_RESUME_SOFT_KEYS = (
    "llm_model", "llm_provider", "survey_model", "survey_provider",
    "thinking", "llm_temperature",
    "local_base_url", "local_extra_body", "local_timeout_s",
)


def _config_hash(serialised_config):
    """Stable hash of a serialised config dict for fingerprinting."""
    blob = json.dumps(serialised_config, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def _agents_by_checkpoint_id(nation):
    """Map serialized IDs to agents, rejecting ambiguous string forms."""
    by_id = {}
    for aid, agent in nation.agents_active.items():
        key = str(aid)
        if key in by_id:
            raise ValueError(f"Ambiguous checkpoint agent ID {key!r}: "
                             "multiple active IDs have the same string form.")
        by_id[key] = agent
    return by_id


def _write_checkpoint(nation, cfg, last_day, checkpoint_dir, *, message_pool=None):
    """Write a per-day checkpoint to ``checkpoint_dir`` (atomic)."""
    _agents_by_checkpoint_id(nation)
    random_state = random.getstate()
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    results = _collect_results(nation, cfg)
    _write_all_csvs(checkpoint_dir, results, is_checkpoint=True)

    serialised = _serialise_config(cfg)
    meta = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "last_completed_day": int(last_day),
        # Sort by string form for stable on-disk fingerprint across runs
        # whose agent IDs may be a mix of ints / floats / strings.
        "agent_ids": sorted(
            (str(aid) for aid in nation.agents_active.keys()),
        ),
        "config": serialised,
        "config_hash": _config_hash(serialised),
        "random_state": random_state,
        "written_at": datetime.now().isoformat(timespec="seconds"),
    }
    if message_pool is not None:
        meta["message_pool_state"] = message_pool.export_state()
    if cfg.get("checkpoint_prompt_logs", False):
        sample = nation._prompt_capture_ids
        meta["prompt_logs"] = {
            "version": 1,
            "sample_ids": [str(aid) for aid in sample],
            "entries": {
                str(aid): [
                    {key: value for key, value in entry.items() if key != "agent_id"}
                    for entry in nation.agents_active[aid].prompt_log
                ]
                for aid in sample
            },
        }
    _atomic_write_json(meta, checkpoint_dir / "checkpoint_meta.json")
    logging.info(
        f"Checkpoint written for day {last_day} to {checkpoint_dir}"
    )


def _checkpoint_prompt_logs(meta, nation, sample_ids):
    """Validate opt-in prompt history before mutating any agent."""
    data = meta.get("prompt_logs")
    if data is None:
        raise ValueError(
            "Checkpoint lacks prompt history required by checkpoint_prompt_logs. "
            "Start a fresh run or resume with prompt persistence disabled."
        )
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Invalid checkpoint prompt history version or format.")
    saved_sample = data.get("sample_ids")
    entries = data.get("entries")
    if (
        not isinstance(saved_sample, list)
        or not all(isinstance(aid, str) for aid in saved_sample)
        or len(set(saved_sample)) != len(saved_sample)
        or not isinstance(entries, dict)
        or set(entries) != set(saved_sample)
    ):
        raise ValueError("Invalid checkpoint prompt history sample or entries.")
    current_sample = [str(aid) for aid in sample_ids]
    if set(saved_sample) != set(current_sample):
        raise ValueError("Cannot resume: resolved prompt capture sample changed.")

    fields = {"prompt_seq", "day", "phase", "stage", "policy_id",
              "system_prompt", "user_prompt", "response"}
    by_id = _agents_by_checkpoint_id(nation)
    restored = {}
    for aid in saved_sample:
        rows = entries[aid]
        if not isinstance(rows, list) or aid not in by_id:
            raise ValueError("Invalid checkpoint prompt history entries.")
        restored[aid] = []
        for index, row in enumerate(rows):
            if (
                not isinstance(row, dict) or set(row) != fields
                or type(row["prompt_seq"]) is not int or row["prompt_seq"] != index
                or type(row["day"]) is not int
                or not 0 <= row["day"] <= int(meta["last_completed_day"])
                or not all(isinstance(row[key], str) for key in fields - {"prompt_seq", "day"})
            ):
                raise ValueError(f"Invalid checkpoint prompt history for agent {aid!r}.")
            restored[aid].append({"agent_id": by_id[aid].id, **row})
    return restored


def _checkpoint_random_state(meta):
    """Validate a JSON-decoded Python random state without changing global state."""
    if "random_state" not in meta:
        raise ValueError(
            "Checkpoint lacks Python random state. Start a fresh run; exact "
            "continuation of this older checkpoint is not supported."
        )
    state = meta["random_state"]
    if (
        not isinstance(state, list) or len(state) != 3
        or type(state[0]) is not int
        or not isinstance(state[1], list)
        or not all(type(value) is int for value in state[1])
        or (
            state[2] is not None
            and (type(state[2]) is not float or not math.isfinite(state[2]))
        )
    ):
        raise ValueError("Invalid Python random state in checkpoint.")
    restored = (state[0], tuple(state[1]), state[2])
    try:
        random.Random().setstate(restored)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid Python random state in checkpoint.") from exc
    return restored


def _load_checkpoint_meta(checkpoint_dir):
    with open(Path(checkpoint_dir) / "checkpoint_meta.json") as f:
        meta = json.load(f)
    if meta.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(
            f"Incompatible checkpoint schema version "
            f"{meta.get('schema_version')!r} (expected "
            f"{CHECKPOINT_SCHEMA_VERSION}). Re-run from scratch."
        )
    return meta


def _validate_resume_config(meta, cfg, nation):
    """Hard-fail on incompatible config; warn on soft-key changes."""
    # Late import: _resolve_network_params lives in cag.abm.sim. Top-level
    # would create an import-time cycle (sim re-exports this module at EOF).
    from cag.abm.sim import _resolve_network_params

    saved = meta["config"]
    new = _serialise_config(cfg)

    # Hard keys: structural, must match exactly.
    for key in _RESUME_HARD_KEYS:
        if saved.get(key) != new.get(key):
            raise ValueError(
                f"Cannot resume: config key '{key}' changed "
                f"(checkpoint={saved.get(key)!r}, new={new.get(key)!r}). "
                f"This would invalidate prior agent state."
            )

    # Network params: compared in *resolved* form so that a config which
    # previously used legacy flat keys (``p_intra``/``p_inter``) and is
    # later upgraded to ``network_params={...}`` (or vice versa) is not
    # rejected for a difference that has no effect on the actual graph.
    saved_net = _resolve_network_params(saved)
    new_net = _resolve_network_params(new)
    if saved_net != new_net:
        raise ValueError(
            f"Cannot resume: resolved network parameters changed "
            f"(checkpoint={saved_net!r}, new={new_net!r}). "
            f"This would invalidate the peer network."
        )

    # Days schedule: the new config must extend (or match) the checkpoint's
    # already-completed prefix. We allow future days to grow / change, but
    # the past is immutable.
    last_completed = int(meta.get("last_completed_day", 0))
    saved_days = saved.get("days") or []
    new_days = new.get("days") or []
    if last_completed > len(new_days):
        raise ValueError(
            f"Cannot resume: checkpoint completed through day "
            f"{last_completed} but new config only declares "
            f"{len(new_days)} day(s). The new config must extend (or "
            f"match) the checkpoint's day schedule."
        )
    if saved_days[:last_completed] != new_days[:last_completed]:
        raise ValueError(
            f"Cannot resume: cfg['days'][0:{last_completed}] differs "
            f"from the checkpoint's already-completed schedule. Past "
            f"days are immutable; only future entries may be added or "
            f"modified."
        )

    # Agent ID set must match.
    saved_id_list = meta.get("agent_ids", [])
    saved_ids = set(saved_id_list)
    if len(saved_ids) != len(saved_id_list):
        raise ValueError("Cannot resume: checkpoint has ambiguous duplicate agent IDs.")
    current_ids = set(_agents_by_checkpoint_id(nation))
    if saved_ids != current_ids:
        missing = saved_ids - current_ids
        extra = current_ids - saved_ids
        raise ValueError(
            f"Cannot resume: active agent set differs from checkpoint. "
            f"Missing: {sorted(missing)[:5]}{'...' if len(missing) > 5 else ''}, "
            f"Extra: {sorted(extra)[:5]}{'...' if len(extra) > 5 else ''}"
        )

    # Soft keys: warn only.
    for key in _RESUME_SOFT_KEYS:
        if saved.get(key) != new.get(key):
            logging.warning(
                "Resume: config key '%s' changed "
                "(checkpoint=%r, new=%r). Proceeding, but downstream "
                "analysis must account for this.",
                key, saved.get(key), new.get(key),
            )


def _load_checkpoint(nation, checkpoint_dir):
    """Hydrate ``nation`` and its agents from a checkpoint dir.

    Returns the ``last_completed_day`` from the checkpoint metadata.
    """
    checkpoint_dir = Path(checkpoint_dir)
    meta = _load_checkpoint_meta(checkpoint_dir)
    last_day = int(meta["last_completed_day"])

    # Build a str(policy_id) -> policy_id lookup so reloaded CSV strings
    # become the same ClimatePolicyID objects used by live code. Agents
    # key opinion_history / daily_summaries / survey_reasoning by the
    # enum object, not its str repr; mixing the two would silently create
    # parallel entries on the next day.
    policy_lookup = {str(pid): pid for pid in ALL_CLIMATE_POLICIES}
    policy_lookup[PACKAGE_SCOPE] = PACKAGE_SCOPE
    policy_lookup[""] = ""

    def _to_policy(value):
        # NaN can leak in from pd.read_csv on optional / package-mode columns
        # (e.g. messages.csv policy_id is empty in package mode). Without this
        # guard, str(NaN) -> 'nan' would propagate as a fake policy id and
        # poison opinion_history / message_log keys, getting strictly worse on
        # every resume cycle.
        if value is None or value == "" or (
            isinstance(value, float) and pd.isna(value)
        ):
            return ""
        return policy_lookup.get(str(value), str(value))

    def _str(value):
        """Coerce optional string-typed cells to '' (NaN/None -> '')."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        return value

    by_id = _agents_by_checkpoint_id(nation)
    saved_ids = meta.get("agent_ids", [])
    if len(set(saved_ids)) != len(saved_ids):
        raise ValueError("Cannot load checkpoint: ambiguous duplicate agent IDs.")

    def _read(name):
        path = checkpoint_dir / f"{name}.csv"
        if not path.exists():
            return pd.DataFrame(columns=_RESULT_CSV_SCHEMAS[name])
        df = pd.read_csv(path, converters={
            "agent_id": str, "sender_id": str, "recipient_id": str,
        })
        # Replace NaN with None across the frame so str()/json.loads/dict-keys
        # don't see literal 'nan' or float NaN downstream. Critical for
        # messages.csv where package mode leaves policy_id empty.
        return df.where(pd.notna(df), None)

    def _citizen_id(value):
        if value not in by_id:
            raise ValueError(f"Checkpoint references unknown citizen ID {value!r}.")
        return by_id[value].id

    msgs = _read("messages")
    for row in msgs.itertuples(index=False):
        if row.sender_type == "citizen":
            _citizen_id(row.sender_id)
        _citizen_id(row.recipient_id)

    # Reset agent mutable state before hydration so re-loading is idempotent.
    for agent in by_id.values():
        agent.opinion_history = {}
        agent.reflections = []
        agent.daily_summaries = {}
        agent.survey_reasoning = {}
        agent.survey_raw_response = {}
        agent.survey_assembled_context = {}
        agent._daily_summary_steps = {}
        agent._survey_reasoning_steps = {}
        agent._survey_raw_response_steps = {}
        agent._survey_assembled_context_steps = {}

    # opinion_history
    opin = _read("opinion_trajectories")
    for row in opin.itertuples(index=False):
        agent = by_id.get(str(row.agent_id))
        if agent is None:
            continue
        pid = _to_policy(row.policy_id)
        agent.opinion_history.setdefault(pid, []).append(
            (int(row.day), int(row.numeric))
        )

    # reflections
    refl = _read("reflections")
    for row in refl.itertuples(index=False):
        agent = by_id.get(str(row.agent_id))
        if agent is None:
            continue
        try:
            messages_received = json.loads(row.messages_received_json)
        except (TypeError, ValueError):
            messages_received = []
        try:
            policy_ids = json.loads(row.policy_ids_json)
        except (TypeError, ValueError):
            policy_ids = []
        entry = {
            "day": int(row.day),
            "phase": row.phase,
            "policy_id": _to_policy(row.policy_id),
            "text": row.text,
            "messages_received": messages_received,
            "sim_step": _safe_step(getattr(row, "sim_step", 0)),
        }
        if policy_ids:
            entry["policy_ids"] = [_to_policy(p) for p in policy_ids]
        agent.reflections.append(entry)

    # daily_summaries
    summ = _read("daily_summaries")
    for row in summ.itertuples(index=False):
        agent = by_id.get(str(row.agent_id))
        if agent is None:
            continue
        key = (int(row.day), _to_policy(row.policy_id))
        agent.daily_summaries[key] = row.summary
        agent._daily_summary_steps[key] = _safe_step(getattr(row, "sim_step", 0))

    # survey_reasoning
    sreas = _read("survey_reasoning")
    for row in sreas.itertuples(index=False):
        agent = by_id.get(str(row.agent_id))
        if agent is None:
            continue
        pid = _to_policy(row.policy_id)
        agent.survey_reasoning.setdefault(pid, []).append(
            (int(row.day), row.reasoning)
        )
        agent._survey_reasoning_steps.setdefault(pid, []).append(
            _safe_step(getattr(row, "sim_step", 0))
        )

    # survey_raw_response (added in v0.5; missing on older checkpoints)
    sraw = _read("survey_raw_response")
    for row in sraw.itertuples(index=False):
        agent = by_id.get(str(row.agent_id))
        if agent is None:
            continue
        pid = _to_policy(row.policy_id)
        agent.survey_raw_response.setdefault(pid, []).append(
            (int(row.day), row.raw_response)
        )
        agent._survey_raw_response_steps.setdefault(pid, []).append(
            _safe_step(getattr(row, "sim_step", 0))
        )

    # survey_assembled_context (added with timeline; missing on older checkpoints)
    sac = _read("survey_assembled_context")
    for row in sac.itertuples(index=False):
        agent = by_id.get(str(row.agent_id))
        if agent is None:
            continue
        pid = _to_policy(row.policy_id)
        agent.survey_assembled_context.setdefault(pid, []).append(
            (int(row.day), row.assembled_context)
        )
        agent._survey_assembled_context_steps.setdefault(pid, []).append(
            _safe_step(getattr(row, "sim_step", 0))
        )

    # nation.message_log
    nation.message_log = []
    for row in msgs.itertuples(index=False):
        try:
            policy_ids = json.loads(row.policy_ids_json)
        except (TypeError, ValueError):
            policy_ids = []
        nation.message_log.append({
            "sim_step": _safe_step(getattr(row, "sim_step", 0)),
            "day": int(row.day) if pd.notna(row.day) else None,
            "phase": _str(row.phase),
            "message_type": _str(row.message_type),
            "sender_type": _str(row.sender_type),
            "sender_id": (
                _citizen_id(row.sender_id)
                if row.sender_type == "citizen"
                else row.sender_id
            ),
            "sender_side": _str(row.sender_side),
            "policy_id": _to_policy(row.policy_id),
            "package_scope": _str(row.package_scope),
            "policy_ids": [_to_policy(p) for p in policy_ids],
            "recipient_id": _citizen_id(row.recipient_id),
            "recipient_scope": _str(row.recipient_scope),
            "message_text": _str(row.message_text),
            "political_message_id": _str(getattr(row, "political_message_id", "")),
        })

    # Restore the monotonic sim_step counter so events logged after
    # resume don't collide (or under-count) relative to the pre-checkpoint
    # tail. Scan every loaded source and take the max.
    max_step = 0
    for df in (refl, summ, sreas, sraw, sac, msgs):
        if df is None or df.empty or "sim_step" not in df.columns:
            continue
        try:
            m = int(pd.to_numeric(df["sim_step"], errors="coerce").max() or 0)
        except Exception:  # noqa: BLE001
            m = 0
        if m > max_step:
            max_step = m
    nation._sim_step = max_step

    return last_day
