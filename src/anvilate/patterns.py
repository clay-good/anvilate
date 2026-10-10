"""The registry of drawable patterns: one table that building, listing and refusing all read.

A pattern was a constant, a build function, a branch in ``build_spec``, a member of a
``Literal`` and a word in a refusal's "supported:" list. When ``timber_beam/1`` shipped, two
of those five were missed and every timber beam failed over MCP. Here a pattern is one
:class:`Pattern` entry, and everything else is derived from the table: which element types
draw, what the catalog says about each, and what a refusal names as supported.

Nothing here builds geometry. An entry points at the element's typed model and at the
function that builds it, and :func:`build` calls that function.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from functools import cache
from types import MappingProxyType
from typing import Any

from pydantic import ConfigDict, Field

from ._models import FrozenMap, ItemCollection, Named, Provenance, StatableModel
from .geometry import GeometryError

__all__ = [
    "PartCatalog",
    "PartDescription",
    "PartParameter",
    "Pattern",
    "build",
    "describe_part",
    "describe_parts",
    "drawable_catalog",
    "example_spec",
    "pattern_for",
    "patterns",
    "register",
]

OUTPUTS = ("views", "step", "3mf", "dxf", "flat_pattern")


class PartParameter(StatableModel):
    """One field of an element: its name, whether it is required, and what it takes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    required: bool
    takes: Named


class PartDescription(StatableModel):
    """One element a spec can declare, as the part catalog describes it.

    A listing carries the first four fields. A full description adds whether the part is
    an envelope, the outputs it supports, its parameters, the fields of every model a
    parameter names (``Hole`` for ``list of Hole``), and an example spec to copy and edit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    element_type: Named
    summary: Provenance
    drawable: bool
    screened: bool
    envelope: bool = Field(default=False, exclude_if=lambda value: not value)
    outputs: tuple[Named, ...] = Field(default=(), exclude_if=lambda value: not value)
    parameters: tuple[PartParameter, ...] = Field(default=(), exclude_if=lambda value: not value)
    types: FrozenMap[str, tuple[PartParameter, ...]] = Field(
        default_factory=lambda: MappingProxyType({}), exclude_if=lambda value: not value
    )
    example: FrozenMap[str, Any] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class PartCatalog(ItemCollection, StatableModel):
    """What ``describe_part`` returns: every element in a line, or one in full."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parts: tuple[PartDescription, ...] = Field(min_length=1)


def _refuse(message: str, *, subject: str) -> GeometryError:
    return GeometryError(
        message,
        action="correct",
        subject=subject,
        source="the pattern registry: one pattern per element type, named '<element_type>/<n>'",
    )


@dataclass(frozen=True)
class Pattern:
    """One drawable archetype: its name, the element it draws, and how it is built.

    ``build`` takes the validated element, the part's name and the element parameters as
    the document wrote them, and returns the built geometry. The parameters are there for
    what validation resolves away: a member's ``section: IPE 200`` reaches the model as
    section properties, and only the document still says which profile it was.
    ``example`` is its worked spec, a path under the repository's ``examples``, and
    ``example_params`` are merged into the element's shipped example, for a pattern that
    draws from a field the screen does not need.
    ``outputs`` are what the pattern supports beyond the solid itself.
    ``envelope`` marks a catalog component drawn from its tabulated size: where it goes, not
    how it is made. ``screened`` is false for a part that is drawn and not checked.
    """

    name: str
    element_type: str
    model: type
    build: Callable[[Any, str, Mapping[str, Any]], Any]
    summary: str
    example: str
    outputs: tuple[str, ...] = ("views", "step", "3mf")
    envelope: bool = False
    screened: bool = True
    example_params: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if self.name != f"{self.element_type}/{self.name.rpartition('/')[2]}":
            raise _refuse(
                f"pattern {self.name!r} must be named '{self.element_type}/<n>'", subject="name"
            )
        unknown = sorted(set(self.outputs) - set(OUTPUTS))
        if unknown:
            raise _refuse(
                f"pattern {self.name!r} names outputs nothing produces: {unknown}",
                subject="outputs",
            )


