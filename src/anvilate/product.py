"""Product structure: a product is a tree of definitions placed as instances.

A combination places a handful of catalog parts. A product nests: a drive module is
defined once and placed four times, a motor nobody here draws is a placeholder with an
envelope and a mass, and every definition carries the identity the rest of the company
uses — a part number, a revision, make or buy. This module reads a product document into
that tree, and answers what a parts list and a reviewer ask of it, before any geometry is
built:

- **Definitions and instances.** An item is defined once (a catalog part's Design Spec, a
  sub-product, or a placeholder) and placed by any number of instances, singly or as a
  linear or circular pattern. A change to a definition reaches every instance.
- **Identity.** Every definition has a part number, a revision, a description and a
  source (make, buy, reference). One with no part number gets a deterministic provisional
  number derived from its content, marked provisional wherever it is shown. A part number
  shared by two definitions with different content is refused, naming both paths.
- **Paths.** Every instance is addressed by its names from the root, ``stage/drive[2]/motor``,
  which a sibling added or reordered does not change.
- **Refusals before any geometry.** A product that contains itself, through any depth of
  nesting; a mirrored instance (an opposite-hand part is a different part to make and to
  buy, so it needs its own definition and number); a sub-product the library does not
  hold; and an instance of a definition the document does not have.

Placement — the mates that put each instance on one already placed — and the cards and
builds per node are later layers of the same document.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from ._models import FrozenMap, Named, Provenance, StatableModel, _refusal_line
from .refusal import RefusalError, Remedy
from .units import Quantity

__all__ = [
    "PRODUCT_VERSION",
    "ItemSource",
    "ItemIdentity",
    "Placeholder",
    "Definition",
    "LinearPattern",
    "CircularPattern",
    "Instance",
    "Product",
    "ProductNode",
    "PartsListLine",
    "ProductError",
    "parse_product",
    "product_tree",
    "parts_list",
]

PRODUCT_VERSION = "1.0.0"
_DOCUMENT_SOURCE = "the product document"


class ProductError(RefusalError, ValueError):
    """A product document that cannot be read into a tree without correction."""


def _refuse(message: str, *, subject: str, action: str = "correct") -> ProductError:
    return ProductError(
        message, remedies=(Remedy(action=action, subject=subject, source=_DOCUMENT_SOURCE),)
    )


class ItemSource(StrEnum):
    """Whether a definition is made, bought, or carried for reference only."""

    MAKE = "make"
    BUY = "buy"
    REFERENCE = "reference"


class ItemIdentity(StatableModel):
    """The identity a PDM, PLM or ERP carries: part number, revision, description, source.

    ``part_number`` may be left out; the tree then gives the definition a provisional
    number derived from its content, marked provisional wherever it is shown.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    part_number: Named | None = None
    revision: Named | None = None
    description: Named
    source: ItemSource


class Placeholder(StatableModel):
    """An item not yet detailed: an envelope, a mass, and why it is still a placeholder."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope: tuple[Quantity, Quantity, Quantity]
    mass: Quantity
    reason: Provenance

    @model_validator(mode="after")
    def _a_body(self) -> Placeholder:
        for index, size in enumerate(self.envelope):
            if not size.has_dimension("[length]") or not size.magnitude > 0:
                raise _refuse(f"placeholder envelope[{index}] is {size}; an envelope is three "
                              "positive lengths", subject="placeholder.envelope")  # fmt: skip
        if not self.mass.has_dimension("[mass]") or not self.mass.magnitude > 0:
            raise _refuse(f"placeholder mass is {self.mass}; a mass is positive",
                          subject="placeholder.mass")  # fmt: skip
        return self


class Definition(StatableModel):
    """One item defined once: a catalog part's spec, a sub-product by name, or a placeholder."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    identity: ItemIdentity
    spec: FrozenMap[str, Any] | None = None
    product: Named | None = None
    placeholder: Placeholder | None = None

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> Definition:
        kinds = [k for k in ("spec", "product", "placeholder") if getattr(self, k) is not None]
        if len(kinds) != 1:
            raise _refuse(
                f"definition '{self.id}' states {kinds or 'none'} of spec, product and "
                "placeholder; a definition is exactly one of them",
                subject="definitions[].spec",
            )
        return self

    @property
    def kind(self) -> str:
        """``part``, ``product`` or ``placeholder``."""
        if self.spec is not None:
            return "part"
        return "product" if self.product is not None else "placeholder"


