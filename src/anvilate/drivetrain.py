"""Drive trains: shaft speeds, torques and gear forces derived from one declared input.

A gearbox is screened mesh by mesh today, each with a torque somebody typed. The torques are
not independent: one input power and speed, and the tooth counts of every mesh, decide every
shaft's speed and torque. A typed torque that disagrees with them is a second source of
truth, and the mesh screened on it is screened on a number the machine does not see.

A :class:`DriveTrain` declares the machine instead: its shafts and what each carries (by
item path), its gears with their teeth, the meshes between them with a declared and cited
efficiency, one input, and the output it must deliver. :func:`derive_flow` walks the gear
graph from the input and derives every shaft's speed, torque and power, and every mesh's
pitch-line velocity and tangential load. It refuses what a machine cannot be:

- a gear no shaft carries, or two shafts carrying one gear;
- a shaft whose speed two paths determine differently, or one nothing drives;
- a mesh whose declared center distance is not the sum of its gears' pitch radii;
- a layout declared reverted whose stages do not share one center distance.

:func:`screen_output_speed` holds the output speed against the required band, and
:func:`check_typed_torque` refuses a torque typed on a mesh inside the train that
contradicts the one the flow derives.
"""

from __future__ import annotations

from math import cos, hypot, isclose, pi, sin, tan
from typing import TYPE_CHECKING

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel

if TYPE_CHECKING:  # the bearing demand type lives with the component record that reads it
    from .components import Demand
from .derivation import DerivationAbsence, Underived
from .refusal import RefusalError, Remedy
from .scorecard import (
    CheckStatus,
    Comparison,
    LimitSense,
    Need,
    ScorecardEntry,
    ValueSource,
)
from .units import Quantity

__all__ = [
    "Gear",
    "DriveShaft",
    "Mesh",
    "DriveInput",
    "RequiredOutput",
    "DriveTrain",
    "ShaftState",
    "MeshState",
    "DriveFlow",
    "ShaftStiffness",
    "ShaftSupport",
    "ShaftStation",
    "SupportReaction",
    "StationMoment",
    "ShaftStatics",
    "derive_flow",
    "screen_output_speed",
    "check_typed_torque",
    "solve_shaft_statics",
    "bearing_demands",
    "CurvePoint",
    "ShaftCurve",
    "solve_shaft_curve",
    "screen_shaft_curve",
]

_SOURCE = "the drive train declaration: shafts, gears, meshes, the input and the output"


class _DriveTrainInputError(RefusalError, ValueError):
    """A drive-train declaration that cannot be used without correction."""


def _refuse(message: str, *, subject: str) -> _DriveTrainInputError:
    return _DriveTrainInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=_SOURCE),)
    )


def _of(value: Quantity, dimension: str, *, name: str) -> Quantity:
    if not isinstance(value, Quantity) or not value.has_dimension(dimension):
        raise _refuse(f"{name} is a {dimension} quantity; got {value!r}", subject=name)
    if not value.magnitude > 0:
        raise _refuse(f"{name} must be positive; got {value}", subject=name)
    return value


def _of_angle(value: Quantity, *, name: str) -> float:
    """An angle in degrees, and not a length someone meant as one.

    Finiteness is the document's rule, applied on the field; see :func:`_at`.
    """
    if not isinstance(value, Quantity) or not value.has_dimension("[]"):
        raise _refuse(f"{name} is an angle; got {value!r}", subject=name)
    return value.to("degree").magnitude


class Gear(StatableModel):
    """One gear: the item it is, its teeth, and its pitch diameter when declared."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    item: Named
    teeth: int = Field(ge=1, le=10_000, strict=True)
    pitch_diameter: Quantity | None = None

    @model_validator(mode="after")
    def _sized(self) -> Gear:
        if self.pitch_diameter is not None:
            _of(self.pitch_diameter, "[length]", name=f"{self.item} pitch_diameter")
        return self


def _at(value: Quantity, *, name: str) -> float:
    """An axial position along a shaft, in metres: any length from the declarer's datum.

    Zero and negative are both positions, so the only thing to check is the dimension. A
    non-finite one never reaches here: every model that declares a position opts into the
    document's finite rule, which refuses it by name on the field.
    """
    if not isinstance(value, Quantity) or not value.has_dimension("[length]"):
        raise _refuse(f"{name} is a [length] quantity; got {value!r}", subject=name)
    return value.to("m").magnitude


def _limits(
    slope: Quantity | None, deflection: Quantity | None, source: Provenance | None, what: str
) -> None:
    """A declared bending limit says what it is and where it came from, or says nothing."""
    if slope is not None:
        _of_angle(slope, name=f"{what} slope_limit")
    if deflection is not None:
        _of(deflection, "[length]", name=f"{what} deflection_limit")
    given = slope is not None or deflection is not None
    if given and source is None:
        raise _refuse(f"{what} declares a bending limit and no limit_source; a limit nothing "
                      "is held to is a number somebody remembered",
                      subject="limit_source")  # fmt: skip
    if source is not None and not given:
        raise _refuse(f"{what} gives a limit_source and no slope_limit or deflection_limit; "
                      "the source is the basis of a limit", subject="slope_limit, "
                      "deflection_limit")  # fmt: skip


class ShaftStiffness(StatableModel):
    """What a shaft's bending resists with: a prismatic shaft's diameter and its modulus.

    One diameter, because the elastic curve this feeds is the prismatic case. A stepped
    shaft bends on a diameter that changes along it, and averaging the steps would report a
    deflection nothing has; such a shaft is refused rather than approximated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    diameter: Quantity
    elastic_modulus: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _real(self) -> ShaftStiffness:
        _of(self.diameter, "[length]", name="shaft diameter")
        _of(self.elastic_modulus, "[pressure]", name="shaft elastic_modulus")
        return self


