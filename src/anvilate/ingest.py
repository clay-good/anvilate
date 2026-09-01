"""Requirements ingestion: extracted values are drafts until a person says otherwise.

Engineers start from a requirement sheet, not from a chat box. The front door for real
work is a document somebody else wrote — an RFQ table, a customer requirement sheet, an
internal design brief — and the values in it are the loads, environments, and acceptance
criteria the whole screening rests on.

Reading one is easy. What is hard, and what this module is actually about, is the rule
that survives the reading: **an extracted value is a draft, and a draft is not an input.**
:meth:`DraftSpec.release` refuses while any load-bearing value is unconfirmed, and it
names them. That refusal is the feature. Everything else here exists to make it
answerable.

Four positions, each of which is a choice:

**No confidence scores.** A number between 0 and 1 attached to an extraction invites
somebody to set a threshold and stop reading, and it is not a measurement of anything —
it is the extractor grading its own homework. Instead every :class:`ExtractedValue`
carries the exact line it came from and where that line was, so the question "is this
right?" is answered by looking rather than by trusting. "Here is where it came from"
beats "I am 87% sure".

**A bare number is not a quantity.** A requirements sheet says "design load: 50 kN" and it
also says "quantity: 4". The first is a physical value and the second is a count, and no
amount of context makes an unlabelled 50 into a load. A line whose value has no unit is
recorded as :class:`UnparsedLine` — visible, countable, and not silently dropped — so a
reader can see what the pass did not take rather than assuming it took everything.

**A conflict is surfaced, never resolved.** Requirement documents contradict themselves:
the table says 50 kN and the notes say 45 kN. Both are kept, both are reported, and
neither is confirmed until somebody decides. Picking the first, the last, or the larger is
a silent decision about the design.

**A limit keeps the direction it was written with.** "Maximum operating pressure: 5 bar"
and "minimum yield: 250 MPa" are not the same kind of statement, and a number that has
lost which end of a range it is is worse than no number: it reads as a design value.
:class:`Bound` records the constraint phrase the line carried — from the label ("maximum
operating pressure") or from the trailing qualifier ("50 kN max", a line the pass used to
decline whole). The field *name* is left exactly as the document wrote it, because
rewriting ``maximum_operating_pressure`` to ``operating_pressure`` merges two fields on the
extractor's own authority, which is the decision this module hands to a person.

**Confirmation is per value and names a person.** Not per document, not per session. The
provenance records who confirmed what, because "the values were reviewed" is not a claim
anybody can act on.

The extraction pass itself is deliberately small: label-driven, over plain text, with the
unit parsed by :class:`~anvilate.units.Quantity`. PDF and table extraction belong with the
document stack and land with it; the state machine here does not change when they do.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from enum import StrEnum
from math import isclose, isfinite

from pydantic import BaseModel, ConfigDict, model_validator

from ._models import RevalidatedModel, cited
from .units import Quantity, UnitError, render

__all__ = [
    "Bound",
    "ConfirmationState",
    "SignatureStatus",
    "CertificateProvenance",
    "SourceLocation",
    "ExtractedValue",
    "UnparsedLine",
    "FieldConflict",
    "DraftSpec",
    "extract_requirements",
]

# A requirement line is "<label><separator><value>". The separators are tried in order and
# the order matters: a colon or an equals sign beats a column gap, because a flattened
# fixed-width table routinely has runs of spaces INSIDE the label. "Design load   (max):
# 50 kN" split on the gap first, labelled the field "design_load", and threw the value
# away. The column gap is still a separator, because that is how a table with no
# punctuation reads once its columns are flattened.
#
# A single space is deliberately not a separator: "design load 50 kN" would split at the
# first space and label the field "design". There is no length bound on the label either —
# an 81-character label used to match nothing at all and vanish without a trace, which
# defeats the "auditable by subtraction" property the whole pass rests on.
_SEPARATORS = (
    re.compile(r"^\s*(?P<label>[^:=]+?)\s*[:=]\s*(?P<value>\S.*?)\s*$"),
    re.compile(r"^\s*(?P<label>\S.*?)\s{2,}(?P<value>\S.*?)\s*$"),
)


def _split(line: str) -> re.Match[str] | None:
    """The first separator that splits ``line`` into a label and a value."""
    for pattern in _SEPARATORS:
        match = pattern.match(line)
        if match is not None:
            return match
    return None


# The value half of a line, when it is a magnitude and a unit. The unit is whatever
# remains; `Quantity.parse` is the judge of whether it is one, so nothing here has to know
# the unit vocabulary.
_VALUE = re.compile(r"^(?P<magnitude>[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?)\s*(?P<unit>\S.*)$")


# How close two extractions of one field have to be to count as the same requirement.
# Relative, so it means the same thing in kilonewtons and in gigametres, and tight enough
# that it only absorbs the float error of a unit conversion (~1e-15) — 50 kN and 50000 N
# agree; 50 kN and 50.04 kN do not, and neither do two baselines 0.4 m apart in a
# gigametre, which an absolute tolerance in the first value's unit used to swallow whole.
_AGREEMENT_TOLERANCE = 1e-12


def _normalize(label: str) -> str:
    """A label as a stable field name: lowercased, punctuation dropped, spaces to under."""
    cleaned = re.sub(r"[^0-9a-z]+", "_", label.strip().lower())
    return cleaned.strip("_")


class Bound(StrEnum):
    """Which end of a range a requirement states, when it says.

    A requirement sheet almost never states a bare design value: it states a ceiling
    ("maximum operating pressure: 5 bar") or a floor ("minimum yield: 250 MPa"). Dropping
    that direction leaves a number that reads as a design value and is not one, and no
    later stage can recover it — which is why this is recorded at extraction rather than
    inferred from the field name downstream.

    ``UNSTATED`` is the honest default and is not a synonym for "nominal". It means the
    line carried no constraint phrase, so nobody has said which end this is; a consumer
    that needs to know has to ask the person confirming, exactly as it would for any other
    unstated fact.
    """

    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    UNSTATED = "unstated"

    def phrase(self) -> str:
        """How to say this bound in a sentence a confirmer reads."""
        return {
            Bound.MAXIMUM: "a maximum",
            Bound.MINIMUM: "a minimum",
            Bound.UNSTATED: "no stated bound",
        }[self]


class ConfirmationState(StrEnum):
    """Where a value stands with the person responsible for it.

    ``DRAFT`` is the state everything is extracted into and the state nothing may be used
    from. ``REJECTED`` is a value a person looked at and refused, which is different
    information from a value nobody has looked at yet — the whole point of keeping three
    states rather than a boolean.
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class SourceLocation(RevalidatedModel):
    """Where in the document a value came from, precisely enough to go and look."""

    model_config = ConfigDict(frozen=True)

    document: str
    line_number: int
    excerpt: str
    page: int | None = None

    @model_validator(mode="after")
    def _locatable(self) -> SourceLocation:
        if not self.document.strip():
            raise ValueError("a source location must name its document")
        if self.line_number < 1:
            raise ValueError(f"line numbers start at 1; got {self.line_number}")
        if not self.excerpt.strip():
            raise ValueError(
                "a source location must carry the text it read; the excerpt is what makes "
                "the extraction checkable instead of merely plausible"
            )
        if self.page is not None and self.page < 1:
            raise ValueError(f"page numbers start at 1; got {self.page}")
        return self

    def __str__(self) -> str:
        where = f"{self.document}:{self.line_number}"
        if self.page is not None:
            where += f" (p. {self.page})"
        return f"{where} — {self.excerpt.strip()!r}"


