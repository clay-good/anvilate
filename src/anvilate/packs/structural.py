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
    cantilever_center_patch_load,
    cantilever_end_load,
    cantilever_offset_load,
    cantilever_partial_uniform_load,
    cantilever_triangular_load,
    cantilever_triangular_load_peak_at_tip,
    cantilever_uniform_load,
    circular_area,
    deflection_scorecard,
    euler_critical_stress,
    fixed_fixed_center_load,
    fixed_fixed_center_patch_load,
    fixed_fixed_offset_load,
    fixed_fixed_partial_uniform_load,
    fixed_fixed_triangular_load,
    fixed_fixed_uniform_load,
    fixed_pinned_center_load,
    fixed_pinned_center_patch_load,
    fixed_pinned_offset_load,
    fixed_pinned_partial_uniform_load,
    fixed_pinned_triangular_load,
    fixed_pinned_triangular_load_peak_at_prop,
    fixed_pinned_uniform_load,
    johnson_critical_stress,
    simply_supported_center_load,
    simply_supported_center_patch_load,
    simply_supported_offset_load,
    simply_supported_partial_uniform_load,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    slenderness_ratio,
    strength_scorecard,
    transition_slenderness,
    von_mises_plane_stress,
)
from ..scorecard import Scorecard, ScorecardEntry
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
    "BasePlate",
    "screen_base_plate",
    "LiftingLug",
    "screen_lifting_lug",
    "GussetPlate",
    "screen_gusset_plate",
    "TensionMember",
    "screen_tension_member",
    "BeamColumnMember",
    "screen_beam_column",
    "ConcreteBearing",
    "screen_concrete_bearing",
    "ShearPlate",
    "screen_shear_plate",
    "StructuralMember",
    "screen_structure",
]

# AISC §J4.3 block-shear rupture: 0.6·Fu·Anv (shear) + Fu·Ant (tension), Ubs=1.
_BLOCK_SHEAR_SHEAR_FRACTION = 0.6

# AISC §J8 nominal concrete bearing on a plate is 0.85·f'c (no confinement bonus).
_CONCRETE_BEARING_FRACTION = 0.85

# The effective throat of a fillet weld is 0.707 (= 1/√2) of its leg size.
_FILLET_THROAT_FACTOR = 0.707
# AISC allowable/nominal fillet-weld shear is 0.6 of the electrode strength F_EXX.
_WELD_SHEAR_FRACTION = 0.6

# Distortion-energy shear-yield fraction of tensile yield (τ_y ≈ 0.577·S_y).
_SHEAR_YIELD_FRACTION = 0.577

# AISC §J3.10 bolt-hole tear-out: R_n = 1.2·l_c·t·Fu on the clear distance to the
# edge, capped by bearing deformation at 2.4·d·t·Fu.
_TEAROUT_CLEAR_FRACTION = 1.2
_TEAROUT_BEARING_CAP_FRACTION = 2.4

# AISC 360-16 clauses each screen cites on its scorecard entry (the discipline
# pack, not the code-agnostic analysis layer, owns these references).
_CLAUSE_FLEXURE = "AISC 360-16 Ch. F"
_CLAUSE_DEFLECTION = "AISC 360-16 §L3"
_CLAUSE_COMPRESSION = "AISC 360-16 Ch. E"
_CLAUSE_BOLT_SHEAR = "AISC 360-16 §J3.6"
_CLAUSE_BOLT_COMBINED = "AISC 360-16 §J3.7"
_CLAUSE_BEARING = "AISC 360-16 §J3.10"
_CLAUSE_WELD = "AISC 360-16 §J2.4"
_CLAUSE_BEARING_CONCRETE = "AISC 360-16 §J8"
_CLAUSE_BASEPLATE_BENDING = "AISC Design Guide 1"
_CLAUSE_LUG = "ASME BTH-1 §3-3"
_CLAUSE_BLOCK_SHEAR = "AISC 360-16 §J4.3"
_CLAUSE_SHEAR = "AISC 360-16 §J4.2"
_SHEAR_STRENGTH_FRACTION = 0.60  # 0.60·Fy (yield) / 0.60·Fu (rupture) on the shear area
_CLAUSE_TENSION = "AISC 360-16 §D2"
_CLAUSE_INTERACTION = "AISC 360-16 §H1.1"
_CLAUSE_CONCRETE_BEARING_ACI = "ACI 318-19 §22.8.3"
_ACI_BEARING_FRACTION = 0.85  # bearing strength coefficient 0.85·f'c
_ACI_CONFINEMENT_CAP = 2.0  # sqrt(A2/A1) is capped at 2 (ACI §22.8.3.2)


