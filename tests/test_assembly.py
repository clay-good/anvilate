"""Assembly order: an order the parts can go in, or every part that blocks one."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.assembly import AssemblyOrder, InsertionDirection, Part, assembly_order
from anvilate.scorecard import CheckStatus

D = InsertionDirection


def _cell_and_retainer(*, retainer_first: bool) -> AssemblyOrder:
    housing = Part(name="housing", insertion=D.MINUS_Z, occupies=("shell",))
    cell = Part(name="lens cell", insertion=D.MINUS_Z, occupies=("bore",), sweeps=("mouth",))
    retainer = Part(name="retainer", insertion=D.MINUS_Z, occupies=("mouth",))
    parts = (housing, retainer, cell) if retainer_first else (housing, cell, retainer)
    return assembly_order(parts)


def test_a_valid_order_is_reported_as_a_result() -> None:
    order = _cell_and_retainer(retainer_first=False)
    assert order.feasible
    entry = order.entry()
    assert entry.status is CheckStatus.PASS
    assert entry.detail == "a valid order exists: housing -> lens cell -> retainer"


def test_the_order_follows_the_blocking_and_not_the_declaration() -> None:
    # Declared retainer-first, and the cell still has to go in before the retainer that
    # occupies the mouth it passes through.
    assert _cell_and_retainer(retainer_first=True).order == ("housing", "lens cell", "retainer")


def _three_way() -> list[Part]:
    return [
        Part(name="bracket", insertion=D.PLUS_X, occupies=("slot a",), sweeps=("slot b",)),
        Part(name="clip", insertion=D.PLUS_Y, occupies=("slot b",), sweeps=("slot c",)),
        Part(name="cover", insertion=D.PLUS_Z, occupies=("slot c",), sweeps=("slot a",)),
    ]


def test_three_parts_that_each_block_another_fail_naming_all_three() -> None:
    """Task 4.3: no valid order is a finding naming the whole cycle, never a silence."""
    order = assembly_order(_three_way())
    assert order.cycles == (("bracket", "clip", "cover"),)
    assert order.order == ()
    entry = order.entry()
    assert entry.status is CheckStatus.FAIL
    assert "no order exists for bracket, clip, cover" in entry.detail
    assert "bracket sweeps slot b, which clip occupies" in entry.detail
    assert "cover sweeps slot a, which bracket occupies" in entry.detail


def test_rerouting_one_insertion_breaks_the_cycle() -> None:
    """The verdict is computed from the declaration: change a path and it moves."""
    parts = _three_way()
    parts[2] = parts[2].model_copy(update={"sweeps": ()})
    order = assembly_order(parts)
    assert order.feasible
    assert order.order == ("bracket", "clip", "cover")


def test_a_part_with_no_insertion_direction_is_not_evaluated_and_named() -> None:
    """Task 4.5: never treated as insertable from anywhere."""
    parts = [*_three_way()[:2], Part(name="gasket", occupies=("groove",))]
    entry = assembly_order(parts).entry()
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "gasket declares no insertion direction" in entry.detail


def test_two_parts_occupying_one_feature_is_an_interference_no_order_resolves() -> None:
    order = assembly_order(
        [
            Part(name="shim", insertion=D.PLUS_Z, occupies=("seat",)),
            Part(name="washer", insertion=D.PLUS_Z, occupies=("seat",)),
        ]
    )
    assert not order.feasible
    assert "shim and washer both occupy seat" in order.entry().detail


def test_an_ambiguous_declaration_is_refused() -> None:
    with pytest.raises(ValueError, match="two parts share a name"):
        assembly_order([Part(name="pin", insertion=D.PLUS_X), Part(name="pin", insertion=D.PLUS_Y)])
    with pytest.raises(ValidationError, match="names one feature twice"):
        Part(name="pin", insertion=D.PLUS_X, occupies=("bore", "bore"))
    assert str(Part(name="pin", insertion=D.PLUS_X)) == "pin (inserted +x)"
    assert "no insertion direction" in str(Part(name="pin"))
    assert str(_cell_and_retainer(retainer_first=False)).startswith("[PASS] assembly order")
