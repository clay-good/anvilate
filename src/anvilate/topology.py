"""Constraint topology: count the constraints before trusting the stress.

A mount rarely fails on strength. It fails on over-constraint: two features both preventing
the same degree of freedom. The part assembles, the analysis passes, and then it distorts on
bolt-up, drifts with temperature and never returns to the same position twice. Where a
freedom is constrained more than once, the redundant constraints either do nothing or deform
the body, and **the loads become indeterminate** — which is why this belongs here: a stress
screened across an indeterminate load path is not conservative or unconservative, it is
unfounded, and reporting it as a clean number with a citation is what this library refuses.

This is counting, not solving. A :class:`Constraint` names the feature it acts at, its
:class:`ConstraintKind` and the body freedoms it removes, in a declared :class:`Frame`
whose axes are described in words. :func:`tally` counts each of the six freedoms:

- **free** — nothing removes it, and nobody declared it intended: named physically
  ("free to rotate about z (the bore axis)"), never as an index;
- **intended** — nothing removes it, and the body declares it on purpose, with the purpose;
- **exact** — exactly one constraint removes it;
- **over** — more than one does, and the redundancy is undeclared: every competing
  constraint is named, with the consequence stated;
- **declared redundant** — more than one does, and the redundancy is declared with a
  justification and the mechanism that makes it tolerable.

Declaring a redundancy does not silence what it does not resolve. Only a compliant
interface determines how the load divides; a controlled assembly sequence or a machining
operation at assembly removes fit-up strain, and the load division under service is still
indeterminate. :meth:`ConstraintTally.qualify` carries that indeterminacy onto any downstream
result, so a strength number on such a path never renders unqualified.

Constraints are never inferred from geometry. A body with none declared is not evaluated.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel, each_one
from .derivation import DerivationAbsence, Underived
from .scorecard import CheckStatus, Need, Scorecard, ScorecardEntry, ValueSource

_NEEDS_CONSTRAINTS = Need(
    declaration="constraint_topology.constraints",
    takes="each interface locating the body: the feature it acts at and the freedoms it removes",
    sources=(ValueSource.USER,),
)

if TYPE_CHECKING:
    from .dependency import ChainRun

__all__ = [
    "Freedom",
    "ConstraintKind",
    "RedundancyMechanism",
    "Frame",
    "IntentionalRedundancy",
    "IntendedFreedom",
    "Constraint",
    "FreedomState",
    "FreedomTally",
    "ConstraintTally",
    "tally",
    "EXACT_CONSTRAINT_SOURCE",
]

#: Where the counting rule comes from.
EXACT_CONSTRAINT_SOURCE = (
    "Blanding, Exact Constraint: Machine Design Using Kinematic Principles (1999)"
)


class Freedom(StrEnum):
    """One of a rigid body's six degrees of freedom, in a declared frame."""

    TX = "tx"
    TY = "ty"
    TZ = "tz"
    RX = "rx"
    RY = "ry"
    RZ = "rz"

    @property
    def axis(self) -> str:
        return self.value[1]

    @property
    def rotation(self) -> bool:
        return self.value[0] == "r"


class ConstraintKind(StrEnum):
    """The common interfaces, each removing a fixed number of freedoms."""

    PLANAR_FACE = "planar_face"
    PIN_IN_HOLE = "pin_in_hole"
    SLOT = "slot"
    BALL_IN_VEE = "ball_in_vee"
    BALL_IN_CONE = "ball_in_cone"
    FLAT_CONTACT = "flat_contact"
    BONDED = "bonded"
    FLEXURE_BLADE = "flexure_blade"


# How many freedoms each interface removes, and what it is. A total map: a kind added
# without a line here fails at import rather than counting as anything.
_REMOVES: dict[ConstraintKind, tuple[frozenset[int], str]] = {
    ConstraintKind.PLANAR_FACE: (
        frozenset({3}),
        "a flat face seated on a flat face: the normal translation and the two tilts",
    ),
    ConstraintKind.PIN_IN_HOLE: (
        frozenset({2, 4}),
        "a pin in a hole: the two translations across its axis, and with a long engagement "
        "the two tilts as well",
    ),
    ConstraintKind.SLOT: (
        frozenset({1, 2}),
        "a pin in a slot: the translation across the slot, and with a long engagement the "
        "tilt about the slot's length",
    ),
    ConstraintKind.BALL_IN_VEE: (frozenset({2}), "a ball in a vee groove: two contact points"),
    ConstraintKind.BALL_IN_CONE: (
        frozenset({3}),
        "a ball in a cone or trihedral seat: three contact points",
    ),
    ConstraintKind.FLAT_CONTACT: (frozenset({1}), "a ball on a flat: one contact point"),
    ConstraintKind.BONDED: (frozenset({6}), "a bonded or welded joint: every freedom"),
    ConstraintKind.FLEXURE_BLADE: (
        frozenset({3}),
        "a blade flexure: its two in-plane translations and the rotation about its normal",
    ),
}
if set(_REMOVES) != set(ConstraintKind):  # pragma: no cover - an import-time total map
    raise RuntimeError(f"constraint kinds with no count: {set(ConstraintKind) - set(_REMOVES)}")


