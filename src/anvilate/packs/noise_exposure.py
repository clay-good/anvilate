"""The occupational noise pack: declare a worker's exposure, get a hearing-conservation scorecard.

Where :mod:`anvilate.packs.masonry` serves the wall designer, this pack serves the industrial
hygienist sizing a worker's noise dose. A :class:`WorkerNoiseExposure` declares the steady sound
levels a worker stands in (one per machine) and how long the shift lasts;
:func:`screen_noise_exposure` combines the sources by energy (the decibel does not add
arithmetically), finds the permissible time
at that level on the standard's exchange rate, and rolls the resulting dose into a cited PASS/FAIL
scorecard entry — no silent green. The criterion level and exchange rate are the standard's own
values: OSHA (90 dBA, 5 dB) by default, or NIOSH (85 dBA, 3 dB) by argument. The measured levels and
duration are the caller's; the exposure limit is the cited regulation, and the safety professional
owns the determination.
"""

from __future__ import annotations

from pydantic import ConfigDict

from ..analysis import (
    noise_dose_fraction,
    permissible_exposure_time,
    sound_level_sum,
)
from ..derivation import Derivation, SymbolValue
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "WorkerNoiseExposure",
    "screen_noise_exposure",
]

_DEFAULT_CRITERION_DURATION = Quantity.parse("8 hour")


class WorkerNoiseExposure(GuardedInputs):
    """A worker's noise exposure over a shift, and the inputs its dose screen needs.

    ``machine_levels`` are the steady sound levels in dBA at the worker's position, one per source
    (they combine by energy, not arithmetic). ``exposure_duration`` is how long the worker is
    exposed at that combined level over the shift. Both are the caller's measured values.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    machine_levels: tuple[float, ...]
    exposure_duration: Quantity


def screen_noise_exposure(
    exposure: WorkerNoiseExposure,
    *,
    criterion_level: float = 90.0,
    exchange_rate: float = 5.0,
    criterion_duration: Quantity = _DEFAULT_CRITERION_DURATION,
    required_safety_factor: float = 1.0,
) -> Scorecard:
    """Screen a :class:`WorkerNoiseExposure` against a hearing-conservation limit; return its card.

    Combines the machine levels by energy, finds the permissible time at that combined level for
    the given ``criterion_level`` and ``exchange_rate`` (OSHA 90 dBA / 5 dB by default; pass 85.0
    and 3.0 for the NIOSH REL), and compares the shift ``exposure_duration`` against it. The safety
    factor is the permissible time over the exposure time (equivalently 1/dose): 1.0 is the full
    permissible dose, below 1.0 the limit is exceeded. Screened against ``required_safety_factor``
    (1.0 — the regulatory limit already carries the margin). Returns a
    :class:`~anvilate.scorecard.Scorecard` with one cited PASS/FAIL entry for the noise dose.
    """
    if not exposure.machine_levels:
        raise ValueError("machine_levels must contain at least one sound level")
    combined = sound_level_sum(levels=list(exposure.machine_levels))
    permissible = permissible_exposure_time(
        sound_level=combined,
        criterion_level=criterion_level,
        exchange_rate=exchange_rate,
        criterion_duration=criterion_duration,
    )
    dose = noise_dose_fraction(
        exposure_time=exposure.exposure_duration, permissible_time=permissible
    )
    dose_sf = 1.0 / dose if dose > 0 else None
    reference = (
        f"OSHA 29 CFR 1910.95 / NIOSH REL — {criterion_level:.0f} dBA criterion, "
        f"{exchange_rate:.0f} dB exchange rate"
    )
    # T is carried in already evaluated: T = T₀ / 2^((L − L_c)/q) is an exponential, and
    # the substituter resolves symbols rather than evaluating expressions, so expanding it
    # would render a formula that stops short of its own number. What the dose *is* — the
    # time spent over the time allowed — is the line a reviewer checks.
    dose_derivation = Derivation(
        symbolic="D = C / T",
        inputs=(
            SymbolValue(
                symbol="C",
                description="time actually spent at the combined level",
                value=exposure.exposure_duration,
                unit="hour",
            ),
            SymbolValue(
                symbol="T",
                description=(
                    f"permissible time at the combined {combined:.1f} dBA, "
                    f"T₀ / 2^((L − {criterion_level:.0f})/{exchange_rate:.0f})"
                ),
                value=permissible,
                unit="hour",
            ),
        ),
        result=SymbolValue(
            symbol="D",
            description="noise dose as a fraction of the permissible exposure",
            value=dose,
        ),
        citation=reference,
    )
    entry = ScorecardEntry.from_safety_factor(
        "noise dose", computed=dose_sf, required=required_safety_factor
    ).model_copy(update={"reference": reference, "derivation": dose_derivation})
    return Scorecard(entries=(entry,))
