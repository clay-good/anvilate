"""CAE handoff: a declared frame written as an input deck for the analyst's own solver.

Anvilate solves frames itself (:mod:`anvilate.frame`). An analyst on a program with a
commercial solver still rebuilds the same model by hand in that solver's input format, and
that retyping is where a support goes missing or a load lands in the wrong unit. This
writes the model once, from the declaration, in the two open text formats most solvers
read: a **keyword** deck (``.inp``) and a **bulk-data** deck (``.bdf``).

Four rules it keeps.

1. **The mesh is the frame.** One Euler-Bernoulli beam element per member (B33 in the
   keyword deck, CBAR in the bulk-data deck), between the member's own nodes, with the
   section and orientation the frame declares. That is the element Anvilate's solver
   uses, so the deck's answer is the one Anvilate gave, and a disagreement is a finding.
2. **One unit system, stated.** Newton, millimetre, second, tonne, megapascal. It is in
   the deck's header and in the sidecar; a value the format cannot hold is refused.
3. **Each frame is a load case.** Pass several frames that share their nodes, members and
   supports and differ in their loads, and each is one step (``.inp``) or one subcase
   (``.bdf``), named after it. Every load carries a comment naming its declaration.
4. **A deck is input, not evidence.** Its header says UNSOLVED INPUT, and nothing here
   reads a result back. No check on a card changes because a deck was written.

What a format cannot say is refused by name rather than approximated: the keyword deck's
beam releases are rotational only, so a released translation is refused there.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field

from ._models import StatableModel, each_one
from .frame import Frame, FrameMember, Freedom, _geometry_of
from .refusal import RefusalError, Remedy

__all__ = [
    "DECK_UNITS",
    "DeckError",
    "AnalysisDeck",
    "frame_deck",
]

#: The consistent unit system every deck is written in, by quantity.
DECK_UNITS: tuple[tuple[str, str], ...] = (
    ("force", "N"),
    ("length", "mm"),
    ("time", "s"),
    ("mass", "t"),
    ("stress", "MPa"),
    ("moment", "N*mm"),
    ("density", "t/mm**3"),
    ("distributed load", "N/mm"),
)

#: Standard gravity in mm/s**2, the value Anvilate's own solve applies (9.80665 m/s**2).
_GRAVITY_MM = 9806.65

_SOURCE = "Anvilate CAE handoff: the deck writer's own rules"

_UNSOLVED = (
    "UNSOLVED INPUT written by Anvilate. This deck is input to your solver, not evidence: "
    "no check passes on it until its results are read back."
)


class DeckError(RefusalError, ValueError):
    """A deck refused: a value the format cannot hold, or a model it cannot say."""


def _refuse(message: str, *, subject: str) -> DeckError:
    return DeckError(message, remedies=(Remedy(action="replace", subject=subject, source=_SOURCE),))


class AnalysisDeck(StatableModel):
    """A written deck: its format, its text, and what a reader needs to trust it.

    ``cases`` are the load cases in order, one step or subcase each. ``digest`` is the
    SHA-256 of ``text``. ``unsolved`` is always true: the deck is input, and a result
    from it counts only when read back.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    format: Literal["inp", "bdf"]
    text: str
    nodes: int = Field(ge=1)
    elements: int = Field(ge=1)
    cases: tuple[str, ...]
    units: tuple[tuple[str, str], ...] = DECK_UNITS
    digest: str
    unsolved: Literal[True] = True

    def sidecar(self) -> str:
        """The sidecar as JSON: the format, units, counts, cases and digest, not the text."""
        return json.dumps(
            {
                "format": self.format,
                "units": dict(self.units),
                "nodes": self.nodes,
                "elements": self.elements,
                "cases": list(self.cases),
                "sha256": self.digest,
                "unsolved": True,
                "note": _UNSOLVED,
            },
            indent=2,
        )

    def write(self, path: str | Path) -> tuple[Path, Path]:
        """Write the deck at ``path`` and its sidecar beside it as ``<path>.units.json``."""
        if not isinstance(path, (str, Path)):
            raise _refuse("path must be a file path", subject="path")
        target = Path(path)
        if target.suffix.lower() != f".{self.format}":
            raise _refuse(f"a {self.format} deck is written to a .{self.format} file; got "
                          f"{target.name}", subject="path")  # fmt: skip
        target.write_text(self.text, encoding="utf-8")
        side = target.with_name(target.name + ".units.json")
        side.write_text(self.sidecar() + "\n", encoding="utf-8")
        return target, side

    def __str__(self) -> str:
        return (
            f"{self.format} deck: {self.nodes} nodes, {self.elements} elements, "
            f"{len(self.cases)} load case(s) ({', '.join(self.cases)}); N-mm-s-t-MPa; "
            f"unsolved input, sha256 {self.digest[:12]}"
        )


