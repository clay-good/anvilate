"""Part combinations: catalog parts placed by the features they share, and checked where they meet.

A single part is rarely the question. A bracket goes on a plate, a flange meets a flange, a
collar sits on a shaft. A combination is a short document that names its parts, each with
its own Design Spec, and says how each one meets a part already placed: this face on that
face, these holes on those holes, this shaft in that bore. No coordinate is written. The
positions are computed from the mates, and a mate that leaves a part free to slide, or that
contradicts another, is refused naming the mates involved.

**Where parts meet is where designs fail, so the meeting is checked.** Hole patterns that
are mated are held to each other hole by hole. A bolt is checked against the holes it passes
through and against the stack it has to clamp. Every pair of bodies is intersected, and an
overlap is reported with its volume. Each result is a scorecard entry, beside one entry per
part carrying that part's own verdict.

**Hardware is an envelope.** A bolt, washer or nut is drawn from its tabulated dimensions as
a cylinder or a hexagon, to show where it goes and what it needs around it. It is labelled
an envelope, carries no thread, and is never offered as the fastener's geometry.

This is not an assembly modeller. There are four mates, the parts are the catalog's, and the
result is a picture, a parts list and a STEP assembly to carry into CAD.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from ._models import FrozenMap, Named, Provenance, StatableModel
from .derivation import DerivationAbsence, Underived
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .units import Quantity

__all__ = [
    "COMBINATION_VERSION",
    "BomLine",
    "BuiltCombination",
    "Combination",
    "CombinationSummary",
    "CombinationError",
    "CombinationPart",
    "HardwareBody",
    "HardwareStack",
    "Mate",
    "MateEnd",
    "Weld",
    "PlacedPart",
    "PlacedSummary",
    "build_combination",
    "parse_combination",
    "render_combination",
    "write_step_assembly",
]

COMBINATION_VERSION = "1.0.0"

#: How far apart two mated holes may be when the document declares no tolerance and no
#: fastener says how much room there is: a micrometre, which is to say they must agree.
EXACT_MM = 1e-3

_FACES = {
    "top": (0.0, 0.0, 1.0),
    "bottom": (0.0, 0.0, -1.0),
    "right": (1.0, 0.0, 0.0),
    "left": (-1.0, 0.0, 0.0),
    "back": (0.0, 1.0, 0.0),
    "front": (0.0, -1.0, 0.0),
}
_AXES = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
_IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

Vec = tuple[float, float, float]
Matrix = tuple[Vec, Vec, Vec]

_MEASURED = Underived(
    kind=DerivationAbsence.NUMERIC_RESULT,
    reason="the result is measured on the placed solids, not computed from a formula",
)
_DOCUMENT = "the combination document: its parts, and the mates that place each one"


class CombinationError(RefusalError, ValueError):
    """A combination that cannot be placed or built as written, with what would fix it."""


def _refuse(message: str, *, subject: str, action: str = "correct") -> CombinationError:
    return CombinationError(
        message, remedies=(Remedy(action=action, subject=subject, source=_DOCUMENT),)
    )


class CombinationPart(StatableModel):
    """One part of a combination: a name for it here, and its own Design Spec."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    spec: FrozenMap[str, Any]


class MateEnd(StatableModel):
    """One side of a mate: a part, and the feature on it that meets the other part.

    ``face`` is one of the part's six outermost faces by direction: ``top``, ``bottom``,
    ``left``, ``right``, ``front`` or ``back``. ``holes`` are hole tags, as the part's
    features carry them, in the order they pair with the other side's. ``axis`` is one of
    the part's own axes (``x``, ``y`` or ``z``) through its origin, which is the axis of a
    round part; ``feature`` names a hole or bore instead, by its tag.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    part: Named
    face: Literal["top", "bottom", "left", "right", "front", "back"] | None = None
    holes: tuple[Named, ...] = ()
    axis: Literal["x", "y", "z"] | None = None
    feature: Named | None = None


class Mate(StatableModel):
    """How one part meets a part already placed.

    ``place`` is the part being placed and ``on`` a part that already is. ``face_to_face``
    puts two faces in contact. ``edge_flush`` lines two faces up in one plane. ``hole_pattern``
    puts ``place.face`` on ``on.face`` with the listed holes coaxial, pair by pair.
    ``shaft_in_bore`` makes two axes one. ``offset`` opens a gap between mated faces, and
    ``rotation_deg`` turns the part about a shared axis that nothing else fixes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    kind: Literal["face_to_face", "edge_flush", "hole_pattern", "shaft_in_bore"]
    place: MateEnd
    on: MateEnd
    offset: Quantity | None = None
    rotation_deg: float | None = None
    # How far apart two mated holes may be and still count as agreeing. When no tolerance
    # is declared, a fastener in the holes sets it from the room it has, and otherwise the
    # holes are held to a micrometre.
    position_tolerance: Quantity | None = None

    @model_validator(mode="after")
    def _the_kind_names_its_features(self) -> Mate:
        for side, end in (("place", self.place), ("on", self.on)):
            if self.kind in ("face_to_face", "edge_flush", "hole_pattern") and end.face is None:
                raise _refuse(
                    f"mate '{self.id}' is {self.kind} and its {side} names no face",
                    subject=f"mates[].{side}.face",
                )
            if self.kind == "hole_pattern" and not end.holes:
                raise _refuse(
                    f"mate '{self.id}' is a hole_pattern and its {side} lists no holes",
                    subject=f"mates[].{side}.holes",
                )
            if self.kind == "shaft_in_bore" and (end.axis is None) == (end.feature is None):
                raise _refuse(
                    f"mate '{self.id}' is shaft_in_bore and its {side} names "
                    "neither or both of axis and feature; it takes exactly one",
                    subject=f"mates[].{side}.axis",
                )
        if self.kind == "hole_pattern" and len(self.place.holes) != len(self.on.holes):
            raise _refuse(
                f"mate '{self.id}' pairs {len(self.place.holes)} holes with "
                f"{len(self.on.holes)}; a hole pattern mates the same number on each side",
                subject="mates[].place.holes",
            )
        if self.place.part == self.on.part:
            raise _refuse(
                f"mate '{self.id}' mates '{self.place.part}' to itself",
                subject="mates[].on.part",
            )
        for name in ("offset", "position_tolerance"):
            value = getattr(self, name)
            if value is not None and not value.has_dimension("[length]"):
                raise _refuse(
                    f"mate '{self.id}' states {name} as {value}, which is not a length",
                    subject=f"mates[].{name}",
                )
        return self


