"""Anvilate standards & materials data: curated, provenance-tagged, offline.

The bundled databases are the sole source of standard dimensions and material
property values in the pipeline — the "retrieval, not recall" rule. This slice
ships the materials database; standard-component dimension tables land here as
they are built out (see openspec/specs/standards-data/).
"""

from __future__ import annotations

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

__all__ = [
    "Material",
    "MaterialsDatabase",
    "PropertyCitation",
    "QuantityProperty",
    "ScalarProperty",
    "UnknownMaterialError",
    "MaterialPropertyUnavailable",
    "default_materials_db",
]
