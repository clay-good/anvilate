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
Goodman and gives the least conservative of the three. Morrow's correction reuses
the Goodman line but draws it to the true fracture strength σ_f' instead of S_u.
The endurance limit is
often a labelled estimate or simply absent for a material — in which case a screen
honours No-silent-green and reports ``NOT_EVALUATED`` rather than a silent pass.
As with the other checks, inputs are dimension-checked
:class:`~anvilate.units.Quantity` stresses.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import inf, sqrt

from pydantic import BaseModel, ConfigDict

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity, require_finite

__all__ = [
    "CyclicStress",
    "cyclic_stress_components",
    "estimated_endurance_limit",
    "marin_endurance_limit",
    "fatigue_notch_factor",
    "neuber_notch_sensitivity",
    "peterson_notch_sensitivity",
    "smith_watson_topper_stress",
    "goodman_equivalent_reversed_stress",
    "morrow_equivalent_reversed_stress",
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
    "coffin_manson_reversals",
    "strain_life_total_amplitude",
    "weld_constant_amplitude_fatigue_limit",
    "weld_cutoff_limit",
    "weld_detail_endurance_cycles",
    "weld_detail_allowable_stress_range",
    "weld_size_effect_factor",
    "weld_size_corrected_detail_category",
    "weld_mean_stress_factor",
    "weld_effective_stress_range",
    "weld_nominal_stress_range_limit",
    "weld_fatigue_scorecard",
]

# EN 1993-1-9 nominal-stress fatigue curve anchors (cycles). The detail category
# Δσ_C is the reference fatigue strength at N_C = 2M cycles; the curve runs at
# slope m = 3 down to the constant-amplitude limit Δσ_D at N_D = 5M, then at slope
# m = 5 down to the cutoff Δσ_L at N_L = 100M, below which the range does no damage.
_WELD_N_C = 2.0e6
_WELD_N_D = 5.0e6
_WELD_N_L = 1.0e8
_WELD_SLOPE_HIGH = 3.0  # m, above the constant-amplitude limit
_WELD_SLOPE_LOW = 5.0  # m, between the constant-amplitude limit and the cutoff

# Shigley's steel rotating-beam endurance-limit estimate: S_e' = 0.5*S_u, capped
# at ENDURANCE_CAP for high-strength steels where the ratio no longer holds.
_ENDURANCE_FRACTION = 0.5
_ENDURANCE_CAP_MPA = 700.0  # ~100 ksi (steels with S_u above ~1400 MPa)


