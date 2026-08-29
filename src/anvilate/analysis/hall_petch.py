"""T1 analytical Hall-Petch grain-size strengthening checks (closed-form).

Finer grains make a metal stronger. Grain boundaries block the dislocations that carry plastic flow,
so the smaller the grains, the more boundaries a dislocation must pile up against, and the higher
the yield strength. The Hall-Petch relation captures this: σ_y = σ_0 + k·d^(−1/2), where σ_0 is the
friction stress (the resistance of the grain interior, extrapolated to infinite grain size), k is
the Hall-Petch slope (a material constant measuring how strongly boundaries strengthen), and d is
the average grain diameter.

The −1/2 power is the signature of dislocation pile-up: halving the grain size does not halve the
strengthening, it multiplies the grain-size term by √2. This is why grain refinement — through
controlled rolling, rapid solidification, or severe plastic deformation — is one of the few
strengthening routes that raises strength and toughness together. Inverting the relation gives the
grain size a target yield strength requires, d = [k/(σ_y − σ_0)]². The friction stress and slope are
caller-supplied material constants; all inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Dieter, *Mechanical Metallurgy* (strengthening mechanisms) — the Hall-Petch relation
sigma_y = sigma_0 + k/sqrt(d) between grain size and yield strength, and the grain diameter a
target yield requires.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "hall_petch_grain_diameter_for_yield",
    "hall_petch_yield_strength",
]


def hall_petch_yield_strength(
    *,
    friction_stress: Quantity,
    strengthening_coefficient: Quantity,
    grain_diameter: Quantity,
) -> Quantity:
    """The Hall-Petch yield strength, σ_y = σ_0 + k·d^(−1/2).

    The yield strength grain refinement produces: from the ``friction_stress`` σ_0 (the grain-
    interior resistance at infinite grain size), the ``strengthening_coefficient`` k (the Hall-Petch
    slope, units of stress·√length, e.g. MPa·√m), and the average ``grain_diameter`` d,
    σ_y = σ_0 + k·d^(−1/2). Finer grains (smaller d) raise the strength through the d^(−1/2) term.
    Invert it with :func:`hall_petch_grain_diameter_for_yield`. Returns the yield strength in MPa.
    """
    _check(friction_stress, "[pressure]", "friction_stress")
    _check(strengthening_coefficient, "[pressure]*[length]**0.5", "strengthening_coefficient")
    _check(grain_diameter, "[length]", "grain_diameter")
    sigma_0 = friction_stress.to("Pa").magnitude
    k = strengthening_coefficient.to("Pa*m**0.5").magnitude
    d = grain_diameter.to("m").magnitude
    if sigma_0 < 0:
        raise ValueError("friction_stress must be non-negative")
    if k < 0:
        raise ValueError("strengthening_coefficient must be non-negative")
    if d <= 0:
        raise ValueError("grain_diameter must be positive")
    sigma_y = sigma_0 + k * d**-0.5
    return Quantity(magnitude=sigma_y, unit="Pa").to("MPa")


def hall_petch_grain_diameter_for_yield(
    *,
    friction_stress: Quantity,
    strengthening_coefficient: Quantity,
    yield_strength: Quantity,
) -> Quantity:
    """The grain size for a target yield, d = [k/(σ_y − σ_0)]².

    The average grain diameter needed to reach a target ``yield_strength`` σ_y, inverting the
    Hall-Petch relation (:func:`hall_petch_yield_strength`): from the ``friction_stress`` σ_0 and
    the ``strengthening_coefficient`` k, d = [k/(σ_y − σ_0)]². The target must exceed the friction
    stress (no grain refinement can drop the strength below the grain-interior resistance σ_0). It
    sizes the grain refinement a thermomechanical process must achieve. Returns the grain diameter
    in µm.
    """
    _check(friction_stress, "[pressure]", "friction_stress")
    _check(strengthening_coefficient, "[pressure]*[length]**0.5", "strengthening_coefficient")
    _check(yield_strength, "[pressure]", "yield_strength")
    sigma_0 = friction_stress.to("Pa").magnitude
    k = strengthening_coefficient.to("Pa*m**0.5").magnitude
    sigma_y = yield_strength.to("Pa").magnitude
    if k <= 0:
        raise ValueError("strengthening_coefficient must be positive")
    if sigma_y <= sigma_0:
        raise ValueError(
            "yield_strength must exceed friction_stress (grain refinement adds to σ_0)"
        )
    d = (k / (sigma_y - sigma_0)) ** 2
    return Quantity(magnitude=d, unit="m").to("um")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
