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

from pydantic import ConfigDict, Field, computed_field, model_validator

from ._models import (
    EMPTY_MAP,
    FrozenMap,
    Named,
    Provenance,
    StatableModel,
    _refusal_line,
)
from .combination import Mate
from .derivation import DerivationAbsence, Underived
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Need, Scorecard, ScorecardEntry, ValueSource
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
    "LayoutParameter",
    "LayoutDatum",
    "Layout",
    "Variant",
    "Product",
    "ProductNode",
    "PartsListLine",
    "ProductError",
    "parse_product",
    "resolve_variant",
    "product_tree",
    "parts_list",
    "PlacedBody",
    "NodeCard",
    "PlacedProduct",
    "BuildCache",
    "SummaryNode",
    "ProductSummary",
    "summarize_product",
    "place_product",
    "write_product_step",
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


class LayoutParameter(StatableModel):
    """A driving parameter: a name, a value, where it comes from, and what reads it.

    An item reads it by writing ``{layout: <name>}`` where a value goes in its spec or its
    placeholder; :func:`parse_product` puts the value there and records the place in
    ``read_by`` as ``<definition>:<dotted path>``. The product checks every recorded place
    still holds the value, so a stored product cannot claim a reader it does not have.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    value: Quantity
    source: Provenance
    read_by: tuple[str, ...] = Field(default=(), max_length=1024)


_FACE_AXIS = {"top": "z", "bottom": "z", "right": "x", "left": "x", "back": "y", "front": "y"}


class LayoutDatum(StatableModel):
    """A named datum items mate to: a point, an axis or a plane, fixed in the product's frame.

    ``at`` is where it is. An ``axis`` runs along ``direction`` through it, and a ``plane``
    is normal to ``direction`` through it. A mate names the datum as its ``on`` part: a
    plane offers the two faces normal to it (``top`` and ``bottom`` for a ``z`` plane), an
    axis offers itself to a ``shaft_in_bore`` mate, and a point offers any face or axis
    through it. Its coordinates may read layout parameters like any other value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    kind: Literal["point", "axis", "plane"]
    at: tuple[Quantity, Quantity, Quantity]
    direction: Literal["x", "y", "z"] | None = None

    @property
    def at_mm(self) -> tuple[float, float, float]:
        """Where the datum is, in millimetres."""
        x, y, z = (float(q.to("mm").magnitude) for q in self.at)
        return x, y, z

    @model_validator(mode="after")
    def _a_datum(self) -> LayoutDatum:
        for index, value in enumerate(self.at):
            if not value.has_dimension("[length]") or not math.isfinite(value.magnitude):
                raise _refuse(f"datum '{self.name}' at[{index}] is {value}; a datum is placed by "
                              "three finite lengths", subject="layout.datums[].at")  # fmt: skip
        if (self.kind == "point") != (self.direction is None):
            raise _refuse(f"datum '{self.name}' is a {self.kind} and "
                          f"{'states' if self.direction else 'states no'} direction; an axis or "
                          "plane takes one and a point none",
                          subject="layout.datums[].direction")  # fmt: skip
        return self


class Layout(StatableModel):
    """The product's driving parameters and datums, read by name and never itself a part."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameters: tuple[LayoutParameter, ...] = Field(default=(), max_length=256)
    datums: tuple[LayoutDatum, ...] = Field(default=(), max_length=256)

    @property
    def unused(self) -> tuple[str, ...]:
        """The parameters no item reads."""
        return tuple(p.name for p in self.parameters if not p.read_by)


class Variant(StatableModel):
    """A named variant: layout parameters overridden and definitions substituted.

    ``parameters`` gives new values to layout parameters by name. ``substitutions`` are
    definitions that replace the base definitions with the same ``id``. A variant is resolved
    to a complete product of its own by :func:`resolve_variant`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    parameters: FrozenMap[str, Quantity] = Field(default_factory=lambda: EMPTY_MAP)
    substitutions: tuple[Definition, ...] = Field(default=(), max_length=256)