class SignatureStatus(StrEnum):
    """Whether a source document carried a cryptographic signature, and what we did about it.

    There is no ``VERIFIED``, and its absence is the point. Verifying an XML digital
    signature needs the issuer's certificate and a trust anchor, neither of which is in a
    local, offline screening tool. So the two honest states are "there was no signature"
    and "there was one and Anvilate did not check it" — the same rule the attestation layer
    applies to its own seals, where a signature nobody checked reports ``not_evaluated``
    rather than pass.
    """

    ABSENT = "absent"
    PRESENT_UNVERIFIED = "present_unverified"


class CertificateProvenance(RevalidatedModel):
    """Where a measured value's certificate came from, and what it does and does not claim.

    The identifier and the issuing laboratory are what make a measured input traceable past
    "somebody measured it" — the chain runs from the check, through this record, to a
    calibrated instrument. ``signature_status`` is the honest half: a certificate is usable
    after confirmation whether or not it is signed, and the record says which, so a value is
    never silently presented as attested.

    ``claims_electronic_seal`` is the issuing laboratory's own assertion, carried separately
    because a document saying it is sealed is not evidence that it is. Two different facts,
    two different fields.
    """

    model_config = ConfigDict(frozen=True)

    identifier: cited(
        "the certificate's unique identifier; without it the measured value is traceable "
        "to nothing in particular"
    )
    laboratory: str  # the issuing calibration laboratory
    signature_status: SignatureStatus
    claims_electronic_seal: bool = False
    country: str | None = None
    issue_date: str | None = None
    performance_end_date: str | None = None
    schema_version: str | None = None

    @model_validator(mode="after")
    def _identified(self) -> CertificateProvenance:
        if not self.laboratory.strip():
            raise ValueError("a calibration certificate must name the laboratory that issued it")
        return self

    def signature_line(self) -> str:
        """The signature situation in one sentence, said the way it should be read."""
        if self.signature_status is SignatureStatus.ABSENT:
            claim = (
                " (the certificate claims an electronic seal it does not carry)"
                if (self.claims_electronic_seal)
                else ""
            )
            return f"no signature on the certificate{claim}"
        return "signature present and NOT verified by Anvilate — treat as unattested"

    def __str__(self) -> str:
        dated = f", issued {self.issue_date}" if self.issue_date else ""
        return (
            f"certificate {self.identifier} from {self.laboratory}{dated} — {self.signature_line()}"
        )


