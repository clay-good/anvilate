"""The one-page part sheet: the part's drawings above its checks, as a single HTML file.

`anvilate view` writes it and the MCP export tool writes the same document, so the page an
engineer opens does not depend on which door produced it. The sheet is static: one file, no
script, nothing fetched. Turning the part over is what the user's CAD does with the STEP file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .scorecard import Scorecard

__all__ = ["PartSheet", "part_sheet"]

_VIEWS = ("iso", "front", "top", "right")


@dataclass(frozen=True)
class PartSheet:
    """A rendered sheet, how many views it carries, and why it carries none if it does."""

    html: str
    views: int
    not_drawn: str | None


def part_sheet(spec: Any, card: Scorecard) -> PartSheet:
    """The sheet for ``spec`` and the card it was screened to.

    The checks do not need the drawing, so a part that cannot be drawn still gets its sheet,
    saying why rather than leaving a gap where the drawing would be.
    """
    from .geometry import (
        GeometryError,
        GeometryUnavailable,
        UnsupportedGeometry,
        build_spec,
        render_viewport,
    )
    from .report import CalculationReport, ReportSection

    views: list[tuple[str, bytes]] = []
    absent: str | None = None
    note: str | None = None
    try:
        built = build_spec(spec)
        views = [(name, render_viewport(built, view=name, width_px=680).data) for name in _VIEWS]
        note = "As built: " + ", ".join(
            f"{name.replace('_', ' ')} {value:g} mm"
            for name, value in sorted(built.dimensions_mm.items())
        )
    except (GeometryUnavailable, UnsupportedGeometry, GeometryError) as failure:
        absent = str(failure)
    report = CalculationReport(
        title=f"{spec.name} — part sheet",
        project=spec.description,
        unit_system=spec.units.value if spec.units else None,
        sections=tuple(ReportSection(entry=entry) for entry in card.entries),
    )
    html = report.to_html(views=views, views_absent=absent, views_note=note)
    return PartSheet(html=html, views=len(views), not_drawn=absent)
