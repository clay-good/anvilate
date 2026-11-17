"""Traceability: each requirement to the checks, tests and evidence that address it.

A requirements tool holds the requirements; Anvilate holds the checks and the
verification plan. What sits between them in most programs is a spreadsheet somebody
keeps by hand, and the rows it loses are exactly the two a reviewer asks about first: a
requirement nothing checks, and a check no requirement asked for.

You declare each :class:`Requirement` with the names of the checks or verification
items that address it. :func:`trace_requirements` follows every name into the scorecard
and the plan, carries a check to the test items standing behind it and a test item to its
recorded outcome, and reports three things it will not smooth over:

- a requirement nothing addresses is **uncovered**;
- a check no requirement names is **untraced**;
- a name that is neither a check nor a test item is **refused**, because a trace to
  something that does not exist reads as coverage and is none.

Coverage is not a verdict. A requirement traced to a failing check is covered and fails;
the row carries the worst status of what addresses it, and whether any evidence was
recorded.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import date

from pydantic import ConfigDict, Field

from ._models import Named, Provenance, StatableModel, each_one
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard, _status_rank
from .verification import VerificationPlan

__all__ = [
    "REQIF_NAMESPACE",
    "TRACE_COLUMNS",
    "Requirement",
    "TraceRow",
    "TraceReport",
    "trace_requirements",
]

_SOURCE = "the requirement set and the checks and tests it names"

#: The trace's CSV columns, in order: one row per requirement.
TRACE_COLUMNS = (
    "requirement",
    "text",
    "source",
    "coverage",
    "status",
    "checks",
    "verification items",
    "evidence",
)


class _TraceInputError(RefusalError, ValueError):
    """A trace input that cannot be used without correction."""


def _refuse(message: str, *, subject: str) -> _TraceInputError:
    return _TraceInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=_SOURCE),)
    )


class Requirement(StatableModel):
    """One requirement, where it comes from, and what addresses it, by name.

    ``addressed_by`` names checks on the scorecard or items of the verification plan.
    Empty is allowed and is the point: the requirement is then reported uncovered rather
    than left out.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    text: Named
    source: Provenance
    addressed_by: tuple[Named, ...] = Field(default=(), max_length=256)


class TraceRow(StatableModel):
    """One requirement traced: what addresses it, and what that comes to.

    ``coverage`` is ``uncovered`` when nothing addresses it, ``covered`` when something
    does. ``status`` is the worst status of the checks and test items that address it, or
    ``not_evaluated`` when nothing does. ``evidence`` is each recorded outcome, as the test
    item's name and its verdict; a test with no outcome is not evidence and is not listed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    requirement: Named
    text: Named
    source: Provenance
    coverage: str = Field(pattern=r"^(covered|uncovered)$")
    status: CheckStatus
    checks: tuple[Named, ...] = ()
    verification_items: tuple[Named, ...] = ()
    evidence: tuple[str, ...] = ()

    def __str__(self) -> str:
        addressed = ", ".join((*self.checks, *self.verification_items)) or "nothing"
        proof = f"; evidence: {', '.join(self.evidence)}" if self.evidence else "; no evidence"
        return (f"{self.requirement} [{self.coverage}, {self.status.value}]: {self.text} "
                f"— addressed by {addressed}{proof}")  # fmt: skip


class TraceReport(StatableModel):
    """Every requirement traced, and every check no requirement names."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[TraceRow, ...]
    untraced_checks: tuple[Named, ...] = ()

    @property
    def uncovered(self) -> tuple[str, ...]:
        """The requirements nothing addresses."""
        return tuple(row.requirement for row in self.rows if row.coverage == "uncovered")

    def to_csv(self) -> str:
        """The trace as CSV, one row per requirement, then one per untraced check.

        An untraced check is a row with no requirement and coverage ``untraced``, so a
        requirements tool importing the file sees it rather than losing it. A cell a
        spreadsheet would read as a formula is written as text.
        """
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(TRACE_COLUMNS)
        for row in self.rows:
            writer.writerow(_safe((row.requirement, row.text, row.source, row.coverage,
                                   row.status.value, "; ".join(row.checks),
                                   "; ".join(row.verification_items),
                                   "; ".join(row.evidence))))  # fmt: skip
        for check in self.untraced_checks:
            writer.writerow(_safe(("", "", "", "untraced", "", check, "", "")))
        return out.getvalue()

    def to_reqif(self, *, as_of: date, title: str) -> str:
        """The trace as a ReqIF 1.2 document (OMG ReqIF 20110401), for a requirements tool.

        Each requirement is a ``SPEC-OBJECT`` whose ``ReqIF.ForeignID`` is its id and
        whose string attributes carry its text, source, coverage, status, checks, test
        items and evidence, so an uncovered requirement arrives marked uncovered. The
        untraced checks are a second specification of their own, so they are not lost in
        the crossing. ``as_of`` stamps the header's creation time and every element's last
        change: the document carries no clock, and the same trace on the same day is the
        same bytes.
        """
        if not isinstance(as_of, date):
            raise _refuse("as_of must be a date", subject="as_of")
        if not isinstance(title, str) or not title.strip():
            raise _refuse("title names the document", subject="title")
        return _reqif(self, stamp=f"{as_of.isoformat()}T00:00:00Z", title=title)

    def __str__(self) -> str:
        loose = (f"; untraced checks: {', '.join(self.untraced_checks)}"
                 if self.untraced_checks else "")  # fmt: skip
        open_ = f"; uncovered: {', '.join(self.uncovered)}" if self.uncovered else ""
        return f"{len(self.rows)} requirement(s) traced{open_}{loose}"


_FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _safe(cells: Sequence[str]) -> list[str]:
    return [("'" + c) if c.startswith(_FORMULA_LEADS) else c for c in cells]


def trace_requirements(
    requirements: Sequence[Requirement],
    *,
    scorecard: Scorecard,
    plan: VerificationPlan | None = None,
) -> TraceReport:
    """Each requirement traced to the checks, test items and evidence that address it.

    A name in ``addressed_by`` is a check on ``scorecard`` or an item of ``plan``. A check
    brings the test items whose driving checks include it; a test item brings its
    recorded outcome. A name that is neither is refused, naming what the card and the
    plan do hold. A check on the card that no requirement names, directly, is untraced.
    """
    requirements = each_one(requirements, Requirement, named="requirements")
    if not isinstance(scorecard, Scorecard):
        raise _refuse("scorecard must be a Scorecard", subject="scorecard")
    if plan is not None and not isinstance(plan, VerificationPlan):
        raise _refuse("plan must be a VerificationPlan from plan_verification", subject="plan")
    ids = [r.id for r in requirements]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    if twice:
        raise _refuse(f"requirements {twice} are declared twice", subject="requirements")
    checks = {entry.name: entry for entry in scorecard.entries}
    items = {item.name: item for item in (plan.items if plan is not None else ())}
    rows, named = [], set()
    for requirement in requirements:
        unknown = [n for n in requirement.addressed_by if n not in checks and n not in items]
        if unknown:
            held = ", ".join(sorted({*checks, *items}))
            raise _refuse(f"requirement {requirement.id} names {unknown}, which are neither "
                          f"checks on the card nor items of the plan ({held})",
                          subject="requirements")  # fmt: skip
        direct = [n for n in requirement.addressed_by if n in checks]
        named.update(direct)
        tests = [n for n in requirement.addressed_by if n in items]
        tests += [item.name for item in items.values() if item.name not in tests
                  and any(check in item.driving_checks for check in direct)]  # fmt: skip
        statuses = [checks[n].status for n in direct] + [items[n].status for n in tests]
        status = (max(statuses, key=_status_rank) if statuses
                  else CheckStatus.NOT_EVALUATED)  # fmt: skip
        evidence = tuple(f"{n}: {items[n].status.value}" for n in tests
                         if items[n].outcome is not None)  # fmt: skip
        rows.append(TraceRow(
            requirement=requirement.id, text=requirement.text, source=requirement.source,
            coverage="covered" if (direct or tests) else "uncovered", status=status,
            checks=tuple(direct), verification_items=tuple(tests), evidence=evidence,
        ))  # fmt: skip
    untraced = tuple(name for name in checks if name not in named)
    return TraceReport(rows=tuple(rows), untraced_checks=untraced)


# --- ReqIF -----------------------------------------------------------------------------------

#: The namespace of ReqIF 1.2, as OMG publishes its schema.
REQIF_NAMESPACE = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"

