"""Failure-mode coverage: what the card did not check, by name.

Anvilate answers every question the document asks. The expensive failures are the ones
nobody asked. A card can report a clean pass on twelve checks while the part goes on to
fail by self-loosening at a bolted joint under transverse vibration, by galvanic corrosion
at a dissimilar-metal interface, by fatigue at a weld toe nobody assessed. None of those is
a bug in a screen: each is a mode no screen addressed and no entry mentioned, and a silent
card reads as a clean one.

A :class:`FailureMode` is one such mode as a record: what it is, the **declared facts** it
applies to, the stage it is normally discovered at, and the citation it comes from.
Applicability keys on facts a document states — an element class, a material pair, an
interface kind — and never on free text, because a catalogue that matched prose would fire
on the wording of a description rather than on the design.

:func:`coverage` answers, for one card: which modes apply, which of them a check on that
card addresses, which are left to a physical test, and which are **unaddressed** — named,
counted, and beside the population they were counted from. Never a bare percentage: a
coverage figure with no denominator and no list is the number that makes an incomplete card
read as a complete one.

The catalogue is a **floor, never an exhaustive list**. It says what this library knows to
ask about; it cannot say that nothing else can go wrong, and every rendering says so.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from ._models import ItemCollection, Named, Provenance, StatableModel, each_one
from .scorecard import CheckStatus, Scorecard
from .verification import VerificationArchetype, VerificationMethod

__all__ = [
    "DiscoveryStage",
    "Applicability",
    "FailureMode",
    "ModeCatalog",
    "ModeCoverage",
    "CoverageReport",
    "DEFAULT_CATALOG",
    "TEST_ARCHETYPES",
    "coverage",
    "facts_from_spec",
    "CATALOG_IS_A_FLOOR",
    "UNDECLARABLE_FACTS",
]

#: What a Design Spec cannot state today, so a mode keyed on it can never apply from a
#: document. Said out loud rather than left as an empty result: a coverage report that
#: silently cannot reach half its catalogue is the shape this module exists to refuse.
UNDECLARABLE_FACTS = (
    "a mode applies only on a fact the document states: an element, an interface kind, an "
    "environment, or a material pair the two references make dissimilar. A key the document "
    "leaves out is never read as benign — the mode simply cannot apply, and the design may "
    "still be exposed to it"
)

#: Printed wherever coverage is. The catalogue is what this library knows to ask about, and
#: a reader who takes it for the set of things that can go wrong has been given false
#: comfort by a tool whose whole purpose is refusing to give any.
CATALOG_IS_A_FLOOR = (
    "this catalogue is a floor and never an exhaustive list: it says what this library "
    "knows to ask about, not that nothing else can go wrong"
)


class DiscoveryStage(StrEnum):
    """Where a mode is normally found. A stage, not a severity — they are different facts.

    The economics of the thing: a defect corrected in design costs a parameter change, in
    production a tooling change, in the field a recall. A mode usually discovered in
    qualification is not *worse* than one discovered in design; it is more expensive to
    have missed, which is a statement about when to look and not about how bad it is.
    """

    DESIGN = "design"
    QUALIFICATION = "qualification"
    PRODUCTION = "production"
    FIELD = "field"


class Applicability(StatableModel):
    """The declared facts a mode applies to, as a conjunction over stated keys.

    Every key is matched against a fact the document states — ``element`` against the
    declared ``element_type``, ``material_pair`` against a dissimilar-metal joint the
    document names, ``interface`` against a declared interface kind. A key the document does
    not state is not a match: a mode cannot apply to a design on the strength of something
    nobody wrote down.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    elements: tuple[Named, ...] = ()
    interfaces: tuple[Named, ...] = ()
    environments: tuple[Named, ...] = ()
    dissimilar_metals: bool = False

    @model_validator(mode="after")
    def _says_something(self) -> Applicability:
        if not (self.elements or self.interfaces or self.environments or self.dissimilar_metals):
            raise ValueError(
                "an applicability that names no element, interface, environment or material "
                "pair applies to everything, which is the same as saying nothing about when "
                "the mode applies"
            )
        return self

    def applies(self, facts: Mapping[str, object]) -> bool:
        """Whether the declared ``facts`` match every key this record states."""
        if self.elements and facts.get("element") not in self.elements:
            return False
        if self.interfaces and not set(self.interfaces) & set(facts.get("interfaces") or ()):
            return False
        if self.environments and facts.get("environment") not in self.environments:
            return False
        return not (self.dissimilar_metals and not facts.get("dissimilar_metals"))

    def __str__(self) -> str:
        parts = []
        if self.elements:
            parts.append(f"elements {', '.join(self.elements)}")
        if self.interfaces:
            parts.append(f"interfaces {', '.join(self.interfaces)}")
        if self.environments:
            parts.append(f"environments {', '.join(self.environments)}")
        if self.dissimilar_metals:
            parts.append("a declared dissimilar-metal pair")
        return "; ".join(parts)


