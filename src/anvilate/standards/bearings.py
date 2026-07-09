"""Rolling-bearing boundary dimensions (deep-groove ball bearings, ISO 15).

A bearing's boundary dimensions — bore, outer diameter, and width — are
standardized across manufacturers by ISO 15, so a shaft seat and a housing bore
design against them directly. They are retrieved from this table, not recalled.
Load ratings and internal geometry vary by manufacturer and bearing design, so
they are deliberately omitted here (the same "mount, not body" rule the NEMA
frame table follows); a mating part sizes to the boundary, not the catalogue.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "Bearing",
    "BearingTable",
    "UnknownBearingError",
    "default_bearing_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "bearing dimension")]


def _bearing_key(designation: str) -> tuple[int, str]:
    """Sort key: the numeric part of the designation, then the full string, so
    ``608`` sorts before ``6000`` and any lettered suffix breaks ties stably."""
    digits = "".join(c for c in designation if c.isdigit())
    return (int(digits) if digits else 0, designation)


class Bearing(BaseModel):
    """A deep-groove ball bearing's ISO 15 boundary dimensions.

    ``bore`` is the inner (shaft) diameter, ``outer_diameter`` the housing-seat
    diameter, and ``width`` the axial thickness.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    bundled: bool = True  # False marks a user- or team-local extension record
    bore: Length
    outer_diameter: Length
    width: Length

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence
        trail, mirroring :meth:`anvilate.standards.NemaFrame.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownBearingError(KeyError):
    """A requested bearing designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for bearing {designation!r}{hint}")


class BearingTable:
    """Deep-groove ball bearing boundary dimensions keyed by designation."""

    def __init__(self, bearings: dict[str, Bearing]) -> None:
        self._bearings = bearings

    def has_bearing(self, designation: str) -> bool:
        return designation in self._bearings

    def designations(self) -> list[str]:
        return sorted(self._bearings, key=_bearing_key)

    def get(self, designation: str) -> Bearing:
        """Return the boundary-dimension record for ``designation``.

        Raises :class:`UnknownBearingError` (with near-misses) rather than
        estimating dimensions for an unrecorded bearing.
        """
        try:
            return self._bearings[designation]
        except KeyError:
            raise UnknownBearingError(
                designation, difflib.get_close_matches(designation, self._bearings, n=3)
            ) from None

    def extension_ids(self) -> list[str]:
        """Designations of extension (user/team-local) records — distinguishable
        in reports, mirroring :meth:`anvilate.standards.MaterialsDatabase.extension_ids`."""
        return sorted(d for d, b in self._bearings.items() if not b.bundled)

    def extended(self, extension_text: str) -> BearingTable:
        """Return a new table with ``extension_text``'s records overlaid.

        Extension records are marked non-bundled and override any bundled record
        of the same designation, so a team can register a special or non-standard
        bearing without forking the bundled table. The bundled table is left
        unchanged — mirrors :meth:`anvilate.standards.MaterialsDatabase.extended`.
        """
        overlay = _load_bearings(extension_text, bundled=False)
        return BearingTable({**self._bearings, **overlay})

    def __len__(self) -> int:
        return len(self._bearings)


def _load_bearings(text: str, *, bundled: bool = True) -> dict[str, Bearing]:
    """Parse a bearing YAML document. ``bundled`` tags the records' origin (a
    bundled dataset vs a user/team extension), so reports can distinguish
    company-local records."""
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"ISO 15 boundary {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    bearings: dict[str, Bearing] = {}
    for designation, row in doc["bearings"].items():
        bearings[designation] = Bearing.model_validate(
            {
                "designation": designation,
                "bundled": bundled,
                "bore": _prop(row["bore"], "bore"),
                "outer_diameter": _prop(row["outer_diameter"], "outer diameter"),
                "width": _prop(row["width"], "width"),
            }
        )
    return bearings


def default_bearing_table() -> BearingTable:
    """The bundled ISO 15 deep-groove ball bearing boundary-dimension table."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "bearings.yaml").read_text(encoding="utf-8")
    return BearingTable(_load_bearings(text))
