"""The Design Spec IR: Anvilate's typed representation of engineering intent.

Every downstream subsystem consumes a :class:`DesignSpec`, never raw prose. The
schema expresses part identity, material, manufacturing method and its DFM
parameters, interfaces, load cases, constraints, and acceptance criteria — with
every physical value a dimensionally-checked :class:`Quantity` and every value's
origin recorded via :class:`Provenanced`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from math import isfinite
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .._models import FrozenMap, Named, Provenance, RevalidatedModel, rebuilt_quantities
from ..loads import (
    CombinationEvidence,
    CombinationSet,
    LoadNature,
    asce7_asd_basic,
    asce7_asd_seismic,
    asce7_lrfd_basic,
    asce7_lrfd_seismic,
    combination_evidence,
)
from ..tolerance import (
    AchievabilityCheck,
    ResolvedTolerance,
    StackContributor,
    StackResult,
    StackUp,
    Tolerance,
    ToleranceClass,
    general_tolerance,
    general_tolerance_source,
    processes_that_can_hold,
    resolve_class,
    tolerance_is_achievable,
)
from ..units import Quantity, UnitSystem, require_dimension
from .provenance import Provenanced

__all__ = [
    "DesignSpec",
    "Envelope",
    "MaterialRef",
    "ManufacturingProcess",
    "Manufacturing",
    "StandardComponentInterface",
    "ImportedInterface",
    "Interface",
    "InterfaceContract",
    "HolePattern",
    "ToleranceDimension",
    "ChainLink",
    "DimensionChain",
    "ChainAnalysis",
    "GeometricCharacteristic",
    "GeometricTolerance",
    "LoadCase",
    "LoadKind",
    "Constraints",
    "AcceptanceCriteria",
    "ValidationTier",
]

# Dimension-pinned quantity types. Assigning a quantity of the wrong dimension
# to one of these fields fails validation, naming the field and the mismatch.
Mass = Annotated[Quantity, AfterValidator(require_dimension("[mass]", name="mass"))]
Length = Annotated[Quantity, AfterValidator(require_dimension("[length]", name="length"))]
Force = Annotated[Quantity, AfterValidator(require_dimension("[force]", name="force"))]


def _first_non_finite(where: str, value: object) -> tuple[str | None, float | None]:
    """The first infinity or NaN under ``value``, and the path to it — or ``(None, None)``.

    A stated bound is wrapped: `max_mass` is a `Provenanced[Quantity]`, so the number is two
    layers in. Unwrapping by attribute rather than by type keeps this from importing the
    provenance module, and an enum's `.value` is a string, which the float check filters out.

    Mappings and sequences are walked because a document's free-form parts are containers —
    `element_params` above all — and the path is built as it goes, so the message names
    `element_params.width.magnitude` rather than `element_params`. Sub-models are not walked:
    each is a `_Base` and has already run this rule on itself.
    """
    value = getattr(value, "value", value)
    if isinstance(value, Quantity):
        return (where, value.magnitude) if not isfinite(value.magnitude) else (None, None)
    if isinstance(value, BaseModel):
        return None, None
    # Before the float branch: `bool` is a subclass of `int`, not of `float`, so it never
    # reaches it — but a mapping's keys and values are `object` here and being explicit is
    # cheaper than working that out again.
    if isinstance(value, bool):
        return None, None
    if isinstance(value, float):
        return (where, value) if not isfinite(value) else (None, None)
    if isinstance(value, Mapping):
        for key, item in value.items():
            found = _first_non_finite(f"{where}.{key}", item)
            if found[0] is not None:
                return found
        return None, None
    if isinstance(value, (list, tuple, set, frozenset)):
        for index, item in enumerate(value):
            found = _first_non_finite(f"{where}[{index}]", item)
            if found[0] is not None:
                return found
    return None, None


class _Base(RevalidatedModel):
    model_config = ConfigDict(extra="forbid")  # unknown keys are rejected

    @model_validator(mode="after")
    def _every_number_is_finite(self) -> _Base:
        """No field of a document is an infinity or a NaN.

        A `Quantity` may hold one — intermediate arithmetic produces them and each consumer
        guards its own — but a *document* never states one. Nothing checked it, and the two
        halves of the consequence differ: `max_mass: .inf kg` is a requirement that reads as
        stated and means nothing, while a dimension whose nominal is NaN screened to **PASS**
        on its tolerance band, because the achievability check compares the band against the
        process floor and never looks at the size it belongs to.

        One rule here rather than a `isfinite` in every validator below: they were written
        one field at a time, and `min_safety_factor > 0` is True for infinity.

        **Into the containers, too, and that is where the hole was.** The claim above is
        about a document, and it was enforced over top-level fields only — so
        `element_params`, a free-form mapping and the place a *screened dimension* actually
        lives, was exempt. A lifting lug 1e400 mm wide compiled, and the twenty-four element
        models set their own `model_config` with no shared base to hang this on. It reached
        the shell as an accepted spec and MCP as an internal error, raised late by the
        canonical-JSON writer with no field named.
        """
        for name in type(self).model_fields:
            where, magnitude = _first_non_finite(name, getattr(self, name, None))
            if where is not None:
                raise ValueError(
                    f"{where} is {magnitude}, which is not a number a document can state; "
                    f"a requirement that is infinite or undefined is not a requirement"
                )
        return self


# --- Material and manufacturing ---


class MaterialRef(_Base):
    """A database identifier for a material (e.g. ``AA-6061-T6``)."""

    ref: Provenance


class ManufacturingProcess(StrEnum):
    CNC_MILLING = "cnc_milling"
    CNC_TURNING = "cnc_turning"
    GRINDING = "grinding"
    WIRE_EDM = "wire_edm"
    REAMING = "reaming"
    FDM = "fdm"
    SLS = "sls"
    SHEET_METAL = "sheet_metal"
    INJECTION_MOLDING = "injection_molding"
    DIE_CASTING = "die_casting"


class Manufacturing(_Base):
    """The manufacturing process and the DFM parameters it is checked against."""

    # The docstring is the published schema's description for this type, so it is left
    # exactly as it was: changing it would change `design-spec.schema.json` and owe the
    # contract a version bump for a sentence. What it means, precisely: `process` selects the
    # achievable-tolerance floor a T2 screen compares against; `tolerance_class` is a
    # reference resolved on the card, near misses named, like any other identifier; and
    # `min_wall` is a bound on built geometry, so a screen reports it as unscreened rather
    # than checking it. Neither of the last two was read on any screening path until the
    # screen learned to answer them.

    process: ManufacturingProcess
    min_wall: Length | None = None
    tolerance_class: str | None = None  # e.g. ISO 2768 "medium"


# --- Interfaces ---


class HolePattern(_Base):
    """A bolt/hole pattern published as part of an interface contract."""

    diameter: Length
    hole_count: int = Field(ge=1)
    hole_size: Length

    @model_validator(mode="after")
    def _positive_dimensions(self) -> HolePattern:
        for field in ("diameter", "hole_size"):
            value: Quantity = getattr(self, field)
            if value.to("mm").magnitude <= 0:
                raise ValueError(f"hole-pattern {field} must be positive; got {value}")
        return self


class InterfaceContract(_Base):
    """A published, importable interface: the geometry a mating part designs against."""

    name: Named
    mating_plane: str  # semantic tag of the mating face
    pattern: HolePattern


class StandardComponentInterface(_Base):
    """An interface to a standard component, referenced by database ID."""

    type: Literal["standard_component"] = "standard_component"
    ref: Provenance  # e.g. "NEMA23", resolved from the standards DB at build time
    tag: str  # semantic tag for the resulting feature, e.g. "motor_pilot_bore"


class ImportedInterface(_Base):
    """An interface imported from another spec's published contract."""

    type: Literal["imported"] = "imported"
    source_spec: str  # identifier of the spec that publishes the contract
    contract: str  # name of the imported InterfaceContract
    tag: str


