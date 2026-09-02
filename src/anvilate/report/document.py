"""The submittal-shaped calculation report and its machine-readable calc record.

A reviewer who receives only this document should be able to answer, without
asking: what was checked, against which code editions, under what assumptions,
with what numbers, and which check governs. So the report assembles in that order
— header, standards relied upon, assumptions, then one section per check showing
its worked derivation, then a margin summary naming the governing check, then the
disclaimer that screening is not sign-off.

Two artifacts come out of the same object. :meth:`CalculationReport.to_html` is
what a person reads; :meth:`CalculationReport.to_record` is what a firm's QA script
reads — a versioned JSON structure carrying inputs, symbolic forms, results,
margins, and citations, so every number can be re-verified without parsing the
rendered page.

Rendering is pure Python, offline, and deterministic: nothing is timestamped
inside the document (the date is the caller's to supply), floats render at fixed
precision, and the same report renders byte-identically on every rebuild — so a
diff between two reports is an engineering change, never rendering noise.
"""

from __future__ import annotations

from html import escape
from math import isfinite

from pydantic import BaseModel, ConfigDict, computed_field

from ..derivation import Derivation, SymbolValue
from ..scorecard import CheckStatus, Scorecard, ScorecardEntry
from ..spec.provenance import Origin, Provenanced
from ..units import UnitSystem
from .mathml import formula_to_mathml

__all__ = [
    "CALC_RECORD_SCHEMA_VERSION",
    "SCREENING_DISCLAIMER",
    "ReportSection",
    "CalculationReport",
    "report_from_record",
]

# The calc-record schema version. Bump the minor for additive fields, the major
# for a change that older readers cannot ignore. 1.1 added the optional scorecard
# annotations (repair hint, upper safety-factor band, uncertainty distribution);
# a 1.0 reader ignores them and still loads the record.
CALC_RECORD_SCHEMA_VERSION = "1.1"

SCREENING_DISCLAIMER = (
    "These are closed-form screening calculations, not a substitute for detailed "
    "analysis or design. Every value shown was computed from the inputs recorded "
    "in this document; inputs supplied by the user are marked as such. Engineering "
    "sign-off remains with a qualified engineer."
)

# What an empty standards or assumptions list renders as. Never an omitted heading: a
# reviewer cannot tell a section that was left empty on purpose from one nobody wrote.
_NONE_DECLARED = "none declared"

# How an assumption's origin reads to a reviewer. Spelled out rather than shown as the enum
# value, because `database_resolved` is a field name and this is a document someone signs.
_ORIGIN_LABEL = {
    Origin.USER_STATED: "engineer stated",
    Origin.DATABASE_RESOLVED: "resolved from bundled data",
    Origin.DEFAULT: "library default",
}

_STATUS_LABEL = {
    CheckStatus.PASS: "PASS",
    CheckStatus.FAIL: "FAIL",
    CheckStatus.OVER_MARGIN: "OVER MARGIN",
    CheckStatus.NOT_EVALUATED: "NOT EVALUATED",
}

_FALLBACK_LABEL = "derivation not rendered"


# Non-finite floats spelled as JSON strings. Python's ``json`` writes ``Infinity`` and
# ``NaN`` as bare tokens that are not in the JSON grammar — JavaScript, Go, and most
# schema validators reject them — and the calc record exists for another firm's QA script
# to read. Nulling them instead loses the value: a `SymbolValue.value` is `Quantity |
# float` and a `Quantity.magnitude` is `float`, neither of which admits `None`, so a
# nulled record failed this build's own loader. These tokens are deliberately unlovely so
# no real string field can collide with one.
_NONFINITE_TOKENS: dict[str, float] = {
    "__nonfinite:inf__": float("inf"),
    "__nonfinite:-inf__": float("-inf"),
    "__nonfinite:nan__": float("nan"),
}
_NONFINITE_SPELLING = {"inf": "__nonfinite:inf__", "-inf": "__nonfinite:-inf__"}