class FailureMode(StatableModel):
    """One way a design fails, what it applies to, and where it is normally found."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    description: Provenance
    applicability: Applicability
    stage: DiscoveryStage
    citation: Provenance
    version: Named = "1.0.0"
    #: The check names that address this mode, and the keys of the verification archetypes
    #: that reach it where analysis cannot. A mode with neither is one this library can only
    #: report. A shipped check binds by declaring the mode instead (``ScorecardEntry.addresses``).
    addressed_by: tuple[Named, ...] = ()
    tested_by: tuple[Named, ...] = ()

    def __str__(self) -> str:
        return f"{self.id} ({self.stage.value}): {self.description} [{self.citation}]"


class ModeCatalog(ItemCollection, StatableModel):
    """The modes this build knows to ask about."""

    model_config = ConfigDict(frozen=True)

    modes: tuple[FailureMode, ...] = ()

    @model_validator(mode="after")
    def _distinct(self) -> ModeCatalog:
        identifiers = [mode.id for mode in self.modes]
        if len(set(identifiers)) != len(identifiers):
            doubled = sorted({name for name in identifiers if identifiers.count(name) > 1})
            raise ValueError(f"the catalogue carries one mode id twice: {doubled}")
        return self

    def applicable(self, facts: Mapping[str, object]) -> tuple[FailureMode, ...]:
        """Every mode whose applicability the declared facts satisfy, in catalogue order."""
        return tuple(mode for mode in self.modes if mode.applicability.applies(facts))

    def extended(self, *modes: FailureMode) -> ModeCatalog:
        """This catalogue with more modes — a module's or a user's — refusing a clash."""
        return ModeCatalog(modes=(*self.modes, *modes))

    def __str__(self) -> str:
        return f"{len(self.modes)} failure modes; {CATALOG_IS_A_FLOOR}"


class ModeCoverage(StatableModel):
    """One applicable mode and what, if anything, on this card addresses it."""

    model_config = ConfigDict(frozen=True)

    mode: FailureMode
    checks: tuple[Named, ...] = ()
    tests: tuple[Named, ...] = ()

    @property
    def addressed(self) -> bool:
        """Whether a check that RAN addresses this mode.

        A test archetype does not count. `verification-planning` states the rule this
        follows: a plan is never evidence, and a mode "left to a fretting test" has had
        nothing done about it — reporting it as covered is the silent green a coverage
        number is most likely to produce.
        """
        return bool(self.checks)

    @property
    def planned(self) -> bool:
        """Whether nothing checked it and a physical test is what would reach it."""
        return bool(self.tests) and not self.checks

    def __str__(self) -> str:
        if self.checks:
            return f"{self.mode.id}: addressed by {', '.join(self.checks)}"
        if self.tests:
            return f"{self.mode.id}: no check; left to {', '.join(self.tests)}"
        return f"{self.mode.id}: UNADDRESSED — {self.mode.description}"


class CoverageReport(StatableModel):
    """What applied, what was addressed, and what nobody looked at — with the population."""

    model_config = ConfigDict(frozen=True)

    entries: tuple[ModeCoverage, ...] = ()
    catalog_size: int = Field(ge=0)

    @property
    def applicable(self) -> int:
        return len(self.entries)

    def unaddressed(self) -> tuple[ModeCoverage, ...]:
        """Applicable, no check that ran, and no test archetype either — task 2.4's set."""
        return tuple(entry for entry in self.entries if not entry.addressed and not entry.planned)

    def addressed(self) -> tuple[ModeCoverage, ...]:
        return tuple(entry for entry in self.entries if entry.addressed)

    def planned(self) -> tuple[ModeCoverage, ...]:
        """Applicable, no check, and a physical test is what would reach them."""
        return tuple(entry for entry in self.entries if entry.planned)

    def complete(self) -> bool:
        """Whether a check that ran addresses every applicable mode — and at least one applied.

        A mode left to a test is not complete: the test is a plan, and this is the question
        "has anything actually been done about it", which a plan does not answer.

        **Nothing applying is not completeness.** "Every applicable mode is addressed" is
        vacuously true of none, and an empty catalogue — or one that knows nothing about this
        element — would otherwise report the fullest coverage there is. No mode applying is a
        statement about the catalogue, and the rendering says so.
        """
        return bool(self.entries) and len(self.addressed()) == len(self.entries)

    def by_stage(self) -> dict[DiscoveryStage, tuple[ModeCoverage, ...]]:
        """The modes no check reached, grouped by where they are normally discovered.

        A stage, rendered as a stage: it says when this would be found if nobody looks now,
        which is a cost, not a severity ranking of the modes against each other.
        """
        grouped: dict[DiscoveryStage, list[ModeCoverage]] = {}
        for entry in (*self.unaddressed(), *self.planned()):
            grouped.setdefault(entry.mode.stage, []).append(entry)
        return {stage: tuple(entries) for stage, entries in grouped.items()}

    def __str__(self) -> str:
        head = (
            f"failure modes: {len(self.addressed())} of {self.applicable} applicable "
            f"addressed by a check that ran, {len(self.planned())} left to a physical test, "
            f"{len(self.unaddressed())} unaddressed, from a catalogue of {self.catalog_size}"
        )
        lines = [head, f"  {CATALOG_IS_A_FLOOR}", f"  {UNDECLARABLE_FACTS}"]
        if not self.catalog_size:
            lines.append("  the catalogue is empty: nothing was asked, so nothing is covered")
            return "\n".join(lines)
        if not self.entries:
            lines.append(
                "  no mode in the catalogue applies to what this document declares — which says "
                "what the catalogue knows, not that this design has no failure modes"
            )
            return "\n".join(lines)
        lines.extend(f"  {entry}" for entry in self.entries)
        for stage, entries in self.by_stage().items():
            names = ", ".join(entry.mode.id for entry in entries)
            lines.append(f"  not yet checked, normally found at {stage.value}: {names}")
        return "\n".join(lines)


