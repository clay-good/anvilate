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
from enum import StrEnum
from math import cos, exp, isfinite, log, pi, sin, sqrt
from typing import TYPE_CHECKING

from pydantic import ConfigDict, model_validator

from .._models import Named, Provenance, StatableModel, cited
from ..budget import CombinationRule
from ..derivation import Derivation, DerivationAbsence, SymbolValue, Underived
from ..scorecard import CheckStatus, Comparison, LimitSense, ScorecardEntry
from ..units import Quantity, require_finite, temperature_difference_kelvin
from .dynamics import half_sine_shock_amplification
from .o_ring import o_ring_gland_fill_fraction, o_ring_squeeze_fraction, o_ring_stretch_fraction
from .plate import simply_supported_circular_plate_uniform_load
from .psychrometrics import dew_point_temperature, saturation_vapor_pressure
from .thermal import temperature_rise

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
    "mount_decenter",
    "decenter_line_of_sight",
    "mirror_tilt_line_of_sight",
    "tilted_plate_image_shift",
    "tilted_plate_focus_shift",
    "ThermalConditionKind",
    "ThermalCondition",
    "dynamic_clearance_scorecard",
    "athermal_bond_thickness",
    "seal_gland_extremes_scorecard",
    "OutsideValidRange",
    "RangedProperty",
    "OpticalMaterial",
    "N_BK7",
    "boresight_scorecard",
    "enclosure_rise_scorecard",
    "ShockPulse",
    "ShockEnvironment",
    "SurfaceDeformation",
    "Prescription",
    "preload_temperature_scorecard",
    "glass_contact_stress_scorecard",
    "BreathingMitigation",
    "seal_breathing_scorecard",
    "window_pressure_opd",
    "pressure_window_scorecard",
    "HarnessCrossing",
    "harness_load_scorecard",
    "cycling_retention_scorecard",
    "SurfaceTreatment",
    "SurfaceLimits",
    "surface_limits_scorecard",
    "OutgassingRecord",
    "outgassing_census_scorecard",
    "iso_cleanroom_concentration",
    "CleanlinessRequirement",
    "cleanliness_scorecard",
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


def mount_decenter(*, mass: Quantity, acceleration: float, radial_stiffness: Quantity) -> Quantity:
    """How far an element moves sideways in its mount under a lateral acceleration, m·a·g₀/k.

    The mount's ``radial_stiffness`` k resists the inertial load of the element's ``mass``
    under an ``acceleration`` in g (Yoder, Opto-Mechanical Systems Design): a quasi-static
    decenter, the input to :func:`decenter_line_of_sight`. A resonant input amplifies it —
    scale the acceleration by the mount's response first (:func:`miles_random_vibration_grms`).
    Returned in micrometres.
    """
    _check(mass, "[mass]", "mass")
    _check(radial_stiffness, "[force] / [length]", "radial_stiffness")
    m = mass.to("kg").magnitude
    a = require_finite(acceleration, name="acceleration")
    k = radial_stiffness.to("N/m").magnitude
    if m <= 0:
        raise ValueError(f"mass must be positive; got {mass}")
    if k <= 0:
        raise ValueError(f"radial_stiffness must be positive; got {radial_stiffness}")
    return Quantity(magnitude=m * a * _STANDARD_GRAVITY / k * 1e6, unit="µm")


def decenter_line_of_sight(*, decenter: Quantity, focal_length: Quantity) -> Quantity:
    """The line-of-sight shift a lens decenter causes, θ = Δ/f.

    A lens of ``focal_length`` f imaging a distant object moves its image sideways by as much
    as the lens moves, so a ``decenter`` Δ turns the line of sight through Δ/f (Yoder,
    Opto-Mechanical Systems Design). A long focal length forgives a decenter that a short one
    does not. Returned in microradians.
    """
    _check(decenter, "[length]", "decenter")
    _check(focal_length, "[length]", "focal_length")
    f = focal_length.to("m").magnitude
    if f <= 0:
        raise ValueError(f"focal_length must be positive; got {focal_length}")
    return Quantity(magnitude=decenter.to("m").magnitude / f * 1e6, unit="µrad")


def mirror_tilt_line_of_sight(*, tilt: Quantity) -> Quantity:
    """The line-of-sight shift a mirror tilt causes: twice the tilt.

    By the law of reflection (Hecht, Optics) a mirror turned through an angle turns the
    reflected ray through twice it, which is why a fold mirror's mount is held to half the
    pointing error of a lens's. ``tilt`` is an angle quantity in rad, mrad, µrad, deg, arcmin or
    arcsec; any other unit is refused, because a strain in mm/m would otherwise convert to
    radians without complaint. Returned in microradians.
    """
    return Quantity(magnitude=2.0 * _radians(tilt, "tilt") * 1e6, unit="µrad")


def _plate_normal_shift(thickness: Quantity, refractive_index: float, tilt: Quantity) -> float:
    _check(thickness, "[length]", "thickness")
    t = thickness.to("m").magnitude
    if t <= 0:
        raise ValueError(f"thickness must be positive; got {thickness}")
    if not (isfinite(refractive_index) and refractive_index >= 1.0):
        raise ValueError(f"refractive_index must be at least 1; got {refractive_index}")
    theta = _radians(tilt, "tilt")
    if not abs(theta) < pi / 2:
        raise ValueError(f"tilt must be less than 90° from the plate normal; got {tilt}")
    return t * (1.0 - cos(theta) / sqrt(refractive_index**2 - sin(theta) ** 2))


def tilted_plate_image_shift(
    *, thickness: Quantity, refractive_index: float, tilt: Quantity
) -> Quantity:
    """The sideways image shift a tilted plane-parallel plate causes, in µm.

    A window, filter or beamsplitter plate of ``thickness`` t and index n, tilted by θ to the
    beam, offsets each ray along the plate normal by s = t·[1 − cosθ/√(n² − sin²θ)] (Smith,
    Modern Optical Engineering). The offset across the beam, s·sinθ, moves the image sideways
    by that much, with the sign of the tilt. With the plate in a converging beam, that shift
    divided by the focal length is the line-of-sight change, which
    :func:`decenter_line_of_sight` computes. The same plate adds astigmatism in a converging
    beam, and this function does not screen for it.
    """
    s = _plate_normal_shift(thickness, refractive_index, tilt)
    return Quantity(magnitude=s * sin(_radians(tilt, "tilt")) * 1e6, unit="µm")


def tilted_plate_focus_shift(
    *, thickness: Quantity, refractive_index: float, tilt: Quantity
) -> Quantity:
    """How far tilting a plane-parallel plate moves focus, relative to the plate square on.

    A plate square to a converging beam already moves focus back by t·(n − 1)/n, which the
    design absorbs. Tilting it by θ changes the shift along the axis to s·cosθ, where
    s = t·[1 − cosθ/√(n² − sin²θ)] (Smith, Modern Optical Engineering). The difference is what
    enters a focus budget as a contributor. Returned in µm, positive away from the plate.
    """
    s = _plate_normal_shift(thickness, refractive_index, tilt)
    n = refractive_index
    nominal = thickness.to("m").magnitude * (n - 1.0) / n
    axial = s * cos(_radians(tilt, "tilt"))
    return Quantity(magnitude=(axial - nominal) * 1e6, unit="µm")


class ThermalConditionKind(StrEnum):
    """What a thermal condition is — the thing every thermal screen is only valid for some of.

    Uniform soak, spatial gradient and transient are the three cases Yoder's Opto-Mechanical
    Systems Design treats separately, because each moves an optic differently.
    """

    SOAK = "soak"
    GRADIENT = "gradient"
    TRANSIENT = "transient"


# How close to equilibrium a dwell must bring the assembly before an equilibrium screen's
# answer describes it: three time constants, 1 − e⁻³ ≈ 95% of the change. A practice
# convention for a lumped first-order response, not a cited clause.
_EQUILIBRIUM_TIME_CONSTANTS = 3.0


