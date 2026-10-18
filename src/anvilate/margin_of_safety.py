"""Margins of safety the way a regulated program reviews them: one governing row per check.

An aerospace stress report is not "safety factor 2.4, pass". It is a margin table: per
check, the governing load case, the allowable with its statistical basis, every factor in
its own column, and MS = allowable / (applied × FS × special factors) − 1, for yield and
for ultimate separately, passing at MS ≥ 0. This module is the bookkeeping that makes such
a table trustworthy, and it refuses the four errors a reviewer looks for first:

- **A load that does not say whether it is limit or ultimate.** Factoring an ultimate load
  again, or forgetting to factor a limit load, is the classic error. An untagged load is
  refused from the report, naming it. An ultimate load is never multiplied by the ultimate
  factor again, and the row says it was already ultimate.
- **Factors chosen by taste.** Every margin is computed under a named :class:`FactorSet`
  with its source. The bundled sets carry only values read from public-domain documents,
  each with its clause (``docs/margin-of-safety.md`` records where each was read). A
  company's own set is declared the same way, with its document number as the source.
- **An allowable on the wrong basis.** Where the set requires a basis for the declared
  load path (A-basis for a single load path, typically), a check on a weaker basis is not
  evaluated, naming the basis required and the basis given.
- **One case reported out of hundreds.** Every check is evaluated over every case that
  reaches it; the row names the governing case, how many were evaluated, every case tied
  with it, and every case that could not be evaluated — counted, never dropped.

The verification approach is part of the binding: an item qualified by analysis alone gets
the set's analysis-only factors, and a material class the set excludes from analysis-only
qualification has its margins refused with the clause, and the test the set requires added
to the report's verification items.

The report informs and never certifies. Certification credit and fitting-factor waivers are
out: a waiver is the user's declared decision, made in their own factor set with its basis.
"""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Sequence
from enum import StrEnum
from math import hypot, inf, isfinite, prod
from typing import Any, Self
from xml.sax.saxutils import escape

from pydantic import ConfigDict, computed_field, model_validator

from ._models import Named, Provenance, StatableModel, each_one
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus
from .verification import VerificationArchetype, VerificationItem, VerificationMethod

__all__ = [
    "LoadLevel",
    "AllowableBasis",
    "LoadPath",
    "VerificationApproach",
    "MaterialClass",
    "QuantityKind",
    "MarginLimit",
    "StackingRule",
    "FactorRow",
    "SpecialFactor",
    "BasisRule",
    "AnalysisExclusion",
    "FactorSet",
    "Allowable",
    "LoadCase",
    "MarginCheck",
    "AppliedFactor",
    "UnevaluatedCase",
    "ForceRole",
    "BodyForce",
    "FreeBody",
    "DEFAULT_EQUILIBRIUM_TOLERANCE",
    "MarginRow",
    "RequiredTest",
    "SubsystemMinimum",
    "MarginReport",
    "DEFAULT_TIE_TOLERANCE",
    "bundled_factor_sets",
    "factor_set",
    "margin_table",
]

_SET_SOURCE = "the factor set's own document: its table, clause and edition"
_CHECK_SOURCE = "the check's declaration: its item, failure mode, allowables and load cases"

#: Cases whose margin is within this of the governing one are reported as ties. Absolute, in
#: margin units: 0.005 is half a percent of the allowable at MS = 0.
DEFAULT_TIE_TOLERANCE = 0.005


class _MarginOfSafetyInputError(RefusalError, ValueError):
    """A margin-of-safety input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _MarginOfSafetyInputError:
    return _MarginOfSafetyInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class LoadLevel(StrEnum):
    """Whether a load is the expected maximum (limit) or already factored to ultimate."""

    LIMIT = "limit"
    ULTIMATE = "ultimate"


class AllowableBasis(StrEnum):
    """The statistical basis of an allowable, as the allowables handbooks name them.

    A and B are population floors (99% and 90% of the population, at 95% confidence); S is
    a specification minimum; typical is the middle of the scatter; user_declared is a value
    the user asserts with their own source. A set states which it accepts per load path —
    no ordering between them is assumed here.
    """

    A = "A"
    B = "B"
    S = "S"
    TYPICAL = "typical"
    USER_DECLARED = "user_declared"


class LoadPath(StrEnum):
    """The load-path redundancy that decides which allowable basis a set requires."""

    SINGLE = "single_load_path"
    REDUNDANT = "redundant"


class VerificationApproach(StrEnum):
    """Whether the item's strength is qualified by a structural test or by analysis alone."""

    TEST = "test"
    ANALYSIS_ONLY = "analysis_only"


class MaterialClass(StrEnum):
    """The material classes the public factor tables distinguish.

    ``composite`` is composite or bonded structure in uniform material, and
    ``composite_discontinuity`` the same at a discontinuity, where stresses concentrate —
    NASA-STD-5001B Table 2 gives the two different ultimate factors. ``bonded`` is a bonded
    insert or joint, which GSFC-STD-7000B Table 2.2-3 states separately.
    """

    METALLIC = "metallic"
    BERYLLIUM = "beryllium"
    COMPOSITE = "composite"
    COMPOSITE_DISCONTINUITY = "composite_discontinuity"
    BONDED = "bonded"
    GLASS_CERAMIC = "glass_ceramic"


class QuantityKind(StrEnum):
    """What the applied effect and the allowable both are, in one unit."""

    FORCE = "force"
    MOMENT = "moment"
    STRESS = "stress"
    STRAIN = "strain"
    PRESSURE = "pressure"


class MarginLimit(StrEnum):
    """The two margins a regulated program reports, on separate rows."""

    YIELD = "yield"
    ULTIMATE = "ultimate"


class StackingRule(StrEnum):
    """How a set combines several special factors that apply to one check."""

    MULTIPLY = "multiply"
    LARGEST = "largest"


def _a_factor(value: float, *, what: str, subject: str) -> None:
    if not isfinite(value) or value < 1.0:
        raise _refusal(
            f"{what} is {value}; a factor of safety is a finite number of at least 1, and "
            "anything below 1 makes a margin less conservative than the load itself",
            subject=subject,
            source=_SET_SOURCE,
        )


