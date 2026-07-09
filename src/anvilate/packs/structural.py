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
    ColumnEnd,
    CrossSection,
    axial_stress,
    cantilever_end_load,
    cantilever_uniform_load,
    deflection_scorecard,
    euler_critical_stress,
    fixed_fixed_center_load,
    fixed_fixed_uniform_load,
    johnson_critical_stress,
    simply_supported_center_load,
    simply_supported_uniform_load,
    slenderness_ratio,
    strength_scorecard,
    transition_slenderness,
)
from ..scorecard import Scorecard
from ..standards import MaterialsDatabase, default_materials_db
from ..units import Quantity

__all__ = [
    "Support",
    "LoadType",
    "BeamMember",
    "screen_beam_member",
    "ColumnMember",
    "screen_column_member",
    "StructuralMember",
    "screen_structure",
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
    deflection_limit: Quantity | None = None  # a member may carry its own limit

    @model_validator(mode="after")
    def _well_formed(self) -> BeamMember:
        if not self.length.has_dimension("[length]"):
            raise ValueError(f"length must be a [length] quantity; got {self.length}")
        if self.deflection_limit is not None and not self.deflection_limit.has_dimension(
            "[length]"
        ):
            raise ValueError(
                f"deflection_limit must be a [length] quantity; got {self.deflection_limit}"
            )
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
    strength (at ``required_safety_factor``) and, when a limit is set, the peak
    deflection against it. The deflection limit is the ``max_deflection`` argument,
    or the member's own ``deflection_limit`` when the argument is omitted.
    ``materials`` defaults to the bundled database; an unknown material id raises
    its lookup error.
    """
    if max_deflection is None:
        max_deflection = member.deflection_limit
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


class ColumnMember(BaseModel):
    """A structural compression member and what a buckling screen needs.

    ``section``'s ``second_moment`` should be the *least* (weak-axis) value, since
    a column buckles about its weak axis. ``end_condition`` sets the effective-
    length factor; ``axial_load`` is the compressive force; ``material`` a database
    id (E and yield drive the screen).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    section: CrossSection
    length: Quantity
    end_condition: ColumnEnd = ColumnEnd.PINNED_PINNED
    axial_load: Quantity
    material: str

    @model_validator(mode="after")
    def _well_formed(self) -> ColumnMember:
        if not self.length.has_dimension("[length]"):
            raise ValueError(f"length must be a [length] quantity; got {self.length}")
        if not self.axial_load.has_dimension("[force]"):
            raise ValueError(f"axial_load must be a [force] quantity; got {self.axial_load}")
        return self


def screen_column_member(
    member: ColumnMember,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`ColumnMember` for buckling and return its scorecard.

    Computes the slenderness λ = K·L/r and picks the regime automatically: the
    Euler elastic-buckling stress above the transition slenderness λ₁, the Johnson
    parabola below it. The critical stress is screened against the applied axial
    stress (load/area) at ``required_safety_factor``. ``materials`` defaults to the
    bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(member.material)
    modulus = record.elastic_modulus.quantity
    yield_strength = record.yield_strength.quantity

    effective_length = Quantity(
        magnitude=member.end_condition.factor() * member.length.to("mm").magnitude,
        unit="mm",
    )
    lam = slenderness_ratio(
        effective_length=effective_length,
        radius_of_gyration=member.section.radius_of_gyration,
    )
    lam_1 = transition_slenderness(yield_strength=yield_strength, elastic_modulus=modulus)
    if lam >= lam_1:
        critical = euler_critical_stress(elastic_modulus=modulus, slenderness_ratio=lam)
        regime = "Euler"
    else:
        critical = johnson_critical_stress(
            yield_strength=yield_strength, elastic_modulus=modulus, slenderness_ratio=lam
        )
        regime = "Johnson"

    applied = axial_stress(force=member.axial_load, area=member.section.area)
    entry = strength_scorecard(
        f"{member.name} buckling ({regime})",
        stress=applied,
        allowable=critical,
        required=required_safety_factor,
    )
    return Scorecard(entries=(entry,))


StructuralMember = BeamMember | ColumnMember


def screen_structure(
    members: list[StructuralMember],
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a whole structure — a mix of beam and column members — into one card.

    Each member is dispatched to its own screen (beams by support/load, columns by
    slenderness regime; a beam applies its own ``deflection_limit`` if set) and all
    the entries are collected into a single :class:`~anvilate.scorecard.Scorecard`.
    The roll-up honours No-silent-green: the structure passes only when every
    member's every check ran and passed.
    """
    materials = materials or default_materials_db()
    entries = []
    for member in members:
        if isinstance(member, BeamMember):
            card = screen_beam_member(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        else:
            card = screen_column_member(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        entries.extend(card.entries)
    return Scorecard(entries=tuple(entries))
