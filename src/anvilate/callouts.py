"""Typed MBD callouts: finish, coating, and heat treat as check inputs, not annotations.

The geometric half of model-based definition is typed in :mod:`anvilate.gdt`. This is the
other half — surface finish, coating and plating, heat treatment, and structured process
notes — and in this library they are not drawing furniture. They are inputs that checks
already parameterize and currently do not receive:

* **Surface finish sets the Marin surface factor** the fatigue module takes as a bare
  float. A part drawn "as-forged" and screened at k_a = 1.0 is screened as a polished
  laboratory specimen, which at 800 MPa overstates the endurance limit by about 3x.
* **Plating changes the dimension the fit was designed around.** A shaft plated 10 µm
  grows 20 µm on diameter, and a 60° thread's pitch diameter grows *four* times the
  plating thickness, not two.
* **Heat treatment selects which material record is legitimate.** The bundled database
  distinguishes conditions in the record identity (``AA-6061-T6``, ``AISI-1018-CD``), so
  a declared condition either resolves to a record or it does not — and when it does not,
  the check says so instead of quietly screening the annealed row.

Three positions worth stating, because each is a choice:

**Identity is what the characteristic *is*, not what it says.** The persistent identifier
is derived from the callout's kind, its scope tag, and (for a note) its category — never
from its value. So revising a finish from 3.2 to 0.8 Ra keeps the identifier and the diff
reports a *change*; adding a finish to a new face mints a new one. That is what lets a
callout, the check that consumed it, and the inspection that verified it name the same
characteristic across revisions, and it needs no counter and no database to stay stable.

**A roughness number is not a production method, and Shigley's fit is by method.** The
surface-factor table is indexed by how the surface was made, not by its Ra, so the callout
carries both and the derivation uses the method. The Ra is not decoration either: it is
checked against the range that method typically attains, and "as-forged, 0.4 µm Ra" is
surfaced as a contradiction rather than averaged into something plausible.

**A note without a recognized category stays free text, and no check may read it.**
:class:`FreeTextNote` has no typed parameters and is excluded from
:meth:`CalloutSet.consumable` — the distinction between "we typed this" and "somebody
wrote a sentence" survives into the scorecard.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from enum import StrEnum
from math import radians, sin
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .units import Quantity

__all__ = [
    "MARIN_SURFACE_CITATION",
    "MARIN_SURFACE_CONSTANTS_MPA",
    "TYPICAL_ROUGHNESS_UM",
    "THREAD_PITCH_DIAMETER_PLATING_MULTIPLIER",
    "RoughnessParameter",
    "ProductionMethod",
    "SurfaceFinish",
    "Coating",
    "HeatTreatment",
    "ProcessNote",
    "FreeTextNote",
    "Callout",
    "CalloutSet",
    "CalloutChange",
    "CalloutDiff",
    "callout_diff",
    "marin_surface_factor",
    "plated_outer_dimension",
    "plated_inner_dimension",
    "plated_thread_pitch_diameter_shift",
    "heat_treated_material_id",
    "callout_scorecard",
]

MARIN_SURFACE_CITATION = (
    "Shigley's Mechanical Engineering Design, Marin surface factor k_a = a·S_u^b "
    "(surface-finish table, S_u in MPa); screening estimate, not a measured factor"
)

# k_a = a * S_u^b with S_u in MPa, indexed by how the surface was produced.
#
# The published table also gives the constants for S_u in kpsi, and the two sets are not
# independent: k_a is a pure number, so a_kpsi = a_MPa * (MPa per kpsi)^b must hold at
# every S_u. It does, to the table's own rounding, for all four rows — which is the
# cheapest available check that these constants were transcribed correctly, and the suite
# asserts it rather than trusting the transcription.
MARIN_SURFACE_CONSTANTS_MPA: dict[str, tuple[float, float]] = {
    "ground": (1.58, -0.085),
    "machined": (4.51, -0.265),
    "hot_rolled": (57.7, -0.718),
    "as_forged": (272.0, -0.995),
}

# Typical *attainable* arithmetic-mean roughness by production method, in micrometres.
# Screening bands, and they overlap by design: the point is not to grade a surface but to
# catch a callout that cannot be both things at once — an as-forged face at 0.4 µm Ra, a
# ground bore at 12 µm. Only a value outside the band is reported, never one merely near
# an edge.
TYPICAL_ROUGHNESS_UM: dict[str, tuple[float, float]] = {
    "polished": (0.025, 0.4),
    "ground": (0.1, 1.6),
    "machined": (0.4, 6.3),
    "hot_rolled": (3.2, 25.0),
    "as_forged": (6.3, 50.0),
}

# A coating of thickness t on the flanks of a 60° thread moves the pitch diameter by
# 2·t/sin(30°) = 4·t: the coating is deposited normal to a flank inclined at 30° to the
# thread axis, and the pitch diameter spans two flanks. The multiplier is derived in
# :func:`plated_thread_pitch_diameter_shift` rather than written as a bare 4, and the
# suite checks the derivation against the constant.
THREAD_PITCH_DIAMETER_PLATING_MULTIPLIER = 2.0 / sin(radians(30.0))


class RoughnessParameter(StrEnum):
    """Which roughness parameter a finish callout states."""

    RA = "Ra"  # arithmetic mean deviation
    RZ = "Rz"  # mean peak-to-valley height


class ProductionMethod(StrEnum):
    """How the surface was produced — the index of the Marin surface-factor table.

    ``POLISHED`` (mirror-polished or lapped) is the rotating-beam specimen's own surface
    and takes k_a = 1.0 by definition rather than by fit. ``MACHINED`` covers cold-drawn
    as well, as the published table does: they share a row.
    """

    POLISHED = "polished"
    GROUND = "ground"
    MACHINED = "machined"
    HOT_ROLLED = "hot_rolled"
    AS_FORGED = "as_forged"


def _characteristic_id(kind: str, scope: str | None, discriminator: str = "") -> str:
    """The persistent identifier for a characteristic at a scope.

    Derived from *what the characteristic is* — kind, scope, and for a note its category
    — and deliberately not from its value, so a revised value keeps its identity and a
    diff can call it a change rather than a deletion plus an addition.
    """
    payload = "\x00".join((kind, scope or "*part*", discriminator))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class _Callout(BaseModel):
    """Shared shape: a scope, a kind, and an identity derived from the two."""

    model_config = ConfigDict(frozen=True)

    # The semantic tag this callout applies to; ``None`` scopes it to the whole part.
    scope: str | None = None

    @model_validator(mode="after")
    def _scope_is_named_or_absent(self) -> _Callout:
        if self.scope is not None and not self.scope.strip():
            raise ValueError(
                "a callout's scope is a semantic tag or None for the whole part; an empty "
                "string is neither"
            )
        return self

    @property
    def discriminator(self) -> str:
        """What distinguishes two callouts of the same kind at the same scope."""
        return ""

    @property
    def characteristic_id(self) -> str:
        """The persistent identifier of the characteristic this callout declares."""
        return _characteristic_id(self.kind, self.scope, self.discriminator)

    @property
    def where(self) -> str:
        return self.scope or "whole part"

    def value_signature(self) -> str:
        """The declared value, as the string a diff compares. Overridden per kind."""
        return self.model_dump_json(exclude={"scope"})


class SurfaceFinish(_Callout):
    """A surface-finish callout: a roughness value, its parameter, and the method.

    ``method`` is what the Marin surface factor is derived from — the published fit is
    indexed by production method, not by roughness. ``roughness`` is still load-bearing:
    it is checked against the range the method typically attains, so a callout that names
    two incompatible things is surfaced rather than silently resolved toward one of them.
    """

    kind: Literal["surface_finish"] = "surface_finish"
    roughness: Quantity
    parameter: RoughnessParameter = RoughnessParameter.RA
    method: ProductionMethod

    @model_validator(mode="after")
    def _roughness_is_a_positive_length(self) -> SurfaceFinish:
        if not self.roughness.has_dimension("[length]"):
            raise ValueError(
                f"roughness must be a [length] quantity (µm, µin); got "
                f"{self.roughness.dimensionality} ({self.roughness})"
            )
        if self.roughness.to("um").magnitude <= 0:
            raise ValueError(f"roughness must be positive; got {self.roughness}")
        return self

    def value_signature(self) -> str:
        return f"{self.parameter.value} {self.roughness.to('um').magnitude:.4g} um {self.method}"

    def __str__(self) -> str:
        return (
            f"{self.method.value.replace('_', ' ')}, "
            f"{self.parameter.value} {self.roughness.to('um').magnitude:.3g} µm"
        )


class Coating(_Callout):
    """A coating or plating callout: a specification, a class, and a thickness range.

    The thickness is a *range* because plating is specified as one: a fit or a thread
    engagement has to be evaluated at both ends of it, and a check handed only the
    nominal is a check that never saw the worst case. ``minimum`` may equal ``maximum``
    for a single declared value.
    """

    kind: Literal["coating"] = "coating"
    specification: str  # e.g. "MIL-DTL-13924 Class 1" or "ASTM B633 SC1 Type III"
    coating_class: str | None = None
    minimum_thickness: Quantity
    maximum_thickness: Quantity

    @model_validator(mode="after")
    def _thickness_range_is_ordered_and_positive(self) -> Coating:
        for field, value in (
            ("minimum_thickness", self.minimum_thickness),
            ("maximum_thickness", self.maximum_thickness),
        ):
            if not value.has_dimension("[length]"):
                raise ValueError(
                    f"{field} must be a [length] quantity; got {value.dimensionality} ({value})"
                )
            if value.to("um").magnitude < 0:
                raise ValueError(f"{field} must not be negative; got {value}")
        low = self.minimum_thickness.to("um").magnitude
        high = self.maximum_thickness.to("um").magnitude
        if low > high:
            raise ValueError(
                f"the coating thickness range runs backwards: minimum {self.minimum_thickness} "
                f"exceeds maximum {self.maximum_thickness}"
            )
        if not self.specification.strip():
            raise ValueError("a coating callout must name its specification")
        return self

    def value_signature(self) -> str:
        return (
            f"{self.specification}|{self.coating_class or '-'}|"
            f"{self.minimum_thickness.to('um').magnitude:.4g}-"
            f"{self.maximum_thickness.to('um').magnitude:.4g} um"
        )

    def __str__(self) -> str:
        cls = f" {self.coating_class}" if self.coating_class else ""
        return (
            f"{self.specification}{cls}, "
            f"{self.minimum_thickness.to('um').magnitude:.3g}–"
            f"{self.maximum_thickness.to('um').magnitude:.3g} µm"
        )


class HeatTreatment(_Callout):
    """A heat-treatment callout: the specification and the condition it produces.

    ``condition`` is the string that has to line up with a material record — ``"T6"``,
    ``"CD"``, ``"QT"``. Anvilate does not infer properties from a hardness range; it
    resolves the *declared condition* against the database and reports "not evaluated"
    naming the condition when no record backs it. ``hardness`` travels with the callout
    for the drawing and the inspection, and is never converted into a strength.
    """

    kind: Literal["heat_treatment"] = "heat_treatment"
    specification: str  # e.g. "AMS 2759/1" or "quench and temper per SAE J1268"
    condition: str  # the material-record condition code this produces
    hardness: str | None = None  # e.g. "38-42 HRC" — recorded, never converted

    @model_validator(mode="after")
    def _named(self) -> HeatTreatment:
        if not self.specification.strip():
            raise ValueError("a heat-treatment callout must name its specification")
        if not self.condition.strip():
            raise ValueError(
                "a heat-treatment callout must name the condition it produces; the "
                "condition is what selects the material record, and a treatment with no "
                "named condition cannot select one"
            )
        return self

    def value_signature(self) -> str:
        return f"{self.specification}|{self.condition}|{self.hardness or '-'}"

    def __str__(self) -> str:
        hardness = f", {self.hardness}" if self.hardness else ""
        return f"{self.specification} to condition {self.condition}{hardness}"


class ProcessNote(_Callout):
    """A structured process note: a recognized category and typed parameters.

    The category is what makes it consumable — two notes of different categories at the
    same scope are different characteristics and get different identifiers. Parameters
    are dimensioned :class:`~anvilate.units.Quantity` values, so a note cannot smuggle an
    unchecked number into a check the way a sentence can.
    """

    kind: Literal["process_note"] = "process_note"
    category: str  # e.g. "deburr", "shot_peen", "stress_relieve"
    parameters: dict[str, Quantity] = {}

    @model_validator(mode="after")
    def _categorized(self) -> ProcessNote:
        if not self.category.strip():
            raise ValueError(
                "a structured process note must name its category; a note with no "
                "category is free text and belongs in a FreeTextNote"
            )
        return self

    @property
    def discriminator(self) -> str:
        return self.category

    def value_signature(self) -> str:
        items = ", ".join(f"{k}={self.parameters[k]}" for k in sorted(self.parameters))
        return f"{self.category}({items})"

    def __str__(self) -> str:
        return self.value_signature()


class FreeTextNote(_Callout):
    """An unstructured note: stored, distinguished, and unreadable by any check.

    It exists so that a drawing's prose is not lost, and it carries no typed parameters
    at all — :meth:`CalloutSet.consumable` excludes it, which is the enforcement rather
    than a convention that a reviewer has to remember.
    """

    kind: Literal["free_text"] = "free_text"
    text: str
    sequence: int = 1  # distinguishes two free-text notes at the same scope

    @model_validator(mode="after")
    def _has_text(self) -> FreeTextNote:
        if not self.text.strip():
            raise ValueError("a free-text note with no text is not a note")
        if self.sequence < 1:
            raise ValueError(f"a note's sequence starts at 1; got {self.sequence}")
        return self

    @property
    def discriminator(self) -> str:
        return str(self.sequence)

    def value_signature(self) -> str:
        return self.text.strip()

    def __str__(self) -> str:
        return f"note: {self.text.strip()}"


Callout = SurfaceFinish | Coating | HeatTreatment | ProcessNote | FreeTextNote


class CalloutSet(BaseModel):
    """The callouts declared on a part, addressable by characteristic and by tag."""

    model_config = ConfigDict(frozen=True)

    callouts: tuple[Callout, ...] = ()

    @model_validator(mode="after")
    def _one_callout_per_characteristic(self) -> CalloutSet:
        seen: dict[str, Callout] = {}
        for callout in self.callouts:
            key = callout.characteristic_id
            if key in seen:
                raise ValueError(
                    f"two {callout.kind} callouts declare the same characteristic at "
                    f"{callout.where!r}: {seen[key]} and {callout}. One characteristic "
                    "carries one declared value; a second one is a contradiction, not a "
                    "refinement"
                )
            seen[key] = callout
        return self

    def resolved_against(self, known_tags: Iterable[str]) -> CalloutSet:
        """This set, having checked every scope tag exists — or raise, naming the tag.

        Whole-part callouts (``scope is None``) resolve trivially. A scoped callout whose
        tag is not in the graph is refused by name: an unresolvable scope means a check
        that should have consumed the callout never will, and the part screens as though
        the callout were never written.
        """
        tags = set(known_tags)
        missing = sorted(
            {c.scope for c in self.callouts if c.scope is not None and c.scope not in tags}
        )
        if missing:
            raise ValueError(
                f"callouts reference semantic tags that do not exist: {missing}. A callout "
                "scoped to a tag nothing defines is never consumed by any check"
            )
        return self

    def for_tag(self, tag: str | None) -> tuple[Callout, ...]:
        """Every callout scoped to ``tag`` (``None`` for the whole-part callouts)."""
        return tuple(c for c in self.callouts if c.scope == tag)

    def consumable(self) -> tuple[Callout, ...]:
        """The typed callouts, excluding free text — what a check is allowed to read."""
        return tuple(c for c in self.callouts if not isinstance(c, FreeTextNote))

    def by_characteristic(self) -> dict[str, Callout]:
        """The set keyed by persistent characteristic identifier."""
        return {c.characteristic_id: c for c in self.callouts}

    def finish_for(self, tag: str | None) -> SurfaceFinish | None:
        """The surface finish at ``tag``, or ``None``."""
        return next((c for c in self.for_tag(tag) if isinstance(c, SurfaceFinish)), None)

    def coating_for(self, tag: str | None) -> Coating | None:
        """The coating at ``tag``, or ``None``."""
        return next((c for c in self.for_tag(tag) if isinstance(c, Coating)), None)

    def heat_treatment_for(self, tag: str | None) -> HeatTreatment | None:
        """The heat treatment at ``tag``, or ``None``."""
        return next((c for c in self.for_tag(tag) if isinstance(c, HeatTreatment)), None)

    def __str__(self) -> str:
        typed = len(self.consumable())
        return f"{len(self.callouts)} callout(s), {typed} typed"


class CalloutChange(BaseModel):
    """One characteristic whose declared value moved between two revisions."""

    model_config = ConfigDict(frozen=True)

    characteristic_id: str
    scope: str | None
    kind: str
    previous: str
    current: str

    def __str__(self) -> str:
        where = self.scope or "whole part"
        return (
            f"{self.kind} at {where} [{self.characteristic_id}]: {self.previous} → {self.current}"
        )


class CalloutDiff(BaseModel):
    """What changed between two revisions of a part's callouts, by characteristic."""

    model_config = ConfigDict(frozen=True)

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[CalloutChange, ...] = ()

    @property
    def unchanged_identity(self) -> bool:
        """Whether every characteristic present before is still present, changed or not."""
        return not self.added and not self.removed

    def __str__(self) -> str:
        return f"{len(self.added)} added, {len(self.removed)} removed, {len(self.changed)} changed"