def _checklist_section(heading: str, entries: list[str]) -> list[str]:
    """A heading and its entries, or the heading and ``none``.

    Never an omitted heading. A draft with no conflicts and one whose conflicts nobody
    looked for are different documents, and they used to be the same one.
    """
    return [heading, *(f"  {entry}" for entry in entries or ("none",)), ""]


def _value_line(value: ExtractedValue) -> str:
    # The bound is rendered next to the number rather than left to the field name. A
    # confirmer reading "50 kN" decides whether the sheet says 50; reading "50 kN
    # (a maximum)" they also decide whether it is a ceiling, which is the half a lost
    # constraint phrase takes with it.
    limit = "" if value.bound is Bound.UNSTATED else f" ({value.bound.phrase()})"
    return f"{value.field} = {render(value.quantity)}{limit}    {value.source}"


class ExtractedValue(RevalidatedModel):
    """One candidate spec value, its source, and where it stands with a human.

    ``load_bearing`` marks a value the screening would actually consume. It defaults to
    True, and that default is the safe direction: a value nobody classified blocks the
    release until somebody looks at it, rather than slipping through as decoration.
    """

    model_config = ConfigDict(frozen=True)

    field: str
    quantity: Quantity
    source: SourceLocation
    load_bearing: bool = True
    # Which end of a range the document said this is. Defaulting to UNSTATED is the honest
    # direction and the opposite of ``load_bearing``'s: a value nobody classified must
    # block the release, and a bound nobody stated must not be invented.
    bound: Bound = Bound.UNSTATED
    state: ConfirmationState = ConfirmationState.DRAFT
    confirmed_by: str | None = None
    # Present when the value came from a calibration certificate rather than a requirement
    # document. It travels with the value through confirmation and into the release, so a
    # check consuming a measured input can say which instrument, on which certificate, and
    # whether anybody verified the signature.
    certificate: CertificateProvenance | None = None

    @model_validator(mode="after")
    def _state_and_signer_agree(self) -> ExtractedValue:
        if not self.field.strip():
            raise ValueError("an extracted value must name the field it fills")
        signed = bool(self.confirmed_by and self.confirmed_by.strip())
        if self.state is ConfirmationState.DRAFT and signed:
            raise ValueError(
                f"{self.field!r} is a draft but names {self.confirmed_by!r} as having "
                "confirmed it; a confirmation is a state change, not an annotation"
            )
        if self.state is not ConfirmationState.DRAFT and not signed:
            raise ValueError(
                f"{self.field!r} is marked {self.state.value} with nobody named. "
                "Confirmation is per value and names a person, because 'the values were "
                "reviewed' is not a claim anybody can act on"
            )
        return self

    @property
    def usable(self) -> bool:
        """Whether a check may consume this value."""
        return self.state is ConfirmationState.CONFIRMED

    def _decided(self, state: ConfirmationState, by: str) -> ExtractedValue:
        """This value moved to ``state`` by ``by``, with the signer rule enforced here.

        ``model_copy`` does not re-run validators, and these two methods are public — so
        ``value.confirmed("   ")`` produced exactly the state the constructor refuses:
        CONFIRMED with nobody named. It then reached ``release()`` and printed as
        "confirmed by " with an empty name. The check has to live on this path too.
        """
        if not by.strip():
            raise ValueError(
                f"marking {self.field!r} {state.value} names the person making the "
                f"decision; confirmation is per value and per person, and an unsigned one "
                f"is the state this model exists to refuse"
            )
        return self.model_copy(update={"state": state, "confirmed_by": by.strip()})

    def confirmed(self, by: str) -> ExtractedValue:
        """This value, confirmed by ``by``."""
        return self._decided(ConfirmationState.CONFIRMED, by)

    def rejected(self, by: str) -> ExtractedValue:
        """This value, refused by ``by`` — a decision, not an absence."""
        return self._decided(ConfirmationState.REJECTED, by)

    def __str__(self) -> str:
        mark = {
            ConfirmationState.DRAFT: "draft",
            ConfirmationState.CONFIRMED: f"confirmed by {self.confirmed_by}",
            ConfirmationState.REJECTED: f"rejected by {self.confirmed_by}",
        }[self.state]
        weight = "load-bearing" if self.load_bearing else "informational"
        cert = f" | {self.certificate}" if self.certificate is not None else ""
        limit = "" if self.bound is Bound.UNSTATED else f", {self.bound.phrase()}"
        return f"{self.field} = {self.quantity} [{weight}{limit}, {mark}] {self.source}{cert}"


class UnparsedLine(BaseModel):
    """A labelled line the pass did not take, and why — visible rather than dropped."""

    model_config = ConfigDict(frozen=True)

    source: SourceLocation
    reason: str

    def __str__(self) -> str:
        return f"not extracted ({self.reason}): {self.source}"


class FieldConflict(RevalidatedModel):
    """Two or more extractions for one field that do not agree.

    Kept whole. A conflict is a question for a person — the table says 50 kN and the notes
    say 45 kN, and choosing the first, the last, or the larger is a silent decision about
    the design.
    """

    model_config = ConfigDict(frozen=True)

    field: str
    values: tuple[ExtractedValue, ...]

    @model_validator(mode="after")
    def _actually_conflicting(self) -> FieldConflict:
        if len(self.values) < 2:
            raise ValueError("a conflict needs at least two values")
        return self

    def __str__(self) -> str:
        seen = ", ".join(
            f"{v.quantity} ({v.source.document}:{v.source.line_number})" for v in self.values
        )
        return f"{self.field}: {len(self.values)} disagreeing values — {seen}"


