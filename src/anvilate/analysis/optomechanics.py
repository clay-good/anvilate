"""T1 analytical opto-mechanical checks: does a lens stay in focus across its temperature range.

A lens and the housing that holds it both move with temperature, and not together. The glass
changes its index (dn/dT) and grows (α_g), so a thin lens's focal length moves by
Δf = f·(α_g − (dn/dT)/(n − 1))·ΔT — the glass thermal constant of Jamieson (1981). The housing
that sets the lens-to-image spacing L grows by α_h·L·ΔT. The image lands where the first puts
it and the detector sits where the second puts it, so the defocus is the difference,
δ = Δf − α_h·L·ΔT, and a design is athermal when the two cancel.

Whether a defocus matters depends on how deep the focus is. By the Rayleigh quarter-wave
criterion a diffraction-limited image stays sharp within ±2·λ·N² of best focus, for a
wavelength λ and working f-number N. :func:`athermal_focus_scorecard` compares the two.

Glass data is an input here, never bundled: dn/dT depends on wavelength, temperature and
whether it is quoted relative to air or vacuum, and a catalogue value used at the wrong one
is a confident wrong answer. The caller states the value and owns where it came from.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import exp, log, pi, sqrt

from ..derivation import Derivation, DerivationAbsence, SymbolValue, Underived
from ..scorecard import CheckStatus, Comparison, LimitSense, ScorecardEntry
from ..units import Quantity, require_finite, temperature_difference_kelvin
from .psychrometrics import dew_point_temperature, saturation_vapor_pressure

__all__ = [
    "depth_of_focus",
    "thermal_focal_shift",
    "athermal_defocus",
    "athermal_focus_scorecard",
    "miles_random_vibration_grms",
    "retention_preload",
    "stress_birefringence_retardance",
    "marechal_strehl_ratio",
    "wavefront_budget_scorecard",
    "internal_condensation_scorecard",
]

_ALDUCHOV = (
    "Alduchov and Eskridge, Improved Magnus form approximation of saturation vapor pressure, "
    "Journal of Applied Meteorology 35 (1996)"
)
_JAMIESON = "Jamieson, Thermal effects in optical systems, Optical Engineering 20(2) (1981)"


def depth_of_focus(*, wavelength: Quantity, f_number: float) -> Quantity:
    """The diffraction-limited depth of focus either side of best focus, ±2·λ·N².

    By the Rayleigh quarter-wave criterion (Smith, Modern Optical Engineering; Hecht, Optics),
    a converging beam at ``wavelength`` λ and working ``f_number`` N stays within a quarter
    wave of perfect focus over ±2·λ·N². Returned as that half-width in micrometres — the
    tolerance on either side, which is what a defocus is compared against. Doubling N
    quadruples it, which is why a slow lens forgives a housing that a fast one does not.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    n = require_finite(f_number, name="f_number")
    if lam <= 0:
        raise ValueError(f"wavelength must be positive; got {wavelength}")
    if n <= 0:
        raise ValueError(f"f_number must be positive; got {f_number}")
    return Quantity(magnitude=2.0 * lam * n * n * 1e6, unit="µm")


def thermal_focal_shift(
    *,
    focal_length: Quantity,
    refractive_index: float,
    dn_dt: Quantity,
    glass_cte: Quantity,
    temperature_change: Quantity,
) -> Quantity:
    """How far a thin lens's focal length moves with temperature, Δf = f·(α_g − (dn/dT)/(n − 1))·ΔT.

    The glass thermal constant of Jamieson (1981): the lens grows with its ``glass_cte`` α_g,
    which lengthens f, and its index changes by ``dn_dt``, which shortens it for a positive
    dn/dT because f scales as 1/(n − 1). ``refractive_index`` n must exceed 1 and ``dn_dt``
    must be quoted relative to the medium the lens works in — relative to air for a lens in
    air. A positive result is a focal length that grew. Returned in micrometres.
    """
    _check(focal_length, "[length]", "focal_length")
    _check(dn_dt, "1 / [temperature]", "dn_dt")
    _check(glass_cte, "1 / [temperature]", "glass_cte")
    _check(temperature_change, "[temperature]", "temperature_change")
    f = focal_length.to("m").magnitude
    n = require_finite(refractive_index, name="refractive_index")
    if f <= 0:
        raise ValueError(f"focal_length must be positive; got {focal_length}")
    if n <= 1:
        raise ValueError(
            f"refractive_index must exceed 1 for a lens in air to focus at all; got {n}"
        )
    constant = glass_cte.to("1/K").magnitude - dn_dt.to("1/K").magnitude / (n - 1)
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    return Quantity(magnitude=f * constant * delta_t * 1e6, unit="µm")


