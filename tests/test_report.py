"""Calculation report: worked derivations, submittal document, and calc record."""

from __future__ import annotations

import json
import socket
from xml.etree import ElementTree as ET

import pytest
from pydantic import ValidationError

from anvilate.derivation import DerivationAbsence
from anvilate.report import (
    CALC_RECORD_SCHEMA_VERSION,
    SCREENING_DISCLAIMER,
    CalculationReport,
    Derivation,
    ReportSection,
    SymbolValue,
    report_from_record,
)
from anvilate.report.mathml import formula_to_mathml
from anvilate.scorecard import CheckStatus, Direction, RepairHint, ScorecardEntry
from anvilate.spec import Provenanced
from anvilate.units import Quantity, UnitSystem, render

BENDING = Derivation(
    symbolic="σ_b = M · c / I",
    inputs=(
        SymbolValue(
            symbol="M",
            description="bending moment at the section",
            value=Quantity.parse("1500 N*m"),
        ),
        SymbolValue(
            symbol="c", description="distance to the extreme fibre", value=Quantity.parse("50 mm")
        ),
        SymbolValue(
            symbol="I",
            description="second moment of area",
            value=Quantity.parse("2.1e6 mm^4"),
            unit="mm^4",
        ),
    ),
    result=SymbolValue(
        symbol="σ_b", description="bending stress", value=Quantity.parse("35.7 MPa")
    ),
    citation="Shigley, Mechanical Engineering Design, 10th ed., Eq. 3-24",
)


def _report() -> CalculationReport:
    return CalculationReport(
        title="Conveyor bracket screening",
        project="Line 4 conveyor",
        date="2026-07-27",
        unit_system=UnitSystem.SI,
        standards=("AISC 360-22",),
        assumptions=(Provenanced.stated("Static load; no impact factor applied."),),
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "bending yield", computed=1.85, required=1.5
                ),
                derivation=BENDING,
            ),
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "tip deflection", computed=1.05, required=1.5
                ),
                inputs=(
                    SymbolValue(
                        symbol="δ", description="tip deflection", value=Quantity.parse("3.2 mm")
                    ),
                ),
            ),
        ),
    )


# -- derivations -----------------------------------------------------------


def test_derivation_shows_formula_substitution_and_result():
    symbolic, substituted, result = BENDING.lines(system=UnitSystem.SI)
    assert symbolic == "σ_b = M · c / I"
    # Every right-hand symbol becomes a value carrying its unit; the left-hand
    # symbol stays, because the reader is looking for what the formula produces.
    assert substituted == "σ_b = 1500000.00 N·mm · 50.00 mm / 2100000.00 mm⁴"
    assert result == "σ_b = 35.7 MPa"
    # And the substituted line EVALUATES to the result it is printed above. It did not
    # before: the moment rendered in N·m beside a second moment in mm⁴, so the line a
    # reviewer is meant to check by hand came out a thousandfold short of its own answer.
    assert 1500000.00 * 50.00 / 2100000.00 == pytest.approx(35.7, abs=0.05)


def test_substituted_values_always_carry_a_unit():
    substituted = BENDING.substituted(system=UnitSystem.SI)
    for value in ("1500000.00", "50.00", "2100000.00"):
        position = substituted.index(value) + len(value)
        assert substituted[position] == " ", f"{value} rendered without a unit"


def test_substitution_respects_symbol_boundaries():
    # "c" must not be substituted inside "C_d", and a substituted value must never
    # itself be rescanned (the "N" in a rendered force is not the symbol N).
    derivation = Derivation(
        symbolic="F = c · C_d · N",
        inputs=(
            SymbolValue(symbol="c", description="chord", value=2.0),
            SymbolValue(symbol="C_d", description="drag coefficient", value=0.8),
            SymbolValue(symbol="N", description="fin count", value=3.0),
        ),
        result=SymbolValue(symbol="F", description="force", value=Quantity.parse("10 N")),
        citation="user-supplied",
    )
    assert derivation.substituted() == "F = 2 · 0.8 · 3"


def test_undeclared_symbol_is_reported_not_silently_dropped():
    derivation = Derivation(
        symbolic="σ = N / A",
        inputs=(SymbolValue(symbol="N", description="axial load", value=Quantity.parse("1 kN")),),
        result=SymbolValue(symbol="σ", description="axial stress", value=Quantity.parse("1 MPa")),
        citation="Shigley, Eq. 3-1",
    )
    assert derivation.unresolved_symbols() == ("A",)
    # A derivation that cannot be fully substituted is not rendered as worked.
    assert not ReportSection(
        entry=ScorecardEntry.from_safety_factor("axial", computed=2.0, required=1.5),
        derivation=derivation,
    ).is_worked


def test_glossary_defines_every_symbol_including_the_result():
    glossary = BENDING.glossary(system=UnitSystem.SI)
    assert [row[0] for row in glossary] == ["M", "c", "I", "σ_b"]
    # No symbol is left bare: each carries a plain-language meaning and a value.
    assert all(description and value for _, description, value in glossary)


def test_derivation_renders_in_the_projects_unit_system():
    # The spec's US scenario: a bearing-stress derivation reads in kip and inches
    # and resolves to ksi, from the same quantities an SI project renders in
    # kN/mm/MPa.
    bearing = Derivation(
        symbolic="σ_p = P / (d · t)",
        inputs=(
            SymbolValue(symbol="P", description="bolt bearing load", value=Quantity.parse("40 kN")),
            SymbolValue(symbol="d", description="bolt diameter", value=Quantity.parse("20 mm")),
            SymbolValue(symbol="t", description="plate thickness", value=Quantity.parse("12 mm")),
        ),
        result=SymbolValue(
            symbol="σ_p", description="bearing stress", value=Quantity.parse("166.7 MPa")
        ),
        citation="AISC 360-22 J3.10",
    )
    us = bearing.substituted(system=UnitSystem.US)
    si = bearing.substituted(system=UnitSystem.SI)
    assert "kip" in us and "in" in us and "ksi" not in us  # inputs only on the RHS
    assert "ksi" in bearing.lines(system=UnitSystem.US)[2]
    assert "kN" in si and "mm" in si
    assert us != si


def test_symbol_can_pin_its_own_display_unit():
    # Dimensions the unit system has no convention for (a moment, a second moment
    # of area) keep their authored unit, and an author can pin any symbol's unit
    # explicitly — the report never silently converts to something it guessed.
    moment = SymbolValue(symbol="M", description="bending moment", value=Quantity.parse("1500 N*m"))
    # A moment now follows the project's unit system like everything else — N·mm in SI,
    # kip·in in US — so a US derivation no longer mixes systems inside one line.
    assert moment.rendered(system=UnitSystem.SI) == "1500000.00 N·mm"
    assert moment.rendered(system=UnitSystem.US) == "13.28 kip·in"
    pinned = SymbolValue(
        symbol="M", description="bending moment", value=Quantity.parse("1500 N*m"), unit="kip*in"
    )
    # 1500 N·m is 13.28 kip·in, and the compound label reads force-first the way every
    # engineering document writes it — Pint's own alphabetical "in·kip" is correct and
    # unreadable.
    assert pinned.rendered(system=UnitSystem.SI) == "13.28 kip·in"


