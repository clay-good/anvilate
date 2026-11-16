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

import csv
import hashlib
import io
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from ._models import Named, StatableModel, each_one
from .frame import Frame, FrameMember, Freedom, _geometry_of
from .refusal import RefusalError, Remedy
from .units import Quantity

__all__ = [
    "DECK_UNITS",
    "DeckError",
    "AnalysisDeck",
    "frame_deck",
    "RESULT_UNITS",
    "ResultSource",
    "InterfaceLoad",
    "CaseBalance",
    "InterfaceImport",
    "read_interface_forces",
    "ImportedGroupCase",
    "ImportedGroupResult",
    "fastener_group_on_import",
    "RegionPeak",
    "RegionImport",
    "RegionComparison",
    "read_region_peaks",
    "compare_region_peak",
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


# --- results read back -------------------------------------------------------------------

#: The unit systems an imported result may declare, as its force and length units.
RESULT_UNITS: tuple[tuple[str, str, str], ...] = (
    ("N-mm", "N", "mm"),
    ("N-m", "N", "m"),
    ("kN-mm", "kN", "mm"),
    ("kN-m", "kN", "m"),
    ("lbf-in", "lbf", "inch"),
    ("lbf-ft", "lbf", "foot"),
    ("kip-in", "kip", "inch"),
    ("kip-ft", "kip", "foot"),
)
_SYSTEMS = {name: (force, length) for name, force, length in RESULT_UNITS}
_COLUMNS = ("case", "interface", "point", "x", "y", "z", "fx", "fy", "fz", "mx", "my", "mz")


class ResultSource(StatableModel):
    """Where an imported result came from, as the import declared it and as its bytes are.

    ``sha256`` is the file's own digest. ``solver`` and ``version`` are as declared:
    nothing here can check them, so they are recorded and named, not vouched for.
    ``coordinate_system`` is the one the forces are in; nothing here rotates them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file: Named
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    solver: Named
    version: Named
    units: Named
    coordinate_system: Named

    @field_validator("units")
    @classmethod
    def _a_system(cls, value: str) -> str:
        if value not in _SYSTEMS:
            raise _refuse(f"units {value!r} is not one of {', '.join(_SYSTEMS)}",
                          subject="units")  # fmt: skip
        return value

    def __str__(self) -> str:
        return (f"{self.file} (sha256 {self.sha256[:12]}) from {self.solver} {self.version}, "
                f"{self.units}, in {self.coordinate_system}")  # fmt: skip


class InterfaceLoad(StatableModel):
    """The resultant at one interface in one load case, in N and N*mm.

    ``moment_nmm`` is about ``about_mm``, the centroid of the interface's points, so it
    is the moment a joint screen at that interface reads. ``points`` counts the rows
    summed into it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case: Named
    interface: Named
    force_n: tuple[float, float, float]
    moment_nmm: tuple[float, float, float]
    about_mm: tuple[float, float, float]
    points: int = Field(ge=1)

    def __str__(self) -> str:
        f = ", ".join(f"{v:.4g}" for v in self.force_n)
        m = ", ".join(f"{v:.4g}" for v in self.moment_nmm)
        return f"{self.case} at {self.interface}: F ({f}) N, M ({m}) N*mm"


class CaseBalance(StatableModel):
    """One case's free body: what its forces and moments leave over, against its tolerance.

    ``residual_force_n`` is the length of the summed force; ``residual_moment_nmm`` that
    of the summed moment about the centroid of every point in the case. Each is held to
    ``tolerance`` times the largest force, or the largest moment, any one row brings.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case: Named
    residual_force_n: float
    residual_moment_nmm: float
    largest_force_n: float
    largest_moment_nmm: float
    tolerance: float
    balanced: bool

    def __str__(self) -> str:
        verdict = "balances" if self.balanced else "DOES NOT BALANCE"
        return (f"{self.case} {verdict}: residual {self.residual_force_n:.4g} N against the "
                f"largest {self.largest_force_n:.4g} N, {self.residual_moment_nmm:.4g} N*mm "
                f"against {self.largest_moment_nmm:.4g} N*mm, at {self.tolerance:g}")  # fmt: skip


class InterfaceImport(StatableModel):
    """Interface loads read back from the user's solver, with where they came from.

    One :class:`InterfaceLoad` per case and interface, and one :class:`CaseBalance` per
    case. ``unbalanced`` names the cases whose free body leaves more than the tolerance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: ResultSource
    loads: tuple[InterfaceLoad, ...]
    balance: tuple[CaseBalance, ...]

    @property
    def cases(self) -> tuple[str, ...]:
        """The load cases, in the order the file gives them."""
        return tuple(b.case for b in self.balance)

    @property
    def unbalanced(self) -> tuple[str, ...]:
        """The cases whose free body does not balance within the tolerance."""
        return tuple(b.case for b in self.balance if not b.balanced)

    def at(self, interface: str) -> tuple[InterfaceLoad, ...]:
        """Every case's load at ``interface``, in case order."""
        found = tuple(load for load in self.loads if load.interface == interface)
        if not found:
            names = sorted({load.interface for load in self.loads})
            raise _refuse(f"no load was read at interface {interface!r}; the file holds "
                          f"{', '.join(names)}", subject="interface")  # fmt: skip
        return found

    def __str__(self) -> str:
        off = f"; unbalanced: {', '.join(self.unbalanced)}" if self.unbalanced else ""
        interfaces = len({load.interface for load in self.loads})
        return (f"{len(self.balance)} case(s) at {interfaces} interface(s) from "
                f"{self.source}{off}")  # fmt: skip


def read_interface_forces(
    path: str | Path,
    *,
    solver: str,
    version: str,
    units: str | None,
    coordinate_system: str,
    tolerance: float = 1e-3,
) -> InterfaceImport:
    """Interface loads read from a CSV of the forces on one free body, case by case.

    Columns: ``case, interface, point, x, y, z, fx, fy, fz, mx, my, mz``. Each row is
    the force and moment acting **on the free body** at one point: the forces at its cut
    interfaces, and any load applied to it under an interface name of its own. Every
    solver's grid-point force output can be written this way.

    ``units`` is the system the file is in, one of :data:`RESULT_UNITS`; a file read
    without one is refused, naming it. The rows are converted to N and N*mm, and each
    interface's resultant is taken about the centroid of its own points. Each case's
    free body is held to ``tolerance``: a case whose forces do not sum to zero is
    reported with its residual, never dropped and never corrected.
    """
    if not isinstance(path, (str, Path)):
        raise _refuse("path must be the path of a CSV file", subject="path")
    name = Path(path).name
    if units is None:
        raise _refuse(f"{name} declares no unit system; a result file states its own, one of "
                      f"{', '.join(_SYSTEMS)}", subject="units")  # fmt: skip
    if units not in _SYSTEMS:
        raise _refuse(f"{name}: units {units!r} is not one of {', '.join(_SYSTEMS)}",
                      subject="units")  # fmt: skip
    if not isinstance(tolerance, (int, float)) or not 0 < tolerance < 1:
        raise _refuse(f"tolerance is a fraction between 0 and 1; got {tolerance!r}",
                      subject="tolerance")  # fmt: skip
    raw = Path(path).read_bytes()
    source = ResultSource(file=name, sha256=hashlib.sha256(raw).hexdigest(), solver=solver,
                          version=version, units=units,
                          coordinate_system=coordinate_system)  # fmt: skip
    force_unit, length_unit = _SYSTEMS[units]
    to_n = Quantity(magnitude=1.0, unit=force_unit).to("N").magnitude
    to_mm = Quantity(magnitude=1.0, unit=length_unit).to("mm").magnitude
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as failure:
        raise _refuse(f"{name} is not UTF-8 text", subject="path") from failure
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip().lower() for h in (reader.fieldnames or ())]
    missing = [c for c in _COLUMNS if c not in header]
    if missing:
        raise _refuse(f"{name} has no {', '.join(missing)} column; its header is "
                      f"{reader.fieldnames}", subject="path")  # fmt: skip
    reader.fieldnames = header
    rows: dict[str, list[tuple[str, list[float], list[float], list[float]]]] = {}
    for line, row in enumerate(reader, start=2):
        values = []
        for column in _COLUMNS[3:]:
            cell = (row.get(column) or "").strip()
            try:
                number = float(cell)
            except ValueError as failure:
                raise _refuse(f"{name} line {line}: {column} {cell!r} is not a number",
                              subject="path") from failure  # fmt: skip
            if not math.isfinite(number):
                raise _refuse(f"{name} line {line}: {column} is {cell}", subject="path")
            values.append(number)
        case, interface = (row.get("case") or "").strip(), (row.get("interface") or "").strip()
        if not case or not interface:
            raise _refuse(f"{name} line {line} names no case or no interface", subject="path")
        point = [v * to_mm for v in values[0:3]]
        force = [v * to_n for v in values[3:6]]
        moment = [v * to_n * to_mm for v in values[6:9]]
        rows.setdefault(case, []).append((interface, point, force, moment))
    if not rows:
        raise _refuse(f"{name} holds a header and no rows", subject="path")
    loads, balance = [], []
    for case, entries in rows.items():
        for interface in dict.fromkeys(e[0] for e in entries):
            mine = [e for e in entries if e[0] == interface]
            centre = _centroid([e[1] for e in mine])
            f, m = _resultant(mine, centre)
            loads.append(InterfaceLoad(case=case, interface=interface,
                                       force_n=_rounded(f), moment_nmm=_rounded(m),
                                       about_mm=_rounded(centre), points=len(mine)))  # fmt: skip
        balance.append(_balance(case, entries, tolerance))
    return InterfaceImport(source=source, loads=tuple(loads), balance=tuple(balance))


