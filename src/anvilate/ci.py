"""Parts as code in CI: findings on the spec's own lines, and a baseline that says what changed.

The CLI's exit codes have always been the interface, and they are the part a merge gate
needs. What a software team takes for granted in the same lane was missing, and it is
exactly what makes a check visible to the people who did not run it.

- **A finding had no line.** A failing check names the field it reads, in prose. A
  reviewer on a pull request saw a red job and a log, not an annotation on the line of
  the spec that caused it. Every linter in the world does better. :func:`source_marks`
  reads the document's own YAML marks, and :func:`locate` puts each finding on the line
  of the field it is about.
- **A dashboard could not count it.** CI systems and quality gates read SARIF 2.1.0 and
  JUnit XML. :func:`to_sarif` and :func:`to_junit` write both, byte-for-byte the same for
  the same cards, because a report whose bytes move on every run is one no cache and no
  diff can use.
- **"Fails" meant two different things.** A repository of forty specs has, on any day,
  some not-evaluated entries that are known and accepted, and one newly failing check
  that is the news. :class:`Baseline` and :func:`compare` separate them.

Three rules this module keeps.

1. **A sweep never writes the baseline.** Comparing against a file that updates itself is
   comparing against nothing. The baseline is written by an explicit flag and committed,
   and a run that compares is a run that only reads.
2. **A baseline entry whose spec is gone is reported, not dropped.** A part deleted and a
   part renamed look identical to a tool and are not the same event to a person.
3. **A pass is not a result.** SARIF carries what somebody has to look at. A passing
   check is not one, and a check the document deliberately deferred is not one either —
   but a warning *is*, because a caution nobody is shown is the silent green this library
   exists to refuse.

Out, by the change that added this: any hosted dashboard or service; GitLab, Azure or
Jenkins plugins (they read these same files); and annotating lines inside a STEP or DXF
that a spec references.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape, quoteattr

import yaml
from pydantic import ConfigDict, model_validator

from ._models import Named, StatableModel, each_one
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard, ScorecardEntry

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from .product import NodeCard

__all__ = [
    "SARIF_VERSION",
    "SARIF_SCHEMA",
    "SARIF_RESULT_LIMIT",
    "SourceMark",
    "source_marks",
    "governing_field",
    "locate",
    "ScreenedSpec",
    "screened",
    "definition_marks",
    "product_specs",
    "BaselineEntry",
    "Baseline",
    "Change",
    "ChangeLine",
    "compare",
    "summary_table",
    "to_sarif",
    "sarif_json",
    "to_junit",
]

#: The SARIF version these documents declare, and the schema a consumer validates against.
SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"
)
#: GitHub code scanning accepts at most this many results in one upload. A caller above
#: this splits rather than truncating, and the number is stated so the split is not magic.
SARIF_RESULT_LIMIT = 5_000

_BASELINE_VERSION = "1.0"
_SOURCE = "the spec document and the card screened from it"


def _refuse(message: str, *, subject: str, source: str = _SOURCE) -> RefusalError:
    return RefusalError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class SourceMark(StatableModel):
    """Where a field is in its document: one-based lines and columns, as editors count.

    PyYAML counts from zero and every consumer of this — SARIF, an editor, a reviewer
    reading a log — counts from one. The conversion happens once, here, rather than at
    each of the places that would each have to remember.
    """

    model_config = ConfigDict(frozen=True)

    path: Named
    line: int
    column: int
    end_line: int
    end_column: int

    @model_validator(mode="after")
    def _one_based(self) -> SourceMark:
        for value, name in (
            (self.line, "line"),
            (self.column, "column"),
            (self.end_line, "end_line"),
            (self.end_column, "end_column"),
        ):
            if value < 1:
                raise _refuse(
                    f"{name} is {value}; a source mark counts from one, as an editor and "
                    f"SARIF both do, and a zero here would annotate the line above",
                    subject=name,
                )
        if self.end_line < self.line:
            raise _refuse(
                f"a mark ends on line {self.end_line} and starts on {self.line}",
                subject="end_line",
            )
        return self

    def __str__(self) -> str:
        return f"{self.path} at line {self.line}, column {self.column}"


def source_marks(text: str) -> dict[str, SourceMark]:
    """Every scalar and collection in a YAML document, by dotted path, with its position.

    Keys are written the way a document writes them and the way a
    :class:`~anvilate.scorecard.Need` names them: ``constraints.min_safety_factor``,
    ``dimensions[2].nominal``. The root is ``""``.

    A separate compose pass rather than a hook in the loader: the strict loader this
    library screens through has its own refusals to make, and threading marks through it
    would entangle two unrelated jobs. The cost is reading the text twice, which is
    nothing beside screening it.

    A document that does not parse yields no marks rather than raising. The caller is on
    its way to a refusal about that document already, and a second exception from the
    annotation layer would replace a message about the YAML with one about the annotator.
    """
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return {}
    if root is None:
        return {}
    marks: dict[str, SourceMark] = {}

    def visit(node: yaml.Node, path: str) -> None:
        start, end = node.start_mark, node.end_mark
        marks[path] = SourceMark(
            path=path or "(document)",
            line=start.line + 1,
            column=start.column + 1,
            end_line=max(end.line + 1, start.line + 1),
            end_column=max(end.column + 1, 1),
        )
        if isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                if not isinstance(key_node, yaml.ScalarNode):
                    continue
                child = f"{path}.{key_node.value}" if path else str(key_node.value)
                visit(value_node, child)
        elif isinstance(node, yaml.SequenceNode):
            for index, item in enumerate(node.value):
                visit(item, f"{path}[{index}]")

    visit(root, "")
    return marks


def governing_field(entry: ScorecardEntry) -> str | None:
    """The document field this check is about, written as a document writes it.

    A check that did not run states what it needed, and the first such declaration is the
    field a reader has to go and write. A check that failed states the parameter that
    moves it back into bounds. Neither is a guess from the detail line's prose: both are
    data the screen itself wrote down.

    ``None`` for a check that is about no single field — which is honest, and puts the
    finding on the document rather than on an arbitrary line of it.
    """
    if entry.needs:
        return entry.needs[0].declaration
    if entry.repair_hint is not None:
        return entry.repair_hint.parameter
    return None


#: Where a bare parameter name is looked for when it is not already a document path. A
#: repair hint names a parameter by its stable name — `thickness`, not
#: `element_params.thickness` — because the same hint is read by callers that have no
#: document at all.
_PARAMETER_PREFIXES = ("", "element_params.", "constraints.", "manufacturing.")


def locate(
    entry: ScorecardEntry,
    marks: Mapping[str, SourceMark],
    *,
    anchor: SourceMark | None = None,
) -> SourceMark | None:
    """The mark of this check's governing field, or of the document when it has none.

    A field named but absent from the document is exactly the not-evaluated case — the
    declaration is missing, which is *why* the check did not run — so the finding lands on
    the ``anchor``, or on the document root when there is none. Annotating a line that
    does not mention the field would point a reader at the wrong place with full
    confidence.

    ``anchor`` is where a *product's* findings go: a node of a product document has no
    fields of its own in the file, and its definition's line is the nearest true thing.
    """
    return _located(entry, marks, anchor=anchor)[0]


def _located(
    entry: ScorecardEntry,
    marks: Mapping[str, SourceMark],
    *,
    anchor: SourceMark | None = None,
) -> tuple[SourceMark | None, bool]:
    """:func:`locate`, and whether the mark is the governing field's own.

    The flag decides how much of the file a result highlights. A field's own mark spans
    the field; a fallback — the document, or a product node's definition — is shown as a
    single line, because an annotation covering sixteen lines of a definition block
    highlights everything and says nothing.
    """
    field = governing_field(entry)
    if field is not None:
        for prefix in _PARAMETER_PREFIXES:
            found = marks.get(f"{prefix}{field}")
            if found is not None:
                return found, True
    return (anchor if anchor is not None else marks.get("")), False


class ScreenedSpec(StatableModel):
    """One spec, the card it screened to, and where its fields are in its own text."""

    model_config = ConfigDict(frozen=True)

    path: Named
    name: Named
    card: Scorecard
    marks: tuple[SourceMark, ...] = ()
    #: Where this document's findings go when no field mark applies. Set for a node of a
    #: product document, whose checks are about an item declared elsewhere in the file.
    anchor: SourceMark | None = None
    #: The node of a product document this card belongs to, when it is one. A product
    #: file holds many cards and a baseline keys on one identity per card, so the file
    #: path alone is not enough: every node of one product would collide on it.
    node: Named | None = None

    @property
    def identity(self) -> str:
        """What a baseline records this card under: the file, or the node inside it."""
        return self.path if self.node is None else f"{self.path}#{self.node}"

    @property
    def by_path(self) -> dict[str, SourceMark]:
        """The marks keyed the way :func:`locate` looks them up."""
        return {"" if mark.path == "(document)" else mark.path: mark for mark in self.marks}

    @property
    def digest(self) -> str:
        """A content digest of the card alone, for the baseline.

        The card and **not** the toolchain, which is where this differs from
        :func:`anvilate.review.artifact_digest`. A review that survived a library upgrade
        would be assurance nobody gave, so that digest binds the version. A baseline that
        marked all forty parts changed on every upgrade would drown the one part that
        really changed, which is the whole thing this file exists to surface.
        """
        return hashlib.sha256(self.card.model_dump_json().encode("utf-8")).hexdigest()


def screened(path: str, name: str, card: Scorecard, text: str | None = None) -> ScreenedSpec:
    """A :class:`ScreenedSpec` with the marks read from ``text`` when there is any."""
    marks = source_marks(text) if text else {}
    return ScreenedSpec(
        path=path,
        name=name,
        card=card,
        marks=tuple(marks[key] for key in sorted(marks)),
    )


# --- the baseline -----------------------------------------------------------------


class BaselineEntry(StatableModel):
    """One spec as it stood when the baseline was written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    digest: str
    status: CheckStatus
    governing: str | None = None