class LinearPattern(StatableModel):
    """``count`` instances ``spacing`` apart along one of the parent's axes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["linear"] = "linear"
    count: int = Field(ge=2, le=256)
    spacing: Quantity
    direction: Literal["x", "y", "z"]


class CircularPattern(StatableModel):
    """``count`` instances spread ``angle_deg`` apart about one of the parent's axes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["circular"] = "circular"
    count: int = Field(ge=2, le=256)
    angle_deg: float
    axis: Literal["x", "y", "z"]


class Instance(StatableModel):
    """A definition placed in its parent, once or as a pattern, under a name.

    ``mirrored`` is refused: an opposite-hand part is a different part to make and to buy,
    so it is its own definition with its own number, never a negatively scaled instance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    item: Named
    pattern: LinearPattern | CircularPattern | None = None
    mirrored: bool = False

    @model_validator(mode="after")
    def _a_placement(self) -> Instance:
        if any(c in self.name for c in "/[]"):
            raise _refuse(f"instance name '{self.name}' contains '/', '[' or ']', which a path "
                          "uses to address it", subject="instances[].name")  # fmt: skip
        if self.mirrored:
            raise _refuse(
                f"instance '{self.name}' mirrors '{self.item}'; an opposite-hand part is a "
                "different part to make and to buy, so give the mirror its own definition "
                "and part number",
                subject="instances[].mirrored",
            )
        if isinstance(self.pattern, LinearPattern) and not self.pattern.spacing.has_dimension(
            "[length]"
        ):
            raise _refuse(f"pattern spacing {self.pattern.spacing} is not a length",
                          subject="instances[].pattern.spacing")  # fmt: skip
        return self


class Product(StatableModel):
    """A product document: its definitions, the instances that place them, and the ground."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    anvilate_product: str = PRODUCT_VERSION
    name: Named
    description: Provenance | None = None
    identity: ItemIdentity | None = None
    definitions: tuple[Definition, ...] = Field(min_length=1, max_length=256)
    instances: tuple[Instance, ...] = Field(min_length=1, max_length=256)
    ground: Named

    @model_validator(mode="after")
    def _refers_to_its_own(self) -> Product:
        ids = [d.id for d in self.definitions]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise _refuse(f"definitions {repeated} are declared twice", subject="definitions[].id")
        names = [i.name for i in self.instances]
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated:
            raise _refuse(f"instances {repeated} are named twice; a path names each once",
                          subject="instances[].name")  # fmt: skip
        for instance in self.instances:
            if instance.item not in ids:
                raise _refuse(f"instance '{instance.name}' places '{instance.item}', which is "
                              f"not a definition here ({', '.join(ids)})",
                              subject="instances[].item")  # fmt: skip
        if self.ground not in names:
            raise _refuse(f"the ground '{self.ground}' is not an instance ({', '.join(names)})",
                          subject="ground")  # fmt: skip
        return self


def parse_product(document: Mapping[str, Any]) -> Product:
    """A product document as its typed model, refusing what cannot be read."""
    from pydantic import ValidationError

    if not isinstance(document, Mapping):
        raise _refuse("a product document is a mapping", subject="document")
    try:
        return Product.model_validate(dict(document))
    except ValidationError as failure:
        first = failure.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "the document"
        raise _refuse(f"the product document is not valid at {where}: "
                      f"{_refusal_line('', first['msg'])}", subject=where) from failure  # fmt: skip


# --- the tree ------------------------------------------------------------------------------


