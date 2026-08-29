"""Fatigue curves as records: the curve, what it was measured on, and where it came from.

An S-N curve is four things at once, and a table that carries only the first is the reason
fatigue data is so easy to misuse:

1. **The curve** — one or more power-law segments, a constant-amplitude limit, a cutoff.
2. **The survival probability** — whether it is a mean fit through the data or a design
   curve at some survival level. This is the fatigue analogue of
   :class:`~anvilate.standards.records.AllowableBasis`, and it matters more here than it
   does for a static strength: design curves are drawn a stated number of standard
   deviations of log N below the mean, and reading the mean as the design curve hands back
   exactly the margin that offset was there to provide.
3. **The specimen** — geometry, surface, loading mode, R-ratio, thickness, environment,
   temperature. A curve measured on a polished rotating-beam specimen and a curve measured
   on a welded joint are both "steel fatigue data" and neither substitutes for the other.
4. **The dataset** — where it came from, under what license, at which version or DOI.

So :class:`FatigueRecord` carries all four and refuses to be built without them. There is no
"just the curve" constructor, because a curve without its specimen is a number waiting to be
applied to the wrong part.

**Two refusals worth naming.** ``survival_probability`` is required, and ``None`` is not
available: an unclassified curve cannot satisfy a design-curve requirement, the same rule
:class:`~anvilate.standards.records.AllowableBasis` already follows. And a curve declines to
answer outside the cycle range its dataset covers — extrapolating a power law two decades
past the last test point is the kind of number that comes back looking like data.

This module is the schema. It bundles no dataset: the packs that will fill it are
license-reviewed separately (see ``openspec/changes/expand-open-design-data``).
"""

from __future__ import annotations

from enum import StrEnum
from math import isfinite

from pydantic import ConfigDict, model_validator

from .._models import RevalidatedModel
from ..units import Quantity

__all__ = [
    "CurveSurvival",
    "DatasetProvenance",
    "FatigueCurve",
    "FatigueRecord",
    "FatigueSegment",
    "LoadingMode",
    "SpecimenGeometry",
    "SpecimenMetadata",
    "WeldDetailCategory",
    "WeldStressKind",
    "EN1993_NORMAL_DETAIL_CATEGORIES",
    "en1993_detail_category_curve",
]


class CurveSurvival(StrEnum):
    """What population claim a fatigue curve carries.

    ``MEAN`` is the fit through the data — the right thing for comparing test programmes
    and the wrong thing for sizing a part. ``P95`` and ``P97_7`` are design curves at 95%
    and 97.7% survival, the latter being the mean-minus-two-standard-deviations convention
    EN 1993-1-9 and IIW curves are drawn at.
    """

    MEAN = "mean"
    P95 = "95% survival"
    P97_7 = "97.7% survival (mean − 2σ)"


# Design-curve strength ordering: a curve satisfies a requirement when it is at least as
# conservative. Mean satisfies only a mean requirement.
_SURVIVAL_RANK: dict[CurveSurvival, int] = {
    CurveSurvival.MEAN: 0,
    CurveSurvival.P95: 1,
    CurveSurvival.P97_7: 2,
}


class LoadingMode(StrEnum):
    """How the specimen was loaded. Not interchangeable: a bending curve sits above an
    axial one for the same material, because less of the section sees the peak stress."""

    AXIAL = "axial"
    BENDING = "bending"
    ROTATING_BENDING = "rotating bending"
    TORSION = "torsion"


class SpecimenGeometry(StrEnum):
    """What was tested. A polished bar and a welded joint are not the same curve."""

    POLISHED = "polished plain specimen"
    MACHINED = "machined plain specimen"
    NOTCHED = "notched specimen"
    WELDED_JOINT = "welded joint"
    COMPONENT = "component or assembly"


class DatasetProvenance(RevalidatedModel):
    """Where a curve came from, and under what terms it may be redistributed.

    ``doi`` or ``url`` is required — not both, but not neither. A fatigue curve with no
    retrievable source is a number somebody typed, and this library's entire product is
    the ability to follow a number back to its source.
    """

    model_config = ConfigDict(frozen=True)

    dataset: str
    version: str
    license: str
    retrieved: str  # ISO date the record was taken
    doi: str | None = None
    url: str | None = None
    # How many test points the curve was fitted through, when the dataset says. A curve
    # fitted to six points and one fitted to six hundred are different evidence.
    specimen_count: int | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> DatasetProvenance:
        for value, name in (
            (self.dataset, "dataset"),
            (self.version, "version"),
            (self.license, "license"),
            (self.retrieved, "retrieved"),
        ):
            if not value.strip():
                raise ValueError(f"a fatigue dataset record needs a {name}")
        if not (self.doi or self.url):
            raise ValueError(
                f"{self.dataset}: a fatigue curve needs a doi or a url. A curve nobody can "
                "retrieve is a number somebody typed"
            )
        if self.specimen_count is not None and self.specimen_count <= 0:
            raise ValueError(f"{self.dataset}: specimen_count must be positive")
        return self


