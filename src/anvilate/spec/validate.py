"""Loading, validating, and serializing Design Specs.

A spec is rejected before any downstream processing if it fails schema
validation (wrong type, unknown key, out-of-range value) — with the offending
path named — or if it references a material or component absent from the
databases. Specs serialize to plain YAML/JSON so line-based diff tools produce
meaningful diffs between revisions.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Mapping
from math import isfinite
from typing import Any, get_args

import yaml
from pydantic import BaseModel, ValidationError

from .._models import _refusal_line
from .ir import SCHEMA_VERSION, DesignSpec
from .provenance import _BareValue
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


# How each required top-level field is spelled, in a line that validates. A document missing
# one is told this line rather than pydantic's "Field required", which names the field and
# says nothing about what goes in it. tests/test_spec.py builds a Design Spec from these
# lines alone, so the advice cannot drift from what the loader accepts.
_REQUIRED_FIELD_EXAMPLES: dict[str, str] = {
    "name": "name: bracket-01",
    "description": 'description: "A motor mount bracket for a NEMA 23 stepper."',
    "units": "units: {value: SI, origin: user_stated}",
    "material": "material: {ref: AA-6061-T6}",
    "manufacturing": "manufacturing: {process: cnc_milling}",
    "acceptance": "acceptance: {tiers: [T1_analytical]}",
}


# The keys a document reaches for when it means `anvilate_spec`, none of them close enough in
# spelling for a near-miss match to find it.
_VERSION_SPELLINGS = frozenset({"version", "schema_version", "spec_version", "schema"})


def _model_in(annotation: Any) -> type[BaseModel] | None:
    """The one pydantic model an annotation holds, through Optional, tuples and Annotated."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    found = {model for arg in get_args(annotation) if (model := _model_in(arg)) is not None}
    return found.pop() if len(found) == 1 else None


def _siblings(location: tuple[Any, ...], root: type[BaseModel]) -> list[str]:
    """The field names beside the last part of ``location``, or none when the path leaves
    the models (a mapping of element parameters, say)."""
    model: type[BaseModel] | None = root
    for part in location[:-1]:
        if isinstance(part, int):
            continue
        field = model.model_fields.get(part) if model is not None else None
        model = _model_in(field.annotation) if field is not None else None
        if model is None:
            return []
    return list(model.model_fields) if model is not None else []


def _model_at(location: tuple[Any, ...], root: type[BaseModel]) -> type[BaseModel] | None:
    """The pydantic model the field at ``location`` holds, or ``None`` off the models."""
    model: type[BaseModel] | None = root
    for part in location:
        if isinstance(part, int):
            continue
        field = model.model_fields.get(part) if model is not None else None
        model = _model_in(field.annotation) if field is not None else None
        if model is None:
            return None
    return model