class FactorRow(StatableModel):
    """The yield and ultimate factors a set prescribes for one material class and approach.

    ``yield_factor`` is ``None`` where the set prescribes no yield margin for the class —
    a composite or glass has no yield point to report against. ``material_class`` or
    ``approach`` is ``None`` where the source does not distinguish them: 14 CFR 25.303 is
    one factor for every material. A row naming both is read before one naming either,
    and either before one naming neither.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    material_class: MaterialClass | None
    approach: VerificationApproach | None
    yield_factor: float | None
    ultimate_factor: float
    clause: Provenance

    @model_validator(mode="after")
    def _factors(self) -> Self:
        if self.yield_factor is not None:
            _a_factor(self.yield_factor, what="the yield factor", subject="yield_factor")
        _a_factor(self.ultimate_factor, what="the ultimate factor", subject="ultimate_factor")
        return self


class SpecialFactor(StatableModel):
    """A factor a set applies on top of the factor of safety: fitting, casting, bearing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    value: float
    clause: Provenance
    applies_to: tuple[MarginLimit, ...] = (MarginLimit.YIELD, MarginLimit.ULTIMATE)

    @model_validator(mode="after")
    def _a_special(self) -> Self:
        _a_factor(self.value, what=f"special factor '{self.name}'", subject="value")
        if not self.applies_to or len(set(self.applies_to)) != len(self.applies_to):
            raise _refusal(
                f"special factor '{self.name}' applies to {list(self.applies_to)}; it must "
                "name yield, ultimate or both, each once",
                subject="applies_to",
                source=_SET_SOURCE,
            )
        return self


class BasisRule(StatableModel):
    """The allowable bases a set accepts for one load-path class, and the clause saying so."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    load_path: LoadPath
    accepted: tuple[AllowableBasis, ...]
    clause: Provenance

    @model_validator(mode="after")
    def _some_basis(self) -> Self:
        if not self.accepted or len(set(self.accepted)) != len(self.accepted):
            raise _refusal(
                f"the basis rule for {self.load_path.value} accepts {list(self.accepted)}; it "
                "must accept at least one basis, each once",
                subject="accepted",
                source=_SET_SOURCE,
            )
        return self


class AnalysisExclusion(StatableModel):
    """A material class a set does not let be qualified by analysis alone, and its test."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    material_class: MaterialClass
    required_test: Named
    clause: Provenance


class FactorSet(StatableModel):
    """A named, cited set of factors a margin report is computed under.

    ``source`` is the document and edition — a bundled set's public-domain standard, or a
    company's own document number. Every row of every report computed under the set names
    both, so a reviewer can tell whose rules a margin was held to.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    source: Provenance
    rows: tuple[FactorRow, ...]
    special_factors: tuple[SpecialFactor, ...] = ()
    stacking: StackingRule = StackingRule.MULTIPLY
    stacking_clause: str | None = None
    basis_rules: tuple[BasisRule, ...] = ()
    exclusions: tuple[AnalysisExclusion, ...] = ()

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if not self.rows:
            raise _refusal(
                f"factor set '{self.name}' has no factor rows; a set prescribes at least one "
                "material class's yield and ultimate factors",
                subject="rows",
                source=_SET_SOURCE,
            )
        keys = [(row.material_class, row.approach) for row in self.rows]
        doubled = sorted({f"{m or 'any'}/{a or 'any'}" for m, a in keys if keys.count((m, a)) > 1})
        if doubled:
            raise _refusal(
                f"factor set '{self.name}' states factors twice for {doubled}; one row per "
                "material class and verification approach, or the margin depends on which "
                "row is read first",
                subject="rows",
                source=_SET_SOURCE,
            )
        names = [special.name for special in self.special_factors]
        if len(set(names)) != len(names):
            raise _refusal(
                f"factor set '{self.name}' names a special factor twice: {names}",
                subject="special_factors",
                source=_SET_SOURCE,
            )
        paths = [rule.load_path for rule in self.basis_rules]
        if len(set(paths)) != len(paths):
            raise _refusal(
                f"factor set '{self.name}' states two basis rules for one load path",
                subject="basis_rules",
                source=_SET_SOURCE,
            )
        excluded = [exclusion.material_class for exclusion in self.exclusions]
        if len(set(excluded)) != len(excluded):
            raise _refusal(
                f"factor set '{self.name}' excludes one material class twice",
                subject="exclusions",
                source=_SET_SOURCE,
            )
        contradicted = sorted(
            m.value for m in excluded if (m, VerificationApproach.ANALYSIS_ONLY) in keys
        )
        if contradicted:
            raise _refusal(
                f"factor set '{self.name}' both excludes {contradicted} from analysis-only "
                "qualification and states analysis-only factors for it; one of the two is "
                "not what the source says",
                subject="exclusions",
                source=_SET_SOURCE,
            )
        if len(self.special_factors) > 1 and not self.stacking_clause:
            raise _refusal(
                f"factor set '{self.name}' has {len(self.special_factors)} special factors and "
                "no clause for how they stack; whether they multiply or the largest governs "
                "changes every margin that carries two of them",
                subject="stacking_clause",
                source=_SET_SOURCE,
            )
        return self

    def row(self, material: MaterialClass, approach: VerificationApproach) -> FactorRow | None:
        """The factors for ``material`` qualified by ``approach``, or ``None`` if unstated.

        The most specific row wins: both named, then the material alone, then the approach
        alone, then a row for every material and approach.
        """
        for key in ((material, approach), (material, None), (None, approach), (None, None)):
            for row in self.rows:
                if (row.material_class, row.approach) == key:
                    return row
        return None

    def exclusion(self, material: MaterialClass) -> AnalysisExclusion | None:
        """The analysis-only exclusion for ``material``, if the set states one."""
        for exclusion in self.exclusions:
            if exclusion.material_class is material:
                return exclusion
        return None

    def basis_rule(self, load_path: LoadPath) -> BasisRule | None:
        """The bases the set accepts for ``load_path``, if it states a rule."""
        for rule in self.basis_rules:
            if rule.load_path is load_path:
                return rule
        return None

    def __str__(self) -> str:
        return f"{self.name} ({self.source})"


class Allowable(StatableModel):
    """A capacity in the check's quantity, with its statistical basis and source."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    states_requirements = True

    value: float
    basis: AllowableBasis
    source: Provenance

    @model_validator(mode="after")
    def _positive(self) -> Self:
        if not self.value > 0:
            raise _refusal(
                f"an allowable of {self.value} is no capacity; an allowable is a positive "
                "finite value in the check's quantity",
                subject="value",
                source="the allowables table, datasheet or test report the value was read from",
            )
        return self


class LoadCase(StatableModel):
    """One load case's applied effect on a check, tagged limit or ultimate.

    ``level`` may be absent — a case imported from a solver arrives untagged — but a margin
    report refuses it: whether it is factored depends on the tag, and guessing is the error
    this module exists to stop.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    states_requirements = True

    case: Named
    applied: float
    level: LoadLevel | None = None


class ForceRole(StrEnum):
    """Whether a force on a free body is a load put on it or a reaction holding it."""

    APPLIED = "applied"
    REACTION = "reaction"


class BodyForce(StatableModel):
    """One force on a planar free body: where it acts, its components, and any couple.

    ``x`` and ``y`` are in the free body's length unit; ``fx`` and ``fy`` in its force unit;
    ``moment`` is a couple about the out-of-plane axis, counter-clockwise positive, in force
    unit × length unit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    states_requirements = True

    name: Named
    role: ForceRole
    x: float
    y: float
    fx: float
    fy: float
    moment: float = 0.0


