"""Capstone: the piston clearance that vanishes when the engine warms up.

An 80 mm aluminium piston runs in a cast-iron bore. Assembled cold on the bench it has a
0.10 mm diametral clearance -- a comfortable slip fit, and by every static measure it is fine.
Nothing is overloaded, nothing is stressed. It seizes anyway, the first time it gets hot.

Aluminium expands roughly twice as fast as cast iron (23 vs 11 µm/m·K), so as the assembly
climbs 150 °C to running temperature the piston grows 0.276 mm across while the bore grows only
0.132 mm. The clearance does not just shrink -- it closes by the *difference*, 0.144 mm, more
than the 0.10 mm it started with. The piston grows into the bore, wipes out its oil film, and
picks up. To survive, the cold clearance has to cover the thermal closure *plus* a minimum film
(here 0.02 mm), so it needs at least 0.164 mm cold; at 0.10 mm it reaches only a safety factor
of 0.61. Opening the cold clearance to 0.20 mm clears the closure and keeps a film, a safety
factor of 1.22.

The lesson is that a running clearance is set by *differential thermal expansion*, not by the
cold fit, whenever two mating parts are different materials or run at different temperatures.
The load never enters it. Size the clearance for the hot condition -- the cold fit is only where
you start -- and remember that the faster-expanding part on the inside is the one that closes the
gap.

Run it directly (``python examples/thermal_clearance_seizure.py``);
:func:`screen_clearance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import free_thermal_expansion
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

PISTON_DIAMETER = Quantity.parse("80 mm")
PISTON_CTE = Quantity.parse("23e-6 /K")  # aluminium
BORE_CTE = Quantity.parse("11e-6 /K")  # cast iron
TEMPERATURE_RISE = Quantity.parse("150 K")
MINIMUM_FILM = Quantity.parse("0.02 mm")

TIGHT_COLD_CLEARANCE = Quantity.parse("0.10 mm")
OPENED_COLD_CLEARANCE = Quantity.parse("0.20 mm")


def _thermal_closure() -> float:
    """The diametral clearance lost to differential expansion (mm), piston minus bore."""
    piston_growth = free_thermal_expansion(
        length=PISTON_DIAMETER,
        thermal_expansion_coefficient=PISTON_CTE,
        temperature_change=TEMPERATURE_RISE,
    )
    bore_growth = free_thermal_expansion(
        length=PISTON_DIAMETER,
        thermal_expansion_coefficient=BORE_CTE,
        temperature_change=TEMPERATURE_RISE,
    )
    return piston_growth.to("mm").magnitude - bore_growth.to("mm").magnitude


def _screen(cold_clearance: Quantity) -> Scorecard:
    # The cold clearance must cover the thermal closure and still leave a film.
    required_cold = _thermal_closure() + MINIMUM_FILM.to("mm").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "hot running clearance (seizure)",
                computed=cold_clearance.to("mm").magnitude / required_cold,
                required=1.0,
            ),
        )
    )


def screen_clearance() -> Scorecard:
    """Screen the 0.10 mm cold fit: fine cold, but it seizes hot."""
    return _screen(TIGHT_COLD_CLEARANCE)


def screen_opened_clearance() -> Scorecard:
    """Screen the 0.20 mm cold fit: enough to survive the thermal closure with a film."""
    return _screen(OPENED_COLD_CLEARANCE)


def main() -> None:
    print(f"thermal closure at temperature: {_thermal_closure():.3f} mm")
    print("tight cold fit (0.10 mm):")
    print(screen_clearance())
    print("\nopened cold fit (0.20 mm):")
    print(screen_opened_clearance())


if __name__ == "__main__":
    main()
