"""Loading, validating, and serializing Design Specs.

A spec is rejected before any downstream processing if it fails schema
validation (wrong type, unknown key, out-of-range value) — with the offending
path named — or if it references a material or component absent from the
databases. Specs serialize to plain YAML/JSON so line-based diff tools produce
meaningful diffs between revisions.
"""

from __future__ import annotations

import difflib
from typing import Any

import yaml
from pydantic import ValidationError

from .ir import DesignSpec
from .references import ReferenceResolver, UnknownReferenceError, default_resolver
from .version import migrate_to_current

__all__ = [
    "SpecValidationError",
    "parse_spec",
    "load_spec_yaml",
    "dump_spec_yaml",
    "validate_references",
    "json_schema",
]


class SpecValidationError(ValueError):
    """A spec failed schema validation. Carries the offending field paths."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        lines = [f"  {e['loc']}: {e['msg']}" for e in errors]
        super().__init__("spec failed validation:\n" + "\n".join(lines))

    @classmethod
    def _from_pydantic(cls, exc: ValidationError) -> SpecValidationError:
        errors = [
            {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]} for e in exc.errors()
        ]
        return cls(errors)


def parse_spec(data: dict) -> DesignSpec:
    """Parse and validate a raw spec dict into a typed :class:`DesignSpec`.

    Applies schema migrations first, then validates. Raises
    :class:`SpecValidationError` naming each offending path on failure.
    """
    migrated = migrate_to_current(data)
    try:
        return DesignSpec.model_validate(migrated)
    except ValidationError as exc:
        raise SpecValidationError._from_pydantic(exc) from exc


def load_spec_yaml(text: str) -> DesignSpec:
    """Load and validate a spec from a YAML (or JSON) document."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise SpecValidationError([{"loc": "<root>", "msg": "spec must be a mapping"}])
    return parse_spec(data)


def dump_spec_yaml(spec: DesignSpec) -> str:
    """Serialize a spec to deterministic, diff-friendly YAML."""
    data = spec.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def validate_references(spec: DesignSpec, resolver: ReferenceResolver | None = None) -> None:
    """Check every material and standard-component reference resolves.

    Validates against any :class:`~anvilate.spec.references.ReferenceResolver`
    (the static seed, or a standards-database-backed resolver), raising
    :class:`~anvilate.spec.references.UnknownReferenceError` with near-miss
    suggestions for the first unresolved identifier.
    """
    res = resolver or default_resolver()
    if not res.has_material(spec.material.ref):
        raise UnknownReferenceError(
            spec.material.ref,
            "material",
            difflib.get_close_matches(spec.material.ref, res.known_materials(), n=3),
        )
    for iface in spec.interfaces:
        if iface.type == "standard_component" and not res.has_component(iface.ref):
            raise UnknownReferenceError(
                iface.ref,
                "component",
                difflib.get_close_matches(iface.ref, res.known_components(), n=3),
            )


def json_schema() -> dict:
    """The JSON Schema for the Design Spec IR."""
    return DesignSpec.model_json_schema()
