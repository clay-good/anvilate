"""The Design Spec IR: Anvilate's typed representation of engineering intent.

Every downstream subsystem consumes a :class:`DesignSpec`, never raw prose. The
schema expresses part identity, material, manufacturing method and its DFM
parameters, interfaces, load cases, constraints, and acceptance criteria — with
every physical value a dimensionally-checked :class:`Quantity` and every value's
origin recorded via :class:`Provenanced`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from ..tolerance import (
    ResolvedTolerance,
    StackContributor,
    StackResult,
    StackUp,
    Tolerance,
)
from ..units import Quantity, UnitSystem, require_dimension
from .provenance import Provenanced

__all__ = [
    "DesignSpec",
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


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown keys are rejected


# --- Material and manufacturing ---


class MaterialRef(_Base):
    """A database identifier for a material (e.g. ``AA-6061-T6``)."""

    ref: str


class ManufacturingProcess(StrEnum):
    CNC_MILLING = "cnc_milling"
    CNC_TURNING = "cnc_turning"
    FDM = "fdm"
    SLS = "sls"
    SHEET_METAL = "sheet_metal"


class Manufacturing(_Base):
    """The manufacturing process and the DFM parameters it is checked against."""

    process: ManufacturingProcess
    min_wall: Length | None = None
    tolerance_class: str | None = None  # e.g. ISO 2768 "medium"


# --- Interfaces ---


class HolePattern(_Base):
    """A bolt/hole pattern published as part of an interface contract."""

    diameter: Length
    hole_count: int = Field(ge=1)
    hole_size: Length


class InterfaceContract(_Base):
    """A published, importable interface: the geometry a mating part designs against."""

    name: str
    mating_plane: str  # semantic tag of the mating face
    pattern: HolePattern


class StandardComponentInterface(_Base):
    """An interface to a standard component, referenced by database ID."""

    type: Literal["standard_component"] = "standard_component"
    ref: str  # e.g. "NEMA23", resolved from the standards DB at build time
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

    name: str
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

    name: str
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

    FLATNESS = "flatness"  # a form control — references no datum
    PERPENDICULARITY = "perpendicularity"  # an orientation control — needs a datum
    POSITION = "position"  # a location control — needs a datum


# Form controls reference no datum; orientation/location controls require one.
_FORM_CHARACTERISTICS = frozenset({GeometricCharacteristic.FLATNESS})
_DATUM_REQUIRED = frozenset(
    {GeometricCharacteristic.PERPENDICULARITY, GeometricCharacteristic.POSITION}
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
    """A single load condition the part must survive."""

    name: str
    kind: LoadKind
    applied_to: str  # semantic tag the load acts on
    force: Force | None = None
    remote_mass: Mass | None = None
    quasi_static_factor: float | None = Field(default=None, gt=0)


# --- Constraints and acceptance ---


class Envelope(_Base):
    """A bounding-box constraint."""

    x: Length
    y: Length
    z: Length


class Constraints(_Base):
    """Bounds the design must satisfy."""

    max_mass: Provenanced[Mass] | None = None
    envelope: Envelope | None = None
    min_safety_factor: Provenanced[float] | None = None
    max_cost: Provenanced[float] | None = None  # currency handled by cost-estimation


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


# --- The spec ---

SCHEMA_VERSION = "1.0.0"


class DesignSpec(_Base):
    """A complete, typed statement of engineering intent for one part."""

    anvilate_spec: str = SCHEMA_VERSION
    name: str
    description: str
    units: Provenanced[UnitSystem]
    material: MaterialRef
    manufacturing: Manufacturing
    interfaces: list[Interface] = Field(default_factory=list)
    dimensions: list[ToleranceDimension] = Field(default_factory=list)
    chains: list[DimensionChain] = Field(default_factory=list)
    geometric_tolerances: list[GeometricTolerance] = Field(default_factory=list)
    load_cases: list[LoadCase] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    acceptance: AcceptanceCriteria

    # Interface contracts this part publishes for others to import against.
    exports: list[InterfaceContract] = Field(default_factory=list)

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