class Product(StatableModel):
    """A product document: its definitions, the instances that place them, and the ground.

    ``layout`` holds the driving parameters its items read by name; it is in no parts list
    and no mass roll-up. ``variants`` are named alternatives to it, each resolved by
    :func:`resolve_variant`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    anvilate_product: str = PRODUCT_VERSION
    name: Named
    description: Provenance | None = None
    identity: ItemIdentity | None = None
    definitions: tuple[Definition, ...] = Field(min_length=1, max_length=256)
    instances: tuple[Instance, ...] = Field(min_length=1, max_length=256)
    ground: Named
    mates: tuple[Mate, ...] = Field(default=(), max_length=512)
    layout: Layout | None = None
    variants: tuple[Variant, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def _refers_to_its_own(self) -> Product:
        ids = [d.id for d in self.definitions]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise _refuse(f"definitions {repeated} are declared twice", subject="definitions[].id")
        names = order = [i.name for i in self.instances]
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
        if self.layout is not None:
            declared = [p.name for p in self.layout.parameters]
            repeated = sorted({n for n in declared if declared.count(n) > 1})
            if repeated:
                raise _refuse(f"layout parameters {repeated} are declared twice",
                              subject="layout.parameters[].name")  # fmt: skip
            names = [d.name for d in self.layout.datums]
            repeated = sorted({n for n in names if names.count(n) > 1 or n in order})
            if repeated:
                raise _refuse(f"layout datums {repeated} are declared twice or share an "
                              "instance's name; a mate names each once",
                              subject="layout.datums[].name")  # fmt: skip
            dumped = {d.id: d.model_dump(mode="json") for d in self.definitions}
            dumped["@layout"] = {"datums": [d.model_dump(mode="json") for d in self.layout.datums]}
            for parameter in self.layout.parameters:
                want = parameter.value.model_dump(mode="json")
                for place in parameter.read_by:
                    owner, _, path = place.partition(":")
                    if _at(dumped.get(owner), path) != want:
                        raise _refuse(f"layout parameter '{parameter.name}' lists '{place}' as "
                                      f"a reader, which does not hold {parameter.value}",
                                      subject="layout.parameters[].read_by")  # fmt: skip
        known = sorted(p.name for p in self.layout.parameters) if self.layout is not None else []
        seen: set[str] = set()
        for variant in self.variants:
            if variant.name in seen:
                raise _refuse(f"variant '{variant.name}' is declared twice",
                              subject="variants[].name")  # fmt: skip
            seen.add(variant.name)
            for name in variant.parameters:
                if name not in known:
                    raise _refuse(f"variant '{variant.name}' overrides '{name}', which the "
                                  f"layout does not declare ({', '.join(known) or 'none'})",
                                  subject="variants[].parameters")  # fmt: skip
            for definition in variant.substitutions:
                if definition.id not in ids:
                    raise _refuse(f"variant '{variant.name}' substitutes '{definition.id}', "
                                  f"which is not a definition here ({', '.join(ids)})",
                                  subject="variants[].substitutions[].id")  # fmt: skip
        return self


_MISSING = object()


def _at(node: Any, path: str) -> Any:
    """The value at a dotted path through mappings and lists, or a sentinel."""
    for step in path.split(".") if path else ():
        if isinstance(node, Mapping) and step in node:
            node = node[step]
        elif isinstance(node, list) and step.isdigit() and int(step) < len(node):
            node = node[int(step)]
        else:
            return _MISSING
    return _MISSING if node is None else node


def _resolve(document: Mapping[str, Any]) -> dict[str, Any]:
    """The document with every ``{layout: name}`` replaced by that parameter's value."""
    layout = document.get("layout")
    if not isinstance(layout, Mapping):
        return dict(document)
    declared = layout.get("parameters")
    declared = declared if isinstance(declared, list) else []
    values: dict[str, Any] = {}
    for parameter in declared:
        if isinstance(parameter, Mapping) and isinstance(parameter.get("name"), str):
            values[parameter["name"]] = parameter.get("value")
    readers: dict[str, list[str]] = {name: [] for name in values}

    def walk(node: Any, owner: str, path: str) -> Any:
        if isinstance(node, Mapping):
            if set(node) == {"layout"}:
                name = node["layout"]
                if not isinstance(name, str) or name not in values:
                    raise _refuse(f"'{owner}' reads layout parameter {name!r} at {path}, which "
                                  f"the layout does not declare ({', '.join(values) or 'none'})",
                                  subject="document")  # fmt: skip
                readers[name].append(f"{owner}:{path}")
                return values[name]
            return {k: walk(v, owner, f"{path}.{k}" if path else str(k)) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, owner, f"{path}.{i}") for i, v in enumerate(node)]
        return node

    definitions = []
    for definition in document.get("definitions") or ():
        if isinstance(definition, Mapping):
            owner = str(definition.get("id"))
            definition = {k: walk(v, owner, k) if k in ("spec", "placeholder") else v
                          for k, v in definition.items()}  # fmt: skip
        definitions.append(definition)
    datums = layout.get("datums")
    if isinstance(datums, list):
        datums = [{**d, "at": walk(d["at"], "@layout", f"datums.{i}.at")}
                  if isinstance(d, Mapping) and "at" in d else d
                  for i, d in enumerate(datums)]  # fmt: skip
    variants = []
    for variant in document.get("variants") or ():
        if isinstance(variant, Mapping) and isinstance(variant.get("substitutions"), list):
            overrides = variant.get("parameters")
            saved = dict(values)
            if isinstance(overrides, Mapping):
                values.update({k: v for k, v in overrides.items() if k in readers})
            label = f"variant {variant.get('name')!s}"
            variant = {**variant, "substitutions": [
                {k: walk(v, f"{label} {d.get('id')!s}", k) if k in ("spec", "placeholder") else v
                 for k, v in d.items()} if isinstance(d, Mapping) else d
                for d in variant["substitutions"]
            ]}  # fmt: skip
            values.clear()
            values.update(saved)
        variants.append(variant)
    for name in readers:
        # a substitution's reads are not the base product's
        readers[name] = [r for r in readers[name] if not r.startswith("variant ")]
    parameters = [
        {**p, "read_by": readers[p["name"]]}
        if isinstance(p, Mapping) and p.get("name") in readers and "read_by" not in p
        else p
        for p in declared
    ]
    resolved_layout = {**layout, "parameters": parameters} if "parameters" in layout else {**layout}
    if isinstance(datums, list):
        resolved_layout["datums"] = datums
    resolved = {**document, "definitions": definitions, "layout": resolved_layout}
    if "variants" in document:
        resolved["variants"] = variants
    return resolved


