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
    ItemCollection,
    Named,
    Provenance,
    StatableModel,
    _refusal_line,
)
from .combination import Mate
from .derivation import DerivationAbsence, Underived
from .interfaces import (
    COMPATIBLE,
    KINDS,
    Interface,
    PartInterface,
    check_interfaces,
    partners_of,
)
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Need, Scorecard, ScorecardEntry, ValueSource
from .units import Quantity

__all__ = [
    "PRODUCT_VERSION",
    "ItemSource",
    "ItemIdentity",
    "Placeholder",
    "PlaceholderHole",
    "Reference",
    "Definition",
    "LinearPattern",
    "CircularPattern",
    "Instance",
    "LayoutParameter",
    "LayoutDatum",
    "Layout",
    "Variant",
    "Joint",
    "Connection",
    "PlacedJoint",
    "OpenInterface",
    "MassGrowth",
    "Limit",
    "ProductLoad",
    "Split",
    "Expansion",
    "Thermal",
    "ChainLink",
    "ProductChain",
    "Cited",
    "Substance",
    "MaterialDeclaration",
    "UL94_CLASSES",
    "Sterilization",
    "MaterialNeeds",
    "Screening",
    "Product",
    "ProductNode",
    "PartsListLine",
    "ProductError",
    "parse_product",
    "load_product",
    "resolve_variant",
    "product_tree",
    "parts_list",
    "PlacedBody",
    "NodeCard",
    "InterfaceRow",
    "InterfaceTable",
    "PlacedProduct",
    "BuildCache",
    "SummaryNode",
    "ProductSummary",
    "summarize_product",
    "place_product",
    "write_product_step",
]

PRODUCT_VERSION: Literal["1.12.0"] = "1.12.0"
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
    interfaces: tuple[Interface, ...] = Field(default=(), max_length=32)

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
        check_interfaces(self.interfaces, set(tags), "the placeholder")
        return self


# A component record offers holes as a placeholder does, so components imports this module
# at its end; importing it here, after PlaceholderHole, keeps either import order working.
from .components import ComponentRecord, Demand, Price  # noqa: E402


class Reference(StatableModel):
    """An existing assembly the product is designed against, read from a STEP file.

    ``file`` is the STEP assembly's path relative to the product's folder. It is placed and
    mated by its envelope's faces like any item, every solid in it is checked for
    interference, and its ``clearance`` is the least gap the product's own items must keep
    to it. It is never made: it is out of the release's STEP and is a reference line on the
    BOM.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Named
    clearance: Quantity | None = None

    @model_validator(mode="after")
    def _a_gap(self) -> Reference:
        if self.clearance is not None and not (
            self.clearance.has_dimension("[length]") and self.clearance.magnitude >= 0
        ):
            raise _refuse(f"reference clearance is {self.clearance}; it is a length, not "
                          "negative", subject="reference.clearance")  # fmt: skip
        return self


class Definition(StatableModel):
    """One item defined once: a catalog part's spec, a sub-product, a placeholder, or a
    purchased component.

    ``component`` is a :class:`~anvilate.components.ComponentRecord`: placed as its envelope
    with its holes, and checked by its ratings against ``demands``, what the product asks
    of it. Only a component states demands, and a component is bought.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    identity: ItemIdentity
    spec: FrozenMap[str, Any] | None = None
    product: Named | None = None
    placeholder: Placeholder | None = None
    component: ComponentRecord | None = None
    reference: Reference | None = None
    demands: tuple[Demand, ...] = Field(default=(), max_length=32)
    # A catalog part's interfaces, bound to its tagged features and read from the built part.
    interfaces: tuple[PartInterface, ...] = Field(default=(), max_length=32)
    # The material a placeholder or component is made of, by its id in the product's
    # material declarations; a catalog part's is its spec's own material.
    material: Named | None = None
    # A made part's or placeholder's unit cost, cited and dated; a component's price is on
    # its record, and a product's cost is what its items roll up to.
    price: Price | None = None

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> Definition:
        kinds = [k for k in ("spec", "product", "placeholder", "component", "reference")
                 if getattr(self, k) is not None]  # fmt: skip
        if len(kinds) != 1:
            raise _refuse(
                f"definition '{self.id}' states {kinds or 'none'} of spec, product, "
                "placeholder, component and reference; a definition is exactly one of them",
                subject="definitions[].spec",
            )
        if self.interfaces and self.spec is None:
            raise _refuse(f"definition '{self.id}' states interfaces and is not a catalog part; "
                          "a placeholder or component states its interfaces inside it",
                          subject="definitions[].interfaces")  # fmt: skip
        names = [i.name for i in self.interfaces]
        if len(set(names)) != len(names):
            raise _refuse(f"definition '{self.id}' offers interfaces {names} with a name twice",
                          subject="definitions[].interfaces")  # fmt: skip
        if self.demands and self.component is None:
            raise _refuse(f"definition '{self.id}' states demands and is not a component; "
                          "demands are what a product asks of a bought component",
                          subject="definitions[].demands")  # fmt: skip
        if self.price is not None and self.spec is None and self.placeholder is None:
            raise _refuse(f"definition '{self.id}' states a price and is a {self.kind}; a "
                          "component's price is on its record, a product's is rolled up, "
                          "and a reference is not costed",
                          subject="definitions[].price")  # fmt: skip
        if self.reference is not None and self.identity.source is not ItemSource.REFERENCE:
            raise _refuse(f"definition '{self.id}' is a reference assembly and its identity "
                          f"says {self.identity.source.value}; a reference is neither made "
                          "nor bought", subject="definitions[].identity.source")  # fmt: skip
        if self.component is not None:
            if self.identity.source is not ItemSource.BUY:
                raise _refuse(f"definition '{self.id}' is a purchased component and its "
                              f"identity says {self.identity.source.value}; a component is "
                              "bought", subject="definitions[].identity.source")  # fmt: skip
            names = [d.name for d in self.demands]
            doubled = sorted({n for n in names if names.count(n) > 1})
            if doubled:
                raise _refuse(f"definition '{self.id}' states demands {doubled} twice",
                              subject="definitions[].demands")  # fmt: skip
        return self

    @property
    def kind(self) -> str:
        """``part``, ``product``, ``placeholder`` or ``component``."""
        if self.spec is not None:
            return "part"
        if self.product is not None:
            return "product"
        if self.reference is not None:
            return "reference"
        return "component" if self.component is not None else "placeholder"


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


_ANGULAR = ("revolute", "cylindrical")


class Joint(StatableModel):
    """How a connection moves: rigid, or about or along the axis its interfaces share.

    A ``revolute`` joint turns and a ``linear`` one slides along the axis; a ``cylindrical``
    one does both and a ``ball`` turns about its point. ``range`` is a revolute or
    cylindrical joint's turn, as angles, or a linear joint's travel, as lengths, from the
    placed position; the placed product sweeps the moving item through it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["rigid", "revolute", "linear", "cylindrical", "ball"]
    range: tuple[Quantity, Quantity] | None = None

    @model_validator(mode="after")
    def _a_range(self) -> Joint:
        if self.range is None:
            return self
        if self.kind in ("rigid", "ball"):
            raise _refuse(f"a {self.kind} joint states no range", subject="joint.range")
        unit = "degree" if self.kind in _ANGULAR else "mm"
        low, high = self.range
        try:
            values = [q.to(unit).magnitude for q in (low, high)]
        except ValueError as failure:
            raise _refuse(f"a {self.kind} joint's range is {low} to {high}; it is "
                          f"{'an angle' if unit == 'degree' else 'a length'}",
                          subject="joint.range") from failure  # fmt: skip
        if not (math.isfinite(values[0]) and math.isfinite(values[1]) and values[0] < values[1]):
            raise _refuse(f"a {self.kind} joint's range is {low} to {high}; it runs from the "
                          "lower to the higher, both finite", subject="joint.range")  # fmt: skip
        return self


class Connection(StatableModel):
    """Two interfaces that meet, each as ``item.interface``: ``place`` is placed on ``on``.

    The item is an instance of the product that declares the connection. The mate is
    derived from the pair: a pattern meets a pattern hole by hole, a face meets a face, a
    shaft runs in its bore. The pairing's checks go on that product's card. ``joint``
    declares how the placed item moves; any joint but a rigid one needs two interfaces that
    define an axis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    on: Named
    place: Named
    joint: Joint | None = None


