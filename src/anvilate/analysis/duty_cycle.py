"""T1 fatigue over a duty cycle: named events, each counted by rainflow, damaged by Miner.

A part's life is not one load. A suspension bracket sees potholes, cornering and braking,
each so many times per kilometre, each a different history; which of them uses the life
is the question a design review asks first. A duty cycle declares that: named events,
each with its stress history (counted by :func:`~anvilate.analysis.rainflow.rainflow_count`)
or its own block of ranges, how many times it occurs per life, and where it came from.

Each counted cycle of range Δσ and mean σ_m has amplitude σ_a = Δσ/2, and the declared
mean-stress correction turns it into a fully reversed equivalent:

- none: σ_a itself;
- Goodman: σ_a/(1 − σ_m/S_u) (:func:`~anvilate.analysis.fatigue.goodman_equivalent_reversed_stress`,
  Shigley §6-12; no credit for a compressive mean);
- Smith-Watson-Topper: √(σ_max·σ_a) (:func:`~anvilate.analysis.fatigue.smith_watson_topper_stress`);
  a cycle whose peak is not tensile does no damage under it.

The cycles to failure come from the declared Basquin S-N curve σ_a = a·N^b
(:func:`~anvilate.analysis.fatigue.basquin_cycles_to_failure`), and Palmgren-Miner sums
n/N: per pass of each event, per life (times its occurrences), and in total. The result
names each event's share of the total and the event with the largest. The S-N curve and
its source are the caller's; a curve read beyond its data is not extended here, and the
endurance limit, if any, is the caller's to state by the curve they declare.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import sqrt

from pydantic import BaseModel, ConfigDict

from .._models import Named, Provenance, RevalidatedModel, each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from .fatigue import basquin_cycles_to_failure, goodman_equivalent_reversed_stress
from .rainflow import RainflowCount, rainflow_count

__all__ = [
    "MeanStressCorrection",
    "BasquinCurve",
    "DutyEvent",
    "EventDamage",
    "DutyCycleDamage",
    "duty_cycle_damage",
]

_DUTY_SOURCE = "the duty-cycle record: each event's history, occurrences and source"


class _DutyCycleInputError(RefusalError, ValueError):
    """A duty-cycle input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str = _DUTY_SOURCE) -> _DutyCycleInputError:
    return _DutyCycleInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class MeanStressCorrection(StrEnum):
    """The declared mean-stress model: none, Goodman (Shigley §6-12), or Smith-Watson-Topper."""

    NONE = "none"
    GOODMAN = "goodman"
    SMITH_WATSON_TOPPER = "smith_watson_topper"


class BasquinCurve(RevalidatedModel):
    """A Basquin S-N curve σ_a = a·N^b and its source (the caller's material record)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    coefficient: Quantity
    exponent: float
    source: Provenance


class DutyEvent(RevalidatedModel):
    """One named event of a duty cycle, counted by rainflow (ASTM E1049): history and source.

    ``history`` is the stress at the critical point through one pass of the event;
    ``repeating`` declares whether one pass is a block that closes on itself (counted
    from its extreme) or a trace applied once (with residual half cycles), as
    :func:`~anvilate.analysis.rainflow.rainflow_count` reads it.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: Named
    history: tuple[Quantity, ...]
    occurrences_per_life: float
    source: Provenance
    repeating: bool = False


class EventDamage(RevalidatedModel):
    """One event's cycles, its damage by Miner's rule per pass and per life, and its share."""

    model_config = ConfigDict(frozen=True)

    event: Named
    count: RainflowCount
    damage_per_pass: float
    damage_per_life: float
    share: float


class DutyCycleDamage(BaseModel):
    """The duty cycle's damage per life by Miner's rule, by event, and what drives it.

    ``total_damage`` is per declared life; at 1 the life is used up. ``lives`` is
    1/total_damage. ``correction`` names the mean-stress model the damage was computed
    with (Palmgren-Miner over Basquin, with Goodman or Smith-Watson-Topper if declared).
    """

    model_config = ConfigDict(frozen=True)

    events: tuple[EventDamage, ...]
    total_damage: float
    lives: float
    governing_event: str
    correction: MeanStressCorrection
    curve_source: str

    def __str__(self) -> str:
        lines = [
            f"duty-cycle damage {self.total_damage:.4g} per life ({self.lives:.4g} lives; "
            f"Miner over the Basquin curve of {self.curve_source}, "
            f"{self.correction.value.replace('_', ' ')} mean-stress correction); "
            f"{self.governing_event} drives it"
        ]
        lines += [
            f"  {e.event}: {e.damage_per_life:.4g} per life ({e.share:.1%}), "
            f"{e.count.total_cycles:g} cycles per pass, {e.damage_per_pass:.4g} per pass"
            for e in self.events
        ]
        return "\n".join(lines)