#: A free body is in equilibrium when each residual is within this share of the largest
#: applied load: 1% of the largest force, and 1% of that force times the outline's diagonal.
DEFAULT_EQUILIBRIUM_TOLERANCE = 0.01


class FreeBody(StatableModel):
    """The free body behind one load case: the item's outline, the loads in, the reactions out.

    The residual is what is left when every force and couple is summed. A free body a
    reviewer can sign has a residual within ``tolerance`` of the largest applied load; one
    that does not is a finding on the margin row it backs, because the reactions it shows
    are not the ones the applied loads produce.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    states_requirements = True

    case: Named
    outline: tuple[tuple[float, float], ...]
    length_unit: Named
    force_unit: Named
    forces: tuple[BodyForce, ...]
    tolerance: float = DEFAULT_EQUILIBRIUM_TOLERANCE

    @model_validator(mode="after")
    def _a_body(self) -> Self:
        if len(self.outline) < 3:
            raise _refusal(
                f"the free body for '{self.case}' has an outline of {len(self.outline)} "
                "points; an outline is a polygon of at least three",
                subject="outline",
                source="the item's outline in the plane of the loads",
            )
        if not any(force.role is ForceRole.APPLIED for force in self.forces):
            raise _refusal(
                f"the free body for '{self.case}' has no applied load; a free body shows the "
                "loads in and the reactions out",
                subject="forces",
                source="the load case's applied loads at their points of application",
            )
        names = [force.name for force in self.forces]
        doubled = sorted({name for name in names if names.count(name) > 1})
        if doubled:
            raise _refusal(
                f"the free body for '{self.case}' names forces {doubled} twice",
                subject="forces",
                source="one name per force on the free body",
            )
        if not 0 < self.tolerance < 1:
            raise _refusal(
                f"the equilibrium tolerance is {self.tolerance}; it is a share of the largest "
                "applied load, above 0 and below 1",
                subject="tolerance",
                source="the share of the largest applied load a residual may be",
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def residual(self) -> tuple[float, float, float]:
        """ΣFx, ΣFy and ΣM about the origin of the outline's coordinates."""
        return (
            sum(force.fx for force in self.forces),
            sum(force.fy for force in self.forces),
            sum(force.x * force.fy - force.y * force.fx + force.moment for force in self.forces),
        )

    def _scales(self) -> tuple[float, float]:
        largest = max(hypot(f.fx, f.fy) for f in self.forces if f.role is ForceRole.APPLIED)
        xs = [x for x, _ in self.outline]
        ys = [y for _, y in self.outline]
        return largest, largest * hypot(max(xs) - min(xs), max(ys) - min(ys))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def balanced(self) -> bool:
        """Whether both residuals are within the tolerance of the largest applied load."""
        return self.finding() is None

    def finding(self) -> str | None:
        """The equilibrium finding a margin row carries, or ``None`` when the body balances."""
        fx, fy, m = self.residual
        force_scale, moment_scale = self._scales()
        out = []
        if hypot(fx, fy) > self.tolerance * force_scale:
            out.append(f"ΣF = ({fx:.4g}, {fy:.4g}) {self.force_unit}")
        if abs(m) > self.tolerance * moment_scale:
            out.append(f"ΣM = {m:.4g} {self.force_unit}·{self.length_unit}")
        if not out:
            return None
        return (
            f"the free body for '{self.case}' is out of equilibrium: {' and '.join(out)}, "
            f"beyond {self.tolerance:g} of the largest applied load "
            f"({force_scale:.4g} {self.force_unit})"
        )

    def svg(self, *, width_px: int = 480) -> bytes:
        """The free body as SVG: outline, applied loads, reactions, and the residual.

        Arrows end at their point of application with length in proportion to magnitude;
        applied loads are drawn solid and reactions dashed, and every arrow is labelled.
        """
        from .projection import _INK, _document, _polyline, _text

        if not 160 <= width_px <= 4096:
            raise _refusal(
                f"width_px is {width_px}; a free-body picture is 160 to 4,096 pixels wide",
                subject="width_px",
                source="a picture width in pixels",
            )
        xs = [x for x, _ in self.outline] + [f.x for f in self.forces]
        ys = [y for _, y in self.outline] + [f.y for f in self.forces]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        largest = max(hypot(f.fx, f.fy) for f in self.forces) or 1.0
        arrow = 0.35 * span  # the longest arrow, in model units
        tails = [(f.x - f.fx / largest * arrow, f.y - f.fy / largest * arrow) for f in self.forces]
        xs += [x for x, _ in tails]
        ys += [y for _, y in tails]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        margin, text = 40.0, max(9.0, width_px / 48)
        scale = (width_px - 2 * margin) / max(x1 - x0, y1 - y0, 1e-12)
        height_px = round((y1 - y0) * scale + 2 * margin + 3 * text * 1.6)

        def at(x: float, y: float) -> tuple[float, float]:
            return margin + (x - x0) * scale, margin + (y1 - y) * scale

        outline = " ".join(f"{a:.2f},{b:.2f}" for a, b in (at(x, y) for x, y in self.outline))
        body = [f'<polygon points="{outline}" fill="#e2e8f0" stroke="{_INK}"/>']
        for force, tail in zip(self.forces, tails, strict=True):
            head = at(force.x, force.y)
            start = at(*tail)
            colour = "#b91c1c" if force.role is ForceRole.APPLIED else "#1d4ed8"
            dash = "" if force.role is ForceRole.APPLIED else ' stroke-dasharray="6 4"'
            body.append(
                f'<path d="{_polyline([start, head])}" fill="none" stroke="{colour}" '
                f'stroke-width="2"{dash}/>'
            )
            length = hypot(head[0] - start[0], head[1] - start[1])
            if length > 0:
                ux, uy = (head[0] - start[0]) / length, (head[1] - start[1]) / length
                barb = 10.0
                left = (
                    head[0] - barb * ux - barb * 0.45 * uy,
                    head[1] - barb * uy + barb * 0.45 * ux,
                )
                right = (
                    head[0] - barb * ux + barb * 0.45 * uy,
                    head[1] - barb * uy - barb * 0.45 * ux,
                )
                body.append(
                    f'<polygon points="{head[0]:.2f},{head[1]:.2f} {left[0]:.2f},{left[1]:.2f} '
                    f'{right[0]:.2f},{right[1]:.2f}" fill="{colour}" stroke="{colour}"/>'
                )
            magnitude = hypot(force.fx, force.fy)
            # A label on the right half reads leftward from its arrow, so none runs off the page.
            right_half = start[0] > width_px / 2
            body.append(
                _text(
                    f"{force.name} {magnitude:.4g} {self.force_unit}",
                    start[0] - 4 if right_half else start[0] + 4,
                    start[1] - 4,
                    text * 0.8,
                    anchor="end" if right_half else "start",
                )
            )
        fx, fy, m = self.residual
        verdict = "IN EQUILIBRIUM" if self.balanced else "OUT OF EQUILIBRIUM"
        base = height_px - 3 * text * 1.6 + text
        body.append(_text(f"{self.case}: {verdict}", 8, base, text))
        body.append(
            _text(f"SUM F: {fx:.4g}, {fy:.4g} {self.force_unit}", 8, base + text * 1.6, text * 0.8)
        )
        body.append(
            _text(f"SUM M: {m:.4g} {self.force_unit} {self.length_unit}", 8,
                  base + text * 3.2, text * 0.8)
        )  # fmt: skip
        label = "".join(c if c.isalnum() or c in " .-_" else " " for c in self.case)
        return _document(width_px, height_px, f"free body {label}", body)