Interface = Annotated[
    StandardComponentInterface | ImportedInterface,
    Field(discriminator="type"),
]


# --- Toleranced dimensions ---


class ToleranceDimension(_Base):
    """An explicitly-toleranced dimension declared on the spec.

    ``tolerance`` is the typed :data:`~anvilate.tolerance.Tolerance` union —
    symmetric ±, asymmetric limits, or an ISO 286 fit — and overrides the general
    class for the feature at ``tag``. :meth:`resolve` yields the common
    :class:`~anvilate.tolerance.ResolvedTolerance` band the drawing, DFM, and
    stack-up layers read.
    """

    tag: str  # semantic tag of the feature the dimension measures
    nominal: Length
    tolerance: Tolerance

    def resolve(self) -> ResolvedTolerance:
        """The resolved band for this dimension (its tolerance at its nominal)."""
        return self.tolerance.resolve(self.nominal)


class ChainLink(_Base):
    """One dimension in a stack-up chain, referenced by its tag.

    ``direction`` is ``+1`` when the dimension growing widens the resulting gap
    and ``-1`` when it narrows it.
    """

    dimension: str  # tag of a ToleranceDimension declared on the spec
    direction: Literal[1, -1] = 1


class DimensionChain(_Base):
    """A user-declared 1D stack-up chain and the clearance it must hold.

    The chain names dimensions (by tag) and sums their directed sizes into a gap
    that must land within ``required_min``..``required_max``. :meth:`build`
    resolves it against the spec's dimensions into a
    :class:`~anvilate.tolerance.StackUp` for worst-case / RSS analysis.
    """

    name: Named
    links: list[ChainLink] = Field(min_length=1)
    required_min: Length
    required_max: Length

    @model_validator(mode="after")
    def _ordered_requirement(self) -> DimensionChain:
        lo = self.required_min.to("mm").magnitude
        hi = self.required_max.to("mm").magnitude
        if hi < lo:
            raise ValueError(
                f"chain {self.name!r} requires a clearance band with required_max "
                f"({self.required_max}) below required_min ({self.required_min})"
            )
        return self

    def build(self, dimensions: list[ToleranceDimension]) -> StackUp:
        """Resolve this chain against ``dimensions`` into a stack-up.

        Raises :class:`KeyError` if a link references a tag no declared dimension
        carries.
        """
        by_tag = {d.tag: d for d in dimensions}
        contributors = []
        for link in self.links:
            dim = by_tag.get(link.dimension)
            if dim is None:
                raise KeyError(
                    f"stack-up chain {self.name!r} references dimension "
                    f"{link.dimension!r}, which no declared dimension carries"
                )
            contributors.append(
                StackContributor(
                    name=link.dimension,
                    tolerance=dim.resolve(),
                    direction=link.direction,
                )
            )
        return StackUp(contributors=tuple(contributors))

    def analyze(self, dimensions: list[ToleranceDimension]) -> ChainAnalysis:
        """Resolve and evaluate this chain against its own required clearance.

        Builds the stack-up (see :meth:`build`), runs both the worst-case and RSS
        analyses, and judges each against the chain's declared
        ``required_min``..``required_max`` band — returning one
        :class:`ChainAnalysis`. Raises :class:`KeyError` for an unknown tag.
        """
        stack = self.build(dimensions)
        return ChainAnalysis(
            name=self.name,
            required_min=self.required_min,
            required_max=self.required_max,
            worst_case=stack.worst_case(),
            rss=stack.rss(),
        )

    def predict_yield(
        self,
        dimensions: list[ToleranceDimension],
        samples: int = 10000,
        *,
        seed: int,
        sigma_level: float = 3.0,
    ) -> float:
        """The predicted fraction of assemblies meeting this chain's clearance.

        Runs a Monte Carlo stack-up (see
        :meth:`~anvilate.tolerance.StackUp.monte_carlo`) and scores the sampled
        gaps against the chain's own ``required_min``..``required_max`` band —
        the realistic pass rate, which the worst-case and RSS ranges cannot give.
        ``seed`` is required so the estimate is reproducible. Raises
        :class:`KeyError` for an unknown dimension tag.
        """
        mc = self.build(dimensions).monte_carlo(samples, seed=seed, sigma_level=sigma_level)
        return mc.yield_fraction(self.required_min, self.required_max)


