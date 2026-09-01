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

from pydantic import ConfigDict, model_validator

from ..analysis import (
    ColumnEnd,
    CrossSection,
    aisc_flexural_buckling_stress,
    axial_stress,
    bearing_stress,
    bolt_shear_stress,
    cantilever_center_patch_load,
    cantilever_end_load,
    cantilever_end_moment,
    cantilever_fundamental_frequency,
    cantilever_offset_load,
    cantilever_offset_moment,
    cantilever_partial_uniform_load,
    cantilever_triangular_load,
    cantilever_triangular_load_peak_at_tip,
    cantilever_uniform_load,
    circular_area,
    deflection_scorecard,
    euler_critical_stress,
    fillet_weld_throat_stress,
    fixed_fixed_center_load,
    fixed_fixed_center_patch_load,
    fixed_fixed_fundamental_frequency,
    fixed_fixed_offset_load,
    fixed_fixed_partial_uniform_load,
    fixed_fixed_triangular_load,
    fixed_fixed_uniform_load,
    fixed_pinned_center_load,
    fixed_pinned_center_patch_load,
    fixed_pinned_end_moment,
    fixed_pinned_fundamental_frequency,
    fixed_pinned_offset_load,
    fixed_pinned_partial_uniform_load,
    fixed_pinned_triangular_load,
    fixed_pinned_triangular_load_peak_at_prop,
    fixed_pinned_uniform_load,
    frequency_scorecard,
    max_transverse_shear_stress,
    overhang_tip_load,
    overhang_uniform_load,
    simply_supported_center_load,
    simply_supported_center_patch_load,
    simply_supported_end_moment,
    simply_supported_fundamental_frequency,
    simply_supported_offset_load,
    simply_supported_offset_moment,
    simply_supported_partial_uniform_load,
    simply_supported_symmetric_point_loads,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    slenderness_ratio,
    strength_scorecard,
    von_mises_plane_stress,
)
from ..derivation import Derivation, SymbolValue
from ..scorecard import (
    CheckStatus,
    Direction,
    RepairHint,
    Scorecard,
    ScorecardEntry,
)
from ..standards import AllowableBasis, MaterialsDatabase, default_materials_db
from ..units import Quantity
from ._guarded import (
    DESIGN_BASIS,
    DesignAllowable,
    GuardedInputs,
    design_allowable,
    disclosed,
)


def _refused(names: tuple[str, ...], note: str, reference: str | None = None) -> Scorecard:
    """A card of NOT_EVALUATED entries, one per check the screen would have produced.

    Used where a strength feeds a raw formula rather than `strength_scorecard`, so there is
    no `allowable=None` to pass. The check names are kept — a consumer looking for
    "column buckling" must find it saying it could not run, not find nothing at all, which
    is its own kind of silence.
    """
    return Scorecard(
        entries=tuple(
            ScorecardEntry(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail=note,
                reference=reference,
            )
            for name in names
        )
    )


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
_CLAUSE_BEAM_SHEAR = "AISC 360-16 Ch. G"
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
    OVERHANG = "overhang"  # simply supported with the section run past one support


class LoadType(StrEnum):
    """How the member is loaded: a single point load, a uniform distributed load,
    a linearly varying (triangular) one — zero at one support, peaking at the
    other (at the fixed end on a cantilever or fixed-pinned member), as
    hydrostatic pressure loads a stiffener — or an applied end moment (a couple
    a bracket or hub hands the member at the tip of a cantilever, at one
    support of a simply-supported span, or at the prop of a fixed-pinned
    member)."""

    POINT = "point"
    DISTRIBUTED = "distributed"
    TRIANGULAR = "triangular"
    MOMENT = "moment"


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
# An applied end couple is encoded where an end is free to receive one: the tip
# of a cantilever, a support of a simply-supported span, or the prop of a
# fixed-pinned member. A built-in wall absorbs an applied couple directly, so
# fixed-fixed (both ends walls) is not a case.
_MOMENT_CHECKS = {
    Support.CANTILEVER: cantilever_end_moment,
    Support.SIMPLY_SUPPORTED: simply_supported_end_moment,
    Support.FIXED_PINNED: fixed_pinned_end_moment,
}
# A couple away from its default position: short of the tip on a cantilever,
# inside the span on a simply-supported member. A wall absorbs an applied
# couple, so fixed-fixed/fixed-pinned interior couples are not encoded.
_OFFSET_MOMENT_CHECKS = {
    Support.CANTILEVER: cantilever_offset_moment,
    Support.SIMPLY_SUPPORTED: simply_supported_offset_moment,
}
# Peak transverse shear V as a multiple of the load (F for a point load, w*L
# for a distributed/triangular one), from the support reactions of the simple
# full-span cases. Off-default positions, patches, pairs, and couples are not
# tabled — those members get no shear entry rather than a wrong one.
_PEAK_SHEAR_FACTORS = {
    (Support.CANTILEVER, LoadType.POINT): 1.0,
    (Support.SIMPLY_SUPPORTED, LoadType.POINT): 0.5,
    (Support.FIXED_FIXED, LoadType.POINT): 0.5,
    (Support.FIXED_PINNED, LoadType.POINT): 11.0 / 16.0,
    (Support.CANTILEVER, LoadType.DISTRIBUTED): 1.0,
    (Support.SIMPLY_SUPPORTED, LoadType.DISTRIBUTED): 0.5,
    (Support.FIXED_FIXED, LoadType.DISTRIBUTED): 0.5,
    (Support.FIXED_PINNED, LoadType.DISTRIBUTED): 5.0 / 8.0,
    (Support.CANTILEVER, LoadType.TRIANGULAR): 0.5,
    (Support.SIMPLY_SUPPORTED, LoadType.TRIANGULAR): 1.0 / 3.0,
    (Support.FIXED_FIXED, LoadType.TRIANGULAR): 7.0 / 20.0,
    (Support.FIXED_PINNED, LoadType.TRIANGULAR): 2.0 / 5.0,
}

# Distributed-mass fundamental frequency per support (exact Euler-Bernoulli
# eigenvalues), for the optional resonance screen.
_MODAL_CHECKS = {
    Support.CANTILEVER: cantilever_fundamental_frequency,
    Support.SIMPLY_SUPPORTED: simply_supported_fundamental_frequency,
    Support.FIXED_FIXED: fixed_fixed_fundamental_frequency,
    Support.FIXED_PINNED: fixed_pinned_fundamental_frequency,
}