class MarginCheck(StatableModel):
    """One failure mode of one item, its allowables, and every load case that reaches it.

    ``applied`` on each case and both allowables are in ``unit`` of ``quantity``: the margin
    is a ratio of the two, so they must be one quantity in one unit. ``special_factors``
    names which of the bound set's special factors apply (``"fitting"`` for a fitting).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Named
    subsystem: Named
    failure_mode: Named
    method: Named
    method_citation: Provenance
    quantity: QuantityKind
    unit: Named
    material_class: MaterialClass
    load_path: LoadPath
    approach: VerificationApproach
    ultimate_allowable: Allowable
    yield_allowable: Allowable | None = None
    special_factors: tuple[str, ...] = ()
    cases: tuple[LoadCase, ...]
    free_bodies: tuple[FreeBody, ...] = ()

    @model_validator(mode="after")
    def _cases(self) -> Self:
        if not self.cases:
            raise _refusal(
                f"check '{self.identity}' has no load cases; a margin is computed against "
                "at least one applied load",
                subject="cases",
                source=_CHECK_SOURCE,
            )
        names = [case.case for case in self.cases]
        doubled = sorted({name for name in names if names.count(name) > 1})
        if doubled:
            raise _refusal(
                f"check '{self.identity}' carries load cases {doubled} twice; the governing "
                "case is named by its identity, so each must be distinct",
                subject="cases",
                source=_CHECK_SOURCE,
            )
        if len(set(self.special_factors)) != len(self.special_factors):
            raise _refusal(
                f"check '{self.identity}' names a special factor twice: "
                f"{list(self.special_factors)}",
                subject="special_factors",
                source=_CHECK_SOURCE,
            )
        bodies = [body.case for body in self.free_bodies]
        stray = sorted(set(bodies) - set(names))
        if stray or len(set(bodies)) != len(bodies):
            raise _refusal(
                f"check '{self.identity}' carries free bodies for {bodies}; each must back one "
                f"of its own load cases ({names}), once"
                + (f" — {stray} is not one of them" if stray else ""),
                subject="free_bodies",
                source=_CHECK_SOURCE,
            )
        return self

    def free_body(self, case: str) -> FreeBody | None:
        """The free body declared for ``case``, if there is one."""
        for body in self.free_bodies:
            if body.case == case:
                return body
        return None

    @property
    def identity(self) -> str:
        """The row identity a reviewer searches for: item, then failure mode."""
        return f"{self.item}: {self.failure_mode}"


class AppliedFactor(StatableModel):
    """One factor in its own column of a margin row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    value: float
    clause: Provenance


class UnevaluatedCase(StatableModel):
    """A load case that reached a check and could not be evaluated, with why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case: Named
    reason: Named


class MarginRow(StatableModel):
    """One margin in the table: a check's governing case for yield or for ultimate.

    ``margin`` is ``None`` exactly when ``status`` is ``NOT_EVALUATED``, and ``reason`` then
    says why. ``factor_of_safety`` is the factor applied to the governing case: 1.0 with
    ``already_ultimate`` set when that case was declared ultimate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check: Named
    item: Named
    subsystem: Named
    failure_mode: Named
    method: Named
    method_citation: Provenance
    limit: MarginLimit
    quantity: QuantityKind
    unit: Named
    factor_set: Named
    factor_set_source: Provenance
    status: CheckStatus
    margin: float | None = None
    reason: str | None = None
    governing_case: str | None = None
    applied: float | None = None
    already_ultimate: bool = False
    allowable: float | None = None
    basis: AllowableBasis | None = None
    allowable_source: str | None = None
    factor_of_safety: float | None = None
    factor_clause: str | None = None
    special: tuple[AppliedFactor, ...] = ()
    special_product: float = 1.0
    cases_evaluated: int = 0
    ties: tuple[str, ...] = ()
    unevaluated: tuple[UnevaluatedCase, ...] = ()
    free_body: FreeBody | None = None
    finding: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        evaluated = self.status is not CheckStatus.NOT_EVALUATED
        if evaluated != (self.margin is not None):
            raise _refusal(
                f"margin row '{self.check}' ({self.limit.value}) is {self.status.value} with "
                f"margin {self.margin}; a margin is stated exactly when it was evaluated",
                subject="margin",
                source="the margin computed for the governing case",
            )
        if not evaluated and not self.reason:
            raise _refusal(
                f"margin row '{self.check}' ({self.limit.value}) was not evaluated and says "
                "nothing about why",
                subject="reason",
                source="the rule that stopped the margin being computed",
            )
        if evaluated and self.status is not (
            CheckStatus.PASS if self.margin >= 0 else CheckStatus.FAIL  # type: ignore[operator]
        ):
            raise _refusal(
                f"margin row '{self.check}' reads {self.status.value} at MS {self.margin}; "
                "a margin passes at MS >= 0 and fails below it",
                subject="status",
                source="the margin computed for the governing case",
            )
        return self

    @property
    def margin_text(self) -> str:
        """The margin as a reviewer reads it: signed, two places, or the reason it is absent."""
        if self.margin is None:
            return "not evaluated"
        if self.margin == inf:
            return "+inf (no applied load)"
        return f"{self.margin:+.2f}"

    def __str__(self) -> str:
        where = f" at {self.governing_case}" if self.governing_case else ""
        tail = f" — {self.reason}" if self.reason else ""
        return (
            f"[{self.status.value.upper()}] {self.check} ({self.limit.value}): "
            f"MS {self.margin_text}{where} [{self.factor_set}]{tail}"
        )