_REGISTRY: dict[str, Pattern] = {}
_LOADED = False


def register(pattern: Pattern) -> Pattern:
    """Add one pattern, refusing a second pattern for the same element type."""
    if pattern.element_type in _REGISTRY:
        raise _refuse(
            f"element type {pattern.element_type!r} already has a pattern",
            subject="element_type",
        )
    _REGISTRY[pattern.element_type] = pattern
    return pattern


def patterns() -> Mapping[str, Pattern]:
    """Every registered pattern, by the element type it draws."""
    global _LOADED
    if not _LOADED:
        _LOADED = True
        # Imported for their registrations. Here rather than at module import, because the
        # builders import this module's `register`.
        from . import _patterns_core, _patterns_parts, _patterns_screened  # noqa: F401

    return MappingProxyType(_REGISTRY)


def pattern_for(element_type: str | None) -> Pattern | None:
    """The pattern that draws ``element_type``, or ``None`` when nothing does."""
    return patterns().get(element_type) if element_type is not None else None


def build(
    element_type: str, element: Any, name: str, params: Mapping[str, Any] | None = None
) -> Any:
    """Build the registered pattern for ``element_type`` from its validated ``element``."""
    return patterns()[element_type].build(element, name, params or {})


def _one(annotation: Any) -> str:
    """What one annotation takes, in a word a spec author can act on."""
    from typing import Literal, get_args, get_origin

    from .units import Quantity

    if annotation is Quantity:
        return "quantity"
    if annotation is bool:
        return "true or false"
    if annotation is int:
        return "whole number"
    if annotation is float:
        return "number"
    if annotation is str:
        return "text"
    if get_origin(annotation) is Literal:
        return " | ".join(str(choice) for choice in get_args(annotation))
    if get_origin(annotation) is tuple:
        return f"list of {_one(get_args(annotation)[0])}"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return " | ".join(str(member.value) for member in annotation)
    if isinstance(annotation, type):
        return annotation.__name__
    members = [_one(arg) for arg in get_args(annotation) if arg is not type(None)]
    return " | ".join(dict.fromkeys(members)) or "value"


def _takes(info: Any) -> str:
    return _one(info.annotation)


def _parameters(model: type) -> list[dict[str, Any]]:
    return [
        {"name": name, "required": info.is_required(), "takes": _takes(info)}
        for name, info in getattr(model, "model_fields", {}).items()
    ]


def _nested(model: type, found: dict[str, type] | None = None) -> dict[str, type]:
    """Every model a field of ``model`` holds, by name: the types a parameter list names."""
    from typing import get_args

    from pydantic import BaseModel

    from .units import Quantity

    found = {} if found is None else found

    def walk(annotation: Any) -> None:
        if (
            isinstance(annotation, type)
            and issubclass(annotation, BaseModel)
            and annotation is not Quantity
        ):
            if annotation.__name__ not in found:
                found[annotation.__name__] = annotation
                _nested(annotation, found)
            return
        for inner in get_args(annotation):
            walk(inner)

    for info in getattr(model, "model_fields", {}).values():
        walk(info.annotation)
    return found


def drawable_catalog() -> tuple[dict[str, Any], ...]:
    """What can be drawn, generated from the registry: one entry per pattern.

    Each entry names the element type, the pattern, what it is, its worked example, its
    parameters with whether each is required and what it takes, the outputs it supports,
    whether it is an envelope and whether a screen checks it. An agent reads this to choose
    a pattern without trial and error.
    """
    entries = []
    for element_type in sorted(patterns()):
        pattern = patterns()[element_type]
        entries.append(
            {
                "element_type": element_type,
                "pattern": pattern.name,
                "summary": pattern.summary,
                "example": pattern.example,
                "parameters": _parameters(pattern.model),
                "outputs": list(pattern.outputs),
                "envelope": pattern.envelope,
                "screened": pattern.screened,
            }
        )
    return tuple(entries)


