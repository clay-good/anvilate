"""Worked example: the office floor that is strong enough and still feels wrong.

A long-span steel floor can pass every strength and deflection check and still be a problem, because
the load nobody puts on a calculator is a person walking. AISC/CISC Design Guide 11 turns that into
a number: the walking-induced peak acceleration as a fraction of gravity,
a_p/g = P₀·e^(−0.35·fₙ)/(β·W), checked against a comfort limit of about 0.5% g for an office.

This example compares two floor bays carrying the same load. The first is a light, springy long-span
bay: a 4.5 Hz fundamental frequency, 220 kN of effective panel weight, and only 2% bare-steel
damping. It is plenty strong, but its acceleration ratio comes out around 1.4% g — well over the
limit, the floor that makes coffee ripple when someone walks past. The second bay is stiffer and
heavier (5.5 Hz, 320 kN) and carries fit-out that lifts the damping to 3.5%; its ratio drops to
about 0.4% g, comfortably acceptable. Neither bay is weak — the difference is entirely in frequency,
mass, and damping, the three levers Design Guide 11 gives you. The lesson is that on a modern
long-span floor the governing limit is often not strength at all but the wobble a footstep sets off.

Run it directly (``python examples/office_floor_vibration.py``);
:func:`floor_ratios` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import floor_vibration_peak_acceleration_ratio
from anvilate.units import Quantity

OFFICE_WALKING_FORCE = Quantity.parse("0.29 kN")  # DG11 P0 for offices/residences
COMFORT_LIMIT = 0.005  # ~0.5% g for offices


def floor_ratios() -> dict[str, float]:
    """Return the walking-vibration acceleration ratio of a springy and a stiff floor bay."""
    springy = floor_vibration_peak_acceleration_ratio(
        fundamental_frequency=Quantity.parse("4.5 Hz"),
        effective_panel_weight=Quantity.parse("220 kN"),
        damping_ratio=0.02,
        constant_force=OFFICE_WALKING_FORCE,
    )
    stiff = floor_vibration_peak_acceleration_ratio(
        fundamental_frequency=Quantity.parse("5.5 Hz"),
        effective_panel_weight=Quantity.parse("320 kN"),
        damping_ratio=0.035,
        constant_force=OFFICE_WALKING_FORCE,
    )
    return {"springy_ratio": springy, "stiff_ratio": stiff}


def main() -> None:
    r = floor_ratios()
    springy_ok = "OK" if r["springy_ratio"] <= COMFORT_LIMIT else "FAIL"
    stiff_ok = "OK" if r["stiff_ratio"] <= COMFORT_LIMIT else "FAIL"
    print(f"comfort limit : {COMFORT_LIMIT * 100:.1f}% g")
    print(f"springy bay (4.5 Hz, 2.0% damping) : {r['springy_ratio'] * 100:.2f}% g ({springy_ok})")
    print(f"stiff bay   (5.5 Hz, 3.5% damping) : {r['stiff_ratio'] * 100:.2f}% g ({stiff_ok})")
    print("  -> both bays are strong; only the springy one fails, on vibration, not strength")


if __name__ == "__main__":
    main()