# -- document --------------------------------------------------------------


def test_report_carries_the_basis_of_design():
    text = _report().to_text()
    for expected in (
        "Conveyor bracket screening",
        "Line 4 conveyor",
        "AISC 360-22",
        # The origin tag rides with the assumption; "(user-supplied)" used to be prose in
        # the sentence, which a reviewer could not distinguish from a library default.
        "Static load; no impact factor applied. [engineer stated]",
        "Shigley, Mechanical Engineering Design, 10th ed., Eq. 3-24",
    ):
        assert expected in text


def test_report_identifies_the_governing_check():
    report = _report()
    governing = report.governing()
    # Deflection runs at 1.05 against a required 1.5 — the tightest utilization.
    assert governing is not None and governing.name == "tip deflection"
    assert "governing check: tip deflection" in report.to_text()
    assert report.status is CheckStatus.FAIL


def test_governing_check_is_the_tightest_not_merely_the_lowest_factor():
    report = CalculationReport(
        title="t",
        sections=(
            # A larger factor can still be the governing check when its
            # requirement is higher: 3.0 against 4.0 is tighter than 2.0/2.5.
            ReportSection(
                entry=ScorecardEntry.from_safety_factor("rigging", computed=3.0, required=4.0)
            ),
            ReportSection(
                entry=ScorecardEntry.from_safety_factor("bracket", computed=2.0, required=2.5)
            ),
        ),
    )
    assert report.governing().name == "rigging"


def test_report_renders_over_margin_and_repair_hint():
    report = CalculationReport(
        title="Over-engineered bracket",
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "bending", computed=8.7, required=2.0, upper=3.0
                )
            ),
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "bolt bearing",
                    computed=0.9,
                    required=1.5,
                    repair_hint=RepairHint.solved(
                        "bolt_diameter", direction=Direction.INCREASE, value=16.0, unit="mm"
                    ),
                )
            ),
        ),
    )
    text = report.to_text()
    assert "OVER MARGIN  bending" in text
    assert "over-engineered" in text  # the band excess is surfaced, not hidden
    assert "repair: increase bolt_diameter to 16 mm" in text
    # A failing check keeps the card blocked; over-margin alone would not.
    assert report.status is CheckStatus.FAIL
    html = report.to_html()
    assert "OVER MARGIN" in html
    assert 'class="repair"' in html


def test_report_renders_a_fragility_warning_on_an_annotated_check():
    from anvilate.uncertainty import MarginUncertainty, Sensitivity

    fragile = MarginUncertainty(
        samples=20000,
        seed=1,
        required=1.5,
        mean=1.7,
        std=0.3,
        shortfall_probability=0.21,
        lower=1.3,
        upper=2.2,
        coverage=0.9,
        sensitivities=(Sensitivity(name="load", variance_share=0.87),),
    )
    report = CalculationReport(
        title="Bracket under load scatter",
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "tension", computed=1.7, required=1.5
                ).model_copy(update={"uncertainty": fragile}),
            ),
        ),
    )
    text = report.to_text()
    # A nominal pass that the distribution fails 21% of the time is flagged FRAGILE.
    assert "uncertainty: P(below 1.50) = 21.0% over 20000 samples by monte_carlo — FRAGILE" in text
    # The method and the screening label ride with the number, never a bare probability.
    assert "Screening only — not a certified reliability analysis." in text
    assert report.status is CheckStatus.PASS  # deterministic verdict unchanged
    html = report.to_html()
    assert 'class="uncertainty fragile"' in html
    assert 'class="uncertainty-method"' in html
    assert "by monte_carlo" in html


def test_over_margin_only_report_is_not_blocked():
    report = CalculationReport(
        title="Comfortably clear",
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "bending", computed=8.7, required=2.0, upper=3.0
                )
            ),
        ),
    )
    assert report.status is CheckStatus.OVER_MARGIN
    assert "OVER MARGIN" in report.to_text()


def test_check_without_derivation_falls_back_honestly():
    text = _report().to_text()
    fallback_section = text.split("FAIL  tip deflection")[1].split("Margin summary")[0]
    assert "derivation not rendered" in fallback_section
    # It shows the inputs it has, states the verdict, and invents no formula: the
    # only "=" in the section belongs to the input listing.
    assert "δ = 3.20 mm" in fallback_section
    assert "safety factor 1.05" in fallback_section
    assert fallback_section.count("=") == 1


def test_report_reports_its_derivation_coverage():
    assert _report().derivation_coverage() == (1, 2)


def test_disclaimer_is_always_present():
    report = _report()
    assert SCREENING_DISCLAIMER in report.to_text()
    assert "qualified engineer" in report.to_html()


def test_html_is_self_contained_and_escapes_user_text():
    report = CalculationReport(title="Bracket <script>alert(1)</script>", sections=())
    html = report.to_html()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    # No external assets: an air-gapped reviewer opens the file and sees the report.
    for scheme in ("http://", "https://", "//cdn"):
        assert scheme not in html


def test_margin_summary_states_the_computed_factor_before_the_required_minimum():
    # The single most-read line of the submittal. Swapping the two columns left the whole
    # suite green, so a report could render "1.50 vs 1.85 required" for a check that
    # actually ran 1.85 against a 1.50 minimum — a PASS row whose own numbers say FAIL.
    report = _report()
    text = report.to_text()
    # Bending runs 1.85 against a required 1.50; deflection 1.05 against 1.50.
    assert "PASS           bending yield: 1.85 vs 1.50 required" in text
    assert "FAIL           tip deflection: 1.05 vs 1.50 required" in text
    # The two checks share a requirement but not a factor: an order swap cannot survive
    # both rows, and the row's verdict must agree with its own numbers.
    for line, verdict in (("bending yield", "PASS"), ("tip deflection", "FAIL")):
        row = next(r for r in text.splitlines() if line in r and "required" in r)
        factor, required = row.split(":")[1].split(" vs ")
        computed = float(factor.strip())
        minimum = float(required.replace("required", "").strip())
        assert row.strip().startswith(verdict)
        assert (computed >= minimum) is (verdict == "PASS")

    # The HTML summary table is fed by the same rows and must carry the same order.
    html = report.to_html()
    assert html.index("1.85") < html.index("1.50")


def test_margin_summary_holds_its_fixed_two_decimal_precision():
    # The module promises a report renders byte-identically on every rebuild "so a diff
    # between two reports is an engineering change, never rendering noise". The precision
    # that promise rests on was itself unasserted, so a widening would dirty every
    # historical report diff without failing a test.
    rows = _report()._summary_rows()
    assert rows == (
        ("bending yield", "1.85", "1.50", "PASS"),
        ("tip deflection", "1.05", "1.50", "FAIL"),
    )


