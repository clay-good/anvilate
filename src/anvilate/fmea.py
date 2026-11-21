"""Design FMEA rows from the design's own evidence, rated on open scales or yours.

A design FMEA is a table an engineer fills by hand from analysis already done: for each
function, the ways it fails, what prevents each (the checks), and what would catch it
before release (the tests). Anvilate holds both halves. :func:`fmea` writes one row per
failure mode the catalogue applies to the item, links each row to the checks and the
verification items it names, and rates it:

- **Severity is yours.** It depends on what the failure does to the system and to people,
  which a part-level screen cannot know, so it is never inferred. A row with no declared
  severity has no priority, and says that is why.
- **Occurrence and detection** are rated on Anvilate's own published scales,
  :data:`OCCURRENCE_SCALE` and :data:`DETECTION_SCALE`: each rank is a band of evidence
  (how much margin the addressing checks hold; how strong the verification behind them
  is), with the derivation written beside it. Or load your organization's ranks for the
  same bands with :func:`load_rating_scale`.
- **Action priority** comes only from a matrix you load, with its source
  (:func:`load_action_priority`). The handbook tables most programs use are licensed;
  none is shipped, and with none loaded the priority is not evaluated.

The rows are only as complete as the failure-mode catalogue, which is a floor and never an
exhaustive list; every rendering says so. Extend it with your own modes
(:meth:`~anvilate.failure_modes.ModeCatalog.extended`) for the item's own functions.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ._models import FrozenMap, Named, Provenance, StatableModel, each_one
from .failure_modes import CATALOG_IS_A_FLOOR, DiscoveryStage, ModeCatalog, coverage
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .verification import VerificationArchetype, VerificationMethod, VerificationPlan

__all__ = [
    "FMEA_COLUMNS",
    "OCCURRENCE_BANDS",
    "DETECTION_BANDS",
    "OCCURRENCE_SCALE",
    "DETECTION_SCALE",
    "RatingScale",
    "PriorityRule",
    "ActionPriorityMatrix",
    "FmeaDeclaration",
    "FmeaRow",
    "FmeaReport",
    "fmea",
    "load_rating_scale",
    "load_action_priority",
]

_M = TypeVar("_M", bound=BaseModel)

_SOURCE = "the FMEA inputs: the failure-mode catalogue, the card, the plan and your ratings"
_SCALE_SOURCE = "your organization's rating table, one rank per band, with its source"
_MATRIX_SOURCE = "your organization's action-priority matrix, with its source"

#: The FMEA's columns, in order: one row per failure mode.
FMEA_COLUMNS = (
    "item",
    "function",
    "failure mode",
    "effect",
    "severity",
    "cause / mechanism",
    "prevention controls",
    "occurrence",
    "occurrence basis",
    "detection controls",
    "detection",
    "detection basis",
    "action priority",
    "discovery stage",
    "citation",
)

#: Each occurrence band: the evidence it stands for. The margin is the worst, over the
#: checks that ran and address the mode, of the computed safety factor over the required.
OCCURRENCE_BANDS: dict[str, str] = {
    "unaddressed": "no check that ran addresses the mode: nothing bounds how often it occurs",
    "check-fails": "a check addressing the mode fails: the design as declared is expected to",
    "margin-below-1.1": "the addressing checks pass with less than 10% over the required factor",
    "passed-no-margin": "the addressing checks pass and state no factor to measure margin by",
    "margin-1.1-to-1.5": "the worst addressing check holds 1.1 to 1.5 times the required factor",
    "margin-1.5-to-2": "the worst addressing check holds 1.5 to 2 times the required factor",
    "margin-2-or-more": "every addressing check holds at least twice the required factor",
}

#: Each detection band: the strongest verification behind the mode.
DETECTION_BANDS: dict[str, str] = {
    "test-recorded": "a test item on the plan has a recorded outcome",
    "test-planned": "a test or demonstration on the plan reaches the mode, not yet run",
    "inspection-planned": "only an inspection on the plan reaches the mode, not yet run",
    "test-named": "the catalogue names a physical test for the mode; the plan holds none",
    "analysis-only": "a check that ran addresses the mode; no physical verification does",
    "none": "nothing on the card or the plan would catch the mode before release",
}


class _FmeaInputError(RefusalError, ValueError):
    """An FMEA input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str = _SOURCE) -> _FmeaInputError:
    return _FmeaInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class RatingScale(StatableModel):
    """One rank from 1 to 10 for every band of one kind, and where the ranks come from.

    ``kind`` is ``occurrence`` or ``detection``; ``ranks`` must give every band of that kind
    (:data:`OCCURRENCE_BANDS` or :data:`DETECTION_BANDS`) and nothing else, so a row can
    never fall into a band the scale is silent on.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(pattern=r"^(occurrence|detection)$")
    source: Provenance
    ranks: FrozenMap[str, int]

    @model_validator(mode="after")
    def _complete(self) -> RatingScale:
        bands = OCCURRENCE_BANDS if self.kind == "occurrence" else DETECTION_BANDS
        missing = sorted(set(bands) - set(self.ranks))
        unknown = sorted(set(self.ranks) - set(bands))
        if missing or unknown:
            raise _refuse(
                f"a {self.kind} scale ranks every band and only those: missing {missing}, "
                f"unknown {unknown}; the bands are {list(bands)}",
                subject="ranks", source=_SCALE_SOURCE,
            )  # fmt: skip
        off = sorted(band for band, rank in self.ranks.items()
                     if isinstance(rank, bool) or not 1 <= rank <= 10)  # fmt: skip
        if off:
            raise _refuse(f"ranks run from 1 to 10; {off} do not", subject="ranks",
                          source=_SCALE_SOURCE)  # fmt: skip
        return self


_ANVILATE = (
    "Anvilate's published FMEA scale (the Quality artifacts docs page, Rating scales): its own "
    "bands of evidence, not a reproduction of any handbook table"
)

#: Anvilate's own occurrence ranks. The derivation: a failing check is as likely as an
#: unchecked mode is unknown (10); a pass with under 10% to spare sits within the scatter of
#: material and load, so it is closer to a failure than to a comfortable pass (7); a pass with
#: no stated factor cannot be told from a thin one (6); each doubling of the factor beyond
#: that steps down. 1 is held back: no check shows a mode cannot occur.
OCCURRENCE_SCALE = RatingScale(kind="occurrence", source=_ANVILATE, ranks={
    "unaddressed": 10, "check-fails": 10, "margin-below-1.1": 7, "passed-no-margin": 6,
    "margin-1.1-to-1.5": 5, "margin-1.5-to-2": 3, "margin-2-or-more": 2,
})  # fmt: skip

#: Anvilate's own detection ranks. The derivation: a test run and recorded is the strongest
#: detection a design record holds (2); a planned test catches it only once run (4), an
#: inspection only what can be seen (5); a test the catalogue names and the plan lacks is
#: an intention (7); analysis alone predicts and does not detect (8); nothing is 10. 1 is held
#: back for detection a design record cannot show, such as an error-proofed process.
DETECTION_SCALE = RatingScale(kind="detection", source=_ANVILATE, ranks={
    "test-recorded": 2, "test-planned": 4, "inspection-planned": 5, "test-named": 7,
    "analysis-only": 8, "none": 10,
})  # fmt: skip


class PriorityRule(StatableModel):
    """One cell block of an action-priority matrix: inclusive rank ranges and their label."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: tuple[int, int]
    occurrence: tuple[int, int]
    detection: tuple[int, int]
    priority: Named

    @model_validator(mode="after")
    def _ranges(self) -> PriorityRule:
        for name in ("severity", "occurrence", "detection"):
            low, high = getattr(self, name)
            if not 1 <= low <= high <= 10:
                raise _refuse(f"{name} range {low}-{high} must run low to high within 1 to 10",
                              subject=name, source=_MATRIX_SOURCE)  # fmt: skip
        return self

    def matches(self, severity: int, occurrence: int, detection: int) -> bool:
        return all(low <= rank <= high for rank, (low, high) in (
            (severity, self.severity), (occurrence, self.occurrence),
            (detection, self.detection)))  # fmt: skip


