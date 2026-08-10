"""Worked example: water flux and permeate quality of a seawater RO membrane.

A seawater reverse-osmosis membrane with a water permeability of 1 L/(m²·h·bar) runs at 60 bar
against seawater whose osmotic pressure is about 28 bar. Its salt permeability is 5e-7 m/s and the
feed holds 35 kg/m³ of salt. How much fresh water does a square metre make, and how salty is it?

Only the net driving pressure counts: 60 − 28 = 32 bar, so the water flux is 1 × 32 = 32 L/(m²·h).
The salt flux (B·ΔC) is largely pressure-independent, so it sets a permeate concentration of
C_p = J_s/J_w ≈ 1.97 kg/m³ — against the 35 kg/m³ feed that is a salt rejection of about 94%. A real
seawater membrane rejects ~99.5%; this illustrative B is deliberately leaky to show the trade-off.

Run it directly (``python examples/reverse_osmosis_seawater_flux.py``);
:func:`seawater_ro_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    membrane_salt_flux,
    reverse_osmosis_water_flux,
    salt_rejection,
)
from anvilate.units import Quantity

WATER_PERMEABILITY = Quantity.parse("1 L/(m**2*hour*bar)")
APPLIED_PRESSURE = Quantity.parse("60 bar")
OSMOTIC_PRESSURE = Quantity.parse("28 bar")
SALT_PERMEABILITY = Quantity.parse("5e-7 m/s")
FEED_CONCENTRATION = Quantity.parse("35 kg/m**3")


def seawater_ro_performance() -> dict[str, float]:
    """Return the water flux (LMH), permeate concentration (kg/m³), and salt rejection."""
    j_w = reverse_osmosis_water_flux(
        water_permeability=WATER_PERMEABILITY,
        applied_pressure=APPLIED_PRESSURE,
        osmotic_pressure_difference=OSMOTIC_PRESSURE,
    )
    j_s = membrane_salt_flux(
        salt_permeability=SALT_PERMEABILITY, concentration_difference=FEED_CONCENTRATION
    )
    # Permeate concentration is the salt flux carried by the water flux, C_p = J_s / J_w.
    c_p = j_s.to("kg/(m**2*s)").magnitude / j_w.to("m/s").magnitude  # kg/m^3
    c_p_q = Quantity(magnitude=c_p, unit="kg/m**3")
    rejection = salt_rejection(permeate_concentration=c_p_q, feed_concentration=FEED_CONCENTRATION)
    return {
        "water_flux_lmh": j_w.to("L/(m**2*hour)").magnitude,
        "permeate_concentration_kg_m3": c_p,
        "salt_rejection": rejection,
    }


def main() -> None:
    d = seawater_ro_performance()
    print("Seawater RO at 60 bar (osmotic 28 bar):")
    print(f"  water flux            : {d['water_flux_lmh']:.1f} L/(m2 h)")
    print(f"  permeate salinity     : {d['permeate_concentration_kg_m3']:.2f} kg/m3")
    print(f"  salt rejection        : {d['salt_rejection'] * 100:.1f} %")


if __name__ == "__main__":
    main()