class DraftSpec(BaseModel):
    """Everything a requirements pass produced, and the gate between it and the pipeline."""

    model_config = ConfigDict(frozen=True)

    values: tuple[ExtractedValue, ...] = ()
    unparsed: tuple[UnparsedLine, ...] = ()
    documents: tuple[str, ...] = ()

    def conflicts(self) -> tuple[FieldConflict, ...]:
        """Fields with two or more extractions that do not agree, in field order.

        Two extractions of the *same* value are not a conflict — a requirement stated
        twice consistently is just stated twice. Comparison is by converted magnitude, so
        "50 kN" in the table and "50000 N" in the notes agree.

        Grouping is by field **and bound**, because "design load: 50 kN max" and "design
        load: 20 kN min" are the two ends of one range, not two answers to one question.
        Reporting them as a conflict would send somebody to reject a requirement the sheet
        meant. They still cannot both be released — :meth:`release` says why.
        """
        by_field: dict[tuple[str, Bound], list[ExtractedValue]] = {}
        for value in self.values:
            if value.state is not ConfirmationState.REJECTED:
                by_field.setdefault((value.field, value.bound), []).append(value)
        found = []
        for key in sorted(by_field):
            field = key[0]
            group = by_field[key]
            if len(group) < 2:
                continue
            first = group[0].quantity
            try:
                converted = [v.quantity.to(first.unit).magnitude for v in group]
            except Exception:
                # Incommensurable units for one field — a load quoted in kN on one line and
                # in mm on another — never agree, and the conversion failure IS the
                # disagreement. Collapsing that to a one-element set read as "they match".
                found.append(FieldConflict(field=field, values=tuple(group)))
                continue
            # Relative, not `round(..., 9)`. An absolute tolerance in whatever unit the
            # first value happened to use floats in physical size with that unit: at
            # gigametres it swallowed a 0.4 m disagreement, and at millimetres it is
            # tighter than any requirement sheet ever written.
            if not all(
                isclose(converted[0], other, rel_tol=_AGREEMENT_TOLERANCE, abs_tol=0.0)
                for other in converted[1:]
            ):
                found.append(FieldConflict(field=field, values=tuple(group)))
        return tuple(found)

    def unconfirmed_load_bearing(self) -> tuple[ExtractedValue, ...]:
        """The load-bearing values nobody has decided on — what blocks a release."""
        return tuple(
            v for v in self.values if v.load_bearing and v.state is ConfirmationState.DRAFT
        )

    def confirmed(self) -> tuple[ExtractedValue, ...]:
        """The values a person has accepted — the only ones a check may consume."""
        return tuple(v for v in self.values if v.usable)

    def split_bounds(self) -> tuple[str, ...]:
        """Confirmed fields carrying more than one bound — a range where a slot is wanted.

        Not a conflict: the sheet is consistent and both readings are true. It still blocks
        :meth:`release`, because the released mapping has one slot per field, so it is
        reported by :meth:`summary` rather than left to surface as a refusal at the gate.
        """
        bounds: dict[str, set[Bound]] = {}
        for value in self.confirmed():
            bounds.setdefault(value.field, set()).add(value.bound)
        return tuple(sorted(field for field, ends in bounds.items() if len(ends) > 1))

    def with_confirmation(
        self,
        field: str,
        *,
        by: str,
        state: ConfirmationState = ConfirmationState.CONFIRMED,
        reconsider: bool = False,
    ) -> DraftSpec:
        """This draft with every extraction of ``field`` moved to ``state`` by ``by``.

        Refuses a field the draft does not carry, rather than silently doing nothing:
        confirming a misspelled field name and getting a clean result back is how an
        unconfirmed value reaches a check.
        """
        if not by.strip():
            raise ValueError("a confirmation names the person making it")
        if field not in {v.field for v in self.values}:
            raise ValueError(
                f"no extracted value for {field!r}; the draft carries "
                f"{sorted({v.field for v in self.values})}"
            )
        already = [
            v
            for v in self.values
            if v.field == field and v.state is not ConfirmationState.DRAFT and v.state is not state
        ]
        if already and not reconsider:
            raise ValueError(
                f"{field!r} already carries a decision "
                f"({already[0].state.value} by {already[0].confirmed_by}) and this would "
                f"overwrite it in place, leaving no trace that it was ever made. Reversing a "
                f"decision is a new decision: pass reconsider=True to say so deliberately"
            )

        def _moved(value: ExtractedValue) -> ExtractedValue:
            # Written as a function rather than a nested conditional expression. The
            # expression form parsed right-associatively as "confirm everything if the
            # state is CONFIRMED, else reject only the matching field" — so confirming one
            # field confirmed the whole draft, which is the precise opposite of per-value
            # confirmation. Its own test caught it.
            if value.field != field:
                return value
            if state is ConfirmationState.CONFIRMED:
                return value.confirmed(by)
            return value.rejected(by)

        return self.model_copy(update={"values": tuple(_moved(v) for v in self.values)})

    def release(self) -> Mapping[str, Quantity]:
        """The confirmed values as a field mapping — or refuse, naming what is unconfirmed.

        This is the gate. A draft value is not an input, and the pipeline gets nothing at
        all while one is outstanding: releasing the confirmed subset and letting the caller
        notice the gap is the same failure with more steps.

        An unresolved conflict blocks too, even if both sides were somehow confirmed — two
        values for one field is not a field.
        """
        outstanding = self.unconfirmed_load_bearing()
        if outstanding:
            raise ValueError(
                f"{len(outstanding)} load-bearing value(s) are still drafts and nobody has "
                f"confirmed them: {sorted({v.field for v in outstanding})}. An extracted value "
                f"is a draft, and a draft is not an input"
            )
        conflicts = self.conflicts()
        if conflicts:
            raise ValueError(
                f"{len(conflicts)} field(s) carry disagreeing values and no one has resolved "
                f"them: {'; '.join(str(c) for c in conflicts)}"
            )
        split = self.split_bounds()
        if split:
            # Not a conflict — the sheet is consistent and both readings are true — and
            # exactly for that reason the mapping cannot carry them: it has one slot per
            # field, and filling it twice drops one end without saying so. The resolution
            # is the one this module already has: reject the end the pipeline is not
            # consuming, which leaves a record that somebody chose.
            bounds: dict[str, set[Bound]] = {}
            for value in self.confirmed():
                bounds.setdefault(value.field, set()).add(value.bound)
            raise ValueError(
                f"{len(split)} field(s) carry more than one bound and this mapping has one "
                f"slot per field: "
                + "; ".join(
                    f"{field} ({', '.join(sorted(b.value for b in bounds[field]))})"
                    for field in split
                )
                + ". Both readings are true, so nothing here can choose between them — "
                "reject the end the check does not consume, or extract them under separate "
                "field names"
            )
        released = {v.field: v.quantity for v in self.confirmed()}
        if not released:
            # Every value rejected, or every one informational and none confirmed. The two
            # gates above both pass, and handing the pipeline an empty mapping makes "there
            # is nothing here" indistinguishable from "everything checked out".
            raise ValueError(
                "nothing to release: the draft carries no confirmed value. That is not a "
                "clean sheet, it is an empty one — a pipeline handed {} cannot tell the "
                "difference"
            )
        return released

    def checklist(self) -> str:
        """Every value a confirmer has to act on, each linked to where it came from.

        `input-ingestion` requires that extracted values "appear as a confirmation
        checklist, each linked to its page location". :meth:`summary` counts them — "2
        unconfirmed" — which is the one thing a confirmer already knows. What they need is
        *which* two, and where each came from, because confirming an extracted number means
        going back to the sheet and reading the line it was taken from.

        The location was on every value the whole time and nothing rendered it. So the
        excerpt is here as well as the page and the line: a reader holding the document open
        matches on the text far faster than on a line number, and a line number alone is
        wrong the moment the document is re-exported.

        Four sections, and each is present even when empty, for the reason the calculation
        report's headings are: a draft with no conflicts and one whose conflicts nobody
        looked for must not render the same.
        """
        outstanding = self.unconfirmed_load_bearing()
        blocking = {id(value) for value in outstanding}
        advisory = [
            value
            for value in self.values
            if value.state is ConfirmationState.DRAFT and id(value) not in blocking
        ]
        lines = [self.summary(), ""]
        lines.extend(
            _checklist_section(
                "TO CONFIRM — load-bearing, blocking release",
                [f"[ ] {_value_line(value)}" for value in outstanding],
            )
        )
        lines.extend(
            _checklist_section(
                "TO CONFIRM — not load-bearing",
                [f"[ ] {_value_line(value)}" for value in advisory],
            )
        )
        lines.extend(
            _checklist_section(
                "CONFIRMED",
                [
                    f"[x] {_value_line(value)} — confirmed by {value.confirmed_by}"
                    for value in self.confirmed()
                ],
            )
        )
        # One line per reading rather than one per conflict: a conflict is the case where a
        # reader most needs both excerpts side by side to decide which line is right, and
        # nesting two of them inside one sentence makes that harder rather than shorter.
        conflicts: list[str] = []
        for conflict in self.conflicts():
            conflicts.append(f"!   {conflict.field} disagrees:")
            conflicts.extend(f"      {_value_line(value)}" for value in conflict.values)
        lines.extend(_checklist_section("CONFLICTS", conflicts))
        lines.extend(
            _checklist_section(
                "NOT EXTRACTED",
                [f"?   {line.source} — {line.reason}" for line in self.unparsed],
            )
        )
        return "\n".join(lines).rstrip() + "\n"

    def summary(self) -> str:
        """One line: what was read, what is outstanding, and whether it can be released."""
        outstanding = len(self.unconfirmed_load_bearing())
        conflicts = len(self.conflicts())
        # The third gate is here for the same reason the other two are: `summary` printing
        # "releasable" over a draft `release` refuses is a worse answer than either the
        # summary or the refusal alone, because the reader believes the cheap one.
        split = len(self.split_bounds())
        gate = (
            "releasable"
            if not outstanding and not conflicts and not split
            else (
                f"blocked: {outstanding} unconfirmed, {conflicts} conflicting, "
                f"{split} split across two bounds"
            )
        )
        return (
            f"{len(self.values)} values from {len(self.documents)} document(s), "
            f"{len(self.confirmed())} confirmed, {len(self.unparsed)} lines not extracted — {gate}"
        )


