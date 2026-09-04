"""Verification planning: the physical test each analytical check implies.

A screening check says a lug will hold. A proof test proves it. Anvilate stopped at the
calculation and left the user to invent the verification that the calculation implies —
even though the standards it cites usually prescribe that test outright: a below-the-hook
lifter gets a proof load, a pressure vessel gets a hydrostatic test, a toleranced feature
gets a dimensional inspection.

The systems-engineering canon has the vocabulary — Analysis, Inspection, Demonstration,
Test — and the requirements-verification matrix that carries it. This inverts that matrix.
Instead of starting from a requirement and choosing a method, it starts from a *check that
already ran* and names the physical counterpart it implies, with the acceptance criterion
derived from the check's own governing quantity.

Three rules keep a plan from reading as evidence:

1. **A planned test is not a verified one.** A plan with no recorded outcomes reports
   ``NOT_EVALUATED``, never a pass. This is the same silent-green rule the scorecard
   keeps, applied one layer out: intending to test something is not testing it.
2. **A check that did not run gets no test, and is named.** You cannot verify an
   analysis that was never performed; the honest output is an unresolved item saying so,
   not a quietly shorter plan.
3. **Coverage is reported, including the checks that map to nothing.** Most checks are
   verified by analysis alone and that is a legitimate method — but the count has to be
   visible, because "12 checks, 2 tests" and "12 checks, 12 tests" are different
   deliverables and a matrix that lists only the tests looks identical either way.

Out of scope: executing tests, acquiring lab data, and any claim of qualification or
certification. This plans; it does not qualify.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from ._models import Named, Provenance, RevalidatedModel
from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .units import Quantity

# The types are named Verification* rather than Test*: `TestOutcome` at module scope is
# collected by pytest as a test class, and a warning in every run is a warning nobody
# reads. The domain word is "verification" anyway — a test is one method of four.
__all__ = [
    "VerificationMethod",
    "VerificationArchetype",
    "VerificationItem",
    "VerificationOutcome",
    "VerificationPlan",
    "DEFAULT_ARCHETYPES",
    "plan_verification",
    "record_outcome",
]

# ASME B30.20 caps the proof load for a below-the-hook lifting device at 125% of the
# rated load, and OSHA 29 CFR 1926.251(a)(4) requires custom-designed lifting accessories
# to be proof tested to that same 125% before use. The two halves of the rule are the
# same statement inverted: B30.20 also holds that the rated load may not exceed 80% of
# the load sustained in the test, and 1/1.25 is exactly 0.80. The suite asserts that
# identity, because a transcribed proof factor that breaks it is transcribed wrong.
_PROOF_LOAD_FACTOR = 1.25
_RATED_LOAD_FRACTION_OF_TEST = 0.80

# ASME VIII Div 1 UG-99(b): the hydrostatic test pressure is 1.3 x MAWP times the lowest
# ratio of the test-temperature to design-temperature allowable stress. UG-100 allows a
# pneumatic test at 1.1 x MAWP on the same ratio, permitted only where the vessel cannot
# safely be filled with liquid — a different test, not a cheaper one.
_HYDROSTATIC_FACTOR = 1.3
_PNEUMATIC_FACTOR = 1.1

# The 10:1 test accuracy ratio: the instrument's uncertainty should be within a tenth of
# the tolerance it is judging. This is long-standing measurement practice, not a clause
# in any standard Anvilate cites, so it is labelled a practice default and says so rather
# than borrowing authority it does not have.
_TEST_ACCURACY_RATIO = 0.10


class VerificationMethod(StrEnum):
    """How a requirement is shown to be met (the systems-engineering four).

    :attr:`ANALYSIS` is the method Anvilate's own checks *are* — and naming it as a
    method rather than an absence is the point: a check verified by analysis alone is
    verified by a legitimate method, it is simply not verified by a physical one.
    """

    ANALYSIS = "analysis"
    INSPECTION = "inspection"
    DEMONSTRATION = "demonstration"
    TEST = "test"


class VerificationArchetype(RevalidatedModel):
    """A class of physical verification, and what a check must supply to plan one.

    ``clause_token`` is matched against a scorecard entry's ``reference`` — the clause
    the check already cites — so the mapping runs off the citation rather than off a
    check's display name, which a caller chooses freely.

    ``required_parameters`` are the quantities the acceptance criterion needs and the
    check itself does not carry: a proof test needs the rated load, a hydrostatic test
    needs the MAWP. When one is missing the item is *unresolved*, not omitted.

    ``practice_default`` marks an archetype whose criterion is established practice
    rather than a clause in a cited standard. It is reported alongside the criterion, so
    a reader can tell which numbers carry a standard's authority and which do not.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    method: VerificationMethod
    title: str
    citation: Provenance
    required_parameters: tuple[str, ...] = ()
    practice_default: bool = False