def callout_diff(previous: CalloutSet, current: CalloutSet) -> CalloutDiff:
    """What moved between two revisions, matched by persistent characteristic identity.

    Because identity is derived from what the characteristic *is* and not from its value,
    a revised finish shows up as one ``changed`` entry rather than a removal and an
    addition — which is the difference between "this face's finish got tighter" and "the
    finish requirement disappeared and a different one appeared".
    """
    before = previous.by_characteristic()
    after = current.by_characteristic()
    changed = tuple(
        CalloutChange(
            characteristic_id=key,
            scope=after[key].scope,
            kind=after[key].kind,
            previous=before[key].value_signature(),
            current=after[key].value_signature(),
        )
        for key in sorted(set(before) & set(after))
        if before[key].value_signature() != after[key].value_signature()
    )
    return CalloutDiff(
        added=tuple(sorted(set(after) - set(before))),
        removed=tuple(sorted(set(before) - set(after))),
        changed=changed,
    )


def marin_surface_factor(finish: SurfaceFinish, *, ultimate_strength: Quantity) -> float:
    """The Marin surface factor k_a implied by a declared finish, k_a = a·S_u^b.

    The published fit is indexed by production method, so that is what this reads;
    ``POLISHED`` is the rotating-beam specimen's own surface and returns exactly 1.0
    rather than a fitted value. The factor is capped at 1.0, because the fit crosses one
    for a ground surface on a low-strength steel and no real surface improves on the
    polished specimen.

    ``ultimate_strength`` must be a positive stress. Feed the result to
    :func:`~anvilate.analysis.fatigue.marin_endurance_limit` as its ``surface_factor``.
    Screening only — see :data:`MARIN_SURFACE_CITATION`.
    """
    if not ultimate_strength.has_dimension("[pressure]"):
        raise ValueError(
            f"ultimate_strength must be a [pressure] quantity; got "
            f"{ultimate_strength.dimensionality} ({ultimate_strength})"
        )
    su = ultimate_strength.to("MPa").magnitude
    if su <= 0:
        raise ValueError(f"ultimate_strength must be positive; got {ultimate_strength}")
    if finish.method is ProductionMethod.POLISHED:
        return 1.0
    a, b = MARIN_SURFACE_CONSTANTS_MPA[finish.method.value]
    return min(1.0, a * su**b)


