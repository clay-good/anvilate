"""T1 random vibration: a declared input spectrum to Grms, Miles' response, and the 3σ load.

A random-vibration environment is specified as an acceleration spectral density (ASD, in
g²/Hz) at a few breakpoints, with straight lines between them on log-log axes — "+6 dB/oct
from 20 to 50 Hz, 0.16 g²/Hz to 800 Hz, −6 dB/oct to 2000 Hz" is GSFC-STD-7000B Table
2.4-3. The overall level is the square root of the area under it. On a log-log segment
the ASD is a power law, a(f) = a₁(f/f₁)ⁿ with n = log(a₂/a₁)/log(f₂/f₁), so the area has a
closed form:

    ∫ a df = a₁f₁/(n + 1) · [(f₂/f₁)ⁿ⁺¹ − 1],   or a₁f₁·ln(f₂/f₁) when n = −1.

Integrating the straight lines a plot shows, rather than the log-log lines the spectrum
means, overstates the sloped segments; the GEVS overall levels (14.1 Grms qualification,
10.0 acceptance, 6.8 workmanship) are what the log-log integral gives, and the tests hold
it to all of them.

A mount of natural frequency f_n and amplification Q responds to it, by Miles' equation,
at G_rms = √(π/2 · f_n · Q · ASD(f_n)) (Miles, 1954), with the ASD read off the declared
spectrum at f_n. Miles' equation assumes a single-degree-of-freedom response to an input
that is flat across the resonance; every result states that. Three times the response
Grms is the 3σ peak a mount is sized to, and it is combined with any quasi-static load
factor by the rule the caller declares: root-sum-square, or the absolute sum.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import exp, isclose, log, pi, sqrt

from pydantic import BaseModel, ConfigDict

from .._models import each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "LoadCombinationRule",
    "RandomVibrationLoad",
    "psd_overall_grms",
    "psd_level",
    "miles_response_grms",
    "random_vibration_load",
]

_SPECTRUM_SOURCE = "the random-vibration test specification's breakpoint table"
_MOUNT_SOURCE = "the mount's natural frequency and amplification, from a modal test or analysis"

#: The assumption every Miles result carries.
_SINGLE_DEGREE_OF_FREEDOM = (
    "Miles' equation assumes a single-degree-of-freedom response to an input flat across the "
    "resonance; a mount with several modes in band, or a spectrum sloped through f_n, needs "
    "a frequency-response analysis"
)


class _RandomVibrationInputError(RefusalError, ValueError):
    """A random-vibration input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _RandomVibrationInputError:
    return _RandomVibrationInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class LoadCombinationRule(StrEnum):
    """How the 3σ random peak is combined with a quasi-static load factor.

    Root-sum-square or the absolute sum, the two GSFC-STD-7000B practice names; which one
    applies is the program's declaration, never a default chosen here.
    """

    ROOT_SUM_SQUARE = "root_sum_square"
    ABSOLUTE_SUM = "absolute_sum"


def _magnitude(value: Quantity, unit: str, name: str, *, source: str) -> float:
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a quantity in {unit}; got {value!r}",
                       subject=name, source=source)  # fmt: skip
    try:
        magnitude = value.to(unit).magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not convertible to {unit}",
                       subject=name, source=source) from error  # fmt: skip
    return require_finite(magnitude, name=name)