def parse_product(document: Mapping[str, Any]) -> Product:
    """A product document as its typed model, refusing what cannot be read.

    Every ``{layout: <name>}`` in a definition's spec or placeholder is replaced by that
    layout parameter's value first, and recorded as one of its readers; a name the layout
    does not declare is refused.
    """
    from pydantic import ValidationError

    if not isinstance(document, Mapping):
        raise _refuse("a product document is a mapping", subject="document")
    try:
        return Product.model_validate(_resolve(document))
    except ValidationError as failure:
        first = failure.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "the document"
        raise _refuse(f"the product document is not valid at {where}: "
                      f"{_refusal_line('', first['msg'])}", subject=where) from failure  # fmt: skip


def resolve_variant(product: Product, name: str) -> Product:
    """The variant ``name`` of ``product`` as a complete product of its own, ``<product>-<name>``.

    Each overridden layout parameter takes its new value at every place that reads it, and
    each substitution replaces the base definition with its id. A substitute that does not
    offer a hole or feature a mate uses is refused, naming the mate. A substituted
    sub-product's interfaces are checked when it is placed.
    """
    if not isinstance(name, str):
        raise _refuse(f"a variant is named by a string, not {name!r}", subject="name")
    variants = {v.name: v for v in product.variants}
    if name not in variants:
        raise _refuse(f"'{product.name}' has no variant '{name}' "
                      f"({', '.join(variants) or 'it declares none'})", subject="name")  # fmt: skip
    variant = variants[name]
    data = product.model_dump(mode="json")
    replaced = {d.id: d for d in variant.substitutions}
    index = {d["id"]: d for d in data["definitions"]}
    if data["layout"] is not None:
        index["@layout"] = data["layout"]
    for parameter in (data["layout"] or {}).get("parameters", ()):
        if parameter["name"] not in variant.parameters:
            continue
        value = variant.parameters[parameter["name"]].model_dump(mode="json")
        parameter["value"] = value
        kept = []
        for place in parameter["read_by"]:
            owner, _, path = place.partition(":")
            if owner in replaced:
                continue  # the substitute stands in for this reader
            *parents, last = path.split(".")
            node = index[owner]
            for step in parents:
                node = node[int(step)] if isinstance(node, list) else node[step]
            node[int(last) if isinstance(node, list) else last] = value
            kept.append(place)
        parameter["read_by"] = kept
    if data["layout"] is not None:
        for parameter in data["layout"]["parameters"]:
            parameter["read_by"] = [p for p in parameter["read_by"]
                                    if p.partition(":")[0] not in replaced]  # fmt: skip
    data["definitions"] = [
        replaced[d["id"]].model_dump(mode="json") if d["id"] in replaced else d
        for d in data["definitions"]
    ]
    data["name"], data["variants"] = f"{product.name}-{name}", []
    items = {i.name: i.item for i in product.instances}
    for mate in product.mates:
        for end in (mate.place, mate.on):
            substitute = replaced.get(items.get(end.part, ""))  # a datum is substituted by none
            wanted = [*end.holes, *([end.feature] if end.feature is not None else [])]
            if substitute is None or not wanted:
                continue
            offered = _interfaces(substitute)
            missing = [tag for tag in wanted if offered is not None and tag not in offered]
            if missing:
                raise _refuse(f"variant '{name}' puts '{substitute.id}' where mate '{mate.id}' "
                              f"uses {missing}, which it does not offer "
                              f"({', '.join(sorted(offered or ())) or 'none'})",
                              subject="name")  # fmt: skip
    return Product.model_validate(data)


