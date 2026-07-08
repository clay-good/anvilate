"""A reference resolver backed by the standards databases.

The spec layer validates material and component references against an injected
resolver (its ``ReferenceResolver`` protocol). This module supplies one backed
by the real materials database, so "which materials exist" has a single source
of truth. Standard components still come from a fixed seed set until a component
dimension database lands.
"""

from __future__ import annotations

from .materials import MaterialsDatabase, default_materials_db

__all__ = ["StandardsResolver", "default_standards_resolver"]

# Standard-component identifiers with a golden-path record, pending a component
# dimension database. Kept here so the resolver stays the single place that
# answers "does this reference exist".
_SEED_COMPONENTS = frozenset(
    {"NEMA17", "NEMA23", "EXT-4040", "EXT-2020", "ISO4762-M5"}
)


class StandardsResolver:
    """Resolves materials against the materials database and components against
    the seed component set. Satisfies the spec layer's ``ReferenceResolver``
    protocol."""

    def __init__(self, materials: MaterialsDatabase, components: frozenset[str]) -> None:
        self._materials = materials
        self._components = components

    def has_material(self, ref: str) -> bool:
        return self._materials.has_material(ref)

    def has_component(self, ref: str) -> bool:
        return ref in self._components

    def known_materials(self) -> list[str]:
        return self._materials.known_materials()

    def known_components(self) -> list[str]:
        return sorted(self._components)


def default_standards_resolver() -> StandardsResolver:
    """The resolver backed by the bundled seed databases."""
    return StandardsResolver(default_materials_db(), _SEED_COMPONENTS)
