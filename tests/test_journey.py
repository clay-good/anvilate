"""The next step: every workflow result says what to do next, from the result alone.

The spec's scenarios: a bracket whose only failure has a solved inverse is told to
re-validate at the solved value first; a passing T1 card whose document demands T3 FEA is
pointed at the FEA tool before any export; and every tool a step can name is one the
server publishes, held against the live catalog.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anvilate.journey import NEXT_STEP_TOOLS, NextStep, NextSteps, next_steps
from anvilate.refusal import RefusalError
from anvilate.scorecard import (
    CheckStatus,
    Direction,
    Need,
    RepairHint,
    Scorecard,
    ScorecardEntry,
    ValueSource,
)

_EXAMPLES = Path(__file__).parents[1] / "examples"


def _passing(name: str = "plate bending") -> ScorecardEntry:
    return ScorecardEntry.from_safety_factor(name, computed=2.0, required=1.0)


def _failing(name: str, *, value: float | None) -> ScorecardEntry:
    hint = RepairHint(parameter="element_params.thickness", direction=Direction.INCREASE,
                      corrective_value=value, unit="mm" if value else None)  # fmt: skip
    entry = ScorecardEntry.from_safety_factor(name, computed=0.8, required=1.0)
    return entry.model_copy(update={"repair_hint": hint})


def _unrun(name: str, *needs: str) -> ScorecardEntry:
    return ScorecardEntry(
        name=name, status=CheckStatus.NOT_EVALUATED, detail="not evaluated",
        needs=tuple(Need(declaration=d, takes=f"the {d}", sources=(ValueSource.USER,))
                    for d in needs),
    )  # fmt: skip


def test_a_failing_check_with_an_inverse_is_revalidated_at_the_solved_value_first():
    card = Scorecard(entries=(_passing(), _failing("upright bending", value=7.4)))
    first = next_steps(card)[0]
    assert first.tool == "run_validation"
    assert dict(first.arguments) == {"set": "element_params.thickness", "to": "7.4 mm"}
    assert "upright bending" in first.reason and "7.4 mm" in first.reason


def test_a_passing_card_with_an_unrun_tier_names_the_fea_tool_before_any_export():
    card = Scorecard(entries=(_passing(), _unrun("T3 FEA")))
    steps = next_steps(card)
    assert [s.tool for s in steps] == ["run_fea_validation"]
    assert card.status is not CheckStatus.PASS


def test_the_precedence_is_fixed_and_identical_cards_give_identical_steps():
    card = Scorecard(entries=(
        _unrun("bolt bearing", "element_params.load"), _unrun("T0 geometry"),
        _failing("weld throat", value=None), _failing("upright bending", value=7.4),
        _unrun("plate yield", "element_params.load", "material.allowable"),
    ))  # fmt: skip
    steps = next_steps(card, remedies=("add `manufacturing` to the document",))
    validate = "run_validation"
    assert [s.tool for s in steps] == [validate, validate, validate, "build_part", validate,
                                       validate]  # fmt: skip
    assert steps[0].reason.startswith("the call was refused: add `manufacturing`")
    assert dict(steps[2].arguments) == {"change": "increase element_params.thickness"}
    assert dict(steps[4].arguments) == {"declare": "element_params.load"}
    assert "bolt bearing, plate yield" in steps[4].reason
    assert next_steps(card, remedies=("add `manufacturing` to the document",)) == steps


def test_nothing_holding_it_back_exports_and_the_list_is_never_empty():
    (step,) = next_steps(Scorecard(entries=(_passing(),)))
    assert (step.tool, dict(step.arguments)) == ("export_artifact", {"format": "evidence_bundle"})
    assert step.reason.startswith("every check has a verdict")
    (draft,) = next_steps(Scorecard(entries=(_passing(), _unrun("constraint max_mass"))))
    assert draft.tool == "export_artifact" and "as a draft" in draft.reason
    assert next_steps(Scorecard())  # an empty card still has a step


def test_every_tool_a_step_can_name_is_in_the_published_catalog():
    """Rename or remove a tool, and this fails until no rule names the old one."""
    from anvilate.mcp import _EXPORT_FORMATS, tool_catalog

    published = {tool.name for tool in tool_catalog()}
    assert set(NEXT_STEP_TOOLS) <= published, set(NEXT_STEP_TOOLS) - published
    assert "evidence_bundle" in _EXPORT_FORMATS
    import anvilate.journey as journey

    assert set(journey._TIER_TOOLS.values()) <= set(NEXT_STEP_TOOLS)


def test_run_validation_returns_next_and_it_validates_against_its_contract():
    from anvilate.mcp import _run_validation
    from anvilate.spec import load_spec_yaml

    spec = load_spec_yaml((_EXAMPLES / "nema23_bracket.spec.yaml").read_text())
    result = _run_validation({"spec": spec.model_dump(mode="json")})
    steps = NextSteps.model_validate(result["next"]).steps
    assert steps[0].tool == "build_part"  # T0 demanded and not run comes before declarations
    assert any(dict(s.arguments) == {"declare": "element_type"} for s in steps)


def test_a_step_renders_its_call_and_why():
    step = NextStep(tool="run_validation", arguments={"declare": "element_type"}, reason="r")
    assert str(step) == "run_validation(declare=element_type): r"


def test_a_tool_no_step_may_name_is_refused():
    with pytest.raises(RefusalError, match="not one a step may name"):
        next_steps(Scorecard(), tool="delete_everything")
    with pytest.raises(RefusalError, match="Scorecard"):
        next_steps({"entries": []})  # type: ignore[arg-type]


def test_a_single_remedy_string_is_refused_not_read_letter_by_letter():
    with pytest.raises((RefusalError, TypeError, ValueError)):
        next_steps(Scorecard(), remedies="add manufacturing")  # type: ignore[arg-type]
