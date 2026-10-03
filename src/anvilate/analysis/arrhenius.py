"""T1 analytical Arrhenius reaction-rate checks (closed-form).

Almost every thermally-activated process — a chemical reaction, a diffusion step, a corrosion or
aging mechanism, the drift of a semiconductor — speeds up with temperature by the Arrhenius law: the
rate climbs exponentially as the temperature rises, governed by an activation energy. This is the
basis of accelerated life testing (run hot to age fast, then extrapolate) and of the rule of thumb
that many reactions roughly double for every 10 K. It is distinct from the creep-rupture
time-temperature of :mod:`anvilate.analysis.creep` (a Larson-Miller correlation, not a rate law).

The rate constant is k = A * exp(-Ea/(R*T)), from the pre-exponential factor A, the activation
energy Ea, the gas constant R, and the absolute temperature T. Comparing two temperatures gives the
acceleration factor k2/k1 = exp((Ea/R)*(1/T1 - 1/T2)) — how much faster the process runs when hot,
the multiplier an accelerated test buys. Reading two measured rates the other way extracts the
activation energy, Ea = R * ln(k2/k1) / (1/T1 - 1/T2), the slope of an Arrhenius plot.

Temperatures are absolute (kelvin); the exponential is meaningless for a Celsius value.

Sources: Fogler, *Elements of Chemical Reaction Engineering* (the rate constant) — the Arrhenius
form k = A·exp(-Ea/RT), the rate ratio between two temperatures, and the activation energy two
measured rates imply.
"""

from __future__ import annotations

from math import exp, log

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_KINETIC_DATA_SOURCE = "the cited or fitted Arrhenius parameters for the reaction"
_TEMPERATURE_SOURCE = "the absolute temperatures of the operating or test conditions"
_RATE_DATA_SOURCE = "the measured rate constants at the two test temperatures"


class _ArrheniusInputError(RefusalError, ValueError):
    """An Arrhenius-kinetics input that cannot be used without correction."""


def _arrhenius_refusal(message: str, *, subject: str, source: str) -> _ArrheniusInputError:
    return _ArrheniusInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _arrhenius_input_source(name: str) -> str:
    if name in {"temperature", "temperature_high", "temperature_low"}:
        return _TEMPERATURE_SOURCE
    if name in {"rate_constant_high", "rate_constant_low"}:
        return _RATE_DATA_SOURCE
    return _KINETIC_DATA_SOURCE


_GAS_CONSTANT = 8.314462618  # J/(mol*K)

__all__ = [
    "arrhenius_activation_energy",
    "arrhenius_rate_constant",
    "arrhenius_rate_ratio",
]


def arrhenius_rate_constant(
    *, pre_exponential_factor: Quantity, activation_energy: Quantity, temperature: Quantity
) -> Quantity:
    """The Arrhenius rate constant, k = A * exp(-Ea/(R*T)).

    The rate constant of a thermally-activated process: the ``pre_exponential_factor`` A (the
    high-temperature limiting rate) times the Boltzmann factor of the ``activation_energy`` Ea at
    absolute ``temperature`` T, k = A * exp(-Ea/(R*T)). It rises steeply with temperature. A is a
    first-order rate (1/time), and the result is returned in the same units (1/s).
    """
    _check(pre_exponential_factor, "1/[time]", "pre_exponential_factor")
    _check(activation_energy, "[energy]/[substance]", "activation_energy")
    _check(temperature, "[temperature]", "temperature")
    a = pre_exponential_factor.to("1/s").magnitude
    ea = activation_energy.to("J/mol").magnitude
    t = temperature.to("K").magnitude
    if a <= 0:
        raise _arrhenius_refusal(
            "pre_exponential_factor must be positive",
            subject="pre_exponential_factor",
            source=_KINETIC_DATA_SOURCE,
        )
    if t <= 0:
        raise _arrhenius_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_TEMPERATURE_SOURCE,
        )
    return Quantity(magnitude=a * exp(-ea / (_GAS_CONSTANT * t)), unit="1/s")


