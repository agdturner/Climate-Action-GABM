"""Exact input contracts for the pure CAG memory formatter."""

from copy import deepcopy
from unittest import mock

import pytest

from cag.abm.agent import SurveyedCitizen
from cag.abm.attributes.opinion import ClimatePolicyID, PACKAGE_SCOPE
from cag.abm.memory import build_daily_memory_input


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (PACKAGE_SCOPE,
         "Reflections after messages:\n"
         "-  carbon reflection \n- package reflection\n- unscoped reflection\n\n"
         "My own survey reasoning today:\n"
         "- Accelerate renewable energy roll-out: renewable first\n"
         "- Accelerate renewable energy roll-out: renewable second\n"
         "- Carbon fee and dividend:  carbon reasoning "),
        (ClimatePolicyID.CARBON_TAX,
         "Reflections after messages:\n-  carbon reflection \n\n"
         "My own survey reasoning today:\n- Carbon fee and dividend:  carbon reasoning "),
    ],
)
def test_exact_scope_order_duplicates_and_whitespace_without_mutation(scope, expected):
    reflections = [
        {"day": 2, "policy_id": ClimatePolicyID.CARBON_TAX,
         "text": " carbon reflection "},
        {"day": 1, "policy_id": ClimatePolicyID.CARBON_TAX, "text": "wrong day"},
        {"day": 2, "policy_id": PACKAGE_SCOPE, "text": "package reflection"},
        {"day": 2, "text": "unscoped reflection"},
    ]
    reasoning = {
        ClimatePolicyID.CARBON_TAX: [(2, " carbon reasoning "), (1, "wrong day")],
        PACKAGE_SCOPE: [(2, "excluded package reasoning")],
        ClimatePolicyID.RENEWABLE_ENERGY: [
            (2, "renewable first"), (2, "renewable second"),
        ],
    }
    before = deepcopy((reflections, reasoning))

    assert build_daily_memory_input(
        reflections, reasoning, day=2, policy_id=scope,
    ) == expected

    assert (reflections, reasoning) == before


@pytest.mark.parametrize(
    ("reflections", "reasoning", "expected"),
    [
        ([], {}, ""),
        ([{"day": 1, "text": "excluded"}], {}, ""),
        ([{"day": 2, "text": ""}], {}, "Reflections after messages:\n- "),
        ([], {"unknown_policy": [(2, " raw\n")]},
         "My own survey reasoning today:\n- unknown_policy:  raw\n"),
    ],
)
def test_empty_and_one_source_inputs(reflections, reasoning, expected):
    assert build_daily_memory_input(
        reflections, reasoning, day=2, policy_id=PACKAGE_SCOPE,
    ) == expected


def test_agent_delegates_inputs_but_retains_transport_and_recording():
    citizen = SurveyedCitizen(agent_id=1, environment=None, year_of_birth=1990)
    citizen.compress_memories = mock.Mock(return_value="raw summary")
    citizen._sim_step = mock.Mock(return_value=23)
    with mock.patch("cag.abm.agent.build_daily_memory_input", return_value="input") as build:
        result = citizen.compress_daily_memory(
            2, PACKAGE_SCOPE, api_key="key", model="model",
            provider="local", temperature=0.25,
        )

    build.assert_called_once_with(
        citizen.reflections, citizen.survey_reasoning, day=2, policy_id=PACKAGE_SCOPE,
    )
    assert build.call_args.args[0] is citizen.reflections
    assert build.call_args.args[1] is citizen.survey_reasoning
    citizen.compress_memories.assert_called_once_with(
        "input", api_key="key", model="model", provider="local", temperature=0.25,
    )
    assert result == "raw summary"
    assert citizen.daily_summaries == {(2, PACKAGE_SCOPE): result}
    assert citizen._daily_summary_steps == {(2, PACKAGE_SCOPE): 23}
