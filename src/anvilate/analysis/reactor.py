"""T1 analytical isothermal reactor-design checks (first-order kinetics, closed-form).

Sizing a chemical reactor turns on one dimensionless group: the Damköhler number, the ratio of the
reaction rate to the rate at which material is fed through. For a first-order reaction it is simply
Da = k·τ, from the rate constant k (from :mod:`anvilate.analysis.arrhenius`) and the mean residence
time τ = V/Q (reactor volume over volumetric flow). Small Da means the fluid leaves before it can
react; large Da means it reacts to near-completion.

The conversion — the fraction of reactant consumed — follows in closed form once Da is known, and it
differs between the two ideal reactor models. A plug-flow reactor (PFR), where fluid moves as
unmixed plugs, gives X = 1 − exp(−Da). A continuous stirred-tank reactor (CSTR), perfectly mixed so
the whole vessel sits at the low outlet concentration, gives X = Da/(1 + Da). For the same Da the
PFR always converts more, which is why it takes a larger CSTR to reach the same conversion — the
classic sizing trade-off. Rate constant and residence time are dimension-checked
:class:`~anvilate.units.Quantity` values; the Damköhler number and conversions are plain floats.
"""

from __future__ import annotations

from math import exp

from ..units import Quantity

__all__ = [
    "damkohler_number_first_order",
    "cstr_conversion_first_order",
    "cstr_series_conversion_first_order",
    "pfr_conversion_first_order",
]


def damkohler_number_first_order(*, rate_constant: Quantity, residence_time: Quantity) -> float:
    """The first-order Damköhler number, Da = k·τ.

    The ratio of the reaction rate to the convective feed rate for a first-order reaction:
    Da = k·τ, from the ``rate_constant`` k (units of 1/time) and the mean ``residence_time`` τ = V/Q
    (reactor volume over volumetric flow). It is the single group that sets conversion: Da ≪ 1 and
    the fluid passes through almost unreacted; Da ≫ 1 and it reacts to near-completion. Feed it to
    :func:`pfr_conversion_first_order` or :func:`cstr_conversion_first_order`. Returns the
    dimensionless Damköhler number as a plain float.
    """
    _check(rate_constant, "1/[time]", "rate_constant")
    _check(residence_time, "[time]", "residence_time")
    k = rate_constant.to("1/s").magnitude
    tau = residence_time.to("s").magnitude
    if k < 0:
        raise ValueError("rate_constant must be non-negative")
    if tau < 0:
        raise ValueError("residence_time must be non-negative")
    return k * tau


def pfr_conversion_first_order(*, damkohler_number: float) -> float:
    """The plug-flow reactor conversion, X = 1 − exp(−Da).

    The fraction of reactant consumed in a plug-flow reactor for a first-order reaction, from the
    ``damkohler_number`` Da = k·τ (:func:`damkohler_number_first_order`): X = 1 − exp(−Da). Fluid
    moves as unmixed plugs, each reacting as it travels, so conversion approaches 1 exponentially
    with Da. At the same Da a PFR always out-converts a CSTR (:func:`cstr_conversion_first_order`).
    Returns the conversion (0 to 1) as a plain float.
    """
    if damkohler_number < 0:
        raise ValueError("damkohler_number must be non-negative")
    return 1.0 - exp(-damkohler_number)


def cstr_conversion_first_order(*, damkohler_number: float) -> float:
    """The stirred-tank reactor conversion, X = Da/(1 + Da).

    The fraction of reactant consumed in a continuous stirred-tank reactor for a first-order
    reaction, from the ``damkohler_number`` Da = k·τ (:func:`damkohler_number_first_order`):
    X = Da/(1 + Da). Perfect mixing holds the whole vessel at the low outlet concentration, so the
    reaction runs slow everywhere and conversion lags a plug-flow reactor
    (:func:`pfr_conversion_first_order`) at the same Da — the reason a CSTR must be larger to reach
    the same conversion. Returns the conversion (0 to 1) as a plain float.
    """
    if damkohler_number < 0:
        raise ValueError("damkohler_number must be non-negative")
    return damkohler_number / (1.0 + damkohler_number)


def cstr_series_conversion_first_order(*, damkohler_number: float, stages: int) -> float:
    """The conversion of n equal stirred tanks in series, X = 1 − 1/(1 + Da/n)ⁿ.

    :func:`cstr_conversion_first_order` and :func:`pfr_conversion_first_order` are the two limiting
    ideal reactors; this is the cascade that spans them, and the one industry actually builds. The
    same total residence time is split over ``stages`` n equal tanks, so each sees a Damköhler
    number Da/n, and applying the single-tank result n times gives X = 1 − 1/(1 + Da/n)ⁿ from the
    total ``damkohler_number`` Da = k·τ_total (:func:`damkohler_number_first_order`).

    Staging recovers most of the plug-flow advantage without a tube: at Da = 4 one tank converts
    80.0%, three tanks 92.1%, ten tanks 96.5%, against the PFR ceiling of 98.2%. Both limits are
    exact — n = 1 reproduces :func:`cstr_conversion_first_order`, and n → ∞ reproduces
    :func:`pfr_conversion_first_order`, since (1 + Da/n)ⁿ → e^Da. Returns the conversion (0 to 1)
    as a plain float.
    """
    if damkohler_number < 0:
        raise ValueError("damkohler_number must be non-negative")
    if int(stages) != stages:
        raise ValueError(f"stages must be a whole number of tanks; got {stages}")
    n = int(stages)
    if n < 1:
        raise ValueError(f"stages must be at least 1; got {n}")
    return 1.0 - 1.0 / (1.0 + damkohler_number / n) ** n


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