def test_rendering_is_byte_identical_across_rebuilds():
    # Two independently constructed reports render identically — nothing inside the
    # document is timestamped or ordered by chance, so a diff is an engineering change.
    assert _report().to_html() == _report().to_html()
    assert _report().to_text() == _report().to_text()


def test_rendering_makes_no_network_calls(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("report rendering attempted a network call")

    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    report = _report()
    assert report.to_html()
    assert report.to_text()
    assert report.to_record()


# -- calc record -----------------------------------------------------------


def test_calc_record_round_trips():
    report = _report()
    record = report.to_record()
    assert record["schema_version"] == CALC_RECORD_SCHEMA_VERSION
    assert report_from_record(record) == report


def test_calc_record_round_trips_the_uncertainty_annotation():
    from anvilate.uncertainty import MarginUncertainty, Sensitivity

    annotated = CalculationReport(
        title="t",
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "tension", computed=1.7, required=1.5
                ).model_copy(
                    update={
                        "uncertainty": MarginUncertainty(
                            samples=5000,
                            seed=2,
                            required=1.5,
                            mean=1.7,
                            std=0.3,
                            shortfall_probability=0.21,
                            lower=1.3,
                            upper=2.2,
                            coverage=0.9,
                            sensitivities=(Sensitivity(name="load", variance_share=0.87),),
                        )
                    }
                ),
            ),
        ),
    )
    restored = report_from_record(annotated.to_record())
    assert restored == annotated
    assert restored.sections[0].entry.is_fragile()


def test_calc_record_carries_full_precision_not_display_precision():
    report = CalculationReport(
        title="t",
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor("bearing", computed=1.234567, required=1.5),
                derivation=Derivation(
                    symbolic="σ = F / A",
                    inputs=(
                        SymbolValue(
                            symbol="F",
                            description="load",
                            value=Quantity(magnitude=1234.56789, unit="N"),
                        ),
                        SymbolValue(
                            symbol="A", description="area", value=Quantity.parse("100 mm^2")
                        ),
                    ),
                    result=SymbolValue(
                        symbol="σ",
                        description="bearing stress",
                        value=Quantity(magnitude=12.3456789, unit="MPa"),
                    ),
                    citation="Shigley, Eq. 3-1",
                ),
            ),
        ),
    )
    record = report.to_record()
    section = record["report"]["sections"][0]
    # The rendered page rounds; the record an external verifier recomputes from
    # keeps every digit.
    assert section["derivation"]["inputs"][0]["value"]["magnitude"] == 1234.56789
    assert section["derivation"]["result"]["value"]["magnitude"] == 12.3456789
    assert section["entry"]["safety_factor"] == 1.234567
    assert "1234.6 N" in report.to_text()


def test_calc_record_rejects_an_unreadable_schema_major():
    record = _report().to_record()
    record["schema_version"] = "99.0"
    with pytest.raises(ValueError, match="not readable by this build"):
        report_from_record(record)


def test_calc_record_requires_a_schema_version():
    with pytest.raises(ValueError, match="no schema_version"):
        report_from_record({"report": {}})


# -- checks that declare their own work ------------------------------------


def test_pack_checks_carry_their_derivation_to_the_report():
    from anvilate.packs.structural import LiftingLug, screen_lifting_lug

    lug = LiftingLug(
        name="padeye",
        width=Quantity.parse("80 mm"),
        hole_diameter=Quantity.parse("25 mm"),
        thickness=Quantity.parse("12 mm"),
        load=Quantity.parse("50 kN"),
        material="ASTM-A36",
    )
    entries = screen_lifting_lug(lug, required_safety_factor=2.0).entries
    # A section built from nothing but the entry renders the check's own work.
    report = CalculationReport(
        title="padeye",
        unit_system=UnitSystem.SI,
        sections=tuple(ReportSection(entry=entry) for entry in entries),
    )
    assert report.derivation_coverage() == (2, 2)
    text = report.to_text()
    assert "σ_p = P / (d · t)" in text
    assert "σ_p = 50.0 kN / (25.00 mm · 12.00 mm)" in text
    assert "σ_p = 166.7 MPa" in text


def test_column_derivation_names_the_regime_that_actually_governed():
    from anvilate.analysis import CrossSection
    from anvilate.packs.structural import ColumnMember, screen_column_member

    section = CrossSection.rectangular(
        width=Quantity.parse("50 mm"), height=Quantity.parse("50 mm")
    )

    def screen(length: str):
        member = ColumnMember(
            name="post",
            section=section,
            length=Quantity.parse(length),
            axial_load=Quantity.parse("40 kN"),
            material="ASTM-A36",
        )
        return screen_column_member(member, required_safety_factor=2.0).entries[0]

    slender = screen("3000 mm")
    # A slender column is on the AISC E3 elastic branch, F_cr = 0.877*F_e: the yield
    # strength is what decides WHICH branch, and does not appear in the branch itself.
    assert "AISC E3 elastic" in slender.name
    assert slender.derivation.symbolic == "F_cr = 0.877 * F_e"
    assert "F_y" not in slender.derivation.substituted()

    stocky = screen("500 mm")
    # A stocky one is on the inelastic branch, and there the yield strength is in the
    # formula twice — as the exponent's numerator and as the multiplier.
    assert "AISC E3 inelastic" in stocky.name
    assert stocky.derivation.symbolic == "F_cr = 0.658 ** (F_y / F_e) * F_y"
    assert any(item.symbol == "F_y" for item in stocky.derivation.inputs)


def test_mathematical_constants_are_not_missing_inputs():
    # π is not a value the caller supplies, so a formula naming it is still fully
    # worked; a superscript exponents the symbol rather than renaming it, and the
    # substituted value is bracketed so the exponent still applies to all of it.
    derivation = Derivation(
        symbolic="σ_cr = π² · E / λ²",
        inputs=(
            SymbolValue(symbol="E", description="elastic modulus", value=Quantity.parse("200 GPa")),
            SymbolValue(symbol="λ", description="slenderness ratio", value=207.846),
        ),
        result=SymbolValue(
            symbol="σ_cr", description="critical stress", value=Quantity.parse("45.7 MPa")
        ),
        citation="Shigley, Eq. 4-43",
    )
    assert derivation.unresolved_symbols() == ()
    assert derivation.substituted() == "σ_cr = π² · 200.0 GPa / (207.846)²"


def test_multi_character_symbol_is_reported_whole_when_undeclared():
    derivation = Derivation(
        symbolic="B_n = 0.85 · f′c · A₁",
        inputs=(
            SymbolValue(symbol="A₁", description="bearing area", value=Quantity.parse("1 mm^2")),
        ),
        result=SymbolValue(
            symbol="B_n", description="bearing strength", value=Quantity.parse("1 N")
        ),
        citation="ACI 318 §22.8.3",
    )
    # The undeclared symbol is named as itself, not split into "f" and "c".
    assert derivation.unresolved_symbols() == ("f′c",)


