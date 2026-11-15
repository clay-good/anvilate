"""The timber discipline pack: declare a sawn-lumber beam, get an NDS scorecard.

A :class:`TimberBeam` declares a rectangular member on two supports, its load, and the NDS
reference design values it is graded to, each as a :class:`~anvilate.standards.timber.
TimberDesignValue` that names its standard, edition, table, species, grade and size
classification. :func:`screen_timber_beam` screens bending, shear and, when a limit is
declared, deflection, each against the value adjusted by the factor chain the document
states. The record refuses a factor NDS Table 4.3.1 does not apply to its property, so a
load duration factor on the modulus is refused by name rather than making the beam stiffer
than the standard allows. The reference values are copyrighted table data and always the
caller's; nothing here supplies one.
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field, model_validator

from .._models import FrozenMap, Named, cited
from ..analysis import (
    DowelConnection,
    YieldMode,
    deflection_scorecard,
    dowel_yield_capacity,
    nds_bearing_area_factor,
    nds_bearing_scorecard,
    nds_bearing_stress,
    nds_bending_scorecard,
    nds_shear_scorecard,
    nds_shear_stress,
)
from ..derivation import Derivation, SymbolValue
from ..refusal import RefusalError, Remedy
from ..scorecard import (
    AppliedFactor,
    CheckStatus,
    Direction,
    Need,
    RepairHint,
    Scorecard,
    ScorecardEntry,
    ValueSource,
)
from ..standards.timber import (
    MAX_CONNECTION_LOAD_DURATION,
    NDS_CONNECTION_FACTORS,
    ConnectionLoad,
    TimberDesignValue,
    TimberProperty,
)
from ..units import Quantity
from ._guarded import GuardedInputs

_TIMBER_GEOMETRY_SOURCE = "the timber member drawing or verified section dimensions"
_TIMBER_LOAD_SOURCE = "the governing load combination and timber member demand analysis"
_TIMBER_RECORD_SOURCE = "the beam's cited NDS reference-value records"
_TIMBER_CODE_SOURCE = "the governing NDS edition and selected design conditions"
_TIMBER_DOCUMENT_SOURCE = "the timber beam declaration and supporting design records"


class _TimberPackInputError(RefusalError, ValueError):
    """Invalid timber-pack input with a machine-readable repair."""


def _timber_pack_refusal(message: str, *, subject: str, source: str) -> _TimberPackInputError:
    return _TimberPackInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "TimberBeam",
    "TimberConnection",
    "TimberLoad",
    "screen_timber_beam",
    "screen_timber_connection",
]

# Each cites the edition the element's own records are from, so a 2018 value is never
# reported against a clause of another edition.
_NDS_BENDING = "NDS {edition} §3.3 bending"
_NDS_SHEAR = "NDS {edition} §3.4 shear parallel to grain"
_NDS_DEFLECTION = "NDS {edition} §3.5 deflection"
_NDS_BEARING = "NDS {edition} §3.10 bearing perpendicular to grain"
_NDS_CONNECTION = (
    "NDS {edition} §12.3 dowel-type fastener lateral design values, with the Table 11.3.1 "
    "adjustment chain"
)

_TIMBER_CONNECTION_SOURCE = (
    "the connection schedule: the fastener, the members it joins, and the cited NDS "
    "reduction terms for the declared edition"
)

if TYPE_CHECKING:
    _NDSEdition = str
else:
    _NDSEdition = cited(
        "the NDS edition the reduction terms and the adjustment chain were read from; "
        "the numbers move between editions and the chain does not say which it is from"
    )


_NEEDS_A_DEMAND = Need(
    declaration="element_params.demand",
    takes="the lateral force the connection carries, from the governing load combination",
    dimension="[force]",
    units=("kN", "lbf"),
    sources=(ValueSource.USER,),
)

# The catalogue's mode, by id: the deflection check addresses it only when it has been told
# which part of the load is sustained.
_CREEP_MODES = ("timber creep under sustained load",)

_NEEDS_A_MODULUS = Need(
    declaration="element_params.modulus",
    takes="the NDS reference modulus of elasticity E for the species and grade, as a record",
    sources=(ValueSource.STANDARD, ValueSource.USER),
)


def _no_factors() -> MappingProxyType:
    """An empty factor chain that is already read-only, even on an unvalidated copy."""
    return MappingProxyType({})


class TimberLoad(StrEnum):
    """How the load sits on the span: spread along it, or at midspan."""

    DISTRIBUTED = "distributed"
    POINT = "point"


class TimberBeam(GuardedInputs):
    """A rectangular sawn-lumber beam on two supports, graded to declared NDS values.

    ``width`` b and ``depth`` d are the actual (dressed) section dimensions, not the
    nominal ones: a 2x10 is 1.5 x 9.25 in. ``span`` L is between the supports. ``load`` is a
    force per length for a ``distributed`` load or a force for a ``point`` load at midspan.

    ``bending``, ``shear`` and the optional ``modulus`` are NDS reference design values for
    F_b, F_v and E, each with the factor chain the document applies to it in
    ``bending_factors``, ``shear_factors`` and ``modulus_factors`` (``{"C_D": 1.15, "C_M":
    1.0, ...}``). Each chain is checked against NDS Table 4.3.1 when the beam is built.
    ``deflection_limit``, when declared, adds a deflection check, which needs ``modulus``.
    ``sustained_load`` is the part of ``load`` that stays on for years (the dead load and
    stored contents, say), and ``creep_factor`` K_cr the NDS §3.5.2 multiplier on its
    deflection: 1.5 for seasoned lumber in dry service, 2.0 for unseasoned or wet. The two are
    declared together, and without them the deflection is the short-term one and says so.

    ``bearing_length`` l_b, the length of each support along the grain, with the F_c⊥
    record ``compression_perpendicular`` and its ``compression_perpendicular_factors``, adds a
    bearing check at the supports. The bearing area factor C_b is derived from l_b and the
    optional ``bearing_end_distance`` (NDS §3.10.4), so the document does not state it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    positive_fields = (
        "width",
        "depth",
        "span",
        "deflection_limit",
        "creep_factor",
        "bearing_length",
    )

    name: Named
    width: Quantity
    depth: Quantity
    span: Quantity
    load: Quantity
    load_type: TimberLoad = TimberLoad.DISTRIBUTED
    bending: TimberDesignValue
    shear: TimberDesignValue
    modulus: TimberDesignValue | None = None
    bending_factors: FrozenMap[str, float] = Field(default_factory=_no_factors)
    shear_factors: FrozenMap[str, float] = Field(default_factory=_no_factors)
    modulus_factors: FrozenMap[str, float] = Field(default_factory=_no_factors)
    deflection_limit: Quantity | None = None
    sustained_load: Quantity | None = None
    creep_factor: float | None = None
    bearing_length: Quantity | None = None
    bearing_end_distance: Quantity | None = None
    compression_perpendicular: TimberDesignValue | None = None
    compression_perpendicular_factors: FrozenMap[str, float] = Field(default_factory=_no_factors)

    @model_validator(mode="after")
    def _well_formed(self) -> TimberBeam:
        for value, name in ((self.width, "width"), (self.depth, "depth"), (self.span, "span")):
            if not value.has_dimension("[length]"):
                raise _timber_pack_refusal(
                    f"{name} must be a [length] quantity; got {value}",
                    subject=name,
                    source=_TIMBER_GEOMETRY_SOURCE,
                )
        expected = "[force]" if self.load_type is TimberLoad.POINT else "[force] / [length]"
        if not self.load.has_dimension(expected):
            raise _timber_pack_refusal(
                f"load must be a {expected} quantity for a {self.load_type.value} load; "
                f"got {self.load}",
                subject="load",
                source=_TIMBER_LOAD_SOURCE,
            )
        if (self.sustained_load is None) != (self.creep_factor is None):
            raise _timber_pack_refusal(
                "sustained_load and creep_factor are declared together: the creep factor "
                "multiplies the deflection of the sustained part of the load",
                subject="sustained_load and creep_factor",
                source=_TIMBER_LOAD_SOURCE,
            )
        if self.sustained_load is not None:
            if not self.sustained_load.has_dimension(expected):
                raise _timber_pack_refusal(
                    f"sustained_load must be a {expected} quantity, like load; "
                    f"got {self.sustained_load}",
                    subject="sustained_load",
                    source=_TIMBER_LOAD_SOURCE,
                )
            if self.sustained_load.to(str(self.load.unit)).magnitude > self.load.magnitude:
                raise _timber_pack_refusal(
                    f"sustained_load ({self.sustained_load}) is the long-term part of load "
                    f"({self.load}) and cannot exceed it",
                    subject="sustained_load",
                    source=_TIMBER_LOAD_SOURCE,
                )
        if self.creep_factor is not None and self.creep_factor < 1:
            raise _timber_pack_refusal(
                f"creep_factor must be at least 1, since creep only adds deflection; got "
                f"{self.creep_factor}",
                subject="creep_factor",
                source=_TIMBER_CODE_SOURCE,
            )
        if self.deflection_limit is not None and not self.deflection_limit.has_dimension(
            "[length]"
        ):
            raise _timber_pack_refusal(
                f"deflection_limit must be a [length] quantity; got {self.deflection_limit}",
                subject="deflection_limit",
                source=_TIMBER_DOCUMENT_SOURCE,
            )
        for field, record, wanted in (
            ("bending", self.bending, TimberProperty.BENDING),
            ("shear", self.shear, TimberProperty.SHEAR),
            ("modulus", self.modulus, TimberProperty.MODULUS),
            (
                "compression_perpendicular",
                self.compression_perpendicular,
                TimberProperty.COMPRESSION_PERPENDICULAR,
            ),
        ):
            if record is not None and record.property is not wanted:
                raise _timber_pack_refusal(
                    f"{field} must be the {wanted.value} reference value; this record is "
                    f"{record.property.value}",
                    subject=field,
                    source=_TIMBER_RECORD_SOURCE,
                )
        if (self.bearing_length is None) != (self.compression_perpendicular is None):
            raise _timber_pack_refusal(
                "bearing_length and compression_perpendicular are declared together: the "
                "bearing check needs the length of each support and the F_c_perp value",
                subject="bearing_length and compression_perpendicular",
                source=_TIMBER_DOCUMENT_SOURCE,
            )
        for value, name in (
            (self.bearing_length, "bearing_length"),
            (self.bearing_end_distance, "bearing_end_distance"),
        ):
            if value is not None and not value.has_dimension("[length]"):
                raise _timber_pack_refusal(
                    f"{name} must be a [length] quantity; got {value}",
                    subject=name,
                    source=_TIMBER_GEOMETRY_SOURCE,
                )
        if "C_b" in self.compression_perpendicular_factors:
            raise _timber_pack_refusal(
                "compression_perpendicular_factors: C_b is derived from bearing_length and "
                "bearing_end_distance (NDS §3.10.4), so the document does not state it",
                subject="compression_perpendicular_factors",
                source=_TIMBER_CODE_SOURCE,
            )
        records = [
            r
            for r in (self.bending, self.shear, self.modulus, self.compression_perpendicular)
            if r is not None
        ]
        woods = {(r.species, r.grade) for r in records}
        if len(woods) > 1:
            raise _timber_pack_refusal(
                "bending, shear and modulus describe one piece of wood, and these records "
                f"name {sorted(f'{species} {grade}' for species, grade in woods)}",
                subject="bending, shear, modulus, and compression_perpendicular records",
                source=_TIMBER_RECORD_SOURCE,
            )
        # The chains are checked here, so a factor NDS does not apply is refused before any
        # screen runs, naming the field that carries it.
        for field, record, factors in (
            ("bending_factors", self.bending, self.bending_factors),
            ("shear_factors", self.shear, self.shear_factors),
            ("modulus_factors", self.modulus, self.modulus_factors),
            (
                "compression_perpendicular_factors",
                self.compression_perpendicular,
                self.compression_perpendicular_factors,
            ),
        ):
            if record is None:
                if factors:
                    raise _timber_pack_refusal(
                        f"{field} were given with no record to apply them to",
                        subject=field,
                        source=_TIMBER_DOCUMENT_SOURCE,
                    )
                continue
            try:
                record.adjusted(factors)
            except ValueError as refused:
                raise _timber_pack_refusal(
                    f"{field}: {refused}",
                    subject=field,
                    source=_TIMBER_CODE_SOURCE,
                ) from None
        return self

    @property
    def declared_material(self) -> str:
        """The species and grade its records are for, which a document's ``material.ref``
        names: timber is not in the materials database, and its values are these records."""
        return _declared_material(self)


