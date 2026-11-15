"""Frame analysis: the member forces a frame carries, solved rather than typed.

Every member check in this library takes the force in that member as an input. For a
simply supported beam the agent can work it out; for a portal frame, a skid or a
two-bay rack it cannot, and until now the only way in was
:mod:`anvilate.interop`'s doorway for forces an external solver produced.
``product-screening`` is correct to refuse an indeterminate load path, and it had nothing
to offer instead. This is the something: a first-order, three-dimensional, linear-elastic
direct-stiffness solve, in the core, in pure Python.

Four rules it keeps.

1. **First order by default, and second order is a declaration.** A code's member checks
   assume first-order forces unless the code's own amplification is applied (AISC 360
   Appendix 8 B1/B2, EN 1993-1-1 §5.2). Solving P-Δ silently and then applying the
   code's amplifier would double count, so the basis travels with every force record and
   the check is told which it has.
2. **A mechanism is named, never solved around.** A frame with a free mode has no
   unique answer; the solve reports which node and which freedom moves under no
   stiffness rather than returning the numbers a regularised matrix would produce.
3. **Equilibrium is reported, not assumed.** Every solution carries the residual of the
   reactions against the applied loads. A solver that does not check its own arithmetic
   is a solver whose arithmetic nobody checks.
4. **The convention is stated once and travels.** Member end forces come out in the
   member's local axes with the sign convention written down here, so a check reading
   them never has to guess whether a positive moment sags or hogs.

The size is capped on purpose, and the cap was measured rather than guessed. The
factorisation is dense and in pure Python, so it is cubic in the free degrees of freedom:
20 nodes solve in 0.01 s, 60 in 0.2 s, and 120 — :data:`MAX_NODES` — in about 1.5 s on
the machine this was written on. Twice that is twelve seconds and four times is a minute
and a half. Past the cap the frame is refused by name, pointing at the external-solver
doorway that exists for exactly that case; a quiet two-minute solve would be worse.

Out of scope here: plates and shells, dynamics, nonlinear material, and buckling
eigenvalues. Pynite (MIT) is the independent referee the tests compare against; nothing
in the package imports it.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import cos, hypot, isfinite, sin, sqrt

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel, each_one
from .dependency import COMPUTED_FROM, CheckNode, Output
from .derivation import DerivationAbsence, Underived
from .refusal import RefusalError, Remedy
from .scorecard import (
    CheckStatus,
    Comparison,
    LimitSense,
    Need,
    Scorecard,
    ScorecardEntry,
    ValueSource,
)
from .units import Quantity

__all__ = [
    "MAX_NODES",
    "Freedom",
    "FrameNode",
    "Support",
    "FrameMaterial",
    "FrameSection",
    "FrameMember",
    "NodeLoad",
    "MemberLoad",
    "Frame",
    "AnalysisBasis",
    "METHODS",
    "NodeDisplacement",
    "Reaction",
    "MemberEndForces",
    "Mechanism",
    "FrameSolution",
    "MechanismFound",
    "solve_frame",
    "DeflectionLimit",
    "screen_frame",
    "screen_solution",
    "MEMBER_OUTPUTS",
    "frame_check_node",
    "frame_outputs",
    "ItemAgreement",
    "frame_over_combination_scorecard",
]

#: The largest frame this solver will take. A dense symmetric factorisation in pure
#: Python is cubic in the free degrees of freedom; at this many nodes the solve is a
#: fraction of a second, and an order of magnitude more would be minutes. A frame past it
#: is refused by name rather than run, and the refusal points at
#: :mod:`anvilate.interop`, whose whole purpose is forces an external solver produced.
MAX_NODES = 120

#: Degrees of freedom per node: three translations then three rotations, in that order.
_DOF = 6

_FRAME_SOURCE = "the frame declaration: its nodes, members, supports and loads"
_SOLVE_SOURCE = "the frame as declared, or an external solver through anvilate.interop"

#: How close to parallel a member has to be to the global vertical before the vertical is
#: useless as the reference for its local axes. ``cos`` of about a quarter of a degree:
#: past this the cross product that builds the local y axis is numerically worthless, and
#: the global X axis is used as the reference instead.
_NEARLY_VERTICAL = 0.99999


def _refuse(message: str, *, subject: str, source: str = _FRAME_SOURCE) -> RefusalError:
    return RefusalError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class MechanismFound(RefusalError, ValueError):
    """The frame has a free mode: no unique set of forces exists to report.

    Raised rather than returned, because every caller of a solve wants the forces and
    there are none. The free freedom is named on :attr:`mechanism`, which is the thing a
    person fixes — a missing support, a member released at both ends, a node nothing
    reaches.
    """

    def __init__(self, mechanism: Mechanism) -> None:
        self.mechanism = mechanism
        super().__init__(
            f"the frame is a mechanism: {mechanism}. There is no unique solution to "
            f"report, and a regularised matrix would return numbers that look like one",
            remedies=(
                Remedy(
                    action="add",
                    subject=f"a restraint or a member reaching {mechanism.node}",
                    source="the frame's supports and members",
                ),
            ),
        )


class Freedom(StrEnum):
    """One degree of freedom at a node, in the order the solver numbers them."""

    UX = "ux"
    UY = "uy"
    UZ = "uz"
    RX = "rx"
    RY = "ry"
    RZ = "rz"

    @property
    def index(self) -> int:
        """Its position in a node's six, 0 to 5."""
        return _FREEDOM_ORDER.index(self)


_FREEDOM_ORDER: tuple[Freedom, ...] = (
    Freedom.UX,
    Freedom.UY,
    Freedom.UZ,
    Freedom.RX,
    Freedom.RY,
    Freedom.RZ,
)


class FrameNode(StatableModel):
    """A point of the frame, in global coordinates. Global **Z is up**."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    name: Named
    x: Quantity
    y: Quantity
    z: Quantity
    #: The connection this node sits at — a combination's mate, or a product's interface.
    #: Declared, not inferred: two parts whose boxes touch are not necessarily joined, and
    #: a node that claims to be a connection it is not puts the solve's reaction on the
    #: wrong bolt. Blank means a node of the model with nothing in the build at it.
    at: str = ""

    @model_validator(mode="after")
    def _is_a_point(self) -> FrameNode:
        for value, axis in ((self.x, "x"), (self.y, "y"), (self.z, "z")):
            if not value.has_dimension("[length]"):
                raise _refuse(
                    f"a node's {axis} is a length; got {value.dimensionality}",
                    subject=axis,
                )
        return self

    @property
    def metres(self) -> tuple[float, float, float]:
        """The point in metres, which is what the solver works in."""
        return (
            self.x.to("m").magnitude,
            self.y.to("m").magnitude,
            self.z.to("m").magnitude,
        )

    def __str__(self) -> str:
        return f"{self.name} at ({self.x}, {self.y}, {self.z})"


class Support(StatableModel):
    """The freedoms a node is held against. Naming none would be no support at all."""

    model_config = ConfigDict(frozen=True)

    node: Named
    restrained: tuple[Freedom, ...]

    @model_validator(mode="after")
    def _holds_something(self) -> Support:
        if not self.restrained:
            raise _refuse(
                f"the support at '{self.node}' restrains nothing; a support that holds no "
                f"freedom is not a support, and declaring one reads as a frame that is "
                f"held where it is not",
                subject="restrained",
            )
        if len(set(self.restrained)) != len(self.restrained):
            raise _refuse(
                f"the support at '{self.node}' names a freedom twice in "
                f"{[f.value for f in self.restrained]}",
                subject="restrained",
            )
        return self

    def __str__(self) -> str:
        held = ", ".join(freedom.value for freedom in self.restrained)
        return f"{self.node}: {held}"


class FrameMaterial(StatableModel):
    """The two elastic constants a frame element needs, with where they came from."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    name: Named
    elastic_modulus: Quantity
    shear_modulus: Quantity
    density: Quantity | None = Field(default=None, exclude_if=lambda value: value is None)
    source: Provenance

    @model_validator(mode="after")
    def _is_elastic(self) -> FrameMaterial:
        for value, name in ((self.elastic_modulus, "elastic_modulus"),
                            (self.shear_modulus, "shear_modulus")):  # fmt: skip
            if not value.has_dimension("[pressure]"):
                raise _refuse(f"{name} is a stress; got {value.dimensionality}", subject=name)
            if value.magnitude <= 0:
                raise _refuse(
                    f"{name} is positive; got {value}. A zero modulus is a member with no "
                    f"stiffness, which is a mechanism stated as a material",
                    subject=name,
                )
        if self.density is not None and (
            not self.density.has_dimension("[mass] / [length] ** 3") or self.density.magnitude <= 0
        ):
            raise _refuse(
                f"density is a positive mass per volume; got {self.density}",
                subject="density",
            )
        return self

    def __str__(self) -> str:
        return f"{self.name}: E {self.elastic_modulus}, G {self.shear_modulus} ({self.source})"