class Support(StrEnum):
    """A beam's end-support condition."""

    CANTILEVER = "cantilever"
    SIMPLY_SUPPORTED = "simply_supported"
    FIXED_FIXED = "fixed_fixed"
    FIXED_PINNED = "fixed_pinned"  # a propped cantilever: one wall, one prop


class LoadType(StrEnum):
    """How the member is loaded: a single point load, a uniform distributed load,
    or a linearly varying (triangular) one — zero at one support, peaking at the
    other (at the fixed end on a cantilever or fixed-pinned member), as
    hydrostatic pressure loads a stiffener."""

    POINT = "point"
    DISTRIBUTED = "distributed"
    TRIANGULAR = "triangular"


# (support, load_type) -> the analysis check and the keyword its load takes.
_POINT_CHECKS = {
    Support.CANTILEVER: cantilever_end_load,
    Support.SIMPLY_SUPPORTED: simply_supported_center_load,
    Support.FIXED_FIXED: fixed_fixed_center_load,
    Support.FIXED_PINNED: fixed_pinned_center_load,
}
_DISTRIBUTED_CHECKS = {
    Support.CANTILEVER: cantilever_uniform_load,
    Support.SIMPLY_SUPPORTED: simply_supported_uniform_load,
    Support.FIXED_FIXED: fixed_fixed_uniform_load,
    Support.FIXED_PINNED: fixed_pinned_uniform_load,
}
_OFFSET_POINT_CHECKS = {
    Support.CANTILEVER: cantilever_offset_load,
    Support.SIMPLY_SUPPORTED: simply_supported_offset_load,
    Support.FIXED_FIXED: fixed_fixed_offset_load,
    Support.FIXED_PINNED: fixed_pinned_offset_load,
}
_TRIANGULAR_CHECKS = {
    Support.CANTILEVER: cantilever_triangular_load,
    Support.SIMPLY_SUPPORTED: simply_supported_triangular_load,
    Support.FIXED_FIXED: fixed_fixed_triangular_load,
    Support.FIXED_PINNED: fixed_pinned_triangular_load,
}
_PARTIAL_UDL_CHECKS = {
    Support.CANTILEVER: cantilever_partial_uniform_load,
    Support.SIMPLY_SUPPORTED: simply_supported_partial_uniform_load,
    Support.FIXED_FIXED: fixed_fixed_partial_uniform_load,
    Support.FIXED_PINNED: fixed_pinned_partial_uniform_load,
}
_CENTER_PATCH_CHECKS = {
    Support.CANTILEVER: cantilever_center_patch_load,
    Support.SIMPLY_SUPPORTED: simply_supported_center_patch_load,
    Support.FIXED_FIXED: fixed_fixed_center_patch_load,
    Support.FIXED_PINNED: fixed_pinned_center_patch_load,
}
# A triangle's mirror orientation (peak away from the wall) is only distinct on
# the two supports with a wall; simply-supported and fixed-fixed are symmetric.
_MIRRORED_TRIANGULAR_CHECKS = {
    Support.CANTILEVER: cantilever_triangular_load_peak_at_tip,
    Support.FIXED_PINNED: fixed_pinned_triangular_load_peak_at_prop,
}


