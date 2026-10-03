"""T1 analytical luminous-efficacy (photometry) checks (closed-form).

How efficiently a lamp turns electricity into visible light is its luminous efficacy — the lumens it
emits per watt it draws. This is the headline number that separates an incandescent bulb (poor) from
an LED (good), and it sets the wattage a lighting job needs to hit a lumen target. It is the source
side of lighting design, upstream of the room-layout lumen method of
:mod:`anvilate.analysis.illumination`, which starts from the lumens a luminaire already emits.

The luminous efficacy is efficacy = luminous_flux / electrical_power (lm/W): about 15 lm/W for an
incandescent lamp, 100+ lm/W for a modern LED. Multiplying a lamp's efficacy by its power gives the
luminous flux it produces. Comparing the efficacy to the theoretical maximum of 683 lm/W — the
luminous efficacy of monochromatic 555 nm light, the peak of human vision — gives the overall
luminous efficiency, the fraction of the ideal a real source achieves.

Sources: the IES *Lighting Handbook* (photometric quantities) — luminous efficacy as lumens per
watt, the luminous flux a radiant power at a stated efficacy produces, and the luminous
efficiency measured against the 683 lm/W peak of the photopic response.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_PHOTOMETRIC_SOURCE = "the lamp's photometric test report (integrating-sphere or goniophotometer)"
_ELECTRICAL_SOURCE = "the lamp's rated or measured electrical input power"


class _PhotometryInputError(RefusalError, ValueError):
    """A photometric input that cannot be used without correction."""


def _photometry_refusal(message: str, *, subject: str, source: str) -> _PhotometryInputError:
    return _PhotometryInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _photometry_input_source(name: str) -> str:
    if name == "electrical_power":
        return _ELECTRICAL_SOURCE
    return _PHOTOMETRIC_SOURCE


_MAX_LUMINOUS_EFFICACY = 683.0  # lm/W, monochromatic 555 nm (peak photopic response)

__all__ = [
    "luminous_efficacy",
    "luminous_efficiency",
    "luminous_flux_from_power",
]


def luminous_efficacy(*, luminous_flux: Quantity, electrical_power: Quantity) -> Quantity:
    """The luminous efficacy of a source, efficacy = luminous_flux / electrical_power.

    How much visible light a lamp delivers per watt drawn: the ``luminous_flux`` (in lumens) over
    the ``electrical_power``. It is the standard efficiency figure for lighting — roughly 15 lm/W
    for incandescent, 60 for fluorescent, and over 100 for LED. Returns the efficacy in lm/W.
    """
    _check(luminous_flux, "[luminosity]", "luminous_flux")
    _check(electrical_power, "[power]", "electrical_power")
    flux = luminous_flux.to("lm").magnitude
    p = electrical_power.to("W").magnitude
    if flux < 0:
        raise _photometry_refusal(
            "luminous_flux must be non-negative",
            subject="luminous_flux",
            source=_PHOTOMETRIC_SOURCE,
        )
    if p <= 0:
        raise _photometry_refusal(
            "electrical_power must be positive",
            subject="electrical_power",
            source=_ELECTRICAL_SOURCE,
        )
    return Quantity(magnitude=flux / p, unit="lm/W")


def luminous_flux_from_power(
    *, electrical_power: Quantity, luminous_efficacy: Quantity
) -> Quantity:
    """The luminous flux a lamp emits, luminous_flux = electrical_power * efficacy.

    The visible light output of a lamp of ``electrical_power`` P and ``luminous_efficacy`` efficacy:
    luminous_flux = P * efficacy. It is how a lamp's rated efficacy and wattage give the lumens it
    contributes to a lighting design. Returns the luminous flux in lumens.
    """
    _check(electrical_power, "[power]", "electrical_power")
    _check(luminous_efficacy, "[luminosity]/[power]", "luminous_efficacy")
    p = electrical_power.to("W").magnitude
    eff = luminous_efficacy.to("lm/W").magnitude
    if p < 0:
        raise _photometry_refusal(
            "electrical_power must be non-negative",
            subject="electrical_power",
            source=_ELECTRICAL_SOURCE,
        )
    if eff < 0:
        raise _photometry_refusal(
            "luminous_efficacy must be non-negative",
            subject="luminous_efficacy",
            source=_PHOTOMETRIC_SOURCE,
        )
    return Quantity(magnitude=p * eff, unit="lm")


def luminous_efficiency(*, luminous_efficacy: Quantity) -> float:
    """The overall luminous efficiency, efficiency = efficacy / 683 lm/W.

    The fraction of the theoretical maximum a source reaches: its ``luminous_efficacy`` over the
    683 lm/W of monochromatic 555 nm light (the peak of human photopic vision). It bundles both the
    electrical-to-optical loss and the spectral mismatch with the eye — an LED at 100 lm/W is about
    15% efficient by this measure. Returns the efficiency as a plain float in [0, 1].
    """
    _check(luminous_efficacy, "[luminosity]/[power]", "luminous_efficacy")
    eff = luminous_efficacy.to("lm/W").magnitude
    if eff < 0:
        raise _photometry_refusal(
            "luminous_efficacy must be non-negative",
            subject="luminous_efficacy",
            source=_PHOTOMETRIC_SOURCE,
        )
    # 683 lm/W is the physical ceiling for any source, so the documented [0, 1] range and
    # the efficacy bound are the same statement. Without the upper half this returned 1.46
    # for a mis-scaled 1000 lm/W -- a source 46% better than ideal, reported as a bare
    # float that downstream code reads as a fraction. Every sibling in the library that
    # promises a bounded fraction enforces the bound.
    if eff > _MAX_LUMINOUS_EFFICACY:
        raise _photometry_refusal(
            f"luminous_efficacy is {luminous_efficacy}, above the {_MAX_LUMINOUS_EFFICACY:g} lm/W "
            f"of monochromatic 555 nm light — the physical maximum for any source. The efficiency "
            f"would be {eff / _MAX_LUMINOUS_EFFICACY:.3f}, better than ideal; check whether the "
            f"figure is a radiant-side or per-optical-watt efficacy",
            subject="luminous_efficacy",
            source=_PHOTOMETRIC_SOURCE,
        )
    return eff / _MAX_LUMINOUS_EFFICACY


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _photometry_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_photometry_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _photometry_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_photometry_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
