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

from ..derivation import Derivation, SymbolValue
from ..scorecard import CheckStatus, Comparison, LimitSense, ScorecardEntry
from ..units import Quantity, require_finite, temperature_difference_kelvin

__all__ = [
    "depth_of_focus",
    "thermal_focal_shift",
    "athermal_defocus",
    "athermal_focus_scorecard",
]

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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    require_finite(value, name=name)
