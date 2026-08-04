"""Worked example: driving ground rods to a resistance target, and why soil rules.

A grounding electrode has to hold the fault and lightning current it sees at a low enough resistance
to earth — often a 25 Ω target for a single made electrode, less for sensitive equipment. This
example takes a single 3 m rod in three soils — moist loam at 100 Ω·m, dry sand at 1000 Ω·m — and
finds each resistance from the Dwight formula. The loam rod is close to target on its own; the
sandy-soil rod is ten times worse, because the soil resistivity, not the rod, dominates the result.
When one rod is not enough, the fix is more rods in parallel — but they interfere, so four rods do
not quarter the resistance. The example shows a four-rod array in the poor soil landing well above
the ideal one-quarter, which is the reality every grounding grid designer plans around.

Run it directly (``python examples/ground_electrode_sizing.py``);
:func:`grounding_study` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import ground_rod_resistance, parallel_ground_electrodes_resistance
from anvilate.units import Quantity

ROD_LENGTH = Quantity.parse("3 m")
ROD_RADIUS = Quantity.parse("0.008 m")  # ~5/8 in rod
ARRANGEMENT_EFFICIENCY = 0.7  # IEEE 142 combining factor for closely spaced rods


def _rod(resistivity: str) -> Quantity:
    return ground_rod_resistance(
        soil_resistivity=Quantity.parse(resistivity),
        rod_length=ROD_LENGTH,
        rod_radius=ROD_RADIUS,
    )


def grounding_study() -> dict[str, float]:
    """Return single-rod resistances in two soils and a four-rod array in the poor soil."""
    loam = _rod("100 ohm*m")
    sand = _rod("1000 ohm*m")
    sand_four = parallel_ground_electrodes_resistance(
        single_rod_resistance=sand,
        rod_count=4,
        arrangement_efficiency=ARRANGEMENT_EFFICIENCY,
    )
    return {
        "loam_ohm": loam.to("ohm").magnitude,
        "sand_ohm": sand.to("ohm").magnitude,
        "sand_four_rods_ohm": sand_four.to("ohm").magnitude,
        "sand_ideal_quarter_ohm": sand.to("ohm").magnitude / 4.0,
    }


def main() -> None:
    g = grounding_study()
    print(f"3 m rod in moist loam (100 Ω·m) : {g['loam_ohm']:.0f} Ω")
    print(f"3 m rod in dry sand (1000 Ω·m)  : {g['sand_ohm']:.0f} Ω (soil dominates)")
    print(
        f"four rods in the sand           : {g['sand_four_rods_ohm']:.0f} Ω "
        f"(ideal ¼ would be {g['sand_ideal_quarter_ohm']:.0f} Ω)"
    )
    print("  -> resistivity sets the scale; parallel rods interfere, so they help less than 1/N")


if __name__ == "__main__":
    main()
