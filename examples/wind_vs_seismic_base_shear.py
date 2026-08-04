"""Worked example: does wind or the earthquake set the lateral design of a building?

A building's lateral system — the frames and walls that resist sideways load — is sized for the
worse of two hazards, and which one wins is not obvious until both are worked out in the same units.
This example takes a 6-story, 20 m by 30 m building weighing 40,000 kN and asks each hazard for the
total horizontal force at its base.

The wind side runs the ASCE 7 velocity pressure (a 45 m/s gust in open terrain) into a design
pressure on the broad 30 m by 22 m windward-plus-leeward face. The seismic side runs the equivalent
lateral force method: a stiff site (SDS = 1.0 g) on a moderately ductile frame (R = 6) draws a base
shear that is a flat fraction of the building's own weight. Here the earthquake wins comfortably —
the seismic base shear is several times the wind shear — because a heavy building on a
strong-shaking site is driven by its mass, not its sail area. The lesson is that wind scales with
exposed area and seismic with weight, so the governing hazard flips: light and broad favors wind,
heavy and compact favors seismic, and only running both tells you which.

Run it directly (``python examples/wind_vs_seismic_base_shear.py``);
:func:`lateral_demands` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    seismic_base_shear,
    seismic_response_coefficient,
    wind_design_pressure,
    wind_velocity_pressure,
)
from anvilate.units import Quantity

# Building.
SEISMIC_WEIGHT = Quantity.parse("40000 kN")
WINDWARD_FACE_AREA = Quantity.parse("660 m**2")  # 30 m wide x 22 m tall

# Wind (ASCE 7).
BASIC_WIND_SPEED = Quantity.parse("45 m/s")
EXPOSURE_COEFFICIENT = 1.0
GUST_FACTOR = 0.85
# Combined windward (+0.8) and leeward (-0.5) pressure coefficients act together.
NET_PRESSURE_COEFFICIENT = 0.8 + 0.5

# Seismic (ASCE 7 equivalent lateral force).
DESIGN_SPECTRAL_ACCELERATION = 1.0  # SDS, in g
RESPONSE_MODIFICATION = 6.0
IMPORTANCE_FACTOR = 1.0


def lateral_demands() -> dict[str, float]:
    """Return the wind and seismic base shears (kN) and which governs."""
    qz = wind_velocity_pressure(
        basic_wind_speed=BASIC_WIND_SPEED, exposure_coefficient=EXPOSURE_COEFFICIENT
    )
    pressure = wind_design_pressure(
        velocity_pressure=qz,
        gust_effect_factor=GUST_FACTOR,
        pressure_coefficient=NET_PRESSURE_COEFFICIENT,
    )
    wind_shear = pressure.to("Pa").magnitude * WINDWARD_FACE_AREA.to("m**2").magnitude / 1000.0

    cs = seismic_response_coefficient(
        design_spectral_acceleration=DESIGN_SPECTRAL_ACCELERATION,
        response_modification_factor=RESPONSE_MODIFICATION,
        importance_factor=IMPORTANCE_FACTOR,
    )
    seismic_shear = (
        seismic_base_shear(seismic_weight=SEISMIC_WEIGHT, response_coefficient=cs)
        .to("kN")
        .magnitude
    )

    return {
        "wind_shear_kn": wind_shear,
        "seismic_shear_kn": seismic_shear,
        "seismic_response_coefficient": cs,
    }


def main() -> None:
    d = lateral_demands()
    governing = "seismic" if d["seismic_shear_kn"] > d["wind_shear_kn"] else "wind"
    cs = d["seismic_response_coefficient"]
    print(f"wind base shear    : {d['wind_shear_kn']:.0f} kN")
    print(f"seismic base shear : {d['seismic_shear_kn']:.0f} kN (Cs = {cs:.3f})")
    print(f"  -> {governing} governs the lateral design")


if __name__ == "__main__":
    main()