def _declared_material(beam: TimberBeam) -> str:
    return f"{beam.bending.species} {beam.bending.grade}"


def _deflection_derivation(
    beam: TimberBeam, modulus: float, second_moment: float, sag: float, citation: str
) -> Derivation:
    """The midspan deflection as worked, with the creep term when a load is sustained."""
    point = beam.load_type is TimberLoad.POINT
    load, unit = ("P", "N") if point else ("w", "N/mm")
    shape = "L³ / (48 · E' · I)" if point else "L⁴ / (384 · E' · I)"
    lead = "" if point else "5 · "
    inputs = [
        SymbolValue(
            symbol=load,
            description="the whole load" if point else "the whole load per length",
            value=Quantity(magnitude=beam.load.to(unit).magnitude, unit=unit),
        )
    ]
    if beam.sustained_load is None:
        symbolic = f"Δ = {lead}{load} · {shape}"
    else:
        symbolic = f"Δ = {lead}(K_cr · {load}_LT + ({load} − {load}_LT)) · {shape}"
        inputs += [
            SymbolValue(
                symbol="K_cr",
                description="the NDS §3.5.2 creep factor",
                value=beam.creep_factor or 1.0,
            ),
            SymbolValue(
                symbol=f"{load}_LT",
                description="the sustained part of the load",
                value=Quantity(magnitude=beam.sustained_load.to(unit).magnitude, unit=unit),
            ),
        ]
    inputs += [
        SymbolValue(symbol="L", description="the span between supports", value=beam.span),
        SymbolValue(
            symbol="E'",
            description="the adjusted modulus of elasticity",
            value=Quantity(magnitude=modulus, unit="MPa"),
        ),
        SymbolValue(
            symbol="I",
            description="the second moment of area, b·d³/12",
            value=Quantity(magnitude=second_moment, unit="mm**4"),
        ),
    ]
    return Derivation(
        symbolic=symbolic,
        inputs=tuple(inputs),
        result=SymbolValue(
            symbol="Δ",
            description="the midspan deflection",
            value=Quantity(magnitude=sag, unit="mm"),
        ),
        citation=citation,
    )