class ActionPriorityMatrix(StatableModel):
    """Your organization's action-priority matrix: every severity, occurrence and detection
    combination given exactly one priority, and the document it comes from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Provenance
    rules: tuple[PriorityRule, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def _total(self) -> ActionPriorityMatrix:
        gaps, doubled = [], []
        for s in range(1, 11):
            for o in range(1, 11):
                for d in range(1, 11):
                    hits = sum(rule.matches(s, o, d) for rule in self.rules)
                    if hits == 0:
                        gaps.append((s, o, d))
                    elif hits > 1:
                        doubled.append((s, o, d))
        if gaps or doubled:
            raise _refuse(
                f"the matrix gives every combination of severity, occurrence and detection "
                f"exactly one priority: {len(gaps)} have none (first {gaps[:3]}), "
                f"{len(doubled)} have more than one (first {doubled[:3]})",
                subject="rules", source=_MATRIX_SOURCE,
            )  # fmt: skip
        return self

    def priority(self, severity: int, occurrence: int, detection: int) -> str:
        return next(r.priority for r in self.rules if r.matches(severity, occurrence, detection))


class FmeaDeclaration(StatableModel):
    """What you declare for one failure mode: its effect on the system, and its severity.

    Both are left blank on the FMEA when not declared, never filled in. ``severity`` runs
    1 to 10 on your organization's severity table, which is yours to name in the export.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: int | None = Field(default=None, ge=1, le=10, strict=True)
    effect: Named | None = None