class HardwareStack(StatableModel):
    """The fasteners in one hole-pattern mate: a bolt in every hole, with washers and a nut.

    ``bolt`` is a bundled designation (``ISO4762-M6`` or ``ISO4014-M6``) and ``length`` the
    bolt's length under its head. ``washer`` goes under the head, and under the nut when
    there is one. ``clearance`` is the ISO 273 class the holes are held to.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mate: Named
    bolt: Named
    length: Quantity
    washer: Named | None = None
    nut: Named | None = None
    clearance: Literal["close", "normal", "coarse"] = "normal"

    @model_validator(mode="after")
    def _a_length(self) -> HardwareStack:
        if not self.length.has_dimension("[length]") or self.length.to("mm").magnitude <= 0:
            raise _refuse(
                f"hardware in mate '{self.mate}' states its bolt length as {self.length}",
                subject="hardware[].length",
            )
        return self


class Weld(StatableModel):
    """A weld between the two faces of a face-to-face mate: its type and its size.

    A weld is a declared joint, not geometry. No bead is modelled. Its strength is the
    business of a ``welded_connection`` element, and the combination says so.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mate: Named
    type: Literal["fillet", "groove", "plug"]
    size: Quantity

    @model_validator(mode="after")
    def _a_size(self) -> Weld:
        if not self.size.has_dimension("[length]") or self.size.to("mm").magnitude <= 0:
            raise _refuse(
                f"the weld on mate '{self.mate}' states its size as {self.size}",
                subject="welds[].size",
            )
        return self


class Combination(StatableModel):
    """A combination document: parts, the mates that place them, and the hardware in them.

    The first part is the base. It stays where its own spec builds it, and every other part
    is placed by one or more mates onto a part placed before it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    anvilate_combination: str = COMBINATION_VERSION
    name: Named
    description: Provenance | None = None
    parts: tuple[CombinationPart, ...] = Field(min_length=2, max_length=24)
    mates: tuple[Mate, ...] = Field(min_length=1, max_length=96)
    hardware: tuple[HardwareStack, ...] = Field(default=(), max_length=24)
    welds: tuple[Weld, ...] = Field(default=(), max_length=24)

    @model_validator(mode="after")
    def _the_document_refers_to_its_own_parts(self) -> Combination:
        ids = [part.id for part in self.parts]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise _refuse(f"parts are named {repeated} more than once", subject="parts[].id")
        mate_ids = [mate.id for mate in self.mates]
        repeated = sorted({i for i in mate_ids if mate_ids.count(i) > 1})
        if repeated:
            raise _refuse(f"mates are named {repeated} more than once", subject="mates[].id")
        order = {part_id: index for index, part_id in enumerate(ids)}
        for mate in self.mates:
            for side, end in (("place", mate.place), ("on", mate.on)):
                if end.part not in order:
                    raise _refuse(
                        f"mate '{mate.id}' names the part '{end.part}', and the parts are "
                        f"{', '.join(ids)}",
                        subject=f"mates[].{side}.part",
                    )
            if mate.place.part == ids[0]:
                raise _refuse(
                    f"mate '{mate.id}' places '{ids[0]}', which is the base: the first part "
                    "stays where it is and the others are placed onto it",
                    subject="mates[].place.part",
                )
            if order[mate.on.part] >= order[mate.place.part]:
                raise _refuse(
                    f"mate '{mate.id}' places '{mate.place.part}' on '{mate.on.part}', which "
                    "comes after it; list a part after the parts it is placed on",
                    subject="parts",
                )
        placed = {mate.place.part for mate in self.mates}
        adrift = [part_id for part_id in ids[1:] if part_id not in placed]
        if adrift:
            raise _refuse(
                f"no mate places {adrift}; every part after the first is placed by a mate",
                subject="mates",
                action="add",
            )
        patterns = {mate.id for mate in self.mates if mate.kind == "hole_pattern"}
        for stack in self.hardware:
            if stack.mate not in patterns:
                raise _refuse(
                    f"hardware names the mate '{stack.mate}', which is not a hole_pattern "
                    f"mate of this combination ({', '.join(sorted(patterns)) or 'it has none'})",
                    subject="hardware[].mate",
                )
        contacts = {mate.id for mate in self.mates if mate.kind == "face_to_face"}
        for weld in self.welds:
            if weld.mate not in contacts:
                raise _refuse(
                    f"a weld names the mate '{weld.mate}', which is not a face_to_face mate "
                    f"of this combination ({', '.join(sorted(contacts)) or 'it has none'})",
                    subject="welds[].mate",
                )
        return self


def parse_combination(document: Mapping[str, Any]) -> Combination:
    """A combination document as its typed model, refusing what it cannot place."""
    from pydantic import ValidationError

    try:
        return Combination.model_validate(dict(document))
    except ValidationError as failure:
        first = failure.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "the document"
        raise _refuse(
            f"the combination document is not valid at {where}: {first['msg']}",
            subject=where,
        ) from failure


# --- small exact linear algebra: three unknowns, no dependency -------------------------


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Vec, factor: float) -> Vec:
    return (a[0] * factor, a[1] * factor, a[2] * factor)


def _norm(a: Vec) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a: Vec) -> Vec:
    length = _norm(a)
    return _scale(a, 1 / length) if length > 1e-12 else (0.0, 0.0, 0.0)


def _apply(matrix: Matrix, vector: Vec) -> Vec:
    return (_dot(matrix[0], vector), _dot(matrix[1], vector), _dot(matrix[2], vector))


def _multiply(a: Matrix, b: Matrix) -> Matrix:
    columns = [(b[0][i], b[1][i], b[2][i]) for i in range(3)]
    return tuple(tuple(_dot(row, column) for column in columns) for row in a)  # type: ignore[return-value]


def _about(axis: Vec, angle: float) -> Matrix:
    """The rotation by ``angle`` radians about the unit ``axis`` (Rodrigues)."""
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    k = 1 - c
    return (
        (c + x * x * k, x * y * k - z * s, x * z * k + y * s),
        (y * x * k + z * s, c + y * y * k, y * z * k - x * s),
        (z * x * k - y * s, z * y * k + x * s, c + z * z * k),
    )


def _turning(a: Vec, b: Vec) -> Matrix:
    """The smallest rotation that takes the unit vector ``a`` onto ``b``."""
    axis = _cross(a, b)
    sine, cosine = _norm(axis), _dot(a, b)
    if sine < 1e-12:
        if cosine > 0:
            return _IDENTITY
        # Opposite: half a turn about any axis square to a.
        helper = (1.0, 0.0, 0.0) if abs(a[0]) < 0.9 else (0.0, 1.0, 0.0)
        return _about(_unit(_cross(a, helper)), math.pi)
    return _about(_scale(axis, 1 / sine), math.atan2(sine, cosine))


def _frame(first: Vec, second: Vec) -> Matrix:
    """An orthonormal frame whose first axis is ``first`` and whose second leans to ``second``."""
    e1 = _unit(first)
    e2 = _unit(_sub(second, _scale(e1, _dot(second, e1))))
    return (e1, e2, _cross(e1, e2))


def _from_frames(source: Matrix, target: Matrix) -> Matrix:
    """The rotation taking each axis of ``source`` onto the same axis of ``target``."""
    return tuple(
        tuple(sum(target[k][row] * source[k][column] for k in range(3)) for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def _solve(rows: Sequence[tuple[Vec, float]]) -> tuple[Vec, list[Vec]]:
    """Least-squares ``t`` for the equations ``row . t = value``, and the directions left free.

    Three unknowns, so the normal equations are reduced by hand with full pivoting. A pivot
    below a micrometre-scale threshold is a direction no equation speaks about.
    """
    m = [[sum(r[0][i] * r[0][j] for r in rows) for j in range(3)] for i in range(3)]
    v = [sum(r[0][i] * r[1] for r in rows) for i in range(3)]
    columns = [0, 1, 2]
    rank = 0
    for step in range(3):
        best, at = 0.0, (step, step)
        for i in range(step, 3):
            for j in range(step, 3):
                if abs(m[i][j]) > best:
                    best, at = abs(m[i][j]), (i, j)
        if best < 1e-9:
            break
        i, j = at
        m[step], m[i] = m[i], m[step]
        v[step], v[i] = v[i], v[step]
        for row in m:
            row[step], row[j] = row[j], row[step]
        columns[step], columns[j] = columns[j], columns[step]
        for i in range(3):
            if i != step:
                factor = m[i][step] / m[step][step]
                m[i] = [a - factor * b for a, b in zip(m[i], m[step], strict=True)]
                v[i] -= factor * v[step]
        rank += 1
    solution = [0.0, 0.0, 0.0]
    for step in range(rank):
        solution[columns[step]] = v[step] / m[step][step]
    free = []
    for step in range(rank, 3):
        direction = [0.0, 0.0, 0.0]
        direction[columns[step]] = 1.0
        for pivot in range(rank):
            direction[columns[pivot]] = -m[pivot][step] / m[pivot][pivot]
        free.append(_unit((direction[0], direction[1], direction[2])))
    return (solution[0], solution[1], solution[2]), free


# --- placement ------------------------------------------------------------------------


@dataclass(frozen=True)
class PlacedPart:
    """One part where its mates put it: its solid, and the rotation and shift that placed it."""

    id: str
    built: Any
    spec: Any
    rotation: Matrix
    translation: Vec
    # Set when nothing fixed the part's turn about a shared axis, and it was left as built.
    turns_freely: bool = False

    def point(self, local: Vec) -> Vec:
        """A point of the part, where it is in the combination."""
        return _add(_apply(self.rotation, local), self.translation)

    def direction(self, local: Vec) -> Vec:
        """A direction of the part, as it points in the combination."""
        return _apply(self.rotation, local)

    @property
    def shape(self) -> Any:
        """The part's solid, moved to where it is placed."""
        return self.built.shape.moved(_location(self.rotation, self.translation))


