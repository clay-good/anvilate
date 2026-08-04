"""Worked example: a worker's noise exposure declared once, screened into a dose scorecard.

The noise pack turns a hearing-conservation check into the reviewable pass/fail the rest of the
library produces: declare the sound levels a worker stands in and the length of the shift, and get
back a scorecard whose single entry combines the machine noise by energy, finds the permissible time
at that level, and reports the dose as PASS or FAIL against the exposure limit. This example takes a
worker beside two machines (92 and 90 dBA) over a 6-hour shift and screens the same exposure against
two standards: the OSHA permissible limit (90 dBA criterion, 5 dB exchange rate) and the stricter
NIOSH recommended limit (85 dBA, 3 dB). The combined level lands near 94 dBA, so both fail — but
NIOSH fails by far more, the gap the two exchange rates open up.

Run it directly (``python examples/worker_noise_dose_scorecard.py``);
:func:`exposure_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.noise_exposure import WorkerNoiseExposure, screen_noise_exposure
from anvilate.units import Quantity


def exposure_scorecards() -> dict[str, object]:
    """Return the OSHA and NIOSH scorecard status and dose for the same worker exposure."""
    worker = WorkerNoiseExposure(
        machine_levels=(92.0, 90.0),
        exposure_duration=Quantity.parse("6 hour"),
    )
    osha = screen_noise_exposure(worker)  # OSHA defaults: 90 dBA, 5 dB
    niosh = screen_noise_exposure(worker, criterion_level=85.0, exchange_rate=3.0)
    return {
        "osha_status": osha.status.value,
        "osha_dose_percent": 100.0 / osha.entries[0].safety_factor,
        "niosh_status": niosh.status.value,
        "niosh_dose_percent": 100.0 / niosh.entries[0].safety_factor,
    }


def main() -> None:
    r = exposure_scorecards()
    print(f"OSHA  (90 dBA, 5 dB): {r['osha_status'].upper()}  dose {r['osha_dose_percent']:.0f}%")
    print(f"NIOSH (85 dBA, 3 dB): {r['niosh_status'].upper()}  dose {r['niosh_dose_percent']:.0f}%")
    print("  -> same 6 h exposure; the tighter NIOSH criterion multiplies the dose")


if __name__ == "__main__":
    main()