class BeamMember(BaseModel):
    """A structural beam member and everything a T1 screen needs to check it.

    ``load`` is a force for a ``point`` member and a force-per-length for a
    ``distributed`` or ``triangular`` one (the triangle's peak intensity — at
    either support on a simply-supported member, at the fixed end on a
    cantilever or fixed-pinned member, where the wall moment governs) — the
    model validates the dimension matches ``load_type``.
    ``material`` is a database id (its E and yield drive the checks). An optional
    ``load_position`` places a point load away from its default position — off
    mid-span on a simply-supported or fixed-fixed member (measured from either
    support), short of the tip on a cantilever (measured from the fixed end), or
    anywhere on a fixed-pinned member (measured from the propped end). Only
    point loads accept it. An optional ``loaded_length`` restricts a distributed
    load to a patch of that length adjacent to one support (the fixed end on a
    cantilever or fixed-pinned member) instead of the full span — encoded for
    every support condition, but only for distributed loads. Setting
    ``patch_centered`` moves that patch to mid-span (a machine footprint in the
    middle of the member rather than parked against a support); it requires a
    ``loaded_length``. Setting ``triangle_mirrored`` flips a triangular load
    end-for-end so it peaks away from the wall — at the tip of a cantilever or
    the prop of a fixed-pinned member, the only supports where the orientation
    is distinct (simply-supported and fixed-fixed members are symmetric).
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
    load_position: Quantity | None = None  # a point load may sit off mid-span
    loaded_length: Quantity | None = None  # a distributed load may cover a patch
    patch_centered: bool = False  # the patch may sit at mid-span instead of at a support
    triangle_mirrored: bool = False  # a triangle may peak at the tip/prop instead of the wall

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
        if self.load_position is not None:
            if not self.load_position.has_dimension("[length]"):
                raise ValueError(
                    f"load_position must be a [length] quantity; got {self.load_position}"
                )
            if self.load_type is not LoadType.POINT:
                raise ValueError(
                    "load_position is only supported for a point load; got "
                    f"{self.support.value}/{self.load_type.value}"
                )
        if self.loaded_length is not None:
            if not self.loaded_length.has_dimension("[length]"):
                raise ValueError(
                    f"loaded_length must be a [length] quantity; got {self.loaded_length}"
                )
            if self.load_type is not LoadType.DISTRIBUTED:
                raise ValueError(
                    "loaded_length is only encoded for a distributed load; got "
                    f"{self.support.value}/{self.load_type.value}"
                )
        if self.patch_centered and self.loaded_length is None:
            raise ValueError("patch_centered requires a loaded_length")
        if self.triangle_mirrored and (
            self.load_type is not LoadType.TRIANGULAR
            or self.support not in _MIRRORED_TRIANGULAR_CHECKS
        ):
            raise ValueError(
                "triangle_mirrored is only encoded for a cantilever or fixed-pinned "
                f"triangular load; got {self.support.value}/{self.load_type.value}"
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
    if member.load_position is not None:
        result = _OFFSET_POINT_CHECKS[member.support](
            force=member.load, load_position=member.load_position, **common
        )
    elif member.load_type is LoadType.POINT:
        result = _POINT_CHECKS[member.support](force=member.load, **common)
    elif member.load_type is LoadType.TRIANGULAR:
        checks = _MIRRORED_TRIANGULAR_CHECKS if member.triangle_mirrored else _TRIANGULAR_CHECKS
        result = checks[member.support](peak_distributed_load=member.load, **common)
    elif member.loaded_length is not None:
        checks = _CENTER_PATCH_CHECKS if member.patch_centered else _PARTIAL_UDL_CHECKS
        result = checks[member.support](
            distributed_load=member.load, loaded_length=member.loaded_length, **common
        )
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
    An optional ``tension`` (a hanger or prying pull along the bolt axis) adds a
    bolt tension check and the §J3.7 combined tension-plus-shear interaction.
    An optional ``edge_distance`` (bolt center to the plate edge, in the load
    direction) adds the §J3.10 bolt-hole tear-out check.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    bolt_diameter: Quantity
    plate_thickness: Quantity
    load: Quantity
    bolt_material: str
    plate_material: str
    shear_planes: int = 1
    tension: Quantity | None = None
    edge_distance: Quantity | None = None

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
        if self.tension is not None:
            if not self.tension.has_dimension("[force]"):
                raise ValueError(f"tension must be a [force] quantity; got {self.tension}")
            if self.tension.to("N").magnitude < 0:
                raise ValueError(f"tension must be non-negative; got {self.tension}")
        if self.shear_planes < 1:
            raise ValueError(f"shear_planes must be a positive integer; got {self.shear_planes}")
        if self.edge_distance is not None:
            if not self.edge_distance.has_dimension("[length]"):
                raise ValueError(
                    f"edge_distance must be a [length] quantity; got {self.edge_distance}"
                )
            if self.edge_distance.to("mm").magnitude <= self.bolt_diameter.to("mm").magnitude / 2:
                raise ValueError(
                    f"edge_distance ({self.edge_distance}) must exceed half the bolt "
                    f"diameter ({self.bolt_diameter}) — the hole would break the edge"
                )
        return self


def screen_bolted_connection(
    connection: BoltedConnection,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`BoltedConnection`'s failure modes into a scorecard.

    Screens the bolt shear stress against the bolt's shear yield (0.577·S_y) and
    the plate bearing stress against the plate's yield, both at
    ``required_safety_factor``. If the connection declares an ``edge_distance``,
    the §J3.10 bolt-hole tear-out follows: R_n = 1.2·l_c·t·Fu on the clear distance
    l_c = edge_distance − d/2 (hole taken at the shank diameter), capped by bearing
    deformation at 2.4·d·t·Fu. If it declares a ``tension``, two more entries
    follow: the bolt's direct tensile stress against its yield (§J3.6) and the
    von Mises combined tension-plus-shear equivalent stress (§J3.7 combined
    loading). ``materials`` defaults to the bundled database.
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
    entries = [
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
    ]
    if connection.edge_distance is not None:
        d_mm = connection.bolt_diameter.to("mm").magnitude
        t_mm = connection.plate_thickness.to("mm").magnitude
        fu = plate.ultimate_strength.quantity.to("MPa").magnitude
        clear = connection.edge_distance.to("mm").magnitude - d_mm / 2
        capacity = min(
            _TEAROUT_CLEAR_FRACTION * clear * t_mm * fu,
            _TEAROUT_BEARING_CAP_FRACTION * d_mm * t_mm * fu,
        )
        load_n = connection.load.to("N").magnitude
        tearout_sf = capacity / load_n if load_n > 0 else float("inf")
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{connection.name} edge tear-out",
                computed=tearout_sf,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_BEARING})
        )
    if connection.tension is not None:
        tensile = axial_stress(
            force=connection.tension, area=circular_area(connection.bolt_diameter)
        )
        combined = von_mises_plane_stress(
            sigma_x=tensile, sigma_y=Quantity(magnitude=0.0, unit="MPa"), tau_xy=shear
        )
        entries.append(
            strength_scorecard(
                f"{connection.name} bolt tension",
                stress=tensile,
                allowable=bolt.yield_strength.quantity,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_BOLT_SHEAR})
        )
        entries.append(
            strength_scorecard(
                f"{connection.name} combined tension+shear",
                stress=combined,
                allowable=bolt.yield_strength.quantity,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_BOLT_COMBINED})
        )
    return Scorecard(entries=tuple(entries))


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


class BasePlate(BaseModel):
    """A column base plate bearing on a concrete footing.

    ``width`` B and ``depth`` N are the plate's plan dimensions, ``axial_load`` P
    the column load it spreads, and ``concrete_strength`` the footing's f'c. The
    bearing pressure P/(B·N) is screened against the concrete bearing capacity
    0.85·f'c (AISC §J8, no confinement bonus).

    The plate-bending thickness check is added when the optional plate details are
    given: ``plate_thickness`` t, ``cantilever`` l (the plate overhang beyond the
    column), and ``plate_material`` (a database id). The cantilevered plate bends
    under the bearing pressure, σ = 3·f_p·l²/t², screened against the plate yield.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    width: Quantity
    depth: Quantity
    axial_load: Quantity
    concrete_strength: Quantity
    plate_thickness: Quantity | None = None
    cantilever: Quantity | None = None
    plate_material: str | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> BasePlate:
        for value, name in ((self.width, "width"), (self.depth, "depth")):
            if not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        if not self.axial_load.has_dimension("[force]"):
            raise ValueError(f"axial_load must be a [force] quantity; got {self.axial_load}")
        if not self.concrete_strength.has_dimension("[pressure]"):
            raise ValueError(
                f"concrete_strength must be a [pressure] quantity; got {self.concrete_strength}"
            )
        bending_fields = (self.plate_thickness, self.cantilever, self.plate_material)
        if any(f is not None for f in bending_fields) and not all(
            f is not None for f in bending_fields
        ):
            raise ValueError(
                "the plate-bending check needs plate_thickness, cantilever, and "
                "plate_material together, or none of them"
            )
        for value, name in (
            (self.plate_thickness, "plate_thickness"),
            (self.cantilever, "cantilever"),
        ):
            if value is not None and not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        return self


