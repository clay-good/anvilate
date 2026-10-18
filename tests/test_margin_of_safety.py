"""Margins of safety: limit and ultimate kept apart, cited factor sets, one governing row."""

from __future__ import annotations

import csv
import io
import zipfile
from math import inf
from xml.etree import ElementTree

import pytest
from pydantic import ValidationError

from anvilate.margin_of_safety import (
    DEFAULT_TIE_TOLERANCE,
    Allowable,
    AllowableBasis,
    AnalysisExclusion,
    BasisRule,
    BodyForce,
    FactorRow,
    FactorSet,
    ForceRole,
    FreeBody,
    LoadCase,
    LoadLevel,
    LoadPath,
    MarginCheck,
    MarginLimit,
    MaterialClass,
    QuantityKind,
    SpecialFactor,
    StackingRule,
    VerificationApproach,
    bundled_factor_sets,
    factor_set,
    margin_table,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus
from anvilate.verification import VerificationMethod

_LIMIT = LoadLevel.LIMIT
_ULT = LoadLevel.ULTIMATE


def _check(**overrides: object) -> MarginCheck:
    fields: dict[str, object] = {
        "item": "bus/bracket-1",
        "subsystem": "bus",
        "failure_mode": "net-section tension",
        "method": "P/A",
        "method_citation": "Bruhn A1.3",
        "quantity": QuantityKind.STRESS,
        "unit": "MPa",
        "material_class": MaterialClass.METALLIC,
        "load_path": LoadPath.REDUNDANT,
        "approach": VerificationApproach.TEST,
        "yield_allowable": Allowable(value=241.0, basis=AllowableBasis.A, source="MMPDS-18"),
        "ultimate_allowable": Allowable(value=290.0, basis=AllowableBasis.A, source="MMPDS-18"),
        "cases": (LoadCase(case="LC1", applied=100.0, level=_LIMIT),),
    }
    fields.update(overrides)
    return MarginCheck(**fields)  # type: ignore[arg-type]


def _rows(report, limit: MarginLimit):
    return [row for row in report.rows if row.limit is limit]


# --- the spec's scenarios -------------------------------------------------------------------


def test_protoflight_metallic_uses_1_25_and_1_4_citing_table_1():
    report = margin_table([_check()], factor_set("nasa-std-5001b-protoflight"))
    (yld,) = _rows(report, MarginLimit.YIELD)
    (ult,) = _rows(report, MarginLimit.ULTIMATE)
    assert yld.factor_of_safety == 1.25 and ult.factor_of_safety == 1.4
    assert "Table 1" in yld.factor_clause and "Table 1" in ult.factor_clause
    # Hand: 241 / (100 x 1.25) - 1 = 0.928; 290 / (100 x 1.4) - 1 = 1.0714
    assert yld.margin == pytest.approx(241 / 125 - 1, rel=1e-12)
    assert ult.margin == pytest.approx(290 / 140 - 1, rel=1e-12)
    assert yld.status is CheckStatus.PASS
    assert report.status is CheckStatus.PASS


def test_an_ultimate_load_is_not_factored_twice():
    check = _check(
        cases=(LoadCase(case="fitting", applied=15.0, level=_ULT),),
        quantity=QuantityKind.FORCE,
        unit="kN",
        yield_allowable=None,
        ultimate_allowable=Allowable(value=18.0, basis=AllowableBasis.A, source="test"),
    )
    report = margin_table([check], factor_set("14-cfr-25"))
    (ult,) = _rows(report, MarginLimit.ULTIMATE)
    assert ult.applied == 15.0 and ult.already_ultimate and ult.factor_of_safety == 1.0
    assert ult.margin == pytest.approx(18 / 15 - 1, rel=1e-12)
    assert "ultimate (not factored again)" in report.to_csv()
    # and the yield row says why there is none: an ultimate load states no limit load
    (yld,) = _rows(report, MarginLimit.YIELD)
    assert yld.status is CheckStatus.NOT_EVALUATED


def test_an_untagged_load_is_refused_naming_it():
    check = _check(cases=(LoadCase(case="LC-imported-7", applied=10.0),))
    with pytest.raises(RefusalError, match="LC-imported-7"):
        margin_table([check], factor_set("14-cfr-25"))


def test_a_fitting_factor_sits_in_its_own_column_and_moves_ms():
    check = _check(special_factors=("fitting",))
    report = margin_table([check], factor_set("14-cfr-25"))
    (ult,) = _rows(report, MarginLimit.ULTIMATE)
    assert ult.factor_of_safety == 1.5
    assert [(s.name, s.value) for s in ult.special] == [("fitting", 1.15)]
    assert ult.margin == pytest.approx(290 / (100 * 1.5 * 1.15) - 1, rel=1e-12)
    # 25.625 is an ultimate-load factor; the yield row carries none
    (yld,) = _rows(report, MarginLimit.YIELD)
    assert yld.special == () and yld.margin == pytest.approx(241 / 100 - 1, rel=1e-12)


def test_part_25_takes_the_highest_special_factor_not_the_product():
    check = _check(special_factors=("fitting", "casting, critical, one static test"))
    (ult,) = _rows(margin_table([check], factor_set("14-cfr-25")), MarginLimit.ULTIMATE)
    assert ult.special_product == 1.5
    assert ult.margin == pytest.approx(290 / (100 * 1.5 * 1.5) - 1, rel=1e-12)


def test_a_multiplying_set_multiplies():
    own = FactorSet(
        name="acme-std-12",
        source="ACME-STD-12 rev C",
        rows=(FactorRow(material_class=None, approach=None, yield_factor=1.1,
                        ultimate_factor=1.5, clause="ACME-STD-12 §3"),),
        special_factors=(SpecialFactor(name="fitting", value=1.15, clause="§4"),
                         SpecialFactor(name="bearing", value=1.2, clause="§5")),
        stacking=StackingRule.MULTIPLY,
        stacking_clause="§6",
    )  # fmt: skip
    (ult,) = _rows(
        margin_table([_check(special_factors=("fitting", "bearing"))], own), MarginLimit.ULTIMATE
    )
    assert ult.special_product == pytest.approx(1.15 * 1.2, rel=1e-12)
    assert ult.factor_set == "acme-std-12" and ult.factor_set_source == "ACME-STD-12 rev C"


def test_a_typical_value_on_single_load_path_structure_is_not_evaluated():
    check = _check(
        load_path=LoadPath.SINGLE,
        ultimate_allowable=Allowable(value=310.0, basis=AllowableBasis.TYPICAL, source="vendor"),
    )
    report = margin_table([check], factor_set("14-cfr-25"))
    (ult,) = _rows(report, MarginLimit.ULTIMATE)
    assert ult.status is CheckStatus.NOT_EVALUATED and ult.margin is None
    assert "A-basis" in ult.reason and "typical" in ult.reason and "25.613(b)(1)" in ult.reason
    assert report.status is CheckStatus.NOT_EVALUATED


def test_redundant_structure_accepts_b_basis():
    check = _check(
        ultimate_allowable=Allowable(value=290.0, basis=AllowableBasis.B, source="MMPDS-18"),
        yield_allowable=Allowable(value=241.0, basis=AllowableBasis.B, source="MMPDS-18"),
    )
    report = margin_table([check], factor_set("14-cfr-25"))
    assert all(row.status is CheckStatus.PASS for row in report.rows)


def test_a_composite_with_no_test_is_refused_and_the_plan_gains_the_test():
    panel = _check(
        item="bus/panel-2",
        material_class=MaterialClass.COMPOSITE,
        approach=VerificationApproach.ANALYSIS_ONLY,
        yield_allowable=None,
    )
    report = margin_table([panel], factor_set("gsfc-std-7000b-static"))
    (ult,) = report.rows
    assert ult.status is CheckStatus.NOT_EVALUATED
    assert ult.reason.startswith("refused:") and "§2.4.1.3" in ult.reason
    (required,) = report.required_tests
    assert "§2.4.1.3" in required.clause
    (test,) = report.verification_items()
    assert test.archetype.method is VerificationMethod.TEST
    assert test.driving_checks == (panel.identity,)
    assert test.status is CheckStatus.NOT_EVALUATED  # planned, never evidence


def test_analysis_only_metallic_uses_the_higher_gevs_factors():
    check = _check(approach=VerificationApproach.ANALYSIS_ONLY)
    report = margin_table([check], factor_set("gsfc-std-7000b-static"))
    (yld,) = _rows(report, MarginLimit.YIELD)
    (ult,) = _rows(report, MarginLimit.ULTIMATE)
    assert (yld.factor_of_safety, ult.factor_of_safety) == (2.0, 2.6)


def test_nasa_5001b_states_no_analysis_only_metallic_factors():
    check = _check(approach=VerificationApproach.ANALYSIS_ONLY)
    report = margin_table([check], factor_set("nasa-std-5001b-protoflight"))
    assert {row.status for row in report.rows} == {CheckStatus.NOT_EVALUATED}
    assert "states no factors for metallic structure qualified by analysis only" in (
        report.rows[0].reason
    )


def test_four_hundred_cases_one_row():
    cases = tuple(
        LoadCase(case=f"LC{i:03d}", applied=50.0 + (i % 97), level=_LIMIT) for i in range(400)
    )
    check = _check(cases=cases)
    report = margin_table([check], factor_set("nasa-std-5001b-protoflight"))
    (ult,) = _rows(report, MarginLimit.ULTIMATE)
    assert ult.cases_evaluated == 400
    # applied peaks at 50 + 96 = 146, first reached at i = 96; then at 193, 290, 387
    assert ult.governing_case == "LC096" and ult.applied == 146.0
    assert ult.ties == ("LC193", "LC290", "LC387")
    assert ult.margin == pytest.approx(290 / (146 * 1.4) - 1, rel=1e-12)


def test_a_case_that_cannot_be_evaluated_is_counted_and_named():
    cases = (
        LoadCase(case="up", applied=100.0, level=_LIMIT),
        LoadCase(case="down", applied=-80.0, level=_LIMIT),
    )
    report = margin_table([_check(cases=cases)], factor_set("14-cfr-25"))
    (ult,) = _rows(report, MarginLimit.ULTIMATE)
    assert ult.cases_evaluated == 1
    assert [u.case for u in ult.unevaluated] == ["down"]
    assert "down" in report.to_csv()


def test_a_tie_within_tolerance_is_listed():
    cases = (
        LoadCase(case="a", applied=100.0, level=_LIMIT),
        LoadCase(case="b", applied=99.9, level=_LIMIT),
        LoadCase(case="c", applied=80.0, level=_LIMIT),
    )
    (ult,) = _rows(
        margin_table([_check(cases=cases)], factor_set("14-cfr-25"), tie_tolerance=0.01),
        MarginLimit.ULTIMATE,
    )
    assert ult.governing_case == "a" and ult.ties == ("b",)


def test_zero_applied_is_an_infinite_margin_not_a_division_error():
    report = margin_table(
        [_check(cases=(LoadCase(case="idle", applied=0.0, level=_LIMIT),))],
        factor_set("14-cfr-25"),
    )
    assert all(row.margin == inf and row.status is CheckStatus.PASS for row in report.rows)
    assert "+inf" in report.section()


def test_a_negative_margin_fails_and_sorts_first_after_the_unknown():
    weak = _check(item="bus/weak", cases=(LoadCase(case="LC", applied=300.0, level=_LIMIT),))
    unknown = _check(
        item="bus/unknown",
        load_path=LoadPath.SINGLE,
        ultimate_allowable=Allowable(value=1.0, basis=AllowableBasis.TYPICAL, source="guess"),
    )
    report = margin_table([_check(), weak, unknown], factor_set("14-cfr-25"))
    assert report.rows[0].status is CheckStatus.NOT_EVALUATED
    margins = [row.margin for row in report.rows if row.margin is not None]
    assert margins == sorted(margins)
    assert report.status is CheckStatus.FAIL


# --- the review artifact --------------------------------------------------------------------


def _product_report():
    checks = [
        _check(),
        _check(item="bus/bracket-2", cases=(LoadCase(case="LC9", applied=180.0, level=_LIMIT),)),
        _check(
            item="payload/mount",
            subsystem="payload",
            cases=(LoadCase(case="LC4", applied=50.0, level=_LIMIT),),
        ),
    ]
    return margin_table(checks, factor_set("nasa-std-5001b-protoflight"))


def test_the_summary_gives_each_subsystems_lowest_margin():
    report = _product_report()
    bus, payload = report.summary
    assert bus.subsystem == "bus" and bus.lowest.check == "bus/bracket-2: net-section tension"
    # yield governs: 241 / (180 x 1.25) - 1 = 0.071 against 290 / (180 x 1.4) - 1 = 0.151
    assert bus.lowest.limit is MarginLimit.YIELD
    assert bus.lowest.margin == pytest.approx(241 / (180 * 1.25) - 1, rel=1e-12)
    assert payload.lowest.margin > bus.lowest.margin
    # the summary is part of what a JSON consumer receives
    assert "summary" in report.model_dump(mode="json")


def test_the_csv_is_every_row_in_report_order():
    report = _product_report()
    rows = list(csv.DictReader(io.StringIO(report.to_csv())))
    assert len(rows) == len(report.rows) == 6
    assert [r["item"] for r in rows] == [row.item for row in report.rows]
    assert float(rows[0]["MS"]) == pytest.approx(report.rows[0].margin, abs=1e-6)
    assert rows[0]["FS clause"].endswith("Table 1")


def test_csv_text_cells_cannot_become_formulas():
    hostile = _check(item="=HYPERLINK(1)")
    rows = list(csv.DictReader(io.StringIO(margin_table([hostile], factor_set("14-cfr-25"))
                                           .to_csv())))  # fmt: skip
    assert all(r["item"] == "'=HYPERLINK(1)" for r in rows)


def _sheets(data: bytes) -> dict[str, list[list[str]]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    out = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        names = [s.get("name") for s in book.iterfind("m:sheets/m:sheet", ns)]
        for i, name in enumerate(names, start=1):
            sheet = ElementTree.fromstring(archive.read(f"xl/worksheets/sheet{i}.xml"))
            out[name] = [
                ["".join(c.itertext()) for c in row.iterfind("m:c", ns)]
                for row in sheet.iterfind("m:sheetData/m:row", ns)
            ]
    return out


def test_the_xlsx_opens_with_summary_then_margins_and_is_reproducible():
    report = _product_report()
    data = report.to_xlsx()
    assert data == report.to_xlsx()
    sheets = _sheets(data)
    assert list(sheets) == ["Summary", "Margins"]
    assert sheets["Summary"][1][0] == "bus"
    assert len(sheets["Margins"]) == 1 + len(report.rows)
    assert float(sheets["Margins"][1][5]) == pytest.approx(report.rows[0].margin, abs=1e-6)


def test_the_report_section_opens_with_the_subsystem_summary():
    text = _product_report().section()
    assert text.index("Lowest margin per subsystem") < text.index("Every margin, ascending")
    assert "NASA-STD-5001B" in text


# --- refusals at the door -------------------------------------------------------------------


def test_bundled_sets_cite_a_clause_on_every_value():
    names = [s.name for s in bundled_factor_sets()]
    assert len(names) == len(set(names)) == 5
    for bundled in bundled_factor_sets():
        for row in bundled.rows:
            assert row.clause.strip()
        for special in bundled.special_factors:
            assert special.clause.startswith("14 CFR 25.6")


def test_an_unknown_set_name_lists_the_known_ones():
    with pytest.raises(RefusalError, match="nasa-std-5001b-protoflight"):
        factor_set("nasa-5001")


def test_an_unknown_special_factor_is_refused():
    with pytest.raises(RefusalError, match="bearing"):
        margin_table([_check(special_factors=("bearing",))], factor_set("14-cfr-25"))


def test_two_checks_with_one_identity_are_refused():
    with pytest.raises(RefusalError, match="declared twice"):
        margin_table([_check(), _check()], factor_set("14-cfr-25"))


@pytest.mark.parametrize("tolerance", [-0.1, float("nan"), inf])
def test_a_tie_tolerance_must_be_finite_and_non_negative(tolerance):
    with pytest.raises(RefusalError, match="tie_tolerance"):
        margin_table([_check()], factor_set("14-cfr-25"), tie_tolerance=tolerance)


def test_one_check_alone_is_refused_as_a_sequence():
    with pytest.raises(ValueError, match="checks"):
        margin_table(_check(), factor_set("14-cfr-25"))  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0.9, float("nan"), inf])