def frame_deck(frames: Sequence[Frame], *, format: Literal["inp", "bdf"]) -> AnalysisDeck:
    """``frames`` as one input deck, each frame a load case.

    The first frame gives the model: its nodes, members, sections, materials and
    supports. Every other frame must declare the same ones and differ only in its loads
    and self weight; a frame that differs is refused, naming what differs, because a
    deck with one model cannot hold two. The same frames always give the same bytes: the
    deck carries no date, so its digest names its content.
    """
    frames = each_one(frames, Frame, named="frames")
    if not frames:
        raise _refuse("frames must hold at least one Frame, one per load case", subject="frames")
    if format not in ("inp", "bdf"):
        raise _refuse(f"format is 'inp' (keyword) or 'bdf' (bulk data); got {format!r}",
                      subject="format")  # fmt: skip
    model = frames[0]
    names = [f.name for f in frames]
    twice = sorted({n for n in names if names.count(n) > 1})
    if twice:
        raise _refuse(f"load cases {twice} are named twice; each frame names its case",
                      subject="frames")  # fmt: skip
    for other in frames[1:]:
        for field in ("nodes", "members", "supports"):
            if getattr(other, field) != getattr(model, field):
                raise _refuse(f"frame '{other.name}' declares different {field} from "
                              f"'{model.name}'; the load cases of one deck share one model "
                              "and differ only in their loads", subject="frames")  # fmt: skip
    for frame in frames:
        weighed = frame.self_weight and any(m.material.density is not None for m in model.members)
        if not (frame.node_loads or frame.member_loads or weighed):
            raise _refuse(f"load case '{frame.name}' applies no load; a step of nothing reads "
                          "as a case that was checked", subject="frames")  # fmt: skip
    writer = _inp if format == "inp" else _bdf
    text = writer(model, frames)
    return AnalysisDeck(
        format=format, text=text, nodes=len(model.nodes), elements=len(model.members),
        cases=tuple(names), digest=hashlib.sha256(text.encode()).hexdigest(),
    )  # fmt: skip


# --- values ----------------------------------------------------------------------------------


def _value(number: float, what: str) -> float:
    if not math.isfinite(number):
        raise _refuse(f"{what} is {number}, which no deck can hold", subject="frames")
    if number != 0 and not (1e-99 <= abs(number) < 1e99):
        raise _refuse(f"{what} is {number:g}, past what a 16-character field holds in "
                      "N-mm-s-t-MPa", subject="frames")  # fmt: skip
    return number


def _mm(member_or_node: object, attribute: str) -> float:
    quantity = getattr(member_or_node, attribute)
    return _value(quantity.to("mm").magnitude, f"{member_or_node}'s {attribute}")


def _section(member: FrameMember) -> tuple[float, float, float, float]:
    section = member.section
    return (
        _value(section.area.to("mm**2").magnitude, f"{section.name}'s area"),
        _value(section.second_moment_y.to("mm**4").magnitude, f"{section.name}'s Iy"),
        _value(section.second_moment_z.to("mm**4").magnitude, f"{section.name}'s Iz"),
        _value(section.torsion_constant.to("mm**4").magnitude, f"{section.name}'s J"),
    )


def _material(member: FrameMember) -> tuple[float, float, float | None]:
    material = member.material
    e = _value(material.elastic_modulus.to("MPa").magnitude, f"{material.name}'s E")
    g = _value(material.shear_modulus.to("MPa").magnitude, f"{material.name}'s G")
    rho = None
    if material.density is not None:
        rho = _value(material.density.to("t/mm**3").magnitude, f"{material.name}'s density")
    return e, g, rho


