"""Anvilate standards & materials data: curated, provenance-tagged, offline.

The bundled databases are the sole source of standard dimensions and material
property values in the pipeline — the "retrieval, not recall" rule. This package
ships the materials database, the NEMA stepper-frame component database, the
ISO 273 clearance-hole and ISO 261/724 metric-thread tables, the ISO 15 ball
bearing boundary-dimension table, the ISO 2338 dowel-pin table, the ISO 4762
socket-head cap screw head-geometry table, the ISO 7089 plain-washer table, and
the DB-backed reference resolver. Further
component families land here as they are built out (see
openspec/specs/standards-data/).
"""

from __future__ import annotations

from .bearings import (
    Bearing,
    BearingTable,
    UnknownBearingError,
    default_bearing_table,
)
from .capscrews import (
    CapScrewTable,
    SocketHeadCapScrew,
    UnknownCapScrewError,
    default_cap_screw_table,
)
from .components import (
    ComponentsDatabase,
    NemaFrame,
    UnknownComponentError,
    default_components_db,
)
from .dowels import (
    DowelPin,
    DowelPinTable,
    UnknownDowelPinError,
    default_dowel_pin_table,
)
from .materials import (
    Material,
    MaterialPropertyUnavailable,
    MaterialsDatabase,
    UnknownMaterialError,
    default_materials_db,
)
from .records import PropertyCitation, QuantityProperty, ScalarProperty
from .resolver import StandardsResolver, default_standards_resolver
from .threads import (
    ClearanceHoleTable,
    Fit,
    MetricThread,
    MetricThreadTable,
    UnknownThreadSizeError,
    default_clearance_table,
    default_thread_table,
)
from .washers import (
    PlainWasher,
    UnknownWasherError,
    WasherTable,
    default_washer_table,
)

__all__ = [
    "Material",
    "MaterialsDatabase",
    "PropertyCitation",
    "QuantityProperty",
    "ScalarProperty",
    "UnknownMaterialError",
    "MaterialPropertyUnavailable",
    "default_materials_db",
    "NemaFrame",
    "ComponentsDatabase",
    "UnknownComponentError",
    "default_components_db",
    "Bearing",
    "BearingTable",
    "UnknownBearingError",
    "default_bearing_table",
    "DowelPin",
    "DowelPinTable",
    "UnknownDowelPinError",
    "default_dowel_pin_table",
    "SocketHeadCapScrew",
    "CapScrewTable",
    "UnknownCapScrewError",
    "default_cap_screw_table",
    "PlainWasher",
    "WasherTable",
    "UnknownWasherError",
    "default_washer_table",
    "Fit",
    "ClearanceHoleTable",
    "MetricThread",
    "MetricThreadTable",
    "UnknownThreadSizeError",
    "default_clearance_table",
    "default_thread_table",
    "StandardsResolver",
    "default_standards_resolver",
]
