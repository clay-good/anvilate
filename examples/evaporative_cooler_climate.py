"""Worked example: why a swamp cooler is magic in Phoenix and useless in Miami.

A direct evaporative cooler chills air by evaporating water into it, and the coldest it can possibly
reach is the entering wet-bulb temperature — the point where the air is saturated. How close a real
cooler gets is its saturation effectiveness, ε = (t_db_in − t_db_out)/(t_db_in − t_wb_in), a trait
of the cooler's media (0.8–0.9 for good rigid pads). But the *cooling delivered* depends on the
climate, because it is ε times the wet-bulb depression, and that depression is huge in dry heat and
nearly zero in humid heat.

This example runs the same 85%-effective cooler in two summers. In the desert the air enters at a
brutal 40 °C but a dry 20 °C wet-bulb, a 20-degree depression; the cooler delivers 0.85 × 20 = 17 °C
of cooling and leaves the air at a pleasant 23 °C. In the humid Gulf the air enters cooler, 33 °C,
but its wet-bulb is a sticky 28 °C — only a 5-degree depression — so the same cooler manages just
0.85 × 5 ≈ 4 °C and leaves the air at a clammy 29 °C. Same machine, same effectiveness; the climate
decides. The lesson is that evaporative cooling is not rated by a single number — the effectiveness
is fixed by the cooler, but the comfort it buys is set by how dry the incoming air is.

Run it directly (``python examples/evaporative_cooler_climate.py``);
:func:`cooler_climates` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import evaporative_cooler_effectiveness
from anvilate.units import Quantity

EFFECTIVENESS = 0.85


def _leaving(entering_db: float, entering_wb: float) -> float:
    """Leaving dry-bulb (deg C) for a cooler of the fixed effectiveness at this climate."""
    return entering_db - EFFECTIVENESS * (entering_db - entering_wb)


def cooler_climates() -> dict[str, float]:
    """Return the leaving temperature and effectiveness for a dry and a humid climate."""

    def climate(db: float, wb: float) -> dict[str, float]:
        leaving = _leaving(db, wb)
        eff = evaporative_cooler_effectiveness(
            entering_dry_bulb=Quantity(magnitude=db, unit="degC"),
            leaving_dry_bulb=Quantity(magnitude=leaving, unit="degC"),
            entering_wet_bulb=Quantity(magnitude=wb, unit="degC"),
        )
        return {"leaving_c": leaving, "effectiveness": eff}

    desert = climate(40.0, 20.0)
    humid = climate(33.0, 28.0)
    return {
        "desert_leaving_c": desert["leaving_c"],
        "desert_effectiveness": desert["effectiveness"],
        "humid_leaving_c": humid["leaving_c"],
        "humid_effectiveness": humid["effectiveness"],
    }


def main() -> None:
    c = cooler_climates()
    de = c["desert_effectiveness"]
    he = c["humid_effectiveness"]
    print(f"desert (40/20 C db/wb) : leaves {c['desert_leaving_c']:.1f} C (eff {de:.2f})")
    print(f"humid  (33/28 C db/wb) : leaves {c['humid_leaving_c']:.1f} C (eff {he:.2f})")
    print("  -> same cooler, same effectiveness; the wet-bulb depression decides the comfort")


if __name__ == "__main__":
    main()