def screen_base_plate(
    plate: BasePlate,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`BasePlate`'s concrete bearing (and plate bending) into a card.

    The bearing pressure f_p = P/(B·N) is screened against the concrete bearing
    capacity 0.85·f'c (AISC §J8). When the plate details are given, the cantilevered
    plate's bending stress σ = 3·f_p·l²/t² is also screened against the plate yield
    (AISC Design Guide 1). Both at ``required_safety_factor``; ``materials`` defaults
    to the bundled database.
    """
    area = plate.width.to("mm").magnitude * plate.depth.to("mm").magnitude
    bearing_mpa = plate.axial_load.to("N").magnitude / area
    bearing = Quantity(magnitude=bearing_mpa, unit="MPa")
    capacity = Quantity(
        magnitude=_CONCRETE_BEARING_FRACTION * plate.concrete_strength.to("MPa").magnitude,
        unit="MPa",
    )
    entries = [
        strength_scorecard(
            f"{plate.name} concrete bearing",
            stress=bearing,
            allowable=capacity,
            required=required_safety_factor,
        ).model_copy(update={"reference": _CLAUSE_BEARING_CONCRETE})
    ]
    if plate.plate_thickness is not None:
        materials = materials or default_materials_db()
        plate_yield = materials.get(plate.plate_material).yield_strength.quantity
        cantilever = plate.cantilever.to("mm").magnitude
        thickness = plate.plate_thickness.to("mm").magnitude
        plate_bending = Quantity(
            magnitude=3 * bearing_mpa * cantilever**2 / thickness**2, unit="MPa"
        )
        entries.append(
            strength_scorecard(
                f"{plate.name} plate bending",
                stress=plate_bending,
                allowable=plate_yield,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_BASEPLATE_BENDING})
        )
    return Scorecard(entries=tuple(entries))


class LiftingLug(BaseModel):
    """A lifting lug (pad eye) loaded in tension through a pin hole.

    ``width`` is the lug width across the hole, ``hole_diameter`` the pin hole,
    ``thickness`` the plate thickness, and ``load`` the lifted force. Two limit
    states are screened: net-section tension across the reduced width (W−d)·t and
    bearing on the pin d·t, both against the lug material's yield (ASME BTH-1).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    width: Quantity
    hole_diameter: Quantity
    thickness: Quantity
    load: Quantity
    material: str

    @model_validator(mode="after")
    def _well_formed(self) -> LiftingLug:
        for value, name in (
            (self.width, "width"),
            (self.hole_diameter, "hole_diameter"),
            (self.thickness, "thickness"),
        ):
            if not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        if not self.load.has_dimension("[force]"):
            raise ValueError(f"load must be a [force] quantity; got {self.load}")
        if self.hole_diameter.to("mm").magnitude >= self.width.to("mm").magnitude:
            raise ValueError(
                f"hole_diameter ({self.hole_diameter}) must be below the lug width ({self.width})"
            )
        return self


def screen_lifting_lug(
    lug: LiftingLug,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`LiftingLug`'s tension and bearing limit states.

    Screens the net-section tension P/((W−d)·t) and the pin bearing P/(d·t), both
    against the lug material's yield at ``required_safety_factor`` (ASME BTH-1).
    ``materials`` defaults to the bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(lug.material)
    yield_strength = record.yield_strength.quantity

    width = lug.width.to("mm").magnitude
    hole = lug.hole_diameter.to("mm").magnitude
    thickness = lug.thickness.to("mm").magnitude
    force = lug.load.to("N").magnitude

    net_tension = Quantity(magnitude=force / ((width - hole) * thickness), unit="MPa")
    bearing = bearing_stress(force=lug.load, diameter=lug.hole_diameter, thickness=lug.thickness)
    return Scorecard(
        entries=(
            strength_scorecard(
                f"{lug.name} net tension",
                stress=net_tension,
                allowable=yield_strength,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_LUG}),
            strength_scorecard(
                f"{lug.name} pin bearing",
                stress=bearing,
                allowable=yield_strength,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_LUG}),
        )
    )