def _spectrum(
    frequencies: Sequence[Quantity], asd: Sequence[Quantity]
) -> list[tuple[float, float]]:
    freqs = each_one(frequencies, Quantity, named="frequencies")
    levels = each_one(asd, Quantity, named="asd")
    if len(freqs) != len(levels) or len(freqs) < 2:
        raise _refusal(
            f"a spectrum is at least two breakpoints with one ASD level each; got "
            f"{len(freqs)} frequencies and {len(levels)} levels",
            subject="frequencies and asd",
            source=_SPECTRUM_SOURCE,
        )
    points: list[tuple[float, float]] = []
    for i, (f, a) in enumerate(zip(freqs, levels, strict=True)):
        hz = _magnitude(f, "Hz", f"frequencies[{i}]", source=_SPECTRUM_SOURCE)
        level = _magnitude(a, "1/Hz", f"asd[{i}]", source=_SPECTRUM_SOURCE)
        if hz <= 0 or level <= 0:
            raise _refusal(
                f"breakpoint {i} is {hz:g} Hz at {level:g} g²/Hz; a log-log spectrum has a "
                "positive frequency and a positive level at every breakpoint",
                subject=f"frequencies[{i}]" if hz <= 0 else f"asd[{i}]",
                source=_SPECTRUM_SOURCE,
            )
        if points and hz <= points[-1][0]:
            raise _refusal(
                f"breakpoint {i} at {hz:g} Hz does not rise above {points[-1][0]:g} Hz; "
                "breakpoints are listed in increasing frequency",
                subject=f"frequencies[{i}]",
                source=_SPECTRUM_SOURCE,
            )
        points.append((hz, level))
    return points


def _segment_area(f1: float, a1: float, f2: float, a2: float) -> float:
    n = log(a2 / a1) / log(f2 / f1)
    if isclose(n, -1.0, abs_tol=1e-12):
        return a1 * f1 * log(f2 / f1)
    return a1 * f1 / (n + 1) * (float((f2 / f1) ** (n + 1)) - 1)


def psd_overall_grms(*, frequencies: Sequence[Quantity], asd: Sequence[Quantity]) -> float:
    """The overall level of a breakpoint spectrum, in g RMS (GSFC-STD-7000B §2.4.2.3).

    ``frequencies`` are the breakpoints in increasing order and ``asd`` the level at each,
    as a per-hertz quantity (``0.16 1/Hz`` for 0.16 g²/Hz — in a unit string ``g`` is the
    gram). Between breakpoints the spectrum is a straight line on log-log axes, integrated
    in closed form; the result is the square root of the area.
    """
    points = _spectrum(frequencies, asd)
    area = sum(
        _segment_area(f1, a1, f2, a2)
        for (f1, a1), (f2, a2) in zip(points, points[1:], strict=False)
    )
    return sqrt(area)


def psd_level(
    *, frequencies: Sequence[Quantity], asd: Sequence[Quantity], at: Quantity
) -> Quantity:
    """The spectrum's ASD at ``at``, interpolated on log-log axes (GSFC-STD-7000B §2.4.2.3).

    A frequency outside the declared band is refused: the spectrum states nothing there,
    and extrapolating a slope past its last breakpoint is a guess. Returned in 1/Hz (g²/Hz).
    """
    points = _spectrum(frequencies, asd)
    f = _magnitude(at, "Hz", "at", source=_MOUNT_SOURCE)
    low, high = points[0][0], points[-1][0]
    if not low <= f <= high:
        raise _refusal(
            f"{f:g} Hz is outside the declared spectrum, {low:g} to {high:g} Hz; the "
            "spectrum states no level there",
            subject="at",
            source=_SPECTRUM_SOURCE,
        )
    for (f1, a1), (f2, a2) in zip(points, points[1:], strict=False):
        if f1 <= f <= f2:
            n = log(a2 / a1) / log(f2 / f1)
            return Quantity(magnitude=a1 * exp(n * log(f / f1)), unit="1/Hz")
    raise AssertionError("unreachable: f lies inside [low, high]")  # pragma: no cover


def _miles(fn: float, quality: float, asd: float) -> float:
    return sqrt(pi / 2 * fn * quality * asd)