@dataclass(frozen=True)
class HardwareBody:
    """One fastener envelope: what it is, the solid as tabulated, and where it goes."""

    designation: str
    kind: Literal["bolt", "washer", "nut"]
    mate: str
    solid: Any
    rotation: Matrix
    translation: Vec

    @property
    def shape(self) -> Any:
        """The envelope, moved to its hole."""
        return self.solid.moved(_location(self.rotation, self.translation))


class BomLine(StatableModel):
    """One line of the parts list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: int = Field(ge=1)
    name: Provenance
    description: Provenance
    quantity: int = Field(ge=1)
    material: str | None = Field(default=None, exclude_if=lambda value: value is None)
    mass_kg: float | None = Field(default=None, exclude_if=lambda value: value is None)
    # True for a fastener or a catalog component drawn from its tabulated size.
    envelope: bool = Field(default=False, exclude_if=lambda value: not value)

    def __str__(self) -> str:
        mass = f", {self.mass_kg:.3g} kg each" if self.mass_kg is not None else ""
        material = f", {self.material}" if self.material else ""
        kind = " (envelope)" if self.envelope else ""
        return (
            f"{self.item:>2}  {self.quantity} x {self.name}: "
            f"{self.description}{material}{mass}{kind}"
        )


class PlacedSummary(StatableModel):
    """One part of a built combination: what it is and where its mates put it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Named
    pattern: Provenance
    # The corner of the part's box nearest the origin, and the box's size, as placed.
    corner_mm: tuple[float, float, float]
    size_mm: tuple[float, float, float]
    # True when nothing fixes the part's turn about a shared axis and it is left as built.
    turns_freely: bool = Field(default=False, exclude_if=lambda value: not value)


class CombinationSummary(StatableModel):
    """A built combination, as the surfaces report it: where each part is, and the parts list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    size_mm: tuple[float, float, float]
    bodies: int = Field(ge=2)
    parts: tuple[PlacedSummary, ...] = Field(min_length=2)
    bom: tuple[BomLine, ...] = Field(min_length=2)

    def __str__(self) -> str:
        size = " x ".join(f"{value:g}" for value in self.size_mm)
        lines = [f"{self.name}: {self.bodies} bodies, {size} mm"]
        for part in self.parts:
            at = ", ".join(f"{value:g}" for value in part.corner_mm)
            box = " x ".join(f"{value:g}" for value in part.size_mm)
            free = "; free to turn about its axis" if part.turns_freely else ""
            lines.append(f"  {part.id}: {part.pattern}, {box} mm, corner at ({at}){free}")
        lines.append("  parts list:")
        lines += [f"  {line}" for line in self.bom]
        return "\n".join(lines)


@dataclass(frozen=True)
class BuiltCombination:
    """A combination placed, checked and counted."""

    name: str
    parts: tuple[PlacedPart, ...]
    hardware: tuple[HardwareBody, ...]
    card: Scorecard
    bom: tuple[BomLine, ...]

    def summary(self) -> CombinationSummary:
        """The document the surfaces publish: each part's place, and the parts list."""
        placed = []
        low = [math.inf] * 3
        high = [-math.inf] * 3
        for label, shape in self.bodies:
            box = shape.bounding_box()
            least, most = tuple(box.min), tuple(box.max)
            low = [min(a, b) for a, b in zip(low, least, strict=True)]
            high = [max(a, b) for a, b in zip(high, most, strict=True)]
            del label
        for part in self.parts:
            box = part.shape.bounding_box()
            placed.append(
                PlacedSummary(
                    id=part.id,
                    pattern=str(part.built.pattern),
                    corner_mm=_tidy(tuple(box.min)),
                    size_mm=_tidy((box.size.X, box.size.Y, box.size.Z)),
                    turns_freely=part.turns_freely,
                )
            )
        return CombinationSummary(
            name=self.name,
            size_mm=_tidy(tuple(b - a for a, b in zip(low, high, strict=True))),
            bodies=len(self.bodies),
            parts=tuple(placed),
            bom=self.bom,
        )

    @property
    def bodies(self) -> tuple[tuple[str, Any], ...]:
        """Every body with a label: the parts by id, then each fastener by what it is."""
        labelled = [(part.id, part.shape) for part in self.parts]
        labelled += [(body.designation, body.shape) for body in self.hardware]
        return tuple(labelled)


