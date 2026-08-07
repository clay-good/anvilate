"""Worked example: why a deep vacuum-formed tray needs a thick blank — walls thin as it stretches.

Thermoforming makes a part by stretching one heated plastic sheet over a mold, adding no material.
Every bit of extra surface area the part has over the flat blank comes from the same plastic spread
thinner, so the walls of a deep part are always thinner than the sheet it started as — and the
deepest corners thinner still. The governing number is the areal draw ratio, the part's surface area
divided by the blank's: the average wall is simply the sheet gauge divided by that ratio. A designer
who wants a guaranteed minimum wall must therefore start from a thicker sheet, scaled up by the draw
ratio, or the part will come out too thin to hold its shape.

This example forms a tray whose surface area is 200000 mm² from a 300 mm square blank of 90000 mm²,
an areal draw ratio of about 2.22. A 2 mm sheet thins to an average wall of about 0.90 mm — and
since that is only an average, the corners run thinner. Turn the problem around: to leave a 0.5 mm
minimum wall at that draw ratio, the blank must start at about 1.11 mm. The example reports the draw
ratio, the average wall a 2 mm sheet gives, and the gauge a 0.5 mm wall demands, so the link from
part depth to blank thickness is explicit.

Run it directly (``python examples/thermoforming_wall_thinning.py``);
:func:`thermoforming_case` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    thermoforming_areal_draw_ratio,
    thermoforming_average_wall_thickness,
    thermoforming_sheet_gauge_for_wall,
)
from anvilate.units import Quantity

PART_SURFACE_AREA = Quantity.parse("200000 mm**2")
SHEET_AREA = Quantity.parse("90000 mm**2")  # 300 mm square blank
STARTING_SHEET_THICKNESS = Quantity.parse("2 mm")
MINIMUM_WALL = Quantity.parse("0.5 mm")


def thermoforming_case() -> dict[str, float]:
    """Return the areal draw ratio, the average wall from a 2 mm sheet, and the gauge for 0.5 mm."""
    draw_ratio = thermoforming_areal_draw_ratio(part_area=PART_SURFACE_AREA, sheet_area=SHEET_AREA)
    avg_wall = thermoforming_average_wall_thickness(
        sheet_thickness=STARTING_SHEET_THICKNESS, areal_draw_ratio=draw_ratio
    )
    gauge = thermoforming_sheet_gauge_for_wall(
        minimum_wall_thickness=MINIMUM_WALL, areal_draw_ratio=draw_ratio
    )
    return {
        "areal_draw_ratio": draw_ratio,
        "average_wall_mm": avg_wall.to("mm").magnitude,
        "gauge_for_half_mm_wall_mm": gauge.to("mm").magnitude,
    }


def main() -> None:
    d = thermoforming_case()
    print(f"areal draw ratio: {d['areal_draw_ratio']:.2f}")
    print(f"average wall from a 2 mm sheet: {d['average_wall_mm']:.2f} mm (corners run thinner)")
    print(
        f"sheet gauge to leave a 0.5 mm wall: {d['gauge_for_half_mm_wall_mm']:.2f} mm "
        f"-> deeper draws need thicker blanks"
    )


if __name__ == "__main__":
    main()
