"""A reference resolver backed by the standards databases.

The spec layer validates material and component references against an injected
resolver (its ``ReferenceResolver`` protocol). This module supplies one backed
by the real databases, so "which references exist" has a single source of
truth: materials from the materials database, NEMA frames from the components
database, ball bearings from the bearing table, dowel pins from the dowel-pin
table, and socket-head cap screws from the cap-screw table. Component families
without a dimension table yet (extrusions) are covered by a small static seed
set until those tables land.
"""

from __future__ import annotations

from .bearings import BearingTable, default_bearing_table
from .capscrews import CapScrewTable, default_cap_screw_table
from .components import ComponentsDatabase, default_components_db
from .dowels import DowelPinTable, default_dowel_pin_table
from .materials import MaterialsDatabase, default_materials_db

__all__ = ["StandardsResolver", "default_standards_resolver"]

# Standard-component IDs that are known but have no dimension table yet. Kept
# here so the resolver stays the single place that answers "does this reference
# exist"; each entry is a candidate for its own components-database slice.
_SEED_COMPONENTS = frozenset({"EXT-4040", "EXT-2020"})


class StandardsResolver:
    """Resolves materials against the materials database and components against
    the components database, bearing table, dowel-pin table, and cap-screw table
    (plus a static seed for families without a table). Satisfies the spec layer's
    ``ReferenceResolver`` protocol."""

    def __init__(
        self,
        materials: MaterialsDatabase,
        components: ComponentsDatabase,
        bearings: BearingTable,
        dowels: DowelPinTable,
        cap_screws: CapScrewTable,
        extra_components: frozenset[str],
    ) -> None:
        self._materials = materials
        self._components = components
        self._bearings = bearings
        self._dowels = dowels
        self._cap_screws = cap_screws
        self._extra_components = extra_components

    def has_material(self, ref: str) -> bool:
        return self._materials.has_material(ref)

    def has_component(self, ref: str) -> bool:
        return (
            self._components.has_component(ref)
            or self._bearings.has_bearing(ref)
            or self._dowels.has_pin(ref)
            or self._cap_screws.has_screw(ref)
            or ref in self._extra_components
        )

    def known_materials(self) -> list[str]:
        return self._materials.known_materials()

    def known_components(self) -> list[str]:
        return sorted(
            set(self._components.known_components())
            | set(self._bearings.designations())
            | set(self._dowels.designations())
            | set(self._cap_screws.designations())
            | self._extra_components
        )


def default_standards_resolver() -> StandardsResolver:
    """The resolver backed by the bundled seed databases."""
    return StandardsResolver(
        default_materials_db(),
        default_components_db(),
        default_bearing_table(),
        default_dowel_pin_table(),
        default_cap_screw_table(),
        _SEED_COMPONENTS,
    )
