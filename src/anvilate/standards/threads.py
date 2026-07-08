"""Metric fastener tables: clearance holes per ISO 273.

The clearance hole a pattern drills for a metric screw is retrieved from this
table, not recalled: it returns the standardized diameter for a given thread
size and fit, with its source citation, so a downstream hole feature and its
evidence bundle both trace to ISO 273.
"""

from __future__ import annotations

import difflib
from enum import StrEnum

import yaml

from ..units import Quantity
from .materials import PropertyCitation, QuantityProperty

__all__ = [
    "Fit",
    "ClearanceHoleTable",
    "UnknownThreadSizeError",
    "default_clearance_table",
]


class Fit(StrEnum):
    """The three standard clearance-hole fits of ISO 273."""

    CLOSE = "close"
    NORMAL = "normal"
    COARSE = "coarse"


class UnknownThreadSizeError(KeyError):
    """A requested thread size has no clearance-hole record."""

    def __init__(self, size: str, suggestions: list[str]) -> None:
        self.size = size
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no clearance-hole record for thread size {size!r}{hint}")


class ClearanceHoleTable:
    """Metric clearance-hole diameters keyed by thread size and fit."""

    def __init__(self, rows: dict[str, dict[Fit, QuantityProperty]]) -> None:
        self._rows = rows

    def sizes(self) -> list[str]:
        return sorted(self._rows, key=lambda s: float(s[1:]))

    def get(self, size: str, fit: Fit = Fit.NORMAL) -> QuantityProperty:
        """Return the clearance-hole diameter for ``size`` at ``fit``.

        Raises :class:`UnknownThreadSizeError` (with near-misses) for a size not
        in the table rather than estimating one.
        """
        try:
            row = self._rows[size]
        except KeyError:
            raise UnknownThreadSizeError(
                size, difflib.get_close_matches(size, self._rows, n=3)
            ) from None
        return row[Fit(fit)]

    def __len__(self) -> int:
        return len(self._rows)


def _load_table(text: str) -> dict[str, dict[Fit, QuantityProperty]]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})
    rows: dict[str, dict[Fit, QuantityProperty]] = {}
    for size, fits in doc["sizes"].items():
        row: dict[Fit, QuantityProperty] = {}
        for fit in Fit:
            diameter = fits[fit.value]
            row[fit] = QuantityProperty(
                quantity=Quantity(magnitude=float(diameter), unit="mm"),
                citation=PropertyCitation(
                    source=dataset["source"],
                    condition=f"{fit.value} fit clearance hole",
                    license=dataset["license"],
                    retrieved=dataset["retrieved"],
                ),
            )
        rows[size] = row
    return rows


def default_clearance_table() -> ClearanceHoleTable:
    """The bundled ISO 273 metric clearance-hole table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "metric_clearance.yaml").read_text(
        encoding="utf-8"
    )
    return ClearanceHoleTable(_load_table(text))