def coverage(
    card: Scorecard,
    facts: Mapping[str, object],
    *,
    catalog: ModeCatalog | None = None,
    archetypes: Sequence[VerificationArchetype] = (),
) -> CoverageReport:
    """Which catalogued modes apply to ``facts``, and which of them ``card`` addresses.

    A check addresses a mode by **declaring** it: a :class:`~anvilate.scorecard.ScorecardEntry`
    whose ``addresses`` names the mode's id. That is data the screen wrote down, and it is
    how every shipped check binds. A catalogue can also bind by check name through
    :attr:`FailureMode.addressed_by`, for a team's own checks whose names it controls.

    A mode is addressed by a check only when that check **ran**: a mode whose only check
    came back not-evaluated is unaddressed, which is the whole point — the card already
    says the check did not run, and counting it as coverage would use one gap to hide
    another.

    A mode's ``tested_by`` names verification archetypes by key, resolved against
    :data:`TEST_ARCHETYPES` and any ``archetypes`` supplied. A key that resolves to nothing is
    refused: a mode "left to" a test nobody defined is left to nothing.

    ``facts`` are the declared facts to match on: ``element``, ``interfaces``,
    ``environment``, ``dissimilar_metals``. What a document does not state cannot make a
    mode apply.
    """
    catalogue = catalog if catalog is not None else DEFAULT_CATALOG
    supplied = each_one(archetypes, VerificationArchetype, named="archetypes")
    lookup = {archetype.key: archetype for archetype in (*TEST_ARCHETYPES, *supplied)}
    ran = [entry for entry in card.entries if entry.status is not CheckStatus.NOT_EVALUATED]
    ran_names = {entry.name for entry in ran}
    entries = []
    for mode in catalogue.applicable(facts):
        unknown = sorted(key for key in mode.tested_by if key not in lookup)
        if unknown:
            raise ValueError(
                f"failure mode '{mode.id}' is left to {unknown}, which no verification "
                f"archetype defines; known: {sorted(lookup)}"
            )
        declared = [entry.name for entry in ran if mode.id in entry.addresses]
        named = [name for name in mode.addressed_by if name in ran_names]
        entries.append(
            ModeCoverage(
                mode=mode,
                checks=tuple(dict.fromkeys(declared + named)),
                tests=tuple(lookup[key].title for key in mode.tested_by),
            )
        )
    return CoverageReport(entries=tuple(entries), catalog_size=len(catalogue.modes))