class VerificationOutcome(RevalidatedModel):
    """A recorded result: what was measured, when, by whom, and on what instrument.

    All four are required. An outcome without an instrument identity or a performer is
    not traceable, and an untraceable record is closer to a claim than to evidence — the
    plan would rather have no outcome than an anonymous one.
    """

    model_config = ConfigDict(frozen=True)

    passed: bool
    measured: str
    performed_on: date
    performed_by: str
    instrument: str

    @model_validator(mode="after")
    def _well_formed(self) -> VerificationOutcome:
        for value, name in (
            (self.measured, "measured"),
            (self.performed_by, "performed_by"),
            (self.instrument, "instrument"),
        ):
            if not value.strip():
                raise ValueError(f"a recorded outcome needs a {name}")
        return self


class VerificationItem(RevalidatedModel):
    """One planned physical verification: what to do, to what, and what counts as a pass.

    ``driving_checks`` names the analytical checks this test stands behind, which is the
    link the matrix exists to make: a test with no driving check is a test nobody asked
    for, and a check with no test is verified by analysis alone.

    ``outcome`` is ``None`` until a result is recorded, and :attr:`status` is
    ``NOT_EVALUATED`` while it is. A planned test never renders as a passed one.
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    archetype: VerificationArchetype
    driving_checks: tuple[str, ...]
    acceptance: str
    required_accuracy: str | None = None
    outcome: VerificationOutcome | None = None

    # Serialised, because the dump of this item is what a bundle's `verification` block
    # is made of and the state was the one thing it did not carry.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        """``NOT_EVALUATED`` until an outcome is recorded; then that outcome's verdict."""
        if self.outcome is None:
            return CheckStatus.NOT_EVALUATED
        return CheckStatus.PASS if self.outcome.passed else CheckStatus.FAIL

    def __str__(self) -> str:
        state = "planned" if self.outcome is None else self.status.value
        # ``driving_checks`` is what this class's own docstring calls the link the matrix
        # exists to make, so it is rendered: an item standing behind one check and an item
        # standing behind three are different rows of the matrix.
        behind = ", ".join(self.driving_checks) or "no driving check"
        # And the accuracy the *instrument* has to meet, which the rendering dropped. It is
        # the difference between an inspection that means something and one that does not —
        # a 0.05 mm tolerance measured with a 0.05 mm instrument verifies nothing — and the
        # plan is a document somebody performs from.
        accuracy = f" ({self.required_accuracy})" if self.required_accuracy else ""
        return f"{self.name} [{state}]: {self.acceptance}{accuracy} — for {behind}"


DEFAULT_ARCHETYPES: tuple[VerificationArchetype, ...] = (
    VerificationArchetype(
        key="proof-load",
        method=VerificationMethod.TEST,
        title="Proof load test",
        citation="ASME B30.20 (proof test) with OSHA 29 CFR 1926.251(a)(4)",
        required_parameters=("rated_load",),
    ),
    VerificationArchetype(
        key="hydrostatic",
        method=VerificationMethod.TEST,
        title="Hydrostatic pressure test",
        citation="ASME VIII Div 1 UG-99(b)",
        required_parameters=("mawp",),
    ),
    VerificationArchetype(
        key="dimensional",
        method=VerificationMethod.INSPECTION,
        title="Dimensional inspection",
        citation="10:1 test accuracy ratio (measurement practice, not a cited clause)",
        required_parameters=("tolerance",),
        practice_default=True,
    ),
)

# Which clause a check cites decides which physical test it implies. Keyed on the
# citation rather than the check's name because the name is the caller's to choose and
# the citation is not.
_CLAUSE_ROUTES: tuple[tuple[str, str], ...] = (
    ("ASME BTH-1", "proof-load"),
    ("ASME VIII", "hydrostatic"),
    ("ISO 286", "dimensional"),
    ("ISO 2768", "dimensional"),
)