class ProductNode(StatableModel):
    """One placed occurrence: its path, its definition, its resolved identity, its children.

    ``part_number`` is the declared one or, with ``provisional`` set, the number derived
    from the definition's content. ``kind`` is part, product or placeholder.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    definition: Named
    kind: Literal["part", "product", "placeholder"]
    part_number: Named
    provisional: bool
    revision: str | None
    description: Named
    source: ItemSource
    children: tuple[ProductNode, ...] = ()

    def walk(self) -> tuple[ProductNode, ...]:
        """This node and every node below it, depth first."""
        out: list[ProductNode] = [self]
        for child in self.children:
            out.extend(child.walk())
        return tuple(out)

    def __str__(self) -> str:
        mark = " (provisional)" if self.provisional else ""
        return f"{self.path}: {self.part_number}{mark} {self.description} [{self.kind}]"


def _content(definition: Definition, library: Mapping[str, Product]) -> str:
    if definition.spec is not None:
        payload: Any = {"spec": dict(definition.spec)}
    elif definition.placeholder is not None:
        payload = {"placeholder": definition.placeholder.model_dump(mode="json")}
    else:
        sub = library.get(definition.product or "")
        payload = {
            "product": sub.model_dump(mode="json") if sub is not None else definition.product
        }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def product_tree(product: Product, *, library: Mapping[str, Product] | None = None) -> ProductNode:
    """The product as a tree of placed occurrences, each with a stable path.

    ``library`` holds the sub-products the document places by name. A product that
    contains itself at any depth, a sub-product the library does not hold, and one part
    number on two definitions with different content are refused, naming the paths.
    """
    if not isinstance(product, Product):
        raise _refuse("product must be a Product from parse_product", subject="product")
    shelf = dict(library or {})
    for name, sub in shelf.items():
        if not isinstance(sub, Product):
            raise _refuse(f"library entry '{name}' is not a Product", subject="library")
    numbers: dict[str, tuple[str, str]] = {}

    def identity_of(definition: Definition, path: str) -> tuple[str, bool]:
        content = _content(definition, shelf)
        declared = definition.identity.part_number
        number = declared or f"PROV-{content[:8].upper()}"
        seen = numbers.get(number)
        if seen is not None and seen[0] != content:
            raise _refuse(
                f"part number {number} is on two different items, at '{seen[1]}' and '{path}'; "
                "a part number names one item",
                subject="definitions[].identity.part_number",
            )
        numbers.setdefault(number, (content, path))
        return number, declared is None

    def expand(current: Product, prefix: str, chain: tuple[str, ...]) -> tuple[ProductNode, ...]:
        definitions = {d.id: d for d in current.definitions}
        nodes = []
        for instance in current.instances:
            definition = definitions[instance.item]
            count = instance.pattern.count if instance.pattern is not None else 1
            for k in range(count):
                label = instance.name if count == 1 else f"{instance.name}[{k + 1}]"
                path = f"{prefix}/{label}"
                children: tuple[ProductNode, ...] = ()
                if definition.kind == "product":
                    target = definition.product or ""
                    if target in chain:
                        raise _refuse(
                            f"product '{target}' contains itself: {' → '.join((*chain, target))}",
                            subject="definitions[].product",
                        )
                    sub = shelf.get(target)
                    if sub is None:
                        raise _refuse(
                            f"'{path}' places the product '{target}', which the library does "
                            f"not hold ({', '.join(sorted(shelf)) or 'it is empty'})",
                            subject="library",
                            action="add",
                        )
                    children = expand(sub, path, (*chain, target))
                number, provisional = identity_of(definition, path)
                nodes.append(
                    ProductNode(
                        path=path, definition=definition.id, kind=definition.kind,  # type: ignore[arg-type]
                        part_number=number, provisional=provisional,
                        revision=definition.identity.revision,
                        description=definition.identity.description,
                        source=definition.identity.source, children=children,
                    )
                )  # fmt: skip
        return tuple(nodes)

    top = product.identity
    content = hashlib.sha256(
        json.dumps(product.model_dump(mode="json"), sort_keys=True, default=str).encode()
    ).hexdigest()
    return ProductNode(
        path=product.name,
        definition=product.name,
        kind="product",
        part_number=(top.part_number if top and top.part_number else f"PROV-{content[:8].upper()}"),
        provisional=not (top and top.part_number),
        revision=top.revision if top else None,
        description=top.description if top else (product.description or product.name),
        source=top.source if top else ItemSource.MAKE,
        children=expand(product, product.name, (product.name,)),
    )


class PartsListLine(StatableModel):
    """One line of the parts list: an item, how many the product holds, and its identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    part_number: Named
    provisional: bool
    revision: str | None
    description: Named
    source: ItemSource
    kind: Literal["part", "product", "placeholder"]
    quantity: int

    def __str__(self) -> str:
        mark = " (provisional)" if self.provisional else ""
        rev = f" rev {self.revision}" if self.revision else ""
        return (
            f"{self.quantity} × {self.part_number}{mark}{rev} {self.description} "
            f"[{self.source.value}, {self.kind}]"
        )


def parts_list(tree: ProductNode) -> tuple[PartsListLine, ...]:
    """Every item under the root, by part number, with the total quantity the product holds."""
    if not isinstance(tree, ProductNode):
        raise _refuse("tree must be a ProductNode from product_tree", subject="tree")
    counts: dict[str, tuple[ProductNode, int]] = {}
    for node in tree.walk()[1:]:
        first, n = counts.get(node.part_number, (node, 0))
        counts[node.part_number] = (first, n + 1)
    return tuple(
        PartsListLine(part_number=number, provisional=node.provisional, revision=node.revision,
                      description=node.description, source=node.source, kind=node.kind,
                      quantity=n)
        for number, (node, n) in sorted(counts.items())
    )  # fmt: skip