def test_a_factor_below_one_or_not_a_number_is_refused(value):
    with pytest.raises(ValidationError):
        FactorRow(material_class=None, approach=None, yield_factor=None, ultimate_factor=value,
                  clause="x")  # fmt: skip


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), inf])
def test_an_allowable_must_be_a_positive_finite_value(value):
    with pytest.raises(ValidationError):
        Allowable(value=value, basis=AllowableBasis.A, source="x")


@pytest.mark.parametrize("value", [float("nan"), inf, -inf])
def test_an_applied_load_that_is_no_number_is_refused(value):
    with pytest.raises(ValidationError):
        LoadCase(case="LC", applied=value, level=_LIMIT)


def test_a_set_cannot_both_exclude_and_factor_one_class():
    with pytest.raises(ValidationError, match="excludes"):
        FactorSet(
            name="bad",
            source="x",
            rows=(FactorRow(material_class=MaterialClass.COMPOSITE,
                            approach=VerificationApproach.ANALYSIS_ONLY, yield_factor=None,
                            ultimate_factor=2.0, clause="x"),),
            exclusions=(AnalysisExclusion(material_class=MaterialClass.COMPOSITE,
                                          required_test="t", clause="x"),),
        )  # fmt: skip


def test_two_special_factors_need_a_stacking_clause():
    with pytest.raises(ValidationError, match="stack"):
        FactorSet(
            name="bad",
            source="x",
            rows=(FactorRow(material_class=None, approach=None, yield_factor=None,
                            ultimate_factor=1.5, clause="x"),),
            special_factors=(SpecialFactor(name="a", value=1.1, clause="x"),
                             SpecialFactor(name="b", value=1.2, clause="x")),
        )  # fmt: skip


