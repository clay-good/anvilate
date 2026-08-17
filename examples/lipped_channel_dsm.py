"""Worked example: the same channel fails three different ways as it gets longer.

A 200 x 75 x 20 x 2.0 mm lipped channel in S350 steel squashes at P_y = 245 kN. What
actually limits it is never that number, and — the point of this example — it is not even
the same *kind* of limit at different lengths.

The Direct Strength Method runs three curves off the section's elastic buckling loads.
Two of them, local (P_crl = 120 kN) and distortional (P_crd = 155 kN), are cross-section
properties: they do not change when the column gets longer. Only the global elastic load
P_cre falls with length. So as the column stretches:

- **1 m** — P_cre is 900 kN, global buckling barely matters, and the *distortional* mode
  governs at 151 kN. The lip is not doing enough to hold the flange straight.
- **3 m** — P_cre is 100 kN. Global buckling has cut the column to 88 kN, and because the
  DSM local curve is anchored on that reduced load rather than on P_y, *local* buckling
  now governs at 82 kN.
- **6 m** — P_cre is 25 kN and *global* buckling governs outright at 22 kN. The
  cross-section modes are irrelevant; the column is simply too slender.

Three lengths, three governing modes, three different repairs. A thicker web fixes the
1 m case and does nothing for the 6 m one; bracing fixes the 6 m case and does nothing for
the 1 m one. This is why `dsm_scorecard` reports the mode beside the number — a bare
capacity cannot tell a reader which way to move.

The elastic buckling loads are **not** computed here. For a real cold-formed shape they
come from a finite-strip analysis (CUFSM and its kin), and inventing them would be a
plausible capacity resting on a buckling load nobody ran. `ElasticBuckling` carries them
with the provenance of the run that produced them, and a screen without them reports
NOT_EVALUATED.

Run it directly (``python examples/lipped_channel_dsm.py``); the screens are exercised in
the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    PREQUALIFIED_LIPPED_CHANNEL,
    ElasticBuckling,
    dsm_compression_strength,
    dsm_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

YIELD_LOAD = Quantity.parse("245 kN")  # A_g · F_y for the 200x75x20x2.0 in S350
SERVICE_LOAD = Quantity.parse("60 kN")

# Cross-section modes: fixed by the shape, not by the length.
LOCAL = Quantity.parse("120 kN")
DISTORTIONAL = Quantity.parse("155 kN")

# Global elastic buckling load, from a finite-strip run at each unbraced length.
LENGTHS = (
    ("1 m", Quantity.parse("900 kN")),
    ("3 m", Quantity.parse("100 kN")),
    ("6 m", Quantity.parse("25 kN")),
)

BUCKLING_SOURCE = "CUFSM v5.04 finite-strip signature curve, run 2026-08-17"

# The section's flat-width ratios, for the AISI S100 §1.1.1.1 prequalification check.
GEOMETRY = {
    "web_flat_to_thickness": 98.0,
    "flange_flat_to_thickness": 37.5,
    "lip_flat_to_thickness": 10.0,
    "web_to_flange": 2.67,
    "lip_to_flange": 0.27,
}


def _strength(global_elastic: Quantity):
    return dsm_compression_strength(
        yield_load=YIELD_LOAD,
        elastic_buckling=ElasticBuckling(
            local=LOCAL,
            distortional=DISTORTIONAL,
            global_=global_elastic,
            source=BUCKLING_SOURCE,
        ),
    )


def screen_column_lengths() -> Scorecard:
    """Screen the 60 kN service load at each unbraced length."""
    outside = PREQUALIFIED_LIPPED_CHANNEL.check(**GEOMETRY)
    return Scorecard(
        entries=tuple(
            dsm_scorecard(
                f"lipped channel at {label}",
                demand=SERVICE_LOAD,
                strength=_strength(global_elastic),
                outside_prequalified=outside,
            )
            for label, global_elastic in LENGTHS
        )
    )


def screen_without_a_buckling_analysis() -> Scorecard:
    """DSM cannot run without elastic buckling values, and says so."""
    return Scorecard(entries=(dsm_scorecard("lipped channel", demand=SERVICE_LOAD, strength=None),))


def main() -> None:
    outside = PREQUALIFIED_LIPPED_CHANNEL.check(**GEOMETRY)
    print("prequalified geometry: " + ("yes" if not outside else "NO — " + "; ".join(outside)))
    print(f"squash load P_y = {YIELD_LOAD.magnitude:.0f} kN\n")
    for label, global_elastic in LENGTHS:
        s = _strength(global_elastic)
        print(
            f"{label:>4}  P_cre {global_elastic.magnitude:6.0f} kN | "
            f"global {s.global_strength.magnitude:6.1f}  "
            f"local {s.local_strength.magnitude:6.1f}  "
            f"distortional {s.distortional_strength.magnitude:6.1f}  "
            f"-> {s.nominal.magnitude:6.1f} kN ({s.governing.value})"
        )
    print()
    for entry in screen_column_lengths().entries:
        print(f"  {entry}")
    print()
    for entry in screen_without_a_buckling_analysis().entries:
        print(f"  {entry}")


if __name__ == "__main__":
    main()
