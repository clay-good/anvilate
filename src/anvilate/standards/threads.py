"""Metric fastener tables: clearance holes (ISO 273) and thread pitch / tap
drill (ISO 261/724).

Both are retrieved, not recalled. :class:`ClearanceHoleTable` returns the
standardized clearance diameter for a thread size and fit; :class:`MetricThreadTable`
returns the pitch and 75%-thread tap drill for a coarse (``M8``) or fine
(``M8x1``) thread. Each dimension carries its source citation, so a downstream
hole feature and its evidence bundle both trace to the standard.
"""

from __future__ import annotations

import difflib
from enum import StrEnum
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from ..units import Quantity
from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "Fit",
    "ClearanceHoleTable",
    "MetricThread",
    "MetricThreadTable",
    "UnknownThreadSizeError",
    "default_clearance_table",
    "default_thread_table",
]


def _numeric_size(size: str) -> tuple[float, str]:
    """Sort key for metric designations: the nominal diameter after the leading
    ``M``, then the full designation. Parses both a bare size (``M8``) and a
    pitch-qualified fine thread (``M8x1``), so a fine thread sorts by its
    diameter and ties break deterministically on the designation string."""
    return (float(size[1:].split("x")[0]), size)


class Fit(StrEnum):
    """The three standard clearance-hole fits of ISO 273."""

    CLOSE = "close"
    NORMAL = "normal"
    COARSE = "coarse"


class UnknownThreadSizeError(KeyError):
    """A requested thread size has no record in the queried table."""

    def __init__(self, size: str, suggestions: list[str]) -> None:
        self.size = size
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for thread size {size!r}{hint}")


class ClearanceHoleTable:
    """Metric clearance-hole diameters keyed by thread size and fit."""

    def __init__(self, rows: dict[str, dict[Fit, QuantityProperty]]) -> None:
        self._rows = rows

    def sizes(self) -> list[str]:
        return sorted(self._rows, key=_numeric_size)

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


# --- Coarse-thread pitch and tap drill (ISO 261 / 724) ---


_Length = Annotated[QuantityProperty, dimensioned("[length]", "thread dimension")]


class MetricThread(BaseModel):
    """A metric thread: its designation, pitch, and 75%-thread tap drill. Covers
    coarse threads (keyed ``M8``) and pitch-qualified fine threads (``M8x1``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    pitch: _Length
    tap_drill: _Length


class MetricThreadTable:
    """Pitch and tap-drill sizes keyed by thread designation (coarse ``M8`` and
    fine ``M8x1``)."""

    def __init__(self, threads: dict[str, MetricThread]) -> None:
        self._threads = threads

    def sizes(self) -> list[str]:
        return sorted(self._threads, key=_numeric_size)

    def get(self, size: str) -> MetricThread:
        """Return the coarse thread record for ``size``.

        Raises :class:`UnknownThreadSizeError` (with near-misses) rather than
        estimating a pitch or drill for an unrecorded size.
        """
        try:
            return self._threads[size]
        except KeyError:
            raise UnknownThreadSizeError(
                size, difflib.get_close_matches(size, self._threads, n=3)
            ) from None

    def __len__(self) -> int:
        return len(self._threads)


def _load_threads(text: str) -> dict[str, MetricThread]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})

    def _prop(value_mm: float, kind: str, series: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"{series} thread {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    threads: dict[str, MetricThread] = {}
    for size, row in doc["threads"].items():
        series = "fine" if "x" in size else "coarse"
        threads[size] = MetricThread.model_validate(
            {
                "designation": size,
                "pitch": _prop(row["pitch"], "pitch", series),
                "tap_drill": _prop(row["tap_drill"], "75% tap drill", series),
            }
        )
    return threads


def default_thread_table() -> MetricThreadTable:
    """The bundled ISO 261/724 metric-thread pitch and tap-drill table (coarse
    threads and common fine-pitch threads)."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "metric_thread.yaml").read_text(encoding="utf-8")
    return MetricThreadTable(_load_threads(text))
