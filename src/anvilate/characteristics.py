"""Characteristic accountability: every characteristic numbered, and the numbers kept.

First-article inspection works from one table: each characteristic on the drawing, a
number, its nominal and tolerance, whether it is special, and a column for what was
measured. The number is the whole point, and the expensive mistake is renumbering: a
revision that adds one hole and shifts every number after it breaks every inspection
record, gauge plan and customer concession that quoted the old numbers.

:func:`characteristics_of` lists a part's characteristics in one place, from its Design
Spec and its callouts: the toleranced dimensions, the geometric tolerances, the notes, and
any material property you mark. Each carries an identity derived from *what it is* (its
kind, the feature it is on, and for a frame its type), never from its value, so a revised
tolerance is the same characteristic. :func:`number_characteristics` numbers them against
the previous revision's :class:`CharacteristicRegister`: a characteristic keeps its number,
a new one takes the next number never used, and a removed one's number is retired and
never handed out again.

**Special characteristics** are yours to declare: a :class:`SpecialMark` names one
characteristic as critical or significant, with the symbol your customer uses and the
reason. A mark that matches no characteristic, or more than one, is refused, and an
unmarked characteristic is never shown as special.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field

from ._models import (
    EMPTY_MAP,
    FrozenMap,
    ItemCollection,
    Named,
    Provenance,
    StatableModel,
    each_one,
)
from .callouts import CalloutSet, _characteristic_id
from .refusal import RefusalError, Remedy

__all__ = [
    "ACCOUNTABILITY_COLUMNS",
    "CharacteristicKind",
    "SpecialClass",
    "SpecialMark",
    "Characteristic",
    "CharacteristicRegister",
    "NumberedCharacteristic",
    "AccountabilityTable",
    "CONTROL_PLAN_COLUMNS",
    "ControlPlanSeed",
    "characteristics_of",
    "number_characteristics",
    "control_plan_seed",
]

_SOURCE = "the part's Design Spec, its callouts, and your special-characteristic marks"
_REGISTER_SOURCE = "the previous revision's characteristic register, as saved"

#: The accountability table's columns, in order: one row per characteristic.
ACCOUNTABILITY_COLUMNS = (
    "number",
    "kind",
    "characteristic",
    "nominal",
    "tolerance",
    "special",
    "symbol",
    "reason",
    "measured result",
)


#: The control-plan seed's columns. The last six are the plant's, and are written empty.
CONTROL_PLAN_COLUMNS = (
    "number",
    "characteristic",
    "specification",
    "tolerance",
    "special",
    "symbol",
    "governing check",
    "suggested measurement method",
    "process step",
    "machine / device",
    "sample size",
    "frequency",
    "control method",
    "reaction plan",
)


class _CharacteristicInputError(RefusalError, ValueError):
    """A characteristic input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str = _SOURCE) -> _CharacteristicInputError:
    return _CharacteristicInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class CharacteristicKind(StrEnum):
    """What a characteristic is."""

    DIMENSION = "dimension"
    GEOMETRIC_TOLERANCE = "geometric_tolerance"
    NOTE = "note"
    PROPERTY = "property"


class SpecialClass(StrEnum):
    """The two classes of special characteristic most customers' schemes distinguish."""

    CRITICAL = "critical"
    SIGNIFICANT = "significant"


class SpecialMark(StatableModel):
    """One characteristic marked special, with your customer's symbol and the reason.

    ``where`` is the semantic tag the characteristic is on (for a property, the property's
    name, such as ``yield strength``). ``detail`` tells apart two characteristics at one
    tag: a frame's type (``position``) or a note's kind (``heat_treatment``). ``check``
    names the check on the card that makes it special, for the control-plan seed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CharacteristicKind
    where: Named
    detail: Named | None = None
    special: SpecialClass
    symbol: Named
    reason: Provenance
    check: Named | None = None


class Characteristic(StatableModel):
    """One characteristic of a part, with the identity that survives a revision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    kind: CharacteristicKind
    where: Named
    detail: str = ""
    description: Named
    nominal: str = ""
    tolerance: str = ""
    special: SpecialClass | None = None
    symbol: str = ""
    reason: str = ""
    check: str = ""

    def __str__(self) -> str:
        mark = f" [{self.special.value} {self.symbol}]" if self.special else ""
        return f"{self.description}{mark}"


