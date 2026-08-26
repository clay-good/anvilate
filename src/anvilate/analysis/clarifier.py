"""T1 analytical sedimentation-basin / clarifier hydraulic design (closed-form).

A settling tank does its work by slowing water down: give the flow enough time and a large enough
surface, and suspended particles settle out before they reach the outlet. Three hydraulic loadings
size that tank. This is the basin-scale companion to the particle-scale
:func:`anvilate.analysis.drag.stokes_settling_velocity` — the surface overflow rate here is exactly
the settling velocity a particle must beat to be captured.

The hydraulic retention time τ = V/Q is how long, on average, a parcel of water stays in a basin of
``volume`` V at ``flow_rate`` Q — the time available for settling or reaction. The surface overflow
rate (surface loading) SOR = Q/A is the flow divided by the basin's plan ``surface_area`` A; it has
units of velocity, and any particle whose settling velocity exceeds it is fully removed regardless
of where it enters — the classic overflow-rate design principle. The weir loading rate Q/L, the flow
over the effluent ``weir_length`` L, must stay low enough that the upward pull near the outlet does
not drag settled floc back over the weir. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Metcalf & Eddy, *Wastewater Engineering: Treatment and Resource Recovery* — the
hydraulic retention time of a basin, the surface overflow rate that sets its settling
performance, and the weir loading rate at its outlet.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "hydraulic_retention_time",
    "surface_overflow_rate",
    "weir_loading_rate",
]


def hydraulic_retention_time(*, volume: Quantity, flow_rate: Quantity) -> Quantity:
    """The hydraulic retention time, τ = V/Q.

    The mean time water spends in a basin, τ = ``volume`` V / ``flow_rate`` Q — the settling or
    reaction time the design provides. Too short and particles leave before they settle (or a
    reaction finishes); too long wastes tank volume. It is the same space-time τ = V/Q that sizes a
    flow reactor. Returns the retention time in hours.
    """
    _check(volume, "[volume]", "volume")
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    v = volume.to("m**3").magnitude
    q = flow_rate.to("m**3/hour").magnitude
    if v < 0:
        raise ValueError("volume must be non-negative")
    if q <= 0:
        raise ValueError("flow_rate must be positive")
    return Quantity(magnitude=v / q, unit="hour")


def surface_overflow_rate(*, flow_rate: Quantity, surface_area: Quantity) -> Quantity:
    """The surface overflow rate (surface loading), SOR = Q/A.

    The flow divided by the basin's plan ``surface_area`` A: SOR = ``flow_rate`` Q / A. Though it
    reads as a flow-per-area, it has the units of a velocity and is the critical settling velocity
    of the design — a particle whose settling velocity (e.g. from
    :func:`anvilate.analysis.drag.stokes_settling_velocity`) exceeds the SOR is captured no matter
    where it enters, while slower particles are only partly removed. Lowering it (a bigger surface)
    catches finer particles. Returns the overflow rate in m/day (m³/m²·day).
    """
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    _check(surface_area, "[area]", "surface_area")
    q = flow_rate.to("m**3/day").magnitude
    a = surface_area.to("m**2").magnitude
    if q < 0:
        raise ValueError("flow_rate must be non-negative")
    if a <= 0:
        raise ValueError("surface_area must be positive")
    return Quantity(magnitude=q / a, unit="m/day")


def weir_loading_rate(*, flow_rate: Quantity, weir_length: Quantity) -> Quantity:
    """The weir loading rate, Q/L.

    The effluent flow spread over the ``weir_length`` L: Q/L = ``flow_rate`` Q / L. A high weir
    loading means a strong upward draw of water near the outlet, which can carry settled or light
    floc back over the weir and into the effluent — so codes cap it (roughly 125–250 m³/m·day for
    settled water). A longer weir (or more launders) lowers it. Returns the weir loading in
    m²/day (m³/m·day).
    """
    _check(flow_rate, "[volume]/[time]", "flow_rate")
    _check(weir_length, "[length]", "weir_length")
    q = flow_rate.to("m**3/day").magnitude
    length = weir_length.to("m").magnitude
    if q < 0:
        raise ValueError("flow_rate must be non-negative")
    if length <= 0:
        raise ValueError("weir_length must be positive")
    return Quantity(magnitude=q / length, unit="m**2/day")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