class BeamMember(GuardedInputs):
    """A structural beam member and everything a T1 screen needs to check it.

    ``load`` is a force for a ``point`` member, a force-per-length for a
    ``distributed`` or ``triangular`` one (the triangle's peak intensity — at
    either support on a simply-supported member, at the fixed end on a
    cantilever or fixed-pinned member, where the wall moment governs), and a
    force-times-length couple for a ``moment`` one (applied at the tip of a
    cantilever, at one support of a simply-supported member, or at the prop of
    a fixed-pinned one — every support with an end free to receive a couple) —
    the model validates the dimension matches ``load_type``.
    ``material`` is a database id (its E and yield drive the checks). An optional
    ``load_position`` places a point load away from its default position — off
    mid-span on a simply-supported or fixed-fixed member (measured from either
    support), short of the tip on a cantilever (measured from the fixed end), or
    anywhere on a fixed-pinned member (measured from the propped end). Point
    loads accept it on every support; a moment load accepts it on a
    cantilever (the couple moves short of the tip, measured from the fixed
    end) or a simply-supported member (the couple moves inside the span) —
    a wall absorbs an applied couple, so the other supports reject it.
    An optional ``loaded_length`` restricts a distributed
    load to a patch of that length adjacent to one support (the fixed end on a
    cantilever or fixed-pinned member) instead of the full span — encoded for
    every support condition, but only for distributed loads. Setting
    ``patch_centered`` moves that patch to mid-span (a machine footprint in the
    middle of the member rather than parked against a support); it requires a
    ``loaded_length``. An optional ``pair_offset`` splits a point load into TWO
    equal loads of ``load`` each at that distance from EACH support of a
    simply-supported member (four-point bending — a machine on two skid rails,
    a spreader-beam lift; the only encoded pair case) — it excludes
    ``load_position``, whose single-load meaning it replaces. Setting
    ``triangle_mirrored`` flips a triangular load
    end-for-end so it peaks away from the wall — at the tip of a cantilever or
    the prop of a fixed-pinned member, the only supports where the orientation
    is distinct (simply-supported and fixed-fixed members are symmetric).
    Declaring a ``mass_per_length`` (self-weight plus smeared attachments)
    adds a resonance entry — the support's exact distributed-mass fundamental
    frequency screened against ``min_frequency``. The floor requires the mass;
    a declared mass with no floor surfaces NOT_EVALUATED, never a silent pass.
    An ``overhang`` member is a simply-supported back span of ``length`` whose
    section runs ``overhang_length`` past one support: a ``point`` load sits
    at the free tip and a ``distributed`` one covers the overhang only (the
    dock-edge cases; the shear entry uses the full overhang reaction); other
    load types, positions, patches, and the resonance screen are not encoded
    for it.
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = (
        "load",
        "load_position",
        "pair_offset",
    )

    name: str
    section: CrossSection
    length: Quantity
    support: Support
    load: Quantity
    load_type: LoadType
    material: str
    deflection_limit: Quantity | None = None  # a member may carry its own limit
    load_position: Quantity | None = None  # a point load may sit off mid-span
    pair_offset: Quantity | None = None  # a point load may split into a symmetric pair
    loaded_length: Quantity | None = None  # a distributed load may cover a patch
    overhang_length: Quantity | None = None  # required for (and only for) OVERHANG
    mass_per_length: Quantity | None = None  # enables the resonance screen
    min_frequency: Quantity | None = None  # the resonance floor (needs mass_per_length)
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
        if self.load_type is LoadType.POINT:
            expected = "[force]"
        elif self.load_type is LoadType.MOMENT:
            expected = "[force] * [length]"
        else:
            expected = "[force] / [length]"
        if not self.load.has_dimension(expected):
            raise ValueError(
                f"a {self.load_type.value} load must be a {expected} quantity; got "
                f"{self.load.dimensionality} ({self.load})"
            )
        if self.load_type is LoadType.MOMENT and self.support not in _MOMENT_CHECKS:
            raise ValueError(
                "a moment load is only encoded for a member with an end free to "
                "receive a couple (cantilever, simply-supported, or fixed-pinned); "
                f"got {self.support.value}/{self.load_type.value}"
            )
        if self.load_position is not None:
            if not self.load_position.has_dimension("[length]"):
                raise ValueError(
                    f"load_position must be a [length] quantity; got {self.load_position}"
                )
            if self.load_type is LoadType.MOMENT:
                if self.support not in _OFFSET_MOMENT_CHECKS:
                    raise ValueError(
                        "an off-end couple is only encoded on a cantilever or "
                        "simply-supported member; got "
                        f"{self.support.value}/{self.load_type.value}"
                    )
            elif self.load_type is not LoadType.POINT:
                raise ValueError(
                    "load_position is only supported for a point load; got "
                    f"{self.support.value}/{self.load_type.value}"
                )
        if self.pair_offset is not None:
            if not self.pair_offset.has_dimension("[length]"):
                raise ValueError(f"pair_offset must be a [length] quantity; got {self.pair_offset}")
            if self.load_type is not LoadType.POINT or self.support is not Support.SIMPLY_SUPPORTED:
                raise ValueError(
                    "pair_offset is only encoded for a simply-supported point load; "
                    f"got {self.support.value}/{self.load_type.value}"
                )
            if self.load_position is not None:
                raise ValueError(
                    "pair_offset and load_position are mutually exclusive — a pair "
                    "sits at pair_offset from each support"
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
        if self.support is Support.OVERHANG:
            if self.overhang_length is None:
                raise ValueError("an overhang member requires an overhang_length")
            if not self.overhang_length.has_dimension("[length]"):
                raise ValueError(
                    f"overhang_length must be a [length] quantity; got {self.overhang_length}"
                )
            if self.load_type not in (LoadType.POINT, LoadType.DISTRIBUTED):
                raise ValueError(
                    "an overhang member is only encoded for a tip point load or a "
                    f"distributed load on the overhang; got {self.load_type.value}"
                )
            if (
                self.load_position is not None
                or self.pair_offset is not None
                or self.loaded_length is not None
            ):
                raise ValueError(
                    "load_position, pair_offset, and loaded_length are not encoded "
                    "for an overhang member"
                )
            if self.mass_per_length is not None:
                raise ValueError(
                    "the resonance screen is not encoded for an overhang member "
                    "(no distributed-mass eigenvalue)"
                )
        elif self.overhang_length is not None:
            raise ValueError(
                f"overhang_length is only meaningful for an overhang member; got "
                f"{self.support.value}"
            )
        if self.mass_per_length is not None and not self.mass_per_length.has_dimension(
            "[mass] / [length]"
        ):
            raise ValueError(
                f"mass_per_length must be a [mass] / [length] quantity; got {self.mass_per_length}"
            )
        if self.min_frequency is not None:
            if not self.min_frequency.has_dimension("[frequency]"):
                raise ValueError(
                    f"min_frequency must be a [frequency] quantity; got {self.min_frequency}"
                )
            if self.mass_per_length is None:
                raise ValueError(
                    "min_frequency requires a mass_per_length — the fundamental "
                    "cannot be computed without the member's distributed mass"
                )
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
    required_basis: AllowableBasis = DESIGN_BASIS,
) -> Scorecard:
    """Screen a :class:`BeamMember` and return its scorecard.

    Dispatches on the member's support and load type to the matching closed-form
    beam check, then screens the peak bending stress against the material's yield
    strength (at ``required_safety_factor``) and, when a limit is set, the peak
    deflection against it. The deflection limit is the ``max_deflection`` argument,
    or the member's own ``deflection_limit`` when the argument is omitted. A
    member declaring a ``mass_per_length`` also gets its distributed-mass
    fundamental frequency screened against its ``min_frequency`` floor.
    Simple full-span members whose section records a shear form factor also
    get a transverse-shear entry (τ = k·V/A vs 0.577·Fy); a hand-built
    section surfaces NOT_EVALUATED there, and off-default positions, patches,
    pairs, and couples get no shear entry rather than a wrong one.
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
    if member.support is Support.OVERHANG:
        overhang_common = {
            "back_span": member.length,
            "overhang": member.overhang_length,
            "second_moment": member.section.second_moment,
            "extreme_fibre": member.section.extreme_fibre,
            "elastic_modulus": record.elastic_modulus.quantity,
        }
        if member.load_type is LoadType.POINT:
            result = overhang_tip_load(force=member.load, **overhang_common)
        else:
            result = overhang_uniform_load(distributed_load=member.load, **overhang_common)
    elif member.pair_offset is not None:
        result = simply_supported_symmetric_point_loads(
            force=member.load, load_offset=member.pair_offset, **common
        )
    elif member.load_position is not None and member.load_type is LoadType.MOMENT:
        result = _OFFSET_MOMENT_CHECKS[member.support](
            moment=member.load, load_position=member.load_position, **common
        )
    elif member.load_position is not None:
        result = _OFFSET_POINT_CHECKS[member.support](
            force=member.load, load_position=member.load_position, **common
        )
    elif member.load_type is LoadType.POINT:
        result = _POINT_CHECKS[member.support](force=member.load, **common)
    elif member.load_type is LoadType.MOMENT:
        result = _MOMENT_CHECKS[member.support](moment=member.load, **common)
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

    yield_allowable = design_allowable(
        record, "yield_strength", material_id=member.material, basis=required_basis
    )
    entries = [
        strength_scorecard(
            f"{member.name} bending",
            stress=result.max_bending_stress,
            allowable=yield_allowable.quantity,
            required=required_safety_factor,
            unavailable_detail=yield_allowable.note,
        ).model_copy(
            update={
                "reference": _CLAUSE_FLEXURE,
                # The peak moment depends on the support and load case; the stress
                # it makes on the section does not. The moment is shown as the
                # value the case produced, so the flexure formula reads the same
                # for every one of them.
                "derivation": Derivation(
                    symbolic="σ_b = M · c / I",
                    inputs=(
                        SymbolValue(
                            symbol="M",
                            description=(
                                f"peak bending moment, {member.support.value} beam under "
                                f"{member.load_type.value} load"
                            ),
                            value=result.max_moment,
                            unit="kN*m",
                        ),
                        SymbolValue(
                            symbol="c",
                            description="distance from the neutral axis to the extreme fibre",
                            value=member.section.extreme_fibre,
                        ),
                        SymbolValue(
                            symbol="I",
                            description="second moment of area about the bending axis",
                            value=member.section.second_moment,
                            unit="mm^4",
                        ),
                    ),
                    result=SymbolValue(
                        symbol="σ_b",
                        description="peak bending stress",
                        value=result.max_bending_stress,
                    ),
                    citation=_CLAUSE_FLEXURE,
                ),
            }
        )
    ]
    if max_deflection is not None:
        update: dict = {"reference": _CLAUSE_DEFLECTION}
        if result.deflection_formula is not None:
            update["derivation"] = Derivation(
                symbolic=result.deflection_formula,
                inputs=(
                    SymbolValue(
                        symbol="F" if member.load_type is LoadType.POINT else "w",
                        description=(
                            "applied load"
                            if member.load_type is LoadType.POINT
                            else "distributed load"
                        ),
                        value=member.load,
                    ),
                    SymbolValue(symbol="L", description="span", value=member.length),
                    SymbolValue(
                        symbol="E",
                        description="elastic modulus",
                        value=record.elastic_modulus.quantity,
                        unit="GPa",
                    ),
                    SymbolValue(
                        symbol="I",
                        description="second moment of area",
                        value=member.section.second_moment,
                        unit="mm^4",
                    ),
                ),
                result=SymbolValue(
                    symbol="δ", description="peak deflection", value=result.max_deflection
                ),
                citation=_CLAUSE_DEFLECTION,
            )
        entries.append(
            deflection_scorecard(
                f"{member.name} deflection",
                deflection=result.max_deflection,
                limit=max_deflection,
            ).model_copy(update=update)
        )
    if member.mass_per_length is not None:
        fundamental = _MODAL_CHECKS[member.support](
            mass_per_length=member.mass_per_length,
            length=member.length,
            second_moment=member.section.second_moment,
            elastic_modulus=record.elastic_modulus.quantity,
        )
        entries.append(
            frequency_scorecard(
                f"{member.name} resonance",
                frequency=fundamental,
                min_frequency=member.min_frequency,
            )
        )
    shear_entry = _shear_entry(member, record, required_safety_factor)
    if shear_entry is not None:
        entries.append(shear_entry)
    return disclosed(
        Scorecard(entries=tuple(entries)),
        yield_allowable,
    )


