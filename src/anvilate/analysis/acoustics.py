"""T1 analytical acoustics checks (sound-level arithmetic, closed-form).

Industrial and plant engineers assess machinery noise for hearing conservation and equipment
specifications, and two relations do most of the work — both of which trip up intuition because
sound levels are logarithmic.

Sound levels do not add arithmetically: because the decibel is a log scale, combining sources means
summing their *energies* and converting back, L_total = 10·log₁₀(Σ 10^(Lᵢ/10)). Two equal sources
are only 3 dB louder than one, not double; a source 10 dB below another adds almost nothing.

A point source in the open loses level with distance by the inverse-square law, which in decibels is
L₂ = L₁ − 20·log₁₀(r₂/r₁) — a clean 6 dB drop for every doubling of distance. Levels are plain
decibel numbers (a dimensionless ratio); distances are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log10

from ..units import Quantity

__all__ = [
    "inverse_square_attenuation",
    "sound_level_sum",
]


def sound_level_sum(*, levels: Sequence[float]) -> float:
    """The combined sound level of several incoherent sources, L = 10·log₁₀(Σ 10^(Lᵢ/10)).

    Decibels are logarithmic, so noise sources add by energy, not arithmetic: L = 10·log₁₀(Σ
    10^(Lᵢ/10)). ``levels`` is the sequence of individual sound levels in dB. Two equal sources come
    out only 3 dB above one, and a source more than ~10 dB below the loudest barely moves the
    total — which is why quieting the single loudest machine is what actually lowers a plant's
    noise. Returns the combined level in dB.
    """
    if not levels:
        raise ValueError("levels must contain at least one sound level")
    total = sum(10.0 ** (level / 10.0) for level in levels)
    return 10.0 * log10(total)


def inverse_square_attenuation(
    *,
    reference_level: float,
    reference_distance: Quantity,
    distance: Quantity,
) -> float:
    """The sound level at a distance from a point source, L₂ = L₁ − 20·log₁₀(r₂/r₁).

    A point source radiating into the open spreads its energy over an expanding sphere, so its level
    falls by the inverse-square law — 6 dB for every doubling of distance:
    L₂ = L₁ − 20·log₁₀(r₂/r₁). ``reference_level`` L₁ is the level (dB) measured at
    ``reference_distance`` r₁, and ``distance``
    r₂ is where you want the level. Valid in a free field (no reflecting surfaces or reverberation).
    Returns the sound level at r₂ in dB.
    """
    _check(reference_distance, "[length]", "reference_distance")
    _check(distance, "[length]", "distance")
    r1 = reference_distance.to("m").magnitude
    r2 = distance.to("m").magnitude
    if r1 <= 0 or r2 <= 0:
        raise ValueError("reference_distance and distance must be positive")
    return reference_level - 20.0 * log10(r2 / r1)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
