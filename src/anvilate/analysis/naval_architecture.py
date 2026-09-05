"""T1 analytical naval-architecture (displacement-hull) checks (closed-form).

A displacement hull pushes through the water rather than planing over it, and its own bow and stern
waves set a speed it cannot economically exceed. A few closed forms size the hull and its speed —
the marine companion to the buoyancy and stability of :mod:`anvilate.analysis.fluid_statics` (which
gives the metacentric height this speed-and-shape work sits alongside).

A hull moving at speed v makes a wave train of wavelength λ = 2π·v²/g. When that wavelength grows to
the waterline length, the hull sits in the trough of its own wave and wave-making drag climbs
steeply — the hull speed v = √(g·L/(2π)), the practical ceiling of a displacement hull (about
1.34·√(L_ft) in knots). The dimensionless speed is the Froude number Fr = v/√(g·L), and hull speed
is simply Fr ≈ 0.4. How full the underwater body is is the block coefficient C_b = ∇/(L·B·T), the
displaced volume over its bounding box — low for a fine, fast hull, high for a bluff, roomy one.
Speeds, lengths, and volumes are dimension-checked :class:`~anvilate.units.Quantity` values; the
Froude number and block coefficient are plain floats.

Sources: Tupper, *Introduction to Naval Architecture* — the hull speed and Froude number of a
displacement hull, the block coefficient, and the roll period from the metacentric height. The
friction line is the ITTC-1957 model-ship correlation line, cited in the function that uses it.
"""

from __future__ import annotations

from math import log10, pi, sqrt

from ..units import Quantity

_STANDARD_GRAVITY = 9.80665  # m/s**2

__all__ = [
    "ittc_friction_coefficient",
    "hull_speed",
    "hull_froude_number",
    "block_coefficient",
    "roll_period",
]


def hull_speed(*, waterline_length: Quantity) -> Quantity:
    """The displacement hull speed, v = √(g·L/(2π)).

    The speed at which a displacement hull's bow wave grows to its own waterline length and
    wave-making drag climbs steeply — the practical top speed of a non-planing hull:
    v = √(g·L/(2π)), from the ``waterline_length`` L. It is the ~1.34·√(L_ft)-knots rule of thumb
    in closed form, and it is why a longer boat is a faster boat: hull speed rises with the square
    root of length. Pushing past it takes disproportionate power (or planing). Returns the hull
    speed in m/s.
    """
    _check(waterline_length, "[length]", "waterline_length")
    length = waterline_length.to("m").magnitude
    if length <= 0:
        raise ValueError("waterline_length must be positive")
    return Quantity(magnitude=sqrt(_STANDARD_GRAVITY * length / (2.0 * pi)), unit="m/s")


def hull_froude_number(*, speed: Quantity, waterline_length: Quantity) -> float:
    """The hull Froude number, Fr = v/√(g·L).

    The dimensionless speed of a hull — the ratio of inertial to gravity (wave) forces — that sets
    its wave-making behaviour and lets model tests scale to full size: Fr = ``speed`` v / √(g ·
    ``waterline_length`` L). A displacement hull runs efficiently below Fr ≈ 0.4 (its
    :func:`hull_speed` corresponds to Fr ≈ 0.4); a semi-displacement hull works the 0.4–1.0 hump,
    and a planing hull lifts clear above ~1.0. Two hulls at the same Froude number make
    geometrically similar wave systems. Both inputs must be positive. Returns the Froude number.
    """
    _check(speed, "[velocity]", "speed")
    _check(waterline_length, "[length]", "waterline_length")
    v = speed.to("m/s").magnitude
    length = waterline_length.to("m").magnitude
    if v < 0:
        raise ValueError("speed must be non-negative")
    if length <= 0:
        raise ValueError("waterline_length must be positive")
    return v / sqrt(_STANDARD_GRAVITY * length)


def block_coefficient(
    *,
    displacement_volume: Quantity,
    waterline_length: Quantity,
    beam: Quantity,
    draft: Quantity,
) -> float:
    """The hull block coefficient, C_b = ∇/(L·B·T).

    How completely the hull fills the rectangular box that bounds its underwater body: the
    ``displacement_volume`` ∇ (the volume of water the hull displaces) over the product of the
    ``waterline_length`` L, the ``beam`` B, and the ``draft`` T — C_b = ∇/(L·B·T). A fine, fast hull
    (a destroyer, a racing yacht) runs a low C_b around 0.4–0.55; a full, capacious hull (a tanker,
    a barge) approaches 0.8–0.9, trading speed for cargo volume. It is the headline shape parameter
    of a hull form. All inputs must be positive, and the result must not exceed 1 (the hull cannot
    displace more than its bounding box). Returns the dimensionless block coefficient.
    """
    _check(displacement_volume, "[volume]", "displacement_volume")
    _check(waterline_length, "[length]", "waterline_length")
    _check(beam, "[length]", "beam")
    _check(draft, "[length]", "draft")
    vol = displacement_volume.to("m**3").magnitude
    length = waterline_length.to("m").magnitude
    b = beam.to("m").magnitude
    t = draft.to("m").magnitude
    if vol <= 0:
        raise ValueError("displacement_volume must be positive")
    if length <= 0 or b <= 0 or t <= 0:
        raise ValueError("waterline_length, beam, and draft must be positive")
    c_b = vol / (length * b * t)
    if c_b > 1.0:
        raise ValueError(
            "block coefficient exceeds 1: the displacement volume is larger than L*B*T "
            "(check the inputs)"
        )
    return c_b