class Baseline(StatableModel):
    """The committed record of what every spec in a repository screened to.

    Written by an explicit command and read by a sweep. A sweep never writes one: a
    baseline that updated itself would make every run pass, which is a gate that is not
    one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = _BASELINE_VERSION
    entries: tuple[BaselineEntry, ...] = ()

    @model_validator(mode="after")
    def _one_entry_per_path(self) -> Baseline:
        paths = [entry.path for entry in self.entries]
        doubled = sorted({path for path in paths if paths.count(path) > 1})
        if doubled:
            raise _refuse(
                f"the baseline records {', '.join(doubled)} more than once; two recorded "
                f"states for one spec is two answers to the question a sweep asks",
                subject="entries",
            )
        return self

    @classmethod
    def of(cls, specs: Sequence[ScreenedSpec]) -> Baseline:
        """The baseline these screened specs would be recorded as."""
        specs = each_one(specs, ScreenedSpec, named="specs")
        return cls(
            entries=tuple(
                BaselineEntry(
                    path=spec.identity,
                    digest=spec.digest,
                    status=spec.card.status,
                    governing=(None if (g := spec.card.governing()) is None else g.name),
                )
                for spec in sorted(specs, key=lambda spec: spec.identity)
            )
        )

    def to_json(self) -> str:
        """The baseline as a file: sorted, indented, and the same bytes every time."""
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"

    @classmethod
    def parse(cls, text: str) -> Baseline:
        """Read a committed baseline file."""
        from ._models import parse_json

        try:
            document = parse_json(text)
        except ValueError as bad:
            raise _refuse(
                f"the baseline file is not readable JSON: {bad}",
                subject="the baseline file",
                source="the committed baseline, written by `--write-baseline`",
            ) from None
        # `Baseline` and not `cls`: the census in tests/test_contract.py resolves every
        # `X.model_validate(...)` to the class it reads into, and a `cls` is a hole in it
        # exactly where an unbounded reader could hide.
        return Baseline.model_validate(document)

    def __str__(self) -> str:
        return f"baseline {self.version}: {len(self.entries)} specs"


class Change(StrEnum):
    """What a sweep found about one spec, against the committed baseline."""

    NEWLY_FAILING = "newly_failing"
    NEWLY_NOT_EVALUATED = "newly_not_evaluated"
    NEWLY_PASSING = "newly_passing"
    GOVERNING_CHANGED = "governing_changed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    NEW = "new"
    MISSING = "missing"

    @property
    def is_news(self) -> bool:
        """Whether this is something a merge gate should stop for."""
        return self in _NEWS


#: The changes a gate stops for. ``NEWLY_PASSING`` is deliberately not one — a part that
#: started passing is good news, and failing a run over it teaches people to ignore runs.
#: ``MISSING`` is: a baseline entry whose spec is gone is either a deletion nobody recorded
#: or a rename, and both want a person.
_NEWS = frozenset({Change.NEWLY_FAILING, Change.NEWLY_NOT_EVALUATED, Change.MISSING})


class ChangeLine(StatableModel):
    """One spec's news: what it was, what it is, and which of the two it is reported as."""

    model_config = ConfigDict(frozen=True)

    path: Named
    change: Change
    before: CheckStatus | None = None
    after: CheckStatus | None = None
    detail: str = ""

    def __str__(self) -> str:
        was = self.before.value if self.before is not None else "—"
        now = self.after.value if self.after is not None else "—"
        detail = f" ({self.detail})" if self.detail else ""
        return f"{self.path}: {self.change.value}, {was} -> {now}{detail}"