class PlacedJoint(StatableModel):
    """A declared joint where the product put it: its axis in the product's frame, its range.

    ``node`` is the product that declares it; ``point_mm`` and ``direction`` are its axis in
    the frame of the product it was placed in (the top product's, for a joint in a
    sub-product). ``range_low`` and ``range_high`` are in ``range_unit``, degrees or mm.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    node: str = ""
    connection: Named
    kind: Named
    point_mm: tuple[float, float, float]
    direction: tuple[float, float, float]
    range_low: float | None = None
    range_high: float | None = None
    range_unit: str | None = None


class OpenInterface(StatableModel):
    """An interface left unconnected on purpose, as ``item.interface``, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: Named
    reason: Provenance


def _split(reference: str, subject: str) -> tuple[str, str]:
    item, dot, name = reference.rpartition(".")
    if not dot or not item or not name:
        raise _refuse(f"'{reference}' is not item.interface", subject=subject)
    return item, name


class MassGrowth(StatableModel):
    """The growth allowance a mass carries by its maturity, as fractions, and their source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    estimated: float = Field(default=0.0, ge=0, le=1)
    calculated: float = Field(default=0.0, ge=0, le=1)
    measured: float = Field(default=0.0, ge=0, le=1)
    source: Provenance


class Limit(StatableModel):
    """A declared limit on the product as a whole, and where it comes from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Quantity
    source: Provenance


class ProductLoad(StatableModel):
    """A load the product carries: on an item, as a force down or a mass under gravity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Named
    force: Quantity | None = None
    mass: Quantity | None = None
    source: Provenance

    @model_validator(mode="after")
    def _one(self) -> ProductLoad:
        if (self.force is None) == (self.mass is None):
            stated = "both" if self.force else "neither"
            raise _refuse(f"load on '{self.item}' states {stated} of force and mass; a load "
                          "states one", subject="screening.loads")  # fmt: skip
        value, dimension = ((self.force, "[force]") if self.force is not None
                            else (self.mass, "[mass]"))  # fmt: skip
        assert value is not None
        if not (value.has_dimension(dimension) and value.magnitude > 0):
            raise _refuse(f"load on '{self.item}' is {value}; it is a positive "
                          f"{dimension.strip('[]')}", subject="screening.loads")  # fmt: skip
        return self


class Split(StatableModel):
    """How a body's load divides among more supports than determine it, and on what basis."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Named
    shares: FrozenMap[str, float]
    basis: Provenance

    @model_validator(mode="after")
    def _whole(self) -> Split:
        if any(not (0 <= v <= 1) for v in self.shares.values()) or (
            abs(sum(self.shares.values()) - 1) > 1e-6
        ):
            raise _refuse(f"the split of '{self.body}' gives shares {dict(self.shares)}; each "
                          "is a fraction and they add up to 1",
                          subject="screening.splits")  # fmt: skip
        return self


class Expansion(StatableModel):
    """A material's coefficient of thermal expansion, as the declaration read it, cited."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    material: Named
    coefficient: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _a_coefficient(self) -> Expansion:
        if not (self.coefficient.has_dimension("1 / [temperature]")
                and self.coefficient.magnitude > 0):  # fmt: skip
            raise _refuse(f"{self.material}'s expansion coefficient is {self.coefficient}; it "
                          "is a positive strain per kelvin, such as 1/K",
                          subject="screening.thermal.coefficients")  # fmt: skip
        return self


class Thermal(StatableModel):
    """The temperature range the product sees, the slip its connections allow, and the
    expansion coefficients of its materials, each cited."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    range: Quantity
    slip: Quantity
    coefficients: tuple[Expansion, ...] = Field(min_length=1, max_length=64)
    source: Provenance

    @model_validator(mode="after")
    def _a_range(self) -> Thermal:
        if not (self.range.has_dimension("[temperature]") and self.range.magnitude > 0):
            raise _refuse(f"the thermal range is {self.range}; it is a positive temperature "
                          "difference, such as K", subject="screening.thermal.range")  # fmt: skip
        if not (self.slip.has_dimension("[length]") and self.slip.magnitude >= 0):
            raise _refuse(f"the thermal slip is {self.slip}; it is a length",
                          subject="screening.thermal.slip")  # fmt: skip
        return self


class ChainLink(StatableModel):
    """One link of a stack-up chain across a product: a part's dimension or a connection.

    A part link names its ``item`` and the ``dimension`` tag; the dimension's declared
    tolerance is used, or, where the item declares none, the ISO 2768-1 general tolerance on
    the ``nominal`` the link states. A connection link names the mate or connection and
    the ± ``allowance`` it contributes, with its ``source``. ``direction`` is +1 when the
    link growing widens the gap.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Named | None = None
    dimension: Named | None = None
    nominal: Quantity | None = None
    connection: Named | None = None
    allowance: Quantity | None = None
    source: Provenance | None = None
    direction: Literal[1, -1] = 1

    @model_validator(mode="after")
    def _a_link(self) -> ChainLink:
        part = self.item is not None and self.dimension is not None
        joint = self.connection is not None and self.allowance is not None
        if part == joint:
            raise _refuse("a chain link is a part's dimension (item and dimension) or a "
                          "connection's allowance (connection and allowance), one of them",
                          subject="screening.chains[].links")  # fmt: skip
        for name, value in (("nominal", self.nominal), ("allowance", self.allowance)):
            if value is not None and not (value.has_dimension("[length]")
                                          and value.magnitude >= 0):  # fmt: skip
                raise _refuse(f"a chain link's {name} is {value}; it is a length",
                              subject="screening.chains[].links")  # fmt: skip
        if joint and self.source is None:
            raise _refuse(f"the allowance of connection {self.connection} is not cited; "
                          "state its source", subject="screening.chains[].links")  # fmt: skip
        return self


class ProductChain(StatableModel):
    """A one-dimensional stack-up through a product's items and connections, and the band
    its gap must land in; ``samples`` and ``seed`` add a seeded Monte Carlo run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    links: tuple[ChainLink, ...] = Field(min_length=1, max_length=64)
    required_min: Quantity
    required_max: Quantity
    samples: int | None = Field(default=None, ge=2, le=1_000_000)
    seed: int | None = None

    @model_validator(mode="after")
    def _a_band(self) -> ProductChain:
        if self.required_max.to("mm").magnitude < self.required_min.to("mm").magnitude:
            raise _refuse(f"chain {self.name} requires a band whose maximum is below its "
                          "minimum", subject="screening.chains[].required_max")  # fmt: skip
        if (self.samples is None) != (self.seed is None):
            raise _refuse(f"chain {self.name} states one of samples and seed; a Monte Carlo "
                          "run takes both, so it repeats",
                          subject="screening.chains[].seed")  # fmt: skip
        return self


