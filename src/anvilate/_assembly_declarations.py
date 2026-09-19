"""The declarations an assembly screen reads: parts, states, operations and their tools.

Kept apart from :mod:`anvilate.assembly`, which re-exports every one, so the Design Spec can
declare an assembly with them without importing the screens, which themselves take a spec.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import ConfigDict, model_validator

from ._models import Named, Provenance, StatableModel
from .units import Quantity

if TYPE_CHECKING:
    from .spec import Keepout

__all__: list[str] = []


class InsertionDirection(StrEnum):
    """The axis and sense a part travels along on its way into the assembly."""

    PLUS_X = "+x"
    MINUS_X = "-x"
    PLUS_Y = "+y"
    MINUS_Y = "-y"
    PLUS_Z = "+z"
    MINUS_Z = "-z"


class Part(StatableModel):
    """One part: how it goes in, what it takes up, and what it passes through on the way."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    insertion: InsertionDirection | None = None
    occupies: tuple[Named, ...] = ()
    sweeps: tuple[Named, ...] = ()

    @model_validator(mode="after")
    def _distinct(self) -> Part:
        for field, values in (("occupies", self.occupies), ("sweeps", self.sweeps)):
            if len(set(values)) != len(values):
                raise ValueError(f"part '{self.name}' names one feature twice in {field}")
        return self

    def __str__(self) -> str:
        how = f"inserted {self.insertion.value}" if self.insertion else "no insertion direction"
        return f"{self.name} ({how})"


class AssemblyState(StatableModel):
    """One state a build passes through, and the parts installed on reaching it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Named
    installs: tuple[Named, ...] = ()

    def __str__(self) -> str:
        parts = ", ".join(self.installs) if self.installs else "nothing new"
        return f"{self.name}: installs {parts}"


class Adjustment(StatableModel):
    """Something done to a feature in a given state, and the route a tool takes to it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: Named
    performed_in: Named
    access: tuple[Named, ...] = ()

    def __str__(self) -> str:
        route = " via " + ", ".join(self.access) if self.access else " with no access route"
        return f"adjust {self.feature} in {self.performed_in}{route}"


class ToolEnvelope(StatableModel):
    """The space a tool occupies while it works: the widest body along its reach.

    A socket, a hex key or a driver sweeps a cylinder from the fastener outward: the
    ``body_diameter`` is its widest section there and ``reach`` how far that section runs.
    No tool dimensions ship with the library; the numbers are the user's, from their tool
    catalogue or measured, and ``source`` records which, the same doctrine as a glass
    allowable (ISO 2936 and ISO 2725 state them, and neither is redistributable).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Named
    body_diameter: Quantity
    reach: Quantity
    source: Provenance

    @model_validator(mode="after")
    def _an_envelope(self) -> ToolEnvelope:
        for label, value in (("body_diameter", self.body_diameter), ("reach", self.reach)):
            if not value.has_dimension("[length]"):
                raise ValueError(f"'{self.tool}': {label} must be a length; got {value}")
            if not value.to("mm").magnitude > 0:
                raise ValueError(f"'{self.tool}': {label} must be positive; got {value}")
        return self


class AccessRequirement(StatableModel):
    """A feature a tool must reach, from the face it approaches, and the clearance it needs.

    The tool's envelope is generated as a keepout standing in front of ``face``, the tagged
    face the feature sits on, out to the tool's reach, and it is checked by the same
    intrusion mechanism as any other keepout (:func:`anvilate.keepouts.screen_keepouts`),
    against the part and every neighbouring body. There is no second collision check.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: Named
    face: Named
    tool: ToolEnvelope
    clearance_margin: Quantity = Quantity(magnitude=0.0, unit="mm")
    # The assembly state the tool is used in: access is judged against the parts installed
    # by then, never against the bare part alone.
    performed_in: Named | None = None

    def keepout(self) -> Keepout:
        """The tool's working envelope as a cylinder keepout in front of the face."""
        from .spec import CylinderKeepout, Keepout

        return Keepout(
            tag=f"access {self.feature} by {self.tool.tool}",
            anchor=self.face,
            rule=CylinderKeepout(diameter=self.tool.body_diameter, height=self.tool.reach),
            clearance_margin=self.clearance_margin,
            reason=(
                f"{self.tool.tool} must reach {self.feature} from {self.face} ({self.tool.source})"
            ),
            owner="assembly access",
            offset=Quantity(magnitude=-self.tool.reach.to("mm").magnitude, unit="mm"),
        )


class SwingRequirement(StatableModel):
    """A wrench that must turn a feature, the arc it needs, and the state it turns it in.

    The handle is a bar ``handle_length`` long from the feature's axis, ``handle_width`` wide
    and ``handle_thickness`` deep, turning in a plane ``height`` above ``face``. The arc is
    the user's to state, with its reason: 60° turns a hexagon one flat, 30° is enough for an
    open-end wrench that can be flipped. The dimensions come from the user's tool, with
    ``source`` saying which.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: Named
    face: Named
    handle_length: Quantity
    handle_width: Quantity
    handle_thickness: Quantity
    height: Quantity
    required_arc: Quantity
    source: Provenance
    performed_in: Named | None = None

    @model_validator(mode="after")
    def _a_swing(self) -> SwingRequirement:
        for label, value in (
            ("handle_length", self.handle_length),
            ("handle_width", self.handle_width),
            ("handle_thickness", self.handle_thickness),
            ("height", self.height),
        ):
            if not value.has_dimension("[length]") or value.to("mm").magnitude <= 0:
                raise ValueError(
                    f"'{self.feature}': {label} must be a positive length; got {value}"
                )
        arc = _degrees(self.required_arc, "required_arc")
        if not 0 < arc <= 360:
            raise ValueError(f"'{self.feature}': required_arc must lie in (0, 360]°; got {arc}")
        return self


def _degrees(value: Quantity, name: str) -> float:
    if str(value.unit).strip() not in {
        "deg",
        "degree",
        "°",
        "rad",
        "radian",
        "arcmin",
        "arcminute",
    }:
        raise ValueError(f"{name} must be an angle; got {value}")
    return value.to("degree").magnitude


class Inspection(StatableModel):
    """How a toleranced dimension is to be measured: the method, and the route to it.

    ``dimension`` is the tag of a toleranced dimension, ``method`` the declared inspection
    method (a height gauge, a CMM probe, a bore gauge), and ``access`` the features the
    instrument passes through to reach the dimension.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dimension: Named
    method: Named
    access: tuple[Named, ...] = ()