class ThermalCondition(StatableModel):
    """A declared thermal condition, with its kind stated rather than assumed.

    A ``soak`` brings the whole assembly to one temperature; a ``gradient`` holds it across
    one; a ``transient`` is a change over a ``dwell``, reaching equilibrium only as the dwell
    approaches the assembly's ``time_constant``. The kind has no default: a gradient read as a
    soak misses the wedge and surface deformation the gradient actually causes (Yoder,
    Opto-Mechanical Systems Design). The transient's approach to equilibrium is the
    first-order lumped response 1 − exp(−t/τ) of Incropera's lumped-capacitance method.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ThermalConditionKind
    temperature_change: Quantity
    dwell: Quantity | None = None
    time_constant: Quantity | None = None

    @model_validator(mode="after")
    def _complete(self) -> ThermalCondition:
        _check(self.temperature_change, "[temperature]", "temperature_change")
        if self.kind is ThermalConditionKind.TRANSIENT:
            if self.dwell is None or self.time_constant is None:
                raise ValueError(
                    "a transient condition needs its dwell and the assembly's time constant; "
                    "without them nothing says whether it reaches equilibrium"
                )
        for value, name in ((self.dwell, "dwell"), (self.time_constant, "time_constant")):
            if value is not None:
                _check(value, "[time]", name)
                if value.to("s").magnitude <= 0:
                    raise ValueError(f"{name} must be positive; got {value}")
        return self

    @property
    def equilibrium_fraction(self) -> float:
        """How much of the change a first-order assembly reaches by the end of the dwell.

        ``1 − exp(−dwell/τ)``; 1.0 for a soak or a gradient, which are equilibrium states.
        """
        if self.dwell is None or self.time_constant is None:
            return 1.0
        return 1.0 - exp(-self.dwell.to("s").magnitude / self.time_constant.to("s").magnitude)

    def qualify(self, entry: ScorecardEntry) -> ScorecardEntry:
        """A soak screen's ``entry`` as this condition allows it to stand.

        Under a gradient the entry is replaced by ``not_evaluated``, naming the mismatch: a
        uniform-soak screen does not describe a part held across a gradient. Under a transient
        whose dwell falls short of three time constants the verdict stands and says it is
        optimistic, naming both durations. A soak leaves the entry as it was.
        """
        if self.kind is ThermalConditionKind.GRADIENT:
            return ScorecardEntry(
                name=entry.name,
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    "not evaluated — this screen requires a uniform soak and the declared "
                    "thermal condition is a gradient, which bends and wedges the element in "
                    "ways a soak does not"
                ),
            )
        if self.kind is ThermalConditionKind.TRANSIENT and entry.evaluated:
            assert self.dwell is not None and self.time_constant is not None
            needed = _EQUILIBRIUM_TIME_CONSTANTS * self.time_constant.to("s").magnitude
            if self.dwell.to("s").magnitude < needed:
                note = (
                    f" — optimistic: the declared dwell of {self.dwell} does not reach "
                    f"equilibrium against a time constant of {self.time_constant} "
                    f"({self.equilibrium_fraction:.0%} of the change), and this is an "
                    "equilibrium result"
                )
                return entry.model_copy(update={"detail": f"{entry.detail}{note}"})
        return entry


def dynamic_clearance_scorecard(
    name: str,
    *,
    natural_frequency: Quantity,
    peak_acceleration: float,
    pulse_duration: Quantity,
    gap: Quantity | None = None,
) -> ScorecardEntry:
    """Screen an internal gap against the displacement a half-sine shock drives across it.

    An element on a mount of ``natural_frequency`` f_n under a half-sine pulse of
    ``peak_acceleration`` a₀ (in g) over ``pulse_duration`` responds with A·a₀, where A is the
    undamped shock amplification of
    :func:`~anvilate.analysis.dynamics.half_sine_shock_amplification` — the maximax response
    spectrum ordinate. Its peak relative displacement is that acceleration over ω²,
    x = A·a₀·g₀/(2π·f_n)² (Harris, Shock and Vibration Handbook). ``PASS`` while x stays within
    the declared ``gap``, ``FAIL`` when the element would strike across it — whatever the
    nominal geometry says, because an intrusion check is computed at rest.

    With no gap declared the entry is ``not_evaluated``, naming it: an undeclared gap is not
    a generous one.
    """
    # The environment is checked whether or not a gap is declared: a NaN acceleration is a
    # mistake in the document either way, and must not hide behind the missing gap.
    _check(natural_frequency, "[frequency]", "natural_frequency")
    a0 = require_finite(peak_acceleration, name="peak_acceleration")
    if a0 <= 0:
        raise ValueError(f"peak_acceleration must be positive, in g; got {peak_acceleration}")
    amplification = half_sine_shock_amplification(
        pulse_duration=pulse_duration, natural_frequency=natural_frequency
    )
    if gap is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "not evaluated — no internal gap is declared for the shock displacement to be "
                "judged against; an undeclared gap is not a generous one"
            ),
        )
    _check(gap, "[length]", "gap")
    if gap.to("m").magnitude <= 0:
        raise ValueError(f"gap must be positive; got {gap}")
    omega = 2 * pi * natural_frequency.to("Hz").magnitude
    displacement = amplification * a0 * _STANDARD_GRAVITY / omega**2
    comparison = Comparison(
        measured=Quantity(magnitude=displacement * 1e6, unit="µm"),
        limit=Quantity(magnitude=gap.to("m").magnitude * 1e6, unit="µm"),
        sense=LimitSense.AT_MOST,
        measured_label="shock displacement",
        limit_label="declared gap",
        minimum_decimals=1,
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=comparison.sentence(),
        reference=_HARRIS,
        comparison=comparison,
        derivation=Derivation(
            symbolic="x = A · a₀ · g₀ / ω²",
            inputs=(
                SymbolValue(
                    symbol="A",
                    description="undamped half-sine shock amplification (maximax SRS)",
                    value=amplification,
                ),
                SymbolValue(symbol="a₀", description="pulse peak, in g", value=a0),
                SymbolValue(
                    symbol="g₀",
                    description="standard gravity",
                    value=Quantity(magnitude=_STANDARD_GRAVITY, unit="m/s**2"),
                    unit="m/s**2",
                ),
                SymbolValue(
                    symbol="ω",
                    description="the mount's natural frequency, 2π·f_n",
                    value=Quantity(magnitude=omega, unit="rad/s"),
                    unit="rad/s",
                ),
            ),
            result=SymbolValue(
                symbol="x",
                description="peak relative displacement",
                value=Quantity(magnitude=displacement * 1e6, unit="µm"),
                unit="µm",
            ),
            citation=_HARRIS,
        ),
    )


def athermal_bond_thickness(
    *,
    glass_diameter: Quantity,
    glass_cte: Quantity,
    cell_cte: Quantity,
    elastomer_cte: Quantity,
) -> Quantity:
    """The elastomer bond thickness that keeps a bonded lens radially athermal, Bayar (1981).

    A lens of ``glass_diameter`` D and ``glass_cte`` α_G, bonded into a cell of ``cell_cte`` α_M
    by an annulus of elastomer with ``elastomer_cte`` α_e, stays unstressed across temperature
    when the cell's bore grows exactly as fast as the glass and the bond together:
    α_M·(D/2 + h) = α_G·D/2 + α_e·h, so h = (D/2)·(α_M − α_G)/(α_e − α_M) (Bayar, Lens barrel
    optomechanical design principles, Optical Engineering 20(2) 1981; Yoder,
    Opto-Mechanical Systems Design). A 50 mm crown lens in aluminium with a silicone bond
    needs about 1.8 mm.

    **Poisson's ratio is not in it.** The formula treats the elastomer as free to expand in
    thickness alone; a nearly incompressible elastomer confined in a thin annulus cannot, and
    its effective radial expansion is larger than α_e, so the true athermal thickness is
    smaller than this. Read the result as the classical estimate that corrections refine,
    not as the answer to a bond with a Poisson's ratio near 0.5.

    A thickness exists only for α_e > α_M > α_G — an elastomer that out-expands the cell, in
    a cell that out-expands the glass. Any other ordering has no positive solution and is
    refused naming it. Returned in millimetres.
    """
    _check(glass_diameter, "[length]", "glass_diameter")
    for value, name in (
        (glass_cte, "glass_cte"),
        (cell_cte, "cell_cte"),
        (elastomer_cte, "elastomer_cte"),
    ):
        _check(value, "1 / [temperature]", name)
    diameter = glass_diameter.to("mm").magnitude
    if diameter <= 0:
        raise ValueError(f"glass_diameter must be positive; got {glass_diameter}")
    a_g, a_m, a_e = (v.to("1/K").magnitude for v in (glass_cte, cell_cte, elastomer_cte))
    if not a_e > a_m > a_g:
        raise ValueError(
            "an athermal bond needs α_e > α_M > α_G — an elastomer that out-expands the cell, "
            f"in a cell that out-expands the glass; got α_e = {elastomer_cte}, "
            f"α_M = {cell_cte}, α_G = {glass_cte}, which has no positive thickness"
        )
    return Quantity(magnitude=diameter / 2 * (a_m - a_g) / (a_e - a_m), unit="mm")


# The Parker O-Ring Handbook's static-seal targets, the bands the o_ring module's docstrings
# already state: squeeze 15-30 %, gland fill at most 85 %, stretch at most 5 %.
_SQUEEZE_BAND = (0.15, 0.30)
_FILL_MAX = 0.85
_STRETCH_MAX = 0.05


def seal_gland_extremes_scorecard(
    name: str,
    *,
    cross_section_diameter: Quantity,
    inner_diameter: Quantity,
    gland_depth: Quantity,
    groove_width: Quantity,
    groove_diameter: Quantity,
    elastomer_cte: Quantity,
    gland_cte: Quantity,
    assembly_temperature: Quantity,
    cold: Quantity,
    hot: Quantity,
) -> ScorecardEntry:
    """Screen an O-ring gland at both temperature extremes, not only at assembly.

    An elastomer expands an order of magnitude faster than the metal around it, so a gland
    that seals at assembly can lose its squeeze cold and overfill hot. The O-ring's
    ``cross_section_diameter`` and ``inner_diameter`` scale with ``elastomer_cte``, the
    gland's ``gland_depth``, ``groove_width`` and ``groove_diameter`` with ``gland_cte``, from
    ``assembly_temperature`` to each of ``cold`` and ``hot``. At each, the squeeze, fill and
    stretch of :mod:`~anvilate.analysis.o_ring` are held to the Parker O-Ring Handbook's
    static-seal bands — squeeze 15-30 %, fill at most 85 %, stretch at most 5 % — and the
    entry fails naming every ratio out of band and at which extreme. A squeeze that falls to
    nothing cold is a leak, reported as one rather than raised.
    """
    _check(elastomer_cte, "1 / [temperature]", "elastomer_cte")
    _check(gland_cte, "1 / [temperature]", "gland_cte")
    _check(assembly_temperature, "[temperature]", "assembly_temperature")

    def scaled(value: Quantity, name: str, factor: float) -> Quantity:
        _check(value, "[length]", name)
        return Quantity(magnitude=value.to("mm").magnitude * factor, unit="mm")

    ratios: dict[str, dict[str, float | None]] = {}
    for label, extreme in (("cold", cold), ("hot", hot)):
        _check(extreme, "[temperature]", label)
        delta = extreme.to("K").magnitude - assembly_temperature.to("K").magnitude
        rubber = 1 + elastomer_cte.to("1/K").magnitude * delta
        metal = 1 + gland_cte.to("1/K").magnitude * delta
        cs = scaled(cross_section_diameter, "cross_section_diameter", rubber)
        ring = scaled(inner_diameter, "inner_diameter", rubber)
        depth = scaled(gland_depth, "gland_depth", metal)
        width = scaled(groove_width, "groove_width", metal)
        bottom = scaled(groove_diameter, "groove_diameter", metal)
        squeeze: float | None
        try:
            squeeze = o_ring_squeeze_fraction(cross_section_diameter=cs, gland_depth=depth)
        except ValueError:
            squeeze = None  # the gland is at least as deep as the cord: nothing is squeezed
        stretch: float | None
        try:
            stretch = o_ring_stretch_fraction(inner_diameter=ring, groove_diameter=bottom)
        except ValueError:
            stretch = 0.0  # the ring is looser than the groove: unstretched
        ratios[label] = {
            "squeeze": squeeze,
            "fill": o_ring_gland_fill_fraction(
                cross_section_diameter=cs, gland_depth=depth, groove_width=width
            ),
            "stretch": stretch,
        }
    findings = []
    for label, values in ratios.items():
        squeeze = values["squeeze"]
        if squeeze is None:
            findings.append(f"{label}: no squeeze — the gland is as deep as the cord, a leak")
        elif not _SQUEEZE_BAND[0] <= squeeze <= _SQUEEZE_BAND[1]:
            findings.append(f"{label}: squeeze {squeeze:.1%} outside 15-30 %")
        fill = values["fill"]
        assert fill is not None
        if fill > _FILL_MAX:
            findings.append(f"{label}: fill {fill:.1%} above 85 %")
        stretch = values["stretch"]
        if stretch is not None and stretch > _STRETCH_MAX:
            findings.append(f"{label}: stretch {stretch:.1%} above 5 %")

    def described(label: str) -> str:
        values = ratios[label]
        squeeze = values["squeeze"]
        shown = "none" if squeeze is None else f"{squeeze:.1%}"
        return (
            f"{label} squeeze {shown}, fill {values['fill']:.1%}, stretch {values['stretch']:.1%}"
        )

    summary = f"{described('cold')}; {described('hot')}"
    governing = sorted({finding.split(":")[0] for finding in findings})
    detail = (
        f"out of band at {' and '.join(governing)} — {'; '.join(findings)} ({summary})"
        if findings
        else f"in band at both extremes ({summary})"
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.FAIL if findings else CheckStatus.PASS,
        detail=detail,
        reference="Parker O-Ring Handbook, static-seal squeeze, fill and stretch",
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "three geometric ratios at two temperatures, each held to a handbook band; "
                "the ratios' own arithmetic is in anvilate.analysis.o_ring"
            ),
        ),
    )


class OutsideValidRange(ValueError):
    """A property asked for outside the temperature range its source states it for.

    Glass catalogues such as SCHOTT's state expansion per temperature range, not as one
    number good everywhere.
    """


class RangedProperty(StatableModel):
    """A material property, the temperature range its source states it for, and that source.

    The shape SCHOTT's catalogue uses for expansion: 7.1 ppm/K over 243-343 K for N-BK7, and
    a different value over 293-573 K.

    A coefficient of expansion quoted for 243-343 K is not a value at 400 K: using it there is
    an invented number with a citation attached, so :meth:`covers` is checked by everything
    that reads one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Quantity
    low: Quantity
    high: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _a_range(self) -> RangedProperty:
        _check(self.low, "[temperature]", "low")
        _check(self.high, "[temperature]", "high")
        require_finite(self.value, name="value")
        if not self.low.to("K").magnitude < self.high.to("K").magnitude:
            raise ValueError(f"a valid range runs low to high; got {self.low} to {self.high}")
        return self

    def covers(self, low: Quantity, high: Quantity) -> bool:
        return (
            self.low.to("K").magnitude <= low.to("K").magnitude
            and high.to("K").magnitude <= self.high.to("K").magnitude
        )

    def __str__(self) -> str:
        return f"{self.value} over {self.low} to {self.high} [{self.source}]"