class VerificationPlan(BaseModel):
    """A scorecard's physical verification plan, with its coverage stated.

    ``analysis_only`` names the checks that map to no physical test **and passed** —
    verified by analysis, which is a method, and counted so the matrix cannot imply
    otherwise. ``failing_checks`` names the ones that failed: a failing check is not
    verified by analysis, it is the thing the analysis found, and no verification plan
    over a failing design rolls up green.
    ``unresolved`` names the checks that *should* have produced a test item and could
    not: a check that did not run, or one whose archetype needed a quantity nobody
    supplied. Both are listed rather than dropped.
    """

    model_config = ConfigDict(frozen=True)

    items: tuple[VerificationItem, ...]
    analysis_only: tuple[str, ...]
    unresolved: tuple[tuple[str, str], ...]
    failing_checks: tuple[str, ...] = ()

    # The sharpest case of a conclusion a plain property drops. This class's own
    # docstring says a plan is not evidence, and the serialised plan carried its items
    # -- every one of them with `outcome: null` -- and nothing that said so.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        """The plan's roll-up. ``NOT_EVALUATED`` until every planned test has a result.

        A plan is not evidence. This never reports PASS on intent — only on a full set of
        recorded outcomes, and a single failed outcome fails the plan.
        """
        # A recorded failure outranks anything unevaluated, which is the precedence
        # `Scorecard` already uses (FAIL blocks harder than NOT_EVALUATED). Checking
        # `unresolved` first inverted it: one unrelated check that never ran downgraded a
        # proof test that physically cracked the device to "not evaluated", which reads as
        # an incomplete plan rather than a broken lifter.
        if self.failing_checks or any(item.status is CheckStatus.FAIL for item in self.items):
            return CheckStatus.FAIL
        if self.unresolved:
            return CheckStatus.NOT_EVALUATED
        if not self.items:
            return CheckStatus.NOT_EVALUATED
        if any(item.status is CheckStatus.NOT_EVALUATED for item in self.items):
            return CheckStatus.NOT_EVALUATED
        return CheckStatus.PASS

    @property
    def verified(self) -> tuple[VerificationItem, ...]:
        """The items with a recorded outcome — the only ones that are evidence."""
        return tuple(item for item in self.items if item.outcome is not None)

    def matrix(self) -> str:
        """The verification matrix as text: every check, its method, and its state."""
        lines = ["check                          method        state"]
        for item in self.items:
            for check in item.driving_checks:
                state = "planned" if item.outcome is None else item.status.value
                lines.append(f"{check:<30} {item.archetype.method.value:<13} {state}")
        for check in self.analysis_only:
            lines.append(f"{check:<30} {'analysis':<13} complete")
        for check in self.failing_checks:
            lines.append(f"{check:<30} {'analysis':<13} FAILED — the design does not pass")
        for check, reason in self.unresolved:
            lines.append(f"{check:<30} {'—':<13} unresolved: {reason}")
        return "\n".join(lines)

    def summary(self) -> str:
        """One line for a report pane. Never says 'verified' on an unexecuted plan."""
        covered = sum(len(item.driving_checks) for item in self.items)
        failing = f", {len(self.failing_checks)} failing" if self.failing_checks else ""
        return (
            f"{covered} checks with a physical test ({len(self.verified)} of "
            f"{len(self.items)} performed), {len(self.analysis_only)} by analysis alone, "
            f"{len(self.unresolved)} unresolved{failing} — plan status {self.status.value}"
        )


def _acceptance(
    archetype: VerificationArchetype, parameters: Mapping[str, Quantity]
) -> tuple[str, str | None]:
    """The acceptance criterion and required instrument accuracy for one archetype."""
    if archetype.key == "proof-load":
        rated = parameters["rated_load"]
        load = Quantity(magnitude=_PROOF_LOAD_FACTOR * rated.to("kN").magnitude, unit="kN")
        return (
            f"apply {load.magnitude:.4g} kN — {_PROOF_LOAD_FACTOR:.2f} x the "
            f"{rated.to('kN').magnitude:.4g} kN rated load — and accept no permanent "
            f"deformation, crack, or loss of function. The rated load may not exceed "
            f"{_RATED_LOAD_FRACTION_OF_TEST:.0%} of the load sustained",
            "load measurement within 1% of the proof load",
        )
    if archetype.key == "hydrostatic":
        mawp = parameters["mawp"]
        ratio = parameters.get("stress_ratio")
        factor = _HYDROSTATIC_FACTOR * (ratio.magnitude if ratio is not None else 1.0)
        pressure = Quantity(magnitude=factor * mawp.to("MPa").magnitude, unit="MPa")
        note = "" if ratio is not None else " (no test/design stress ratio supplied; taken as 1.0)"
        return (
            f"hold {pressure.magnitude:.4g} MPa — {_HYDROSTATIC_FACTOR} x the "
            f"{mawp.to('MPa').magnitude:.4g} MPa MAWP on the test/design allowable-stress "
            f"ratio{note} — with no leakage and no visible distortion. A pneumatic test "
            f"per UG-100 runs at {_PNEUMATIC_FACTOR} x instead, and is permitted only "
            f"where the vessel cannot safely be filled with liquid",
            "pressure gauge within 1% of the test pressure",
        )
    tolerance = parameters["tolerance"]
    accuracy = _TEST_ACCURACY_RATIO * tolerance.to("mm").magnitude
    return (
        f"measure the feature and accept within the {tolerance.to('mm').magnitude:.4g} mm "
        f"tolerance",
        f"instrument uncertainty within {accuracy:.4g} mm — a tenth of the tolerance "
        f"(practice default, not a cited clause)",
    )


def plan_verification(
    scorecard: Scorecard,
    *,
    parameters: Mapping[str, Quantity] | None = None,
    archetypes: Sequence[VerificationArchetype] = DEFAULT_ARCHETYPES,
) -> VerificationPlan:
    """Emit the physical verification plan a scorecard implies.

    Each entry is routed by the clause it cites — not by its name — to a
    :class:`VerificationArchetype`, and checks sharing an archetype share one test item, because
    one proof load verifies every member check on the lifter it loads.

    ``parameters`` supplies the quantities an acceptance criterion needs and the check
    does not carry (``rated_load``, ``mawp``, optionally ``stress_ratio``, ``tolerance``).
    A missing one makes the item **unresolved** rather than omitted: a proof test whose
    rated load nobody supplied is not a plan, and a shorter plan reads as a smaller job.

    A ``NOT_EVALUATED`` check is unresolved too. There is no physical counterpart to an
    analysis that did not run — the test would be verifying nothing — and the honest
    output says which check and why.
    """
    parameters = dict(parameters or {})
    by_archetype: dict[str, list[str]] = {}
    analysis_only: list[str] = []
    unresolved: list[tuple[str, str]] = []
    lookup = {archetype.key: archetype for archetype in archetypes}

    failing: list[str] = []
    for entry in scorecard.entries:
        if entry.status is CheckStatus.NOT_EVALUATED:
            unresolved.append(
                (entry.name, "the check did not run, so there is nothing to verify against")
            )
            continue
        if entry.status is CheckStatus.FAIL:
            # A failing check is not "verified by analysis" — the analysis is what says it
            # does not pass. Routing it to `analysis_only` printed it in the matrix with
            # the state `complete`, and let a plan whose every test was performed roll up
            # green over a scorecard that failed.
            failing.append(entry.name)
            continue
        key = _route(entry, lookup)
        if key is None:
            analysis_only.append(entry.name)
            continue
        missing = [p for p in lookup[key].required_parameters if p not in parameters]
        if missing:
            unresolved.append(
                (
                    entry.name,
                    f"{lookup[key].title} needs {', '.join(missing)}, which was not supplied",
                )
            )
            continue
        by_archetype.setdefault(key, []).append(entry.name)

    items = tuple(
        VerificationItem(
            name=lookup[key].title,
            archetype=lookup[key],
            driving_checks=tuple(checks),
            acceptance=acceptance,
            required_accuracy=accuracy,
        )
        for key, checks in by_archetype.items()
        for acceptance, accuracy in (_acceptance(lookup[key], parameters),)
    )
    return VerificationPlan(
        items=items,
        analysis_only=tuple(analysis_only),
        unresolved=tuple(unresolved),
        failing_checks=tuple(failing),
    )


def _route(entry: ScorecardEntry, lookup: Mapping[str, VerificationArchetype]) -> str | None:
    """The archetype key an entry's citation routes to, or ``None`` for analysis-only."""
    reference = entry.reference or ""
    for token, key in _CLAUSE_ROUTES:
        if token in reference and key in lookup:
            return key
    return None


def record_outcome(
    plan: VerificationPlan, *, name: str, outcome: VerificationOutcome
) -> VerificationPlan:
    """Attach a recorded outcome to the named item, returning a new plan.

    Recording is the only way an item becomes evidence, and it is deliberately explicit:
    nothing in this module infers a result from a passing analysis, because that is the
    substitution the whole change exists to prevent.
    """
    if not any(item.name == name for item in plan.items):
        raise KeyError(f"{name!r} is not an item of this plan; have {[i.name for i in plan.items]}")
    return plan.model_copy(
        update={
            "items": tuple(
                item.model_copy(update={"outcome": outcome}) if item.name == name else item
                for item in plan.items
            )
        }
    )
