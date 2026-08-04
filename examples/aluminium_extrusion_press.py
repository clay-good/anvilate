"""Worked example: why an aluminium extrusion press is enormous, and why it runs hot.

Extrusion makes a long constant-section shape by shoving a heated billet through a die, and a single
pass reaches reductions no other process touches — an area ratio of 40 is routine for aluminium. The
catch is the force. The ram pressure grows with the natural log of the extrusion ratio, and real
extrusion adds friction on the container wall and the redundant work of internal shearing on top of
that ideal, so the presses are among the largest force-producing machines in a factory.

This example pushes a 200 mm diameter aluminium billet through a die that yields a 32 mm round — an
extrusion ratio of about 39. At the hot working temperature the metal's flow stress is a modest
50 MPa, and the ideal (frictionless, homogeneous) ram pressure to work it down is about 183 MPa. But
at a 55% deformation efficiency — accounting for wall friction and redundant shear — the real ram
pressure climbs to about 333 MPa, and acting on the big 200 mm billet that is a ram force near
10,500 kN, over a thousand tonnes. The example also shows the temperature lever: were the billet
extruded cold, its flow stress would be several times higher and the force several times larger,
past what any press could give — which is exactly why aluminium and most metals are extruded hot,
where the low flow stress keeps the enormous ratios within a buildable press. The point is that
extrusion trades force for reduction, and temperature is how that trade is made affordable.

Run it directly (``python examples/aluminium_extrusion_press.py``);
:func:`extrusion_press` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import extrusion_force, extrusion_pressure, extrusion_ratio
from anvilate.units import Quantity

BILLET_DIAMETER = 200.0  # mm
EXTRUDATE_DIAMETER = 32.0  # mm
BILLET_AREA = Quantity(magnitude=pi / 4 * BILLET_DIAMETER**2, unit="mm**2")
EXTRUDATE_AREA = Quantity(magnitude=pi / 4 * EXTRUDATE_DIAMETER**2, unit="mm**2")
HOT_FLOW_STRESS = Quantity.parse("50 MPa")  # aluminium at extrusion temperature
DEFORMATION_EFFICIENCY = 0.55


def extrusion_press() -> dict[str, float]:
    """Return the extrusion ratio, the ideal and real ram pressure, and the ram force."""
    ratio = extrusion_ratio(billet_area=BILLET_AREA, extrudate_area=EXTRUDATE_AREA)
    ideal_pressure = extrusion_pressure(flow_stress=HOT_FLOW_STRESS, extrusion_ratio=ratio)
    real_pressure = extrusion_pressure(
        flow_stress=HOT_FLOW_STRESS,
        extrusion_ratio=ratio,
        deformation_efficiency=DEFORMATION_EFFICIENCY,
    )
    ram_force = extrusion_force(extrusion_pressure=real_pressure, billet_area=BILLET_AREA)
    return {
        "ratio": ratio,
        "ideal_pressure_mpa": ideal_pressure.to("MPa").magnitude,
        "real_pressure_mpa": real_pressure.to("MPa").magnitude,
        "ram_force_kn": ram_force.to("kN").magnitude,
    }


def main() -> None:
    e = extrusion_press()
    print(f"extrusion ratio : {e['ratio']:.0f} (200 mm billet -> 32 mm round)")
    print(f"ideal pressure  : {e['ideal_pressure_mpa']:.0f} MPa (Y*ln R, frictionless)")
    print(f"real pressure   : {e['real_pressure_mpa']:.0f} MPa (55% deformation efficiency)")
    print(
        f"ram force       : {e['ram_force_kn']:.0f} kN "
        f"(~{e['ram_force_kn'] / 9.80665:.0f} tonnes) -> extrude hot to keep it buildable"
    )


if __name__ == "__main__":
    main()