def _local_y(model: Frame, member: FrameMember) -> tuple[float, float, float]:
    """The member's local y axis, as Anvilate's solver defines it, in global axes."""
    points = {n.name: n.metres for n in model.nodes}
    ey = _geometry_of(member, points).rotation[1]
    return (ey[0], ey[1], ey[2])


def _loads(frame: Frame) -> tuple[list[tuple[str, int, float, str]], list[tuple[str, int, float]]]:
    """Each node load component as (node, dof 1-6, value, comment), and each member's
    distributed components as (member, direction 1-3, N/mm), both global."""
    point: list[tuple[str, int, float, str]] = []
    for index, load in enumerate(frame.node_loads):
        for dof, (name, unit) in enumerate(
            (("fx", "N"), ("fy", "N"), ("fz", "N"),
             ("mx", "N*mm"), ("my", "N*mm"), ("mz", "N*mm")), start=1,
        ):  # fmt: skip
            quantity = getattr(load, name)
            if quantity is not None:
                value = _value(quantity.to(unit).magnitude, f"node_loads[{index}].{name}")
                point.append((load.node, dof, value, f"node_loads[{index}].{name}"))
    spread: list[tuple[str, int, float]] = []
    for index, load in enumerate(frame.member_loads):
        for axis, name in enumerate(("wx", "wy", "wz"), start=1):
            quantity = getattr(load, name)
            if quantity is not None:
                value = _value(quantity.to("N/mm").magnitude, f"member_loads[{index}].{name}")
                spread.append((load.member, axis, value))
    return point, spread


def _header(model: Frame, mark: str) -> list[str]:
    units = ", ".join(f"{q} {u}" for q, u in DECK_UNITS)
    return [
        f"{mark} {_UNSOLVED}",
        f"{mark} Model: frame '{model.name}'.",
        f"{mark} Units: {units}.",
        f"{mark} Elements: one Euler-Bernoulli beam per member, the element Anvilate solves.",
    ]


# --- keyword deck ------------------------------------------------------------------------

#: A released set of rotations, as the keyword deck's release combination names it. M1 is
#: about the section's first axis (local y here), M2 about the second (local z), T torsion.
_RELEASE_NAMES = {
    frozenset({Freedom.RY}): "M1",
    frozenset({Freedom.RZ}): "M2",
    frozenset({Freedom.RX}): "T",
    frozenset({Freedom.RY, Freedom.RZ}): "M1-M2",
    frozenset({Freedom.RY, Freedom.RX}): "M1-T",
    frozenset({Freedom.RZ, Freedom.RX}): "M2-T",
    frozenset({Freedom.RX, Freedom.RY, Freedom.RZ}): "ALLM",
}


def _f(number: float) -> str:
    """A value to twelve significant figures: past that is unit-conversion noise, and a
    direction cosine of 6e-17 is a zero that reads as a number."""
    tidy = float(f"{number:.12g}")
    return repr(0.0 if abs(tidy) < 1e-12 and abs(number) < 1e-12 else tidy)