class Cited(StatableModel):
    """A declared value and the source it was read from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Quantity | float | str
    source: Provenance


class Substance(StatableModel):
    """One substance in a material: its CAS number, its name, its mass fraction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cas: str = Field(pattern=r"^\d{2,7}-\d{2}-\d$")
    name: Named
    fraction: float = Field(ge=0, le=1)


class MaterialDeclaration(StatableModel):
    """What a material is made of and what it withstands, each value with its source.

    ``material`` is the id the product's items name. ``plastic`` counts it in the recycled
    plastic roll-up. ``attributes`` are the material's own declared values, read by the
    material needs: ``service_max_temperature``, ``total_mass_loss`` (a fraction),
    ``flammability`` (a UL 94 class) and ``biocompatibility`` (a body-contact category).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    material: Named
    plastic: bool = False
    composition: tuple[Substance, ...] = Field(default=(), max_length=256)
    composition_source: Provenance | None = None
    recycled_fraction: Cited | None = None
    attributes: FrozenMap[str, Cited] = Field(default_factory=lambda: EMPTY_MAP)

    @model_validator(mode="after")
    def _a_declaration(self) -> MaterialDeclaration:
        if self.composition and self.composition_source is None:
            raise _refuse(f"material {self.material}'s composition is not cited; state "
                          "composition_source", subject="screening.materials")  # fmt: skip
        if sum(s.fraction for s in self.composition) > 1 + 1e-6:
            raise _refuse(f"material {self.material}'s composition adds up past 1",
                          subject="screening.materials")  # fmt: skip
        unknown = sorted(set(self.attributes) - set(_MATERIAL_ATTRIBUTES))
        if unknown:
            raise _refuse(f"material {self.material} declares {unknown}; the attributes "
                          f"read are {', '.join(_MATERIAL_ATTRIBUTES)}",
                          subject="screening.materials")  # fmt: skip
        for attribute, stated in self.attributes.items():
            problem = _cited_problem(_ATTRIBUTE_KINDS[attribute], stated.value)
            if problem:
                raise _refuse(f"material {self.material}'s {attribute} is {stated.value!r}; "
                              f"it is {problem}", subject="screening.materials")  # fmt: skip
        return self


_MATERIAL_ATTRIBUTES = ("service_max_temperature", "total_mass_loss", "flammability",
                        "biocompatibility")  # fmt: skip
#: UL 94 classes, least to most flame-retardant, as the classes are named.
UL94_CLASSES = ("HB", "V-2", "V-1", "V-0", "5VB", "5VA")

_ATTRIBUTE_KINDS = {"service_max_temperature": "temperature", "total_mass_loss": "fraction",
                    "flammability": "ul94", "biocompatibility": "category"}  # fmt: skip
_NEED_KINDS = {"service_temperature": "temperature", "vacuum": "fraction",
               "flammability": "ul94", "body_contact": "category"}  # fmt: skip


def _cited_problem(kind: str, value: Any) -> str | None:
    """What a cited value of ``kind`` must be, when ``value`` is not one; else None."""
    if kind == "temperature":
        if isinstance(value, Quantity) and value.has_dimension("[temperature]"):
            return None
        return "a temperature with its unit"
    if kind == "fraction":
        if isinstance(value, float) and 0 <= value <= 1:
            return None
        return "a fraction from 0 to 1"
    if kind == "ul94":
        return None if value in UL94_CLASSES else f"a UL 94 class ({', '.join(UL94_CLASSES)})"
    return None if isinstance(value, str) and value.strip() else "a named category"


class Sterilization(StatableModel):
    """A sterilization the material must survive: the method, its temperature, the source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Named
    temperature: Quantity
    source: Provenance


class MaterialNeeds(StatableModel):
    """What the product's materials must withstand, each need with its limit and source.

    ``items`` limits the needs to those items (all of them when empty). Each need is a
    :class:`Cited` limit: ``service_temperature`` and ``sterilization`` a temperature the
    material's service maximum must reach; ``vacuum`` the largest total mass loss allowed;
    ``flammability`` the least UL 94 class; ``body_contact`` the category the material must
    be declared for.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[Named, ...] = ()
    service_temperature: Cited | None = None
    sterilization: Sterilization | None = None
    vacuum: Cited | None = None
    flammability: Cited | None = None
    body_contact: Cited | None = None

    @model_validator(mode="after")
    def _typed(self) -> MaterialNeeds:
        for name, kind in _NEED_KINDS.items():
            need = getattr(self, name)
            problem = need is not None and _cited_problem(kind, need.value)
            if problem:
                raise _refuse(f"material need {name} is {need.value!r}; it is {problem}",
                              subject=f"screening.needs.{name}")  # fmt: skip
        if self.sterilization is not None and _cited_problem(
            "temperature", self.sterilization.temperature
        ):
            raise _refuse(f"sterilization temperature is {self.sterilization.temperature}; it "
                          "is a temperature with its unit",
                          subject="screening.needs.sterilization")  # fmt: skip
        return self


class Screening(StatableModel):
    """What the product as a whole is held to.

    ``mass_growth`` is the growth allowance per mass maturity; ``max_mass`` is checked on
    the predicted mass, basic plus growth; ``min_tilt`` is the tilt the centre of mass must
    stay inside the footprint up to; ``min_clearance`` the least gap between any two items
    that share no connection. ``loads`` are what the product carries, which travel down
    through the bodies they rest on to the floor; ``splits`` divide a body's load among
    more supports than determine it, each with its basis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mass_growth: MassGrowth | None = None
    max_mass: Limit | None = None
    min_tilt: Limit | None = None
    min_clearance: Limit | None = None
    loads: tuple[ProductLoad, ...] = Field(default=(), max_length=256)
    splits: tuple[Split, ...] = Field(default=(), max_length=256)
    thermal: Thermal | None = None
    chains: tuple[ProductChain, ...] = Field(default=(), max_length=64)
    materials: tuple[MaterialDeclaration, ...] = Field(default=(), max_length=256)
    needs: MaterialNeeds | None = None
    # Items separated for service, which assembly economy never proposes merging.
    serviced: tuple[Named, ...] = Field(default=(), max_length=256)

    @model_validator(mode="after")
    def _dimensions(self) -> Screening:
        stated = (
            ("max_mass", self.max_mass, "[mass]"),
            ("min_tilt", self.min_tilt, "[]"),
            ("min_clearance", self.min_clearance, "[length]"),
        )
        for name, limit, dimension in stated:
            if limit is not None and not (
                limit.value.has_dimension(dimension) and limit.value.magnitude >= 0
            ):
                raise _refuse(f"screening {name} is {limit.value}; it is a non-negative "
                              f"{'angle' if dimension == '[]' else dimension}",
                              subject=f"screening.{name}")  # fmt: skip
        ids = [m.material for m in self.materials]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise _refuse(f"materials {repeated} are declared twice; each is declared once",
                          subject="screening.materials")  # fmt: skip
        return self