def athermal_defocus(
    *,
    focal_shift: Quantity,
    housing_cte: Quantity,
    housing_length: Quantity,
    temperature_change: Quantity,
) -> Quantity:
    """The defocus at the detector, δ = Δf − α_h·L·ΔT.

    The lens moves its image by ``focal_shift`` Δf (from :func:`thermal_focal_shift`); the
    housing, of ``housing_cte`` α_h and lens-to-image ``housing_length`` L, moves the
    detector by α_h·L·ΔT. The difference is how far out of focus the image lands, and zero is
    the athermal condition α_h·L = f·(α_g − (dn/dT)/(n − 1)) of Jamieson (1981) and Yoder,
    Opto-Mechanical Systems Design. Signed: positive when the image lands beyond the
    detector. Returned in micrometres.
    """
    _check(focal_shift, "[length]", "focal_shift")
    _check(housing_cte, "1 / [temperature]", "housing_cte")
    _check(housing_length, "[length]", "housing_length")
    _check(temperature_change, "[temperature]", "temperature_change")
    length = housing_length.to("m").magnitude
    if length <= 0:
        raise ValueError(f"housing_length must be positive; got {housing_length}")
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    growth = housing_cte.to("1/K").magnitude * length * delta_t
    return Quantity(magnitude=(focal_shift.to("m").magnitude - growth) * 1e6, unit="µm")


def athermal_focus_scorecard(
    name: str,
    *,
    focal_length: Quantity,
    f_number: float,
    wavelength: Quantity,
    refractive_index: float,
    dn_dt: Quantity,
    glass_cte: Quantity,
    housing_cte: Quantity,
    housing_length: Quantity,
    temperature_change: Quantity,
) -> ScorecardEntry:
    """Screen a lens in its housing for focus across a temperature change.

    ``PASS`` when the defocus of :func:`athermal_defocus` stays within the ±2·λ·N² depth of
    focus of :func:`depth_of_focus` (the Rayleigh quarter-wave criterion), ``FAIL`` beyond it.
    Judged on the size of the defocus, because the depth of focus runs both ways. The thermal
    focal shift follows Jamieson (1981); every glass property is the caller's, stated at the
    wavelength and temperature range the design runs at.
    """
    shift = thermal_focal_shift(
        focal_length=focal_length,
        refractive_index=refractive_index,
        dn_dt=dn_dt,
        glass_cte=glass_cte,
        temperature_change=temperature_change,
    )
    defocus = athermal_defocus(
        focal_shift=shift,
        housing_cte=housing_cte,
        housing_length=housing_length,
        temperature_change=temperature_change,
    )
    tolerance = depth_of_focus(wavelength=wavelength, f_number=f_number)
    size = Quantity(magnitude=abs(defocus.to("µm").magnitude), unit="µm")
    comparison = Comparison(
        measured=size,
        limit=tolerance,
        sense=LimitSense.AT_MOST,
        measured_label="defocus",
        limit_label="depth of focus",
        minimum_decimals=1,
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=comparison.sentence(),
        reference=_JAMIESON,
        comparison=comparison,
        derivation=Derivation(
            symbolic="δ = Δf − α_h · L · ΔT",
            inputs=(
                SymbolValue(
                    symbol="Δf",
                    description=("the lens's thermal focal shift, f·(α_g − (dn/dT)/(n − 1))·ΔT"),
                    value=shift,
                    unit="µm",
                ),
                SymbolValue(
                    symbol="α_h",
                    description="the housing's coefficient of thermal expansion",
                    value=housing_cte.to("1/K"),
                    unit="1/K",
                ),
                SymbolValue(
                    symbol="L",
                    description="the lens-to-image spacing the housing sets",
                    value=Quantity(magnitude=housing_length.to("µm").magnitude, unit="µm"),
                    unit="µm",
                ),
                SymbolValue(
                    symbol="ΔT",
                    description="the temperature change",
                    value=Quantity(
                        magnitude=temperature_difference_kelvin(
                            temperature_change, name="temperature_change"
                        ),
                        unit="K",
                    ),
                    unit="K",
                ),
            ),
            result=SymbolValue(
                symbol="δ", description="defocus at the detector", value=defocus, unit="µm"
            ),
            citation=_JAMIESON,
        ),
    )


