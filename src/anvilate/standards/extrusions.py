"""T-slot aluminum extrusion profile dimensions.

Modular T-slot framing profiles keyed by the square module width (the series:
20/30/40/45 mm). A mating bracket designs against the profile width (the bolting
face and the grid spacing) and the T-slot width (the mouth a T-nut engages), so
those are what this table records.

Unlike the ISO fastener tables, T-slot cross-sections are not covered by a single
dimension standard — vendors diverge — so the bundled values follow the common
Bosch Rexroth / Misumi HFS metric convention and the source standard is a vendor
convention, tagged as such in the provenance. See ``data/extrusions.yaml``.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import PropertyCitation, QuantityProperty, dimensioned

__all__ = [
    "ExtrusionProfile",
    "ExtrusionTable",
    "UnknownExtrusionError",
    "default_extrusion_table",
]


Length = Annotated[QuantityProperty, dimensioned("[length]", "extrusion dimension")]


def _profile_key(designation: str) -> tuple[float, str]:
    """Sort key: the module width after the ``EXT-`` prefix (first two digits of
    the NNNN size), then the full designation, so ``EXT-2020`` sorts before
    ``EXT-4040``."""
    tail = designation.rsplit("-", 1)[-1]
    digits = "".join(c for c in tail if c.isdigit())
    # The NNNN designation repeats the square module (2020, 3030); take its width.
    width = digits[: len(digits) // 2] if digits else ""
    try:
        return (float(width), designation)
    except ValueError:
        return (0.0, designation)


class ExtrusionProfile(BaseModel):
    """A T-slot extrusion profile's mating dimensions.

    ``profile_width`` is the square module width (the bolting face and the grid
    spacing); ``slot_width`` is the T-slot mouth a T-nut or bolt head engages.
    The slot width is a vendor convention, not an ISO standard — see the table's
    provenance and the data file's vendor-variance note.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    designation: str
    name: str
    profile_width: Length
    slot_width: Length

    def citations(self) -> dict[str, PropertyCitation]:
        """Every dimension's citation, keyed by property name — the evidence
        trail, mirroring :meth:`anvilate.standards.NemaFrame.citations`."""
        out: dict[str, PropertyCitation] = {}
        for field in type(self).model_fields:
            value = getattr(self, field)
            if isinstance(value, QuantityProperty):
                out[field] = value.citation
        return out


class UnknownExtrusionError(KeyError):
    """A requested extrusion designation has no record in the table."""

    def __init__(self, designation: str, suggestions: list[str]) -> None:
        self.designation = designation
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"no record for extrusion {designation!r}{hint}")


class ExtrusionTable:
    """T-slot extrusion profile dimensions keyed by designation (``EXT-2020``)."""

    def __init__(self, profiles: dict[str, ExtrusionProfile]) -> None:
        self._profiles = profiles

    def has_profile(self, designation: str) -> bool:
        return designation in self._profiles

    def designations(self) -> list[str]:
        return sorted(self._profiles, key=_profile_key)

    def get(self, designation: str) -> ExtrusionProfile:
        """Return the profile record for ``designation``.

        Raises :class:`UnknownExtrusionError` (with near-misses) rather than
        estimating dimensions for an unrecorded profile.
        """
        try:
            return self._profiles[designation]
        except KeyError:
            raise UnknownExtrusionError(
                designation, difflib.get_close_matches(designation, self._profiles, n=3)
            ) from None

    def __len__(self) -> int:
        return len(self._profiles)


def _load_profiles(text: str) -> dict[str, ExtrusionProfile]:
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})

    def _prop(value_mm: float, kind: str) -> dict:
        return {
            "quantity": {"magnitude": float(value_mm), "unit": "mm"},
            "citation": {
                "source": dataset["source"],
                "condition": f"T-slot {kind}",
                "license": dataset["license"],
                "retrieved": dataset["retrieved"],
            },
        }

    profiles: dict[str, ExtrusionProfile] = {}
    for designation, row in doc["profiles"].items():
        profiles[designation] = ExtrusionProfile.model_validate(
            {
                "designation": designation,
                "name": row["name"],
                "profile_width": _prop(row["profile_width"], "profile width"),
                "slot_width": _prop(row["slot_width"], "slot width (vendor convention)"),
            }
        )
    return profiles


def default_extrusion_table() -> ExtrusionTable:
    """The bundled T-slot extrusion profile table (common metric convention)."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "extrusions.yaml").read_text(encoding="utf-8")
    return ExtrusionTable(_load_profiles(text))