class Product(StatableModel):
    """A product document: its definitions, the instances that place them, and the ground.

    ``layout`` holds the driving parameters its items read by name; it is in no parts list
    and no mass roll-up. ``variants`` are named alternatives to it, each resolved by
    :func:`resolve_variant`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # 1.1.0 adds a definition's component and demands, 1.2.0 a component's vendor model and
    # drafted state, 1.3.0 interfaces, connections and open interfaces, and 1.4.0 a catalog
    # part's interfaces bound to its features, 1.5.0 a joint on a connection, and 1.6.0 a
    # reference assembly, 1.7.0 what the product as a whole is screened against, and 1.8.0
    # the loads it carries and declared splits, and 1.9.0 its thermal range and the items
    # separated for service, and 1.10.0 stack-up chains through its items, and 1.11.0 its
    # materials and what they must withstand, and 1.12.0 a unit price on a part or a
    # component record; an older document reads unchanged.
    anvilate_product: Literal[
        "1.0.0",
        "1.1.0",
        "1.2.0",
        "1.3.0",
        "1.4.0",
        "1.5.0",
        "1.6.0",
        "1.7.0",
        "1.8.0",
        "1.9.0",
        "1.10.0",
        "1.11.0",
        "1.12.0",
    ] = PRODUCT_VERSION
    name: Named
    description: Provenance | None = None
    identity: ItemIdentity | None = None
    definitions: tuple[Definition, ...] = Field(min_length=1, max_length=256)
    instances: tuple[Instance, ...] = Field(min_length=1, max_length=256)
    ground: Named
    mates: tuple[Mate, ...] = Field(default=(), max_length=512)
    layout: Layout | None = None
    variants: tuple[Variant, ...] = Field(default=(), max_length=64)
    connections: tuple[Connection, ...] = Field(default=(), max_length=512)
    screening: Screening | None = None
    open_interfaces: tuple[OpenInterface, ...] = Field(default=(), max_length=512)

    def offers(self) -> dict[str, dict[str, Interface | PartInterface]]:
        """Each instance's interfaces by name: its placeholder's or component's, or a
        catalog part's bindings, which are read from the part once it is built."""
        definitions = {d.id: d for d in self.definitions}
        offered: dict[str, dict[str, Interface | PartInterface]] = {}
        for instance in self.instances:
            definition = definitions[instance.item]
            held = definition.placeholder or definition.component
            stated = held.interfaces if held is not None else definition.interfaces
            offered[instance.name] = {i.name: i for i in stated}
        return offered

    def interface_at(self, reference: str, subject: str) -> tuple[str, Interface | PartInterface]:
        """The instance and interface ``item.interface`` names, or a refusal naming it."""
        item, name = _split(reference, subject)
        offered = self.offers()
        if item not in offered:
            raise _refuse(f"'{reference}' names '{item}', which is not an instance of "
                          f"'{self.name}'", subject=subject)  # fmt: skip
        if name not in offered[item]:
            raise _refuse(f"'{item}' offers no interface '{name}' "
                          f"({', '.join(offered[item]) or 'it offers none'})",
                          subject=subject)  # fmt: skip
        return item, offered[item][name]

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
        needs = self.screening.needs if self.screening is not None else None
        for item in needs.items if needs is not None else ():
            if item not in names:
                raise _refuse(f"material needs name '{item}', which is not an instance "
                              f"({', '.join(names)})", subject="screening.needs")  # fmt: skip
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
        connected: set[str] = set()
        for connection in self.connections:
            _on_item, first = self.interface_at(connection.on, "connections[].on")
            _place_item, second = self.interface_at(connection.place, "connections[].place")
            pair = (first.kind, second.kind)
            if pair not in COMPATIBLE and pair[::-1] not in COMPATIBLE:
                raise _refuse(f"{connection.on} is a {first.kind} and {connection.place} a "
                              f"{second.kind}, which do not meet; a {first.kind} meets "
                              f"{' or '.join(partners_of(first.kind))}",
                              subject="connections[].place")  # fmt: skip
            joint = connection.joint
            if joint is not None and joint.kind != "rigid":
                kinds = (first.kind, second.kind)
                if any(KINDS[k][0] != "axis" for k in kinds):
                    raise _refuse(f"connection {connection.on} ~ {connection.place} declares a "
                                  f"{joint.kind} joint, and its interfaces ({kinds[0]}, "
                                  f"{kinds[1]}) define no axis to move about",
                                  subject="connections[].joint")  # fmt: skip
                patterned = {i.name for i in self.instances if i.pattern is not None}
                if _place_item in patterned:
                    raise _refuse(f"connection {connection.on} ~ {connection.place} declares a "
                                  f"{joint.kind} joint on a pattern, whose members each move "
                                  "about their own axis; give the moving item one instance",
                                  subject="connections[].joint")  # fmt: skip
            if _place_item == self.ground:
                raise _refuse(f"connection {connection.on} ~ {connection.place} places the ground "
                              f"'{self.ground}', which stays where it is; put it on the on side",
                              subject="connections[].place")  # fmt: skip
            connected |= {connection.on, connection.place}
        for left_open in self.open_interfaces:
            self.interface_at(left_open.at, "open_interfaces[].at")
            if left_open.at in connected:
                raise _refuse(f"{left_open.at} is declared open and is connected",
                              subject="open_interfaces[].at")  # fmt: skip
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