class SubsystemMinimum(StatableModel):
    """A subsystem's lowest margin and the row that holds it, for a design review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subsystem: Named
    lowest: MarginRow | None
    rows: int
    not_evaluated: int


class RequiredTest(StatableModel):
    """A test the bound set requires before an item's margins can be computed.

    Planned, never evidence: :meth:`MarginReport.verification_items` turns each into a
    :class:`~anvilate.verification.VerificationItem` whose status is not evaluated until an
    outcome is recorded.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    check: Named
    item: Named
    test: Named
    clause: Provenance
    factor_set: Named


_STATUS_ORDER = {CheckStatus.NOT_EVALUATED: 0, CheckStatus.FAIL: 1, CheckStatus.PASS: 2}

_COLUMNS = (
    "subsystem",
    "item",
    "failure mode",
    "limit",
    "status",
    "MS",
    "governing case",
    "cases evaluated",
    "ties",
    "unevaluated cases",
    "quantity",
    "unit",
    "applied",
    "load level",
    "allowable",
    "basis",
    "allowable source",
    "FS",
    "FS clause",
    "special factors",
    "special product",
    "method",
    "method citation",
    "factor set",
    "factor set source",
    "reason",
    "free body",
)


def _number(value: float | None) -> str:
    if value is None:
        return ""
    return "inf" if value == inf else f"{value:.6g}"


def _cells(row: MarginRow) -> tuple[str, ...]:
    if row.governing_case is None:
        level = ""
    else:
        level = "ultimate (not factored again)" if row.already_ultimate else "limit"
    return (
        row.subsystem,
        row.item,
        row.failure_mode,
        row.limit.value,
        row.status.value,
        "" if row.margin is None else _number(round(row.margin, 6)),
        row.governing_case or "",
        str(row.cases_evaluated),
        "; ".join(row.ties),
        "; ".join(f"{u.case} ({u.reason})" for u in row.unevaluated),
        row.quantity.value,
        row.unit,
        _number(row.applied),
        level,
        _number(row.allowable),
        row.basis.value if row.basis is not None else "",
        row.allowable_source or "",
        _number(row.factor_of_safety),
        row.factor_clause or "",
        "; ".join(f"{s.name} {s.value:g} ({s.clause})" for s in row.special),
        _number(row.special_product),
        row.method,
        row.method_citation,
        row.factor_set,
        row.factor_set_source,
        row.reason or "",
        row.finding
        or ("" if row.free_body is None else f"in equilibrium within {row.free_body.tolerance:g}"),
    )


# A text cell a spreadsheet would read as a formula. Numbers are written as numbers and a
# negative margin is not text, so only the free-text columns are guarded.
_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")
_NUMERIC_COLUMNS = frozenset({"MS", "cases evaluated", "applied", "allowable", "FS"})
_NUMERIC_COLUMNS |= {"special product"}


def _csv_safe(column: str, cell: str) -> str:
    if column in _NUMERIC_COLUMNS or not cell.startswith(_FORMULA_LEADS):
        return cell
    return "'" + cell