def test_exponent_brackets_the_substituted_value():
    # d² with d = 16 mm must render as "(16.00 mm)²" — "16.00 mm²" would read as an
    # area, which is a different quantity entirely.
    derivation = Derivation(
        symbolic="A = π · d² / 4",
        inputs=(
            SymbolValue(symbol="d", description="bolt diameter", value=Quantity.parse("16 mm")),
        ),
        result=SymbolValue(
            symbol="A", description="bolt shank area", value=Quantity.parse("201 mm^2")
        ),
        citation="geometry",
    )
    assert derivation.substituted() == "A = π · (16.00 mm)² / 4"


def test_beam_bending_derivation_names_the_load_case_behind_the_moment():
    from anvilate.analysis import CrossSection
    from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member

    member = BeamMember(
        name="joist",
        section=CrossSection.rectangular(
            width=Quantity.parse("100 mm"), height=Quantity.parse("150 mm")
        ),
        length=Quantity.parse("4 m"),
        support=Support.SIMPLY_SUPPORTED,
        load_type=LoadType.DISTRIBUTED,
        load=Quantity.parse("5 kN/m"),
        material="ASTM-A36",
    )
    bending = screen_beam_member(member, required_safety_factor=1.5).entries[0]
    derivation = bending.derivation
    # The flexure formula is the same for every support and load case; the moment
    # is the value that case produced, and it says which case that was.
    assert derivation.symbolic == "σ_b = M · c / I"
    assert derivation.unresolved_symbols() == ()
    moment = next(item for item in derivation.inputs if item.symbol == "M")
    assert "simply_supported" in moment.description
    assert "distributed" in moment.description
    assert derivation.substituted() == "σ_b = 10.00 kN·m · 75.00 mm / 28125000.00 mm⁴"


def test_beam_deflection_derivation_only_where_a_closed_form_exists():
    from anvilate.analysis import CrossSection
    from anvilate.packs.structural import BeamMember, LoadType, Support, screen_beam_member

    section = CrossSection.rectangular(
        width=Quantity.parse("100 mm"), height=Quantity.parse("150 mm")
    )

    def deflection_entry(**overrides):
        fields = {
            "name": "b",
            "section": section,
            "length": Quantity.parse("4 m"),
            "support": Support.SIMPLY_SUPPORTED,
            "load_type": LoadType.DISTRIBUTED,
            "load": Quantity.parse("5 kN/m"),
            "material": "ASTM-A36",
            "deflection_limit": Quantity.parse("20 mm"),
        }
        member = BeamMember(**{**fields, **overrides})
        card = screen_beam_member(member, required_safety_factor=1.5)
        return next(e for e in card.entries if "deflection" in e.name)

    standard = deflection_entry()
    # The standard full-span case states the formula a reviewer can follow.
    assert standard.derivation.symbolic == "δ = 5·w·L⁴/(384·E·I)"
    assert standard.derivation.unresolved_symbols() == ()
    assert "2.96 mm" in standard.derivation.lines(system=UnitSystem.SI)[2]

    # An offset point load has a closed form of its own, and it names the offset — which
    # is why the symbols moved onto the case: the pack's old fixed F/L/E/I set left an `a`
    # standing where a number belongs, and the report refused to show it as worked.
    offset = deflection_entry(
        load_type=LoadType.POINT,
        load=Quantity.parse("10 kN"),
        load_position=Quantity.parse("1 m"),
    )
    assert offset.derivation.symbolic == "δ = F·b·√((L² − b²)³)/(9·√3·L·E·I)"
    assert offset.derivation.unresolved_symbols() == ()

    # A partial patch does not. Its peak is the elastic curve evaluated at a solved
    # position, and the entry says so rather than saying nothing.
    patch = deflection_entry(
        load_type=LoadType.DISTRIBUTED,
        load=Quantity.parse("5 kN/m"),
        loaded_length=Quantity.parse("1.5 m"),
    )
    assert patch.derivation is None
    assert patch.underived.kind is DerivationAbsence.NUMERIC_RESULT
    assert "slope vanishes" in patch.underived.reason


def test_cover_plate_derivation_only_for_the_closed_form_cases():
    from anvilate.packs.industrial import CoverPlate, PlateEdge, screen_cover_plate

    def bending(**overrides):
        fields = {
            "name": "manway",
            "diameter": Quantity.parse("500 mm"),
            "thickness": Quantity.parse("12 mm"),
            "pressure": Quantity.parse("0.4 MPa"),
            "material": "ASTM-A36",
            "edge": PlateEdge.CLAMPED,
        }
        card = screen_cover_plate(CoverPlate(**{**fields, **overrides}), required_safety_factor=1.5)
        return card.entries[0]

    clamped = bending().derivation
    assert clamped.symbolic == "σ = 3·q·R²/(4·t²)"
    assert clamped.substituted() == "σ = 3·0.400 MPa·(250.00 mm)²/(4·(12.00 mm)²)"

    # The simply-supported form carries Poisson's ratio, so it declares it.
    supported = bending(edge=PlateEdge.SIMPLY_SUPPORTED).derivation
    assert "ν" in supported.symbolic
    assert any(item.symbol == "ν" for item in supported.inputs)
    assert supported.unresolved_symbols() == ()

    # A CLAMPED rectangle is a closed form too — two coefficients read out of Roark
    # Table 11.4 — and the pack rendered it as a bare table for as long as the symbols
    # were assembled here from a fixed q/R/t set that only a round cover fits.
    rectangular = bending(
        diameter=None, length=Quantity.parse("600 mm"), width=Quantity.parse("400 mm")
    )
    assert rectangular.derivation.symbolic == "σ = β·q·b²/t²"
    assert rectangular.derivation.unresolved_symbols() == ()
    coefficient = next(item for item in rectangular.derivation.inputs if item.symbol == "β")
    assert "Table 11.4" in coefficient.description

    # A simply-supported rectangle sums a Navier series; there is no one-line formula
    # that is what was computed, so it declares none.
    navier = bending(
        diameter=None,
        length=Quantity.parse("600 mm"),
        width=Quantity.parse("400 mm"),
        edge=PlateEdge.SIMPLY_SUPPORTED,
    )
    assert navier.derivation is None

    # The flatness half is worked wherever the bending half is. It rendered its limit
    # with nothing behind it on every cover, including the ones whose centre deflection
    # is a single line.
    flat = screen_cover_plate(
        CoverPlate(
            name="manway",
            diameter=Quantity.parse("500 mm"),
            thickness=Quantity.parse("12 mm"),
            pressure=Quantity.parse("0.4 MPa"),
            material="ASTM-A36",
            edge=PlateEdge.CLAMPED,
            deflection_limit=Quantity.parse("2 mm"),
        ),
        required_safety_factor=1.5,
    )
    flatness = next(entry for entry in flat.entries if "flatness" in entry.name)
    assert flatness.derivation.symbolic == "w = q·R⁴/(64·D)"
    assert flatness.derivation.unresolved_symbols() == ()


