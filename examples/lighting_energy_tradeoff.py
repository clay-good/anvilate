"""Worked example: one lighting layout, screened where illuminance and the energy code collide.

The lighting pack reports the two verdicts a real layout must win at once, and they pull in
opposite directions: adding luminaires to reach the task illuminance drives the connected power
density up toward the energy-code cap. This example holds the room, fixture, and targets fixed —
an 80 m² office lit with 3400-lumen, 30 W troffers, needing 400 lux and capped at 8.8 W/m² (ASHRAE
90.1) — and varies only the fixture count. Fourteen fixtures stay well under the power cap but
leave the office too dim; twenty-eight light it brightly but blow the energy budget; twenty land in
the window that passes both. It is the same balance the masonry pack shows between gravity and
combined stress, here between seeing well and spending watts.

Run it directly (``python examples/lighting_energy_tradeoff.py``);
:func:`layout_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.lighting import LightingInstallation, screen_lighting
from anvilate.units import Quantity

_FIXTURE = {
    "lumens_per_luminaire": Quantity.parse("3400 lumen"),
    "input_watts_per_luminaire": Quantity.parse("30 W"),
    "coefficient_of_utilization": 0.62,
    "light_loss_factor": 0.8,
    "floor_area": Quantity.parse("80 m**2"),
    "required_illuminance": Quantity.parse("400 lux"),
    "allowable_power_density": Quantity.parse("8.8 W/m**2"),
}


def layout_scorecards() -> dict[str, str]:
    """Return the scorecard status for 14, 20, and 28 fixture counts."""
    out: dict[str, str] = {}
    for count in (14, 20, 28):
        card = screen_lighting(LightingInstallation(luminaire_count=count, **_FIXTURE))
        fails = ", ".join(e.name for e in card.failures())
        out[f"count_{count}"] = card.status.value
        out[f"count_{count}_fails"] = fails
    return out


def main() -> None:
    r = layout_scorecards()
    for count in (14, 20, 28):
        status = r[f"count_{count}"].upper()
        fails = r[f"count_{count}_fails"]
        tail = f" (fails: {fails})" if fails else ""
        print(f"{count:>2} fixtures : {status}{tail}")
    print("  -> too few is dim, too many blows the energy cap; 20 clears both")


if __name__ == "__main__":
    main()