class FmeaRow(StatableModel):
    """One failure mode of one function, its controls, and its ratings.

    ``prevention_checks`` and ``verification_items`` are the names of the card's checks and
    the plan's items this row rests on, so a reader can follow each control to its entry.
    ``priority`` is ``None`` when it was not evaluated, and ``priority_note`` says why.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Named
    function: Named
    failure_mode: Named
    effect: str = ""
    severity: int | None = None
    cause: Provenance
    prevention_checks: tuple[Named, ...] = ()
    prevention: tuple[str, ...] = ()
    occurrence: int = Field(ge=1, le=10)
    occurrence_basis: Named
    verification_items: tuple[Named, ...] = ()
    detection_controls: tuple[str, ...] = ()
    detection: int = Field(ge=1, le=10)
    detection_basis: Named
    priority: str | None = None
    priority_note: str = ""
    stage: DiscoveryStage
    citation: Provenance

    def cells(self) -> tuple[str, ...]:
        """The row in :data:`FMEA_COLUMNS` order."""
        return (
            self.item, self.function, self.failure_mode, self.effect,
            "" if self.severity is None else str(self.severity), self.cause,
            "; ".join(self.prevention) or "none", str(self.occurrence), self.occurrence_basis,
            "; ".join(self.detection_controls) or "none", str(self.detection),
            self.detection_basis, self.priority if self.priority is not None
            else self.priority_note, self.stage.value, self.citation,
        )  # fmt: skip

    def __str__(self) -> str:
        severity = "S?" if self.severity is None else f"S{self.severity}"
        priority = self.priority if self.priority is not None else self.priority_note
        return (f"{self.failure_mode}: {severity} O{self.occurrence} ({self.occurrence_basis}) "
                f"D{self.detection} ({self.detection_basis}); priority {priority}")  # fmt: skip


class FmeaReport(StatableModel):
    """The FMEA for one item and function, and the sources of every rating it used."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[FmeaRow, ...]
    occurrence_source: Provenance
    detection_source: Provenance
    priority_source: Provenance | None = None

    def sources(self) -> tuple[str, ...]:
        """Where each rating comes from, as the export's footer lines."""
        return (
            "severity: declared by the user per failure mode; never inferred",
            f"occurrence: {self.occurrence_source}",
            f"detection: {self.detection_source}",
            f"action priority: {self.priority_source}" if self.priority_source
            else "action priority: not evaluated, no matrix loaded; none is shipped",
            f"failure modes: {CATALOG_IS_A_FLOOR}",
        )  # fmt: skip

    def to_csv(self) -> str:
        """The FMEA as CSV: a header, one row per failure mode, a blank line, then the
        sources of the ratings. A cell a spreadsheet would read as a formula is text."""
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(FMEA_COLUMNS)
        for row in self.rows:
            writer.writerow(_safe(row.cells()))
        writer.writerow(())
        for line in self.sources():
            writer.writerow(_safe((line,)))
        return out.getvalue()

    def to_xlsx(self) -> bytes:
        """The FMEA as an XLSX workbook: the rows, and a second sheet with the sources."""
        from .margin_of_safety import _workbook

        numeric = {FMEA_COLUMNS.index(c) for c in ("severity", "occurrence", "detection")}
        rows = [list(FMEA_COLUMNS), *(_safe(row.cells()) for row in self.rows)]
        sources = [["source"], *([line] for line in _safe(self.sources()))]
        return _workbook((("DFMEA", rows, numeric), ("Rating sources", sources, set())))

    def __str__(self) -> str:
        unrated = sum(row.severity is None for row in self.rows)
        lines = [f"FMEA: {len(self.rows)} failure mode row(s); {unrated} without a severity"]
        lines.extend(f"  {row}" for row in self.rows)
        lines.extend(f"  {line}" for line in self.sources())
        return "\n".join(lines)