def _shear_entry(member, record, required_safety_factor: float) -> ScorecardEntry | None:
    """The transverse-shear entry for a simple full-span member, or None.

    Only the tabled (support, load_type) cases at their default positions get
    a shear entry — an off-default member gets none rather than a wrong one.
    A tabled member whose section records no shear form factor (hand-built)
    surfaces NOT_EVALUATED, never a silent pass.
    """
    off_default = (
        member.load_position is not None
        or member.pair_offset is not None
        or member.loaded_length is not None
        or member.triangle_mirrored
    )
    if member.support is Support.OVERHANG:
        # The overhang carries its whole load in shear at the inner support -- V = F for a tip
        # point load, w*c for an overhang-only UDL -- but that is only the overhang segment.
        # The BACK SPAN carries the constant shear |R_A| = F*c/L (point) or w*c^2/(2L) (UDL),
        # which OVERTAKES the overhang value once c > L (or c > 2L). Nothing constrains c
        # against L, so a long overhang used to report the short-overhang shear and pass:
        # at c = 4L the reported safety factor was 4x the true one, unconservatively.
        span_mm = member.length.to("mm").magnitude
        overhang_mm = member.overhang_length.to("mm").magnitude
        if member.load_type is LoadType.POINT:
            factor = max(1.0, overhang_mm / span_mm)
        else:
            factor = max(1.0, overhang_mm / (2.0 * span_mm))
        shear_length = member.overhang_length
    else:
        factor = _PEAK_SHEAR_FACTORS.get((member.support, member.load_type))
        shear_length = member.length
    if off_default or factor is None:
        return None
    if member.section.shear_form_factor is None:
        return ScorecardEntry(
            name=f"{member.name} shear",
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — the section records no shear form factor",
            reference=_CLAUSE_BEAM_SHEAR,
        )
    if member.load_type is LoadType.POINT:
        peak_shear = Quantity(magnitude=factor * member.load.to("N").magnitude, unit="N")
    else:
        peak_shear = Quantity(
            magnitude=factor * member.load.to("N/mm").magnitude * shear_length.to("mm").magnitude,
            unit="N",
        )
    shear = max_transverse_shear_stress(
        shear_force=peak_shear,
        area=member.section.area,
        form_factor=member.section.shear_form_factor,
    )
    shear_yield = Quantity(
        magnitude=_SHEAR_YIELD_FRACTION * record.yield_strength.quantity.to("MPa").magnitude,
        unit="MPa",
    )
    derivation = Derivation(
        # The form factor k carries the section shape: 3/2 for a rectangle, 4/3 for
        # a circle — the peak at the neutral axis, not the V/A average.
        symbolic="τ = k · V / A",
        inputs=(
            SymbolValue(
                symbol="k",
                description="section shear form factor, peak over average",
                value=member.section.shear_form_factor,
            ),
            SymbolValue(
                symbol="V",
                description="peak transverse shear force in the span",
                value=peak_shear,
                unit="kN",
            ),
            SymbolValue(symbol="A", description="cross-sectional area", value=member.section.area),
        ),
        result=SymbolValue(symbol="τ", description="peak transverse shear stress", value=shear),
        citation=_CLAUSE_BEAM_SHEAR,
    )
    return strength_scorecard(
        f"{member.name} shear",
        stress=shear,
        allowable=shear_yield,
        required=required_safety_factor,
    ).model_copy(update={"reference": _CLAUSE_BEAM_SHEAR, "derivation": derivation})