def _roughness_contradiction(finish: SurfaceFinish) -> str | None:
    """The reason a declared roughness cannot come from the declared method, or ``None``."""
    low, high = TYPICAL_ROUGHNESS_UM[finish.method.value]
    ra = finish.roughness.to("um").magnitude
    if low <= ra <= high:
        return None
    side = "finer" if ra < low else "coarser"
    return (
        f"{finish.parameter.value} {ra:.3g} µm is {side} than "
        f"{finish.method.value.replace('_', ' ')} typically attains ({low:g}–{high:g} µm)"
    )


def plated_outer_dimension(nominal: Quantity, coating: Coating) -> tuple[Quantity, Quantity]:
    """An external diameter or width across the coating's declared thickness range.

    A coating lands on both sides of an outside dimension, so the dimension grows by twice
    the thickness. Returned as ``(at minimum plating, at maximum plating)`` — a fit has to
    be evaluated at both, and the maximum is the one that closes a clearance.
    """
    return _plated(nominal, coating, sign=+1.0)


def plated_inner_dimension(nominal: Quantity, coating: Coating) -> tuple[Quantity, Quantity]:
    """A bore or slot width across the coating's declared thickness range.

    A coating inside a hole shrinks it by twice the thickness. Returned as ``(at minimum
    plating, at maximum plating)``; here it is the *maximum* plating that produces the
    smallest bore, so the pair is still ordered by plating thickness and not by size.
    """
    return _plated(nominal, coating, sign=-1.0)