def _require_stress(value: Quantity, name: str) -> float:
    if not value.has_dimension("[pressure]"):
        raise ValueError(
            f"{name} must be a [pressure] quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN stress used to travel all the way to a NaN safety
    # factor, which the scorecard does catch — but the elastic-range limit below is a
    # *guard*, and `range > nan` is False for every range, so a NaN yield strength turned
    # it off entirely rather than making it loud. A guard that stops guarding is worse
    # than a NaN answer.
    require_finite(value, name=name)
    return value.to("MPa").magnitude


def _require_length(value: Quantity, name: str) -> None:
    if not value.has_dimension("[length]"):
        raise ValueError(
            f"{name} must be a [length] quantity; got {value.dimensionality} ({value})"
        )
    require_finite(value, name=name)


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


def smith_watson_topper_stress(*, max_stress: Quantity, alternating_stress: Quantity) -> Quantity:
    """The Smith-Watson-Topper equivalent fully-reversed stress σ_ar = √(σ_max·σ_a).

    An alternative to Goodman for mean-stress correction: SWT collapses a cycle with
    a tensile mean to the fully-reversed amplitude σ_ar = √(σ_max·σ_a) that would do
    the same fatigue damage, ready to compare against the endurance limit or S-N
    curve. ``max_stress`` σ_max = σ_m + σ_a is the peak stress and
    ``alternating_stress`` σ_a the amplitude (from :func:`cyclic_stress_components`).
    A fully-reversed cycle (σ_m = 0, σ_max = σ_a) returns σ_a unchanged; a tensile
    mean raises σ_ar above σ_a. SWT often fits tensile-mean-dominated data better
    than Goodman and needs no ultimate strength. ``max_stress`` must be positive (a
    compressive peak does no tensile-fatigue damage under SWT) and σ_a non-negative.
    Returns the equivalent fully-reversed stress in MPa.
    """
    smax = _require_stress(max_stress, "max_stress")
    sa = _require_stress(alternating_stress, "alternating_stress")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if smax <= 0:
        raise ValueError(
            f"max_stress must be positive for the SWT tensile-fatigue model; got {smax} MPa"
        )
    # σ_max < σ_a is a COMPRESSIVE mean (σ_m = σ_max − σ_a < 0), and SWT is a tensile-mean
    # model: the sign of the peak was checked and the mean never was, so the whole region
    # 0 < σ_max < σ_a slid through returning √(σ_max·σ_a), which credits compression with a
    # reduction in damaging stress. At σ_max = 1, σ_a = 100 that is 10 MPa against the 100
    # MPa the amplitude alone justifies — a 10x understatement of the number the caller
    # looks up on an S-N curve. This module's own Gerber check gives no credit for a
    # non-positive mean; refusing here says the same thing without silently changing it.
    if smax < sa:
        raise ValueError(
            f"max_stress {smax:.4g} MPa is below alternating_stress {sa:.4g} MPa, so the mean "
            f"stress is {smax - sa:.4g} MPa — compressive. SWT is a tensile-mean model and "
            f"returns a *lower* equivalent stress for a compressive mean, which is unconservative "
            f"by {sa / sqrt(smax * sa):.3g}x here. For a non-positive mean the amplitude governs: "
            f"use σ_a directly, as goodman_safety_factor does."
        )
    return Quantity(magnitude=sqrt(smax * sa), unit="MPa")


def goodman_equivalent_reversed_stress(
    *, alternating_stress: Quantity, mean_stress: Quantity, ultimate_strength: Quantity
) -> Quantity:
    """The Goodman equivalent fully-reversed stress σ_ar = σ_a/(1 − σ_m/S_u).

    The fully-reversed amplitude that, on the modified-Goodman line, does the same
    fatigue damage as the actual cycle — the value to look up on an S-N curve or
    compare to the endurance limit, and the equivalent-stress counterpart of
    :func:`goodman_safety_factor`. ``alternating_stress`` σ_a is the amplitude,
    ``mean_stress`` σ_m the mean (tension positive), and ``ultimate_strength`` S_u the
    material's ultimate. A fully-reversed cycle (σ_m = 0) returns σ_a unchanged; a
    tensile mean inflates it toward infinity as σ_m approaches S_u. Compared with
    :func:`smith_watson_topper_stress`, this is the Goodman rather than the SWT
    mean-stress model. σ_a must be non-negative and σ_m below S_u (a mean at the
    ultimate has zero fatigue life). Returns the equivalent reversed stress in MPa.
    """
    sa = _require_stress(alternating_stress, "alternating_stress")
    sm = _require_stress(mean_stress, "mean_stress")
    su = _require_stress(ultimate_strength, "ultimate_strength")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if su <= 0:
        raise ValueError(f"ultimate_strength must be positive; got {su} MPa")
    if sm >= su:
        raise ValueError(
            f"mean_stress ({sm} MPa) must be below ultimate_strength ({su} MPa) "
            "for a finite equivalent stress"
        )
    return Quantity(magnitude=sa / (1.0 - sm / su), unit="MPa")


def morrow_equivalent_reversed_stress(
    *, alternating_stress: Quantity, mean_stress: Quantity, true_fracture_strength: Quantity
) -> Quantity:
    """The Morrow equivalent fully-reversed stress σ_ar = σ_a/(1 − σ_m/σ_f').

    Morrow's mean-stress correction, identical in form to
    :func:`goodman_equivalent_reversed_stress` but drawn to the material's *true
    fracture strength* σ_f' (from a strain-life fit) instead of the ultimate S_u.
    Because σ_f' exceeds S_u, Morrow is less conservative than Goodman for a tensile
    mean and fits steel fatigue data better, especially where the mean is large.
    ``alternating_stress`` σ_a is the amplitude, ``mean_stress`` σ_m the mean (tension
    positive), and ``true_fracture_strength`` σ_f' the material constant. A
    fully-reversed cycle (σ_m = 0) returns σ_a unchanged; σ_m must stay below σ_f'.
    Returns the equivalent reversed stress in MPa.
    """
    sa = _require_stress(alternating_stress, "alternating_stress")
    sm = _require_stress(mean_stress, "mean_stress")
    sf = _require_stress(true_fracture_strength, "true_fracture_strength")
    if sa < 0:
        raise ValueError(f"alternating_stress (an amplitude) must be non-negative; got {sa} MPa")
    if sf <= 0:
        raise ValueError(f"true_fracture_strength must be positive; got {sf} MPa")
    if sm >= sf:
        raise ValueError(
            f"mean_stress ({sm} MPa) must be below true_fracture_strength ({sf} MPa) "
            "for a finite equivalent stress"
        )
    return Quantity(magnitude=sa / (1.0 - sm / sf), unit="MPa")


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
    # The textbook root is (a/2b²)·(√(1+z²) − 1) with z = 2b/a, but √(1+z²) − 1 loses every
    # significant digit as the mean stress falls: below z² ≈ 2e-16 it evaluates to exactly 0
    # and the factor collapses to 0.0 — a hard FAIL for a component that is fine, reached just
    # by spelling a small mean in Pa instead of MPa. Multiplying through by the conjugate,
    # √(1+z²) − 1 = z²/(√(1+z²) + 1), cancels the subtraction analytically and leaves
    # n = 2/(a·(√(1+z²) + 1)), which is exact for every z and tends continuously to the
    # σ_m → 0 limit S_e/σ_a that the branch above returns.
    z = 2 * b / a
    return 2.0 / (a * (sqrt(1 + z * z) + 1))


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


def coffin_manson_reversals(
    *,
    plastic_strain_amplitude: float,
    fatigue_ductility_coefficient: float,
    fatigue_ductility_exponent: float,
) -> float:
    """The reversals to failure in low-cycle fatigue by the Coffin-Manson law, from plastic strain.

    Where Basquin's stress-life governs high-cycle fatigue, the Coffin-Manson relation governs the
    *low*-cycle, plastic regime (thermal cycling, seismic, forming): Δε_p/2 = εf'·(2N)^c, inverted
    for life as 2N = (Δε_p/2 / εf')^(1/c). ``plastic_strain_amplitude`` Δε_p/2 is the plastic strain
    amplitude, ``fatigue_ductility_coefficient`` εf' (~the true fracture strain), and
    ``fatigue_ductility_exponent`` c (negative, ~−0.5 to −0.7). Returns the number of reversals to
    failure 2N (two per cycle).
    """
    if plastic_strain_amplitude <= 0:
        raise ValueError("plastic_strain_amplitude must be positive")
    if fatigue_ductility_coefficient <= 0:
        raise ValueError("fatigue_ductility_coefficient must be positive")
    if fatigue_ductility_exponent >= 0:
        raise ValueError("fatigue_ductility_exponent (c) must be negative")
    return (plastic_strain_amplitude / fatigue_ductility_coefficient) ** (
        1.0 / fatigue_ductility_exponent
    )


def strain_life_total_amplitude(
    *,
    reversals: float,
    fatigue_strength_coefficient: Quantity,
    elastic_modulus: Quantity,
    fatigue_strength_exponent: float,
    fatigue_ductility_coefficient: float,
    fatigue_ductility_exponent: float,
) -> float:
    """The total strain amplitude at a given life by the strain-life (Coffin-Manson-Basquin) law.

    The full strain-life curve sums an elastic branch (Basquin, in strain) and a plastic branch
    (Coffin-Manson): Δε/2 = (σf'/E)·(2N)^b + εf'·(2N)^c. At short lives the plastic term dominates
    (low-cycle fatigue), at long lives the elastic term does (high-cycle). ``reversals`` 2N is the
    life, ``fatigue_strength_coefficient`` σf' and ``elastic_modulus`` E and
    ``fatigue_strength_exponent`` b give the elastic branch, and
    ``fatigue_ductility_coefficient`` εf' with ``fatigue_ductility_exponent`` c the plastic branch.
    Returns the dimensionless total strain amplitude Δε/2.
    """
    sigma_f = _require_stress(fatigue_strength_coefficient, "fatigue_strength_coefficient")
    e = _require_stress(elastic_modulus, "elastic_modulus")
    if reversals <= 0:
        raise ValueError("reversals must be positive")
    if sigma_f <= 0 or e <= 0:
        raise ValueError("fatigue_strength_coefficient and elastic_modulus must be positive")
    if fatigue_strength_exponent >= 0:
        raise ValueError("fatigue_strength_exponent (b) must be negative")
    if fatigue_ductility_coefficient <= 0:
        raise ValueError("fatigue_ductility_coefficient must be positive")
    if fatigue_ductility_exponent >= 0:
        raise ValueError("fatigue_ductility_exponent (c) must be negative")
    elastic = (sigma_f / e) * reversals**fatigue_strength_exponent
    plastic = fatigue_ductility_coefficient * reversals**fatigue_ductility_exponent
    return elastic + plastic


def weld_constant_amplitude_fatigue_limit(*, detail_category: Quantity) -> Quantity:
    """The EN 1993-1-9 constant-amplitude fatigue limit Δσ_D of a weld detail.

    Below this stress range a constant-amplitude spectrum causes no fatigue damage.
    It sits at N_D = 5M cycles on the m = 3 line through the ``detail_category``
    Δσ_C (the category's reference strength at 2M cycles, a user-supplied value from
    EN 1993-1-9 Table 8.x — Anvilate encodes the curve, not the copyrighted table):
    Δσ_D = Δσ_C·(N_C/N_D)^(1/3) = Δσ_C·(2/5)^(1/3) ≈ 0.737·Δσ_C. Returns MPa.
    """
    dsc = _require_stress(detail_category, "detail_category")
    if dsc <= 0:
        raise ValueError(f"detail_category must be positive; got {detail_category}")
    return Quantity(magnitude=dsc * (_WELD_N_C / _WELD_N_D) ** (1.0 / _WELD_SLOPE_HIGH), unit="MPa")


def weld_cutoff_limit(*, detail_category: Quantity) -> Quantity:
    """The EN 1993-1-9 cutoff limit Δσ_L of a weld detail.

    Below this stress range even a variable-amplitude spectrum does no damage. It
    sits at N_L = 100M cycles on the m = 5 line below the constant-amplitude limit:
    Δσ_L = Δσ_D·(N_D/N_L)^(1/5) = Δσ_D·(5/100)^(1/5) ≈ 0.549·Δσ_D ≈ 0.405·Δσ_C, from
    the user-supplied ``detail_category`` Δσ_C. Returns MPa.
    """
    dsd = weld_constant_amplitude_fatigue_limit(detail_category=detail_category)
    return Quantity(
        magnitude=dsd.magnitude * (_WELD_N_D / _WELD_N_L) ** (1.0 / _WELD_SLOPE_LOW),
        unit="MPa",
    )


def weld_detail_endurance_cycles(
    *,
    stress_range: Quantity,
    detail_category: Quantity,
    variable_amplitude: bool = True,
) -> float:
    """The EN 1993-1-9 endurance N of a weld detail at a nominal ``stress_range``.

    The standardized trilinear S-N curve from the user-supplied ``detail_category``
    Δσ_C: at slope m = 3 above the constant-amplitude limit Δσ_D,
    N = N_C·(Δσ_C/Δσ)³; between Δσ_D and the cutoff Δσ_L at slope m = 5,
    N = N_D·(Δσ_D/Δσ)⁵; and below the cutoff the range does no damage (``inf``).
    ``variable_amplitude`` selects which limit ends the life: under a variable
    spectrum (the default, EN 1993-1-9 §7) the m = 5 branch runs to the cutoff Δσ_L;
    under a constant-amplitude spectrum, life is infinite below Δσ_D. Returns the
    cycles to failure (``math.inf`` below the governing limit).
    """
    ds = _require_stress(stress_range, "stress_range")
    dsc = _require_stress(detail_category, "detail_category")
    if ds <= 0:
        raise ValueError(f"stress_range must be positive; got {stress_range}")
    if dsc <= 0:
        raise ValueError(f"detail_category must be positive; got {detail_category}")
    dsd = weld_constant_amplitude_fatigue_limit(detail_category=detail_category).magnitude
    if ds >= dsd:
        return _WELD_N_C * (dsc / ds) ** _WELD_SLOPE_HIGH
    if not variable_amplitude:
        return inf  # constant amplitude: no damage below the CAFL
    dsl = weld_cutoff_limit(detail_category=detail_category).magnitude
    if ds < dsl:
        return inf  # below the cutoff: no damage even under a variable spectrum
    return _WELD_N_D * (dsd / ds) ** _WELD_SLOPE_LOW


def weld_detail_allowable_stress_range(
    *,
    life_cycles: float,
    detail_category: Quantity,
) -> Quantity:
    """The EN 1993-1-9 stress range a weld detail tolerates for a target life.

    The design inverse of :func:`weld_detail_endurance_cycles`: the nominal stress
    range Δσ that reaches ``life_cycles`` N on the standardized curve from the
    user-supplied ``detail_category`` Δσ_C. For N ≤ N_D (5M) it is on the m = 3
    branch, Δσ = Δσ_C·(N_C/N)^(1/3); for N_D < N ≤ N_L (100M) on the m = 5 branch,
    Δσ = Δσ_D·(N_D/N)^(1/5); beyond the cutoff N_L it is the cutoff limit Δσ_L.
    Returns MPa.
    """
    dsc = _require_stress(detail_category, "detail_category")
    if dsc <= 0:
        raise ValueError(f"detail_category must be positive; got {detail_category}")
    if life_cycles <= 0:
        raise ValueError(f"life_cycles must be positive; got {life_cycles}")
    if life_cycles <= _WELD_N_D:
        return Quantity(
            magnitude=dsc * (_WELD_N_C / life_cycles) ** (1.0 / _WELD_SLOPE_HIGH), unit="MPa"
        )
    dsd = weld_constant_amplitude_fatigue_limit(detail_category=detail_category).magnitude
    if life_cycles <= _WELD_N_L:
        return Quantity(
            magnitude=dsd * (_WELD_N_D / life_cycles) ** (1.0 / _WELD_SLOPE_LOW), unit="MPa"
        )
    return weld_cutoff_limit(detail_category=detail_category)


# EN 1993-1-9 §7.2.2 size-effect reference thickness and exponent (the standard
# values for the thickness-sensitive details; detail-dependent, so caller-tunable).
_WELD_SIZE_REFERENCE_MM = 25.0
_WELD_SIZE_EXPONENT = 0.2


def weld_size_effect_factor(
    *,
    thickness: Quantity,
    reference_thickness: Quantity | None = None,
    exponent: float = _WELD_SIZE_EXPONENT,
) -> float:
    """The EN 1993-1-9 §7.2.2 thickness size-effect factor k_s ≤ 1.

    A thicker plate cracks at a lower stress range: for a thickness-sensitive detail
    above the ``reference_thickness`` t_ref (25 mm by default), the fatigue strength
    is reduced by k_s = (t_ref/t)^n, with the standard ``exponent`` n = 0.2 (both
    detail-dependent, so caller-tunable — the mechanics are exact, the convention is
    yours, guardrail-safe). At or below the reference thickness there is no penalty
    (k_s = 1). Multiply the detail category by k_s before building the S-N curve.
    Returns the dimensionless factor.
    """
    t = thickness.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"thickness must be positive; got {thickness}")
    # A negative exponent inverts the penalty: (t_ref/t)^n rises above 1 and the thick plate
    # comes out STRONGER than the reference, against this function's own k_s <= 1 contract.
    if exponent < 0:
        raise ValueError(
            f"exponent must be non-negative; got {exponent}, which turns the thickness "
            f"penalty into a bonus (k_s > 1)"
        )
    t_ref = (
        _WELD_SIZE_REFERENCE_MM
        if reference_thickness is None
        else reference_thickness.to("mm").magnitude
    )
    if t_ref <= 0:
        raise ValueError(f"reference_thickness must be positive; got {reference_thickness}")
    if t <= t_ref:
        return 1.0
    return (t_ref / t) ** exponent