class ChainAnalysis(_Base):
    """A declared chain's resolved stack-up judged against its requirement.

    Carries the worst-case and RSS gap ranges and the chain's required clearance
    band. The worst-case range is the authoritative gate — a chain ``passes`` only
    when its worst case fits — while the RSS range reports the realistic spread.
    Each result already ranks its per-contributor sensitivities.
    """

    name: Named
    required_min: Length
    required_max: Length
    worst_case: StackResult
    rss: StackResult

    @property
    def worst_case_passes(self) -> bool:
        """Whether the worst-case gap range fits the required band."""
        return self.worst_case.satisfies(self.required_min, self.required_max)

    @property
    def rss_passes(self) -> bool:
        """Whether the RSS gap range fits the required band."""
        return self.rss.satisfies(self.required_min, self.required_max)

    @property
    def passes(self) -> bool:
        """The chain's pass/fail: the worst case must fit the requirement."""
        return self.worst_case_passes

    def __str__(self) -> str:
        lo = self.required_min.to("mm").magnitude
        hi = self.required_max.to("mm").magnitude
        verdict = "PASS" if self.passes else "FAIL"
        return f"{self.name}: {verdict} — need {lo:.3f}..{hi:.3f} mm; {self.worst_case}"


# --- Geometric tolerances (GD&T) ---