def miles_random_vibration_grms(
    *, natural_frequency: Quantity, quality_factor: float, input_asd: Quantity
) -> float:
    """The RMS response of a single mode to flat random input, by Miles' equation.

    G_rms = √(π/2 · f_n · Q · ASD) (Miles, Journal of the Aeronautical Sciences, 1954), for a
    single-degree-of-freedom mount of ``natural_frequency`` f_n and amplification
    ``quality_factor`` Q under an ``input_asd`` flat across the resonance, in g²/Hz — written
    as a per-hertz quantity (``0.04 1/Hz``), because in a unit string ``g`` is the gram.
    Returned in g (standard gravities). Three times it is the 3σ peak a mount is sized to.

    Q is required and never defaulted: the answer scales with √Q, and the common "Q = 10"
    is an assumption about somebody else's mount. The flat-input premise is the caller's to
    hold; a spectrum that rolls off across the resonance is not what this answers.
    """
    _check(natural_frequency, "[frequency]", "natural_frequency")
    _check(input_asd, "1 / [frequency]", "input_asd")
    fn = natural_frequency.to("Hz").magnitude
    quality = require_finite(quality_factor, name="quality_factor")
    asd = input_asd.to("1/Hz").magnitude
    if fn <= 0:
        raise ValueError(f"natural_frequency must be positive; got {natural_frequency}")
    if quality <= 0.5:
        raise ValueError(
            f"quality_factor must exceed 0.5 for a mode that resonates at all; got {quality}"
        )
    if asd <= 0:
        raise ValueError(f"input_asd must be positive (g²/Hz); got {input_asd}")
    return sqrt(pi / 2 * fn * quality * asd)


def retention_preload(*, mass: Quantity, acceleration: float) -> Quantity:
    """The axial preload that keeps an optic seated against an ``acceleration`` in g.

    P = m·a·g₀ (Yoder, Opto-Mechanical Systems Design): the retainer must press the element
    against its seat at least as hard as the acceleration tries to lift it off, or the lens
    unseats, rattles and comes back somewhere else. ``mass`` is the element's; the
    ``acceleration`` is the worst axial one it must hold through, in g, positive. Returned in
    newtons. Friction does not enter an axial hold, which is why this is the floor.
    """
    _check(mass, "[mass]", "mass")
    m = mass.to("kg").magnitude
    a = require_finite(acceleration, name="acceleration")
    if m <= 0:
        raise ValueError(f"mass must be positive; got {mass}")
    if a <= 0:
        raise ValueError(f"acceleration must be positive, in g; got {acceleration}")
    return Quantity(magnitude=m * a * _STANDARD_GRAVITY, unit="N")