def facts_from_spec(spec: Any) -> dict[str, object]:
    """The declared facts of a Design Spec, for :func:`coverage` to match on.

    Four keys, each read off something the document states: the element, the kinds of its
    declared interfaces, the environment it declares, and whether any interface names a
    mating material different from the part's own.

    **Dissimilarity is derived, not declared.** An author does not tick a "dissimilar
    metals" box: the document names the part's material and the material on the other side
    of a joint, and this compares the two references. A self-reported flag would be one more
    thing to get wrong, and the pair is already written down.

    A key the document omits is absent, never false-by-default: the mode does not apply, and
    :data:`UNDECLARABLE_FACTS` — printed with every report — says that this is a statement
    about the document and not about the design.
    """
    interfaces = tuple(
        interface.kind.value
        for interface in getattr(spec, "interfaces", ())
        if getattr(interface, "kind", None) is not None
    )
    mating = {
        interface.mating_material.ref
        for interface in getattr(spec, "interfaces", ())
        if getattr(interface, "mating_material", None) is not None
    }
    facts: dict[str, object] = {"element": spec.element_type, "interfaces": interfaces}
    if spec.environment is not None:
        facts["environment"] = spec.environment.value
    if mating:
        facts["dissimilar_metals"] = any(ref != spec.material.ref for ref in mating)
    return facts


#: The physical tests the shipped catalogue leaves its modes to, as verification archetypes a
#: mode names by key. None is routed from a check's citation — no shipped check implies one —
#: so they live here rather than in `anvilate.verification.DEFAULT_ARCHETYPES`, where the
#: verification plan would carry five tests it can never reach.
TEST_ARCHETYPES: tuple[VerificationArchetype, ...] = (
    VerificationArchetype(
        key="transverse-vibration",
        method=VerificationMethod.TEST,
        title="transverse vibration (Junker) test",
        citation=(
            "DIN 65151:2002 dynamic testing of the locking characteristics of fasteners "
            "under transverse loading"
        ),
    ),
    VerificationArchetype(
        key="salt-spray",
        method=VerificationMethod.TEST,
        title="neutral salt spray exposure",
        citation="ASTM B117-19 Standard Practice for Operating Salt Spray (Fog) Apparatus",
    ),
    VerificationArchetype(
        key="constant-amplitude-fatigue",
        method=VerificationMethod.TEST,
        title="constant-amplitude fatigue test",
        citation=(
            "ASTM E466-15 Standard Practice for Conducting Force Controlled Constant "
            "Amplitude Axial Fatigue Tests of Metallic Materials"
        ),
    ),
    VerificationArchetype(
        key="fretting-fatigue",
        method=VerificationMethod.TEST,
        title="fretting fatigue test",
        citation="ASTM E2789-10 Standard Guide for Fretting Fatigue Testing",
    ),
    VerificationArchetype(
        key="thermal-cycling",
        method=VerificationMethod.TEST,
        title="thermal cycling test",
        citation="ISO 16750-4:2010 temperature cycling of assembled equipment",
    ),
)


