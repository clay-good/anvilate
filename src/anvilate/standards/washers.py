"""Plain washer dimensions (ISO 7089, normal series).

A bolted joint seats a plain washer under the head or nut. The standardized facts
it retrieves are the inner diameter (clears the screw), the outer diameter (the
bearing footprint), and the thickness (which adds to the grip length). They are
looked up here, not recalled, keyed by the nominal thread size the washer serves
— the same pattern the cap-screw table follows.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "PlainWasher",
    "WasherTable",
    "UnknownWasherError",
    "default_washer_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "washer dimension")]


def _washer_key(designation: str) -> tuple[float, str]:
    """Sort key: the nominal thread diameter after the ``ISO7089-M`` prefix, then
    the full designation, so ``ISO7089-M4`` sorts before ``ISO7089-M10``."""
    tail = designation.rsplit("-M", 1)[-1]
    try:
        return (float(tail), designation)
    except ValueError:
        return (0.0, designation)


class PlainWasher(BaseModel):
    """An ISO 7089 plain washer's standardized dimensions.

    ``inner_diameter`` is the bore d1 that clears the screw, ``outer_diameter`` the
    outer diameter d2 (the bearing footprint under the head or nut), and
    ``thickness`` the washer thickness h, which adds to the joint's grip length.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    inner_diameter: Length
    outer_diameter: Length
    thickness: Length

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence
        trail, mirroring :meth:`anvilate.standards.Bearing.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownWasherError(KeyError):
    """A requested washer designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for washer {designation!r}{hint}")


class WasherTable:
    """ISO 7089 plain washer dimensions keyed by designation (``ISO7089-M5``)."""

    def __init__(self, washers: dict[str, PlainWasher]) -> None:
        self._washers = washers

    def has_washer(self, designation: str) -> bool:
        return designation in self._washers

    def designations(self) -> list[str]:
        return sorted(self._washers, key=_washer_key)

    def get(self, designation: str) -> PlainWasher:
        """Return the dimension record for ``designation``.

        Raises :class:`UnknownWasherError` (with near-misses) rather than
        estimating dimensions for an unrecorded washer.
        """
        try:
            return self._washers[designation]
        except KeyError:
            raise UnknownWasherError(
                designation, difflib.get_close_matches(designation, self._washers, n=3)
            ) from None

    def __len__(self) -> int:
        return len(self._washers)


def _load_washers(text: str) -> dict[str, PlainWasher]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"ISO 7089 {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    washers: dict[str, PlainWasher] = {}
    for designation, row in doc["washers"].items():
        washers[designation] = PlainWasher.model_validate(
            {
                "designation": designation,
                "inner_diameter": _prop(row["inner_diameter"], "inner diameter"),
                "outer_diameter": _prop(row["outer_diameter"], "outer diameter"),
                "thickness": _prop(row["thickness"], "thickness"),
            }
        )
    return washers


def default_washer_table() -> WasherTable:
    """The bundled ISO 7089 plain washer dimension table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "washers.yaml").read_text(encoding="utf-8")
    return WasherTable(_load_washers(text))