def _tidy(values: Sequence[float]) -> tuple[float, float, float]:
    """Three lengths to a micrometre, with no negative zero."""
    return tuple(round(float(value), 6) + 0.0 for value in values)  # type: ignore[return-value]


def _location(rotation: Matrix, translation: Vec) -> Any:
    from build123d import Location
    from OCP.gp import gp_Trsf  # type: ignore[import-untyped]

    transform = gp_Trsf()
    transform.SetValues(
        rotation[0][0], rotation[0][1], rotation[0][2], translation[0],
        rotation[1][0], rotation[1][1], rotation[1][2], translation[1],
        rotation[2][0], rotation[2][1], rotation[2][2], translation[2],
    )  # fmt: skip
    return Location(transform)


def _face(part_id: str, built: Any, face: str) -> tuple[Vec, Vec]:
    """A part's outermost face in one direction, in its own frame: a point on it, its normal."""
    normal = _FACES[face]
    box = built.shape.bounding_box()
    low, high = (box.min.X, box.min.Y, box.min.Z), (box.max.X, box.max.Y, box.max.Z)
    centre = tuple((a + b) / 2 for a, b in zip(low, high, strict=True))
    axis = next(index for index, component in enumerate(normal) if component)
    point = list(centre)
    point[axis] = high[axis] if normal[axis] > 0 else low[axis]
    del part_id
    return (point[0], point[1], point[2]), normal


def _hole(mate: Mate, side: str, part_id: str, built: Any, tag: str) -> Any:
    found = next((feature for feature in built.features if feature.tag == tag), None)
    if found is None:
        tags = ", ".join(feature.tag for feature in built.features) or "none"
        raise _refuse(
            f"mate '{mate.id}' names the hole '{tag}' on '{part_id}', whose features are: {tags}",
            subject=f"mates[].{side}.holes",
        )
    return found


def _axis(mate: Mate, side: str, end: MateEnd, built: Any) -> tuple[Vec, Vec]:
    """A point on the named axis and its direction, in the part's own frame."""
    if end.axis is not None:
        return (0.0, 0.0, 0.0), _AXES[end.axis]
    feature = _hole(mate, side, end.part, built, str(end.feature))
    return tuple(feature.position_mm), _unit(tuple(feature.axis))  # type: ignore[return-value]


def _square_to(direction: Vec) -> tuple[Vec, Vec]:
    helper = (1.0, 0.0, 0.0) if abs(direction[0]) < 0.9 else (0.0, 1.0, 0.0)
    first = _unit(_cross(direction, helper))
    return first, _cross(direction, first)


def _place(
    part_id: str, built: Any, mates: Sequence[Mate], placed: Mapping[str, PlacedPart]
) -> tuple[Matrix, Vec, bool]:
    """The rotation and shift the mates give ``part_id``, or a refusal naming them."""
    named = ", ".join(f"'{mate.id}'" for mate in mates)
    directions: list[tuple[Vec, Vec, str]] = []
    for mate in mates:
        fixed = placed[mate.on.part]
        if mate.kind in ("face_to_face", "hole_pattern", "edge_flush"):
            _point, normal = _face(part_id, built, str(mate.place.face))
            _on_point, on_normal = _face(fixed.id, fixed.built, str(mate.on.face))
            target = fixed.direction(on_normal)
            if mate.kind != "edge_flush":
                target = _scale(target, -1.0)
            directions.append((normal, target, mate.id))
            if mate.kind == "hole_pattern" and len(mate.place.holes) >= 2:
                mine = [_hole(mate, "place", part_id, built, tag) for tag in mate.place.holes]
                theirs = [_hole(mate, "on", fixed.id, fixed.built, tag) for tag in mate.on.holes]
                # The line from the first hole to the one farthest from it, on each side.
                far = max(
                    range(1, len(mine)),
                    key=lambda i: math.dist(mine[i].position_mm, mine[0].position_mm),
                )
                span = _sub(tuple(mine[far].position_mm), tuple(mine[0].position_mm))
                span = _sub(span, _scale(normal, _dot(span, normal)))
                other = _sub(
                    fixed.point(tuple(theirs[far].position_mm)),
                    fixed.point(tuple(theirs[0].position_mm)),
                )
                other = _sub(other, _scale(target, _dot(other, target)))
                if _norm(span) > 1e-9 and _norm(other) > 1e-9:
                    directions.append((_unit(span), _unit(other), mate.id))
        else:
            _point, direction = _axis(mate, "place", mate.place, built)
            _on_point, on_direction = _axis(mate, "on", mate.on, fixed.built)
            directions.append((direction, fixed.direction(on_direction), mate.id))

    first_a, first_b, _first_mate = directions[0]
    second = next(
        (
            (a, b, mate_id)
            for a, b, mate_id in directions[1:]
            if _norm(_cross(first_a, a)) > 1e-6 and _norm(_cross(first_b, b)) > 1e-6
        ),
        None,
    )
    turns_freely = second is None
    if second is None:
        rotation = _turning(first_a, first_b)
        turn = next((mate.rotation_deg for mate in mates if mate.rotation_deg is not None), None)
        if turn is not None:
            rotation = _multiply(_about(first_b, math.radians(turn)), rotation)
            turns_freely = False
    else:
        rotation = _from_frames(_frame(first_a, second[0]), _frame(first_b, second[1]))
    for a, b, mate_id in directions:
        if _norm(_sub(_apply(rotation, a), b)) > 1e-6:
            raise _refuse(
                f"the mates {named} ask '{part_id}' to face two ways at once: mate "
                f"'{mate_id}' cannot be met with the others",
                subject="mates",
            )

    rows: list[tuple[Vec, float]] = []
    owners: list[str] = []

    def on_plane(local: Vec, normal: Vec, through: Vec, mate_id: str) -> None:
        rows.append((normal, _dot(normal, through) - _dot(normal, _apply(rotation, local))))
        owners.append(mate_id)

    def on_line(local: Vec, through: Vec, along: Vec, mate_id: str) -> None:
        for square in _square_to(along):
            on_plane(local, square, through, mate_id)

    for mate in mates:
        fixed = placed[mate.on.part]
        if mate.kind in ("face_to_face", "hole_pattern", "edge_flush"):
            point, _normal = _face(part_id, built, str(mate.place.face))
            on_point, on_normal = _face(fixed.id, fixed.built, str(mate.on.face))
            world_normal = fixed.direction(on_normal)
            gap = mate.offset.to("mm").magnitude if mate.offset is not None else 0.0
            through = _add(fixed.point(on_point), _scale(world_normal, gap))
            on_plane(point, world_normal, through, mate.id)
            if mate.kind == "hole_pattern":
                for mine_tag, their_tag in zip(mate.place.holes, mate.on.holes, strict=True):
                    mine = _hole(mate, "place", part_id, built, mine_tag)
                    theirs = _hole(mate, "on", fixed.id, fixed.built, their_tag)
                    on_line(
                        tuple(mine.position_mm),
                        fixed.point(tuple(theirs.position_mm)),
                        world_normal,
                        mate.id,
                    )
        else:
            point, _direction = _axis(mate, "place", mate.place, built)
            on_point, on_direction = _axis(mate, "on", mate.on, fixed.built)
            on_line(point, fixed.point(on_point), fixed.direction(on_direction), mate.id)

    translation, free = _solve(rows)
    if free:
        # Sorted and with no negative zero, so the same freedom always reads the same way.
        tidy = sorted(tuple(round(c, 6) + 0.0 for c in d) for d in free)
        ways = "; ".join(f"({d[0]:.3g}, {d[1]:.3g}, {d[2]:.3g})" for d in reversed(tidy))
        raise _refuse(
            f"the mates {named} leave '{part_id}' free to slide along {ways}. Add a mate "
            "that fixes it: a hole_pattern, a second edge_flush, or a face_to_face square "
            "to the first",
            subject="mates",
            action="add",
        )
    patterns = {mate.id for mate in mates if mate.kind == "hole_pattern"}
    for (row, value), owner in zip(rows, owners, strict=True):
        if owner not in patterns and abs(_dot(row, translation) - value) > 1e-6:
            raise _refuse(
                f"the mates {named} contradict each other for '{part_id}': mate '{owner}' "
                "cannot be met with the others",
                subject="mates",
            )
    return rotation, translation, turns_freely


