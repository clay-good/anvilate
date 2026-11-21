"""Characteristic accountability: numbered once, kept across revisions, marks carried.

The spec's scenario: revision B of a plate adds a hole; every characteristic from
revision A keeps its number, and the new hole's take the next unused numbers.
"""

from __future__ import annotations

import csv
import io
import zipfile

import pytest

from anvilate.callouts import CalloutSet, HeatTreatment
from anvilate.characteristics import (
    ACCOUNTABILITY_COLUMNS,
    CONTROL_PLAN_COLUMNS,
    CharacteristicKind,
    CharacteristicRegister,
    SpecialClass,
    SpecialMark,
    characteristics_of,
    control_plan_seed,
    number_characteristics,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.spec import (
    AcceptanceCriteria,
    DesignSpec,
    GeometricCharacteristic,
    GeometricTolerance,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Provenanced,
    ToleranceDimension,
    ValidationTier,
)
from anvilate.tolerance import FitTolerance, SymmetricTolerance
from anvilate.units import Quantity, UnitSystem


def _dim(tag: str, nominal: str, plus_minus: str = "0.1 mm") -> ToleranceDimension:
    band = SymmetricTolerance(plus_minus=Quantity.parse(plus_minus))
    return ToleranceDimension(tag=tag, nominal=Quantity.parse(nominal), tolerance=band)


def _position(feature: str) -> GeometricTolerance:
    return GeometricTolerance(characteristic=GeometricCharacteristic.POSITION, diametral=True,
                              tolerance=Quantity.parse("0.2 mm"), feature=feature,
                              datums=["A", "B"])  # fmt: skip


def _plate(dimensions, frames) -> DesignSpec:
    return DesignSpec(
        name="plate", description="plate", units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="AA-6061-T6"),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        dimensions=dimensions, geometric_tolerances=frames,
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T0_GEOMETRY]),
    )  # fmt: skip


REV_A = _plate([_dim("width", "120 mm"), _dim("hole_1", "8.5 mm", "0.05 mm")],
               [_position("hole_1")])  # fmt: skip
REV_B = _plate([_dim("width", "120 mm", "0.2 mm"), _dim("hole_1", "8.5 mm", "0.05 mm"),
                _dim("hole_2", "6.6 mm")], [_position("hole_1"), _position("hole_2")])  # fmt: skip


def test_a_revision_adding_a_hole_keeps_every_number_and_takes_the_next():
    a = number_characteristics(characteristics_of(REV_A), part="P-100", revision="A")
    assert [(r.number, r.characteristic.description) for r in a.rows] == [
        (1, "size of width"),
        (2, "size of hole_1"),
        (3, "position of hole_1"),
    ]
    b = number_characteristics(characteristics_of(REV_B), part="P-100", revision="B",
                               previous=a.numbering)  # fmt: skip
    numbered = {r.characteristic.description: r.number for r in b.rows}
    assert numbered == {"size of width": 1, "size of hole_1": 2, "position of hole_1": 3,
                        "size of hole_2": 4, "position of hole_2": 5}  # fmt: skip
    assert b.added == (4, 5) and b.retired == ()


def test_a_revised_tolerance_is_the_same_characteristic():
    a = characteristics_of(REV_A)[0]
    b = characteristics_of(REV_B)[0]
    assert a.id == b.id and (a.tolerance, b.tolerance) == ("119.9 to 120.1 mm", "119.8 to 120.2 mm")


def test_a_removed_characteristic_is_retired_and_its_number_never_reused():
    a = number_characteristics(characteristics_of(REV_B), part="P-100", revision="B")
    shrunk = _plate([_dim("width", "120 mm")], [])
    c = number_characteristics(characteristics_of(shrunk), part="P-100", revision="C",
                               previous=a.numbering)  # fmt: skip
    assert c.retired == (2, 3, 4, 5)
    grown = _plate([_dim("width", "120 mm"), _dim("slot", "10 mm")], [])
    d = number_characteristics(characteristics_of(grown), part="P-100", revision="D",
                               previous=c.numbering)  # fmt: skip
    assert [r.number for r in d.rows] == [1, 6]