def compare(baseline: Baseline, specs: Sequence[ScreenedSpec]) -> tuple[ChangeLine, ...]:
    """What changed between the committed baseline and this sweep, path order.

    Every spec gets a line, including the unchanged ones: a table listing only the news
    cannot tell "nothing changed" from "the sweep did not run".
    """
    specs = each_one(specs, ScreenedSpec, named="specs")
    recorded = {entry.path: entry for entry in baseline.entries}
    lines: list[ChangeLine] = []
    for spec in specs:
        was = recorded.pop(spec.identity, None)
        now = spec.card.status
        governing = None if (g := spec.card.governing()) is None else g.name
        if was is None:
            lines.append(
                ChangeLine(
                    path=spec.identity,
                    change=Change.NEW,
                    after=now,
                    detail="no baseline entry for this spec",
                )
            )
            continue
        if was.digest == spec.digest:
            lines.append(
                ChangeLine(
                    path=spec.identity, change=Change.UNCHANGED, before=was.status, after=now
                )
            )
            continue
        change = _classify(was.status, now)
        detail = ""
        if change is Change.CHANGED and was.governing != governing:
            change = Change.GOVERNING_CHANGED
            detail = f"{was.governing or 'nothing'} -> {governing or 'nothing'}"
        lines.append(
            ChangeLine(
                path=spec.identity, change=change, before=was.status, after=now, detail=detail
            )
        )
    for path, entry in recorded.items():
        lines.append(
            ChangeLine(
                path=path,
                change=Change.MISSING,
                before=entry.status,
                detail="the baseline records this spec and the sweep did not find it",
            )
        )
    return tuple(sorted(lines, key=lambda line: line.path))


