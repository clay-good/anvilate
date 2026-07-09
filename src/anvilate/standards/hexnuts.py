"""Hexagon nut dimensions (ISO 4032, style 1).

A bolted joint torques against a hex nut. The standardized facts it retrieves are
the width across flats (the wrench size and the pocket a design clears) and the
nut height (which adds to the stack). They are looked up here, not recalled,
keyed by the nominal thread size the nut serves — the same pattern the cap-screw
and washer tables follow. The ISO 4032 widths across flats differ from the older
DIN 934 at M10/M12; these are the ISO 4032 values.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "HexNut",
    "HexNutTable",
    "UnknownHexNutError",
    "default_hex_nut_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "hex-nut dimension")]


def _nut_key(designation: str) -> tuple[float, str]:
    """Sort key: the nominal thread diameter after the ``ISO4032-M`` prefix, then
    the full designation, so ``ISO4032-M4`` sorts before ``ISO4032-M10``."""
    tail = designation.rsplit("-M", 1)[-1]
    try:
        return (float(tail), designation)
    except ValueError:
        return (0.0, designation)


class HexNut(BaseModel):
    """An ISO 4032 style-1 hexagon nut's standardized dimensions.

    ``width_across_flats`` is the wrench size s and the pocket a design must clear;
    ``height`` is the nut height m, which adds to the joint's stack.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    width_across_flats: Length
    height: Length

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence
        trail, mirroring :meth:`anvilate.standards.Bearing.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownHexNutError(KeyError):
    """A requested hex-nut designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for hex nut {designation!r}{hint}")


class HexNutTable:
    """ISO 4032 hexagon nut dimensions keyed by designation (``ISO4032-M5``)."""

    def __init__(self, nuts: dict[str, HexNut]) -> None:
        self._nuts = nuts

    def has_nut(self, designation: str) -> bool:
        return designation in self._nuts

    def designations(self) -> list[str]:
        return sorted(self._nuts, key=_nut_key)

    def get(self, designation: str) -> HexNut:
        """Return the dimension record for ``designation``.

        Raises :class:`UnknownHexNutError` (with near-misses) rather than
        estimating dimensions for an unrecorded nut.
        """
        try:
            return self._nuts[designation]
        except KeyError:
            raise UnknownHexNutError(
                designation, difflib.get_close_matches(designation, self._nuts, n=3)
            ) from None

    def __len__(self) -> int:
        return len(self._nuts)


def _load_nuts(text: str) -> dict[str, HexNut]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"ISO 4032 {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    nuts: dict[str, HexNut] = {}
    for designation, row in doc["nuts"].items():
        nuts[designation] = HexNut.model_validate(
            {
                "designation": designation,
                "width_across_flats": _prop(row["width_across_flats"], "width across flats"),
                "height": _prop(row["height"], "nut height"),
            }
        )
    return nuts


def default_hex_nut_table() -> HexNutTable:
    """The bundled ISO 4032 hexagon nut dimension table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "hex_nuts.yaml").read_text(encoding="utf-8")
    return HexNutTable(_load_nuts(text))