class ColumnMember(GuardedInputs):
    """A structural compression member and what a buckling screen needs.

    The screen buckles the member about the least axis ``section`` carries
    (its ``least_radius_of_gyration``) — a strong-axis declaration cannot
    inflate the capacity. A hand-built section with no transverse second
    moment is screened about its declared bending axis, so the caller owns
    the weak-axis choice there. ``end_condition`` sets the effective-length
    factor; ``axial_load`` is the compressive force; ``material`` a database
    id (E and yield drive the screen).
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = ("axial_load",)

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
    required_basis: AllowableBasis = DESIGN_BASIS,
) -> Scorecard:
    """Screen a :class:`ColumnMember` for buckling and return its scorecard.

    Computes the slenderness λ = K·L/r about the section's LEAST radius of gyration —
    a pin-ended column bows whichever way is easiest, whatever axis was declared — and
    takes the AISC 360 §E3 flexural buckling stress from it: F_cr = 0.658^(F_y/F_e)·F_y
    while F_y/F_e ≤ 2.25, and 0.877·F_e above it. The critical stress is screened against
    the applied axial stress (load/area) at ``required_safety_factor``. ``materials``
    defaults to the bundled database.

    This screen used to compute Euler above a transition slenderness and the J. B.
    Johnson parabola below it, while citing §E either way. Those are different curves:
    the old pair ran 9-14% HIGH for a small A36 section, which was enough to flip a
    verdict at a required safety factor of 2.6. The §E3 curve is the one the citation
    names, and its elastic branch carries the 0.877 out-of-straightness knockdown the
    bare Euler stress does not.
    """
    materials = materials or default_materials_db()
    record = materials.get(member.material)
    modulus = record.elastic_modulus.quantity
    column_allowable = design_allowable(
        record, "yield_strength", material_id=member.material, basis=required_basis
    )
    if column_allowable.quantity is None:
        return _refused((f"{member.name} buckling",), column_allowable.note)
    yield_strength = column_allowable.quantity

    effective_length = Quantity(
        magnitude=member.end_condition.factor() * member.length.to("mm").magnitude,
        unit="mm",
    )
    lam = slenderness_ratio(
        effective_length=effective_length,
        radius_of_gyration=member.section.least_radius_of_gyration,
    )
    # AISC 360 §E3, which is what this entry cites. It used to compute Euler above the
    # transition slenderness and the Johnson parabola below it, and stamp the §E citation
    # on the result anyway. The two curves are not the same: for a 50 x 50 mm A36 section
    # the old one ran 9-14% HIGH, which was enough to flip a verdict (a 3 m post at
    # required_safety_factor = 2.6 passed at 2.856 and fails at 2.504 on the real curve).
    # §E3 is the modern column curve and it is the one the reference names.
    euler = euler_critical_stress(elastic_modulus=modulus, slenderness_ratio=lam)
    critical = aisc_flexural_buckling_stress(yield_strength=yield_strength, euler_stress=euler)
    inelastic = yield_strength.to("MPa").magnitude / euler.to("MPa").magnitude <= 2.25
    regime = "AISC E3 inelastic" if inelastic else "AISC E3 elastic"

    applied = axial_stress(force=member.axial_load, area=member.section.area)
    yield_symbol = SymbolValue(
        symbol="F_y", description="material yield strength", value=yield_strength
    )
    euler_symbol = SymbolValue(
        symbol="F_e",
        description="elastic (Euler) buckling stress π²·E/λ²",
        value=euler,
    )
    if inelastic:
        derivation = Derivation(
            symbolic="F_cr = 0.658 ** (F_y / F_e) * F_y",
            inputs=(yield_symbol, euler_symbol),
            result=SymbolValue(
                symbol="F_cr",
                description=(
                    f"inelastic flexural buckling stress (F_y/F_e = "
                    f"{yield_strength.to('MPa').magnitude / euler.to('MPa').magnitude:.3g} "
                    f"≤ 2.25), at λ = {lam:.3g}"
                ),
                value=critical,
            ),
            citation=_CLAUSE_COMPRESSION,
        )
    else:
        derivation = Derivation(
            symbolic="F_cr = 0.877 * F_e",
            inputs=(euler_symbol,),
            result=SymbolValue(
                symbol="F_cr",
                description=(
                    f"elastic flexural buckling stress (F_y/F_e = "
                    f"{yield_strength.to('MPa').magnitude / euler.to('MPa').magnitude:.3g} "
                    f"> 2.25), the Euler stress with the §E3 out-of-straightness "
                    f"knockdown, at λ = {lam:.3g}"
                ),
                value=critical,
            ),
            citation=_CLAUSE_COMPRESSION,
        )
    entry = strength_scorecard(
        f"{member.name} buckling ({regime})",
        stress=applied,
        allowable=critical,
        required=required_safety_factor,
    ).model_copy(update={"reference": _CLAUSE_COMPRESSION, "derivation": derivation})
    return disclosed(
        Scorecard(entries=(entry,)),
        column_allowable,
    )


class BoltedConnection(GuardedInputs):
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
    signed_fields: tuple[str, ...] = (
        "load",
        "tension",
    )

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
    required_basis: AllowableBasis = DESIGN_BASIS,
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
    bolt_allowable = design_allowable(
        bolt, "yield_strength", material_id=connection.bolt_material, basis=required_basis
    )
    plate_allowable = design_allowable(
        plate, "yield_strength", material_id=connection.plate_material, basis=required_basis
    )
    plate_ultimate = design_allowable(
        plate, "ultimate_strength", material_id=connection.plate_material, basis=required_basis
    )
    if bolt_allowable.quantity is None or plate_allowable.quantity is None:
        return _refused(
            (
                f"{connection.name} plate bearing",
                f"{connection.name} bolt shear",
                f"{connection.name} edge tear-out",
            ),
            bolt_allowable.note or plate_allowable.note,
        )

    shear = bolt_shear_stress(
        force=connection.load,
        diameter=connection.bolt_diameter,
        shear_planes=connection.shear_planes,
    )
    bolt_sy = bolt_allowable.quantity.to("MPa").magnitude
    shear_yield = Quantity(magnitude=_SHEAR_YIELD_FRACTION * bolt_sy, unit="MPa")

    bearing = bearing_stress(
        force=connection.load,
        diameter=connection.bolt_diameter,
        thickness=connection.plate_thickness,
    )
    load_symbol = SymbolValue(
        symbol="P", description="load transferred by the connection", value=connection.load
    )
    diameter_symbol = SymbolValue(
        symbol="d", description="bolt shank diameter", value=connection.bolt_diameter
    )
    thickness_symbol = SymbolValue(
        symbol="t", description="plate thickness", value=connection.plate_thickness
    )
    entries = [
        strength_scorecard(
            f"{connection.name} bolt shear",
            stress=shear,
            allowable=shear_yield,
            required=required_safety_factor,
        ).model_copy(
            update={
                "reference": _CLAUSE_BOLT_SHEAR,
                "derivation": Derivation(
                    symbolic="τ = P / (n · π · d² / 4)",
                    inputs=(
                        load_symbol,
                        SymbolValue(
                            symbol="n",
                            description="shear planes through the bolt",
                            value=float(connection.shear_planes),
                        ),
                        diameter_symbol,
                    ),
                    result=SymbolValue(symbol="τ", description="bolt shear stress", value=shear),
                    citation=_CLAUSE_BOLT_SHEAR,
                ),
            }
        ),
        strength_scorecard(
            f"{connection.name} plate bearing",
            stress=bearing,
            allowable=plate_allowable.quantity,
            required=required_safety_factor,
        ).model_copy(
            update={
                "reference": _CLAUSE_BEARING,
                "derivation": Derivation(
                    symbolic="σ_p = P / (d · t)",
                    inputs=(load_symbol, diameter_symbol, thickness_symbol),
                    result=SymbolValue(
                        symbol="σ_p",
                        description="bearing stress on the projected hole area",
                        value=bearing,
                    ),
                    citation=_CLAUSE_BEARING,
                ),
            }
        ),
    ]
    if connection.edge_distance is not None:
        d_mm = connection.bolt_diameter.to("mm").magnitude
        t_mm = connection.plate_thickness.to("mm").magnitude
        fu = plate_ultimate.quantity.to("MPa").magnitude
        clear = connection.edge_distance.to("mm").magnitude - d_mm / 2
        tear_capacity = _TEAROUT_CLEAR_FRACTION * clear * t_mm * fu
        deformation_cap = _TEAROUT_BEARING_CAP_FRACTION * d_mm * t_mm * fu
        capacity = min(tear_capacity, deformation_cap)
        load_n = connection.load.to("N").magnitude
        tearout_sf = capacity / load_n if load_n > 0 else None
        ultimate_symbol = SymbolValue(
            symbol="F_u",
            description="plate ultimate tensile strength",
            value=plate_ultimate.quantity,
        )
        # §J3.10 takes the lesser of tear-out on the clear distance and the
        # bearing-deformation cap. Show the one that actually governed rather than
        # a min() the reader has to evaluate.
        if tear_capacity <= deformation_cap:
            tearout_derivation = Derivation(
                symbolic="R_n = 1.2 · l_c · t · F_u",
                inputs=(
                    SymbolValue(
                        symbol="l_c",
                        description="clear distance from hole edge to plate edge, e − d/2",
                        value=Quantity(magnitude=clear, unit="mm"),
                    ),
                    thickness_symbol,
                    ultimate_symbol,
                ),
                result=SymbolValue(
                    symbol="R_n",
                    description="tear-out capacity (below the bearing-deformation cap)",
                    value=Quantity(magnitude=capacity, unit="N"),
                ),
                citation=_CLAUSE_BEARING,
            )
        else:
            tearout_derivation = Derivation(
                symbolic="R_n = 2.4 · d · t · F_u",
                inputs=(diameter_symbol, thickness_symbol, ultimate_symbol),
                result=SymbolValue(
                    symbol="R_n",
                    description=(
                        "bearing-deformation cap, which governs below the tear-out capacity"
                    ),
                    value=Quantity(magnitude=capacity, unit="N"),
                ),
                citation=_CLAUSE_BEARING,
            )
        entries.append(
            ScorecardEntry.from_safety_factor(
                f"{connection.name} edge tear-out",
                computed=tearout_sf,
                required=required_safety_factor,
            ).model_copy(update={"reference": _CLAUSE_BEARING, "derivation": tearout_derivation})
        )
    if connection.tension is not None:
        tensile = axial_stress(
            force=connection.tension, area=circular_area(connection.bolt_diameter)
        )
        combined = von_mises_plane_stress(
            sigma_x=tensile, sigma_y=Quantity(magnitude=0.0, unit="MPa"), tau_xy=shear
        )
        tension_symbol = SymbolValue(
            symbol="P_t", description="tensile load on the bolt", value=connection.tension
        )
        shear_result = SymbolValue(symbol="τ", description="bolt shear stress", value=shear)
        tensile_result = SymbolValue(
            symbol="σ_t", description="bolt direct tensile stress", value=tensile
        )
        entries.append(
            strength_scorecard(
                f"{connection.name} bolt tension",
                stress=tensile,
                allowable=bolt_allowable.quantity,
                required=required_safety_factor,
            ).model_copy(
                update={
                    "reference": _CLAUSE_BOLT_SHEAR,
                    "derivation": Derivation(
                        symbolic="σ_t = P_t / (π · d² / 4)",
                        inputs=(tension_symbol, diameter_symbol),
                        result=tensile_result,
                        citation=_CLAUSE_BOLT_SHEAR,
                    ),
                }
            )
        )
        entries.append(
            strength_scorecard(
                f"{connection.name} combined tension+shear",
                stress=combined,
                allowable=bolt_allowable.quantity,
                required=required_safety_factor,
            ).model_copy(
                update={
                    "reference": _CLAUSE_BOLT_COMBINED,
                    "derivation": Derivation(
                        # Plane stress with no transverse direct stress, so the
                        # general von Mises form collapses to tension and shear.
                        symbolic="σ_vm = √(σ_t² + 3 · τ²)",
                        inputs=(tensile_result, shear_result),
                        result=SymbolValue(
                            symbol="σ_vm",
                            description="von Mises equivalent stress under combined loading",
                            value=combined,
                        ),
                        citation=_CLAUSE_BOLT_COMBINED,
                    ),
                }
            )
        )
    return disclosed(
        Scorecard(entries=tuple(entries)),
        bolt_allowable,
        plate_allowable,
        plate_ultimate,
    )


class WeldedConnection(GuardedInputs):
    """A fillet-welded connection carrying a load in shear on the weld throat.

    ``leg_size`` is the fillet leg w (the effective throat is 0.707·w),
    ``weld_length`` the total weld length L, ``load`` the transferred force, and
    ``electrode_strength`` the weld-metal tensile strength F_EXX (e.g. 483 MPa for
    an E70 electrode). The allowable weld shear is 0.6·F_EXX (AISC §J2.4).
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = ("load",)

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
    shear = fillet_weld_throat_stress(
        force=connection.load,
        leg_size=connection.leg_size,
        length=connection.weld_length,
    )
    allowable = Quantity(
        magnitude=_WELD_SHEAR_FRACTION * connection.electrode_strength.to("MPa").magnitude,
        unit="MPa",
    )
    derivation = Derivation(
        # 0.707·w is the effective throat of an equal-leg fillet: the shortest path
        # through the weld, at 45° to the legs.
        symbolic="τ = P / (0.707 · w · L)",
        inputs=(
            SymbolValue(symbol="P", description="load carried by the weld", value=connection.load),
            SymbolValue(symbol="w", description="fillet leg size", value=connection.leg_size),
            SymbolValue(symbol="L", description="total weld length", value=connection.weld_length),
        ),
        result=SymbolValue(
            symbol="τ", description="shear stress on the effective throat", value=shear
        ),
        citation=_CLAUSE_WELD,
    )
    entry = strength_scorecard(
        f"{connection.name} weld shear",
        stress=shear,
        allowable=allowable,
        required=required_safety_factor,
    ).model_copy(update={"reference": _CLAUSE_WELD, "derivation": derivation})
    return Scorecard(entries=(entry,))


