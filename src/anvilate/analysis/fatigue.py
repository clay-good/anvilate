"""T1 analytical fatigue screening (Goodman / Soderberg / Gerber, closed-form).

A part under fluctuating load fails by fatigue below its static strength. The
modified Goodman criterion combines the alternating stress amplitude σ_a and the
mean stress σ_m against the endurance limit S_e and the ultimate strength S_u:

    σ_a/S_e + σ_m/S_u = 1/n

so the fatigue safety factor is ``n = 1 / (σ_a/S_e + σ_m/S_u)`` (Shigley). The
Soderberg criterion is the same line drawn to the *yield* strength S_y instead of
S_u, ``σ_a/S_e + σ_m/S_y = 1/n`` — more conservative, and the one criterion that
also guards the mean stress against first-cycle yielding. The Gerber criterion
replaces the straight line with a parabola through the same intercepts,
``n·σ_a/S_e + (n·σ_m/S_u)² = 1`` — the best fit to test data, so it sits above
Goodman and gives the least conservative of the three. The endurance limit is
often a labelled estimate or simply absent for a material — in which case a screen
honours No-silent-green and reports ``NOT_EVALUATED`` rather than a silent pass.
As with the other checks, inputs are dimension-checked
:class:`~anvilate.units.Quantity` stresses.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import inf, sqrt

from pydantic import BaseModel, ConfigDict

from ..scorecard import ScorecardEntry
from ..units import Quantity

__all__ = [
    "CyclicStress",
    "cyclic_stress_components",
    "estimated_endurance_limit",
    "marin_endurance_limit",
    "fatigue_notch_factor",
    "neuber_notch_sensitivity",
    "peterson_notch_sensitivity",
    "goodman_safety_factor",
    "goodman_scorecard",
    "soderberg_safety_factor",
    "soderberg_scorecard",
    "gerber_safety_factor",
    "gerber_scorecard",
    "miner_cumulative_damage",
    "miner_spectrum_repeats_to_failure",
    "basquin_cycles_to_failure",
    "basquin_stress_for_life",
]

# Shigley's steel rotating-beam endurance-limit estimate: S_e' = 0.5*S_u, capped
# at ENDURANCE_CAP for high-strength steels where the ratio no longer holds.
_ENDURANCE_FRACTION = 0.5
_ENDURANCE_CAP_MPA = 700.0  # ~100 ksi (steels with S_u above ~1400 MPa)


def _require_stress(value: Quantity, name: str) -> float:
    if not value.has_dimension("[pressure]"):
        raise ValueError(
            f"{name} must be a [pressure] quantity; got {value.dimensionality} ({value})"
        )
    return value.to("MPa").magnitude


def _require_length(value: Quantity, name: str) -> None:
    if not value.has_dimension("[length]"):
        raise ValueError(
            f"{name} must be a [length] quantity; got {value.dimensionality} ({value})"
        )


class CyclicStress(BaseModel):
    """A fluctuating stress cycle resolved into its fatigue components.

    ``alternating_stress`` is the amplitude σ_a = (σ_max − σ_min)/2 and
    ``mean_stress`` the mean σ_m = (σ_max + σ_min)/2 — the pair the Goodman /
    Soderberg / Gerber criteria consume. ``stress_ratio`` is R = σ_min/σ_max, the
    common way loads are catalogued: R = −1 is fully reversed, R = 0 zero-to-tension,
    R = +1 static (and −inf for a cycle peaking at zero).
    """

    model_config = ConfigDict(frozen=True)

    alternating_stress: Quantity
    mean_stress: Quantity
    stress_ratio: float


def fatigue_notch_factor(*, kt: float, notch_sensitivity: float) -> float:
    """The fatigue stress-concentration factor K_f = 1 + q·(K_t − 1).

    A part is less sensitive to a notch in fatigue than the static geometric factor
    K_t (from :func:`~anvilate.analysis.concentrated_stress`) implies; the notch
    sensitivity ``notch_sensitivity`` q (0 to 1) scales the excess. K_f = 1 (q = 0,
    fully insensitive — some cast irons) up to K_f = K_t (q = 1, fully sensitive —
    high-strength steel with a sharp notch). Multiply the *alternating* stress by
    K_f before a Goodman/Soderberg/Gerber screen. ``kt`` must be at least 1 (a
    raiser never reduces stress) and ``notch_sensitivity`` must lie in [0, 1].
    """
    if kt < 1:
        raise ValueError(f"kt must be at least 1 (a stress raiser); got {kt}")
    if not 0 <= notch_sensitivity <= 1:
        raise ValueError(f"notch_sensitivity must lie in [0, 1]; got {notch_sensitivity}")
    return 1.0 + notch_sensitivity * (kt - 1.0)


def neuber_notch_sensitivity(*, notch_radius: Quantity, neuber_constant: Quantity) -> float:
    """The Neuber notch sensitivity q = 1/(1 + √a/√r) from the notch radius.

    Instead of guessing the notch sensitivity q for :func:`fatigue_notch_factor`,
    Neuber's rule derives it from the notch geometry: q = 1/(1 + √a/√r), where
    ``notch_radius`` r is the notch root radius and ``neuber_constant`` √a is the
    Neuber material constant (a √length, tabulated by ultimate strength — smaller
    for stronger steels, which are more notch-sensitive). A blunt notch (r ≫ a) is
    fully sensitive (q → 1); a sharp one (r ≪ a) is insensitive (q → 0) because the
    tiny highly-stressed volume yields locally. ``notch_radius`` is a positive length
    and ``neuber_constant`` a non-negative √length (pass it as e.g. ``"0.25 mm**0.5"``).
    Returns the dimensionless q in [0, 1].
    """
    _require_length(notch_radius, "notch_radius")
    if not neuber_constant.has_dimension("[length]**0.5"):
        raise ValueError(
            f"neuber_constant must be a [length]**0.5 quantity (√a); got "
            f"{neuber_constant.dimensionality} ({neuber_constant})"
        )
    r = notch_radius.to("mm").magnitude
    if r <= 0:
        raise ValueError(f"notch_radius must be positive; got {notch_radius}")
    sqrt_a = neuber_constant.to("mm**0.5").magnitude
    if sqrt_a < 0:
        raise ValueError(f"neuber_constant must be non-negative; got {neuber_constant}")
    return 1.0 / (1.0 + sqrt_a / sqrt(r))


def peterson_notch_sensitivity(*, notch_radius: Quantity, peterson_constant: Quantity) -> float:
    """The Peterson notch sensitivity q = 1/(1 + a/r) from the notch radius.

    Peterson's alternative to :func:`neuber_notch_sensitivity`: q = 1/(1 + a/r),
    with ``notch_radius`` r the notch root radius and ``peterson_constant`` a the
    Peterson material constant (a length, tabulated by strength). Like Neuber it runs
    from insensitive (q → 0) at a sharp notch to fully sensitive (q → 1) at a blunt
    one, crossing q = 0.5 when r = a; it just uses a/r rather than √(a/r). Both
    arguments are lengths, r positive and a non-negative. Returns the dimensionless
    q in [0, 1].
    """
    _require_length(notch_radius, "notch_radius")
    _require_length(peterson_constant, "peterson_constant")
    r = notch_radius.to("mm").magnitude
    a = peterson_constant.to("mm").magnitude
    if r <= 0:
        raise ValueError(f"notch_radius must be positive; got {notch_radius}")
    if a < 0:
        raise ValueError(f"peterson_constant must be non-negative; got {peterson_constant}")
    return 1.0 / (1.0 + a / r)


def estimated_endurance_limit(*, ultimate_strength: Quantity) -> Quantity:
    """Shigley's steel rotating-beam endurance-limit estimate S_e' ≈ 0.5·S_u.

    When a material carries no measured endurance limit, this gives the standard
    screening estimate for steel: half the ultimate strength, capped at 700 MPa
    (~100 ksi) for high-strength steels where the 0.5 ratio breaks down. It is the
    *uncorrected* rotating-beam value — a real part needs the Marin surface, size,
    loading, and temperature factors applied on top — so treat a screen built on it
    as an estimate, not a measured limit. ``ultimate_strength`` S_u must be a
    positive stress; the result feeds :func:`goodman_safety_factor` and its
    siblings. Returns the estimate in MPa.
    """
    if not ultimate_strength.has_dimension("[pressure]"):
        raise ValueError(
            f"ultimate_strength must be a [pressure] quantity; got "
            f"{ultimate_strength.dimensionality} ({ultimate_strength})"
        )
    su = ultimate_strength.to("MPa").magnitude
    if su <= 0:
        raise ValueError(f"ultimate_strength must be positive; got {ultimate_strength}")
    return Quantity(magnitude=min(_ENDURANCE_FRACTION * su, _ENDURANCE_CAP_MPA), unit="MPa")


def marin_endurance_limit(
    *,
    base_endurance_limit: Quantity,
    surface_factor: float = 1.0,
    size_factor: float = 1.0,
    load_factor: float = 1.0,
    temperature_factor: float = 1.0,
    reliability_factor: float = 1.0,
    miscellaneous_factor: float = 1.0,
) -> Quantity:
    """The Marin-corrected endurance limit, S_e = k_a·k_b·k_c·k_d·k_e·k_f·S_e′.

    The rotating-beam endurance limit (measured, or estimated by
    :func:`estimated_endurance_limit`) belongs to a polished 7.6 mm specimen in
    bending at room temperature; a real part earns less. Shigley's Marin factors
    discount it: ``surface_factor`` k_a (machined/hot-rolled/forged finish),
    ``size_factor`` k_b (larger sections expose more highly-stressed volume),
    ``load_factor`` k_c (1.0 bending, ~0.85 axial, ~0.59 torsion),
    ``temperature_factor`` k_d, ``reliability_factor`` k_e (below 1 for
    reliability above 50%), and ``miscellaneous_factor`` k_f (platings, residual
    stress, corrosion). The factor *values* are the engineer's inputs — from the
    Marin a·S_u^b surface fits, the size formulas, or test data — supplied like
    any allowable; each defaults to 1.0 (no correction) and must be positive
    (typically at or below 1). Feed the result to :func:`goodman_safety_factor`
    and its siblings. Returns the corrected limit in MPa.
    """
    se_prime = _require_stress(base_endurance_limit, "base_endurance_limit")
    if se_prime <= 0:
        raise ValueError(f"base_endurance_limit must be positive; got {base_endurance_limit}")
    factors = {
        "surface_factor": surface_factor,
        "size_factor": size_factor,
        "load_factor": load_factor,
        "temperature_factor": temperature_factor,
        "reliability_factor": reliability_factor,
        "miscellaneous_factor": miscellaneous_factor,
    }
    product = 1.0
    for name, factor in factors.items():
        if factor <= 0:
            raise ValueError(f"{name} must be positive; got {factor}")
        product *= factor
    return Quantity(magnitude=product * se_prime, unit="MPa")


def cyclic_stress_components(*, max_stress: Quantity, min_stress: Quantity) -> CyclicStress:
    """Resolve a stress cycle given by its peak and valley into fatigue components.

    Loads usually arrive as the maximum and minimum stress of the cycle, not as an
    amplitude and mean; this converts them. σ_a = (σ_max − σ_min)/2,
    σ_m = (σ_max + σ_min)/2, and R = σ_min/σ_max, ready to feed
    :func:`goodman_safety_factor` and its Soderberg/Gerber siblings.
    ``max_stress`` must exceed ``min_stress`` (both signed, tension positive);
    the stress ratio is −inf when the cycle peaks at exactly zero. Returns a
    :class:`CyclicStress`.
    """
    smax = _require_stress(max_stress, "max_stress")
    smin = _require_stress(min_stress, "min_stress")
    if smax <= smin:
        raise ValueError(
            f"max_stress ({max_stress}) must exceed min_stress ({min_stress}) for a cycle"
        )
    if smax == 0:
        ratio = -inf  # cycle peaks at zero (fully compressive)
    else:
        ratio = smin / smax
    return CyclicStress(
        alternating_stress=Quantity(magnitude=(smax - smin) / 2, unit="MPa"),
        mean_stress=Quantity(magnitude=(smax + smin) / 2, unit="MPa"),
        stress_ratio=ratio,
    )


def goodman_safety_factor(
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity,
    ultimate_strength: Quantity,
) -> float:
    """The modified-Goodman fatigue safety factor n = 1/(σ_a/S_e + σ_m/S_u).

    ``alternating_stress`` is the stress amplitude σ_a (non-negative), ``mean_stress``
    the mean σ_m (tension positive), ``endurance_limit`` S_e and
    ``ultimate_strength`` S_u the material strengths (both positive). All must be
    stresses. Returns ``inf`` when the combination predicts no fatigue failure
    (a non-positive Goodman sum, e.g. a fully-compressive mean with no amplitude).
    """
    sa = _require_stress(alternating_stress, "alternating_stress")
    sm = _require_stress(mean_stress, "mean_stress")
    se = _require_stress(endurance_limit, "endurance_limit")
    su = _require_stress(ultimate_strength, "ultimate_strength")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if se <= 0 or su <= 0:
        raise ValueError("endurance_limit and ultimate_strength must be positive")
    goodman_sum = sa / se + sm / su
    return inf if goodman_sum <= 0 else 1.0 / goodman_sum


def goodman_scorecard(
    name: str,
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity | None,
    ultimate_strength: Quantity,
    required: float,
) -> ScorecardEntry:
    """Screen a fluctuating stress state for fatigue → a :class:`ScorecardEntry`.

    Computes the modified-Goodman safety factor and judges it against ``required``.
    When ``endurance_limit`` is ``None`` — a material with no listed (or estimable)
    endurance limit — the entry is ``NOT_EVALUATED`` rather than a silent pass,
    honouring No-silent-green for the fatigue dimension.
    """
    if endurance_limit is None:
        computed = None
    else:
        computed = goodman_safety_factor(
            alternating_stress=alternating_stress,
            mean_stress=mean_stress,
            endurance_limit=endurance_limit,
            ultimate_strength=ultimate_strength,
        )
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)


def soderberg_safety_factor(
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity,
    yield_strength: Quantity,
) -> float:
    """The Soderberg fatigue safety factor n = 1/(σ_a/S_e + σ_m/S_y).

    The same construction as :func:`goodman_safety_factor` but drawn to the
    ``yield_strength`` S_y instead of the ultimate — more conservative, and unlike
    Goodman it also holds the mean stress below yield, so a passing part is safe
    from first-cycle yielding too. ``alternating_stress`` is the amplitude σ_a
    (non-negative), ``mean_stress`` the mean σ_m (tension positive), and
    ``endurance_limit`` S_e / ``yield_strength`` S_y the material strengths (both
    positive). All must be stresses. Returns ``inf`` when the combination predicts
    no fatigue failure (a non-positive Soderberg sum).
    """
    sa = _require_stress(alternating_stress, "alternating_stress")
    sm = _require_stress(mean_stress, "mean_stress")
    se = _require_stress(endurance_limit, "endurance_limit")
    sy = _require_stress(yield_strength, "yield_strength")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if se <= 0 or sy <= 0:
        raise ValueError("endurance_limit and yield_strength must be positive")
    soderberg_sum = sa / se + sm / sy
    return inf if soderberg_sum <= 0 else 1.0 / soderberg_sum


def soderberg_scorecard(
    name: str,
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity | None,
    yield_strength: Quantity,
    required: float,
) -> ScorecardEntry:
    """Screen a fluctuating stress state for fatigue (Soderberg) → a
    :class:`ScorecardEntry`.

    The conservative counterpart of :func:`goodman_scorecard`, judging the
    Soderberg safety factor against ``required``. When ``endurance_limit`` is
    ``None`` the entry is ``NOT_EVALUATED`` rather than a silent pass, honouring
    No-silent-green for the fatigue dimension.
    """
    if endurance_limit is None:
        computed = None
    else:
        computed = soderberg_safety_factor(
            alternating_stress=alternating_stress,
            mean_stress=mean_stress,
            endurance_limit=endurance_limit,
            yield_strength=yield_strength,
        )
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)


def gerber_safety_factor(
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity,
    ultimate_strength: Quantity,
) -> float:
    """The Gerber fatigue safety factor, the positive root of
    ``n·σ_a/S_e + (n·σ_m/S_u)² = 1``.

    The Gerber parabola passes through the same S_e and S_u intercepts as
    :func:`goodman_safety_factor` but bulges above the Goodman line, so for a
    tensile mean it returns the larger (least conservative) factor — the best fit
    to fatigue data (Shigley). ``alternating_stress`` is the amplitude σ_a
    (non-negative), ``mean_stress`` the mean σ_m (tension positive), and
    ``endurance_limit`` S_e / ``ultimate_strength`` S_u the material strengths
    (both positive). All must be stresses.

    A non-positive (compressive or zero) mean earns no fatigue credit — the screen
    falls back to the amplitude-only endurance ratio n = S_e/σ_a — while a pure
    mean (σ_a = 0) returns the static ultimate ratio S_u/σ_m. Returns ``inf`` when
    no fatigue failure is predicted.
    """
    sa = _require_stress(alternating_stress, "alternating_stress")
    sm = _require_stress(mean_stress, "mean_stress")
    se = _require_stress(endurance_limit, "endurance_limit")
    su = _require_stress(ultimate_strength, "ultimate_strength")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if se <= 0 or su <= 0:
        raise ValueError("endurance_limit and ultimate_strength must be positive")
    if sm <= 0:
        # No credit for a compressive/zero mean: amplitude governs.
        return inf if sa == 0 else se / sa
    if sa == 0:
        # Pure mean stress: the parabola meets the σ_m axis at S_u.
        return su / sm
    a = sa / se
    b = sm / su
    return (a / (2 * b * b)) * (-1 + sqrt(1 + (2 * b / a) ** 2))


def gerber_scorecard(
    name: str,
    *,
    alternating_stress: Quantity,
    mean_stress: Quantity,
    endurance_limit: Quantity | None,
    ultimate_strength: Quantity,
    required: float,
) -> ScorecardEntry:
    """Screen a fluctuating stress state for fatigue (Gerber) → a
    :class:`ScorecardEntry`.

    The least conservative counterpart of :func:`goodman_scorecard`, judging the
    Gerber safety factor against ``required``. When ``endurance_limit`` is ``None``
    the entry is ``NOT_EVALUATED`` rather than a silent pass, honouring
    No-silent-green for the fatigue dimension.
    """
    if endurance_limit is None:
        computed = None
    else:
        computed = gerber_safety_factor(
            alternating_stress=alternating_stress,
            mean_stress=mean_stress,
            endurance_limit=endurance_limit,
            ultimate_strength=ultimate_strength,
        )
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)


def _validate_spectrum(applied_cycles: Sequence[float], cycles_to_failure: Sequence[float]) -> None:
    if len(applied_cycles) != len(cycles_to_failure):
        raise ValueError(
            f"applied_cycles and cycles_to_failure must be the same length; got "
            f"{len(applied_cycles)} and {len(cycles_to_failure)}"
        )
    if not applied_cycles:
        raise ValueError("the load spectrum must have at least one stress level")
    for n in applied_cycles:
        if n < 0:
            raise ValueError(f"applied_cycles must be non-negative; got {n}")
    for big_n in cycles_to_failure:
        if big_n <= 0:
            raise ValueError(f"cycles_to_failure must be positive; got {big_n}")


def miner_cumulative_damage(
    *,
    applied_cycles: Sequence[float],
    cycles_to_failure: Sequence[float],
) -> float:
    """The Palmgren-Miner cumulative fatigue damage D = Σ(nᵢ/Nᵢ) of a load
    spectrum.

    Under a spectrum of stress levels, each block of ``applied_cycles`` nᵢ at a
    level consumes a fraction nᵢ/Nᵢ of the fatigue life, where ``cycles_to_failure``
    Nᵢ is the S-N life at that level (read off the material's S-N curve for each
    stress amplitude). The linear-damage rule sums those fractions: fatigue failure
    is predicted when D reaches 1.0, so D is the fraction of life used and 1 − D the
    fraction remaining. The two sequences pair level-for-level and must be the same
    non-empty length; ``applied_cycles`` must be non-negative and
    ``cycles_to_failure`` positive. Returns the dimensionless damage D.
    """
    _validate_spectrum(applied_cycles, cycles_to_failure)
    return sum(n / big_n for n, big_n in zip(applied_cycles, cycles_to_failure, strict=True))


def miner_spectrum_repeats_to_failure(
    *,
    applied_cycles: Sequence[float],
    cycles_to_failure: Sequence[float],
) -> float:
    """The number of repeats of a load spectrum a part survives, 1/D by
    Palmgren-Miner.

    If one pass through the spectrum accumulates damage D =
    :func:`miner_cumulative_damage`, the part fails after 1/D passes (the fatigue
    safety factor on spectrum life — screen it against a required number of
    service blocks). Returns ``inf`` when the spectrum does no damage (every level
    has zero applied cycles). Same arguments and validation as
    :func:`miner_cumulative_damage`.
    """
    damage = miner_cumulative_damage(
        applied_cycles=applied_cycles, cycles_to_failure=cycles_to_failure
    )
    if damage == 0.0:
        return inf
    return 1.0 / damage


def basquin_cycles_to_failure(
    *,
    stress_amplitude: Quantity,
    coefficient: Quantity,
    exponent: float,
) -> float:
    """The finite fatigue life N from Basquin's S-N law σ_a = a·N^b, solved for N.

    In the high-cycle finite-life region the S-N curve is a straight line on
    log-log axes, σ_a = a·N^b, with the fatigue-strength ``coefficient`` a (a
    stress) and the ``exponent`` b (dimensionless and negative, typically −0.05 to
    −0.12 for steel — the two constants come from the material's S-N curve).
    Inverting gives the cycles to failure at a stress amplitude,
    N = (σ_a/a)^(1/b) — exactly the per-level life
    :func:`miner_cumulative_damage` needs. ``stress_amplitude`` σ_a and
    ``coefficient`` a must be positive stresses and ``exponent`` b must be
    negative (a steeper, more negative b spends life faster). Returns the life N in
    cycles.
    """
    sa = _require_stress(stress_amplitude, "stress_amplitude")
    a = _require_stress(coefficient, "coefficient")
    if sa <= 0:
        raise ValueError(f"stress_amplitude must be positive; got {stress_amplitude}")
    if a <= 0:
        raise ValueError(f"coefficient must be positive; got {coefficient}")
    if exponent >= 0:
        raise ValueError(f"exponent (Basquin's b) must be negative; got {exponent}")
    return (sa / a) ** (1.0 / exponent)


def basquin_stress_for_life(
    *,
    life_cycles: float,
    coefficient: Quantity,
    exponent: float,
) -> Quantity:
    """The stress amplitude a part tolerates for a target life, σ_a = a·N^b.

    The forward of :func:`basquin_cycles_to_failure`: the fatigue strength at a
    design life ``life_cycles`` N on Basquin's S-N line, with the same fatigue
    strength ``coefficient`` a and (negative) ``exponent`` b. ``life_cycles`` must
    be positive; a longer target life lowers the allowable amplitude. Returns the
    stress amplitude in MPa.
    """
    a = _require_stress(coefficient, "coefficient")
    if a <= 0:
        raise ValueError(f"coefficient must be positive; got {coefficient}")
    if life_cycles <= 0:
        raise ValueError(f"life_cycles must be positive; got {life_cycles}")
    if exponent >= 0:
        raise ValueError(f"exponent (Basquin's b) must be negative; got {exponent}")
    return Quantity(magnitude=a * life_cycles**exponent, unit="MPa")