class SpecimenMetadata(RevalidatedModel):
    """What the curve was measured on.

    ``stress_ratio`` R = σ_min/σ_max is the one field most likely to be missing from a
    quoted curve and most likely to matter: an R = 0 curve and an R = −1 curve for the same
    material differ by a factor that is the entire subject of mean-stress correction. It is
    required. Welded-joint curves are conventionally quoted as residual-stress-dominated
    and R-independent; say that with ``stress_ratio_independent`` rather than by inventing
    an R.
    """

    model_config = ConfigDict(frozen=True)

    material: str
    geometry: SpecimenGeometry
    loading_mode: LoadingMode
    environment: str  # "laboratory air", "3.5% NaCl", "vacuum"
    temperature: Quantity
    stress_ratio: float | None = None
    stress_ratio_independent: bool = False
    surface_finish: str | None = None
    thickness: Quantity | None = None
    stress_concentration_factor: float | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> SpecimenMetadata:
        if not self.material.strip():
            raise ValueError("a fatigue specimen record needs a material")
        if not self.environment.strip():
            raise ValueError(f"{self.material}: a fatigue specimen record needs an environment")
        if not self.temperature.has_dimension("[temperature]"):
            raise ValueError(
                f"{self.material}: temperature must be a temperature; got {self.temperature}"
            )
        if self.stress_ratio_independent and self.stress_ratio is not None:
            raise ValueError(
                f"{self.material}: the curve is declared stress-ratio independent and also "
                "carries an R. One of the two is wrong, and guessing which would put a "
                "mean-stress correction on a curve that already includes one"
            )
        if not self.stress_ratio_independent and self.stress_ratio is None:
            raise ValueError(
                f"{self.material}: a fatigue curve needs its stress ratio R. The difference "
                "between an R = 0 and an R = −1 curve is the whole subject of mean-stress "
                "correction, and a curve that does not say which it is cannot be corrected"
            )
        if self.stress_ratio is not None and not isfinite(self.stress_ratio):
            # R = −inf is a real cycle (peak at zero), but it is not a value this record
            # can carry through arithmetic, so it is declined rather than stored.
            raise ValueError(
                f"{self.material}: stress_ratio must be finite; got {self.stress_ratio}"
            )
        if self.stress_concentration_factor is not None and self.stress_concentration_factor < 1:
            raise ValueError(
                f"{self.material}: a stress concentration factor is at least 1; got "
                f"{self.stress_concentration_factor}"
            )
        if self.thickness is not None and not self.thickness.has_dimension("[length]"):
            raise ValueError(f"{self.material}: thickness must be a length; got {self.thickness}")
        return self


class FatigueSegment(RevalidatedModel):
    """One power-law branch: Δσ = Δσ_ref · (N_ref / N)^(1/m), valid up to ``max_cycles``.

    ``slope`` is the S-N exponent m in the ``N · Δσ^m = constant`` form the fatigue
    literature writes — 3 and 5 for the two EN 1993-1-9 branches. Larger m is a flatter
    curve.
    """

    model_config = ConfigDict(frozen=True)

    slope: float
    reference_stress_range: Quantity
    reference_cycles: float
    max_cycles: float

    @model_validator(mode="after")
    def _well_formed(self) -> FatigueSegment:
        if not isfinite(self.slope) or self.slope <= 0:
            raise ValueError(f"the S-N slope m must be positive and finite; got {self.slope}")
        if not self.reference_stress_range.has_dimension("[pressure]"):
            raise ValueError(
                f"reference_stress_range must be a stress; got {self.reference_stress_range}"
            )
        magnitude = self.reference_stress_range.to("MPa").magnitude
        if not isfinite(magnitude) or magnitude <= 0:
            raise ValueError(
                f"reference_stress_range must be positive and finite; got "
                f"{self.reference_stress_range}"
            )
        for value, name in (
            (self.reference_cycles, "reference_cycles"),
            (self.max_cycles, "max_cycles"),
        ):
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite; got {value}")
        return self

    def stress_range_at(self, cycles: float) -> Quantity:
        """The stress range this branch places at ``cycles``."""
        reference = self.reference_stress_range.to("MPa").magnitude
        return Quantity(
            magnitude=reference * (self.reference_cycles / cycles) ** (1.0 / self.slope),
            unit="MPa",
        )


