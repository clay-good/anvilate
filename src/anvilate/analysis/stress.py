"""T1 stress-combination utilities (von Mises equivalent stress).

The individual checks in this package report component stresses — a bending
stress from a beam, a shear stress from a shaft. A ductile part yields on the
*combined* state, so those components are rolled into a single von Mises
equivalent stress before comparing to the yield strength:

    plane stress:      σ_vm = √(σx² − σx·σy + σy² + 3·τxy²)
    bending + torsion: σ_vm = √(σ² + 3·τ²)   (the common shaft case)

Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity`
stresses; a helper returns the factor of safety against yield.
"""

from __future__ import annotations

from math import sqrt

from pydantic import BaseModel, ConfigDict

from ..scorecard import ScorecardEntry
from ..units import Quantity

__all__ = [
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "yield_safety_factor",
    "strength_scorecard",
    "CombinedNormalStress",
    "combine_axial_bending",
]


def _require_stress(value: Quantity, name: str) -> float:
    if not value.has_dimension("[pressure]"):
        raise ValueError(
            f"{name} must be a [pressure] quantity; got {value.dimensionality} ({value})"
        )
    return value.to("MPa").magnitude


class CombinedNormalStress(BaseModel):
    """The extreme-fibre normal stresses of combined axial + bending loading.

    ``tension_fibre`` is the axial stress plus the bending stress (the most
    tensile fibre); ``compression_fibre`` is the axial minus the bending (the most
    compressive). ``peak_magnitude`` is the larger of the two in magnitude — the
    stress that governs a yield check.
    """

    model_config = ConfigDict(frozen=True)

    tension_fibre: Quantity
    compression_fibre: Quantity

    @property
    def peak_magnitude(self) -> Quantity:
        t = abs(self.tension_fibre.to("MPa").magnitude)
        c = abs(self.compression_fibre.to("MPa").magnitude)
        return Quantity(magnitude=max(t, c), unit="MPa")

    def __str__(self) -> str:
        return (
            f"combined: tension fibre {self.tension_fibre.to('MPa')}, "
            f"compression fibre {self.compression_fibre.to('MPa')}"
        )


def combine_axial_bending(
    *,
    axial_stress: Quantity,
    bending_stress: Quantity,
) -> CombinedNormalStress:
    """Superpose a uniform ``axial_stress`` and a ``bending_stress`` on a section.

    Bending puts one fibre in tension and the opposite in compression; the axial
    stress shifts both. Returns the two extreme-fibre stresses (axial ± |bending|)
    — the governing normal stresses for an eccentrically-loaded member or a
    beam-column. Both inputs must be stresses; a signed ``axial_stress`` (negative
    for compression) carries through.
    """
    a = _require_stress(axial_stress, "axial_stress")
    b = abs(_require_stress(bending_stress, "bending_stress"))
    return CombinedNormalStress(
        tension_fibre=Quantity(magnitude=a + b, unit="MPa"),
        compression_fibre=Quantity(magnitude=a - b, unit="MPa"),
    )


def von_mises_plane_stress(
    *,
    sigma_x: Quantity,
    sigma_y: Quantity,
    tau_xy: Quantity,
) -> Quantity:
    """The von Mises equivalent stress for a 2D plane-stress state.

    σ_vm = √(σx² − σx·σy + σy² + 3·τxy²). All three components must be stresses
    (pressure). Returns the equivalent stress in MPa.
    """
    sx = _require_stress(sigma_x, "sigma_x")
    sy = _require_stress(sigma_y, "sigma_y")
    txy = _require_stress(tau_xy, "tau_xy")
    vm = sqrt(sx * sx - sx * sy + sy * sy + 3 * txy * txy)
    return Quantity(magnitude=vm, unit="MPa")


def von_mises_bending_torsion(
    *,
    bending_stress: Quantity,
    shear_stress: Quantity,
) -> Quantity:
    """The von Mises equivalent stress for the common bending-plus-torsion case.

    σ_vm = √(σ² + 3·τ²), the plane-stress form with a single normal stress
    ``bending_stress`` (σ) and a single shear ``shear_stress`` (τ) — e.g. a shaft
    carrying both a bending moment and a torque. Returns the equivalent stress in
    MPa.
    """
    sigma = _require_stress(bending_stress, "bending_stress")
    tau = _require_stress(shear_stress, "shear_stress")
    vm = sqrt(sigma * sigma + 3 * tau * tau)
    return Quantity(magnitude=vm, unit="MPa")


def yield_safety_factor(equivalent_stress: Quantity, yield_strength: Quantity) -> float:
    """The factor of safety against yielding: yield strength / equivalent stress.

    Both arguments must be stresses. A value below 1 means the part yields.
    """
    sigma = _require_stress(equivalent_stress, "equivalent_stress")
    sy = _require_stress(yield_strength, "yield_strength")
    return sy / sigma


def strength_scorecard(
    name: str,
    *,
    stress: Quantity,
    allowable: Quantity | None,
    required: float,
) -> ScorecardEntry:
    """Screen a computed ``stress`` against a material ``allowable`` strength.

    Builds a :class:`~anvilate.scorecard.ScorecardEntry`: the safety factor is
    ``allowable``/|``stress``| (stress magnitude, so tension and compression are
    treated alike), judged against the ``required`` minimum. When ``allowable`` is
    ``None`` — a material property that is not in the database, such as an
    unlisted endurance limit — the entry is ``NOT_EVALUATED`` rather than a silent
    pass, honouring the No-silent-green rule. ``stress`` (and ``allowable`` when
    given) must be stresses.
    """
    sigma = abs(_require_stress(stress, "stress"))
    if allowable is None:
        computed = None
    else:
        strength = _require_stress(allowable, "allowable")
        computed = float("inf") if sigma == 0 else strength / sigma
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
