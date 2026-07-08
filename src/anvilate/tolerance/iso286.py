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

from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from ..units import Quantity
from .general import ToleranceRangeError

__all__ = [
    "StandardTolerance",
    "standard_tolerance",
    "LimitDeviations",
    "zone_limits",
    "Fit",
    "fit",
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


# --- Limit deviations for the H/h basis tolerance zones ---
#
# A full ISO 286 zone designation (H7, g6, ...) is a fundamental-deviation letter
# plus an IT grade. The letter fixes the deviation closest to the basic size; the
# grade fixes the zone width. The H hole and h shaft are the basis zones of the
# hole-basis and shaft-basis systems: their fundamental deviation is exactly zero
# by definition, so their limits follow from the IT grade alone — no
# fundamental-deviation table. Other letters land as that table is encoded.

_BASIS_LETTERS = {"H", "h"}


class LimitDeviations(BaseModel):
    """Resolved limit deviations for an ISO 286 tolerance zone.

    ``upper`` and ``lower`` are the signed deviations from the basic size (ES/EI
    for a hole, es/ei for a shaft). The permitted feature size runs from
    ``nominal + lower`` to ``nominal + upper``.
    """

    model_config = ConfigDict(frozen=True)

    nominal: Quantity
    designation: str  # the zone, e.g. "H7" or "h6"
    hole: bool  # True for a hole (uppercase letter), False for a shaft
    grade: int
    upper: Quantity  # ES (hole) / es (shaft), signed, a length
    lower: Quantity  # EI (hole) / ei (shaft), signed, a length
    size_range: str
    source: str

    @property
    def width(self) -> Quantity:
        """The total width of the tolerance zone (``upper - lower``)."""
        return Quantity(
            magnitude=self.upper.to("mm").magnitude - self.lower.to("mm").magnitude,
            unit="mm",
        )

    @property
    def min_size(self) -> Quantity:
        """The smallest permitted feature size (``nominal + lower``)."""
        return Quantity(
            magnitude=self.nominal.to("mm").magnitude + self.lower.to("mm").magnitude,
            unit="mm",
        )

    @property
    def max_size(self) -> Quantity:
        """The largest permitted feature size (``nominal + upper``)."""
        return Quantity(
            magnitude=self.nominal.to("mm").magnitude + self.upper.to("mm").magnitude,
            unit="mm",
        )

    def __str__(self) -> str:
        u = self.upper.to("mm").magnitude
        low = self.lower.to("mm").magnitude
        return f"{self.nominal} {self.designation} ({u:+.3f} / {low:+.3f} mm)"


def _parse_designation(designation: str) -> tuple[str, str]:
    """Split a zone designation into its letter(s) and grade, e.g. ``H7`` →
    ``("H", "7")``. Raises :class:`ValueError` if either part is missing."""
    token = designation.strip()
    cut = 0
    while cut < len(token) and token[cut].isalpha():
        cut += 1
    letter, grade = token[:cut], token[cut:]
    if not letter or not grade:
        raise ValueError(
            f"malformed ISO 286 zone {designation!r}; expected a letter and grade, e.g. 'H7'"
        )
    return letter, grade


def zone_limits(designation: str, nominal: Quantity) -> LimitDeviations:
    """Resolve the limit deviations for an ISO 286 tolerance zone at ``nominal``.

    ``designation`` is a fundamental-deviation letter plus an IT grade, e.g.
    ``"H7"`` (hole) or ``"h6"`` (shaft). Only the H/h basis zones — whose
    fundamental deviation is zero — are encoded so far; any other letter raises
    :class:`ToleranceRangeError`. Raises :class:`ValueError` for a malformed
    designation, and :class:`ToleranceRangeError` for an out-of-range nominal or
    ungraded IT grade (via :func:`standard_tolerance`).
    """
    letter, grade = _parse_designation(designation)
    if letter not in _BASIS_LETTERS:
        raise ToleranceRangeError(
            f"fundamental deviation for zone '{letter}' is not yet encoded; "
            "only the H/h basis zones are supported so far"
        )
    grade_tol = standard_tolerance(nominal, grade)
    hole = letter.isupper()
    width = grade_tol.width
    zero = Quantity(magnitude=0.0, unit=width.unit)
    negative = Quantity(magnitude=-width.magnitude, unit=width.unit)
    # H hole: EI = 0, ES = +IT. h shaft: es = 0, ei = -IT.
    upper, lower = (width, zero) if hole else (zero, negative)
    return LimitDeviations(
        nominal=nominal,
        designation=f"{letter}{grade_tol.grade}",
        hole=hole,
        grade=grade_tol.grade,
        upper=upper,
        lower=lower,
        size_range=grade_tol.size_range,
        source=grade_tol.source,
    )


# --- Fits: a hole zone mated with a shaft zone ---


class Fit(BaseModel):
    """A resolved ISO 286 fit: a hole zone mated with a shaft zone.

    Clearance is measured as hole size minus shaft size, so a positive value is
    a gap and a negative value is interference. ``min_clearance`` pairs the
    smallest hole with the largest shaft; ``max_clearance`` the largest hole with
    the smallest shaft.
    """

    model_config = ConfigDict(frozen=True)

    nominal: Quantity
    designation: str  # e.g. "H7/h6"
    hole: LimitDeviations
    shaft: LimitDeviations
    min_clearance: Quantity  # signed; negative => interference
    max_clearance: Quantity  # signed
    kind: Literal["clearance", "transition", "interference"]
    source: str

    def __str__(self) -> str:
        lo = self.min_clearance.to("mm").magnitude
        hi = self.max_clearance.to("mm").magnitude
        return f"{self.nominal} {self.designation} {self.kind} ({lo:+.3f} to {hi:+.3f} mm)"


def _clearance(hole_dev: Quantity, shaft_dev: Quantity) -> Quantity:
    return Quantity(
        magnitude=hole_dev.to("mm").magnitude - shaft_dev.to("mm").magnitude,
        unit="mm",
    )


def fit(designation: str, nominal: Quantity) -> Fit:
    """Resolve an ISO 286 fit ``"H7/h6"`` at ``nominal`` into its clearance range.

    ``designation`` is a hole zone and a shaft zone separated by ``/``. Both
    zones must resolve (see :func:`zone_limits`; only H/h basis zones are encoded
    so far). Raises :class:`ValueError` if the designation is malformed or the
    hole/shaft roles are swapped, and propagates :class:`ToleranceRangeError`
    from the zone lookups.
    """
    parts = [p for p in designation.split("/") if p.strip()]
    if len(parts) != 2:
        raise ValueError(
            f"malformed fit {designation!r}; expected a hole and shaft zone, e.g. 'H7/h6'"
        )
    hole = zone_limits(parts[0].strip(), nominal)
    shaft = zone_limits(parts[1].strip(), nominal)
    if not hole.hole or shaft.hole:
        raise ValueError(
            f"fit {designation!r} must be hole/shaft (uppercase then lowercase), e.g. 'H7/h6'"
        )
    min_clearance = _clearance(hole.lower, shaft.upper)
    max_clearance = _clearance(hole.upper, shaft.lower)
    if min_clearance.magnitude >= 0:
        kind: Literal["clearance", "transition", "interference"] = "clearance"
    elif max_clearance.magnitude <= 0:
        kind = "interference"
    else:
        kind = "transition"
    return Fit(
        nominal=nominal,
        designation=f"{hole.designation}/{shaft.designation}",
        hole=hole,
        shaft=shaft,
        min_clearance=min_clearance,
        max_clearance=max_clearance,
        kind=kind,
        source=hole.source,
    )
