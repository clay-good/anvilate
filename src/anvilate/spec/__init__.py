"""The Design Spec IR: Anvilate's durable, typed, diffable statement of intent.

The spec — not the chat — is the product. This package defines the schema
(:mod:`.ir`), value provenance (:mod:`.provenance`), reference resolution
(:mod:`.references`), versioning/migration (:mod:`.version`), and the
load/validate/serialize surface (:mod:`.validate`).
"""

from __future__ import annotations

from .ir import (
    SCHEMA_VERSION,
    AcceptanceCriteria,
    ChainLink,
    Constraints,
    DesignSpec,
    DimensionChain,
    Envelope,
    HolePattern,
    ImportedInterface,
    InterfaceContract,
    LoadCase,
    LoadKind,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    StandardComponentInterface,
    ToleranceDimension,
    ValidationTier,
)
from .provenance import Origin, Provenanced
from .references import (
    ReferenceResolver,
    StaticReferenceResolver,
    UnknownReferenceError,
    default_resolver,
)
from .validate import (
    SpecValidationError,
    dump_spec_yaml,
    json_schema,
    load_spec_yaml,
    parse_spec,
    validate_references,
)
from .version import UnsupportedSchemaVersion, migrate_to_current

__all__ = [
    "SCHEMA_VERSION",
    "DesignSpec",
    "MaterialRef",
    "Manufacturing",
    "ManufacturingProcess",
    "StandardComponentInterface",
    "ImportedInterface",
    "InterfaceContract",
    "HolePattern",
    "ToleranceDimension",
    "ChainLink",
    "DimensionChain",
    "LoadCase",
    "LoadKind",
    "Constraints",
    "Envelope",
    "AcceptanceCriteria",
    "ValidationTier",
    "Origin",
    "Provenanced",
    "ReferenceResolver",
    "StaticReferenceResolver",
    "UnknownReferenceError",
    "default_resolver",
    "SpecValidationError",
    "parse_spec",
    "load_spec_yaml",
    "dump_spec_yaml",
    "validate_references",
    "json_schema",
    "migrate_to_current",
    "UnsupportedSchemaVersion",
]
