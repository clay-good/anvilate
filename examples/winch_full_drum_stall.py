"""Worked example: the winch that stalls on its last layer of rope.

A recovery winch must hold 7 kN of line pull through a 60 m lift, driven at 850 N·m of
drum torque. On the bare 200 mm drum the numbers are comfortable: the first layer of
13 mm rope works at a 106.5 mm radius, so the winch pulls 7.98 kN -- a 1.14 margin, and
that is the number on the catalogue plate. The narrow drum stores the 60 m easily too:
20 wraps per layer, four layers, 63.3 m tight-wound (1.06).

But a drum is a lever that grows as it winds. By the fourth layer the rope works at
(200 + 7·13)/2 = 145.5 mm -- almost 40 mm more arm -- and the same 850 N·m delivers only
5.84 kN (0.83). The winch that started the lift with margin stalls near the top, exactly
when the load is highest off the ground. Nothing failed; the geometry simply traded pull
for radius, layer by layer.

The fix is not a bigger motor but a *wider* drum: 45 wraps per layer stores the same
60 m in two layers (63.9 m, 1.06), the top layer works at 119.5 mm, and the pull at the
end of the lift is 7.11 kN (1.02). The lesson is that a winch's line pull is a bare-drum
rating that falls with every layer wound on: screen the pull at the highest layer the
lift reaches, and when it comes up short, spread the rope wider instead of stacking it
higher -- drum width buys back the lever arm that drum layers spend.

Run it directly (``python examples/winch_full_drum_stall.py``);
:func:`screen_narrow_drum` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import drum_line_pull, drum_rope_capacity
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

REQUIRED_PULL = Quantity.parse("7 kN")
REQUIRED_ROPE = Quantity.parse("60 m")
DRUM_TORQUE = Quantity.parse("850 N*m")
CORE_DIAMETER = Quantity.parse("200 mm")
ROPE_DIAMETER = Quantity.parse("13 mm")

NARROW_WRAPS, NARROW_LAYERS = 20, 4  # a compact drum stacking the rope high
WIDE_WRAPS, WIDE_LAYERS = 45, 2  # a wide drum spreading it low


def _screen(wraps_per_layer: int, layers: int) -> Scorecard:
    capacity = drum_rope_capacity(
        core_diameter=CORE_DIAMETER,
        rope_diameter=ROPE_DIAMETER,
        wraps_per_layer=wraps_per_layer,
        layers=layers,
    )
    pulls = {
        layer: drum_line_pull(
            torque=DRUM_TORQUE,
            core_diameter=CORE_DIAMETER,
            rope_diameter=ROPE_DIAMETER,
            layer=layer,
        )
        for layer in (1, layers)
    }
    required_n = REQUIRED_PULL.to("N").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "stored rope vs required length",
                computed=capacity.to("m").magnitude / REQUIRED_ROPE.to("m").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "line pull at bare drum vs load",
                computed=pulls[1].to("N").magnitude / required_n,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "line pull at full drum vs load",
                computed=pulls[layers].to("N").magnitude / required_n,
                required=1.0,
            ),
        )
    )


def screen_narrow_drum() -> Scorecard:
    """Screen the narrow four-layer drum: it stalls on the top layer."""
    return _screen(NARROW_WRAPS, NARROW_LAYERS)


def screen_wide_drum() -> Scorecard:
    """Screen the wide two-layer drum: the same rope, the pull recovered."""
    return _screen(WIDE_WRAPS, WIDE_LAYERS)


def main() -> None:
    print(f"narrow drum ({NARROW_WRAPS} wraps x {NARROW_LAYERS} layers):")
    print(screen_narrow_drum())
    print(f"\nwide drum ({WIDE_WRAPS} wraps x {WIDE_LAYERS} layers):")
    print(screen_wide_drum())


if __name__ == "__main__":
    main()
