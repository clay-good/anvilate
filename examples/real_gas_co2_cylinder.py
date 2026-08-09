"""Worked example: how far a high-pressure CO₂ cylinder strays from the ideal-gas law.

Ideal-gas sizing is fine for air at room conditions, but a CO₂ cylinder at 60 bar sits near enough
to condensation that PV = nRT is noticeably off. This example makes it concrete for CO₂ at 60 bar
and 300 K by asking a simple question: if you fill a mole into the volume the ideal law predicts for
60 bar, what pressure does the Van der Waals equation say it actually reaches?

The answer is about 46 bar, not 60 — the intermolecular attraction the ideal law ignores pulls the
pressure down. The compressibility factor at that state is Z ≈ 0.76 (well below 1), a direct measure
of how far the gas has strayed from ideal; the real molar volume it implies follows from
v̄ = Z·R·T/P. (Finding the true molar volume at exactly 60 bar means solving the Van der Waals cubic,
which is iterative rather than closed-form — this example stays with the one-step illustration.)

Run it directly (``python examples/real_gas_co2_cylinder.py``);
:func:`co2_deviation` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    compressibility_factor,
    real_gas_molar_volume,
    van_der_waals_pressure,
)
from anvilate.units import Quantity

PRESSURE = Quantity.parse("60 bar")
TEMPERATURE = Quantity.parse("300 K")
# Van der Waals constants for CO2.
COHESION_A = Quantity.parse("0.3640 Pa*m**6/mol**2")
COVOLUME_B = Quantity.parse("4.267e-5 m**3/mol")
_R = 8.314462618  # J/(mol*K)


def co2_deviation() -> dict[str, float]:
    """Return the ideal and Van der Waals pressures (bar) at the ideal molar volume, and Z."""
    # The ideal-gas molar volume at 60 bar, 300 K.
    v_ideal = _R * 300.0 / PRESSURE.to("Pa").magnitude  # m^3/mol
    v_ideal_q = Quantity(magnitude=v_ideal, unit="m**3/mol")
    # Van der Waals pressure at that same molar volume — below the ideal RT/v.
    p_vdw = van_der_waals_pressure(
        temperature=TEMPERATURE,
        molar_volume=v_ideal_q,
        cohesion_a=COHESION_A,
        covolume_b=COVOLUME_B,
    )
    # Compressibility factor from the Van der Waals pressure at the ideal volume.
    z = compressibility_factor(pressure=p_vdw, molar_volume=v_ideal_q, temperature=TEMPERATURE)
    # The real molar volume that Z implies at the *original* 60 bar — smaller than ideal (Z < 1).
    v_real = real_gas_molar_volume(
        pressure=PRESSURE, temperature=TEMPERATURE, compressibility_factor=z
    )
    return {
        "ideal_pressure_bar": PRESSURE.to("bar").magnitude,
        "vdw_pressure_bar": p_vdw.to("bar").magnitude,
        "compressibility_factor": z,
        "real_molar_volume_l_mol": v_real.to("L/mol").magnitude,
        "ideal_molar_volume_l_mol": v_ideal_q.to("L/mol").magnitude,
    }


def main() -> None:
    d = co2_deviation()
    print("CO2 at 60 bar, 300 K (ideal molar volume):")
    print(f"  ideal pressure       : {d['ideal_pressure_bar']:.1f} bar")
    print(f"  Van der Waals P       : {d['vdw_pressure_bar']:.1f} bar (attraction pulls it down)")
    print(f"  compressibility Z     : {d['compressibility_factor']:.3f} (< 1: denser than ideal)")


if __name__ == "__main__":
    main()
