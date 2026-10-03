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

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (metal-casting
processes) — the casting modulus V/A, Chvorinov's rule t = C·(V/A)^n for solidification time,
and the riser modulus that must exceed the casting's for the riser to feed rather than freeze
first.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_CASTING_GEOMETRY_SOURCE = "the casting and riser drawing or verified solid-model properties"
_CASTING_PROCESS_SOURCE = "the qualified foundry process sheet or calibrated pour trial"
_CASTING_FEEDING_SOURCE = "the approved riser-design criterion or foundry practice"


class _CastingInputError(RefusalError, ValueError):
    """A casting input that cannot be used without correction."""


def _casting_refusal(message: str, *, subject: str, source: str) -> _CastingInputError:
    return _CastingInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _casting_input_source(name: str) -> str:
    if name == "mold_constant":
        return _CASTING_PROCESS_SOURCE
    return _CASTING_GEOMETRY_SOURCE


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
        raise _casting_refusal(
            "volume must be positive", subject="volume", source=_CASTING_GEOMETRY_SOURCE
        )
    if a <= 0:
        raise _casting_refusal(
            "surface_area must be positive",
            subject="surface_area",
            source=_CASTING_GEOMETRY_SOURCE,
        )
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
        raise _casting_refusal(
            "modulus must be positive", subject="modulus", source=_CASTING_GEOMETRY_SOURCE
        )
    if b <= 0:
        raise _casting_refusal(
            "mold_constant must be positive",
            subject="mold_constant",
            source=_CASTING_PROCESS_SOURCE,
        )
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
    require_finite(feeding_factor, name="feeding_factor")
    _check(casting_modulus, "[length]", "casting_modulus")
    if feeding_factor <= 1.0:
        raise _casting_refusal(
            "feeding_factor must exceed 1 (the riser must outlast the casting)",
            subject="feeding_factor",
            source=_CASTING_FEEDING_SOURCE,
        )
    m_c = casting_modulus.to("cm").magnitude
    if m_c <= 0:
        raise _casting_refusal(
            "casting_modulus must be positive",
            subject="casting_modulus",
            source=_CASTING_GEOMETRY_SOURCE,
        )
    return Quantity(magnitude=feeding_factor * m_c, unit="cm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _casting_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_casting_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _casting_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_casting_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