class FrameSection(StatableModel):
    """The four section properties a three-dimensional frame element needs.

    ``second_moment_y`` bends the member about its local y axis (deflection in local z),
    ``second_moment_z`` about its local z (deflection in local y). ``torsion_constant``
    is St Venant's J, which for an open section is **not** the polar moment and is the
    one a caller most often supplies wrong — so it is named for what it is.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    name: Named
    area: Quantity
    second_moment_y: Quantity
    second_moment_z: Quantity
    torsion_constant: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _is_a_section(self) -> FrameSection:
        checks = (
            (self.area, "area", "[length] ** 2"),
            (self.second_moment_y, "second_moment_y", "[length] ** 4"),
            (self.second_moment_z, "second_moment_z", "[length] ** 4"),
            (self.torsion_constant, "torsion_constant", "[length] ** 4"),
        )
        for value, name, dimension in checks:
            if not value.has_dimension(dimension):
                raise _refuse(
                    f"{name} is a {dimension.replace('**', 'to the power')}; got "
                    f"{value.dimensionality}",
                    subject=name,
                )
            if value.magnitude <= 0:
                raise _refuse(
                    f"{name} is positive; got {value}. A section property of zero is a "
                    f"member free in that mode, which is a release and not a section",
                    subject=name,
                )
        return self

    def __str__(self) -> str:
        return (
            f"{self.name}: A {self.area}, Iy {self.second_moment_y}, "
            f"Iz {self.second_moment_z}, J {self.torsion_constant} ({self.source})"
        )


class FrameMember(StatableModel):
    """One element between two nodes, with its section, material and orientation.

    ``roll`` rotates the local y and z axes about the member's own axis. With no roll the
    local **z** axis is as near the global vertical as the member allows, which puts
    major-axis bending of an ordinary beam in the vertical plane where a reader expects
    it. A member within a quarter of a degree of vertical has no such reference, so the
    global X axis is used instead and the roll is measured from there.

    ``releases_start`` and ``releases_end`` free a freedom at that end — a pinned
    connection is the two bending rotations released. An axial or shear release is
    accepted and is almost always a mistake, so it is not special-cased into silence:
    the mechanism detector will say so if it makes one.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    name: Named
    start: Named
    end: Named
    section: FrameSection
    material: FrameMaterial
    #: The built part this member models — a combination's part id, or a product's item.
    #: More than one member may name the same item: a column with a node at mid-height is
    #: two members of one part. Blank means a member of the model with no part behind it,
    #: which :func:`frame_over_combination_scorecard` reports rather than assumes.
    item: str = ""
    roll: Quantity | None = Field(default=None, exclude_if=lambda value: value is None)
    releases_start: tuple[Freedom, ...] = ()
    releases_end: tuple[Freedom, ...] = ()

    @model_validator(mode="after")
    def _is_a_member(self) -> FrameMember:
        if self.start == self.end:
            raise _refuse(
                f"member '{self.name}' starts and ends at '{self.start}'; a member of zero "
                f"length has no direction and no stiffness",
                subject="start and end",
            )
        if self.roll is not None and str(self.roll.pint.dimensionality) != "dimensionless":
            raise _refuse(f"roll is an angle; got {self.roll.dimensionality}", subject="roll")
        for released, side in ((self.releases_start, "start"), (self.releases_end, "end")):
            if len(set(released)) != len(released):
                raise _refuse(
                    f"member '{self.name}' releases a freedom twice at its {side}",
                    subject=f"releases_{side}",
                )
        both = set(self.releases_start) & set(self.releases_end)
        if both:
            raise _refuse(
                f"member '{self.name}' releases "
                f"{', '.join(sorted(f.value for f in both))} at both ends, which leaves it "
                f"free in that mode and the frame a mechanism through it",
                subject="releases_start and releases_end",
            )
        return self

    @property
    def roll_radians(self) -> float:
        """The roll angle in radians; zero when none is declared."""
        return 0.0 if self.roll is None else self.roll.to("radian").magnitude

    def __str__(self) -> str:
        released = ""
        if self.releases_start or self.releases_end:
            released = (
                f", released {[f.value for f in self.releases_start]} / "
                f"{[f.value for f in self.releases_end]}"
            )
        return f"{self.name}: {self.start} to {self.end}, {self.section.name}{released}"


class NodeLoad(StatableModel):
    """A force and a moment applied at a node, in global axes."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    node: Named
    fx: Quantity | None = None
    fy: Quantity | None = None
    fz: Quantity | None = None
    mx: Quantity | None = None
    my: Quantity | None = None
    mz: Quantity | None = None

    @model_validator(mode="after")
    def _is_a_load(self) -> NodeLoad:
        forces = ((self.fx, "fx"), (self.fy, "fy"), (self.fz, "fz"))
        moments = ((self.mx, "mx"), (self.my, "my"), (self.mz, "mz"))
        for value, name in forces:
            if value is not None and not value.has_dimension("[force]"):
                raise _refuse(f"{name} is a force; got {value.dimensionality}", subject=name)
        for value, name in moments:
            if value is not None and not value.has_dimension("[force] * [length]"):
                raise _refuse(f"{name} is a moment; got {value.dimensionality}", subject=name)
        if all(value is None for value, _ in (*forces, *moments)):
            raise _refuse(
                f"the load at '{self.node}' states no component; a load of nothing is not "
                f"a load, and declaring one reads as a frame that is loaded where it is not",
                subject="fx, fy, fz, mx, my, mz",
            )
        return self

    @property
    def vector(self) -> tuple[float, float, float, float, float, float]:
        """The six components in newtons and newton-metres, zero where unstated."""
        return (
            _si(self.fx, "N"),
            _si(self.fy, "N"),
            _si(self.fz, "N"),
            _si(self.mx, "N*m"),
            _si(self.my, "N*m"),
            _si(self.mz, "N*m"),
        )

    def __str__(self) -> str:
        shown = [
            f"{name} {value}"
            for name, value in (
                ("fx", self.fx),
                ("fy", self.fy),
                ("fz", self.fz),
                ("mx", self.mx),
                ("my", self.my),
                ("mz", self.mz),
            )  # fmt: skip
            if value is not None
        ]
        return f"{self.node}: " + ", ".join(shown)


def _si(value: Quantity | None, unit: str) -> float:
    return 0.0 if value is None else value.to(unit).magnitude


class MemberLoad(StatableModel):
    """A uniformly distributed load along a member, in **global** axes.

    Global and not local, because that is how a reader states gravity, wind and snow, and
    converting once here is better than asking every caller to resolve it into the local
    axes of a member they declared with a roll angle.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    member: Named
    wx: Quantity | None = None
    wy: Quantity | None = None
    wz: Quantity | None = None

    @model_validator(mode="after")
    def _is_a_load(self) -> MemberLoad:
        components = ((self.wx, "wx"), (self.wy, "wy"), (self.wz, "wz"))
        for value, name in components:
            if value is not None and not value.has_dimension("[force] / [length]"):
                raise _refuse(
                    f"{name} is a force per length; got {value.dimensionality}", subject=name
                )
        if all(value is None for value, _ in components):
            raise _refuse(
                f"the distributed load on '{self.member}' states no component",
                subject="wx, wy, wz",
            )
        return self

    @property
    def vector(self) -> tuple[float, float, float]:
        """The three components in newtons per metre, zero where unstated."""
        return (_si(self.wx, "N/m"), _si(self.wy, "N/m"), _si(self.wz, "N/m"))

    def __str__(self) -> str:
        shown = [
            f"{name} {value}"
            for name, value in (("wx", self.wx), ("wy", self.wy), ("wz", self.wz))
            if value is not None
        ]
        return f"{self.member}: " + ", ".join(shown)


