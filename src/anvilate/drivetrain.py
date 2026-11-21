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

from math import cos, isclose, pi, tan

from pydantic import ConfigDict, Field, model_validator

from ._models import Named, Provenance, StatableModel
from .derivation import DerivationAbsence, Underived
from .refusal import RefusalError, Remedy
from .scorecard import CheckStatus, Need, ScorecardEntry, ValueSource
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
    "derive_flow",
    "screen_output_speed",
    "check_typed_torque",
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


class Gear(StatableModel):
    """One gear: the item it is, its teeth, and its pitch diameter when declared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item: Named
    teeth: int = Field(ge=1, le=10_000, strict=True)
    pitch_diameter: Quantity | None = None

    @model_validator(mode="after")
    def _sized(self) -> Gear:
        if self.pitch_diameter is not None:
            _of(self.pitch_diameter, "[length]", name=f"{self.item} pitch_diameter")
        return self


class DriveShaft(StatableModel):
    """One shaft and the items it carries, gears among them, by item path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    carries: tuple[Named, ...] = Field(min_length=1, max_length=64)


class Mesh(StatableModel):
    """Two gears in mesh: which drives, the efficiency and its source, the center distance.

    ``efficiency`` is the fraction of power the mesh passes on, declared with ``source``;
    a lossless analysis declares 1.0 and says so. ``stage`` groups the meshes a reverted
    layout requires to share one center distance.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    driver: Named
    driven: Named
    efficiency: float = Field(gt=0, le=1, allow_inf_nan=False)
    source: Provenance
    center_distance: Quantity | None = None
    # The transverse pressure angle, declared: it splits the tangential load into the
    # radial load that bends the shafts. No default, because 14.5, 20 and 25 degrees all ship.
    pressure_angle: Quantity | None = None

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
        return self


class DriveInput(StatableModel):
    """The one input: the shaft driven, its speed, and its power or its torque."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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
    """The output the train must deliver: the shaft, and its speed band."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    shaft: Named
    speed_low: Quantity
    speed_high: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _band(self) -> RequiredOutput:
        low = _of(self.speed_low, "1/[time]", name="speed_low").to("rpm").magnitude
        high = _of(self.speed_high, "1/[time]", name="speed_high").to("rpm").magnitude
        if low > high:
            raise _refuse(f"speed_low {self.speed_low} is above speed_high {self.speed_high}",
                          subject="speed_low, speed_high")  # fmt: skip
        return self


class DriveTrain(StatableModel):
    """A declared drive train over a product's items."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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