def _classify(before: CheckStatus, after: CheckStatus) -> Change:
    if after is before:
        return Change.CHANGED
    if after is CheckStatus.FAIL:
        return Change.NEWLY_FAILING
    if after is CheckStatus.NOT_EVALUATED:
        return Change.NEWLY_NOT_EVALUATED
    if before in {CheckStatus.FAIL, CheckStatus.NOT_EVALUATED}:
        return Change.NEWLY_PASSING
    return Change.CHANGED


def summary_table(changes: Sequence[ChangeLine]) -> str:
    """The change table a job summary shows: the news first, then a count of the rest."""
    changes = each_one(changes, ChangeLine, named="changes")
    news = [line for line in changes if line.change.is_news]
    other = [line for line in changes if not line.change.is_news]
    lines = ["| Spec | Change | Was | Now |", "| --- | --- | --- | --- |"]
    for line in (*news, *other):
        was = line.before.value if line.before is not None else "—"
        now = line.after.value if line.after is not None else "—"
        lines.append(f"| `{line.path}` | **{line.change.value}** | {was} | {now} |")
    if not changes:
        lines.append("| _no specs screened_ | | | |")
    counts: dict[Change, int] = {}
    for line in changes:
        counts[line.change] = counts.get(line.change, 0) + 1
    tally = ", ".join(f"{counts[change]} {change.value}" for change in Change if change in counts)
    lines.extend(["", f"{len(changes)} specs: {tally}."])
    if news:
        plural = "is" if len(news) == 1 else "are"
        lines.append(f"{len(news)} of them {plural} news a gate stops for.")
    else:
        lines.append("Nothing a gate stops for.")
    return "\n".join(lines)


# --- SARIF ------------------------------------------------------------------------

#: The SARIF level each verdict reports at. A TOTAL map over `CheckStatus`, and the two
#: ``None``s are deliberate: a pass is not something anyone has to look at, and a check the
#: document *deliberately deferred* is a decision somebody already made.
_SARIF_LEVELS: dict[CheckStatus, str | None] = {
    CheckStatus.PASS: None,
    CheckStatus.FAIL: "error",
    CheckStatus.NOT_EVALUATED: "warning",
    CheckStatus.WARNING: "note",
    CheckStatus.OVER_MARGIN: "note",
    CheckStatus.OUT_OF_DEPTH: None,
}