class ShaftSupport(StatableModel):
    """One bearing on a shaft, at an axial position.

    A shaft with more than two supports is statically indeterminate: its reactions do not
    follow from equilibrium alone. Such a shaft is named as indeterminate and refused, unless
    every support declares the ``share`` of the load it takes and the ``source`` that share
    rests on. Two supports need neither.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    name: Named
    at: Quantity
    share: float | None = Field(default=None, gt=0, le=1, allow_inf_nan=False)
    source: Provenance | None = None
    # What this bearing will take of the shaft's bending, where the document says so. Both
    # are what the point is held to, never a default: a tapered roller bearing and a
    # self-aligning one differ by two orders of magnitude in the slope they accept.
    slope_limit: Quantity | None = None
    deflection_limit: Quantity | None = None
    limit_source: Provenance | None = None

    @model_validator(mode="after")
    def _placed(self) -> ShaftSupport:
        _at(self.at, name=f"support {self.name} at")
        _limits(self.slope_limit, self.deflection_limit, self.limit_source, f"support {self.name}")
        if self.share is not None and self.source is None:
            raise _refuse(f"support {self.name} declares a share of {self.share:g} and no "
                          "source; a split a shaft's statics cannot give is only as good as "
                          "what it rests on", subject="source")  # fmt: skip
        if self.share is None and self.source is not None:
            raise _refuse(f"support {self.name} gives a source and no share; the source is "
                          "the basis of a declared share", subject="share")  # fmt: skip
        return self


class ShaftStation(StatableModel):
    """A carried item's axial position on its shaft; a gear's station is where its mesh pulls."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    item: Named
    at: Quantity
    slope_limit: Quantity | None = None
    deflection_limit: Quantity | None = None
    limit_source: Provenance | None = None

    @model_validator(mode="after")
    def _placed(self) -> ShaftStation:
        _at(self.at, name=f"station {self.item} at")
        _limits(self.slope_limit, self.deflection_limit, self.limit_source, f"station {self.item}")
        return self


class DriveShaft(StatableModel):
    """One shaft, the items it carries by item path, and where its bearings and items sit.

    ``supports`` and ``stations`` are what :func:`solve_shaft_statics` reads; a shaft that
    declares neither still carries its speed, torque and power through the flow.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    name: Named
    carries: tuple[Named, ...] = Field(min_length=1, max_length=64)
    supports: tuple[ShaftSupport, ...] = Field(default=(), max_length=16)
    stations: tuple[ShaftStation, ...] = Field(default=(), max_length=64)
    stiffness: ShaftStiffness | None = None

    @model_validator(mode="after")
    def _laid_out(self) -> DriveShaft:
        for named, label in ((tuple(s.name for s in self.supports), "supports"),
                             (tuple(s.item for s in self.stations), "stations")):  # fmt: skip
            twice = sorted({n for n in named if named.count(n) > 1})
            if twice:
                raise _refuse(f"shaft {self.name} declares {label} {twice} twice",
                              subject=label)  # fmt: skip
        placed = {s.item for s in self.stations}
        stray = sorted(placed - set(self.carries))
        if stray:
            raise _refuse(f"shaft {self.name} stations {stray}, which it does not carry; a "
                          "station places an item the shaft carries",
                          subject="stations")  # fmt: skip
        declared = [s for s in self.supports if s.share is not None]
        if declared and len(declared) != len(self.supports):
            raise _refuse(f"shaft {self.name} declares a load share on some of its supports "
                          "and not others; a declared split gives every support its share",
                          subject="supports")  # fmt: skip
        if declared and not isclose(sum(s.share or 0.0 for s in self.supports), 1.0,
                                    rel_tol=1e-6):  # fmt: skip
            raise _refuse(f"shaft {self.name} declares support shares summing to "
                          f"{sum(s.share or 0.0 for s in self.supports):.4g}, not 1",
                          subject="share")  # fmt: skip
        return self


class Mesh(StatableModel):
    """Two gears in mesh: which drives, the efficiency and its source, the center distance.

    ``efficiency`` is the fraction of power the mesh passes on, declared with ``source``;
    a lossless analysis declares 1.0 and says so. ``stage`` groups the meshes a reverted
    layout requires to share one center distance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    name: Named
    driver: Named
    driven: Named
    efficiency: float = Field(gt=0, le=1, allow_inf_nan=False)
    source: Provenance
    center_distance: Quantity | None = None
    # The transverse pressure angle, declared: it splits the tangential load into the
    # radial load that bends the shafts. No default, because 14.5, 20 and 25 degrees all ship.
    pressure_angle: Quantity | None = None
    # Where this mesh pulls, about the shaft axis: the angle from +y to the line joining the
    # two gear centres, driver towards driven, seen looking along +x. A shaft carrying two
    # loaded gears needs it, because the two mesh loads do not act in one plane.
    line_of_centers: Quantity | None = None

    @model_validator(mode="after")
    def _distinct(self) -> Mesh:
        if self.driver == self.driven:
            raise _refuse(f"mesh {self.name} names {self.driver} as both gears",
                          subject="driver, driven")  # fmt: skip
        if self.center_distance is not None:
            _of(self.center_distance, "[length]", name=f"{self.name} center_distance")
        if self.pressure_angle is not None:
            degrees = _of(self.pressure_angle, "[]", name=f"{self.name} pressure_angle")
            if not 0 < degrees.to("degree").magnitude < 45:
                raise _refuse(f"{self.name} pressure_angle {self.pressure_angle} is outside "
                              "0 to 45 degrees", subject="pressure_angle")  # fmt: skip
        if self.line_of_centers is not None:
            angle = _of_angle(self.line_of_centers, name=f"{self.name} line_of_centers")
            if not -360 <= angle <= 360:
                raise _refuse(f"{self.name} line_of_centers {self.line_of_centers} is outside "
                              "-360 to 360 degrees", subject="line_of_centers")  # fmt: skip
        return self