def weld_size_corrected_detail_category(
    *,
    detail_category: Quantity,
    thickness: Quantity,
    reference_thickness: Quantity | None = None,
    exponent: float = _WELD_SIZE_EXPONENT,
) -> Quantity:
    """The detail category reduced for the plate thickness, k_s·Δσ_C.

    Applies :func:`weld_size_effect_factor` to the user-supplied ``detail_category``
    so the size-corrected value can be fed straight into
    :func:`weld_detail_endurance_cycles` or :func:`weld_detail_allowable_stress_range`.
    Below the reference thickness it returns the category unchanged. Returns MPa.
    """
    dsc = _require_stress(detail_category, "detail_category")
    if dsc <= 0:
        raise ValueError(f"detail_category must be positive; got {detail_category}")
    factor = weld_size_effect_factor(
        thickness=thickness, reference_thickness=reference_thickness, exponent=exponent
    )
    return Quantity(magnitude=dsc * factor, unit="MPa")


# EN 1993-1-9 §7.2.1: in a stress-relieved or non-welded detail the compressive part of
# the range is only 60% as damaging, because there are no tensile residual stresses holding
# the crack open through it. In an as-welded detail the residual stress sits at yield and
# the whole range does damage, so the bonus does not apply.
_WELD_COMPRESSION_FACTOR = 0.6