def _interfaces(definition: Definition) -> set[str] | None:
    """The hole and feature tags a definition offers to a mate; None for a sub-product."""
    if definition.placeholder is not None:
        return {hole.tag for hole in definition.placeholder.holes}
    if definition.spec is None:
        return None
    from .geometry import GeometryError, build_spec
    from .spec import SpecValidationError, parse_spec

    try:
        built = build_spec(parse_spec(dict(definition.spec)))
    except (SpecValidationError, GeometryError) as failure:
        raise _refuse(f"'{definition.id}' cannot be built: {failure}",
                      subject="product") from failure  # fmt: skip
    return {feature.tag for feature in built.features}


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


_WORST_FIRST = (
    CheckStatus.FAIL,
    CheckStatus.NOT_EVALUATED,
    CheckStatus.WARNING,
    CheckStatus.OVER_MARGIN,
    CheckStatus.OUT_OF_DEPTH,
    CheckStatus.PASS,
)


class NodeCard(StatableModel):
    """One node's card: the checks it owns, and its children's cards.

    A part owns its own card's checks, a placeholder owns one not-evaluated entry saying it
    stands in for an undetailed item, and a product owns the interference between its
    children. ``status`` is the worst of its own card and its children's verdicts, with
    not evaluated never counted as a pass. A finding is held once, by the node that owns
    it; an ancestor fails by reference to it (:meth:`findings` lists them with their
    owners).
    """

    # As Scorecard: ``status`` is dump-only, so a card read back from its dump is unchanged.
    model_config = ConfigDict(frozen=True)

    path: Named
    kind: Literal["part", "product", "placeholder"]
    entries: tuple[ScorecardEntry, ...]
    children: tuple[NodeCard, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        present = {Scorecard(entries=self.entries).status, *(c.status for c in self.children)}
        return next(status for status in _WORST_FIRST if status in present)

    def findings(self) -> tuple[tuple[str, ScorecardEntry], ...]:
        """Every entry at or below this node that did not pass, with the path that owns it."""
        own = tuple((self.path, e) for e in self.entries if e.status is not CheckStatus.PASS)
        return own + tuple(f for child in self.children for f in child.findings())

    def flattened(self) -> Scorecard:
        """Every entry at or below this node as one card, for the export gate to judge."""
        return Scorecard(entries=self.entries + tuple(
            entry for child in self.children for entry in child.flattened().entries
        ))  # fmt: skip

    def find(self, path: str) -> NodeCard:
        """The card of the node at ``path``, at or below this one."""
        if path == self.path:
            return self
        for child in self.children:
            if path == child.path or path.startswith(child.path + "/"):
                return child.find(path)
        raise _refuse(f"no node '{path}' under '{self.path}'", subject="path")

    def __str__(self) -> str:
        lines: list[str] = []

        def walk(card: NodeCard, depth: int) -> None:
            own = [e for e in card.entries if e.status is not CheckStatus.PASS]
            line = f"{'  ' * depth}{card.path}: {card.status.value}"
            below = [path for path, e in card.findings()
                     if path != card.path and e.status is card.status]  # fmt: skip
            if below and not own:
                owners = list(dict.fromkeys(below))
                line += (
                    f" by reference to {', '.join(owners[:4])}{', …' if len(owners) > 4 else ''}"
                )
            lines.append(line)
            for entry in own:
                lines.append(f"{'  ' * depth}  - {entry.name} {entry.status.value}: {entry.detail}")
            for child in card.children:
                walk(child, depth + 1)

        walk(self, 0)
        return "\n".join(lines)


class PlacedProduct(StatableModel):
    """A product placed through its mates: its leaves, interference and mass roll-up.

    ``interference`` is the combination's pairwise intersection over every leaf body, and
    says which placeholders it rests on. ``mass_kg`` is the sum of the leaves' masses and
    ``center_of_mass_mm`` their mass-weighted centre; ``mass_rests_on`` names each
    placeholder in them, ``center_assumed`` each placeholder whose centre of mass is its
    envelope's centre, and ``mass_unknown`` each leaf whose material gives no density, so
    the roll-up never reads as more complete than it is. ``unused_parameters`` names each
    layout parameter no item reads. ``card`` is the tree of cards, one per node, each
    product node owning the interference between its own children. ``rebuilt`` and
    ``reused`` count the distinct items built for this placement and taken from a
    :class:`BuildCache`.
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
    unused_parameters: tuple[str, ...] = ()
    card: NodeCard
    rebuilt: int = Field(default=0, ge=0)
    reused: int = Field(default=0, ge=0)

    def __str__(self) -> str:
        rests = f"; rests on placeholders {list(self.mass_rests_on)}" if self.mass_rests_on else ""
        unknown = f"; no mass for {list(self.mass_unknown)}" if self.mass_unknown else ""
        centre = ""
        if self.center_of_mass_mm is not None:
            x, y, z = self.center_of_mass_mm
            assumed = (f", assuming envelope centres for {list(self.center_assumed)}"
                       if self.center_assumed else "")  # fmt: skip
            centre = f"; centre of mass ({x:.4g}, {y:.4g}, {z:.4g}) mm{assumed}"
        if self.unused_parameters:
            centre += f"; layout parameters no item reads: {list(self.unused_parameters)}"
        return (
            f"{self.name}: {len(self.bodies)} bodies, {self.mass_kg:.4g} kg{rests}{unknown}"
            f"{centre}; "
            f"interference {self.interference.status.value}; card {self.card.status.value}; "
            f"{self.rebuilt} of {self.rebuilt + self.reused} items built, {self.reused} reused"
        )


class SummaryNode(StatableModel):
    """One node of a product summary: where it is, what it is, its verdict and why.

    ``findings`` counts the entries this node itself holds that did not pass. ``governing``
    is the worst of them at a node that did not pass, or the paths below it that it fails
    by reference to.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Named
    part_number: Named
    provisional: bool
    status: CheckStatus
    findings: int = Field(ge=0)
    governing: str | None = None


class ProductSummary(StatableModel):
    """A bounded summary of a placed product: one line per node, worst first when cut.

    ``omitted`` counts nodes left out to keep it within its bound; ``more`` says how to ask
    for any node's full card by its path.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    status: CheckStatus
    nodes: tuple[SummaryNode, ...]
    omitted: int = Field(default=0, ge=0)
    more: Provenance
    mass_kg: float
    rebuilt: int = Field(ge=0)
    reused: int = Field(ge=0)

    def __str__(self) -> str:
        lines = [f"{self.name}: {self.status.value} — {self.mass_kg:.4g} kg; "
                 f"{self.rebuilt} of {self.rebuilt + self.reused} items built"]  # fmt: skip
        for node in self.nodes:
            depth = node.path.count("/")
            number = f"{node.part_number}{' (provisional)' if node.provisional else ''}"
            line = f"{'  ' * depth}{node.path} [{number}] {node.status.value}"
            if node.findings:
                line += f", {node.findings} finding{'s' if node.findings != 1 else ''}"
            if node.governing:
                line += f" — {node.governing}"
            lines.append(line)
        if self.omitted:
            lines.append(f"{self.omitted} node{'s' if self.omitted != 1 else ''} not shown, "
                         "none worse than those shown")  # fmt: skip
        lines.append(self.more)
        return "\n".join(lines)


def summarize_product(
    placed: PlacedProduct, tree: ProductNode, *, limit: int = 60, more: str | None = None
) -> ProductSummary:
    """A bounded summary tree of ``placed``: path, part number, verdict and findings per node.

    ``tree`` is :func:`product_tree` of the same product, for the part numbers. Within
    ``limit`` nodes every node is shown in tree order; past it, the nodes on the way to a
    finding are kept first and the rest counted in ``omitted``. ``more`` says how to ask for
    a node's full card; it defaults to :meth:`NodeCard.find`.
    """
    if not isinstance(placed, PlacedProduct):
        raise _refuse("placed must be a PlacedProduct from place_product", subject="placed")
    if not isinstance(tree, ProductNode):
        raise _refuse("tree must be a ProductNode from product_tree", subject="tree")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise _refuse(f"limit is {limit!r}; a summary shows at least one node", subject="limit")
    numbers = {node.path: node for node in tree.walk()}
    numbers[placed.card.path] = tree
    cards: list[NodeCard] = []

    def walk(card: NodeCard) -> None:
        cards.append(card)
        for child in card.children:
            walk(child)

    walk(placed.card)
    keep = cards
    if len(cards) > limit:
        ranked = sorted(range(len(cards)),
                        key=lambda i: (_WORST_FIRST.index(cards[i].status), i))[:limit]  # fmt: skip
        keep = [cards[i] for i in sorted(ranked)]
    nodes = []
    for card in keep:
        own = [e for e in card.entries if e.status is not CheckStatus.PASS]
        governing = None
        if card.status is not CheckStatus.PASS:
            if own:
                worst = min(own, key=lambda e: _WORST_FIRST.index(e.status))
                governing = f"{worst.name}: {worst.detail}"
            else:
                owners = list(dict.fromkeys(
                    p for p, e in card.findings() if p != card.path and e.status is card.status
                ))  # fmt: skip
                governing = f"by reference to {', '.join(owners[:4])}" + (
                    f" and {len(owners) - 4} more" if len(owners) > 4 else ""
                )
        node = numbers[card.path]
        nodes.append(SummaryNode(
            path=card.path, part_number=node.part_number, provisional=node.provisional,
            status=card.status, findings=len(own), governing=governing,
        ))  # fmt: skip
    return ProductSummary(
        name=placed.name,
        status=placed.card.status,
        nodes=tuple(nodes),
        omitted=len(cards) - len(keep),
        more=more or "any node's full card: NodeCard.find(path) on the placed product's card",
        mass_kg=placed.mass_kg,
        rebuilt=placed.rebuilt,
        reused=placed.reused,
    )


class _Leaf:
    def __init__(
        self,
        path: str,
        shape: Any,
        placeholder: bool,
        mass: float | None,
        com: Any,
        assumed: bool,
        entries: tuple[ScorecardEntry, ...],
        key: str = "",
        built: Any = None,
        where: Any = None,
    ) -> None:
        self.path, self.shape, self.placeholder, self.mass = path, shape, placeholder, mass
        # The centre of mass as a vertex, moved with the shape; ``assumed`` when it is a
        # placeholder's envelope centre rather than a declared centre of mass.
        self.com, self.assumed, self.entries = com, assumed, entries
        # For export: the definition's content key, its shape as built, and every move
        # applied to it since, so a repeated item is one STEP product placed many times.
        self.key, self.built, self.where = key, built if built is not None else shape, where

    def moved(self, path: str, where: Any) -> _Leaf:
        return _Leaf(path, self.shape.moved(where), self.placeholder, self.mass,
                     self.com.moved(where), self.assumed, self.entries, self.key, self.built,
                     where if self.where is None else where * self.where)  # fmt: skip


class _Assembly:
    """A placed (sub-)product: a shape and features for ``_place``, and its leaves."""

    def __init__(self, shape: Any, leaves: list[_Leaf]) -> None:
        self.shape, self.leaves, self.features = shape, leaves, ()


class BuildCache:
    """Built items kept between product builds, keyed on the content of their definitions.

    Pass the same cache to successive :func:`place_product` calls: an item whose spec or
    placeholder is unchanged is reused, built geometry and card alike, and only changed
    ones are built again. The key is the definition's content, not its id or identity, so
    renaming or renumbering an item does not rebuild it. Placement and every check that
    spans items run on each build.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, Any, _Leaf]] = {}

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"BuildCache({len(self._store)} built items)"