def load_product(path: Any) -> tuple[Product, dict[str, Product]]:
    """The product document at ``path`` and the library of every product it places.

    A definition's ``product`` is a name the library holds, a sub-product embedded whole,
    or ``{file: <path>}`` relative to the document that names it, read the same way at any
    depth. A file that is missing or will not read is refused naming the path and the
    definition that references it; a chain of files that comes back to itself is refused
    naming the chain. Two different sub-products under one name are refused.
    """
    from pathlib import Path

    from ._models import parse_yaml

    if not isinstance(path, (str, Path)):
        raise _refuse(f"path is a {type(path).__name__}; give a file path", subject="path")
    library: dict[str, Product] = {}

    def read(file: Path, referrer: str, chain: tuple[Path, ...]) -> Product:
        file = file.resolve()
        if file in chain:
            names = " → ".join(str(p) for p in (*chain, file))
            raise _refuse(f"the product files contain themselves: {names}", subject="path")
        try:
            document = parse_yaml(file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as failure:
            raise _refuse(f"{referrer} references {file}, which cannot be read: {failure}",
                          subject="path") from failure  # fmt: skip
        if not isinstance(document, Mapping):
            raise _refuse(f"{referrer} references {file}, which is not a product document",
                          subject="path")  # fmt: skip
        return gather(document, file.parent, (*chain, file))

    def keep(sub: Product) -> str:
        held = library.get(sub.name)
        if held is not None and held != sub:
            raise _refuse(f"two different sub-products are named '{sub.name}'; a library "
                          "holds one product per name", subject="path")  # fmt: skip
        library[sub.name] = sub
        return sub.name

    def gather(document: Mapping[str, Any], folder: Path, chain: tuple[Path, ...]) -> Product:
        definitions = []
        for definition in document.get("definitions") or ():
            target = definition.get("product") if isinstance(definition, Mapping) else None
            if isinstance(target, Mapping):
                where = f"definition '{definition.get('id')}' in {chain[-1]}"
                if set(target) == {"file"} and isinstance(target["file"], str):
                    sub = read(folder / target["file"], where, chain)
                else:
                    sub = gather(target, folder, chain)
                definition = {**definition, "product": keep(sub)}
            definitions.append(definition)
        return parse_product({**document, "definitions": definitions})

    top = Path(path)
    return read(top, "the call", ()), library


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
    kind: Literal["part", "product", "placeholder", "component", "reference"]
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
    elif definition.reference is not None:
        payload = {"reference": definition.reference.model_dump(mode="json")}
    elif definition.component is not None:
        payload = {
            "component": definition.component.model_dump(mode="json"),
            "demands": [d.model_dump(mode="json") for d in definition.demands],
        }
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
    kind: Literal["part", "product", "placeholder", "component", "reference"]
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
    kind: Literal["part", "product", "placeholder", "component", "reference"]
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


class InterfaceRow(StatableModel):
    """One row of the interface control table: a connection, or an interface left open.

    ``node`` is the product that declares it; ``on`` and ``place`` are ``item.interface``
    within it. Each side has its kind, the values its kind states, and its owner (the item's
    make, buy or reference, and part number or description). ``checks`` are the
    connection's entries as ``name: status``. An open row has ``reason`` and no ``place``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    node: str = ""
    on: Named
    on_kind: Named
    on_values: str
    on_owner: Named
    place: str | None = None
    place_kind: str | None = None
    place_values: str | None = None
    place_owner: str | None = None
    checks: tuple[str, ...] = ()
    reason: str | None = None


_TABLE_COLUMNS = ("product", "on", "on kind", "on values", "on owner", "place", "place kind",
                  "place values", "place owner", "checks", "open reason")  # fmt: skip


class InterfaceTable(ItemCollection, StatableModel):
    """The interface control table: every connection and every open interface, by product."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[InterfaceRow, ...]

    def to_csv(self) -> str:
        """The table as CSV, a header then one line per row; no cell reads as a formula."""
        import csv
        import io

        from .margin_of_safety import _csv_safe

        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(_TABLE_COLUMNS)
        for row in self.rows:
            cells = (row.node, row.on, row.on_kind, row.on_values, row.on_owner,
                     row.place or "", row.place_kind or "", row.place_values or "",
                     row.place_owner or "", "; ".join(row.checks), row.reason or "")  # fmt: skip
            writer.writerow(
                [_csv_safe(c, cell) for c, cell in zip(_TABLE_COLUMNS, cells, strict=True)]
            )
        return out.getvalue()

    def section(self) -> str:
        """The table as a Markdown report section: connections, then open interfaces."""

        def cell(text: str) -> str:
            return text.replace("|", "\\|")

        header = "| Product | On | Kind | Values | Owner | Place | Kind | Values | Owner | Checks |"
        lines = ["## Interface control table", "", header, "|" + " --- |" * 10]
        for row in self.rows:
            if row.place is not None:
                lines.append(" | ".join([
                    f"| {cell(row.node)}", cell(row.on), row.on_kind, cell(row.on_values),
                    cell(row.on_owner), cell(row.place), row.place_kind or "",
                    cell(row.place_values or ""), cell(row.place_owner or ""),
                    cell("; ".join(row.checks) or "—"),
                ]) + " |")  # fmt: skip
        opened = [row for row in self.rows if row.place is None]
        if opened:
            lines += ["", "Left open:", ""]
            lines += [f"- {row.node} {row.on} ({row.on_kind}): {row.reason}" for row in opened]
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
    interfaces: InterfaceTable = Field(default_factory=lambda: InterfaceTable(rows=()))
    joints: tuple[PlacedJoint, ...] = ()
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
        kind: str = "",
        parts: tuple[tuple[str, Any], ...] = (),
    ) -> None:
        self.path, self.shape, self.placeholder, self.mass = path, shape, placeholder, mass
        # The centre of mass as a vertex, moved with the shape; ``assumed`` when it is a
        # placeholder's envelope centre rather than a declared centre of mass.
        self.com, self.assumed, self.entries = com, assumed, entries
        # For export: the definition's content key, its shape as built, and every move
        # applied to it since, so a repeated item is one STEP product placed many times.
        self.key, self.built, self.where = key, built if built is not None else shape, where
        self.kind = kind or ("placeholder" if placeholder else "part")
        # A reference's solids, each at its path in the file, moved with the leaf.
        self.parts = parts

    def moved(self, path: str, where: Any) -> _Leaf:
        return _Leaf(path, self.shape.moved(where), self.placeholder, self.mass,
                     self.com.moved(where), self.assumed, self.entries, self.key, self.built,
                     where if self.where is None else where * self.where, self.kind,
                     tuple((name, part.moved(where)) for name, part in self.parts))  # fmt: skip


class _Assembly:
    """A placed (sub-)product: a shape and features for ``_place``, and its leaves."""

    def __init__(
        self,
        shape: Any,
        leaves: list[_Leaf],
        extra: dict[str, tuple[ScorecardEntry, ...]],
        tables: dict[str, tuple[InterfaceRow, ...]],
        joints: dict[str, tuple[PlacedJoint, ...]],
    ) -> None:
        self.shape, self.leaves, self.features = shape, leaves, ()
        self.joints = joints
        # The entries each product node owns beyond its interference: its connections'; and
        # the interface-table rows for them, by the same node path.
        self.extra, self.tables = extra, tables


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
    product: Product,
    library: Mapping[str, Product] | None,
    cache: BuildCache | None,
    root: Any = None,
) -> tuple[
    list[_Leaf],
    int,
    int,
    dict[str, tuple[ScorecardEntry, ...]],
    dict[str, tuple[InterfaceRow, ...]],
    dict[str, tuple[PlacedJoint, ...]],
]:
    """Every leaf body placed where its mates put it, the items rebuilt and reused, and the
    connection entries each product node owns."""
    from .combination import _IDENTITY, PlacedPart, _place

    if cache is not None and not isinstance(cache, BuildCache):
        raise _refuse(f"cache is a {type(cache).__name__}; pass a BuildCache or none",
                      subject="cache")  # fmt: skip
    store = cache._store if cache is not None else {}
    from pathlib import Path

    folder = Path(root) if root is not None else None
    rebuilt: set[str] = set()
    reused: set[str] = set()

    shelf = dict(library or {})
    product_tree(product, library=shelf)  # the identity and containment refusals first

    def assemble(current: Product, prefix: str) -> _Assembly:
        from build123d import CenterOf, Compound, Vertex

        from .combination import _mass
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
            if definition.reference is not None:
                return _reference_built(definition.reference, folder, path)
            if definition.component is not None:
                from .components import _rating_entries

                record = definition.component
                built = _boxed(record.envelope, record.holes, "component")
                return built, None, _Leaf(path, built.shape, False,
                                          float(record.mass.to("kg").magnitude), Vertex(0, 0, 0),
                                          True,
                                          _rating_entries(record, definition.demands, folder),
                                          kind="component")  # fmt: skip
            holder = definition.placeholder
            if holder is None:  # a placeholder definition holds one, by its validator
                raise _refuse(f"'{path}' has no placeholder", subject="definitions[]")
            built = _boxed(holder.envelope, holder.holes, "placeholder")
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
        extra: dict[str, tuple[ScorecardEntry, ...]] = {}
        tables: dict[str, tuple[InterfaceRow, ...]] = {}
        joints: dict[str, tuple[PlacedJoint, ...]] = {}
        # Each placed instance's interfaces, as its built geometry states them, and the mate
        # each connection was placed by, in the order the connections are declared.
        resolved: dict[str, dict[str, Interface]] = {}
        derived: dict[int, Mate] = {}
        ground_first = sorted(current.instances, key=lambda i: i.name != current.ground)
        for instance in ground_first:
            definition = definitions[instance.item]
            path = f"{prefix}/{instance.name}"
            spec = None
            below: dict[str, tuple[ScorecardEntry, ...]] = {}
            below_rows: dict[str, tuple[InterfaceRow, ...]] = {}
            below_joints: dict[str, tuple[PlacedJoint, ...]] = {}
            if definition.kind in ("part", "placeholder", "component", "reference"):
                key = _content(definition, shelf)
                if definition.reference is not None and folder is not None:
                    # The reference is read from its file: the file's state is in the key.
                    held_file = folder / definition.reference.file
                    key += ":" + (hashlib.sha256(held_file.read_bytes()).hexdigest()
                                  if held_file.is_file() else "missing")  # fmt: skip
                model = definition.component.model if definition.component is not None else None
                if model is not None and folder is not None:
                    # The vendor file is read on every build: its state is part of the key.
                    vendor = folder / model.file
                    key += ":" + (hashlib.sha256(vendor.read_bytes()).hexdigest()
                                  if vendor.is_file() else "missing")  # fmt: skip
                if key not in store:
                    store[key] = make(definition, path)
                    rebuilt.add(key)
                elif key not in rebuilt:
                    reused.add(key)
                built, spec, leaf = store[key]
                inner = [_Leaf(path, leaf.shape, leaf.placeholder, leaf.mass, leaf.com,
                               leaf.assumed, leaf.entries, key, kind=leaf.kind,
                               parts=leaf.parts)]  # fmt: skip
            else:
                sub = shelf[definition.product or ""]
                built = assemble(sub, path)
                inner = built.leaves
                below, below_rows, below_joints = built.extra, built.tables, built.joints
            resolved[instance.name] = _resolved_offers(definition, built, path)
            if instance.name == current.ground:
                rotation, translation = _IDENTITY, (0.0, 0.0, 0.0)
            else:
                mates = [m for m in current.mates if m.place.part == instance.name]
                for index, connection in enumerate(current.connections):
                    on_item, _on = _split(connection.on, "connections[].on")
                    if _split(connection.place, "connections[].place")[0] != instance.name:
                        continue
                    if on_item not in resolved:
                        raise _refuse(f"connection {connection.on} ~ {connection.place} places "
                                      f"'{instance.name}' on '{on_item}', which is not placed "
                                      "yet; list it first", subject="instances")  # fmt: skip
                    derived[index] = _connection_mate(connection, resolved)
                    mates.append(derived[index])
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
                extra.update({label + key[len(path) :]: held for key, held in below.items()})
                tables.update({label + key[len(path) :]: rows for key, rows in below_rows.items()})
                joints.update({label + key[len(path) :]: tuple(_moved_joint(j, r, t) for j in held)
                               for key, held in below_joints.items()})  # fmt: skip
        in_order = [derived[i] for i in range(len(current.connections))]
        joints[prefix], sweeps = _joints(current, placed, resolved, leaves, prefix)
        gaps = _clearances(current, leaves, prefix)
        extra[prefix] = (*_connection_entries(current, in_order, placed, resolved), *sweeps, *gaps)
        tables[prefix] = _interface_rows(current, extra[prefix], resolved)
        shape = Compound([leaf.shape for leaf in leaves])
        return _Assembly(shape, leaves, extra, tables, joints)

    top = assemble(product, product.name)
    return top.leaves, len(rebuilt), len(reused), top.extra, top.tables, top.joints