class DriveInput(StatableModel):
    """The one input: the shaft driven, its speed, and its power or its torque."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    shaft: Named
    speed: Quantity
    power: Quantity | None = None
    torque: Quantity | None = None

    @model_validator(mode="after")
    def _one_of(self) -> DriveInput:
        _of(self.speed, "1/[time]", name="input speed")
        if (self.power is None) == (self.torque is None):
            raise _refuse("the input gives its power or its torque, one of them",
                          subject="power, torque")  # fmt: skip
        if self.power is not None:
            _of(self.power, "[power]", name="input power")
        if self.torque is not None:
            _of(self.torque, "[torque]", name="input torque")
        return self


class RequiredOutput(StatableModel):
    """The output the train must deliver: the shaft, its speed band, and the life it runs.

    ``life`` is the running time the train must reach, and it is what every bearing's ISO 281
    rating life is held against. It is optional because a train may be screened on its
    kinematics alone; without it the bearing demands say so rather than assuming one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    shaft: Named
    speed_low: Quantity
    speed_high: Quantity
    source: Provenance
    life: Quantity | None = None

    @model_validator(mode="after")
    def _band(self) -> RequiredOutput:
        low = _of(self.speed_low, "1/[time]", name="speed_low").to("rpm").magnitude
        high = _of(self.speed_high, "1/[time]", name="speed_high").to("rpm").magnitude
        if low > high:
            raise _refuse(f"speed_low {self.speed_low} is above speed_high {self.speed_high}",
                          subject="speed_low, speed_high")  # fmt: skip
        if self.life is not None:
            _of(self.life, "[time]", name="required life")
        return self


class DriveTrain(StatableModel):
    """A declared drive train over a product's items."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    # A product document declares this, so every number in it is finite.
    states_requirements = True

    shafts: tuple[DriveShaft, ...] = Field(min_length=1, max_length=64)
    gears: tuple[Gear, ...] = Field(min_length=2, max_length=128)
    meshes: tuple[Mesh, ...] = Field(min_length=1, max_length=128)
    input: DriveInput
    output: RequiredOutput | None = None
    reverted: bool = False


class ShaftState(StatableModel):
    """One shaft's derived speed, torque and power."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shaft: Named
    speed: Quantity
    torque: Quantity
    power: Quantity

    def __str__(self) -> str:
        return (f"{self.shaft}: {self.speed.to('rpm').magnitude:.4g} rpm, "
                f"{self.torque.to('N*m').magnitude:.4g} N·m, "
                f"{self.power.to('kW').magnitude:.4g} kW")  # fmt: skip


class MeshState(StatableModel):
    """One mesh's driver torque, and its pitch-line velocity and tangential load when the
    driver's pitch diameter is declared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mesh: Named
    driver_torque: Quantity
    pitch_line_velocity: Quantity | None = None
    tangential_load: Quantity | None = None
    radial_load: Quantity | None = None
    total_load: Quantity | None = None


class DriveFlow(StatableModel):
    """Every shaft's speed, torque and power, and every mesh's loads, from one input."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shafts: tuple[ShaftState, ...]
    meshes: tuple[MeshState, ...]

    def shaft(self, name: str) -> ShaftState:
        """One shaft's state, by name."""
        for state in self.shafts:
            if state.shaft == name:
                return state
        raise _refuse(f"no shaft is named {name!r}; the train has "
                      f"{[s.shaft for s in self.shafts]}", subject="shaft")  # fmt: skip

    def __str__(self) -> str:
        return "\n".join(str(state) for state in self.shafts)


def _carriers(train: DriveTrain) -> dict[str, str]:
    held: dict[str, str] = {}
    for shaft in train.shafts:
        for item in shaft.carries:
            if item in held:
                raise _refuse(f"{item} is carried by two shafts, {held[item]} and {shaft.name}; "
                              "a gear sits on exactly one", subject="shafts")  # fmt: skip
            held[item] = shaft.name
    return held


def derive_flow(train: DriveTrain) -> DriveFlow:
    """Every shaft's speed, torque and power, derived from the input through each mesh.

    A driven gear turns at the driver's speed times the driver's teeth over its own, and
    receives the driver's power times the mesh efficiency. Refused, naming what to correct:
    a gear on no shaft, a shaft two paths give different speeds, a shaft nothing drives, a
    center distance that does not close, a reverted layout whose stages differ.
    """
    if not isinstance(train, DriveTrain):
        raise _refuse("train must be a DriveTrain", subject="train")
    names = [s.name for s in train.shafts]
    if len(set(names)) != len(names):
        raise _refuse(f"shafts {sorted({n for n in names if names.count(n) > 1})} are declared "
                      "twice", subject="shafts")  # fmt: skip
    gears = {g.item: g for g in train.gears}
    if len(gears) != len(train.gears):
        raise _refuse("a gear is declared twice", subject="gears")
    on = _carriers(train)
    for mesh in train.meshes:
        for gear in (mesh.driver, mesh.driven):
            if gear not in gears:
                raise _refuse(f"mesh {mesh.name} names {gear}, which is not a declared gear",
                              subject="meshes")  # fmt: skip
            if gear not in on:
                raise _refuse(f"mesh {mesh.name} names gear {gear}, which no shaft carries",
                              subject="shafts")  # fmt: skip
        if on[mesh.driver] == on[mesh.driven]:
            raise _refuse(f"mesh {mesh.name} joins two gears on one shaft, "
                          f"{on[mesh.driver]}", subject="meshes")  # fmt: skip
    if train.input.shaft not in names:
        raise _refuse(f"the input drives {train.input.shaft}, which is not a declared shaft",
                      subject="input")  # fmt: skip

    speed_in = train.input.speed.to("rad/s").magnitude
    given = train.input
    if given.power is not None:
        power_in = given.power.to("W").magnitude
    else:
        assert given.torque is not None  # the input's validator requires one of the two
        power_in = given.torque.to("N*m").magnitude * speed_in
    speed: dict[str, float] = {train.input.shaft: speed_in}
    power: dict[str, float] = {train.input.shaft: power_in}
    pending = list(train.meshes)
    mesh_states: dict[str, MeshState] = {}
    while pending:
        progressed = False
        for mesh in list(pending):
            driver_shaft, driven_shaft = on[mesh.driver], on[mesh.driven]
            if driver_shaft not in speed:
                continue
            ratio = gears[mesh.driver].teeth / gears[mesh.driven].teeth
            n_driven = speed[driver_shaft] * ratio
            p_driven = power[driver_shaft] * mesh.efficiency
            if driven_shaft in speed:
                if not isclose(speed[driven_shaft], n_driven, rel_tol=1e-9):
                    raise _refuse(
                        f"shaft {driven_shaft} turns at {speed[driven_shaft] * 30 / pi:.6g} rpm "
                        f"by one path and {n_driven * 30 / pi:.6g} rpm through mesh "
                        f"{mesh.name}; a shaft's speed is determined once",
                        subject="meshes",
                    )  # fmt: skip
            else:
                speed[driven_shaft], power[driven_shaft] = n_driven, p_driven
            torque = power[driver_shaft] / speed[driver_shaft]
            mesh_states[mesh.name] = _mesh_state(mesh, gears, torque, speed[driver_shaft])
            pending.remove(mesh)
            progressed = True
        if not progressed:
            stuck = sorted({on[m.driver] for m in pending} - set(speed))
            raise _refuse(f"meshes {[m.name for m in pending]} hang from shafts {stuck} that "
                          "nothing drives from the input", subject="meshes")  # fmt: skip
    undriven = [n for n in names if n not in speed]
    if undriven:
        raise _refuse(f"shafts {undriven} are driven by nothing from the input",
                      subject="shafts")  # fmt: skip
    _closes(train, gears)
    shafts = tuple(
        ShaftState(shaft=n, speed=Quantity(magnitude=speed[n] * 30 / pi, unit="rpm"),
                   torque=Quantity(magnitude=power[n] / speed[n], unit="N*m"),
                   power=Quantity(magnitude=power[n], unit="W"))
        for n in names
    )  # fmt: skip
    return DriveFlow(shafts=shafts, meshes=tuple(mesh_states[m.name] for m in train.meshes))