class Frame(StatableModel):
    """A frame as declared: its nodes, members, supports and loads.

    Every reference is checked on the way in. A member naming a node that does not exist,
    a support on no node, a node nothing reaches — each is refused by name here rather
    than producing a singular matrix three hundred lines later, where the message would be
    about arithmetic instead of about the document.
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    nodes: tuple[FrameNode, ...]
    members: tuple[FrameMember, ...]
    supports: tuple[Support, ...] = ()
    node_loads: tuple[NodeLoad, ...] = ()
    member_loads: tuple[MemberLoad, ...] = ()
    #: Gravity along global −Z, applied to every member whose material states a density.
    #: Off by default: a self-weight nobody asked for is a load nobody can see.
    self_weight: bool = False

    @model_validator(mode="after")
    def _is_a_frame(self) -> Frame:
        if not self.nodes:
            raise _refuse(f"frame '{self.name}' has no nodes", subject="nodes")
        if not self.members:
            raise _refuse(
                f"frame '{self.name}' has no members; a set of nodes with nothing between "
                f"them is not a frame",
                subject="members",
            )
        if len(self.nodes) > MAX_NODES:
            raise _refuse(
                f"frame '{self.name}' has {len(self.nodes)} nodes and this solver takes at "
                f"most {MAX_NODES}. The factorisation is dense and in pure Python, so a "
                f"larger frame would run for minutes rather than refuse in a line; solve it "
                f"outside and bring the member forces in through anvilate.interop",
                subject="nodes",
                source=_SOLVE_SOURCE,
            )
        named = [node.name for node in self.nodes]
        doubled = sorted({name for name in named if named.count(name) > 1})
        if doubled:
            raise _refuse(
                f"frame '{self.name}' declares the node {', '.join(doubled)} more than once",
                subject="nodes",
            )
        members = [member.name for member in self.members]
        doubled = sorted({name for name in members if members.count(name) > 1})
        if doubled:
            raise _refuse(
                f"frame '{self.name}' declares the member {', '.join(doubled)} more than once",
                subject="members",
            )
        known = set(named)
        for member in self.members:
            for end, side in ((member.start, "start"), (member.end, "end")):
                if end not in known:
                    raise _refuse(
                        f"member '{member.name}' has its {side} at '{end}', which is not a "
                        f"node of this frame",
                        subject="members",
                    )
        for support in self.supports:
            if support.node not in known:
                raise _refuse(
                    f"the support at '{support.node}' is on no node of this frame",
                    subject="supports",
                )
        supported = [support.node for support in self.supports]
        doubled = sorted({name for name in supported if supported.count(name) > 1})
        if doubled:
            raise _refuse(
                f"frame '{self.name}' supports {', '.join(doubled)} twice; one node has one "
                f"set of restrained freedoms, and two declarations is two answers",
                subject="supports",
            )
        reached = {end for member in self.members for end in (member.start, member.end)}
        orphans = sorted(known - reached)
        if orphans:
            raise _refuse(
                f"frame '{self.name}' declares {', '.join(orphans)} and no member reaches "
                f"{'them' if len(orphans) > 1 else 'it'}; an unreferenced node is free in "
                f"all six freedoms and makes the frame a mechanism",
                subject="nodes",
            )
        for load in self.node_loads:
            if load.node not in known:
                raise _refuse(
                    f"the load at '{load.node}' is on no node of this frame",
                    subject="node_loads",
                )
        by_member = {member.name for member in self.members}
        for load in self.member_loads:
            if load.member not in by_member:
                raise _refuse(
                    f"the distributed load on '{load.member}' is on no member of this frame",
                    subject="member_loads",
                )
        if self.self_weight and not any(
            member.material.density is not None for member in self.members
        ):
            raise _refuse(
                f"frame '{self.name}' asks for self weight and no member's material states "
                f"a density, so the load would be zero and would read as applied",
                subject="self_weight",
            )
        return self

    @property
    def free_degrees(self) -> int:
        """The unrestrained degrees of freedom this frame solves for."""
        held = sum(len(support.restrained) for support in self.supports)
        return len(self.nodes) * _DOF - held

    def __str__(self) -> str:
        return (
            f"{self.name}: {len(self.nodes)} nodes, {len(self.members)} members, "
            f"{len(self.supports)} supports, {self.free_degrees} free degrees of freedom"
        )


class AnalysisBasis(StrEnum):
    """Which analysis produced a set of forces. It travels with every record."""

    FIRST_ORDER = "first_order_elastic"
    SECOND_ORDER = "second_order_p_delta"


class NodeDisplacement(StatableModel):
    """One node's six displacements, in global axes: metres and radians."""

    model_config = ConfigDict(frozen=True)

    node: Named
    ux: float
    uy: float
    uz: float
    rx: float
    ry: float
    rz: float

    @property
    def translation(self) -> Quantity:
        """The resultant translation, which is what a deflection limit is written against."""
        return Quantity(magnitude=sqrt(self.ux**2 + self.uy**2 + self.uz**2), unit="m")

    def __str__(self) -> str:
        return (
            f"{self.node}: ux {self.ux:.6g}, uy {self.uy:.6g}, uz {self.uz:.6g} m; "
            f"rx {self.rx:.6g}, ry {self.ry:.6g}, rz {self.rz:.6g} rad"
        )


class Reaction(StatableModel):
    """What a support carries, in global axes: newtons and newton-metres."""

    model_config = ConfigDict(frozen=True)

    node: Named
    fx: float
    fy: float
    fz: float
    mx: float
    my: float
    mz: float

    def __str__(self) -> str:
        return (
            f"{self.node}: Fx {self.fx:.6g}, Fy {self.fy:.6g}, Fz {self.fz:.6g} N; "
            f"Mx {self.mx:.6g}, My {self.my:.6g}, Mz {self.mz:.6g} N·m"
        )


class MemberEndForces(StatableModel):
    """A member's forces at each end, in its **local** axes, with the convention stated.

    Local x runs from ``start`` to ``end``. A positive ``axial_start`` is the force the
    node applies to the member along +x, so a member in **compression** has a positive
    ``axial_start`` and a negative ``axial_end``; :attr:`axial` reports the familiar
    signed value, tension positive, which is what a member check wants.

    ``basis`` says which analysis produced these, because a code's member check amplifies
    first-order forces and would double count if handed second-order ones.
    """

    model_config = ConfigDict(frozen=True)

    member: Named
    basis: AnalysisBasis
    axial_start: float
    shear_y_start: float
    shear_z_start: float
    torsion_start: float
    moment_y_start: float
    moment_z_start: float
    axial_end: float
    shear_y_end: float
    shear_z_end: float
    torsion_end: float
    moment_y_end: float
    moment_z_end: float

    @property
    def axial(self) -> Quantity:
        """The axial force, **tension positive**, as every member check reads it."""
        return Quantity(magnitude=-self.axial_start, unit="N")

    @property
    def worst_moment_z(self) -> Quantity:
        """The larger end moment about the local z axis, by magnitude."""
        return Quantity(magnitude=max(abs(self.moment_z_start), abs(self.moment_z_end)), unit="N*m")

    @property
    def worst_moment_y(self) -> Quantity:
        """The larger end moment about the local y axis, by magnitude."""
        return Quantity(magnitude=max(abs(self.moment_y_start), abs(self.moment_y_end)), unit="N*m")

    def __str__(self) -> str:
        return (
            f"{self.member} [{self.basis.value}]: axial {self.axial.magnitude:.6g} N "
            f"(tension positive), Mz {self.moment_z_start:.6g} / {self.moment_z_end:.6g}, "
            f"My {self.moment_y_start:.6g} / {self.moment_y_end:.6g} N·m"
        )


class Mechanism(StatableModel):
    """The free mode a singular frame has, named where a person can act on it."""

    model_config = ConfigDict(frozen=True)

    node: Named
    freedom: Freedom
    detail: str = ""

    def __str__(self) -> str:
        detail = f" ({self.detail})" if self.detail else ""
        return f"{self.node} is free in {self.freedom.value}{detail}"


class FrameSolution(StatableModel):
    """What the solve produced, and the check it ran on its own arithmetic.

    ``residual`` is the largest out-of-balance force, in newtons, between the reactions
    and everything applied. It is reported rather than asserted: a reader deciding
    whether to trust a number is entitled to see how well the solver closed.
    """

    model_config = ConfigDict(frozen=True)

    frame: Named
    basis: AnalysisBasis
    #: The analysis in words. The codes mean different things by "second order", so the
    #: solution says which one this was rather than leaving a reader to infer it.
    method: str = "first-order linear elastic direct stiffness"
    #: How many times the system was solved. One under first order; more under P-Delta,
    #: and a reader watching that number climb is watching a frame approach its limit.
    passes: int = 1
    displacements: tuple[NodeDisplacement, ...]
    reactions: tuple[Reaction, ...]
    member_forces: tuple[MemberEndForces, ...]
    residual: float
    free_degrees: int

    def displacement(self, node: str) -> NodeDisplacement:
        """One node's displacements, by name."""
        found = next((d for d in self.displacements if d.node == node), None)
        if found is None:
            raise KeyError(f"{node!r} is not a node of this solution")
        return found

    def forces(self, member: str) -> MemberEndForces:
        """One member's end forces, by name."""
        found = next((f for f in self.member_forces if f.member == member), None)
        if found is None:
            raise KeyError(f"{member!r} is not a member of this solution")
        return found

    def reaction(self, node: str) -> Reaction:
        """One support's reaction, by name."""
        found = next((r for r in self.reactions if r.node == node), None)
        if found is None:
            raise KeyError(f"{node!r} is not a supported node of this solution")
        return found

    @property
    def largest_translation(self) -> NodeDisplacement | None:
        """The node that moved furthest, which is where a deflection limit is read."""
        if not self.displacements:
            return None
        return max(self.displacements, key=lambda d: d.translation.magnitude)

    def __str__(self) -> str:
        passes = "" if self.passes == 1 else f" in {self.passes} passes"
        return (
            f"{self.frame} [{self.basis.value}]: {len(self.member_forces)} members solved "
            f"over {self.free_degrees} free degrees of freedom{passes}, equilibrium "
            f"residual {self.residual:.3g} N ({self.method})"
        )