class RedundancyMechanism(StrEnum):
    """What makes a declared redundancy tolerable."""

    COMPLIANT_INTERFACE = "compliant_interface"
    ASSEMBLY_SEQUENCE = "assembly_sequence"
    MACHINED_AT_ASSEMBLY = "machined_at_assembly"


# Whether a mechanism determines how the load divides among the redundant constraints. A
# compliant interface does: it sheds its share to the stiff one. The other two remove the
# strain locked in at fit-up, and under service load the division is still set by stiffness
# nobody declared — so the path stays indeterminate however well the declaration is argued.
_DETERMINES_LOAD_DIVISION: dict[RedundancyMechanism, bool] = {
    RedundancyMechanism.COMPLIANT_INTERFACE: True,
    RedundancyMechanism.ASSEMBLY_SEQUENCE: False,
    RedundancyMechanism.MACHINED_AT_ASSEMBLY: False,
}
if set(_DETERMINES_LOAD_DIVISION) != set(RedundancyMechanism):  # pragma: no cover
    raise RuntimeError("a redundancy mechanism with no load-division ruling")


class Frame(StatableModel):
    """The frame the six freedoms are counted in, each axis described in words.

    A tally is meaningless without one: "rotation about z" is actionable only when z is
    "the bore axis". The descriptions are what every rendering names a freedom against.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    x: Provenance
    y: Provenance
    z: Provenance

    def names(self, freedom: Freedom) -> str:
        motion = "rotation about" if freedom.rotation else "translation along"
        return f"{motion} {freedom.axis} ({getattr(self, freedom.axis)})"

    def __str__(self) -> str:
        return f"frame {self.name}: x {self.x}; y {self.y}; z {self.z}"


class IntentionalRedundancy(StatableModel):
    """A redundancy declared on purpose: why, and what makes it tolerable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    justification: Provenance
    mechanism: RedundancyMechanism

    @property
    def determines_load_division(self) -> bool:
        return _DETERMINES_LOAD_DIVISION[self.mechanism]

    def __str__(self) -> str:
        return f"{self.justification} ({self.mechanism.value.replace('_', ' ')})"


class IntendedFreedom(StatableModel):
    """A freedom the body keeps on purpose — an adjustment axis, a thermal slide."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    freedom: Freedom
    purpose: Provenance

    def __str__(self) -> str:
        return f"{self.freedom.value}: {self.purpose}"


class Constraint(StatableModel):
    """One interface: the feature it acts at, its kind, and the freedoms it removes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: Named
    kind: ConstraintKind
    removes: tuple[Freedom, ...] = Field(min_length=1)
    redundancy: IntentionalRedundancy | None = None

    @model_validator(mode="after")
    def _counts_what_its_kind_removes(self) -> Constraint:
        if len(set(self.removes)) != len(self.removes):
            raise ValueError(
                f"{self.name} names one freedom twice: {[f.value for f in self.removes]}"
            )
        allowed, description = _REMOVES[self.kind]
        if len(self.removes) not in allowed:
            counts = " or ".join(str(n) for n in sorted(allowed))
            raise ValueError(
                f"{self.name} declares {len(self.removes)} freedoms, and {description} removes "
                f"{counts}; a count that does not match the interface is a tally of nothing"
            )
        return self

    @property
    def name(self) -> str:
        return f"{self.kind.value.replace('_', ' ')} at {self.feature}"

    def __str__(self) -> str:
        removed = ", ".join(f.value for f in self.removes)
        declared = f"; declared redundant: {self.redundancy}" if self.redundancy else ""
        return f"{self.name}: removes {removed}{declared}"


class FreedomState(StrEnum):
    """Where one freedom stands once every declared constraint is counted against it."""

    FREE = "free"
    INTENDED = "intended"
    EXACT = "exact"
    OVER = "over"
    DECLARED_REDUNDANT = "declared_redundant"


