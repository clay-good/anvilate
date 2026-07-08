"""Anvilate standards & materials data: curated, provenance-tagged, offline.

The bundled databases are the sole source of standard dimensions and material
property values in the pipeline — the "retrieval, not recall" rule. This slice
ships the materials database; standard-component dimension tables land here as
they are built out (see openspec/specs/standards-data/).
"""

from __future__ import annotations

from .components import (
    ComponentsDatabase,
    NemaFrame,
    UnknownComponentError,
    default_components_db,
)
from .materials import (
    Material,
    MaterialPropertyUnavailable,
    MaterialsDatabase,
    PropertyCitation,
    QuantityProperty,
    ScalarProperty,
    UnknownMaterialError,
    default_materials_db,
)
from .resolver import StandardsResolver, default_standards_resolver
from .threads import (
    ClearanceHoleTable,
    Fit,
    UnknownThreadSizeError,
    default_clearance_table,
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
    "Fit",
    "ClearanceHoleTable",
    "UnknownThreadSizeError",
    "default_clearance_table",
    "StandardsResolver",
    "default_standards_resolver",
]
