"""ISO 286-1 standard tolerance grades (IT grades).

An ISO fit designation splits into two halves: a fundamental deviation letter
that fixes where the tolerance zone sits relative to the basic size (the ``H``
in ``H7``), and an IT grade number that fixes how wide the zone is (the ``7``).
This module resolves the grade half — the standard tolerance, the total width of
the zone — for a nominal size and IT grade from the encoded ISO 286-1 table,
with its citation. Fundamental deviations and full fit resolution (H7/g6 → limit
deviations) build on this table (see openspec/specs/tolerance-management/).
"""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict

from ..units import Quantity
from .general import ToleranceRangeError

__all__ = [
    "StandardTolerance",
    "standard_tolerance",
]


class StandardTolerance(BaseModel):
    """A resolved ISO 286-1 standard tolerance: the zone width and its source."""

    model_config = ConfigDict(frozen=True)

    nominal: Quantity
    grade: int  # the IT grade number, e.g. 7 for IT7
    width: Quantity  # the standard tolerance (total width of the zone), a length
    size_range: str  # the ISO 286-1 range applied, e.g. "over 18 up to 30 mm"
    source: str

    @property
    def designation(self) -> str:
        """The IT-grade designation, e.g. ``IT7``."""
        return f"IT{self.grade}"

    def __str__(self) -> str:
        return f"{self.nominal} IT{self.grade} = {self.width}"


def _parse_grade(grade: int | str) -> int:
    """Parse an IT grade from an int (``7``) or a string (``IT7`` / ``7``)."""
    if isinstance(grade, int):
        return grade
    token = grade.strip().upper()
    if token.startswith("IT"):
        token = token[2:]
    try:
        return int(token)
    except ValueError:
        raise ValueError(f"unrecognized IT grade {grade!r}; expected e.g. 7 or 'IT7'") from None


_TABLE: dict | None = None


def _table() -> dict:
    global _TABLE
    if _TABLE is None:
        from importlib.resources import files

        text = (files("anvilate.tolerance") / "data" / "iso286_grades.yaml").read_text(
            encoding="utf-8"
        )
        _TABLE = yaml.safe_load(text)
    return _TABLE


def _range_label(low: float, up_to: float, first: bool) -> str:
    # The first range starts above 0; the rest are "over X".
    return f"up to {up_to:g} mm" if first else f"over {low:g} up to {up_to:g} mm"


def standard_tolerance(nominal: Quantity, grade: int | str) -> StandardTolerance:
    """Resolve the ISO 286-1 standard tolerance (IT grade width) for ``nominal``.

    ``nominal`` must be a length; ``grade`` is an IT grade as an int (``7``) or a
    string (``"IT7"`` / ``"7"``). Raises :class:`ToleranceRangeError` if the
    nominal is at or below zero, beyond the table's maximum, or if the grade is
    not encoded (only IT5–IT16 are). Raises :class:`ValueError` for a malformed
    grade string.
    """
    if not nominal.has_dimension("[length]"):
        raise ToleranceRangeError(
            f"standard tolerance needs a length; got {nominal.dimensionality} ({nominal})"
        )
    it = _parse_grade(grade)
    doc = _table()
    magnitude = abs(nominal.to("mm").magnitude)
    if magnitude <= 0:
        raise ToleranceRangeError("basic size must be greater than 0 mm")
    low = 0.0
    for index, row in enumerate(doc["ranges"]):
        up_to = float(row["up_to_mm"])
        if magnitude <= up_to:
            widths = row["it"]
            if it not in widths:
                grades = ", ".join(f"IT{g}" for g in sorted(widths))
                raise ToleranceRangeError(
                    f"IT{it} is not in the encoded ISO 286-1 table (have {grades})"
                )
            return StandardTolerance(
                nominal=nominal,
                grade=it,
                width=Quantity(magnitude=float(widths[it]) / 1000.0, unit="mm"),
                size_range=_range_label(low, up_to, first=index == 0),
                source=doc["dataset"]["source"],
            )
        low = up_to
    raise ToleranceRangeError(
        f"{nominal} exceeds ISO 286-1's {doc['max_nominal_mm']:g} mm maximum "
        "for this table; needs an explicit tolerance"
    )
