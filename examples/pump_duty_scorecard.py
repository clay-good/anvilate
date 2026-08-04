"""Worked example: a pump duty declared once, screened into a selection scorecard.

The hydraulics pack turns a pump selection into the same reviewable pass/fail the rest of the
library produces: declare the duty and the chosen equipment once, and get a scorecard naming the
two checks that most often sink a pump — is the motor big enough for the shaft power, and does the
available NPSH clear the required NPSH so it won't cavitate. This example screens the same 0.05 m³/s
/ 20 m water duty with two selections: a sound one (an 18.5 kW motor, healthy suction) that passes
both checks, and a marginal one (an 11 kW motor that can't supply the 14 kW shaft power, and a
suction with barely any cavitation margin) that fails both. The failures come back together and
cited, not as two loose numbers a reviewer has to weigh.

Run it directly (``python examples/pump_duty_scorecard.py``);
:func:`duty_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.hydraulics import PumpDuty, screen_pump_duty
from anvilate.units import Quantity


def duty_scorecards() -> dict[str, str]:
    """Return the scorecard status for a sound pump selection and a marginal one."""
    sound = PumpDuty(
        flow_rate=Quantity.parse("0.05 m**3/s"),
        total_head=Quantity.parse("20 m"),
        fluid_density=Quantity.parse("1000 kg/m**3"),
        efficiency=0.70,
        motor_rating=Quantity.parse("18.5 kW"),
        npsh_available=Quantity.parse("5.6 m"),
        npsh_required=Quantity.parse("4 m"),
    )
    marginal = PumpDuty(
        flow_rate=Quantity.parse("0.05 m**3/s"),
        total_head=Quantity.parse("20 m"),
        fluid_density=Quantity.parse("1000 kg/m**3"),
        efficiency=0.70,
        motor_rating=Quantity.parse("11 kW"),
        npsh_available=Quantity.parse("4.2 m"),
        npsh_required=Quantity.parse("4 m"),
    )
    sound_card = screen_pump_duty(sound)
    marginal_card = screen_pump_duty(marginal)
    return {
        "sound_status": sound_card.status.value,
        "marginal_status": marginal_card.status.value,
        "marginal_failures": ", ".join(e.name for e in marginal_card.failures()),
    }


def main() -> None:
    d = duty_scorecards()
    print(f"sound selection    : {d['sound_status'].upper()}")
    print(f"marginal selection : {d['marginal_status'].upper()} (fails: {d['marginal_failures']})")
    print("  -> declare the duty once; motor adequacy and cavitation come back cited and pass/fail")


if __name__ == "__main__":
    main()