def _inp(model: Frame, frames: Sequence[Frame]) -> str:
    node_id = {n.name: i for i, n in enumerate(model.nodes, start=1)}
    lines = ["*HEADING", f"Frame {model.name}: {_UNSOLVED}"]
    lines += _header(model, "**")
    # The names first: a comment inside a data block ends it for some readers.
    lines += [f"** node {node_id[n.name]} = {n.name}" for n in model.nodes]
    lines.append("*NODE, NSET=NALL")
    for node in model.nodes:
        lines.append(f"{node_id[node.name]}, {_f(_mm(node, 'x'))}, {_f(_mm(node, 'y'))}, "
                     f"{_f(_mm(node, 'z'))}")  # fmt: skip
    heavy: list[str] = []
    releases: list[str] = []
    for k, member in enumerate(model.members, start=1):
        elset = f"M{k}"
        a, iy, iz, j = _section(member)
        e, g, rho = _material(member)
        n1 = _local_y(model, member)
        lines.append(f"** element {k} = member {member.name}; section {member.section.name} "
                     f"({member.section.source}); material {member.material.name} "
                     f"({member.material.source})")  # fmt: skip
        lines.append(f"*ELEMENT, TYPE=B33, ELSET={elset}")
        lines.append(f"{k}, {node_id[member.start]}, {node_id[member.end]}")
        density = "" if rho is None else f", DENSITY={_f(rho)}"
        lines.append(f"*BEAM GENERAL SECTION, ELSET={elset}, SECTION=GENERAL{density}")
        lines.append(f"{_f(a)}, {_f(iy)}, 0.0, {_f(iz)}, {_f(j)}")
        lines.append(", ".join(_f(c) for c in n1))
        lines.append(f"{_f(e)}, {_f(g)}")
        if rho is not None:
            heavy.append(str(k))
        for released, end in ((member.releases_start, "S1"), (member.releases_end, "S2")):
            if not released:
                continue
            name = _RELEASE_NAMES.get(frozenset(released))
            if name is None:
                moved = sorted(f.value for f in released if f not in _ROTATIONS)
                raise _refuse(f"member '{member.name}' releases {moved} at its "
                              f"{'start' if end == 'S1' else 'end'}; a keyword deck releases "
                              "rotations only. Write a bdf deck, whose pin flags take all "
                              "six", subject="format")  # fmt: skip
            releases.append(f"{k}, {end}, {name}")
    if releases:
        lines.append("*RELEASE")
        lines += releases
    if heavy:
        lines.append("*ELSET, ELSET=WEIGHED")
        lines += [", ".join(heavy[i : i + 8]) for i in range(0, len(heavy), 8)]
    if model.supports:
        lines.append("*BOUNDARY")
        for support in model.supports:
            for freedom in support.restrained:
                dof = freedom.index + 1
                lines.append(f"{node_id[support.node]}, {dof}, {dof}")
    member_id = {m.name: k for k, m in enumerate(model.members, start=1)}
    for frame in frames:
        point, spread = _loads(frame)
        lines.append(f"** load case {frame.name}")
        lines.append("*STEP")
        lines.append("*STATIC")
        # OP=NEW in every step: a step otherwise inherits the loads of the one before, and
        # each frame is its own case, not an increment on the last.
        lines.append("*CLOAD, OP=NEW")
        for node, dof, value, comment in point:
            lines.append(f"** {comment} at node {node}")
            lines.append(f"{node_id[node]}, {dof}, {_f(value)}")
        lines.append("*DLOAD, OP=NEW")
        for index, (member, axis, value) in enumerate(spread):
            lines.append(f"** member_loads on {member} ({index})")
            lines.append(f"{member_id[member]}, P{'XYZ'[axis - 1]}, {_f(value)}")
        if frame.self_weight and heavy:
            lines.append("** self_weight: gravity along -Z on every member with a density")
            lines.append(f"WEIGHED, GRAV, {_f(_GRAVITY_MM)}, 0.0, 0.0, -1.0")
        lines.append("*NODE PRINT, NSET=NALL")
        lines.append("U, RF")
        lines.append("*END STEP")
    return "\n".join(lines) + "\n"


_ROTATIONS = (Freedom.RX, Freedom.RY, Freedom.RZ)


# --- bulk-data deck ----------------------------------------------------------------------


def _field(value: int | float | str | None) -> str:
    if value is None:
        return " " * 16
    if isinstance(value, int):
        return f"{value:>16d}"
    if isinstance(value, float):
        return f"{float(_f(value)):16.9E}"
    return f"{value:>16s}"


def _card(name: str, *fields: int | float | str | None) -> list[str]:
    """One large-field card: the name in eight columns, then four sixteen-column fields a
    line, each continuation line opening with an asterisk."""
    lines = []
    rows = [fields[i : i + 4] for i in range(0, len(fields), 4)] or [()]
    for n, row in enumerate(rows):
        lead = f"{name + '*':<8s}" if n == 0 else f"{'*':<8s}"
        lines.append((lead + "".join(_field(v) for v in row)).rstrip())
    return lines


def _digits(freedoms: Sequence[Freedom]) -> str:
    """Freedoms as a component string, 1 to 6 in order: ux uy uz rx ry rz."""
    return "".join(str(f.index + 1) for f in sorted(freedoms, key=lambda f: f.index))


