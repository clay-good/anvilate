"""Worked example: which way the snow drifts decides a canopy screen.

Declares the same 1.8 m cantilevered entrance-canopy beam — an 80 x 40 x 4 mm
A36 box at 1.2 m centers under a 3 kPa drift surcharge (w₀ = 3.6 N/mm at the
peak) — and screens the two places that drift can pile up. Assumed against the
building face, the triangle peaks at the wall and tapers to the free edge:
M = w₀·L²/6 screens comfortably (SF 2.29, tip deflection 8.855 mm inside
L/180 = 10 mm). But this canopy carries a raised fascia sign band at the free
edge, and drift forms against the fascia instead — the same surcharge mirrored
(``triangle_mirrored``) puts the resultant at 2·L/3 from the wall, doubling
the wall moment (M = w₀·L²/3, SF 1.14) and nearly tripling the tip deflection
(11·w₀·L⁴/120EI = 24.35 mm): both screens flip to FAIL. The load didn't
change; only where it piles up did — declaring the drift orientation is how
the screen can tell.

Run it directly (``python examples/canopy_snow_drift.py``);
:func:`screen_canopy_drift` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import CrossSection
from anvilate.packs.structural import (
    BeamMember,
    LoadType,
    Support,
    screen_structure,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

# 3 kPa peak drift surcharge at 1.2 m beam spacing.
PEAK_LOAD = Quantity.parse("3.6 N/mm")
SPAN = Quantity.parse("1.8 m")
DEFLECTION_LIMIT = Quantity(magnitude=1800 / 180, unit="mm")  # L/180 for a cantilever tip
REQUIRED_SF = 1.5

_DRIFT_SPOTS = (
    ("drift against the building face", False),
    ("drift against the edge fascia", True),
)


def screen_canopy_drift() -> Scorecard:
    """Screen the canopy beam under both drift orientations, as one structure."""
    section = CrossSection.hollow_rectangular(
        width=Quantity.parse("40 mm"),
        height=Quantity.parse("80 mm"),
        wall_thickness=Quantity.parse("4 mm"),
    )
    members = [
        BeamMember(
            name=name,
            section=section,
            length=SPAN,
            support=Support.CANTILEVER,
            load=PEAK_LOAD,
            load_type=LoadType.TRIANGULAR,
            material="ASTM-A36",
            deflection_limit=DEFLECTION_LIMIT,
            triangle_mirrored=mirrored,
        )
        for name, mirrored in _DRIFT_SPOTS
    ]
    return screen_structure(members, required_safety_factor=REQUIRED_SF)


def main() -> None:
    card = screen_canopy_drift()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
