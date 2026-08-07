"""T1 analytical thermoforming (vacuum-forming) checks (closed-form).

Thermoforming heats a plastic sheet until it is rubbery, then stretches it over or into a mold with
vacuum or pressure. Unlike the injection molding of :mod:`anvilate.analysis.injection_molding`, no
new material is added — the same sheet is simply spread thinner over a larger surface, so it is
governed by conservation of volume, not by flow or clamp force. The deeper the draw, the more the
sheet must stretch, and the thinner the walls become; a draw taken too deep leaves walls too thin to
hold the part's shape or blows through entirely.

The measure of the stretch is the areal draw ratio S = A_part/A_sheet, the surface area of the
formed part over the area of the sheet blank it came from — always greater than one, and larger for
more complex parts. Because the plastic volume is fixed, the average wall thins in exact proportion,
t_avg = t_sheet/S: double the area and you halve the wall. Turning that around sizes the job, giving
the starting sheet gauge t_sheet = t_min·S needed to leave a specified minimum wall after forming —
the number that decides how thick a blank to buy for a given part depth.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "thermoforming_areal_draw_ratio",
    "thermoforming_average_wall_thickness",
    "thermoforming_sheet_gauge_for_wall",
]


def thermoforming_areal_draw_ratio(*, part_area: Quantity, sheet_area: Quantity) -> float:
    """The areal draw ratio, S = A_part/A_sheet.

    How much the sheet must stretch to form the part: the surface area ``part_area`` A_part of the
    finished part over the ``sheet_area`` A_sheet of the flat blank it is drawn from, S =
    A_part/A_sheet. It is always greater than one, and grows with the depth and complexity of the
    part; it sets directly how much the walls thin (:func:`thermoforming_average_wall_thickness`). A
    high draw ratio is the warning sign of thin walls and possible blow-through. Returns the areal
    draw ratio (> 1).
    """
    _check(part_area, "[area]", "part_area")
    _check(sheet_area, "[area]", "sheet_area")
    a_part = part_area.to("mm**2").magnitude
    a_sheet = sheet_area.to("mm**2").magnitude
    if a_sheet <= 0:
        raise ValueError("sheet_area must be positive")
    if a_part <= a_sheet:
        raise ValueError("part_area must exceed sheet_area (forming stretches the sheet)")
    return a_part / a_sheet


def thermoforming_average_wall_thickness(
    *, sheet_thickness: Quantity, areal_draw_ratio: float
) -> Quantity:
    """The average wall thickness after forming, t_avg = t_sheet/S.

    The mean wall the formed part is left with once the sheet has been stretched: because the volume
    of plastic is conserved, spreading the ``sheet_thickness`` t_sheet over an ``areal_draw_ratio``
    S times more area thins it in exact proportion, t_avg = t_sheet/S. It is an average — corners
    and the deepest draw run thinner still — so the real minimum wall is below this, and a large S
    drives a part toward walls too thin to stand. Returns the average wall thickness in mm.
    """
    _check(sheet_thickness, "[length]", "sheet_thickness")
    t = sheet_thickness.to("mm").magnitude
    if t <= 0:
        raise ValueError("sheet_thickness must be positive")
    if areal_draw_ratio < 1.0:
        raise ValueError("areal_draw_ratio must be at least 1 (forming cannot thicken the sheet)")
    return Quantity(magnitude=t / areal_draw_ratio, unit="mm")


def thermoforming_sheet_gauge_for_wall(
    *, minimum_wall_thickness: Quantity, areal_draw_ratio: float
) -> Quantity:
    """The starting sheet gauge for a target wall, t_sheet = t_min·S.

    Inverting the wall-thinning relation (:func:`thermoforming_average_wall_thickness`) to size the
    blank: the sheet gauge needed so that after stretching by the ``areal_draw_ratio`` S the walls
    are left no thinner than ``minimum_wall_thickness`` t_min, t_sheet = t_min·S. It is how a deeper
    part is specified — a bigger draw ratio simply demands a proportionally thicker starting sheet.
    Returns the required sheet gauge in mm.
    """
    _check(minimum_wall_thickness, "[length]", "minimum_wall_thickness")
    t_min = minimum_wall_thickness.to("mm").magnitude
    if t_min <= 0:
        raise ValueError("minimum_wall_thickness must be positive")
    if areal_draw_ratio < 1.0:
        raise ValueError("areal_draw_ratio must be at least 1 (forming cannot thicken the sheet)")
    return Quantity(magnitude=t_min * areal_draw_ratio, unit="mm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
