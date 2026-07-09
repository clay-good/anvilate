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


# --- Limit deviations for a tolerance zone ---
#
# A full ISO 286 zone designation (H7, g6, ...) is a fundamental-deviation letter
# plus an IT grade. The letter fixes the deviation closest to the basic size; the
# grade fixes the zone width. The H hole and h shaft are the basis zones: their
# fundamental deviation is exactly zero by definition. The clearance letters
# d/e/f/g carry a negative shaft deviation `es` (drawn from the encoded table),
# and their uppercase holes mirror it through the ISO 286 general rule EI = -es.
# The js/JS zones straddle the basic size symmetrically (±IT/2). m/n/p carry a
# positive shaft deviation `ei` that lifts the zone above the basic size (the
# transition/interference side); their uppercase holes M/N/P take the ISO 286
# special rule ES = -ei + Δ, where the grade-dependent delta correction
# Δ = IT_n − IT_(n−1) is computed from the encoded IT-grade table. The grade-
# dependent letters j and k and the finer-stepped r/s/t/u land as the table grows.

_BASIS_LETTERS = {"h"}  # zero fundamental deviation; no table lookup needed
_CLEARANCE_LETTERS = {"d", "e", "f", "g"}  # negative shaft `es`, encoded below
_SYMMETRIC_LETTERS = {"js"}  # zone centered on the basic size, ±IT/2
_INTERFERENCE_LETTERS = {"m", "n", "p"}  # positive shaft `ei`; holes via delta rule
_ENCODED_LETTERS = _BASIS_LETTERS | _CLEARANCE_LETTERS | _SYMMETRIC_LETTERS | _INTERFERENCE_LETTERS

# The ISO 286 special rule ES = -ei + Δ holds for the M and N holes up to IT8 and
# the P holes up to IT7. Below IT6 the correction Δ = IT_n − IT_(n−1) would need
# IT_(n−1) beneath the encoded IT5, so IT6 is the finest hole grade resolved here.
_HOLE_MAX_GRADE = {"m": 8, "n": 8, "p": 7}
_HOLE_MIN_GRADE = 6


_DEVIATIONS: dict | None = None


def _deviation_table() -> dict:
    global _DEVIATIONS
    if _DEVIATIONS is None:
        from importlib.resources import files

        text = (files("anvilate.tolerance") / "data" / "iso286_deviations.yaml").read_text(
            encoding="utf-8"
        )
        _DEVIATIONS = yaml.safe_load(text)
    return _DEVIATIONS


def _fundamental_dev(key: str, letter: str, nominal_mm: float) -> float:
    """The tabulated fundamental deviation (mm) for a shaft letter.

    ``key`` selects the deviation kind: ``"es"`` (clearance letters, <= 0) or
    ``"ei"`` (transition/interference letters, >= 0). ``letter`` is the lowercase
    letter; ``nominal_mm`` is the basic size in mm, already validated in range by
    :func:`standard_tolerance`.
    """
    for row in _deviation_table()["ranges"]:
        if nominal_mm <= float(row["up_to_mm"]):
            return float(row[key][letter]) / 1000.0
    raise AssertionError("nominal beyond deviation table")  # pragma: no cover