def test_a_set_states_one_row_per_class_and_approach():
    row = FactorRow(material_class=None, approach=None, yield_factor=None, ultimate_factor=1.5,
                    clause="x")  # fmt: skip
    with pytest.raises(ValidationError, match="twice"):
        FactorSet(name="bad", source="x", rows=(row, row))


def test_a_basis_rule_accepts_something():
    with pytest.raises(ValidationError):
        BasisRule(load_path=LoadPath.SINGLE, accepted=(), clause="x")


def test_a_model_copy_cannot_make_a_row_pass_a_negative_margin():
    (row, *_) = margin_table(
        [_check(cases=(LoadCase(case="LC", applied=500.0, level=_LIMIT),))],
        factor_set("14-cfr-25"),
    ).rows
    assert row.status is CheckStatus.FAIL
    with pytest.raises(ValidationError):
        row.model_copy(update={"status": CheckStatus.PASS})


def test_the_default_tie_tolerance_is_stated_in_the_section():
    report = margin_table([_check()], factor_set("14-cfr-25"))
    assert report.tie_tolerance == DEFAULT_TIE_TOLERANCE
    assert f"{DEFAULT_TIE_TOLERANCE:g}" in report.section()


def test_the_docs_page_prints_the_margins_it_argues_from(capsys):
    """docs/margin-of-safety.md quotes +0.03 and +0.73; run its block and hold it to them."""
    import re
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "margin-of-safety.md").read_text()
    (block,) = re.findall(r"```python\n(.*?)```", page, re.S)
    exec(compile(block, "margin-of-safety.md", "exec"), {})
    printed = capsys.readouterr().out
    assert "(ultimate): MS +0.03 at crash 9g" in printed
    assert "(yield): MS +0.73 at hard landing" in printed
    for quoted in ("MS +0.03", "+0.15", "reads +0.73", "476 / (400 × 1.0 × 1.15) − 1"):
        assert quoted in page