class CharacteristicRegister(StatableModel):
    """Every number a part's characteristics have ever been given, by identity.

    Save it with each revision (``model_dump_json``) and pass it back as ``previous`` for
    the next one. A retired characteristic stays in it, so its number is never reused.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    part: Named
    revision: Named
    numbers: FrozenMap[str, int] = Field(default_factory=lambda: EMPTY_MAP)


class NumberedCharacteristic(StatableModel):
    """One characteristic and its number."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int = Field(ge=1)
    characteristic: Characteristic

    def cells(self) -> tuple[str, ...]:
        """The row in :data:`ACCOUNTABILITY_COLUMNS` order; the measured result is empty."""
        c = self.characteristic
        return (str(self.number), c.kind.value, c.description, c.nominal, c.tolerance,
                c.special.value if c.special else "", c.symbol, c.reason, "")  # fmt: skip


class AccountabilityTable(StatableModel):
    """One revision's characteristics, numbered, and what changed since the last one."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[NumberedCharacteristic, ...]
    numbering: CharacteristicRegister
    added: tuple[int, ...] = ()
    retired: tuple[int, ...] = ()

    def to_csv(self) -> str:
        """The table as CSV, ordered by number, the measured-result column empty. A cell a
        spreadsheet would read as a formula is written as text."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(ACCOUNTABILITY_COLUMNS)
        for row in self.rows:
            writer.writerow(_safe(row.cells()))
        return out.getvalue()

    def to_xlsx(self) -> bytes:
        """The table as an XLSX workbook with one sheet."""
        from .margin_of_safety import _workbook

        rows = [list(ACCOUNTABILITY_COLUMNS), *(_safe(row.cells()) for row in self.rows)]
        return _workbook((("Characteristics", rows, {0}),))

    def __str__(self) -> str:
        r = self.numbering
        head = (f"{r.part} rev {r.revision}: {len(self.rows)} characteristic(s); "
                f"new {list(self.added)}; retired {list(self.retired)}")  # fmt: skip
        return "\n".join([head, *(f"  {row.number}. {row.characteristic}" for row in self.rows)])


_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _safe(cells: Sequence[str]) -> list[str]:
    return [("'" + c) if c.startswith(_FORMULA_LEADS) else c for c in cells]


def _mm(value: Any) -> str:
    return f"{value.to('mm').magnitude:g} mm"


def _limit(nominal: Any, deviation: Any) -> str:
    """A limit of size in mm, rounded to clear the float noise of the sum (0.1 nm)."""
    return f"{round(nominal.to('mm').magnitude + deviation.to('mm').magnitude, 7):g}"