def _equivalent_amplitude(
    stress_range: float, mean: float, correction: MeanStressCorrection, su: float | None
) -> float:
    amplitude = stress_range / 2
    if correction is MeanStressCorrection.NONE or amplitude == 0:
        return amplitude
    if correction is MeanStressCorrection.GOODMAN:
        if su is None:
            raise _refusal("Goodman's correction needs `ultimate_strength`",
                           subject="ultimate_strength")  # fmt: skip
        return float(
            goodman_equivalent_reversed_stress(
                alternating_stress=Quantity(magnitude=amplitude, unit="MPa"),
                mean_stress=Quantity(magnitude=mean, unit="MPa"),
                ultimate_strength=Quantity(magnitude=su, unit="MPa"),
            )
            .to("MPa")
            .magnitude
        )
    peak = mean + amplitude
    if peak <= 0:
        return 0.0  # a cycle with no tensile peak does no damage under SWT
    if peak < amplitude:  # a compressive mean: SWT is a tensile-mean model, so no credit
        return amplitude
    return sqrt(peak * amplitude)


def duty_cycle_damage(
    events: Sequence[DutyEvent],
    *,
    curve: BasquinCurve,
    correction: MeanStressCorrection,
    ultimate_strength: Quantity | None = None,
) -> DutyCycleDamage:
    """A duty cycle's damage by event: Miner's rule over a Basquin S-N curve.

    Every event's history is counted by rainflow; each cycle's equivalent amplitude under
    ``correction`` is read on ``curve`` for its life; damage per pass is Σ count/N, and per
    life it is that times the event's occurrences. ``ultimate_strength`` is required for
    Goodman. A history with fewer than three reversals is refused naming its event.
    """
    declared = each_one(events, DutyEvent, named="events")
    if not declared:
        raise _refusal("a duty cycle has at least one event", subject="events")
    names = [e.name for e in declared]
    if len(set(names)) != len(names):
        raise _refusal(f"events {names} repeat a name; each is reported by it", subject="events")
    if not isinstance(curve, BasquinCurve):
        raise _refusal("curve must be a BasquinCurve with its source", subject="curve",
                       source="the material's S-N record")  # fmt: skip
    if not isinstance(correction, MeanStressCorrection):
        raise _refusal(f"correction must be a MeanStressCorrection; got {correction!r}",
                       subject="correction", source="the program's fatigue method")  # fmt: skip
    su = None
    if correction is MeanStressCorrection.GOODMAN:
        if ultimate_strength is None:
            raise _refusal("Goodman's correction needs the material's ultimate strength; "
                           "declare `ultimate_strength`", subject="ultimate_strength",
                           source="the material's ultimate tensile strength")  # fmt: skip
        su = float(ultimate_strength.to("MPa").magnitude)
    damages = []
    for event in declared:
        occurrences = require_finite(event.occurrences_per_life, name="occurrences_per_life")
        if occurrences < 0:
            raise _refusal(f"event '{event.name}' occurs {occurrences} times per life",
                           subject="events")  # fmt: skip
        try:
            count = rainflow_count(list(event.history), repeating=event.repeating)
        except RefusalError as error:
            raise _refusal(f"event '{event.name}': {error}", subject="events") from error
        reversals = count.reversals
        if reversals < 3:
            raise _refusal(
                f"event '{event.name}' has a history of {reversals} reversals; a history "
                "shorter than three reversals has no closed cycle to count",
                subject="events",
            )
        per_pass = 0.0
        for cycle in count.cycles:
            amplitude = _equivalent_amplitude(
                float(Quantity(magnitude=cycle.range, unit=count.unit).to("MPa").magnitude),
                float(Quantity(magnitude=cycle.mean, unit=count.unit).to("MPa").magnitude),
                correction,
                su,
            )
            if amplitude == 0:
                continue
            life = basquin_cycles_to_failure(
                stress_amplitude=Quantity(magnitude=amplitude, unit="MPa"),
                coefficient=curve.coefficient,
                exponent=curve.exponent,
            )
            per_pass += cycle.count / life
        damages.append((event, count, per_pass, per_pass * occurrences))
    total = sum(d[3] for d in damages)
    results = tuple(
        EventDamage(event=e.name, count=c, damage_per_pass=p, damage_per_life=life,
                    share=(life / total if total > 0 else 0.0))
        for e, c, p, life in damages
    )  # fmt: skip
    governing = max(results, key=lambda r: r.damage_per_life).event
    return DutyCycleDamage(
        events=results,
        total_damage=total,
        lives=(1 / total if total > 0 else float("inf")),
        governing_event=governing,
        correction=correction,
        curve_source=curve.source,
    )
