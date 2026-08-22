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

from pydantic import BaseModel, ConfigDict, model_validator

from .units import Quantity, UnitError

__all__ = [
    "ConfirmationState",
    "SourceLocation",
    "ExtractedValue",
    "UnparsedLine",
    "FieldConflict",
    "DraftSpec",
    "extract_requirements",
]

# A requirement line is "<label><separator><value>", and the separator is a colon, an
# equals sign, or a run of two or more spaces (which is how a fixed-width RFQ table reads
# once its columns are flattened to text). A single space is deliberately not a separator:
# "design load 50 kN" would split at the first space and label the field "design".
_LINE = re.compile(r"^\s*(?P<label>[^:=]{1,80}?)\s*(?::|=|\s{2,})\s*(?P<value>\S.*?)\s*$")

# The value half of a line, when it is a magnitude and a unit. The unit is whatever
# remains; `Quantity.parse` is the judge of whether it is one, so nothing here has to know
# the unit vocabulary.
_VALUE = re.compile(r"^(?P<magnitude>[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?)\s*(?P<unit>\S.*)$")


def _normalize(label: str) -> str:
    """A label as a stable field name: lowercased, punctuation dropped, spaces to under."""
    cleaned = re.sub(r"[^0-9a-z]+", "_", label.strip().lower())
    return cleaned.strip("_")


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


class SourceLocation(BaseModel):
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


class ExtractedValue(BaseModel):
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
    state: ConfirmationState = ConfirmationState.DRAFT
    confirmed_by: str | None = None

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

    def confirmed(self, by: str) -> ExtractedValue:
        """This value, confirmed by ``by``."""
        return self.model_copy(
            update={"state": ConfirmationState.CONFIRMED, "confirmed_by": by.strip()}
        )

    def rejected(self, by: str) -> ExtractedValue:
        """This value, refused by ``by`` — a decision, not an absence."""
        return self.model_copy(
            update={"state": ConfirmationState.REJECTED, "confirmed_by": by.strip()}
        )

    def __str__(self) -> str:
        mark = {
            ConfirmationState.DRAFT: "draft",
            ConfirmationState.CONFIRMED: f"confirmed by {self.confirmed_by}",
            ConfirmationState.REJECTED: f"rejected by {self.confirmed_by}",
        }[self.state]
        weight = "load-bearing" if self.load_bearing else "informational"
        return f"{self.field} = {self.quantity} [{weight}, {mark}] {self.source}"


class UnparsedLine(BaseModel):
    """A labelled line the pass did not take, and why — visible rather than dropped."""

    model_config = ConfigDict(frozen=True)

    source: SourceLocation
    reason: str

    def __str__(self) -> str:
        return f"not extracted ({self.reason}): {self.source}"


class FieldConflict(BaseModel):
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
        """
        by_field: dict[str, list[ExtractedValue]] = {}
        for value in self.values:
            if value.state is not ConfirmationState.REJECTED:
                by_field.setdefault(value.field, []).append(value)
        found = []
        for field in sorted(by_field):
            group = by_field[field]
            if len(group) < 2:
                continue
            first = group[0].quantity
            try:
                magnitudes = {round(v.quantity.to(first.unit).magnitude, 9) for v in group}
                disagree = len(magnitudes) > 1
            except Exception:
                # Incommensurable units for one field — a load quoted in kN on one line and
                # in mm on another — never agree, and the conversion failure IS the
                # disagreement. Collapsing that to a one-element set read as "they match".
                disagree = True
            if disagree:
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

    def with_confirmation(
        self, field: str, *, by: str, state: ConfirmationState = ConfirmationState.CONFIRMED
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
        return {v.field: v.quantity for v in self.confirmed()}

    def summary(self) -> str:
        """One line: what was read, what is outstanding, and whether it can be released."""
        outstanding = len(self.unconfirmed_load_bearing())
        conflicts = len(self.conflicts())
        gate = (
            "releasable"
            if not outstanding and not conflicts
            else f"blocked: {outstanding} unconfirmed, {conflicts} conflicting"
        )
        return (
            f"{len(self.values)} values from {len(self.documents)} document(s), "
            f"{len(self.confirmed())} confirmed, {len(self.unparsed)} lines not extracted — {gate}"
        )


def _quantity(magnitude: str, unit: str) -> Quantity:
    """A magnitude and a unit as a :class:`~anvilate.units.Quantity`.

    ``Quantity.parse`` is tried first because it is the library's front door, and it
    refuses a bare number — which is the behaviour this pass wants. It also refuses an
    OFFSET temperature unit (pint will not parse ``"-20 degC"`` from text, only construct
    it), and "service temperature: -20 degC" is on every requirement sheet there is. So a
    parse failure falls back to direct construction, which handles the offset units and
    still raises on a unit that is not one.
    """
    try:
        return Quantity.parse(f"{magnitude} {unit}")
    except (UnitError, ValueError):
        return Quantity(magnitude=float(magnitude), unit=unit)


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
        match = _LINE.match(raw)
        if match is None:
            continue
        field = _normalize(match.group("label"))
        if not field:
            continue
        location = SourceLocation(document=document, line_number=number, excerpt=raw, page=page)
        value_match = _VALUE.match(match.group("value"))
        if value_match is None:
            unparsed.append(
                UnparsedLine(source=location, reason="the value is not a number with a unit")
            )
            continue
        magnitude = value_match.group("magnitude").replace(",", "")
        unit = value_match.group("unit")
        try:
            quantity = _quantity(magnitude, unit)
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
            )
        )
    return DraftSpec(values=tuple(values), unparsed=tuple(unparsed), documents=(document.strip(),))
