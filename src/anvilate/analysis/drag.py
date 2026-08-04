"""T1 analytical fluid-drag checks (drag force and terminal velocity, closed-form).

A body moving through a fluid — or a fluid moving past a body — feels a drag force that grows with
the square of the relative speed: F_d = ½·ρ·V²·C_d·A. The density ρ and the projected area A are
geometry; all the messy physics of the flow (separation, wake, whether it is streamlined or bluff)
is bundled into the dimensionless drag coefficient C_d, which the caller supplies from a table
(~1.2 for a flat plate or a sign, ~0.5 for a sphere, ~0.04 for an airfoil). This is the wind load
on a billboard or an antenna, the force on a submerged pipe in a current, the push on a vehicle.

When drag balances the driving force — a body falling under its own weight, a particle settling in
a tank — the speed stops rising at the terminal velocity, V_t = √(2·W/(ρ·C_d·A)), found by setting
the drag equal to the weight. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "drag_force",
    "jet_impact_force",
    "terminal_velocity",
]


def drag_force(
    *,
    density: Quantity,
    velocity: Quantity,
    drag_coefficient: float,
    reference_area: Quantity,
) -> Quantity:
    """The fluid drag force on a body, F_d = ½·ρ·V²·C_d·A.

    The force a fluid exerts on a body in relative motion: F_d = ½·ρ·V²·C_d·A, growing with the
    *square* of the relative ``velocity`` V. ``density`` ρ is the fluid density,
    ``drag_coefficient`` C_d the body's tabulated coefficient (~1.2 flat plate/sign, ~0.5 sphere,
    ~0.04 airfoil), and
    ``reference_area`` A its projected frontal area. This is the wind load on a sign or the current
    force on a submerged member — and because of the square, a 40% faster wind is nearly double the
    load. Returns the drag force in N.
    """
    _check(density, "[mass]/[length]**3", "density")
    _check(velocity, "[length]/[time]", "velocity")
    _check(reference_area, "[area]", "reference_area")
    rho = density.to("kg/m**3").magnitude
    v = velocity.to("m/s").magnitude
    a = reference_area.to("m**2").magnitude
    if rho <= 0 or a <= 0:
        raise ValueError("density and reference_area must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    if drag_coefficient <= 0:
        raise ValueError("drag_coefficient must be positive")
    return Quantity(magnitude=0.5 * rho * v**2 * drag_coefficient * a, unit="N")


def terminal_velocity(
    *,
    weight: Quantity,
    density: Quantity,
    drag_coefficient: float,
    reference_area: Quantity,
) -> Quantity:
    """The terminal velocity where drag balances the driving force, V_t = √(2·W/(ρ·C_d·A)).

    The steady speed a falling or settling body reaches once drag has grown to cancel the force
    driving it: set F_d = W in the drag law and solve, V_t = √(2·W/(ρ·C_d·A)). ``weight`` W is the
    net driving force (the body's weight, or its *submerged* weight for a particle settling in
    liquid), ``density`` ρ the fluid density, ``drag_coefficient`` C_d, and ``reference_area`` A.
    This is the settling velocity in a clarifier or the free-fall speed of a dropped object. Returns
    the terminal velocity in m/s.
    """
    _check(weight, "[force]", "weight")
    _check(density, "[mass]/[length]**3", "density")
    _check(reference_area, "[area]", "reference_area")
    w = weight.to("N").magnitude
    rho = density.to("kg/m**3").magnitude
    a = reference_area.to("m**2").magnitude
    if w <= 0 or rho <= 0 or a <= 0:
        raise ValueError("weight, density, and reference_area must be positive")
    if drag_coefficient <= 0:
        raise ValueError("drag_coefficient must be positive")
    return Quantity(magnitude=sqrt(2.0 * w / (rho * drag_coefficient * a)), unit="m/s")


def jet_impact_force(
    *,
    density: Quantity,
    flow_rate: Quantity,
    jet_velocity: Quantity,
    deflection_angle: float = 90.0,
) -> Quantity:
    """The force a fluid jet delivers to a surface it strikes, F = ρ·Q·V·(1 − cos θ).

    Where drag is the force a stream exerts on a body immersed *in* it, this is the force a confined
    jet delivers *to* a surface by giving up its momentum: F = ρ·Q·V·(1 − cos θ). ``density`` ρ,
    volumetric ``flow_rate`` Q, and ``jet_velocity`` V set the momentum flux ρ·Q·V, and
    ``deflection_angle`` θ is the angle the surface turns the jet through — 90° for a flat plate
    that spreads the jet sideways (F = ρQV, the default) and 180° for a bucket that reverses it
    (F = 2ρQV, the Pelton-wheel case that doubles the force). This is the reaction of a fire-hose
    nozzle,
    the thrust on a turbine bucket, or the kick of a cutting jet. Returns the force in N.
    """
    from math import cos, radians

    _check(density, "[mass]/[length]**3", "density")
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(jet_velocity, "[length]/[time]", "jet_velocity")
    rho = density.to("kg/m**3").magnitude
    q = flow_rate.to("m**3/s").magnitude
    v = jet_velocity.to("m/s").magnitude
    if rho <= 0 or q <= 0 or v <= 0:
        raise ValueError("density, flow_rate, and jet_velocity must be positive")
    if not 0.0 <= deflection_angle <= 180.0:
        raise ValueError(f"deflection_angle must be in [0, 180] degrees; got {deflection_angle}")
    return Quantity(magnitude=rho * q * v * (1.0 - cos(radians(deflection_angle))), unit="N")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
