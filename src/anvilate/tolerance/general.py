"""ISO 2768-1 general tolerances for linear dimensions.

Every untoleranced dimension falls under a general-tolerance class; this module
resolves the permissible deviation for a nominal size and class from the encoded
ISO 2768-1 table, with its citation, so the applied tolerance can be stated on
drawings and in the evidence bundle. The class bridges to the Spec IR's
``Manufacturing.tolerance_class`` string via :meth:`ToleranceClass.parse`.
"""

from __future__ import annotations

from enum import StrEnum

import yaml
from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "ToleranceClass",
    "GeneralTolerance",
    "ToleranceRangeError",
    "general_tolerance",
]


class ToleranceClass(StrEnum):
    """An ISO 2768-1 general-tolerance class."""

    FINE = "fine"
    MEDIUM = "medium"
    COARSE = "coarse"
    VERY_COARSE = "very_coarse"

    @property
    def letter(self) -> str:
        """The single-letter designation (f/m/c/v) used in the table and title block."""
        return {"fine": "f", "medium": "m", "coarse": "c", "very_coarse": "v"}[self.value]

    @classmethod
    def parse(cls, text: str) -> ToleranceClass:
        """Parse a class from a letter (``m``) or word (``medium``).

        Bridges the Spec IR's free-form ``tolerance_class`` string to the typed
        class. Raises :class:`ValueError` on an unrecognized value.
        """
        token = text.strip().lower()
        by_letter = {"f": cls.FINE, "m": cls.MEDIUM, "c": cls.COARSE, "v": cls.VERY_COARSE}
        if token in by_letter:
            return by_letter[token]
        return cls(token)


class GeneralTolerance(BaseModel):
    """A resolved general tolerance: the permissible ± deviation and its source."""

    model_config = ConfigDict(frozen=True)

    nominal: Quantity
    tolerance_class: ToleranceClass
    deviation: Quantity  # the permissible ± deviation, a length
    size_range: str  # the ISO 2768-1 range applied, e.g. "over 30 up to 120 mm"
    source: str

    def __str__(self) -> str:
        return f"{self.nominal} ±{self.deviation} (ISO 2768 {self.tolerance_class.letter})"


class ToleranceRangeError(ValueError):
    """A nominal dimension or class has no ISO 2768-1 general tolerance."""


class _Table:
    def __init__(self, min_nominal_mm: float, ranges: list[dict], source: str) -> None:
        self.min_nominal_mm = min_nominal_mm
        self.ranges = ranges  # ordered by up_to_mm ascending
        self.source = source


def _load_table(text: str) -> _Table:
    doc = yaml.safe_load(text)
    return _Table(
        min_nominal_mm=float(doc["min_nominal_mm"]),
        ranges=doc["ranges"],
        source=doc["dataset"]["source"],
    )


_TABLE: _Table | None = None


def _table() -> _Table:
    global _TABLE
    if _TABLE is None:
        from importlib.resources import files

        text = (files("anvilate.tolerance") / "data" / "iso2768_linear.yaml").read_text(
            encoding="utf-8"
        )
        _TABLE = _load_table(text)
    return _TABLE


def _range_label(low: float, up_to: float, first: bool) -> str:
    # The first range is inclusive of its lower bound; the rest are "over X".
    return f"{low:g} up to {up_to:g} mm" if first else f"over {low:g} up to {up_to:g} mm"


def general_tolerance(
    nominal: Quantity, tolerance_class: ToleranceClass | str = ToleranceClass.MEDIUM
) -> GeneralTolerance:
    """Resolve the ISO 2768-1 general tolerance for ``nominal`` under a class.

    ``nominal`` must be a length. Raises :class:`ToleranceRangeError` if the
    dimension is below the table's minimum (needs an explicit tolerance), beyond
    its maximum, or if the class is undefined for the matched range.
    """
    if not nominal.has_dimension("[length]"):
        raise ToleranceRangeError(
            f"general tolerance needs a length; got {nominal.dimensionality} ({nominal})"
        )
    cls = (
        tolerance_class
        if isinstance(tolerance_class, ToleranceClass)
        else ToleranceClass.parse(tolerance_class)
    )
    table = _table()
    magnitude = abs(nominal.to("mm").magnitude)
    if magnitude < table.min_nominal_mm:
        raise ToleranceRangeError(
            f"{nominal} is below ISO 2768-1's {table.min_nominal_mm:g} mm minimum; "
            "dimensions this small need an explicit tolerance"
        )
    low = table.min_nominal_mm
    for index, row in enumerate(table.ranges):
        up_to = float(row["up_to_mm"])
        if magnitude <= up_to:
            deviation = row[cls.letter]
            label = _range_label(low, up_to, first=index == 0)
            if deviation is None:
                raise ToleranceRangeError(
                    f"ISO 2768-1 class {cls.letter} is not defined for the {label} range"
                )
            return GeneralTolerance(
                nominal=nominal,
                tolerance_class=cls,
                deviation=Quantity(magnitude=float(deviation), unit="mm"),
                size_range=label,
                source=table.source,
            )
        low = up_to
    raise ToleranceRangeError(
        f"{nominal} exceeds ISO 2768-1's {low:g} mm maximum; needs an explicit tolerance"
    )
