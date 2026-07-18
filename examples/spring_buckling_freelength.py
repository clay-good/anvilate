"""Worked example: the spring that was strong enough but folded sideways.

A helical compression spring is squeezed 50 mm in service. Sizing the wire for
stress is the obvious job, but a tall, slender coil has a second way to fail that
has nothing to do with wire stress: like a loaded column, it can buckle sideways
and spit itself out of its bore. How soon depends almost entirely on how tall the
spring is relative to its coil diameter.

Three free lengths, same 25 mm coils, all squeezed the same 50 mm. The short
120 mm spring is squat enough to be absolutely stable — it cannot buckle at any
deflection up to solid. Stretch the free length to 150 mm and it becomes a column:
it now buckles, but only past 63 mm of deflection, so at 50 mm it is still safe
(1.26). Go to 180 mm and the critical deflection drops to 46 mm — below the 50 mm
the spring actually sees — so it buckles in service (0.92), even though its wire is
nowhere near overstressed.

A compression spring has a slenderness limit just like a column, set by the ratio
of free length to coil diameter. Past it, more free length does not buy a softer
spring — it buys a buckling failure. Guide a long spring in a bore or over a rod,
or keep it squat. The elastic moduli are material data, declared inline.

Run it directly (``python examples/spring_buckling_freelength.py``);
:func:`screen_spring_buckling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import helical_spring_buckling
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity

MEAN_COIL_DIAMETER = Quantity.parse("25 mm")
ELASTIC_MODULUS = Quantity.parse("207 GPa")
SHEAR_MODULUS = Quantity.parse("79 GPa")
OPERATING_DEFLECTION = Quantity.parse("50 mm")

FREE_LENGTHS = {
    "short (120 mm)": Quantity.parse("120 mm"),
    "medium (150 mm)": Quantity.parse("150 mm"),
    "tall (180 mm)": Quantity.parse("180 mm"),
}


def screen_spring_buckling() -> Scorecard:
    """Screen each free length: the operating deflection must stay below the
    lateral-buckling critical deflection (safety factor = critical / operating)."""
    operating = OPERATING_DEFLECTION.to("mm").magnitude
    entries = []
    for name, free_length in FREE_LENGTHS.items():
        result = helical_spring_buckling(
            free_length=free_length,
            mean_coil_diameter=MEAN_COIL_DIAMETER,
            elastic_modulus=ELASTIC_MODULUS,
            shear_modulus=SHEAR_MODULUS,
        )
        if result.absolutely_stable or result.critical_deflection is None:
            entries.append(
                ScorecardEntry(
                    name=name,
                    status=CheckStatus.PASS,
                    detail="absolutely stable — cannot buckle at any deflection",
                )
            )
        else:
            entries.append(
                ScorecardEntry.from_safety_factor(
                    name,
                    computed=result.critical_deflection.to("mm").magnitude / operating,
                    required=1.0,
                )
            )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, free_length in FREE_LENGTHS.items():
        result = helical_spring_buckling(
            free_length=free_length,
            mean_coil_diameter=MEAN_COIL_DIAMETER,
            elastic_modulus=ELASTIC_MODULUS,
            shear_modulus=SHEAR_MODULUS,
        )
        if result.critical_deflection is None:
            print(f"{name}: absolutely stable")
        else:
            print(f"{name}: buckles past {result.critical_deflection.to('mm').magnitude:.0f} mm")
    print(screen_spring_buckling())


if __name__ == "__main__":
    main()