def weld_effective_stress_range(
    *,
    max_stress: Quantity,
    min_stress: Quantity,
    stress_relieved: bool = False,
    compression_factor: float = _WELD_COMPRESSION_FACTOR,
) -> Quantity:
    """The EN 1993-1-9 §7.2.1 effective stress range, with the compressive part discounted.

    A fatigue crack grows while it is held open, so the compressive half of a cycle is less
    damaging than the tensile half — but only if there is no tensile residual stress holding
    the crack open anyway. In an *as-welded* detail the residual stress sits at yield and the
    whole range does damage; in a *stress-relieved* or non-welded one the compressive part
    counts at ``compression_factor`` (0.6 in the standard):

        Δσ_eff = σ_max + factor·|σ_min|   when σ_min < 0 and the detail is stress-relieved,
        Δσ_eff = σ_max − σ_min            otherwise.

    ``max_stress`` and ``min_stress`` are the signed algebraic extremes of the cycle
    (tension positive), so a fully reversed ±100 MPa cycle is max = +100, min = −100.
    ``stress_relieved`` defaults to ``False`` — the conservative as-welded case — because
    claiming the bonus is a statement about the fabrication, not about the geometry, and it
    is the caller's to make. Returns Δσ_eff in MPa.
    """
    smax = _require_stress(max_stress, "max_stress")
    smin = _require_stress(min_stress, "min_stress")
    if smin > smax:
        raise ValueError(
            f"min_stress ({min_stress}) exceeds max_stress ({max_stress}): the algebraic "
            f"extremes of the cycle are swapped"
        )
    if not 0 < compression_factor <= 1:
        raise ValueError(
            f"compression_factor must lie in (0, 1]; got {compression_factor}. Above 1 the "
            f"compressive part would be more damaging than the tensile part"
        )
    if not stress_relieved or smin >= 0:
        return Quantity(magnitude=smax - smin, unit="MPa")
    # Wholly compressive cycles keep a discounted range too — the tensile part is simply zero.
    tensile = max(smax, 0.0)
    return Quantity(magnitude=tensile + compression_factor * (min(smax, 0.0) - smin), unit="MPa")


