"""Every derivation the packs build: the line a reader sees comes to the number beside it.

`tests/test_beam_deflection_formulas.py` and its siblings ask whether the *formula* is
right, by reducing every symbol to SI base units. This asks the question a reviewer
actually asks, which is a different one: does the line **as printed**, in the units printed
beside each symbol, evaluate to the result printed underneath.

The difference is a unit the report converts for one symbol and not another. That is
invisible to a formula check — the arithmetic is fine, only the rendering mixes — and it is
the whole of what a reviewer is doing when they check a line by hand. It has been the
defect twice: a US-customary report reading

    σ_b = 10.00 kN·m · 2.953 in / 28125000.00 mm⁴

and a ventilation line dividing a flow in ft³/min by a room volume in mm³, nine orders of
magnitude out, because the system's unit table maps one unit per *dimension* and reads
every `[length]³` as a section modulus.

The corpus is the derivations the discipline packs really build, collected by running the
screens rather than by listing them, so a pack cannot leave itself out.
"""

from __future__ import annotations

import math

import pytest

from anvilate.units import Quantity, UnitSystem
from formula_arithmetic import evaluates_as_rendered


def _screens():
    """The cards the corpus is built from, so both halves read the same screens."""
    from anvilate.analysis import CrossSection
    from anvilate.packs.industrial import CoverPlate, PlateEdge, screen_cover_plate
    from anvilate.packs.structural import (
        BeamMember,
        LoadType,
        Support,
        screen_beam_member,
    )
    from anvilate.packs.ventilation import VentilationZone, screen_ventilation

    cards = []
    section = CrossSection.rectangular(
        width=Quantity.parse("100 mm"), height=Quantity.parse("150 mm")
    )
    for load_type, load in (
        (LoadType.DISTRIBUTED, Quantity.parse("5 kN/m")),
        (LoadType.POINT, Quantity.parse("10 kN")),
    ):
        cards.append(
            screen_beam_member(
                BeamMember(
                    name="rafter",
                    section=section,
                    length=Quantity.parse("4 m"),
                    support=Support.SIMPLY_SUPPORTED,
                    load_type=load_type,
                    load=load,
                    material="ASTM-A36",
                    deflection_limit=Quantity.parse("16 mm"),
                ),
                required_safety_factor=1.5,
            )
        )
    cards.append(
        screen_cover_plate(
            CoverPlate(
                name="manway",
                length=Quantity.parse("900 mm"),
                width=Quantity.parse("620 mm"),
                thickness=Quantity.parse("12 mm"),
                pressure=Quantity.parse("0.4 MPa"),
                material="ASTM-A36",
                edge=PlateEdge.CLAMPED,
                deflection_limit=Quantity.parse("3 mm"),
                min_frequency=Quantity.parse("60 Hz"),
            ),
            required_safety_factor=1.5,
        )
    )
    cards.append(
        screen_ventilation(
            VentilationZone(
                name="office",
                people_outdoor_rate=Quantity.parse("2.5 L/s"),
                occupancy=12,
                area_outdoor_rate=Quantity.parse("0.3 L/s/m**2"),
                floor_area=Quantity.parse("120 m**2"),
                zone_air_distribution_effectiveness=0.8,
                provided_outdoor_airflow=Quantity.parse("340 m**3/hour"),
                room_volume=Quantity.parse("360 m**3"),
                required_air_changes=0.9,
            ),
            required_safety_factor=1.0,
        )
    )

    return cards


def _derivations():
    """Every distinct derivation those screens build."""
    found = {}
    for card in _screens():
        for entry in card.entries:
            if entry.derivation is not None:
                found.setdefault(entry.derivation.symbolic, entry.derivation)
    return sorted(found.items())


_CASES = _derivations()


def test_the_corpus_reaches_more_than_one_pack():
    """Without this the file proves whatever the screens above happen to build."""
    assert len(_CASES) >= 8, f"only {len(_CASES)} derivations collected: {[s for s, _ in _CASES]}"
    assert any("ACH" in symbolic for symbolic, _ in _CASES), "the ventilation pack is missing"
    assert any("f₁" in symbolic for symbolic, _ in _CASES), "the modal derivation is missing"