class GussetPlate(BaseModel):
    """A gusset (or connection element) checked for block-shear rupture.

    ``net_shear_area`` A_nv and ``net_tension_area`` A_nt are the areas along the
    tear-out failure path (from the bolt pattern geometry); ``load`` is the force
    transferred. The block-shear capacity R_n = 0.6·Fu·A_nv + Fu·A_nt (AISC §J4.3,
    Ubs = 1) uses the material's ultimate strength.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    net_shear_area: Quantity
    net_tension_area: Quantity
    load: Quantity
    material: str

    @model_validator(mode="after")
    def _well_formed(self) -> GussetPlate:
        for value, name in (
            (self.net_shear_area, "net_shear_area"),
            (self.net_tension_area, "net_tension_area"),
        ):
            if not value.has_dimension("[length]**2"):
                raise ValueError(f"{name} must be an area ([length]**2); got {value}")
        if not self.load.has_dimension("[force]"):
            raise ValueError(f"load must be a [force] quantity; got {self.load}")
        return self


def screen_gusset_plate(
    gusset: GussetPlate,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`GussetPlate` for block-shear rupture into a scorecard.

    The block-shear capacity R_n = 0.6·Fu·A_nv + Fu·A_nt is compared to the
    transferred load; the safety factor is R_n / load, judged against
    ``required_safety_factor`` (AISC §J4.3). ``materials`` defaults to the bundled
    database.
    """
    materials = materials or default_materials_db()
    ultimate = materials.get(gusset.material).ultimate_strength.quantity.to("MPa").magnitude
    shear_area = gusset.net_shear_area.to("mm**2").magnitude
    tension_area = gusset.net_tension_area.to("mm**2").magnitude
    capacity_n = ultimate * (_BLOCK_SHEAR_SHEAR_FRACTION * shear_area + tension_area)
    load_n = gusset.load.to("N").magnitude
    safety = capacity_n / load_n if load_n > 0 else float("inf")
    entry = ScorecardEntry.from_safety_factor(
        f"{gusset.name} block shear", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _CLAUSE_BLOCK_SHEAR})
    return Scorecard(entries=(entry,))