def _repair_source(section) -> str:
    """Where a repair hint's number came from, as a clause to append to it.

    Empty when the hint declares no provenance, so a hint without one renders exactly as it
    did. The packs populate it with the inverse or the monotonicity argument behind the
    value, and both renderings dropped it.
    """
    hint = section.entry.repair_hint
    source = (hint.provenance or "").strip() if hint is not None else ""
    return f" — from the {source}" if source else ""


def _json_safe(value: object) -> object:
    """Encode non-finite floats as string tokens so the record is strict-JSON valid.

    Round-trips through :func:`_json_revive`, which is what separates this from simply
    dropping the value: an infinite safety factor is a real result (a weld range below the
    fatigue cutoff does no damage), and the archived evidence for exactly the
    strongest-passing checks has to be loadable again.
    """
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not isfinite(value):
        return _NONFINITE_SPELLING.get(repr(value), "__nonfinite:nan__")
    return value


def _json_revive(value: object) -> object:
    """Turn the tokens :func:`_json_safe` wrote back into their non-finite floats."""
    if isinstance(value, dict):
        return {k: _json_revive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_revive(v) for v in value]
    if isinstance(value, str) and value in _NONFINITE_TOKENS:
        return _NONFINITE_TOKENS[value]
    return value


class ReportSection(BaseModel):
    """One check in the report: its verdict, and the work behind it.

    Checks that declare their own derivation carry it on the scorecard entry, and
    the section renders that without being told. ``derivation`` overrides it for a
    caller assembling work a check does not yet declare. Without either, the
    section renders a plain inputs table labeled "derivation not rendered" — an
    honest gap, never a formula invented to fill the space — from ``inputs``.
    """

    model_config = ConfigDict(frozen=True)

    entry: ScorecardEntry
    derivation: Derivation | None = None
    inputs: tuple[SymbolValue, ...] = ()

    @property
    def worked(self) -> Derivation | None:
        """The derivation this section renders: the caller's, else the check's own."""
        return self.derivation if self.derivation is not None else self.entry.derivation

    @property
    def is_worked(self) -> bool:
        """Whether this section renders a derivation rather than the fallback table.

        A derivation whose formula uses symbols it never declares cannot be shown as
        worked — the substituted line would carry a bare symbol where a value
        belongs — so it falls back with the rest.
        """
        derivation = self.worked
        return derivation is not None and not derivation.unresolved_symbols()

    def worked_lines(self, *, system: UnitSystem | None = None) -> tuple[str, ...]:
        """The worked calculation as text: the three lines, then the symbol glossary.

        Empty when the section has no derivation it can show as worked, so a caller cannot
        print a heading over nothing. It is a method rather than inline text because the
        shell renders the same block: two renderings of one derivation are two things to
        keep in step, and the one that drifts is the one nobody is reading.
        """
        derivation = self.worked
        if derivation is None or not self.is_worked:
            return ()
        lines = [f"    {line}" for line in derivation.lines(system=system)]
        lines.append("  where:")
        lines.extend(
            f"    {symbol} = {value}  ({description})"
            for symbol, description, value in derivation.glossary(system=system)
        )
        return tuple(lines)

    def verdict(self, *, system: UnitSystem | None = None) -> str:
        """The check's detail line, in ``system``'s units where the check carries them.

        `ScorecardEntry.detail` is a sentence written at screening time, and a screen does
        not know what system its result will be read in. A check that compares two
        quantities carries them, so this restates the comparison in the document's own
        units; everything else — a safety-factor line, a refusal, an identification line —
        falls through to the sentence it was given.
        """
        if self.entry.comparison is None:
            return self.entry.detail
        return self.entry.comparison.sentence(system=system)

    @property
    def fallback_label(self) -> str:
        """The label over the inputs table, with the check's own reason when it states one.

        A bare "derivation not rendered" tells a reviewer that work is missing and not
        whether anyone owes it. An exemption, a table comparison and an unwritten closed
        form all print the same three words, and only the first two are finished. When
        the check declares why it has no formula, the reason belongs here — it is the one
        place a reader is already looking for it.
        """
        if self.entry.underived is None:
            return _FALLBACK_LABEL
        return f"{_FALLBACK_LABEL} — {self.entry.underived.reason}"

    @property
    def citation(self) -> str | None:
        """The clause behind the check, from the derivation or the entry."""
        derivation = self.worked
        if derivation is not None:
            return derivation.citation
        return self.entry.reference