# --- the solve ---------------------------------------------------------------------


#: How many times the second-order solve may re-solve before it gives up. A sway frame
#: well below its elastic critical load converges in three or four; one that does not
#: converge in this many is at or past that load, and saying so is the answer.
_MAX_PDELTA_PASSES = 25

#: Convergence of the second-order solve: the largest relative change in any member's
#: axial force between two passes.
_PDELTA_TOLERANCE = 1e-9

#: The method each basis is, named on the solution so a reader never has to ask which
#: second-order analysis was run — the codes mean different things by the phrase.
METHODS: dict[AnalysisBasis, str] = {
    AnalysisBasis.FIRST_ORDER: "first-order linear elastic direct stiffness",
    AnalysisBasis.SECOND_ORDER: (
        "P-Delta by consistent geometric stiffness, iterated on the member axial forces "
        "to convergence"
    ),
}


def solve_frame(frame: Frame, *, basis: AnalysisBasis = AnalysisBasis.FIRST_ORDER) -> FrameSolution:
    """Solve a frame by direct stiffness, three-dimensional, linear elastic.

    First order by default. ``basis=AnalysisBasis.SECOND_ORDER`` asks for P-Delta — the
    geometric stiffness of each member built from its own axial force and the whole
    solved again until those forces stop moving — and **it is a declaration on purpose**.
    A code's member check amplifies first-order forces (AISC 360 Appendix 8, EN 1993-1-1
    §5.2), so running second order silently and then applying the amplifier would double
    count. Whichever was run is named on the solution and on every force record.

    Raises :class:`MechanismFound` naming the free freedom when the frame has one, rather
    than returning the numbers a regularised matrix would produce. Under second order
    that includes a frame driven past its elastic critical load: the softened matrix
    stops being positive definite, which is the buckling this analysis can see.
    """
    if not isinstance(frame, Frame):
        raise _refuse(
            f"solve_frame takes a Frame; got {type(frame).__name__}",
            subject="frame",
            source=_SOLVE_SOURCE,
        )
    if basis not in METHODS:
        raise _refuse(
            f"basis is one of {sorted(b.value for b in METHODS)}; got {basis!r}",
            subject="basis",
            source=_SOLVE_SOURCE,
        )
    index = {node.name: position for position, node in enumerate(frame.nodes)}
    points = {node.name: node.metres for node in frame.nodes}
    size = len(frame.nodes) * _DOF

    held: set[int] = set()
    for support in frame.supports:
        base = index[support.node] * _DOF
        held.update(base + freedom.index for freedom in support.restrained)
    free = [position for position in range(size) if position not in held]

    geometry = {member.name: _geometry_of(member, points) for member in frame.members}
    distributed = {load.member: load.vector for load in frame.member_loads}
    locals_by_member = {
        member.name: _member_matrices(member, geometry[member.name], frame, distributed)
        for member in frame.members
    }

    loads = [0.0] * size
    for member in frame.members:
        _, local_load = locals_by_member[member.name]
        if any(local_load):
            dofs = _member_dofs(member, index)
            rotation = geometry[member.name].rotation
            for position, value in zip(dofs, _to_global(rotation, local_load), strict=True):
                loads[position] += value
    for load in frame.node_loads:
        base = index[load.node] * _DOF
        for offset, value in enumerate(load.vector):
            loads[base + offset] += value

    axial: dict[str, float] = {member.name: 0.0 for member in frame.members}
    passes = 1 if basis is AnalysisBasis.FIRST_ORDER else _MAX_PDELTA_PASSES
    stiffness: list[list[float]] = []
    displacement: list[float] = []
    solved = 0
    for _attempt in range(passes):
        solved += 1
        stiffness = _assemble(frame, index, geometry, locals_by_member, axial, size, basis)
        displacement = _displacements(frame, stiffness, loads, free, size, index)
        moved = {
            member.name: _end_forces(
                member,
                geometry[member.name],
                displacement,
                index,
                locals_by_member[member.name],
            ).axial.magnitude
            for member in frame.members
        }
        if basis is AnalysisBasis.FIRST_ORDER:
            break
        scale = max((abs(value) for value in moved.values()), default=0.0) or 1.0
        shift = max(abs(moved[name] - axial[name]) for name in moved)
        axial = moved
        if shift / scale <= _PDELTA_TOLERANCE:
            break
    else:
        raise _refuse(
            f"the second-order solve of '{frame.name}' did not settle in "
            f"{_MAX_PDELTA_PASSES} passes; the member forces are still moving, which is "
            f"what a frame at or past its elastic critical load does. Reduce the load, "
            f"stiffen the frame, or read the first-order forces and amplify them by the "
            f"code's own factor",
            subject="basis",
            source=_SOLVE_SOURCE,
        )

    reactions = tuple(
        _reaction(support, stiffness, displacement, loads, index, size)
        for support in frame.supports
    )
    member_forces = tuple(
        _end_forces(
            member,
            geometry[member.name],
            displacement,
            index,
            locals_by_member[member.name],
            basis=basis,
        )
        for member in frame.members
    )
    return FrameSolution(
        frame=frame.name,
        basis=basis,
        method=METHODS[basis],
        passes=solved,
        displacements=tuple(
            NodeDisplacement(
                node=node.name,
                ux=displacement[index[node.name] * _DOF + 0],
                uy=displacement[index[node.name] * _DOF + 1],
                uz=displacement[index[node.name] * _DOF + 2],
                rx=displacement[index[node.name] * _DOF + 3],
                ry=displacement[index[node.name] * _DOF + 4],
                rz=displacement[index[node.name] * _DOF + 5],
            )
            for node in frame.nodes
        ),
        reactions=reactions,
        member_forces=member_forces,
        residual=_residual(frame, reactions, loads, index, size),
        free_degrees=len(free),
    )


def _assemble(
    frame: Frame,
    index: dict[str, int],
    geometry: dict[str, _Geometry],
    locals_by_member: dict[str, tuple[list[list[float]], list[float]]],
    axial: dict[str, float],
    size: int,
    basis: AnalysisBasis,
) -> list[list[float]]:
    """The global stiffness, with each member's geometric term under second order."""
    stiffness = [[0.0] * size for _ in range(size)]
    for member in frame.members:
        shape = geometry[member.name]
        local_k = locals_by_member[member.name][0]
        if basis is AnalysisBasis.SECOND_ORDER and axial[member.name] != 0.0:
            geometric = _geometric_stiffness(axial[member.name], shape.length, member.section)
            local_k = [[local_k[i][j] + geometric[i][j] for j in range(12)] for i in range(12)]
        global_k = _congruent(shape.rotation, local_k)
        dofs = _member_dofs(member, index)
        for row, i in enumerate(dofs):
            krow, grow = stiffness[i], global_k[row]
            for column, j in enumerate(dofs):
                krow[j] += grow[column]
    return stiffness