# --- free bodies (calculation-report delta) -------------------------------------------------


def _fitting_body(*, bolt_b: float = 6.0) -> FreeBody:
    """A 100 x 40 fitting: 12 kN down at x = 50, two bolts at x = 10 and x = 90."""
    return FreeBody(
        case="LC1",
        outline=((0.0, 0.0), (100.0, 0.0), (100.0, 40.0), (0.0, 40.0)),
        length_unit="mm",
        force_unit="kN",
        forces=(
            BodyForce(name="P", role=ForceRole.APPLIED, x=50.0, y=40.0, fx=0.0, fy=-12.0),
            BodyForce(name="bolt A", role=ForceRole.REACTION, x=10.0, y=0.0, fx=0.0, fy=6.0),
            BodyForce(name="bolt B", role=ForceRole.REACTION, x=90.0, y=0.0, fx=0.0, fy=bolt_b),
        ),
    )


def test_a_reviewer_checks_equilibrium_first():
    body = _fitting_body()
    assert body.residual == (0.0, 0.0, 0.0) and body.balanced and body.finding() is None
    report = margin_table([_check(free_bodies=(body,))], factor_set("14-cfr-25"))
    for row in report.rows:
        assert row.free_body == body and row.finding is None
    assert "in equilibrium within 0.01" in report.to_csv()


