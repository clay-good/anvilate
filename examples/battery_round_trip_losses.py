"""Worked example: the solar surplus that shrinks on its way through the battery.

An off-grid system stores the day's solar surplus and spends it at night, but a battery is not a
lossless bucket — every kilowatt-hour charged in comes back out smaller, because both the charge and
the discharge waste some energy to internal resistance. The round-trip efficiency η = E_out/E_in is
the fraction that survives the round trip, and the energy the loads actually see is E_stored·η.

This example runs a day's 12 kWh solar surplus through two battery chemistries. A lithium-ion bank
at 0.94 round-trip returns 11.3 kWh — nearly all of it. A lead-acid bank at 0.80 returns only
9.6 kWh from the same charge, losing 2.4 kWh to the round trip, enough to leave the evening loads
short if the system was sized on the stored figure. The 14-point efficiency gap is 1.7 kWh a day —
the quiet reason lead-acid off-grid systems need more panels and battery than their nameplate
suggests. The lesson is that storage sizing must be done on delivered energy, not stored: the
round-trip efficiency is the difference between what the panels made and what the house gets.

Run it directly (``python examples/battery_round_trip_losses.py``);
:func:`delivered_energy` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import battery_delivered_energy
from anvilate.units import Quantity

SOLAR_SURPLUS = Quantity.parse("12 kWh")
LITHIUM_EFFICIENCY = 0.94
LEAD_ACID_EFFICIENCY = 0.80


def delivered_energy() -> dict[str, float]:
    """Return the energy each chemistry returns from the same stored solar surplus."""
    lithium = battery_delivered_energy(
        stored_energy=SOLAR_SURPLUS, round_trip_efficiency=LITHIUM_EFFICIENCY
    )
    lead_acid = battery_delivered_energy(
        stored_energy=SOLAR_SURPLUS, round_trip_efficiency=LEAD_ACID_EFFICIENCY
    )
    return {
        "lithium_kwh": lithium.to("kWh").magnitude,
        "lead_acid_kwh": lead_acid.to("kWh").magnitude,
    }


def main() -> None:
    d = delivered_energy()
    stored = SOLAR_SURPLUS.to("kWh").magnitude
    print(f"stored solar surplus : {stored:.1f} kWh")
    print(f"lithium (94% RT)  : delivers {d['lithium_kwh']:.1f} kWh")
    print(
        f"lead-acid (80% RT) : delivers {d['lead_acid_kwh']:.1f} kWh "
        f"(loses {stored - d['lead_acid_kwh']:.1f} kWh)"
    )
    print("  -> size the storage on delivered energy, not stored; the round-trip loss is real")


if __name__ == "__main__":
    main()