def test_the_register_round_trips_as_json():
    a = number_characteristics(characteristics_of(REV_A), part="P-100", revision="A")
    saved = CharacteristicRegister.model_validate_json(a.numbering.model_dump_json())
    b = number_characteristics(characteristics_of(REV_B), part="P-100", revision="B",
                               previous=saved)  # fmt: skip
    assert b.added == (4, 5)
    with pytest.raises(TypeError):
        a.numbering.numbers["x"] = 9  # type: ignore[index]


def test_a_marked_bore_carries_its_mark_and_an_unmarked_one_does_not():
    mark = SpecialMark(kind=CharacteristicKind.GEOMETRIC_TOLERANCE, where="hole_1",
                       detail="position", special=SpecialClass.CRITICAL, symbol="◆",
                       reason="brake caliper mounting, customer drawing note 4")  # fmt: skip
    rows = number_characteristics(characteristics_of(REV_B, marks=[mark]), part="P",
                                  revision="B").rows  # fmt: skip
    special = {r.characteristic.description: r.characteristic.special for r in rows}
    assert special["position of hole_1"] is SpecialClass.CRITICAL
    assert [d for d, s in special.items() if s is not None] == ["position of hole_1"]


def test_a_mark_matching_nothing_or_two_is_refused():
    nowhere = SpecialMark(kind=CharacteristicKind.DIMENSION, where="hole_9",
                          special=SpecialClass.SIGNIFICANT, symbol="SC", reason="r")  # fmt: skip
    with pytest.raises(RefusalError, match="matches no characteristic"):
        characteristics_of(REV_A, marks=[nowhere])
    spec = _plate([], [_position("hole_1"),
                       GeometricTolerance(characteristic=GeometricCharacteristic.PERPENDICULARITY,
                                          tolerance=Quantity.parse("0.1 mm"), feature="hole_1",
                                          datums=["A"])])  # fmt: skip
    vague = SpecialMark(kind=CharacteristicKind.GEOMETRIC_TOLERANCE, where="hole_1",
                        special=SpecialClass.SIGNIFICANT, symbol="SC", reason="r")  # fmt: skip
    with pytest.raises(RefusalError, match="matches 2"):
        characteristics_of(spec, marks=[vague])
    with pytest.raises(RefusalError, match="marked twice"):
        characteristics_of(REV_A, marks=[nowhere.model_copy(update={"where": "width"})] * 2)


def test_notes_and_marked_properties_are_characteristics_too():
    treated = HeatTreatment(scope="hole_1", specification="AMS 2759/1", condition="T6",
                            hardness="40-45 HRC")  # fmt: skip
    callouts = CalloutSet(callouts=(treated,))
    yield_mark = SpecialMark(kind=CharacteristicKind.PROPERTY, where="yield strength",
                             special=SpecialClass.SIGNIFICANT, symbol="SC",
                             reason="the lug's bearing check rests on it")  # fmt: skip
    found = characteristics_of(REV_A, callouts=callouts, marks=[yield_mark])
    assert [c.kind for c in found][-2:] == [CharacteristicKind.NOTE, CharacteristicKind.PROPERTY]
    assert found[-2].id == callouts.callouts[0].characteristic_id
    assert found[-1].description == "yield strength of AA-6061-T6"


def test_a_fit_reports_its_band():
    spec = _plate([ToleranceDimension(tag="bore", nominal=Quantity.parse("35 mm"),
                                      tolerance=FitTolerance(designation="H7"))], [])  # fmt: skip
    (bore,) = characteristics_of(spec)
    assert bore.nominal == "35 mm" and bore.tolerance == "35 to 35.025 mm"


def test_the_table_has_an_empty_measured_column_in_csv_and_xlsx():
    mark = SpecialMark(kind=CharacteristicKind.DIMENSION, where="width",
                       special=SpecialClass.SIGNIFICANT, symbol="=SC", reason="fit")  # fmt: skip
    table = number_characteristics(characteristics_of(REV_A, marks=[mark]), part="P",
                                   revision="A")  # fmt: skip
    rows = list(csv.reader(io.StringIO(table.to_csv())))
    assert tuple(rows[0]) == ACCOUNTABILITY_COLUMNS
    assert rows[1] == ["1", "dimension", "size of width", "120 mm", "119.9 to 120.1 mm",
                       "significant", "'=SC", "fit", ""]  # fmt: skip
    assert all(row[-1] == "" for row in rows[1:])
    with zipfile.ZipFile(io.BytesIO(table.to_xlsx())) as book:
        assert "position of hole_1" in book.read("xl/worksheets/sheet1.xml").decode()