def _deepened(entry: ScorecardEntry, depth_mm: float, exponent: float) -> ScorecardEntry:
    """``entry`` with the depth that brings it to the NDS allowable, when it fails.

    The stress goes as 1/dⁿ with the width held (n = 2 in bending, 1 in shear), so the
    safety factor goes as dⁿ and the depth that reaches one is d·(1/SF)^(1/n), exactly.
    """
    if entry.status is not CheckStatus.FAIL or not entry.safety_factor:
        return entry
    return entry.model_copy(
        update={
            "repair_hint": RepairHint.solved(
                "depth",
                direction=Direction.INCREASE,
                value=depth_mm * (1.0 / entry.safety_factor) ** (1.0 / exponent),
                unit="mm",
                provenance=f"NDS stress ∝ 1/d^{exponent:g} at a held width, so SF ∝ d^{exponent:g}",
            )
        }
    )


def _with_source(entry: ScorecardEntry, record: TimberDesignValue) -> ScorecardEntry:
    """``entry`` naming the table the value it was judged against came from."""
    return entry.model_copy(update={"detail": f"{entry.detail} (reference value: {record})"})


def screen_timber_beam(beam: TimberBeam) -> Scorecard:
    """Screen a :class:`TimberBeam` for bending, shear and deflection (NDS allowable stress).

    Simply supported: a distributed load w gives M = w·L²/8 and V = w·L/2, a midspan point
    load P gives M = P·L/4 and V = P/2. Bending is f_b = M/S with S = b·d²/6 against F'_b,
    and shear f_v = 1.5·V/(b·d) against F'_v, where each adjusted value is the reference
    value times its declared factor chain. The NDS allowable already carries the margin, so
    each check passes at a factor of one. With a ``deflection_limit``, the midspan
    deflection 5·w·L⁴/(384·E'·I) or P·L³/(48·E'·I), with I = b·d³/12, is judged against it;
    a limit with no ``modulus`` is not evaluated, naming it. Shear is taken at the support,
    without the NDS §3.4.3 allowance to ignore load within d of it, which is conservative.
    """
    edition = beam.bending.edition
    span = beam.span.to("mm").magnitude
    width = beam.width.to("mm").magnitude
    depth = beam.depth.to("mm").magnitude
    if beam.load_type is TimberLoad.POINT:
        force = beam.load.to("N").magnitude
        moment = force * span / 4
        shear = force / 2
    else:
        intensity = beam.load.to("N/mm").magnitude
        moment = intensity * span**2 / 8
        shear = intensity * span / 2
    bending_stress = Quantity(magnitude=moment / (width * depth**2 / 6), unit="MPa")
    entries = [
        _deepened(
            _with_source(
                nds_bending_scorecard(
                    f"{beam.name} bending",
                    bending_stress=bending_stress,
                    adjusted_bending_value=beam.bending.adjusted(beam.bending_factors),
                ),
                beam.bending,
            ).model_copy(update={"reference": _NDS_BENDING.format(edition=edition)}),
            depth,
            2.0,
        ),
        _deepened(
            _with_source(
                nds_shear_scorecard(
                    f"{beam.name} shear",
                    shear_stress=nds_shear_stress(
                        shear_force=Quantity(magnitude=shear, unit="N"),
                        width=beam.width,
                        depth=beam.depth,
                    ),
                    adjusted_shear_value=beam.shear.adjusted(beam.shear_factors),
                ),
                beam.shear,
            ).model_copy(update={"reference": _NDS_SHEAR.format(edition=edition)}),
            depth,
            1.0,
        ),
    ]
    if beam.bearing_length is not None and beam.compression_perpendicular is not None:
        area_factor = nds_bearing_area_factor(
            bearing_length=beam.bearing_length, end_distance=beam.bearing_end_distance
        )
        chain = {**beam.compression_perpendicular_factors, "C_b": area_factor}
        entries.append(
            _with_source(
                nds_bearing_scorecard(
                    f"{beam.name} bearing",
                    bearing_stress=nds_bearing_stress(
                        bearing_force=Quantity(magnitude=shear, unit="N"),
                        width=beam.width,
                        bearing_length=beam.bearing_length,
                    ),
                    adjusted_bearing_value=beam.compression_perpendicular.adjusted(chain),
                ),
                beam.compression_perpendicular,
            ).model_copy(update={"reference": _NDS_BEARING.format(edition=edition)})
        )
    if beam.deflection_limit is not None:
        if beam.modulus is None:
            entries.append(
                ScorecardEntry(
                    name=f"{beam.name} deflection",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        "not evaluated — a deflection limit is declared and no modulus of "
                        "elasticity to compute the deflection from; declare `modulus`"
                    ),
                    reference=_NDS_DEFLECTION.format(edition=edition),
                    needs=(_NEEDS_A_MODULUS,),
                )
            )
        else:
            modulus = beam.modulus.adjusted(beam.modulus_factors).to("MPa").magnitude
            second_moment = width * depth**3 / 12
            if beam.load_type is TimberLoad.POINT:
                per_unit_load = span**3 / (48 * modulus * second_moment)
                unit = "N"
            else:
                per_unit_load = 5 * span**4 / (384 * modulus * second_moment)
                unit = "N/mm"
            total = beam.load.to(unit).magnitude
            if beam.sustained_load is None:
                sag = per_unit_load * total
                note = (
                    "short-term; the long-term creep of a sustained load is not included, "
                    "so declare sustained_load and creep_factor for a beam that carries one"
                )
            else:
                sustained = beam.sustained_load.to(unit).magnitude
                creep = beam.creep_factor or 1.0
                # NDS §3.5.2: Δ_T = K_cr·Δ_LT + Δ_ST.
                sag = per_unit_load * (creep * sustained + (total - sustained))
                note = (
                    f"K_cr = {creep:g} on the sustained {beam.sustained_load} "
                    "(NDS §3.5.2, Δ_T = K_cr·Δ_LT + Δ_ST)"
                )
            entry = _with_source(
                deflection_scorecard(
                    f"{beam.name} deflection",
                    deflection=Quantity(magnitude=sag, unit="mm"),
                    limit=beam.deflection_limit,
                ),
                beam.modulus,
            )
            citation = _NDS_DEFLECTION.format(edition=edition)
            entries.append(
                entry.model_copy(
                    update={
                        "reference": citation,
                        "detail": f"{entry.detail}; {note}",
                        "derivation": _deflection_derivation(
                            beam, modulus, second_moment, sag, citation
                        ),
                    }
                )
            )
            if beam.sustained_load is not None:
                entries[-1] = entries[-1].model_copy(update={"addresses": _CREEP_MODES})
    return Scorecard(entries=tuple(entries))