class FatigueCurve(RevalidatedModel):
    """A piecewise S-N curve with a stated validity range and a survival probability.

    Segments run in ascending ``max_cycles`` order and must be continuous where they meet:
    a curve whose branches disagree at the breakpoint is two curves, and which one answers
    a query would depend on a floating-point comparison.

    ``cutoff_stress_range`` is the range below which the dataset claims no damage
    accumulates. It is optional, because it is a claim not every dataset makes, and a
    curve without one simply has no answer past its last segment.
    """

    model_config = ConfigDict(frozen=True)

    survival: CurveSurvival
    segments: tuple[FatigueSegment, ...]
    min_cycles: float
    cutoff_stress_range: Quantity | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> FatigueCurve:
        if not self.segments:
            raise ValueError("a fatigue curve needs at least one segment")
        if not isfinite(self.min_cycles) or self.min_cycles <= 0:
            raise ValueError(f"min_cycles must be positive and finite; got {self.min_cycles}")
        previous = self.min_cycles
        for index, segment in enumerate(self.segments):
            if segment.max_cycles <= previous:
                raise ValueError(
                    f"segment {index} ends at {segment.max_cycles:g} cycles, which is not "
                    f"beyond where the previous branch ended ({previous:g}). Segments run "
                    "in ascending order and each one has to cover ground"
                )
            previous = segment.max_cycles
        for index in range(len(self.segments) - 1):
            breakpoint_cycles = self.segments[index].max_cycles
            here = self.segments[index].stress_range_at(breakpoint_cycles).to("MPa").magnitude
            there = self.segments[index + 1].stress_range_at(breakpoint_cycles).to("MPa").magnitude
            # A relative tolerance, because the two branches are computed through different
            # fractional powers and will not agree to the last bit.
            if abs(here - there) > 1e-9 * max(here, there):
                raise ValueError(
                    f"the curve jumps at {breakpoint_cycles:g} cycles: branch {index} ends at "
                    f"{here:.6g} MPa and branch {index + 1} starts at {there:.6g} MPa. A "
                    "discontinuous curve answers a query by which side of a float comparison "
                    "it lands on"
                )
        if self.cutoff_stress_range is not None:
            if not self.cutoff_stress_range.has_dimension("[pressure]"):
                raise ValueError(
                    f"cutoff_stress_range must be a stress; got {self.cutoff_stress_range}"
                )
            cutoff = self.cutoff_stress_range.to("MPa").magnitude
            if not isfinite(cutoff) or cutoff <= 0:
                # `cutoff > last` is False for NaN, so the step-up check below waves a NaN
                # through and the curve then answers NaN past its last segment — a stress
                # range that compares False against every limit it meets. Zero and negative
                # are worse for being plausible-looking: a cutoff of zero says every stress
                # range survives forever.
                raise ValueError(
                    f"the cutoff must be a positive finite stress; got "
                    f"{self.cutoff_stress_range}. A cutoff of zero says every stress range "
                    "survives forever, and a NaN one compares False against every limit it "
                    "is checked against"
                )
            last = self.segments[-1].stress_range_at(self.segments[-1].max_cycles)
            if cutoff > last.to("MPa").magnitude * (1 + 1e-9):
                raise ValueError(
                    f"the cutoff ({self.cutoff_stress_range}) sits above where the curve ends "
                    f"({last}). A cutoff is the floor the curve runs down to, not a step up"
                )
        return self

    @property
    def max_cycles(self) -> float:
        """The last cycle count the curve's segments cover."""
        return self.segments[-1].max_cycles

    def meets_survival(self, required: CurveSurvival) -> bool:
        """Whether this curve is at least as conservative as ``required``."""
        return _SURVIVAL_RANK[self.survival] >= _SURVIVAL_RANK[required]

    def stress_range_at(self, cycles: float) -> Quantity | None:
        """The allowable stress range at ``cycles``, or ``None`` outside the curve's range.

        ``None`` rather than an extrapolation, and rather than an exception, because the
        caller's honest response is a ``not_evaluated`` check. A power law run two decades
        past the last test point returns a number that looks exactly like data.
        """
        if not isfinite(cycles) or cycles <= 0:
            return None
        if cycles < self.min_cycles:
            return None
        for segment in self.segments:
            if cycles <= segment.max_cycles:
                return segment.stress_range_at(cycles)
        return self.cutoff_stress_range


