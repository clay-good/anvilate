"""Hexagon-head bolt/screw head geometry (ISO 4014 / ISO 4017).

ISO 4014 (partially threaded bolts) and ISO 4017 (fully threaded screws) share
one hex head, so both resolve from this table. The standardized facts a design
retrieves are the width across flats (the wrench size and the pocket to clear)
and the head height (which adds to the stack). They are looked up here, not
recalled, keyed by the nominal thread size — the same pattern the cap-screw and
hex-nut tables follow.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "HexBolt",
    "HexBoltTable",
    "UnknownHexBoltError",
    "default_hex_bolt_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "hex-bolt dimension")]


def _bolt_key(designation: str) -> tuple[float, str]:
    """Sort key: the nominal thread diameter after the ``ISO4014-M`` prefix, then
    the full designation, so ``ISO4014-M4`` sorts before ``ISO4014-M10``."""
    tail = designation.rsplit("-M", 1)[-1]
    try:
        return (float(tail), designation)
    except ValueError:
        return (0.0, designation)


class HexBolt(BaseModel):
    """An ISO 4014/4017 hexagon-head bolt's standardized head geometry.

    ``width_across_flats`` is the wrench size s and the pocket a design must clear;
    ``head_height`` is the head height k, which adds to the joint's stack.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    width_across_flats: Length
    head_height: Length

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence
        trail, mirroring :meth:`anvilate.standards.Bearing.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownHexBoltError(KeyError):
    """A requested hex-bolt designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for hex bolt {designation!r}{hint}")


class HexBoltTable:
    """ISO 4014/4017 hexagon-head bolt head geometry keyed by designation
    (``ISO4014-M5``)."""

    def __init__(self, bolts: dict[str, HexBolt]) -> None:
        self._bolts = bolts

    def has_bolt(self, designation: str) -> bool:
        return designation in self._bolts

    def designations(self) -> list[str]:
        return sorted(self._bolts, key=_bolt_key)

    def get(self, designation: str) -> HexBolt:
        """Return the head-geometry record for ``designation``.

        Raises :class:`UnknownHexBoltError` (with near-misses) rather than
        estimating dimensions for an unrecorded bolt.
        """
        try:
            return self._bolts[designation]
        except KeyError:
            raise UnknownHexBoltError(
                designation, difflib.get_close_matches(designation, self._bolts, n=3)
            ) from None

    def __len__(self) -> int:
        return len(self._bolts)


def _load_bolts(text: str) -> dict[str, HexBolt]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"ISO 4014/4017 {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    bolts: dict[str, HexBolt] = {}
    for designation, row in doc["bolts"].items():
        bolts[designation] = HexBolt.model_validate(
            {
                "designation": designation,
                "width_across_flats": _prop(row["width_across_flats"], "width across flats"),
                "head_height": _prop(row["head_height"], "head height"),
            }
        )
    return bolts


def default_hex_bolt_table() -> HexBoltTable:
    """The bundled ISO 4014/4017 hexagon-head bolt head-geometry table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "hex_bolts.yaml").read_text(encoding="utf-8")
    return HexBoltTable(_load_bolts(text))