def stress_birefringence_retardance(
    *, stress_optic_coefficient: Quantity, stress: Quantity, path_length: Quantity
) -> Quantity:
    """The optical path difference stress induces in glass, OPD = K·σ·t.

    A stressed glass is birefringent: the two polarizations see different indices, and over
    ``path_length`` t under ``stress`` σ they separate by K·σ·t for a ``stress_optic_coefficient``
    K (Yoder, Opto-Mechanical Systems Design; the coefficient is the glass maker's, quoted in
    mm²/N or 1/Pa). Signed as the stress is. Returned in nanometres, the unit a retardance
    budget is written in.
    """
    _check(stress_optic_coefficient, "1 / [pressure]", "stress_optic_coefficient")
    _check(stress, "[pressure]", "stress")
    _check(path_length, "[length]", "path_length")
    t = path_length.to("m").magnitude
    if t <= 0:
        raise ValueError(f"path_length must be positive; got {path_length}")
    opd = stress_optic_coefficient.to("1/Pa").magnitude * stress.to("Pa").magnitude * t
    return Quantity(magnitude=opd * 1e9, unit="nm")


def marechal_strehl_ratio(*, rms_wavefront_error: Quantity, wavelength: Quantity) -> float:
    """The Strehl ratio an RMS wavefront error allows, S ≈ exp(−(2π·σ/λ)²).

    The Maréchal approximation: the peak intensity of the aberrated image relative to a
    perfect one, for an ``rms_wavefront_error`` σ at ``wavelength`` λ. Good for small errors —
    the region a diffraction-limited design lives in — and optimistic well beyond it.
    Maréchal's criterion calls an image diffraction-limited at S ≥ 0.8, σ ≈ λ/14.
    """
    _check(rms_wavefront_error, "[length]", "rms_wavefront_error")
    _check(wavelength, "[length]", "wavelength")
    sigma = rms_wavefront_error.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if sigma < 0:
        raise ValueError(f"rms_wavefront_error cannot be negative; got {rms_wavefront_error}")
    if lam <= 0:
        raise ValueError(f"wavelength must be positive; got {wavelength}")
    return exp(-((2 * pi * sigma / lam) ** 2))


def wavefront_budget_scorecard(
    name: str,
    *,
    contributors: Mapping[str, Quantity],
    wavelength: Quantity,
    strehl_threshold: float,
) -> ScorecardEntry:
    """Screen a root-sum-square wavefront error budget against a declared Strehl threshold.

    The ``contributors`` are independent RMS wavefront errors, each named: surface figure,
    mount distortion, alignment, thermal. They combine as the root sum of squares, and the
    total passes when its Maréchal Strehl ratio (:func:`marechal_strehl_ratio`) meets
    ``strehl_threshold``. The threshold is declared, never defaulted: 0.8 is Maréchal's
    diffraction limit, and a system that only needs to resolve a feature twice the size may
    declare less.

    An empty budget is refused: a total of nothing is a zero error, which would pass.
    """
    threshold = require_finite(strehl_threshold, name="strehl_threshold")
    if not 0 < threshold < 1:
        raise ValueError(
            f"strehl_threshold must lie strictly between 0 and 1; got {strehl_threshold}"
        )
    if not contributors:
        raise ValueError(
            "a wavefront budget needs at least one contributor; a total of none is a zero "
            "error, and a budget that passes on nothing has not been written"
        )
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("nm").magnitude
    if lam <= 0:
        raise ValueError(f"wavelength must be positive; got {wavelength}")
    terms = []
    for label, error in contributors.items():
        _check(error, "[length]", f"contributor '{label}'")
        value = error.to("nm").magnitude
        if value < 0:
            raise ValueError(f"contributor '{label}' is a negative RMS error: {error}")
        terms.append(value)
    total = sqrt(sum(value * value for value in terms))
    # The RMS error at which the declared Strehl is exactly met, from S = exp(−(2πσ/λ)²).
    allowed = lam / (2 * pi) * sqrt(-log(threshold))
    comparison = Comparison(
        measured=Quantity(magnitude=total, unit="nm"),
        limit=Quantity(magnitude=allowed, unit="nm"),
        sense=LimitSense.AT_MOST,
        measured_label="RSS wavefront error",
        limit_label=f"RMS error at Strehl {threshold:g}",
        minimum_decimals=1,
    )
    symbols = [f"σ_{index}" for index in range(1, len(terms) + 1)]
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=comparison.sentence(),
        reference="Maréchal criterion, S = exp(−(2πσ/λ)²)",
        comparison=comparison,
        derivation=Derivation(
            symbolic="σ = √(" + " + ".join(f"{symbol}²" for symbol in symbols) + ")",
            inputs=tuple(
                SymbolValue(
                    symbol=symbol,
                    description=f"{label}, RMS",
                    value=Quantity(magnitude=value, unit="nm"),
                    unit="nm",
                )
                for symbol, label, value in zip(symbols, contributors, terms, strict=True)
            ),
            result=SymbolValue(
                symbol="σ",
                description="the budget's root-sum-square total",
                value=Quantity(magnitude=total, unit="nm"),
                unit="nm",
            ),
            citation="Maréchal criterion, S = exp(−(2πσ/λ)²)",
        ),
    )