class TensionMember(BaseModel):
    """An axially loaded tension member checked for the two AISC §D2 limit states.

    A rod, angle, or plate carrying ``load`` in tension. ``gross_area`` A_g is the
    full cross-section; ``net_area`` A_n is the area after deducting bolt holes.
    ``shear_lag_factor`` U (default 1.0) reduces the net area to the effective net
    area A_e = U·A_n where the load engages only part of the section (§D3). Two
    limit states are screened: tensile yielding on the gross section (P/A_g vs Fy)
    and tensile rupture on the effective net section (P/A_e vs Fu).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    gross_area: Quantity
    net_area: Quantity
    load: Quantity
    material: str
    shear_lag_factor: float = 1.0

    @model_validator(mode="after")
    def _well_formed(self) -> TensionMember:
        for value, name in (
            (self.gross_area, "gross_area"),
            (self.net_area, "net_area"),
        ):
            if not value.has_dimension("[length]**2"):
                raise ValueError(f"{name} must be an area ([length]**2); got {value}")
        if not self.load.has_dimension("[force]"):
            raise ValueError(f"load must be a [force] quantity; got {self.load}")
        if self.net_area.to("mm**2").magnitude > self.gross_area.to("mm**2").magnitude:
            raise ValueError(
                f"net_area ({self.net_area}) cannot exceed gross_area ({self.gross_area})"
            )
        if not 0.0 < self.shear_lag_factor <= 1.0:
            raise ValueError(f"shear_lag_factor must be in (0, 1]; got {self.shear_lag_factor}")
        return self


def screen_tension_member(
    member: TensionMember,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`TensionMember`'s gross-yield and net-rupture limit states.

    Gross-section yielding screens P/A_g against the material yield Fy (§D2(a));
    net-section rupture screens P/A_e against the ultimate Fu (§D2(b)) with the
    effective net area A_e = U·A_n. The lesser safety factor governs the member.
    ``materials`` defaults to the bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(member.material)

    force = member.load.to("N").magnitude
    gross = member.gross_area.to("mm**2").magnitude
    effective_net = member.shear_lag_factor * member.net_area.to("mm**2").magnitude

    gross_stress = Quantity(magnitude=force / gross, unit="MPa")
    net_stress = Quantity(magnitude=force / effective_net, unit="MPa")
    return Scorecard(
        entries=(
            strength_scorecard(
                f"{member.name} gross yielding",
                stress=gross_stress,
                allowable=record.yield_strength.quantity,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_TENSION}),
            strength_scorecard(
                f"{member.name} net rupture",
                stress=net_stress,
                allowable=record.ultimate_strength.quantity,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_TENSION}),
        )
    )


class BeamColumnMember(BaseModel):
    """A member carrying combined axial compression and bending (a beam-column).

    Screened by the AISC §H1.1 interaction equation. ``section``'s ``second_moment``
    is the buckling (weak) axis; ``end_condition`` sets the effective-length factor;
    ``axial_load`` is the compression and ``moment`` the applied bending moment;
    ``material`` a database id (E and yield drive both capacities).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    section: CrossSection
    length: Quantity
    axial_load: Quantity
    moment: Quantity
    material: str
    end_condition: ColumnEnd = ColumnEnd.PINNED_PINNED

    @model_validator(mode="after")
    def _well_formed(self) -> BeamColumnMember:
        if not self.length.has_dimension("[length]"):
            raise ValueError(f"length must be a [length] quantity; got {self.length}")
        if not self.axial_load.has_dimension("[force]"):
            raise ValueError(f"axial_load must be a [force] quantity; got {self.axial_load}")
        if not self.moment.has_dimension("[force] * [length]"):
            raise ValueError(
                f"moment must be a [force]*[length] quantity; got {self.moment.dimensionality}"
            )
        return self