class BasePlate(GuardedInputs):
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
    signed_fields: tuple[str, ...] = ("axial_load",)

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
    required_basis: AllowableBasis = DESIGN_BASIS,
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
    bearing_symbol = SymbolValue(
        symbol="f_p", description="bearing pressure under the plate", value=bearing
    )
    entries = [
        strength_scorecard(
            f"{plate.name} concrete bearing",
            stress=bearing,
            allowable=capacity,
            required=required_safety_factor,
        ).model_copy(
            update={
                "reference": _CLAUSE_BEARING_CONCRETE,
                "derivation": Derivation(
                    symbolic="f_p = P / (B · N)",
                    inputs=(
                        SymbolValue(
                            symbol="P", description="column axial load", value=plate.axial_load
                        ),
                        SymbolValue(symbol="B", description="plate width", value=plate.width),
                        SymbolValue(symbol="N", description="plate depth", value=plate.depth),
                    ),
                    result=bearing_symbol,
                    citation=_CLAUSE_BEARING_CONCRETE,
                ),
            }
        )
    ]
    # Declared before the branch: the plate-bending check is optional, and the disclosure at
    # the return has to be reachable whether or not it ran.
    base_allowable = DesignAllowable()
    if plate.plate_thickness is not None:
        materials = materials or default_materials_db()
        base_allowable = design_allowable(
            materials.get(plate.plate_material),
            "yield_strength",
            material_id=plate.plate_material,
            basis=required_basis,
        )
        if base_allowable.quantity is None:
            return _refused(
                (f"{plate.name} concrete bearing", f"{plate.name} plate bending"),
                base_allowable.note,
            )
        plate_yield = base_allowable.quantity
        cantilever = plate.cantilever.to("mm").magnitude
        thickness = plate.plate_thickness.to("mm").magnitude
        plate_bending = Quantity(
            magnitude=3 * bearing_mpa * cantilever**2 / thickness**2, unit="MPa"
        )
        bending_entry = strength_scorecard(
            f"{plate.name} plate bending",
            stress=plate_bending,
            allowable=plate_yield,
            required=required_safety_factor,
        ).model_copy(
            update={
                "reference": _CLAUSE_BASEPLATE_BENDING,
                "derivation": Derivation(
                    # The plate is treated as a cantilever of length l carrying
                    # the bearing pressure: M = f_p·l²/2 over a section modulus
                    # t²/6, which collapses to 3·f_p·l²/t².
                    symbolic="σ = 3 · f_p · l² / t²",
                    inputs=(
                        bearing_symbol,
                        SymbolValue(
                            symbol="l",
                            description="cantilever from the column face to the plate edge",
                            value=plate.cantilever,
                        ),
                        SymbolValue(
                            symbol="t",
                            description="base plate thickness",
                            value=plate.plate_thickness,
                        ),
                    ),
                    result=SymbolValue(
                        symbol="σ",
                        description="bending stress in the cantilevered plate",
                        value=plate_bending,
                    ),
                    citation=_CLAUSE_BASEPLATE_BENDING,
                ),
            }
        )
        # The plate-bending stress runs ∝ 1/t², so the safety factor is ∝ t² and
        # the thickness that reaches the required margin is t·√(required/SF) —
        # exact, and decoupled from the footprint (which sets f_p and l). A thicker
        # plate is the standard fix, so the hint names thickness unambiguously.
        if bending_entry.status is CheckStatus.FAIL and bending_entry.safety_factor:
            bending_entry = bending_entry.model_copy(
                update={
                    "repair_hint": RepairHint.solved(
                        "plate_thickness",
                        direction=Direction.INCREASE,
                        value=thickness
                        * (required_safety_factor / bending_entry.safety_factor) ** 0.5,
                        unit="mm",
                        provenance="base-plate bending inverse (σ ∝ 1/t², so SF ∝ t²)",
                    )
                }
            )
        entries.append(bending_entry)
    return disclosed(
        Scorecard(entries=tuple(entries)),
        base_allowable,
    )


