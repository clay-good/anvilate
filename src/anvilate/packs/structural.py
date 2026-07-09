"""The structural discipline pack: declare a beam member, get a scorecard.

This pack closes the T1 loop for beams. A :class:`BeamMember` declares what the
core Spec IR deliberately does not carry — a member's cross-section, span,
support condition, load, and material. :func:`screen_beam_member` then dispatches
to the matching closed-form beam check in :mod:`anvilate.analysis`, screens the
resulting stress and deflection against the material yield and an optional
deflection limit, and returns a :class:`~anvilate.scorecard.Scorecard`. The
"No silent green" rule carries through — an absent material property or limit
surfaces as NOT_EVALUATED, never a silent pass.

Every check cites the governing AISC 360-16 clause on its scorecard entry — the
"cited clauses" the discipline-packs spec calls for. The code references live
here in the discipline pack, not in the code-agnostic analysis layer.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from ..analysis import (
    ColumnEnd,
    CrossSection,
    axial_stress,
    bearing_stress,
    bolt_shear_stress,
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
    "BoltedConnection",
    "screen_bolted_connection",
    "WeldedConnection",
    "screen_welded_connection",
    "StructuralMember",
    "screen_structure",
]

# The effective throat of a fillet weld is 0.707 (= 1/√2) of its leg size.
_FILLET_THROAT_FACTOR = 0.707
# AISC allowable/nominal fillet-weld shear is 0.6 of the electrode strength F_EXX.
_WELD_SHEAR_FRACTION = 0.6

# Distortion-energy shear-yield fraction of tensile yield (τ_y ≈ 0.577·S_y).
_SHEAR_YIELD_FRACTION = 0.577

# AISC 360-16 clauses each screen cites on its scorecard entry (the discipline
# pack, not the code-agnostic analysis layer, owns these references).
_CLAUSE_FLEXURE = "AISC 360-16 Ch. F"
_CLAUSE_DEFLECTION = "AISC 360-16 §L3"
_CLAUSE_COMPRESSION = "AISC 360-16 Ch. E"
_CLAUSE_BOLT_SHEAR = "AISC 360-16 §J3.6"
_CLAUSE_BEARING = "AISC 360-16 §J3.10"
_CLAUSE_WELD = "AISC 360-16 §J2.4"


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
        ).model_copy(update={"reference": _CLAUSE_FLEXURE})
    ]
    if max_deflection is not None:
        entries.append(
            deflection_scorecard(
                f"{member.name} deflection",
                deflection=result.max_deflection,
                limit=max_deflection,
            ).model_copy(update={"reference": _CLAUSE_DEFLECTION})
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
    ).model_copy(update={"reference": _CLAUSE_COMPRESSION})
    return Scorecard(entries=(entry,))


class BoltedConnection(BaseModel):
    """A bolted lap/clevis connection transferring a transverse load.

    ``bolt_diameter`` is the shank diameter, ``shear_planes`` 1 (single) or 2
    (double), ``plate_thickness`` the bearing plate; ``load`` the transferred
    force. ``bolt_material`` and ``plate_material`` are database ids — the bolt's
    yield sets the shear allowable (0.577·S_y) and the plate's the bearing one.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    bolt_diameter: Quantity
    plate_thickness: Quantity
    load: Quantity
    bolt_material: str
    plate_material: str
    shear_planes: int = 1

    @model_validator(mode="after")
    def _well_formed(self) -> BoltedConnection:
        for value, name in (
            (self.bolt_diameter, "bolt_diameter"),
            (self.plate_thickness, "plate_thickness"),
        ):
            if not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        if not self.load.has_dimension("[force]"):
            raise ValueError(f"load must be a [force] quantity; got {self.load}")
        if self.shear_planes < 1:
            raise ValueError(f"shear_planes must be a positive integer; got {self.shear_planes}")
        return self


