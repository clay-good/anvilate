"""Worked example: hitting a dry-film spec and estimating paint for a coating job.

A protective-coating spec calls for a 125 µm dry film of a two-pack epoxy whose data sheet lists
60% volume solids. The applicator needs to know the wet-film reading to target during spraying, and
the estimator needs the paint quantity to order for a 400 m² tank.

To leave 125 µm dry at 60% solids the wet film must be 208 µm — the reading a wet-film comb should
show right after each pass. The theoretical coverage is 4.8 m²/L, so 400 m² would take 83 L of
paint with perfect transfer; in practice a loss factor for overspray and the blasted surface profile
pushes the order higher, but the theoretical figure anchors the take-off.

Run it directly (``python examples/coating_spec_wet_film_and_coverage.py``);
:func:`coating_spec` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    coating_theoretical_coverage,
    coating_wet_film_thickness,
)
from anvilate.units import Quantity

TARGET_DRY_FILM = Quantity.parse("125 um")
VOLUME_SOLIDS = 0.60
AREA_TO_COAT = Quantity.parse("400 m**2")


def coating_spec() -> dict[str, float]:
    """Return the wet film to apply (µm), the coverage (m²/L), and the paint for the area (L)."""
    wft = coating_wet_film_thickness(
        dry_film_thickness=TARGET_DRY_FILM, volume_solids_fraction=VOLUME_SOLIDS
    )
    coverage = coating_theoretical_coverage(
        volume_solids_fraction=VOLUME_SOLIDS, dry_film_thickness=TARGET_DRY_FILM
    )
    coverage_m2_per_l = coverage.to("m**2/L").magnitude
    paint_litres = AREA_TO_COAT.to("m**2").magnitude / coverage_m2_per_l
    return {
        "wet_film_um": wft.to("um").magnitude,
        "coverage_m2_per_L": coverage_m2_per_l,
        "paint_litres": paint_litres,
    }


def main() -> None:
    d = coating_spec()
    print("Epoxy coating spec, 125 um DFT at 60% volume solids:")
    print(f"  wet film to apply   : {d['wet_film_um']:.0f} um")
    print(f"  theoretical coverage: {d['coverage_m2_per_L']:.1f} m^2/L")
    print(f"  paint for 400 m^2   : {d['paint_litres']:.0f} L (theoretical, before losses)")


if __name__ == "__main__":
    main()
