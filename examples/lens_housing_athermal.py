"""Worked example: one lens, three housings, 40 K of temperature swing.

A 100 mm f/4 crown-glass singlet images at 550 nm onto a detector 100 mm behind it. Its
depth of focus is ±2·λ·N² = ±17.6 µm. Warm it by 40 K and the lens's own focal length grows
16.0 µm: the glass expands, and its rising index pulls the other way, less strongly.

Whether the image stays sharp depends on what the housing does over the same 40 K:

- aluminium (23.1 ppm/K) carries the detector 92.4 µm back, and the image lands 76.4 µm
  short of it — more than four times the depth of focus. It fails.
- titanium (8.6 ppm/K) carries it 34.4 µm, 18.4 µm too far: just outside, and it fails too.
- Invar (1.2 ppm/K) carries it 4.8 µm, leaving 11.2 µm of defocus inside the ±17.6 µm band.

The glass values are this example's statement, not a library table: dn/dT depends on the
wavelength, the temperature range and whether it is quoted relative to air, and the caller is
the one who knows which.

Run it directly (``python examples/lens_housing_athermal.py``);
:func:`screen_housings` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.optomechanics import athermal_focus_scorecard
from anvilate.scorecard import ScorecardEntry
from anvilate.units import Quantity

HOUSINGS = {
    "aluminium 6061": "23.1e-6 1/K",
    "titanium Ti-6Al-4V": "8.6e-6 1/K",
    "Invar 36": "1.2e-6 1/K",
}


def screen_housings() -> dict[str, ScorecardEntry]:
    """The singlet's focus across 40 K, in each housing."""
    return {
        housing: athermal_focus_scorecard(
            f"focus in {housing}",
            focal_length=Quantity.parse("100 mm"),
            f_number=4.0,
            wavelength=Quantity.parse("550 nm"),
            refractive_index=1.5168,
            dn_dt=Quantity.parse("1.6e-6 1/K"),
            glass_cte=Quantity.parse("7.1e-6 1/K"),
            housing_cte=Quantity.parse(cte),
            housing_length=Quantity.parse("100 mm"),
            temperature_change=Quantity.parse("40 K"),
        )
        for housing, cte in HOUSINGS.items()
    }


def main() -> None:
    for entry in screen_housings().values():
        print(entry)
        if entry.derivation is not None:
            print(f"    {entry.derivation.substituted()}")


if __name__ == "__main__":
    main()
