"""Model credibility: the test read back against the prediction, on a public scale.

Anvilate says what it predicted, and :mod:`anvilate.verification` says what physical test
would confirm it and lets a person record that test's result. Nothing then read the
result. A proof test that held 8% less than the lug check predicted sat beside a check
that still read ``PASS``, and no card, dossier or benchmark learned that the prediction
had been unconservative. That is the one loop the project's own doctrine demands and did
not close.

Three things live here, and none of them changes a verdict:

1. A :class:`Correlation` — the predicted value, the measured value, their ratio and
   difference in the quantity's own units, judged against an :class:`AcceptanceBand` the
   document declares *with its source*. Unconservative beyond the band is a finding on
   the card; conservative beyond it is a note for the margin ledger, because a check that
   is stronger than the test is information, not a defect. With no declared band the
   comparison is ``NOT_EVALUATED`` and says which band it needs: a corridor nobody
   declared is the weak metric ASME V&V 10's own teaching warns about.
2. An :class:`EscapedDefectCandidate` — an unconservative correlation on a check that
   *passed*, carrying the bundle digest and the test record into the post-mortem process
   ``benchmarking`` already requires. It stays visible until a person dispositions it, and
   dispositioning it never removes the finding from the card.
3. A :class:`CredibilityFactorSet` — the eight NASA-STD-7009A credibility factors, each
   scored 0 to 4 with the evidence the score rests on named beside it. A score is proposed
   only from evidence this library holds, by the published mapping in
   :data:`EVIDENCE_CEILINGS`; a factor with no evidence is 0; a person may override any
   score with a stated reason, and the override, the reason and the person are all kept.

The factor names are read from the standard, not recalled. **Revision A renamed them**:
the 2008 original's "code verification / solution verification / conceptual validation /
referent validation" became the Rev A factors ``Verification`` and ``Validation``, and
Rev A adds ``M&S History`` and ``M&S Process/Product Management`` as a third, supporting
category. Anything written against the 2008 names is a revision behind.

Two rules the standard states and this module obeys:

- The levels are **ordinal only** and "should not be arithmetically manipulated"
  (NASA-STD-7009A E.4). There is deliberately no mean, total or overall score here, and a
  gate holds that absence: an average of eight ordinal scales is a number with no meaning
  that a reader will nonetheless compare.
- Level 0 means *insufficient evidence*, not *bad*. It is what this library scores every
  factor it holds nothing for.

Out of scope, by the change that added this: statistical validation metrics beyond ratio
and difference; any automatic re-tuning of a check from test data (a correlation is
information for a person and a regression for CI, never a calibration); and any statement
that a result is "validated" in a regulatory sense.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from enum import StrEnum
from math import isclose, isfinite
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field, computed_field, model_validator

from ._models import Named, Provenance, StatableModel, each_one
from .refusal import RefusalError, Remedy
from .units import Quantity

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from .scorecard import Scorecard
    from .verification import VerificationPlan

__all__ = [
    "NASA_7009A_CITATION",
    "VV10_CITATION",
    "PredictionSense",
    "AcceptanceBand",
    "CorrelationVerdict",
    "Correlation",
    "DispositionKind",
    "Disposition",
    "EscapedDefectCandidate",
    "CredibilityFactor",
    "FactorCategory",
    "FACTOR_LABELS",
    "EVIDENCE_CEILINGS",
    "HeldEvidence",
    "FactorScore",
    "CredibilityFactorSet",
    "propose_factor_set",
    "ValidationRange",
    "DomainKind",
    "DomainLabel",
    "ValidationDomain",
    "label_use",
    "label_checks",
    "correlate",
    "annotate",
    "candidates",
    "UnattributedConservatism",
    "unattributed_conservatisms",
]

#: The standard the factor set is stated on. Approved for public release, distribution
#: unlimited (NTRS 20160011121), so its factor names and its 0–4 scale are cited verbatim
#: and nothing is reproduced beyond them.
NASA_7009A_CITATION = "NASA-STD-7009A, Appendix E (credibility assessment, levels 0-4)"

#: Where the words come from. ASME V&V 10 is copyrighted; only its vocabulary is used —
#: verification (the model is solved correctly), validation (it is the right model for the
#: use, shown against a referent), validation metric, validation domain.
VV10_CITATION = "ASME V&V 10 vocabulary (verification, validation, validation domain)"

_BAND_SOURCE = "the acceptance band the test plan or the governing standard declares"
_CORRELATION_SOURCE = "the recorded test and the check that predicted it"

#: The widest band this module will accept. A ±100% band accepts a measurement of twice or
#: none of the prediction, which is not an acceptance criterion; past it the number is
#: decoration and the comparison would read as evaluated when nothing was evaluated.
_WIDEST_BAND = 1.0


def _refusal(message: str, *, subject: str, source: str) -> RefusalError:
    return RefusalError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class PredictionSense(StrEnum):
    """Which direction of disagreement is the unsafe one.

    The same 8% gap means opposite things on the two kinds of prediction a screen makes. A
    predicted *capacity* measured low is the design holding less than the calculation
    said; a predicted *response* — a stress, a deflection, a temperature — measured high is
    the design working harder than the calculation said. Both are the unconservative case,
    and which one applies is the check's to state, never this module's to guess.
    """

    CAPACITY = "capacity"
    RESPONSE = "response"


class AcceptanceBand(StatableModel):
    """How far predicted and measured may differ and still be called agreement.

    ``fraction`` is the half-width as a fraction of the prediction: 0.05 is ±5%. ``source``
    is required and may not be blank, because a corridor nobody can attribute is the
    arbitrary one ASME V&V 10's teaching material warns against — the reader has to be able
    to disagree with the band rather than with the verdict it produced.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    fraction: float
    source: Provenance

    @model_validator(mode="after")
    def _is_a_band(self) -> AcceptanceBand:
        if not isfinite(self.fraction) or self.fraction <= 0.0:
            raise _refusal(
                f"an acceptance band needs a positive half-width; got {self.fraction}. A "
                f"band of zero accepts only an exact match, which no instrument produces, "
                f"and every correlation under it would read as disagreement",
                subject="fraction",
                source=_BAND_SOURCE,
            )
        if self.fraction > _WIDEST_BAND:
            raise _refusal(
                f"an acceptance band of ±{self.fraction:.0%} accepts a measurement of twice "
                f"the prediction or none of it, which is not an acceptance criterion; "
                f"±{_WIDEST_BAND:.0%} is the widest this will state as one",
                subject="fraction",
                source=_BAND_SOURCE,
            )
        # A blank source needs no branch here: `Provenance` refuses an uncited value on
        # the way in, which is the same rule one layer down — a band nobody can attribute
        # is the arbitrary corridor this comparison exists to avoid.
        return self

    def __str__(self) -> str:
        return f"±{self.fraction:.3g} ({self.source})"


