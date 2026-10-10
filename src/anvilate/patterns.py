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
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from .geometry import GeometryError

__all__ = ["Pattern", "build", "drawable_catalog", "pattern_for", "patterns", "register"]

OUTPUTS = ("views", "step", "3mf", "dxf", "flat_pattern")


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

    ``build`` takes the validated element and the part's name and returns the built
    geometry. ``example`` is its worked spec, a path under the repository's ``examples``.
    ``outputs`` are what the pattern supports beyond the solid itself.
    ``envelope`` marks a catalog component drawn from its tabulated size: where it goes, not
    how it is made. ``screened`` is false for a part that is drawn and not checked.
    """

    name: str
    element_type: str
    model: type
    build: Callable[[Any, str], Any]
    summary: str
    example: str
    outputs: tuple[str, ...] = ("views", "step", "3mf")
    envelope: bool = False
    screened: bool = True

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
        from . import _patterns_core, _patterns_parts  # noqa: F401

    return MappingProxyType(_REGISTRY)


def pattern_for(element_type: str | None) -> Pattern | None:
    """The pattern that draws ``element_type``, or ``None`` when nothing does."""
    return patterns().get(element_type) if element_type is not None else None


def build(element_type: str, element: Any, name: str) -> Any:
    """Build the registered pattern for ``element_type`` from its validated ``element``."""
    return patterns()[element_type].build(element, name)


def _takes(info: Any) -> str:
    """What one parameter takes, in a word a spec author can act on."""
    from typing import Literal, get_args, get_origin

    from .units import Quantity

    def one(annotation: Any) -> str:
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
            return f"list of {one(get_args(annotation)[0])}"
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            return " | ".join(str(member.value) for member in annotation)
        if isinstance(annotation, type):
            return annotation.__name__
        members = [one(arg) for arg in get_args(annotation) if arg is not type(None)]
        return " | ".join(dict.fromkeys(members)) or "value"

    return one(info.annotation)


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
        fields = getattr(pattern.model, "model_fields", {})
        entries.append(
            {
                "element_type": element_type,
                "pattern": pattern.name,
                "summary": pattern.summary,
                "example": pattern.example,
                "parameters": [
                    {"name": field, "required": info.is_required(), "takes": _takes(info)}
                    for field, info in fields.items()
                ],
                "outputs": list(pattern.outputs),
                "envelope": pattern.envelope,
                "screened": pattern.screened,
            }
        )
    return tuple(entries)
