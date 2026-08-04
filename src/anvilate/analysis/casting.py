"""T1 analytical metal-casting solidification checks (closed-form).

A casting freezes from its surfaces inward, losing heat through the mould, so how long it takes to
solidify depends on how much metal there is relative to how much surface it can lose heat through.
That ratio, the *casting modulus* M = V/A (volume over cooling surface area), is the one geometric
number foundry design turns on — a thick, chunky section has a large modulus and freezes slowly; a
thin web has a small one and freezes fast.

Chvorinov's rule makes the dependence explicit: the solidification time is t = B·M², proportional to
the *square* of the modulus, where the mould constant B (from the mould material, the pouring
superheat, and the metal — the caller's, from test data or handbooks) carries the units. Doubling
the modulus quadruples the freezing time.

The rule is also the basis of riser design. A riser is a reservoir that feeds liquid metal into the
casting as it shrinks on freezing, so it must still be liquid *after* the casting has solidified —
which means its modulus must exceed the casting's. The usual rule of thumb sizes the riser to a
modulus about 1.2× the casting's, so it freezes last and the shrinkage porosity ends up in the
riser, not the part. This module gives the modulus, the Chvorinov time, and the riser-modulus goal.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "casting_modulus",
    "chvorinov_solidification_time",
    "riser_modulus_for_feeding",
]


def casting_modulus(*, volume: Quantity, surface_area: Quantity) -> Quantity:
    """The casting modulus, M = V/A.

    The ratio of a casting's ``volume`` V to its heat-losing ``surface_area`` A: M = V/A. It is the
    single geometric measure of how fast a section freezes — a large modulus (a chunky section)
    cools slowly, a small one (a thin web) quickly — and it drives both the solidification time (see
    :func:`chvorinov_solidification_time`) and the riser sizing (see
    :func:`riser_modulus_for_feeding`). Returns the modulus as a length.
    """
    _check(volume, "[length]**3", "volume")
    _check(surface_area, "[length]**2", "surface_area")
    v = volume.to("cm**3").magnitude
    a = surface_area.to("cm**2").magnitude
    if v <= 0:
        raise ValueError("volume must be positive")
    if a <= 0:
        raise ValueError("surface_area must be positive")
    return Quantity(magnitude=v / a, unit="cm")


def chvorinov_solidification_time(*, modulus: Quantity, mold_constant: Quantity) -> Quantity:
    """The solidification time by Chvorinov's rule, t = B·M².

    How long a casting takes to freeze solid, from its ``modulus`` M (from :func:`casting_modulus`)
    and the ``mold_constant`` B: t = B·M². The time goes as the *square* of the modulus, so a
    section twice as chunky takes four times as long to solidify. B [time/length²] rolls together
    the mould material, the pouring superheat, and the metal's properties, and is the caller's from
    pours or handbooks. Returns the solidification time (in the mould constant's time unit, reported
    as minutes).
    """
    _check(modulus, "[length]", "modulus")
    _check(mold_constant, "[time]/[length]**2", "mold_constant")
    m = modulus.to("cm").magnitude
    b = mold_constant.to("min/cm**2").magnitude
    if m <= 0:
        raise ValueError("modulus must be positive")
    if b <= 0:
        raise ValueError("mold_constant must be positive")
    return Quantity(magnitude=b * m**2, unit="min")


def riser_modulus_for_feeding(
    *,
    casting_modulus: Quantity,
    feeding_factor: float = 1.2,
) -> Quantity:
    """The riser modulus needed to feed the casting, M_r = k·M_c.

    The modulus a riser must have to keep feeding a casting until the casting has solidified:
    M_r = k·M_c, from the ``casting_modulus`` M_c and a ``feeding_factor`` k (the usual rule
    is ~1.2). Because solidification time scales with modulus squared (Chvorinov), a riser modulus
    above the casting's guarantees the riser freezes *last*, so it — not the part — takes the
    shrinkage porosity. A riser sized below this target starves the casting and leaves a shrinkage
    cavity. Returns the required riser modulus as a length.
    """
    _check(casting_modulus, "[length]", "casting_modulus")
    if feeding_factor <= 1.0:
        raise ValueError("feeding_factor must exceed 1 (the riser must outlast the casting)")
    m_c = casting_modulus.to("cm").magnitude
    if m_c <= 0:
        raise ValueError("casting_modulus must be positive")
    return Quantity(magnitude=feeding_factor * m_c, unit="cm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