# --- hardware -------------------------------------------------------------------------


def _fastener(designation: str) -> tuple[str, float, float, float]:
    """A bolt's head shape, head size, head height and thread diameter, from the tables."""
    from .standards.capscrews import default_cap_screw_table
    from .standards.hexbolts import default_hex_bolt_table

    size = designation.rpartition("-M")[2]
    cap, hexagon = default_cap_screw_table(), default_hex_bolt_table()
    try:
        diameter = float(size)
    except ValueError:
        diameter = math.nan
    if designation.startswith("ISO4762") and math.isfinite(diameter):
        try:
            record = cap.get(designation)
        except KeyError as unknown:
            raise _unknown(designation, cap.designations(), "bolt") from unknown
        return (
            "round",
            record.head_diameter.quantity.to("mm").magnitude,
            record.head_height.quantity.to("mm").magnitude,
            diameter,
        )
    if designation.startswith("ISO4014") and math.isfinite(diameter):
        try:
            record = hexagon.get(designation)
        except KeyError as unknown:
            raise _unknown(designation, hexagon.designations(), "bolt") from unknown
        return (
            "hex",
            record.width_across_flats.quantity.to("mm").magnitude,
            record.head_height.quantity.to("mm").magnitude,
            diameter,
        )
    raise _unknown(designation, [*cap.designations(), *hexagon.designations()], "bolt")


def _unknown(designation: str, known: Sequence[str], what: str) -> CombinationError:
    import difflib

    near = difflib.get_close_matches(designation, list(known), n=4, cutoff=0.5)
    return _refuse(
        f"no bundled {what} is designated '{designation}'"
        + (f"; closest: {', '.join(near)}" if near else ""),
        subject=f"hardware[].{what}",
        action="select",
    )


def _hex(across_flats: float, height: float, bore: float = 0.0) -> Any:
    from build123d import Cylinder, RegularPolygon, extrude

    from ._patterns_parts import _low

    solid = extrude(RegularPolygon(across_flats / 2, 6, major_radius=False), amount=height)
    return solid - Cylinder(bore / 2, height, align=_low()) if bore else solid


def _stack(
    stack: HardwareStack, mate: Mate, moving: PlacedPart, fixed: PlacedPart
) -> tuple[list[HardwareBody], list[ScorecardEntry]]:
    """The bolt, washers and nut in every hole of one mate, and what the stack is checked for."""
    from build123d import Align, Cylinder

    from ._patterns_parts import _low, _ring
    from .standards.hexnuts import default_hex_nut_table
    from .standards.threads import default_clearance_table
    from .standards.washers import default_washer_table

    head, head_size, head_height, diameter = _fastener(str(stack.bolt))
    length = stack.length.to("mm").magnitude
    washer = None
    if stack.washer is not None:
        table = default_washer_table()
        try:
            washer = table.get(str(stack.washer))
        except KeyError as unknown:
            raise _unknown(str(stack.washer), table.designations(), "washer") from unknown
    nut = None
    if stack.nut is not None:
        nuts = default_hex_nut_table()
        try:
            nut = nuts.get(str(stack.nut))
        except KeyError as unknown:
            raise _unknown(str(stack.nut), nuts.designations(), "nut") from unknown
    washer_thickness = washer.thickness.quantity.to("mm").magnitude if washer else 0.0
    nut_height = nut.height.quantity.to("mm").magnitude if nut else 0.0

    bolt_solid = Cylinder(diameter / 2, length, align=(Align.CENTER, Align.CENTER, Align.MAX))
    bolt_solid = bolt_solid + (
        Cylinder(head_size / 2, head_height, align=_low())
        if head == "round"
        else _hex(head_size, head_height)
    )
    washer_solid = (
        _ring(
            washer.outer_diameter.quantity.to("mm").magnitude,
            washer.inner_diameter.quantity.to("mm").magnitude,
            washer_thickness,
        )
        if washer
        else None
    )
    nut_solid = (
        _hex(nut.width_across_flats.quantity.to("mm").magnitude, nut_height, bore=diameter)
        if nut
        else None
    )

    _point, on_normal = _face(fixed.id, fixed.built, str(mate.on.face))
    outward = fixed.direction(on_normal)  # from the fixed part toward the placed one
    upright = _turning((0.0, 0.0, 1.0), outward)
    inverted = _turning((0.0, 0.0, 1.0), _scale(outward, -1.0))
    bodies: list[HardwareBody] = []
    thinnest, clamped, smallest = math.inf, 0.0, math.inf
    for mine_tag, their_tag in zip(mate.place.holes, mate.on.holes, strict=True):
        mine = _hole(mate, "place", moving.id, moving.built, mine_tag)
        theirs = _hole(mate, "on", fixed.id, fixed.built, their_tag)
        plane_point, _n = _face(fixed.id, fixed.built, str(mate.on.face))
        seat = fixed.point(tuple(theirs.position_mm))
        # The hole's axis where it crosses the mating plane.
        seat = _add(seat, _scale(outward, _dot(outward, _sub(fixed.point(plane_point), seat))))
        top, under = mine.depth_mm, theirs.depth_mm
        clamped = max(clamped, top + under)
        thinnest = min(thinnest, top + under)
        smallest = min(smallest, mine.diameter_mm, theirs.diameter_mm)
        if washer_solid is not None:
            bodies.append(
                HardwareBody(
                    str(stack.washer),
                    "washer",
                    mate.id,
                    washer_solid,
                    upright,
                    _add(seat, _scale(outward, top)),
                )  # fmt: skip
            )
        bodies.append(
            HardwareBody(
                f"{stack.bolt}x{length:g}",
                "bolt",
                mate.id,
                bolt_solid,
                upright,
                _add(seat, _scale(outward, top + washer_thickness)),
            )  # fmt: skip
        )
        if nut_solid is not None:
            if washer_solid is not None:
                bodies.append(
                    HardwareBody(
                        str(stack.washer),
                        "washer",
                        mate.id,
                        washer_solid,
                        inverted,
                        _add(seat, _scale(outward, -under)),
                    )  # fmt: skip
                )
            bodies.append(
                HardwareBody(
                    str(stack.nut),
                    "nut",
                    mate.id,
                    nut_solid,
                    inverted,
                    _add(seat, _scale(outward, -under - washer_thickness)),
                )  # fmt: skip
            )

    entries = []
    try:
        wanted = default_clearance_table().get(f"M{diameter:g}", stack.clearance)
        needed_hole = wanted.quantity.to("mm").magnitude
    except KeyError:
        needed_hole = None
    if needed_hole is None:
        entries.append(
            ScorecardEntry(
                name=f"{mate.id} bolt clearance",
                status=CheckStatus.NOT_EVALUATED,
                detail=f"the bundled ISO 273 table has no clearance hole for M{diameter:g}",
                underived=_MEASURED,
            )
        )
    else:
        fits = smallest >= needed_hole - 1e-9
        entries.append(
            ScorecardEntry(
                name=f"{mate.id} bolt clearance",
                status=CheckStatus.PASS if fits else CheckStatus.FAIL,
                detail=(
                    f"the smallest mated hole is {smallest:g} mm and an M{diameter:g} bolt "
                    f"takes {needed_hole:g} mm at the ISO 273 {stack.clearance} class"
                    + ("" if fits else f"; open the holes to {needed_hole:g} mm")
                ),
                reference="ISO 273:1979 clearance holes for bolts and screws",
                underived=_MEASURED,
            )
        )
    if nut is None:
        entries.append(
            ScorecardEntry(
                name=f"{mate.id} bolt length",
                status=CheckStatus.NOT_EVALUATED,
                detail=(
                    f"the bolt is {length:g} mm long through a {clamped:g} mm stack with no "
                    "nut declared; thread engagement in a tapped hole is not screened"
                ),
                underived=_MEASURED,
            )
        )
    else:
        needed = clamped + 2 * washer_thickness + nut_height
        reaches = length >= needed - 1e-9
        entries.append(
            ScorecardEntry(
                name=f"{mate.id} bolt length",
                status=CheckStatus.PASS if reaches else CheckStatus.FAIL,
                detail=(
                    f"a {length:g} mm bolt through {clamped:g} mm of parts, "
                    f"{2 if washer else 0} washer(s) of {washer_thickness:g} mm and a "
                    f"{nut_height:g} mm nut needs {needed:g} mm to fill the nut"
                    + ("" if reaches else f"; it is {needed - length:g} mm short")
                ),
                underived=_MEASURED,
            )
        )
    del thinnest
    return bodies, entries


