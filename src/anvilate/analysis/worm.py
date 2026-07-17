"""T1 analytical worm-drive mechanics (closed-form, Shigley ch. 13).

A worm drive is a screw (the worm) meshing with a gear wheel — the machine-element
cousin of the power screw, and it self-locks for the same reason. Its two defining
numbers are the huge single-mesh reduction and the lead angle that governs both
efficiency and whether the wheel can back-drive the worm.

The velocity ratio is set by the counts alone: m_G = N_G/N_W, the wheel teeth over
the worm's thread *starts* — a single-start worm on a 40-tooth wheel reduces 40:1 in
one mesh. The worm's lead is L = N_W·p_x (axial pitch × starts), and its lead angle
follows from wrapping that lead around the worm pitch diameter,

    tan λ = L / (π·d_W).

Driving from the worm, the mesh efficiency is

    η = (cos φ_n − μ·tan λ) / (cos φ_n + μ·cot λ)

with φ_n the normal pressure angle and μ the tooth friction. As with a power screw,
the set is *self-locking* — the wheel cannot turn the worm — when friction beats the
lead, μ ≥ cos φ_n·tan λ (the pressure-angle-corrected mirror of the screw's
μ ≥ tan λ). Self-locking worms run at low efficiency, the price of holding load
without a brake. These forms exclude thrust-bearing friction (add it separately).
Diameters/pitches are dimension-checked :class:`~anvilate.units.Quantity` values;
angles are plain degree floats, μ a dimensionless coefficient the user supplies.
"""

from __future__ import annotations

from math import atan2, cos, degrees, pi, radians, tan

from ..units import Quantity

__all__ = [
    "worm_gear_ratio",
    "worm_lead_angle",
    "worm_gear_efficiency",
    "worm_is_self_locking",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _check_starts(worm_starts: int) -> int:
    whole = int(worm_starts)
    if whole != worm_starts or whole <= 0:
        raise ValueError(f"worm_starts must be a positive whole number; got {worm_starts}")
    return whole


def _check_gear_teeth(gear_teeth: int) -> int:
    whole = int(gear_teeth)
    if whole != gear_teeth or whole <= 0:
        raise ValueError(f"gear_teeth must be a positive whole number; got {gear_teeth}")
    return whole


def _check_lead_angle(lead_angle: float) -> float:
    if not 0 < lead_angle < 90:
        raise ValueError(f"lead_angle (degrees) must lie in (0, 90); got {lead_angle}")
    return radians(lead_angle)


def _check_pressure_angle(normal_pressure_angle: float) -> float:
    if not 0 <= normal_pressure_angle < 90:
        raise ValueError(
            f"normal_pressure_angle (degrees) must lie in [0, 90); got {normal_pressure_angle}"
        )
    return radians(normal_pressure_angle)


def _check_friction(friction_coefficient: float) -> float:
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    return friction_coefficient


def worm_gear_ratio(*, worm_starts: int, gear_teeth: int) -> float:
    """The worm-drive velocity (reduction) ratio m_G = N_G/N_W.

    Unlike a spur mesh, the worm's *lead* — not its diameter — sets the ratio, so
    a small single-start worm drives a large reduction: the wheel turns once per
    N_G/N_W worm turns. ``worm_starts`` N_W is the number of thread starts on the
    worm (1, 2, 3, … — a single start gives the deepest reduction and best chance
    of self-locking) and ``gear_teeth`` N_G the wheel's tooth count; both are
    positive whole numbers. Returns the dimensionless reduction ratio.
    """
    starts = _check_starts(worm_starts)
    teeth = _check_gear_teeth(gear_teeth)
    return teeth / starts


def worm_lead_angle(
    *, worm_starts: int, axial_pitch: Quantity, worm_pitch_diameter: Quantity
) -> float:
    """The worm's lead angle λ = atan(L/(π·d_W)), L = N_W·p_x.

    The lead L is the axial distance the worm thread advances per revolution —
    the number of ``worm_starts`` N_W times the ``axial_pitch`` p_x — and the lead
    angle is that lead wrapped around the ``worm_pitch_diameter`` d_W. A small
    lead angle means a fine, self-locking worm; a large one a fast, efficient,
    back-drivable one. ``axial_pitch`` and ``worm_pitch_diameter`` are positive
    lengths, ``worm_starts`` a positive whole number. Returns λ in **degrees**,
    ready for :func:`worm_gear_efficiency` and :func:`worm_is_self_locking`.
    """
    starts = _check_starts(worm_starts)
    _require(axial_pitch, "[length]", "axial_pitch")
    _require(worm_pitch_diameter, "[length]", "worm_pitch_diameter")
    px = axial_pitch.to("mm").magnitude
    dw = worm_pitch_diameter.to("mm").magnitude
    if px <= 0:
        raise ValueError(f"axial_pitch must be positive; got {axial_pitch}")
    if dw <= 0:
        raise ValueError(f"worm_pitch_diameter must be positive; got {worm_pitch_diameter}")
    lead = starts * px
    return degrees(atan2(lead, pi * dw))


def worm_gear_efficiency(
    *,
    lead_angle: float,
    friction_coefficient: float,
    normal_pressure_angle: float = 14.5,
) -> float:
    """The worm-driving mesh efficiency η = (cos φ_n − μ tan λ)/(cos φ_n + μ cot λ).

    The fraction of input power the worm delivers to the wheel, lost mostly to the
    sliding friction of the screw-like tooth contact. ``lead_angle`` λ (degrees,
    from :func:`worm_lead_angle`), ``friction_coefficient`` μ, and
    ``normal_pressure_angle`` φ_n (degrees, default 14.5° — the common worm value;
    also 20°/25°/30° for steeper leads) describe the mesh. A frictionless mesh
    (μ = 0) returns 1.0; efficiency climbs with lead angle, which is why
    multi-start worms drive harder but self-lock less. Returns the dimensionless
    η in (0, 1].
    """
    lam = _check_lead_angle(lead_angle)
    mu = _check_friction(friction_coefficient)
    phi_n = _check_pressure_angle(normal_pressure_angle)
    numerator = cos(phi_n) - mu * tan(lam)
    denominator = cos(phi_n) + mu / tan(lam)
    return numerator / denominator


def worm_is_self_locking(
    *,
    lead_angle: float,
    friction_coefficient: float,
    normal_pressure_angle: float = 14.5,
) -> bool:
    """Whether the wheel cannot back-drive the worm: μ ≥ cos φ_n·tan λ.

    A worm drive holds its load without a brake when the tooth friction beats the
    lead — the pressure-angle-corrected mirror of the power screw's μ ≥ tan λ.
    ``lead_angle`` λ, ``friction_coefficient`` μ, and ``normal_pressure_angle``
    φ_n are as in :func:`worm_gear_efficiency`. Fine single-start worms self-lock
    (hoists, holding fixtures); coarse multi-start ones back-drive. Returns True
    when the set is self-locking.
    """
    lam = _check_lead_angle(lead_angle)
    mu = _check_friction(friction_coefficient)
    phi_n = _check_pressure_angle(normal_pressure_angle)
    return mu >= cos(phi_n) * tan(lam)