def characteristics_of(
    spec: Any, *, callouts: CalloutSet | None = None, marks: Sequence[SpecialMark] = ()
) -> tuple[Characteristic, ...]:
    """Every characteristic of the part ``spec`` declares, with its marks applied.

    The order is the drawing's: toleranced dimensions, then geometric tolerances, then the
    callouts' notes, then marked material properties. Two characteristics of one kind on
    one tag (two dimensions on ``bore``) are told apart by their order there.
    """
    from .spec import DesignSpec

    if not isinstance(spec, DesignSpec):
        raise _refuse("spec must be a DesignSpec", subject="spec")
    if callouts is not None and not isinstance(callouts, CalloutSet):
        raise _refuse("callouts must be a CalloutSet", subject="callouts")
    marks = each_one(marks, SpecialMark, named="marks")
    found: list[Characteristic] = []
    seen: dict[tuple[str, str, str], int] = {}

    def add(kind: CharacteristicKind, where: str, detail: str, **fields: Any) -> None:
        key = (kind.value, where, detail)
        ordinal = seen.get(key, 0)
        seen[key] = ordinal + 1
        identity = fields.pop("id", None) or _characteristic_id(
            kind.value, where, f"{detail}#{ordinal}" if ordinal else detail)  # fmt: skip
        found.append(Characteristic(id=identity, kind=kind, where=where, detail=detail,
                                    **fields))  # fmt: skip

    for dimension in spec.dimensions:
        band = dimension.resolve()
        add(CharacteristicKind.DIMENSION, dimension.tag, "",
            description=f"size of {dimension.tag}", nominal=_mm(dimension.nominal),
            tolerance=f"{_limit(dimension.nominal, band.lower)} to "
                      f"{_limit(dimension.nominal, band.upper)} mm")  # fmt: skip
    for frame in spec.geometric_tolerances:
        zone = f"⌀{_mm(frame.tolerance)}" if frame.diametral else _mm(frame.tolerance)
        datums = f" to {'|'.join(frame.datums)}" if frame.datums else ""
        add(CharacteristicKind.GEOMETRIC_TOLERANCE, frame.feature, frame.characteristic.value,
            description=f"{frame.characteristic.value} of {frame.feature}",
            tolerance=f"{zone}{datums}")  # fmt: skip
    for callout in callouts.callouts if callouts is not None else ():
        add(CharacteristicKind.NOTE, callout.where, callout.kind, id=callout.characteristic_id,
            description=str(callout))  # fmt: skip
    for mark in marks:
        if mark.kind is CharacteristicKind.PROPERTY:
            add(CharacteristicKind.PROPERTY, mark.where, "",
                description=f"{mark.where} of {spec.material.ref}",
                tolerance=f"per the material specification for {spec.material.ref}")  # fmt: skip
    marked: list[Characteristic] = []
    applied: dict[str, SpecialMark] = {}
    for mark in marks:
        hits = [c for c in found if c.kind is mark.kind and c.where == mark.where
                and (mark.detail is None or c.detail == mark.detail)]  # fmt: skip
        label = f"{mark.kind.value} at {mark.where}" + (f" ({mark.detail})" if mark.detail else "")
        if len(hits) != 1:
            held = sorted({f"{c.kind.value} at {c.where} ({c.detail})" if c.detail
                           else f"{c.kind.value} at {c.where}" for c in found})  # fmt: skip
            problem = "matches no characteristic" if not hits else (
                f"matches {len(hits)}; give its detail to name one")  # fmt: skip
            raise _refuse(f"the mark on {label} {problem}; the part holds {held}",
                          subject="marks")  # fmt: skip
        if hits[0].id in applied:
            raise _refuse(f"{label} is marked twice", subject="marks")
        applied[hits[0].id] = mark
    for c in found:
        said = applied.get(c.id)
        marked.append(c if said is None else c.model_copy(update={
            "special": said.special, "symbol": said.symbol, "reason": said.reason,
            "check": said.check or ""}))  # fmt: skip
    return tuple(marked)


def number_characteristics(
    characteristics: Sequence[Characteristic],
    *,
    part: str,
    revision: str,
    previous: CharacteristicRegister | None = None,
) -> AccountabilityTable:
    """Number each characteristic, keeping every number ``previous`` gave.

    A characteristic ``previous`` numbered keeps its number; a new one takes the next
    number never used; one ``previous`` numbered that is gone is retired, and its number
    stays in the register so it is never reused. ``previous`` must be the same part's.
    """
    characteristics = each_one(characteristics, Characteristic, named="characteristics")
    for name, value in (("part", part), ("revision", revision)):
        if not isinstance(value, str) or not value.strip():
            raise _refuse(f"{name} names what the register is for", subject=name)
    if previous is not None:
        if not isinstance(previous, CharacteristicRegister):
            raise _refuse("previous must be a CharacteristicRegister", subject="previous",
                          source=_REGISTER_SOURCE)  # fmt: skip
        if previous.part != part:
            raise _refuse(f"previous is the register of {previous.part!r}, not {part!r}",
                          subject="previous", source=_REGISTER_SOURCE)  # fmt: skip
        if previous.revision == revision:
            raise _refuse(f"previous is already revision {revision!r}; number a new revision "
                          "against the last one", subject="revision")  # fmt: skip
    ids = [c.id for c in characteristics]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    if twice:
        raise _refuse(f"characteristics {twice} are listed twice", subject="characteristics")
    numbers = dict(previous.numbers) if previous is not None else {}
    following = max(numbers.values(), default=0) + 1
    added = []
    for c in characteristics:
        if c.id not in numbers:
            numbers[c.id] = following
            added.append(following)
            following += 1
    current = set(ids)
    retired = sorted(n for i, n in numbers.items() if i not in current)
    rows = sorted((NumberedCharacteristic(number=numbers[c.id], characteristic=c)
                   for c in characteristics), key=lambda row: row.number)  # fmt: skip
    return AccountabilityTable(
        rows=tuple(rows), added=tuple(added),
        retired=tuple(retired),
        numbering=CharacteristicRegister(part=part, revision=revision, numbers=numbers),
    )  # fmt: skip