def test_an_unbalanced_free_body_is_a_finding_on_its_row():
    body = _fitting_body(bolt_b=5.0)
    # ΣFy = -12 + 6 + 5 = -1; ΣM = 50(-12) + 10(6) + 90(5) = -90 kN·mm
    fx, fy, m = body.residual
    assert (fx, fy) == (0.0, -1.0) and m == pytest.approx(-90.0, rel=1e-12)
    report = margin_table([_check(free_bodies=(body,))], factor_set("14-cfr-25"))
    for row in report.rows:
        assert "out of equilibrium" in row.finding and "ΣM = -90" in row.finding
        assert row.status is CheckStatus.PASS  # a finding, not a verdict change
    assert "finding: the free body for 'LC1'" in report.section()


def test_a_residual_inside_the_tolerance_is_balanced():
    # 0.1 kN of 12 is 0.83%, inside 1%; the moment 9 kN·mm against 12 x 107.7 = 1,292 is 0.7%
    assert _fitting_body(bolt_b=5.9).balanced
    assert not _fitting_body(bolt_b=5.8).balanced


def test_only_the_governing_cases_free_body_is_carried():
    cases = (
        LoadCase(case="LC1", applied=100.0, level=_LIMIT),
        LoadCase(case="LC2", applied=150.0, level=_LIMIT),
    )
    report = margin_table(
        [_check(cases=cases, free_bodies=(_fitting_body(bolt_b=5.0),))], factor_set("14-cfr-25")
    )
    for row in report.rows:
        assert row.governing_case == "LC2" and row.free_body is None and row.finding is None