def _centroid(points: list[list[float]]) -> list[float]:
    return [sum(p[i] for p in points) / len(points) for i in range(3)]


def _arm(point: list[float], centre: list[float], force: list[float]) -> list[float]:
    r = [point[i] - centre[i] for i in range(3)]
    return [r[1] * force[2] - r[2] * force[1], r[2] * force[0] - r[0] * force[2],
            r[0] * force[1] - r[1] * force[0]]  # fmt: skip


def _resultant(entries: list, centre: list[float]) -> tuple[list[float], list[float]]:
    force = [sum(e[2][i] for e in entries) for i in range(3)]
    moment = [0.0, 0.0, 0.0]
    for _interface, point, f, m in entries:
        turn = _arm(point, centre, f)
        moment = [moment[i] + m[i] + turn[i] for i in range(3)]
    return force, moment


def _balance(case: str, entries: list, tolerance: float) -> CaseBalance:
    centre = _centroid([e[1] for e in entries])
    force, moment = _resultant(entries, centre)
    largest_f = max(math.hypot(*e[2]) for e in entries)
    largest_m = max(math.hypot(*e[3]) + math.hypot(*_arm(e[1], centre, e[2])) for e in entries)
    residual_f, residual_m = math.hypot(*force), math.hypot(*moment)
    balanced = residual_f <= tolerance * largest_f and residual_m <= tolerance * largest_m
    return CaseBalance(case=case, residual_force_n=residual_f, residual_moment_nmm=residual_m,
                       largest_force_n=largest_f, largest_moment_nmm=largest_m,
                       tolerance=tolerance, balanced=balanced)  # fmt: skip