def _plated(nominal: Quantity, coating: Coating, *, sign: float) -> tuple[Quantity, Quantity]:
    if not nominal.has_dimension("[length]"):
        raise ValueError(
            f"the nominal dimension must be a [length] quantity; got "
            f"{nominal.dimensionality} ({nominal})"
        )
    unit = nominal.unit
    base = nominal.to("mm").magnitude
    if base <= 0:
        raise ValueError(f"the nominal dimension must be positive; got {nominal}")
    out = []
    for thickness in (coating.minimum_thickness, coating.maximum_thickness):
        plated = base + sign * 2.0 * thickness.to("mm").magnitude
        if plated <= 0:
            raise ValueError(
                f"a coating {thickness} thick closes a {nominal} feature entirely "
                f"(plated size {plated:.4g} mm); the callout and the geometry disagree"
            )
        out.append(Quantity(magnitude=plated, unit="mm").to(unit))
    return out[0], out[1]


def plated_thread_pitch_diameter_shift(coating: Coating) -> tuple[Quantity, Quantity]:
    """How far a 60° thread's pitch diameter moves across the plating range.

    Not twice the thickness — *four* times it. The coating is deposited normal to a flank
    inclined at 30° to the thread axis, so a radial thickness t displaces the flank by
    t/sin(30°) = 2t, and the pitch diameter spans two flanks. Getting this wrong by the
    factor of two is the classic plated-thread interference: an external thread plated to
    the top of its range can lose its entire allowance and refuse to assemble.

    Returned as ``(at minimum plating, at maximum plating)``, always positive: apply it as
    a growth on an external thread and a reduction on an internal one.
    """
    multiplier = THREAD_PITCH_DIAMETER_PLATING_MULTIPLIER
    return tuple(  # type: ignore[return-value]
        Quantity(magnitude=multiplier * t.to("mm").magnitude, unit="mm")
        for t in (coating.minimum_thickness, coating.maximum_thickness)
    )


