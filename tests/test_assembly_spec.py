"""An assembly declared in the Design Spec: typed, refused when it names what is not there."""

from __future__ import annotations

import difflib

import pytest

from anvilate.scorecard import CheckStatus
from anvilate.screening import screen_spec
from anvilate.spec import dump_spec_yaml, load_spec_yaml
from anvilate.spec.validate import SpecValidationError

_HOUSING = """
anvilate_spec: "1.17.0"
name: sealed_lens_housing
description: A lens cell in a housing, sealed by a cover and focused afterwards.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}
assembly:
  states:
    - {name: open, installs: [housing, lens cell]}
    - {name: closed, installs: [cover]}
  parts:
    - {name: housing, insertion: "-z", occupies: [housing bore]}
    - {name: lens cell, insertion: "-z", occupies: [cell seat], sweeps: [housing bore]}
    - {name: cover, insertion: "-z", occupies: [top opening]}
  adjustments:
    - {feature: focus screw, performed_in: closed, access: [top opening]}
  inspections:
    - {dimension: cell seat height, method: height gauge, access: [top opening]}
"""


def test_the_assembly_round_trips() -> None:
    spec = load_spec_yaml(_HOUSING)
    again = load_spec_yaml(dump_spec_yaml(spec))
    assert again.assembly == spec.assembly
    assert [state.name for state in again.assembly.states] == ["open", "closed"]


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (
            ("performed_in: closed", "performed_in: painted"),
            "'painted', which the assembly does not define",
        ),
        (
            ("installs: [cover]", "installs: [cover, gasket]"),
            "'gasket', which the assembly does not declare",
        ),
        (("{name: cover, insertion", "{name: housing, insertion"), "more than once"),
    ],
)
def test_an_assembly_naming_what_is_not_there_is_refused(
    change: tuple[str, str], match: str
) -> None:
    before, after = change
    assert before in _HOUSING
    with pytest.raises(SpecValidationError, match=match):
        load_spec_yaml(_HOUSING.replace(before, after, 1))


def test_screening_the_document_finds_the_sealed_away_adjustment() -> None:
    card = screen_spec(load_spec_yaml(_HOUSING))
    found = {entry.name: entry for entry in card.entries}
    focus = found["access: focus screw in closed"]
    assert focus.status is CheckStatus.FAIL and "cover" in focus.detail
    assert found["inspectability"].detail.startswith(
        "1 toleranced dimension examined across 2 states"
    )
    assert found["inspectability: cell seat height"].status is CheckStatus.PASS
    revised = screen_spec(
        load_spec_yaml(_HOUSING.replace("performed_in: closed", "performed_in: open"))
    )
    assert {e.name: e for e in revised.entries}["access: focus screw in open"].status is (
        CheckStatus.PASS
    )


def test_moving_an_operation_to_another_state_is_one_line_in_the_diff() -> None:
    before = dump_spec_yaml(load_spec_yaml(_HOUSING)).splitlines()
    after = dump_spec_yaml(
        load_spec_yaml(_HOUSING.replace("performed_in: closed", "performed_in: open"))
    ).splitlines()
    changed = [
        line
        for line in difflib.unified_diff(before, after, lineterm="", n=0)
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    assert len(changed) == 2 and all("performed_in" in line for line in changed)


def test_a_declared_assembly_reaches_the_assembly_modes_and_its_screens_address_them() -> None:
    """Assembly 3.3: the modes apply on a fact the document states, and nowhere else."""
    from anvilate.failure_modes import coverage, facts_from_spec

    spec = load_spec_yaml(_HOUSING)
    facts = facts_from_spec(spec)
    assert facts["assembly"] is True
    report = coverage(screen_spec(spec), facts)
    by_mode = {entry.mode.id: entry for entry in report.entries}
    assert by_mode["an adjustment sealed away by the part closed over it"].addressed
    assert by_mode["a tolerance nobody can measure on the built article"].addressed
    bare = _HOUSING.split("assembly:")[0]
    assert "assembly" not in facts_from_spec(load_spec_yaml(bare))