def _bdf(model: Frame, frames: Sequence[Frame]) -> str:
    node_id = {n.name: i for i, n in enumerate(model.nodes, start=1)}
    lines = _header(model, "$")
    lines += ["SOL 101", "CEND", f"TITLE = {model.name}: unsolved input written by Anvilate",
              "ECHO = NONE", "DISPLACEMENT = ALL", "SPCFORCES = ALL", "FORCE = ALL"]  # fmt: skip
    if model.supports:
        lines.append("SPC = 1")
    for k, frame in enumerate(frames, start=1):
        lines += [f"SUBCASE {k}", f"  LABEL = {frame.name}", f"  LOAD = {k}"]
    lines.append("BEGIN BULK")
    for node in model.nodes:
        lines.append(f"$ node {node_id[node.name]} = {node.name}")
        lines += _card("GRID", node_id[node.name], None,
                       _mm(node, "x"), _mm(node, "y"), _mm(node, "z"))  # fmt: skip
    materials: dict[tuple[float, float, float | None], int] = {}
    properties: dict[tuple[int, float, float, float, float], int] = {}
    for k, member in enumerate(model.members, start=1):
        e, g, rho = _material(member)
        mid = materials.get((e, g, rho))
        if mid is None:
            mid = materials[(e, g, rho)] = len(materials) + 1
            lines.append(f"$ material {mid} = {member.material.name} ({member.material.source})")
            lines += _card("MAT1", mid, e, g, None, rho)
        a, iy, iz, j = _section(member)
        # A bar's I1 bends it in its plane 1, the plane of its axis and its orientation
        # vector: about its z axis. Its I2 is about its y axis.
        key = (mid, a, iz, iy, j)
        pid = properties.get(key)
        if pid is None:
            pid = properties[key] = len(properties) + 1
            lines.append(f"$ property {pid} = section {member.section.name} "
                         f"({member.section.source})")  # fmt: skip
            lines += _card("PBAR", pid, mid, a, iz, iy, j)
        v = _local_y(model, member)
        pins = []
        for released in (member.releases_start, member.releases_end):
            digits = _digits(released)
            pins.append(int(digits) if digits else None)
        lines.append(f"$ element {k} = member {member.name}")
        tail = (pins[0], pins[1]) if any(p is not None for p in pins) else ()
        lines += _card("CBAR", k, pid, node_id[member.start], node_id[member.end],
                       v[0], v[1], v[2], None, *tail)  # fmt: skip
    for support in model.supports:
        digits = _digits(support.restrained)
        lines.append(f"$ support at {support.node}")
        lines += _card("SPC1", 1, int(digits), node_id[support.node])
    member_id = {m.name: k for k, m in enumerate(model.members, start=1)}
    heavy = any(m.material.density is not None for m in model.members)
    for k, frame in enumerate(frames, start=1):
        simple, gravity = 100 + k, 200 + k
        point, spread = _loads(frame)
        lines.append(f"$ load case {k} = {frame.name}")
        sets: list[int] = []
        for node, dof, value, comment in point:
            lines.append(f"$ {comment} at node {node}")
            direction = [0.0, 0.0, 0.0]
            direction[(dof - 1) % 3] = 1.0
            lines += _card("FORCE" if dof <= 3 else "MOMENT", simple, node_id[node], 0,
                           value, *direction)  # fmt: skip
        for index, (member, axis, value) in enumerate(spread):
            lines.append(f"$ member_loads on {member} ({index})")
            lines += _card("PLOAD1", simple, member_id[member], f"F{'XYZ'[axis - 1]}", "FR",
                           0.0, value, 1.0, value)  # fmt: skip
        if point or spread:
            sets.append(simple)
        if frame.self_weight and heavy:
            # A gravity entry may not share its set with simple loads; a LOAD entry adds them.
            lines.append("$ self_weight: gravity along -Z on every member with a density")
            lines += _card("GRAV", gravity, 0, _GRAVITY_MM, 0.0, 0.0, -1.0)
            sets.append(gravity)
        combined: list[int | float] = [1.0]
        for each in sets:
            combined += [1.0, each]
        lines += _card("LOAD", k, *combined)
    lines.append("ENDDATA")
    return "\n".join(lines) + "\n"
