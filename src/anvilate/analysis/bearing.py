"""T1 analytical rolling-bearing life (ISO 281 basic rating life, closed-form).

A rolling bearing does not have a static strength limit so much as a *life*: run
long enough under load and its raceways spall by rolling-contact fatigue. The
ISO 281 basic rating life L10 — the life 90% of a population reaches before the
first spall — follows a simple power law in the load,

    L10 = (C/P)^p   [millions of revolutions]

where C is the bearing's *dynamic load rating* (the load giving one million
revolutions of L10, a catalogue value), P the equivalent dynamic load actually
carried, and p the life exponent: 3 for ball bearings, 10/3 for roller bearings.
Expressed as running hours at a shaft speed n, L10h = (10⁶/60·n)·(C/P)^p.

The dynamic load rating C is manufacturer- and design-specific, so — like a
material allowable — it is supplied as an argument, not read from the standards
:class:`~anvilate.standards.Bearing` table (which carries only ISO 15 boundary
dimensions). As with the other checks, force and speed inputs are dimension-checked
:class:`~anvilate.units.Quantity` values through Pint.
"""

from __future__ import annotations

from math import log

from ..units import Quantity

# ISO 281 life exponents: the load-life power law L10 = (C/P)^p.
BALL_BEARING_LIFE_EXPONENT = 3.0
ROLLER_BEARING_LIFE_EXPONENT = 10.0 / 3.0

# Weibull dispersion exponent for rolling-bearing life scatter (ISO 281): the
# reliability-adjustment a1 = (ln(1/R)/ln(1/0.90))^(1/e) with e ≈ 1.5 reproduces the
# standard a1 table (0.62 at 95%, 0.21 at 99%).
BEARING_WEIBULL_SLOPE = 1.5