def screen_bolted_connection(
    connection: BoltedConnection,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`BoltedConnection`'s two failure modes into a scorecard.

    Screens the bolt shear stress against the bolt's shear yield (0.577·S_y) and
    the plate bearing stress against the plate's yield, both at
    ``required_safety_factor``. ``materials`` defaults to the bundled database.
    """
    materials = materials or default_materials_db()
    bolt = materials.get(connection.bolt_material)
    plate = materials.get(connection.plate_material)

    shear = bolt_shear_stress(
        force=connection.load,
        diameter=connection.bolt_diameter,
        shear_planes=connection.shear_planes,
    )
    bolt_sy = bolt.yield_strength.quantity.to("MPa").magnitude
    shear_yield = Quantity(magnitude=_SHEAR_YIELD_FRACTION * bolt_sy, unit="MPa")

    bearing = bearing_stress(
        force=connection.load,
        diameter=connection.bolt_diameter,
        thickness=connection.plate_thickness,
    )
    return Scorecard(
        entries=(
            strength_scorecard(
                f"{connection.name} bolt shear",
                stress=shear,
                allowable=shear_yield,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_BOLT_SHEAR}),
            strength_scorecard(
                f"{connection.name} plate bearing",
                stress=bearing,
                allowable=plate.yield_strength.quantity,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_BEARING}),
        )
    )


class WeldedConnection(BaseModel):
    """A fillet-welded connection carrying a load in shear on the weld throat.

    ``leg_size`` is the fillet leg w (the effective throat is 0.707·w),
    ``weld_length`` the total weld length L, ``load`` the transferred force, and
    ``electrode_strength`` the weld-metal tensile strength F_EXX (e.g. 483 MPa for
    an E70 electrode). The allowable weld shear is 0.6·F_EXX (AISC §J2.4).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    leg_size: Quantity
    weld_length: Quantity
    load: Quantity
    electrode_strength: Quantity

    @model_validator(mode="after")
    def _well_formed(self) -> WeldedConnection:
        for value, name in ((self.leg_size, "leg_size"), (self.weld_length, "weld_length")):
            if not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        if not self.load.has_dimension("[force]"):
            raise ValueError(f"load must be a [force] quantity; got {self.load}")
        if not self.electrode_strength.has_dimension("[pressure]"):
            raise ValueError(
                f"electrode_strength must be a [pressure] quantity; got {self.electrode_strength}"
            )
        return self


def screen_welded_connection(
    connection: WeldedConnection,
    *,
    required_safety_factor: float,
) -> Scorecard:
    """Screen a :class:`WeldedConnection`'s throat shear into a scorecard.

    The shear on the effective throat is τ = F/(0.707·w·L); it is screened against
    the allowable weld shear 0.6·F_EXX at ``required_safety_factor`` (AISC §J2.4).
    No material lookup is needed — the electrode strength is carried on the member.
    """
    throat_area = (
        _FILLET_THROAT_FACTOR
        * connection.leg_size.to("mm").magnitude
        * connection.weld_length.to("mm").magnitude
    )
    shear = Quantity(magnitude=connection.load.to("N").magnitude / throat_area, unit="MPa")
    allowable = Quantity(
        magnitude=_WELD_SHEAR_FRACTION * connection.electrode_strength.to("MPa").magnitude,
        unit="MPa",
    )
    entry = strength_scorecard(
        f"{connection.name} weld shear",
        stress=shear,
        allowable=allowable,
        required=required_safety_factor,
    ).model_copy(update={"reference": _CLAUSE_WELD})
    return Scorecard(entries=(entry,))


StructuralMember = BeamMember | ColumnMember | BoltedConnection | WeldedConnection


def screen_structure(
    members: list[StructuralMember],
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a whole structure — beams, columns, and connections — into one card.

    Each member is dispatched to its own screen (beams by support/load, columns by
    slenderness regime, bolted connections by shear/bearing, welds by throat shear;
    a beam applies its own ``deflection_limit`` if set) and all the entries are
    collected into a single :class:`~anvilate.scorecard.Scorecard`.
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
        elif isinstance(member, ColumnMember):
            card = screen_column_member(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        elif isinstance(member, BoltedConnection):
            card = screen_bolted_connection(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        else:
            card = screen_welded_connection(member, required_safety_factor=required_safety_factor)
        entries.extend(card.entries)
    return Scorecard(entries=tuple(entries))