_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _safe(cells: Sequence[str]) -> list[str]:
    return [("'" + c) if c.startswith(_FORMULA_LEADS) else c for c in cells]


def _occurrence_band(entry: ScorecardEntry) -> str:
    if entry.status is CheckStatus.FAIL:
        return "check-fails"
    computed, required = entry.safety_factor, entry.required_safety_factor
    if computed is None or not required:
        return "passed-no-margin"
    ratio = computed / required
    if ratio < 1.1:
        return "margin-below-1.1"
    if ratio < 1.5:
        return "margin-1.1-to-1.5"
    return "margin-1.5-to-2" if ratio < 2.0 else "margin-2-or-more"


def fmea(
    card: Scorecard,
    facts: Mapping[str, object],
    *,
    item: str,
    function: str,
    plan: VerificationPlan | None = None,
    catalog: ModeCatalog | None = None,
    archetypes: Sequence[VerificationArchetype] = (),
    declared: Mapping[str, FmeaDeclaration] | None = None,
    occurrence_scale: RatingScale = OCCURRENCE_SCALE,
    detection_scale: RatingScale = DETECTION_SCALE,
    priority_matrix: ActionPriorityMatrix | None = None,
) -> FmeaReport:
    """One FMEA row per failure mode the catalogue applies to ``facts``.

    The modes, and the checks that address each, come from
    :func:`~anvilate.failure_modes.coverage` over ``card``: prevention controls are those
    checks, with their status. Detection controls are the items of ``plan`` standing behind
    those checks, then any physical test the catalogue names for the mode. ``declared``
    gives a mode's effect and severity by its id; a mode not declared is left without
    either, and its priority is not evaluated. A declaration for a mode with no row is
    refused: it would otherwise vanish from the record.
    """
    if not isinstance(card, Scorecard):
        raise _refuse("card must be a Scorecard", subject="card")
    if plan is not None and not isinstance(plan, VerificationPlan):
        raise _refuse("plan must be a VerificationPlan from plan_verification", subject="plan")
    for name, value in (("item", item), ("function", function)):
        if not isinstance(value, str) or not value.strip():
            raise _refuse(f"{name} names what the FMEA is about", subject=name)
    for kind, scale in (("occurrence", occurrence_scale), ("detection", detection_scale)):
        if not isinstance(scale, RatingScale) or scale.kind != kind:
            raise _refuse(f"{kind}_scale must be a {kind} RatingScale", subject=f"{kind}_scale")
    if priority_matrix is not None and not isinstance(priority_matrix, ActionPriorityMatrix):
        raise _refuse("priority_matrix must be an ActionPriorityMatrix from "
                      "load_action_priority", subject="priority_matrix")  # fmt: skip
    supplied = each_one(archetypes, VerificationArchetype, named="archetypes")
    report = coverage(card, facts, catalog=catalog, archetypes=supplied)
    declared = dict(declared or {})
    modes = [entry.mode.id for entry in report.entries]
    stray = sorted(set(declared) - set(modes))
    if stray:
        raise _refuse(f"declared names {stray}, which are not failure modes applying to this "
                      f"item ({modes})", subject="declared")  # fmt: skip
    entries = {entry.name: entry for entry in card.entries}
    items = plan.items if plan is not None else ()
    rows = []
    for mode_coverage in report.entries:
        mode = mode_coverage.mode
        said = declared.get(mode.id) or FmeaDeclaration()
        if not isinstance(said, FmeaDeclaration):
            raise _refuse(f"declared[{mode.id!r}] must be an FmeaDeclaration", subject="declared")
        checks = [entries[name] for name in mode_coverage.checks]
        rated = [e for e in checks if e.status is not CheckStatus.OUT_OF_DEPTH]
        bands = [_occurrence_band(e) for e in rated] or ["unaddressed"]
        occurrence_basis = max(bands, key=lambda band: occurrence_scale.ranks[band])
        tests = [i for i in items if set(i.driving_checks) & set(mode_coverage.checks)]
        if any(i.outcome is not None for i in tests):
            detection_basis = "test-recorded"
        elif any(i.archetype.method in (VerificationMethod.TEST, VerificationMethod.DEMONSTRATION)
                 for i in tests):  # fmt: skip
            detection_basis = "test-planned"
        elif any(i.archetype.method is VerificationMethod.INSPECTION for i in tests):
            detection_basis = "inspection-planned"
        elif mode_coverage.tests:
            detection_basis = "test-named"
        else:
            detection_basis = "analysis-only" if checks else "none"
        occurrence = occurrence_scale.ranks[occurrence_basis]
        detection = detection_scale.ranks[detection_basis]
        missing = [what for what, absent in (("a severity, which only you can give",
                                              said.severity is None),
                                             ("an action-priority matrix; none is shipped",
                                              priority_matrix is None)) if absent]  # fmt: skip
        priority = None
        if not missing:
            priority = priority_matrix.priority(said.severity, occurrence, detection)  # type: ignore[union-attr,arg-type]
        rows.append(FmeaRow(
            item=item, function=function, failure_mode=mode.id, effect=said.effect or "",
            severity=said.severity, cause=mode.description,
            prevention_checks=tuple(e.name for e in checks),
            prevention=tuple(f"{e.name} ({e.status.value})" for e in checks),
            occurrence=occurrence, occurrence_basis=occurrence_basis,
            verification_items=tuple(i.name for i in tests),
            detection_controls=(*(f"{i.name} ({i.status.value})" for i in tests),
                                *(f"{t} (named, not on the plan)" for t in mode_coverage.tests
                                  if not tests)),
            detection=detection, detection_basis=detection_basis, priority=priority,
            priority_note=("not evaluated — needs " + " and ".join(missing)) if missing else "",
            stage=mode.stage, citation=mode.citation,
        ))  # fmt: skip
    return FmeaReport(
        rows=tuple(rows), occurrence_source=occurrence_scale.source,
        detection_source=detection_scale.source,
        priority_source=priority_matrix.source if priority_matrix is not None else None,
    )  # fmt: skip