def _placed_leaves(
    product: Product, library: Mapping[str, Product] | None, cache: BuildCache | None
) -> tuple[list[_Leaf], int, int]:
    """Every leaf body placed where its mates put it, and the items rebuilt and reused."""
    from .combination import _IDENTITY, PlacedPart, _place

    if cache is not None and not isinstance(cache, BuildCache):
        raise _refuse(f"cache is a {type(cache).__name__}; pass a BuildCache or none",
                      subject="cache")  # fmt: skip
    store = cache._store if cache is not None else {}
    rebuilt: set[str] = set()
    reused: set[str] = set()

    shelf = dict(library or {})
    product_tree(product, library=shelf)  # the identity and containment refusals first

    def assemble(current: Product, prefix: str) -> _Assembly:
        from build123d import Box, CenterOf, Compound, Vertex

        from .combination import _mass
        from .features import Feature
        from .geometry import BuiltGeometry, GeometryError, build_spec
        from .screening import screen_spec
        from .spec import SpecValidationError, parse_spec

        definitions = {d.id: d for d in current.definitions}
        order = [i.name for i in current.instances]
        datums = {d.name: d for d in current.layout.datums} if current.layout is not None else {}
        for mate in current.mates:
            if mate.place.part in datums:
                raise _refuse(f"mate '{mate.id}' places the datum '{mate.place.part}', which is "
                              "fixed; a datum is a mate's 'on' end",
                              subject="mates[].place.part")  # fmt: skip
            for end in (mate.place, mate.on):
                if end.part not in order and end.part not in datums:
                    raise _refuse(f"mate '{mate.id}' names '{end.part}', which is not an instance "
                                  f"or datum of '{current.name}' ({', '.join([*order, *datums])})",
                                  subject="mates[].place.part")  # fmt: skip
            if mate.place.part == current.ground:
                raise _refuse(f"mate '{mate.id}' places the ground '{current.ground}', which stays "
                              "where it is", subject="mates[].place.part")  # fmt: skip
            if mate.on.part in datums:
                _offers(datums[mate.on.part], mate)
        placed: dict[str, PlacedPart] = {
            name: PlacedPart(name, BuiltGeometry(name=name, pattern="datum", shape=Vertex(0, 0, 0),
                                                 faces={}, dimensions_mm={}),
                             None, _IDENTITY, datum.at_mm)
            for name, datum in datums.items()
        }  # fmt: skip

        def make(definition: Definition, path: str) -> tuple[Any, Any, _Leaf]:
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
                return built, spec, _Leaf(path, built.shape, False, mass,
                                          Vertex(centre.X, centre.Y, centre.Z), False,
                                          screen_spec(spec).entries)  # fmt: skip
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
            built = BuiltGeometry(name="placeholder", pattern="placeholder", shape=Box(x, y, z),
                                  faces={}, dimensions_mm={}, features=holes)  # fmt: skip
            declared = holder.center_of_mass
            com = (0.0, 0.0, 0.0) if declared is None else tuple(
                q.to("mm").magnitude for q in declared
            )  # fmt: skip
            stands_in = ScorecardEntry(
                name="placeholder",
                status=CheckStatus.NOT_EVALUATED,
                detail=f"a placeholder stands in for an undetailed item ({holder.reason}); "
                "every result resting on it is provisional",
                underived=_STANDS_IN,
                needs=(_NEEDS_A_DETAIL,),
            )
            return built, None, _Leaf(path, built.shape, True,
                                      float(holder.mass.to("kg").magnitude), Vertex(*com),
                                      declared is None, (stands_in,))  # fmt: skip

        leaves: list[_Leaf] = []
        ground_first = sorted(current.instances, key=lambda i: i.name != current.ground)
        for instance in ground_first:
            definition = definitions[instance.item]
            path = f"{prefix}/{instance.name}"
            spec = None
            if definition.kind in ("part", "placeholder"):
                key = _content(definition, shelf)
                if key not in store:
                    store[key] = make(definition, path)
                    rebuilt.add(key)
                elif key not in rebuilt:
                    reused.add(key)
                built, spec, leaf = store[key]
                inner = [_Leaf(path, leaf.shape, leaf.placeholder, leaf.mass, leaf.com,
                               leaf.assumed, leaf.entries, key)]  # fmt: skip
            else:
                sub = shelf[definition.product or ""]
                built = assemble(sub, path)
                inner = built.leaves
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
                where = _location(r, t)
                leaves.extend(leaf.moved(label + leaf.path[len(path) :], where) for leaf in inner)
        shape = Compound([leaf.shape for leaf in leaves])
        return _Assembly(shape, leaves)

    return assemble(product, product.name).leaves, len(rebuilt), len(reused)