class ControlPlanSeed(ItemCollection, StatableModel):
    """The control-plan rows design hands to manufacturing: one per special characteristic.

    The design columns are filled; the process columns are the plant's and are empty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[tuple[str, ...], ...]

    def to_csv(self) -> str:
        """The seed as CSV, in :data:`CONTROL_PLAN_COLUMNS` order. A cell a spreadsheet
        would read as a formula is written as text."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(CONTROL_PLAN_COLUMNS)
        for row in self.rows:
            writer.writerow(_safe(row))
        return out.getvalue()

    def to_xlsx(self) -> bytes:
        """The seed as an XLSX workbook with one sheet."""
        from .margin_of_safety import _workbook

        rows = [list(CONTROL_PLAN_COLUMNS), *(_safe(row) for row in self.rows)]
        return _workbook((("Control plan seed", rows, {0}),))

    def __str__(self) -> str:
        return f"control-plan seed: {len(self.rows)} special characteristic(s)"


#: The suggested method per frame type: what usually measures it, never a requirement.
_FORM = {"straightness", "flatness", "circularity", "cylindricity"}


def _method(c: Characteristic) -> str:
    if c.kind is CharacteristicKind.DIMENSION:
        return "variable gauge sized to the tolerance (micrometer, bore gauge or CMM)"
    if c.kind is CharacteristicKind.GEOMETRIC_TOLERANCE:
        if c.detail in _FORM:
            return f"{c.detail} by CMM or form tester; no datum"
        return f"{c.detail} by CMM against the datums named in the frame"
    if c.kind is CharacteristicKind.NOTE:
        return "process record or certificate of conformance to the note"
    return "material certificate, or a test coupon from the same lot"


def control_plan_seed(table: AccountabilityTable, *, scorecard: Any = None) -> ControlPlanSeed:
    """The control-plan seed for the special characteristics of ``table``.

    Each row carries the characteristic's number, description, specification, tolerance,
    special class and symbol, the check that governs it, and a suggested measurement
    method; process step, machine, sample size, frequency, control method and reaction
    plan are left empty for the plant. With ``scorecard``, the governing check's status is
    named beside it, and a mark naming a check the card does not hold is refused. An
    unmarked characteristic has no row.
    """
    from .scorecard import Scorecard

    if not isinstance(table, AccountabilityTable):
        raise _refuse("table must be an AccountabilityTable from number_characteristics",
                      subject="table")  # fmt: skip
    if scorecard is not None and not isinstance(scorecard, Scorecard):
        raise _refuse("scorecard must be a Scorecard", subject="scorecard")
    status = {e.name: e.status.value for e in scorecard.entries} if scorecard else {}
    rows = []
    for numbered in table.rows:
        c = numbered.characteristic
        if c.special is None:
            continue
        check = c.check
        if check and scorecard is not None:
            if check not in status:
                raise _refuse(f"the mark on {c.description} names check {check!r}, which is "
                              f"not on the card ({sorted(status)})", subject="marks")  # fmt: skip
            check = f"{check} ({status[check]})"
        specification = c.nominal or "as the drawing callout states"
        rows.append((str(numbered.number), c.description, specification, c.tolerance,
                     c.special.value, c.symbol, check, _method(c),
                     "", "", "", "", "", ""))  # fmt: skip
    return ControlPlanSeed(rows=tuple(rows))
