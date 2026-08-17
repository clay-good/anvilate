"""Calculation report: worked derivations, submittal document, and calc record."""

from __future__ import annotations

import json
import socket

import pytest

from anvilate.report import (
    CALC_RECORD_SCHEMA_VERSION,
    SCREENING_DISCLAIMER,
    CalculationReport,
    Derivation,
    ReportSection,
    SymbolValue,
    report_from_record,
)
from anvilate.scorecard import CheckStatus, Direction, RepairHint, ScorecardEntry
from anvilate.units import Quantity, UnitSystem

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
        assumptions=("Static load; no impact factor applied (user-supplied).",),
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
    assert substituted == "σ_b = 1500.00 m·N · 50.00 mm / 2100000.00 mm⁴"
    assert result == "σ_b = 35.7 MPa"


def test_substituted_values_always_carry_a_unit():
    substituted = BENDING.substituted(system=UnitSystem.SI)
    for value in ("1500.00", "50.00", "2100000.00"):
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
    assert moment.rendered(system=UnitSystem.US) == moment.rendered(system=UnitSystem.SI)
    pinned = SymbolValue(
        symbol="M", description="bending moment", value=Quantity.parse("1500 N*m"), unit="kip*in"
    )
    # 1500 N·m is 13.28 kip·in. Compound factors print in the unit registry's
    # alphabetical order rather than the force-first convention.
    assert pinned.rendered(system=UnitSystem.SI) == "13.28 in·kip"


# -- document --------------------------------------------------------------


def test_report_carries_the_basis_of_design():
    text = _report().to_text()
    for expected in (
        "Conveyor bracket screening",
        "Line 4 conveyor",
        "AISC 360-22",
        "Static load; no impact factor applied (user-supplied).",
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
    assert "uncertainty: P(below 1.50) = 21.0% over 20000 samples — FRAGILE" in text
    assert report.status is CheckStatus.PASS  # deterministic verdict unchanged
    html = report.to_html()
    assert 'class="uncertainty fragile"' in html


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
    # A slender column buckles elastically: the formula shown must be Euler's, and
    # the yield strength must not appear in it.
    assert "Euler" in slender.name
    assert slender.derivation.symbolic == "σ_cr = π² · E / λ²"
    assert "S_y" not in slender.derivation.substituted()

    stocky = screen("500 mm")
    # A stocky one is inelastic, and the Johnson parabola does use the yield strength.
    assert "Johnson" in stocky.name
    assert "S_y" in stocky.derivation.symbolic
    assert any(item.symbol == "S_y" for item in stocky.derivation.inputs)


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

    # An offset point load solves for the peak position rather than evaluating a
    # one-line formula, so it declares none and the report falls back honestly.
    offset = deflection_entry(
        load_type=LoadType.POINT,
        load=Quantity.parse("10 kN"),
        load_position=Quantity.parse("1 m"),
    )
    assert offset.derivation is None


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
    assert clamped.substituted() == "σ = 3·0.4 MPa·(250.00 mm)²/(4·(12.00 mm)²)"

    # The simply-supported form carries Poisson's ratio, so it declares it.
    supported = bending(edge=PlateEdge.SIMPLY_SUPPORTED).derivation
    assert "ν" in supported.symbolic
    assert any(item.symbol == "ν" for item in supported.inputs)
    assert supported.unresolved_symbols() == ()

    # A rectangular cover sums a Navier series; there is no one-line formula that
    # is what was computed, so it declares none.
    rectangular = bending(
        diameter=None, length=Quantity.parse("600 mm"), width=Quantity.parse("400 mm")
    )
    assert rectangular.derivation is None


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