def place_product(
    product: Product,
    *,
    library: Mapping[str, Product] | None = None,
    cache: BuildCache | None = None,
    root: Any = None,
) -> PlacedProduct:
    """Place every instance through its mates, then check interference and roll up mass.

    The ground stays at the origin. Every other instance — a pattern's first member, named
    by the instance's name — must be placed by at least one mate onto an instance listed
    before it; the rest of a pattern follows its first member. A mate that leaves an
    instance free or contradicts another is refused by the combination's own rules.

    With a ``cache``, an item built before from the same content is reused; the placed
    product's ``rebuilt`` and ``reused`` count the distinct items each way. ``root`` is the
    folder a purchased component's vendor model is read from, by its relative path.
    """
    from .combination import _interference

    leaves, rebuilt, reused, extra, tables, joints = _placed_leaves(product, library, cache, root)
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
        mass_unknown=tuple(
            leaf.path for leaf in leaves if leaf.mass is None and leaf.kind != "reference"
        ),
        center_of_mass_mm=centre,
        center_assumed=tuple(leaf.path for leaf in leaves if leaf.assumed),
        unused_parameters=product.layout.unused if product.layout is not None else (),
        card=_card(product.name, leaves, extra),
        joints=tuple(
            joint.model_copy(update={"node": node})
            for node, held in joints.items()
            for joint in held
        ),
        interfaces=InterfaceTable(
            rows=tuple(
                row.model_copy(update={"node": node})
                for node, rows in tables.items()
                for row in rows
            )
        ),  # fmt: skip
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


_PATTERNS = ("bolt_pattern", "tapped_pattern")
_MALE = ("shaft", "pin", "keyed_shaft")
_AGREE_MM = 0.01
_NEEDS_A_CONNECTION = Need(
    declaration="connections",
    takes="a connection for each interface an item offers, or open_interfaces with the reason",
    sources=(ValueSource.USER,),
)
_COMPARED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="the two interfaces' declared values compared as stated",
)


def _resolved_offers(definition: Definition, built: Any, path: str) -> dict[str, Interface]:
    """An instance's interfaces as built: stated by a placeholder or component, or a catalog
    part's bindings read from its built features."""
    held = definition.placeholder or definition.component
    if held is not None:
        return {i.name: i for i in held.interfaces}
    if not definition.interfaces:
        return {}
    from .interfaces import InterfaceError

    features = {feature.tag: feature for feature in getattr(built, "features", ())}
    try:
        return {i.name: i.resolve(features, f"'{path}'") for i in definition.interfaces}
    except InterfaceError as refused:  # the CLI and the build tool answer a ProductError
        raise _refuse(str(refused), subject="definitions[].interfaces") from refused


def _resolved_at(
    resolved: Mapping[str, Mapping[str, Interface]], reference: str
) -> tuple[str, Interface]:
    item, name = _split(reference, "connections")
    return item, resolved[item][name]


def _interface_rows(
    current: Product,
    entries: tuple[ScorecardEntry, ...],
    resolved: Mapping[str, Mapping[str, Interface]],
) -> tuple[InterfaceRow, ...]:
    """One row per connection, with its checks as named on the card, then one per open one."""
    definitions = {d.id: d for d in current.definitions}
    owners = {}
    for instance in current.instances:
        identity = definitions[instance.item].identity
        owners[instance.name] = (f"{identity.source.value}, "
                                 f"{identity.part_number or identity.description}")  # fmt: skip

    def values(interface: Interface) -> str:
        stated = [f"{name} {value}" for name, value in interface.parameters.items()]
        if interface.holes:
            stated.insert(0, f"{len(interface.holes)} holes on {interface.face}")
        return ", ".join(stated) or (interface.face or interface.axis or "")

    rows = []
    for connection in current.connections:
        on_item, on = _resolved_at(resolved, connection.on)
        place_item, place = _resolved_at(resolved, connection.place)
        pair = f"{connection.on} ~ {connection.place} "
        checks = tuple(f"{e.name[len(pair):]}: {e.status.value}" for e in entries
                       if e.name.startswith(pair))  # fmt: skip
        rows.append(InterfaceRow(
            on=connection.on, on_kind=on.kind, on_values=values(on), on_owner=owners[on_item],
            place=connection.place, place_kind=place.kind, place_values=values(place),
            place_owner=owners[place_item], checks=checks,
        ))  # fmt: skip
    for left in current.open_interfaces:
        item, interface = _resolved_at(resolved, left.at)
        rows.append(InterfaceRow(on=left.at, on_kind=interface.kind, on_values=values(interface),
                                 on_owner=owners[item], reason=left.reason))  # fmt: skip
    return tuple(rows)