def _mesh_state(mesh: Mesh, gears: dict[str, Gear], torque: float, omega: float) -> MeshState:
    diameter = gears[mesh.driver].pitch_diameter
    if diameter is None:
        return MeshState(mesh=mesh.name, driver_torque=Quantity(magnitude=torque, unit="N*m"))
    radius = diameter.to("m").magnitude / 2
    tangential = torque / radius
    split: dict[str, Quantity] = {}
    if mesh.pressure_angle is not None:
        phi = mesh.pressure_angle.to("radian").magnitude
        split = {"radial_load": Quantity(magnitude=tangential * tan(phi), unit="N"),
                 "total_load": Quantity(magnitude=tangential / cos(phi), unit="N")}  # fmt: skip
    return MeshState(
        mesh=mesh.name, driver_torque=Quantity(magnitude=torque, unit="N*m"),
        pitch_line_velocity=Quantity(magnitude=omega * radius, unit="m/s"),
        tangential_load=Quantity(magnitude=tangential, unit="N"), **split,
    )  # fmt: skip


def _closes(train: DriveTrain, gears: dict[str, Gear]) -> None:
    sums: list[tuple[str, float]] = []
    for mesh in train.meshes:
        a, b = gears[mesh.driver].pitch_diameter, gears[mesh.driven].pitch_diameter
        computed = None if a is None or b is None else (a.to("m").magnitude
                                                         + b.to("m").magnitude) / 2  # fmt: skip
        declared = (None if mesh.center_distance is None
                    else mesh.center_distance.to("m").magnitude)  # fmt: skip
        if (computed is not None and declared is not None
                and not isclose(computed, declared, rel_tol=1e-3)):  # fmt: skip
            raise _refuse(
                f"mesh {mesh.name} declares a center distance of {declared * 1000:.4g} mm and "
                f"its pitch radii sum to {computed * 1000:.4g} mm", subject="center_distance",
            )  # fmt: skip
        distance = declared if declared is not None else computed
        if distance is not None:
            sums.append((mesh.name, distance))
    if train.reverted:
        if len(sums) < len(train.meshes):
            raise _refuse("a reverted layout is checked on its center distances; give each "
                          "mesh's center distance or both pitch diameters",
                          subject="center_distance")  # fmt: skip
        first = sums[0]
        for other in sums[1:]:
            if not isclose(first[1], other[1], rel_tol=1e-3):
                raise _refuse(
                    f"a reverted layout shares one center distance, and stage {first[0]} has "
                    f"{first[1] * 1000:.4g} mm while {other[0]} has {other[1] * 1000:.4g} mm",
                    subject="reverted",
                )  # fmt: skip


_BAND_COMPARISON = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason=(
        "a comparison of the output speed against the declared band; the speed itself is "
        "derived by the flow, mesh ratio by mesh ratio, and the comparison has no arithmetic "
        "of its own to substitute"
    ),
)


def screen_output_speed(train: DriveTrain, flow: DriveFlow) -> ScorecardEntry:
    """The output speed against the band the product requires, as a card entry."""
    if train.output is None:
        return ScorecardEntry(
            name="output speed", status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated: the drive train declares no required output band",
            underived=_BAND_COMPARISON,
            needs=(Need(declaration="drive_train.output",
                        takes="the output shaft and the speed band it must turn within, "
                              "with the requirement it comes from",
                        dimension="1/[time]", units=("rpm",), sources=(ValueSource.USER,)),),
        )  # fmt: skip
    rpm = flow.shaft(train.output.shaft).speed.to("rpm").magnitude
    low = train.output.speed_low.to("rpm").magnitude
    high = train.output.speed_high.to("rpm").magnitude
    inside = low <= rpm <= high
    return ScorecardEntry(
        name="output speed", status=CheckStatus.PASS if inside else CheckStatus.FAIL,
        detail=(f"{train.output.shaft} turns at {rpm:.4g} rpm, "
                f"{'inside' if inside else 'outside'} the required {low:g} to {high:g} rpm"),
        reference=train.output.source, underived=_BAND_COMPARISON,
    )  # fmt: skip