@cache
def _examples_document() -> bytes:
    from importlib import resources

    return resources.files("anvilate.packs").joinpath("element_examples.json").read_bytes()


def _examples() -> Mapping[str, Any]:
    """One valid parameter set per element type, shipped with the package.

    Parsed on each call from the cached bytes, so a caller holds its own copy and cannot
    edit the next caller's example.
    """
    from ._models import parse_json

    return parse_json(_examples_document())


def example_spec(element_type: str) -> dict[str, Any]:
    """A complete Design Spec document for ``element_type``, to copy and edit.

    The element parameters are the shipped example for that element. The material, the
    process and the name are placeholders a caller replaces with what the user stated.
    """
    import copy

    # An optional field the example leaves unset is left out, not written as null.
    params = {
        key: value
        for key, value in copy.deepcopy(dict(_examples()[element_type])).items()
        if value is not None
    }
    pattern = pattern_for(element_type)
    if pattern is not None:
        params |= copy.deepcopy(dict(pattern.example_params))
    material = next(
        (params[key] for key in ("material", "plate_material") if isinstance(params.get(key), str)),
        "ASTM-A36",
    )
    return {
        "anvilate_spec": "1.3.0",
        "name": str(params.get("name") or element_type.replace("_", "-")),
        "description": f"An example {element_type.replace('_', ' ')}; replace its values.",
        "units": {"value": "SI", "origin": "user_stated"},
        "material": {"ref": material},
        "manufacturing": {"process": "cnc_milling"},
        "element_type": element_type,
        "element_params": params,
        "acceptance": {"tiers": ["T1_analytical"]},
    }


def _summary(element_type: str, model: type) -> str:
    pattern = pattern_for(element_type)
    if pattern is not None:
        return pattern.summary
    lines = (model.__doc__ or "").strip().splitlines()
    return lines[0].strip() if lines else element_type.replace("_", " ")


def describe_parts() -> PartCatalog:
    """Every element a spec can declare: what it is, whether it draws and whether it is checked."""
    from .screening import element_registry

    listed = []
    for element_type, (model, _screen) in sorted(element_registry().items()):
        pattern = pattern_for(element_type)
        listed.append(
            PartDescription(
                element_type=element_type,
                summary=_summary(element_type, model),
                drawable=pattern is not None,
                screened=pattern is None or pattern.screened,
            )
        )
    return PartCatalog(parts=tuple(listed))


def describe_part(element_type: str) -> PartCatalog:
    """One element in full: its fields, the types they name, and an example spec to edit.

    An unknown name is refused with the closest names the registry carries, so a caller
    one guess away is told the spelling.
    """
    import difflib

    from .screening import element_registry

    registry = element_registry()
    if element_type not in registry:
        near = difflib.get_close_matches(element_type, sorted(registry), n=5, cutoff=0.4)
        raise GeometryError(
            f"no element is named {element_type!r}"
            + (f"; closest: {', '.join(near)}" if near else "")
            + ". Ask with no element type to list every one",
            action="select",
            subject="element_type",
            source="the element registry: every part a spec can declare",
        )
    model, _screen = registry[element_type]
    pattern = pattern_for(element_type)
    return PartCatalog(
        parts=(
            PartDescription(
                element_type=element_type,
                summary=_summary(element_type, model),
                drawable=pattern is not None,
                screened=pattern is None or pattern.screened,
                envelope=bool(pattern and pattern.envelope),
                outputs=pattern.outputs if pattern else (),
                parameters=_parameters(model),
                types={
                    name: _parameters(nested) for name, nested in sorted(_nested(model).items())
                },
                example=example_spec(element_type) if element_type in _examples() else None,
            ),
        )
    )
