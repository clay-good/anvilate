"""T1 analytical exergy (availability / Second-Law) checks (closed-form).

Energy is conserved, so a First-Law balance never shows where a plant actually loses its ability to
do work — a First-Law analysis rates a furnace that turns 1800 K flame into 320 K hot water as
highly efficient. Exergy (availability) is the Second-Law measure that does show it: the useful work
a stream or a quantity of heat can deliver as it comes to equilibrium with the surroundings (the
*dead state* at T₀). This module is the availability companion to the energy-based cycles of
:mod:`anvilate.analysis.power_cycles` and :mod:`anvilate.analysis.refrigeration` and the heat flows
of :mod:`anvilate.analysis.thermal`.

Heat is not all available work: the exergy of a heat interaction Q at a source temperature T is only
its Carnot-weighted part, X_Q = Q·(1 − T₀/T) — heat delivered near the dead state carries almost no
exergy, which is why low-grade waste heat is hard to use. The flow (physical) exergy of a stream is
ψ = (h − h₀) − T₀·(s − s₀): the enthalpy it carries above the dead state, docked the part T₀·Δs that
is thermodynamically unavailable. And every real, irreversible process destroys exergy at a rate the
Gouy-Stodola theorem ties to entropy generation, İ = T₀·Ṡ_gen — the lost work that makes a real
device fall short of its reversible ideal. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values; temperatures must be absolute.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_ENERGY_SOURCE = "the energy balance's heat duty or enthalpy change for the process"
_STATE_SOURCE = "the property tables' state points for the stream (enthalpy and entropy)"
_TEMPERATURE_SOURCE = "the process design basis's reservoir and stream temperatures"
_DEAD_STATE_SOURCE = "the site design basis's ambient (dead-state) temperature"
_ENTROPY_SOURCE = "the entropy balance over the control volume"


class _ExergyInputError(RefusalError, ValueError):
    """An exergy input that cannot be used without correction."""


def _exergy_refusal(message: str, *, subject: str, source: str) -> _ExergyInputError:
    return _ExergyInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _exergy_input_source(name: str) -> str:
    if name in {"heat", "heat_transferred"}:
        return _ENERGY_SOURCE
    if name == "dead_state_temperature":
        return _DEAD_STATE_SOURCE
    if name in {"enthalpy_difference", "entropy_difference"}:
        return _STATE_SOURCE
    if name == "entropy_generation":
        return _ENTROPY_SOURCE
    return _TEMPERATURE_SOURCE


__all__ = [
    "entropy_generation_heat_transfer",
    "exergy_of_heat",
    "flow_exergy",
    "irreversibility_from_entropy_generation",
]


def exergy_of_heat(
    *,
    heat: Quantity,
    source_temperature: Quantity,
    dead_state_temperature: Quantity,
) -> Quantity:
    """The exergy (available work) of a heat interaction, X_Q = Q·(1 − T₀/T).

    The most work obtainable from a quantity (or rate) of ``heat`` Q supplied at a
    ``source_temperature`` T, relative to a surroundings ``dead_state_temperature`` T₀: X_Q =
    Q·(1 − T₀/T), the Carnot factor times the heat. Heat at a high temperature is nearly all
    exergy; as T falls toward T₀ the available work vanishes, which is why low-grade heat is hard to
    put to work. Both temperatures must be absolute and T ≥ T₀. Returns the exergy in the units of
    ``heat`` (energy or power).
    """
    require_finite(heat, name="heat")
    _check(source_temperature, "[temperature]", "source_temperature")
    _check(dead_state_temperature, "[temperature]", "dead_state_temperature")
    t = source_temperature.to("K").magnitude
    t0 = dead_state_temperature.to("K").magnitude
    for subject, magnitude in (("source_temperature", t), ("dead_state_temperature", t0)):
        if magnitude <= 0:
            raise _exergy_refusal(
                "temperatures must be positive absolute (kelvin) values",
                subject=subject,
                source=_exergy_input_source(subject),
            )
    if t < t0:
        raise _exergy_refusal(
            "source_temperature must be at least the dead_state_temperature",
            subject="source_temperature and dead_state_temperature",
            source=_TEMPERATURE_SOURCE,
        )
    if heat.has_dimension("[power]"):
        q = heat.to("W").magnitude
        return Quantity(magnitude=q * (1.0 - t0 / t), unit="W")
    if heat.has_dimension("[energy]"):
        q = heat.to("J").magnitude
        return Quantity(magnitude=q * (1.0 - t0 / t), unit="J")
    raise _exergy_refusal(
        f"heat must be an [energy] or [power] quantity; got {heat.dimensionality}",
        subject="heat",
        source=_ENERGY_SOURCE,
    )


def flow_exergy(
    *,
    enthalpy_difference: Quantity,
    entropy_difference: Quantity,
    dead_state_temperature: Quantity,
) -> Quantity:
    """The specific flow (physical) exergy of a stream, ψ = Δh − T₀·Δs.

    The maximum work a unit mass of a flowing stream can deliver as it is brought to the dead state,
    ψ = ``enthalpy_difference`` (h − h₀) − ``dead_state_temperature`` T₀ · ``entropy_difference``
    (s − s₀). The enthalpy term is the energy the stream carries above the surroundings; the T₀·Δs
    term is the part that is unavailable because it cannot be extracted without dumping entropy.
    Both differences are per unit mass and measured from the dead state; T₀ must be absolute.
    Returns the specific exergy in kJ/kg.
    """
    _check(enthalpy_difference, "[energy]/[mass]", "enthalpy_difference")
    _check(entropy_difference, "[energy]/[mass]/[temperature]", "entropy_difference")
    _check(dead_state_temperature, "[temperature]", "dead_state_temperature")
    dh = enthalpy_difference.to("kJ/kg").magnitude
    ds = entropy_difference.to("kJ/(kg*K)").magnitude
    t0 = dead_state_temperature.to("K").magnitude
    if t0 <= 0:
        raise _exergy_refusal(
            "dead_state_temperature must be positive absolute (kelvin)",
            subject="dead_state_temperature",
            source=_DEAD_STATE_SOURCE,
        )
    return Quantity(magnitude=dh - t0 * ds, unit="kJ/kg")


def irreversibility_from_entropy_generation(
    *,
    entropy_generation: Quantity,
    dead_state_temperature: Quantity,
) -> Quantity:
    """The exergy destroyed (irreversibility), İ = T₀·Ṡ_gen (Gouy-Stodola).

    The available work a real process destroys, tied to the entropy it generates by the
    Gouy-Stodola theorem: I = ``dead_state_temperature`` T₀ · ``entropy_generation`` S_gen. Every
    irreversibility — friction, unrestrained expansion, heat transfer across a finite ΔT, mixing —
    shows up here as lost work, the gap between a real device and its reversible ideal. Pass S_gen
    as a total ([energy]/[temperature], giving lost work) or a rate ([power]/[temperature], giving a
    lost-power); T₀ must be absolute. Returns the irreversibility in the matching units (J or W).
    """
    _check(dead_state_temperature, "[temperature]", "dead_state_temperature")
    t0 = dead_state_temperature.to("K").magnitude
    if t0 <= 0:
        raise _exergy_refusal(
            "dead_state_temperature must be positive absolute (kelvin)",
            subject="dead_state_temperature",
            source=_DEAD_STATE_SOURCE,
        )
    if entropy_generation.has_dimension("[power]/[temperature]"):
        sgen = entropy_generation.to("W/K").magnitude
        if sgen < 0:
            raise _exergy_refusal(
                "entropy_generation must be non-negative (Second Law)",
                subject="entropy_generation",
                source=_ENTROPY_SOURCE,
            )
        return Quantity(magnitude=t0 * sgen, unit="W")
    if entropy_generation.has_dimension("[energy]/[temperature]"):
        sgen = entropy_generation.to("J/K").magnitude
        if sgen < 0:
            raise _exergy_refusal(
                "entropy_generation must be non-negative (Second Law)",
                subject="entropy_generation",
                source=_ENTROPY_SOURCE,
            )
        return Quantity(magnitude=t0 * sgen, unit="J")
    raise _exergy_refusal(
        "entropy_generation must be an [energy]/[temperature] or [power]/[temperature] quantity; "
        f"got {entropy_generation.dimensionality}",
        subject="entropy_generation",
        source=_ENTROPY_SOURCE,
    )


def entropy_generation_heat_transfer(
    *,
    heat_transferred: Quantity,
    hot_temperature: Quantity,
    cold_temperature: Quantity,
) -> Quantity:
    """The entropy generated by heat flow across a finite ΔT, Ṡ_gen = Q·(1/T_c − 1/T_h).

    The most common irreversibility: whenever heat ``heat_transferred`` Q crosses from a hotter body
    at ``hot_temperature`` T_h to a colder one at ``cold_temperature`` T_c, the cold side gains more
    entropy (Q/T_c) than the hot side loses (Q/T_h), so the universe generates S_gen = Q·(1/T_c −
    1/T_h). This is the S_gen that :func:`irreversibility_from_entropy_generation` turns into
    destroyed work — and it is why a big temperature gap in a heat exchanger is thermodynamically
    expensive even though no energy is lost. Feed Q as an energy (S_gen in J/K) or a rate (S_gen in
    W/K). ``hot_temperature`` must exceed ``cold_temperature``; both are absolute. Returns S_gen in
    the matching units.
    """
    _check(hot_temperature, "[temperature]", "hot_temperature")
    _check(cold_temperature, "[temperature]", "cold_temperature")
    t_h = hot_temperature.to("K").magnitude
    t_c = cold_temperature.to("K").magnitude
    for subject, magnitude in (("cold_temperature", t_c), ("hot_temperature", t_h)):
        if magnitude <= 0:
            raise _exergy_refusal(
                "temperatures must be positive absolute (kelvin)",
                subject=subject,
                source=_TEMPERATURE_SOURCE,
            )
    if t_h <= t_c:
        raise _exergy_refusal(
            "hot_temperature must exceed cold_temperature (heat flows hot to cold)",
            subject="hot_temperature and cold_temperature",
            source=_TEMPERATURE_SOURCE,
        )
    factor = 1.0 / t_c - 1.0 / t_h
    if heat_transferred.has_dimension("[power]"):
        q = heat_transferred.to("W").magnitude
        if q < 0:
            raise _exergy_refusal(
                "heat_transferred must be non-negative",
                subject="heat_transferred",
                source=_ENERGY_SOURCE,
            )
        return Quantity(magnitude=q * factor, unit="W/K")
    if heat_transferred.has_dimension("[energy]"):
        q = heat_transferred.to("J").magnitude
        if q < 0:
            raise _exergy_refusal(
                "heat_transferred must be non-negative",
                subject="heat_transferred",
                source=_ENERGY_SOURCE,
            )
        return Quantity(magnitude=q * factor, unit="J/K")
    raise _exergy_refusal(
        "heat_transferred must be an [energy] or [power] quantity; "
        f"got {heat_transferred.dimensionality}",
        subject="heat_transferred",
        source=_ENERGY_SOURCE,
    )


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _exergy_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_exergy_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _exergy_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_exergy_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
