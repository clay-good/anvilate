"""Worked example: reading temperature from color, and why hot metal glows red then white.

A blackbody radiates most strongly at a wavelength that shifts inversely with its temperature —
Wien's displacement law, λ_max = b/T. This example runs it forward for a piece of steel heated
through the range a blacksmith knows by eye: at 800 K the peak sits deep in the infrared and the
steel only just shows a dull red; by 1500 K the peak has marched up toward the visible and it glows
bright orange; and the Sun's ≈ 5800 K surface peaks in green at about 500 nm, which reads to the eye
as brilliant white. The example then runs the law backwards, the way a spectral pyrometer works:
hand it the peak wavelength a hot object radiates and Wien's law returns its temperature without any
contact — the only way to take the temperature of a furnace interior, a filament, or a star.

Run it directly (``python examples/pyrometer_color_temperature.py``);
:func:`glow_colors` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import wien_peak_wavelength, wien_temperature_from_peak
from anvilate.units import Quantity


def glow_colors() -> dict[str, float]:
    """Return the peak wavelength (nm) at several temperatures and a pyrometer's inferred T (K)."""
    peaks = {
        f"peak_nm_{t}K": wien_peak_wavelength(temperature=Quantity(magnitude=t, unit="K"))
        .to("nm")
        .magnitude
        for t in (800, 1500, 5800)
    }
    inferred = wien_temperature_from_peak(peak_wavelength=Quantity.parse("500 nm"))
    peaks["inferred_T_from_500nm"] = inferred.to("K").magnitude
    return peaks


def main() -> None:
    g = glow_colors()
    print(f"800 K steel  : peak {g['peak_nm_800K']:.0f} nm (deep infrared — dull red glow)")
    print(f"1500 K steel : peak {g['peak_nm_1500K']:.0f} nm (near infrared — bright orange)")
    print(f"5800 K Sun   : peak {g['peak_nm_5800K']:.0f} nm (green — reads as white)")
    print(
        f"pyrometer: a 500 nm peak -> {g['inferred_T_from_500nm']:.0f} K (contactless temperature)"
    )
    print(
        "  -> the peak marches out of the infrared as things heat; a pyrometer reads it backwards"
    )


if __name__ == "__main__":
    main()