# Trailing words that qualify a value rather than measure it. pint reads several of them
# as units and produces a number with the wrong dimension and no complaint: "Grade: 8.8
# min" becomes 8.8 MINUTES, and "Pressure: 5 bar g" becomes bar*gram. A qualifier is
# information, but it is not part of the unit, and guessing which it was is exactly the
# decision this module hands to a person.
_QUALIFIERS = frozenset(
    {
        "min",
        "max",
        "nom",
        "nominal",
        "typ",
        "typical",
        "ref",
        "abs",
        "absolute",
        "gauge",
        "gage",
        "g",
        "a",
        "approx",
        "each",
        "off",
    }
)

# The qualifiers that state a *direction* rather than merely qualify. They are why
# "Design load: 50 kN max" — a line on every requirement sheet there is — used to be
# declined whole: `max` is in `_QUALIFIERS`, and refusing the qualifier refused the
# quantity with it. Stripped and recorded as a `Bound` instead, so the value survives
# carrying the constraint it was written under.
_DIRECTIONAL_QUALIFIERS = {
    "min": Bound.MINIMUM,
    "minimum": Bound.MINIMUM,
    "max": Bound.MAXIMUM,
    "maximum": Bound.MAXIMUM,
}

# Constraint phrases as they read once a label is normalized to underscore-separated
# tokens. Matched as a contiguous run of whole tokens, never as a substring: "min" is a
# substring of "nominal", and a nominal dimension read as a floor is exactly the confident
# wrong answer the rest of this module exists to refuse.
_LABEL_BOUND_PHRASES: tuple[tuple[tuple[str, ...], Bound], ...] = (
    (("not", "to", "exceed"), Bound.MAXIMUM),
    (("not", "exceeding"), Bound.MAXIMUM),
    (("no", "more", "than"), Bound.MAXIMUM),
    (("at", "most"), Bound.MAXIMUM),
    (("up", "to"), Bound.MAXIMUM),
    (("maximum",), Bound.MAXIMUM),
    (("max",), Bound.MAXIMUM),
    (("no", "less", "than"), Bound.MINIMUM),
    (("not", "less", "than"), Bound.MINIMUM),
    (("at", "least"), Bound.MINIMUM),
    (("minimum",), Bound.MINIMUM),
    (("min",), Bound.MINIMUM),
)