def _built(model: type[_M], **fields: object) -> _M:
    """``model(**fields)``, raising a refusal its validator raised as itself, not wrapped."""
    try:
        return model(**fields)
    except ValidationError as error:
        for detail in error.errors():
            cause = (detail.get("ctx") or {}).get("error")
            if isinstance(cause, RefusalError):
                raise cause from None
        raise


def _read_csv(text: str, *, columns: tuple[str, ...], source: str, what: str) -> list[dict]:
    if not isinstance(text, str) or not text.strip():
        raise _refuse(f"the {what} is empty; give the {what} as CSV text with columns "
                      f"{list(columns)}",
                      subject="text", source=source)  # fmt: skip
    if not isinstance(source, str) or not source.strip():
        raise _refuse(f"name the document the {what} comes from: a loaded table with no "
                      "source cannot be named in the export", subject="source",
                      source=f"the document the {what} comes from")  # fmt: skip
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = tuple((name or "").strip().lower() for name in (reader.fieldnames or ()))
    if header != columns:
        raise _refuse(f"the {what}'s header is {list(header)}; it must be {list(columns)}",
                      subject="text", source=source)  # fmt: skip
    rows = []
    for line, raw in enumerate(reader, start=2):
        cells = {name.strip().lower(): (value or "").strip() for name, value in raw.items()
                 if name is not None}  # fmt: skip
        if None in raw or any(not cells[c] for c in columns):
            raise _refuse(f"line {line} of the {what} must fill each of {list(columns)} once",
                          subject="text", source=source)  # fmt: skip
        rows.append({"line": line, **cells})
    return rows


