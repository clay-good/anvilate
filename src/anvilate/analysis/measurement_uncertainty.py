"""T1 analytical measurement uncertainty (ISO GUM, closed-form).

Every measurement is a value plus a doubt, and a defensible result has to state the doubt. The ISO
Guide to the Expression of Uncertainty in Measurement (GUM) sets out how: gather the individual
uncertainty contributions, combine them in quadrature, then expand the result to a stated level.
This module carries those three steps as closed forms — the metrology companion to the process
capability of :mod:`anvilate.analysis.process_capability`.

The standard uncertainty of a mean of repeated readings (a Type A evaluation) is u = s/√n, from the
sample standard deviation s and the number of readings n — averaging more readings tightens it.
Independent contributions combine by the law of propagation into the combined standard uncertainty
u_c = √(Σuᵢ²), the root-sum-of-squares (pass each contribution already multiplied by its sensitivity
coefficient, so it carries the units of the result). Finally the expanded uncertainty U = k·u_c
scales the combined value by a coverage factor k — k = 2 gives roughly 95% confidence for a normal
distribution — so the result is reported as value ± U. All contributions must share a dimension; the
sample size is a plain integer. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "standard_uncertainty_of_mean",
    "combined_standard_uncertainty",
    "expanded_uncertainty",
]


def standard_uncertainty_of_mean(*, standard_deviation: Quantity, sample_size: int) -> Quantity:
    """The Type A standard uncertainty of a mean, u = s/√n.

    The uncertainty in the average of ``sample_size`` n repeated readings whose scatter is the
    ``standard_deviation`` s: u = s/√n (the standard error of the mean). It shrinks only with the
    square root of the number of readings, so cutting it in half takes four times as many. The
    sample size must be at least 1. Returns the standard uncertainty in the units of
    ``standard_deviation``.
    """
    if not isinstance(sample_size, int) or sample_size < 1:
        raise ValueError("sample_size must be an integer of at least 1")
    s = standard_deviation.to(standard_deviation.unit).magnitude
    if s < 0:
        raise ValueError("standard_deviation must be non-negative")
    return Quantity(magnitude=s / sample_size**0.5, unit=standard_deviation.unit)


def combined_standard_uncertainty(*components: Quantity) -> Quantity:
    """The combined standard uncertainty, u_c = √(Σuᵢ²).

    The overall standard uncertainty from independent ``components``, combined in quadrature by the
    GUM law of propagation: u_c = √(Σuᵢ²). Pass each contribution already scaled by its sensitivity
    coefficient (so all share the units of the result); because they add as squares, the largest one
    dominates and shaving a small contributor barely moves the total. Needs at least one component,
    and all must share a dimension. Returns the combined standard uncertainty in the units of the
    first component.
    """
    if not components:
        raise ValueError("combined_standard_uncertainty needs at least one component")
    ref_unit = components[0].unit
    total = 0.0
    for u in components:
        if not u.has_dimension(components[0].dimensionality):
            raise ValueError(
                "all uncertainty components must share a dimension; got "
                f"{u.dimensionality} and {components[0].dimensionality}"
            )
        value = u.to(ref_unit).magnitude
        if value < 0:
            raise ValueError("uncertainty components must be non-negative")
        total += value * value
    return Quantity(magnitude=total**0.5, unit=ref_unit)


def expanded_uncertainty(
    *, combined_standard_uncertainty: Quantity, coverage_factor: float = 2.0
) -> Quantity:
    """The expanded uncertainty, U = k·u_c.

    The uncertainty interval to report at a stated confidence: U = ``coverage_factor`` k ·
    ``combined_standard_uncertainty`` u_c (from :func:`combined_standard_uncertainty`). For a
    roughly normal result k = 2 gives about 95% confidence and k = 3 about 99.7%; the measurement is
    reported as its value ± U. The coverage factor must be positive. Returns the expanded
    uncertainty in the units of ``combined_standard_uncertainty``.
    """
    uc = combined_standard_uncertainty.to(combined_standard_uncertainty.unit).magnitude
    if uc < 0:
        raise ValueError("combined_standard_uncertainty must be non-negative")
    if coverage_factor <= 0:
        raise ValueError("coverage_factor must be positive")
    return Quantity(magnitude=coverage_factor * uc, unit=combined_standard_uncertainty.unit)
