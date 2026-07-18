"""T1 analytical impact / shock-load amplification (energy method, closed-form).

A load dropped onto a structure, or applied suddenly rather than eased on, strains
it further than its dead weight would. Equating the work done by a weight W falling
a height h onto an elastic member to the strain energy stored at the peak
deflection gives the impact factor

    K = 1 + √(1 + 2·h/δ_st)

where δ_st is the static deflection the same weight makes when placed gently. The
peak deflection and every stress scale by K. Two limits are worth knowing: a load
lowered to rest (h = 0) still doubles the static values (K = 2 — the classic
"suddenly applied load is twice as bad as a static one"), and a large drop
(h ≫ δ_st) tends to K ≈ √(2·h/δ_st).

This is the standard Roark / Shigley energy-method estimate: it assumes a
linear-elastic member, no energy lost to local denting or damping, and the
striking mass staying with the member — so it is a conservative screen, not a
transient dynamic analysis. Inputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

# The impact factor for a load applied suddenly with no drop (h = 0): K = 2.
SUDDENLY_APPLIED_FACTOR = 2.0

__all__ = [
    "SUDDENLY_APPLIED_FACTOR",
    "impact_factor",
    "impact_stress",
    "horizontal_impact_force",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def impact_factor(*, drop_height: Quantity, static_deflection: Quantity) -> float:
    """The impact amplification factor K = 1 + √(1 + 2·h/δ_st).

    ``drop_height`` h is the distance the load falls before contact (0 for a load
    applied suddenly but from rest) and ``static_deflection`` δ_st the deflection
    the same weight produces when placed gently — from a beam, spring, or axial
    member deflection formula. The peak deflection and stress are K times their
    static values. ``drop_height`` must be a non-negative length and
    ``static_deflection`` a positive length. Returns the dimensionless K (never
    below 2, the suddenly-applied floor).
    """
    _require(drop_height, "[length]", "drop_height")
    _require(static_deflection, "[length]", "static_deflection")
    h = drop_height.to("mm").magnitude
    delta = static_deflection.to("mm").magnitude
    if h < 0:
        raise ValueError(f"drop_height must be non-negative; got {drop_height}")
    if delta <= 0:
        raise ValueError(f"static_deflection must be positive; got {static_deflection}")
    return 1.0 + sqrt(1.0 + 2.0 * h / delta)


def impact_stress(
    *,
    static_stress: Quantity,
    drop_height: Quantity,
    static_deflection: Quantity,
) -> Quantity:
    """The peak stress a dropped or suddenly-applied load makes, σ = K·σ_st.

    Multiplies the ``static_stress`` σ_st (the stress the load makes when placed
    gently) by the :func:`impact_factor` K for the same ``drop_height`` and
    ``static_deflection``. Screen this amplified stress — not the static one —
    against the material allowable for a dropped or shock load. ``static_stress``
    must be a stress. Returns the peak stress in MPa.
    """
    _require(static_stress, "[pressure]", "static_stress")
    k = impact_factor(drop_height=drop_height, static_deflection=static_deflection)
    return Quantity(magnitude=static_stress.to("MPa").magnitude * k, unit="MPa")


def horizontal_impact_force(*, mass: Quantity, velocity: Quantity, stiffness: Quantity) -> Quantity:
    """The peak force F = v·√(m·k) of a mass striking a spring end-on.

    A mass ``mass`` m moving at ``velocity`` v that runs into a stop of stiffness
    ``stiffness`` k — a carriage hitting a bumper, a load swinging into an arrest —
    has no gravitational drop; its kinetic energy ½·m·v² all goes into the spring.
    Equating ½·m·v² = ½·k·δ_max² gives the peak deflection δ_max = v·√(m/k) and the
    peak force F = k·δ_max = v·√(m·k). This is the horizontal (energy-from-motion)
    counterpart to the drop-height :func:`impact_factor` — the force rises with the
    *square root* of the stiffness, so a softer stop (lower k) cushions the blow. All
    three must be positive. Returns the peak arresting force in newtons.
    """
    _require(mass, "[mass]", "mass")
    _require(velocity, "[velocity]", "velocity")
    _require(stiffness, "[force] / [length]", "stiffness")
    m = mass.to("kg").magnitude
    v = velocity.to("m/s").magnitude
    k = stiffness.to("N/m").magnitude
    if m <= 0:
        raise ValueError(f"mass must be positive; got {mass}")
    if v <= 0:
        raise ValueError(f"velocity must be positive; got {velocity}")
    if k <= 0:
        raise ValueError(f"stiffness must be positive; got {stiffness}")
    return Quantity(magnitude=v * sqrt(m * k), unit="N")
