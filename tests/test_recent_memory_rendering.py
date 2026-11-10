"""Direct contracts for pure recent-memory rendering and agent delegation."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from cag.abm.agent import SurveyedCitizen
from cag.abm.attributes.opinion import ClimatePolicyID, PACKAGE_SCOPE
from cag.abm.memory import render_recent_own_reasoning, render_recent_reflections


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (PACKAGE_SCOPE, "- Day 3:  package \n- Day 2: older package"),
        (ClimatePolicyID.CARBON_TAX, "- Day 2: single"),
        (None, "- Day 3:  package \n- Day 2: single\n- Day 2: older package"),
    ],
)
def test_reflection_scope_order_whitespace_and_non_mutation(scope, expected):
    reflections = [
        {"day": 3, "policy_id": PACKAGE_SCOPE, "text": " package "},
        {"day": 1, "policy_id": PACKAGE_SCOPE, "text": "outside"},
        {"day": 2, "policy_id": ClimatePolicyID.CARBON_TAX, "text": "single"},
        {"day": 2, "policy_id": PACKAGE_SCOPE, "text": "older package"},
    ]
    before = deepcopy(reflections)
    assert render_recent_reflections(
        reflections, day=3, policy_id=scope, window=2,
    ) == "Recent reflections following received messages:\n" + expected
    assert reflections == before


@pytest.mark.parametrize("window", [1, 2, None])
def test_window_boundaries_day_zero_and_future_entries(window):
    reflections = [
        {"day": d, "text": str(d)} for d in range(4)
    ]
    reasoning = {"custom": [(d, f" {d} ") for d in range(4)]}
    keep = {1: [2], 2: [1, 2], None: [0, 1, 2]}[window]
    assert render_recent_reflections(
        reflections, day=2, policy_id=None, window=window,
    ) == "Recent reflections following received messages:\n" + "\n".join(
        f"- Day {d}: {d}" for d in keep
    )
    assert render_recent_own_reasoning(
        reasoning, day=2, target_policy_id="custom", window=window,
    ) == "Your considered position in recent days:\n" + "\n".join(
        f"- Day {d} \u2014 custom: {d}" for d in keep if d > 0
    )


def test_reasoning_preserves_duplicates_order_and_strips_text_without_mutation():
    target = ClimatePolicyID.CARBON_TAX
    reasoning = {
        target: [(2, " current\n"), (1, " previous "), (2, " duplicate ")],
        ClimatePolicyID.RENEWABLE_ENERGY: [(2, "excluded")],
    }
    before = deepcopy(reasoning)
    assert render_recent_own_reasoning(
        reasoning, day=2, target_policy_id=target, window=2,
    ) == (
        "Your considered position in recent days:\n"
        "- Day 2 \u2014 Carbon fee and dividend: current\n"
        "- Day 1 \u2014 Carbon fee and dividend: previous\n"
        "- Day 2 \u2014 Carbon fee and dividend: duplicate"
    )
    assert reasoning == before


@pytest.mark.parametrize("target", [None, PACKAGE_SCOPE, "missing"])
def test_absent_or_non_target_reasoning_is_empty(target):
    assert render_recent_own_reasoning(
        {}, day=2, target_policy_id=target, window=2,
    ) == ""


def test_day_zero_and_empty_histories_render_nothing():
    assert render_recent_reflections(
        [{"day": 0, "text": "day zero"}], day=0, policy_id=None, window=None,
    ) == ""
    assert render_recent_own_reasoning(
        {"custom": [(0, "anchor")]}, day=0,
        target_policy_id="custom", window=None,
    ) == ""
    assert render_recent_reflections([], day=2, policy_id=None, window=2) == ""


def test_agent_section_wrappers_pass_original_histories_and_arguments():
    citizen = SurveyedCitizen(agent_id=1, environment=None, year_of_birth=1990)
    with patch("cag.abm.agent.render_recent_reflections", return_value="reflections") as reflections:
        assert citizen._section_recent_reflections(3, PACKAGE_SCOPE, 2) == "reflections"
    reflections.assert_called_once_with(
        citizen.reflections, day=3, policy_id=PACKAGE_SCOPE, window=2,
    )
    assert reflections.call_args.args[0] is citizen.reflections
    with patch("cag.abm.agent.render_recent_own_reasoning", return_value="reasoning") as reasoning:
        assert citizen._section_recent_own_reasoning(3, "custom", None) == "reasoning"
    reasoning.assert_called_once_with(
        citizen.survey_reasoning, day=3, target_policy_id="custom", window=None,
    )
    assert reasoning.call_args.args[0] is citizen.survey_reasoning