@pytest.mark.parametrize(
    ("symbolic", "derivation"),
    [pytest.param(symbolic, derivation, id=symbolic[:40]) for symbolic, derivation in _CASES],
)
@pytest.mark.parametrize("system", [None, UnitSystem.SI, UnitSystem.US], ids=["none", "SI", "US"])
def test_a_rendered_line_evaluates_to_the_result_printed_under_it(symbolic, derivation, system):
    why, got, want = evaluates_as_rendered(derivation, system=system)
    assert why is None, f"{symbolic!r} could not be checked under {system}: {why}"
    try:
        left = float(got.to(want.units).magnitude) if hasattr(want, "units") else float(got)
        right = float(want.magnitude) if hasattr(want, "magnitude") else float(want)
    except Exception as exc:  # a dimensional mismatch is the failure, not an error
        pytest.fail(
            f"{symbolic!r} under {system}: the line comes to {getattr(got, 'units', got)} and "
            f"the result is printed as {getattr(want, 'units', want)} — {exc}"
        )
    # Loose, because both sides are rounded for display. A units mismatch is orders of
    # magnitude out, which is what this is looking for; a rounding difference is not.
    assert math.isclose(left, right, rel_tol=2e-2), (
        f"{symbolic!r} under {system}: the printed line comes to {left:.6g} and the result "
        f"printed under it is {right:.6g}"
    )


def test_no_verdict_line_carries_a_unit_the_document_did_not_declare():
    """The other half of the same property, and the half a fix to the derivation cannot reach.

    A verdict is a sentence written at screening time, and a screen does not know what
    system its result will be read in. A US-customary report printed

        δ = 5·0.0286 kip/in·(157.480 in)⁴/(384·29007.5 ksi·67.57 in⁴)
        δ = 0.117 in
      deflection 2.963 mm vs limit 16.000 mm

    — the work in inches and the verdict beneath it in millimetres, on the line a reviewer
    reads first. A check that compares two quantities carries them now, and the report
    states the comparison in its own units.
    """
    from anvilate.report import CalculationReport, ReportSection

    si_only = ("mm", "MPa", "GPa", "kPa", "kN·m", "N·mm")
    us_only = (" in", " ft", "kip", "ksi", "psi")
    cards = _screens()
    compared = [entry for card in cards for entry in card.entries if entry.comparison is not None]
    assert len(compared) >= 3, (
        f"only {len(compared)} comparison verdicts in the corpus, so this proves little"
    )

    for system, forbidden in ((UnitSystem.US, si_only), (UnitSystem.SI, us_only)):
        report = CalculationReport(
            title="unit fidelity",
            unit_system=system,
            sections=tuple(ReportSection(entry=entry) for card in cards for entry in card.entries),
        )
        for section in report.sections:
            if section.entry.comparison is None:
                continue
            line = section.verdict(system=system)
            stray = [unit for unit in forbidden if unit in line]
            assert not stray, f"under {system.value} the verdict {line!r} carries {stray}"


def test_a_comparison_between_unlike_quantities_is_refused():
    """A length judged against a frequency is not a comparison, and a rendered sentence
    would give it the appearance of one — two numbers, a "vs", and a unit that changed
    between them.
    """
    import pytest as _pytest
    from pydantic import ValidationError

    from anvilate.scorecard import Comparison, LimitSense

    with _pytest.raises(ValidationError, match="same dimension"):
        Comparison(
            measured=Quantity.parse("15 mm"),
            limit=Quantity.parse("60 Hz"),
            sense=LimitSense.AT_MOST,
            measured_label="deflection",
            limit_label="limit",
        )


def test_the_verdict_sentence_is_the_one_the_screens_have_always_written():
    """`detail` is written from the comparison now, and must not have moved.

    Every surface that reads a scorecard — the CLI, the evidence bundle, the QIF export —
    reads that sentence, and it is quoted in the README's own quickstart output. Deriving
    it from the numbers is only safe if it derives the same words.
    """
    from anvilate.analysis import deflection_scorecard

    entry = deflection_scorecard(
        "tip deflection",
        deflection=Quantity.parse("36.284 mm"),
        limit=Quantity.parse("15 mm"),
    )
    assert entry.detail == "deflection 36.284 mm vs limit 15.000 mm"
    # And the widening that keeps a FAIL from printing two identical figures still works.
    close = deflection_scorecard(
        "tip deflection",
        deflection=Quantity.parse("15.0004 mm"),
        limit=Quantity.parse("15 mm"),
    )
    assert close.status.value == "fail"
    assert "15.0004" in close.detail and "15.0000" in close.detail
