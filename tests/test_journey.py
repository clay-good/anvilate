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
    assert (step.tool, dict(step.arguments)) == ("export_artifact", {"format": "review_package"})
    assert step.reason.startswith("every check has a verdict")
    (draft,) = next_steps(Scorecard(entries=(_passing(), _unrun("constraint max_mass"))))
    assert draft.tool == "export_artifact" and "as a draft" in draft.reason
    assert dict(draft.arguments) == {"format": "review_package", "draft": "true"}
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


def test_stopping_early_is_visible_in_the_stage_and_its_gaps():
    from anvilate.journey import JOURNEY_STAGES, journey_state

    state = journey_state(Scorecard(entries=(_passing(), _unrun("T3 FEA"))))
    assert state.stage == "screened"
    by = {s.stage: s for s in state.stages}
    assert [s.stage for s in state.stages] == list(JOURNEY_STAGES)
    assert (by["simulated"].state, by["simulated"].gaps) == ("not_reached", ("T3 FEA has not run",))
    assert by["optimized"].state == "not_applicable"
    assert by["review_ready"].state == "not_reached"
    assert "T3 FEA has no verdict" in by["review_ready"].gaps


def test_a_stage_that_does_not_apply_is_passed_over_never_reached():
    from anvilate.journey import journey_state

    state = journey_state(Scorecard(entries=(_passing(),)))
    by = {s.stage: s for s in state.stages}
    assert state.stage == "screened" and by["simulated"].state == "not_applicable"
    unscreened = journey_state(Scorecard(entries=(_unrun("bolt bearing", "element_params.load"),)))
    assert unscreened.stage == "described"
    assert unscreened.stages[1].gaps == ("bolt bearing has no verdict",)
    assert str(unscreened).startswith("journey: described\n  described reached\n  screened not")
    simulated = journey_state(Scorecard(entries=(_passing(), _passing("T3 FEA"))))
    assert simulated.stage == "simulated"


def test_run_validation_states_the_journey():
    from anvilate.journey import JourneyState
    from anvilate.mcp import _run_validation
    from anvilate.spec import load_spec_yaml

    spec = load_spec_yaml((_EXAMPLES / "padeye.spec.yaml").read_text())
    journey = JourneyState.model_validate(
        _run_validation({"spec": spec.model_dump(mode="json")})["journey"]
    )
    assert journey.stage == "screened"


def test_a_combination_is_rechecked_by_building_it_and_exported_as_step():
    card = Scorecard(entries=(_failing("bolt bearing", value=None),))
    (step,) = next_steps(card, tool="build_combination", export_format="step")
    assert step.tool == "build_combination"
    (done,) = next_steps(Scorecard(entries=(_passing(),)), tool="build_combination",
                         export_format="step")  # fmt: skip
    assert (done.tool, dict(done.arguments)) == ("export_artifact", {"format": "step"})
    with pytest.raises(RefusalError, match="export_format"):
        next_steps(card, export_format="pdf")


def test_build_combination_returns_next_and_journey():
    import yaml

    from anvilate.journey import JourneyState
    from anvilate.mcp import _build_combination

    document = yaml.safe_load(
        (_EXAMPLES / "combinations" / "bracket_on_plate.combination.yaml").read_text()
    )
    result = _build_combination({"combination": document})
    steps = NextSteps.model_validate(result["next"]).steps
    assert steps and all(s.tool in NEXT_STEP_TOOLS for s in steps)
    assert JourneyState.model_validate(result["journey"]).stage in ("described", "screened")


def _screened(name: str) -> str:
    from anvilate.mcp import _run_validation
    from anvilate.spec import load_spec_yaml

    spec = load_spec_yaml((_EXAMPLES / name).read_text())
    return _run_validation({"spec": spec.model_dump(mode="json")})["subject"]


def test_a_review_package_is_refused_short_of_every_verdict_unless_a_draft(monkeypatch, tmp_path):
    """Guided design journey 2.1/2.2: the finish line, and a draft that says so everywhere."""
    import json

    from anvilate.mcp import _export_artifact, _InvalidArguments

    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path))
    handle = _screened("nema23_bracket.spec.yaml")  # T0 and T1 have no verdict
    with pytest.raises(_InvalidArguments, match="ask for a draft"):
        _export_artifact({"subject": handle, "format": "review_package"})
    result = _export_artifact({"subject": handle, "format": "review_package", "draft": True})
    assert result["draft"] is True and len(result["files"]) == 3
    names = [Path(f["path"]).name for f in result["files"]]
    assert all(".draft." in n for n in names)
    bundle = json.loads((tmp_path / names[0]).read_text())
    assert bundle["draft"] is True
    dossier = (tmp_path / names[1]).read_text()
    assert dossier.startswith("DRAFT: not review-ready; no verdict for T0 geometry")
    manifest = json.loads((tmp_path / names[2]).read_text())
    assert manifest["draft"] is True and manifest["journey"]["stage"] == "described"


