"""A reference resolver backed by the standards databases.

The spec layer validates material and component references against an injected
resolver (its ``ReferenceResolver`` protocol). This module supplies one backed
by the real databases, so "which references exist" has a single source of
truth: materials from the materials database, NEMA frames from the components
database, ball bearings from the bearing table, dowel pins from the dowel-pin
table, socket-head cap screws from the cap-screw table, plain washers from the
washer table, hex nuts from the hex-nut table, hex bolts from the hex-bolt table,
and T-slot extrusions from the extrusion table. A small static seed set remains
as the extension point for the next untabled component family.
"""

from __future__ import annotations

from .bearings import BearingTable, default_bearing_table
from .capscrews import CapScrewTable, default_cap_screw_table
from .components import ComponentsDatabase, default_components_db
from .dowels import DowelPinTable, default_dowel_pin_table
from .extrusions import ExtrusionTable, default_extrusion_table
from .hexbolts import HexBoltTable, default_hex_bolt_table
from .hexnuts import HexNutTable, default_hex_nut_table
from .materials import MaterialsDatabase, default_materials_db
from .washers import WasherTable, default_washer_table

__all__ = ["StandardsResolver", "default_standards_resolver"]

# Standard-component IDs that are known but have no dimension table yet. Every
# seed family now has a real table, so this is empty; it is kept as the extension
# point the resolver reserves for the next untabled component family.
_SEED_COMPONENTS: frozenset[str] = frozenset()


class StandardsResolver:
    """Resolves materials against the materials database and components against
    the components database, bearing table, dowel-pin table, cap-screw table, and
    washer table, hex-nut table, hex-bolt table, and extrusion table (plus a
    static seed for families without a table). Satisfies the spec layer's
    ``ReferenceResolver`` protocol."""

    def __init__(
        self,
        materials: MaterialsDatabase,
        components: ComponentsDatabase,
        bearings: BearingTable,
        dowels: DowelPinTable,
        cap_screws: CapScrewTable,
        washers: WasherTable,
        hex_nuts: HexNutTable,
        hex_bolts: HexBoltTable,
        extrusions: ExtrusionTable,
        extra_components: frozenset[str],
    ) -> None:
        self._materials = materials
        self._components = components
        self._bearings = bearings
        self._dowels = dowels
        self._cap_screws = cap_screws
        self._washers = washers
        self._hex_nuts = hex_nuts
        self._hex_bolts = hex_bolts
        self._extrusions = extrusions
        self._extra_components = extra_components

    def has_material(self, ref: str) -> bool:
        return self._materials.has_material(ref)

    def has_component(self, ref: str) -> bool:
        return (
            self._components.has_component(ref)
            or self._bearings.has_bearing(ref)
            or self._dowels.has_pin(ref)
            or self._cap_screws.has_screw(ref)
            or self._washers.has_washer(ref)
            or self._hex_nuts.has_nut(ref)
            or self._hex_bolts.has_bolt(ref)
            or self._extrusions.has_profile(ref)
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
            | set(self._washers.designations())
            | set(self._hex_nuts.designations())
            | set(self._hex_bolts.designations())
            | set(self._extrusions.designations())
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
        default_washer_table(),
        default_hex_nut_table(),
        default_hex_bolt_table(),
        default_extrusion_table(),
        _SEED_COMPONENTS,
    )