def _rule_id(entry: ScorecardEntry) -> str:
    """The stable identity a dashboard groups by: the check id where there is one.

    ``check_id`` exists precisely so a module check keeps its identity when the element
    instance in its display name is renamed. A rule keyed on the display name would make
    every rename look like a new rule and an old one gone.
    """
    return entry.check_id or entry.name


def to_sarif(
    specs: Sequence[ScreenedSpec], *, tool_version: str, category: str = "anvilate"
) -> dict:
    """A SARIF 2.1.0 log: one rule per check identity, one result per thing to look at.

    ``partialFingerprints`` is keyed on the spec path and the rule, not on the line, which
    is what partial fingerprints are for: moving a declaration down the file is not a new
    finding, and a de-duplicating consumer should say so.

    ``category`` becomes ``runs[].automationDetails.id``, which is what GitHub code
    scanning reads as the category when an upload does not override it. One category per
    spec set is how two runs over two folders stop overwriting each other's findings.
    """
    if not category.strip():
        raise _refuse(
            "a SARIF category names the spec set this run covers; an empty one makes two "
            "runs over two folders overwrite each other's findings",
            subject="category",
            source="the folder or spec set this run screens",
        )
    specs = each_one(specs, ScreenedSpec, named="specs")
    rules: dict[str, dict] = {}
    results: list[dict] = []
    for spec in specs:
        marks = spec.by_path
        for entry in spec.card.entries:
            level = _SARIF_LEVELS[entry.status]
            if level is None:
                continue
            rule = _rule_id(entry)
            if rule not in rules:
                descriptor: dict = {
                    "id": rule,
                    "name": entry.name,
                    "shortDescription": {"text": entry.name},
                }
                if entry.reference:
                    # The clause as the rule's help: a reviewer who has never seen this
                    # check needs the standard it comes from before anything else.
                    descriptor["help"] = {"text": entry.reference}
                rules[rule] = descriptor
            mark, exact = _located(entry, marks, anchor=spec.anchor)
            region = _region(mark, exact=exact)
            results.append(
                {
                    "ruleId": rule,
                    "level": level,
                    "message": {"text": f"{entry.name}: {entry.detail}"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": spec.path},
                                "region": region,
                            }
                        }
                    ],
                    "partialFingerprints": {
                        "anvilateCheck/v1": hashlib.sha256(
                            f"{spec.path}\x00{rule}".encode()
                        ).hexdigest()[:16]
                    },
                }
            )
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "anvilate",
                        "version": tool_version,
                        "informationUri": "https://github.com/clay-good/anvilate",
                        "rules": [rules[key] for key in sorted(rules)],
                    }
                },
                "automationDetails": {"id": category},
                "results": results,
            }
        ],
    }


def _region(mark: SourceMark | None, *, exact: bool) -> dict:
    """The region a result annotates.

    A finding on a *field* annotates that field's whole span. A finding that fell back to
    the document, or to a product node's definition, annotates its **first line only**:
    the root node runs from line one to the end of the file, and a definition block runs
    for a dozen, and an annotation covering all of it highlights everything in a
    reviewer's diff and says nothing.
    """
    if mark is None:
        return {"startLine": 1}
    if not exact:
        return {"startLine": mark.line, "startColumn": mark.column}
    return {
        "startLine": mark.line,
        "startColumn": mark.column,
        "endLine": mark.end_line,
        "endColumn": mark.end_column,
    }


def sarif_json(
    specs: Sequence[ScreenedSpec], *, tool_version: str, category: str = "anvilate"
) -> str:
    """:func:`to_sarif` as bytes a diff can read: sorted keys, two-space indent, no clock."""
    specs = each_one(specs, ScreenedSpec, named="specs")
    document = to_sarif(specs, tool_version=tool_version, category=category)
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


# --- JUnit ------------------------------------------------------------------------


