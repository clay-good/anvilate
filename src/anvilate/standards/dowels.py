"""Parallel dowel-pin dimensions (ISO 2338).

A dowel pin locates two parts by seating in a reamed hole. Its standardized
facts — nominal diameter, tolerance class, end chamfer, and the range of stocked
lengths — are retrieved from this table, not recalled. The mating hole is sized
from the nominal diameter and the pin's tolerance class through the ISO 286 fit
tables (:mod:`anvilate.tolerance.iso286`), so only the pin's own dimensions live
here, the same "mount, not body" rule the NEMA frame and bearing tables follow.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "DowelPin",
    "DowelPinTable",
    "UnknownDowelPinError",
    "default_dowel_pin_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "dowel-pin dimension")]


def _dowel_key(designation: str) -> tuple[float, str]:
    """Sort key: the nominal diameter after the ``ISO2338-`` prefix, then the full
    designation, so ``ISO2338-2`` sorts before ``ISO2338-10`` numerically."""
    tail = designation.rsplit("-", 1)[-1]
    try:
        return (float(tail), designation)
    except ValueError:
        return (0.0, designation)


class DowelPin(BaseModel):
    """An ISO 2338 parallel pin's standardized dimensions.

    ``nominal_diameter`` is the pin diameter d, toleranced to ``tolerance_class``
    (m6 by default, h8 the alternative); ``chamfer`` is the end chamfer c; the pin
    is stocked over ``length_min`` to ``length_max``. The mating reamed hole is
    sized from the diameter and class through the ISO 286 tables.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    tolerance_class: str
    nominal_diameter: Length
    chamfer: Length
    length_min: Length
    length_max: Length

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence
        trail, mirroring :meth:`anvilate.standards.Bearing.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownDowelPinError(KeyError):
    """A requested dowel-pin designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for dowel pin {designation!r}{hint}")


class DowelPinTable:
    """ISO 2338 parallel-pin dimensions keyed by designation (``ISO2338-6``)."""

    def __init__(self, pins: dict[str, DowelPin]) -> None:
        self._pins = pins

    def has_pin(self, designation: str) -> bool:
        return designation in self._pins

    def designations(self) -> list[str]:
        return sorted(self._pins, key=_dowel_key)

    def get(self, designation: str) -> DowelPin:
        """Return the dimension record for ``designation``.

        Raises :class:`UnknownDowelPinError` (with near-misses) rather than
        estimating dimensions for an unrecorded pin.
        """
        try:
            return self._pins[designation]
        except KeyError:
            raise UnknownDowelPinError(
                designation, difflib.get_close_matches(designation, self._pins, n=3)
            ) from None

    def __len__(self) -> int:
        return len(self._pins)


def _load_pins(text: str) -> dict[str, DowelPin]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})
    tolerance_class = doc["tolerance_class"]

    diameter_kind = f"nominal diameter ({tolerance_class})"

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"ISO 2338 {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    pins: dict[str, DowelPin] = {}
    for designation, row in doc["pins"].items():
        pins[designation] = DowelPin.model_validate(
            {
                "designation": designation,
                "tolerance_class": tolerance_class,
                "nominal_diameter": _prop(row["nominal_diameter"], diameter_kind),
                "chamfer": _prop(row["chamfer"], "chamfer"),
                "length_min": _prop(row["length_min"], "minimum stocked length"),
                "length_max": _prop(row["length_max"], "maximum stocked length"),
            }
        )
    return pins


def default_dowel_pin_table() -> DowelPinTable:
    """The bundled ISO 2338 parallel dowel-pin dimension table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "dowel_pins.yaml").read_text(encoding="utf-8")
    return DowelPinTable(_load_pins(text))