class OpticalMaterial(StatableModel):
    """An optical glass as a record: every property with where it came from.

    ``refractive_index`` and ``abbe_number`` are at the d line. Expansion is a set of
    :class:`RangedProperty` values, each good only over its own temperature range. The
    thermo-optic, elastic, hardness and stress-optic properties are optional: a catalogue
    that does not state one leaves it ``None``, and a screen that needs it says so rather
    than using a recalled number. Glass data in this library comes from sources it may
    redistribute — the bundled :data:`N_BK7` from the SCHOTT catalogue via the CC0
    refractiveindex.info database.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    source: Provenance
    refractive_index: float
    abbe_number: float
    cte: tuple[RangedProperty, ...]
    density: Quantity | None = None
    dn_dt: RangedProperty | None = None
    elastic_modulus: Quantity | None = None
    poisson_ratio: float | None = None
    stress_optic_coefficient: Quantity | None = None

    @model_validator(mode="after")
    def _a_glass(self) -> OpticalMaterial:
        if not self.refractive_index > 1:
            raise ValueError(f"{self.name}: refractive_index must exceed 1")
        if not self.cte:
            raise ValueError(f"{self.name}: a glass record needs at least one stated CTE range")
        for ranged in self.cte:
            _check(ranged.value, "1 / [temperature]", "cte")
        return self

    def cte_over(self, low: Quantity, high: Quantity) -> Quantity:
        """The stated expansion coefficient for a swing from ``low`` to ``high``.

        Refused with :class:`OutsideValidRange`, naming every stated range, when no single
        range covers the swing — a coefficient carried past its range is an invented one.
        """
        _check(low, "[temperature]", "low")
        _check(high, "[temperature]", "high")
        lo, hi = sorted((low, high), key=lambda t: t.to("K").magnitude)
        for ranged in self.cte:
            if ranged.covers(lo, hi):
                return ranged.value
        stated = "; ".join(f"{r.low} to {r.high}" for r in self.cte)
        raise OutsideValidRange(
            f"{self.name}'s expansion is stated for {stated}, and {lo} to {hi} is inside none "
            "of them"
        )

    def athermal_focus(
        self,
        name: str,
        *,
        dn_dt: Quantity,
        focal_length: Quantity,
        f_number: float,
        wavelength: Quantity,
        housing_cte: Quantity,
        housing_length: Quantity,
        low: Quantity,
        high: Quantity,
    ) -> ScorecardEntry:
        """:func:`athermal_focus_scorecard` with the index and expansion read from this record.

        The swing from ``low`` to ``high`` must lie inside a stated expansion range, or the
        entry is ``not_evaluated`` naming the ranges. ``dn_dt`` stays the caller's unless the
        record states one covering the swing, because it depends on wavelength and the
        medium it is quoted against.
        """
        try:
            cte = self.cte_over(low, high)
        except OutsideValidRange as outside:
            return ScorecardEntry(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail=f"not evaluated — {outside}",
            )
        if self.dn_dt is not None and self.dn_dt.covers(
            *sorted((low, high), key=lambda t: t.to("K").magnitude)
        ):
            dn_dt = self.dn_dt.value
        return athermal_focus_scorecard(
            name,
            focal_length=focal_length,
            f_number=f_number,
            wavelength=wavelength,
            refractive_index=self.refractive_index,
            dn_dt=dn_dt,
            glass_cte=cte,
            housing_cte=housing_cte,
            housing_length=housing_length,
            temperature_change=Quantity(
                magnitude=high.to("K").magnitude - low.to("K").magnitude, unit="K"
            ),
        )

    def __str__(self) -> str:
        return (
            f"{self.name}: n_d {self.refractive_index}, V_d {self.abbe_number}, "
            f"CTE {'; '.join(str(r) for r in self.cte)}"
        )


def boresight_scorecard(
    name: str,
    *,
    first_path: Mapping[str, Quantity] | None,
    second_path: Mapping[str, Quantity] | None,
    allowance: Quantity,
    rule: CombinationRule,
) -> ScorecardEntry:
    """Screen the boresight between two optical paths: their difference, not either's drift.

    Each path maps a named contributor to the line-of-sight shift it causes on that path —
    a housing's tilt, a combiner mount, a fold mirror — as an angle. A contributor that moves
    both paths equally is **common-mode**: it moves the two together and is named and left
    out of the differential. One that moves them unequally enters as the difference; one that
    acts on a single path enters in full, named with its path. The differential terms combine
    under the declared ``rule`` — worst case or root-sum-square, with no default — against
    the ``allowance`` (Yoder, Opto-Mechanical Systems Design, on boresight between channels).

    With either path missing the entry is ``not_evaluated`` naming it: the drift of one path
    is not a boresight error.
    """
    missing = [
        label for label, path in (("first", first_path), ("second", second_path)) if not path
    ]
    if missing:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — the {' and '.join(missing)} path is not declared, and the "
                "drift of one path is not a boresight error"
            ),
        )
    assert first_path is not None and second_path is not None
    if rule is CombinationRule.HYBRID:
        raise ValueError(
            "a boresight takes worst_case or rss; hybrid needs correlation groups this screen "
            "does not carry"
        )
    limit = _radians(allowance, "allowance") * 1e6
    if limit <= 0:
        raise ValueError(f"allowance must be positive; got {allowance}")
    first = {
        label: _radians(v, f"'{label}' on the first path") * 1e6 for label, v in first_path.items()
    }
    second = {
        label: _radians(v, f"'{label}' on the second path") * 1e6
        for label, v in second_path.items()
    }
    common, terms = [], []
    for label in dict.fromkeys([*first, *second]):
        a, b = first.get(label), second.get(label)
        if a is not None and b is not None and abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1.0):
            common.append(label)
        elif a is not None and b is not None:
            terms.append((f"{label} ({a:g} vs {b:g} µrad)", a - b))
        elif a is not None:
            terms.append((f"{label} (first path only)", a))
        else:
            assert b is not None
            terms.append((f"{label} (second path only)", -b))
    if rule is CombinationRule.WORST_CASE:
        total = sum(abs(value) for _, value in terms)
    else:
        total = sqrt(sum(value * value for _, value in terms))
    comparison = Comparison(
        measured=Quantity(magnitude=total, unit="µrad"),
        limit=Quantity(magnitude=limit, unit="µrad"),
        sense=LimitSense.AT_MOST,
        measured_label=f"differential boresight by {rule.value.replace('_', ' ')}",
        limit_label="allowance",
        minimum_decimals=1,
    )
    differential = "; ".join(label for label, _ in terms) or "none"
    common_text = ", ".join(common) or "none"
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=(
            f"{comparison.sentence()} — differential: {differential}; common-mode, excluded: "
            f"{common_text}"
        ),
        reference="Yoder, Opto-Mechanical Systems Design, boresight between channels",
        comparison=comparison,
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "the per-contributor differences of two declared paths, combined by the "
                "declared rule; the terms are listed on the entry"
            ),
        ),
    )


def enclosure_rise_scorecard(
    name: str,
    *,
    dissipations: Mapping[str, Quantity],
    allowed_rise: Quantity,
    thermal_resistance: Quantity | None = None,
) -> ScorecardEntry:
    """Screen the temperature rise a housing's own dissipation drives inside it.

    A display, an emitter, a detector or its electronics heats the volume the optics sit in.
    The named ``dissipations`` sum to the heat the enclosure sheds through its declared
    ``thermal_resistance`` to ambient, and the rise is Q·R
    (:func:`~anvilate.analysis.thermal.temperature_rise`; Incropera's resistance network).
    ``PASS`` while it stays within ``allowed_rise``. The rise is the entry's measured quantity,
    so a thermal or condensation screen downstream can consume it along a dependency chain
    rather than starting from ambient.

    With sources and no declared heat path the entry is ``not_evaluated`` naming the path: a
    sealed volume does not shed heat by assumption.
    """
    if not dissipations:
        raise ValueError(
            "declare at least one dissipating source; an enclosure with none has no rise to screen"
        )
    _check(allowed_rise, "[temperature]", "allowed_rise")
    allowed = temperature_difference_kelvin(allowed_rise, name="allowed_rise")
    if allowed <= 0:
        raise ValueError(f"allowed_rise must be positive; got {allowed_rise}")
    watts = 0.0
    for label, power in dissipations.items():
        _check(power, "[power]", f"dissipation '{label}'")
        if power.to("W").magnitude < 0:
            raise ValueError(f"dissipation '{label}' cannot be negative: {power}")
        watts += power.to("W").magnitude
    sources = ", ".join(f"{label} {power}" for label, power in dissipations.items())
    if thermal_resistance is None:
        verb = "dissipates" if len(dissipations) == 1 else "dissipate"
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — {sources} {verb} inside the enclosure and no heat path "
                "to ambient is declared; a sealed volume does not shed heat by assumption"
            ),
        )
    rise = temperature_rise(
        power=Quantity(magnitude=watts, unit="W"), thermal_resistance=thermal_resistance
    )
    comparison = Comparison(
        measured=Quantity(magnitude=rise.to("K").magnitude, unit="K"),
        limit=Quantity(magnitude=allowed, unit="K"),
        sense=LimitSense.AT_MOST,
        measured_label="internal rise",
        limit_label="allowed rise",
        minimum_decimals=1,
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=f"{comparison.sentence()} — from {sources}",
        reference=_INCROPERA,
        comparison=comparison,
        derivation=Derivation(
            symbolic="ΔT = Q · R",
            inputs=(
                SymbolValue(
                    symbol="Q",
                    description=f"total internal dissipation: {sources}",
                    value=Quantity(magnitude=watts, unit="W"),
                    unit="W",
                ),
                SymbolValue(
                    symbol="R",
                    description="the enclosure's declared thermal resistance to ambient",
                    value=Quantity(magnitude=thermal_resistance.to("K/W").magnitude, unit="K/W"),
                    unit="K/W",
                ),
            ),
            result=SymbolValue(
                symbol="ΔT",
                description="internal temperature rise over ambient",
                value=Quantity(magnitude=rise.to("K").magnitude, unit="K"),
                unit="K",
            ),
            citation=_INCROPERA,
        ),
    )


class ShockPulse(StrEnum):
    """The classical shock pulse shapes a test specification names (Harris, Shock and Vibration
    Handbook)."""

    HALF_SINE = "half_sine"
    SQUARE = "square"
    TERMINAL_PEAK_SAWTOOTH = "terminal_peak_sawtooth"


class ShockEnvironment(StatableModel):
    """A declared shock: its peak, shape, duration, the axis it acts on, and how many.

    The shape, the duration and the axis are all required: an amplification depends on the
    first two and a mount's stiffness on the third, and none of them is a default a reader
    could see (Harris, Shock and Vibration Handbook, on classical pulses).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    peak_acceleration: float
    pulse_duration: Quantity
    shape: ShockPulse
    axis: Named
    cycles: int = 1

    @model_validator(mode="after")
    def _a_pulse(self) -> ShockEnvironment:
        _check(self.pulse_duration, "[time]", "pulse_duration")
        require_finite(self.peak_acceleration, name="peak_acceleration")
        if self.peak_acceleration <= 0:
            raise ValueError(
                f"peak_acceleration must be positive, in g; got {self.peak_acceleration}"
            )
        if self.pulse_duration.to("s").magnitude <= 0:
            raise ValueError(f"pulse_duration must be positive; got {self.pulse_duration}")
        if self.cycles < 1:
            raise ValueError(f"a shock environment applies at least once; got {self.cycles}")
        return self

    def _pulse(self, t: float, duration: float) -> float:
        if not 0.0 <= t <= duration:
            return 0.0
        if self.shape is ShockPulse.HALF_SINE:
            return sin(pi * t / duration)
        if self.shape is ShockPulse.SQUARE:
            return 1.0
        return t / duration

    def amplification(self, *, natural_frequency: Quantity, quality_factor: float) -> float:
        """The maximax absolute-acceleration amplification of a damped single mode.

        The mount of ``natural_frequency`` f_n and ``quality_factor`` Q (damping ζ = 1/(2Q),
        required — the answer moves with it and a default Q is somebody else's mount) is
        driven through its base by this pulse, and the peak absolute acceleration it reaches
        during and after the pulse, over the pulse's peak, is returned: the shock response
        spectrum ordinate (Harris, Shock and Vibration Handbook). Integrated numerically by
        fourth-order Runge-Kutta at 1/400 of the shorter of the pulse and the period, over the
        pulse and two periods after it, where the residual peak of any damped mode has passed.
        """
        _check(natural_frequency, "[frequency]", "natural_frequency")
        quality = require_finite(quality_factor, name="quality_factor")
        if quality <= 0.5:
            raise ValueError(f"quality_factor must exceed 0.5 to resonate at all; got {quality}")
        fn = natural_frequency.to("Hz").magnitude
        if fn <= 0:
            raise ValueError(f"natural_frequency must be positive; got {natural_frequency}")
        omega, zeta = 2 * pi * fn, 1 / (2 * quality)
        duration = self.pulse_duration.to("s").magnitude
        period = 1 / fn
        step = min(duration, period) / 400
        steps = int((duration + 2 * period) / step) + 1

        def derivatives(t: float, z: float, v: float) -> tuple[float, float]:
            # Relative motion z of the mass against a base accelerating at the unit pulse.
            return v, -self._pulse(t, duration) - 2 * zeta * omega * v - omega * omega * z

        z = v = peak = 0.0
        for index in range(steps):
            t = index * step
            k1 = derivatives(t, z, v)
            k2 = derivatives(t + step / 2, z + step / 2 * k1[0], v + step / 2 * k1[1])
            k3 = derivatives(t + step / 2, z + step / 2 * k2[0], v + step / 2 * k2[1])
            k4 = derivatives(t + step, z + step * k3[0], v + step * k3[1])
            z += step / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            v += step / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            peak = max(peak, abs(2 * zeta * omega * v + omega * omega * z))
        return peak

    def equivalent_static_acceleration(
        self, *, natural_frequency: Quantity, quality_factor: float
    ) -> float:
        """The static acceleration, in g, that loads the mount as this shock does: A·a₀."""
        return self.peak_acceleration * self.amplification(
            natural_frequency=natural_frequency, quality_factor=quality_factor
        )

    def __str__(self) -> str:
        repeats = "" if self.cycles == 1 else f", {self.cycles} times"
        return (
            f"{self.peak_acceleration:g} g {self.shape.value.replace('_', ' ')} over "
            f"{self.pulse_duration} along {self.axis}{repeats}"
        )


class SurfaceDeformation(StatableModel):
    """One surface's deformation as an optical-design or FEA tool exported it.

    A surface displaced by an RMS error δ changes the wavefront by 2δ on reflection and by
    (n − 1)·δ on transmission through an index-n boundary (Hecht, Optics; Yoder,
    Opto-Mechanical Systems Design), so a refracting surface needs its index and a mirror
    does not.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: Named
    rms: Quantity
    reflective: bool
    refractive_index: float | None = None

    @model_validator(mode="after")
    def _a_surface(self) -> SurfaceDeformation:
        _check(self.rms, "[length]", "rms")
        if self.rms.to("m").magnitude < 0:
            raise ValueError(f"an RMS deformation cannot be negative; got {self.rms}")
        if not self.reflective:
            if self.refractive_index is None:
                raise ValueError(
                    f"'{self.surface}' refracts, so its wavefront error needs the index across it"
                )
            if require_finite(self.refractive_index, name="refractive_index") <= 1:
                raise ValueError(f"'{self.surface}': refractive_index must exceed 1")
        return self

    def wavefront_rms(self) -> Quantity:
        """The RMS wavefront error this deformation puts in the beam, in nanometres."""
        factor = 2.0 if self.reflective else (self.refractive_index or 1.0) - 1.0
        return Quantity(magnitude=factor * self.rms.to("nm").magnitude, unit="nm")


class Prescription(StatableModel):
    """What an optical-design tool exported, typed, with the tool that exported it.

    Every quantity a screen reads from the prescription is optional here, because an export
    may not carry it, and a screen that needs one it lacks reports not evaluated naming it —
    it is never estimated. The ``tool`` and ``tool_version`` travel into every entry, so a
    verdict can be traced to the model it came from (Yoder, Opto-Mechanical Systems Design,
    on the optical and mechanical models agreeing).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Named
    tool_version: Named
    effective_focal_length: Quantity | None = None
    f_number: float | None = None
    wavelength: Quantity | None = None
    deformations: tuple[SurfaceDeformation, ...] = ()

    def _refused(self, name: str, needed: dict[str, object]) -> ScorecardEntry | None:
        missing = [field.replace("_", " ") for field, value in needed.items() if value is None]
        if not missing:
            return None
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — the {self.tool} {self.tool_version} prescription does not "
                f"carry {', '.join(missing)}, and a prescription input is never estimated"
            ),
        )

    def _traced(self, entry: ScorecardEntry) -> ScorecardEntry:
        return entry.model_copy(
            update={"detail": f"{entry.detail} — from {self.tool} {self.tool_version}"}
        )

    def athermal_focus(
        self,
        name: str,
        *,
        refractive_index: float,
        dn_dt: Quantity,
        glass_cte: Quantity,
        housing_cte: Quantity,
        housing_length: Quantity,
        temperature_change: Quantity,
    ) -> ScorecardEntry:
        """:func:`athermal_focus_scorecard` with focal length, f-number and wavelength read
        from this prescription."""
        refused = self._refused(
            name,
            {
                "effective_focal_length": self.effective_focal_length,
                "f_number": self.f_number,
                "wavelength": self.wavelength,
            },
        )
        if refused is not None:
            return refused
        assert self.effective_focal_length is not None and self.wavelength is not None
        assert self.f_number is not None
        return self._traced(
            athermal_focus_scorecard(
                name,
                focal_length=self.effective_focal_length,
                f_number=self.f_number,
                wavelength=self.wavelength,
                refractive_index=refractive_index,
                dn_dt=dn_dt,
                glass_cte=glass_cte,
                housing_cte=housing_cte,
                housing_length=housing_length,
                temperature_change=temperature_change,
            )
        )

    def wavefront_budget(
        self,
        name: str,
        *,
        strehl_threshold: float,
        others: Mapping[str, Quantity] | None = None,
    ) -> ScorecardEntry:
        """:func:`wavefront_budget_scorecard` over this prescription's surface deformations,
        each converted to wavefront error, plus any ``others`` the caller states."""
        refused = self._refused(
            name,
            {"wavelength": self.wavelength, "surface deformations": self.deformations or None},
        )
        if refused is not None:
            return refused
        assert self.wavelength is not None
        contributors = {d.surface: d.wavefront_rms() for d in self.deformations}
        contributors.update(others or {})
        return self._traced(
            wavefront_budget_scorecard(
                name,
                contributors=contributors,
                wavelength=self.wavelength,
                strehl_threshold=strehl_threshold,
            )
        )


