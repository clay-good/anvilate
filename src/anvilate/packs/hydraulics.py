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

from pydantic import BaseModel, ConfigDict

from ..analysis import pump_hydraulic_power, pump_shaft_power
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity

__all__ = [
    "PumpDuty",
    "screen_pump_duty",
]

_MOTOR_REFERENCE = "Pump shaft power P = ρgQH/η"
_NPSH_REFERENCE = "NPSH available vs required (cavitation margin)"


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
