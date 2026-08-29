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

Sources: ISO 6020/6022 for the cylinder series, and standard
fluid-power relations (force = pressure x area, speed = flow / area) as given in the
*Fluid Power Handbook*.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity, require_finite

__all__ = [
    "cylinder_extend_force",
    "cylinder_retract_force",
    "cylinder_extend_speed",
    "cylinder_retract_speed",
    "cylinder_regen_extend_force",
    "cylinder_regen_extend_speed",
    "cylinder_rodside_intensified_pressure",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


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
    if not isinstance(flow_rate, Quantity):
        raise ValueError(f"flow_rate must be a [length]**3 / [time] quantity; got {flow_rate!r}")
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
    if not isinstance(flow_rate, Quantity):
        raise ValueError(f"flow_rate must be a [length]**3 / [time] quantity; got {flow_rate!r}")
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


def cylinder_regen_extend_force(
    *, pressure: Quantity, rod_diameter: Quantity, bore_diameter: Quantity
) -> Quantity:
    """The regenerative-circuit extend force F = p·(π/4)·d² of a fluid cylinder.

    In a regeneration (differential) circuit the rod-side oil is routed back to join the pump
    flow into the cap side, so supply pressure acts on *both* faces of the piston. The two
    thrusts cancel over the annulus and the net extend force is just pressure over the rod's own
    cross-section: ``pressure`` p times (π/4)·``rod_diameter``². That is far less than the normal
    :func:`cylinder_extend_force`, the price paid for the speed that
    :func:`cylinder_regen_extend_speed` buys — a differential circuit is for a fast, light approach
    stroke, not for pushing the load.
    ``bore_diameter`` D is required only to check the rod fits (d < D). Returns the force in kN.
    """
    _require(pressure, "[pressure]", "pressure")
    p = pressure.to("MPa").magnitude
    bore = _bore(bore_diameter)
    rod = _rod(rod_diameter, bore)
    if p <= 0:
        raise ValueError(f"pressure must be positive; got {pressure}")
    force_n = p * pi / 4.0 * rod**2  # MPa*mm^2 = N; net force acts over the rod area
    return Quantity(magnitude=force_n / 1000.0, unit="kN")


def cylinder_regen_extend_speed(
    *, flow_rate: Quantity, rod_diameter: Quantity, bore_diameter: Quantity
) -> Quantity:
    """The regenerative-circuit extend speed v = Q/(π/4·d²) of a fluid cylinder.

    With the rod-side oil fed back into the cap side, the pump only has to supply the difference
    between the two sides — the rod's cross-section area — so the piston extends as if filling
    just (π/4)·``rod_diameter``²: ``flow_rate`` Q over that small area. The rod moves much *faster*
    than the normal :func:`cylinder_extend_speed` (the smaller the rod, the bigger the gain), at
    the cost of the reduced :func:`cylinder_regen_extend_force`. ``bore_diameter`` D is required
    only to check the rod fits (d < D). Returns the speed in mm/s.
    """
    if not isinstance(flow_rate, Quantity):
        raise ValueError(f"flow_rate must be a [length]**3 / [time] quantity; got {flow_rate!r}")
    if not flow_rate.has_dimension("[length]**3 / [time]"):
        raise ValueError(
            f"flow_rate must be a volume/time quantity; got {flow_rate.dimensionality}"
        )
    q = flow_rate.to("mm**3/s").magnitude
    bore = _bore(bore_diameter)
    rod = _rod(rod_diameter, bore)
    if q <= 0:
        raise ValueError(f"flow_rate must be positive; got {flow_rate}")
    return Quantity(magnitude=q / (pi / 4.0 * rod**2), unit="mm/s")


def cylinder_rodside_intensified_pressure(
    *, supply_pressure: Quantity, bore_diameter: Quantity, rod_diameter: Quantity
) -> Quantity:
    """The rod-side pressure p·D²/(D² − d²) a driven, blocked cylinder intensifies to.

    A cylinder pressurised on the bore side while its rod-side flow is restricted or blocked
    (a meter-out circuit, a stalled retract, a regeneration deadhead) traps the rod-side oil,
    and force balance across the piston raises its pressure by the *area ratio*: the same
    force acts over the smaller annular area, so p_rod = ``supply_pressure``·D²/(D² − d²) for
    ``bore_diameter`` D and ``rod_diameter`` d. A small rod barely intensifies; a fat rod can
    double or triple the pressure. This is the over-pressure that bursts a rod-side seal or
    hose rated only for the supply — check it against their rating, not the pump pressure.
    All inputs must be positive and d < D. Returns the intensified pressure in the supply's
    pressure units.
    """
    if not isinstance(supply_pressure, Quantity):
        raise ValueError(f"supply_pressure must be a [pressure] quantity; got {supply_pressure!r}")
    if not supply_pressure.has_dimension("[pressure]"):
        raise ValueError(
            f"supply_pressure must be a [pressure] quantity; got {supply_pressure.dimensionality}"
        )
    p = supply_pressure.to("MPa").magnitude
    bore = _bore(bore_diameter)
    rod = _rod(rod_diameter, bore)
    if p <= 0:
        raise ValueError(f"supply_pressure must be positive; got {supply_pressure}")
    intensified = p * bore**2 / (bore**2 - rod**2)
    return Quantity(magnitude=intensified, unit="MPa")