def test_a_review_ready_package_reaches_the_stage_and_records_no_review(monkeypatch, tmp_path):
    """Guided design journey 2.3: the package is not an approval; the dossier still reads
    "not yet reviewed" and the manifest says it records no review."""
    import json

    from anvilate.mcp import _export_artifact

    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path))
    result = _export_artifact({"subject": _screened("padeye.spec.yaml"),
                               "format": "review_package"})  # fmt: skip
    assert result["draft"] is False and result["journey"]["stage"] == "review_ready"
    names = [Path(f["path"]).name for f in result["files"]]
    assert "draft" not in json.loads((tmp_path / names[0]).read_text())
    dossier = (tmp_path / names[1]).read_text()
    assert dossier.startswith("Review-ready for content sha256:")
    assert "not yet reviewed" in dossier and "records no review" in dossier
    manifest = json.loads((tmp_path / names[2]).read_text())
    assert manifest["records_review"] is False
    assert [f["sha256"] for f in manifest["files"]] == [f["sha256"] for f in result["files"][:2]]


def test_draft_marks_only_a_review_package(monkeypatch, tmp_path):
    from anvilate.mcp import _export_artifact, _InvalidArguments

    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path))
    with pytest.raises(_InvalidArguments, match="draft: marks a review_package"):
        _export_artifact({"subject": _screened("padeye.spec.yaml"), "format": "evidence_bundle",
                          "draft": True})  # fmt: skip


def test_a_review_package_bundle_carries_the_screening_disclaimer(monkeypatch, tmp_path):
    import json

    from anvilate.bundle import SCREENING_DISCLAIMER
    from anvilate.mcp import _export_artifact

    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path))
    result = _export_artifact({"subject": _screened("padeye.spec.yaml"),
                               "format": "review_package"})  # fmt: skip
    bundle = json.loads(Path(result["files"][0]["path"]).read_text())
    assert bundle["disclaimer"] == SCREENING_DISCLAIMER


def test_a_changed_design_loses_its_stage_and_names_the_change(monkeypatch, tmp_path):
    """Guided design journey 1.3: a package covers one content digest; change a dimension
    and the next validation falls back from review_ready, naming what moved."""
    from anvilate.mcp import _export_artifact, _run_validation
    from anvilate.spec import load_spec_yaml

    monkeypatch.setenv("ANVILATE_OUT", str(tmp_path))
    spec = load_spec_yaml((_EXAMPLES / "padeye.spec.yaml").read_text()).model_dump(mode="json")
    first = _run_validation({"spec": spec})
    assert first["journey"]["stage"] == "screened"  # nothing written yet
    _export_artifact({"subject": first["subject"], "format": "review_package"})
    again = _run_validation({"spec": spec})
    assert again["journey"]["stage"] == "review_ready"
    thicker = {**spec["element_params"], "thickness": {"magnitude": 22.0, "unit": "mm"}}
    moved = {**spec, "element_params": thicker}
    after = _run_validation({"spec": moved})
    ready = {s["stage"]: s for s in after["journey"]["stages"]}["review_ready"]
    assert after["journey"]["stage"] == "screened" and ready["state"] == "not_reached"
    assert ready["gaps"] == ["the review package was written for earlier content; changed "
                             "since: element_params"]  # fmt: skip


def test_a_draft_package_never_counts_as_written():
    from anvilate.journey import package_standing
    from anvilate.spec import load_spec_yaml

    card = Scorecard(entries=(_passing(),))
    spec = load_spec_yaml((_EXAMPLES / "padeye.spec.yaml").read_text())
    assert package_standing({"draft": True, "content_sha256": "x"}, spec, card) == (False, ())
    assert package_standing("not a manifest", spec, card) == (False, ())
    written, changed = package_standing({"draft": False, "content_sha256": "x",
                                         "spec_fields": {}}, spec, card)  # fmt: skip
    assert not written and "name" in changed
