"""Worked example: the heat a steam pipe loses bare, and how much a lagging layer saves.

Heat leaving a pipe crosses two resistances in series: radial conduction through any insulation,
then convection off the outer surface into the room. This example takes a 100 mm steam pipe at
150°C in a 20°C plant and compares two states. Bare, the pipe meets only the outer-surface
convection, and sheds over 400 W for every metre of run. Wrapped in 50 mm of mineral-wool lagging
(k = 0.04 W/m·K), the radial conduction resistance dominates and the loss drops by nearly 90%. The
example also reports the critical insulation radius k/h — the radius below which a first insulation
layer would *increase* loss — to confirm the pipe is far above it, so the lagging only ever helps.

Run it directly (``python examples/insulated_steam_pipe_heat_loss.py``);
:func:`pipe_heat_loss` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    convection_thermal_resistance,
    critical_insulation_radius,
    cylindrical_conduction_resistance,
    series_thermal_resistance,
)
from anvilate.units import Quantity

PIPE_RADIUS = Quantity.parse("0.05 m")  # 100 mm OD
INSULATION_THICKNESS = Quantity.parse("0.05 m")
LENGTH = Quantity.parse("1 m")
INSULATION_K = Quantity.parse("0.04 W/(m*K)")
SURFACE_H = Quantity.parse("10 W/(m**2*K)")
DELTA_T = 130.0  # 150 degC pipe, 20 degC room


def _loss_watts(resistance_kw: float) -> float:
    return DELTA_T / resistance_kw


def pipe_heat_loss() -> dict[str, float]:
    """Return the bare and insulated heat loss per metre (W) and the critical radius (mm)."""
    import math

    r1 = PIPE_RADIUS.to("m").magnitude
    r2 = r1 + INSULATION_THICKNESS.to("m").magnitude

    bare_conv = convection_thermal_resistance(
        area=Quantity(magnitude=2 * math.pi * r1, unit="m**2"), heat_transfer_coefficient=SURFACE_H
    )
    bare = _loss_watts(bare_conv.to("K/W").magnitude)

    conduction = cylindrical_conduction_resistance(
        inner_radius=PIPE_RADIUS,
        outer_radius=Quantity(magnitude=r2, unit="m"),
        length=LENGTH,
        conductivity=INSULATION_K,
    )
    outer_conv = convection_thermal_resistance(
        area=Quantity(magnitude=2 * math.pi * r2, unit="m**2"), heat_transfer_coefficient=SURFACE_H
    )
    insulated_r = series_thermal_resistance(conduction, outer_conv)
    insulated = _loss_watts(insulated_r.to("K/W").magnitude)

    r_cr = critical_insulation_radius(
        conductivity=INSULATION_K, heat_transfer_coefficient=SURFACE_H
    )
    return {
        "bare_w_per_m": bare,
        "insulated_w_per_m": insulated,
        "reduction_percent": (1 - insulated / bare) * 100.0,
        "critical_radius_mm": r_cr.to("mm").magnitude,
    }


def main() -> None:
    p = pipe_heat_loss()
    print(f"bare pipe      : {p['bare_w_per_m']:.0f} W/m")
    print(f"50 mm lagging  : {p['insulated_w_per_m']:.0f} W/m ({p['reduction_percent']:.0f}% less)")
    print(
        f"critical radius: {p['critical_radius_mm']:.0f} mm (pipe is far above it — lagging helps)"
    )


if __name__ == "__main__":
    main()