def _rounded(vector: list[float]) -> tuple[float, float, float]:
    return (round(vector[0], 9), round(vector[1], 9), round(vector[2], 9))


# --- joint screens on imported loads -----------------------------------------------------


class ImportedGroupCase(StatableModel):
    """One imported case on a fastener pattern: the loads it put there, and the verdict.

    Loads are on the pattern, in N and N*mm, about its weighted centroid. ``evaluated`` is
    false, with ``note`` saying why, for a case whose free body did not balance or that
    carries a moment about an in-plane axis, which the group method does not distribute.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case: Named
    evaluated: bool
    note: str = Field(default="", max_length=400)
    shear_x_n: float
    shear_y_n: float
    twist_nmm: float
    tension_n: float
    out_of_plane_nmm: float
    governing: str | None = None
    governing_index: float | None = None
    governing_shear_n: float | None = None


class ImportedGroupResult(StatableModel):
    """A fastener pattern screened case by case on loads read back from a solver.

    ``governing_case`` is the evaluated case with the highest NASA-STD-5020B interaction
    index; ``not_evaluated`` names the rest. ``source`` is where every load came from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    interface: Named
    source: ResultSource
    cases: tuple[ImportedGroupCase, ...]
    governing_case: str | None
    governing_index: float | None
    not_evaluated: tuple[str, ...] = ()

    def __str__(self) -> str:
        if self.governing_case is None:
            head = f"{self.interface}: no case evaluated"
        else:
            worst = next(c for c in self.cases if c.case == self.governing_case)
            head = (f"{self.interface}: case {self.governing_case} governs, fastener "
                    f"{worst.governing} at interaction {self.governing_index:.3f} "
                    "(NASA-STD-5020B, without the bending term)")  # fmt: skip
        skipped = f"; not evaluated: {', '.join(self.not_evaluated)}" if self.not_evaluated else ""
        return f"{head}{skipped}; loads from {self.source}"