# --- checks ---------------------------------------------------------------------------


def _pattern_entry(
    mate: Mate, moving: PlacedPart, fixed: PlacedPart, stack: HardwareStack | None
) -> ScorecardEntry:
    """Whether the holes two parts are mated by are where each other's are."""
    _point, on_normal = _face(fixed.id, fixed.built, str(mate.on.face))
    normal = fixed.direction(on_normal)
    worst, at = 0.0, ""
    room = math.inf
    for mine_tag, their_tag in zip(mate.place.holes, mate.on.holes, strict=True):
        mine = _hole(mate, "place", moving.id, moving.built, mine_tag)
        theirs = _hole(mate, "on", fixed.id, fixed.built, their_tag)
        apart = _sub(moving.point(tuple(mine.position_mm)), fixed.point(tuple(theirs.position_mm)))
        apart = _sub(apart, _scale(normal, _dot(apart, normal)))
        if _norm(apart) > worst:
            worst, at = _norm(apart), f"{mine_tag} and {their_tag}"
        room = min(room, mine.diameter_mm, theirs.diameter_mm)
    if mate.position_tolerance is not None:
        allowed = mate.position_tolerance.to("mm").magnitude
        basis = f"the declared tolerance of {allowed:g} mm"
    elif stack is not None:
        _head, _size, _height, diameter = _fastener(str(stack.bolt))
        allowed = max(0.0, room - diameter)
        basis = f"the {allowed:g} mm an M{diameter:g} bolt has to spare in the smallest hole"
    else:
        allowed = EXACT_MM
        basis = "no declared tolerance, so the holes are held to a micrometre"
    count = len(mate.place.holes)
    agree = worst <= allowed + 1e-9
    return ScorecardEntry(
        name=f"{mate.id} hole pattern",
        status=CheckStatus.PASS if agree else CheckStatus.FAIL,
        detail=(
            f"{count} hole{'s' if count != 1 else ''} of '{moving.id}' on {count} of "
            f"'{fixed.id}': the farthest pair is {worst:.4g} mm apart, against {basis}"
            + ("" if agree else f"; {at} do not line up")
        ),
        underived=_MEASURED,
    )


def _interference(bodies: Sequence[tuple[str, Any]]) -> ScorecardEntry:
    """Every pair of bodies intersected; an overlap is named with its volume."""
    clashes = []
    boxes = [shape.bounding_box() for _label, shape in bodies]
    pairs = 0
    for first in range(len(bodies)):
        for second in range(first + 1, len(bodies)):
            a, b = boxes[first], boxes[second]
            if (
                a.max.X <= b.min.X or b.max.X <= a.min.X
                or a.max.Y <= b.min.Y or b.max.Y <= a.min.Y
                or a.max.Z <= b.min.Z or b.max.Z <= a.min.Z
            ):  # fmt: skip
                continue
            pairs += 1
            common = bodies[first][1] & bodies[second][1]
            volume = float(common.volume) if common is not None else 0.0
            if volume > 1e-6:
                clashes.append(f"{bodies[first][0]} and {bodies[second][0]} by {volume:.4g} mm^3")
    if clashes:
        shown = "; ".join(clashes[:8]) + (
            f"; and {len(clashes) - 8} more" if len(clashes) > 8 else ""
        )
        return ScorecardEntry(
            name="interference",
            status=CheckStatus.FAIL,
            detail=f"{len(clashes)} pair{'s' if len(clashes) != 1 else ''} overlap: {shown}",
            underived=_MEASURED,
        )
    return ScorecardEntry(
        name="interference",
        status=CheckStatus.PASS,
        detail=(
            f"no two of the {len(bodies)} bodies overlap; {pairs} pair"
            f"{'s' if pairs != 1 else ''} whose boxes meet were intersected"
        ),
        underived=_MEASURED,
    )


def _part_entry(part: PlacedPart, card: Scorecard) -> ScorecardEntry:
    """One part's own verdict, carried onto the combination's card."""
    governing = next(
        (entry for entry in card.entries if entry.status is card.status), card.entries[0]
    )
    return ScorecardEntry(
        name=f"{part.id} part",
        status=card.status,
        detail=(
            f"its own card is {card.status.value.replace('_', ' ')}: "
            f"{governing.name} — {governing.detail}"
        ),
        underived=Underived(
            kind=DerivationAbsence.NUMERIC_RESULT,
            reason="the part's own scorecard holds each check and its derivation",
        ),
    )


