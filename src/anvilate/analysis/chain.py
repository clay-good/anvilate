"""T1 analytical roller-chain drive geometry (closed-form).

A roller chain wraps two sprockets like a belt, but it is a *polygon*, not a
smooth loop, and that shows up in two numbers the designer needs before anything
else: how long the chain must be, and how roughly it runs.

The chain length is counted in pitches (whole links), and for a centre distance C
(also in pitches) between an N₁- and N₂-tooth sprocket it is

    L_p = 2·C_p + (N₁ + N₂)/2 + ((N₂ − N₁)/(2π))² / C_p

which is rounded up to a whole — preferably even — number of links, since an odd
count needs an offset link. The roughness is *chordal action*: because the chain
sits on the flats of a polygon, the pitch-line radius rises and falls as each
tooth engages, so even at constant sprocket speed the chain's linear speed swings
between ω·R and ω·R·cos(π/N). The fractional swing 1 − cos(π/N) shrinks fast with
tooth count, which is why small sprockets run rough and 17+ teeth are preferred.

Lengths are dimension-checked :class:`~anvilate.units.Quantity` values; tooth
counts are positive whole numbers.
"""

from __future__ import annotations

from math import cos, pi

from ..units import Quantity

__all__ = [
    "chain_length_in_pitches",
    "chordal_speed_variation",
    "chain_speed",
    "chain_working_tension",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _check_teeth(count: int, name: str) -> int:
    whole = int(count)
    if whole != count or whole <= 0:
        raise ValueError(f"{name} must be a positive whole number of teeth; got {count}")
    return whole


def chain_length_in_pitches(
    *,
    small_sprocket_teeth: int,
    large_sprocket_teeth: int,
    center_distance: Quantity,
    chain_pitch: Quantity,
) -> float:
    """The roller-chain length in pitches (links) for a two-sprocket drive.

    Counts the whole links a chain needs to wrap an ``small_sprocket_teeth`` N₁
    and ``large_sprocket_teeth`` N₂ sprocket pair at a given ``center_distance`` C:

        L_p = 2·C_p + (N₁ + N₂)/2 + ((N₂ − N₁)/(2π))² / C_p

    where C_p = C/pitch is the centre distance expressed in pitches. ``chain_pitch``
    is the pitch (roller spacing) of the chain, and both it and ``center_distance``
    are positive lengths. The returned value is the exact (fractional) pitch count;
    round it *up* to a whole — preferably even — number of links for the build, and
    trim the centre distance to suit. Returns the dimensionless pitch count.
    """
    n1 = _check_teeth(small_sprocket_teeth, "small_sprocket_teeth")
    n2 = _check_teeth(large_sprocket_teeth, "large_sprocket_teeth")
    _require(center_distance, "[length]", "center_distance")
    _require(chain_pitch, "[length]", "chain_pitch")
    c = center_distance.to("mm").magnitude
    p = chain_pitch.to("mm").magnitude
    if p <= 0:
        raise ValueError(f"chain_pitch must be positive; got {chain_pitch}")
    if c <= 0:
        raise ValueError(f"center_distance must be positive; got {center_distance}")
    cp = c / p
    return 2.0 * cp + (n1 + n2) / 2.0 + ((n2 - n1) / (2.0 * pi)) ** 2 / cp


def chordal_speed_variation(*, sprocket_teeth: int) -> float:
    """The fractional chordal speed variation 1 − cos(π/N) of a chain sprocket.

    A chain rides the flats of a polygon, so its linear speed swings between ω·R
    at a tooth and ω·R·cos(π/N) at a flat as each of the ``sprocket_teeth`` N teeth
    engages — a fractional swing of 1 − cos(π/N) even at constant sprocket speed.
    The variation falls quickly with tooth count (about 4% at 11 teeth, 1.7% at
    17, under 1% past 23), which is why small sprockets run rough and drives avoid
    them. ``sprocket_teeth`` is a positive whole number. Returns the dimensionless
    peak-to-flat fraction of the chain speed.
    """
    n = _check_teeth(sprocket_teeth, "sprocket_teeth")
    return 1.0 - cos(pi / n)


def chain_speed(
    *, sprocket_teeth: int, chain_pitch: Quantity, rotational_speed: Quantity
) -> Quantity:
    """The mean linear chain speed v = N·p·n.

    A sprocket's pitch circle carries N·p of chain per revolution, so the chain's
    mean linear speed is v = N·p·n for a sprocket turning at speed n — the
    velocity that turns a tension into transmitted power (P = F·v). ``sprocket_teeth``
    N and ``chain_pitch`` p describe the sprocket, and ``rotational_speed`` n is its
    speed (rpm or rad/s — a rotational frequency). All must be positive. Returns
    the mean speed in m/s (the chordal action swings the instantaneous speed about
    it by :func:`chordal_speed_variation`).
    """
    n = _check_teeth(sprocket_teeth, "sprocket_teeth")
    _require(chain_pitch, "[length]", "chain_pitch")
    if not rotational_speed.has_dimension("[frequency]"):
        raise ValueError(
            f"rotational_speed must be a rotational-speed ([frequency]) quantity; got "
            f"{rotational_speed.dimensionality} ({rotational_speed})"
        )
    p = chain_pitch.to("m").magnitude
    if p <= 0:
        raise ValueError(f"chain_pitch must be positive; got {chain_pitch}")
    omega = rotational_speed.to("rad/s").magnitude
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    rev_per_second = omega / (2.0 * pi)
    return Quantity(magnitude=n * p * rev_per_second, unit="m/s")


def chain_working_tension(*, power: Quantity, chain_speed: Quantity) -> Quantity:
    """The working (tight-side) tension F = P/v a roller chain carries.

    A chain drive transmits power as a tension on its tight strand pulling the driven
    sprocket, so the working tension is simply F = P/v for a transmitted ``power`` P
    at the mean ``chain_speed`` v (:func:`chain_speed`). Unlike a belt the chain has
    no meaningful slack-side pull to subtract — it does not rely on friction — so this
    single tension is the load to compare against the chain's rated tensile strength
    (through a service factor and a generous margin for fatigue and the chordal
    pulsation). ``power`` must be a power and ``chain_speed`` a positive velocity.
    Returns the tension in newtons.
    """
    _require(power, "[power]", "power")
    _require(chain_speed, "[velocity]", "chain_speed")
    p = power.to("W").magnitude
    v = chain_speed.to("m/s").magnitude
    if p <= 0:
        raise ValueError(f"power must be positive; got {power}")
    if v <= 0:
        raise ValueError(f"chain_speed must be positive; got {chain_speed}")
    return Quantity(magnitude=p / v, unit="N")