def weld_mean_stress_factor(
    *,
    max_stress: Quantity,
    min_stress: Quantity,
    stress_relieved: bool = False,
    compression_factor: float = _WELD_COMPRESSION_FACTOR,
) -> float:
    """The visible mean-stress correction factor Δσ_eff/Δσ ≤ 1 (EN 1993-1-9 §7.2.1).

    The same correction as :func:`weld_effective_stress_range`, expressed as the factor it
    applies, so it can sit beside the thickness factor k_s in a record that shows every
    correction that moved the number. It is 1.0 for an as-welded detail and for any cycle
    with no compressive part; it reaches its floor (``compression_factor``, 0.6) for a
    fully compressive cycle on a stress-relieved detail. Returns the dimensionless factor.
    """
    smax = _require_stress(max_stress, "max_stress")
    smin = _require_stress(min_stress, "min_stress")
    full_range = smax - smin
    if full_range <= 0:
        raise ValueError(
            f"max_stress ({max_stress}) and min_stress ({min_stress}) give a stress range of "
            f"{full_range:.4g} MPa: there is no cycle to correct"
        )
    effective = weld_effective_stress_range(
        max_stress=max_stress,
        min_stress=min_stress,
        stress_relieved=stress_relieved,
        compression_factor=compression_factor,
    )
    return effective.to("MPa").magnitude / full_range