def preload_temperature_scorecard(
    name: str,
    *,
    preload: Quantity,
    axial_stiffness: Quantity,
    edge_thickness: Quantity,
    glass_cte: Quantity,
    cell_cte: Quantity,
    cold_change: Quantity,
    hot_change: Quantity,
    max_preload: Quantity,
) -> ScorecardEntry:
    """Screen a retained lens's axial preload across its temperature range.

    The cell's clamping length and the glass edge it clamps grow at different rates: over an
    ``edge_thickness`` t_E their mismatch is (α_M − α_G)·t_E·ΔT, and the clamped stack's
    ``axial_stiffness`` k turns it into a preload change ΔP = −k·(α_M − α_G)·t_E·ΔT — a
    compatibility statement, Yoder's Opto-Mechanical Systems Design treatment of preload
    versus temperature. A cell that out-expands its glass loses preload hot and gains it
    cold. ``cold_change`` and ``hot_change`` are the signed temperature changes from
    assembly to each extreme.

    ``FAIL`` when the ``preload`` falls to nothing at either extreme — the element comes loose
    and moves — or rises above ``max_preload``, the load the glass and seat may carry. The
    stiffness is required: it is the whole of the answer, and a default one describes no
    mount.
    """
    _check(preload, "[force]", "preload")
    _check(axial_stiffness, "[force] / [length]", "axial_stiffness")
    _check(edge_thickness, "[length]", "edge_thickness")
    _check(glass_cte, "1 / [temperature]", "glass_cte")
    _check(cell_cte, "1 / [temperature]", "cell_cte")
    _check(max_preload, "[force]", "max_preload")
    p0 = preload.to("N").magnitude
    k = axial_stiffness.to("N/m").magnitude
    t = edge_thickness.to("m").magnitude
    limit = max_preload.to("N").magnitude
    for value, label in ((p0, "preload"), (k, "axial_stiffness"), (t, "edge_thickness")):
        if value <= 0:
            raise ValueError(f"{label} must be positive; got {value}")
    if limit <= p0:
        raise ValueError(f"max_preload must exceed the assembled preload; got {max_preload}")
    mismatch = cell_cte.to("1/K").magnitude - glass_cte.to("1/K").magnitude
    at: dict[str, float] = {}
    for label, change in (("cold", cold_change), ("hot", hot_change)):
        delta = temperature_difference_kelvin(change, name=f"{label}_change")
        at[label] = p0 - k * mismatch * t * delta
    findings = [
        f"{label}: preload {value:.1f} N — the element comes loose"
        for label, value in at.items()
        if value <= 0
    ] + [
        f"{label}: preload {value:.1f} N above the {limit:.1f} N the seat may carry"
        for label, value in at.items()
        if value > limit
    ]
    summary = f"assembled {p0:.1f} N, cold {at['cold']:.1f} N, hot {at['hot']:.1f} N"
    return ScorecardEntry(
        name=name,
        status=CheckStatus.FAIL if findings else CheckStatus.PASS,
        detail=("; ".join(findings) + f" ({summary})")
        if findings
        else f"held at both extremes ({summary})",
        reference="Yoder, Opto-Mechanical Systems Design, preload versus temperature",
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "the preload at each extreme, P₀ − k·(α_M − α_G)·t_E·ΔT, held to two bounds; "
                "the three values are on the entry"
            ),
        ),
    )