_READ_FROM_FILE = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="the existing assembly as its file states it, read rather than computed",
)
_NEEDS_A_CLEARANCE = Need(
    declaration="definitions[].reference.clearance",
    takes="the least gap the product's own items must keep to the existing assembly",
    dimension="[length]",
    units=("mm", "in"),
    sources=(ValueSource.USER, ValueSource.STANDARD),
)


def _reference_built(reference: Reference, folder: Any, path: str) -> tuple[Any, Any, _Leaf]:
    """An existing assembly read from its STEP file: one body of all its solids, placed."""
    from build123d import Compound, Vertex

    from .context import ContextError, _assembly_solids
    from .geometry import BuiltGeometry

    if folder is None:
        raise _refuse(
            f"'{path}' is a reference read from {reference.file}, and no folder was given to "
            "read it from; place the product with root", subject="root",
        )  # fmt: skip
    try:
        solids, duplicates = _assembly_solids(folder / reference.file)
    except ContextError as refused:
        raise _refuse(f"'{path}' cannot read {reference.file}: {refused}",
                      subject="definitions[].reference.file") from refused  # fmt: skip
    if not solids:
        raise _refuse(f"'{path}': {reference.file} holds no solid",
                      subject="definitions[].reference.file")  # fmt: skip
    shape = Compound([shape for _p, _n, shape in solids])
    built = BuiltGeometry(name="reference", pattern="reference", shape=shape, faces={},
                          dimensions_mm={}, features=())  # fmt: skip
    note = f"; its file repeats names: {'; '.join(duplicates)}" if duplicates else ""
    entry = ScorecardEntry(
        name="reference",
        status=CheckStatus.PASS,
        detail=f"the existing assembly in {reference.file}, {len(solids)} solid"
        f"{'s' if len(solids) != 1 else ''}, read to check against and not itself made{note}",
        underived=_READ_FROM_FILE,
    )
    return built, None, _Leaf(path, shape, False, None, Vertex(0, 0, 0), False, (entry,),
                              kind="reference",
                              parts=tuple((name, part) for name, _n, part in solids))  # fmt: skip


def _clearances(current: Product, leaves: list[_Leaf], prefix: str) -> tuple[ScorecardEntry, ...]:
    """For each reference placed here, the nearest approach of every other item to its solids."""
    definitions = {d.id: d for d in current.definitions}
    entries = []
    for instance in current.instances:
        reference = definitions[instance.item].reference
        if reference is None:
            continue
        base = f"{prefix}/{instance.name}"
        mine = [leaf for leaf in leaves if leaf.path == base or leaf.path.startswith(base + "[")]
        others = [leaf for leaf in leaves if leaf.kind != "reference"]
        nearest: tuple[float, str, str] | None = None
        for held in mine:
            for name, part in held.parts:
                for other in others:
                    gap = float(part.distance_to(other.shape))
                    if nearest is None or gap < nearest[0]:
                        nearest = (gap, f"{held.path}/{name}", other.path)
        if nearest is None:
            continue
        said = f"{nearest[2]} comes within {nearest[0]:.4g} mm of {nearest[1]}"
        if reference.clearance is None:
            entries.append(ScorecardEntry(
                name=f"{instance.name} clearance", status=CheckStatus.NOT_EVALUATED,
                detail=f"{said}; no least clearance is declared to judge it by",
                needs=(_NEEDS_A_CLEARANCE,),
            ))  # fmt: skip
            continue
        least = reference.clearance.to("mm").magnitude
        entries.append(ScorecardEntry(
            name=f"{instance.name} clearance",
            status=CheckStatus.PASS if nearest[0] >= least else CheckStatus.FAIL,
            detail=f"{said}, against the {least:g} mm it must keep", underived=_SWEPT,
        ))  # fmt: skip
    return tuple(entries)


_SWEEP_STEP_DEG = 15.0
_SWEEP_STEPS_LINEAR = 10


def _moved_joint(joint: PlacedJoint, rotation: Any, translation: Any) -> PlacedJoint:
    """A sub-product's joint, carried into the frame its placement puts it in."""
    from .combination import _add, _apply, _tidy

    point = _tidy(_add(_apply(rotation, joint.point_mm), translation))
    direction = _tidy(_apply(rotation, joint.direction))
    return joint.model_copy(update={"point_mm": point, "direction": direction})


def _joints(
    current: Product,
    placed: Mapping[str, Any],
    resolved: Mapping[str, Mapping[str, Interface]],
    leaves: list[_Leaf],
    prefix: str,
) -> tuple[tuple[PlacedJoint, ...], tuple[ScorecardEntry, ...]]:
    """Each declared joint's axis as placed, and the sweep of its moving item through its range.

    The axis is the ``on`` interface's: through its bound feature on a catalog part, or
    the item's own axis through its origin. The moving item (the ``place`` side) is turned
    or slid through the range in steps of at most 15 degrees, or ten steps of travel, and
    must clear every other body at each.
    """
    from build123d import Axis, Location

    from .combination import _AXES, _tidy, _unit

    placed_joints: list[PlacedJoint] = []
    entries: list[ScorecardEntry] = []
    for connection in current.connections:
        joint = connection.joint
        if joint is None:
            continue
        on_item, on = _resolved_at(resolved, connection.on)
        place_item, _place = _resolved_at(resolved, connection.place)
        fixed = placed[on_item]
        local_point: Any = (0.0, 0.0, 0.0)
        local_direction: Any = _AXES[on.axis] if on.axis is not None else (0.0, 0.0, 1.0)
        if on.feature is not None:
            feature = next(f for f in fixed.built.features if f.tag == on.feature)
            local_point, local_direction = tuple(feature.position_mm), tuple(feature.axis)
        point = _tidy(fixed.point(local_point))
        direction = _tidy(_unit(fixed.direction(local_direction)))
        pair = f"{connection.on} ~ {connection.place}"
        unit = "degree" if joint.kind in _ANGULAR else "mm"
        low = high = None
        if joint.range is not None:
            low, high = (float(q.to(unit).magnitude) for q in joint.range)
        placed_joints.append(PlacedJoint(
            connection=pair, kind=joint.kind, point_mm=point, direction=direction,
            range_low=low, range_high=high, range_unit=None if low is None else unit,
        ))  # fmt: skip
        if low is None or high is None:
            continue
        base = f"{prefix}/{place_item}"
        moving = [leaf for leaf in leaves if leaf.path == base or leaf.path.startswith(base + "/")]
        others = [leaf for leaf in leaves if leaf not in moving]
        angular = unit == "degree"
        steps = (max(2, math.ceil((high - low) / _SWEEP_STEP_DEG) + 1) if angular
                 else _SWEEP_STEPS_LINEAR + 1)  # fmt: skip
        samples = [low + (high - low) * i / (steps - 1) for i in range(steps)]
        axis = Axis(point, direction)
        clash: tuple[float, str, str, float] | None = None
        for value in samples:
            for leaf in moving:
                if angular:
                    shape = leaf.shape.rotate(axis, value)
                else:
                    shape = leaf.shape.moved(Location(tuple(d * value for d in direction)))
                for other in others:
                    common = shape & other.shape
                    volume = float(common.volume) if common is not None else 0.0
                    if volume > 1e-6 and (clash is None or volume > clash[3]):
                        clash = (value, leaf.path, other.path, volume)
        word = "degrees" if angular else "mm"
        swept = f"{joint.kind} joint swept from {low:g} to {high:g} {word} in {steps} steps"
        detail = (f"{swept}: the moving item clears every other body" if clash is None else
                  f"{swept}: at {clash[0]:g} {word} {clash[1]} meets {clash[2]} by "
                  f"{clash[3]:.4g} mm^3")  # fmt: skip
        entries.append(ScorecardEntry(
            name=f"{pair} joint sweep", detail=detail, underived=_SWEPT,
            status=CheckStatus.PASS if clash is None else CheckStatus.FAIL,
        ))  # fmt: skip
    return tuple(placed_joints), tuple(entries)