class CorrelationVerdict(StrEnum):
    """What the comparison said. Never what the check said."""

    AGREES = "agrees"
    UNCONSERVATIVE = "unconservative"
    CONSERVATIVE = "conservative"
    NOT_EVALUATED = "not_evaluated"


class Correlation(StatableModel):
    """One prediction compared with one measurement of the same quantity.

    ``predicted`` is what the driving check computed; ``measured`` is what the recorded
    verification outcome measured. They are converted into the prediction's own unit before
    anything is compared, so a preload predicted in kN and measured in lbf correlates.

    The test record travels with the comparison — the date, the performer and the
    instrument — because the escaped-defect process downstream needs the record, not a
    reference to one, and because a correlation whose instrument nobody can name is a claim.

    :attr:`verdict` is ``NOT_EVALUATED`` with no band: both values and the ratio are still
    reported, and :meth:`__str__` names the band it needs.
    """

    model_config = ConfigDict(frozen=True)

    check: Named
    item: Named
    predicted: Quantity
    measured: Quantity
    sense: PredictionSense
    performed_on: date
    performed_by: str
    instrument: str
    band: AcceptanceBand | None = None
    instrument_uncertainty: Quantity | None = None
    check_passed: bool = True
    citation: Provenance = VV10_CITATION

    @model_validator(mode="after")
    def _comparable(self) -> Correlation:
        for quantity, name in (
            (self.predicted, "predicted"),
            (self.measured, "measured"),
            (self.instrument_uncertainty, "instrument_uncertainty"),
        ):
            if quantity is not None and not isfinite(quantity.magnitude):
                raise _refusal(
                    f"a correlation cannot hold a non-finite {name} ({quantity.magnitude}); "
                    f"a ratio computed from it would render as a number",
                    subject=name,
                    source=_CORRELATION_SOURCE,
                )
        if self.predicted.pint.dimensionality != self.measured.pint.dimensionality:
            raise _refusal(
                f"a correlation needs two quantities of the same dimension; got "
                f"{self.predicted.dimensionality} predicted against "
                f"{self.measured.dimensionality} measured. A capacity correlated against a "
                f"temperature would render a ratio that means nothing",
                subject="predicted and measured",
                source=_CORRELATION_SOURCE,
            )
        if self.predicted.magnitude == 0.0:
            raise _refusal(
                "a correlation needs a non-zero predicted value; the ratio against a "
                "predicted zero is not a measure of agreement",
                subject="predicted",
                source=_CORRELATION_SOURCE,
            )
        if self.instrument_uncertainty is not None and (
            self.instrument_uncertainty.pint.dimensionality != self.measured.pint.dimensionality
        ):
            raise _refusal(
                f"the instrument's uncertainty is a "
                f"{self.instrument_uncertainty.dimensionality} against a "
                f"{self.measured.dimensionality} measurement; an uncertainty in another "
                f"dimension cannot bound this measurement",
                subject="instrument_uncertainty",
                source="the instrument's calibration record",
            )
        for value, name in ((self.performed_by, "performed_by"), (self.instrument, "instrument")):
            if not value.strip():
                raise _refusal(
                    f"a correlation needs the {name} of the test it reads; an untraceable "
                    f"record is closer to a claim than to evidence",
                    subject=name,
                    source="the test record the outcome was taken from",
                )
        return self

    @property
    def _measured_in_predicted_units(self) -> float:
        return self.measured.to(self.predicted.unit).magnitude

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ratio(self) -> float:
        """Measured over predicted, both in the prediction's unit. 1.0 is exact agreement."""
        return self._measured_in_predicted_units / self.predicted.magnitude

    @computed_field  # type: ignore[prop-decorator]
    @property
    def difference(self) -> Quantity:
        """Measured minus predicted, in the prediction's own unit."""
        return Quantity(
            magnitude=self._measured_in_predicted_units - self.predicted.magnitude,
            unit=self.predicted.unit,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verdict(self) -> CorrelationVerdict:
        """Agreement, or which way it fell outside the declared band."""
        if self.band is None:
            return CorrelationVerdict.NOT_EVALUATED
        gap = abs(self.ratio - 1.0)
        # `isclose` as well as `<=`, because the edge of the band is inside it and binary
        # floating point puts it outside: 95/100 leaves a gap of 0.050000000000000044,
        # and a measurement exactly on a ±5% limit would have read as disagreement.
        if gap <= self.band.fraction or isclose(gap, self.band.fraction, rel_tol=1e-9):
            return CorrelationVerdict.AGREES
        low = self.ratio < 1.0
        if self.sense is PredictionSense.CAPACITY:
            return CorrelationVerdict.UNCONSERVATIVE if low else CorrelationVerdict.CONSERVATIVE
        return CorrelationVerdict.CONSERVATIVE if low else CorrelationVerdict.UNCONSERVATIVE

    @property
    def is_escaped_defect_candidate(self) -> bool:
        """An unconservative correlation on a check that passed — the candidate's condition."""
        return self.check_passed and self.verdict is CorrelationVerdict.UNCONSERVATIVE

    def __str__(self) -> str:
        predicted = f"{self.predicted.magnitude:.4g} {self.predicted.unit}"
        measured = f"{self._measured_in_predicted_units:.4g} {self.predicted.unit}"
        if self.band is None:
            return (
                f"{self.check}: predicted {predicted}, measured {measured} "
                f"(ratio {self.ratio:.3f}) — not evaluated, no acceptance band declared"
            )
        return (
            f"{self.check}: predicted {predicted}, measured {measured} "
            f"(ratio {self.ratio:.3f}, band {self.band}) — {self.verdict.value}"
        )


class DispositionKind(StrEnum):
    """The three ways a person can close an escaped-defect candidate."""

    ESCAPED_DEFECT = "escaped_defect"
    TEST_OR_INSTRUMENT_ISSUE = "test_or_instrument_issue"
    CONSERVATIVE_TEST = "conservative_test"


class Disposition(StatableModel):
    """A person's judgement on a candidate, with the reason and the person recorded."""

    model_config = ConfigDict(frozen=True)

    kind: DispositionKind
    reason: str
    by: str
    on: date

    @model_validator(mode="after")
    def _attributed(self) -> Disposition:
        for value, name in ((self.reason, "reason"), (self.by, "by")):
            if not value.strip():
                raise _refusal(
                    f"dispositioning a candidate needs a {name}; an unattributed "
                    f"disposition closes the finding and tells the next reader nothing",
                    subject=name,
                    source="the person who dispositioned the candidate",
                )
        return self

    def __str__(self) -> str:
        return f"{self.kind.value} — {self.reason} ({self.by}, {self.on.isoformat()})"


class EscapedDefectCandidate(StatableModel):
    """A passing check whose test came in unconservative, filed for the post-mortem.

    ``benchmarking`` defines an escaped defect as a green-checked part that failed
    physically for a reason the validation claims to model, and requires a post-mortem and
    a permanent regression. The record that detects one is this. It carries the bundle
    digest so the post-mortem can reach the exact evidence the verdict was written from.

    Dispositioning sets :attr:`disposition` and nothing else: the finding stays on the card,
    because the card states what the test found and that did not change.
    """

    model_config = ConfigDict(frozen=True)

    bundle_digest: str
    correlation: Correlation
    disposition: Disposition | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _is_a_candidate(self) -> EscapedDefectCandidate:
        if not self.correlation.is_escaped_defect_candidate:
            raise _refusal(
                f"'{self.correlation.check}' is not an escaped-defect candidate: its "
                f"correlation is {self.correlation.verdict.value} on a check that "
                f"{'passed' if self.correlation.check_passed else 'did not pass'}. A "
                f"candidate is an unconservative correlation on a check that passed, and "
                f"filing anything else dilutes the count the release reports",
                subject="correlation",
                source="an unconservative correlation on a passing check",
            )
        if not self.bundle_digest.strip():
            raise _refusal(
                "an escaped-defect candidate needs the digest of the bundle the verdict was "
                "written from; without it the post-mortem cannot reach the evidence",
                subject="bundle_digest",
                source="the evidence bundle's digest",
            )
        return self

    @property
    def check(self) -> str:
        """The check the candidate was filed against."""
        return self.correlation.check

    @property
    def undispositioned(self) -> bool:
        """Whether a person still has to judge it. The count a release reports."""
        return self.disposition is None

    def __str__(self) -> str:
        state = "undispositioned" if self.undispositioned else str(self.disposition)
        return f"escaped-defect candidate [{state}]: {self.correlation}"


class UnattributedConservatism(StatableModel):
    """A test the design beat: a conservative correlation, read as a margin nobody elected.

    The margin ledger exists to state the conservatism a design carries and where each
    factor came from. A check whose test came in 12% stronger than the prediction is
    carrying a thirteenth factor the ledger has no entry for — the check itself is
    conservative by an amount one measurement now puts a number on.

    It is a note and not a finding, and not a ledger entry either: nothing was *applied*,
    so there is no factor to multiply into a stack. The engineer reads it beside the
    factors they did elect and decides whether it is one.
    """

    model_config = ConfigDict(frozen=True)

    correlation: Correlation

    @model_validator(mode="after")
    def _is_conservative(self) -> UnattributedConservatism:
        if self.correlation.verdict is not CorrelationVerdict.CONSERVATIVE:
            raise _refusal(
                f"'{self.correlation.check}' correlated "
                f"{self.correlation.verdict.value}, not conservative; noting it to the "
                f"ledger as an unelected conservatism would state the opposite of what the "
                f"test found",
                subject="correlation",
                source="a conservative correlation beyond the declared band",
            )
        return self

    @property
    def quantity(self) -> str:
        """The check the conservatism sits on, as the ledger names a quantity."""
        return self.correlation.check

    @property
    def implied_factor(self) -> float:
        """How much stronger than predicted the test came in, as a factor above 1.0.

        For a predicted capacity that is measured over predicted; for a predicted response
        measured low it is the reciprocal, so both read as "x1.12 of conservatism" rather
        than one of them reading as 0.89.
        """
        if self.correlation.sense is PredictionSense.CAPACITY:
            return self.correlation.ratio
        return 1.0 / self.correlation.ratio

    def __str__(self) -> str:
        c = self.correlation
        return (
            f"possible unattributed conservatism on {self.quantity}: the test came in "
            f"x{self.implied_factor:.4g} beyond the prediction "
            f"({c.measured.magnitude:.4g} {c.measured.unit} measured against "
            f"{c.predicted.magnitude:.4g} {c.predicted.unit} predicted, band {c.band}), "
            f"and no ledger entry accounts for it"
        )


def unattributed_conservatisms(
    correlations: Sequence[Correlation],
) -> tuple[UnattributedConservatism, ...]:
    """The notes the margin ledger takes from a set of correlations.

    Only the conservative ones. An unconservative correlation is a finding and an
    escaped-defect candidate, and putting it here too would read as spare margin.
    """
    correlations = each_one(correlations, Correlation, named="correlations")
    return tuple(
        UnattributedConservatism(correlation=correlation)
        for correlation in correlations
        if correlation.verdict is CorrelationVerdict.CONSERVATIVE
    )


class FactorCategory(StrEnum):
    """The three groups NASA-STD-7009A figure 2 puts the eight factors in."""

    DEVELOPMENT = "ms_development"
    USE = "ms_use"
    SUPPORTING = "supporting_evidence"

    @property
    def label(self) -> str:
        """The category's name as the standard writes it, for a rendering."""
        return _CATEGORY_LABELS[self]


#: A TOTAL map, so a rendering never falls back to a de-underscored enum value: the
#: standard's three category names are "M&S Development", "M&S Use (Operations)" and
#: "Supporting Evidence", and "ms use" is none of them.
_CATEGORY_LABELS: dict[FactorCategory, str] = {
    FactorCategory.DEVELOPMENT: "M&S Development",
    FactorCategory.USE: "M&S Use (Operations)",
    FactorCategory.SUPPORTING: "Supporting Evidence",
}


class CredibilityFactor(StrEnum):
    """The eight factors of NASA-STD-7009A Appendix E, Revision A's names.

    Rev A's set is not the 2008 original's. ``VERIFICATION`` subsumes what the original
    split into code and solution verification, ``VALIDATION`` what it split into conceptual
    and referent validation, and the last two factors are new in Rev A.
    """

    DATA_PEDIGREE = "data_pedigree"
    VERIFICATION = "verification"
    VALIDATION = "validation"
    INPUT_PEDIGREE = "input_pedigree"
    UNCERTAINTY_CHARACTERIZATION = "uncertainty_characterization"
    RESULTS_ROBUSTNESS = "results_robustness"
    MS_HISTORY = "ms_history"
    MS_MANAGEMENT = "ms_management"


#: The one place a factor's rendered name and its category are written, as a TOTAL map. A
#: gate holds every member of the enum to a row here, so a ninth factor cannot be added
#: without being named and categorised.
FACTOR_LABELS: dict[CredibilityFactor, tuple[str, FactorCategory]] = {
    CredibilityFactor.DATA_PEDIGREE: ("Data Pedigree", FactorCategory.DEVELOPMENT),
    CredibilityFactor.VERIFICATION: ("Verification", FactorCategory.DEVELOPMENT),
    CredibilityFactor.VALIDATION: ("Validation", FactorCategory.DEVELOPMENT),
    CredibilityFactor.INPUT_PEDIGREE: ("Input Pedigree", FactorCategory.USE),
    CredibilityFactor.UNCERTAINTY_CHARACTERIZATION: (
        "Uncertainty Characterization",
        FactorCategory.USE,
    ),
    CredibilityFactor.RESULTS_ROBUSTNESS: ("Results Robustness", FactorCategory.USE),
    CredibilityFactor.MS_HISTORY: ("M&S History", FactorCategory.SUPPORTING),
    CredibilityFactor.MS_MANAGEMENT: (
        "M&S Process/Product Management",
        FactorCategory.SUPPORTING,
    ),
}

#: The published evidence-to-level mapping: the highest level this library will *propose*
#: for a factor, and the one sentence saying why that is the ceiling. It is published so a
#: reviewer can disagree with the mapping rather than with a number, and it is a ceiling in
#: both directions — Anvilate never proposes above it, and a person who believes a higher
#: level is earned has to say so as an override, under their name.
#:
#: Every ceiling here is 2 or below, and that is the honest reading of the standard's own
#: level definitions: level 3 needs formal verification practices over the end-to-end model
#: and validation points that significantly span the domain of operation, and level 4 needs
#: comparison against the real-world system across its full operating range. A screening
#: library anchored to worked examples and correlated against the handful of tests a user
#: happens to record has neither, whatever its test count.
EVIDENCE_CEILINGS: dict[CredibilityFactor, tuple[int, str]] = {
    CredibilityFactor.DATA_PEDIGREE: (
        2,
        "bundled standards and materials records are traceable to formal documentation "
        "with their edition and clause, which is level 2; nothing here is traced to "
        "measurements on a real-world system",
    ),
    CredibilityFactor.VERIFICATION: (
        2,
        "worked-example anchors and the derivation-evaluation gates are documented "
        "verification practices over the checks, which is level 2; there is no formal "
        "end-to-end verification argument",
    ),
    CredibilityFactor.VALIDATION: (
        2,
        "a recorded test is a comparison against a representative system, which is "
        "level 2; level 3 needs validation points that significantly span the domain of "
        "operation and no screening run establishes that",
    ),
    CredibilityFactor.INPUT_PEDIGREE: (
        2,
        "a value origin on every input is formal traceability with estimated "
        "uncertainties, which is level 2",
    ),
    CredibilityFactor.UNCERTAINTY_CHARACTERIZATION: (
        2,
        "a declared distribution set propagated by Monte Carlo identifies and quantifies "
        "the sources it was given, which is level 2; it cannot claim all known sources",
    ),
    CredibilityFactor.RESULTS_ROBUSTNESS: (
        2,
        "the first-order sensitivity ranking quantifies a few parameters, which is level 2",
    ),
    CredibilityFactor.MS_HISTORY: (
        2,
        "a declared change history and a use within previous norms is level 2; this "
        "library holds neither unless the caller states them",
    ),
    CredibilityFactor.MS_MANAGEMENT: (
        2,
        "a declared, documented and approved process is level 2; this library holds it "
        "only when the caller states it",
    ),
}

_NO_EVIDENCE = "no evidence held"


class HeldEvidence(StatableModel):
    """What the caller holds that bears on the eight factors.

    Each field is the evidence Anvilate can actually point at, stated by the caller rather
    than sniffed: a screening run does not know whether its inputs were traced, and a
    library that guessed would be proposing scores from its own optimism.
    """

    model_config = ConfigDict(frozen=True)

    #: Bundled standard or material records carrying an edition and a clause.
    cited_data_records: int = 0
    #: Checks anchored to a published worked example.
    worked_example_anchors: int = 0
    #: Correlations that agreed with a recorded test.
    agreeing_correlations: int = 0
    #: Inputs carrying a stated origin (user-stated, database-resolved, confirmed, …).
    inputs_with_an_origin: int = 0
    #: Inputs in total. A share below one is not full traceability.
    inputs_total: int = 0
    #: Whether a declared distribution set was propagated to the result.
    uncertainty_propagated: bool = False
    #: Parameters whose sensitivity is quantified.
    quantified_sensitivities: int = 0
    #: The model's change history, when the caller states one.
    change_history: str | None = None
    #: The managed process the work ran under, when the caller states one.
    managed_process: str | None = None

    @model_validator(mode="after")
    def _counts_are_counts(self) -> HeldEvidence:
        counts = {
            "cited_data_records": self.cited_data_records,
            "worked_example_anchors": self.worked_example_anchors,
            "agreeing_correlations": self.agreeing_correlations,
            "inputs_with_an_origin": self.inputs_with_an_origin,
            "inputs_total": self.inputs_total,
            "quantified_sensitivities": self.quantified_sensitivities,
        }
        for name, value in counts.items():
            if value < 0:
                raise _refusal(
                    f"{name} counts evidence and cannot be negative; got {value}",
                    subject=name,
                    source="a count of the evidence actually held",
                )
        if self.inputs_with_an_origin > self.inputs_total:
            raise _refusal(
                f"{self.inputs_with_an_origin} inputs with an origin out of "
                f"{self.inputs_total} inputs is more traced than there are; the share this "
                f"scores input pedigree from would exceed one",
                subject="inputs_with_an_origin",
                source="the count of inputs the run actually read",
            )
        return self


class FactorScore(StatableModel):
    """One factor's level, the evidence it rests on, and any person's override.

    ``level`` is the effective score. When a person overrode the proposal, ``proposed_level``
    keeps what this library said, and ``override_reason`` and ``override_by`` say who
    disagreed and why — the dossier renders all four, because an override nobody can see is
    indistinguishable from a proposal.
    """

    model_config = ConfigDict(frozen=True)

    factor: CredibilityFactor
    level: int
    evidence: str
    proposed_level: int | None = Field(default=None, exclude_if=lambda value: value is None)
    override_reason: str | None = Field(default=None, exclude_if=lambda value: value is None)
    override_by: str | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _on_the_scale(self) -> FactorScore:
        for level, name in ((self.level, "level"), (self.proposed_level, "proposed_level")):
            if level is not None and not 0 <= level <= 4:
                raise _refusal(
                    f"{name} {level} is off the NASA-STD-7009A scale, which runs 0 to 4 with "
                    f"0 meaning insufficient evidence",
                    subject=name,
                    source=NASA_7009A_CITATION,
                )
        if not self.evidence.strip():
            raise _refusal(
                f"the {self.factor.value} score needs the evidence it rests on named; a "
                f"level with no evidence beside it is the bare number the standard's whole "
                f"assessment exists to replace",
                subject="evidence",
                source="the evidence the score was read from",
            )
        overridden = self.proposed_level is not None
        if overridden and not (self.override_reason or "").strip():
            raise _refusal(
                f"the {self.factor.value} score overrides a proposed {self.proposed_level} "
                f"and states no reason; an unexplained override is a number nobody can "
                f"argue with",
                subject="override_reason",
                source="the reviewer's reason for disagreeing with the proposal",
            )
        if overridden and not (self.override_by or "").strip():
            raise _refusal(
                f"the {self.factor.value} score overrides a proposed {self.proposed_level} "
                f"and names nobody; an override is a person's judgement and is attributed",
                subject="override_by",
                source="the reviewer who made the override",
            )
        if not overridden and (self.override_reason or self.override_by):
            raise _refusal(
                f"the {self.factor.value} score carries an override reason or person and no "
                f"proposed level to override; the dossier would show a disagreement with "
                f"nothing on the other side of it",
                subject="proposed_level",
                source="the level this library proposed before the override",
            )
        return self

    @property
    def label(self) -> str:
        """The factor's name as the standard writes it."""
        return FACTOR_LABELS[self.factor][0]

    @property
    def category(self) -> FactorCategory:
        """Which of the standard's three categories the factor sits in."""
        return FACTOR_LABELS[self.factor][1]

    def overridden(self) -> bool:
        """Whether a person moved this score off the proposal."""
        return self.proposed_level is not None

    def override(self, *, level: int, reason: str, by: str) -> FactorScore:
        """A person's score in place of this one, keeping the proposal visible."""
        return FactorScore(
            factor=self.factor,
            level=level,
            evidence=self.evidence,
            proposed_level=self.level if self.proposed_level is None else self.proposed_level,
            override_reason=reason,
            override_by=by,
        )

    def __str__(self) -> str:
        line = f"{self.label}: {self.level} — {self.evidence}"
        if self.overridden():
            line += (
                f" [overridden from {self.proposed_level} by {self.override_by}: "
                f"{self.override_reason}]"
            )
        return line


class CredibilityFactorSet(StatableModel):
    """The eight factors of a result or a bundle, each with its evidence.

    There is no overall score here and there will not be one. NASA-STD-7009A E.4 states
    that the assessments are ordinal only and "should not be arithmetically manipulated";
    a mean of eight ordinal scales is a number with no meaning that every reader would
    nonetheless compare against another one.
    """

    model_config = ConfigDict(frozen=True)

    subject: Named
    scores: tuple[FactorScore, ...]
    citation: Provenance = NASA_7009A_CITATION

    @model_validator(mode="after")
    def _all_eight_once(self) -> CredibilityFactorSet:
        seen = [score.factor for score in self.scores]
        if len(set(seen)) != len(seen):
            duplicated = sorted({f.value for f in seen if seen.count(f) > 1})
            raise _refusal(
                f"a factor set scores {', '.join(duplicated)} more than once; two levels for "
                f"one factor is two answers to one question",
                subject="scores",
                source=NASA_7009A_CITATION,
            )
        missing = [f.value for f in CredibilityFactor if f not in set(seen)]
        if missing:
            raise _refusal(
                f"a factor set states {len(seen)} of the eight NASA-STD-7009A factors and "
                f"omits {', '.join(missing)}; a partial set reads as a better assessment "
                f"than it is, because the factor with no evidence is the one left out",
                subject="scores",
                source=NASA_7009A_CITATION,
            )
        return self

    def level(self, factor: CredibilityFactor) -> int:
        """The effective level of one factor."""
        return next(score.level for score in self.scores if score.factor is factor)

    def score(self, factor: CredibilityFactor) -> FactorScore:
        """One factor's whole score, with its evidence and any override."""
        return next(s for s in self.scores if s.factor is factor)

    def with_override(
        self, factor: CredibilityFactor, *, level: int, reason: str, by: str
    ) -> CredibilityFactorSet:
        """This set with one factor overridden by a person, the proposal kept."""
        return CredibilityFactorSet(
            subject=self.subject,
            scores=tuple(
                s.override(level=level, reason=reason, by=by) if s.factor is factor else s
                for s in self.scores
            ),
            citation=self.citation,
        )

    @property
    def insufficient(self) -> tuple[CredibilityFactor, ...]:
        """The factors scored 0 — insufficient evidence, which is not the same as bad."""
        return tuple(s.factor for s in self.scores if s.level == 0)

    def table(self) -> str:
        """The set as text, by category, with the standard cited and no total."""
        lines = [f"credibility of {self.subject} — {self.citation}"]
        for category in FactorCategory:
            lines.append(f"  {category.label}")
            for score in self.scores:
                if score.category is category:
                    lines.append(f"    {score}")
        lines.append(
            "  the levels are ordinal; the standard states they are not to be averaged or "
            "totalled, and this is an assessment of evidence, not a certification"
        )
        return "\n".join(lines)

    def __str__(self) -> str:
        zeros = len(self.insufficient)
        return (
            f"credibility of {self.subject}: eight factors on the NASA-STD-7009A scale, "
            f"{zeros} with insufficient evidence"
        )


def _ceiling(factor: CredibilityFactor, level: int) -> int:
    return min(level, EVIDENCE_CEILINGS[factor][0])


def propose_factor_set(subject: str, evidence: HeldEvidence) -> CredibilityFactorSet:
    """Score the eight factors from held evidence only, naming it on every score.

    A factor this library holds nothing for is 0 — insufficient evidence, the standard's
    own meaning — and the evidence line says what is missing rather than leaving a bare
    zero. No proposal exceeds the published ceiling in :data:`EVIDENCE_CEILINGS`.
    """
    scores: list[FactorScore] = []

    if evidence.cited_data_records > 0:
        scores.append(
            FactorScore(
                factor=CredibilityFactor.DATA_PEDIGREE,
                level=_ceiling(CredibilityFactor.DATA_PEDIGREE, 2),
                evidence=(
                    f"{evidence.cited_data_records} bundled "
                    f"{'record' if evidence.cited_data_records == 1 else 'records'} "
                    f"traceable to formal documentation by edition and clause"
                ),
            )
        )
    else:
        scores.append(
            FactorScore(
                factor=CredibilityFactor.DATA_PEDIGREE,
                level=0,
                evidence=f"{_NO_EVIDENCE}: no cited data record was resolved for this result",
            )
        )

    if evidence.worked_example_anchors > 0:
        scores.append(
            FactorScore(
                factor=CredibilityFactor.VERIFICATION,
                level=_ceiling(CredibilityFactor.VERIFICATION, 2),
                evidence=(
                    f"{evidence.worked_example_anchors} "
                    f"{'check' if evidence.worked_example_anchors == 1 else 'checks'} "
                    f"anchored to a published worked example, with the derivation "
                    f"evaluated in CI"
                ),
            )
        )
    else:
        scores.append(
            FactorScore(
                factor=CredibilityFactor.VERIFICATION,
                level=0,
                evidence=f"{_NO_EVIDENCE}: no check here is anchored to a worked example",
            )
        )

    if evidence.agreeing_correlations > 0:
        scores.append(
            FactorScore(
                factor=CredibilityFactor.VALIDATION,
                level=_ceiling(CredibilityFactor.VALIDATION, 2),
                evidence=(
                    f"{evidence.agreeing_correlations} recorded "
                    f"{'test' if evidence.agreeing_correlations == 1 else 'tests'} agreed "
                    f"with the prediction within the declared band, on a representative "
                    f"system"
                ),
            )
        )
    else:
        scores.append(
            FactorScore(
                factor=CredibilityFactor.VALIDATION,
                level=0,
                evidence=(
                    f"{_NO_EVIDENCE}: no recorded test has been correlated with these predictions"
                ),
            )
        )

    if evidence.inputs_total > 0 and evidence.inputs_with_an_origin == evidence.inputs_total:
        level, why = (
            2,
            (
                f"all {evidence.inputs_total} inputs carry a stated origin, which is formal "
                f"traceability"
            ),
        )
    elif evidence.inputs_with_an_origin > 0:
        level, why = (
            1,
            (
                f"{evidence.inputs_with_an_origin} of {evidence.inputs_total} inputs carry a "
                f"stated origin; the rest are untraced"
            ),
        )
    else:
        level, why = 0, f"{_NO_EVIDENCE}: no input carries a stated origin"
    scores.append(
        FactorScore(
            factor=CredibilityFactor.INPUT_PEDIGREE,
            level=_ceiling(CredibilityFactor.INPUT_PEDIGREE, level),
            evidence=why,
        )
    )

    scores.append(
        FactorScore(
            factor=CredibilityFactor.UNCERTAINTY_CHARACTERIZATION,
            level=_ceiling(CredibilityFactor.UNCERTAINTY_CHARACTERIZATION, 2)
            if evidence.uncertainty_propagated
            else 0,
            evidence=(
                "a declared distribution set was propagated to the result by Monte Carlo"
                if evidence.uncertainty_propagated
                else f"{_NO_EVIDENCE}: no distribution was declared, so no band was computed"
            ),
        )
    )

    if evidence.quantified_sensitivities > 0:
        robustness = FactorScore(
            factor=CredibilityFactor.RESULTS_ROBUSTNESS,
            level=_ceiling(CredibilityFactor.RESULTS_ROBUSTNESS, 2),
            evidence=(
                f"the sensitivity of {evidence.quantified_sensitivities} "
                f"{'parameter' if evidence.quantified_sensitivities == 1 else 'parameters'} "
                f"is quantified by the first-order variance ranking"
            ),
        )
    else:
        robustness = FactorScore(
            factor=CredibilityFactor.RESULTS_ROBUSTNESS,
            level=0,
            evidence=f"{_NO_EVIDENCE}: no sensitivity of this result is quantified",
        )
    scores.append(robustness)

    for factor, stated, missing in (
        (
            CredibilityFactor.MS_HISTORY,
            evidence.change_history,
            "no change or use history is stated for these checks",
        ),
        (
            CredibilityFactor.MS_MANAGEMENT,
            evidence.managed_process,
            "no managed process is stated for this work",
        ),
    ):
        text = (stated or "").strip()
        scores.append(
            FactorScore(
                factor=factor,
                level=_ceiling(factor, 2) if text else 0,
                evidence=text or f"{_NO_EVIDENCE}: {missing}",
            )
        )

    return CredibilityFactorSet(subject=subject, scores=tuple(scores))


class ValidationRange(StatableModel):
    """One parameter's range over which a check has been anchored or correlated.

    ``source`` is the worked example or the recorded test the range came from, so a reader
    can see that a check "validated from 10 to 40 mm" was validated against two points and
    not a continuum.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    parameter: Named
    low: Quantity
    high: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _is_a_range(self) -> ValidationRange:
        # A non-finite bound needs no branch: this model states requirements, so the
        # base class refuses an infinite or undefined magnitude before this runs.
        if self.low.pint.dimensionality != self.high.pint.dimensionality:
            raise _refusal(
                f"a validation range needs two bounds of the same dimension; got "
                f"{self.low.dimensionality} and {self.high.dimensionality}",
                subject="low and high",
                source="the anchored or correlated points the range spans",
            )
        if self.high.to(self.low.unit).magnitude < self.low.magnitude:
            raise _refusal(
                f"a validation range runs low to high; got {self.low} above {self.high}",
                subject="low and high",
                source="the anchored or correlated points the range spans",
            )
        # As above: `Provenance` refuses a blank source, so a range nobody can attribute
        # never reaches here. A range without its anchor would claim a validation that
        # may never have happened.
        return self

    def contains(self, value: Quantity) -> bool:
        """Whether a value falls inside this range, converted into the range's unit."""
        if value.pint.dimensionality != self.low.pint.dimensionality:
            return False
        here = value.to(self.low.unit).magnitude
        return self.low.magnitude <= here <= self.high.to(self.low.unit).magnitude

    def distance(self, value: Quantity) -> float:
        """How far outside this range a value is, as a fraction of the range's own width.

        Zero inside. A width of zero — a single validated point — measures the gap against
        the point's own magnitude instead, so one anchored point still ranks against another.
        """
        if value.pint.dimensionality != self.low.pint.dimensionality:
            return float("inf")
        here = value.to(self.low.unit).magnitude
        low, high = self.low.magnitude, self.high.to(self.low.unit).magnitude
        gap = max(low - here, here - high, 0.0)
        if gap == 0.0:
            return 0.0
        scale = high - low
        if scale == 0.0:
            scale = abs(low) or 1.0
        return gap / scale

    def __str__(self) -> str:
        return (
            f"{self.parameter} {self.low.magnitude:.4g} to "
            f"{self.high.to(self.low.unit).magnitude:.4g} {self.low.unit} ({self.source})"
        )


class DomainKind(StrEnum):
    """Whether a use sits inside the domain a check was compared in, or outside it."""

    INTERPOLATIVE = "interpolative"
    EXTRAPOLATIVE = "extrapolative"


class DomainLabel(StatableModel):
    """Where a use sits relative to the validation domain. Never a verdict.

    ASME V&V 10's distinction: a prediction inside the domain the model was compared in is
    interpolative, one outside it is extrapolative. The label is the information — an
    extrapolative check may well be right, and the reader is entitled to know that nothing
    has ever been measured out there.
    """

    model_config = ConfigDict(frozen=True)

    kind: DomainKind
    parameter: Named
    value: Quantity
    nearest: ValidationRange
    citation: Provenance = VV10_CITATION

    def __str__(self) -> str:
        return (
            f"{self.kind.value}: {self.parameter} at {self.value.magnitude:.4g} "
            f"{self.value.unit}, {'inside' if self.kind is DomainKind.INTERPOLATIVE else 'outside'}"
            f" the recorded range {self.nearest}"
        )


def label_use(
    inputs: Mapping[str, Quantity], ranges: Sequence[ValidationRange]
) -> DomainLabel | None:
    """Label one check's use against the ranges it has been anchored and correlated over.

    ``None`` when no recorded range names any of the inputs *in its dimension*: a check
    that has never been compared anywhere has no validation domain, and labelling it
    interpolative would claim one.

    A parameter inside any one of its recorded ranges is interpolative on that parameter —
    two ranges are two tests, not two requirements. Extrapolative wins over interpolative
    across parameters, and the parameter named is the one furthest outside its *nearest*
    range, measured as a fraction of that range's own width, so the reader is pointed at
    the input doing the extrapolating rather than at whichever came first.
    """
    ranges = each_one(ranges, ValidationRange, named="ranges")
    outside: list[tuple[float, str, Quantity, ValidationRange]] = []
    inside: tuple[str, Quantity, ValidationRange] | None = None
    for name, value in inputs.items():
        comparable = [
            recorded
            for recorded in ranges
            if recorded.parameter == name
            and recorded.low.pint.dimensionality == value.pint.dimensionality
        ]
        if not comparable:
            continue
        if any(recorded.contains(value) for recorded in comparable):
            if inside is None:
                here = next(r for r in comparable if r.contains(value))
                inside = (name, value, here)
            continue
        nearest = min(comparable, key=lambda recorded: recorded.distance(value))
        outside.append((nearest.distance(value), name, value, nearest))
    if outside:
        _, name, value, nearest = max(outside, key=lambda item: item[0])
        return DomainLabel(
            kind=DomainKind.EXTRAPOLATIVE, parameter=name, value=value, nearest=nearest
        )
    if inside is not None:
        name, value, nearest = inside
        return DomainLabel(
            kind=DomainKind.INTERPOLATIVE, parameter=name, value=value, nearest=nearest
        )
    return None


class ValidationDomain(StatableModel):
    """Everywhere one check has actually been compared, recorded against the check.

    This is the record the extrapolative label is read from: not "the lug check is valid
    from 10 to 40 mm" as a claim, but the anchored worked examples and the recorded tests
    that happen to lie in that interval, each naming its own source. A check with no
    domain recorded gets no label, which is the honest output — it has never been
    compared anywhere.
    """

    model_config = ConfigDict(frozen=True)

    check: Named
    ranges: tuple[ValidationRange, ...]

    @model_validator(mode="after")
    def _has_a_domain(self) -> ValidationDomain:
        if not self.ranges:
            raise _refusal(
                f"the validation domain of '{self.check}' records no range; an empty "
                f"domain is a check that has never been compared, and recording one "
                f"would claim a comparison that did not happen",
                subject="ranges",
                source="the anchored worked examples and recorded tests for this check",
            )
        return self

    def label(self, inputs: Mapping[str, Quantity]) -> DomainLabel | None:
        """Where this use sits relative to the recorded domain. See :func:`label_use`."""
        return label_use(inputs, self.ranges)

    @property
    def parameters(self) -> tuple[str, ...]:
        """The parameters this check has been compared over, each named once."""
        return tuple(dict.fromkeys(recorded.parameter for recorded in self.ranges))

    def __str__(self) -> str:
        return f"{self.check} compared over: " + "; ".join(str(r) for r in self.ranges)


def label_checks(
    domains: Sequence[ValidationDomain],
    inputs: Mapping[str, Mapping[str, Quantity]],
) -> dict[str, DomainLabel]:
    """Label each check's use against its own recorded domain.

    ``inputs`` maps a check's name to the parameter values it ran at. A check with no
    recorded domain, or one whose inputs name none of the domain's parameters, is absent
    from the result rather than labelled: there is nothing to interpolate within.
    """
    domains = each_one(domains, ValidationDomain, named="domains")
    labels: dict[str, DomainLabel] = {}
    for domain in domains:
        label = domain.label(inputs.get(domain.check, {}))
        if label is not None:
            labels[domain.check] = label
    return labels


def correlate(
    plan: VerificationPlan,
    scorecard: Scorecard,
    *,
    bands: Mapping[str, AcceptanceBand] | None = None,
    senses: Mapping[str, PredictionSense] | None = None,
) -> tuple[Correlation, ...]:
    """Every recorded outcome that measured a value, compared with the check that planned it.

    An outcome with no measured value produces no correlation: the item is performed and
    uncorrelated, and nothing here implies agreement from a bare "passed".

    The predicted value is the driving check's own :class:`~anvilate.scorecard.Comparison`
    — the two numbers a comparison check already carries. A check with no comparison cannot
    be correlated by number, and is skipped rather than correlated against a parsed detail
    line. ``bands`` and ``senses`` are keyed on the check's name; a check with no band gets
    a ``NOT_EVALUATED`` comparison rather than an invented corridor, and a check with no
    stated sense is treated as a capacity, which is what a screening check's limit almost
    always is — state it where it is not.
    """
    bands = dict(bands or {})
    senses = dict(senses or {})
    by_name = {entry.name: entry for entry in scorecard.entries}
    found: list[Correlation] = []
    for item in plan.items:
        outcome = item.outcome
        if outcome is None or outcome.measured_value is None:
            continue
        for check in item.driving_checks:
            entry = by_name.get(check)
            if entry is None or entry.comparison is None:
                continue
            predicted = entry.comparison.limit if _is_capacity(entry) else entry.comparison.measured
            if predicted.pint.dimensionality != outcome.measured_value.pint.dimensionality:
                continue
            found.append(
                Correlation(
                    check=check,
                    item=item.name,
                    predicted=predicted,
                    measured=outcome.measured_value,
                    sense=senses.get(check, PredictionSense.CAPACITY),
                    performed_on=outcome.performed_on,
                    performed_by=outcome.performed_by,
                    instrument=outcome.instrument,
                    band=bands.get(check),
                    instrument_uncertainty=outcome.instrument_uncertainty,
                    check_passed=entry.status.value == "pass",
                )
            )
    return tuple(found)


def _is_capacity(entry: Any) -> bool:
    """Whether the check's *limit* is the prediction a test measures, not its response.

    A proof test measures what the part withstood, which is the capacity the check's limit
    states; a deflection inspection measures the response the check computed. The
    comparison's own sense says which: a value judged ``at_most`` is a response, one judged
    ``at_least`` is a capacity.
    """
    return entry.comparison.sense.value == "at_least"


def annotate(
    scorecard: Scorecard,
    correlations: Sequence[Correlation] = (),
    *,
    labels: Mapping[str, DomainLabel] | None = None,
) -> Scorecard:
    """The same scorecard with each correlation and domain label on its own entry.

    No verdict moves. Both land on the entry as annotations beside the uncertainty band,
    in the same shape and for the same reason: the numbers travel, and whoever renders
    the card decides how to say them.
    """
    correlations = each_one(correlations, Correlation, named="correlations")
    labels = dict(labels or {})
    from .scorecard import Scorecard as _Scorecard
    from .scorecard import ScorecardEntry

    by_check: dict[str, Correlation] = {}
    for correlation in correlations:
        by_check.setdefault(correlation.check, correlation)
    entries = []
    for entry in scorecard.entries:
        added = {
            name: value
            for name, value in (
                ("correlation", by_check.get(entry.name)),
                ("domain", labels.get(entry.name)),
            )
            if value is not None
        }
        if not added:
            entries.append(entry)
            continue
        entries.append(
            ScorecardEntry(
                **{
                    **entry.model_dump(exclude={"status", *added}),
                    "status": entry.status,
                    **added,
                }
            )
        )
    return _Scorecard(**{**scorecard.model_dump(exclude={"entries"}), "entries": tuple(entries)})


def candidates(
    correlations: Sequence[Correlation], *, bundle_digest: str
) -> tuple[EscapedDefectCandidate, ...]:
    """File an escaped-defect candidate for every unconservative correlation on a pass."""
    correlations = each_one(correlations, Correlation, named="correlations")
    return tuple(
        EscapedDefectCandidate(bundle_digest=bundle_digest, correlation=correlation)
        for correlation in correlations
        if correlation.is_escaped_defect_candidate
    )