def _delta_correction(letter: str, grade: int, nominal: Quantity) -> float:
    """The ISO 286 delta correction Δ = IT_n − IT_(n−1) (mm) for a special-rule hole.

    The uppercase transition/interference holes M/N/P take their fundamental
    deviation from the shaft's ``ei`` by the rule ES = -ei + Δ. That rule holds
    for M/N up to IT8 and P up to IT7; finer than IT6 the correction would need
    IT_(n−1) below the encoded IT5, and coarser than the letter's cap leaves the
    rule's validity — both raise :class:`ToleranceRangeError`.
    """
    cap = _HOLE_MAX_GRADE[letter]
    if grade < _HOLE_MIN_GRADE or grade > cap:
        up = letter.upper()
        raise ToleranceRangeError(
            f"the delta-corrected hole '{up}{grade}' is out of range; the encoded "
            f"ISO 286 special rule covers {up}{_HOLE_MIN_GRADE} through {up}{cap}"
        )
    it_n = standard_tolerance(nominal, grade).width.to("mm").magnitude
    it_prev = standard_tolerance(nominal, grade - 1).width.to("mm").magnitude
    return it_n - it_prev


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
    ``"H7"`` (hole), ``"h6"`` (shaft), ``"g6"``, ``"js6"``, or ``"p6"``. The H/h
    basis zones, the clearance letters d/e/f/g, and js/JS resolve in both cases;
    the transition/interference letters m/n/p resolve on the shaft side at any
    grade, and on the hole side (M/N/P) via the ISO 286 delta rule for M/N up to
    IT8 and P up to IT7. Any other letter raises :class:`ToleranceRangeError`,
    as does a delta-corrected hole outside that grade band. Raises
    :class:`ValueError` for a malformed
    designation, and :class:`ToleranceRangeError` for an out-of-range nominal or
    ungraded IT grade (via :func:`standard_tolerance`).
    """
    letter, grade = _parse_designation(designation)
    base = letter.lower()
    if base not in _ENCODED_LETTERS:
        raise ToleranceRangeError(
            f"fundamental deviation for zone '{letter}' is not yet encoded; "
            "the H/h basis, clearance letters d/e/f/g, and js/JS are supported so far"
        )
    grade_tol = standard_tolerance(nominal, grade)
    hole = letter.isupper()
    it = grade_tol.width.to("mm").magnitude
    nominal_mm = abs(nominal.to("mm").magnitude)
    if base in _SYMMETRIC_LETTERS:
        # js/JS: the zone straddles the basic size, es = +IT/2, ei = -IT/2.
        upper_mm, lower_mm = it / 2.0, -it / 2.0
    elif base in _INTERFERENCE_LETTERS:
        ei = _fundamental_dev("ei", base, nominal_mm)
        if hole:
            # Hole (ISO 286 special rule): ES = -ei + Δ, and EI = ES - IT.
            delta = _delta_correction(base, grade_tol.grade, nominal)
            es = -ei + delta
            upper_mm, lower_mm = es, es - it
        else:
            # Shaft: ei is the lower deviation, es = ei + IT.
            upper_mm, lower_mm = ei + it, ei
    else:
        es = 0.0 if base in _BASIS_LETTERS else _fundamental_dev("es", base, nominal_mm)
        # Shaft: es is the upper deviation, ei = es - IT. Hole (general rule): the
        # fundamental deviation EI = -es, and ES = EI + IT.
        upper_mm, lower_mm = (-es + it, -es) if hole else (es, es - it)
    # Adding 0.0 collapses the -0.0 that -es yields when es == 0 (the H/h basis),
    # so a zero deviation renders "+0.000", not "-0.000".
    upper = Quantity(magnitude=upper_mm + 0.0, unit="mm")
    lower = Quantity(magnitude=lower_mm + 0.0, unit="mm")
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

    def satisfies_clearance(self, min_required: Quantity, max_required: Quantity) -> bool:
        """Whether the fit's whole clearance range falls within a required band.

        Passes only when the worst cases both fit: the tightest clearance
        (``min_clearance``) is at least ``min_required`` and the loosest
        (``max_clearance``) is at most ``max_required``. Both bounds must be
        lengths, else :class:`ToleranceRangeError`.
        """
        for bound in (min_required, max_required):
            if not bound.has_dimension("[length]"):
                raise ToleranceRangeError(
                    f"clearance requirement must be a length; got {bound.dimensionality} ({bound})"
                )
        lo = self.min_clearance.to("mm").magnitude
        hi = self.max_clearance.to("mm").magnitude
        return min_required.to("mm").magnitude <= lo and hi <= max_required.to("mm").magnitude

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
