"""The structural discipline pack: declare a beam member, get a scorecard.

This pack closes the T1 loop for beams. A :class:`BeamMember` declares what the
core Spec IR deliberately does not carry — a member's cross-section, span,
support condition, load, and material. :func:`screen_beam_member` then dispatches
to the matching closed-form beam check in :mod:`anvilate.analysis`, screens the
resulting stress and deflection against the material yield and an optional
deflection limit, and returns a :class:`~anvilate.scorecard.Scorecard`. The
"No silent green" rule carries through — an absent material property or limit
surfaces as NOT_EVALUATED, never a silent pass.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from ..analysis import (
    CrossSection,
    cantilever_end_load,
    cantilever_uniform_load,
    deflection_scorecard,
    fixed_fixed_center_load,
    fixed_fixed_uniform_load,
    simply_supported_center_load,
    simply_supported_uniform_load,
    strength_scorecard,
)
from ..scorecard import Scorecard
from ..standards import MaterialsDatabase, default_materials_db
from ..units import Quantity

__all__ = [
    "Support",
    "LoadType",
    "BeamMember",
    "screen_beam_member",
]


class Support(StrEnum):
    """A beam's end-support condition."""

    CANTILEVER = "cantilever"
    SIMPLY_SUPPORTED = "simply_supported"
    FIXED_FIXED = "fixed_fixed"


class LoadType(StrEnum):
    """How the member is loaded: a single point load or a uniform distributed one."""

    POINT = "point"
    DISTRIBUTED = "distributed"


# (support, load_type) -> the analysis check and the keyword its load takes.
_POINT_CHECKS = {
    Support.CANTILEVER: cantilever_end_load,
    Support.SIMPLY_SUPPORTED: simply_supported_center_load,
    Support.FIXED_FIXED: fixed_fixed_center_load,
}
_DISTRIBUTED_CHECKS = {
    Support.CANTILEVER: cantilever_uniform_load,
    Support.SIMPLY_SUPPORTED: simply_supported_uniform_load,
    Support.FIXED_FIXED: fixed_fixed_uniform_load,
}


class BeamMember(BaseModel):
    """A structural beam member and everything a T1 screen needs to check it.

    ``load`` is a force for a ``point`` member and a force-per-length for a
    ``distributed`` one — the model validates the dimension matches ``load_type``.
    ``material`` is a database id (its E and yield drive the checks).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    section: CrossSection
    length: Quantity
    support: Support
    load: Quantity
    load_type: LoadType
    material: str

    @model_validator(mode="after")
    def _well_formed(self) -> BeamMember:
        if not self.length.has_dimension("[length]"):
            raise ValueError(f"length must be a [length] quantity; got {self.length}")
        expected = "[force]" if self.load_type is LoadType.POINT else "[force] / [length]"
        if not self.load.has_dimension(expected):
            raise ValueError(
                f"a {self.load_type.value} load must be a {expected} quantity; got "
                f"{self.load.dimensionality} ({self.load})"
            )
        return self


def screen_beam_member(
    member: BeamMember,
    *,
    required_safety_factor: float,
    max_deflection: Quantity | None = None,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`BeamMember` and return its scorecard.

    Dispatches on the member's support and load type to the matching closed-form
    beam check, then screens the peak bending stress against the material's yield
    strength (at ``required_safety_factor``) and, when given, the peak deflection
    against ``max_deflection``. ``materials`` defaults to the bundled database;
    an unknown material id raises its lookup error.
    """
    materials = materials or default_materials_db()
    record = materials.get(member.material)
    common = {
        "length": member.length,
        "second_moment": member.section.second_moment,
        "extreme_fibre": member.section.extreme_fibre,
        "elastic_modulus": record.elastic_modulus.quantity,
    }
    if member.load_type is LoadType.POINT:
        result = _POINT_CHECKS[member.support](force=member.load, **common)
    else:
        result = _DISTRIBUTED_CHECKS[member.support](distributed_load=member.load, **common)

    entries = [
        strength_scorecard(
            f"{member.name} bending",
            stress=result.max_bending_stress,
            allowable=record.yield_strength.quantity,
            required=required_safety_factor,
        )
    ]
    if max_deflection is not None:
        entries.append(
            deflection_scorecard(
                f"{member.name} deflection",
                deflection=result.max_deflection,
                limit=max_deflection,
            )
        )
    return Scorecard(entries=tuple(entries))