class MarginReport(StatableModel):
    """The margin table under one factor set: every row, ascending, and the review summary.

    Rows are sorted not-evaluated first (a margin nobody computed is the least known), then
    by ascending margin. ``required_tests`` holds the tests the set requires for items it
    excludes from analysis-only qualification — planned, never evidence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    factor_set: Named
    factor_set_source: Provenance
    tie_tolerance: float
    rows: tuple[MarginRow, ...]
    required_tests: tuple[RequiredTest, ...] = ()

    def verification_items(self) -> tuple[VerificationItem, ...]:
        """The required tests as verification-plan items, each planned and not evaluated."""
        return tuple(
            VerificationItem(
                name=f"{test.test}: {test.item}",
                archetype=VerificationArchetype(
                    key="structural-qualification",
                    method=VerificationMethod.TEST,
                    title=test.test,
                    citation=test.clause,
                ),
                driving_checks=(test.check,),
                acceptance=f"the test {test.factor_set} requires ({test.clause})",
            )
            for test in self.required_tests
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        """FAIL if any margin is negative, else NOT_EVALUATED if any is missing, else PASS."""
        statuses = {row.status for row in self.rows}
        if CheckStatus.FAIL in statuses:
            return CheckStatus.FAIL
        if CheckStatus.NOT_EVALUATED in statuses or not self.rows:
            return CheckStatus.NOT_EVALUATED
        return CheckStatus.PASS

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> tuple[SubsystemMinimum, ...]:
        """Each subsystem's lowest evaluated margin, in ascending order of it."""
        subsystems: dict[str, list[MarginRow]] = {}
        for row in self.rows:
            subsystems.setdefault(row.subsystem, []).append(row)
        minima = []
        for name, rows in subsystems.items():
            evaluated = [row for row in rows if row.margin is not None]
            lowest = min(evaluated, key=lambda row: row.margin) if evaluated else None  # type: ignore[arg-type,return-value]
            minima.append(
                SubsystemMinimum(
                    subsystem=name,
                    lowest=lowest,
                    rows=len(rows),
                    not_evaluated=len(rows) - len(evaluated),
                )
            )
        return tuple(
            sorted(
                minima,
                key=lambda m: (
                    m.lowest is not None,
                    m.lowest.margin if m.lowest is not None else 0.0,
                    m.subsystem,
                ),
            )
        )

    def to_csv(self) -> str:
        """The table as CSV: a header row, then every row in the report's order."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(_COLUMNS)
        for row in self.rows:
            writer.writerow(
                [
                    _csv_safe(column, cell)
                    for column, cell in zip(_COLUMNS, _cells(row), strict=True)
                ]
            )
        return out.getvalue()

    def to_xlsx(self) -> bytes:
        """The table as an XLSX workbook: a Summary sheet, then a Margins sheet.

        Written with the standard library: inline strings and numbers only, so no cell is
        ever a formula, and fixed archive timestamps so one report is one byte string.
        """
        summary = [("subsystem", "lowest MS", "check", "limit", "governing case", "rows",
                    "not evaluated")]  # fmt: skip
        for minimum in self.summary:
            lowest = minimum.lowest
            summary.append(
                (
                    minimum.subsystem,
                    _number(lowest.margin) if lowest is not None else "not evaluated",
                    lowest.check if lowest is not None else "",
                    lowest.limit.value if lowest is not None else "",
                    (lowest.governing_case or "") if lowest is not None else "",
                    str(minimum.rows),
                    str(minimum.not_evaluated),
                )
            )
        margins = [_COLUMNS, *(_cells(row) for row in self.rows)]
        numeric = {i for i, column in enumerate(_COLUMNS) if column in _NUMERIC_COLUMNS}
        return _workbook((("Summary", summary, {1, 5, 6}), ("Margins", margins, numeric)))

    def section(self) -> str:
        """The table as a Markdown report section, summary first, rows ascending."""
        lines = [
            f"## Margins of safety — {self.factor_set}",
            "",
            f"Factor set: {self.factor_set_source}. MS = allowable / (applied × FS × special "
            f"factors) − 1, passing at MS ≥ 0. Cases within {self.tie_tolerance:g} of the "
            "governing margin are listed as ties.",
            "",
            "### Lowest margin per subsystem",
            "",
            "| Subsystem | Lowest MS | Check | Limit | Governing case | Not evaluated |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for minimum in self.summary:
            lowest = minimum.lowest
            if lowest is None:
                lines.append(
                    f"| {_md(minimum.subsystem)} | not evaluated | | | | {minimum.not_evaluated} |"
                )
                continue
            lines.append(
                f"| {_md(minimum.subsystem)} | {lowest.margin_text} | {_md(lowest.check)} | "
                f"{lowest.limit.value} | {_md(lowest.governing_case or '')} | "
                f"{minimum.not_evaluated} |"
            )
        lines += [
            "",
            "### Every margin, ascending",
            "",
            "| Check | Limit | MS | Governing case | Evaluated | Applied | Level | Allowable "
            "(basis) | FS | Special | Status |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for row in self.rows:
            cells = _cells(row)
            special = "; ".join(f"{s.name} {s.value:g}" for s in row.special) or "—"
            basis = f" ({row.basis.value})" if row.basis is not None else ""
            lines.append(
                f"| {_md(row.check)} | {row.limit.value} | {row.margin_text} | "
                f"{_md(row.governing_case or '—')} | {row.cases_evaluated} | {cells[12]} "
                f"{_md(row.unit)} | {cells[13] or '—'} | {cells[14]}{basis} | {cells[17]} | "
                f"{_md(special)} | {row.status.value}"
                + (f": {_md(row.reason)}" if row.reason else "")
                + (f"; finding: {_md(row.finding)}" if row.finding else "")
                + " |"
            )
        for test in self.required_tests:
            lines += [
                "",
                f"- Required test for {_md(test.check)}: {_md(test.test)} ({_md(test.clause)})",
            ]
        return "\n".join(lines) + "\n"


def _md(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _sheet_xml(rows: Sequence[Sequence[str]], numeric: set[int]) -> str:
    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        "<sheetData>",
    ]
    for r, row in enumerate(rows, start=1):
        out.append(f'<row r="{r}">')
        for c, cell in enumerate(row):
            ref = f"{_column_letter(c)}{r}"
            if r > 1 and c in numeric and _is_finite_number(cell):
                out.append(f'<c r="{ref}"><v>{cell}</v></c>')
            else:
                out.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(cell)}</t></is></c>')
        out.append("</row>")
    out += ["</sheetData>", "</worksheet>"]
    return "".join(out)


def _is_finite_number(cell: str) -> bool:
    try:
        return isfinite(float(cell))
    except ValueError:
        return False


def _workbook(sheets: Sequence[tuple[str, Sequence[Sequence[str]], set[int]]]) -> bytes:
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg = "http://schemas.openxmlformats.org/package/2006/relationships"
    sheet_type = f"{rel}/worksheet"
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/'
                'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{pkg}"><Relationship Id="rId1" '
            f'Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets>'
            + "".join(
                f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                for i, (name, _, _) in enumerate(sheets, start=1)
            )
            + "</sheets></workbook>"
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{pkg}">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="{sheet_type}" Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + "</Relationships>"
        ),
    }
    for i, (_, rows, numeric) in enumerate(sheets, start=1):
        parts[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(rows, numeric)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, text.encode("utf-8"))
    return buffer.getvalue()


# --- Computing the margins ------------------------------------------------------------------


def _special(
    check: MarginCheck, factors: FactorSet, limit: MarginLimit
) -> tuple[tuple[AppliedFactor, ...], float]:
    known = {special.name: special for special in factors.special_factors}
    applied = tuple(
        AppliedFactor(name=known[name].name, value=known[name].value, clause=known[name].clause)
        for name in check.special_factors
        if limit in known[name].applies_to
    )
    if not applied:
        return (), 1.0
    values = [factor.value for factor in applied]
    product = prod(values) if factors.stacking is StackingRule.MULTIPLY else max(values)
    return applied, product


def _row(
    check: MarginCheck,
    factors: FactorSet,
    limit: MarginLimit,
    *,
    tie_tolerance: float,
    refused: str | None,
) -> MarginRow | None:
    common: dict[str, Any] = {
        "check": check.identity,
        "item": check.item,
        "subsystem": check.subsystem,
        "failure_mode": check.failure_mode,
        "method": check.method,
        "method_citation": check.method_citation,
        "limit": limit,
        "quantity": check.quantity,
        "unit": check.unit,
        "factor_set": factors.name,
        "factor_set_source": factors.source,
    }

    def not_evaluated(reason: str, **extra: object) -> MarginRow:
        return MarginRow(status=CheckStatus.NOT_EVALUATED, reason=reason, **common, **extra)  # type: ignore[arg-type]

    row = factors.row(check.material_class, check.approach)
    allowable = check.yield_allowable if limit is MarginLimit.YIELD else check.ultimate_allowable
    if limit is MarginLimit.YIELD:
        stated = row is not None and row.yield_factor is not None
        if allowable is None and not stated:
            return None  # the set asks no yield margin for this class, and none was declared
    if refused is not None:
        return not_evaluated(refused)
    if row is None:
        return not_evaluated(
            f"factor set '{factors.name}' states no factors for {check.material_class.value} "
            f"structure qualified by {check.approach.value.replace('_', ' ')}"
        )
    factor = row.yield_factor if limit is MarginLimit.YIELD else row.ultimate_factor
    if factor is None:
        return not_evaluated(
            f"factor set '{factors.name}' states no yield factor for "
            f"{check.material_class.value} structure ({row.clause}), so a yield margin has "
            "no factor to be computed under"
        )
    if allowable is None:
        return not_evaluated(
            f"the set requires a yield margin ({row.clause}) and the check declares no yield "
            "allowable"
        )
    sourced: dict[str, Any] = {
        "allowable": allowable.value,
        "basis": allowable.basis,
        "allowable_source": allowable.source,
    }
    rule = factors.basis_rule(check.load_path)
    if rule is not None and allowable.basis not in rule.accepted:
        required = " or ".join(f"{b.value}-basis" if len(b) == 1 else b.value
                               for b in rule.accepted)  # fmt: skip
        return not_evaluated(
            f"the {limit.value} allowable is on a {allowable.basis.value} basis, and "
            f"'{factors.name}' requires {required} for {check.load_path.value.replace('_', ' ')} "
            f"structure ({rule.clause})",
            **sourced,
        )
    special, special_product = _special(check, factors, limit)
    evaluated: list[tuple[float, LoadCase, float]] = []
    unevaluated: list[UnevaluatedCase] = []
    for case in check.cases:
        if case.applied < 0:
            unevaluated.append(
                UnevaluatedCase(
                    case=case.case,
                    reason=f"applied {case.applied:g} is negative; the allowable is a "
                    "magnitude, so declare the reversed sense as its own check",
                )
            )
            continue
        if case.level is LoadLevel.ULTIMATE:
            if limit is MarginLimit.YIELD:
                unevaluated.append(
                    UnevaluatedCase(
                        case=case.case,
                        reason="declared ultimate; a yield margin is computed on the limit "
                        "load, which an ultimate load does not state",
                    )
                )
                continue
            fs = 1.0
        else:
            fs = factor
        demand = case.applied * fs * special_product
        margin = inf if demand == 0 else allowable.value / demand - 1.0
        evaluated.append((margin, case, fs))
    if not evaluated:
        return not_evaluated(
            f"none of the {len(check.cases)} load cases could be evaluated",
            unevaluated=tuple(unevaluated),
            **sourced,
        )
    # Ties are kept in the order the cases were declared; the governing one is the first
    # case at the minimum, so the same input always names the same case.
    margin, governing, fs = min(evaluated, key=lambda entry: entry[0])
    body = check.free_body(governing.case)
    ties = tuple(
        case.case
        for value, case, _ in evaluated
        if case is not governing and value - margin <= tie_tolerance
    )
    return MarginRow(
        status=CheckStatus.PASS if margin >= 0 else CheckStatus.FAIL,
        margin=margin,
        governing_case=governing.case,
        applied=governing.applied,
        already_ultimate=governing.level is LoadLevel.ULTIMATE,
        factor_of_safety=fs,
        factor_clause=row.clause,
        special=special,
        special_product=special_product,
        cases_evaluated=len(evaluated),
        ties=ties,
        unevaluated=tuple(unevaluated),
        free_body=body,
        finding=body.finding() if body is not None else None,
        **sourced,
        **common,
    )


def margin_table(
    checks: Sequence[MarginCheck],
    factors: FactorSet,
    *,
    tie_tolerance: float = DEFAULT_TIE_TOLERANCE,
) -> MarginReport:
    """Every check's yield and ultimate margins under ``factors``, as the review table.

    Refuses, naming what to correct: a load case with no limit/ultimate tag, a special
    factor the set does not define, and two checks with one identity. Everything else that
    stops a margin — a missing factor row, a basis the set does not accept, an
    analysis-only exclusion, a case that cannot be evaluated — is a named row, not a
    refusal, so one bad check never hides the rest of the table.
    """
    checks = each_one(checks, MarginCheck, named="checks")
    if not isinstance(factors, FactorSet):
        raise _refusal(
            f"factors is a {type(factors).__name__}; a margin table is computed under a "
            "FactorSet — a bundled one from factor_set(name), or the user's own",
            subject="factors",
            source=_SET_SOURCE,
        )
    if not (isfinite(tie_tolerance) and tie_tolerance >= 0):
        raise _refusal(
            f"tie_tolerance is {tie_tolerance}; it is a finite, non-negative margin difference",
            subject="tie_tolerance",
            source="the margin difference within which two cases are reported as tied",
        )
    identities = [check.identity for check in checks]
    doubled = sorted({name for name in identities if identities.count(name) > 1})
    if doubled:
        raise _refusal(
            f"checks {doubled} are declared twice; each row of a margin table is one item's "
            "one failure mode",
            subject="checks",
            source=_CHECK_SOURCE,
        )
    known = {special.name for special in factors.special_factors}
    for check in checks:
        untagged = [case.case for case in check.cases if case.level is None]
        if untagged:
            raise _refusal(
                f"check '{check.identity}' has load cases {untagged} with no limit or "
                "ultimate tag; a margin report factors a limit load and never re-factors an "
                "ultimate one, so an untagged load cannot be placed in it",
                subject="level",
                source="the load source's statement of whether each case is limit or ultimate",
            )
        unknown = sorted(set(check.special_factors) - known)
        if unknown:
            raise _refusal(
                f"check '{check.identity}' names special factors {unknown} that "
                f"'{factors.name}' does not define; it defines {sorted(known) or 'none'}",
                subject="special_factors",
                source=_SET_SOURCE,
            )
    rows: list[MarginRow] = []
    tests: list[RequiredTest] = []
    for check in checks:
        refused = None
        exclusion = factors.exclusion(check.material_class)
        if exclusion is not None and check.approach is VerificationApproach.ANALYSIS_ONLY:
            refused = (
                f"refused: '{factors.name}' does not allow {check.material_class.value} "
                f"structure to be qualified by analysis alone ({exclusion.clause}); "
                f"it requires {exclusion.required_test}"
            )
            tests.append(
                RequiredTest(
                    check=check.identity,
                    item=check.item,
                    test=exclusion.required_test,
                    clause=exclusion.clause,
                    factor_set=factors.name,
                )
            )
        for limit in MarginLimit:
            row = _row(check, factors, limit, tie_tolerance=tie_tolerance, refused=refused)
            if row is not None:
                rows.append(row)
    rows.sort(
        key=lambda row: (
            _STATUS_ORDER[row.status] != 0,
            row.margin if row.margin is not None else 0.0,
            row.check,
            row.limit.value,
        )
    )
    return MarginReport(
        factor_set=factors.name,
        factor_set_source=factors.source,
        tie_tolerance=tie_tolerance,
        rows=tuple(rows),
        required_tests=tuple(tests),
    )


# --- The bundled, public-domain sets --------------------------------------------------------

# Every value below was read from the document itself, not recalled; docs/margin-of-safety.md
# records the edition, the URL it was read from, and the date. What a source does NOT state
# is left out rather than filled in: NASA-STD-5001B gives no numeric analysis-only factors
# for metallic structure (FSR 16 leaves them to the project) and does not cover fitting
# factors (§1.2.1), so neither appears in its sets.

_M = MaterialClass
_TEST = VerificationApproach.TEST
_ANALYSIS = VerificationApproach.ANALYSIS_ONLY

_5001B = "NASA-STD-5001B w/Change 3 (2022-10-24)"


def _nasa_5001b(name: str, *, metallic_yield: float, composite: float, test: str) -> FactorSet:
    t1 = f"{_5001B} Table 1"
    t2 = f"{_5001B} Table 2"
    required = f"a {test} structural test (NASA-STD-5001B Table 2)"
    only_metallic = f"{_5001B} §4.1.2.3: analysis-only verification is for metallic structures only"
    return FactorSet(
        name=name,
        source=_5001B,
        rows=(
            FactorRow(material_class=_M.METALLIC, approach=_TEST, yield_factor=metallic_yield,
                      ultimate_factor=1.4, clause=t1),
            FactorRow(material_class=_M.COMPOSITE, approach=_TEST, yield_factor=None,
                      ultimate_factor=composite, clause=f"{t2}, uniform material"),
            FactorRow(material_class=_M.COMPOSITE_DISCONTINUITY, approach=_TEST,
                      yield_factor=None, ultimate_factor=2.0,
                      clause=f"{t2}, discontinuity area (concentrated stresses)"),
            FactorRow(material_class=_M.BERYLLIUM, approach=_TEST, yield_factor=1.4,
                      ultimate_factor=1.6, clause=f"{_5001B} Table 7"),
            FactorRow(material_class=_M.GLASS_CERAMIC, approach=_TEST, yield_factor=None,
                      ultimate_factor=3.0, clause=f"{_5001B} Table 3"),
        ),
        exclusions=(
            AnalysisExclusion(material_class=_M.COMPOSITE, required_test=required,
                            clause=only_metallic),
            AnalysisExclusion(material_class=_M.COMPOSITE_DISCONTINUITY, required_test=required,
                            clause=only_metallic),
        ),
    )  # fmt: skip


_GEVS = "GSFC-STD-7000B (2021-04-28, administratively extended 2026-04-24)"


def _gevs(
    name: str,
    column: str,
    *,
    metallic: tuple[float, float],
    beryllium: tuple[float, float],
    composite: float,
    analysis_only: bool,
) -> FactorSet:
    t = f"{_GEVS} Table 2.2-3, {column}"
    alone = f"{_GEVS} §2.4.1.3: not qualified by analysis alone"
    required = "a strength qualification test at 1.25 x limit load (GSFC-STD-7000B Table 2.2-2)"
    rows = [
        FactorRow(
            material_class=_M.METALLIC,
            approach=_TEST,
            yield_factor=metallic[0],
            ultimate_factor=metallic[1],
            clause=t,
        ),
        FactorRow(
            material_class=_M.BERYLLIUM,
            approach=_TEST,
            yield_factor=beryllium[0],
            ultimate_factor=beryllium[1],
            clause=t,
        ),
        FactorRow(
            material_class=_M.COMPOSITE,
            approach=_TEST,
            yield_factor=None,
            ultimate_factor=composite,
            clause=t,
        ),
        FactorRow(
            material_class=_M.BONDED,
            approach=_TEST,
            yield_factor=None,
            ultimate_factor=composite,
            clause=f"{t}, bonded inserts/joints",
        ),
    ]
    if analysis_only:
        rows.append(
            FactorRow(
                material_class=_M.METALLIC,
                approach=_ANALYSIS,
                yield_factor=2.0,
                ultimate_factor=2.6,
                clause=f"{_GEVS} §2.4.1.3 and Table 2.2-3 note 3",
            ),
        )
    return FactorSet(
        name=name,
        source=_GEVS,
        rows=tuple(rows),
        exclusions=tuple(
            AnalysisExclusion(material_class=m, required_test=required, clause=alone)
            for m in (_M.COMPOSITE, _M.BERYLLIUM, _M.BONDED)
        ),
    )  # fmt: skip


_PART_25 = "14 CFR Part 25 (eCFR, current 2026-10-15)"


def _part_25() -> FactorSet:
    def casting(label: str, value: float, paragraph: str) -> SpecialFactor:
        return SpecialFactor(name=f"casting, {label}", value=value,
                             clause=f"14 CFR 25.621{paragraph}",
                             applies_to=(MarginLimit.ULTIMATE,))  # fmt: skip

    return FactorSet(
        name="14-cfr-25",
        source=_PART_25,
        rows=(
            FactorRow(material_class=None, approach=None, yield_factor=1.0, ultimate_factor=1.5,
                      clause="14 CFR 25.303 (ultimate); 25.305(a) (limit load without "
                      "detrimental permanent deformation)"),
        ),
        special_factors=(
            SpecialFactor(name="fitting", value=1.15, clause="14 CFR 25.625(a)",
                          applies_to=(MarginLimit.ULTIMATE,)),
            casting("critical, one static test", 1.5, "(c)(3)"),
            casting("critical, three static tests", 1.25, "(c)(2)"),
            casting("non-critical, radiographic inspection", 1.25, "(d)(2)"),
            casting("non-critical, penetrant inspection", 1.5, "(d)(3)"),
            casting("non-critical, visual inspection", 2.0, "(d)(4)"),
        ),
        stacking=StackingRule.LARGEST,
        stacking_clause="14 CFR 25.619: the highest pertinent special factor",
        basis_rules=(
            BasisRule(load_path=LoadPath.SINGLE, accepted=(AllowableBasis.A,),
                      clause="14 CFR 25.613(b)(1): 99% probability, 95% confidence"),
            BasisRule(load_path=LoadPath.REDUNDANT, accepted=(AllowableBasis.A, AllowableBasis.B),
                      clause="14 CFR 25.613(b)(2): 90% probability, 95% confidence"),
        ),
    )  # fmt: skip


_BUNDLED: tuple[FactorSet, ...] = (
    _nasa_5001b("nasa-std-5001b-prototype", metallic_yield=1.0, composite=1.4,
                test="prototype qualification (1.4 x limit)"),
    _nasa_5001b("nasa-std-5001b-protoflight", metallic_yield=1.25, composite=1.5,
                test="protoflight (1.2 x limit)"),
    _gevs("gsfc-std-7000b-static", "static and sine loads", metallic=(1.25, 1.4),
          beryllium=(1.4, 1.6), composite=1.5, analysis_only=True),
    _gevs("gsfc-std-7000b-random", "random and acoustic loads (3-sigma peak)",
          metallic=(1.6, 1.8), beryllium=(1.8, 2.0), composite=1.9, analysis_only=False),
    _part_25(),
)  # fmt: skip


def bundled_factor_sets() -> tuple[FactorSet, ...]:
    """The factor sets read from public-domain documents, each value with its clause."""
    return _BUNDLED


def factor_set(name: str) -> FactorSet:
    """The bundled factor set called ``name``, refusing an unknown name with the known ones."""
    for candidate in _BUNDLED:
        if candidate.name == name:
            return candidate
    raise _refusal(
        f"no bundled factor set is called '{name}'; the bundled sets are "
        f"{[candidate.name for candidate in _BUNDLED]}, and a company's own set is declared "
        "as a FactorSet with its document as the source",
        subject="name",
        source="the name of a bundled factor set",
    )