class FreedomTally(StatableModel):
    """One freedom, and every constraint that removes it."""

    model_config = ConfigDict(frozen=True)

    freedom: Freedom
    by: tuple[Constraint, ...] = ()
    intended: IntendedFreedom | None = None

    @property
    def state(self) -> FreedomState:
        if not self.by:
            return FreedomState.FREE if self.intended is None else FreedomState.INTENDED
        if len(self.by) == 1:
            return FreedomState.EXACT
        declared = sum(1 for constraint in self.by if constraint.redundancy is not None)
        # n constraints on one freedom are n - 1 redundancies, and each must be declared.
        if declared >= len(self.by) - 1:
            return FreedomState.DECLARED_REDUNDANT
        return FreedomState.OVER

    @property
    def indeterminate(self) -> bool:
        """Whether the load along this freedom divides in a way the declaration cannot say."""
        if self.state is FreedomState.OVER:
            return True
        if self.state is FreedomState.DECLARED_REDUNDANT:
            return not all(
                constraint.redundancy.determines_load_division
                for constraint in self.by
                if constraint.redundancy is not None
            )
        return False

    def describe(self, frame: Frame) -> str:
        named = frame.names(self.freedom)
        state = self.state
        if state is FreedomState.FREE:
            return f"{named}: FREE — nothing removes it and nobody declared it intended"
        if state is FreedomState.INTENDED:
            return f"{named}: free by intent — {self.intended.purpose}"  # type: ignore[union-attr]
        competing = ", ".join(constraint.name for constraint in self.by)
        if state is FreedomState.EXACT:
            return f"{named}: exactly constrained by {competing}"
        if state is FreedomState.OVER:
            return (
                f"{named}: OVER-CONSTRAINED by {competing} — the redundant constraints either "
                "do nothing or deform the body, which of the two depends on manufacturing "
                "variation rather than on design intent, and the load division among them is "
                "indeterminate"
            )
        reasons = "; ".join(
            f"{constraint.name}: {constraint.redundancy}"
            for constraint in self.by
            if constraint.redundancy is not None
        )
        load = (
            "the load division is still indeterminate"
            if self.indeterminate
            else "the compliant interface sheds its share, so the load division is determined"
        )
        return f"{named}: redundant by declaration among {competing} ({reasons}); {load}"