def _mass(spec: Any, built: Any) -> float | None:
    from .standards.materials import default_materials_db

    try:
        material = default_materials_db().get(str(spec.material.ref))
    except (KeyError, ValueError):
        return None
    density = material.density.quantity.to("kg/mm**3").magnitude
    return float(built.volume_mm3) * density


def build_combination(combination: Combination) -> BuiltCombination:
    """Build every part, place each by its mates, add the hardware, and check where they meet.

    A mate that leaves a part free to slide, or contradicts another, is refused naming the
    mates. A mismatch between mated holes is not a refusal: the parts are placed as near as
    they go and the mismatch is a failing entry, so the picture shows what is wrong.
    """
    from .geometry import GeometryError, build_spec
    from .patterns import pattern_for
    from .screening import screen_spec
    from .spec import SpecValidationError, parse_spec

    built_parts: dict[str, tuple[Any, Any]] = {}
    for part in combination.parts:
        try:
            spec = parse_spec(dict(part.spec))
            built_parts[part.id] = (spec, build_spec(spec))
        except (SpecValidationError, GeometryError) as failure:
            raise _refuse(
                f"part '{part.id}' cannot be built: {failure}", subject="parts[].spec"
            ) from failure

    placed: dict[str, PlacedPart] = {}
    base = combination.parts[0].id
    placed[base] = PlacedPart(
        base, built_parts[base][1], built_parts[base][0], _IDENTITY, (0.0, 0.0, 0.0)
    )
    entries: list[ScorecardEntry] = []
    for part in combination.parts[1:]:
        mates = [mate for mate in combination.mates if mate.place.part == part.id]
        spec, built = built_parts[part.id]
        rotation, translation, turns_freely = _place(part.id, built, mates, placed)
        placed[part.id] = PlacedPart(part.id, built, spec, rotation, translation, turns_freely)

    stacks = {stack.mate: stack for stack in combination.hardware}
    hardware: list[HardwareBody] = []
    for part in combination.parts:
        entries.append(_part_entry(placed[part.id], screen_spec(placed[part.id].spec)))
    for mate in combination.mates:
        moving, fixed = placed[mate.place.part], placed[mate.on.part]
        if mate.kind == "hole_pattern":
            entries.append(_pattern_entry(mate, moving, fixed, stacks.get(mate.id)))
        if moving.turns_freely and mate is next(
            m for m in combination.mates if m.place.part == moving.id
        ):
            entries.append(
                ScorecardEntry(
                    name=f"{moving.id} placement",
                    status=CheckStatus.PASS,
                    detail=(
                        f"'{moving.id}' is placed, and nothing fixes its turn about the "
                        "shared axis, so it is left as built; state rotation_deg on a mate "
                        "to turn it"
                    ),
                    underived=_MEASURED,
                )
            )
        if mate.id in stacks:
            bodies, checks = _stack(stacks[mate.id], mate, moving, fixed)
            hardware += bodies
            entries += checks
        for weld in combination.welds:
            if weld.mate == mate.id:
                entries.append(
                    ScorecardEntry(
                        name=f"{mate.id} weld",
                        status=CheckStatus.NOT_EVALUATED,
                        detail=(
                            f"a {weld.size.to('mm').magnitude:g} mm {weld.type} weld joins "
                            f"'{moving.id}' to '{fixed.id}'. It is declared, not checked "
                            "here: screen it as a welded_connection element with its load"
                        ),
                        underived=_MEASURED,
                    )
                )

    parts = tuple(placed[part.id] for part in combination.parts)
    labelled = [(part.id, part.shape) for part in parts]
    labelled += [(f"{body.designation} in {body.mate}", body.shape) for body in hardware]
    entries.append(_interference(labelled))

    bom: list[BomLine] = []
    for part in parts:
        pattern = pattern_for(part.spec.element_type)
        bom.append(
            BomLine(
                item=len(bom) + 1,
                name=part.id,
                description=str(pattern.name if pattern else part.spec.element_type),
                quantity=1,
                material=str(part.spec.material.ref),
                mass_kg=_mass(part.spec, part.built),
                envelope=bool(part.built.envelope),
            )
        )
    counted: dict[tuple[str, str], int] = {}
    for body in hardware:
        counted[(body.kind, body.designation)] = counted.get((body.kind, body.designation), 0) + 1
    for (kind, designation), quantity in counted.items():
        bom.append(
            BomLine(
                item=len(bom) + 1,
                name=designation,
                description=kind,
                quantity=quantity,
                envelope=True,
            )
        )
    return BuiltCombination(
        name=str(combination.name),
        parts=parts,
        hardware=tuple(hardware),
        card=Scorecard(entries=tuple(entries)),
        bom=tuple(bom),
    )


# --- what the engineer takes away -----------------------------------------------------


def _numbered(built: BuiltCombination) -> tuple[list[tuple[str, Any, bool]], list[tuple[str, int]]]:
    """Every body as (label, solid, is_envelope), and one balloon per parts-list line."""
    bodies = [(part.id, part.shape, bool(part.built.envelope)) for part in built.parts]
    bodies += [(body.designation, body.shape, True) for body in built.hardware]
    item = {line.name: line.item for line in built.bom}
    places: dict[str, list[int]] = {}
    for index, (label, _solid, _envelope) in enumerate(bodies):
        places.setdefault(label, []).append(index)
    # One balloon per line of the parts list. A fastener that is in several holes is
    # marked in a different hole from the one before it, so the bolt, its washer and its
    # nut are not three balloons on one stack.
    marks = []
    for turn, (label, indices) in enumerate(places.items()):
        marks.append((str(item[label]), indices[turn % len(indices)]))
    return bodies, marks


def render_combination(
    built: BuiltCombination,
    *,
    width_px: int = 1100,
    format: str = "png",  # noqa: A002
) -> tuple[bytes, int, int]:
    """The combination as one picture: four views, each part numbered, the parts list below.

    Returns the image, its width and its height. ``format`` is ``png`` or ``svg``.
    """
    from . import projection
    from .raster import svg_to_png

    if format not in ("png", "svg"):
        raise _refuse(f"unknown image format {format!r}; choose png or svg", subject="format")
    if not 320 <= width_px <= 4096:
        raise _refuse(f"width_px must be from 320 through 4096; got {width_px}", subject="width_px")
    bodies, marks = _numbered(built)
    box_low = [
        min(tuple(shape.bounding_box().min)[axis] for _l, shape, _e in bodies) for axis in range(3)
    ]
    box_high = [
        max(tuple(shape.bounding_box().max)[axis] for _l, shape, _e in bodies) for axis in range(3)
    ]
    size = " x ".join(f"{high - low:.4g}" for low, high in zip(box_low, box_high, strict=True))
    svg, height = projection.render_assembly(
        bodies,
        name=built.name,
        lines=[f"{size} mm", built.card.status.value.replace("_", " ")],
        parts_list=[str(line) for line in built.bom],
        marks=marks,
        width_px=width_px,
    )
    return (svg if format == "svg" else svg_to_png(svg)), width_px, height