class FatigueRecord(RevalidatedModel):
    """One fatigue curve, what it was measured on, and where it came from."""

    model_config = ConfigDict(frozen=True)

    name: str
    curve: FatigueCurve
    specimen: SpecimenMetadata
    provenance: DatasetProvenance

    @model_validator(mode="after")
    def _well_formed(self) -> FatigueRecord:
        if not self.name.strip():
            raise ValueError("a fatigue record needs a name")
        return self

    def allowable_stress_range(
        self, *, cycles: float, required_survival: CurveSurvival
    ) -> Quantity | None:
        """The allowable range at ``cycles``, or ``None`` if this record cannot answer.

        Two ways it declines, and they are the two this schema exists for: the curve does
        not carry the survival probability the caller requires (a mean curve asked for a
        design answer), or the target life sits outside the range the dataset covers.
        """
        if not self.curve.meets_survival(required_survival):
            return None
        return self.curve.stress_range_at(cycles)


# EN 1993-1-9's standardized nominal-stress curve, as a record's worth of curve. The
# anchors are the standard's: Δσ_C at 2M cycles, m = 3 down to the constant-amplitude limit
# at 5M, m = 5 to the cutoff at 100M. Δσ_D = Δσ_C·(2/5)^(1/3) and Δσ_L = Δσ_D·(5/100)^(1/5)
# fall out of the two branches rather than being separate constants, which is why they are
# computed here instead of tabulated.
_EN1993_N_C = 2.0e6
_EN1993_N_D = 5.0e6
_EN1993_N_L = 1.0e8
_EN1993_SLOPE_HIGH = 3.0
_EN1993_SLOPE_LOW = 5.0
# The standard's curves are drawn at mean minus two standard deviations of log N.
_EN1993_SURVIVAL = CurveSurvival.P97_7
# Below 10,000 cycles the nominal-stress method is outside its scope: that is low-cycle
# territory, where the standard directs you to a strain-based assessment instead.
_EN1993_MIN_CYCLES = 1.0e4


class WeldStressKind(StrEnum):
    """Which stress range a weld detail category is a category *for*.

    EN 1993-1-9 draws two different families of curve. The direct-stress curves run at
    m = 3 to the constant-amplitude limit at 5 million cycles and m = 5 from there to the
    cutoff. **The shear curves run at a single slope of m = 5 throughout**, with no knee
    at 5 million. The standard's combined-stress interaction says the same thing in its
    exponents: (Δσ/Δσ_C)³ + (Δτ/Δτ_C)⁵ ≤ 1.

    So the two are not interchangeable, and the number alone does not say which it is: a
    Δτ_C of 100 and a Δσ_C of 100 are different curves with the same label.
    """

    NORMAL = "normal"
    SHEAR = "shear"


# The direct-stress detail categories of EN 1993-1-9, read off the published fatigue
# strength curve legend (Figure 7.1; reproduced in SCI's "Introduction to fatigue design
# to BS EN 1993-1-9", New Steel Construction, September 2018). The ladder is discrete:
# the standard tabulates details into these categories and does not define curves between
# them, so a value off the ladder is a transcription error or an interpolation nobody
# published.
EN1993_NORMAL_DETAIL_CATEGORIES: tuple[int, ...] = (
    36,
    40,
    45,
    50,
    56,
    63,
    71,
    80,
    90,
    100,
    112,
    125,
    140,
    160,
)

_EN1993_STANDARD_PREFIX = "EN 1993-1-9"