def _bound_from_label(field: str) -> Bound:
    """The constraint the label states, or ``UNSTATED`` — refusing a label that states both.

    A label carrying both directions ("minimum and maximum pressure") names two
    requirements in one field, and picking either end of it is the silent decision this
    module hands to a person. The line is declined with the reason instead.
    """
    tokens = field.split("_")
    found = {
        bound
        for phrase, bound in _LABEL_BOUND_PHRASES
        if any(tuple(tokens[i : i + len(phrase)]) == phrase for i in range(len(tokens)))
    }
    if len(found) > 1:
        raise ValueError(
            f"the label {field!r} states both a maximum and a minimum, so it names two "
            f"requirements in one field. Split them into two lines — which end this value "
            f"is is not something the pass may choose"
        )
    return found.pop() if found else Bound.UNSTATED


# Single letters pint resolves to something a requirement sheet almost never means. "C" is
# coulomb and "F" is farad; on a requirement sheet they are Celsius and Fahrenheit, and the
# difference is a temperature check running on a charge.
_AMBIGUOUS_UNITS = {
    "C": "coulomb, and a requirement sheet means degC",
    "F": "farad, and a requirement sheet means degF",
    "min": "minutes, and on a requirement sheet 'min' is usually 'minimum' — write "
    "'minute' if you mean the time unit",
    "max": "a maximum qualifier rather than a unit",
}

# What a range or a tolerance looks like once the leading magnitude is taken off.
_RANGE_START = re.compile(r"^[-–—±~]|^\+\s*/\s*-|^to\b", re.IGNORECASE)


def _magnitude(text: str) -> str:
    """The magnitude with thousands separators removed — or a refusal if it is ambiguous.

    Stripping every comma unconditionally turned "1,5 m" into 15 m, a tenfold error on
    exactly the European requirement sheets this module is aimed at. A comma is only
    removed where it is unambiguously a thousands separator: digit groups of exactly three.
    """
    if "," not in text:
        return text
    if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+", text):
        return text.replace(",", "")
    raise ValueError(
        f"the comma in {text!r} is ambiguous — it is a decimal point in most of Europe and "
        f"a thousands separator elsewhere, and the two readings differ by a factor of ten. "
        f"Write it with a point, or group thousands in threes"
    )