class CalculationReport(BaseModel):
    """A set of checks assembled into a document a reviewer can act on.

    ``standards`` lists the code and standard editions relied upon, ``assumptions``
    the defaults in force **with their origin**, and ``sections`` the checks in the
    order they should be read.

    An assumption is a :class:`~anvilate.spec.provenance.Provenanced` string rather than a
    bare one, because "the engineer asserted this" and "the library chose this for you" are
    different facts about a document someone signs, and they rendered as the same bullet.
    A bare string is refused rather than tagged with a guess — the docstring said "with
    their origin" for a release while the type was ``tuple[str, ...]``. ``Provenanced``
    already requires a defaulted value to carry its rationale, so an untraceable default
    cannot be declared at all. ``date`` is a caller-supplied string so the document
    never stamps itself and rebuilds stay byte-identical.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    project: str | None = None
    prepared_by: str | None = None
    date: str | None = None
    unit_system: UnitSystem | None = None
    standards: tuple[str, ...] = ()
    assumptions: tuple[Provenanced[str], ...] = ()
    sections: tuple[ReportSection, ...] = ()

    def scorecard(self) -> Scorecard:
        """The report's checks as a scorecard, for the usual roll-up rules."""
        return Scorecard(entries=tuple(section.entry for section in self.sections))

    # Serialised with the report: `to_json` dumps this model, and a submittal document
    # carrying its sections without its verdict leaves the reader to roll them up.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        """The rolled-up verdict, honouring No-silent-green."""
        return self.scorecard().status

    def governing(self) -> ScorecardEntry | None:
        """The check running closest to its limit — what a reviewer reads first."""
        return self.scorecard().governing()

    def derivation_coverage(self) -> tuple[int, int]:
        """``(worked, total)`` sections — the ratio CI reports and gates on."""
        return (sum(1 for s in self.sections if s.is_worked), len(self.sections))

    # -- rendering ---------------------------------------------------------

    def to_text(self) -> str:
        """The report as plain text, for a terminal or a diff."""
        out: list[str] = [self.title, "=" * len(self.title)]
        for label, value in self._header_rows():
            out.append(f"{label}: {value}")
        out.append("")
        out.append("Standards relied upon:")
        out.extend(f"  - {item}" for item in self.standards or (_NONE_DECLARED,))
        out.append("")
        out.append("Assumptions:")
        out.extend(f"  - {line}" for line in self._assumption_lines())
        for section in self.sections:
            out.append("")
            heading = f"{_STATUS_LABEL[section.entry.status]}  {section.entry.name}"
            out.append(heading)
            out.append("-" * len(heading))
            if section.is_worked:
                out.extend(section.worked_lines(system=self.unit_system))
            else:
                out.append(f"  [{section.fallback_label}]")
                for item in section.inputs:
                    out.append(
                        f"    {item.symbol} = {item.rendered(system=self.unit_system)}"
                        f"  ({item.description})"
                    )
            out.append(f"  {section.verdict(system=self.unit_system)}")
            if section.entry.repair_hint is not None:
                # With its provenance, which nothing rendered. The packs write a real
                # sentence into it — "lug thickness inverse (σ ∝ 1/t, so SF ∝ t)" — and it
                # is the difference between a value that solves the check exactly and a
                # direction taken from a monotonicity declaration. This is the document a
                # reviewer signs, so it is where that difference has to be legible.
                out.append(f"  repair: {section.entry.repair_hint}{_repair_source(section)}")
            unc = section.entry.uncertainty
            if unc is not None:
                flag = " — FRAGILE" if section.entry.is_fragile() else ""
                out.append(
                    f"  uncertainty: P(below {unc.required:.2f}) = "
                    f"{unc.shortfall_probability * 100:.1f}% over {unc.samples} samples "
                    f"by {unc.method}{flag}"
                )
                out.append(f"    {unc.citation}")
            if section.citation:
                out.append(f"  source: {section.citation}")
        out.append("")
        out.append("Margin summary")
        out.append("--------------")
        for name, factor, required, verdict in self._summary_rows():
            out.append(f"  {verdict:<14} {name}: {factor} vs {required} required")
        governing = self.governing()
        if governing is not None:
            out.append(f"  governing check: {governing.name}")
        out.append(f"  overall: {_STATUS_LABEL[self.status]}")
        out.append("")
        out.append(SCREENING_DISCLAIMER)
        return "\n".join(out) + "\n"

    def to_html(self) -> str:
        """The report as a self-contained HTML document (no external assets)."""
        out: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{escape(self.title)}</title>",
            "<style>",
            _STYLESHEET,
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{escape(self.title)}</h1>",
        ]
        header_rows = self._header_rows()
        if header_rows:
            out.append('<table class="header">')
            for label, value in header_rows:
                out.append(f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>")
            out.append("</table>")
        out.extend(self._html_list("Standards relied upon", self.standards))
        out.extend(self._html_list("Assumptions", tuple(self._assumption_lines())))
        for section in self.sections:
            out.extend(self._html_section(section))
        out.extend(self._html_summary())
        out.append(f'<p class="disclaimer">{escape(SCREENING_DISCLAIMER)}</p>')
        out.append("</body>")
        out.append("</html>")
        return "\n".join(out) + "\n"

    # -- calc record -------------------------------------------------------

    def to_record(self) -> dict:
        """The machine-readable calc record: every number, no rendering to parse.

        Values are carried in full canonical precision (as the quantities were
        computed), not at display precision, so an external verifier recomputing a
        check matches the recorded result exactly.

        The record is valid JSON in the strict sense — no bare ``Infinity`` or ``NaN``
        tokens, which Python emits happily and most other languages' parsers reject.
        A non-finite float is recorded as ``null``; the check's ``detail`` line still
        says what it was, so nothing is lost that a QA script needed. It is reachable
        through an ordinary passing check: an EN 1993-1-9 weld range below the cutoff
        does no damage, so its safety factor is genuinely infinite.
        """
        return {
            "schema_version": CALC_RECORD_SCHEMA_VERSION,
            "report": _json_safe(self.model_dump(mode="json")),
        }

    # -- internals ---------------------------------------------------------

    def _header_rows(self) -> tuple[tuple[str, str], ...]:
        rows = (
            ("Project", self.project),
            ("Prepared by", self.prepared_by),
            ("Date", self.date),
            ("Units", self.unit_system.value if self.unit_system else None),
        )
        return tuple((label, value) for label, value in rows if value)

    def _governing_index(self) -> int | None:
        """Which *row* governs, by position — two checks can share a name.

        Marking the governing row by name bolded every row that shared it, so a passing
        duplicate was presented as the controlling check of a failing card. Nothing stops
        a real submittal from screening the same detail at two locations.
        """
        governing = self.governing()
        if governing is None:
            return None
        for index, section in enumerate(self.sections):
            if section.entry is governing:
                return index
        return None

    def _summary_rows(self) -> tuple[tuple[str, str, str, str], ...]:
        rows = []
        for section in self.sections:
            entry = section.entry
            factor = "—" if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
            required = (
                "—"
                if entry.required_safety_factor is None
                else f"{entry.required_safety_factor:.2f}"
            )
            rows.append((entry.name, factor, required, _STATUS_LABEL[entry.status]))
        return tuple(rows)

    def _assumption_lines(self) -> tuple[str, ...]:
        """Each assumption with its origin tag, or ``none declared``.

        The tag is the point of the field: a reviewer reading only this document has to be
        able to tell the value the engineer asserted from the one the library supplied, and
        a defaulted assumption shows the rationale ``Provenanced`` already makes it carry.
        """
        if not self.assumptions:
            return (_NONE_DECLARED,)
        lines = []
        for assumption in self.assumptions:
            tag = _ORIGIN_LABEL[assumption.origin]
            if assumption.origin is Origin.DEFAULT:
                tag = f"{tag}: {assumption.rationale}"
            lines.append(f"{assumption.value} [{tag}]")
        return tuple(lines)

    def _html_list(self, heading: str, items: tuple[str, ...]) -> list[str]:
        """A headed list, or the heading with ``none declared`` under it.

        An empty list used to render as nothing at all, which made a report whose author
        declared no assumptions and one whose author forgot the section look identical to
        the reviewer the document exists for. The heading is always emitted; what changes
        is whether there is anything under it.
        """
        if not items:
            return [f"<h2>{escape(heading)}</h2>", f'<p class="none">{_NONE_DECLARED}</p>']
        out = [f"<h2>{escape(heading)}</h2>", "<ul>"]
        out.extend(f"<li>{escape(item)}</li>" for item in items)
        out.append("</ul>")
        return out

    def _html_section(self, section: ReportSection) -> list[str]:
        status = section.entry.status
        out = [
            f'<section class="check {status.value}">',
            f"<h2>{escape(section.entry.name)}"
            f' <span class="status">{_STATUS_LABEL[status]}</span></h2>',
        ]
        if section.is_worked:
            derivation = section.worked
            assert derivation is not None  # guaranteed by is_worked
            out.append('<div class="derivation">')
            for line in derivation.lines(system=self.unit_system):
                # MathML where the formula round-trips, plain text where it does not. A
                # stacked rendering of something other than what the check cited is worse
                # than a line of text, so `formula_to_mathml` declines rather than guesses.
                math = formula_to_mathml(line)
                if math is None:
                    out.append(f"<p>{escape(line)}</p>")
                else:
                    out.append(f'<p class="math">{math}</p>')
            out.append("</div>")
            out.append('<table class="glossary">')
            out.append("<tr><th>Symbol</th><th>Meaning</th><th>Value</th></tr>")
            for symbol, description, value in derivation.glossary(system=self.unit_system):
                out.append(
                    f"<tr><td>{escape(symbol)}</td><td>{escape(description)}</td>"
                    f"<td>{escape(value)}</td></tr>"
                )
            out.append("</table>")
        else:
            out.append(f'<p class="fallback">[{escape(section.fallback_label)}]</p>')
            if section.inputs:
                out.append('<table class="glossary">')
                out.append("<tr><th>Symbol</th><th>Meaning</th><th>Value</th></tr>")
                for item in section.inputs:
                    out.append(
                        f"<tr><td>{escape(item.symbol)}</td>"
                        f"<td>{escape(item.description)}</td>"
                        f"<td>{escape(item.rendered(system=self.unit_system))}</td></tr>"
                    )
                out.append("</table>")
        out.append(f'<p class="detail">{escape(section.verdict(system=self.unit_system))}</p>')
        if section.entry.repair_hint is not None:
            out.append(
                f'<p class="repair">Repair: {escape(str(section.entry.repair_hint))}'
                f"{escape(_repair_source(section))}</p>"
            )
        unc = section.entry.uncertainty
        if unc is not None:
            fragile = section.entry.is_fragile()
            flag = " — FRAGILE" if fragile else ""
            cls = "uncertainty fragile" if fragile else "uncertainty"
            message = (
                f"Uncertainty: P(below {unc.required:.2f}) = "
                f"{unc.shortfall_probability * 100:.1f}% over {unc.samples} samples "
                f"by {unc.method}{flag}"
            )
            out.append(f'<p class="{cls}">{escape(message)}</p>')
            out.append(f'<p class="uncertainty-method">{escape(unc.citation)}</p>')
        if section.citation:
            out.append(f'<p class="source">Source: {escape(section.citation)}</p>')
        out.append("</section>")
        return out

    def _html_summary(self) -> list[str]:
        out = ["<h2>Margin summary</h2>", '<table class="summary">']
        out.append("<tr><th>Check</th><th>Safety factor</th><th>Required</th><th>Result</th></tr>")
        governing = self.governing()
        governing_index = self._governing_index()
        for index, (name, factor, required, verdict) in enumerate(self._summary_rows()):
            row_class = ' class="governing"' if index == governing_index else ""
            out.append(
                f"<tr{row_class}><td>{escape(name)}</td><td>{escape(factor)}</td>"
                f"<td>{escape(required)}</td><td>{escape(verdict)}</td></tr>"
            )
        out.append("</table>")
        if governing is not None:
            out.append(f"<p>Governing check: <strong>{escape(governing.name)}</strong></p>")
        out.append(f"<p>Overall: <strong>{_STATUS_LABEL[self.status]}</strong></p>")
        return out


def report_from_record(record: dict) -> CalculationReport:
    """Load a calc record back into a :class:`CalculationReport`.

    Rejects a record whose schema major version this build does not understand;
    a newer minor version is additive and loads with the extra fields ignored.
    """
    version = record.get("schema_version")
    if not isinstance(version, str):
        raise ValueError("calc record has no schema_version")
    major = version.split(".", 1)[0]
    expected_major = CALC_RECORD_SCHEMA_VERSION.split(".", 1)[0]
    if major != expected_major:
        raise ValueError(
            f"calc record schema version {version} is not readable by this build "
            f"(expects {expected_major}.x)"
        )
    return CalculationReport.model_validate(_json_revive(record["report"]))


# The document declares its own surface. It sets a text colour, and every status colour
# in it (#a00 failing, #060 passing, #444 for a note) is chosen against paper — so a
# viewer whose browser is in dark mode and a stylesheet that names no background renders
# near-black text on near-black, which is a blank page to a reviewer and looked fine in
# every test the suite had. `color-scheme: light` also keeps the UA's own furniture —
# scrollbars, form controls — on the same footing as the print it is a stand-in for.
_STYLESHEET = """
html { color-scheme: light; background: #fff; }
body { font-family: Georgia, serif; max-width: 46em; margin: 2em auto; color: #111;
       background: #fff; }
h1 { border-bottom: 2px solid #111; padding-bottom: 0.2em; }
h2 { margin-top: 1.6em; font-size: 1.1em; }
table { border-collapse: collapse; margin: 0.6em 0; }
th, td { border: 1px solid #bbb; padding: 0.25em 0.6em; text-align: left; }
table.header th { background: #f4f4f4; }
section.check { page-break-inside: avoid; }
.derivation { font-family: "DejaVu Sans Mono", monospace; margin: 0.6em 0 0.6em 1.5em; }
.derivation p { margin: 0.2em 0; }
.status { font-size: 0.8em; letter-spacing: 0.08em; }
.fail .status { color: #a00; }
.pass .status { color: #060; }
.over_margin .status { color: #b60; }
.repair { font-size: 0.9em; color: #a00; }
.uncertainty { font-size: 0.9em; color: #444; }
.uncertainty-method { font-size: 0.85em; color: #666; margin-top: -0.4em; }
.uncertainty.fragile { color: #a00; font-weight: bold; }
.fallback { font-style: italic; color: #666; }
.source { font-size: 0.9em; color: #444; }
tr.governing td { font-weight: bold; }
.disclaimer { margin-top: 2em; font-size: 0.9em; color: #444; border-top: 1px solid #bbb;
  padding-top: 0.8em; }
""".strip()
