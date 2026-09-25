"""Every rendering of the calculation report, held to a committed copy (presentation-craft 7).

A reference corpus of reports is rendered as text, HTML and PDF, and each rendering is
compared with the file committed under ``tests/renderings/``. Any change to what a reviewer
would see fails here with the difference shown. That includes a reworded label, a moved
column, a changed glyph and a new page break. A change that was meant is acknowledged by
regenerating the files and committing them, so it is reviewed in the diff like any other
change:

    ANVILATE_ACCEPT_RENDERINGS=1 pytest tests/test_renderings.py

The corpus is chosen to reach every status and every optional block the report renders:
worked derivations and the fallback inputs table, a repair line, an uncertainty
annotation, a margin ledger, a performance budget, and both unit systems. The HTML carries
its light and dark schemes in the one file, so one copy covers both themes. The PDF is
held by digest, and its text layer by the text form it is typeset from.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import anvilate
from anvilate.report import CalculationReport, ReportSection
from anvilate.scorecard import CheckStatus, ScorecardEntry
from anvilate.units import UnitSystem

_REPO = Path(__file__).resolve().parent.parent
_GOLDEN = Path(__file__).resolve().parent / "renderings"
_ACCEPT = os.environ.get("ANVILATE_ACCEPT_RENDERINGS") == "1"


def _lifting_lug(system: UnitSystem = UnitSystem.SI) -> CalculationReport:
    sys.path.insert(0, str(_REPO / "examples"))
    try:
        from lifting_lug_calc_report import build_report
    finally:
        sys.path.pop(0)
    return build_report().model_copy(update={"unit_system": system, "revision": "A"})


def _every_status() -> CalculationReport:
    entries = (
        ScorecardEntry.from_safety_factor("bearing", computed=2.6, required=2.0),
        ScorecardEntry.from_safety_factor("net tension", computed=1.4, required=2.0),
        ScorecardEntry.from_safety_factor("weld shear", computed=6.7, required=2.0, upper=4.0),
        ScorecardEntry.from_safety_factor(
            "gross yielding",
            computed=None,
            required=2.0,
            unavailable="the material record carries no yield strength",
        ),
        ScorecardEntry(
            name="edge distance",
            status=CheckStatus.WARNING,
            detail="edge distance 1.4 d is inside the 1.5 d the clause recommends",
        ),
        ScorecardEntry(
            name="fatigue",
            status=CheckStatus.OUT_OF_DEPTH,
            detail="cyclic loading needs a fatigue assessment this tier does not make",
        ),
    )
    return CalculationReport(
        title="Every status",
        project="Rendering corpus",
        date="2026-09-25",
        unit_system=UnitSystem.SI,
        sections=tuple(ReportSection(entry=entry) for entry in entries),
    )


def _from_test_report(name: str) -> Callable[[], CalculationReport]:
    def build() -> CalculationReport:
        import test_report

        return getattr(test_report, name)()

    return build


CASES: dict[str, Callable[[], CalculationReport]] = {
    "lifting_lug_si": _lifting_lug,
    "lifting_lug_us": lambda: _lifting_lug(UnitSystem.US),
    "every_status": _every_status,
    "fallback_inputs": _from_test_report("_report"),
    "uncertainty": _from_test_report("_annotated_report"),
    "margin_ledger": _from_test_report("_ledgered_report"),
    "performance_budget": _from_test_report("_budgeted_report"),
}


def _renderings(report: CalculationReport, monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    # The PDF names its producer, and a version bump is not a rendering change.
    monkeypatch.setattr(anvilate, "__version__", "rendering-corpus")
    pdf = report.to_pdf()
    return {
        ".txt": report.to_text().encode("utf-8"),
        ".html": report.to_html().encode("utf-8"),
        ".pdf.sha256": (hashlib.sha256(pdf).hexdigest() + "\n").encode("ascii"),
    }


def _difference(name: str, suffix: str, expected: bytes | None, actual: bytes) -> str | None:
    """Nothing when ``actual`` is the committed rendering, else what changed and what to do."""
    if expected == actual:
        return None
    if expected is None:
        shown = "no committed copy exists"
    else:
        lines = difflib.unified_diff(
            expected.decode("utf-8").splitlines(),
            actual.decode("utf-8").splitlines(),
            f"committed/{name}{suffix}",
            f"rendered/{name}{suffix}",
            lineterm="",
            n=2,
        )
        shown = "\n".join(list(lines)[:80])
    if suffix == ".pdf.sha256":
        shown += (
            "\nThe PDF's text layer is typeset from the .txt rendering. If that is unchanged, "
            "the difference is in a glyph drawing or the page layout: render both and compare."
        )
    return (
        f"the {suffix} rendering of {name!r} changed:\n{shown}\n\nIf the change is meant, "
        "acknowledge it with `ANVILATE_ACCEPT_RENDERINGS=1 pytest tests/test_renderings.py` "
        "and commit tests/renderings/, where the diff is reviewed like any other."
    )


@pytest.mark.parametrize("name", sorted(CASES))
def test_each_rendering_is_the_committed_one(name, monkeypatch):
    changed = []
    for suffix, actual in _renderings(CASES[name](), monkeypatch).items():
        path = _GOLDEN / f"{name}{suffix}"
        expected = path.read_bytes() if path.exists() else None
        difference = _difference(name, suffix, expected, actual)
        if difference is None:
            continue
        if _ACCEPT:
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(actual)
        else:
            changed.append(difference)
    assert not changed, "\n\n".join(changed)


def test_every_committed_rendering_belongs_to_a_case():
    """The other direction: a renamed case must not leave its old copy behind unchecked."""
    committed = sorted(path.name for path in _GOLDEN.iterdir())
    assert len(committed) == 3 * len(CASES)
    expected = sorted(
        f"{name}{suffix}" for name in CASES for suffix in (".txt", ".html", ".pdf.sha256")
    )
    assert committed == expected


def test_the_corpus_reaches_every_status_and_every_optional_block():
    reports = [build() for build in CASES.values()]
    statuses = {section.entry.status for report in reports for section in report.sections}
    assert statuses == set(CheckStatus)
    text = "\n".join(report.to_text() for report in reports)
    for block in ("repair: ", "uncertainty: P(below", "[derivation not rendered]", "  where:"):
        assert block in text, block
    assert any(report.margins for report in reports)
    assert any(report.budgets for report in reports)
    assert {report.unit_system for report in reports} >= {UnitSystem.SI, UnitSystem.US}


def test_a_changed_rendering_fails_with_the_difference_shown():
    """The gate's adversary: a one-word change is caught, located and explained."""
    before = b"PASS  bearing\n  safety factor 2.60 vs required minimum 2.00\n"
    after = b"PASS  bearing\n  safety factor 2.60 vs required 2.00\n"
    message = _difference("every_status", ".txt", before, after)
    assert message is not None
    assert "-  safety factor 2.60 vs required minimum 2.00" in message
    assert "+  safety factor 2.60 vs required 2.00" in message
    assert "ANVILATE_ACCEPT_RENDERINGS=1" in message
    assert _difference("every_status", ".txt", before, before) is None