def glass_contact_stress_scorecard(
    name: str,
    *,
    preload: Quantity,
    contact_diameter: Quantity,
    glass_radius: Quantity,
    mount_radius: Quantity,
    glass_modulus: Quantity,
    glass_poisson: float,
    mount_modulus: Quantity,
    mount_poisson: float,
    allowable_tensile_stress: Quantity,
) -> ScorecardEntry:
    """Screen the stress a retainer's preload puts into the glass at its contact ring.

    The ``preload`` P spreads around a contact circle of ``contact_diameter`` D_c as a line
    load p = P/(π·D_c). In section the glass surface (``glass_radius``, the lens's surface
    radius) and the mount's contact profile (``mount_radius``, a toroid's section radius)
    meet as two cylinders, so Hertz line contact gives the peak compressive stress
    p₀ = √(p·E*/(π·R)), with 1/R = 1/R_glass + 1/R_mount and
    1/E* = (1 − ν_g²)/E_g + (1 − ν_m²)/E_m (Johnson, Contact Mechanics, 1985). Glass breaks in
    tension, estimated as σ_T ≈ (1 − 2ν_g)/3 · p₀ — the Hertzian edge-tension relation, which
    is exact for a point contact and an approximation for this annular one.

    ``PASS`` while σ_T stays within ``allowable_tensile_stress``, which is the caller's. The
    entry says what that number is: a glass allowable is a probability of fracture, set by
    the Weibull statistics of the surface flaws under stress, not a strength like a metal's.
    A concave mount profile is a negative ``mount_radius``.
    """
    for value, label in (
        (preload, "preload"),
        (allowable_tensile_stress, "allowable_tensile_stress"),
    ):
        _check(value, "[force]" if label == "preload" else "[pressure]", label)
    for value, label in (
        (contact_diameter, "contact_diameter"),
        (glass_radius, "glass_radius"),
        (mount_radius, "mount_radius"),
    ):
        _check(value, "[length]", label)
    _check(glass_modulus, "[pressure]", "glass_modulus")
    _check(mount_modulus, "[pressure]", "mount_modulus")
    nu_g = require_finite(glass_poisson, name="glass_poisson")
    nu_m = require_finite(mount_poisson, name="mount_poisson")
    for nu, label in ((nu_g, "glass_poisson"), (nu_m, "mount_poisson")):
        if not 0 <= nu < 0.5:
            raise ValueError(f"{label} must lie in [0, 0.5); got {nu}")
    force = preload.to("N").magnitude
    diameter = contact_diameter.to("m").magnitude
    allowable = allowable_tensile_stress.to("Pa").magnitude
    if force <= 0 or diameter <= 0 or allowable <= 0:
        raise ValueError("preload, contact_diameter and the allowable must all be positive")
    curvature = 1 / glass_radius.to("m").magnitude + 1 / mount_radius.to("m").magnitude
    if curvature <= 0:
        raise ValueError(
            "the mount's concave profile is flatter than the glass it holds: the two do not "
            "meet in a line contact this relation describes"
        )
    modulus = 1 / (
        (1 - nu_g**2) / glass_modulus.to("Pa").magnitude
        + (1 - nu_m**2) / mount_modulus.to("Pa").magnitude
    )
    line_load = force / (pi * diameter)
    compressive = sqrt(line_load * modulus * curvature / pi)
    tensile = (1 - 2 * nu_g) / 3 * compressive
    comparison = Comparison(
        measured=Quantity(magnitude=tensile / 1e6, unit="MPa"),
        limit=Quantity(magnitude=allowable / 1e6, unit="MPa"),
        sense=LimitSense.AT_MOST,
        measured_label="glass tensile stress",
        limit_label="allowable",
        minimum_decimals=2,
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=(
            f"{comparison.sentence()} (peak contact compression {compressive / 1e6:.1f} MPa) "
            "— the allowable is a probability of fracture set by the Weibull statistics of "
            "the surface flaws under stress, not a strength"
        ),
        reference=_JOHNSON,
        comparison=comparison,
        addresses=("glass fracture at a mount contact",),
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "Hertz line contact p₀ = √(p·E*/(π·R)) and σ_T = (1 − 2ν)/3·p₀ over five "
                "intermediate quantities; both stresses are stated on the entry"
            ),
        ),
    )


class BreathingMitigation(StrEnum):
    """What a sealed volume declares against the air a thermal cycle pumps through its seal.

    An equalization path, usually a membrane that passes air and stops liquid water, admits
    the differential. A desiccant absorbs the water the seal lets in, and a dry purge fill
    starts the volume with none. Only the path removes the differential; the other two let
    the seal resist it and deal with what leaks past (Yoder, Opto-Mechanical Systems Design,
    on sealing and purging).
    """

    EQUALIZATION_PATH = "equalization_path"
    DESICCANT = "desiccant"
    PURGE = "purge"


def seal_breathing_scorecard(
    name: str,
    *,
    fill_pressure: Quantity,
    fill_temperature: Quantity,
    cold: Quantity,
    hot: Quantity,
    cycles: int,
    mitigation: BreathingMitigation | None = None,
) -> ScorecardEntry:
    """Screen the pressure a thermal cycle drives across a sealed volume's boundary.

    A rigid volume sealed at ``fill_pressure`` and ``fill_temperature`` follows the ideal-gas
    law at constant volume, P = P_f·T/T_f (Cengel and Boles), so cycling between ``cold`` and
    ``hot`` swings its pressure by ΔP = P_f·(T_h − T_c)/T_f. Temperatures are absolute. The
    ambient pressure is taken as the fill pressure; a volume that also changes altitude sees
    more.

    A seal resisting that swing on every one of many ``cycles`` leaks ambient air in and
    keeps its water, which is the mechanism behind most fogged instruments. With repeated
    cycles and no declared ``mitigation``, the entry is a failure that names the mechanism.
    With an equalization path, the differential is admitted. With a desiccant or a purge,
    the seal still resists it, and the water accumulated over the cycles is a matter for a
    humidity-cycling test, which the entry names because no formula here predicts it.
    """
    _check(fill_pressure, "[pressure]", "fill_pressure")
    temperatures = {}
    for label, value in (("fill_temperature", fill_temperature), ("cold", cold), ("hot", hot)):
        _check(value, "[temperature]", label)
        kelvin = value.to("K").magnitude
        if kelvin <= 0:
            raise ValueError(f"{label} must be above absolute zero; got {value}")
        temperatures[label] = kelvin
    p_fill = fill_pressure.to("kPa").magnitude
    if p_fill <= 0:
        raise ValueError(f"fill_pressure must be positive; got {fill_pressure}")
    if temperatures["hot"] <= temperatures["cold"]:
        raise ValueError(f"hot must exceed cold; got hot {hot} and cold {cold}")
    if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 1:
        raise ValueError(f"cycles must be a whole number of at least 1; got {cycles!r}")
    t_fill, t_cold, t_hot = (
        temperatures["fill_temperature"],
        temperatures["cold"],
        temperatures["hot"],
    )
    swing = p_fill * (t_hot - t_cold) / t_fill
    over = p_fill * (t_hot / t_fill - 1.0)
    under = p_fill * (t_cold / t_fill - 1.0)
    state = (
        f"the sealed volume swings {swing:.2f} kPa per cycle ({over:+.2f} kPa hot, "
        f"{under:+.2f} kPa cold) over {cycles} cycle{'s' if cycles != 1 else ''}"
    )
    status = CheckStatus.PASS
    if mitigation is BreathingMitigation.EQUALIZATION_PATH:
        verdict = "the declared equalization path admits it, so the seal carries no differential"
    elif cycles == 1:
        verdict = "one excursion, which the seal resists; nothing accumulates over one cycle"
    elif mitigation is None:
        status = CheckStatus.FAIL
        verdict = (
            "with no equalization path, desiccant or purge declared, the seal breathes: each "
            "cycle draws ambient air in past it and the water stays, accumulating until the "
            "optics fog"
        )
    else:
        verdict = (
            f"the seal resists it and the declared {mitigation.value} takes the water that "
            f"leaks past; how much accumulates over {cycles} cycles is verification-only, "
            "for a humidity-cycling test of the sealed unit"
        )
    return ScorecardEntry(
        name=name,
        status=status,
        detail=f"{state} — {verdict}",
        reference=_CENGEL,
        derivation=Derivation(
            symbolic="ΔP = P_f · (T_h − T_c) / T_f",
            inputs=(
                SymbolValue(
                    symbol="P_f",
                    description="the fill pressure",
                    value=Quantity(magnitude=p_fill, unit="kPa"),
                    unit="kPa",
                ),
                SymbolValue(
                    symbol="T_h",
                    description="the hot extreme, absolute",
                    value=Quantity(magnitude=t_hot, unit="K"),
                    unit="K",
                ),
                SymbolValue(
                    symbol="T_c",
                    description="the cold extreme, absolute",
                    value=Quantity(magnitude=t_cold, unit="K"),
                    unit="K",
                ),
                SymbolValue(
                    symbol="T_f",
                    description="the fill temperature, absolute",
                    value=Quantity(magnitude=t_fill, unit="K"),
                    unit="K",
                ),
            ),
            result=SymbolValue(
                symbol="ΔP",
                description="the pressure swing per cycle",
                value=Quantity(magnitude=swing, unit="kPa"),
                unit="kPa",
            ),
            citation=_CENGEL,
        ),
        addresses=("condensation in a breathing sealed volume",),
    )


