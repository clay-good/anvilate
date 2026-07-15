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

from ..units import Quantity

# ISO 281 life exponents: the load-life power law L10 = (C/P)^p.
BALL_BEARING_LIFE_EXPONENT = 3.0
ROLLER_BEARING_LIFE_EXPONENT = 10.0 / 3.0

__all__ = [
    "BALL_BEARING_LIFE_EXPONENT",
    "ROLLER_BEARING_LIFE_EXPONENT",
    "bearing_basic_rating_life",
    "bearing_life_hours",
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
