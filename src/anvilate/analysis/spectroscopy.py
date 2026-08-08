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
"""

from __future__ import annotations

from ..units import Quantity

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
        raise ValueError("molar_absorptivity must be non-negative")
    if c < 0:
        raise ValueError("concentration must be non-negative")
    if length <= 0:
        raise ValueError("path_length must be positive")
    return eps * c * length


def transmittance_from_absorbance(*, absorbance: float) -> float:
    """The transmittance from an absorbance, T = 10^(-A).

    The fraction of light a sample passes, from its ``absorbance`` A: T = 10^(-A). An absorbance of
    0 passes everything, 1 passes 10%, 2 passes 1% — the logarithmic scale absorbance is defined on.
    Returns the transmittance as a plain float in (0, 1].
    """
    if absorbance < 0:
        raise ValueError("absorbance must be non-negative")
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
    _check(molar_absorptivity, "[length]**2/[substance]", "molar_absorptivity")
    _check(path_length, "[length]", "path_length")
    eps = molar_absorptivity.to("L/(mol*cm)").magnitude
    length = path_length.to("cm").magnitude
    if absorbance < 0:
        raise ValueError("absorbance must be non-negative")
    if eps <= 0:
        raise ValueError("molar_absorptivity must be positive")
    if length <= 0:
        raise ValueError("path_length must be positive")
    return Quantity(magnitude=absorbance / (eps * length), unit="mol/L")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