# EN 1993-1-9 §8 limits the *nominal* stress range a fatigue assessment may be run on:
# Δσ ≤ 1.5·f_y for direct stress and Δτ ≤ 1.5·f_y/√3 for shear. Above it the detail is
# yielding under the fatigue load and the nominal-stress S-N method — which is elastic,
# and calibrated on tests that stayed elastic — is not the applicable one.
_WELD_ELASTIC_RANGE_FACTOR = 1.5


def weld_nominal_stress_range_limit(*, yield_strength: Quantity, shear: bool = False) -> Quantity:
    """The EN 1993-1-9 §8 upper limit on a nominal stress range: 1.5·f_y, or 1.5·f_y/√3.

    A nominal-stress fatigue assessment is an elastic method calibrated on details that
    stayed elastic. Above 1.5·f_y (1.5·f_y/√3 in shear, the von Mises equivalent) the
    detail is yielding under the fatigue load itself, and the S-N curve is being read
    outside the range the tests behind it cover. Returns the limiting range.

    This is a limit the standard states in prose and that nothing in an S-N formula
    enforces: the curve happily returns a life for any range you hand it, and the number
    looks like every other number it returns.
    """
    stress = _require_stress(yield_strength, "yield_strength")
    if stress <= 0:
        raise ValueError(f"yield_strength must be positive; got {yield_strength}")
    limit = _WELD_ELASTIC_RANGE_FACTOR * stress
    if shear:
        limit /= sqrt(3.0)
    return Quantity(magnitude=limit, unit="MPa")