class ConstraintTally(StatableModel):
    """The six freedoms of one body, counted in a declared frame."""

    model_config = ConfigDict(frozen=True)

    body: Named
    frame: Frame
    constraints: tuple[Constraint, ...]
    freedoms: tuple[FreedomTally, ...]

    @property
    def removed(self) -> int:
        """Freedoms removed, summed over the constraints — the arithmetic a reader checks."""
        return sum(len(constraint.removes) for constraint in self.constraints)

    def free(self) -> tuple[FreedomTally, ...]:
        return tuple(t for t in self.freedoms if t.state is FreedomState.FREE)

    def over(self) -> tuple[FreedomTally, ...]:
        return tuple(t for t in self.freedoms if t.state is FreedomState.OVER)

    @property
    def exactly_constrained(self) -> bool:
        """Every freedom accounted for exactly once, or declared, with none free or over."""
        return bool(self.constraints) and not self.free() and not self.over()

    @property
    def indeterminate(self) -> tuple[FreedomTally, ...]:
        return tuple(t for t in self.freedoms if t.indeterminate)

    def entry(self) -> ScorecardEntry:
        """The tally as one scorecard check: FAIL on an undeclared free or over freedom.

        A body that declares no constraints is ``not_evaluated``, naming it. Constraints are
        never inferred from geometry, so it has not been counted — which is different from
        a body that counted to six free freedoms.
        """
        if not self.constraints:
            return ScorecardEntry(
                name=f"constraint topology: {self.body}",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"{self.body} declares no constraints, and they are never inferred from "
                    "geometry; declare each interface, the feature it acts at and the "
                    "freedoms it removes"
                ),
                needs=(_NEEDS_CONSTRAINTS,),
            )
        contributions = ", ".join(
            f"{constraint.name} {len(constraint.removes)}" for constraint in self.constraints
        )
        arithmetic = f"{contributions} = {self.removed} removed, in {self.frame.name}"
        findings = [t.describe(self.frame) for t in (*self.free(), *self.over())]
        status = CheckStatus.FAIL if findings else CheckStatus.PASS
        if findings:
            detail = f"{'; '.join(findings)} [{arithmetic}]"
        else:
            accounted = sum(1 for t in self.freedoms if t.state is not FreedomState.INTENDED)
            detail = (
                f"all six freedoms accounted for, {accounted} of them constrained [{arithmetic}]"
            )
            if self.indeterminate:
                detail += (
                    "; the load path is indeterminate along "
                    f"{', '.join(t.freedom.value for t in self.indeterminate)}"
                )
        return ScorecardEntry(
            name=f"constraint topology: {self.body}",
            status=status,
            detail=detail,
            reference=EXACT_CONSTRAINT_SOURCE,
            underived=Underived(
                kind=DerivationAbsence.LOOKUP,
                reason=(
                    "a count of the freedoms each declared constraint removes, per freedom; "
                    "there is no arithmetic between two numbers to substitute"
                ),
            ),
        )

    def qualify(self, entry: ScorecardEntry) -> ScorecardEntry:
        """``entry`` carrying the indeterminacy, when this body's load path is indeterminate.

        A strength, deflection or alignment number computed across an over-constrained path
        rests on a load division the declaration does not determine. It is never rendered
        unqualified: the cause is appended to the entry's own detail, which every surface
        prints. A check that did not run, or a path that is determinate, is returned as it was.
        """
        cause = self.indeterminate
        if not cause or not entry.evaluated:
            return entry
        by = sorted({constraint.name for t in cause for constraint in t.by})
        freedoms = ", ".join(t.freedom.value for t in cause)
        note = (
            f" — on an indeterminate load path: {self.body} is over-constrained along "
            f"{freedoms} by {', '.join(by)}, so the load division this rests on is not "
            "determined by the declared geometry"
        )
        return entry.model_copy(update={"detail": f"{entry.detail}{note}"})

    def qualify_downstream(self, run: ChainRun, load_path: str) -> Scorecard:
        """``run``'s card with every check resting on ``load_path`` carrying the indeterminacy.

        Which checks rest on it is read off the run's dependency graph, not guessed: the
        ``load_path`` check itself and every check that consumes it, directly or through
        others (:meth:`~anvilate.dependency.DependencyGraph.downstream_of`). A check the graph
        does not connect to the path is left as it ran, because its number does not depend on
        how this body divides its load.
        """
        run.result(load_path)  # refuses a check the run does not carry, by name
        affected = {load_path, *run.graph.downstream_of(load_path)}
        return Scorecard(
            entries=tuple(
                self.qualify(entry) if entry.name in affected else entry
                for entry in run.card().entries
            )
        )

    def __str__(self) -> str:
        if not self.constraints:
            return f"constraint topology of {self.body}: no constraints declared, not counted"
        lines = [
            f"constraint topology of {self.body}, in {self.frame}",
            f"  {self.removed} freedoms removed by {len(self.constraints)} constraints",
        ]
        lines += [f"  {t.describe(self.frame)}" for t in self.freedoms]
        return "\n".join(lines)


def tally(
    body: str,
    frame: Frame,
    constraints: Sequence[Constraint],
    *,
    intended: Sequence[IntendedFreedom] = (),
) -> ConstraintTally:
    """Count each of ``body``'s six freedoms against its declared constraints.

    A body that declares none still comes back as a tally, whose :meth:`~ConstraintTally.entry`
    is ``not_evaluated`` naming it: constraints are never inferred from geometry.

    An ``intended`` freedom that a constraint removes anyway is refused: the declaration says
    it is free, the constraints say it is not, and one of the two is wrong.
    """
    constraints = each_one(constraints, Constraint, named="constraints")
    intended = each_one(intended, IntendedFreedom, named="intended")
    by_freedom = {freedom: [c for c in constraints if freedom in c.removes] for freedom in Freedom}
    kept: dict[Freedom, IntendedFreedom] = {}
    for declared in intended:
        if declared.freedom in kept:
            raise ValueError(f"{body} declares {declared.freedom.value} intended twice")
        if by_freedom[declared.freedom]:
            removers = ", ".join(c.name for c in by_freedom[declared.freedom])
            raise ValueError(
                f"{body} declares {frame.names(declared.freedom)} intended free, and {removers} "
                "removes it; the declaration and the constraints disagree"
            )
        kept[declared.freedom] = declared
    return ConstraintTally(
        body=body,
        frame=frame,
        constraints=constraints,
        freedoms=tuple(
            FreedomTally(freedom=freedom, by=tuple(by_freedom[freedom]), intended=kept.get(freedom))
            for freedom in Freedom
        ),
    )