def check_typed_torque(flow: DriveFlow, mesh: str, torque: Quantity) -> None:
    """Refuse a torque typed on a mesh inside the train that the flow contradicts."""
    states = {m.mesh: m for m in flow.meshes}
    if mesh not in states:
        raise _refuse(f"no mesh is named {mesh!r}; the train has {sorted(states)}",
                      subject="mesh")  # fmt: skip
    typed = _of(torque, "[torque]", name="typed torque").to("N*m").magnitude
    derived = states[mesh].driver_torque.to("N*m").magnitude
    if not isclose(typed, derived, rel_tol=1e-3):
        raise _refuse(
            f"mesh {mesh} is typed with a driver torque of {typed:.4g} N·m and the drive "
            f"train derives {derived:.4g} N·m; inside a declared train the torque is the "
            "flow's, so leave it out", subject="torque",
        )  # fmt: skip


class SupportReaction(StatableModel):
    """What one bearing carries: the two cross-section components and their resultant."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    support: Named
    at: Quantity
    y: Quantity
    z: Quantity
    magnitude: Quantity
    share: float | None = None

    def __str__(self) -> str:
        return (f"{self.support} at {self.at.to('mm').magnitude:.4g} mm: "
                f"{self.magnitude.to('N').magnitude:.4g} N "
                f"({self.y.to('N').magnitude:+.4g}, {self.z.to('N').magnitude:+.4g})")  # fmt: skip


class StationMoment(StatableModel):
    """The bending moment at one point on the shaft, in each plane and in all."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at_item: Named
    at: Quantity
    in_xy: Quantity
    in_xz: Quantity
    magnitude: Quantity

    def __str__(self) -> str:
        return (f"{self.at_item} at {self.at.to('mm').magnitude:.4g} mm: "
                f"{self.magnitude.to('N*m').magnitude:.4g} N·m bending")  # fmt: skip


class ShaftStatics(StatableModel):
    """One shaft's bearing reactions and bending moments, or the reason it has none.

    ``determinate`` is true when two supports carry the shaft and equilibrium alone gives the
    reactions. It is false when more supports do, and the reactions come from the shares the
    document declares: then ``basis`` carries what those shares rest on, and ``moments`` is
    empty, because a split that equilibrium did not give cannot be integrated into a bending
    moment diagram without the shaft's stiffness.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    shaft: Named
    determinate: bool
    reactions: tuple[SupportReaction, ...] = Field(min_length=2, max_length=16)
    moments: tuple[StationMoment, ...] = Field(default=(), max_length=80)
    basis: tuple[Provenance, ...] = ()

    @property
    def peak(self) -> StationMoment | None:
        """The largest bending moment on the shaft, or None when none was derived."""
        return max(self.moments, key=lambda m: m.magnitude.to("N*m").magnitude, default=None)

    def reaction(self, name: str) -> SupportReaction:
        """One support's reaction, by name."""
        for found in self.reactions:
            if found.support == name:
                return found
        raise _refuse(f"shaft {self.shaft} has no support named {name!r}; it has "
                      f"{[r.support for r in self.reactions]}", subject="support")  # fmt: skip

    def __str__(self) -> str:
        how = ("two-bearing statics" if self.determinate
               else f"a declared split over {len(self.reactions)} supports")  # fmt: skip
        lines = [f"{self.shaft}: {how}", *(f"  {r}" for r in self.reactions)]
        if self.peak is not None:
            lines.append(f"  peak {self.peak}")
        return "\n".join(lines)


_LOADS_NEEDED = (
    "every mesh on the shaft declares both gears' pitch_diameter and its "
    "pressure_angle, so the tangential and radial loads are derived"
)


def _senses(train: DriveTrain, on: dict[str, str]) -> dict[str, float]:
    """Each shaft's rotation sense about +x, with the input shaft taken as +1.

    External gears reverse, so a driven shaft turns against its driver. Only the relative
    senses matter: flipping them all flips every tangential load together, which leaves every
    reaction and bending magnitude where it was.
    """
    sense = {train.input.shaft: 1.0}
    pending = list(train.meshes)
    while pending:
        for mesh in list(pending):
            driver, driven = on[mesh.driver], on[mesh.driven]
            if driver in sense:
                sense[driven] = -sense[driver]
                pending.remove(mesh)
                break
        else:  # pragma: no cover - derive_flow refuses a train whose graph does not close
            break
    return sense