class LiftingLug(GuardedInputs):
    """A lifting lug (pad eye) loaded in tension through a pin hole.

    ``width`` is the lug width across the hole, ``hole_diameter`` the pin hole,
    ``thickness`` the plate thickness, and ``load`` the lifted force. Two limit
    states are screened: net-section tension across the reduced width (W−d)·t and
    bearing on the pin d·t, both against the lug material's yield (ASME BTH-1).
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = ("load",)

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


def _thickness_repair_hint(entry: ScorecardEntry, thickness: Quantity, required: float):
    """A solved repair hint for a lug check that failed on thickness.

    Both lug limit states run stress ∝ 1/t, so the safety factor is linear in the
    plate thickness: the thickness that reaches the required margin is simply
    t · required / computed. Thickness is the lug's design lever — the pin
    diameter is set by the shackle, the width by clearance — so the hint names it
    unambiguously. Returns ``None`` for a check that did not fail.
    """
    if entry.status is not CheckStatus.FAIL or not entry.safety_factor:
        return None
    t_mm = thickness.to("mm").magnitude
    return RepairHint.solved(
        "thickness",
        direction=Direction.INCREASE,
        value=t_mm * required / entry.safety_factor,
        unit="mm",
        provenance="lug thickness inverse (σ ∝ 1/t, so SF ∝ t)",
    )


def screen_lifting_lug(
    lug: LiftingLug,
    *,
    required_safety_factor: float,
    target_safety_factor: float | None = None,
    materials: MaterialsDatabase | None = None,
    required_basis: AllowableBasis = DESIGN_BASIS,
) -> Scorecard:
    """Screen a :class:`LiftingLug`'s tension and bearing limit states.

    Screens the net-section tension P/((W−d)·t) and the pin bearing P/(d·t), both
    against the lug material's yield at ``required_safety_factor`` (ASME BTH-1).
    A failing check carries a typed repair hint: because both limit states run
    stress ∝ 1/t, the thickness that reaches the required margin is t·required/SF,
    solved directly rather than searched.

    ``target_safety_factor`` opts into a two-sided band: a check running above it
    is flagged ``OVER_MARGIN`` — a pass, never blocking — so an over-plated lug is
    as visible as an under-plated one. ``materials`` defaults to the bundled
    database.
    """
    materials = materials or default_materials_db()
    record = materials.get(lug.material)
    lug_allowable = design_allowable(
        record, "yield_strength", material_id=lug.material, basis=required_basis
    )
    if lug_allowable.quantity is None:
        return _refused((f"{lug.name} pin bearing", f"{lug.name} net tension"), lug_allowable.note)
    yield_strength = lug_allowable.quantity

    width = lug.width.to("mm").magnitude
    hole = lug.hole_diameter.to("mm").magnitude
    thickness = lug.thickness.to("mm").magnitude
    force = lug.load.to("N").magnitude

    net_tension = Quantity(magnitude=force / ((width - hole) * thickness), unit="MPa")
    bearing = bearing_stress(force=lug.load, diameter=lug.hole_diameter, thickness=lug.thickness)

    load_symbol = SymbolValue(symbol="P", description="lifted load", value=lug.load)
    width_symbol = SymbolValue(symbol="W", description="lug width across the hole", value=lug.width)
    hole_symbol = SymbolValue(symbol="d", description="pin hole diameter", value=lug.hole_diameter)
    thickness_symbol = SymbolValue(
        symbol="t", description="lug plate thickness", value=lug.thickness
    )
    tension_derivation = Derivation(
        symbolic="σ_t = P / ((W − d) · t)",
        inputs=(load_symbol, width_symbol, hole_symbol, thickness_symbol),
        result=SymbolValue(
            symbol="σ_t", description="net-section tensile stress", value=net_tension
        ),
        citation=_CLAUSE_LUG,
    )
    bearing_derivation = Derivation(
        symbolic="σ_p = P / (d · t)",
        inputs=(load_symbol, hole_symbol, thickness_symbol),
        result=SymbolValue(symbol="σ_p", description="pin bearing stress", value=bearing),
        citation=_CLAUSE_LUG,
    )
    tension_entry = strength_scorecard(
        f"{lug.name} net tension",
        stress=net_tension,
        allowable=yield_strength,
        required=required_safety_factor,
        upper=target_safety_factor,
    ).model_copy(update={"reference": _CLAUSE_LUG, "derivation": tension_derivation})
    bearing_entry = strength_scorecard(
        f"{lug.name} pin bearing",
        stress=bearing,
        allowable=yield_strength,
        required=required_safety_factor,
        upper=target_safety_factor,
    ).model_copy(update={"reference": _CLAUSE_LUG, "derivation": bearing_derivation})
    return disclosed(
        Scorecard(
            entries=(
                tension_entry.model_copy(
                    update={
                        "repair_hint": _thickness_repair_hint(
                            tension_entry, lug.thickness, required_safety_factor
                        )
                    }
                ),
                bearing_entry.model_copy(
                    update={
                        "repair_hint": _thickness_repair_hint(
                            bearing_entry, lug.thickness, required_safety_factor
                        )
                    }
                ),
            )
        ),
        lug_allowable,
    )


class GussetPlate(GuardedInputs):
    """A gusset (or connection element) checked for block-shear rupture.

    ``net_shear_area`` A_nv and ``net_tension_area`` A_nt are the areas along the
    tear-out failure path (from the bolt pattern geometry); ``load`` is the force
    transferred. The block-shear capacity R_n = 0.6·Fu·A_nv + Fu·A_nt (AISC §J4.3,
    Ubs = 1) uses the material's ultimate strength.
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = ("load",)

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
    required_basis: AllowableBasis = DESIGN_BASIS,
) -> Scorecard:
    """Screen a :class:`GussetPlate` for block-shear rupture into a scorecard.

    The block-shear capacity R_n = 0.6·Fu·A_nv + Fu·A_nt is compared to the
    transferred load; the safety factor is R_n / load, judged against
    ``required_safety_factor`` (AISC §J4.3). ``materials`` defaults to the bundled
    database.
    """
    materials = materials or default_materials_db()
    gusset_allowable = design_allowable(
        materials.get(gusset.material),
        "ultimate_strength",
        material_id=gusset.material,
        basis=required_basis,
    )
    if gusset_allowable.quantity is None:
        return _refused((f"{gusset.name} block shear",), gusset_allowable.note)
    ultimate = gusset_allowable.quantity.to("MPa").magnitude
    shear_area = gusset.net_shear_area.to("mm**2").magnitude
    tension_area = gusset.net_tension_area.to("mm**2").magnitude
    capacity_n = ultimate * (_BLOCK_SHEAR_SHEAR_FRACTION * shear_area + tension_area)
    load_n = gusset.load.to("N").magnitude
    safety = capacity_n / load_n if load_n > 0 else None
    derivation = Derivation(
        # Block shear tears a wedge out: the shear planes carry 0.6·Fu, the tension
        # plane the full Fu.
        symbolic="R_n = 0.6 · F_u · A_nv + F_u · A_nt",
        inputs=(
            SymbolValue(
                symbol="F_u",
                description="plate ultimate tensile strength",
                value=gusset_allowable.quantity,
            ),
            SymbolValue(
                symbol="A_nv",
                description="net area along the shear planes",
                value=gusset.net_shear_area,
            ),
            SymbolValue(
                symbol="A_nt",
                description="net area across the tension plane",
                value=gusset.net_tension_area,
            ),
        ),
        result=SymbolValue(
            symbol="R_n",
            description="block-shear rupture capacity",
            value=Quantity(magnitude=capacity_n, unit="N"),
        ),
        citation=_CLAUSE_BLOCK_SHEAR,
    )
    entry = ScorecardEntry.from_safety_factor(
        f"{gusset.name} block shear", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _CLAUSE_BLOCK_SHEAR, "derivation": derivation})
    return disclosed(
        Scorecard(entries=(entry,)),
        gusset_allowable,
    )


class TensionMember(GuardedInputs):
    """An axially loaded tension member checked for the two AISC §D2 limit states.

    A rod, angle, or plate carrying ``load`` in tension. ``gross_area`` A_g is the
    full cross-section; ``net_area`` A_n is the area after deducting bolt holes.
    ``shear_lag_factor`` U (default 1.0) reduces the net area to the effective net
    area A_e = U·A_n where the load engages only part of the section (§D3). Two
    limit states are screened: tensile yielding on the gross section (P/A_g vs Fy)
    and tensile rupture on the effective net section (P/A_e vs Fu).
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = ("load",)

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
    required_basis: AllowableBasis = DESIGN_BASIS,
) -> Scorecard:
    """Screen a :class:`TensionMember`'s gross-yield and net-rupture limit states.

    Gross-section yielding screens P/A_g against the material yield Fy (§D2(a));
    net-section rupture screens P/A_e against the ultimate Fu (§D2(b)) with the
    effective net area A_e = U·A_n. The lesser safety factor governs the member.
    ``materials`` defaults to the bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(member.material)
    yield_allowable = design_allowable(
        record, "yield_strength", material_id=member.material, basis=required_basis
    )
    ultimate_allowable = design_allowable(
        record, "ultimate_strength", material_id=member.material, basis=required_basis
    )

    force = member.load.to("N").magnitude
    gross = member.gross_area.to("mm**2").magnitude
    effective_net = member.shear_lag_factor * member.net_area.to("mm**2").magnitude

    gross_stress = Quantity(magnitude=force / gross, unit="MPa")
    net_stress = Quantity(magnitude=force / effective_net, unit="MPa")
    load_symbol = SymbolValue(symbol="P", description="axial tension", value=member.load)
    return disclosed(
        Scorecard(
            entries=(
                strength_scorecard(
                    f"{member.name} gross yielding",
                    stress=gross_stress,
                    allowable=yield_allowable.quantity,
                    required=required_safety_factor,
                    unavailable_detail=yield_allowable.note,
                ).model_copy(
                    update={
                        "reference": _CLAUSE_TENSION,
                        "derivation": Derivation(
                            symbolic="σ_g = P / A_g",
                            inputs=(
                                load_symbol,
                                SymbolValue(
                                    symbol="A_g",
                                    description="gross cross-sectional area",
                                    value=member.gross_area,
                                ),
                            ),
                            result=SymbolValue(
                                symbol="σ_g",
                                description="stress on the gross section",
                                value=gross_stress,
                            ),
                            citation=_CLAUSE_TENSION,
                        ),
                    }
                ),
                strength_scorecard(
                    f"{member.name} net rupture",
                    stress=net_stress,
                    allowable=ultimate_allowable.quantity,
                    required=required_safety_factor,
                    unavailable_detail=ultimate_allowable.note,
                ).model_copy(
                    update={
                        "reference": _CLAUSE_TENSION,
                        "derivation": Derivation(
                            # The shear-lag factor U reduces the net area to the part of
                            # the section the connection actually engages.
                            symbolic="σ_n = P / (U · A_n)",
                            inputs=(
                                load_symbol,
                                SymbolValue(
                                    symbol="U",
                                    description="shear-lag factor",
                                    value=member.shear_lag_factor,
                                ),
                                SymbolValue(
                                    symbol="A_n",
                                    description="net area through the connection",
                                    value=member.net_area,
                                ),
                            ),
                            result=SymbolValue(
                                symbol="σ_n",
                                description="stress on the effective net section",
                                value=net_stress,
                            ),
                            citation=_CLAUSE_TENSION,
                        ),
                    }
                ),
            )
        ),
        yield_allowable,
        ultimate_allowable,
    )