def fastener_group_on_import(
    fasteners: Sequence[Any],
    imported: InterfaceImport,
    interface: str,
    *,
    coordinate_system: str,
    away: Literal["+z", "-z"],
) -> ImportedGroupResult:
    """Each imported case's load at ``interface``, shared over a fastener pattern.

    The pattern lies in the x-y plane of ``coordinate_system``, its fasteners placed in
    that system, and it must be the system the import declared: nothing here rotates a
    load, so a different one is refused naming both. ``away`` is the direction the joined
    part leaves the pattern; the tension on the pattern is the pull along it, and a push
    bears on the plates and carries none.

    An imported load is the force **on** the free body at the interface, so the pattern
    carries its opposite. The in-plane shear and the twist about z go to
    :func:`~anvilate.analysis.fastener_group.fastener_group_loads`, which shares them by
    NASA TM X-73305 §B1.1.1 and checks each fastener by NASA-STD-5020B §4.4.4. A case
    whose free body did not balance, or that carries a moment about an in-plane axis
    beyond the import's own tolerance, is not evaluated and says why.
    """
    from .analysis.fastener_group import GroupFastener, fastener_group_loads

    group = each_one(fasteners, GroupFastener, named="fasteners")
    if not group:
        raise _refuse("fasteners must hold the pattern's fasteners", subject="fasteners")
    if not isinstance(imported, InterfaceImport):
        raise _refuse("imported must be an InterfaceImport from read_interface_forces",
                      subject="imported")  # fmt: skip
    if coordinate_system != imported.source.coordinate_system:
        raise _refuse(f"the pattern is in {coordinate_system!r} and the loads in "
                      f"{imported.source.coordinate_system!r}; nothing here rotates a load "
                      "between them", subject="coordinate_system")  # fmt: skip
    if away not in ("+z", "-z"):
        raise _refuse(f"away is '+z' or '-z'; got {away!r}", subject="away")
    loads = imported.at(interface)
    balance = {b.case: b for b in imported.balance}
    xs = [f.x.to("mm").magnitude for f in group]
    ys = [f.y.to("mm").magnitude for f in group]
    weights = [f._weight(by_stiffness=all(g.stiffness is not None for g in group)) for f in group]
    total = sum(weights)
    centre = [sum(w * x for w, x in zip(weights, xs, strict=True)) / total,
              sum(w * y for w, y in zip(weights, ys, strict=True)) / total, 0.0]  # fmt: skip
    normal = 1.0 if away == "+z" else -1.0
    cases = []
    for load in loads:
        # The pattern carries the opposite of the force on the free body, moved to its
        # centroid. The z of that centroid is taken as the interface's own.
        centre[2] = load.about_mm[2]
        force = [-v for v in load.force_n]
        moment = [-v for v in load.moment_nmm]
        moment = [m + a for m, a in zip(moment, _arm(list(load.about_mm), centre, force),
                                        strict=True)]  # fmt: skip
        tension = max(0.0, force[2] * normal)
        prying = math.hypot(moment[0], moment[1])
        said = balance[load.case]
        common: dict[str, Any] = {
            "case": load.case, "shear_x_n": force[0], "shear_y_n": force[1],
            "twist_nmm": moment[2], "tension_n": tension, "out_of_plane_nmm": prying,
        }  # fmt: skip
        if not said.balanced:
            short = f"its free body leaves {said.residual_force_n:.4g} N unbalanced"
            cases.append(ImportedGroupCase(evaluated=False, note=short, **common))
            continue
        if prying > said.tolerance * said.largest_moment_nmm:
            cases.append(ImportedGroupCase(evaluated=False, note=(
                f"it carries {prying:.4g} N*mm about an in-plane axis, which the group "
                "method does not distribute into the fasteners"), **common))  # fmt: skip
            continue
        result = fastener_group_loads(
            group, shear_x=Quantity(magnitude=force[0], unit="N"),
            shear_y=Quantity(magnitude=force[1], unit="N"),
            moment=Quantity(magnitude=moment[2], unit="N*mm"),
            load_x=Quantity(magnitude=centre[0], unit="mm"),
            load_y=Quantity(magnitude=centre[1], unit="mm"),
            tension=Quantity(magnitude=tension, unit="N"),
        )  # fmt: skip
        worst = next(f for f in result.fasteners if f.name == result.governing)
        cases.append(ImportedGroupCase(evaluated=True, governing=result.governing,
                                       governing_index=result.governing_index,
                                       governing_shear_n=worst.shear, **common))  # fmt: skip
    evaluated = [c for c in cases if c.evaluated]
    top = max(evaluated, key=lambda c: c.governing_index or 0.0) if evaluated else None
    return ImportedGroupResult(
        interface=interface, source=imported.source, cases=tuple(cases),
        governing_case=top.case if top else None,
        governing_index=top.governing_index if top else None,
        not_evaluated=tuple(c.case for c in cases if not c.evaluated),
    )  # fmt: skip