def _mesh_loads(train: DriveTrain, flow: DriveFlow, shaft: str) -> list[tuple[float, float, float]]:
    """Each mesh load the shaft carries, as (position, F_y, F_z) in metres and newtons.

    Shared by the statics and the elastic curve, so the two can never disagree about
    what is pulling on the shaft.
    """
    here = next((s for s in train.shafts if s.name == shaft), None)
    if here is None:
        raise _refuse(f"no shaft is named {shaft!r}; the train has "
                      f"{sorted(s.name for s in train.shafts)}", subject="shaft")  # fmt: skip
    on = _carriers(train)
    states = {m.mesh: m for m in flow.meshes}
    foreign = sorted({m.name for m in train.meshes} - set(states))
    if foreign:
        raise _refuse(f"the flow does not carry meshes {foreign}, so it was not derived from "
                      "this train; pass the flow derive_flow returned for it",
                      subject="flow")  # fmt: skip
    station = {s.item: _at(s.at, name=f"station {s.item} at") for s in here.stations}
    mine = [m for m in train.meshes if shaft in (on[m.driver], on[m.driven])]
    if not mine:
        raise _refuse(f"shaft {shaft} carries no gear in any mesh, so no mesh load reaches "
                      "its bearings", subject="shafts")  # fmt: skip
    sense = _senses(train, on)
    loads: list[tuple[float, float, float]] = []  # (x, Fy, Fz)
    for mesh in mine:
        gear = mesh.driver if on[mesh.driver] == shaft else mesh.driven
        state = states[mesh.name]
        if state.tangential_load is None or state.radial_load is None:
            raise _refuse(
                f"mesh {mesh.name} has no tangential and radial load to apply at {gear}; "
                f"{_LOADS_NEEDED}", subject="pitch_diameter, pressure_angle",
            )  # fmt: skip
        if gear not in station:
            raise _refuse(f"shaft {shaft} carries {gear} and does not station it; a mesh load "
                          "is applied where its gear sits along the shaft",
                          subject="stations")  # fmt: skip
        if mesh.line_of_centers is None:
            if len(mine) > 1:
                raise _refuse(
                    f"shaft {shaft} carries {len(mine)} meshing gears, whose loads do not act "
                    f"in one plane, and mesh {mesh.name} declares no line_of_centers; give "
                    "each mesh the angle, about the shaft axis, of the line joining its gear "
                    "centres", subject="line_of_centers",
                )  # fmt: skip
            theta = 0.0
        else:
            theta = mesh.line_of_centers.to("radian").magnitude
        toward = (cos(theta), sin(theta))  # driver towards driven, in the cross-section
        across = (-sin(theta), cos(theta))  # x times toward: where the mesh drags the driven
        tangential = state.tangential_load.to("N").magnitude
        radial = state.radial_load.to("N").magnitude
        driving = on[mesh.driver] == shaft
        # The driven gear is dragged along +across and pushed away from the driver, along
        # +toward; the driver takes both back. The driver shaft's sense flips the drag.
        away = -1.0 if driving else 1.0
        drag = (-1.0 if driving else 1.0) * sense[on[mesh.driver]]
        loads.append((station[gear],
                      drag * tangential * across[0] + away * radial * toward[0],
                      drag * tangential * across[1] + away * radial * toward[1]))  # fmt: skip

    return loads


def solve_shaft_statics(train: DriveTrain, flow: DriveFlow, shaft: str) -> ShaftStatics:
    """One shaft's bearing reactions and bending moments from the mesh loads it carries.

    Each gear on the shaft is pulled by its mesh: the tangential load perpendicular to the
    line joining the gear centres, and the radial load along it, pushing the two gears apart.
    Both are resolved into the shaft's cross-section with the mesh's declared
    ``line_of_centers``; a shaft carrying one loaded gear needs no angle, since the reference
    plane may be taken as its line of centres. The input shaft is taken to turn
    counter-clockwise seen along +x.

    Two supports are solved by equilibrium. More than two are statically indeterminate: the
    shaft is named as such and refused, unless every support declares the share it takes and
    the source that share rests on, and then the reactions are those shares and no bending
    moment is derived from them.
    """
    if not isinstance(flow, DriveFlow):
        raise _refuse("flow must be the DriveFlow derive_flow returned", subject="flow")
    declared = {s.name: s for s in train.shafts}
    if shaft not in declared:
        raise _refuse(f"no shaft is named {shaft!r}; the train has {sorted(declared)}",
                      subject="shaft")  # fmt: skip
    here = declared[shaft]
    if len(here.supports) < 2:
        raise _refuse(f"shaft {shaft} declares {len(here.supports)} support(s); a shaft is "
                      "carried by at least two bearings, each at its axial position",
                      subject="supports")  # fmt: skip
    split = here.supports[0].share is not None  # the shaft validator holds all or none
    if split and len(here.supports) == 2:
        raise _refuse(f"shaft {shaft} declares load shares on its two supports, whose "
                      "reactions equilibrium already gives; drop the shares and let the "
                      "statics answer", subject="share")  # fmt: skip
    if not split and len(here.supports) > 2:
        raise _refuse(
            f"shaft {shaft} is statically indeterminate: {len(here.supports)} supports carry "
            "it and equilibrium gives two reactions; declare each support's share of the "
            "load with the source it rests on, or carry the shaft on two bearings",
            subject="supports",
        )  # fmt: skip

    loads = _mesh_loads(train, flow, shaft)
    total = (sum(f[1] for f in loads), sum(f[2] for f in loads))
    if split:
        reactions = tuple(
            _reaction(support, -(support.share or 0.0) * total[0],
                      -(support.share or 0.0) * total[1])
            for support in here.supports
        )  # fmt: skip
        basis = tuple(s.source for s in here.supports if s.source is not None)
        return ShaftStatics(shaft=shaft, determinate=False, reactions=reactions, basis=basis)

    first, second = here.supports
    x_a = _at(first.at, name=f"support {first.name} at")
    x_b = _at(second.at, name=f"support {second.name} at")
    if isclose(x_a, x_b, abs_tol=1e-9):
        raise _refuse(f"shaft {shaft} puts both its supports at "
                      f"{x_a * 1000:.4g} mm; two bearings carry a shaft over a span",
                      subject="supports")  # fmt: skip
    span = x_b - x_a
    r_b = (-sum(f[1] * (f[0] - x_a) for f in loads) / span,
           -sum(f[2] * (f[0] - x_a) for f in loads) / span)  # fmt: skip
    r_a = (-total[0] - r_b[0], -total[1] - r_b[1])
    reactions = (_reaction(first, *r_a), _reaction(second, *r_b))
    points = [*loads, (x_a, *r_a), (x_b, *r_b)]
    named = [*((s.item, _at(s.at, name=f"station {s.item} at")) for s in here.stations),
             (first.name, x_a), (second.name, x_b)]  # fmt: skip
    moments = tuple(_moment(name, x, points) for name, x in sorted(named, key=lambda pair: pair[1]))
    return ShaftStatics(shaft=shaft, determinate=True, reactions=reactions, moments=moments)


def _reaction(support: ShaftSupport, y: float, z: float) -> SupportReaction:
    return SupportReaction(
        support=support.name, at=support.at, y=Quantity(magnitude=y, unit="N"),
        z=Quantity(magnitude=z, unit="N"),
        magnitude=Quantity(magnitude=hypot(y, z), unit="N"), share=support.share,
    )  # fmt: skip