class BeamColumnMember(GuardedInputs):
    """A member carrying combined axial compression and bending (a beam-column).

    Screened by the AISC §H1.1 interaction equation. ``section``'s
    ``second_moment`` is the declared bending axis, which the flexural term
    keeps; the axial (buckling) term uses the least axis the section carries
    (its ``least_radius_of_gyration``), falling back to the bending axis for a
    hand-built section with no transverse second moment. ``end_condition``
    sets the effective-length factor; ``axial_load`` is the compression and
    ``moment`` the applied bending moment; ``material`` a database id (E and
    yield drive both capacities).
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = (
        "axial_load",
        "moment",
    )

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
    required_basis: AllowableBasis = DESIGN_BASIS,
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
    beam_column_allowable = design_allowable(
        record, "yield_strength", material_id=member.material, basis=required_basis
    )
    if beam_column_allowable.quantity is None:
        return _refused(
            (f"{member.name} axial", f"{member.name} interaction"),
            beam_column_allowable.note,
        )
    yield_strength = beam_column_allowable.quantity

    effective_length = Quantity(
        magnitude=member.end_condition.factor() * member.length.to("mm").magnitude,
        unit="mm",
    )
    lam = slenderness_ratio(
        effective_length=effective_length,
        radius_of_gyration=member.section.least_radius_of_gyration,
    )
    # The §H1.1 axial term P_r/P_c consumes the SAME capacity as screen_column_member, so
    # it moves to §E3 with it. Leaving the two on different curves is how one quantity
    # ends up computed two ways in one library.
    critical = aisc_flexural_buckling_stress(
        yield_strength=yield_strength,
        euler_stress=euler_critical_stress(elastic_modulus=modulus, slenderness_ratio=lam),
    )

    axial_capacity = critical.to("MPa").magnitude * member.section.area.to("mm**2").magnitude
    flexural_capacity = (
        yield_strength.to("MPa").magnitude * member.section.section_modulus.to("mm**3").magnitude
    )
    # The MOMENT is a magnitude. §H1.1 sums demand ratios, and a sign-reversed demand
    # still consumes capacity — left signed, a hogging moment SUBTRACTED from the sum and
    # flipped a FAIL at 1.19 into a PASS at 6.34 on the same member. `moment` is declared
    # signed on BeamColumnMember precisely so a real hogging moment can be expressed,
    # which is exactly why the consumer has to take the magnitude.
    #
    # The AXIAL load is NOT a magnitude, because its sign changes which clause applies: a
    # net tension plus flexure is §H1.2, a different interaction with a different capacity
    # on the axial term. Screening it as compression would be conservative but silent, so
    # it is reported as not evaluated instead, naming the clause it needs.
    axial_n = member.axial_load.to("N").magnitude
    pr_pc = axial_n / axial_capacity
    mr_mc = abs(member.moment.to("N*mm").magnitude) / flexural_capacity
    if pr_pc >= 0.2:
        interaction = pr_pc + (8.0 / 9.0) * mr_mc
    else:
        interaction = pr_pc / 2.0 + mr_mc

    # The 20th site of the zero-demand idiom, and the only one that spelled it `inf`. An
    # interaction of zero means P_r = M_r = 0: the AISC H1.1 criterion had nothing to
    # evaluate, not a member with infinite reserve. `None` -> NOT_EVALUATED, matching the
    # 19 sibling screens and the doctrine loads.combination_scorecard spells out.
    safety = 1.0 / interaction if interaction > 0 else None
    tension_governed = axial_n < 0
    capacity_symbols = (
        SymbolValue(symbol="P_r", description="required axial strength", value=member.axial_load),
        SymbolValue(
            symbol="P_c",
            description="available axial strength, buckling stress × area",
            value=Quantity(magnitude=axial_capacity, unit="N"),
        ),
        SymbolValue(symbol="M_r", description="required flexural strength", value=member.moment),
        SymbolValue(
            symbol="M_c",
            description="available flexural strength, first yield F_y·S",
            value=Quantity(magnitude=flexural_capacity, unit="N*mm"),
        ),
    )
    ratio_result = SymbolValue(
        symbol="IR",
        description="interaction ratio; the member is at capacity at 1.0",
        value=interaction,
    )
    # §H1.1 switches form at Pr/Pc = 0.2. Show the branch that actually applied,
    # not both with a condition for the reader to resolve.
    interaction_derivation = (
        Derivation(
            symbolic="IR = P_r/P_c + 8/9 · M_r/M_c",
            inputs=capacity_symbols,
            result=ratio_result,
            citation=_CLAUSE_INTERACTION,
        )
        if pr_pc >= 0.2
        else Derivation(
            symbolic="IR = P_r/(2 · P_c) + M_r/M_c",
            inputs=capacity_symbols,
            result=ratio_result,
            citation=_CLAUSE_INTERACTION,
        )
    )
    if tension_governed:
        # A net tension plus flexure is §H1.2, not §H1.1: the axial term is checked
        # against the tensile capacity, which is not the buckling capacity this screen
        # computed. Screening it as compression would be conservative and silent; saying
        # which clause it needs is neither.
        entry = ScorecardEntry(
            name=f"{member.name} interaction",
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — the axial load is a net TENSION ({member.axial_load}), "
                f"which takes AISC 360 §H1.2 (combined tension and flexure) against the "
                f"tensile capacity, not the §H1.1 form this screen computes against the "
                f"buckling capacity"
            ),
            reference="AISC 360-16 §H1.2",
        )
    else:
        entry = ScorecardEntry.from_safety_factor(
            f"{member.name} interaction", computed=safety, required=required_safety_factor
        ).model_copy(
            update={"reference": _CLAUSE_INTERACTION, "derivation": interaction_derivation}
        )
    # H1-1b HALVES the axial term, and it is only permitted to because Chapter E caps
    # P_r <= P_c independently. Screening the interaction alone reported exactly TWICE the
    # buckling safety factor `screen_column_member` gives for the same member, all through
    # the P_r/P_c < 0.2 region — and it flipped verdicts: a column failing at 5.21 passed
    # at 10.41. The axial check is not optional context for the interaction; it is the
    # premise the interaction's own form rests on, so the card carries both.
    pr = member.axial_load.to("N").magnitude
    axial_safety = axial_capacity / pr if pr > 0 else None
    axial_entry = ScorecardEntry.from_safety_factor(
        f"{member.name} axial capacity", computed=axial_safety, required=required_safety_factor
    ).model_copy(
        update={
            "reference": _CLAUSE_COMPRESSION,
            "derivation": Derivation(
                symbolic="n = P_c / P_r",
                inputs=capacity_symbols[:2],
                result=SymbolValue(
                    symbol="n",
                    description="axial safety factor against buckling (AISC Chapter E)",
                    value=axial_safety if axial_safety is not None else 0.0,
                ),
                citation=_CLAUSE_COMPRESSION,
            )
            if axial_safety is not None
            else None,
        }
    )
    return disclosed(
        Scorecard(entries=(axial_entry, entry)),
        beam_column_allowable,
    )


class ConcreteBearing(GuardedInputs):
    """A plate bearing on concrete, checked by the ACI 318 confined-bearing rule.

    When the loaded area ``bearing_area`` A₁ (a base plate or pedestal cap) is
    smaller than the ``support_area`` A₂ of the concrete beneath it, the surrounding
    concrete confines the bearing zone and raises its strength by √(A₂/A₁), capped
    at 2. ``concrete_strength`` is the compressive strength f′c; ``load`` the force
    delivered. The nominal bearing strength is 0.85·f′c·A₁·√(A₂/A₁).
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = ("load",)

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

    unconfined = (a2 / a1) ** 0.5
    capped = unconfined > _ACI_CONFINEMENT_CAP
    confinement = min(unconfined, _ACI_CONFINEMENT_CAP)
    capacity_n = _ACI_BEARING_FRACTION * fc * a1 * confinement
    safety = capacity_n / load_n if load_n > 0 else None
    # The rendered formula has to be the one that was actually evaluated. Writing
    # √(A₂/A₁) while the §22.8.3 cap is binding prints a substituted line that does not
    # multiply out to the result under it — 25% high whenever A₂ > 4·A₁ — in the one
    # artifact whose whole purpose is being re-derivable by its reader. So the capped
    # branch renders the cap, and drops A₂ from the inputs because the evaluated formula
    # genuinely does not use it.
    strength_inputs = [
        SymbolValue(
            symbol="f′c",
            description="concrete compressive strength",
            value=bearing.concrete_strength,
        ),
        SymbolValue(symbol="A₁", description="loaded (bearing) area", value=bearing.bearing_area),
    ]
    if capped:
        symbolic = f"B_n = 0.85 · f′c · A₁ · {_ACI_CONFINEMENT_CAP:.0f}"
        result_note = (
            f", confinement factor √(A₂/A₁) = {unconfined:.2f} capped at "
            f"{_ACI_CONFINEMENT_CAP:.0f} by ACI 318 §22.8.3"
        )
    else:
        symbolic = "B_n = 0.85 · f′c · A₁ · √(A₂/A₁)"
        result_note = f", confinement factor {confinement:.2f}"
        strength_inputs.append(
            SymbolValue(
                symbol="A₂",
                description="supporting concrete area, confining the bearing zone",
                value=bearing.support_area,
            )
        )
    derivation = Derivation(
        symbolic=symbolic,
        inputs=tuple(strength_inputs),
        result=SymbolValue(
            symbol="B_n",
            description="nominal bearing strength" + result_note,
            value=Quantity(magnitude=capacity_n, unit="N"),
        ),
        citation=_CLAUSE_CONCRETE_BEARING_ACI,
    )
    entry = ScorecardEntry.from_safety_factor(
        f"{bearing.name} concrete bearing", computed=safety, required=required_safety_factor
    ).model_copy(update={"reference": _CLAUSE_CONCRETE_BEARING_ACI, "derivation": derivation})
    return Scorecard(entries=(entry,))


