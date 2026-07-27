"""Calculation report: worked derivations, submittal document, and calc record."""

from __future__ import annotations

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
from anvilate.scorecard import CheckStatus, ScorecardEntry
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
