"""Worked example: picking the injection machine and what the wall thickness costs the cycle.

Moulding a plastic part starts with two process numbers the part geometry decides for you. The first
sizes the machine: molten plastic is injected at high pressure, and that pressure pushing on the
part's projected area tries to force the mould halves apart, so the machine's clamp must hold them
shut with a force equal to area times pressure. The second sizes the cycle: the part cannot be
ejected until its core has cooled enough to keep its shape, and that cooling time — which dominates
the cycle — grows with the *square* of the wall thickness.

This example takes an ABS housing with a 120 cm² projected area moulded at 45 MPa cavity pressure.
The clamp force works out to about 540 kN, roughly 55 tonnes, so a 60- or 80-tonne press is the
right pick with margin. The example also runs the inverse: a 100-tonne machine (about 980 kN) could
hold a part up to roughly 218 cm² at that pressure — head-room for a bigger tool later. Then the
cycle: a 2.5 mm wall cools in about 11 seconds, but the same part drawn with a 3.5 mm wall
would take about 22 seconds — twice the cycle for one extra millimetre, because cooling scales with
the square of the wall. That trade is why moulded parts are designed thin and even: the wall
thickness you draw is the cycle time you pay for, on every shot for the life of the tool.

Run it directly (``python examples/injection_molding_machine_pick.py``);
:func:`mould_process` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    injection_clamp_force,
    injection_cooling_time,
    max_projected_area_for_clamp,
)
from anvilate.units import Quantity

PROJECTED_AREA = Quantity.parse("120 cm**2")
CAVITY_PRESSURE = Quantity.parse("45 MPa")
MACHINE_CLAMP = Quantity.parse("980 kN")  # ~100 tonne press
ABS_DIFFUSIVITY = Quantity.parse("1e-7 m**2/s")
MELT_TEMP = Quantity(magnitude=230.0, unit="degC")
MOLD_TEMP = Quantity(magnitude=50.0, unit="degC")
EJECT_TEMP = Quantity(magnitude=90.0, unit="degC")


def mould_process() -> dict[str, float]:
    """Return the clamp force, the tonnage's max area, and cooling time at two wall thicknesses."""
    clamp = injection_clamp_force(projected_area=PROJECTED_AREA, cavity_pressure=CAVITY_PRESSURE)
    max_area = max_projected_area_for_clamp(
        clamp_force=MACHINE_CLAMP, cavity_pressure=CAVITY_PRESSURE
    )

    def cooling(wall_mm: float) -> float:
        t = injection_cooling_time(
            wall_thickness=Quantity(magnitude=wall_mm, unit="mm"),
            thermal_diffusivity=ABS_DIFFUSIVITY,
            melt_temperature=MELT_TEMP,
            mold_temperature=MOLD_TEMP,
            ejection_temperature=EJECT_TEMP,
        )
        return t.to("s").magnitude

    return {
        "clamp_force_kn": clamp.to("kN").magnitude,
        "clamp_force_tonnes": clamp.to("kN").magnitude / 9.80665,
        "max_area_cm2": max_area.to("cm**2").magnitude,
        "cooling_2p5mm_s": cooling(2.5),
        "cooling_3p5mm_s": cooling(3.5),
    }


def main() -> None:
    m = mould_process()
    print(
        f"clamp force needed: {m['clamp_force_kn']:.0f} kN "
        f"(~{m['clamp_force_tonnes']:.0f} tonnes) -> pick a 60-80 t press"
    )
    print(f"a 100 t machine could hold up to {m['max_area_cm2']:.0f} cm2 at 45 MPa")
    print(
        f"cooling: {m['cooling_2p5mm_s']:.0f} s at 2.5 mm wall vs "
        f"{m['cooling_3p5mm_s']:.0f} s at 3.5 mm"
    )
    print("  -> cooling scales with wall^2; thin, even walls are the first rule of part design")


if __name__ == "__main__":
    main()