class WeldDetailCategory(RevalidatedModel):
    """A weld detail category as a record: the standard, the detail, and which curve.

    A detail category is published as a bare number — "90" — and that number is the
    whole input to a weld fatigue screen. Three things have to travel with it or the
    screen is being run on a coincidence:

    * **The standard and its edition.** EN 1993-1-9's category 90 and IIW's FAT 90 are the
      same number and a different curve (the knee sits at 5 million cycles in one and
      10 million in the other), and AASHTO's letter categories are a third construction.
    * **Which stress the category is for.** See :class:`WeldStressKind`: the direct-stress
      and shear families have different slopes, and the label does not say which.
    * **The detail itself, and the table it came from.** A category number is a *verdict*
      about a geometry — where the crack starts, how the weld is finished, which direction
      the stress runs. Recording only the number is how a butt weld's category ends up on
      a fillet-welded attachment.

    ``curve()`` hands back the :class:`FatigueCurve` for the record, and refuses on a
    shear category rather than returning the direct-stress construction.
    """

    model_config = ConfigDict(frozen=True)

    standard: str
    edition: str
    table: str
    description: str
    detail_category: Quantity
    stress_kind: WeldStressKind = WeldStressKind.NORMAL

    @model_validator(mode="after")
    def _well_formed(self) -> WeldDetailCategory:
        for field, value in (
            ("standard", self.standard),
            ("edition", self.edition),
            ("table", self.table),
            ("description", self.description),
        ):
            if not value.strip():
                raise ValueError(
                    f"a weld detail category must state its {field}; a bare number is a "
                    "curve label, not a detail"
                )
        if not self.detail_category.has_dimension("[pressure]"):
            raise ValueError(f"detail_category must be a stress range; got {self.detail_category}")
        value = self.detail_category.to("MPa").magnitude
        if not isfinite(value) or value <= 0:
            raise ValueError(
                f"detail_category must be a positive, finite stress range; got "
                f"{self.detail_category}"
            )
        if (
            self.standard.startswith(_EN1993_STANDARD_PREFIX)
            and self.stress_kind is WeldStressKind.NORMAL
        ):
            ladder = EN1993_NORMAL_DETAIL_CATEGORIES
            if not any(abs(value - c) < 1e-9 for c in ladder):
                near = sorted(ladder, key=lambda c: abs(c - value))[:2]
                raise ValueError(
                    f"{value:g} MPa is not an {_EN1993_STANDARD_PREFIX} direct-stress "
                    f"detail category. The standard tabulates details into a fixed ladder "
                    f"and defines no curve between the rungs; the nearest are "
                    f"{sorted(near)}. If this came from a National Annex or another "
                    f"standard, declare that standard instead of interpolating this one"
                )
        return self

    def curve(self) -> FatigueCurve:
        """The record's S-N curve.

        Refuses on a shear category rather than handing back the direct-stress
        construction: the shear family is a single m = 5 slope with no constant-amplitude
        knee, and evaluating Δτ_C on the m = 3 branch returns a life that is wrong in the
        unconservative direction at every range above the knee.
        """
        if self.stress_kind is not WeldStressKind.NORMAL:
            raise ValueError(
                f"{self.description!r} is a {self.stress_kind.value}-stress category, and "
                "this module builds the direct-stress curve only. The shear family runs at "
                "a single slope of m = 5 with no knee at 5 million cycles, so the "
                "direct-stress construction would over-state its life"
            )
        return en1993_detail_category_curve(self.detail_category)

    def __str__(self) -> str:
        symbol = "Δσ_C" if self.stress_kind is WeldStressKind.NORMAL else "Δτ_C"
        return (
            f"{self.standard}:{self.edition} {self.table} — {self.description} "
            f"({self.stress_kind.value} {symbol} = {self.detail_category})"
        )


def en1993_detail_category_curve(detail_category: Quantity) -> FatigueCurve:
    """The EN 1993-1-9 curve for a detail category, as a :class:`FatigueCurve`.

    The standard's curve expressed in this schema rather than as a second implementation:
    the same two branches, the same breakpoints, and the constant-amplitude limit and
    cutoff derived from the branches instead of tabulated separately. It exists so a
    dataset-backed curve and a code curve are the same kind of object to a screen, and so
    the schema is held against a curve whose answers are independently known —
    :func:`~anvilate.analysis.fatigue.weld_detail_allowable_stress_range` computes them
    from the standard directly, and the two are compared in the test suite.
    """
    if not detail_category.has_dimension("[pressure]"):
        raise ValueError(f"detail_category must be a stress; got {detail_category}")
    reference = detail_category.to("MPa").magnitude
    if not isfinite(reference) or reference <= 0:
        raise ValueError(f"detail_category must be positive and finite; got {detail_category}")
    high = FatigueSegment(
        slope=_EN1993_SLOPE_HIGH,
        reference_stress_range=Quantity(magnitude=reference, unit="MPa"),
        reference_cycles=_EN1993_N_C,
        max_cycles=_EN1993_N_D,
    )
    constant_amplitude_limit = high.stress_range_at(_EN1993_N_D)
    low = FatigueSegment(
        slope=_EN1993_SLOPE_LOW,
        reference_stress_range=constant_amplitude_limit,
        reference_cycles=_EN1993_N_D,
        max_cycles=_EN1993_N_L,
    )
    return FatigueCurve(
        survival=_EN1993_SURVIVAL,
        segments=(high, low),
        min_cycles=_EN1993_MIN_CYCLES,
        cutoff_stress_range=low.stress_range_at(_EN1993_N_L),
    )