#: What this build knows to ask about. Every entry cites a source a reader can go and read,
#: and names the checks this library ships that address it — a mode bound to a check nobody
#: ships would report coverage that does not exist.
DEFAULT_CATALOG = ModeCatalog(
    modes=(
        FailureMode(
            id="shaft fatigue at a stress raiser",
            description=(
                "a rotating shaft cracking at a shoulder, keyway or groove under reversed "
                "bending, well below the load that would yield it"
            ),
            applicability=Applicability(elements=("transmission_shaft",)),
            stage=DiscoveryStage.FIELD,
            citation=(
                "Shigley, Mechanical Engineering Design, 10th ed. (2015), shaft design for fatigue"
            ),
        ),
        FailureMode(
            id="gear tooth surface pitting",
            description=(
                "contact fatigue pitting the flanks of meshing gear teeth, the surface giving "
                "way long before the tooth root breaks"
            ),
            applicability=Applicability(elements=("spur_gear_mesh",)),
            stage=DiscoveryStage.FIELD,
            citation="ISO 6336-2:2019 surface durability (pitting)",
        ),
        FailureMode(
            id="rolling-contact fatigue of a bearing",
            description=(
                "subsurface fatigue spalling the raceways of a rolling bearing after a number "
                "of revolutions its rating life predicts only statistically"
            ),
            applicability=Applicability(elements=("rolling_bearing",)),
            stage=DiscoveryStage.FIELD,
            citation="ISO 281:2007 dynamic load ratings and rating life",
        ),
        FailureMode(
            id="coil spring buckling",
            description=(
                "a slender compression spring bowing sideways under deflection, losing its "
                "force and rubbing its guide, while every stress on it passes"
            ),
            applicability=Applicability(elements=("helical_compression_spring",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Shigley, Mechanical Engineering Design, 10th ed. (2015), "
                "stability of compression springs"
            ),
        ),
        FailureMode(
            id="bolt self-loosening",
            description=(
                "a preloaded bolt backing off under transverse vibration, losing preload "
                "before any static check on it would fail"
            ),
            applicability=Applicability(elements=("bolted_connection",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Junker, 'New Criteria for Self-Loosening of Fasteners Under Vibration', "
                "SAE 690055 (1969)"
            ),
            tested_by=("transverse-vibration",),
        ),
        FailureMode(
            id="galvanic corrosion",
            description=(
                "the less noble metal of a wetted dissimilar-metal pair corroding at the "
                "joint, at a rate set by the area ratio rather than by either metal alone"
            ),
            applicability=Applicability(dissimilar_metals=True),
            stage=DiscoveryStage.FIELD,
            citation="ASTM G82-98 (2014), Standard Guide for Galvanic Series and Corrosion",
            tested_by=("salt-spray",),
        ),
        FailureMode(
            id="weld toe fatigue",
            description=(
                "a crack initiating at the toe of a welded joint under cyclic load, at a "
                "stress range far below the joint's static capacity"
            ),
            applicability=Applicability(elements=("welded_connection",)),
            stage=DiscoveryStage.FIELD,
            citation="EN 1993-1-9:2005 detail categories for welded joints",
            addressed_by=(),
            tested_by=("constant-amplitude-fatigue",),
        ),
        FailureMode(
            id="fretting at a clamped interface",
            description=(
                "micro-slip at a clamped joint wearing the faying surfaces and nucleating "
                "cracks, where neither part is overloaded and the joint never comes apart"
            ),
            applicability=Applicability(interfaces=("clamped", "bolted_face")),
            stage=DiscoveryStage.FIELD,
            citation="Waterhouse, *Fretting Fatigue* (1981), the clamped-joint case",
            tested_by=("fretting-fatigue",),
        ),
        FailureMode(
            id="glass fracture at a mount contact",
            description=(
                "a lens clamped by a retainer cracking from the tension beside the contact, "
                "where the preload holds and no stress in the metal is high"
            ),
            applicability=Applicability(interfaces=("clamped",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation="Johnson, Contact Mechanics (1985), Hertzian line contact",
        ),
        FailureMode(
            id="condensation in a breathing sealed volume",
            description=(
                "a sealed housing drawing moist air past its seal on every thermal cycle and "
                "keeping the water, until the optics fog, while the seal passes every leak test"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.FIELD,
            citation=(
                "Cengel and Boles, Thermodynamics: An Engineering Approach, 9th ed. (2019), "
                "ideal-gas equation of state"
            ),
            tested_by=("thermal-cycling",),
        ),
        FailureMode(
            id="window fracture under a pressure differential",
            description=(
                "a sealing window cracking from the tension on the face a pressure "
                "differential bows convex, in the direction nobody screened"
            ),
            applicability=Applicability(environments=("submerged", "thermal_cycling")),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Timoshenko and Woinowsky-Krieger, Theory of Plates and Shells, 2nd ed. "
                "(1959), simply supported circular plate"
            ),
        ),
        FailureMode(
            id="alignment drift from a harness crossing a mount",
            description=(
                "a cable or ribbon routed across an adjustable mount pulling the element off "
                "its alignment, while every load path the drawing shows is stiff enough"
            ),
            applicability=Applicability(interfaces=("clamped", "bonded", "sliding")),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Yoder and Vukobratovich, Opto-Mechanical Systems Design, 4th ed. (2015), "
                "line of sight"
            ),
        ),
        FailureMode(
            id="alignment loss over repeated cycles",
            description=(
                "a bonded or preloaded element walking off its alignment a little on every "
                "thermal or vibration cycle, while each single excursion screens clean"
            ),
            applicability=Applicability(environments=("thermal_cycling", "vibration")),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Yoder and Vukobratovich, Opto-Mechanical Systems Design, 4th ed. (2015), "
                "line of sight"
            ),
            tested_by=("thermal-cycling",),
        ),
        FailureMode(
            id="a cement or coating failing at an environment extreme",
            description=(
                "a cemented joint softening or a coating crazing at a temperature or humidity "
                "the housing survives, with every mechanical screen clean"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Yoder and Vukobratovich, Opto-Mechanical Systems Design, 4th ed. (2015), "
                "bonded and cemented optics"
            ),
        ),
        FailureMode(
            id="condensable outgassing on an optical surface",
            description=(
                "an adhesive, jacket or lubricant inside a sealed optical volume releasing "
                "volatiles that condense on the coldest optic as a haze"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "ASTM E595-15 total mass loss and collected volatile condensable materials "
                "from outgassing in a vacuum environment"
            ),
        ),
        FailureMode(
            id="particulate on an optical surface from the assembly room",
            description=(
                "an optic built to a surface cleanliness level in a room that cannot hold "
                "it, found as scatter at acceptance rather than at the drawing"
            ),
            applicability=Applicability(environments=("indoor_dry",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation="ISO 14644-1:2015 classification of air cleanliness by particle concentration",
        ),
        FailureMode(
            id="an adjustment that does not reach or does not hold",
            description=(
                "an alignment adjustment whose travel falls short of the correction, or that "
                "creeps off its setting in service because nothing holds it"
            ),
            applicability=Applicability(environments=("vibration", "thermal_cycling")),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Shigley, Mechanical Engineering Design, 10th ed. (2015), power screws and "
                "self-locking"
            ),
        ),
        FailureMode(
            id="thermal defocus of a lens housing",
            description=(
                "a lens and its housing expanding apart so the image leaves the depth of focus at "
                "a temperature extreme"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Jamieson, Thermal effects in optical systems, Optical Engineering 20(2) (1981)"
            ),
        ),
        FailureMode(
            id="boresight drift between optical paths",
            description=(
                "two channels meant to point together drifting apart, while each channel's own "
                "pointing screens clean"
            ),
            applicability=Applicability(
                environments=(
                    "vibration",
                    "thermal_cycling",
                )
            ),
            stage=DiscoveryStage.QUALIFICATION,
            citation="Yoder, Opto-Mechanical Systems Design, boresight between channels",
        ),
        FailureMode(
            id="an optic striking its housing under shock",
            description=(
                "a mounted optic swinging across its radial gap under shock and chipping on the "
                "housing or a neighbor"
            ),
            applicability=Applicability(environments=("vibration",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation="Harris and Piersol, Harris' Shock and Vibration Handbook, 5th ed. (2002)",
        ),
        FailureMode(
            id="self-heating inside an optical enclosure",
            description=(
                "a display, emitter or detector warming the volume the optics sit in past what the"
                " thermal screens assumed"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Incropera, Fundamentals of Heat and Mass Transfer, 7th ed. (2011), "
                "thermal resistance"
            ),
        ),
        FailureMode(
            id="condensation on the coldest internal surface",
            description=(
                "the gas sealed inside a housing reaching its dew point on the coldest optic at a "
                "cold soak"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Alduchov and Eskridge, Improved Magnus form approximation of saturation vapor "
                "pressure, Journal of Applied Meteorology 35 (1996)"
            ),
        ),
        FailureMode(
            id="lens preload lost or overstressed at a temperature extreme",
            description=(
                "a retainer's preload lost as the cell grows away from the lens, or crushing it as"
                " the cell shrinks"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation="Yoder, Opto-Mechanical Systems Design, preload versus temperature",
        ),
        FailureMode(
            id="a static seal leaking at a temperature extreme",
            description=(
                "an O-ring squeezed in band at assembly falling out of its squeeze, fill or "
                "stretch band at an extreme"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation="Parker O-Ring Handbook, static-seal squeeze, fill and stretch",
        ),
        FailureMode(
            id="image quality lost to stacked wavefront errors",
            description=(
                "surface figure, mount distortion and alignment errors each small, together past "
                "the Strehl the system needs"
            ),
            applicability=Applicability(
                environments=(
                    "thermal_cycling",
                    "vibration",
                )
            ),
            stage=DiscoveryStage.QUALIFICATION,
            citation="Maréchal criterion, S = exp(−(2πσ/λ)²)",
        ),
        FailureMode(
            id="a fastener no tool reaches in the state it is driven",
            description=(
                "a bolt whose head clears but whose driver does not, once the parts installed "
                "before it are in place, found on the assembly line rather than the drawing"
            ),
            applicability=Applicability(interfaces=("bolted_face",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation=(
                "Boothroyd, Dewhurst and Knight, Product Design for Manufacture and Assembly, "
                "3rd ed. (2011), accessibility of fastening operations"
            ),
        ),
        FailureMode(
            id="thermal ratcheting of a clearance",
            description=(
                "a running clearance closing over repeated thermal cycles as the parts grow "
                "at different rates, seizing a guide that was clear when cold"
            ),
            applicability=Applicability(environments=("thermal_cycling",)),
            stage=DiscoveryStage.QUALIFICATION,
            citation="ASME BPVC VIII-2 §5.5.6, the ratcheting assessment's premise",
            tested_by=("thermal-cycling",),
        ),
    )
)