def test_the_calc_record_is_strict_json_even_with_an_infinite_safety_factor():
    # to_record exists so another firm's QA script can re-verify the numbers. Python's json
    # writes Infinity and NaN as bare tokens that are not in the JSON grammar, so a
    # JavaScript, Go, or schema-validating reader rejects the file. It is reachable through
    # an ordinary PASSING check: an EN 1993-1-9 weld range below the cutoff does no damage,
    # so its safety factor is genuinely infinite.
    from anvilate.analysis import weld_fatigue_scorecard

    entry = weld_fatigue_scorecard(
        "weld fatigue",
        applied_cycles=[1.0e6],
        stress_ranges=[Quantity.parse("10 MPa")],
        detail_category=Quantity.parse("90 MPa"),
    )
    assert entry.status is CheckStatus.PASS
    assert entry.safety_factor == float("inf")

    base = _report()
    report = base.model_copy(
        update={"sections": (base.sections[0].model_copy(update={"entry": entry}),)}
    )
    text = json.dumps(report.to_record())
    assert "Infinity" not in text and "NaN" not in text

    # A strict reader (the JSON grammar has no constants beyond true/false/null) round-trips.
    def _reject(token):
        raise AssertionError(f"strict JSON reader rejects the bare token {token}")

    reloaded = json.loads(text, parse_constant=_reject)
    # The non-finite value is spelled as a token, not dropped. Nulling it lost the value:
    # `SymbolValue.value` is `Quantity | float` and `Quantity.magnitude` is `float`, so a
    # nulled record failed this build's own loader — the archived evidence for exactly the
    # strongest-passing checks was unrecoverable.
    assert reloaded["report"]["sections"][0]["entry"]["safety_factor"] == "__nonfinite:inf__"
    assert reloaded["report"]["sections"][0]["entry"]["status"] == "pass"
    assert "inf" in reloaded["report"]["sections"][0]["entry"]["detail"]

    # And it round-trips: the loaded report is the report that was written.
    restored = report_from_record(json.loads(text, parse_constant=_reject))
    assert restored.sections[0].entry.safety_factor == float("inf")
    assert restored.to_text() == report.to_text()

    # A finite record is untouched: full computed precision, not display precision.
    plain = json.loads(json.dumps(_report().to_record()), parse_constant=_reject)
    assert plain["report"]["sections"][0]["entry"]["safety_factor"] == pytest.approx(1.85, abs=0.01)


def test_a_record_carrying_an_infinite_derivation_value_reloads():
    # The nulling this replaced was undetectable on a safety factor alone (declared
    # `float | None`); it only bit on a Derivation, whose `value` has no None member.
    from anvilate.derivation import Derivation, SymbolValue

    derivation = Derivation(
        symbolic="n = N_R / N_E",
        inputs=(
            SymbolValue(symbol="N_R", description="cycles to failure", value=float("inf")),
            SymbolValue(symbol="N_E", description="applied cycles", value=2.0e6),
        ),
        result=SymbolValue(symbol="n", description="fatigue safety factor", value=float("inf")),
        citation="EN 1993-1-9",
    )
    entry = ScorecardEntry.from_safety_factor(
        "weld fatigue", computed=float("inf"), required=1.0
    ).model_copy(update={"derivation": derivation})
    base = _report()
    report = base.model_copy(
        update={"sections": (base.sections[0].model_copy(update={"entry": entry}),)}
    )
    record = json.loads(json.dumps(report.to_record()))
    restored = report_from_record(record)
    assert restored.sections[0].entry.derivation is not None
    assert restored.sections[0].entry.derivation.result.value == float("inf")
    assert restored.to_text() == report.to_text()


def test_the_governing_row_is_marked_by_position_not_by_name():
    # Two checks can share a name in a real submittal — the same detail screened at two
    # locations. Marking the governing row by name bolded both, presenting a PASSING row
    # as the controlling check of a FAILING card.
    failing = ScorecardEntry.from_safety_factor("bolt shear", computed=0.5, required=1.5)
    passing = ScorecardEntry.from_safety_factor("bolt shear", computed=4.0, required=1.5)
    report = CalculationReport(
        title="Duplicate names",
        sections=(ReportSection(entry=failing), ReportSection(entry=passing)),
    )
    assert report.status is CheckStatus.FAIL
    governing_rows = [
        line for line in report.to_html().splitlines() if 'tr class="governing"' in line
    ]
    assert len(governing_rows) == 1
    assert "FAIL" in governing_rows[0] and "0.50" in governing_rows[0]


# --- MathML typesetting -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("formula", "expected"),
    [
        ("σ_b = M · c / I", "<mfrac>"),
        ("σ_vm = √(σ_t² + 3 · τ²)", "<msqrt>"),
        ("F_cr = 0.658 ** (F_y / F_e) * F_y", "<msup>"),
        ("τ = P / (n · π · d² / 4)", "<msup>"),
        ("σ_b = M · c / I", "<msub><mi>σ</mi><mi>b</mi></msub>"),
    ],
)
def test_the_structure_a_reviewer_reads_is_in_the_markup(formula, expected):
    math = formula_to_mathml(formula)
    assert math is not None
    assert expected in math


def test_the_emitted_element_is_well_formed_and_self_contained():
    math = formula_to_mathml("σ_b = M · c / I")
    assert math is not None
    ET.fromstring(math)  # valid XML, or a browser will not render it
    # No script, no stylesheet, no font, no fetch. MathML is laid out by the browser, which
    # is the reason it was chosen over MathJax: the report stays one air-gapped file.
    assert "script" not in math and "http" not in math.replace(
        "http://www.w3.org/1998/Math/MathML", ""
    )


@pytest.mark.parametrize(
    "formula",
    [
        "σ = ∑ F_i / A",  # a symbol outside the grammar
        "a = b = c",  # two equals signs
        "σ = M · / I",  # an operator with nothing to its right
        "σ = (M · c / I",  # unbalanced
        "σ = ",  # an empty side
    ],
)
def test_a_formula_outside_the_grammar_is_declined_not_guessed(formula):
    assert formula_to_mathml(formula) is None


def test_the_round_trip_guard_is_what_stops_a_wrong_rendering(monkeypatch):
    """Attack the guard: make the parse tree write back out as something else.

    The grammar check alone would not catch a parser that builds a *valid* tree of the
    wrong shape — a precedence bug reads `a / b · c` as `a / (b · c)` and emits a
    perfectly well-formed fraction of a formula the check never cited. The round trip is
    the only thing standing between that and a sealed document, so it is asserted to be
    load-bearing rather than assumed to be.
    """
    import anvilate.report.mathml as mathml_module

    assert formula_to_mathml("σ_b = M · c / I") is not None
    monkeypatch.setattr(mathml_module, "_unparse", lambda node: "something else entirely")
    assert formula_to_mathml("σ_b = M · c / I") is None