class GeometricCharacteristic(StrEnum):
    """The geometric characteristics this slice supports (ISO 1101 / ASME Y14.5)."""

    # Form controls — reference no datum.
    FLATNESS = "flatness"
    STRAIGHTNESS = "straightness"
    CIRCULARITY = "circularity"  # roundness
    CYLINDRICITY = "cylindricity"
    # Orientation controls — need a datum.
    PERPENDICULARITY = "perpendicularity"
    PARALLELISM = "parallelism"
    ANGULARITY = "angularity"
    # Location control — needs a datum.
    POSITION = "position"
    # Runout controls — need a datum axis.
    CIRCULAR_RUNOUT = "circular_runout"
    TOTAL_RUNOUT = "total_runout"


# Form controls reference no datum; orientation/location controls require one.
_FORM_CHARACTERISTICS = frozenset(
    {
        GeometricCharacteristic.FLATNESS,
        GeometricCharacteristic.STRAIGHTNESS,
        GeometricCharacteristic.CIRCULARITY,
        GeometricCharacteristic.CYLINDRICITY,
    }
)
_DATUM_REQUIRED = frozenset(
    {
        GeometricCharacteristic.PERPENDICULARITY,
        GeometricCharacteristic.PARALLELISM,
        GeometricCharacteristic.ANGULARITY,
        GeometricCharacteristic.POSITION,
        GeometricCharacteristic.CIRCULAR_RUNOUT,
        GeometricCharacteristic.TOTAL_RUNOUT,
    }
)


class GeometricTolerance(_Base):
    """A geometric tolerance (GD&T feature control frame) on a tagged feature.

    ``tolerance`` is the tolerance-zone width, or its diameter when ``diametral``
    (the ⌀ modifier, used for a hole axis under a position control). ``feature``
    is the semantic tag the control applies to; ``datums`` are the ordered datum
    references (primary, secondary, tertiary). Whether a ``feature`` or ``datum``
    tag names a real geometry feature is checked by the tag-graph layer, not here.
    """

    characteristic: GeometricCharacteristic
    tolerance: Length  # the tolerance-zone width (or diameter, if diametral)
    feature: str  # semantic tag of the controlled feature
    datums: list[str] = Field(default_factory=list)  # ordered datum references
    diametral: bool = False  # a cylindrical (⌀) zone rather than a width

    @model_validator(mode="after")
    def _well_formed(self) -> GeometricTolerance:
        if self.tolerance.to("mm").magnitude <= 0:
            raise ValueError(
                f"{self.characteristic.value} tolerance must be positive; got {self.tolerance}"
            )
        if self.characteristic in _FORM_CHARACTERISTICS and self.datums:
            raise ValueError(
                f"{self.characteristic.value} is a form control and references no datum; "
                f"got {self.datums}"
            )
        if self.characteristic in _DATUM_REQUIRED and not self.datums:
            raise ValueError(f"{self.characteristic.value} requires at least one datum reference")
        if len(set(self.datums)) != len(self.datums):
            raise ValueError(
                f"a datum reference repeats in the frame {self.datums}; each datum is "
                "referenced at most once (primary, secondary, tertiary)"
            )
        return self

    def __str__(self) -> str:
        zone = f"⌀{self.tolerance}" if self.diametral else f"{self.tolerance}"
        frame = f"{self.characteristic.value} {zone}"
        if self.datums:
            frame += " to " + "|".join(self.datums)
        return f"{frame} on {self.feature}"


# --- Load cases ---


class LoadKind(StrEnum):
    STATIC = "static"
    QUASI_STATIC = "quasi_static"
    REMOTE_MASS = "remote_mass"