def screen_beam_column(
    member: BeamColumnMember,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`BeamColumnMember` by the AISC §H1.1 interaction equation.

    The available axial strength Pc is the buckling critical stress (Euler or
    Johnson, chosen by slenderness, as in :func:`screen_column_member`) times the
    area; the available flexural strength Mc is the first-yield moment Fy·S. The
    §H1.1 interaction ratio — Pr/Pc + 8/9·Mr/Mc when Pr/Pc ≥ 0.2, else Pr/(2·Pc) +
    Mr/Mc — is unity at capacity, so its reciprocal is the safety factor screened
    against ``required_safety_factor``. ``materials`` defaults to the bundled
    database.
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
    else:
        critical = johnson_critical_stress(
            yield_strength=yield_strength, elastic_modulus=modulus, slenderness_ratio=lam
        )

    axial_capacity = critical.to("MPa").magnitude * member.section.area.to("mm**2").magnitude
    flexural_capacity = (
        yield_strength.to("MPa").magnitude * member.section.section_modulus.to("mm**3").magnitude
    )
    pr_pc = member.axial_load.to("N").magnitude / axial_capacity
    mr_mc = member.moment.to("N*mm").magnitude / flexural_capacity
    if pr_pc >= 0.2:
        interaction = pr_pc + (8.0 / 9.0) * mr_mc
    else:
        interaction = pr_pc / 2.0 + mr_mc

    safety = float("inf") if interaction == 0 else 1.0 / interaction
    entry = ScorecardEntry.from_safety_factor(
        f"{member.name} interaction", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _CLAUSE_INTERACTION})
    return Scorecard(entries=(entry,))


class ConcreteBearing(BaseModel):
    """A plate bearing on concrete, checked by the ACI 318 confined-bearing rule.

    When the loaded area ``bearing_area`` A₁ (a base plate or pedestal cap) is
    smaller than the ``support_area`` A₂ of the concrete beneath it, the surrounding
    concrete confines the bearing zone and raises its strength by √(A₂/A₁), capped
    at 2. ``concrete_strength`` is the compressive strength f′c; ``load`` the force
    delivered. The nominal bearing strength is 0.85·f′c·A₁·√(A₂/A₁).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    bearing_area: Quantity
    support_area: Quantity
    concrete_strength: Quantity
    load: Quantity

    @model_validator(mode="after")
    def _well_formed(self) -> ConcreteBearing:
        for value, name in (
            (self.bearing_area, "bearing_area"),
            (self.support_area, "support_area"),
        ):
            if not value.has_dimension("[length]**2"):
                raise ValueError(f"{name} must be an area ([length]**2); got {value}")
        if not self.concrete_strength.has_dimension("[pressure]"):
            raise ValueError(
                f"concrete_strength must be a [pressure] quantity; got {self.concrete_strength}"
            )
        if not self.load.has_dimension("[force]"):
            raise ValueError(f"load must be a [force] quantity; got {self.load}")
        if self.support_area.to("mm**2").magnitude < self.bearing_area.to("mm**2").magnitude:
            raise ValueError(
                f"support_area ({self.support_area}) cannot be smaller than the "
                f"bearing_area ({self.bearing_area})"
            )
        return self


def screen_concrete_bearing(
    bearing: ConcreteBearing,
    *,
    required_safety_factor: float,
) -> Scorecard:
    """Screen a :class:`ConcreteBearing` by the ACI 318 §22.8.3 confined-bearing rule.

    The nominal bearing strength Bn = 0.85·f′c·A₁·√(A₂/A₁), with the confinement
    factor √(A₂/A₁) capped at 2, is compared to the delivered load; the safety
    factor Bn/load is judged against ``required_safety_factor``.
    """
    a1 = bearing.bearing_area.to("mm**2").magnitude
    a2 = bearing.support_area.to("mm**2").magnitude
    fc = bearing.concrete_strength.to("MPa").magnitude
    load_n = bearing.load.to("N").magnitude

    confinement = min((a2 / a1) ** 0.5, _ACI_CONFINEMENT_CAP)
    capacity_n = _ACI_BEARING_FRACTION * fc * a1 * confinement
    safety = capacity_n / load_n if load_n > 0 else float("inf")
    entry = ScorecardEntry.from_safety_factor(
        f"{bearing.name} concrete bearing", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _CLAUSE_CONCRETE_BEARING_ACI})
    return Scorecard(entries=(entry,))


class ShearPlate(BaseModel):
    """A plate element loaded in direct shear (a shear tab, coped-beam web, bracket).

    Screened for the two AISC §J4.2 limit states: shear yielding on the gross shear
    area ``gross_shear_area`` A_gv (0.60·Fy·A_gv) and shear rupture on the net shear
    area ``net_shear_area`` A_nv after bolt-hole deductions (0.60·Fu·A_nv). ``load``
    is the shear force transferred; ``material`` a database id (Fy and Fu drive the
    two checks). This is the pure-shear limit state, distinct from block-shear
    tear-out (§J4.3) and bolt shear (§J3.6).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    gross_shear_area: Quantity
    net_shear_area: Quantity
    load: Quantity
    material: str

    @model_validator(mode="after")
    def _well_formed(self) -> ShearPlate:
        for value, name in (
            (self.gross_shear_area, "gross_shear_area"),
            (self.net_shear_area, "net_shear_area"),
        ):
            if not value.has_dimension("[length]**2"):
                raise ValueError(f"{name} must be an area ([length]**2); got {value}")
        if not self.load.has_dimension("[force]"):
            raise ValueError(f"load must be a [force] quantity; got {self.load}")
        if self.net_shear_area.to("mm**2").magnitude > self.gross_shear_area.to("mm**2").magnitude:
            raise ValueError(
                f"net_shear_area ({self.net_shear_area}) cannot exceed the "
                f"gross_shear_area ({self.gross_shear_area})"
            )
        return self