def test_a_register_from_another_part_or_the_same_revision_is_refused():
    a = number_characteristics(characteristics_of(REV_A), part="P-100", revision="A")
    with pytest.raises(RefusalError, match="register of 'P-100'"):
        number_characteristics(characteristics_of(REV_B), part="P-200", revision="B",
                               previous=a.numbering)  # fmt: skip
    with pytest.raises(RefusalError, match="already revision"):
        number_characteristics(characteristics_of(REV_B), part="P-100", revision="A",
                               previous=a.numbering)  # fmt: skip


def test_a_safety_critical_bore_reaches_the_control_plan_seed_with_empty_process_columns():
    mark = SpecialMark(kind=CharacteristicKind.GEOMETRIC_TOLERANCE, where="hole_1",
                       detail="position", special=SpecialClass.CRITICAL, symbol="◆",
                       reason="caliper mounting", check="bolt bearing")  # fmt: skip
    table = number_characteristics(characteristics_of(REV_B, marks=[mark]), part="P",
                                   revision="B")  # fmt: skip
    card = Scorecard(entries=(ScorecardEntry.from_safety_factor(
        "bolt bearing", computed=2.0, required=1.0),))  # fmt: skip
    seed = control_plan_seed(table, scorecard=card)
    rows = list(csv.reader(io.StringIO(seed.to_csv())))
    assert tuple(rows[0]) == CONTROL_PLAN_COLUMNS and len(rows) == 2  # unmarked: no row
    row = dict(zip(CONTROL_PLAN_COLUMNS, rows[1], strict=True))
    assert (row["number"], row["special"], row["symbol"]) == ("4", "critical", "◆")
    assert row["tolerance"] == "⌀0.2 mm to A|B"
    assert row["governing check"] == "bolt bearing (pass)"
    assert "CMM against the datums" in row["suggested measurement method"]
    for plant in ("process step", "machine / device", "reaction plan", "sample size"):
        assert row[plant] == ""
    with zipfile.ZipFile(io.BytesIO(seed.to_xlsx())) as book:
        assert "caliper" not in book.read("xl/worksheets/sheet1.xml").decode()
        assert "position of hole_1" in book.read("xl/worksheets/sheet1.xml").decode()


def test_a_mark_naming_a_check_the_card_lacks_is_refused():
    mark = SpecialMark(kind=CharacteristicKind.DIMENSION, where="width",
                       special=SpecialClass.SIGNIFICANT, symbol="SC", reason="r",
                       check="ghost")  # fmt: skip
    table = number_characteristics(characteristics_of(REV_A, marks=[mark]), part="P",
                                   revision="A")  # fmt: skip
    with pytest.raises(RefusalError, match="ghost"):
        control_plan_seed(table, scorecard=Scorecard(entries=()))
    (row,) = control_plan_seed(table).rows  # without a card the name is carried as written
    assert row[6] == "ghost" and row[7].startswith("variable gauge")


def test_each_rendering_names_what_tells_its_objects_apart():
    mark = SpecialMark(kind=CharacteristicKind.GEOMETRIC_TOLERANCE, where="hole_1",
                       detail="position", special=SpecialClass.CRITICAL, symbol="◆",
                       reason="caliper")  # fmt: skip
    a = number_characteristics(characteristics_of(REV_A), part="P-100", revision="A")
    b = number_characteristics(characteristics_of(REV_B, marks=[mark]), part="P-100",
                               revision="B", previous=a.numbering)  # fmt: skip
    text = str(b)
    assert text.startswith("P-100 rev B: 5 characteristic(s); new [4, 5]; retired []")
    assert "  3. position of hole_1 [critical ◆]" in text and "  4. size of hole_2" in text
    assert str(b.rows[0].characteristic) == "size of width"
    assert str(control_plan_seed(b)) == "control-plan seed: 1 special characteristic(s)"
