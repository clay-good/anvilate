"""Worked example: smearing a machine foot over a panel is dangerously green.

A 5 kN machine foot lands on a 100 x 100 mm pad in the middle of a
500 x 500 x 6 mm simply-supported A36 panel. Smeared over the whole panel
(0.02 MPa) the screen looks comfortable: 39.9 MPa (SF 6.27) and 1.28 mm,
inside a b/250 = 2 mm limit. Declared on its true footprint
(``simply_supported_plate_center_patch_load``, 0.5 MPa over the pad) the same
5 kN concentrates 4.4x the bending — 177 MPa, SF 1.41, FAIL — and 3.43 mm of
deflection, past both the limit and the w ~ t/2 thin-plate validity edge.
Beams forgave smearing within ~2x (`pallet_bay_floor_beam`); a plate's
two-way spread makes the footprint matter even more, and shrinking the pad
at the same load only drives the peak higher (the point-load singularity).

Run it directly (``python examples/machine_foot_on_panel.py``);
:func:`screen_machine_foot` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    deflection_scorecard,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_uniform_load,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

PANEL = Quantity.parse("500 mm")
THICKNESS = Quantity.parse("6 mm")
PAD = Quantity.parse("100 mm")
FOOT_LOAD = 5000.0  # N
DEFLECTION_LIMIT = Quantity(magnitude=500 / 250, unit="mm")  # b/250
REQUIRED_SF = 1.5


def screen_machine_foot() -> Scorecard:
    """Screen the foot smeared over the panel, then on its true pad."""
    record = default_materials_db().get("ASTM-A36")
    common = {
        "length": PANEL,
        "width": PANEL,
        "thickness": THICKNESS,
        "elastic_modulus": record.elastic_modulus.quantity,
    }
    panel_mm = PANEL.to("mm").magnitude
    pad_mm = PAD.to("mm").magnitude
    smeared = simply_supported_plate_uniform_load(
        pressure=Quantity(magnitude=FOOT_LOAD / panel_mm**2, unit="MPa"), **common
    )
    footprint = simply_supported_plate_center_patch_load(
        pressure=Quantity(magnitude=FOOT_LOAD / pad_mm**2, unit="MPa"),
        patch_length=PAD,
        patch_width=PAD,
        **common,
    )

    entries = []
    for label, result in (
        ("smeared over the panel", smeared),
        ("declared 100 mm pad", footprint),
    ):
        entries.append(
            strength_scorecard(
                f"{label} bending",
                stress=result.max_bending_stress,
                allowable=record.yield_strength.quantity,
                required=REQUIRED_SF,
            )
        )
        entries.append(
            deflection_scorecard(
                f"{label} deflection",
                deflection=result.max_deflection,
                limit=DEFLECTION_LIMIT,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_machine_foot()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
