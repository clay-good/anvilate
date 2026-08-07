"""Worked example: why EDM roughs and finishes on the same machine — energy per spark trades off.

Electrical discharge machining erodes metal one spark at a time, and the size of each spark is the
whole story. A big spark — high current, long pulse — melts a large crater and clears metal fast,
but that crater is also the surface it leaves and the gap it opens, so a fast cut is a rough one. A
small spark leaves a fine finish but barely removes anything. There is no single best setting; the
operator picks a setting per stage, roughing on high energy to hog out the bulk and finishing on low
energy to bring the surface in. The removal rate follows the average current, while the surface
finish follows the energy in each individual pulse — two knobs pulling against each other.

This example contrasts a roughing pulse (25 V gap, 20 A peak, 100 µs on, 100 µs off) with a
finishing pulse (25 V, 4 A, 10 µs on, 50 µs off) eroding steel of coefficient 2 mm³/(min·A).
Roughing dumps
50 mJ per spark at a 50% duty factor and clears about 20 mm³/min. Finishing drops the pulse to just
1 mJ — one-fiftieth the crater — but its low current and short on-time cut the duty factor to about
17% and the removal rate to roughly 1.3 mm³/min. The example reports the discharge energy, duty
factor, and removal rate for both, so the fifty-fold swing in per-spark energy that buys the finish,
and the fifteen-fold drop in speed it costs, are explicit side by side.

Run it directly (``python examples/edm_roughing_vs_finishing.py``);
:func:`edm_settings` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    edm_discharge_energy,
    edm_duty_factor,
    edm_material_removal_rate,
)
from anvilate.units import Quantity

GAP_VOLTAGE = Quantity.parse("25 V")
EROSION_COEFFICIENT = Quantity.parse("2 mm**3/(min*A)")


def _stage(peak_current: str, on_time: str, off_time: str) -> dict[str, float]:
    current = Quantity.parse(peak_current)
    energy = edm_discharge_energy(
        gap_voltage=GAP_VOLTAGE,
        peak_current=current,
        pulse_on_time=Quantity.parse(on_time),
    )
    duty = edm_duty_factor(
        pulse_on_time=Quantity.parse(on_time), pulse_off_time=Quantity.parse(off_time)
    )
    mrr = edm_material_removal_rate(
        erosion_coefficient=EROSION_COEFFICIENT, peak_current=current, duty_factor=duty
    )
    return {
        "energy_mj": energy.to("mJ").magnitude,
        "duty_factor": duty,
        "mrr_mm3_min": mrr.to("mm**3/min").magnitude,
    }


def edm_settings() -> dict[str, dict[str, float]]:
    """Return the discharge energy, duty factor, and removal rate for roughing and finishing."""
    return {
        "roughing": _stage("20 A", "100 us", "100 us"),
        "finishing": _stage("4 A", "10 us", "50 us"),
    }


def main() -> None:
    d = edm_settings()
    for name in ("roughing", "finishing"):
        s = d[name]
        print(
            f"{name:>9}: {s['energy_mj']:.2f} mJ/spark, duty {s['duty_factor']:.0%}, "
            f"MRR {s['mrr_mm3_min']:.2f} mm^3/min"
        )
    print("  -> big sparks cut fast and rough; small sparks finish fine and slow")


if __name__ == "__main__":
    main()