def arrhenius_rate_ratio(
    *,
    activation_energy: Quantity,
    temperature_low: Quantity,
    temperature_high: Quantity,
) -> float:
    """The acceleration factor between two temperatures, k2/k1 = exp((Ea/R)*(1/T1 - 1/T2)).

    How much faster a process of ``activation_energy`` Ea runs at ``temperature_high`` T2 than at
    ``temperature_low`` T1: k2/k1 = exp((Ea/R)*(1/T1 - 1/T2)). It is the multiplier an accelerated
    life test buys by running hot, and it captures the "rate doubles every ~10 K" rule for typical
    activation energies. Returns the ratio as a plain float (> 1 for T2 > T1).
    """
    _check(activation_energy, "[energy]/[substance]", "activation_energy")
    _check(temperature_low, "[temperature]", "temperature_low")
    _check(temperature_high, "[temperature]", "temperature_high")
    ea = activation_energy.to("J/mol").magnitude
    t1 = temperature_low.to("K").magnitude
    t2 = temperature_high.to("K").magnitude
    for subject, magnitude in (("temperature_low", t1), ("temperature_high", t2)):
        if magnitude <= 0:
            raise _arrhenius_refusal(
                "temperatures must be positive (absolute temperature)",
                subject=subject,
                source=_TEMPERATURE_SOURCE,
            )
    if t2 <= t1:
        raise _arrhenius_refusal(
            "temperature_high must exceed temperature_low",
            subject="temperature_low and temperature_high",
            source=_TEMPERATURE_SOURCE,
        )
    return exp((ea / _GAS_CONSTANT) * (1.0 / t1 - 1.0 / t2))


def arrhenius_activation_energy(
    *,
    rate_constant_low: Quantity,
    rate_constant_high: Quantity,
    temperature_low: Quantity,
    temperature_high: Quantity,
) -> Quantity:
    """The activation energy from two rates, Ea = R * ln(k2/k1) / (1/T1 - 1/T2).

    The materials/kinetics inverse: the ``activation_energy`` extracted from two measured rate
    constants, ``rate_constant_low`` k1 at ``temperature_low`` T1 and ``rate_constant_high`` k2 at
    ``temperature_high`` T2, Ea = R * ln(k2/k1) / (1/T1 - 1/T2). It is the slope of an Arrhenius
    plot (ln k versus 1/T) and characterizes the mechanism. Returns the activation energy in J/mol.
    """
    _check(rate_constant_low, "1/[time]", "rate_constant_low")
    _check(rate_constant_high, "1/[time]", "rate_constant_high")
    _check(temperature_low, "[temperature]", "temperature_low")
    _check(temperature_high, "[temperature]", "temperature_high")
    k1 = rate_constant_low.to("1/s").magnitude
    k2 = rate_constant_high.to("1/s").magnitude
    t1 = temperature_low.to("K").magnitude
    t2 = temperature_high.to("K").magnitude
    for subject, magnitude in (("rate_constant_low", k1), ("rate_constant_high", k2)):
        if magnitude <= 0:
            raise _arrhenius_refusal(
                "rate constants must be positive", subject=subject, source=_RATE_DATA_SOURCE
            )
    for subject, magnitude in (("temperature_low", t1), ("temperature_high", t2)):
        if magnitude <= 0:
            raise _arrhenius_refusal(
                "temperatures must be positive (absolute temperature)",
                subject=subject,
                source=_TEMPERATURE_SOURCE,
            )
    if t2 <= t1:
        raise _arrhenius_refusal(
            "temperature_high must exceed temperature_low",
            subject="temperature_low and temperature_high",
            source=_TEMPERATURE_SOURCE,
        )
    if k2 <= k1:
        raise _arrhenius_refusal(
            "rate_constant_high must exceed rate_constant_low (rate rises with T)",
            subject="rate_constant_low and rate_constant_high",
            source=_RATE_DATA_SOURCE,
        )
    ea = _GAS_CONSTANT * log(k2 / k1) / (1.0 / t1 - 1.0 / t2)
    return Quantity(magnitude=ea, unit="J/mol")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _arrhenius_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_arrhenius_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _arrhenius_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_arrhenius_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
