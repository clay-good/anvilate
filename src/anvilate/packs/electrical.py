"""The electrical pack: declare a feeder, get an NEC voltage-drop-and-ampacity scorecard.

Alongside the facility packs, this pack screens the wire between a panel and a load. A
:class:`Feeder` declares the load it serves (power, power factor, voltage), the conductor run
(resistivity, one-way length, cross-section, optional reactance), and the two limits it must satisfy
— the ampacity of the chosen conductor and the acceptable voltage-drop percentage.
:func:`screen_feeder` finds the load current, the drop that current makes along the run, and rolls
both checks into a cited PASS/FAIL scorecard. The two governing conditions trade off with conductor
size: a wire fat enough to carry the current can still drop too much voltage over a long run, so the
length, not the current, often sizes the cable. The ampacity and drop limit are the caller's
code-derived values; the arithmetic is the pack's.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..analysis import (
    conductor_resistance,
    line_current_for_power,
    voltage_drop_three_phase,
)
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity

__all__ = [
    "Feeder",
    "screen_feeder",
]

_DROP_REFERENCE = "NEC 210.19(A)/215.2 informational note — feeder voltage drop"
_AMPACITY_REFERENCE = "NEC 310.16 — conductor ampacity"


class Feeder(BaseModel):
    """A three-phase feeder run and the two limits its screen checks.

    ``load_power`` P, ``power_factor`` cosφ, and ``line_voltage`` V_LL describe the load; the run is
    a conductor of ``resistivity`` ρ, ``one_way_length`` L, and ``conductor_area`` A, with optional
    ``reactance`` X. ``conductor_ampacity`` is the chosen conductor's rated current and
    ``drop_limit_percent`` the acceptable drop as a percent of nominal (3.0 by the NEC note). All
    are the caller's values.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    load_power: Quantity
    power_factor: float
    line_voltage: Quantity
    resistivity: Quantity
    one_way_length: Quantity
    conductor_area: Quantity
    conductor_ampacity: Quantity
    drop_limit_percent: float = 3.0
    reactance: Quantity | None = None


def screen_feeder(
    feeder: Feeder,
    *,
    required_safety_factor: float = 1.0,
) -> Scorecard:
    """Screen a :class:`Feeder` for voltage drop and ampacity, and return its scorecard.

    Finds the load current, the voltage drop it makes along the run, and screens the drop percent
    against the limit (safety factor limit/drop) and the load current against the conductor ampacity
    (safety factor ampacity/current), each against ``required_safety_factor`` (1.0 — the limits
    carry their own margins). Returns a :class:`~anvilate.scorecard.Scorecard` with a cited
    PASS/FAIL entry for each; a long run can pass ampacity yet fail on voltage drop.
    """
    current = line_current_for_power(
        real_power=feeder.load_power,
        line_voltage=feeder.line_voltage,
        power_factor=feeder.power_factor,
    )
    resistance = conductor_resistance(
        resistivity=feeder.resistivity,
        length=feeder.one_way_length,
        cross_section_area=feeder.conductor_area,
    )
    drop = voltage_drop_three_phase(
        line_current=current,
        resistance=resistance,
        power_factor=feeder.power_factor,
        reactance=feeder.reactance,
    )
    drop_percent = drop.to("V").magnitude / feeder.line_voltage.to("V").magnitude * 100.0
    drop_sf = feeder.drop_limit_percent / drop_percent if drop_percent > 0 else None
    drop_entry = ScorecardEntry.from_safety_factor(
        "voltage drop", computed=drop_sf, required=required_safety_factor
    ).model_copy(update={"reference": _DROP_REFERENCE})

    amps = current.to("A").magnitude
    ampacity = feeder.conductor_ampacity.to("A").magnitude
    ampacity_sf = ampacity / amps if amps > 0 else None
    ampacity_entry = ScorecardEntry.from_safety_factor(
        "conductor ampacity", computed=ampacity_sf, required=required_safety_factor
    ).model_copy(update={"reference": _AMPACITY_REFERENCE})
    return Scorecard(entries=(drop_entry, ampacity_entry))
