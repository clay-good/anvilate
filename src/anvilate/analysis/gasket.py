"""T1 analytical bolted-flange gasket loads (ASME BPVC VIII-1 Appendix 2).

A bolted flange has to do two different jobs, and its bolts are sized for whichever needs
more force. First the gasket must be *seated* — crushed enough to conform to the flange
faces and form a seal — which takes a bolt load

    W_seat = π · b · G · y,

for the effective gasket seating width ``b``, the gasket mean (reaction-circle) diameter
``G``, and the gasket's seating stress ``y`` (a tabulated material property). Second, once
the vessel is pressurised, the bolts must still both react the hydrostatic end force that
tries to blow the flanges apart, H = (π/4)·G²·P, *and* keep a residual crush on the gasket
so it does not leak, H_p = 2·b·π·G·m·P, where ``m`` is the gasket maintenance factor
(also tabulated). Their sum is the operating bolt load

    W_op = (π/4)·G²·P + 2·b·π·G·m·P.

The joint is designed for the larger of the two: a low-pressure joint with a hard gasket is
governed by seating, a high-pressure joint by operation. The lesson these formulas encode
is that a leak is not an end-force problem alone — the bolts must out-pull the pressure
*and* keep the gasket squeezed.

The gasket factors ``m`` and ``y`` are the ASME Table 2-5.1 values the caller supplies
(dimensionless m; y a stress); every diameter, width, and pressure is a dimension-checked
:class:`~anvilate.units.Quantity`, and each load comes back as a force.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "gasket_seating_load",
    "gasket_operating_load",
    "governing_gasket_bolt_load",
]


def _positive_mm(value: Quantity, name: str) -> float:
    if not value.has_dimension("[length]"):
        raise ValueError(
            f"{name} must be a [length] quantity; got {value.dimensionality} ({value})"
        )
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def gasket_seating_load(
    *, gasket_mean_diameter: Quantity, effective_seating_width: Quantity, seating_stress: Quantity
) -> Quantity:
    """The bolt load W = π·b·G·y to seat (initially crush) a flange gasket.

    The force to crush the gasket onto the flange faces before pressure is applied:
    π·b·G·y for the ``gasket_mean_diameter`` G, ``effective_seating_width`` b, and the
    gasket's ``seating_stress`` y (ASME Table 2-5.1). All must be positive. Returns the
    load in N.
    """
    g = _positive_mm(gasket_mean_diameter, "gasket_mean_diameter")
    b = _positive_mm(effective_seating_width, "effective_seating_width")
    if not seating_stress.has_dimension("[pressure]"):
        raise ValueError(
            f"seating_stress must be a [pressure] quantity; got {seating_stress.dimensionality}"
        )
    y = seating_stress.to("MPa").magnitude
    if y <= 0:
        raise ValueError(f"seating_stress must be positive; got {seating_stress}")
    return Quantity(magnitude=pi * b * g * y, unit="N")


def gasket_operating_load(
    *,
    gasket_mean_diameter: Quantity,
    effective_seating_width: Quantity,
    gasket_factor: float,
    pressure: Quantity,
) -> Quantity:
    """The operating bolt load W = (π/4)·G²·P + 2·b·π·G·m·P of a pressurised flange.

    Under pressure the bolts carry the hydrostatic end force H = (π/4)·G²·P that tries
    to separate the flanges *plus* the residual gasket crush H_p = 2·b·π·G·m·P that keeps
    the joint tight, for a ``gasket_mean_diameter`` G, ``effective_seating_width`` b,
    ``gasket_factor`` m (ASME Table 2-5.1, dimensionless), and internal ``pressure`` P.
    All must be positive. Returns the load in N.
    """
    g = _positive_mm(gasket_mean_diameter, "gasket_mean_diameter")
    b = _positive_mm(effective_seating_width, "effective_seating_width")
    if gasket_factor <= 0:
        raise ValueError(f"gasket_factor must be positive; got {gasket_factor}")
    if not pressure.has_dimension("[pressure]"):
        raise ValueError(
            f"pressure must be a [pressure] quantity; got {pressure.dimensionality} ({pressure})"
        )
    p = pressure.to("MPa").magnitude
    if p <= 0:
        raise ValueError(f"pressure must be positive; got {pressure}")
    end_force = pi / 4.0 * g**2 * p
    gasket_reaction = 2.0 * b * pi * g * gasket_factor * p
    return Quantity(magnitude=end_force + gasket_reaction, unit="N")


def governing_gasket_bolt_load(
    *,
    gasket_mean_diameter: Quantity,
    effective_seating_width: Quantity,
    seating_stress: Quantity,
    gasket_factor: float,
    pressure: Quantity,
) -> Quantity:
    """The larger of the seating and operating bolt loads — what the bolts are sized for.

    A flange's bolts must satisfy both jobs, so the design load is
    max(:func:`gasket_seating_load`, :func:`gasket_operating_load`). A low-pressure joint
    with a hard gasket is seating-governed; a high-pressure one is operation-governed.
    Arguments as for the two component functions. Returns the governing load in N.
    """
    seating = gasket_seating_load(
        gasket_mean_diameter=gasket_mean_diameter,
        effective_seating_width=effective_seating_width,
        seating_stress=seating_stress,
    )
    operating = gasket_operating_load(
        gasket_mean_diameter=gasket_mean_diameter,
        effective_seating_width=effective_seating_width,
        gasket_factor=gasket_factor,
        pressure=pressure,
    )
    governing = max(seating.to("N").magnitude, operating.to("N").magnitude)
    return Quantity(magnitude=governing, unit="N")