def _moment(name: str, x: float, points: list[tuple[float, float, float]]) -> StationMoment:
    in_xy = sum(f[1] * (x - f[0]) for f in points if f[0] < x)
    in_xz = sum(f[2] * (x - f[0]) for f in points if f[0] < x)
    return StationMoment(
        at_item=name, at=Quantity(magnitude=x * 1000, unit="mm"),
        in_xy=Quantity(magnitude=in_xy, unit="N*m"), in_xz=Quantity(magnitude=in_xz, unit="N*m"),
        magnitude=Quantity(magnitude=hypot(in_xy, in_xz), unit="N*m"),
    )  # fmt: skip


def bearing_demands(
    train: DriveTrain, flow: DriveFlow, shaft: str
) -> dict[str, tuple[Demand, ...]]:
    """What each bearing on one shaft is asked to carry, derived rather than typed.

    The existing rolling-bearing screen reads three demands — ``equivalent_load``, ``speed``
    and ``required_life`` — and until now a product typed all three beside the bearing. Two
    of them are not free: the load is the reaction :func:`solve_shaft_statics` derives, and
    the speed is the one :func:`derive_flow` derives for that shaft. This returns them, by
    support name, each ``Demand`` sourced to the derivation it came from, so the bearing's
    rating life is screened against the machine and the entry says where its numbers are from.

    ``required_life`` is the train's declared output life. Where the train declares none the
    demand is left out, and the bearing screen reports its life entry as not evaluated naming
    it, which is the honest answer: nothing here knows how long the product must run.

    The equivalent load is the radial reaction alone. A train with helical gears also loads
    its bearings axially, and until those axial loads are derived an equivalent load combining
    them with X and Y factors would be understating the demand, so it is not offered.
    """
    from .components import Demand

    statics = solve_shaft_statics(train, flow, shaft)
    speed = flow.shaft(shaft).speed
    rpm = speed.to("rpm").magnitude
    how = "two-bearing statics" if statics.determinate else "a declared support split"
    demands: dict[str, tuple[Demand, ...]] = {}
    for reaction in statics.reactions:
        each = [
            Demand(name="equivalent_load", value=reaction.magnitude,
                   source=f"the drive train's {how} on shaft {shaft}: the radial reaction at "
                          f"{reaction.support}"),
            Demand(name="speed", value=speed,
                   source=f"the drive train flow: shaft {shaft} turns at {rpm:.4g} rpm"),
        ]  # fmt: skip
        if train.output is not None and train.output.life is not None:
            each.append(Demand(name="required_life", value=train.output.life,
                               source=f"the drive train's required output life "
                                      f"({train.output.source})"))  # fmt: skip
        demands[reaction.support] = tuple(each)
    return demands


class CurvePoint(StatableModel):
    """How far the shaft has moved, and how far it has tilted, at one point along it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at_item: Named
    at: Quantity
    deflection: Quantity
    slope: Quantity

    def __str__(self) -> str:
        return (f"{self.at_item} at {self.at.to('mm').magnitude:.4g} mm: "
                f"{self.deflection.to('mm').magnitude:.4g} mm, "
                f"{self.slope.to('degree').magnitude:.4g}°")  # fmt: skip


class ShaftCurve(StatableModel):
    """One prismatic shaft's deflection and slope at every bearing and station on it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shaft: Named
    span: Quantity
    second_moment: Quantity
    points: tuple[CurvePoint, ...] = Field(min_length=2, max_length=80)

    @property
    def worst(self) -> CurvePoint:
        """The point that has moved furthest — the shape's headline, and never a support."""
        return max(self.points, key=lambda p: p.deflection.to("mm").magnitude)

    def point(self, name: str) -> CurvePoint:
        """One bearing's or station's point on the curve, by name."""
        for found in self.points:
            if found.at_item == name:
                return found
        raise _refuse(f"shaft {self.shaft} has no point named {name!r}; it has "
                      f"{[p.at_item for p in self.points]}", subject="at_item")  # fmt: skip

    def __str__(self) -> str:
        return "\n".join([f"{self.shaft} over {self.span.to('mm').magnitude:.4g} mm",
                          *(f"  {p}" for p in self.points)])  # fmt: skip


_CURVE_CITATION = (
    "Roark/Shigley, the elastic curve of a simply-supported prismatic beam under a point "
    "load, superposed over the shaft's mesh loads in two planes"
)