def weld_fatigue_scorecard(
    name: str,
    *,
    applied_cycles: Sequence[float],
    stress_ranges: Sequence[Quantity],
    detail_category: Quantity | None,
    thickness: Quantity | None = None,
    yield_strength: Quantity | None = None,
    variable_amplitude: bool = True,
    required: float = 1.0,
) -> ScorecardEntry:
    """Screen a weld detail over a stress-range spectrum → a :class:`ScorecardEntry`.

    Builds the EN 1993-1-9 S-N curve from ``detail_category`` (optionally reduced for
    ``thickness`` via the size effect), computes each range's life, sums the
    Palmgren-Miner damage D over the ``applied_cycles``, and reports the fatigue
    safety factor 1/D against ``required`` (1.0 = exactly the design life).

    When ``detail_category`` is ``None`` the entry is ``NOT_EVALUATED``, never a
    silent pass: choosing and defending the detail category is the engineer's call,
    and a weld fatigue check without one has not been made. ``applied_cycles`` and
    ``stress_ranges`` must be the same length.

    ``yield_strength`` enables the EN 1993-1-9 §8 elastic limit: a spectrum containing a
    range above 1.5·f_y is reported ``NOT_EVALUATED`` naming it, because the detail is
    yielding under the fatigue load and the nominal-stress method is an elastic one. The
    S-N curve returns a life for such a range without complaint, and it looks like every
    other life it returns — which is why the limit has to be checked here rather than
    trusted to the formula. Omitted, the limit is not applied and the entry says nothing
    about it either way.
    """
    if len(applied_cycles) != len(stress_ranges):
        raise ValueError(
            f"applied_cycles ({len(applied_cycles)}) and stress_ranges "
            f"({len(stress_ranges)}) must have the same length"
        )
    if detail_category is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no EN 1993-1-9 detail category chosen",
            reference="EN 1993-1-9",
        )
    if yield_strength is not None:
        limit = weld_nominal_stress_range_limit(yield_strength=yield_strength)
        over = [sr for sr in stress_ranges if _require_stress(sr, "stress_range") > limit.magnitude]
        if over:
            return ScorecardEntry(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"not evaluated — {len(over)} stress range(s) exceed the EN 1993-1-9 §8 "
                    f"elastic limit of {limit}: {', '.join(str(sr) for sr in over)}. The "
                    "detail is yielding under the fatigue load, and the nominal-stress S-N "
                    "method does not cover it"
                ),
                reference="EN 1993-1-9 §8",
            )
    category = (
        detail_category
        if thickness is None
        else weld_size_corrected_detail_category(
            detail_category=detail_category, thickness=thickness
        )
    )
    lives = [
        weld_detail_endurance_cycles(
            stress_range=sr, detail_category=category, variable_amplitude=variable_amplitude
        )
        for sr in stress_ranges
    ]
    # An empty spectrum, or one whose every block applies zero cycles, is a check with
    # nothing to evaluate — the `inf` it used to divide out to read as the strongest
    # possible PASS. Zero damage from ranges that all sit *below the cutoff* is different:
    # that is an evaluated EN 1993-1-9 conclusion of infinite life, and it still passes.
    if not applied_cycles or sum(applied_cycles) == 0:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — the spectrum applies no cycles",
            reference="EN 1993-1-9",
        )
    damage = miner_cumulative_damage(applied_cycles=applied_cycles, cycles_to_failure=lives)
    computed = inf if damage == 0 else 1.0 / damage
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required).model_copy(
        update={"reference": "EN 1993-1-9"}
    )