def to_junit(specs: Sequence[ScreenedSpec]) -> str:
    """A JUnit XML report: one test case per check per spec.

    A not-evaluated check is **skipped**, never a pass. Every reporter in this format
    counts a skip separately and a pass as a pass, and reporting a check that could not
    run as a passing one is the silent green this library exists to refuse.

    No timestamp and no duration: the same cards give the same bytes, so a report can be
    cached, diffed and attached to a content-addressed bundle.
    """
    specs = each_one(specs, ScreenedSpec, named="specs")
    suites: list[str] = []
    totals = {"tests": 0, "failures": 0, "skipped": 0}
    for spec in specs:
        cases: list[str] = []
        counts = {"tests": 0, "failures": 0, "skipped": 0}
        for entry in spec.card.entries:
            counts["tests"] += 1
            case = f"    <testcase classname={quoteattr(spec.name)} name={quoteattr(entry.name)}"
            if entry.status is CheckStatus.FAIL:
                counts["failures"] += 1
                cases.append(
                    f"{case}>\n      <failure message={quoteattr(entry.detail)}>"
                    f"{escape(_case_body(entry))}</failure>\n    </testcase>"
                )
            elif entry.status in {CheckStatus.NOT_EVALUATED, CheckStatus.OUT_OF_DEPTH}:
                counts["skipped"] += 1
                cases.append(
                    f"{case}>\n      <skipped message={quoteattr(entry.detail)}/>\n    </testcase>"
                )
            else:
                cases.append(f"{case}/>")
        for key in totals:
            totals[key] += counts[key]
        suites.append(
            f'  <testsuite name={quoteattr(spec.path)} tests="{counts["tests"]}" '
            f'failures="{counts["failures"]}" skipped="{counts["skipped"]}" errors="0">\n'
            + "\n".join(cases)
            + ("\n" if cases else "")
            + "  </testsuite>"
        )
    header = (
        f'<testsuites tests="{totals["tests"]}" failures="{totals["failures"]}" '
        f'skipped="{totals["skipped"]}" errors="0">'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + header
        + "\n"
        + "\n".join(suites)
        + ("\n" if suites else "")
        + "</testsuites>\n"
    )


def _case_body(entry: ScorecardEntry) -> str:
    """What a failing case says beyond its message: the clause, and the repair if any."""
    parts = [entry.detail]
    if entry.reference:
        parts.append(f"source: {entry.reference}")
    if entry.repair_hint is not None:
        parts.append(f"repair: {entry.repair_hint}")
    return "\n".join(parts)


def definition_marks(text: str) -> dict[str, SourceMark]:
    """Each definition of a product document, by its ``id``, with its position.

    A node of a product has no fields of its own in the file — it is an *instance* of a
    definition, and the definition is the thing a reader edits. So that is where a node's
    findings are annotated.
    """
    try:
        root = yaml.compose(text)
    except yaml.YAMLError:
        return {}
    if not isinstance(root, yaml.MappingNode):
        return {}
    found: dict[str, SourceMark] = {}
    for key_node, value_node in root.value:
        if getattr(key_node, "value", None) != "definitions":
            continue
        if not isinstance(value_node, yaml.SequenceNode):
            continue
        for item in value_node.value:
            if not isinstance(item, yaml.MappingNode):
                continue
            for inner_key, inner_value in item.value:
                if getattr(inner_key, "value", None) != "id":
                    continue
                identifier = getattr(inner_value, "value", None)
                if not isinstance(identifier, str):
                    continue
                found[identifier] = SourceMark(
                    path=f"definitions[{identifier}]",
                    line=item.start_mark.line + 1,
                    column=item.start_mark.column + 1,
                    end_line=max(item.end_mark.line + 1, item.start_mark.line + 1),
                    end_column=max(item.end_mark.column + 1, 1),
                )
    return found


def product_specs(
    path: str,
    text: str,
    card: NodeCard,
    definitions: Mapping[str, str] | None = None,
) -> tuple[ScreenedSpec, ...]:
    """Every node of a product's card as its own :class:`ScreenedSpec`, anchored in the file.

    ``card`` is the product's :class:`~anvilate.product.NodeCard`. ``definitions`` maps a
    node path to the definition id it instantiates; a node with no mapping is anchored on
    the document, which is honest and never on another node's line.
    """
    anchors = definition_marks(text)
    mapping = dict(definitions or {})
    marks = source_marks(text)
    root = marks.get("")
    specs: list[ScreenedSpec] = []

    def walk(node: NodeCard) -> None:
        if node.entries:
            anchor = anchors.get(mapping.get(node.path, ""), root)
            specs.append(
                ScreenedSpec(
                    path=path,
                    name=node.path,
                    card=Scorecard(entries=node.entries),
                    anchor=anchor,
                    node=node.path,
                )
            )
        for child in node.children:
            walk(child)

    walk(card)
    return tuple(specs)
