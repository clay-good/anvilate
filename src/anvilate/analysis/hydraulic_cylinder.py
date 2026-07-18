"""T1 analytical hydraulic/pneumatic cylinder actuator sizing (closed-form).

A fluid cylinder converts pressure into linear thrust, the fluid-power cousin of the power
screw. Its defining asymmetry is the rod: the piston has full bore area on the cap side but
only the annular area (bore minus rod) on the rod side, so a cylinder pushes harder and
slower than it pulls. For a bore diameter D, rod diameter d, and supply pressure p,

    F_extend  = p · (π/4)·D²          (full bore area),
    F_retract = p · (π/4)·(D² − d²)   (annular area),

and for a volumetric flow Q the piston speed is the flow divided by the area it fills, so the
same pump extends the rod slowly and retracts it faster (less area to fill):

    v_extend  = Q / (π/4·D²),   v_retract = Q / (π/4·(D² − d²)).

The rod steals both force and volume on the retract stroke, which is why a cylinder is sized
on its *extend* force (the weaker-per-area but larger-area stroke usually does the work) and
why its retract stroke is quicker — the fact behind the regeneration circuit and behind sizing
a cylinder for the direction that actually pushes the load. These are exact for a frictionless
cylinder; a real one loses a few percent to seal friction. Pressure, diameters, and flow are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "cylinder_extend_force",
    "cylinder_retract_force",
    "cylinder_extend_speed",
    "cylinder_retract_speed",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _bore(bore_diameter: Quantity) -> float:
    _require(bore_diameter, "[length]", "bore_diameter")
    d = bore_diameter.to("mm").magnitude
    if d <= 0:
        raise ValueError(f"bore_diameter must be positive; got {bore_diameter}")
    return d


def _rod(rod_diameter: Quantity, bore_mm: float) -> float:
    _require(rod_diameter, "[length]", "rod_diameter")
    d = rod_diameter.to("mm").magnitude
    if d <= 0:
        raise ValueError(f"rod_diameter must be positive; got {rod_diameter}")
    if d >= bore_mm:
        raise ValueError(
            f"rod_diameter ({rod_diameter}) must be smaller than the bore ({bore_mm} mm)"
        )
    return d


def cylinder_extend_force(*, pressure: Quantity, bore_diameter: Quantity) -> Quantity:
    """The extend (push) force F = p·(π/4)·D² of a fluid cylinder.

    The thrust on the cap side, where the piston presents its full bore area:
    ``pressure`` p over (π/4)·``bore_diameter``². This is the larger stroke force and the
    one a cylinder is usually sized on. Both inputs must be positive. Returns the force in kN.
    """
    _require(pressure, "[pressure]", "pressure")
    p = pressure.to("MPa").magnitude
    d = _bore(bore_diameter)
    if p <= 0:
        raise ValueError(f"pressure must be positive; got {pressure}")
    force_n = p * pi / 4.0 * d**2  # MPa*mm^2 = N
    return Quantity(magnitude=force_n / 1000.0, unit="kN")


def cylinder_retract_force(
    *, pressure: Quantity, bore_diameter: Quantity, rod_diameter: Quantity
) -> Quantity:
    """The retract (pull) force F = p·(π/4)·(D² − d²) of a fluid cylinder.

    The thrust on the rod side, where the rod steals its own area from the bore, so the
    force acts over the annulus (π/4)·(D² − d²): ``pressure`` p, ``bore_diameter`` D, and
    ``rod_diameter`` d (which must be smaller than the bore). Always less than the extend
    force. Returns the force in kN.
    """
    _require(pressure, "[pressure]", "pressure")
    p = pressure.to("MPa").magnitude
    bore = _bore(bore_diameter)
    rod = _rod(rod_diameter, bore)
    if p <= 0:
        raise ValueError(f"pressure must be positive; got {pressure}")
    force_n = p * pi / 4.0 * (bore**2 - rod**2)
    return Quantity(magnitude=force_n / 1000.0, unit="kN")


def cylinder_extend_speed(*, flow_rate: Quantity, bore_diameter: Quantity) -> Quantity:
    """The extend speed v = Q/(π/4·D²) of a fluid cylinder at a supply ``flow_rate``.

    The rod extends as fast as the pump fills the full bore area: ``flow_rate`` Q over
    (π/4)·``bore_diameter``². Both must be positive. Returns the speed in mm/s.
    """
    if not flow_rate.has_dimension("[length]**3 / [time]"):
        raise ValueError(
            f"flow_rate must be a volume/time quantity; got {flow_rate.dimensionality}"
        )
    q = flow_rate.to("mm**3/s").magnitude
    d = _bore(bore_diameter)
    if q <= 0:
        raise ValueError(f"flow_rate must be positive; got {flow_rate}")
    return Quantity(magnitude=q / (pi / 4.0 * d**2), unit="mm/s")


def cylinder_retract_speed(
    *, flow_rate: Quantity, bore_diameter: Quantity, rod_diameter: Quantity
) -> Quantity:
    """The retract speed v = Q/(π/4·(D² − d²)) of a fluid cylinder.

    The rod side has less area to fill, so the same ``flow_rate`` Q retracts the rod
    *faster* than it extends: Q over the annulus (π/4)·(D² − d²) for ``bore_diameter`` D
    and ``rod_diameter`` d (smaller than the bore). Returns the speed in mm/s.
    """
    if not flow_rate.has_dimension("[length]**3 / [time]"):
        raise ValueError(
            f"flow_rate must be a volume/time quantity; got {flow_rate.dimensionality}"
        )
    q = flow_rate.to("mm**3/s").magnitude
    bore = _bore(bore_diameter)
    rod = _rod(rod_diameter, bore)
    if q <= 0:
        raise ValueError(f"flow_rate must be positive; got {flow_rate}")
    return Quantity(magnitude=q / (pi / 4.0 * (bore**2 - rod**2)), unit="mm/s")