def _unit(text: str) -> tuple[str, Bound]:
    """The unit half and the bound its trailing qualifier states, if it states one.

    Refused when it is a range, a tolerance, or a qualifier that is not directional — each
    of those produced a confident wrong number rather than a refusal, which is worse than
    anything the pass declines. A *directional* qualifier is taken rather than refused:
    "50 kN max" is a quantity and a constraint, not a broken unit, and declining it lost
    the most common line on any requirement sheet.
    """
    unit = text.strip()
    if _RANGE_START.match(unit) or "±" in unit:
        raise ValueError(
            f"{text!r} looks like a range or a tolerance, not a single value. State which "
            f"end of it the requirement means — a range multiplied out is not a number "
            f"anybody wrote down"
        )
    tokens = unit.split()
    bound = Bound.UNSTATED
    if len(tokens) > 1 and tokens[-1].lower().strip(".") in _DIRECTIONAL_QUALIFIERS:
        # Only when something is left to be a unit. "Grade: 8.8 min" strips to a bare
        # number, and a bare number is not a quantity however it was qualified — it falls
        # through to the ambiguity refusal below, which says so in those words.
        bound = _DIRECTIONAL_QUALIFIERS[tokens[-1].lower().strip(".")]
        tokens = tokens[:-1]
        unit = " ".join(tokens)
    if len(tokens) > 1 and tokens[-1].lower().strip(".") in _QUALIFIERS:
        raise ValueError(
            f"{tokens[-1]!r} in {text!r} is a qualifier, not part of the unit. pint reads "
            f"several of them as units and returns the wrong dimension without complaint"
        )
    if unit in _AMBIGUOUS_UNITS:
        raise ValueError(f"{unit!r} is ambiguous: it reads as {_AMBIGUOUS_UNITS[unit]}")
    return unit, bound


#: What a requirements sheet writes for an offset temperature, mapped to the unit pint
#: constructs for it. A mapping rather than a set, because the membership test was
#: case-insensitive and the construction was not: ``"20 Celsius"`` was declared handled here
#: and then raised on the capital C, so the line was declined for the wrong reason.
_OFFSET_TEMPERATURE_UNITS = {
    "degc": "degC",
    "c": "degC",
    "celsius": "degC",
    "degree_celsius": "degC",
    "degf": "degF",
    "f": "degF",
    "fahrenheit": "degF",
    "degree_fahrenheit": "degF",
}

#: The unit tokens a document writes for a temperature that pint **already parses as
#: something else**. ``C`` is the coulomb, ``F`` the farad, and lowercase ``c`` the speed of
#: light, so ``Quantity.parse`` succeeds on all three and the offset fallback below never saw
#: them: "operating temperature: 5 C" came out of this pass as five coulombs. Refused by name
#: rather than guessed at — a requirements pass that silently picks one of two readings is
#: the same silent green the scorecard refuses, one layer earlier.
_AMBIGUOUS_UNIT_TOKENS = {
    "C": ("coulomb", "degC"),
    "c": ("the speed of light", "degC"),
    "F": ("farad", "degF"),
    "f": ("farad", "degF"),
}


def _quantity(magnitude: str, unit: str) -> Quantity:
    """A magnitude and a unit as a :class:`~anvilate.units.Quantity`.

    ``Quantity.parse`` is tried first because it is the library's front door, and it
    refuses a bare number — which is the behaviour this pass wants. It also refuses an
    OFFSET temperature unit (pint will not parse ``"-20 degC"`` from text, only construct
    it), and "service temperature: -20 degC" is on every requirement sheet there is. So a
    parse failure falls back to direct construction, which handles the offset units and
    still raises on a unit that is not one.
    """
    bare = unit.strip()
    if bare in _AMBIGUOUS_UNIT_TOKENS:
        reads_as, meant = _AMBIGUOUS_UNIT_TOKENS[bare]
        raise ValueError(
            f"{bare!r} is {reads_as} to the unit registry, not a temperature, and this line "
            f"gives no way to tell which was meant. Write {meant!r} or '°{bare.upper()}' for "
            f"the temperature, or the unit's full name for the electrical quantity"
        )
    try:
        quantity = Quantity.parse(f"{magnitude} {unit}")
    except (UnitError, ValueError):
        # Narrow on purpose. `Quantity.parse` is the library's front door and it refuses a
        # dimensionless result, which is the behaviour this pass wants — "12 %" and "3
        # dimensionless" are not physical values. The one thing it cannot do is an OFFSET
        # temperature unit (pint will construct "-20 degC" but not parse it), and that is
        # on every requirement sheet there is. So the fallback is for those units and
        # nothing else; a general escape hatch here quietly re-admitted everything parse
        # had just declined.
        offset = _OFFSET_TEMPERATURE_UNITS.get(unit.lower().lstrip("°"))
        if offset is None:
            raise
        # Constructed with pint's own spelling rather than the document's, so a sheet
        # writing "Celsius" is handled as the list above says it is.
        quantity = Quantity(magnitude=float(magnitude), unit=offset)
    # The general net under the specific ones. If the parsed magnitude is not the magnitude
    # the line stated, the "unit" half contained a number and pint multiplied it in:
    # "45–50 kN" came back as 2250 kN and "25 ±0.1 mm" as 2.5 mm. Whatever produced that,
    # the answer is not what the document says.
    stated = float(magnitude)
    if quantity.magnitude != stated:
        raise ValueError(
            f"{magnitude!r} in {unit!r} parsed to a magnitude of {quantity.magnitude:g}, so "
            f"the unit half carries a number of its own — a range, a tolerance, or a second "
            f"value. This is not one quantity"
        )
    # The two ways a written number stops being the number written. `inf kN` is refused by
    # the value pattern above, and `1e400 kN` walked straight past it: `float` overflows to
    # the same infinity, the comparison two lines up is inf == inf, and the pass released an
    # infinite load as a confirmable draft value. `1e-400 mm` is the mirror — a dimension
    # the author wrote as positive, extracted as exactly zero.
    if not isfinite(stated):
        raise ValueError(
            f"{magnitude!r} overflows to {stated}; a value a float cannot hold is not the "
            f"value the document states, and an infinite one is refused however it is spelt"
        )
    if stated == 0.0 and any(digit in magnitude for digit in "123456789"):
        raise ValueError(
            f"{magnitude!r} underflows to zero; the document states a value that is not "
            f"zero and this pass will not record it as one"
        )
    return quantity


