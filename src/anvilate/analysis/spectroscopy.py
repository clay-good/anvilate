"""T1 analytical Beer-Lambert spectroscopy checks (closed-form).

When light passes through an absorbing solution, the fraction it loses depends on how much absorber
it meets — the Beer-Lambert law. This is the basis of colorimetry and UV-Vis spectrophotometry: read
how much light a sample absorbs and infer the concentration of the species responsible. It is a
distinct absorption law from the gamma/x-ray attenuation of
:mod:`anvilate.analysis.radiation_shielding` (which uses a bulk linear coefficient); here the
absorption is tied to a molar concentration through the molar absorptivity.

The absorbance is A = epsilon * c * l, from the molar absorptivity epsilon (how strongly the species
absorbs at that wavelength), the concentration c, and the path length l of the cell. Absorbance is a
base-10 logarithmic measure, so the transmittance — the fraction of light that gets through — is
T = 10^(-A): an absorbance of 1 passes 10%, of 2 passes 1%. Inverting the law turns a measured
absorbance back into the concentration that produced it, c = A / (epsilon * l) — the working
relation of quantitative absorption spectroscopy, valid in the dilute (linear) regime.

Sources: Skoog, West & Holler, *Principles of Instrumental Analysis* (molecular absorption
spectrometry) — the Beer-Lambert law A = eps·b·c, the transmittance it converts to and from, and
the concentration a measured absorbance infers at a known path length and molar absorptivity.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_ABSORPTIVITY_SOURCE = "the analyte's calibration curve or cited absorptivity at the wavelength"
_SAMPLE_SOURCE = "the prepared sample's concentration record"
_CELL_SOURCE = "the cuvette or flow-cell path length specification"
_READING_SOURCE = "the spectrophotometer's blank-corrected absorbance reading"


class _SpectroscopyInputError(RefusalError, ValueError):
    """A Beer-Lambert spectroscopy input that cannot be used without correction."""


def _spectroscopy_refusal(message: str, *, subject: str, source: str) -> _SpectroscopyInputError:
    return _SpectroscopyInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _spectroscopy_input_source(name: str) -> str:
    if name == "molar_absorptivity":
        return _ABSORPTIVITY_SOURCE
    if name == "concentration":
        return _SAMPLE_SOURCE
    if name == "path_length":
        return _CELL_SOURCE
    return _READING_SOURCE


__all__ = [
    "absorbance",
    "concentration_from_absorbance",
    "transmittance_from_absorbance",
]


def absorbance(
    *, molar_absorptivity: Quantity, concentration: Quantity, path_length: Quantity
) -> float:
    """The Beer-Lambert absorbance, A = epsilon * c * l.

    The absorbance of a sample: the ``molar_absorptivity`` epsilon (in L/(mol·cm)) times the
    ``concentration`` c and the cell ``path_length`` l, A = epsilon * c * l. It is a dimensionless,
    base-10 logarithmic measure — each unit of absorbance is another tenfold cut in transmitted
    light. Valid in the dilute regime where absorbance stays linear in concentration. Returns the
    absorbance as a plain float.
    """
    _check(molar_absorptivity, "[length]**2/[substance]", "molar_absorptivity")
    _check(concentration, "[substance]/[length]**3", "concentration")
    _check(path_length, "[length]", "path_length")
    eps = molar_absorptivity.to("L/(mol*cm)").magnitude
    c = concentration.to("mol/L").magnitude
    length = path_length.to("cm").magnitude
    if eps < 0:
        raise _spectroscopy_refusal(
            "molar_absorptivity must be non-negative",
            subject="molar_absorptivity",
            source=_ABSORPTIVITY_SOURCE,
        )
    if c < 0:
        raise _spectroscopy_refusal(
            "concentration must be non-negative", subject="concentration", source=_SAMPLE_SOURCE
        )
    if length <= 0:
        raise _spectroscopy_refusal(
            "path_length must be positive", subject="path_length", source=_CELL_SOURCE
        )
    return eps * c * length


def transmittance_from_absorbance(*, absorbance: float) -> float:
    """The transmittance from an absorbance, T = 10^(-A).

    The fraction of light a sample passes, from its ``absorbance`` A: T = 10^(-A). An absorbance of
    0 passes everything, 1 passes 10%, 2 passes 1% — the logarithmic scale absorbance is defined on.
    Returns the transmittance as a plain float in (0, 1].
    """
    require_finite(absorbance, name="absorbance")
    if absorbance < 0:
        raise _spectroscopy_refusal(
            "absorbance must be non-negative", subject="absorbance", source=_READING_SOURCE
        )
    return 10.0 ** (-absorbance)


def concentration_from_absorbance(
    *, absorbance: float, molar_absorptivity: Quantity, path_length: Quantity
) -> Quantity:
    """The concentration from a measured absorbance, c = A / (epsilon * l).

    The working inverse of :func:`absorbance`: the ``concentration`` of the absorbing species behind
    a measured ``absorbance`` A, given the ``molar_absorptivity`` epsilon and cell ``path_length``
    l, c = A / (epsilon * l). It is how a spectrophotometer reads a concentration from a light
    measurement, in the dilute (linear Beer-Lambert) regime. Returns the concentration in mol/L.
    """
    require_finite(absorbance, name="absorbance")
    _check(molar_absorptivity, "[length]**2/[substance]", "molar_absorptivity")
    _check(path_length, "[length]", "path_length")
    eps = molar_absorptivity.to("L/(mol*cm)").magnitude
    length = path_length.to("cm").magnitude
    if absorbance < 0:
        raise _spectroscopy_refusal(
            "absorbance must be non-negative", subject="absorbance", source=_READING_SOURCE
        )
    if eps <= 0:
        raise _spectroscopy_refusal(
            "molar_absorptivity must be positive",
            subject="molar_absorptivity",
            source=_ABSORPTIVITY_SOURCE,
        )
    if length <= 0:
        raise _spectroscopy_refusal(
            "path_length must be positive", subject="path_length", source=_CELL_SOURCE
        )
    return Quantity(magnitude=absorbance / (eps * length), unit="mol/L")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _spectroscopy_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_spectroscopy_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _spectroscopy_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_spectroscopy_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