def window_pressure_opd(
    *,
    differential: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    refractive_index: float,
) -> Quantity:
    """The transmitted wavefront error a pressure differential bends into a window, in nm.

    A rim-mounted window bows under a ``differential`` ΔP, and because both faces bend
    together the first-order change cancels. What remains is the second-order term
    OPD = 0.00889·(n − 1)·ΔP²·D⁶/(E²·t⁵) of Sparks and Cottis (1973), J. Appl. Phys. 44(2), for
    the window's unsupported ``diameter`` D. It goes as ΔP², so it has the same sign in both
    directions. The value is the error the source states, not an RMS, so a budget of RMS
    contributors needs it converted for the declared aperture's shape.
    """
    _check(differential, "[pressure]", "differential")
    _check(diameter, "[length]", "diameter")
    _check(thickness, "[length]", "thickness")
    _check(elastic_modulus, "[pressure]", "elastic_modulus")
    if not (isfinite(refractive_index) and refractive_index > 1.0):
        raise ValueError(f"refractive_index must exceed 1; got {refractive_index}")
    d = diameter.to("m").magnitude
    t = thickness.to("m").magnitude
    e = elastic_modulus.to("Pa").magnitude
    for label, value, given in (
        ("diameter", d, diameter),
        ("thickness", t, thickness),
        ("elastic_modulus", e, elastic_modulus),
    ):
        if value <= 0:
            raise ValueError(f"{label} must be positive; got {given}")
    dp = differential.to("Pa").magnitude
    opd = 0.00889 * (refractive_index - 1.0) * dp**2 * d**6 / (e**2 * t**5)
    return Quantity(magnitude=opd * 1e9, unit="nm")


def pressure_window_scorecard(
    name: str,
    *,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float,
    allowable_tensile_stress: Quantity,
    outward: Quantity | None = None,
    inward: Quantity | None = None,
) -> ScorecardEntry:
    """Screen a sealing window under the declared pressure differential in both directions.

    A volume sealed at one pressure sees an ``outward`` differential at altitude or when it
    warms, and an ``inward`` one under immersion or when it cools. Both are magnitudes. The
    window is taken as rim-mounted over its unsupported ``diameter``, the Timoshenko simply
    supported plate (:func:`~anvilate.analysis.plate.simply_supported_circular_plate_uniform_load`):
    peak stress 3·(3 + ν)·ΔP·R²/(8·t²) at the centre, on the face the pressure bows convex,
    which is the outer face for an outward differential and the inner one for an inward.
    The larger differential governs, and the entry names it.

    A window with neither differential declared is not evaluated, naming both, rather than
    assumed to see sea-level fill. The allowable is the caller's, a fracture probability
    under Weibull flaw statistics and not a strength, and the entry says so.
    """
    for label, value, dimension in (
        ("diameter", diameter, "[length]"),
        ("thickness", thickness, "[length]"),
        ("elastic_modulus", elastic_modulus, "[pressure]"),
        ("allowable_tensile_stress", allowable_tensile_stress, "[pressure]"),
    ):
        _check(value, dimension, label)
        if value.magnitude <= 0:
            raise ValueError(f"{label} must be positive; got {value}")
    if not 0 < require_finite(poisson_ratio, name="poisson_ratio") < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")
    allowable = allowable_tensile_stress.to("MPa").magnitude
    declared = {
        label: value
        for label, value in (("outward", outward), ("inward", inward))
        if value is not None
    }
    if not declared:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "no pressure differential declared: state the outward differential (altitude, "
                "warm) and the inward one (immersion, cold) from the fill condition; a sea-level "
                "fill is not assumed"
            ),
            reference=_TIMOSHENKO,
        )
    faces = {"outward": "outer", "inward": "inner"}
    results = {}
    for label, value in declared.items():
        _check(value, "[pressure]", label)
        if value.magnitude < 0:
            raise ValueError(f"{label} is a magnitude and cannot be negative; got {value}")
        results[label] = simply_supported_circular_plate_uniform_load(
            pressure=value,
            diameter=diameter,
            thickness=thickness,
            elastic_modulus=elastic_modulus,
            poisson_ratio=poisson_ratio,
        )
    governing = max(results, key=lambda label: results[label].max_bending_stress.magnitude)
    stress = results[governing].max_bending_stress.to("MPa").magnitude
    comparison = Comparison(
        measured=Quantity(magnitude=stress, unit="MPa"),
        limit=Quantity(magnitude=allowable, unit="MPa"),
        sense=LimitSense.AT_MOST,
        measured_label=f"{governing} window stress",
        limit_label="allowable",
        minimum_decimals=2,
    )
    each = "; ".join(
        f"{label} {declared[label].to('kPa').magnitude:.1f} kPa: "
        f"{result.max_bending_stress.to('MPa').magnitude:.2f} MPa on the {faces[label]} face, "
        f"bow {result.max_deflection.to('µm').magnitude:.1f} µm"
        for label, result in results.items()
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=(
            f"{comparison.sentence()} ({each}; the {governing} differential governs) — the "
            "allowable is a probability of fracture set by the Weibull statistics of the "
            "surface flaws under stress, not a strength"
        ),
        reference=_TIMOSHENKO,
        comparison=comparison,
        addresses=("window fracture under a pressure differential",),
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "the plate module's Timoshenko closed form, evaluated for each declared "
                "direction; each direction's stress and bow are stated on the entry"
            ),
        ),
    )


def _records(value: object, kind: type, label: str) -> tuple:
    """``value`` as a tuple of ``kind`` records, or a refusal naming ``label``."""
    if not isinstance(value, tuple | list) or not all(isinstance(v, kind) for v in value):
        raise ValueError(f"{label} must be a tuple of {kind.__name__} records; got {value!r}")
    if not value:
        raise ValueError(f"{label} is empty; declare at least one {kind.__name__}")
    return tuple(value)


