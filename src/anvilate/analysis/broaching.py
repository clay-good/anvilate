"""T1 analytical broaching checks (closed-form).

Broaching pushes or pulls a long, toothed bar through (or over) a workpiece to cut a profile in a
single stroke, each tooth standing a little proud of the one before it so the cut deepens tooth by
tooth. It is a bulk metal-cutting process like the turning of :mod:`anvilate.analysis.machining`,
but it earns its own module for the same reason wire drawing (:mod:`anvilate.analysis.wire_drawing`)
does: a *pull* broach carries the entire cutting force as tension through its own weakest section,
so its governing failure mode is not the cut but the bar snapping in two.

Three numbers size a broaching stroke. The teeth in cut n = L/p is how many teeth the workpiece
length L spans at the tooth pitch p — the teeth cutting at once, and what sets the instantaneous
load. The cutting force F = k_s·n·w·t is that count times the chip cross-section each tooth peels,
the cut width w times the rise per tooth t, scaled by the specific cutting force k_s of the metal.
The pull capacity F_max = σ_allow·A_root is the tension the broach's minimum root section can carry
before it yields: the self-limit that caps how many teeth may cut at once and how deep each may
bite, and the reason a broach is designed with generous roots and modest rise per tooth.

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (broaching) — the teeth
simultaneously in cut over a length, the cutting force they develop together, and the pull the
broach itself can carry before it yields.
"""

from __future__ import annotations

from ..units import Quantity
from ._counting import whole_count_floor

__all__ = [
    "broaching_cutting_force",
    "broaching_pull_capacity",
    "broaching_teeth_in_cut",
]


def broaching_teeth_in_cut(*, workpiece_length: Quantity, tooth_pitch: Quantity) -> int:
    """The number of teeth cutting at once, n = ⌊L/p⌋ (at least 1).

    How many broach teeth the workpiece is in contact with simultaneously: the ``workpiece_length``
    L (the length of surface being broached, along the stroke) divided by the ``tooth_pitch`` p, and
    rounded down because only whole teeth cut — n = ⌊L/p⌋, but never fewer than one. This count
    sets the instantaneous cutting force (:func:`broaching_cutting_force`), so a coarse pitch that
    keeps two or three teeth engaged is chosen deliberately to keep the load steady without
    overloading the broach. Returns the engaged-tooth count as an integer.
    """
    _check(workpiece_length, "[length]", "workpiece_length")
    _check(tooth_pitch, "[length]", "tooth_pitch")
    length = workpiece_length.to("mm").magnitude
    pitch = tooth_pitch.to("mm").magnitude
    if length <= 0:
        raise ValueError("workpiece_length must be positive")
    if pitch <= 0:
        raise ValueError("tooth_pitch must be positive")
    return max(1, whole_count_floor(length / pitch))


def broaching_cutting_force(
    *,
    specific_cutting_force: Quantity,
    teeth_in_cut: int,
    cut_width: Quantity,
    rise_per_tooth: Quantity,
) -> Quantity:
    """The broaching cutting force, F = k_s·n·w·t.

    The force to drive the broach through the cut: the ``specific_cutting_force`` k_s (the force per
    unit chip cross-section of the metal) times the total chip area cut at once — the
    ``teeth_in_cut`` n (from :func:`broaching_teeth_in_cut`) each peeling a chip of the
    ``cut_width`` w by the ``rise_per_tooth`` t, so F = k_s·n·w·t. On a pull broach the whole force
    is tension in the bar and must stay under its capacity (:func:`broaching_pull_capacity`) or it
    snaps; on a push broach it is compression, which can buckle a slender broach. Returns the force
    in kN.
    """
    _check(specific_cutting_force, "[pressure]", "specific_cutting_force")
    _check(cut_width, "[length]", "cut_width")
    _check(rise_per_tooth, "[length]", "rise_per_tooth")
    k_s = specific_cutting_force.to("Pa").magnitude
    w = cut_width.to("m").magnitude
    t = rise_per_tooth.to("m").magnitude
    if k_s <= 0:
        raise ValueError("specific_cutting_force must be positive")
    if not isinstance(teeth_in_cut, int) or teeth_in_cut < 1:
        raise ValueError("teeth_in_cut must be an integer of at least 1")
    if w <= 0:
        raise ValueError("cut_width must be positive")
    if t <= 0:
        raise ValueError("rise_per_tooth must be positive")
    return Quantity(magnitude=k_s * teeth_in_cut * w * t / 1000.0, unit="kN")


def broaching_pull_capacity(*, allowable_stress: Quantity, root_area: Quantity) -> Quantity:
    """The pull broach tensile capacity, F_max = σ_allow·A_root.

    The largest pull the broach can carry before its minimum root section yields: the
    ``allowable_stress`` σ_allow of the broach material times the ``root_area`` A_root — the
    smallest cross-section, at the bottom of a gullet — giving F_max = σ_allow·A_root. It is the
    self-limit of the process: the cutting force (:func:`broaching_cutting_force`) must stay below
    it, which caps how many teeth may cut at once and how deep each may bite, and it is why broaches
    are cut with generous roots and modest rise per tooth. Returns the pull capacity in kN.
    """
    _check(allowable_stress, "[pressure]", "allowable_stress")
    _check(root_area, "[area]", "root_area")
    sigma = allowable_stress.to("Pa").magnitude
    area = root_area.to("m**2").magnitude
    if sigma <= 0:
        raise ValueError("allowable_stress must be positive")
    if area <= 0:
        raise ValueError("root_area must be positive")
    return Quantity(magnitude=sigma * area / 1000.0, unit="kN")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
