"""T1 analytical HVAC duct sizing checks (closed-form).

Air-distribution design turns a required airflow into a duct size and the fan power to push it, and
two relations do most of the work.

Ducts are usually run rectangular to fit above ceilings, but friction charts are drawn for round
duct, so a rectangular duct is sized through its *circular equivalent* — the round duct that carries
the same airflow at the same friction loss. ASHRAE's fit is D_e = 1.30·(a·b)^0.625/(a+b)^0.25, from
the duct's side dimensions a and b. (This is not the hydraulic diameter 4A/P; it is larger, because
equal *friction* is a different condition than equal cross-section.)

The power a fan must deliver is the airflow times the pressure it must develop, divided by how
efficiently the fan turns shaft power into air power: P = Q·Δp/η, from the volume ``flow_rate`` Q,
the ``total_pressure`` Δp the system needs (the summed duct and fitting losses), and the
``fan_efficiency`` η. The efficiency is the caller's from the fan curve; the arithmetic is here.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "circular_equivalent_diameter",
    "fan_power",
]


def circular_equivalent_diameter(*, width: Quantity, height: Quantity) -> Quantity:
    """The round duct equal in friction to a rectangular one, D_e = 1.30·(a·b)^0.625/(a+b)^0.25.

    The diameter of the round duct that carries the same airflow at the same friction loss as a
    rectangular duct of sides ``width`` a and ``height`` b (ASHRAE's fit): D_e =
    1.30·(a·b)^0.625/(a+b)^0.25. Use it to read a round-duct friction chart for a rectangular run.
    It is larger than the hydraulic diameter 4A/P, because matching friction is a stricter condition
    than matching cross-section. Returns the equivalent diameter as a length.
    """
    _check(width, "[length]", "width")
    _check(height, "[length]", "height")
    a = width.to("m").magnitude
    b = height.to("m").magnitude
    if a <= 0 or b <= 0:
        raise ValueError("width and height must be positive")
    d_e = 1.30 * (a * b) ** 0.625 / (a + b) ** 0.25
    return Quantity(magnitude=d_e, unit="m")


def fan_power(
    *,
    flow_rate: Quantity,
    total_pressure: Quantity,
    fan_efficiency: float,
) -> Quantity:
    """The shaft power a fan needs, P = Q·Δp/η.

    The air power a fan delivers is the volume ``flow_rate`` Q times the ``total_pressure`` Δp it
    develops (the sum of the system's duct and fitting losses); dividing by the ``fan_efficiency`` η
    gives the shaft power the motor must supply: P = Q·Δp/η. Because the pressure a duct system
    needs rises with the square of the flow, oversizing the airflow is costly in fan power. Returns
    the shaft power in watts.
    """
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(total_pressure, "[pressure]", "total_pressure")
    if flow_rate.to("m**3/s").magnitude <= 0:
        raise ValueError("flow_rate must be positive")
    if total_pressure.to("Pa").magnitude <= 0:
        raise ValueError("total_pressure must be positive")
    if not 0.0 < fan_efficiency <= 1.0:
        raise ValueError(f"fan_efficiency must be in (0, 1]; got {fan_efficiency}")
    power = flow_rate.pint * total_pressure.pint / fan_efficiency
    return Quantity(magnitude=float(power.to("W").magnitude), unit="W")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