def test_a_declined_formula_falls_back_to_the_plain_text_line():
    # The report stays readable when the renderer declines, and the fallback carries the
    # derivation's own text. Note the two lines are decided independently: the symbolic
    # line here is outside the grammar, while the substituted line — where ∑F has become a
    # number — typesets normally.
    derivation = Derivation(
        symbolic="σ = ∑F / A",
        inputs=(
            SymbolValue(symbol="∑F", description="summed force", value=Quantity.parse("1 kN")),
            SymbolValue(symbol="A", description="area", value=Quantity.parse("10 mm**2")),
        ),
        result=SymbolValue(symbol="σ", description="stress", value=Quantity.parse("100 MPa")),
        citation="a source",
    )
    section = ReportSection(
        entry=ScorecardEntry.from_safety_factor("odd formula", computed=2.0, required=1.5),
        derivation=derivation,
    )
    assert section.is_worked, "the fallback under test is the renderer's, not the report's"
    html = CalculationReport(
        title="t", project="p", date="2026-08-25", sections=(section,)
    ).to_html()
    assert "<p>σ = ∑F / A</p>" in html


def test_a_unit_stays_with_its_number_across_a_division():
    """The precedence bug the round trip cannot see, pinned.

    A substituted line puts a value beside its unit with no operator. At the same
    precedence as division, "1.00 kN / 10.00 mm²" reads left to right as
    "(1.00 kN / 10.00) · mm²" — a stress drawn as a force over a number, times an area —
    and it writes back out as the identical string, so the round trip passes it. The
    numerator and denominator are asserted here by content, not by the emitted element
    count, because the failing rendering had the right number of elements.
    """
    math = formula_to_mathml("σ = 1.00 kN / 10.00 mm²")
    assert math is not None
    fraction = ET.fromstring(math).find("{http://www.w3.org/1998/Math/MathML}mfrac")
    assert fraction is not None
    numerator, denominator = list(fraction)
    assert "".join(numerator.itertext()) == "1.00kN"
    assert "".join(denominator.itertext()) == "10.00mm2"


def test_the_calculation_report_pages_rendered_block_is_the_reports_own():
    """`docs/calculation-reports.md` shows a rendered check, and nothing opened the page.

    The block is the page's whole claim — that a report shows the formula, the numbers
    put into it, the answer and the clause — so it is compared against the text the
    page's own worked block renders, line for line rather than by spot-checking numbers.
    """
    import re
    from pathlib import Path

    from anvilate.packs.structural import LiftingLug, screen_lifting_lug

    page = (Path(__file__).resolve().parent.parent / "docs" / "calculation-reports.md").read_text()

    lug = LiftingLug(
        name="padeye",
        width=Quantity.parse("80 mm"),
        hole_diameter=Quantity.parse("25 mm"),
        thickness=Quantity.parse("12 mm"),
        load=Quantity.parse("50 kN"),
        material="ASTM-A36",
    )
    card = screen_lifting_lug(lug, required_safety_factor=2.0)
    report = CalculationReport(
        title="Lifting padeye — screening calculations",
        project="Shop crane padeye, 50 kN",
        date="2026-07-27",
        unit_system=UnitSystem.SI,
        standards=("ASME BTH-1 — Design of Below-the-Hook Lifting Devices",),
        assumptions=(Provenanced.stated("Static lift; no impact or side-load factor applied."),),
        sections=tuple(ReportSection(entry=entry) for entry in card.entries),
    )

    shown = re.search(r"```\n(FAIL  padeye pin bearing\n(?:.|\n)*?)```", page)
    assert shown is not None, "the rendered check in docs/calculation-reports.md has moved"
    text = report.to_text()
    start = text.index("FAIL  padeye pin bearing")
    rendered = text[start : text.index("\n\n", start)]
    # Equality, not containment: a page that drops the trailing citation line, or the
    # repair hint, is still a substring of the rendering and is no longer the rendering.
    assert shown.group(1).rstrip("\n") == rendered

    # The unit-system argument the page makes in prose: the substituted line has to
    # evaluate to the result printed under it, which is why moments are in N·mm.
    line = re.search(
        r"`([\d.]+) N·mm · ([\d.]+) mm / ([\d.]+) mm⁴ = ([\d.]+) MPa`",
        page,
    )
    assert line is not None, "the page no longer shows the N·mm substituted line"
    moment, fibre, second_moment, stress = (float(g) for g in line.groups())
    assert moment * fibre / second_moment == pytest.approx(stress, abs=0.05)
    # And the same line in N·m, which is the mistake the sentence beside it describes.
    in_newton_metres = (moment / 1000.0) * fibre / second_moment
    assert stress / in_newton_metres == pytest.approx(1000.0, rel=1e-3)

    # The precision claim: 0.087 ksi displayed as 0.1 ksi is the percentage the page names.
    precision = re.search(
        r"a stress of ([\d.]+) ksi used to print as `([\d.]+) ksi`,\s+a (\d+)% error", page
    )
    assert precision is not None, "the page no longer states the small-value precision error"
    actual, displayed, claimed = precision.groups()
    error = 100.0 * abs(float(displayed) - float(actual)) / float(actual)
    assert error == pytest.approx(float(claimed), abs=0.5)
    # And the widening itself: that stress renders to a figure a reviewer can check
    # against, not to the one-decimal form the sentence describes as the old behavior.
    shown = render(Quantity.parse("0.6 MPa"), unit="ksi", pretty=True)
    assert float(shown.split()[0]) == pytest.approx(float(actual), abs=5e-4)


def test_the_report_declares_its_own_surface_rather_than_inheriting_the_viewers():
    """A sealed document cannot depend on the reviewer's browser theme.

    Found by rendering a report and looking at it: the stylesheet set a text colour and
    no background, so in a dark-mode browser the whole document came out near-black on
    near-black — a blank page to a checker, and green in every test here, because every
    assertion was about the markup. Every colour in the sheet (a failing red, a passing
    green, a grey note) is chosen against paper, so the sheet has to say so.
    """
    import re

    html = _report().to_html()
    style = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    assert style is not None, "the report no longer carries a stylesheet"
    sheet = style.group(1)

    def _declarations(selector: str) -> str:
        rule = re.search(rf"(?m)^{re.escape(selector)} \{{(.*?)\}}", sheet, re.DOTALL)
        return "" if rule is None else rule.group(1)

    root, body = _declarations("html"), _declarations("body")
    assert "color-scheme: light" in root, (
        "the document renders as print: it must declare the scheme, or the browser's "
        "furniture and its own colours disagree"
    )
    # On the root, not merely on the body: the canvas outside a max-width column is the
    # root's, so a background set only on `body` still paints a white page onto whatever
    # the viewer's theme puts behind it.
    assert re.search(r"background:\s*#fff", root), (
        "the stylesheet sets a text colour and no root background, so the page inherits "
        "the viewer's — which is how a dark-mode reviewer gets a blank document"
    )
    # And the text colour it is chosen against is still a dark one, so the pair is a
    # readable document rather than two settings that happen to be present.
    text_colour = re.search(r"color:\s*#([0-9a-f]{3,6})", body)
    assert text_colour is not None, "the body no longer sets a text colour"
    channels = text_colour.group(1)
    if len(channels) == 3:
        channels = "".join(char * 2 for char in channels)
    assert max(int(channels[index : index + 2], 16) for index in (0, 2, 4)) < 0x80


