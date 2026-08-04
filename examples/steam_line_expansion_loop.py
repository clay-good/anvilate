"""Worked example: sizing an expansion loop for a hot steam line that would otherwise buckle.

A long pipe run heated from ambient to operating temperature grows, and if both ends are anchored
that growth has nowhere to go — the restrained expansion builds enormous stress. The fix is to give
the run a loop or an offset leg long enough to flex and take the movement within an allowable
stress. This example works the two steps in order for a 60 m carbon-steel steam header from 20°C to
300°C: first the free thermal growth it would make if unrestrained (α·L·ΔT), then the guided-
cantilever leg length that absorbs that growth in DN150 pipe within a 150 MPa allowable. The run
grows about 200 mm, and it needs roughly a 12 m leg to take it — the reason long steam lines zig-zag
across a plant rather than run dead straight between anchors.

Run it directly (``python examples/steam_line_expansion_loop.py``);
:func:`loop_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import free_thermal_expansion, guided_cantilever_leg_length
from anvilate.units import Quantity

RUN_LENGTH = Quantity.parse("60 m")
CARBON_STEEL_CTE = Quantity.parse("12e-6 1/K")
TEMPERATURE_RISE = Quantity.parse("280 K")  # 20 C to 300 C
ELASTIC_MODULUS = Quantity.parse("200 GPa")
PIPE_OD = Quantity.parse("0.168 m")  # DN150 (6 in) pipe OD
ALLOWABLE_STRESS = Quantity.parse("150 MPa")


def loop_sizing() -> dict[str, float]:
    """Return the free thermal growth (mm) and the expansion-loop leg length (m)."""
    growth = free_thermal_expansion(
        length=RUN_LENGTH,
        thermal_expansion_coefficient=CARBON_STEEL_CTE,
        temperature_change=TEMPERATURE_RISE,
    )
    leg = guided_cantilever_leg_length(
        elastic_modulus=ELASTIC_MODULUS,
        pipe_outside_diameter=PIPE_OD,
        expansion_to_absorb=growth,
        allowable_stress=ALLOWABLE_STRESS,
    )
    return {
        "growth_mm": growth.to("mm").magnitude,
        "leg_length_m": leg.to("m").magnitude,
    }


def main() -> None:
    s = loop_sizing()
    print(f"free thermal growth (60 m, +280 K) : {s['growth_mm']:.0f} mm")
    print(f"expansion-loop leg to absorb it     : {s['leg_length_m']:.1f} m")
    print(
        "  -> anchoring both ends would overstress the pipe; the loop gives the growth room to flex"
    )


if __name__ == "__main__":
    main()