def _combined_bound(field: str, from_label: Bound, from_qualifier: Bound) -> Bound:
    """The one bound a line states, refusing a line whose two halves state opposite ends.

    "Minimum bore: 25 mm max" is not a requirement anybody can act on, and taking either
    half of it means preferring one of two things the document says with equal authority.
    """
    if from_label is from_qualifier or Bound.UNSTATED in (from_label, from_qualifier):
        return from_label if from_qualifier is Bound.UNSTATED else from_qualifier
    raise ValueError(
        f"the label {field!r} states {from_label.phrase()} and the value states "
        f"{from_qualifier.phrase()}; one line cannot be both ends of a range, and choosing "
        f"between them is a decision about the design"
    )


def extract_requirements(
    text: str,
    *,
    document: str,
    page: int | None = None,
    informational_fields: Iterable[str] = (),
) -> DraftSpec:
    """Read a plain-text requirement sheet into a draft spec, extracting nothing silently.

    Each line is matched as ``label: value`` (a colon, an equals sign, or a column gap of
    two or more spaces). A value that parses as a magnitude with a unit becomes an
    :class:`ExtractedValue` in ``DRAFT``; a labelled line that does not is recorded as an
    :class:`UnparsedLine` with the reason, so the pass is auditable by subtraction rather
    than by trust.

    ``informational_fields`` names the normalized fields that are *not* load-bearing —
    a part number, a revision, a quantity ordered. Everything else defaults to
    load-bearing, which is the safe direction: an unclassified value blocks the release
    until somebody looks at it.

    The pass is label-driven and knows nothing about engineering vocabulary. That is
    deliberate: a pass that guessed which line was "really" the design load would be
    making the decision this module exists to hand to a person.
    """
    if not document.strip():
        raise ValueError("extraction must name the document it read")
    informational = {_normalize(name) for name in informational_fields}
    values: list[ExtractedValue] = []
    unparsed: list[UnparsedLine] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        match = _split(raw)
        if match is None:
            continue  # no separator at all: prose, not a labelled requirement
        location = SourceLocation(document=document, line_number=number, excerpt=raw, page=page)
        field = _normalize(match.group("label"))
        if not field:
            # A label of punctuation ("***: 50 kN") normalizes away to nothing. It used to
            # `continue` and disappear; it is a labelled line the pass declined, so it is
            # recorded as one.
            unparsed.append(
                UnparsedLine(source=location, reason="the label normalizes to an empty field name")
            )
            continue
        value_match = _VALUE.match(match.group("value"))
        if value_match is None:
            unparsed.append(
                UnparsedLine(source=location, reason="the value is not a number with a unit")
            )
            continue
        try:
            magnitude = _magnitude(value_match.group("magnitude"))
            unit, qualifier_bound = _unit(value_match.group("unit"))
            quantity = _quantity(magnitude, unit)
            bound = _combined_bound(field, _bound_from_label(field), qualifier_bound)
        except (UnitError, ValueError) as exc:
            # A bare number is the important case: a requirements sheet says "quantity: 4"
            # as often as it says "design load: 50 kN", and no amount of context turns an
            # unlabelled 4 into a physical value. Recorded, not guessed at, not dropped.
            unparsed.append(UnparsedLine(source=location, reason=str(exc)))
            continue
        values.append(
            ExtractedValue(
                field=field,
                quantity=quantity,
                source=location,
                load_bearing=field not in informational,
                bound=bound,
            )
        )
    return DraftSpec(values=tuple(values), unparsed=tuple(unparsed), documents=(document.strip(),))
