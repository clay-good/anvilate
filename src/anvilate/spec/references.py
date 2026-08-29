"""Resolution of material and standard-component references.

The Spec IR stores standard components and materials as database *identifiers*
(``AA-6061-T6``, ``NEMA23``, ``ISO4762-M5``) — never free-form dimensions. The
real dimension and property tables are the standards-data capability; this
module defines the resolver interface the spec layer validates against and
ships a small static resolver seeded with the golden-path identifiers.

**The real resolver is `anvilate.standards.StandardsResolver`, and callers wire
it — this package deliberately imports nothing.** The static seed is not a
placeholder waiting on that database: the database landed, and the seed stays
because the spec layer has no dependencies to take, which is what lets the
resolver be injected at all. `anvilate.screening.screen_spec` builds the
standards-backed one by default; the note here used to say "replace this once
that database exists", and a reader who believed it would conclude that
resolution was still pending when what was pending was the wiring.
"""

from __future__ import annotations

from typing import Protocol

__all__ = [
    "ReferenceResolver",
    "StaticReferenceResolver",
    "UnknownReferenceError",
    "default_resolver",
]


class UnknownReferenceError(ValueError):
    """A referenced material or component ID is not in the databases."""

    def __init__(self, ref: str, kind: str, suggestions: list[str]) -> None:
        self.ref = ref
        self.kind = kind
        self.suggestions = suggestions
        hint = f"; did you mean {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"unknown {kind} reference {ref!r}{hint}")


class ReferenceResolver(Protocol):
    """Knows which material and component identifiers exist."""

    def has_material(self, ref: str) -> bool: ...

    def has_component(self, ref: str) -> bool: ...

    def known_materials(self) -> list[str]: ...

    def known_components(self) -> list[str]: ...


class StaticReferenceResolver:
    """A resolver backed by fixed identifier sets.

    Seeded with the identifiers the golden-path bracket references, so the spec
    layer's own tests need no database. Production callers pass
    :func:`anvilate.standards.default_standards_resolver` instead — the spec layer
    only depends on the :class:`ReferenceResolver` protocol, which is why it can.
    """

    def __init__(self, materials: set[str], components: set[str]) -> None:
        self._materials = materials
        self._components = components

    def has_material(self, ref: str) -> bool:
        return ref in self._materials

    def has_component(self, ref: str) -> bool:
        return ref in self._components

    def known_materials(self) -> list[str]:
        return sorted(self._materials)

    def known_components(self) -> list[str]:
        return sorted(self._components)


def default_resolver() -> StaticReferenceResolver:
    """The seed resolver covering the launch/golden-path identifiers.

    Five materials and five components. This is the spec layer's own fixture, not the
    library's answer to "which identifiers exist" — that is
    :func:`anvilate.standards.default_standards_resolver`, which reads the bundled tables
    and is what :func:`anvilate.screening.screen_spec` uses.
    """
    return StaticReferenceResolver(
        materials={"AA-6061-T6", "AA-7075-T6", "ASTM-A36", "ASTM-A992", "SS-304"},
        components={"NEMA17", "NEMA23", "EXT-4040", "EXT-2020", "ISO4762-M5"},
    )
