"""Worked example: the seismic drift check that passes only if you forget to amplify it.

A seismic analysis is run with the design forces — the base shear already cut down by the system's
response modification factor R — so the story sways it reports are small. The trap is to check those
small elastic drifts straight against the limit. ASCE 7 does not let you: because the structure is
expected to yield and sway much further than the reduced-force analysis shows, the elastic drift is
amplified by the deflection factor Cd (close to R) before it is checked, Δ = Cd·δxe/Ie.

This example takes one story of a special moment frame — 4 m tall, Cd = 5.5 — whose elastic analysis
under the design earthquake reports a 12 mm drift. Checked raw, 12 mm is far inside the 80 mm limit
(0.020·h), and the frame looks fine. Amplified, the real expected drift is 5.5 × 12 = 66 mm — still
under 80 mm, but now the margin is thin, not comfortable, and a slightly softer frame would fail
outright. The lesson is that the Cd amplification is not optional bookkeeping: it is a factor-of-Cd
difference between the drift the analysis prints and the drift the building will actually see, and
skipping it turns a marginal frame into a false pass.

Run it directly (``python examples/seismic_story_drift_check.py``);
:func:`drift_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import allowable_story_drift, seismic_design_story_drift
from anvilate.units import Quantity

ELASTIC_DRIFT = Quantity.parse("12 mm")  # from the reduced-force seismic analysis
DEFLECTION_AMPLIFICATION = 5.5  # Cd, special moment frame
STORY_HEIGHT = Quantity.parse("4 m")
DRIFT_LIMIT_RATIO = 0.020  # ASCE 7 Table 12.12-1, typical building


def drift_check() -> dict[str, float]:
    """Return the raw and Cd-amplified drifts and the allowable, all in mm."""
    amplified = seismic_design_story_drift(
        elastic_story_drift=ELASTIC_DRIFT,
        deflection_amplification_factor=DEFLECTION_AMPLIFICATION,
    )
    allowable = allowable_story_drift(
        story_height=STORY_HEIGHT, drift_limit_ratio=DRIFT_LIMIT_RATIO
    )
    return {
        "elastic_mm": ELASTIC_DRIFT.to("mm").magnitude,
        "amplified_mm": amplified.to("mm").magnitude,
        "allowable_mm": allowable.to("mm").magnitude,
    }


def main() -> None:
    d = drift_check()
    print(f"allowable drift : {d['allowable_mm']:.0f} mm (0.020 x 4 m)")
    print(f"raw elastic drift : {d['elastic_mm']:.0f} mm (looks comfortable, but wrong)")
    print(f"Cd-amplified drift : {d['amplified_mm']:.0f} mm (the real expected sway)")
    margin = d["allowable_mm"] / d["amplified_mm"]
    print(
        f"  -> the check is on the amplified drift (safety factor {margin:.2f}), not the raw 12 mm"
    )


if __name__ == "__main__":
    main()
