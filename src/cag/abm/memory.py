"""CAG-owned selection and formatting of episodic memory."""

from collections.abc import Mapping, Sequence

from cag.abm.attributes.opinion import (
    ClimatePolicyID,
    PACKAGE_SCOPE,
    SURVEY_SHORT_LABELS,
)
from cag.abm.config.memory import verbatim_days


def render_recent_reflections(
    reflections: Sequence[Mapping[str, object]],
    *,
    day: int,
    policy_id: ClimatePolicyID | str | None,
    window: int | None,
) -> str:
    """Render in-window reflections in history order, retaining raw whitespace."""
    if day < 1:
        return ""
    keep_days = verbatim_days(window, day)
    entries = [
        r for r in reflections
        if r["day"] in keep_days
        and (policy_id is None or r.get("policy_id") == policy_id)
    ]
    if not entries:
        return ""
    return "Recent reflections following received messages:\n" + "\n".join(
        f"- Day {r['day']}: {r['text']}" for r in entries
    )


def render_recent_own_reasoning(
    survey_reasoning: Mapping[ClimatePolicyID | str, Sequence[tuple[int, str]]],
    *,
    day: int,
    target_policy_id: ClimatePolicyID | str | None,
    window: int | None,
) -> str:
    """Render target reasoning in history order, stripping text and excluding Day 0."""
    if day < 1 or target_policy_id is None or target_policy_id == PACKAGE_SCOPE:
        return ""
    keep_days = verbatim_days(window, day)
    entries = survey_reasoning.get(target_policy_id, [])
    label = SURVEY_SHORT_LABELS.get(target_policy_id, str(target_policy_id))
    lines = [
        f"- Day {d} \u2014 {label}: {text.strip()}"
        for d, text in entries
        if d in keep_days and d > 0
    ]
    if not lines:
        return ""
    return "Your considered position in recent days:\n" + "\n".join(lines)


def build_daily_memory_input(
    reflections: Sequence[Mapping[str, object]],
    survey_reasoning: Mapping[ClimatePolicyID | str, Sequence[tuple[int, str]]],
    *,
    day: int,
    policy_id: ClimatePolicyID | str,
) -> str:
    """Render a day's compression input without transport or state changes.

    Package scope includes all same-day reflections and policy reasoning,
    excluding the package reasoning bucket. Single-policy scope matches only
    that policy. Retains reflection order, string-sorted policy order,
    duplicate entries, and raw whitespace. Returns empty text for no memories.
    """
    if policy_id == PACKAGE_SCOPE:
        day_reflections = [r for r in reflections if r["day"] == day]
    else:
        day_reflections = [
            r for r in reflections
            if r["day"] == day and r.get("policy_id") == policy_id
        ]

    day_reasoning = []
    if policy_id == PACKAGE_SCOPE:
        for pid in sorted(survey_reasoning.keys(), key=str):
            if pid == PACKAGE_SCOPE:
                continue
            for d, text in survey_reasoning[pid]:
                if d == day:
                    label = SURVEY_SHORT_LABELS.get(pid, str(pid))
                    day_reasoning.append((label, text))
    else:
        for d, text in survey_reasoning.get(policy_id, []):
            if d == day:
                label = SURVEY_SHORT_LABELS.get(policy_id, str(policy_id))
                day_reasoning.append((label, text))

    parts = []
    if day_reflections:
        parts.append(
            "Reflections after messages:\n"
            + "\n".join(f"- {r['text']}" for r in day_reflections)
        )
    if day_reasoning:
        parts.append(
            "My own survey reasoning today:\n"
            + "\n".join(f"- {label}: {text}" for label, text in day_reasoning)
        )
    return "\n\n".join(parts)