# --- a probability never travels without its method and its label -------------------------


def _annotated_report(**overrides):
    from anvilate.uncertainty import MarginUncertainty, Sensitivity

    fields = {
        "samples": 4096,
        "seed": 7,
        "required": 2.0,
        "mean": 2.4,
        "std": 0.2,
        "shortfall_probability": 0.031,
        "lower": 2.0,
        "upper": 2.8,
        "coverage": 0.9,
        "sensitivities": (Sensitivity(name="load", variance_share=1.0),),
        **overrides,
    }
    return CalculationReport(
        title="Annotated",
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor(
                    "tension", computed=2.4, required=2.0
                ).model_copy(update={"uncertainty": MarginUncertainty(**fields)}),
            ),
        ),
    )


def test_no_rendering_shows_a_probability_without_its_method_and_screening_label():
    """`uncertainty-quantification`'s "Method visible" scenario, held to both renderings.

    The requirement is that an annotation names the sampling method, the sample count and
    the screening label — "never a bare probability presented as a certified reliability
    figure". Both renderings printed the probability and the sample count and dropped the
    other two, while `MarginUncertainty` had carried `method` and `citation` all along with
    nothing consuming either. The sole place a reviewer meets the number is the document
    they sign.
    """
    report = _annotated_report()
    unc = report.sections[0].entry.uncertainty
    assert unc is not None
    for rendering in (report.to_text(), report.to_html()):
        assert "3.1%" in rendering, "the probability is not being rendered at all"
        assert unc.method in rendering
        assert "4096 samples" in rendering
        assert unc.citation in rendering


def test_the_label_a_rendering_shows_is_the_annotations_own():
    """A hardcoded "Monte Carlo, screening only" line passes the test above and becomes a lie
    the moment a second method exists — which is exactly what the requirement anticipates
    when it says FORM/SORM-class methods plug into the same contract. So the values are
    replaced with sentinels no source file contains and the renderings have to show those.

    `method` is a single-valued `Literal` today, so a sentinel cannot be constructed through
    the constructor; `model_construct` is pydantic's documented bypass and is the honest way
    to stand in for the second method that does not exist yet.
    """
    from anvilate.uncertainty import MarginUncertainty

    report = _annotated_report(citation="SENTINEL LABEL TEXT")
    entry = report.sections[0].entry
    annotated = MarginUncertainty.model_construct(
        **{**entry.uncertainty.__dict__, "method": "sentinel_method"}
    )
    report = CalculationReport(
        title=report.title,
        sections=(ReportSection(entry=entry.model_copy(update={"uncertainty": annotated})),),
    )
    for rendering in (report.to_text(), report.to_html()):
        assert "sentinel_method" in rendering
        assert "SENTINEL LABEL TEXT" in rendering
        assert "monte_carlo" not in rendering


def test_the_calc_record_carries_the_method_and_the_label_too():
    """An external verifier reads the record, not the rendering — the requirement's
    "sufficient to re-verify every number without parsing the rendered document"."""
    record = _annotated_report().to_record()
    annotation = record["report"]["sections"][0]["entry"]["uncertainty"]
    assert annotation["method"] == "monte_carlo"
    assert "Screening only" in annotation["citation"]


def test_an_assumption_shows_who_put_it_there():
    """`calculation-report`'s "assumptions and defaults in force (with origin tags)".

    The field was `tuple[str, ...]` while the model's own docstring said "with their
    origin", so an assumption the engineer asserted and one the library supplied rendered
    as the same bullet in the document that gets signed. `Provenanced[str]` was already the
    exact type — value, origin, and a rationale a default cannot omit.
    """
    report = CalculationReport(
        title="Mixed basis",
        assumptions=(
            Provenanced.stated("Static lift; no impact factor."),
            Provenanced.resolved("Yield 250 MPa for ASTM A36."),
            Provenanced.default(
                "Required safety factor 2.0.", rationale="ASME BTH-1 Design Category B"
            ),
        ),
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor("tension", computed=3.0, required=2.0)
            ),
        ),
    )
    for rendering in (report.to_text(), report.to_html()):
        assert "Static lift; no impact factor. [engineer stated]" in rendering
        assert "Yield 250 MPa for ASTM A36. [resolved from bundled data]" in rendering
        # A default shows the reason it was chosen, which `Provenanced` already requires.
        assert (
            "Required safety factor 2.0. [library default: ASME BTH-1 Design Category B]"
            in rendering
        )
    # The three read differently, which is the whole point of the tag.
    assert len(set(report._assumption_lines())) == 3


def test_a_bare_string_assumption_is_refused_rather_than_tagged_with_a_guess():
    """Defaulting an untagged assumption to "engineer stated" would put a claim about
    provenance into a signed document on nobody's authority."""
    with pytest.raises(ValidationError):
        CalculationReport(title="Untagged", assumptions=("no impact factor",))


def test_an_empty_assumptions_list_still_names_the_heading():
    """The tagging must not have reintroduced the vanishing-heading defect: a report whose
    author declared none and one whose author forgot the section were the same document."""
    # Standards are declared so that "none declared" can only have come from the
    # assumptions. The first draft left both empty, and dropping the assumptions filler
    # entirely still passed — the standards heading was answering for it.
    report = CalculationReport(title="Nothing declared", standards=("AISC 360-22",))
    for rendering in (report.to_text(), report.to_html()):
        assert "Assumptions" in rendering
        assert "none declared" in rendering
    assert report._assumption_lines() == ("none declared",)


def test_the_calculation_report_page_states_the_precision_the_record_actually_keeps():
    """`docs/calculation-reports.md` contrasts a displayed figure with a recorded one.

    "the page may show `1234.6 N` while the record holds `1234.56789`" is the whole
    argument for the calc record existing, and both halves of it were prose. Held here
    against the two mechanisms the sentence names: the display rounds, and the record
    carries what was computed.
    """
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "docs" / "calculation-reports.md").read_text()
    claim = re.search(r"`([\d.]+) N` while the record holds `([\d.]+)`", page)
    assert claim is not None, "the record-precision sentence on calculation-reports.md has moved"
    displayed, held = claim.groups()
    assert float(displayed) != float(held), "the sentence only says something if they differ"

    shown = SymbolValue(
        symbol="P", description="pin load", value=Quantity.parse(f"{held} N"), unit="N"
    )
    assert shown.rendered() == f"{displayed} N"

    report = CalculationReport(
        title="Pin bearing",
        project="Record precision",
        date="2026-07-27",
        unit_system=UnitSystem.SI,
        sections=(
            ReportSection(
                entry=ScorecardEntry.from_safety_factor("bearing", computed=1.2, required=1.0),
                inputs=(shown,),
            ),
        ),
    )
    recorded = json.dumps(report.to_record())
    assert held in recorded, "the record is meant to carry the value at full precision"
    assert f'"{displayed}"' not in recorded


