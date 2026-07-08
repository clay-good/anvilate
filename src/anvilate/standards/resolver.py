"""A reference resolver backed by the standards databases.

The spec layer validates material and component references against an injected
resolver (its ``ReferenceResolver`` protocol). This module supplies one backed
by the real databases, so "which references exist" has a single source of
truth: materials from the materials database, NEMA frames from the components
database. Component families without a dimension table yet (extrusions,
fasteners) are covered by a small static seed set until those tables land.
"""

from __future__ import annotations

from .components import ComponentsDatabase, default_components_db
from .materials import MaterialsDatabase, default_materials_db

__all__ = ["StandardsResolver", "default_standards_resolver"]

# Standard-component IDs that are known but have no dimension table yet. Kept
# here so the resolver stays the single place that answers "does this reference
# exist"; each entry is a candidate for its own components-database slice.
_SEED_COMPONENTS = frozenset({"EXT-4040", "EXT-2020", "ISO4762-M5"})


class StandardsResolver:
    """Resolves materials against the materials database and components against
    the components database (plus a static seed for families without a table).
    Satisfies the spec layer's ``ReferenceResolver`` protocol."""

    def __init__(
        self,
        materials: MaterialsDatabase,
        components: ComponentsDatabase,
        extra_components: frozenset[str],
    ) -> None:
        self._materials = materials
        self._components = components
        self._extra_components = extra_components

    def has_material(self, ref: str) -> bool:
        return self._materials.has_material(ref)

    def has_component(self, ref: str) -> bool:
        return self._components.has_component(ref) or ref in self._extra_components

    def known_materials(self) -> list[str]:
        return self._materials.known_materials()

    def known_components(self) -> list[str]:
        return sorted(set(self._components.known_components()) | self._extra_components)


def default_standards_resolver() -> StandardsResolver:
    """The resolver backed by the bundled seed databases."""
    return StandardsResolver(
        default_materials_db(),
        default_components_db(),
        _SEED_COMPONENTS,
    )