def _normalised(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", text.lower()).strip("_")


def _nearest_option(written: str, expected: str) -> str | None:
    """The allowed value ``written`` was reaching for: `si` for `SI`, `CNC milling` for
    `cnc_milling`, `T1` for `T1_analytical`. ``expected`` is pydantic's list of them."""
    options = re.findall(r"'([^']*)'", expected)
    wanted = _normalised(written)
    if not wanted:
        return None
    same = [option for option in options if _normalised(option) == wanted]
    if same:
        return same[0]
    starts = [option for option in options if _normalised(option).startswith(wanted)]
    if len(starts) == 1:
        return starts[0]
    near = difflib.get_close_matches(wanted, [_normalised(o) for o in options], n=1)
    return next((o for o in options if near and _normalised(o) == near[0]), None)


def _remedy(error: Mapping[str, Any], root: type[BaseModel] = DesignSpec) -> str | None:
    """What to do about one pydantic validation failure against ``root``, when its kind says.

    A missing field says to add it, with a line that validates for a required top-level
    Design Spec field. An unknown field says to remove it and names the nearest real one. A
    quantity written as a string, such as `load: 60 kN`, is shown in the form the document
    needs. It is the likeliest mistake a person makes in one, and pydantic answers it with
    "Input should be a valid dictionary or instance of Quantity". A provenanced value written
    bare, such as `min_safety_factor: 1.5`, is shown with its origin, a bare value where a
    one-field mapping or a list belongs is shown wrapped, and a near-miss of an allowed value
    (`si`, `CNC milling`, `T1`) is told the value it nearly named. None of these remedies
    holds a semicolon, because MCP joins a refusal's issues with "; ".
    """
    kind = error.get("type")
    location = tuple(error.get("loc", ()))
    path = ".".join(str(part) for part in location)
    if kind == "missing":
        if root is not DesignSpec:
            return f"add `{path}`, which a {root.__name__} requires"
        example = _REQUIRED_FIELD_EXAMPLES.get(path)
        if example is not None:
            return f"add `{path}` to the document, for example `{example}`"
        return f"add `{path}` to the document"
    if kind == "extra_forbidden" and location:
        owner = ".".join(str(part) for part in location[:-1])
        if owner:
            owner = f"`{owner}`"
        else:
            owner = "a Design Spec" if root is DesignSpec else f"a {root.__name__}"
        if root is DesignSpec and len(location) == 1 and location[0] in _VERSION_SPELLINGS:
            hint = f' (a document states its schema version as `anvilate_spec: "{SCHEMA_VERSION}"`)'
        else:
            near = difflib.get_close_matches(str(location[-1]), _siblings(location, root), n=1)
            hint = f" (did you mean `{near[0]}`?)" if near else ""
        return f"remove `{path}`, which {owner} does not have{hint}"
    cause = (error.get("ctx") or {}).get("error")
    if isinstance(cause, _BareValue) and location:
        return (
            f"write `{path}` as `{{value: {cause.value!r}, origin: user_stated}}` if you chose "
            "it, or give the origin it came from"
        )
    written = error.get("input")
    if kind in ("model_type", "dict_type") and isinstance(written, str) and location:
        from ..units import Quantity

        try:
            quantity = Quantity.parse(written)
        except (ValueError, TypeError):
            quantity = None
        if quantity is not None:
            return (
                f"write `{path}` as `{{magnitude: {quantity.magnitude:g}, unit: "
                f"{quantity.unit}}}` rather than the string {written!r}"
            )
        # `material: ASTM-A36` for `material: {ref: ASTM-A36}`: a value written bare where a
        # mapping of one required field belongs. pydantic's answer named the Python class.
        model = _model_at(location, root)
        required = [n for n, f in model.model_fields.items() if f.is_required()] if model else []
        if len(required) == 1:
            return f"write `{path}` as `{{{required[0]}: {written}}}`"
        return None
    if (
        kind in ("model_type", "dict_type")
        and isinstance(written, int | float)
        and not isinstance(written, bool)
        and location
        and (error.get("ctx") or {}).get("class_name") == "Quantity"
    ):
        return (
            f"write `{path}` as `{{magnitude: {written:g}, unit: ...}}` with the unit the "
            f"{written:g} is in, since a bare number states none"
        )
    if kind == "list_type" and isinstance(written, str | int | float) and location:
        return f"write `{path}` as a list, `[{written}]`"
    if kind in ("enum", "literal_error") and isinstance(written, str) and location:
        option = _nearest_option(written, str((error.get("ctx") or {}).get("expected", "")))
        if option is not None:
            return f"write `{path}` as `{option}` rather than {written!r}"
    return None


class SpecValidationError(ValueError):
    """A spec failed schema validation. Carries the offending field paths.

    Each error is a ``{"loc", "msg"}`` mapping, and carries a ``"remedy"`` when its kind has
    one: a missing field says to add it (with a line that validates, for a required
    top-level field), and an unknown one says to remove it and names the nearest real field.
    """

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors
        lines = [f"  {_refusal_line(e['loc'], e['msg'])}" for e in errors]
        super().__init__("spec failed validation:\n" + "\n".join(lines))

    @property
    def remedies(self) -> tuple[str, ...]:
        """Each distinct remedy the errors carry, in order."""
        return tuple(dict.fromkeys(e["remedy"] for e in self.errors if e.get("remedy")))

    @classmethod
    def _from_pydantic(cls, exc: ValidationError) -> SpecValidationError:
        errors = []
        for e in exc.errors():
            location = tuple(e["loc"])
            remedy = _remedy(e)
            error: dict[str, Any] = {"loc": ".".join(str(p) for p in location), "msg": e["msg"]}
            if remedy is not None:
                # An em dash, not a semicolon: MCP joins a refusal's issues with "; ", and a
                # remedy carrying one would split into a field path that does not exist.
                error["msg"] = f"{e['msg']} — {remedy}"
                error["remedy"] = remedy
            errors.append(error)
        return cls(errors)


class _StrictSpecLoader(yaml.SafeLoader):
    """``yaml.safe_load`` plus a refusal of documents that do not say what they appear to.

    Two things PyYAML reads without complaint, both of which change the design being
    screened and neither of which leaves a trace anywhere in the run.

    **A key declared twice.** PyYAML takes the last one. A spec with ``constraints:`` written
    twice is screened against whichever copy happens to be lower in the file: declare
    ``min_safety_factor: 10.0`` and then, forty lines down after a paste, ``2.0``, and the
    part **passes**, with the 10 in no card, no stderr line and no evidence bundle. That is
    the same defect as an ignored keyword — a declaration the user makes that nothing
    answers — arriving through the document rather than through a field name. Refusing is
    what the YAML specification itself says to do: "it is an error for two equal keys to
    appear in the same mapping node".

    **A number that is not read in base ten.** YAML 1.1, which PyYAML implements, resolves
    ``020`` to **16** and ``1:20`` to **80**. A thickness typed with a leading zero — from a
    padded column, a CAD export, or somebody lining up a table — is silently a different
    thickness, and every check downstream is correct arithmetic on the wrong number. So a
    scalar YAML resolves to a number has to mean what the digits say: the resolved value is
    compared against the base-ten reading of the same text, and a disagreement is refused
    naming both.

    Both are reported the way a tab in the indentation is, and both carry the position. The
    duplicate carries two, because one is not enough to act on: the line the key is repeated
    on is where the reader looks, and the line it was first declared on is what they have to
    compare it against.
    """

    def construct_mapping(self, node, deep: bool = False):
        # Over the keys **as authored**, before `SafeConstructor.construct_mapping` calls
        # `flatten_mapping` and moves a `<<:` merge's keys into this node. After the flatten
        # a key the document overrides locally appears twice by construction, and refusing
        # that would refuse the one YAML feature specs use to share defaults.
        #
        # Compared as raw scalars rather than constructed objects: a key node's tag is the
        # merge tag itself for `<<:`, which has no constructor of its own, so constructing
        # one here is what broke merge keys the first time.
        first: dict[tuple[str, str], Any] = {}
        for key_node, _value_node in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                continue
            key = (key_node.tag, key_node.value)
            if key in first:
                raise yaml.MarkedYAMLError(
                    context=f"the key {key_node.value!r} was already declared at line "
                    f"{first[key].line + 1}, column {first[key].column + 1}",
                    context_mark=None,
                    problem="a key declared twice silently discards the earlier "
                    "declaration, so the document does not say what it appears to",
                    problem_mark=key_node.start_mark,
                )
            first[key] = key_node.start_mark
        return super().construct_mapping(node, deep=deep)


def _construct_int(loader: _StrictSpecLoader, node: yaml.ScalarNode) -> int:
    value = yaml.SafeLoader.construct_yaml_int(loader, node)
    # A plain run of base-ten digits, underscores allowed because YAML and Python group them
    # the same way — `20_0` is 200 to both, so it means what it looks like. Anything else
    # (`020`, `0x20`, `0b101`, `1:20`) is a base or a notation the digits do not announce.
    if re.fullmatch(r"[+-]?[0-9_]+", node.value) and int(node.value) == value:
        return value
    raise _misread(node, value)


def _construct_float(loader: _StrictSpecLoader, node: yaml.ScalarNode) -> float:
    value = yaml.SafeLoader.construct_yaml_float(loader, node)
    # Finiteness first, and on the value rather than on the spelling. `.inf` is read exactly
    # as written, so it agrees with its own base-ten reading and would fall through the
    # comparison below — but so does `1.0e+400`, which is an overflow to infinity that looks
    # like an ordinary number. Checking the spelling caught the first and not the second.
    if not isfinite(value):
        raise _misread(node, value)
    try:
        if float(node.value) == value:
            return value
    except (ValueError, OverflowError):
        pass
    raise _misread(node, value)


def _misread(node: yaml.ScalarNode, value: object) -> yaml.MarkedYAMLError:
    if isinstance(value, float) and not isfinite(value):
        # `.inf` and `.nan` are read exactly as written, so the sentence below would be a
        # lie about them. They are refused for the other reason: nothing downstream of here
        # has a defined answer for a dimension that is not a finite number, and a NaN in
        # particular is dropped rather than propagated by every `max` it reaches.
        problem = "a dimension has to be a finite number"
    else:
        problem = (
            "a number written this way does not mean what its digits say — YAML 1.1 reads "
            "a leading zero as octal and a colon as sexagesimal — so the document does not "
            "say what it appears to"
        )
    return yaml.MarkedYAMLError(
        context=f"{node.value!r} is read as {value!r}",
        context_mark=None,
        problem=problem,
        problem_mark=node.start_mark,
    )


_StrictSpecLoader.add_constructor("tag:yaml.org,2002:int", _construct_int)
_StrictSpecLoader.add_constructor("tag:yaml.org,2002:float", _construct_float)


def parse_spec(data: dict) -> DesignSpec:
    """Parse and validate a raw spec dict into a typed :class:`DesignSpec`.

    Applies schema migrations first, then validates. Raises
    :class:`SpecValidationError` naming each offending path on failure.

    **A document that is not a mapping is one of those failures**, and this guard used to
    live in :func:`load_spec_yaml` one line above the call to here — so the YAML path
    refused a top-level list with a sentence and this one, the entry point a caller reaches
    with `parse_spec(json.load(handle))`, answered it with ``'list' object has no attribute
    'get'``. A JSON file that is a list, a bare string or ``null`` is the ordinary way to
    hand a tool the wrong file, and `anvilate.cli` catches `ValueError`, `TypeError` and
    `KeyError` — not `AttributeError`, which would have reached a user as a traceback if any
    caller had gone this way.
    """
    if not isinstance(data, dict):
        # The whole document is the subject, so there is no field to name: an empty
        # location, which `_refusal_line` prints without the `<root>: ` it used to carry.
        found = {type(None): "empty", list: "a list", str: "a bare string"}.get(
            type(data), f"a {type(data).__name__}"
        )
        remedy = "write a mapping of fields, starting with the required ones: " + ", ".join(
            f"`{name}`" for name in _REQUIRED_FIELD_EXAMPLES
        )
        raise SpecValidationError(
            [
                {
                    "loc": "",
                    "msg": f"spec must be a mapping, and this document is {found} — {remedy}",
                    "remedy": remedy,
                }
            ]
        )
    migrated = migrate_to_current(data)
    try:
        return DesignSpec.model_validate(migrated)
    except ValidationError as exc:
        raise SpecValidationError._from_pydantic(exc) from exc


def load_spec_yaml(text: str) -> DesignSpec:
    """Load and validate a spec from a YAML (or JSON) document.

    A document that is not well-formed YAML is a :class:`SpecValidationError` like any other
    bad document, carrying the line and column PyYAML found the trouble at. A key declared
    twice is one of those documents, and so is a magnitude written `020` — see
    :class:`_StrictSpecLoader` for both, and for why reading them quietly is the worst
    of the three available answers.

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
        data = yaml.load(text, Loader=_StrictSpecLoader)
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
