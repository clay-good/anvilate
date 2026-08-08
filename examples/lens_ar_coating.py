"""Worked example: designing a single-layer anti-reflection coating for a camera lens.

A camera lens loses light and gains glare at every glass-air surface unless it is coated. A single
quarter-wave layer cancels the reflection at one wavelength by interference. Designing it answers
three questions: what index the coating should ideally have, how thick to make it for the target
color, and — since the coating is tuned to one wavelength — what color it is optimized for.

The lens glass has a refractive index of 1.52. The ideal coating index is the geometric mean with
air, about 1.23; real coatings use magnesium fluoride at 1.38 as the closest practical material.
For best performance at green light (550 nm, mid-spectrum), an MgF2 coating must be a quarter-wave,
about 100 nm. Confirming the design, a 100 nm MgF2 layer is tuned to about 550 nm — green — which is
why AR-coated lenses leave a faint purple (red+blue) residual reflection. The example reports the
ideal coating index, the MgF2 thickness for green, and the wavelength that thickness is tuned to.

Run it directly (``python examples/lens_ar_coating.py``);
:func:`ar_coating_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    optimal_ar_coating_index,
    quarter_wave_thickness,
    thin_film_tuned_wavelength,
)
from anvilate.units import Quantity

GLASS_INDEX = 1.52
MGF2_INDEX = 1.38
GREEN_WAVELENGTH = Quantity.parse("550 nm")


def ar_coating_design() -> dict[str, float]:
    """Return the ideal coating index, the MgF2 thickness for green, and its tuned wavelength."""
    ideal_index = optimal_ar_coating_index(substrate_index=GLASS_INDEX)
    thickness = quarter_wave_thickness(wavelength=GREEN_WAVELENGTH, coating_index=MGF2_INDEX)
    tuned = thin_film_tuned_wavelength(thickness=thickness, coating_index=MGF2_INDEX)
    return {
        "ideal_coating_index": ideal_index,
        "mgf2_thickness_nm": thickness.to("nm").magnitude,
        "tuned_wavelength_nm": tuned.to("nm").magnitude,
    }


def main() -> None:
    d = ar_coating_design()
    print(f"ideal coating index for glass: {d['ideal_coating_index']:.2f}")
    print(f"MgF2 thickness for green: {d['mgf2_thickness_nm']:.0f} nm")
    print(f"wavelength that thickness is tuned to: {d['tuned_wavelength_nm']:.0f} nm")


if __name__ == "__main__":
    main()