def place_product(
    product: Product,
    *,
    library: Mapping[str, Product] | None = None,
    cache: BuildCache | None = None,
) -> PlacedProduct:
    """Place every instance through its mates, then check interference and roll up mass.

    The ground stays at the origin. Every other instance — a pattern's first member, named
    by the instance's name — must be placed by at least one mate onto an instance listed
    before it; the rest of a pattern follows its first member. A mate that leaves an
    instance free or contradicts another is refused by the combination's own rules.

    With a ``cache``, an item built before from the same content is reused; the placed
    product's ``rebuilt`` and ``reused`` count the distinct items each way.
    """
    from .combination import _interference

    leaves, rebuilt, reused = _placed_leaves(product, library, cache)
    interference = _provisional(_interference([(leaf.path, leaf.shape) for leaf in leaves]), leaves)
    holders = [leaf.path for leaf in leaves if leaf.placeholder]
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
        unused_parameters=product.layout.unused if product.layout is not None else (),
        card=_card(product.name, leaves),
        rebuilt=rebuilt,
        reused=reused,
    )


def _offers(datum: LayoutDatum, mate: Mate) -> None:
    """Refuse a mate that asks a datum for a face or axis it does not have."""
    if mate.kind == "hole_pattern" or mate.on.feature is not None or mate.on.holes:
        raise _refuse(f"mate '{mate.id}' asks the datum '{datum.name}' for holes or a feature; a "
                      "datum offers faces and axes", subject="product")  # fmt: skip
    face, axis = mate.on.face, mate.on.axis
    if datum.kind == "plane" and (face is None or _FACE_AXIS[face] != datum.direction):
        raise _refuse(f"mate '{mate.id}' asks the {datum.direction} plane '{datum.name}' for "
                      f"{f'its {face} face' if face else 'an axis'}; it offers only the two faces "
                      f"normal to {datum.direction}", subject="product")  # fmt: skip
    if datum.kind == "axis" and axis != datum.direction:
        raise _refuse(f"mate '{mate.id}' asks the {datum.direction} axis '{datum.name}' for "
                      f"{f'a {face} face' if face else f'the {axis} axis'}; it offers only itself "
                      "to a shaft_in_bore mate", subject="product")  # fmt: skip