class TimberConnection(GuardedInputs):
    """A group of identical dowel-type fasteners carrying one lateral force.

    ``connection`` is the geometry of **one** fastener at **one** shear plane, as the
    yield limit equations take it; :func:`~anvilate.analysis.dowel_yield.
    dowel_yield_capacity` gives the unreduced 5% offset yield value P of each mode.

    ``reduction_terms`` is the caller's: NDS Table 12.3.1B gives a reduction term R_d per
    mode, modified by the angle to grain, and it is a copyrighted table this library does
    not carry. **Every mode the connection can reach needs one**, because the reference
    design value is the least of ``P/R_d`` over the modes and not ``P_governing/R_d`` —
    the terms differ by mode, so the mode with the smallest P is not always the one with
    the smallest Z.

    ``factors`` is the NDS Table 11.3.1 chain for a lateral value, checked when the
    connection is built: C_D (capped at 1.6 for a connection), C_M, C_t, C_g, C_Delta,
    C_eg, C_di and C_tn. ``fasteners`` is the number in the group, which multiplies the
    adjusted value, and ``demand`` is the force the group carries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    positive_fields = ()

    name: Named
    connection: DowelConnection
    reduction_terms: FrozenMap[str, float]
    demand: Quantity
    fasteners: int = 1
    factors: FrozenMap[str, float] = Field(default_factory=_no_factors)
    edition: _NDSEdition

    @model_validator(mode="after")
    def _well_formed(self) -> TimberConnection:
        if not self.demand.has_dimension("[force]"):
            raise _timber_pack_refusal(
                f"demand is the lateral force on the group, a [force]; got {self.demand}",
                subject="demand",
                source=_TIMBER_LOAD_SOURCE,
            )
        if isinstance(self.fasteners, bool) or self.fasteners < 1:
            raise _timber_pack_refusal(
                f"fasteners is the number in the group, and a connection has at least "
                f"one; got {self.fasteners}",
                subject="fasteners",
                source=_TIMBER_CONNECTION_SOURCE,
            )
        known = {mode.value for mode in YieldMode}
        unknown = sorted(set(self.reduction_terms) - known)
        if unknown:
            raise _timber_pack_refusal(
                f"reduction_terms names {unknown}, which are not yield modes; the modes "
                f"are {sorted(known)}",
                subject="reduction_terms",
                source=_TIMBER_CONNECTION_SOURCE,
            )
        for mode, term in self.reduction_terms.items():
            if not isfinite(term) or term <= 0:
                raise _timber_pack_refusal(
                    f"the reduction term for mode {mode} must be positive and finite; got {term}",
                    subject="reduction_terms",
                    source=_TIMBER_CONNECTION_SOURCE,
                )
        allowed = NDS_CONNECTION_FACTORS[ConnectionLoad.LATERAL]
        inapplicable = sorted(set(self.factors) - allowed)
        if inapplicable:
            raise _timber_pack_refusal(
                f"NDS Table 11.3.1 does not apply {inapplicable} to a lateral connection "
                f"value; it takes {sorted(allowed)}",
                subject="factors",
                source=_TIMBER_CODE_SOURCE,
            )
        duration = self.factors.get("C_D")
        if duration is not None and duration > MAX_CONNECTION_LOAD_DURATION:
            raise _timber_pack_refusal(
                f"NDS Table 11.3.1 footnote 1 caps C_D at {MAX_CONNECTION_LOAD_DURATION} "
                f"for a connection; got {duration}. The member it joins may take 2.0 under "
                f"an impact load, and copying that across overstates the connection",
                subject="factors",
                source=_TIMBER_CODE_SOURCE,
            )
        for name, factor in self.factors.items():
            if not isfinite(factor) or factor <= 0:
                raise _timber_pack_refusal(
                    f"the adjustment factor {name} must be positive and finite; got {factor}",
                    subject="factors",
                    source=_TIMBER_CODE_SOURCE,
                )
        return self


def screen_timber_connection(connection: TimberConnection) -> Scorecard:
    """Screen a dowel-type fastener group against its lateral demand (NDS §12.3, §11.3).

    Three steps, and the middle one is where a hand calculation goes wrong:

    1. The yield limit equations give the unreduced 5% offset yield value P of every mode
       the connection can reach (AWC TR12 Table 1-1).
    2. The reference design value is **the least of P/R_d over those modes**, with the
       caller's reduction terms. Not P_governing/R_d: the terms differ by mode — NDS gives
       4.0 for the bearing modes against 3.2 for the hinge ones — so a thin main member
       can have mode IIIm governing P and mode Im governing Z, and dividing only the
       smallest P by its own term overstates the connection by a fifth.
    3. Z' = Z · ∏C_i over the Table 11.3.1 chain, times the fastener count, against the
       demand. The NDS allowable carries its own margin, so the check passes at 1.0.

    A mode with no reduction term declared is not evaluated, naming the mode: a connection
    screened on three of its five reachable modes has been screened on the wrong one as
    often as not.

    **What this does not check.** The yield limit equations describe the fastener and the
    wood bearing on it, and not the wood *around* the group: a row of closely spaced
    fasteners loaded parallel to grain can tear a block out of the member before any
    fastener reaches the mode its capacity was computed from. NDS 2018 Appendix E
    (non-mandatory) gives net section tension (E.2), row tear-out (E.3) and group tear-out
    (E.4) for that, and none of them is screened here. Nor are the edge, end and spacing
    minimums themselves — :func:`~anvilate.analysis.nds_timber.nds_geometry_factor` turns
    a declared distance into C_Delta, and the distance is the caller's to declare.
    """
    yielded = dowel_yield_capacity(connection.connection)
    reachable = [entry for entry in yielded.modes if entry.capacity is not None]
    # In the modes' own order, not alphabetical: "Im, Is, II, IIIm" is how the table
    # prints them, and "II, IIIm, IIIs, IV, Is" reads as a different connection.
    missing = [
        entry.mode.value
        for entry in reachable
        if entry.mode.value not in connection.reduction_terms
    ]
    citation = _NDS_CONNECTION.format(edition=connection.edition)
    if missing:
        return Scorecard(
            entries=(
                ScorecardEntry(
                    name=f"{connection.name} lateral capacity",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"not evaluated — no reduction term declared for mode(s) "
                        f"{', '.join(missing)}, which this connection can reach. The "
                        f"reference design value is the least of P/R_d over every reachable "
                        f"mode, so a missing term is a mode that might have governed"
                    ),
                    reference=citation,
                    needs=(
                        Need(
                            declaration="element_params.reduction_terms",
                            takes=(
                                "the NDS Table 12.3.1B reduction term R_d for each yield "
                                "mode, at the connection's angle to grain"
                            ),
                            sources=(ValueSource.STANDARD, ValueSource.USER),
                        ),
                    ),
                ),
            )
        )

    reduced = {
        entry.mode: entry.capacity.to("lbf").magnitude
        / connection.reduction_terms[entry.mode.value]
        for entry in reachable
    }
    governing = min(reduced, key=lambda mode: reduced[mode])
    product = 1.0
    for factor in connection.factors.values():
        product *= factor
    capacity = reduced[governing] * product * connection.fasteners
    demand = connection.demand.to("lbf").magnitude
    chain = (
        ", ".join(f"{name} {value:g}" for name, value in sorted(connection.factors.items()))
        or "no adjustment factors declared"
    )
    unreduced = yielded.governing.mode
    crossed = (
        ""
        if unreduced is governing
        else (
            f"; mode {unreduced.value} governs the unreduced value and mode "
            f"{governing.value} governs the design value, because their reduction terms "
            f"differ"
        )
    )
    entry = ScorecardEntry.from_safety_factor(
        f"{connection.name} lateral capacity",
        computed=None if demand == 0 else capacity / demand,
        required=1.0,
        unavailable=(
            "the demand is zero, so there is no force to screen; pass the `demand` the "
            "governing load combination puts on the connection"
        ),
        needs=(_NEEDS_A_DEMAND,),
    )
    return Scorecard(
        entries=(
            entry.model_copy(
                update={
                    "reference": citation,
                    "derivation": Derivation(
                        symbolic="Z'_group = (P / R_d) · C · n",
                        inputs=(
                            SymbolValue(
                                symbol="P",
                                description=(
                                    f"the unreduced 5% offset yield value of mode "
                                    f"{governing.value}, the mode that governs after the "
                                    f"reduction terms"
                                ),
                                value=Quantity(
                                    magnitude=yielded.of(governing).capacity.to("lbf").magnitude,
                                    unit="lbf",
                                ),
                            ),
                            SymbolValue(
                                symbol="R_d",
                                description="the declared reduction term for that mode",
                                value=connection.reduction_terms[governing.value],
                            ),
                            SymbolValue(
                                symbol="C",
                                description=f"the Table 11.3.1 chain multiplied out ({chain})",
                                value=product,
                            ),
                            SymbolValue(
                                symbol="n",
                                description="the fasteners in the group",
                                value=float(connection.fasteners),
                            ),
                        ),
                        result=SymbolValue(
                            symbol="Z'_group",
                            description="the group's adjusted lateral design value",
                            value=Quantity(magnitude=capacity, unit="lbf"),
                        ),
                        citation=citation,
                    ),
                    "applied_factors": (
                        AppliedFactor(
                            label=f"R_d, reduction term for mode {governing.value}",
                            value=connection.reduction_terms[governing.value],
                            origin="the NDS reduction term the document declares",
                            authority=(
                                f"NDS {connection.edition} Table 12.3.1B reduction term "
                                f"R_d, at the connection's angle to grain"
                            ),
                        ),
                    ),
                    "detail": (
                        f"{entry.detail}; governs on mode {governing.value} "
                        f"({governing.description}) at R_d "
                        f"{connection.reduction_terms[governing.value]:g}, Z "
                        f"{reduced[governing]:.0f} lbf per fastener, chain {chain}, "
                        f"{connection.fasteners} fastener(s){crossed}"
                    ),
                }
            ),
        )
    )
