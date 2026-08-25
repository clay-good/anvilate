"""T1 analytical bulk-deformation (open-die forging) checks (closed-form).

Forging shapes metal by squeezing it past its yield point, and sizing the press is a short chain:
how much the work is strained, how hard the metal resists at that strain, and how much the friction
between die and work drives the load up beyond that. It completes the manufacturing set with the
subtractive :mod:`anvilate.analysis.machining`, the near-net :mod:`anvilate.analysis.casting`, and
the plastics :mod:`anvilate.analysis.injection_molding`.

Squeezing a billet from an initial to a final height imposes a true (logarithmic) strain
ε = ln(h₀/h₁) — the natural measure of large plastic deformation, which adds up over successive
blows the way engineering strain does not. Metal work-hardens as it deforms, and the Hollomon power
law gives its flow stress at that strain: σ = K·εⁿ, from the strength coefficient K and the
strain-hardening exponent n (both the material's, from a tension test). That flow stress is the base
pressure the press must supply.

Friction adds the rest. As the work spreads, die friction resists the outward flow and piles the
pressure up toward the centre — the *friction hill* — so the average pressure on a solid disc of
radius r and height h upset with a friction coefficient μ is σ·(1 + 2μr/(3h)), and the press load is
that pressure over the contact area. A flatter, wider forging (large r/h) fights more friction and
needs a disproportionately bigger press.

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (bulk deformation,
forging) — the true strain a height reduction imposes, the power-law flow stress K·eps^n it
develops, and the open-die forging load with its friction multiplier.
"""

from __future__ import annotations

from math import log, pi

from ..units import Quantity

__all__ = [
    "flow_stress_power_law",
    "forging_true_strain",
    "open_die_forging_load",
]


def forging_true_strain(*, initial_height: Quantity, final_height: Quantity) -> float:
    """The true (logarithmic) strain of an upset, ε = ln(h₀/h₁).

    The natural strain a forging blow imposes squeezing a billet from an ``initial_height`` h₀ to a
    ``final_height`` h₁: ε = ln(h₀/h₁). True strain is used instead of engineering strain because it
    adds across successive reductions and stays finite and meaningful at the large deformations
    forging reaches. It feeds the flow stress (see :func:`flow_stress_power_law`). Returns the
    dimensionless true strain.
    """
    _check(initial_height, "[length]", "initial_height")
    _check(final_height, "[length]", "final_height")
    h0 = initial_height.to("mm").magnitude
    h1 = final_height.to("mm").magnitude
    if h0 <= 0 or h1 <= 0:
        raise ValueError("initial_height and final_height must be positive")
    if h1 >= h0:
        raise ValueError("final_height must be less than initial_height (an upset reduces height)")
    return log(h0 / h1)


def flow_stress_power_law(
    *,
    strength_coefficient: Quantity,
    true_strain: float,
    strain_hardening_exponent: float,
) -> Quantity:
    """The flow stress by the Hollomon power law, σ = K·εⁿ.

    How hard a metal resists deforming at a given ``true_strain`` ε, from the
    ``strength_coefficient`` K and the ``strain_hardening_exponent`` n (both the material's):
    σ = K·εⁿ. Work-hardening (n > 0) raises the flow stress as the metal is worked, which is why a
    cold forging gets progressively harder to press. n ranges ~0.1–0.5 for annealed metals (0 is
    perfectly plastic). Feeds :func:`open_die_forging_load`. Returns the flow stress in MPa.
    """
    _check(strength_coefficient, "[pressure]", "strength_coefficient")
    k = strength_coefficient.to("MPa").magnitude
    if k <= 0:
        raise ValueError("strength_coefficient must be positive")
    if true_strain < 0:
        raise ValueError("true_strain must be non-negative")
    if not 0.0 <= strain_hardening_exponent < 1.0:
        raise ValueError(
            f"strain_hardening_exponent must be in [0, 1); got {strain_hardening_exponent}"
        )
    return Quantity(magnitude=k * true_strain**strain_hardening_exponent, unit="MPa")


def open_die_forging_load(
    *,
    flow_stress: Quantity,
    radius: Quantity,
    height: Quantity,
    friction_coefficient: float,
) -> Quantity:
    """The open-die upsetting load, F = σ·π·r²·(1 + 2μr/(3h)).

    The press force to upset a solid cylindrical billet of ``radius`` r and ``height`` h at a
    ``flow_stress`` σ (from :func:`flow_stress_power_law`) with a die ``friction_coefficient`` μ:
    F = σ·π·r²·(1 + 2μr/(3h)). The friction term (1 + 2μr/(3h)) is the friction hill — as the work
    spreads, die friction resists the outward flow and drives the average pressure above the flow
    stress. A flatter forging (larger r/h) fights more friction and needs a disproportionately
    bigger press, which is why forgings are struck in stages. Returns the forging load in kN.
    """
    _check(flow_stress, "[pressure]", "flow_stress")
    _check(radius, "[length]", "radius")
    _check(height, "[length]", "height")
    sigma = flow_stress.to("Pa").magnitude
    r = radius.to("m").magnitude
    h = height.to("m").magnitude
    if sigma <= 0:
        raise ValueError("flow_stress must be positive")
    if r <= 0 or h <= 0:
        raise ValueError("radius and height must be positive")
    if friction_coefficient < 0:
        raise ValueError("friction_coefficient must be non-negative")
    area = pi * r**2
    friction_hill = 1.0 + 2.0 * friction_coefficient * r / (3.0 * h)
    return Quantity(magnitude=sigma * area * friction_hill / 1000.0, unit="kN")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