def internal_condensation_scorecard(
    name: str,
    *,
    coldest_surface_temperature: Quantity,
    internal_dew_point: Quantity | None = None,
    fill_temperature: Quantity | None = None,
    fill_relative_humidity: float | None = None,
) -> ScorecardEntry:
    """Screen a sealed optical housing for fogging at its cold soak.

    Water sealed inside condenses on the first surface colder than its dew point, and on an
    optic that is fog. ``PASS`` when the ``coldest_surface_temperature`` at the declared cold
    soak stays at or above the internal dew point, ``FAIL`` below it, naming the margin.

    The dew point is the declared ``internal_dew_point`` — a purge gas's specification — or,
    failing that, the one a ``fill_temperature`` and ``fill_relative_humidity`` imply through
    the Magnus form of Alduchov and Eskridge (1996) that
    :func:`~anvilate.analysis.psychrometrics.dew_point_temperature` evaluates, taking the water
    sealed in as fixed. With neither, the entry is ``not_evaluated`` naming both: an unstated purge
    is not a dry one.
    """
    _check(coldest_surface_temperature, "[temperature]", "coldest_surface_temperature")
    surface = coldest_surface_temperature.to("K").magnitude
    if surface <= 0:
        raise ValueError("coldest_surface_temperature must be above absolute zero")
    if internal_dew_point is not None:
        _check(internal_dew_point, "[temperature]", "internal_dew_point")
        dew = internal_dew_point.to("K").magnitude
        basis = "the declared internal dew point"
    elif fill_temperature is not None and fill_relative_humidity is not None:
        humidity = require_finite(fill_relative_humidity, name="fill_relative_humidity")
        if not 0 < fill_relative_humidity <= 1:
            raise ValueError(
                f"fill_relative_humidity is a fraction in (0, 1]; got {fill_relative_humidity}"
            )
        vapour = saturation_vapor_pressure(temperature=fill_temperature).to("Pa").magnitude
        dew = (
            dew_point_temperature(vapor_pressure=Quantity(magnitude=humidity * vapour, unit="Pa"))
            .to("K")
            .magnitude
        )
        fill = fill_temperature.to("K").magnitude - 273.15
        basis = f"the dew point of a fill at {fill:.1f} °C and {humidity:.0%} relative humidity"
    else:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "not evaluated — the sealed volume declares neither an internal dew point nor "
                "a fill temperature and relative humidity; an unstated purge is not a dry one"
            ),
        )
    comparison = Comparison(
        measured=Quantity(magnitude=surface - 273.15, unit="°C"),
        limit=Quantity(magnitude=dew - 273.15, unit="°C"),
        sense=LimitSense.AT_LEAST,
        measured_label="coldest internal surface",
        limit_label="internal dew point",
        minimum_decimals=1,
    )
    margin = surface - dew
    consequence = (
        f", {margin:.1f} K clear"
        if comparison.passes()
        else f": the optic fogs, {-margin:.1f} K short"
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=f"{comparison.sentence()}{consequence} — {basis}",
        reference=_ALDUCHOV,
        comparison=comparison,
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "a comparison of two temperatures; the dew point is declared, or read off the "
                "Magnus curve by its inverse"
            ),
        ),
    )


_STANDARD_GRAVITY = 9.80665  # m/s², the conventional g₀ of the CGPM (1901)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    require_finite(value, name=name)
