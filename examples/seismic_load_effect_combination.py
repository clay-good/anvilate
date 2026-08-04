"""Worked example: assembling the earthquake force the load combinations actually want.

The seismic force that goes into a strength combination is not the number a lateral analysis prints.
ASCE 7 wraps that horizontal result Q_E in two adjustments before it is combined with gravity: a
redundancy factor ρ that penalizes systems with few lateral-load paths (1.0 or 1.3), and a vertical
earthquake term 0.2·SDS·D that shakes the dead load up and down. The combined effect is
E = ρ·Q_E ± 0.2·SDS·D, and the sign matters — the vertical part *adds* to gravity in the downward
combinations and *relieves* it in the uplift ones.

This example takes a column whose lateral analysis gives a 90 kN axial from the earthquake, on a
non-redundant frame (ρ = 1.3) at a stiff site (SDS = 1.1), carrying 260 kN dead and 150 kN live. It
builds the additive seismic effect — ρ·Q_E plus the vertical term — and runs the governing LRFD
combination, then does it again with the bare, unadjusted 90 kN to show what skipping the ρ and
vertical adjustments would cost. The adjusted effect nearly doubles the raw one, and it carries
straight into a larger factored demand. The lesson is that the seismic load effect is a small
assembly step with a large consequence: ρ and the vertical earthquake are not optional trimmings,
and the combination is only as right as the E you feed it.

Run it directly (``python examples/seismic_load_effect_combination.py``);
:func:`seismic_demand` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import asce7_lrfd_factored_load, seismic_load_effect
from anvilate.units import Quantity

HORIZONTAL_SEISMIC = Quantity.parse("90 kN")  # Q_E from the lateral analysis
DEAD = Quantity.parse("260 kN")
LIVE = Quantity.parse("150 kN")
REDUNDANCY_FACTOR = 1.3
DESIGN_SPECTRAL_ACCELERATION = 1.1  # SDS


def seismic_demand() -> dict[str, float]:
    """Return the assembled E and the LRFD demand, versus using the raw horizontal force."""
    e = seismic_load_effect(
        horizontal_effect=HORIZONTAL_SEISMIC,
        dead_load_effect=DEAD,
        design_spectral_acceleration=DESIGN_SPECTRAL_ACCELERATION,
        redundancy_factor=REDUNDANCY_FACTOR,
    )
    demand_adjusted = asce7_lrfd_factored_load(dead=DEAD, live=LIVE, seismic=e)
    demand_raw = asce7_lrfd_factored_load(dead=DEAD, live=LIVE, seismic=HORIZONTAL_SEISMIC)
    return {
        "raw_qe_kn": HORIZONTAL_SEISMIC.to("kN").magnitude,
        "assembled_e_kn": e.to("kN").magnitude,
        "demand_adjusted_kn": demand_adjusted.to("kN").magnitude,
        "demand_raw_kn": demand_raw.to("kN").magnitude,
    }


def main() -> None:
    d = seismic_demand()
    grew = (d["assembled_e_kn"] / d["raw_qe_kn"] - 1.0) * 100.0
    print(f"raw horizontal Q_E : {d['raw_qe_kn']:.0f} kN")
    print(f"assembled E (rho*Q_E + 0.2*SDS*D) : {d['assembled_e_kn']:.0f} kN ({grew:.0f}% larger)")
    print(f"LRFD demand with assembled E : {d['demand_adjusted_kn']:.0f} kN")
    print(f"LRFD demand with raw Q_E     : {d['demand_raw_kn']:.0f} kN (unconservative)")
    print("  -> rho and the vertical earthquake are part of E, not optional trimmings")


if __name__ == "__main__":
    main()