class HarnessCrossing(StatableModel):
    """A cable, ribbon or flexible attachment declared crossing a mount interface.

    Its ``stiffness`` is the force per unit offset across the interface, and its
    ``routing_offset`` is how far the routing holds it from its free shape at assembly. An
    optional ``lever_arm`` from the mount's centre turns the force into a moment. Either of
    the first two left undeclared is what the harness screen names, because a harness
    assumed to be free is a common unmodelled source of alignment drift (Yoder,
    Opto-Mechanical Systems Design).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    harness: Named
    stiffness: Quantity | None = None
    routing_offset: Quantity | None = None
    lever_arm: Quantity | None = None

    @model_validator(mode="after")
    def _a_harness(self) -> HarnessCrossing:
        for label, value, dimension in (
            ("stiffness", self.stiffness, "[force] / [length]"),
            ("routing_offset", self.routing_offset, "[length]"),
            ("lever_arm", self.lever_arm, "[length]"),
        ):
            if value is None:
                continue
            _check(value, dimension, label)
            if value.magnitude < 0:
                raise ValueError(f"'{self.harness}': {label} cannot be negative; got {value}")
        return self

    def missing(self) -> tuple[str, ...]:
        """What the screen needs from this harness and was not given."""
        return tuple(
            label
            for label, value in (
                ("stiffness", self.stiffness),
                ("routing offset", self.routing_offset),
            )
            if value is None
        )


def harness_load_scorecard(
    name: str,
    *,
    crossings: tuple[HarnessCrossing, ...],
    mount_stiffness: Quantity,
    focal_length: Quantity,
    allowed_line_of_sight: Quantity,
) -> ScorecardEntry:
    """Screen the alignment shift the harnesses crossing a mount pull into it.

    Each harness pulls with F = k·δ, its stiffness times its routing offset. The harnesses
    act in parallel with the mount's radial ``mount_stiffness`` k_m, so the mount moves by
    Δ = Σk·δ/(k_m + Σk), taking every pull in one direction because the routing rarely
    states which. The element's line of sight then turns through Δ/f
    (:func:`decenter_line_of_sight`; Yoder, Opto-Mechanical Systems Design), compared against
    ``allowed_line_of_sight``. Each harness's force, and its moment where a lever arm is
    declared, is stated on the entry.

    A crossing missing its stiffness or routing offset makes the entry not evaluated,
    naming each one and what it lacks, rather than screening the harness as free.
    """
    _check(mount_stiffness, "[force] / [length]", "mount_stiffness")
    _check(focal_length, "[length]", "focal_length")
    k_mount = mount_stiffness.to("N/m").magnitude
    if k_mount <= 0:
        raise ValueError(f"mount_stiffness must be positive; got {mount_stiffness}")
    if focal_length.to("m").magnitude <= 0:
        raise ValueError(f"focal_length must be positive; got {focal_length}")
    allowed = _radians(allowed_line_of_sight, "allowed_line_of_sight") * 1e6
    if allowed <= 0:
        raise ValueError(f"allowed_line_of_sight must be positive; got {allowed_line_of_sight}")
    crossings = _records(crossings, HarnessCrossing, "crossings")
    unstated = [
        f"{crossing.harness} ({' and '.join(crossing.missing())})"
        for crossing in crossings
        if crossing.missing()
    ]
    if unstated:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "a harness crossing the mount with no declared stiffness or routing is "
                "screened as free, which it is not; state them for " + ", ".join(unstated)
            ),
            reference=_YODER,
        )
    pulls = []
    for crossing in crossings:
        k = (crossing.stiffness or Quantity(magnitude=0.0, unit="N/m")).to("N/m").magnitude
        offset = (crossing.routing_offset or Quantity(magnitude=0.0, unit="m")).to("m")
        force = k * offset.magnitude
        moment = (
            f", {force * crossing.lever_arm.to('m').magnitude * 1e3:.1f} N·mm about the mount"
            if crossing.lever_arm is not None
            else ""
        )
        pulls.append((k, force, f"{crossing.harness} {force:.3f} N{moment}"))
    stiffness = sum(k for k, _, _ in pulls)
    shift = sum(force for _, force, _ in pulls) / (k_mount + stiffness)
    line_of_sight = decenter_line_of_sight(
        decenter=Quantity(magnitude=shift, unit="m"), focal_length=focal_length
    ).magnitude
    comparison = Comparison(
        measured=Quantity(magnitude=line_of_sight, unit="µrad"),
        limit=Quantity(magnitude=allowed, unit="µrad"),
        sense=LimitSense.AT_MOST,
        measured_label="harness line-of-sight shift",
        limit_label="allowed",
        minimum_decimals=1,
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
        detail=(
            f"{comparison.sentence()} (mount shift {shift * 1e6:.2f} µm from "
            + "; ".join(text for _, _, text in pulls)
            + ")"
        ),
        reference=_YODER,
        comparison=comparison,
        addresses=("alignment drift from a harness crossing a mount",),
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "Δ = Σk·δ/(k_m + Σk) over a declared set of harnesses, then Δ/f; each "
                "harness's force and the mount shift are stated on the entry"
            ),
        ),
    )


def cycling_retention_scorecard(
    name: str,
    *,
    requirement: str,
    cycles: int,
    test_method: str,
) -> ScorecardEntry:
    """The entry a retention-after-cycling requirement carries: not evaluated, by design.

    Bolted joints, adhesives and preloaded interfaces do not return to where they started
    after a cycle. Every closed-form screen in this module is a single excursion, so none
    of them models that path dependence (Yoder, Opto-Mechanical Systems Design). The
    ``requirement``, for example "boresight within 50 µrad", held over ``cycles``, is
    therefore stated as not evaluated, naming the ``test_method`` that establishes it. A
    card holding this entry cannot pass on its single-excursion screens alone.
    """
    for label, text in (("requirement", requirement), ("test_method", test_method)):
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{label} must name something; got {text!r}")
    if isinstance(cycles, bool) or not isinstance(cycles, int) or cycles < 2:
        raise ValueError(
            f"cycles must be a whole number of at least 2 for a retention-after-cycling "
            f"requirement; got {cycles!r}"
        )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.NOT_EVALUATED,
        detail=(
            f"{requirement.strip()} after {cycles} cycles is verification-only: no screen "
            "here models how a joint, bond or preload drifts over repeated cycles, and a "
            "single-excursion result does not stand in for it; established by "
            f"{test_method.strip()}"
        ),
        reference=_YODER,
        addresses=("alignment loss over repeated cycles",),
    )


class SurfaceTreatment(StrEnum):
    """What sits on an optical surface with environmental limits of its own.

    A thin-film coating and an optical cement are the two Yoder and Vukobratovich
    (Opto-Mechanical Systems Design) treat as rated separately from the glass they sit on.
    """

    COATING = "coating"
    CEMENT = "cement"


class SurfaceLimits(StatableModel):
    """A coated or cemented surface and the environment its maker rates it for.

    A cement softens, and a coating crazes or delaminates, at a temperature or humidity the
    housing around it survives (Yoder and Vukobratovich, Opto-Mechanical Systems Design).
    ``coldest`` and ``hottest`` bound the rated temperature. ``relative_humidity`` is the
    highest rated exposure, as a fraction from 0 to 1, and ``irradiance`` the highest rated
    flux. Each is optional, and a limit left out is one the screen names when the
    environment states that condition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    surface: Named
    treatment: SurfaceTreatment
    coldest: Quantity | None = None
    hottest: Quantity | None = None
    relative_humidity: float | None = None
    irradiance: Quantity | None = None

    @model_validator(mode="after")
    def _limits(self) -> SurfaceLimits:
        for label, value in (("coldest", self.coldest), ("hottest", self.hottest)):
            if value is not None:
                _check(value, "[temperature]", label)
        if self.coldest is not None and self.hottest is not None:
            if self.hottest.to("K").magnitude <= self.coldest.to("K").magnitude:
                raise ValueError(
                    f"'{self.surface}': hottest must exceed coldest; got {self.hottest} and "
                    f"{self.coldest}"
                )
        if self.relative_humidity is not None:
            humidity = require_finite(self.relative_humidity, name="relative_humidity")
            if not 0 < humidity <= 1:
                raise ValueError(
                    f"'{self.surface}': relative_humidity must lie in (0, 1]; got {humidity}"
                )
        if self.irradiance is not None:
            _check(self.irradiance, "[power] / [area]", "irradiance")
            if self.irradiance.magnitude <= 0:
                raise ValueError(f"'{self.surface}': irradiance must be positive")
        return self


def surface_limits_scorecard(
    name: str,
    *,
    surfaces: tuple[SurfaceLimits, ...],
    cold: Quantity,
    hot: Quantity,
    relative_humidity: float | None = None,
    irradiance: Quantity | None = None,
) -> ScorecardEntry:
    """Screen every coated and cemented surface against the declared environment.

    Each surface's rated temperature range must cover ``cold`` to ``hot``, and where the
    environment states a ``relative_humidity`` (a fraction) or an ``irradiance``, each
    surface's rating for it must cover that too. A surface exceeded is a failure naming
    the surface, the limit and the environment. A surface with no rating for a condition
    the environment states is not evaluated, naming it: a cement softening at a temperature
    the housing survives is a failure no mechanical screen sees (Yoder and Vukobratovich,
    Opto-Mechanical Systems Design).
    """
    _check(cold, "[temperature]", "cold")
    _check(hot, "[temperature]", "hot")
    if hot.to("K").magnitude <= cold.to("K").magnitude:
        raise ValueError(f"hot must exceed cold; got hot {hot} and cold {cold}")
    if relative_humidity is not None:
        require_finite(relative_humidity, name="relative_humidity")
        if not 0 <= relative_humidity <= 1:
            raise ValueError(f"relative_humidity must lie in [0, 1]; got {relative_humidity}")
    if irradiance is not None:
        _check(irradiance, "[power] / [area]", "irradiance")
    surfaces = _records(surfaces, SurfaceLimits, "surfaces")
    exceeded: list[str] = []
    unrated: list[str] = []
    for limits in surfaces:
        label = f"{limits.surface} ({limits.treatment.value})"
        missing = []
        if limits.coldest is None:
            missing.append("coldest rating")
        elif cold.to("K").magnitude < limits.coldest.to("K").magnitude:
            exceeded.append(f"{label} rated to {limits.coldest}, environment reaches {cold}")
        if limits.hottest is None:
            missing.append("hottest rating")
        elif hot.to("K").magnitude > limits.hottest.to("K").magnitude:
            exceeded.append(f"{label} rated to {limits.hottest}, environment reaches {hot}")
        if relative_humidity is not None:
            if limits.relative_humidity is None:
                missing.append("humidity rating")
            elif relative_humidity > limits.relative_humidity:
                exceeded.append(
                    f"{label} rated to {limits.relative_humidity:.0%} relative humidity, "
                    f"environment reaches {relative_humidity:.0%}"
                )
        if irradiance is not None:
            if limits.irradiance is None:
                missing.append("irradiance rating")
            elif irradiance.to("W/m**2").magnitude > limits.irradiance.to("W/m**2").magnitude:
                exceeded.append(
                    f"{label} rated to {limits.irradiance}, environment reaches {irradiance}"
                )
        if missing:
            unrated.append(f"{label}: no {' or '.join(missing)}")
    population = f"{len(surfaces)} surface{'s' if len(surfaces) != 1 else ''} examined"
    if exceeded:
        status = CheckStatus.FAIL
        detail = f"{population}; the environment exceeds " + "; ".join(exceeded)
        if unrated:
            detail += "; and unrated: " + "; ".join(unrated)
    elif unrated:
        status = CheckStatus.NOT_EVALUATED
        detail = f"{population}; a rating the environment needs is missing for " + "; ".join(
            unrated
        )
    else:
        status = CheckStatus.PASS
        detail = (
            f"{population}; every rating covers {cold} to {hot}"
            + (
                f" at {relative_humidity:.0%} relative humidity"
                if relative_humidity is not None
                else ""
            )
            + (f" under {irradiance}" if irradiance is not None else "")
        )
    return ScorecardEntry(
        name=name,
        status=status,
        detail=detail,
        reference=_YODER_BONDED,
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "each surface's rated limits compared with the declared environment; the "
                "exceeded and unrated surfaces are named on the entry"
            ),
        ),
        addresses=("a cement or coating failing at an environment extreme",),
    )


if TYPE_CHECKING:
    _OutgassingSource = str
else:
    _OutgassingSource = cited(
        "where the outgassing figures came from — a test report, a data sheet or a database"
    )


