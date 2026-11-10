"""Exact context-rendering contracts before separating pure renderers."""

from copy import deepcopy
from unittest.mock import Mock

from cag.abm.agent import SurveyedCitizen
from cag.abm.attributes.opinion import ClimatePolicyID, PACKAGE_SCOPE
from cag.abm.config.memory import resolve_memory_config


def _citizen():
    citizen = SurveyedCitizen(agent_id=1, environment=None, year_of_birth=1990)
    citizen.get_persona = Mock(return_value=" persona ")
    return citizen


def test_complete_context_exact_order_whitespace_scope_and_no_mutation():
    citizen = _citizen()
    target = ClimatePolicyID.CARBON_TAX
    other = ClimatePolicyID.RENEWABLE_ENERGY
    citizen.memory_cfg = resolve_memory_config({
        "opinion_trajectory": {"enabled": True},
    })
    citizen.daily_summaries = {
        (2, PACKAGE_SCOPE): "too recent",
        (1, PACKAGE_SCOPE): " summary ",
    }
    citizen.reflections = [
        {"day": 3, "policy_id": PACKAGE_SCOPE, "text": " current "},
        {"day": 2, "policy_id": target, "text": "wrong scope"},
        {"day": 2, "policy_id": PACKAGE_SCOPE, "text": "previous"},
    ]
    citizen.survey_reasoning = {
        target: [(0, " anchor \n"), (0, "ignored duplicate anchor"),
                 (3, " current reasoning "), (2, "\n previous reasoning ")],
        other: [(3, "earlier reason"), (3, " latest reason \n")],
    }
    citizen.opinion_history = {
        target: [(2, 1), (0, 0), (4, -3)],
        other: [(3, -1), (3, 2)],
    }
    before = deepcopy((
        citizen.daily_summaries, citizen.reflections,
        citizen.survey_reasoning, citizen.opinion_history, citizen.memory_cfg,
    ))

    actual = citizen.assemble_context(
        day=3, policy_id=PACKAGE_SCOPE, target_policy_id=target,
    )

    assert actual == "\n\n".join([
        " persona ",
        'Original prior position on "Carbon fee and dividend":\nanchor',
        "Summary of recent days:\nDay 1:  summary ",
        "Recent reflections following received messages:\n"
        "- Day 3:  current \n- Day 2: previous",
        "Your considered position in recent days:\n"
        "- Day 3 \u2014 Carbon fee and dividend: current reasoning\n"
        "- Day 2 \u2014 Carbon fee and dividend: previous reasoning",
        'Your recorded stance over time on "Carbon fee and dividend":\n'
        "- Day 2: slightly support\n- Day 0: neutral",
        "Your answers so far in today's survey:\n"
        "- Accelerate renewable energy roll-out: somewhat support. "
        "(Why: latest reason)",
    ])
    assert (
        citizen.daily_summaries, citizen.reflections,
        citizen.survey_reasoning, citizen.opinion_history, citizen.memory_cfg,
    ) == before


def test_stage_overrides_skip_persona_and_trajectory_without_changing_global_config():
    citizen = _citizen()
    target = ClimatePolicyID.CARBON_TAX
    citizen.memory_cfg = resolve_memory_config({
        "opinion_trajectory": {"enabled": True},
        "stages": {"reflection": {
            "persona": {"enabled": False},
            "opinion_trajectory": {"enabled": False},
        }},
    })
    citizen.opinion_history[target] = [(1, 0)]
    before = deepcopy(citizen.memory_cfg)

    assert citizen.assemble_context(
        day=1, policy_id=target, target_policy_id=target, stage="reflection",
    ) == ""
    citizen.get_persona.assert_not_called()
    assert citizen.assemble_context(
        day=1, policy_id=target, target_policy_id=target, stage="survey",
    ) == (
        " persona \n\n"
        'Your recorded stance over time on "Carbon fee and dividend":\n'
        "- Day 1: neutral"
    )
    assert citizen.memory_cfg == before


def test_package_anchor_uses_canonical_order_first_entries_and_strips_text():
    citizen = _citizen()
    citizen.survey_reasoning = {
        ClimatePolicyID.CARBON_TAX: [(0, " carbon "), (0, "ignored")],
        ClimatePolicyID.RENEWABLE_ENERGY: [(0, " renewable\n")],
    }

    assert citizen.assemble_context(day=0, policy_id=PACKAGE_SCOPE) == (
        " persona \n\nOriginal prior positions:\n"
        "- Accelerate renewable energy roll-out: renewable\n"
        "- Carbon fee and dividend: carbon"
    )


def test_empty_persona_still_contributes_separator_when_enabled():
    citizen = _citizen()
    citizen.get_persona.return_value = ""
    target = ClimatePolicyID.CARBON_TAX
    citizen.survey_reasoning[target] = [(0, "anchor")]

    assert citizen.assemble_context(day=0, target_policy_id=target) == (
        '\n\nOriginal prior position on "Carbon fee and dividend":\nanchor'
    )