_NEEDS_A_DETAIL = Need(
    declaration="definitions[].spec",
    takes="the item's Design Spec in place of its placeholder, once it is detailed or chosen",
    sources=(ValueSource.USER, ValueSource.DATABASE),
)
_STANDS_IN = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="a placeholder is declared, not analysed: its card is its reason",
)


def _provisional(entry: ScorecardEntry, leaves: list[_Leaf]) -> ScorecardEntry:
    """``entry``, saying it is provisional when any of ``leaves`` is a placeholder."""
    holders = [leaf.path for leaf in leaves if leaf.placeholder]
    if not holders:
        return entry
    shown = ", ".join(holders[:6]) + (", …" if len(holders) > 6 else "")
    plural = "s" if len(holders) != 1 else ""
    return entry.model_copy(update={"detail": f"{entry.detail}; provisional: {len(holders)} "
                                    f"placeholder{plural} ({shown}) stand in for undetailed "
                                    "items"})  # fmt: skip


def _card(path: str, leaves: list[_Leaf]) -> NodeCard:
    """The card of the node at ``path``, from the leaves under it, each child in order."""
    from build123d import Compound

    from .combination import _interference

    if len(leaves) == 1 and leaves[0].path == path:
        leaf = leaves[0]
        return NodeCard(path=path, kind="placeholder" if leaf.placeholder else "part",
                        entries=leaf.entries)  # fmt: skip
    groups: dict[str, list[_Leaf]] = {}
    for leaf in leaves:
        child = leaf.path[len(path) + 1 :].split("/")[0]
        groups.setdefault(f"{path}/{child}", []).append(leaf)
    bodies = [
        (child, group[0].shape if len(group) == 1 else Compound([g.shape for g in group]))
        for child, group in groups.items()
    ]
    interference = _provisional(_interference(bodies), leaves)
    return NodeCard(
        path=path,
        kind="product",
        entries=(interference,),
        children=tuple(_card(child, group) for child, group in groups.items()),
    )


def write_product_step(
    product: Product,
    path: Any,
    *,
    authorization: Any,
    library: Mapping[str, Product] | None = None,
    cache: BuildCache | None = None,
) -> Any:
    """Write the placed product as one STEP AP242 assembly, each item one named product.

    Every occurrence of an item is a component placed where its mates put it, so a drive
    used twice is one product placed twice. Each product is named by its part number and
    description, provisional numbers included. ``authorization`` is the export gate's
    verdict on the product's card (:meth:`NodeCard.flattened`); a product resting on
    placeholders is not evaluated, so it is written only watermarked unvalidated.
    """
    from build123d import Location

    from .combination import _write_assembly

    tree = product_tree(product, library=library)
    nodes = {node.path: node for node in tree.walk()}
    leaves, _rebuilt, _reused = _placed_leaves(product, library, cache)
    bodies = []
    for leaf in leaves:
        node = nodes[leaf.path]
        bodies.append((leaf.key, f"{node.part_number} {node.description}", leaf.built,
                       leaf.where if leaf.where is not None else Location()))  # fmt: skip
    return _write_assembly(
        product.name,
        bodies,
        path,
        authorization=authorization,
        description="Anvilate product: an assembly of its items, each placed by its mates",
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