def screen_shear_plate(
    plate: ShearPlate,
    *,
    required_safety_factor: float,
    materials: MaterialsDatabase | None = None,
) -> Scorecard:
    """Screen a :class:`ShearPlate`'s two AISC §J4.2 shear limit states.

    Shear yielding compares 0.60·Fy·A_gv to the load; shear rupture compares
    0.60·Fu·A_nv. Each safety factor (capacity/load) is judged against
    ``required_safety_factor``; the lesser governs. ``materials`` defaults to the
    bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(plate.material)
    fy = record.yield_strength.quantity.to("MPa").magnitude
    fu = record.ultimate_strength.quantity.to("MPa").magnitude
    gross = plate.gross_shear_area.to("mm**2").magnitude
    net = plate.net_shear_area.to("mm**2").magnitude
    load_n = plate.load.to("N").magnitude

    yield_capacity = _SHEAR_STRENGTH_FRACTION * fy * gross
    rupture_capacity = _SHEAR_STRENGTH_FRACTION * fu * net
    yield_sf = yield_capacity / load_n if load_n > 0 else float("inf")
    rupture_sf = rupture_capacity / load_n if load_n > 0 else float("inf")
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                f"{plate.name} shear yielding", computed=yield_sf, required=required_safety_factor
            ).model_copy(update={"reference": _CLAUSE_SHEAR}),
            ScorecardEntry.from_safety_factor(
                f"{plate.name} shear rupture", computed=rupture_sf, required=required_safety_factor
            ).model_copy(update={"reference": _CLAUSE_SHEAR}),
        )
    )


StructuralMember = (
    BeamMember
    | ColumnMember
    | BoltedConnection
    | WeldedConnection
    | BasePlate
    | LiftingLug
    | GussetPlate
    | TensionMember
    | BeamColumnMember
    | ConcreteBearing
    | ShearPlate
)


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
        elif isinstance(member, WeldedConnection):
            card = screen_welded_connection(member, required_safety_factor=required_safety_factor)
        elif isinstance(member, BasePlate):
            card = screen_base_plate(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        elif isinstance(member, LiftingLug):
            card = screen_lifting_lug(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        elif isinstance(member, GussetPlate):
            card = screen_gusset_plate(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        elif isinstance(member, TensionMember):
            card = screen_tension_member(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        elif isinstance(member, BeamColumnMember):
            card = screen_beam_column(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        elif isinstance(member, ConcreteBearing):
            card = screen_concrete_bearing(member, required_safety_factor=required_safety_factor)
        else:
            card = screen_shear_plate(
                member, required_safety_factor=required_safety_factor, materials=materials
            )
        entries.extend(card.entries)
    return Scorecard(entries=tuple(entries))