#: Each string attribute a requirement carries into ReqIF, by its LONG-NAME. The first two
#: are the names requirements tools read by convention (the ReqIF Implementation Guide's
#: ``ReqIF.ForeignID`` and ``ReqIF.Text``); the rest are this trace's own.
_REQIF_ATTRIBUTES = ("ReqIF.ForeignID", "ReqIF.Text", "Source", "Coverage", "Status",
                     "Checks", "Verification items", "Evidence")  # fmt: skip


def _reqif(report: TraceReport, *, stamp: str, title: str) -> str:
    ET.register_namespace("", REQIF_NAMESPACE)

    def tag(name: str) -> str:
        return f"{{{REQIF_NAMESPACE}}}{name}"

    def sub(parent: ET.Element, name: str, text: str | None = None, **attrs: str) -> ET.Element:
        element = ET.SubElement(
            parent, tag(name), {k.replace("_", "-"): v for k, v in attrs.items()}
        )
        if text is not None:
            element.text = text
        return element

    def identified(parent: ET.Element, name: str, identifier: str, **attrs: str) -> ET.Element:
        return sub(parent, name, IDENTIFIER=identifier, LAST_CHANGE=stamp, **attrs)

    root = ET.Element(tag("REQ-IF"))
    header = sub(sub(root, "THE-HEADER"), "REQ-IF-HEADER", IDENTIFIER="header")
    sub(header, "CREATION-TIME", stamp)
    sub(header, "REQ-IF-TOOL-ID", "Anvilate")
    sub(header, "REQ-IF-VERSION", "1.0")  # fixed by the schema, and in this order
    sub(header, "SOURCE-TOOL-ID", "Anvilate requirement trace")
    sub(header, "TITLE", title)
    content = sub(sub(root, "CORE-CONTENT"), "REQ-IF-CONTENT")
    identified(sub(content, "DATATYPES"), "DATATYPE-DEFINITION-STRING", "dt-string",
               LONG_NAME="String", MAX_LENGTH="32000")  # fmt: skip
    types = sub(content, "SPEC-TYPES")
    object_type = identified(types, "SPEC-OBJECT-TYPE", "type-requirement",
                             LONG_NAME="Traced requirement")  # fmt: skip
    attributes = sub(object_type, "SPEC-ATTRIBUTES")
    for index, name in enumerate(_REQIF_ATTRIBUTES):
        definition = identified(attributes, "ATTRIBUTE-DEFINITION-STRING", f"attr-{index}",
                                LONG_NAME=name)  # fmt: skip
        sub(sub(definition, "TYPE"), "DATATYPE-DEFINITION-STRING-REF", "dt-string")
    identified(types, "SPECIFICATION-TYPE", "type-specification", LONG_NAME="Trace")
    objects = sub(content, "SPEC-OBJECTS")
    rows = [(row.requirement, row.text, row.source, row.coverage, row.status.value,
             "; ".join(row.checks), "; ".join(row.verification_items),
             "; ".join(row.evidence)) for row in report.rows]  # fmt: skip
    loose = [(check, "", "", "untraced", "", check, "", "") for check in report.untraced_checks]
    specifications = sub(content, "SPECIFICATIONS")
    for key, label, group in (("req", title, rows), ("untraced", "Untraced checks", loose)):
        hierarchy = None
        if group:
            specification = identified(specifications, "SPECIFICATION", f"spec-{key}",
                                       LONG_NAME=label)  # fmt: skip
            sub(sub(specification, "TYPE"), "SPECIFICATION-TYPE-REF", "type-specification")
            hierarchy = sub(specification, "CHILDREN")
        for number, cells in enumerate(group, start=1):
            identifier = f"{key}-{number}"
            spec_object = identified(objects, "SPEC-OBJECT", identifier, LONG_NAME=cells[0])
            values = sub(spec_object, "VALUES")
            for index, cell in enumerate(cells):
                value = sub(values, "ATTRIBUTE-VALUE-STRING", THE_VALUE=cell)
                sub(sub(value, "DEFINITION"), "ATTRIBUTE-DEFINITION-STRING-REF", f"attr-{index}")
            sub(sub(spec_object, "TYPE"), "SPEC-OBJECT-TYPE-REF", "type-requirement")
            node = identified(hierarchy, "SPEC-HIERARCHY", f"node-{identifier}")  # type: ignore[arg-type]
            sub(sub(node, "OBJECT"), "SPEC-OBJECT-REF", identifier)
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"