# --- peak values in a region -------------------------------------------------------------

_QUANTITIES = ("stress", "strain", "displacement")


class RegionPeak(StatableModel):
    """One peak value a solver reported in a named region, in one case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case: Named
    region: Named
    quantity: Literal["stress", "strain", "displacement"]
    value: Quantity

    def __str__(self) -> str:
        return f"{self.case}: peak {self.quantity} {self.value} in {self.region}"


class RegionImport(StatableModel):
    """Peak values read back from the user's solver, with where they came from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: ResultSource
    peaks: tuple[RegionPeak, ...] = Field(min_length=1)

    def __str__(self) -> str:
        return f"{len(self.peaks)} peak value(s) from {self.source}"


class RegionComparison(StatableModel):
    """An imported peak as a cited input: its own verdict, and the hand estimate beside it.

    ``within_limit`` is the imported value held to ``limit`` when one is given (a
    displacement or stress at most it), and ``None`` otherwise. ``difference`` is the
    imported value over the estimate, less one; ``agrees`` is whether its size is within
    ``tolerance``. Neither value replaces the other: a disagreement is a finding about one
    of them, and both are named.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case: Named
    region: Named
    quantity: Named
    imported: Quantity
    estimate: Quantity
    estimate_source: Named
    difference: float
    tolerance: float
    agrees: bool
    limit: Quantity | None = None
    limit_source: str | None = None
    within_limit: bool | None = None
    source: ResultSource

    def __str__(self) -> str:
        side = "above" if self.difference > 0 else "below"
        said = (f"{self.case}, {self.region}: the solver's peak {self.quantity} {self.imported} "
                f"is {abs(self.difference):.0%} {side} the estimate {self.estimate} "
                f"({self.estimate_source})")  # fmt: skip
        said += (", within the stated tolerance" if self.agrees else
                 f": they DISAGREE past the {self.tolerance:.0%} tolerance")  # fmt: skip
        if self.limit is not None:
            verdict = "within" if self.within_limit else "PAST"
            said += f"; {verdict} the limit {self.limit} ({self.limit_source})"
        return f"{said}; from {self.source}"


def read_region_peaks(
    path: str | Path,
    *,
    solver: str,
    version: str,
    units: str | None,
    coordinate_system: str,
) -> RegionImport:
    """Peak values read from a CSV with ``case, region, quantity, value`` columns.

    ``quantity`` is ``stress``, ``strain`` or ``displacement``. Stress is in the declared
    system's force over length squared, displacement in its length, strain a ratio. A
    file without its unit system is refused, naming it, as for interface forces.
    """
    if not isinstance(path, (str, Path)):
        raise _refuse("path must be the path of a CSV file", subject="path")
    name = Path(path).name
    if units is None:
        raise _refuse(f"{name} declares no unit system; a result file states its own, one of "
                      f"{', '.join(_SYSTEMS)}", subject="units")  # fmt: skip
    if units not in _SYSTEMS:
        raise _refuse(f"{name}: units {units!r} is not one of {', '.join(_SYSTEMS)}",
                      subject="units")  # fmt: skip
    raw = Path(path).read_bytes()
    source = ResultSource(file=name, sha256=hashlib.sha256(raw).hexdigest(), solver=solver,
                          version=version, units=units,
                          coordinate_system=coordinate_system)  # fmt: skip
    force, length = _SYSTEMS[units]
    unit_of = {"stress": f"{force}/{length}**2", "strain": "dimensionless",
               "displacement": length}  # fmt: skip
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as failure:
        raise _refuse(f"{name} is not UTF-8 text", subject="path") from failure
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip().lower() for h in (reader.fieldnames or ())]
    missing = [c for c in ("case", "region", "quantity", "value") if c not in header]
    if missing:
        raise _refuse(f"{name} has no {', '.join(missing)} column; its header is "
                      f"{reader.fieldnames}", subject="path")  # fmt: skip
    reader.fieldnames = header
    peaks = []
    for line, row in enumerate(reader, start=2):
        case, region = (row.get("case") or "").strip(), (row.get("region") or "").strip()
        quantity = (row.get("quantity") or "").strip().lower()
        cell = (row.get("value") or "").strip()
        if not case or not region:
            raise _refuse(f"{name} line {line} names no case or no region", subject="path")
        if quantity not in _QUANTITIES:
            raise _refuse(f"{name} line {line}: quantity {quantity!r} is one of "
                          f"{', '.join(_QUANTITIES)}", subject="path")  # fmt: skip
        try:
            number = float(cell)
        except ValueError as failure:
            raise _refuse(f"{name} line {line}: value {cell!r} is not a number",
                          subject="path") from failure  # fmt: skip
        if not math.isfinite(number):
            raise _refuse(f"{name} line {line}: value is {cell}", subject="path")
        value = Quantity(magnitude=number, unit=unit_of[quantity])
        peaks.append(RegionPeak.model_validate(
            {"case": case, "region": region, "quantity": quantity, "value": value}))  # fmt: skip
    if not peaks:
        raise _refuse(f"{name} holds a header and no rows", subject="path")
    return RegionImport(source=source, peaks=tuple(peaks))


def compare_region_peak(
    imported: RegionImport,
    *,
    region: str,
    quantity: Literal["stress", "strain", "displacement"],
    estimate: Quantity,
    estimate_source: str,
    tolerance: float,
    case: str | None = None,
    limit: Quantity | None = None,
    limit_source: str | None = None,
) -> RegionComparison:
    """An imported peak beside the closed-form estimate for the same region.

    ``case`` picks one case; left out, the case with the largest magnitude governs.
    ``tolerance`` is the fraction the two may differ by and still agree, and is the
    caller's to state. ``limit``, with its ``limit_source``, gives the imported value a
    verdict of its own; it is never applied to the estimate in its place.
    """
    if not isinstance(imported, RegionImport):
        raise _refuse("imported must be a RegionImport from read_region_peaks",
                      subject="imported")  # fmt: skip
    if not isinstance(tolerance, (int, float)) or not 0 < tolerance < 1:
        raise _refuse(f"tolerance is a fraction between 0 and 1; got {tolerance!r}",
                      subject="tolerance")  # fmt: skip
    found = [p for p in imported.peaks if p.region == region and p.quantity == quantity
             and (case is None or p.case == case)]  # fmt: skip
    if not found:
        held = sorted({f"{p.region} {p.quantity}" for p in imported.peaks})
        raise _refuse(f"no peak {quantity} was read in region {region!r}"
                      + (f" for case {case!r}" if case else "") + f"; the file holds "
                      f"{', '.join(held)}", subject="region")  # fmt: skip
    peak = max(found, key=lambda p: abs(p.value.magnitude))
    if not isinstance(estimate, Quantity) or not estimate.has_dimension(
        str(peak.value.pint.dimensionality)
    ):
        raise _refuse(f"estimate must be a quantity of the same kind as the peak "
                      f"{quantity} ({peak.value.unit}); got {estimate!r}",
                      subject="estimate")  # fmt: skip
    if not isinstance(estimate_source, str) or not estimate_source.strip():
        raise _refuse("estimate_source names the check the estimate came from",
                      subject="estimate_source")  # fmt: skip
    expected = estimate.to(peak.value.unit).magnitude
    if expected == 0 or not math.isfinite(expected):
        raise _refuse(f"the estimate is {estimate}; a ratio to it needs a finite, nonzero "
                      "value", subject="estimate")  # fmt: skip
    difference = abs(peak.value.magnitude) / abs(expected) - 1.0
    within = None
    if limit is not None:
        if not isinstance(limit, Quantity) or not limit.has_dimension(
            str(peak.value.pint.dimensionality)
        ):
            raise _refuse(f"limit must be a quantity of the same kind as the peak {quantity}",
                          subject="limit")  # fmt: skip
        if not limit_source:
            raise _refuse("a limit names its source", subject="limit_source")
        within = abs(peak.value.magnitude) <= limit.to(peak.value.unit).magnitude
    return RegionComparison(
        case=peak.case, region=region, quantity=quantity, imported=peak.value,
        estimate=estimate, estimate_source=estimate_source, difference=difference,
        tolerance=tolerance, agrees=abs(difference) <= tolerance, limit=limit,
        limit_source=limit_source, within_limit=within, source=imported.source,
    )  # fmt: skip
