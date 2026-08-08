"""Worked example: measuring a concentration by colorimetry (Beer-Lambert).

A spectrophotometer measures concentration indirectly: it shines light through a sample, reads how
much is absorbed, and converts that absorbance to concentration through the Beer-Lambert law. This
example runs the chain forward — predicting the absorbance and transmittance of a known sample, so
an instrument's range can be checked — and backward — recovering a concentration from a measured
absorbance, which is what an assay actually does.

The absorber has a molar absorptivity of 6000 L/(mol·cm) at the measurement wavelength, in a
standard 1 cm cell. A 1e-4 mol/L (0.1 mM) sample gives an absorbance of 0.6, meaning it passes about
25% of the light. Reading it the other way, an absorbance of 0.6 through the same cell recovers the
1e-4 mol/L concentration — the calibration an assay relies on. The example reports the absorbance
and transmittance of the known sample and the concentration recovered from the absorbance.

Run it directly (``python examples/colorimetry_concentration.py``);
:func:`assay_sample` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    absorbance,
    concentration_from_absorbance,
    transmittance_from_absorbance,
)
from anvilate.units import Quantity

MOLAR_ABSORPTIVITY = Quantity(magnitude=6000.0, unit="L/(mol*cm)")
CONCENTRATION = Quantity(magnitude=1e-4, unit="mol/L")
PATH_LENGTH = Quantity.parse("1 cm")


def assay_sample() -> dict[str, float]:
    """Return the absorbance and transmittance of the sample and the concentration recovered."""
    a = absorbance(
        molar_absorptivity=MOLAR_ABSORPTIVITY,
        concentration=CONCENTRATION,
        path_length=PATH_LENGTH,
    )
    t = transmittance_from_absorbance(absorbance=a)
    c = concentration_from_absorbance(
        absorbance=a, molar_absorptivity=MOLAR_ABSORPTIVITY, path_length=PATH_LENGTH
    )
    return {
        "absorbance": a,
        "transmittance_percent": t * 100.0,
        "recovered_concentration_mol_l": c.to("mol/L").magnitude,
    }


def main() -> None:
    d = assay_sample()
    print(f"absorbance: {d['absorbance']:.2f}")
    print(f"transmittance: {d['transmittance_percent']:.0f}%")
    print(f"concentration recovered: {d['recovered_concentration_mol_l']:.2e} mol/L")


if __name__ == "__main__":
    main()
