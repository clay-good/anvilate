"""Worked example: when one key runs out of length and a spline does not.

A 50 mm shaft has to hand 2000 N·m to its hub through a 60 mm-long connection. The obvious
choice is a single parallel key, and the shear is fine -- but the key does not fail in shear,
it fails in *bearing*, crushing against the side of its keyway. Sizing the key against a
100 MPa bearing allowable asks for 114 mm of engaged length, nearly twice the 60 mm hub the
design allows. A single key simply cannot carry this torque in this space: a safety factor of
0.53 on the length available.

The problem is that a key concentrates the whole tangential force onto one narrow flank. A
*spline* is the same idea multiplied -- a ring of integral keys cut into the shaft -- so it
spreads the identical torque across, here, ten tooth flanks at once. Each flank bears gently,
and the connection carries 2115 N·m in the same 60 mm length, a safety factor of 1.06. Same
shaft, same length, same bearing allowable; the load is just shared instead of concentrated.

The lesson is that a key and a spline fail the same way -- bearing on a flank -- and the spline
wins by having many flanks. When a single key runs out of length (its bearing length exceeds
the hub it has to fit in), the answer is not a bigger key but *more* flanks: a spline, or a
pair of keys, or an interference fit. High torque in a short hub is a bearing-area problem,
and area is what extra teeth buy.

Run it directly (``python examples/key_vs_spline.py``);
:func:`screen_connection` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import key_length_for_torque, spline_torque_capacity
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TORQUE = Quantity.parse("2000 N*m")
SHAFT_DIAMETER = Quantity.parse("50 mm")
AVAILABLE_HUB_LENGTH = Quantity.parse("60 mm")
ALLOWABLE_SHEAR = Quantity.parse("60 MPa")
ALLOWABLE_BEARING = Quantity.parse("100 MPa")

KEY_WIDTH = Quantity.parse("14 mm")
KEY_HEIGHT = Quantity.parse("14 mm")

SPLINE_TEETH = 10
SPLINE_TOOTH_HEIGHT = Quantity.parse("3 mm")
SPLINE_MEAN_RADIUS = Quantity.parse("23.5 mm")
SPLINE_LOAD_FRACTION = 0.5


def screen_connection() -> Scorecard:
    """Screen a single key (by length it needs) and a spline (by torque it carries)."""
    key = key_length_for_torque(
        torque=TORQUE,
        shaft_diameter=SHAFT_DIAMETER,
        key_width=KEY_WIDTH,
        key_height=KEY_HEIGHT,
        allowable_shear=ALLOWABLE_SHEAR,
        allowable_bearing=ALLOWABLE_BEARING,
    )
    spline = spline_torque_capacity(
        allowable_pressure=ALLOWABLE_BEARING,
        mean_radius=SPLINE_MEAN_RADIUS,
        tooth_height=SPLINE_TOOTH_HEIGHT,
        spline_length=AVAILABLE_HUB_LENGTH,
        number_of_teeth=SPLINE_TEETH,
        load_fraction=SPLINE_LOAD_FRACTION,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "single key: hub length vs length needed",
                computed=AVAILABLE_HUB_LENGTH.to("mm").magnitude
                / key.required_length.to("mm").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "spline: capacity vs torque",
                computed=spline.to("N*m").magnitude / TORQUE.to("N*m").magnitude,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(screen_connection())


if __name__ == "__main__":
    main()
