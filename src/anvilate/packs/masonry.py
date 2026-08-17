"""The masonry discipline pack: declare a wall, get a TMS 402 allowable-stress scorecard.

The masonry pack serves the masonry designer the way :mod:`anvilate.packs.structural` serves the
steel designer. A :class:`MasonryWall` declares an unreinforced masonry wall's specified strength,
slenderness, and the axial and out-of-plane bending stresses on it; :func:`screen_masonry_wall`
screens both the gravity-only axial stress against the slenderness-reduced allowable and the
combined axial-plus-flexure unity check that actually governs a wall carrying gravity and wind at
once. Each rolls into a cited PASS/FAIL scorecard entry, no silent green. The specified strength
f'm and the applied stresses are the caller's; the allowable-stress screen is TMS 402 theory, and
the engineer of record owns the design.
"""

from __future__ import annotations

from pydantic import ConfigDict

from ..analysis import (
    masonry_allowable_axial_stress,
    masonry_allowable_flexural_stress,
    masonry_combined_stress_ratio,
)
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "MasonryWall",
    "screen_masonry_wall",
]

_AXIAL_REFERENCE = "TMS 402 §8.2.4 allowable axial stress"
_COMBINED_REFERENCE = "TMS 402 §8.2.4.2 combined axial + flexure unity"


class MasonryWall(GuardedInputs):
    """An unreinforced masonry wall under gravity plus out-of-plane bending, and its screen inputs.

    ``masonry_strength`` f'm is the specified compressive strength and ``slenderness_ratio`` h/r the
    effective height over the net-section radius of gyration (which derates the allowable axial
    stress). ``axial_stress`` f_a is the applied gravity stress and ``flexural_stress`` f_b the
    extreme-fibre bending stress from out-of-plane wind. All stresses are the caller's.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    signed_fields: tuple[str, ...] = ("axial_stress", "flexural_stress")

    masonry_strength: Quantity
    slenderness_ratio: float
    axial_stress: Quantity
    flexural_stress: Quantity


def screen_masonry_wall(
    wall: MasonryWall,
    *,
    required_safety_factor: float = 1.0,
) -> Scorecard:
    """Screen a :class:`MasonryWall` for axial and combined stress, and return its scorecard.

    Screens the gravity-only axial utilization (F_a/f_a, where F_a is the slenderness-reduced
    allowable) and the combined axial-plus-flexure unity check (1/(f_a/F_a + f_b/F_b), which is 1.0
    at the TMS 402 unity limit), each against ``required_safety_factor`` (1.0 — the allowable
    already carries the code's margin). Returns a :class:`~anvilate.scorecard.Scorecard` with a
    cited PASS/FAIL entry for each; the combined check is the one that catches a wall gravity alone
    would pass.
    """
    allowable_axial = masonry_allowable_axial_stress(
        masonry_strength=wall.masonry_strength, slenderness_ratio=wall.slenderness_ratio
    )
    allowable_flexural = masonry_allowable_flexural_stress(masonry_strength=wall.masonry_strength)

    f_a = wall.axial_stress.to("MPa").magnitude
    fa_allow = allowable_axial.to("MPa").magnitude
    axial_sf = fa_allow / f_a if f_a > 0 else None
    axial_entry = ScorecardEntry.from_safety_factor(
        "axial stress", computed=axial_sf, required=required_safety_factor
    ).model_copy(update={"reference": _AXIAL_REFERENCE})

    unity = masonry_combined_stress_ratio(
        axial_stress=wall.axial_stress,
        allowable_axial_stress=allowable_axial,
        flexural_stress=wall.flexural_stress,
        allowable_flexural_stress=allowable_flexural,
    )
    combined_sf = 1.0 / unity if unity > 0 else None
    combined_entry = ScorecardEntry.from_safety_factor(
        "combined axial + flexure", computed=combined_sf, required=required_safety_factor
    ).model_copy(update={"reference": _COMBINED_REFERENCE})
    return Scorecard(entries=(axial_entry, combined_entry))