class OutgassingRecord(StatableModel):
    """One non-metallic inside a sealed optical volume, and its outgassing figures.

    ``total_mass_loss`` (TML) and ``condensable`` (CVCM, the collected volatile condensable
    material) are mass fractions from 0 to 1, as ASTM E595-15 reports them in percent.
    ``test_method`` and ``source`` say where the figures came from. A material declared
    with neither figure is one the census names rather than assumes clean.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    material: Named
    total_mass_loss: float | None = None
    condensable: float | None = None
    test_method: str | None = None
    source: _OutgassingSource | None = None

    @model_validator(mode="after")
    def _figures(self) -> OutgassingRecord:
        for label, value in (
            ("total_mass_loss", self.total_mass_loss),
            ("condensable", self.condensable),
        ):
            if value is None:
                continue
            require_finite(value, name=label)
            if not 0 <= value <= 1:
                raise ValueError(
                    f"'{self.material}': {label} is a mass fraction in [0, 1]; got {value}"
                )
        if (self.total_mass_loss is None) != (self.condensable is None):
            raise ValueError(
                f"'{self.material}': a test reports total mass loss and condensable material "
                "together; state both or neither"
            )
        if self.total_mass_loss is not None and not (
            self.test_method and self.test_method.strip() and self.source and self.source.strip()
        ):
            raise ValueError(
                f"'{self.material}': outgassing figures need the test_method and source they "
                "came from"
            )
        return self


def outgassing_census_scorecard(
    name: str,
    *,
    materials: tuple[OutgassingRecord, ...],
    total_mass_loss_limit: float,
    condensable_limit: float,
) -> ScorecardEntry:
    """Census every non-metallic in a sealed optical volume against declared outgassing limits.

    Adhesives, elastomers, potting, coatings, cable jackets, labels and lubricants each
    carry a total mass loss and a condensable fraction by the ASTM E595-15 vacuum test.
    The condensable fraction governs, because it is what deposits on cold and optical
    surfaces; both are compared and both are stated. The limits are declared, never
    defaulted, because a programme's own criteria set them. A material with no figures is
    not evaluated, naming it, and the entry states how many materials it examined, so a
    clean census is distinguishable from an empty one.
    """
    for label, value in (
        ("total_mass_loss_limit", total_mass_loss_limit),
        ("condensable_limit", condensable_limit),
    ):
        require_finite(value, name=label)
        if not 0 < value <= 1:
            raise ValueError(f"{label} is a mass fraction in (0, 1]; got {value}")
    materials = _records(materials, OutgassingRecord, "materials")
    exceeded: list[str] = []
    unstated: list[str] = []
    listed: list[str] = []
    for record in materials:
        if record.total_mass_loss is None or record.condensable is None:
            unstated.append(str(record.material))
            continue
        figures = (
            f"{record.material} CVCM {record.condensable:.2%}, TML {record.total_mass_loss:.2%} "
            f"({record.test_method}; {record.source})"
        )
        listed.append(figures)
        if record.condensable > condensable_limit:
            exceeded.append(f"{record.material} CVCM {record.condensable:.2%}")
        if record.total_mass_loss > total_mass_loss_limit:
            exceeded.append(f"{record.material} TML {record.total_mass_loss:.2%}")
    population = f"{len(materials)} material{'s' if len(materials) != 1 else ''} examined"
    applied = f"limits CVCM {condensable_limit:.2%} (governing) and TML {total_mass_loss_limit:.2%}"
    parts = [population, applied]
    if listed:
        parts.append("; ".join(listed))
    if exceeded:
        status = CheckStatus.FAIL
        parts.append("over the limit: " + ", ".join(exceeded))
    elif unstated:
        status = CheckStatus.NOT_EVALUATED
    else:
        status = CheckStatus.PASS
    if unstated:
        parts.append("no outgassing data for " + ", ".join(unstated))
    return ScorecardEntry(
        name=name,
        status=status,
        detail=" — ".join(parts),
        reference=_ASTM_E595,
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "each material's tested figures compared with the declared limits; every "
                "material, its figures and its source are stated on the entry"
            ),
        ),
        addresses=("condensable outgassing on an optical surface",),
    )


if TYPE_CHECKING:
    _CleanlinessBasis = str
else:
    _CleanlinessBasis = cited(
        "why this cleanliness level needs that room — the contamination-control plan, the "
        "programme requirement or the practice guide the implication was read from"
    )


def iso_cleanroom_concentration(*, iso_class: float, particle_size: Quantity) -> float:
    """The most particles per m³ at or above ``particle_size`` an ISO class-N room allows.

    ISO 14644-1:2015 classification of air cleanliness sets the limit
    C = 10^N·(0.1/D)^2.08 for particle size D in µm, and its table rounds the result: class 5
    allows 3,520 per m³ of 0.5 µm and larger, class 7 allows 352,000. ``iso_class`` runs from
    1 to 9 and the particle size from 0.1 to 5 µm, the ranges the standard states.
    """
    require_finite(iso_class, name="iso_class")
    if not 1 <= iso_class <= 9:
        raise ValueError(f"iso_class must lie in [1, 9]; got {iso_class}")
    _check(particle_size, "[length]", "particle_size")
    size = particle_size.to("µm").magnitude
    if not 0.1 <= size <= 5:
        raise ValueError(f"particle_size must lie in [0.1, 5] µm; got {particle_size}")
    return 10**iso_class * (0.1 / size) ** 2.08


def _three_figures(value: float) -> float:
    # ISO 14644-1 states its limits rounded to three significant figures, and a report
    # should print the figure a reader finds in the standard's table.
    return float(f"{value:.3g}")


class CleanlinessRequirement(StatableModel):
    """A declared surface cleanliness level, and the ISO 14644-1 room class it needs.

    ``level`` is the requirement as the programme states it, for example "IEST-STD-CC1246E
    level 300". No standard turns a surface level into a room class by formula, so the
    implication is declared as ``implies_iso_class`` with the ``basis`` it was read from,
    and a report carries both.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Named
    implies_iso_class: float
    basis: _CleanlinessBasis

    @model_validator(mode="after")
    def _a_class(self) -> CleanlinessRequirement:
        require_finite(self.implies_iso_class, name="implies_iso_class")
        if not 1 <= self.implies_iso_class <= 9:
            raise ValueError(f"implies_iso_class must lie in [1, 9]; got {self.implies_iso_class}")
        return self


def cleanliness_scorecard(
    name: str,
    *,
    requirement: CleanlinessRequirement,
    assembly_iso_class: float | None = None,
) -> ScorecardEntry:
    """Screen a cleanliness requirement against the room the assembly is declared built in.

    The ``requirement`` names the ISO 14644-1 class its level needs. The assembly room's
    ``assembly_iso_class`` must be that class or cleaner, a lower number. Each room's limit
    for particles of 0.5 µm and larger, from :func:`iso_cleanroom_concentration`, is stated
    so the gap reads as particles, not as class numbers. With no assembly room declared,
    the entry is not evaluated, naming it: a cleanliness requirement nobody costed into the
    build environment is found at assembly.
    """
    if not isinstance(requirement, CleanlinessRequirement):
        raise ValueError(f"requirement must be a CleanlinessRequirement; got {requirement!r}")
    needed = requirement.implies_iso_class
    half_micron = Quantity(magnitude=0.5, unit="µm")
    limit = _three_figures(iso_cleanroom_concentration(iso_class=needed, particle_size=half_micron))
    stated = (
        f"{requirement.level} needs ISO class {needed:g} "
        f"({limit:,.0f} per m³ at 0.5 µm; {requirement.basis})"
    )
    if assembly_iso_class is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=f"{stated}; no assembly environment is declared to build it in",
            reference=_ISO_14644,
        )
    require_finite(assembly_iso_class, name="assembly_iso_class")
    if not 1 <= assembly_iso_class <= 9:
        raise ValueError(f"assembly_iso_class must lie in [1, 9]; got {assembly_iso_class}")
    room = iso_cleanroom_concentration(iso_class=assembly_iso_class, particle_size=half_micron)
    achieved = assembly_iso_class <= needed
    return ScorecardEntry(
        name=name,
        status=CheckStatus.PASS if achieved else CheckStatus.FAIL,
        detail=(
            f"{stated}; the assembly room is ISO class {assembly_iso_class:g} "
            f"({_three_figures(room):,.0f} per m³ at 0.5 µm), which "
            + ("achieves it" if achieved else "cannot achieve it")
        ),
        reference=_ISO_14644,
        underived=Underived(
            kind=DerivationAbsence.LOOKUP,
            reason=(
                "the declared room class compared with the class the requirement names; "
                "both rooms' limits C = 10^N·(0.1/D)^2.08 are stated on the entry"
            ),
        ),
        addresses=("particulate on an optical surface from the assembly room",),
    )


_JOHNSON = "Johnson, Contact Mechanics (1985), Hertzian line contact"
_ISO_14644 = "ISO 14644-1:2015 classification of air cleanliness by particle concentration"
_ASTM_E595 = (
    "ASTM E595-15 total mass loss and collected volatile condensable materials from "
    "outgassing in a vacuum environment"
)
_YODER_BONDED = (
    "Yoder and Vukobratovich, Opto-Mechanical Systems Design, 4th ed. (2015), bonded and "
    "cemented optics"
)
_YODER = "Yoder and Vukobratovich, Opto-Mechanical Systems Design, 4th ed. (2015), line of sight"
_TIMOSHENKO = (
    "Timoshenko and Woinowsky-Krieger, Theory of Plates and Shells, 2nd ed. (1959), "
    "simply supported circular plate"
)
_CENGEL = (
    "Cengel and Boles, Thermodynamics: An Engineering Approach, 9th ed. (2019), "
    "ideal-gas equation of state"
)
_INCROPERA = "Incropera, Fundamentals of Heat and Mass Transfer, 7th ed. (2011), thermal resistance"
_HARRIS = "Harris and Piersol, Harris' Shock and Vibration Handbook, 5th ed. (2002)"


# The unit layer counts an angle as dimensionless, so a strain in mm/m would convert to
# radians without complaint. An angle is accepted only in a unit that is one.
_ANGLE_UNITS = frozenset(
    {
        "rad",
        "radian",
        "mrad",
        "milliradian",
        "µrad",
        "urad",
        "microradian",
        "deg",
        "degree",
        "arcmin",
        "arcminute",
        "arcsec",
        "arcsecond",
    }
)


def _radians(value: Quantity, name: str) -> float:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be an angle quantity; got {value!r}")
    if str(value.unit).strip() not in _ANGLE_UNITS:
        raise ValueError(
            f"{name} must be an angle — rad, mrad, µrad, deg, arcmin or arcsec; got {value}"
        )
    require_finite(value, name=name)
    return value.to("rad").magnitude


_STANDARD_GRAVITY = 9.80665  # m/s², the conventional g₀ of the CGPM (1901)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    require_finite(value, name=name)


_REFRACTIVEINDEX = (
    "SCHOTT Zemax catalog 2017-01-20b, via the refractiveindex.info database (CC0 1.0)"
)

#: N-BK7, only what the cited source states. dn/dT, the elastic constants, hardness and the
#: stress-optic coefficient are not on that page, so they are left unstated rather than
#: recalled.
N_BK7 = OpticalMaterial(
    name="N-BK7",
    source=_REFRACTIVEINDEX,
    refractive_index=1.5168,
    abbe_number=64.17,
    cte=(
        RangedProperty(
            value=Quantity(magnitude=7.1e-6, unit="1/K"),
            low=Quantity(magnitude=243.0, unit="K"),
            high=Quantity(magnitude=343.0, unit="K"),
            source=_REFRACTIVEINDEX,
        ),
        RangedProperty(
            value=Quantity(magnitude=8.3e-6, unit="1/K"),
            low=Quantity(magnitude=293.0, unit="K"),
            high=Quantity(magnitude=573.0, unit="K"),
            source=_REFRACTIVEINDEX,
        ),
    ),
    density=Quantity(magnitude=2510.0, unit="kg/m**3"),
)
