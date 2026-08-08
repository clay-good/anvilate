"""Worked example: the energy in a mass defect, and why iron sits at the bottom.

Mass and energy are the same thing scaled by c^2, and the astonishing energy of nuclear processes is
just the tiny mass lost when nucleons rearrange. This example makes that concrete two ways: the raw
energy locked in a gram of mass, and the binding energy per nucleon that decides whether a nucleus
releases energy by fusing or by fissioning.

A single gram of mass, fully converted, is worth about 90 terajoules — roughly the energy of 20
kilotons of TNT, which is why a nuclear reaction's mass defect of a fraction of a percent dwarfs any
chemical reaction. Turned around, a 200 MeV fission energy corresponds to a mass loss of only about
3.6e-28 kg. And uranium-235, with a total binding energy near 1784 MeV across its 235 nucleons, is
bound at about 7.6 MeV per nucleon — below iron's ~8.8 MeV peak, so it releases energy by fissioning
toward it. The example reports the gram-mass energy, the fission mass defect, and U-235's binding
energy per nucleon.

Run it directly (``python examples/nuclear_mass_energy.py``);
:func:`nuclear_energetics` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import binding_energy_per_nucleon, mass_energy, mass_from_energy
from anvilate.units import Quantity

ONE_GRAM = Quantity.parse("1 g")
FISSION_ENERGY = Quantity.parse("200 MeV")
U235_BINDING_ENERGY = Quantity(magnitude=1783.9, unit="MeV")
U235_NUCLEONS = 235


def nuclear_energetics() -> dict[str, float]:
    """Return the gram-mass energy (TJ), the fission mass defect (kg), and U-235 binding/nucleon."""
    gram_energy = mass_energy(mass=ONE_GRAM)
    fission_mass = mass_from_energy(energy=FISSION_ENERGY)
    be_per_nucleon = binding_energy_per_nucleon(
        binding_energy=U235_BINDING_ENERGY, nucleon_count=U235_NUCLEONS
    )
    return {
        "gram_mass_energy_tj": gram_energy.to("J").magnitude / 1e12,
        "fission_mass_defect_kg": fission_mass.to("kg").magnitude,
        "u235_binding_per_nucleon_mev": be_per_nucleon.to("MeV").magnitude,
    }


def main() -> None:
    d = nuclear_energetics()
    print(f"energy in 1 g of mass: {d['gram_mass_energy_tj']:.0f} TJ")
    print(f"mass defect of a 200 MeV fission: {d['fission_mass_defect_kg']:.2e} kg")
    print(f"U-235 binding energy per nucleon: {d['u235_binding_per_nucleon_mev']:.1f} MeV")


if __name__ == "__main__":
    main()
