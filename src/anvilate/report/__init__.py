"""Reviewable calculation reports: the worked calculation behind every verdict.

A scorecard says whether a design passes. A calculation report says *why*, in the
form a checker actually reviews: the governing formula, the same formula with the
real values substituted, the result, and the clause it rests on — assembled into a
submittal-shaped document with the code editions, assumptions, margin summary, and
governing check. Alongside it comes a versioned calc record carrying the same
numbers in machine-readable form, so a firm's QA script can re-verify every value
without parsing the page.

See openspec/specs/ for the capability this implements. Rendering is pure Python,
offline, and byte-identical across rebuilds.
"""

from __future__ import annotations

from ..derivation import Derivation, SymbolValue
from .document import (
    CALC_RECORD_SCHEMA_VERSION,
    SCREENING_DISCLAIMER,
    CalculationReport,
    ReportSection,
    report_from_record,
)

__all__ = [
    "CALC_RECORD_SCHEMA_VERSION",
    "SCREENING_DISCLAIMER",
    "CalculationReport",
    "Derivation",
    "ReportSection",
    "SymbolValue",
    "report_from_record",
]