def solve_shaft_curve(train: DriveTrain, flow: DriveFlow, shaft: str) -> ShaftCurve:
    """The shaft's deflection and slope where each bearing and each carried item sits.

    Every mesh load the shaft carries is put on the elastic curve of a simply-supported
    prismatic beam between its two bearings, in each of the two cross-section planes, and
    the two planes are combined at each point: the deflection is the resultant of the two
    deflections and the slope the resultant of the two slopes. A gear's misalignment and a
    bearing's are read *where they sit*, which is why this is not the beam's single largest
    deflection.

    Refused, naming what to correct: a shaft with no declared ``stiffness``; a shaft whose
    reactions came from a declared split rather than from equilibrium, since a split
    equilibrium did not give does not carry a shape either; and a load outside the bearing
    span, because an overhung shaft is the overhanging-beam case and this is not it.
    """
    from .analysis.beam import (
        circular_second_moment,
        simply_supported_offset_load_deflection_at,
        simply_supported_offset_load_slope_at,
    )

    statics = solve_shaft_statics(train, flow, shaft)
    if not statics.determinate:
        raise _refuse(
            f"shaft {shaft} carries its load on a declared split over {len(statics.reactions)} "
            "supports, so its reactions do not come from equilibrium and neither does its "
            "shape; carry it on two bearings to read a deflection",
            subject="supports",
        )  # fmt: skip
    here = next(s for s in train.shafts if s.name == shaft)
    if here.stiffness is None:
        raise _refuse(f"shaft {shaft} declares no stiffness, so nothing here knows how far it "
                      "bends; give its diameter and elastic modulus with their source",
                      subject="stiffness")  # fmt: skip
    first, second = here.supports
    x_a = _at(first.at, name=f"support {first.name} at")
    x_b = _at(second.at, name=f"support {second.name} at")
    low, high = min(x_a, x_b), max(x_a, x_b)
    span = high - low
    second_moment = circular_second_moment(here.stiffness.diameter)
    common = {"length": Quantity(magnitude=span * 1000, unit="mm"),
              "second_moment": second_moment,
              "elastic_modulus": here.stiffness.elastic_modulus}  # fmt: skip

    loads = _mesh_loads(train, flow, shaft)
    for at, _, _ in loads:
        if not low < at < high:
            raise _refuse(
                f"shaft {shaft} carries a mesh load at {at * 1000:.4g} mm, outside the "
                f"{low * 1000:.4g} to {high * 1000:.4g} mm its bearings span; an overhung "
                "shaft bends as an overhanging beam, which this is not",
                subject="stations",
            )  # fmt: skip

    named = [*((s.item, _at(s.at, name=f"station {s.item} at")) for s in here.stations),
             (first.name, x_a), (second.name, x_b)]  # fmt: skip
    points = []
    for name, at in sorted(named, key=lambda pair: pair[1]):
        if not low <= at <= high:
            raise _refuse(f"shaft {shaft} stations {name} at {at * 1000:.4g} mm, outside the "
                          f"{low * 1000:.4g} to {high * 1000:.4g} mm its bearings span",
                          subject="stations")  # fmt: skip
        where = Quantity(magnitude=(at - low) * 1000, unit="mm")
        planes = []
        for component in (1, 2):
            deflection = slope = 0.0
            for load_at, *force in loads:
                each = {"force": Quantity(magnitude=force[component - 1], unit="N"),
                        "load_position": Quantity(magnitude=(load_at - low) * 1000, unit="mm"),
                        "position": where, **common}  # fmt: skip
                deflection += simply_supported_offset_load_deflection_at(**each).to("mm").magnitude
                slope += simply_supported_offset_load_slope_at(**each).to("degree").magnitude
            planes.append((deflection, slope))
        points.append(CurvePoint(
            at_item=name, at=Quantity(magnitude=at * 1000, unit="mm"),
            deflection=Quantity(magnitude=hypot(planes[0][0], planes[1][0]), unit="mm"),
            slope=Quantity(magnitude=hypot(planes[0][1], planes[1][1]), unit="degree"),
        ))  # fmt: skip
    return ShaftCurve(shaft=shaft, span=Quantity(magnitude=span * 1000, unit="mm"),
                      second_moment=second_moment, points=tuple(points))  # fmt: skip


_CURVE_UNDERIVED = Underived(
    kind=DerivationAbsence.LOOKUP,
    reason=(
        "a comparison of a deflection and a slope against the limits the document declares "
        "for the point; the two values are derived by the elastic curve, load by load and "
        "plane by plane, and the comparison has no arithmetic of its own to substitute"
    ),
)


def _limit_need(what: str, kind: str) -> Need:
    return Need(
        declaration=f"drive_train.shafts[].{what}.{kind}_limit",
        takes=f"the {kind} this point will take, and the bearing or gear data it comes from",
        dimension="[]" if kind == "slope" else "[length]",
        units=("degree",) if kind == "slope" else ("mm", "in"),
        sources=(ValueSource.USER,),
    )


def screen_shaft_curve(
    train: DriveTrain, flow: DriveFlow, shaft: str
) -> tuple[ScorecardEntry, ...]:
    """Each bearing's and gear's deflection and slope against the limit declared for it.

    One entry per declared limit. A point that declares none is not screened and not
    reported — it is the document's statement that nothing there is held — but a shaft where
    *no* point declares one gets a single not-evaluated entry naming the declaration, because
    a shaft screened on nothing looks exactly like a shaft that passed.

    No limit is supplied from this library. A tapered roller bearing and a self-aligning one
    differ by two orders of magnitude in the slope they take, and a limit is only worth what
    its source is worth, so each one is declared with the bearing or gear data it comes from.
    """
    curve = solve_shaft_curve(train, flow, shaft)
    here = next(s for s in train.shafts if s.name == shaft)
    declared = {**{s.name: s for s in here.supports}, **{s.item: s for s in here.stations}}
    entries: list[ScorecardEntry] = []
    for point in curve.points:
        limits = declared[point.at_item]
        for kind, value, limit in (
            ("slope", point.slope, limits.slope_limit),
            ("deflection", point.deflection, limits.deflection_limit),
        ):
            if limit is None:
                continue
            entries.append(ScorecardEntry(
                name=f"{shaft} {point.at_item} {kind}",
                status=(CheckStatus.PASS if _within(value, limit, kind) else CheckStatus.FAIL),
                detail=f"{point}, against a declared limit of {limit}",
                reference=limits.limit_source, underived=_CURVE_UNDERIVED,
                addresses=("a shaft bending enough to misalign its gears and bearings",),
                comparison=Comparison(measured=value, limit=limit, sense=LimitSense.AT_MOST,
                                      measured_label=f"{point.at_item} {kind}",
                                      limit_label="declared limit"),
            ))  # fmt: skip
    if entries:
        return tuple(entries)
    return (ScorecardEntry(
        name=f"{shaft} bending", status=CheckStatus.NOT_EVALUATED,
        detail=(f"not evaluated: shaft {shaft} bends {curve.worst}, and no point on it "
                "declares a limit"),
        underived=_CURVE_UNDERIVED,
        addresses=("a shaft bending enough to misalign its gears and bearings",),
        needs=(_limit_need("supports[]", "slope"), _limit_need("stations[]", "deflection")),
    ),)  # fmt: skip


def _within(value: Quantity, limit: Quantity, kind: str) -> bool:
    unit = "degree" if kind == "slope" else "mm"
    return value.to(unit).magnitude <= limit.to(unit).magnitude