def write_step_assembly(built: BuiltCombination, path: Any, *, authorization: Any) -> Any:
    """Write the combination as one STEP AP242 assembly, each body a named component.

    Each part is a product placed by its own transform, and every fastener of one kind is
    one product placed once per hole, so the file opens as an assembly whose components can
    be selected and hidden, not as one fused body. The header carries the authorization's
    watermark, as a single part's file does. The file is read back before it is released:
    it must hold one assembly with a component for every body.
    """
    import re
    from pathlib import Path

    from OCP.IFSelect import IFSelect_ReturnStatus  # type: ignore[import-untyped]
    from OCP.Interface import Interface_Static  # type: ignore[import-untyped]
    from OCP.Message import Message, Message_Gravity  # type: ignore[import-untyped]
    from OCP.STEPCAFControl import (  # type: ignore[import-untyped]
        STEPCAFControl_Controller,
        STEPCAFControl_Reader,
        STEPCAFControl_Writer,
    )
    from OCP.STEPControl import (  # type: ignore[import-untyped]
        STEPControl_Controller,
        STEPControl_StepModelType,
    )
    from OCP.TCollection import TCollection_ExtendedString  # type: ignore[import-untyped]
    from OCP.TDataStd import TDataStd_Name  # type: ignore[import-untyped]
    from OCP.TDF import TDF_LabelSequence  # type: ignore[import-untyped]
    from OCP.TDocStd import TDocStd_Document  # type: ignore[import-untyped]
    from OCP.TopLoc import TopLoc_Location  # type: ignore[import-untyped]
    from OCP.XCAFApp import XCAFApp_Application  # type: ignore[import-untyped]
    from OCP.XCAFDoc import XCAFDoc_DocumentTool  # type: ignore[import-untyped]
    from OCP.XSControl import XSControl_WorkSession  # type: ignore[import-untyped]

    from . import geometry
    from .export.dxf import _atomic_path

    path = Path(path)

    def named(label: Any, text: str) -> None:
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def new_document() -> Any:
        document = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
        application = XCAFApp_Application.GetApplication_s()
        application.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), document)
        application.InitDocument(document)
        return document

    with geometry._STEP_IO_LOCK, _atomic_path(path) as staging:
        document = new_document()
        XCAFDoc_DocumentTool.SetLengthUnit_s(document, 0.001)
        tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
        assembly = tool.NewShape()
        named(assembly, built.name)
        products: list[str] = []
        prototypes: dict[str, Any] = {}
        instances = 0

        def component(key: str, product: str, solid: Any, rotation: Matrix, shift: Vec) -> None:
            nonlocal instances
            if key not in prototypes:
                prototypes[key] = tool.AddShape(solid.solids()[0].wrapped, False)
                named(prototypes[key], product)
                products.append(product)
            placed = tool.AddComponent(
                assembly,
                prototypes[key],
                TopLoc_Location(_location(rotation, shift).wrapped.Transformation()),
            )
            instances += 1
            named(placed, f"{product} {instances}")

        for part in built.parts:
            component(f"part:{part.id}", part.id, part.built.shape, part.rotation, part.translation)
        for body in built.hardware:
            component(
                f"{body.kind}:{body.designation}",
                f"{body.designation} (envelope)",
                body.solid,
                body.rotation,
                body.translation,
            )
        tool.UpdateAssemblies()

        STEPCAFControl_Controller.Init_s()
        STEPControl_Controller.Init_s()
        previous = Interface_Static.CVal_s("write.step.schema")
        try:
            Interface_Static.SetCVal_s("write.step.schema", "AP242DIS")
            for printer in Message.DefaultMessenger_s().Printers():
                printer.SetTraceLevel(Message_Gravity.Message_Fail)
            writer = STEPCAFControl_Writer(XSControl_WorkSession(), False)
            writer.SetNameMode(True)
            done = writer.Transfer(document, STEPControl_StepModelType.STEPControl_AsIs)
            if not done or writer.Write(str(staging)) != IFSelect_ReturnStatus.IFSelect_RetDone:
                raise _refuse(
                    "the STEP writer could not write the assembly", subject="path", action="retry"
                )
        finally:
            Interface_Static.SetCVal_s("write.step.schema", previous)

        try:
            text = staging.read_text(encoding="utf-8")
        except UnicodeDecodeError as failure:
            raise _refuse(
                "the STEP writer produced a file that is not UTF-8; refusing to release it",
                subject="path",
                action="report",
            ) from failure
        # Every product must be one this exporter named: the assembly, then each part and
        # each kind of fastener. A product under the kernel's placeholder name is a body
        # that would open in CAD as "SOLID".
        written = re.findall(r"PRODUCT\('((?:[^']|'')*)'", text)
        expected = [geometry._step_string(name) for name in (built.name, *products)]
        descriptions = [
            "Open CASCADE Model",
            "Anvilate combination: an assembly of catalog parts and fastener envelopes",
            *(f"{key}={value}" for key, value in authorization.metadata()),
        ]
        header = (
            "FILE_DESCRIPTION(("
            + ",".join(f"'{geometry._step_string(value)}'" for value in descriptions)
            + "),'2;1');"
        )
        text, described = re.subn(r"FILE_DESCRIPTION\(.*?\);", header, text, count=1)
        filename = f"FILE_NAME('{geometry._step_string(built.name)}','2000-01-01T00:00:00',"
        text, filed = re.subn(r"FILE_NAME\('[^']*','[^']*',", lambda _m: filename, text, count=1)
        if written != expected or described != 1 or filed != 1:
            raise _refuse(
                "the STEP writer produced a file this exporter does not recognise; refusing "
                "to release an assembly with unnamed parts or no watermark",
                subject="path",
                action="report",
            )
        staging.write_text(text, encoding="utf-8")

        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True)
        check = new_document()
        if reader.ReadFile(
            str(staging)
        ) != IFSelect_ReturnStatus.IFSelect_RetDone or not reader.Transfer(check):
            raise _refuse(
                "the written assembly does not read back", subject="path", action="report"
            )
        read_tool = XCAFDoc_DocumentTool.ShapeTool_s(check.Main())
        roots = TDF_LabelSequence()
        read_tool.GetFreeShapes(roots)
        children = TDF_LabelSequence()
        if roots.Length() == 1:
            read_tool.GetComponents_s(roots.Value(1), children, False)
        if roots.Length() != 1 or children.Length() != instances:
            raise _refuse(
                f"the written assembly reads back as {roots.Length()} root(s) with "
                f"{children.Length()} component(s), not one assembly of {instances}",
                subject="path",
                action="report",
            )
    return path