class LoadCase(_Base):
    """A single load condition the part must survive.

    Each ``kind`` carries its own magnitude: a ``static`` or ``quasi_static`` case
    a ``force`` (quasi-static also a ``quasi_static_factor`` that scales it), a
    ``remote_mass`` case an offset ``remote_mass``. A case missing its magnitude is
    rejected at construction — a downstream analysis can never be handed a load
    with nothing to apply.

    ``nature`` optionally classifies the case by its ASCE 7 load nature (dead, live,
    wind, seismic, …) so a declared combination set can factor it. It is orthogonal
    to ``kind`` (which is how the load is applied) and defaults to ``None`` — a spec
    that does not use load combinations leaves it unset.
    """

    name: Named
    kind: LoadKind
    applied_to: str  # semantic tag the load acts on
    force: Force | None = None
    remote_mass: Mass | None = None
    quasi_static_factor: float | None = Field(default=None, gt=0)
    nature: LoadNature | None = None

    @model_validator(mode="after")
    def _kind_carries_its_magnitude(self) -> LoadCase:
        if self.kind in (LoadKind.STATIC, LoadKind.QUASI_STATIC) and self.force is None:
            raise ValueError(
                f"a {self.kind.value} load case needs a force; none given on {self.name!r}"
            )
        if self.kind is LoadKind.QUASI_STATIC and self.quasi_static_factor is None:
            raise ValueError(
                f"a quasi_static load case needs a quasi_static_factor; none given on {self.name!r}"
            )
        if self.kind is LoadKind.REMOTE_MASS and self.remote_mass is None:
            raise ValueError(
                f"a remote_mass load case needs a remote_mass; none given on {self.name!r}"
            )
        return self


# --- Constraints and acceptance ---


class Envelope(_Base):
    """A bounding-box constraint."""

    x: Length
    y: Length
    z: Length

    @model_validator(mode="after")
    def _positive_extent(self) -> Envelope:
        for axis in ("x", "y", "z"):
            value: Quantity = getattr(self, axis)
            if value.to("mm").magnitude <= 0:
                raise ValueError(f"envelope {axis} extent must be positive; got {value}")
        return self


class Constraints(_Base):
    """Bounds the design must satisfy."""

    max_mass: Provenanced[Mass] | None = None
    envelope: Envelope | None = None
    min_safety_factor: Provenanced[float] | None = None
    # The band's other end: a check running above it is OVER_MARGIN — passing, and flagged as
    # over-engineered. The status has been first-class in the scorecard, the exit codes and
    # the QIF export since they were written, and exactly one pack screen could produce it,
    # from a `target_safety_factor` argument no document could set. This is how a document
    # asks for it.
    max_safety_factor: Provenanced[float] | None = None
    max_cost: Provenanced[float] | None = None  # currency handled by cost-estimation

    @model_validator(mode="after")
    def _positive_bounds(self) -> Constraints:
        if self.max_mass is not None and self.max_mass.value.to("kg").magnitude <= 0:
            raise ValueError(f"max_mass must be positive; got {self.max_mass.value}")
        if self.min_safety_factor is not None and self.min_safety_factor.value <= 0:
            raise ValueError(
                f"min_safety_factor must be positive; got {self.min_safety_factor.value}"
            )
        if self.max_safety_factor is not None and self.max_safety_factor.value <= 0:
            raise ValueError(
                f"max_safety_factor must be positive; got {self.max_safety_factor.value}"
            )
        if (
            self.min_safety_factor is not None
            and self.max_safety_factor is not None
            and self.max_safety_factor.value <= self.min_safety_factor.value
        ):
            raise ValueError(
                f"max_safety_factor {self.max_safety_factor.value:g} is not above "
                f"min_safety_factor {self.min_safety_factor.value:g}; a band whose top is at "
                "or below its floor asks for a check to pass and be over-engineered at once"
            )
        if self.max_cost is not None and self.max_cost.value <= 0:
            raise ValueError(f"max_cost must be positive; got {self.max_cost.value}")
        return self


class ValidationTier(StrEnum):
    T0_GEOMETRY = "T0_geometry"
    T1_ANALYTICAL = "T1_analytical"
    T2_DFM = "T2_dfm"
    T3_FEA = "T3_fea"