__all__ = [
    "BALL_BEARING_LIFE_EXPONENT",
    "ROLLER_BEARING_LIFE_EXPONENT",
    "BEARING_WEIBULL_SLOPE",
    "bearing_basic_rating_life",
    "bearing_life_hours",
    "bearing_static_safety_factor",
    "bearing_equivalent_dynamic_load",
    "bearing_reliability_life_factor",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def bearing_basic_rating_life(
    *,
    dynamic_load_rating: Quantity,
    equivalent_load: Quantity,
    life_exponent: float = BALL_BEARING_LIFE_EXPONENT,
) -> float:
    """The ISO 281 basic rating life L10 = (C/P)^p, in **millions of revolutions**.

    ``dynamic_load_rating`` C is the bearing's catalogue dynamic capacity and
    ``equivalent_load`` P the equivalent dynamic radial load it carries (both
    forces); ``life_exponent`` p is 3 for ball bearings
    (:data:`BALL_BEARING_LIFE_EXPONENT`) or 10/3 for roller bearings
    (:data:`ROLLER_BEARING_LIFE_EXPONENT`). The load-life law is steep — halving the
    load raises a ball bearing's life eightfold. Returns the dimensionless L10 in
    millions of revolutions; both loads must be positive and ``life_exponent``
    positive.
    """
    _require(dynamic_load_rating, "[force]", "dynamic_load_rating")
    _require(equivalent_load, "[force]", "equivalent_load")
    c = dynamic_load_rating.to("N").magnitude
    p = equivalent_load.to("N").magnitude
    if c <= 0:
        raise ValueError(f"dynamic_load_rating must be positive; got {dynamic_load_rating}")
    if p <= 0:
        raise ValueError(f"equivalent_load must be positive; got {equivalent_load}")
    if life_exponent <= 0:
        raise ValueError(f"life_exponent must be positive; got {life_exponent}")
    return (c / p) ** life_exponent


def bearing_life_hours(
    *,
    dynamic_load_rating: Quantity,
    equivalent_load: Quantity,
    speed: Quantity,
    life_exponent: float = BALL_BEARING_LIFE_EXPONENT,
) -> Quantity:
    """The ISO 281 basic rating life expressed in running **hours** at a speed.

    L10h = (10⁶/(60·n))·(C/P)^p converts the basic rating life
    (:func:`bearing_basic_rating_life`, in millions of revolutions) to service
    hours at shaft speed ``speed`` n. The load and exponent arguments are as there;
    ``speed`` must be a positive rotational frequency (rpm or rad/s). Returns the
    life in hours.
    """
    life_mrev = bearing_basic_rating_life(
        dynamic_load_rating=dynamic_load_rating,
        equivalent_load=equivalent_load,
        life_exponent=life_exponent,
    )
    _require(speed, "[frequency]", "speed")
    rpm = speed.to("rpm").magnitude
    if rpm <= 0:
        raise ValueError(f"speed must be positive; got {speed}")
    hours = life_mrev * 1.0e6 / (60.0 * rpm)
    return Quantity(magnitude=hours, unit="hour")


def bearing_static_safety_factor(
    *,
    static_load_rating: Quantity,
    equivalent_static_load: Quantity,
) -> float:
    """The static load safety factor s₀ = C₀/P₀ of a rolling bearing.

    Alongside the L10 dynamic life, a bearing must survive its heaviest *static*
    (or slow, shock) load without brinelling the raceways. The static safety factor
    is the basic static load rating ``static_load_rating`` C₀ (a catalogue value)
    over the equivalent static load ``equivalent_static_load`` P₀ actually applied.
    Typical minimums are s₀ ≈ 1–2 for smooth-running bearings and up to 3+ where
    shock or quiet running matters. Both loads must be positive forces. Returns the
    dimensionless s₀.
    """
    _require(static_load_rating, "[force]", "static_load_rating")
    _require(equivalent_static_load, "[force]", "equivalent_static_load")
    c0 = static_load_rating.to("N").magnitude
    p0 = equivalent_static_load.to("N").magnitude
    if c0 <= 0:
        raise ValueError(f"static_load_rating must be positive; got {static_load_rating}")
    if p0 <= 0:
        raise ValueError(f"equivalent_static_load must be positive; got {equivalent_static_load}")
    return c0 / p0


def bearing_equivalent_dynamic_load(
    *,
    radial_load: Quantity,
    axial_load: Quantity,
    radial_factor: float,
    axial_factor: float,
) -> Quantity:
    """The ISO 281 equivalent dynamic bearing load P = X·F_r + Y·F_a.

    A rolling bearing under *combined* radial and thrust load feels an equivalent
    pure-radial load P = X·F_r + Y·F_a that does the same fatigue damage — the value
    to feed :func:`bearing_basic_rating_life`. ``radial_load`` F_r and ``axial_load``
    F_a are the two load components, and ``radial_factor`` X and ``axial_factor`` Y
    the dimensionless ISO 281 combination factors, read from the bearing's table by
    the axial-to-radial ratio against its e value (supplied like any catalogue
    datum; a common pair is X = 0.56, Y ≈ 1.4–2). For pure radial load below the e
    threshold X = 1, Y = 0 and P = F_r. Both loads must be non-negative and the
    factors positive. Returns the equivalent load in newtons.
    """
    _require(radial_load, "[force]", "radial_load")
    _require(axial_load, "[force]", "axial_load")
    fr = radial_load.to("N").magnitude
    fa = axial_load.to("N").magnitude
    if fr < 0 or fa < 0:
        raise ValueError("radial_load and axial_load must be non-negative")
    if radial_factor <= 0 or axial_factor <= 0:
        raise ValueError("radial_factor and axial_factor must be positive")
    return Quantity(magnitude=radial_factor * fr + axial_factor * fa, unit="N")


def bearing_reliability_life_factor(
    *, reliability: float, weibull_slope: float = BEARING_WEIBULL_SLOPE
) -> float:
    """The ISO 281 life-adjustment factor a₁ = (ln(1/R)/ln(1/0.90))^(1/e) for a
    reliability above 90%.

    The basic rating life L10 (:func:`bearing_basic_rating_life`) is the life 90% of
    bearings reach — a 10% failure probability. To design for a higher reliability R
    the life is scaled down by a₁, which follows from the Weibull scatter of bearing
    life: a₁ = (ln(1/R)/ln(1/0.90))^(1/e), with ``weibull_slope`` e ≈ 1.5. This
    reproduces the standard ISO 281 a₁ table — 1.0 at 90%, 0.62 at 95%, 0.33 at 98%,
    0.21 at 99% — so the reliability-adjusted life is L_R = a₁·L10 (multiply the
    output of :func:`bearing_basic_rating_life` or :func:`bearing_life_hours` by it).
    ``reliability`` R must lie in (0, 1); at R = 0.90 a₁ = 1. A higher reliability
    buys a shorter usable life. Returns the dimensionless a₁ (≤ 1 for R ≥ 0.90).
    """
    if not 0.0 < reliability < 1.0:
        raise ValueError(f"reliability must lie in (0, 1); got {reliability}")
    if weibull_slope <= 0:
        raise ValueError(f"weibull_slope must be positive; got {weibull_slope}")
    return (log(1.0 / reliability) / log(1.0 / 0.90)) ** (1.0 / weibull_slope)