def _rank(cell: str, *, line: int, column: str, source: str) -> tuple[int, int]:
    low, _, high = cell.partition("-")
    try:
        bounds = (int(low), int(high or low))
    except ValueError:
        raise _refuse(f"line {line}: {column} {cell!r} is a rank 1 to 10 or a range such as "
                      "'4-6'", subject="text", source=source) from None  # fmt: skip
    return bounds


def load_rating_scale(text: str, *, kind: str, source: str) -> RatingScale:
    """Your organization's ranks for Anvilate's bands, from CSV with columns ``band, rank``.

    ``kind`` is ``occurrence`` or ``detection``. Every band of that kind must be ranked
    exactly once: your table decides what each band of evidence is worth to you, and the
    bands stay Anvilate's, because they are what the design record can show.
    """
    if kind not in ("occurrence", "detection"):
        raise _refuse(f"kind is 'occurrence' or 'detection', not {kind!r}", subject="kind",
                      source=_SCALE_SOURCE)  # fmt: skip
    rows = _read_csv(text, columns=("band", "rank"), source=source, what=f"{kind} scale")
    bands = [row["band"] for row in rows]
    twice = sorted({b for b in bands if bands.count(b) > 1})
    if twice:
        raise _refuse(f"bands {twice} are ranked twice", subject="text", source=source)
    ranks = {}
    for row in rows:
        low, high = _rank(row["rank"], line=row["line"], column="rank", source=source)
        if low != high:
            raise _refuse(f"line {row['line']}: a band takes one rank, not a range",
                          subject="text", source=source)  # fmt: skip
        ranks[row["band"]] = low
    return _built(RatingScale, kind=kind, source=source, ranks=ranks)


def load_action_priority(text: str, *, source: str) -> ActionPriorityMatrix:
    """Your organization's action-priority matrix, from CSV with columns
    ``severity, occurrence, detection, priority``.

    Each rank cell is one rank or an inclusive range (``7-8``); ``priority`` is your label,
    such as ``H``. Every one of the 1,000 combinations must get exactly one priority, so no
    row of the FMEA can fall through the table. ``source`` names the document the matrix
    comes from, and the export names it.
    """
    columns = ("severity", "occurrence", "detection", "priority")
    rows = _read_csv(text, columns=columns, source=source, what="action-priority matrix")
    rules = []
    for row in rows:
        ranges = {c: _rank(row[c], line=row["line"], column=c, source=source)
                  for c in columns[:3]}  # fmt: skip
        rules.append(_built(PriorityRule, priority=row["priority"], **ranges))
    return _built(ActionPriorityMatrix, source=source, rules=tuple(rules))