class ShearPlate(GuardedInputs):
    """A plate element loaded in direct shear (a shear tab, coped-beam web, bracket).

    Screened for the two AISC §J4.2 limit states: shear yielding on the gross shear
    area ``gross_shear_area`` A_gv (0.60·Fy·A_gv) and shear rupture on the net shear
    area ``net_shear_area`` A_nv after bolt-hole deductions (0.60·Fu·A_nv). ``load``
    is the shear force transferred; ``material`` a database id (Fy and Fu drive the
    two checks). This is the pure-shear limit state, distinct from block-shear
    tear-out (§J4.3) and bolt shear (§J3.6).
    """

    model_config = ConfigDict(frozen=True)
    signed_fields: tuple[str, ...] = ("load",)

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
    required_basis: AllowableBasis = DESIGN_BASIS,
) -> Scorecard:
    """Screen a :class:`ShearPlate`'s two AISC §J4.2 shear limit states.

    Shear yielding compares 0.60·Fy·A_gv to the load; shear rupture compares
    0.60·Fu·A_nv. Each safety factor (capacity/load) is judged against
    ``required_safety_factor``; the lesser governs. ``materials`` defaults to the
    bundled database.
    """
    materials = materials or default_materials_db()
    record = materials.get(plate.material)
    shear_yield = design_allowable(
        record, "yield_strength", material_id=plate.material, basis=required_basis
    )
    shear_ultimate = design_allowable(
        record, "ultimate_strength", material_id=plate.material, basis=required_basis
    )
    if shear_yield.quantity is None or shear_ultimate.quantity is None:
        return _refused(
            (f"{plate.name} shear yielding", f"{plate.name} shear rupture"),
            shear_yield.note or shear_ultimate.note,
        )
    fy = shear_yield.quantity.to("MPa").magnitude
    fu = shear_ultimate.quantity.to("MPa").magnitude
    gross = plate.gross_shear_area.to("mm**2").magnitude
    net = plate.net_shear_area.to("mm**2").magnitude
    load_n = plate.load.to("N").magnitude

    yield_capacity = _SHEAR_STRENGTH_FRACTION * fy * gross
    rupture_capacity = _SHEAR_STRENGTH_FRACTION * fu * net
    yield_sf = yield_capacity / load_n if load_n > 0 else None
    rupture_sf = rupture_capacity / load_n if load_n > 0 else None
    return disclosed(
        Scorecard(
            entries=(
                ScorecardEntry.from_safety_factor(
                    f"{plate.name} shear yielding",
                    computed=yield_sf,
                    required=required_safety_factor,
                ).model_copy(
                    update={
                        "reference": _CLAUSE_SHEAR,
                        "derivation": Derivation(
                            # Yielding is checked on the gross area: the whole section
                            # has to go plastic before the plate deforms.
                            symbolic="R_n = 0.60 · F_y · A_gv",
                            inputs=(
                                SymbolValue(
                                    symbol="F_y",
                                    description="plate yield strength",
                                    value=shear_yield.quantity,
                                ),
                                SymbolValue(
                                    symbol="A_gv",
                                    description="gross area resisting shear",
                                    value=plate.gross_shear_area,
                                ),
                            ),
                            result=SymbolValue(
                                symbol="R_n",
                                description="shear yielding capacity",
                                value=Quantity(magnitude=yield_capacity, unit="N"),
                            ),
                            citation=_CLAUSE_SHEAR,
                        ),
                    }
                ),
                ScorecardEntry.from_safety_factor(
                    f"{plate.name} shear rupture",
                    computed=rupture_sf,
                    required=required_safety_factor,
                ).model_copy(
                    update={
                        "reference": _CLAUSE_SHEAR,
                        "derivation": Derivation(
                            # Rupture is checked on the net area, through the holes, and
                            # against the ultimate rather than the yield strength.
                            symbolic="R_n = 0.60 · F_u · A_nv",
                            inputs=(
                                SymbolValue(
                                    symbol="F_u",
                                    description="plate ultimate tensile strength",
                                    value=shear_ultimate.quantity,
                                ),
                                SymbolValue(
                                    symbol="A_nv",
                                    description="net area resisting shear, through the holes",
                                    value=plate.net_shear_area,
                                ),
                            ),
                            result=SymbolValue(
                                symbol="R_n",
                                description="shear rupture capacity",
                                value=Quantity(magnitude=rupture_capacity, unit="N"),
                            ),
                            citation=_CLAUSE_SHEAR,
                        ),
                    }
                ),
            )
        ),
        shear_yield,
        shear_ultimate,
    )


# The members `screen_structure` dispatches, as a tuple as well as a type union: the union
# is an annotation, which nothing checks at run time, and the refusal below has to name them.
_STRUCTURAL_MEMBER_TYPES = (
    BeamMember,
    ColumnMember,
    BoltedConnection,
    WeldedConnection,
    BasePlate,
    LiftingLug,
    GussetPlate,
    TensionMember,
    BeamColumnMember,
    ConcreteBearing,
    ShearPlate,
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
    required_basis: AllowableBasis = DESIGN_BASIS,
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
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, ColumnMember):
            card = screen_column_member(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, BoltedConnection):
            card = screen_bolted_connection(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, WeldedConnection):
            card = screen_welded_connection(member, required_safety_factor=required_safety_factor)
        elif isinstance(member, BasePlate):
            card = screen_base_plate(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, LiftingLug):
            card = screen_lifting_lug(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, GussetPlate):
            card = screen_gusset_plate(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, TensionMember):
            card = screen_tension_member(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, BeamColumnMember):
            card = screen_beam_column(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        elif isinstance(member, ConcreteBearing):
            card = screen_concrete_bearing(member, required_safety_factor=required_safety_factor)
        elif isinstance(member, ShearPlate):
            card = screen_shear_plate(
                member,
                required_safety_factor=required_safety_factor,
                materials=materials,
                required_basis=required_basis,
            )
        else:
            # The last branch used to be the shear plate rather than a refusal, so anything
            # this chain did not recognise was screened *as* a shear plate. Nothing that
            # ships today carries the fields it reads, so what a caller actually saw was an
            # AttributeError naming a missing `material` -- a diagnosis pointing at the
            # member's contents when the fault is its type. And a member that did carry them
            # would have been screened on the wrong limit states with no sign of it.
            raise TypeError(
                f"screen_structure cannot screen a {type(member).__name__}; a member must be "
                f"one of {', '.join(sorted(m.__name__ for m in _STRUCTURAL_MEMBER_TYPES))}"
            )
        entries.extend(card.entries)
    return Scorecard(entries=tuple(entries))
