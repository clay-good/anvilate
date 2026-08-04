"""Worked example: the energy in a drive's DC-link capacitor, and where its filter rings.

A variable-frequency motor drive stores energy in a DC-link capacitor to smooth the bus, and that
stored energy is both a design target and a hazard. This example takes a 1500 µF bank charged to the
650 V DC bus of a typical three-phase drive and finds the energy it holds — over 300 J, enough to be
dangerous long after the drive is switched off, which is why the bleed-down time matters for service
safety. It then pairs the bus capacitor with the 2 mH line-filter inductor and finds the LC resonant
frequency of that filter — around 90 hertz, well below the switching frequency it is meant to
attenuate but a ring the drive's control must not excite. Reactive components do not burn energy;
they store it and trade it, and both the storing and the trading have to be designed for.

Run it directly (``python examples/dc_link_capacitor_energy.py``);
:func:`dc_link_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import capacitor_stored_energy, lc_resonant_frequency
from anvilate.units import Quantity

DC_LINK_CAPACITANCE = Quantity.parse("1500 uF")
BUS_VOLTAGE = Quantity.parse("650 V")
FILTER_INDUCTANCE = Quantity.parse("2 mH")


def dc_link_design() -> dict[str, float]:
    """Return the DC-link stored energy (J) and the LC filter resonant frequency (Hz)."""
    energy = capacitor_stored_energy(capacitance=DC_LINK_CAPACITANCE, voltage=BUS_VOLTAGE)
    resonance = lc_resonant_frequency(inductance=FILTER_INDUCTANCE, capacitance=DC_LINK_CAPACITANCE)
    return {
        "stored_energy_j": energy.to("J").magnitude,
        "resonant_frequency_hz": resonance.to("Hz").magnitude,
    }


def main() -> None:
    d = dc_link_design()
    print(
        f"DC-link stored energy   : {d['stored_energy_j']:.0f} J (a shock hazard after power-off)"
    )
    print(f"LC filter resonance     : {d['resonant_frequency_hz']:.0f} Hz")
    print("  -> reactive parts store and trade energy; size the bleed-down and avoid the resonance")


if __name__ == "__main__":
    main()
