"""T1 analytical gamma/x-ray shielding (Beer-Lambert) checks (closed-form).

A beam of gamma rays or x-rays is attenuated as it passes through matter: each layer removes a fixed
fraction of what reaches it, so the intensity falls exponentially with thickness. This is the
narrow-beam Beer-Lambert law behind radiography shielding, medical-room walls, and the lead castle
around a source, and it complements the decay of :mod:`anvilate.analysis.radioactivity`: decay sets
how strong a source is over time, attenuation sets how much shielding tames its beam.

The transmitted fraction through a shield is T = exp(-mu * x), from the material's linear
attenuation coefficient mu (higher for denser, higher-Z shields like lead) and the thickness x.
Shielding is usually quoted as the half-value layer HVL = ln(2) / mu, the thickness that cuts the
beam in half; each added HVL halves it again. Designing a shield inverts the law: the thickness for
a target transmission is x = -ln(T) / mu. These are narrow-beam values — they ignore the build-up
from scattered photons, so a real broad-beam shield is somewhat thicker; this is a screening figure.

Sources: Krane, *Introductory Nuclear Physics* (interaction of radiation with matter) — the
exponential attenuation of a narrow beam, the half-value layer it implies, and the shield
thickness a target transmission requires. Narrow-beam attenuation only: no build-up factor is
applied.
"""

from __future__ import annotations

from math import exp, log

from ..units import Quantity

__all__ = [
    "half_value_layer",
    "radiation_transmission_fraction",
    "shield_thickness_for_transmission",
]


def radiation_transmission_fraction(
    *, attenuation_coefficient: Quantity, thickness: Quantity
) -> float:
    """The transmitted fraction through a shield, T = exp(-mu * x).

    The narrow-beam Beer-Lambert transmission: the fraction of a gamma/x-ray beam that passes a
    shield of ``thickness`` x with linear ``attenuation_coefficient`` mu, T = exp(-mu * x). Multiply
    a source intensity or dose rate by it for the value behind the shield. Ignores scattered-photon
    build-up (narrow beam). Returns the transmission as a plain float in (0, 1].
    """
    _check(attenuation_coefficient, "1/[length]", "attenuation_coefficient")
    _check(thickness, "[length]", "thickness")
    mu = attenuation_coefficient.to("1/m").magnitude
    x = thickness.to("m").magnitude
    if mu <= 0:
        raise ValueError("attenuation_coefficient must be positive")
    if x < 0:
        raise ValueError("thickness must be non-negative")
    return exp(-mu * x)


def half_value_layer(*, attenuation_coefficient: Quantity) -> Quantity:
    """The half-value layer, HVL = ln(2) / mu.

    The shield thickness that cuts a beam in half: from the linear ``attenuation_coefficient`` mu,
    HVL = ln(2) / mu. It is the standard way shielding is quoted — each added half-value layer
    halves the beam again, so n HVLs give a transmission of 2^(-n). Returns the HVL as a length.
    """
    _check(attenuation_coefficient, "1/[length]", "attenuation_coefficient")
    mu = attenuation_coefficient.to("1/m").magnitude
    if mu <= 0:
        raise ValueError("attenuation_coefficient must be positive")
    return Quantity(magnitude=log(2.0) / mu, unit="m")


def shield_thickness_for_transmission(
    *, attenuation_coefficient: Quantity, transmission_fraction: float
) -> Quantity:
    """The shield thickness for a target transmission, x = -ln(T) / mu.

    The design inverse of :func:`radiation_transmission_fraction`: the shield thickness needed to
    cut a beam to a target ``transmission_fraction`` T (e.g. 0.001 for a 1000-fold cut), given the
    linear ``attenuation_coefficient`` mu, x = -ln(T) / mu. It is a narrow-beam screening thickness;
    add margin for build-up in a real broad-beam geometry. Returns the thickness as a length.
    """
    _check(attenuation_coefficient, "1/[length]", "attenuation_coefficient")
    mu = attenuation_coefficient.to("1/m").magnitude
    if mu <= 0:
        raise ValueError("attenuation_coefficient must be positive")
    if not 0.0 < transmission_fraction <= 1.0:
        raise ValueError("transmission_fraction must be in (0, 1]")
    return Quantity(magnitude=-log(transmission_fraction) / mu, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