def _displacements(
    frame: Frame,
    stiffness: list[list[float]],
    loads: list[float],
    free: list[int],
    size: int,
    index: dict[str, int],
) -> list[float]:
    """Solve the restrained system, naming the free mode when there is one."""
    reduced = [[stiffness[i][j] for j in free] for i in free]
    right = [loads[i] for i in free]
    try:
        answer = _solve_symmetric(reduced, right)
    except _Singular as singular:
        position = free[singular.pivot]
        node = frame.nodes[position // _DOF]
        raise MechanismFound(
            Mechanism(
                node=node.name,
                freedom=_FREEDOM_ORDER[position % _DOF],
                detail="no path of stiffness reaches this freedom",
            )
        ) from None
    displacement = [0.0] * size
    for position, value in zip(free, answer, strict=True):
        displacement[position] = value
    return displacement


def _reaction(
    support: Support,
    stiffness: list[list[float]],
    displacement: list[float],
    loads: list[float],
    index: dict[str, int],
    size: int,
) -> Reaction:
    base = index[support.node] * _DOF
    carried = [
        sum(stiffness[base + offset][j] * displacement[j] for j in range(size))
        - loads[base + offset]
        for offset in range(_DOF)
    ]
    return Reaction(
        node=support.node,
        fx=carried[0], fy=carried[1], fz=carried[2],
        mx=carried[3], my=carried[4], mz=carried[5],
    )  # fmt: skip


class _Geometry:
    """A member's length and its 3x3 direction-cosine matrix, computed once."""

    __slots__ = ("length", "rotation")

    def __init__(self, length: float, rotation: list[list[float]]) -> None:
        self.length = length
        self.rotation = rotation


def _geometry_of(member: FrameMember, points: dict[str, tuple[float, float, float]]) -> _Geometry:
    """The member's length and local axes.

    The local x axis runs start to end. With no roll the local **z** axis is as near the
    global vertical as the member allows: take the global Z as a reference, make local y
    perpendicular to both, and local z the third. A member within
    :data:`_NEARLY_VERTICAL` of the global Z has no usable reference there — the cross
    product collapses — so the global X axis is used instead, which is the standard
    treatment and is why a column's bending axes are defined at all.
    """
    x1, y1, z1 = points[member.start]
    x2, y2, z2 = points[member.end]
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    length = sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 0.0 or not isfinite(length):
        raise _refuse(
            f"member '{member.name}' has length {length}; two nodes at the same point are "
            f"not a member",
            subject="members",
        )
    ex = [dx / length, dy / length, dz / length]
    reference = [0.0, 0.0, 1.0]
    if abs(ex[2]) > _NEARLY_VERTICAL:
        reference = [1.0, 0.0, 0.0]
    ey = _cross(reference, ex)
    norm = hypot(hypot(ey[0], ey[1]), ey[2])
    ey = [value / norm for value in ey]
    ez = _cross(ex, ey)
    roll = member.roll_radians
    if roll:
        c, s = cos(roll), sin(roll)
        ey, ez = (
            [c * ey[i] + s * ez[i] for i in range(3)],
            [-s * ey[i] + c * ez[i] for i in range(3)],
        )
    return _Geometry(length, [ex, ey, ez])


def _cross(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _local_stiffness(member: FrameMember, length: float) -> list[list[float]]:
    """The 12x12 elastic stiffness of a three-dimensional frame element, local axes.

    Degrees of freedom in the order u, v, w, θx, θy, θz at the start then the end, which
    is the order :class:`Freedom` numbers them in, so no reordering happens anywhere else.
    """
    e = member.material.elastic_modulus.to("Pa").magnitude
    g = member.material.shear_modulus.to("Pa").magnitude
    a = member.section.area.to("m**2").magnitude
    iy = member.section.second_moment_y.to("m**4").magnitude
    iz = member.section.second_moment_z.to("m**4").magnitude
    j = member.section.torsion_constant.to("m**4").magnitude
    length2, length3 = length * length, length * length * length

    k = [[0.0] * 12 for _ in range(12)]
    axial = e * a / length
    k[0][0] = k[6][6] = axial
    k[0][6] = k[6][0] = -axial
    torsion = g * j / length
    k[3][3] = k[9][9] = torsion
    k[3][9] = k[9][3] = -torsion

    # Bending about local z: v (1, 7) with θz (5, 11).
    v, m = 12.0 * e * iz / length3, 6.0 * e * iz / length2
    k[1][1] = k[7][7] = v
    k[1][7] = k[7][1] = -v
    k[1][5] = k[5][1] = k[1][11] = k[11][1] = m
    k[7][5] = k[5][7] = k[7][11] = k[11][7] = -m
    k[5][5] = k[11][11] = 4.0 * e * iz / length
    k[5][11] = k[11][5] = 2.0 * e * iz / length

    # Bending about local y: w (2, 8) with θy (4, 10). The signs differ from the pair
    # above because θy = −dw/dx where θz = +dv/dx — the one asymmetry of the convention,
    # and the one place a transcription error hides in a matrix that still looks right.
    v, m = 12.0 * e * iy / length3, 6.0 * e * iy / length2
    k[2][2] = k[8][8] = v
    k[2][8] = k[8][2] = -v
    k[2][4] = k[4][2] = k[2][10] = k[10][2] = -m
    k[8][4] = k[4][8] = k[8][10] = k[10][8] = m
    k[4][4] = k[10][10] = 4.0 * e * iy / length
    k[4][10] = k[10][4] = 2.0 * e * iy / length
    return k


def _condense(
    k: list[list[float]], load: list[float], member: FrameMember
) -> tuple[list[list[float]], list[float]]:
    """Condense out the released freedoms, stiffness **and** load together.

    Static condensation on each released degree of freedom in turn. Two mistakes live
    here and both were made on the way to this version.

    Zeroing the released row and column instead of eliminating leaves the diagonal and
    gives a member stiffer than a pin — the release then changes nothing a reader can
    see, which is worse than refusing it.

    Condensing the stiffness and **not** the fixed-end load leaves the released end
    carrying its fixed-end moment: a hinge at the end of a uniformly loaded span came
    out holding ``wL²/12``, which is the number a fixed end carries and the exact
    opposite of a hinge. The load is condensed in the same elimination, in the same
    order, which is the only way the two stay consistent.
    """
    released = [freedom.index for freedom in member.releases_start]
    released += [6 + freedom.index for freedom in member.releases_end]
    for r in released:
        pivot = k[r][r]
        if pivot == 0.0:
            continue
        at_r = load[r]
        row_r = k[r]
        for i in range(12):
            if i == r:
                continue
            factor = k[i][r] / pivot
            if factor == 0.0:
                continue
            load[i] -= factor * at_r
            row_i = k[i]
            for j in range(12):
                row_i[j] -= factor * row_r[j]
        load[r] = 0.0
        for i in range(12):
            k[i][r] = 0.0
            k[r][i] = 0.0
    return k, load


def _member_matrices(
    member: FrameMember,
    shape: _Geometry,
    frame: Frame,
    distributed: dict[str, tuple[float, float, float]],
) -> tuple[list[list[float]], list[float]]:
    """A member's local stiffness and local equivalent nodal load, releases condensed.

    One function, called by both the assembly and the force recovery, because the two
    have to see the same matrix: condensing in one place and not the other is a member
    whose reported forces are not the ones the frame was solved with.
    """
    local_k = _local_stiffness(member, shape.length)
    udl = _member_udl(member, frame, distributed)
    local_load = _local_consistent_load(shape, udl) if any(udl) else [0.0] * 12
    if member.releases_start or member.releases_end:
        local_k, local_load = _condense(local_k, local_load, member)
    return local_k, local_load


def _geometric_stiffness(axial: float, length: float, section: FrameSection) -> list[list[float]]:
    """The consistent geometric stiffness of a frame element, local axes, tension positive.

    An axial force changes a member's lateral stiffness: tension stiffens it, compression
    softens it, and in a sway frame the compression in the columns is most of what makes
    a second-order analysis differ from a first-order one. This is the standard
    consistent matrix — ``6/5``, ``L/10``, ``2L²/15`` and ``−L²/30`` on the bending
    pairs, scaled by ``P/L``.

    The sign asymmetry between the two bending planes is the same one the elastic matrix
    has, and for the same reason: ``θy = −dw/dx`` where ``θz = +dv/dx``.
    """
    a = section.area.to("m**2").magnitude
    j = section.torsion_constant.to("m**4").magnitude
    scale = axial / length
    kg = [[0.0] * 12 for _ in range(12)]
    # The torsional term, which a planar formulation drops and a space frame needs.
    twist = axial * j / (a * length)
    kg[3][3] = kg[9][9] = twist
    kg[3][9] = kg[9][3] = -twist
    shear, couple = 1.2 * scale, axial / 10.0
    bending, carry = 2.0 * axial * length / 15.0, -axial * length / 30.0

    kg[1][1] = kg[7][7] = shear
    kg[1][7] = kg[7][1] = -shear
    kg[1][5] = kg[5][1] = kg[1][11] = kg[11][1] = couple
    kg[7][5] = kg[5][7] = kg[7][11] = kg[11][7] = -couple
    kg[5][5] = kg[11][11] = bending
    kg[5][11] = kg[11][5] = carry

    kg[2][2] = kg[8][8] = shear
    kg[2][8] = kg[8][2] = -shear
    kg[2][4] = kg[4][2] = kg[2][10] = kg[10][2] = -couple
    kg[8][4] = kg[4][8] = kg[8][10] = kg[10][8] = couple
    kg[4][4] = kg[10][10] = bending
    kg[4][10] = kg[10][4] = carry
    return kg


def _congruent(rotation: list[list[float]], local: list[list[float]]) -> list[list[float]]:
    """``Tᵀ k T`` for the block-diagonal T built from one 3x3 rotation, four times over.

    ``rotation``'s rows are the member's local axes in global components, so for a global
    vector ``v`` the local components are ``rotation · v`` — that is ``T`` — and the
    global stiffness is ``Tᵀ k T``. Each 3x3 block of the result is therefore
    ``λᵀ · block · λ``, and getting that transpose the wrong way round produces a matrix
    that is still symmetric, still positive definite, and wrong for every member that is
    not axis-aligned. The portal-frame case in the suite is what catches it.
    """
    transformed = [[0.0] * 12 for _ in range(12)]
    for bi in range(4):
        for bj in range(4):
            block = [[local[bi * 3 + i][bj * 3 + j] for j in range(3)] for i in range(3)]
            middle = [
                [sum(block[i][m] * rotation[m][n] for m in range(3)) for n in range(3)]
                for i in range(3)
            ]
            product = [
                [sum(rotation[m][i] * middle[m][n] for m in range(3)) for n in range(3)]
                for i in range(3)
            ]
            for i in range(3):
                for j in range(3):
                    transformed[bi * 3 + i][bj * 3 + j] = product[i][j]
    return transformed


def _member_dofs(member: FrameMember, index: dict[str, int]) -> list[int]:
    start, end = index[member.start] * _DOF, index[member.end] * _DOF
    return [start + i for i in range(_DOF)] + [end + i for i in range(_DOF)]


def _member_udl(
    member: FrameMember, frame: Frame, distributed: dict[str, tuple[float, float, float]]
) -> tuple[float, float, float]:
    """The member's distributed load in global axes, self weight included when asked."""
    wx, wy, wz = distributed.get(member.name, (0.0, 0.0, 0.0))
    if frame.self_weight and member.material.density is not None:
        density = member.material.density.to("kg/m**3").magnitude
        area = member.section.area.to("m**2").magnitude
        wz -= density * area * 9.80665
    return (wx, wy, wz)


def _local_consistent_load(shape: _Geometry, udl: tuple[float, float, float]) -> list[float]:
    """The equivalent nodal load vector of a uniform load, in the member's local axes.

    Derived from the element's own shape functions — ``∫ Nᵀ q dx`` — rather than copied
    from a table, because the one sign that differs between the two bending planes is the
    one a table is transcribed wrong at. For a constant load the integrals are ``L/2`` on
    each translation and ``±L²/12`` on each rotation, and the rotation's sign flips in the
    x–z plane because ``θy = −dw/dx`` where ``θz = +dv/dx``.

    Local and not global, because a released end condenses this vector along with the
    stiffness and the condensation is in local axes.
    """
    rotation, length = shape.rotation, shape.length
    qx, qy, qz = (sum(rotation[i][j] * udl[j] for j in range(3)) for i in range(3))
    half, twelfth = length / 2.0, length * length / 12.0
    return [
        qx * half, qy * half, qz * half, 0.0, -qz * twelfth, qy * twelfth,
        qx * half, qy * half, qz * half, 0.0, qz * twelfth, -qy * twelfth,
    ]  # fmt: skip


def _to_global(rotation: list[list[float]], local: Sequence[float]) -> list[float]:
    """``Tᵀ v`` for the block-diagonal T built from one 3x3 rotation."""
    out = [0.0] * 12
    for block in range(4):
        base = block * 3
        for i in range(3):
            out[base + i] = sum(rotation[m][i] * local[base + m] for m in range(3))
    return out


def _to_local(rotation: list[list[float]], vector: Sequence[float]) -> list[float]:
    """``T v`` for the same block-diagonal T."""
    out = [0.0] * 12
    for block in range(4):
        base = block * 3
        for i in range(3):
            out[base + i] = sum(rotation[i][m] * vector[base + m] for m in range(3))
    return out


def _end_forces(
    member: FrameMember,
    shape: _Geometry,
    displacement: list[float],
    index: dict[str, int],
    matrices: tuple[list[list[float]], list[float]],
    *,
    basis: AnalysisBasis = AnalysisBasis.FIRST_ORDER,
) -> MemberEndForces:
    """``k_local · u_local − fixed-end forces``, which is the member's own equilibrium.

    The **elastic** stiffness, not the elastic plus geometric one, even under a
    second-order solve: the geometric term is how the displacements were found, and the
    force in the member is still what its own elasticity carries at those displacements.
    Adding it here would count the P-Delta effect twice in the number a check reads.
    """
    dofs = _member_dofs(member, index)
    local_u = _to_local(shape.rotation, [displacement[position] for position in dofs])
    local_k, local_load = matrices
    forces = [sum(local_k[i][j] * local_u[j] for j in range(12)) - local_load[i] for i in range(12)]
    return MemberEndForces(
        member=member.name,
        basis=basis,
        axial_start=forces[0], shear_y_start=forces[1], shear_z_start=forces[2],
        torsion_start=forces[3], moment_y_start=forces[4], moment_z_start=forces[5],
        axial_end=forces[6], shear_y_end=forces[7], shear_z_end=forces[8],
        torsion_end=forces[9], moment_y_end=forces[10], moment_z_end=forces[11],
    )  # fmt: skip


def _residual(
    frame: Frame,
    reactions: Sequence[Reaction],
    loads: Sequence[float],
    index: dict[str, int],
    size: int,
) -> float:
    """The largest out-of-balance force between the reactions and everything applied.

    Translations only. A moment residual is in newton-metres and comparing it with a
    force would be comparing two dimensions, so the number reported is the one a reader
    can put beside the applied load.
    """
    applied = [0.0, 0.0, 0.0]
    for position in range(size):
        if position % _DOF < 3:
            applied[position % _DOF] += loads[position]
    carried = [
        sum(reaction.fx for reaction in reactions),
        sum(reaction.fy for reaction in reactions),
        sum(reaction.fz for reaction in reactions),
    ]
    return max(abs(applied[i] + carried[i]) for i in range(3))


class _Singular(Exception):
    """The reduced stiffness matrix has no positive pivot at ``pivot``."""

    def __init__(self, pivot: int) -> None:
        self.pivot = pivot
        super().__init__(f"no stiffness at reduced degree of freedom {pivot}")


def _solve_symmetric(matrix: list[list[float]], right: list[float]) -> list[float]:
    """Solve ``K u = f`` for a symmetric positive-definite K, by LDLᵀ.

    LDLᵀ and not Gaussian elimination with pivoting, for two reasons. The reduced
    stiffness of a properly restrained frame **is** positive definite, so no pivoting is
    needed and the factorisation is half the arithmetic. And a non-positive pivot is
    exactly the mechanism this module refuses to solve around — the condition a pivoting
    solver would quietly work past.

    The tolerance is relative to the largest diagonal the matrix started with, because an
    absolute one means something different for a frame in newtons per metre and the same
    frame in kilonewtons per millimetre.
    """
    n = len(matrix)
    if n == 0:
        return []
    scale = max(abs(matrix[i][i]) for i in range(n))
    floor = scale * 1e-12
    lower = [[0.0] * n for _ in range(n)]
    diagonal = [0.0] * n
    for j in range(n):
        total = matrix[j][j]
        row_j = lower[j]
        for k in range(j):
            total -= row_j[k] * row_j[k] * diagonal[k]
        if total <= floor:
            raise _Singular(j)
        diagonal[j] = total
        for i in range(j + 1, n):
            row_i = lower[i]
            value = matrix[i][j]
            for k in range(j):
                value -= row_i[k] * row_j[k] * diagonal[k]
            row_i[j] = value / total
    # L z = f, with L unit lower triangular.
    z = list(right)
    for i in range(n):
        row = lower[i]
        total = z[i]
        for k in range(i):
            total -= row[k] * z[k]
        z[i] = total
    # D y = z, then Lᵀ u = y.
    for i in range(n):
        z[i] /= diagonal[i]
    for i in range(n - 1, -1, -1):
        total = z[i]
        for k in range(i + 1, n):
            total -= lower[k][i] * z[k]
        z[i] = total
    return z


# --- the card the solve produces -----------------------------------------------------


class DeflectionLimit(StatableModel):
    """How far a node may move, and the document that says so.

    ``freedom`` limits one component — a sway limit is on ``ux``, a beam's sag on ``uz``
    — and ``None`` limits the resultant translation, which is what a clearance is
    written against. A limit with no source is refused by :class:`Provenance`: a
    deflection limit is a decision somebody made, usually out of a code or a client's
    specification, and a number with no author is one nobody can argue with.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    node: Named
    limit: Quantity
    source: Provenance
    freedom: Freedom | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def _is_a_limit(self) -> DeflectionLimit:
        if not self.limit.has_dimension("[length]"):
            raise _refuse(
                f"a deflection limit is a length; got {self.limit.dimensionality}",
                subject="limit",
                source="the code or specification that states the limit",
            )
        if self.limit.magnitude <= 0:
            raise _refuse(
                f"a deflection limit is positive; got {self.limit}. A limit of zero is a "
                f"node that may not move, which is a support and not a limit",
                subject="limit",
                source="the code or specification that states the limit",
            )
        if self.freedom is not None and self.freedom not in _TRANSLATIONS:
            raise _refuse(
                f"a deflection limit is on a translation; '{self.freedom.value}' is a "
                f"rotation, and a length cannot bound it",
                subject="freedom",
                source="the freedom the limit is written against",
            )
        return self

    def __str__(self) -> str:
        where = "resultant translation" if self.freedom is None else self.freedom.value
        return f"{self.node} {where} at most {self.limit} ({self.source})"


_TRANSLATIONS = (Freedom.UX, Freedom.UY, Freedom.UZ)


_SOLVE_CHECK = "frame solve"
_FRAME_CITATION = "direct stiffness, this library's own solve (anvilate.frame)"


def screen_frame(
    frame: Frame,
    *,
    limits: Sequence[DeflectionLimit] = (),
    basis: AnalysisBasis = AnalysisBasis.FIRST_ORDER,
) -> Scorecard:
    """Solve a frame and read its card: the solve itself, then each declared limit.

    A mechanism is one ``NOT_EVALUATED`` entry naming the free freedom, and no deflection
    entries at all — a limit judged against displacements that do not exist would be a
    verdict on nothing.

    A caller that already has a solution calls :func:`screen_solution` instead. Solving
    twice for one card is the kind of duplication that eventually returns two answers.
    """
    limits = each_one(limits, DeflectionLimit, named="limits")
    try:
        solution = solve_frame(frame, basis=basis)
    except MechanismFound as refused:
        return Scorecard(
            entries=(
                ScorecardEntry(
                    name=f"{frame.name} {_SOLVE_CHECK}",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        f"the frame is a mechanism: {refused.mechanism}. No member force "
                        f"and no displacement exists to check"
                    ),
                    reference=_FRAME_CITATION,
                    needs=(
                        Need(
                            declaration=f"supports[{refused.mechanism.node}]",
                            takes=(
                                f"a restraint on {refused.mechanism.freedom.value}, or a "
                                f"member reaching that node"
                            ),
                            sources=(ValueSource.USER,),
                        ),
                    ),
                    underived=Underived(
                        kind=DerivationAbsence.NUMERIC_RESULT,
                        reason=(
                            "the solve is a factorisation, not a formula, and it did not "
                            "reach an answer to show"
                        ),
                    ),
                ),
            )
        )
    return screen_solution(frame, solution, limits=limits)


def screen_solution(
    frame: Frame, solution: FrameSolution, *, limits: Sequence[DeflectionLimit] = ()
) -> Scorecard:
    """The card a solution reads to: the solve as a check, then each declared limit.

    The solve is a check of its own, and it is first. It carries the equilibrium residual
    and the analysis that was run, so every deflection entry below it says what it was
    computed from rather than appearing out of a factorisation nobody can see.
    """
    limits = each_one(limits, DeflectionLimit, named="limits")
    known = {node.name for node in frame.nodes}
    for limit in limits:
        if limit.node not in known:
            raise _refuse(
                f"the deflection limit at '{limit.node}' is on no node of this frame",
                subject="limits",
            )
    entries = [
        ScorecardEntry(
            name=f"{frame.name} {_SOLVE_CHECK}",
            status=CheckStatus.PASS,
            detail=(
                f"{len(solution.member_forces)} members solved over "
                f"{solution.free_degrees} free degrees of freedom by {solution.method}; "
                f"equilibrium residual {solution.residual:.3g} N"
            ),
            reference=_FRAME_CITATION,
            underived=_underived_frame_entry(),
        )
    ]
    for limit in limits:
        moved = solution.displacement(limit.node)
        if limit.freedom is None:
            measured, label = moved.translation, "resultant translation"
        else:
            measured = Quantity(magnitude=abs(getattr(moved, limit.freedom.value)), unit="m")
            label = limit.freedom.value
        comparison = Comparison(
            measured=measured,
            limit=limit.limit,
            sense=LimitSense.AT_MOST,
            measured_label=f"{limit.node} {label}",
            limit_label="the declared limit",
        )
        entries.append(
            ScorecardEntry(
                # The label is in the name because two limits on one node is ordinary —
                # a sway limit and a clearance — and two entries called the same thing is
                # a card a reader cannot act on.
                name=f"{limit.node} {label} deflection",
                status=CheckStatus.PASS if comparison.passes() else CheckStatus.FAIL,
                detail=(
                    f"{comparison.sentence()} ({limit.source})"
                    # The method in words, not the enum's own spelling: this line is what
                    # a report, a terminal and an evidence bundle print, and
                    # `first_order_elastic` is a key and not English.
                    f"{COMPUTED_FROM}{frame.name} {_SOLVE_CHECK} by {solution.method}"
                ),
                reference=limit.source,
                comparison=comparison,
                underived=_underived_frame_entry(),
            )
        )
    return Scorecard(entries=tuple(entries))


def _underived_frame_entry() -> Underived:
    """Why a frame entry shows no worked line: the answer came out of a factorisation."""
    return Underived(
        kind=DerivationAbsence.NUMERIC_RESULT,
        reason=(
            "the displacement is the solution of the frame's stiffness equations, solved "
            "rather than evaluated, so there is no substitutable line to show; the inputs "
            "are the frame's own declaration"
        ),
    )


# --- the frame as a node of a dependency chain ---------------------------------------

#: What a frame hands downstream, per member, and the dimension each is in. Written here
#: once so the node's declaration and the values it produces cannot drift apart: the
#: gate in `anvilate.dependency` compares them textually at registration, and a member
#: check that bound a moment to a force would be caught there rather than on the first
#: frame that runs.
MEMBER_OUTPUTS: dict[str, str] = {
    "axial": "[force]",
    "shear_y": "[force]",
    "shear_z": "[force]",
    "torsion": "[force] * [length]",
    "moment_y": "[force] * [length]",
    "moment_z": "[force] * [length]",
}


def frame_check_node(frame: Frame, *, check_id: str = _SOLVE_CHECK) -> CheckNode:
    """The frame as one node of a dependency graph, producing every member's forces.

    A member check downstream declares ``Consumes(upstream=check_id,
    output="beam.moment_z", parameter="moment", dimension="[force] * [length]")`` and is
    then *ordered after* the solve, fed the solved value, and — this is the part that
    matters — reported ``NOT_EVALUATED`` naming the frame when the frame did not solve.
    A member check handed a default in place of a force nobody computed is the silent
    green the rest of this library refuses.

    Output names are ``<member>.<quantity>``. The quantities are the six of
    :data:`MEMBER_OUTPUTS`, and the moments are the **larger end moment by magnitude**,
    which is what a member check is written against.
    """
    return CheckNode(
        id=check_id,
        produces=tuple(
            Output(name=f"{member.name}.{quantity}", dimension=dimension)
            for member in frame.members
            for quantity, dimension in MEMBER_OUTPUTS.items()
        ),
    )


def frame_outputs(solution: FrameSolution) -> dict[str, Quantity]:
    """Every member force a downstream check can consume, keyed as the node declares it.

    The moments are the larger of the two ends by magnitude, and the shears likewise: a
    member check takes one number, and the end that is not governing is not the one to
    hand it. The axial force is tension positive, as :attr:`MemberEndForces.axial` is.
    """
    values: dict[str, Quantity] = {}
    for force in solution.member_forces:
        worst_shear_y = max(abs(force.shear_y_start), abs(force.shear_y_end))
        worst_shear_z = max(abs(force.shear_z_start), abs(force.shear_z_end))
        worst_torsion = max(abs(force.torsion_start), abs(force.torsion_end))
        values[f"{force.member}.axial"] = force.axial
        values[f"{force.member}.shear_y"] = Quantity(magnitude=worst_shear_y, unit="N")
        values[f"{force.member}.shear_z"] = Quantity(magnitude=worst_shear_z, unit="N")
        values[f"{force.member}.torsion"] = Quantity(magnitude=worst_torsion, unit="N*m")
        values[f"{force.member}.moment_y"] = force.worst_moment_y
        values[f"{force.member}.moment_z"] = force.worst_moment_z
    return values


class ItemAgreement(StatableModel):
    """One built part, and what the frame says about it.

    ``modelled_length`` is the total of the members that name the part; ``built_length``
    is the longest dimension of the part where its mates put it. They are compared, and
    not assumed equal: a frame whose members are the lengths the engineer meant and a
    build whose parts are the lengths the mates produced is the commonest way a solve
    describes a structure nobody is going to make.
    """

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    item: Named
    members: tuple[str, ...]
    modelled_length: Quantity
    built_length: Quantity
    #: The largest of the part's two cross-section dimensions, which bounds how much of
    #: its length a joint at each end can swallow.
    section_depth: Quantity

    @property
    def over_modelled(self) -> float:
        """How much longer the model is than the part, as a fraction of the part.

        Positive is steel that is not there, and that is always wrong: a member cannot
        be longer than the part it is.
        """
        built = self.built_length.to("m").magnitude
        return (self.modelled_length.to("m").magnitude - built) / built

    @property
    def shortfall(self) -> Quantity:
        """How much of the part the model leaves out, which a joint at each end explains."""
        missing = self.built_length.to("m").magnitude - self.modelled_length.to("m").magnitude
        return Quantity(magnitude=max(0.0, missing), unit="m")

    @property
    def joint_allowance(self) -> Quantity:
        """Twice the part's section depth: the most two joints can account for."""
        return Quantity(magnitude=2.0 * self.section_depth.to("m").magnitude, unit="m")

    @property
    def explained(self) -> bool:
        """Is the difference one two joints can account for, or a different part?"""
        return self.over_modelled <= ITEM_LENGTH_TOLERANCE and self.shortfall.to(
            "m"
        ).magnitude <= self.joint_allowance.to("m").magnitude * (1.0 + ITEM_LENGTH_TOLERANCE)

    def __str__(self) -> str:
        return (
            f"{self.item}: {', '.join(self.members)} model {self.modelled_length} of a "
            f"{self.built_length} part, {self.shortfall} short against a "
            f"{self.joint_allowance} joint allowance"
        )


_ITEM_SOURCE = "the combination document: its parts, and the mates that place them"
#: Three of the four checks compare one set of names with another, so they share one
#: sentence rather than composing it three times.
_NAMES_NOT_A_FORMULA = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason="the frame's names are read against the build's; there is no formula to work",
)

#: A node at a mate is at the mate's own point, and a part's length is read off a solid
#: built to a rounded dimension, so the two never agree to the micrometre. A twentieth is
#: wide enough for that and narrow enough to catch a member that models the wrong part.
ITEM_LENGTH_TOLERANCE = 0.05


def frame_over_combination_scorecard(frame: Frame, built: object) -> Scorecard:
    """Does the declared frame describe the combination it names? → a scorecard.

    A frame and a combination are two documents about one structure, and nothing has
    held them to each other: the frame solves, the combination draws and exports, and a
    member that models the wrong part passes every check it has on a force computed for
    a structure that is not being built.

    Three checks, each over the whole document rather than one part:

    1. **Every member's ``item`` is a part of the combination.** A member naming a part
       that is not there is a frame of a different build.
    2. **Every part of the combination is named by a member**, or the entry says which
       parts are not modelled. A part left out of the frame carries no force in the solve
       and still carries load in the shop.
    3. **Each named part's modelled length is one the part can account for.** A
       centreline model is *shorter* than its part, by however much of each end the
       joints swallow, so the two are not compared for equality. Two things are refused:
       a model **longer** than its part, which is steel that is not there, and a
       shortfall larger than twice the part's section depth, which is the most two joints
       can account for and so marks a member that is modelling a different part.

    A frame whose members name no items at all is reported ``NOT_EVALUATED``: nothing was
    claimed, so nothing is confirmed, and that is a different fact from agreement.
    """
    parts = {part.id: part for part in getattr(built, "parts", ())}
    mates = {mate for mate, _part in getattr(built, "placed_by", ())}
    named: dict[str, list[FrameMember]] = {}
    for member in frame.members:
        if member.item:
            named.setdefault(member.item, []).append(member)
    at = {node.name: node for node in frame.nodes}

    if not named:
        return Scorecard(
            entries=(
                ScorecardEntry(
                    name=f"{frame.name} over {getattr(built, 'name', 'the combination')}",
                    status=CheckStatus.NOT_EVALUATED,
                    detail=(
                        "not evaluated — no member of this frame names the part it models, "
                        "so there is nothing to hold the two documents to each other. Set "
                        "`item` on each member to the combination part id it is"
                    ),
                    reference=_ITEM_SOURCE,
                    needs=(
                        Need(
                            declaration="members[].item",
                            takes="the combination part id each member models",
                            sources=(ValueSource.USER,),
                        ),
                    ),
                    underived=Underived(
                        kind=DerivationAbsence.LOOKUP,
                        reason=(
                            "two documents are read against each other; there is no formula "
                            "to work, only a set of names and a set of lengths"
                        ),
                    ),
                ),
            )
        )

    entries: list[ScorecardEntry] = []
    strangers = sorted({item for item in named if item not in parts})
    entries.append(
        ScorecardEntry(
            name=f"{frame.name} members name built parts",
            status=CheckStatus.FAIL if strangers else CheckStatus.PASS,
            detail=(
                f"{len(named)} of the frame's {len(frame.members)} members name a part; "
                + (
                    f"{', '.join(strangers)} {'are' if len(strangers) > 1 else 'is'} not a "
                    f"part of this combination, whose parts are {', '.join(sorted(parts))}"
                    if strangers
                    else "every one is a part of this combination"
                )
            ),
            reference=_ITEM_SOURCE,
            underived=_NAMES_NOT_A_FORMULA,
        )
    )

    unmodelled = sorted(set(parts) - set(named))
    entries.append(
        ScorecardEntry(
            name=f"{frame.name} covers every built part",
            status=CheckStatus.FAIL if unmodelled else CheckStatus.PASS,
            detail=(
                f"{', '.join(unmodelled)} {'carry' if len(unmodelled) > 1 else 'carries'} "
                f"no force in this frame and will carry load in the shop; name "
                f"{'them' if len(unmodelled) > 1 else 'it'} on a member, or take "
                f"{'them' if len(unmodelled) > 1 else 'it'} out of the build"
                if unmodelled
                else f"all {len(parts)} parts of the combination are modelled"
            ),
            reference=_ITEM_SOURCE,
            underived=_NAMES_NOT_A_FORMULA,
        )
    )

    agreements: list[ItemAgreement] = []
    for item in sorted(set(named) & set(parts)):
        total = 0.0
        for member in named[item]:
            start, end = at[member.start].metres, at[member.end].metres
            total += sqrt(sum((a - b) ** 2 for a, b in zip(start, end, strict=True)))
        box = parts[item].shape.bounding_box()
        sides = sorted((box.size.X, box.size.Y, box.size.Z))
        agreements.append(
            ItemAgreement(
                item=item,
                members=tuple(member.name for member in named[item]),
                modelled_length=Quantity(magnitude=total, unit="m"),
                built_length=Quantity(magnitude=sides[2] / 1000.0, unit="m"),
                section_depth=Quantity(magnitude=sides[1] / 1000.0, unit="m"),
            )
        )
    unexplained = [item for item in agreements if not item.explained]
    if agreements:
        worst = max(agreements, key=lambda a: a.shortfall.to("m").magnitude)
        entries.append(
            ScorecardEntry(
                name=f"{frame.name} member lengths are ones the build can account for",
                status=CheckStatus.FAIL if unexplained else CheckStatus.PASS,
                detail=(
                    "; ".join(str(item) for item in unexplained)
                    + " — a model longer than its part is steel that is not there, and a "
                    "shortfall past two joints' worth is a member modelling a different part"
                    if unexplained
                    else f"the largest difference is {worst}, which its two joints account for"
                ),
                reference=_ITEM_SOURCE,
                underived=Underived(
                    kind=DerivationAbsence.LOOKUP,
                    reason=(
                        "each length is read off a document — one declared, one measured "
                        "on the placed solid — and the two are compared"
                    ),
                ),
            )
        )

    strayed = sorted({node.at for node in frame.nodes if node.at and node.at not in mates})
    if any(node.at for node in frame.nodes):
        entries.append(
            ScorecardEntry(
                name=f"{frame.name} nodes sit at mates of the build",
                status=CheckStatus.FAIL if strayed else CheckStatus.PASS,
                detail=(
                    f"{', '.join(strayed)} {'are' if len(strayed) > 1 else 'is'} not a mate "
                    f"of this combination, so the solve's reaction there is on no joint"
                    if strayed
                    else "every node that names a connection names a mate of this build"
                ),
                reference=_ITEM_SOURCE,
                underived=_NAMES_NOT_A_FORMULA,
            )
        )
    return Scorecard(entries=tuple(entries))