def miles_response_grms(*, natural_frequency: float, quality_factor: float, asd: float) -> float:
    """Miles' equation on plain magnitudes: f_n in Hz, Q, ASD in g²/Hz; result in g RMS.

    The one implementation (Miles, 1954). :func:`random_vibration_load` reads the ASD off
    a declared spectrum and checks the units, and the opto-mechanics
    ``miles_random_vibration_grms`` takes one flat level; both call this.
    """
    fn = require_finite(natural_frequency, name="natural_frequency")
    quality = require_finite(quality_factor, name="quality_factor")
    level = require_finite(asd, name="asd")
    if fn <= 0:
        raise _refusal(f"natural_frequency must be positive; got {fn}",
                       subject="natural_frequency", source=_MOUNT_SOURCE)  # fmt: skip
    if quality <= 0.5:
        raise _refusal(
            f"quality_factor must exceed 0.5 for a mode that resonates at all; got {quality}",
            subject="quality_factor",
            source=_MOUNT_SOURCE,
        )
    if level <= 0:
        raise _refusal(f"asd must be positive (g²/Hz); got {level}", subject="asd",
                       source=_SPECTRUM_SOURCE)  # fmt: skip
    return _miles(fn, quality, level)


class RandomVibrationLoad(BaseModel):
    """A mount's random-vibration load: the input, Miles' response, the 3σ and design load.

    The response is Miles' equation (Miles, 1954) at the ASD the spectrum states at f_n.

    Accelerations are in g. ``design_load`` is the 3σ peak combined with
    ``quasi_static`` by ``rule``; ``assumption`` is the single-degree-of-freedom premise
    the response rests on, carried so no rendering can drop it.
    """

    model_config = ConfigDict(frozen=True)

    input_grms: float
    asd_at_natural_frequency: float
    response_grms: float
    peak_3_sigma: float
    quasi_static: float
    rule: LoadCombinationRule
    design_load: float
    assumption: str = _SINGLE_DEGREE_OF_FREEDOM

    def __str__(self) -> str:
        return (
            f"input {self.input_grms:.3g} Grms; response {self.response_grms:.3g} Grms at "
            f"{self.asd_at_natural_frequency:.3g} g²/Hz; 3σ {self.peak_3_sigma:.3g} g; "
            f"design load {self.design_load:.3g} g ({self.rule.value.replace('_', ' ')} with "
            f"{self.quasi_static:g} g quasi-static) — {self.assumption}"
        )


def random_vibration_load(
    *,
    frequencies: Sequence[Quantity],
    asd: Sequence[Quantity],
    natural_frequency: Quantity,
    quality_factor: float,
    quasi_static: float = 0.0,
    rule: LoadCombinationRule = LoadCombinationRule.ROOT_SUM_SQUARE,
) -> RandomVibrationLoad:
    """The 3σ random load on a mount from a declared spectrum, combined with quasi-static.

    The input Grms integrates the spectrum (:func:`psd_overall_grms`); the response is
    Miles' equation at f_n with the ASD read off the spectrum there (:func:`psd_level`);
    the peak is 3σ = 3·G_rms. ``quasi_static`` is a steady load factor in g that acts at the
    same time (a launch's sustained axial acceleration), combined as √(3σ² + qs²) or
    3σ + |qs| by ``rule`` — the caller's declaration, because programs differ. Q is
    required and never defaulted: the answer scales with √Q.
    """
    if not isinstance(rule, LoadCombinationRule):
        raise _refusal(f"rule must be a LoadCombinationRule; got {rule!r}", subject="rule",
                       source="the program's load-combination rule")  # fmt: skip
    qs = require_finite(quasi_static, name="quasi_static")
    grms = psd_overall_grms(frequencies=frequencies, asd=asd)
    fn = _magnitude(natural_frequency, "Hz", "natural_frequency", source=_MOUNT_SOURCE)
    level = psd_level(frequencies=frequencies, asd=asd, at=natural_frequency).magnitude
    response = miles_response_grms(natural_frequency=fn, quality_factor=quality_factor, asd=level)
    peak = 3 * response
    if rule is LoadCombinationRule.ROOT_SUM_SQUARE:
        design = sqrt(peak**2 + qs**2)
    else:
        design = peak + abs(qs)
    return RandomVibrationLoad(
        input_grms=grms,
        asd_at_natural_frequency=level,
        response_grms=response,
        peak_3_sigma=peak,
        quasi_static=qs,
        rule=rule,
        design_load=design,
    )