class AcceptanceCriteria(_Base):
    """Which checks must run and the thresholds they are judged against."""

    tiers: list[ValidationTier] = Field(min_length=1)
    fea_convergence_tol: float | None = Field(default=None, gt=0)
    max_displacement: Length | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> AcceptanceCriteria:
        if len(set(self.tiers)) != len(self.tiers):
            raise ValueError(
                f"validation tiers must be unique; got {[t.value for t in self.tiers]}"
            )
        if self.max_displacement is not None and self.max_displacement.to("mm").magnitude <= 0:
            raise ValueError(f"max_displacement must be positive; got {self.max_displacement}")
        return self


# --- The spec ---

# 1.1.0 added the optional LoadCase.nature classification, the DesignSpec
# combination_basis, and the seismic parameters. 1.2.0 added element_type and
# element_params. 1.3.0 added constraints.max_safety_factor, the top of the target band an
# OVER_MARGIN verdict is measured against. All additive, which is what lets an older 1.x
# spec load unchanged — and it comes back saying which version it is, not this one. The
# version a document carries is a record of what it is, never an assertion that it is
# current; see `migrate_to_current`.
SCHEMA_VERSION = "1.3.0"


class DesignSpec(_Base):
    """A complete, typed statement of engineering intent for one part."""

    anvilate_spec: str = SCHEMA_VERSION
    name: Named
    description: str
    units: Provenanced[UnitSystem]
    material: MaterialRef
    manufacturing: Manufacturing
    interfaces: list[Interface] = Field(default_factory=list)
    dimensions: list[ToleranceDimension] = Field(default_factory=list)
    chains: list[DimensionChain] = Field(default_factory=list)
    geometric_tolerances: list[GeometricTolerance] = Field(default_factory=list)
    load_cases: list[LoadCase] = Field(default_factory=list)
    # The ASCE 7-22 load-combination basis to factor the classified cases under, if
    # any. ``None`` leaves the spec evaluated per load case, as before. The seismic
    # bases additionally read ``seismic_design_acceleration`` and
    # ``seismic_redundancy_factor``.
    combination_basis: (
        Literal["asce7_lrfd", "asce7_asd", "asce7_lrfd_seismic", "asce7_asd_seismic"] | None
    ) = None
    # Seismic parameters, needed only when a seismic basis is declared: the design
    # spectral acceleration S_DS and the redundancy factor ρ.
    seismic_design_acceleration: float | None = Field(default=None, gt=0)
    seismic_redundancy_factor: float = Field(default=1.0, gt=0)
    # The discipline-pack element this part *is*, as a tag plus the element's own fields.
    # Until this landed a `DesignSpec` could not say what kind of structural element it
    # described, so no pack screen could be selected from a document and the T1 analytical
    # tier reported NOT_EVALUATED on every spec -- 236 closed-form modules unreachable from
    # the front door.
    #
    # A tag and a parameter map rather than a typed union, deliberately: `spec-ir` and the
    # packs stay independently versionable, and a new pack element ships without a bump to
    # this published schema or to the MCP tool contracts that reference it at its version.
    # What that trades away is total validation at parse time, and the trade is paid for
    # rather than waved through -- each element's own schema is published beside this one
    # and named by the same tag, so the contract stays complete without this file learning
    # what a lifting lug is. `anvilate.screening.element_registry` resolves the tag.
    element_type: str | None = None
    element_params: FrozenMap[str, Any] = Field(default_factory=dict)
    constraints: Constraints = Field(default_factory=Constraints)
    acceptance: AcceptanceCriteria

    @field_validator("element_params", mode="before")
    @classmethod
    def _a_quantity_survives_a_round_trip(cls, value: Any) -> Any:
        """An element parameter written as a quantity comes back as one.

        ``element_params`` is typed ``Any`` because a pack element's fields are quantities,
        numbers, strings and enum tags, and ``Any`` is not told how to rebuild any of them.
        So a spec stating ``pin_diameter`` as ``25 mm`` serialised to
        ``{"magnitude": 25.0, "unit": "mm"}`` and read back as that dictionary -- and the
        pack model behind the tag takes a `Quantity`. The same repair `CompilationTask`
        needed, for the same reason, and only the two-key shape this library's own
        serialiser emits: a mapping that does not parse stays a mapping.
        """
        return rebuilt_quantities(value)

    @model_validator(mode="after")
    def _an_element_is_a_tag_and_its_fields(self) -> DesignSpec:
        """Neither half of an element declaration means anything without the other."""
        if self.element_type is None:
            if self.element_params:
                raise ValueError(
                    "element_params were given with no element_type, so nothing says which "
                    "pack element they belong to; declare the type or drop the parameters"
                )
            return self
        if not self.element_type.strip():
            raise ValueError("element_type is a pack element's tag; an empty string is not one")
        if not self.element_params:
            raise ValueError(
                f"element_type {self.element_type!r} is declared with no element_params, and "
                "no pack element screens on its name alone; state the element's fields"
            )
        return self

    # Interface contracts this part publishes for others to import against.
    exports: list[InterfaceContract] = Field(default_factory=list)

    def combination_set(self) -> CombinationSet | None:
        """The declared ASCE 7-22 combination set, or ``None`` if none is declared.

        Resolves ``combination_basis`` to its generator — the §2.3.1 strength (LRFD) or
        §2.4.1 allowable-stress (ASD) basic set, or the §2.3.6 / §2.4.5 seismic set — so
        the spec-driven flow is
        ``spec.combination_set().governing(spec.combination_loads())``. A seismic basis
        additionally reads ``seismic_design_acceleration`` (S_DS, required) and
        ``seismic_redundancy_factor`` (ρ).
        """
        if self.combination_basis is None:
            return None
        if self.combination_basis == "asce7_lrfd":
            return asce7_lrfd_basic()
        if self.combination_basis == "asce7_asd":
            return asce7_asd_basic()
        if self.seismic_design_acceleration is None:
            raise ValueError(
                f"combination_basis {self.combination_basis!r} needs "
                "seismic_design_acceleration (S_DS) to be declared"
            )
        if self.combination_basis == "asce7_lrfd_seismic":
            return asce7_lrfd_seismic(
                s_ds=self.seismic_design_acceleration,
                redundancy=self.seismic_redundancy_factor,
            )
        return asce7_asd_seismic(
            s_ds=self.seismic_design_acceleration,
            redundancy=self.seismic_redundancy_factor,
        )

    def combination_loads(self) -> dict[LoadNature, float]:
        """Aggregate the classified load cases into a per-nature demand mapping (N).

        Sums the *effective* force of every load case that declares a ``nature`` into
        a ``{LoadNature: newtons}`` mapping — the input the ASCE 7 combination
        generators in :mod:`anvilate.loads` consume. A quasi-static case contributes
        ``force * quasi_static_factor``: the factor is the dynamic amplification the
        schema obliges that case to declare, so dropping it here would discard a
        declared amplification and under-state the demand by exactly that factor.
        A case with no ``nature`` (or no force, such as a remote-mass case) is
        skipped: only classified force cases enter a load combination. Force signs
        carry through, so a case tagged as a wind uplift contributes a negative
        magnitude and drives the counteracting combinations.
        """
        loads: dict[LoadNature, float] = {}
        for case in self.load_cases:
            if case.nature is None or case.force is None:
                continue
            effective = case.force.to("N").magnitude * (case.quasi_static_factor or 1.0)
            loads[case.nature] = loads.get(case.nature, 0.0) + effective
        return loads

    def combination_evidence(self, *, minimize: bool = False) -> CombinationEvidence | None:
        """The governing combination for this spec, or ``None`` if no basis is declared.

        The short path, and the safe one: it passes :meth:`unclassified_force_cases` for
        you, so the evidence a bundle carries cannot forget the cases the factoring could
        not see. Handing :func:`~anvilate.loads.combination_evidence` a mapping directly
        works too and leaves that to the caller — which is exactly the step this exists so
        nobody has to remember.
        """
        combinations = self.combination_set()
        if combinations is None:
            return None
        return combination_evidence(
            combinations,
            self.combination_loads(),
            unclassified=self.unclassified_force_cases(),
            minimize=minimize,
        )

    def unclassified_force_cases(self) -> tuple[str, ...]:
        """Load cases that carry a force and no ``nature``, in declaration order.

        These are the cases :meth:`combination_loads` skips, and skipping them is only
        safe if somebody looks at the list. A combination generator treats a nature nobody
        supplied as zero, so a spec that declares a 200 kN case and forgets to classify it
        produces a demand that never saw the 200 kN — and every capacity screened against
        that demand passes. Hand this to
        :func:`~anvilate.loads.combination_scorecard` or
        :func:`~anvilate.loads.combination_evidence` and the result reports
        ``NOT_EVALUATED`` instead.

        A case with no force (a remote-mass case, say) is not listed: it has nothing to
        contribute to a factored sum, so leaving it unclassified costs nothing.
        """
        return tuple(
            case.name for case in self.load_cases if case.force is not None and case.nature is None
        )

    def analyze_chains(self) -> list[ChainAnalysis]:
        """Analyze every declared stack-up chain against this spec's dimensions.

        Returns one :class:`ChainAnalysis` per chain, in declaration order (empty
        when none are declared); each carries its own pass/fail so a scorecard can
        surface the failures. Raises :class:`KeyError` if a chain references an
        undeclared dimension tag — run
        :func:`~anvilate.spec.validate_dimension_graph` first to surface every
        such problem at once.
        """
        return [chain.analyze(self.dimensions) for chain in self.chains]

    def check_tolerances_manufacturable(self) -> dict[str, AchievabilityCheck]:
        """Screen every explicitly-declared tolerance against the declared process.

        Returns one :class:`~anvilate.tolerance.AchievabilityCheck` per declared
        :class:`ToleranceDimension`, keyed by its tag — each says whether the
        process can hold that tolerance band (a T2 DFM screen). General-class
        dimensions are not screened here: the general class is chosen to be
        process-appropriate, so only explicit tolerances can under-run the floor.
        Filter for ``not check.achievable`` to get the scorecard failures. Raises
        :class:`~anvilate.tolerance.ToleranceRangeError` if the process has no
        capability record.
        """
        process = self.manufacturing.process.value
        return {
            dim.tag: tolerance_is_achievable(process, dim.resolve().width)
            for dim in self.dimensions
        }

    def suggest_processes_for_tight_tolerances(self) -> dict[str, list[str]]:
        """For each declared tolerance the chosen process cannot hold, the other
        processes that could — the "change the process" half of the T2 DFM scenario
        (:meth:`check_tolerances_manufacturable` is the flag half).

        Keyed by dimension tag; only tolerances that fail on the declared process
        appear. Each value is the alternative processes whose finest-achievable
        floor can hold the band, coarsest-capable (most economical) first, with the
        already-declared process removed. An empty list means no bundled process
        can hold the band, so the tolerance must be relaxed instead.
        """
        process = self.manufacturing.process.value
        suggestions: dict[str, list[str]] = {}
        for dim in self.dimensions:
            band = dim.resolve().width
            if not tolerance_is_achievable(process, band).achievable:
                suggestions[dim.tag] = [p for p in processes_that_can_hold(band) if p != process]
        return suggestions

    def general_tolerance_class(self) -> ToleranceClass:
        """The ISO 2768 general class governing this spec's untoleranced dimensions.

        Parsed from ``manufacturing.tolerance_class`` (a letter ``m`` or word
        ``medium``), defaulting to the ISO 2768 medium class when the spec says
        nothing. Raises :class:`ValueError` if the declared string is unrecognized.
        """
        return resolve_class(self.manufacturing.tolerance_class)

    def effective_tolerance(self, tag: str, nominal: Quantity) -> ResolvedTolerance:
        """The tolerance band that actually governs the feature at ``tag``.

        An explicitly-declared :class:`ToleranceDimension` for ``tag`` overrides
        the general class and resolves at its own declared nominal; otherwise this
        spec's ISO 2768 general class resolves ``nominal`` into a symmetric band,
        carrying the ISO 2768 citation. Either way the return is one
        :class:`~anvilate.tolerance.ResolvedTolerance`, so the drawing and DFM
        layers read a feature's permitted band the same way. ``nominal`` must be a
        length; it is consulted only for the general fallback.
        """
        for dim in self.dimensions:
            if dim.tag == tag:
                return dim.resolve()
        gt = general_tolerance(nominal, self.general_tolerance_class())
        deviation_mm = gt.deviation.to("mm").magnitude
        return ResolvedTolerance(
            nominal=nominal,
            upper=Quantity(magnitude=deviation_mm, unit="mm"),
            lower=Quantity(magnitude=-deviation_mm, unit="mm"),
            label=f"ISO 2768-{gt.tolerance_class.letter}",
            source=general_tolerance_source(),
        )
