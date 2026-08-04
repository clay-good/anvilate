"""The hydraulics discipline pack: declare a pump duty, get a scorecard.

The hydraulics pack serves the pump-system engineer the way :mod:`anvilate.packs.geotechnical`
serves the foundation engineer. A :class:`PumpDuty` declares the flow, head, fluid, and efficiency
of a pumping duty together with the selected motor rating and the pump's NPSH figures;
:func:`screen_pump_duty` checks the two things that most often bite — that the motor is big enough
for the shaft power (with margin), and that the available NPSH clears the required NPSH so the pump
does not cavitate. Each rolls into a cited PASS/FAIL scorecard entry with no silent green. These are
screening checks from pump hydraulics, not a code; the mechanical engineer of record owns the
selection.
"""

from __future__ import annotations

from math import pi

from pydantic import BaseModel, ConfigDict

from ..analysis import (
    darcy_friction_factor,
    darcy_weisbach_head_loss,
    minor_loss_head,
    pump_hydraulic_power,
    pump_shaft_power,
    reynolds_number,
)
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity

__all__ = [
    "PipeRun",
    "PumpDuty",
    "screen_pipe_run",
    "screen_pump_duty",
]

_MOTOR_REFERENCE = "Pump shaft power P = ρgQH/η"
_NPSH_REFERENCE = "NPSH available vs required (cavitation margin)"
_PIPE_REFERENCE = "Darcy-Weisbach friction + fitting minor losses"


class PumpDuty(BaseModel):
    """A pumping duty and the selected equipment, and what its screen needs.

    ``flow_rate`` Q, ``total_head`` H, and ``fluid_density`` ρ set the hydraulic duty; the
    ``efficiency`` η turns it into the shaft power the driver must supply. ``motor_rating`` is the
    selected motor's output power, and ``npsh_available`` / ``npsh_required`` are the suction-side
    figures (the former from the installation, the latter from the pump curve). All positive.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    flow_rate: Quantity
    total_head: Quantity
    fluid_density: Quantity
    efficiency: float
    motor_rating: Quantity
    npsh_available: Quantity
    npsh_required: Quantity


def screen_pump_duty(
    duty: PumpDuty,
    *,
    motor_service_factor: float = 1.0,
    npsh_margin_factor: float = 1.1,
) -> Scorecard:
    """Screen a :class:`PumpDuty` for motor adequacy and cavitation, and return its scorecard.

    Computes the shaft power the duty needs and screens the ``motor_rating`` against it (with a
    ``motor_service_factor``, usually 1.0–1.15), and screens the available NPSH against the required
    NPSH (with an ``npsh_margin_factor``, usually ~1.1, so there is a cushion against cavitation).
    Returns a :class:`~anvilate.scorecard.Scorecard` with a cited PASS/FAIL entry for each, no
    silent green.
    """
    hydraulic = pump_hydraulic_power(
        flow_rate=duty.flow_rate, head=duty.total_head, density=duty.fluid_density
    )
    shaft = (
        pump_shaft_power(hydraulic_power=hydraulic, efficiency=duty.efficiency).to("kW").magnitude
    )
    motor = duty.motor_rating.to("kW").magnitude
    motor_sf = motor / shaft if shaft > 0 else None
    motor_entry = ScorecardEntry.from_safety_factor(
        "motor rating", computed=motor_sf, required=motor_service_factor
    ).model_copy(update={"reference": _MOTOR_REFERENCE})

    npsh_a = duty.npsh_available.to("m").magnitude
    npsh_r = duty.npsh_required.to("m").magnitude
    npsh_sf = npsh_a / npsh_r if npsh_r > 0 else None
    npsh_entry = ScorecardEntry.from_safety_factor(
        "NPSH margin", computed=npsh_sf, required=npsh_margin_factor
    ).model_copy(update={"reference": _NPSH_REFERENCE})
    return Scorecard(entries=(motor_entry, npsh_entry))


class PipeRun(BaseModel):
    """A pressurized pipe run and the head available to drive it, and its screen inputs.

    ``flow_rate`` Q, inside ``diameter`` D, ``length`` L, and wall ``roughness`` ε set the friction
    loss; ``fitting_loss_coefficient`` ΣK is the summed minor-loss coefficient of the valves, bends,
    and fittings; and ``kinematic_viscosity`` ν is the fluid's (water is ~1e-6 m²/s). The
    ``available_head`` is the head the source (a pump, a reservoir) can supply against the losses.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    flow_rate: Quantity
    diameter: Quantity
    length: Quantity
    roughness: Quantity
    fitting_loss_coefficient: float
    kinematic_viscosity: Quantity
    available_head: Quantity


def screen_pipe_run(pipe: PipeRun) -> Scorecard:
    """Screen a :class:`PipeRun` for head budget and return its scorecard.

    Computes the mean velocity, the Darcy-Weisbach friction head, and the fitting minor losses, sums
    them, and screens the ``available_head`` against that total demand. Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited PASS/FAIL entry — the run works only if the
    source can supply more head than the pipe and fittings consume.
    """
    d = pipe.diameter.to("m").magnitude
    velocity = Quantity(
        magnitude=pipe.flow_rate.to("m**3/s").magnitude / (pi / 4 * d**2), unit="m/s"
    )
    reynolds = reynolds_number(
        velocity=velocity, diameter=pipe.diameter, kinematic_viscosity=pipe.kinematic_viscosity
    )
    friction_factor = darcy_friction_factor(
        reynolds=reynolds,
        relative_roughness=pipe.roughness.to("m").magnitude / d,
    )
    friction = (
        darcy_weisbach_head_loss(
            friction_factor=friction_factor,
            length=pipe.length,
            diameter=pipe.diameter,
            velocity=velocity,
        )
        .to("m")
        .magnitude
    )
    minor = (
        minor_loss_head(loss_coefficient=pipe.fitting_loss_coefficient, velocity=velocity)
        .to("m")
        .magnitude
    )
    total_loss = friction + minor
    available = pipe.available_head.to("m").magnitude
    ratio = available / total_loss if total_loss > 0 else None
    entry = ScorecardEntry.from_safety_factor(
        "head budget", computed=ratio, required=1.0
    ).model_copy(update={"reference": _PIPE_REFERENCE})
    return Scorecard(entries=(entry,))
