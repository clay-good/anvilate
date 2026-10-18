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

**Placement** (:func:`place_product`) puts the ground instance at the origin and every other
instance where its mates put it, using the combination's mate vocabulary with instance
names as the parts: a product never states a coordinate. A catalog part is built from its
spec, a placeholder is its envelope box, and a sub-product is its own placed assembly,
moved as one body. Members of a pattern follow its first: shifted by the spacing along
the parent's axis, or turned by the angle about it. The placed product reports every leaf
body at its path, the interference between them, and the mass, naming each placeholder
the mass rests on.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from ._models import FrozenMap, Named, Provenance, StatableModel, _refusal_line
from .combination import Mate
from .refusal import RefusalError, Remedy
from .scorecard import ScorecardEntry
from .units import Quantity

__all__ = [
    "PRODUCT_VERSION",
    "ItemSource",
    "ItemIdentity",
    "Placeholder",
    "PlaceholderHole",
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
    "PlacedBody",
    "PlacedProduct",
    "place_product",
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


class PlaceholderHole(StatableModel):
    """A hole a placeholder offers to a mate: its tag, where it is, its size, the face it is in.

    ``x``, ``y`` and ``z`` are the hole's entry point in the placeholder's frame, whose origin
    is the envelope's centre; ``face`` is the envelope face it opens on, which sets its axis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag: Named
    x: Quantity
    y: Quantity
    z: Quantity
    diameter: Quantity
    face: Literal["top", "bottom", "left", "right", "front", "back"]


class Placeholder(StatableModel):
    """An item not yet detailed: an envelope, a mass, and why it is still a placeholder.

    ``holes`` are the interfaces it offers, so a bought motor's bolt pattern can take a
    hole-pattern mate before the motor is chosen. ``center_of_mass`` is measured from the
    envelope's centre; left out, the centre is used and the placed product says so.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope: tuple[Quantity, Quantity, Quantity]
    mass: Quantity
    reason: Provenance
    holes: tuple[PlaceholderHole, ...] = Field(default=(), max_length=64)
    center_of_mass: tuple[Quantity, Quantity, Quantity] | None = None

    @model_validator(mode="after")
    def _a_body(self) -> Placeholder:
        for index, size in enumerate(self.envelope):
            if not size.has_dimension("[length]") or not size.magnitude > 0:
                raise _refuse(f"placeholder envelope[{index}] is {size}; an envelope is three "
                              "positive lengths", subject="placeholder.envelope")  # fmt: skip
        if not self.mass.has_dimension("[mass]") or not self.mass.magnitude > 0:
            raise _refuse(f"placeholder mass is {self.mass}; a mass is positive",
                          subject="placeholder.mass")  # fmt: skip
        half = [size.to("mm").magnitude / 2 for size in self.envelope]
        for hole in self.holes:
            point = [q.to("mm").magnitude for q in (hole.x, hole.y, hole.z)]
            if any(abs(p) > h + 1e-9 for p, h in zip(point, half, strict=True)):
                raise _refuse(f"placeholder hole '{hole.tag}' at {point} mm is outside its "
                              "envelope", subject="placeholder.holes")  # fmt: skip
        if self.center_of_mass is not None:
            point = [q.to("mm").magnitude for q in self.center_of_mass]
            if any(abs(p) > h + 1e-9 for p, h in zip(point, half, strict=True)):
                raise _refuse(f"placeholder centre of mass {point} mm is outside its envelope",
                              subject="placeholder.center_of_mass")  # fmt: skip
        tags = [hole.tag for hole in self.holes]
        if len(set(tags)) != len(tags):
            raise _refuse(f"placeholder holes {tags} repeat a tag", subject="placeholder.holes")
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
    mates: tuple[Mate, ...] = Field(default=(), max_length=512)

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


# --- placement -----------------------------------------------------------------------------


class PlacedBody(StatableModel):
    """One leaf of a placed product: its path, mass if known, placeholder or not, and its box."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    placeholder: bool
    mass_kg: float | None
    box_min_mm: tuple[float, float, float]
    box_max_mm: tuple[float, float, float]
    center_of_mass_mm: tuple[float, float, float]


class PlacedProduct(StatableModel):
    """A product placed through its mates: its leaves, interference and mass roll-up.

    ``interference`` is the combination's pairwise intersection over every leaf body, and
    says which placeholders it rests on. ``mass_kg`` is the sum of the leaves' masses and
    ``center_of_mass_mm`` their mass-weighted centre; ``mass_rests_on`` names each
    placeholder in them, ``center_assumed`` each placeholder whose centre of mass is its
    envelope's centre, and ``mass_unknown`` each leaf whose material gives no density, so
    the roll-up never reads as more complete than it is.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    bodies: tuple[PlacedBody, ...]
    interference: ScorecardEntry
    mass_kg: float
    mass_rests_on: tuple[str, ...]
    mass_unknown: tuple[str, ...]
    center_of_mass_mm: tuple[float, float, float] | None
    center_assumed: tuple[str, ...] = ()

    def __str__(self) -> str:
        rests = f"; rests on placeholders {list(self.mass_rests_on)}" if self.mass_rests_on else ""
        unknown = f"; no mass for {list(self.mass_unknown)}" if self.mass_unknown else ""
        centre = ""
        if self.center_of_mass_mm is not None:
            x, y, z = self.center_of_mass_mm
            assumed = (f", assuming envelope centres for {list(self.center_assumed)}"
                       if self.center_assumed else "")  # fmt: skip
            centre = f"; centre of mass ({x:.4g}, {y:.4g}, {z:.4g}) mm{assumed}"
        return (
            f"{self.name}: {len(self.bodies)} bodies, {self.mass_kg:.4g} kg{rests}{unknown}"
            f"{centre}; "
            f"interference {self.interference.status.value}"
        )


class _Leaf:
    def __init__(
        self, path: str, shape: Any, placeholder: bool, mass: float | None, com: Any, assumed: bool
    ) -> None:
        self.path, self.shape, self.placeholder, self.mass = path, shape, placeholder, mass
        # The centre of mass as a vertex, moved with the shape; ``assumed`` when it is a
        # placeholder's envelope centre rather than a declared centre of mass.
        self.com, self.assumed = com, assumed


class _Assembly:
    """A placed (sub-)product: a shape and features for ``_place``, and its leaves."""

    def __init__(self, shape: Any, leaves: list[_Leaf]) -> None:
        self.shape, self.leaves, self.features = shape, leaves, ()


def place_product(
    product: Product, *, library: Mapping[str, Product] | None = None
) -> PlacedProduct:
    """Place every instance through its mates, then check interference and roll up mass.

    The ground stays at the origin. Every other instance — a pattern's first member, named
    by the instance's name — must be placed by at least one mate onto an instance listed
    before it; the rest of a pattern follows its first member. A mate that leaves an
    instance free or contradicts another is refused by the combination's own rules.
    """
    from .combination import _IDENTITY, PlacedPart, _interference, _place

    shelf = dict(library or {})
    product_tree(product, library=shelf)  # the identity and containment refusals first

    def assemble(current: Product, prefix: str) -> _Assembly:
        from build123d import Box, CenterOf, Compound, Vertex

        from .combination import _mass
        from .features import Feature
        from .geometry import BuiltGeometry, GeometryError, build_spec
        from .spec import SpecValidationError, parse_spec

        definitions = {d.id: d for d in current.definitions}
        order = [i.name for i in current.instances]
        for mate in current.mates:
            for end in (mate.place, mate.on):
                if end.part not in order:
                    raise _refuse(f"mate '{mate.id}' names '{end.part}', which is not an instance "
                                  f"of '{current.name}' ({', '.join(order)})",
                                  subject="mates[].place.part")  # fmt: skip
            if mate.place.part == current.ground:
                raise _refuse(f"mate '{mate.id}' places the ground '{current.ground}', which stays "
                              "where it is", subject="mates[].place.part")  # fmt: skip
        placed: dict[str, PlacedPart] = {}
        leaves: list[_Leaf] = []
        ground_first = sorted(current.instances, key=lambda i: i.name != current.ground)
        for instance in ground_first:
            definition = definitions[instance.item]
            path = f"{prefix}/{instance.name}"
            spec = None
            if definition.kind == "part":
                try:
                    spec = parse_spec(dict(definition.spec or {}))
                    built: Any = build_spec(spec)
                except (SpecValidationError, GeometryError) as failure:
                    raise _refuse(f"'{path}' cannot be built: {failure}",
                                  subject="definitions[].spec") from failure  # fmt: skip
                mass = _mass(spec, built)
                centre = built.shape.center(CenterOf.MASS)
                inner = [(path, built.shape, False, mass, Vertex(centre.X, centre.Y, centre.Z),
                          False)]  # fmt: skip
            elif definition.kind == "placeholder":
                holder = definition.placeholder
                if holder is None:  # a placeholder definition holds one, by its validator
                    raise _refuse(f"'{path}' has no placeholder", subject="definitions[]")
                x, y, z = (q.to("mm").magnitude for q in holder.envelope)
                holes = tuple(
                    Feature(
                        tag=h.tag, kind="blind_hole", diameter_mm=h.diameter.to("mm").magnitude,
                        depth_mm=0.0,
                        position_mm=(h.x.to("mm").magnitude, h.y.to("mm").magnitude,
                                     h.z.to("mm").magnitude),
                        axis=_OUTWARD[h.face],
                    )
                    for h in holder.holes
                )  # fmt: skip
                built = BuiltGeometry(name=instance.name, pattern="placeholder", shape=Box(x, y, z),
                                      faces={}, dimensions_mm={}, features=holes)  # fmt: skip
                declared = holder.center_of_mass
                com = (0.0, 0.0, 0.0) if declared is None else tuple(
                    q.to("mm").magnitude for q in declared
                )  # fmt: skip
                inner = [(path, built.shape, True, float(holder.mass.to("kg").magnitude),
                          Vertex(*com), declared is None)]  # fmt: skip
            else:
                sub = shelf[definition.product or ""]
                built = assemble(sub, path)
                inner = [
                    (leaf.path, leaf.shape, leaf.placeholder, leaf.mass, leaf.com, leaf.assumed)
                    for leaf in built.leaves
                ]
            if instance.name == current.ground:
                rotation, translation = _IDENTITY, (0.0, 0.0, 0.0)
            else:
                mates = [m for m in current.mates if m.place.part == instance.name]
                if not mates:
                    raise _refuse(
                        f"'{path}' has no mate; every instance but the ground is placed through "
                        "mates onto one already placed, and a product never states a coordinate",
                        subject="mates",
                        action="add",
                    )
                for mate in mates:
                    if mate.on.part not in placed:
                        raise _refuse(f"mate '{mate.id}' places '{instance.name}' on "
                                      f"'{mate.on.part}', which is not placed yet; list it first",
                                      subject="instances")  # fmt: skip
                rotation, translation, _ = _place(instance.name, built, mates, placed)
            placed[instance.name] = PlacedPart(instance.name, built, spec, rotation, translation)
            members = instance.pattern.count if instance.pattern is not None else 1
            for k in range(members):
                r, t = _member(instance, k, rotation, translation)
                label = path if members == 1 else f"{path}[{k + 1}]"
                for leaf_path, shape, holder_flag, leaf_mass, com, assumed in inner:
                    where = _location(r, t)
                    leaf_label = label + leaf_path[len(path) :]
                    leaves.append(_Leaf(leaf_label, shape.moved(where), holder_flag, leaf_mass,
                                        com.moved(where), assumed))  # fmt: skip
        shape = Compound([leaf.shape for leaf in leaves])
        return _Assembly(shape, leaves)

    assembly = assemble(product, product.name)
    leaves = assembly.leaves
    interference = _interference([(leaf.path, leaf.shape) for leaf in leaves])
    holders = [leaf.path for leaf in leaves if leaf.placeholder]
    if holders:
        interference = interference.model_copy(
            update={
                "detail": f"{interference.detail}; provisional: {len(holders)} placeholder"
                f"{'s' if len(holders) != 1 else ''} ({', '.join(holders[:6])}"
                f"{', …' if len(holders) > 6 else ''}) stand in for undetailed items"
            }
        )
    weighed = [(leaf.mass, _corner(leaf.com.center())) for leaf in leaves if leaf.mass is not None]
    total = sum(mass for mass, _ in weighed)
    centre: tuple[float, float, float] | None = None
    if total > 0:
        x, y, z = (round(sum(m * c[i] for m, c in weighed) / total, 6) + 0.0 for i in range(3))
        centre = (x, y, z)
    return PlacedProduct(
        name=product.name,
        bodies=tuple(
            PlacedBody(
                path=leaf.path,
                placeholder=leaf.placeholder,
                mass_kg=leaf.mass,
                box_min_mm=_corner(leaf.shape.bounding_box().min),
                box_max_mm=_corner(leaf.shape.bounding_box().max),
                center_of_mass_mm=_corner(leaf.com.center()),
            )
            for leaf in leaves
        ),
        interference=interference,
        mass_kg=total,
        mass_rests_on=tuple(holders),
        mass_unknown=tuple(leaf.path for leaf in leaves if leaf.mass is None),
        center_of_mass_mm=centre,
        center_assumed=tuple(leaf.path for leaf in leaves if leaf.assumed),
    )


_OUTWARD: dict[str, tuple[float, float, float]] = {
    "top": (0.0, 0.0, 1.0),
    "bottom": (0.0, 0.0, -1.0),
    "right": (1.0, 0.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "front": (0.0, -1.0, 0.0),
}


def _corner(v: Any) -> tuple[float, float, float]:
    # A vector; a moved Vertex keeps its construction-time .X, so read one by .center().
    x, y, z = (float(v.X), float(v.Y), float(v.Z))
    return round(x, 6) + 0.0, round(y, 6) + 0.0, round(z, 6) + 0.0


def _location(rotation: Any, translation: Any) -> Any:
    from .combination import _location as located

    return located(rotation, translation)


def _member(instance: Instance, k: int, rotation: Any, translation: Any) -> tuple[Any, Any]:
    """The k-th member of an instance's pattern, from the first member's placement."""
    from .combination import _AXES, _about, _add, _apply, _multiply, _scale

    pattern = instance.pattern
    if pattern is None or k == 0:
        return rotation, translation
    if isinstance(pattern, LinearPattern):
        step = pattern.spacing.to("mm").magnitude * k
        return rotation, _add(translation, _scale(_AXES[pattern.direction], step))
    turn = _about(_AXES[pattern.axis], math.radians(pattern.angle_deg * k))
    return _multiply(turn, rotation), _apply(turn, translation)