def roll_period(*, roll_radius_of_gyration: Quantity, metacentric_height: Quantity) -> Quantity:
    """A vessel's natural roll period, T = 2π·k/√(g·GM).

    A ship rolling about its long axis is a pendulum: the righting moment restores it and its
    rotational inertia resists, giving T = 2π·k/√(g·GM) from the ``roll_radius_of_gyration`` k
    about the roll axis (typically 0.35-0.40 of the beam) and the ``metacentric_height`` GM that
    :func:`anvilate.analysis.fluid_statics.metacentric_height` computes.

    GM is the stability number, but it is not free: it appears under a square root in the
    denominator, so a stiff ship — large GM, very stable in the naval-architecture sense — has a
    *short* roll period and snaps back violently, which is punishing for crew, cargo lashings, and
    deck equipment. A tender ship with small GM rolls slowly and comfortably but has less reserve
    to right itself. Choosing GM is therefore choosing a roll period, and the comfort criterion
    usually binds before the stability one. It also names the wave-encounter period to avoid:
    a seaway that matches T rolls the ship in resonance. Returns the roll period in seconds.
    """
    _check(roll_radius_of_gyration, "[length]", "roll_radius_of_gyration")
    _check(metacentric_height, "[length]", "metacentric_height")
    k = roll_radius_of_gyration.to("m").magnitude
    gm = metacentric_height.to("m").magnitude
    if k <= 0:
        raise ValueError("roll_radius_of_gyration must be positive")
    if gm <= 0:
        raise ValueError("metacentric_height must be positive (a negative GM is unstable)")
    return Quantity(magnitude=2.0 * pi * k / sqrt(_STANDARD_GRAVITY * gm), unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def ittc_friction_coefficient(*, reynolds_number: float) -> float:
    """The ITTC-1957 friction line, C_F = 0.075/(log₁₀(Re) − 2)².

    The skin-friction coefficient of a ship hull, from the ``reynolds_number`` Re built on the
    waterline length. The module gives hull speed, Froude number, and block coefficient — all of
    them the wave-making side of resistance — and had nothing for the viscous side, which is 70 to
    80 percent of a slow ship's drag and therefore most of the installed power.

    Froude's insight is that hull resistance splits into a frictional part scaling with Reynolds
    number and a residuary part scaling with Froude number; this correlation line is the
    frictional half, fitted to towing-tank plank data and used to scale model results to full
    size. A 100 m waterline at 15 knots runs Re = 6.5×10⁸ and C_F = 0.00162, so with 2500 m² of
    wetted surface the friction alone is 123 kN — about 950 kW of effective power before any
    wave-making at all.

    It sits deliberately a few percent above a true flat-plate line (compare
    :func:`anvilate.analysis.boundary_layer.turbulent_plate_drag_coefficient` at the same Re),
    because the correlation absorbs some three-dimensional form effect; that offset is a feature
    of the standard, not an error. Multiply by the dynamic pressure and the wetted surface to get
    the frictional resistance.

    The correlation has a pole at Re = 10², where log₁₀Re − 2 vanishes, and returns absurd values
    on the way there — 4×10¹⁷ just above it, 4016 at Re = 101 — so the guard sits at Re = 10⁵
    instead. That is the low end of the towing-tank data the line was fitted to; below it the flow
    is not the fully turbulent boundary layer the line describes, and any real hull or model runs
    Re ≥ 10⁶ anyway. Returns the friction coefficient as a plain float.

    Source: Tupper, *Introduction to Naval Architecture*, the ITTC-1957 correlation line.
    """
    if reynolds_number < 1.0e5:
        raise ValueError(
            f"reynolds_number must be at least 1e5 for the ITTC-57 correlation, which is fitted "
            f"to turbulent plank data and blows up toward its pole at Re = 100; "
            f"got {reynolds_number}"
        )
    return 0.075 / (log10(reynolds_number) - 2.0) ** 2
