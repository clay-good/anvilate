"""Standard-component dimension tables: the mounting geometry a mating part
designs against.

Following the same "retrieval, not recall" rule as the materials database, the
standardized mounting dimensions of standard components come from here, never
from a model's memory. This slice covers NEMA stepper motor frames; other
component families (extrusions, fasteners, bearings) land here as they are
built out. Only the *standardized* dimensions are recorded — the mounting
bolt-square, pilot boss, and faceplate — not the manufacturer-specific body
length.
"""

from __future__ import annotations

import difflib
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict

from .records import QuantityProperty, dimensioned

__all__ = [
    "NemaFrame",
    "ComponentsDatabase",
    "UnknownComponentError",
    "default_components_db",
]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Length = Annotated[QuantityProperty, dimensioned("[length]", "length")]


class NemaFrame(_Base):
    """A NEMA stepper frame's standardized mounting geometry.

    ``bolt_spacing`` is the pitch of the square mounting-hole pattern;
    ``pilot_diameter`` the raised locating boss; ``mounting_hole`` the clearance
    hole a bracket drills for the mounting screws.
    """

    id: str
    name: str
    bundled: bool = True

    faceplate_width: Length
    bolt_spacing: Length
    pilot_diameter: Length
    mounting_hole: Length


class UnknownComponentError(KeyError):
    """A referenced standard-component ID is not in the database."""

    def __init__(self, component_id: str, suggestions: list[str]) -> None:
        self.component_id = component_id
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"unknown component {component_id!r}{hint}")


class ComponentsDatabase:
    """A queryable set of NEMA frame records. Satisfies the component half of the
    spec layer's reference-resolver protocol
    (:meth:`has_component`, :meth:`known_components`)."""

    def __init__(self, frames: dict[str, NemaFrame]) -> None:
        self._frames = frames

    def has_component(self, component_id: str) -> bool:
        return component_id in self._frames

    def known_components(self) -> list[str]:
        return sorted(self._frames)

    def get(self, component_id: str) -> NemaFrame:
        """Return a record or raise :class:`UnknownComponentError` with near-misses."""
        try:
            return self._frames[component_id]
        except KeyError:
            raise UnknownComponentError(
                component_id,
                difflib.get_close_matches(component_id, self._frames, n=3),
            ) from None

    def __len__(self) -> int:
        return len(self._frames)


def _load_frames(text: str) -> dict[str, NemaFrame]:
    """Parse the NEMA frame YAML, filling shared dataset-level citation fields."""
    doc = yaml.safe_load(text)
    dataset = doc.get("dataset", {})
    fallback = {
        "license": dataset.get("license"),
        "retrieved": dataset.get("retrieved"),
        "source": dataset.get("source"),
    }

    def _fill(node: object) -> None:
        if isinstance(node, dict):
            if "citation" in node and isinstance(node["citation"], dict):
                for key, value in fallback.items():
                    node["citation"].setdefault(key, value)
            for child in node.values():
                _fill(child)

    frames: dict[str, NemaFrame] = {}
    for component_id, record in doc["frames"].items():
        _fill(record)
        frames[component_id] = NemaFrame.model_validate({"id": component_id, **record})
    return frames


def default_components_db() -> ComponentsDatabase:
    """The bundled seed NEMA frame database."""
    from importlib.resources import files

    text = (files("anvilate.standards") / "data" / "nema_frames.yaml").read_text(encoding="utf-8")
    return ComponentsDatabase(_load_frames(text))