_SWEPT = Underived(
    kind=DerivationAbsence.NUMERIC_RESULT,
    reason="the moving item's solids are intersected with the others at each step of the range",
)


def _connection_mate(
    connection: Connection, resolved: Mapping[str, Mapping[str, Interface]]
) -> Mate:
    """The mate a connection stands for: pattern to pattern, face to face, or on an axis."""
    on_item, on = _resolved_at(resolved, connection.on)
    place_item, place = _resolved_at(resolved, connection.place)
    ends: dict[str, Any] = {}
    if KINDS[on.kind][0] == "face":
        kind = "hole_pattern" if on.kind in _PATTERNS else "face_to_face"
        ends = {"place": {"part": place_item, "face": place.face, "holes": place.holes},
                "on": {"part": on_item, "face": on.face, "holes": on.holes}}  # fmt: skip
    else:
        kind = "shaft_in_bore"
        ends = {
            side: {"part": item, "feature": offer.feature}
            if offer.feature is not None
            else {"part": item, "axis": offer.axis}
            for side, item, offer in (("place", place_item, place), ("on", on_item, on))
        }
    return Mate.model_validate({"id": f"{connection.on}~{connection.place}",
                                "kind": kind, **ends})  # fmt: skip


def _connection_entries(
    current: Product,
    derived: list[Mate],
    placed: Mapping[str, Any],
    resolved: Mapping[str, Mapping[str, Interface]],
) -> tuple[ScorecardEntry, ...]:
    """Each connection's checks, then every interface accounted for and its partners counted."""
    from collections import Counter

    from .combination import _pattern_entry

    entries: list[ScorecardEntry] = []
    for connection, mate in zip(current.connections, derived, strict=True):
        on_item, on = _resolved_at(resolved, connection.on)
        place_item, place = _resolved_at(resolved, connection.place)
        pair = f"{connection.on} ~ {connection.place}"
        _agree, checks = COMPATIBLE.get((on.kind, place.kind)) or COMPATIBLE[(place.kind, on.kind)]
        for check in checks:
            if check == "hole pattern":
                entry = _pattern_entry(mate, placed[place_item], placed[on_item], None)
                entries.append(entry.model_copy(update={"name": f"{pair} hole pattern"}))
                continue
            a, b = (
                on.parameters[check].to("mm").magnitude,
                place.parameters[check].to("mm").magnitude,
            )
            if check == "diameter":
                male, female = (a, b) if on.kind in _MALE else (b, a)
                ok = male <= female + 1e-9
                fit = (f"{female - male:.4g} mm clearance" if ok
                       else f"the {male:g} mm side is {male - female:.4g} mm over")  # fmt: skip
                detail = f"{male:g} mm in {female:g} mm: {fit}"
            else:
                ok = abs(a - b) <= _AGREE_MM
                detail = (f"{connection.on} {a:g} mm and {connection.place} {b:g} mm"
                          + ("" if ok else f", {abs(a - b):.4g} mm apart"))  # fmt: skip
            entries.append(ScorecardEntry(name=f"{pair} {check.replace('_', ' ')}",
                                          status=CheckStatus.PASS if ok else CheckStatus.FAIL,
                                          detail=detail, underived=_COMPARED))  # fmt: skip
    partners: Counter[str] = Counter()
    for connection in current.connections:
        partners.update((connection.on, connection.place))
    opened = {declared.at for declared in current.open_interfaces}
    offered = resolved
    loose = [f"{item}.{name}" for item, held in offered.items() for name in held
             if f"{item}.{name}" not in partners and f"{item}.{name}" not in opened]  # fmt: skip
    if loose:
        entries.append(ScorecardEntry(
            name="unconnected interfaces", status=CheckStatus.NOT_EVALUATED,
            detail=f"{', '.join(loose)} {'is' if len(loose) == 1 else 'are'} neither connected "
            "nor declared open with a reason", needs=(_NEEDS_A_CONNECTION,),
        ))  # fmt: skip
    for reference, count in partners.items():
        item, name = _split(reference, "connections")
        allowed = KINDS[offered[item][name].kind][2]
        if allowed is not None and count > allowed:
            others = [c.place if c.on == reference else c.on for c in current.connections
                      if reference in (c.on, c.place)]  # fmt: skip
            entries.append(ScorecardEntry(
                name=f"{reference} partners", status=CheckStatus.FAIL, underived=_COMPARED,
                detail=f"{reference} is a {offered[item][name].kind}, which takes {allowed} "
                f"partner, and meets {', '.join(others)}",
            ))  # fmt: skip
    return tuple(entries)


def _card(
    path: str, leaves: list[_Leaf], extra: Mapping[str, tuple[ScorecardEntry, ...]]
) -> NodeCard:
    """The card of the node at ``path``, from the leaves under it, each child in order."""
    from build123d import Compound

    from .combination import _interference

    if len(leaves) == 1 and leaves[0].path == path:
        leaf = leaves[0]
        return NodeCard(path=path, kind=leaf.kind, entries=leaf.entries)  # type: ignore[arg-type]
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
        entries=(interference, *extra.get(path, ())),
        children=tuple(_card(child, group, extra) for child, group in groups.items()),
    )


def write_product_step(
    product: Product,
    path: Any,
    *,
    authorization: Any,
    library: Mapping[str, Product] | None = None,
    cache: BuildCache | None = None,
    root: Any = None,
) -> Any:
    """Write the placed product as one STEP AP242 assembly, each item one named product.

    Every occurrence of an item is a component placed where its mates put it, so a drive
    used twice is one product placed twice. Each product is named by its part number and
    description, provisional numbers included. ``authorization`` is the export gate's
    verdict on the product's card (:meth:`NodeCard.flattened`); a product resting on
    placeholders is not evaluated, so it is written only watermarked unvalidated. A
    reference item is never written: it is what the product is checked against. ``root`` is
    the folder the product's files (a reference, a vendor model) are read from.
    """
    from build123d import Location

    from .combination import _write_assembly

    tree = product_tree(product, library=library)
    nodes = {node.path: node for node in tree.walk()}
    leaves, _rebuilt, _reused, _extra, _tables, _joints = _placed_leaves(
        product, library, cache, root
    )
    bodies = []
    for leaf in leaves:
        if leaf.kind == "reference":
            continue  # an existing assembly the product is checked against, never made
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


def _boxed(envelope: Any, holes: Any, pattern: str) -> Any:
    """An envelope box centred on its own origin, carrying its holes as features."""
    from build123d import Box

    from .features import Feature
    from .geometry import BuiltGeometry

    x, y, z = (q.to("mm").magnitude for q in envelope)
    features = tuple(
        Feature(
            tag=h.tag, kind="blind_hole", diameter_mm=h.diameter.to("mm").magnitude,
            depth_mm=0.0,
            position_mm=(h.x.to("mm").magnitude, h.y.to("mm").magnitude, h.z.to("mm").magnitude),
            axis=_OUTWARD[h.face],
        )
        for h in holes
    )  # fmt: skip
    return BuiltGeometry(name=pattern, pattern=pattern, shape=Box(x, y, z), faces={},
                         dimensions_mm={}, features=features)  # fmt: skip


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
