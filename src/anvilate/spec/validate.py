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
    "validate_dimension_graph",
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


class _RefuseDuplicateKeys(yaml.SafeLoader):
    """A loader that refuses a mapping declaring the same key twice.

    PyYAML takes the last one and says nothing, so a spec with ``constraints:`` written
    twice is screened against whichever copy happens to be lower in the file — and the
    declaration the engineer wrote first is nowhere in the card, the stderr lines or the
    evidence bundle. A padeye declaring ``min_safety_factor: 10.0`` and then, forty lines
    down after a paste, ``min_safety_factor: 2.0`` **passes**, and nothing in the run
    mentions the 10. That is the same defect as an ignored keyword — a declaration the user
    makes that nothing answers — arriving through the document rather than through a field
    name.

    Refusing is what the YAML specification itself says to do: "it is an error for two equal
    keys to appear in the same mapping node". So this is a malformed document like a tab in
    the indentation, it is reported the same way, and both marks are carried — the line the
    key is repeated on is where the reader looks, and the line it was first declared on is
    the one they have to compare it against.
    """

    def construct_mapping(self, node, deep: bool = False):
        first: dict[Any, Any] = {}
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                seen = key in first
            except TypeError:
                # An unhashable key — a list or a mapping used as one. It cannot collide
                # with anything here and PyYAML refuses it a moment later on its own terms.
                continue
            if seen:
                raise yaml.MarkedYAMLError(
                    context=f"the key {key!r} was already declared at line "
                    f"{first[key].line + 1}, column {first[key].column + 1}",
                    context_mark=None,
                    problem="a key declared twice silently discards the earlier "
                    "declaration, so the document does not say what it appears to",
                    problem_mark=key_node.start_mark,
                )
            first[key] = key_node.start_mark
        return super().construct_mapping(node, deep=deep)


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
    """Load and validate a spec from a YAML (or JSON) document.

    A document that is not well-formed YAML is a :class:`SpecValidationError` like any other
    bad document, carrying the line and column PyYAML found the trouble at. A key declared
    twice is one of those documents — see :class:`_RefuseDuplicateKeys` for why taking the
    last one quietly is the worst of the three available answers.

    It used to be a traceback. `yaml.YAMLError` descends from `Exception` and not from
    `ValueError`, so it fell through every caller's guard — including the CLI's, which
    catches `ValueError`, `TypeError` and `KeyError` — and `anvilate check` answered a tab in
    the indentation with a stack trace through `yaml/scanner.py` and exit 1, the code that
    means a part failed. A tab is one of the commonest things to get wrong in a YAML file,
    and the answer to it is a sentence with a line number in it.
    """
    try:
        # `yaml.load` with an explicit SafeLoader subclass, which is `safe_load` plus the
        # duplicate-key refusal; nothing here can construct an arbitrary Python object.
        data = yaml.load(text, Loader=_RefuseDuplicateKeys)
    except Exception as failure:
        # `except Exception`, not `yaml.YAMLError`, and measuring is what settled it. Over 21
        # malformed documents `safe_load` answers with `YAMLError` twenty times and, for
        # `a: 2026-13-45`, with a plain `ValueError: month must be in 1..12` out of PyYAML's
        # date constructor. YAML resolves any `YYYY-MM-DD`-shaped scalar to a date whatever
        # field it is in, so one typo'd month anywhere in a document reached the CLI as
        # `anvilate check: month must be in 1..12` — naming no file, no line and no field.
        #
        # The `try` wraps exactly one call whose only job is to read the text, so any failure
        # of it is an unreadable document and gets the same sentence. The position is carried
        # when PyYAML gives one and the reason always is.
        mark = getattr(failure, "problem_mark", None)
        where = f"line {mark.line + 1}, column {mark.column + 1}" if mark is not None else "<root>"
        problem = getattr(failure, "problem", None) or str(failure).split("\n")[0]
        context = getattr(failure, "context", None)
        detail = f"{context}, {problem}" if context else str(problem)
        raise SpecValidationError(
            [{"loc": where, "msg": f"the document is not valid YAML — {detail}"}]
        ) from failure
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


def validate_dimension_graph(spec: DesignSpec) -> None:
    """Check the toleranced-dimension graph is internally consistent.

    Validates that dimension tags are unique, stack-up chain names are unique,
    and every chain link references a declared dimension. Reports every problem
    at once (not just the first) via :class:`SpecValidationError`, so an author
    fixes a whole spec in one pass. This is the structural counterpart to
    :func:`validate_references`, which resolves external database identifiers.
    """
    errors: list[dict[str, Any]] = []
    declared: set[str] = set()
    for i, dim in enumerate(spec.dimensions):
        if dim.tag in declared:
            errors.append(
                {"loc": f"dimensions.{i}.tag", "msg": f"duplicate dimension tag {dim.tag!r}"}
            )
        declared.add(dim.tag)
    seen_chains: set[str] = set()
    for i, chain in enumerate(spec.chains):
        if chain.name in seen_chains:
            errors.append(
                {"loc": f"chains.{i}.name", "msg": f"duplicate chain name {chain.name!r}"}
            )
        seen_chains.add(chain.name)
        for j, link in enumerate(chain.links):
            if link.dimension not in declared:
                errors.append(
                    {
                        "loc": f"chains.{i}.links.{j}.dimension",
                        "msg": f"chain link references unknown dimension {link.dimension!r}",
                    }
                )
    if errors:
        raise SpecValidationError(errors)


def json_schema() -> dict:
    """The JSON Schema for the Design Spec IR."""
    return DesignSpec.model_json_schema()