def heat_treated_material_id(
    base_material: str, treatment: HeatTreatment, *, known_materials: Iterable[str]
) -> str | None:
    """The material record for ``base_material`` in the declared condition, or ``None``.

    The bundled database carries the condition in the record identity — ``AA-6061-T6``,
    ``AISI-1018-CD`` — so resolution is a lookup, not an inference: either a record exists
    for the declared condition or none does. ``None`` is the honest answer for the second
    case and a check that gets it reports "not evaluated" naming the condition, rather
    than screening the untreated row and calling the result a screening of the treated
    part.

    A ``base_material`` that already names the declared condition resolves to itself, so
    declaring "AISI-1018-CD, condition CD" is consistent rather than a miss.
    """
    known = set(known_materials)
    condition = treatment.condition.strip()
    if base_material in known and base_material.upper().endswith(f"-{condition.upper()}"):
        return base_material
    candidate = f"{base_material}-{condition}"
    if candidate in known:
        return candidate
    # The database is keyed case-sensitively but a callout is written by a person.
    folded = {k.upper(): k for k in known}
    return folded.get(candidate.upper())


def callout_scorecard(
    callouts: CalloutSet,
    *,
    ultimate_strength: Quantity | None = None,
    base_material: str | None = None,
    known_materials: Iterable[str] = (),
) -> Scorecard:
    """What the declared callouts do to the checks, and where they contradict one.

    One entry per consumable callout, stating the value consumed and its effect — the
    surface factor a finish implies, the dimensional shift a coating implies, the material
    record a heat treatment resolves to. A callout the caller gave no context for is
    ``NOT_EVALUATED`` naming what is missing, never dropped; a contradiction between a
    callout and what it would have to be true for is ``FAIL``, never resolved by
    preferring one side.

    Free-text notes produce no entries at all: they are not consumable, and an entry for
    one would imply a check had read it.
    """
    entries: list[ScorecardEntry] = []
    for callout in callouts.consumable():
        marker = f"[{callout.characteristic_id}]"
        if isinstance(callout, SurfaceFinish):
            contradiction = _roughness_contradiction(callout)
            if contradiction is not None:
                entries.append(
                    ScorecardEntry(
                        name=f"surface finish at {callout.where}",
                        status=CheckStatus.FAIL,
                        detail=f"{marker} {callout} contradicts itself: {contradiction}",
                        reference=MARIN_SURFACE_CITATION,
                    )
                )
            elif ultimate_strength is None:
                entries.append(
                    ScorecardEntry(
                        name=f"surface finish at {callout.where}",
                        status=CheckStatus.NOT_EVALUATED,
                        detail=(
                            f"{marker} {callout} declared, but no ultimate strength was "
                            "supplied to derive the surface factor from"
                        ),
                        reference=MARIN_SURFACE_CITATION,
                    )
                )
            else:
                factor = marin_surface_factor(callout, ultimate_strength=ultimate_strength)
                entries.append(
                    ScorecardEntry(
                        name=f"surface finish at {callout.where}",
                        status=CheckStatus.PASS,
                        detail=(
                            f"{marker} {callout} → Marin surface factor k_a = {factor:.3f} "
                            f"at S_u = {ultimate_strength.to('MPa').magnitude:.0f} MPa"
                        ),
                        reference=MARIN_SURFACE_CITATION,
                    )
                )
        elif isinstance(callout, Coating):
            low, high = plated_thread_pitch_diameter_shift(callout)
            entries.append(
                ScorecardEntry(
                    name=f"coating at {callout.where}",
                    status=CheckStatus.PASS,
                    detail=(
                        f"{marker} {callout} → outside dimensions grow "
                        f"{2 * callout.minimum_thickness.to('um').magnitude:.3g}–"
                        f"{2 * callout.maximum_thickness.to('um').magnitude:.3g} µm on "
                        f"diameter, and a 60° thread's pitch diameter by "
                        f"{low.to('um').magnitude:.3g}–{high.to('um').magnitude:.3g} µm"
                    ),
                )
            )
        elif isinstance(callout, HeatTreatment):
            if base_material is None:
                entries.append(
                    ScorecardEntry(
                        name=f"heat treatment at {callout.where}",
                        status=CheckStatus.NOT_EVALUATED,
                        detail=(
                            f"{marker} {callout} declared, but no base material was "
                            "supplied to resolve the condition against"
                        ),
                    )
                )
                continue
            resolved = heat_treated_material_id(
                base_material, callout, known_materials=known_materials
            )
            if resolved is None:
                entries.append(
                    ScorecardEntry(
                        name=f"heat treatment at {callout.where}",
                        status=CheckStatus.NOT_EVALUATED,
                        detail=(
                            f"{marker} {callout}: no material record for {base_material!r} "
                            f"in condition {callout.condition!r}; properties for the "
                            "treated part are unavailable"
                        ),
                    )
                )
            else:
                entries.append(
                    ScorecardEntry(
                        name=f"heat treatment at {callout.where}",
                        status=CheckStatus.PASS,
                        detail=(
                            f"{marker} {callout} → material properties resolved from "
                            f"record {resolved!r}"
                        ),
                    )
                )
        else:  # ProcessNote — typed, recorded, and consumed by nothing yet
            entries.append(
                ScorecardEntry(
                    name=f"process note '{callout.category}' at {callout.where}",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"{marker} {callout} is typed and carried, but no check in this "
                        "library consumes this category yet"
                    ),
                )
            )
    return Scorecard(entries=tuple(entries))
