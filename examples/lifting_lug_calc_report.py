"""Worked example: the lifting padeye screening, rendered as a submittal.

The same padeye :mod:`examples.lifting_padeye` screens -- an 80 mm x 12 mm A36 lug
with a 25 mm pin hole raising 50 kN at a rigging factor of 2 -- but rendered as the
document a checker actually reviews rather than a list of verdicts.

A scorecard says "pin bearing FAIL, safety factor 1.50 vs 2.00." That tells a
reviewer the answer and nothing about how it was reached. The report below shows,
for each limit state, the formula ASME BTH-1 writes, the same formula with the
actual load and dimensions substituted (each carrying its unit), the resulting
stress, and the clause it rests on -- plus the code editions relied on, the
assumptions in force, and a margin summary naming the governing check. That is the
difference between an answer and a calculation, and it is what a permitting
jurisdiction, an engineer of record, or an independent checker asks for.

Two of the three checks here are worked derivations. The weld check is deliberately
left without derivation metadata, so the example also shows the honest fallback:
its inputs and verdict in a table labeled "derivation not rendered," never a
formula invented to fill the space.

The governing check is pin bearing: at 166.7 MPa against A36's 250 MPa yield, it
carries a 1.50 factor where the lift demands 2.00 -- so the pin hole, not the lug
width or the weld, is what has to change.

Run it directly (``python examples/lifting_lug_calc_report.py``) to print the
report and write an HTML copy to the system temp directory;
:func:`build_report` is also exercised in the test suite.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from anvilate.packs.structural import LiftingLug, WeldedConnection, screen_structure
from anvilate.report import CalculationReport, Derivation, ReportSection, SymbolValue
from anvilate.units import Quantity, UnitSystem

LIFT_LOAD = Quantity.parse("50 kN")
LUG_WIDTH = Quantity.parse("80 mm")
HOLE_DIAMETER = Quantity.parse("25 mm")
THICKNESS = Quantity.parse("12 mm")
WELD_LEG = Quantity.parse("8 mm")
WELD_LENGTH = Quantity.parse("160 mm")
ELECTRODE_STRENGTH = Quantity.parse("483 MPa")  # E70
RIGGING_FACTOR = 2.0

_LUG_CLAUSE = "ASME BTH-1 §3-3"

# The two limit-state stresses, computed the same way the structural pack computes
# them, so the derivations show the numbers the scorecard actually screened.
_NET_TENSION = Quantity(
    magnitude=LIFT_LOAD.to("N").magnitude
    / (
        (LUG_WIDTH.to("mm").magnitude - HOLE_DIAMETER.to("mm").magnitude)
        * THICKNESS.to("mm").magnitude
    ),
    unit="MPa",
)
_BEARING = Quantity(
    magnitude=LIFT_LOAD.to("N").magnitude
    / (HOLE_DIAMETER.to("mm").magnitude * THICKNESS.to("mm").magnitude),
    unit="MPa",
)


def _screen():
    """Screen the padeye assembly exactly as the structural pack does."""
    lug = LiftingLug(
        name="padeye",
        width=LUG_WIDTH,
        hole_diameter=HOLE_DIAMETER,
        thickness=THICKNESS,
        load=LIFT_LOAD,
        material="ASTM-A36",
    )
    weld = WeldedConnection(
        name="padeye_weld",
        leg_size=WELD_LEG,
        weld_length=WELD_LENGTH,
        load=LIFT_LOAD,
        electrode_strength=ELECTRODE_STRENGTH,
    )
    return screen_structure([lug, weld], required_safety_factor=RIGGING_FACTOR)


def _net_tension_derivation() -> Derivation:
    return Derivation(
        symbolic="σ_t = P / ((W − d) · t)",
        inputs=(
            SymbolValue(symbol="P", description="lifted load", value=LIFT_LOAD),
            SymbolValue(symbol="W", description="lug width across the hole", value=LUG_WIDTH),
            SymbolValue(symbol="d", description="pin hole diameter", value=HOLE_DIAMETER),
            SymbolValue(symbol="t", description="lug plate thickness", value=THICKNESS),
        ),
        result=SymbolValue(
            symbol="σ_t", description="net-section tensile stress", value=_NET_TENSION
        ),
        citation=_LUG_CLAUSE,
    )


def _bearing_derivation() -> Derivation:
    return Derivation(
        symbolic="σ_p = P / (d · t)",
        inputs=(
            SymbolValue(symbol="P", description="lifted load", value=LIFT_LOAD),
            SymbolValue(symbol="d", description="pin hole diameter", value=HOLE_DIAMETER),
            SymbolValue(symbol="t", description="lug plate thickness", value=THICKNESS),
        ),
        result=SymbolValue(symbol="σ_p", description="pin bearing stress", value=_BEARING),
        citation=_LUG_CLAUSE,
    )


def build_report() -> CalculationReport:
    """Assemble the padeye screening into a submittal-shaped calculation report."""
    entries = {entry.name: entry for entry in _screen().entries}
    derivations = {
        "padeye net tension": _net_tension_derivation(),
        "padeye pin bearing": _bearing_derivation(),
    }
    sections = []
    for name, entry in entries.items():
        derivation = derivations.get(name)
        if derivation is not None:
            sections.append(ReportSection(entry=entry, derivation=derivation))
        else:
            # No derivation metadata for the weld check: the report says so rather
            # than fabricating a formula.
            sections.append(
                ReportSection(
                    entry=entry,
                    inputs=(
                        SymbolValue(symbol="P", description="lifted load", value=LIFT_LOAD),
                        SymbolValue(symbol="w", description="fillet leg size", value=WELD_LEG),
                        SymbolValue(symbol="L", description="total weld length", value=WELD_LENGTH),
                        SymbolValue(
                            symbol="F_EXX",
                            description="electrode tensile strength (E70)",
                            value=ELECTRODE_STRENGTH,
                        ),
                    ),
                )
            )
    return CalculationReport(
        title="Lifting padeye — screening calculations",
        project="Shop crane padeye, 50 kN",
        prepared_by="Anvilate T1 screening",
        date="2026-07-27",
        unit_system=UnitSystem.SI,
        standards=(
            "ASME BTH-1 — Design of Below-the-Hook Lifting Devices",
            "AISC 360-16 — Specification for Structural Steel Buildings",
            "Material: ASTM A36, yield 250 MPa (bundled standards data)",
        ),
        assumptions=(
            f"Rigging safety factor of {RIGGING_FACTOR:.1f} on the lifted load "
            "(user-supplied design category).",
            "Static lift; no impact or side-load factor applied.",
            "Pin fits the hole; bearing taken over the full projected area d·t.",
        ),
        sections=tuple(sections),
    )


def main() -> None:
    report = build_report()
    print(report.to_text())
    destination = Path(tempfile.gettempdir()) / "lifting_lug_report.html"
    destination.write_text(report.to_html())
    print(f"wrote {destination}")


if __name__ == "__main__":
    main()
