"""The ventilation pack: declare a zone's outdoor air, get an ASHRAE 62.1 adequacy scorecard.

Completing the facility trio with :mod:`anvilate.packs.noise_exposure` and
:mod:`anvilate.packs.lighting`, this pack screens what an occupied space breathes. A
:class:`VentilationZone` declares the ASHRAE 62.1 demand (per-person and per-area outdoor-air rates,
occupancy, floor area, and the zone air distribution effectiveness), the outdoor airflow actually
delivered, the room volume, and the minimum air-change rate the application calls for.
:func:`screen_ventilation` computes the required outdoor air and the delivered air-change rate, and
rolls both into a cited PASS/FAIL scorecard — a zone can meet the outdoor-air rate yet fall short on
air changes in a large-volume space, or the reverse. The rates and the air-change minimum are the
caller's cited values; the arithmetic is the pack's.
"""

from __future__ import annotations

from pydantic import ConfigDict

from ..analysis import air_changes_per_hour, breathing_zone_outdoor_airflow
from ..derivation import Derivation, SymbolValue
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "VentilationZone",
    "screen_ventilation",
]

_OUTDOOR_AIR_REFERENCE = "ASHRAE 62.1 ventilation-rate procedure (Voz)"
_AIR_CHANGE_REFERENCE = "application minimum air changes per hour"


class VentilationZone(GuardedInputs):
    """An occupied zone's ventilation demand and what it is actually given.

    ``people_outdoor_rate`` R_p (airflow per person) and ``occupancy`` P_z set the people demand;
    ``area_outdoor_rate`` R_a (airflow per floor area) and ``floor_area`` A_z set the area demand;
    ``zone_air_distribution_effectiveness`` E_z discounts for imperfect delivery.
    ``provided_outdoor_airflow`` is the outdoor air actually supplied, ``room_volume`` the space it
    serves, and ``required_air_changes`` the minimum ACH the application needs. All caller-supplied.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    people_outdoor_rate: Quantity
    occupancy: float
    area_outdoor_rate: Quantity
    floor_area: Quantity
    zone_air_distribution_effectiveness: float
    provided_outdoor_airflow: Quantity
    room_volume: Quantity
    required_air_changes: float


def screen_ventilation(
    zone: VentilationZone,
    *,
    required_safety_factor: float = 1.0,
) -> Scorecard:
    """Screen a :class:`VentilationZone` for outdoor air and air changes; return its scorecard.

    Screens the delivered outdoor airflow against the ASHRAE 62.1 required V_oz (safety factor
    provided/required, PASS when the zone gets enough outdoor air) and the delivered air-change rate
    against the application minimum (safety factor ACH/ACH_required), each against
    ``required_safety_factor`` (1.0 — the rates carry their own margins). Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited PASS/FAIL entry for each.
    """
    required = breathing_zone_outdoor_airflow(
        people_outdoor_rate=zone.people_outdoor_rate,
        occupancy=zone.occupancy,
        area_outdoor_rate=zone.area_outdoor_rate,
        floor_area=zone.floor_area,
        zone_air_distribution_effectiveness=zone.zone_air_distribution_effectiveness,
    )
    provided = zone.provided_outdoor_airflow.to("L/s").magnitude
    required_ls = required.to("L/s").magnitude
    oa_sf = provided / required_ls if required_ls > 0 else None
    oa_derivation = Derivation(
        symbolic="V_oz = (R_p · P_z + R_a · A_z) / E_z",
        inputs=(
            SymbolValue(
                symbol="R_p",
                description="outdoor airflow required per person",
                value=zone.people_outdoor_rate,
                unit="L/s",
            ),
            SymbolValue(symbol="P_z", description="zone occupancy", value=zone.occupancy),
            SymbolValue(
                symbol="R_a",
                description="outdoor airflow required per unit of floor area",
                value=zone.area_outdoor_rate,
            ),
            SymbolValue(
                symbol="A_z", description="zone floor area", value=zone.floor_area, unit="m**2"
            ),
            SymbolValue(
                symbol="E_z",
                description="zone air distribution effectiveness — 1.0 for good mixing, less "
                "where supply air short-circuits to the return",
                value=zone.zone_air_distribution_effectiveness,
            ),
        ),
        result=SymbolValue(
            symbol="V_oz",
            description="outdoor airflow the zone must be supplied",
            value=required,
            unit="L/s",
        ),
        citation=_OUTDOOR_AIR_REFERENCE,
    )
    oa_entry = ScorecardEntry.from_safety_factor(
        "outdoor air", computed=oa_sf, required=required_safety_factor
    ).model_copy(update={"reference": _OUTDOOR_AIR_REFERENCE, "derivation": oa_derivation})

    ach = air_changes_per_hour(airflow=zone.provided_outdoor_airflow, room_volume=zone.room_volume)
    ach_sf = ach / zone.required_air_changes if zone.required_air_changes > 0 else None
    ach_derivation = Derivation(
        symbolic="ACH = Q / V",
        inputs=(
            SymbolValue(
                symbol="Q",
                description="outdoor airflow delivered to the zone",
                value=zone.provided_outdoor_airflow,
                unit="m**3/hour",
                # Both halves keep their unit under every system, because the pair has to
                # divide to a per-hour rate and the system's table has no unit for a
                # volumetric flow and reads a volume as a section modulus.
                unit_is_required=True,
            ),
            SymbolValue(
                symbol="V",
                description="room volume",
                value=zone.room_volume,
                unit="m**3",
                unit_is_required=True,
            ),
        ),
        result=SymbolValue(
            symbol="ACH",
            description="air changes per hour the delivered airflow achieves",
            # A rate, with its unit, because that is what Q/V comes to. It was a bare
            # 0.94 while the line above it divided a flow by a volume and gave 0.94 per
            # hour — a reviewer doing the division on the page arrives at a rate and reads
            # a pure number, and only the gloss said which.
            value=Quantity(magnitude=ach, unit="1/hour"),
            unit="1/hour",
            unit_is_required=True,
        ),
        citation=_AIR_CHANGE_REFERENCE,
    )
    ach_entry = ScorecardEntry.from_safety_factor(
        "air changes per hour", computed=ach_sf, required=required_safety_factor
    ).model_copy(update={"reference": _AIR_CHANGE_REFERENCE, "derivation": ach_derivation})
    return Scorecard(entries=(oa_entry, ach_entry))