def test_a_derivation_with_no_inputs_is_refused():
    """A derivation is the formula *with its values in it*.

    With no inputs, `substituted()` returns the symbolic form unchanged — the
    reconstruction this type exists to replace, rendered under the heading of a worked
    calculation. Nothing this library writes ever built one, which is what let it stand.
    """
    with pytest.raises(ValidationError, match="at least 1 item"):
        Derivation(
            symbolic="σ = M / S",
            inputs=(),
            result=SymbolValue(
                symbol="σ", description="bending stress", value=Quantity.parse("120 MPa")
            ),
            citation="AISC 360-22 §F2",
        )


def test_a_repair_hint_carries_where_its_number_came_from():
    """The packs write a real sentence into `RepairHint.provenance` — "lug thickness inverse
    (σ ∝ 1/t, so SF ∝ t)" — and no rendering showed it.

    It is the difference between a value that solves the check exactly and a direction taken
    from a monotonicity declaration, and this is the document a reviewer signs. A hint with no
    provenance renders exactly as it did, which the second half holds.
    """
    from anvilate.report.document import _repair_source

    class _Section:
        def __init__(self, entry):
            self.entry = entry

    solved = ScorecardEntry.from_safety_factor(
        "lug tension",
        computed=1.0,
        required=2.0,
        repair_hint=RepairHint(
            parameter="thickness",
            direction=Direction.INCREASE,
            corrective_value=16.0,
            unit="mm",
            provenance="lug thickness inverse (σ ∝ 1/t, so SF ∝ t)",
        ),
    )
    assert _repair_source(_Section(solved)) == (
        " — from the lug thickness inverse (σ ∝ 1/t, so SF ∝ t)"
    )

    bare = ScorecardEntry.from_safety_factor(
        "lug tension",
        computed=1.0,
        required=2.0,
        repair_hint=RepairHint.directional("thickness", direction=Direction.INCREASE),
    )
    assert _repair_source(_Section(bare)) == ""


def test_a_negative_value_does_not_drop_a_formula_out_of_the_grammar():
    """A sign in front of a value, which the grammar had no rule for.

    Every substituted line carrying a negative number fell outside the grammar, so the
    report rendered it as plain text — and negatives are not exotic here: an uplift demand,
    a counteracting load combination and a sagging moment all produce one. The load
    combination that surfaced it evaluates to −29.2 under 0.9D + 1.0W.

    The round-trip guard is what makes this safe to add: a sign parsed into the wrong shape
    would write back out as a different string and the renderer would decline rather than
    typeset something the check did not say.
    """
    from xml.etree import ElementTree as ET

    from anvilate.report.mathml import formula_to_mathml

    for formula in (
        "U = 0.9 · 12 + 1.0 · -40",
        "U = -29.2",
        "M = -12.5 kN·m",
        "ΔT = +4.0 K",
    ):
        math = formula_to_mathml(formula)
        assert math is not None, formula
        ET.fromstring(math)

    # A minus BETWEEN two values is still a subtraction, not a sign — the round trip is
    # what proves the tree did not change shape.
    binary = formula_to_mathml("x = 3 - 2")
    assert binary is not None
    assert "<mn>3</mn><mo>-</mo><mn>2</mn>" in binary
    assert "<mo>-</mo><mn>29.2</mn>" in formula_to_mathml("U = -29.2")

    # And the grammar has not become permissive: what it declined before, it still
    # declines. A doubled operator in particular — the shape a careless sign rule admits.
    assert formula_to_mathml("x = 3 · · 4") is None
    assert formula_to_mathml("x = (3") is None
    assert formula_to_mathml("ΔV% = 100 · I") is None


def test_a_units_slash_is_not_a_stacked_fraction():
    """A slash inside a value belongs to its unit; a slash in the formula is a division.

    Found by rendering a report and looking at it. A substituted line whose values carry
    compound units — the pump duty's ρ·g·Q·H/η is four of them — parses left-associatively
    into four nested divisions, and typeset as four nested fractions it came out three font
    sizes down and unreadable. The arithmetic was right the whole time, which is why the
    render-truth gate could not see it: the numbers agreed and the page was illegible.

    The test is the nesting depth, because that is the thing that was wrong.
    """
    from anvilate.report.mathml import formula_to_mathml

    def depth(markup: str) -> int:
        deepest = current = index = 0
        while index < len(markup):
            if markup.startswith("<mfrac>", index):
                current += 1
                deepest = max(deepest, current)
                index += 7
            elif markup.startswith("</mfrac>", index):
                current -= 1
                index += 8
            else:
                index += 1
        return deepest

    pump = formula_to_mathml("P_s = 1000.00 kg/m³ · 9.81 m/s² · 50.00 L/s · 20.000 m / 0.7")
    assert pump is not None
    assert depth(pump) == 1, "the unit slashes are being stacked again"
    assert "<mo>/</mo>" in pump

    # A value with nothing but a unit slash is not a fraction at all.
    assert depth(formula_to_mathml("V_oz = 237.50 L/s")) == 0

    # The formula's own divisions are still stacked, and being unit-SHAPED is not enough:
    # in the symbolic line every operand is a name, so "H / η" would qualify on shape
    # alone. A unit slash always has a number on its left.
    assert depth(formula_to_mathml("P_s = ρ · g · Q · H / η")) == 1
    assert depth(formula_to_mathml("σ_b = M · c / I")) == 1
    # And a division BY a value stays a fraction even with units on both sides.
    assert depth(formula_to_mathml("σ_b = 12.5 kN·m · 25.00 mm / 4166666.67 mm⁴")) == 1
    assert depth(formula_to_mathml("n = 124.0 MPa / 96.0 MPa")) == 1


def test_no_derivation_the_library_builds_typesets_more_than_two_fractions_deep():
    """The corpus-wide version, because one formula proves one formula.

    Two is the depth a genuinely nested division reaches — σ_t = P_t / (π · d² / 4) — and
    anything past it is a unit slash being stacked. Held over every line of every
    derivation the packs build, in the sample the render-truth gate uses.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from anvilate.report.mathml import formula_to_mathml
    from test_contract import _sample_derivations

    def depth(markup: str) -> int:
        deepest = current = index = 0
        while index < len(markup):
            if markup.startswith("<mfrac>", index):
                current += 1
                deepest = max(deepest, current)
                index += 7
            elif markup.startswith("</mfrac>", index):
                current -= 1
                index += 8
            else:
                index += 1
        return deepest

    corpus = _sample_derivations()
    assert len(corpus) >= 20
    too_deep = []
    for label, derivation in corpus:
        for line in derivation.lines():
            markup = formula_to_mathml(line)
            if markup is not None and depth(markup) > 2:
                too_deep.append(f"{label}: {line}")
    assert not too_deep, "formulas typeset more than two fractions deep:\n  " + "\n  ".join(
        too_deep
    )
