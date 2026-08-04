"""Worked example: sizing a riser so the shrinkage cavity ends up in the scrap, not the casting.

Metal shrinks as it freezes, and if nothing feeds liquid into the casting to make up that shrinkage,
the last place to solidify is left with a void. A riser is a sacrificial reservoir of metal attached
to the casting for exactly this — but it only works if it stays liquid *longer* than the part it
feeds. Chvorinov's rule says freezing time goes as the square of the casting modulus M = V/A (volume
over cooling surface), so the riser wins that race only if its modulus is larger than the casting's.

This example takes a steel plate casting, 200 mm × 150 mm × 40 mm, poured in sand with a mould
constant of 2 min/cm². Its modulus works out to about 1.36 cm, which by Chvorinov gives a
solidification time of about 3.7 minutes. To feed it, the riser needs a modulus about 1.2 times as
large — roughly 1.64 cm — so it freezes last and draws the shrinkage into itself. A riser sized to
that modulus (a compact cylinder, whose own V/A must reach 1.64 cm) solidifies after the plate and
leaves the part sound; a skimpier riser freezes first, stops feeding, and the plate ends up with an
internal shrinkage cavity right where it was thickest. The example computes the casting's modulus,
its freezing time, and the riser modulus target, turning "add a riser" into the number it must hit.

Run it directly (``python examples/casting_riser_sizing.py``);
:func:`riser_sizing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    casting_modulus,
    chvorinov_solidification_time,
    riser_modulus_for_feeding,
)
from anvilate.units import Quantity

# A 200 x 150 x 40 mm plate: volume and total surface area.
LENGTH = 200.0  # mm
WIDTH = 150.0  # mm
THICKNESS = 40.0  # mm
VOLUME = Quantity(magnitude=LENGTH * WIDTH * THICKNESS, unit="mm**3")
SURFACE_AREA = Quantity(
    magnitude=2.0 * (LENGTH * WIDTH + LENGTH * THICKNESS + WIDTH * THICKNESS),
    unit="mm**2",
)
MOLD_CONSTANT = Quantity.parse("2 min/cm**2")  # steel in green sand


def riser_sizing() -> dict[str, float]:
    """Return the casting modulus, its Chvorinov freezing time, and the riser modulus target."""
    modulus = casting_modulus(volume=VOLUME, surface_area=SURFACE_AREA)
    freeze_time = chvorinov_solidification_time(modulus=modulus, mold_constant=MOLD_CONSTANT)
    riser_modulus = riser_modulus_for_feeding(casting_modulus=modulus)
    return {
        "casting_modulus_cm": modulus.to("cm").magnitude,
        "freeze_time_min": freeze_time.to("min").magnitude,
        "riser_modulus_cm": riser_modulus.to("cm").magnitude,
    }


def main() -> None:
    s = riser_sizing()
    print(f"casting modulus : {s['casting_modulus_cm']:.2f} cm")
    print(f"freezing time   : {s['freeze_time_min']:.1f} min (Chvorinov, t = B*M^2)")
    print(f"riser modulus   : {s['riser_modulus_cm']:.2f} cm target (1.2x, so it freezes last)")
    print("  -> size the riser to that modulus and the shrinkage cavity lands in the riser")


if __name__ == "__main__":
    main()