def test_a_free_body_backs_one_of_the_checks_own_cases():
    stray = _fitting_body().model_copy(update={"case": "LC99"})
    with pytest.raises(ValidationError, match="LC99"):
        _check(free_bodies=(stray,))


def test_a_free_body_needs_an_outline_and_an_applied_load():
    body = _fitting_body()
    with pytest.raises(ValidationError, match="outline"):
        body.model_copy(update={"outline": ((0.0, 0.0), (1.0, 0.0))})
    with pytest.raises(ValidationError, match="applied"):
        body.model_copy(update={"forces": body.forces[1:]})
    with pytest.raises(ValidationError, match="tolerance"):
        body.model_copy(update={"tolerance": 0.0})


@pytest.mark.parametrize("value", [float("nan"), inf])
def test_a_force_that_is_no_number_is_refused(value):
    with pytest.raises(ValidationError):
        BodyForce(name="P", role=ForceRole.APPLIED, x=0.0, y=0.0, fx=value, fy=0.0)


def test_the_free_body_renders_and_rasterizes():
    from anvilate.raster import svg_to_png

    for body in (_fitting_body(), _fitting_body(bolt_b=5.0)):
        svg = body.svg()
        root = ElementTree.fromstring(svg)
        assert root.get("aria-label") == "free body LC1"
        assert svg.count(b'stroke-dasharray="6 4"') == 2  # the two reactions
        assert svg_to_png(svg).startswith(b"\x89PNG")
    with pytest.raises(RefusalError, match="width_px"):
        _fitting_body().svg(width_px=10)


def test_every_label_on_the_free_body_stays_on_the_page():
    """A label beside a right-hand reaction ran off the page until it read leftward."""
    import re

    svg = _fitting_body(bolt_b=5.0).svg(width_px=480)
    root = ElementTree.fromstring(svg)
    width, height = float(root.get("width")), float(root.get("height"))
    for path in root.iter("{http://www.w3.org/2000/svg}path"):
        numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", path.get("d"))]
        xs, ys = numbers[0::2], numbers[1::2]
        assert all(0 <= x <= width for x in xs) and all(0 <= y <= height for y in ys)
