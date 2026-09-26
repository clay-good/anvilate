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
from types import MappingProxyType

from pydantic import ConfigDict, Field, model_validator

from .._models import FrozenMap, Named
from ..analysis import (
    deflection_scorecard,
    nds_bending_scorecard,
    nds_shear_scorecard,
    nds_shear_stress,
)
from ..derivation import Derivation, SymbolValue
from ..scorecard import (
    CheckStatus,
    Direction,
    Need,
    RepairHint,
    Scorecard,
    ScorecardEntry,
    ValueSource,
)
from ..standards.timber import TimberDesignValue, TimberProperty
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "TimberBeam",
    "TimberLoad",
    "screen_timber_beam",
]

# Each cites the edition the element's own records are from, so a 2018 value is never
# reported against a clause of another edition.
_NDS_BENDING = "NDS {edition} §3.3 bending"
_NDS_SHEAR = "NDS {edition} §3.4 shear parallel to grain"
_NDS_DEFLECTION = "NDS {edition} §3.5 deflection"

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
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    positive_fields = ("width", "depth", "span", "deflection_limit", "creep_factor")

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

    @model_validator(mode="after")
    def _well_formed(self) -> TimberBeam:
        for value, name in ((self.width, "width"), (self.depth, "depth"), (self.span, "span")):
            if not value.has_dimension("[length]"):
                raise ValueError(f"{name} must be a [length] quantity; got {value}")
        expected = "[force]" if self.load_type is TimberLoad.POINT else "[force] / [length]"
        if not self.load.has_dimension(expected):
            raise ValueError(
                f"load must be a {expected} quantity for a {self.load_type.value} load; "
                f"got {self.load}"
            )
        if (self.sustained_load is None) != (self.creep_factor is None):
            raise ValueError(
                "sustained_load and creep_factor are declared together: the creep factor "
                "multiplies the deflection of the sustained part of the load"
            )
        if self.sustained_load is not None:
            if not self.sustained_load.has_dimension(expected):
                raise ValueError(
                    f"sustained_load must be a {expected} quantity, like load; "
                    f"got {self.sustained_load}"
                )
            if self.sustained_load.to(str(self.load.unit)).magnitude > self.load.magnitude:
                raise ValueError(
                    f"sustained_load ({self.sustained_load}) is the long-term part of load "
                    f"({self.load}) and cannot exceed it"
                )
        if self.creep_factor is not None and self.creep_factor < 1:
            raise ValueError(
                f"creep_factor must be at least 1, since creep only adds deflection; got "
                f"{self.creep_factor}"
            )
        if self.deflection_limit is not None and not self.deflection_limit.has_dimension(
            "[length]"
        ):
            raise ValueError(
                f"deflection_limit must be a [length] quantity; got {self.deflection_limit}"
            )
        for field, record, wanted in (
            ("bending", self.bending, TimberProperty.BENDING),
            ("shear", self.shear, TimberProperty.SHEAR),
            ("modulus", self.modulus, TimberProperty.MODULUS),
        ):
            if record is not None and record.property is not wanted:
                raise ValueError(
                    f"{field} must be the {wanted.value} reference value; this record is "
                    f"{record.property.value}"
                )
        records = [r for r in (self.bending, self.shear, self.modulus) if r is not None]
        woods = {(r.species, r.grade) for r in records}
        if len(woods) > 1:
            raise ValueError(
                "bending, shear and modulus describe one piece of wood, and these records "
                f"name {sorted(f'{species} {grade}' for species, grade in woods)}"
            )
        # The chains are checked here, so a factor NDS does not apply is refused before any
        # screen runs, naming the field that carries it.
        for field, record, factors in (
            ("bending_factors", self.bending, self.bending_factors),
            ("shear_factors", self.shear, self.shear_factors),
            ("modulus_factors", self.modulus, self.modulus_factors),
        ):
            if record is None:
                if factors:
                    raise ValueError(f"{field} were given with no modulus to apply them to")
                continue
            try:
                record.adjusted(factors)
            except ValueError as refused:
                raise ValueError(f"{field}: {refused}") from None
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
