"""Capstone: a pump station's weakest link is the wire, not the pump.

A booster pump moving 45 L/s of water at 35 m head looks like a hydraulics problem, but it is an
electromechanical system, and four different subsystems from three parts of the library all have to
pass. This capstone screens them together:

1. **Cavitation margin** -- the NPSH available at the inlet (atmospheric minus vapor pressure, plus
   the flooded suction head, minus the suction pipe's Darcy friction loss) against the pump's
   required NPSH.
2. **Inlet reliability** -- the suction specific speed against the Hydraulic Institute's ~3.5 cap
   that keeps the impeller eye clear of suction recirculation.
3. **Motor sizing** -- the shaft power (hydraulic power over pump efficiency) against the installed
   motor rating.
4. **Feeder voltage drop** -- the three-phase drop down the 120 m cable to the motor against the
   customary 3% limit.

The hydraulics are all comfortable -- the cavitation margin sits at a safety factor of 3.4, the
suction reliability at 1.5, the motor at 1.2 -- and every instinct says the design is fine. It is
not: the **feeder governs at 0.65**, because a 6 mm² cable strung 120 m to the motor drops 4.6% of
the line voltage, well past the 3% a motor needs to start and run. Nothing about the pump is wrong;
the cable is. A pump station is only as good as its worst subsystem, and here that subsystem is the
copper, not the impeller.

Run it directly (``python examples/pump_station_electromechanical.py``);
:func:`screen_station` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    conductor_resistance,
    darcy_friction_factor,
    darcy_weisbach_head_loss,
    line_current_for_power,
    npsh_available,
    pump_hydraulic_power,
    pump_shaft_power,
    pump_suction_specific_speed,
    reynolds_number,
    voltage_drop_three_phase,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

# Duty and fluid (water at 20 C).
FLOW = Quantity.parse("45 L/s")
TOTAL_HEAD = Quantity.parse("35 m")
DENSITY = Quantity.parse("998 kg/m**3")
KINEMATIC_VISCOSITY = Quantity.parse("1.004e-6 m**2/s")
ATMOSPHERIC = Quantity.parse("101.325 kPa")
VAPOR_PRESSURE = Quantity.parse("2.34 kPa")

# Suction line (flooded from a wet well 2 m above the pump).
SUCTION_ID = Quantity.parse("200 mm")
SUCTION_LENGTH = Quantity.parse("6 m")
SUCTION_ROUGHNESS = 0.045 / 200.0  # commercial steel eps/D
STATIC_SUCTION_HEAD = Quantity.parse("2 m")

# Pump and motor.
PUMP_SPEED = Quantity.parse("1450 rpm")
NPSH_REQUIRED = Quantity.parse("3.5 m")
NSS_RELIABILITY_CAP = 3.5
PUMP_EFFICIENCY = 0.82
MOTOR_RATING = Quantity.parse("22 kW")

# Motor feeder (three-phase, copper).
LINE_VOLTAGE = Quantity.parse("400 V")
POWER_FACTOR = 0.85
FEEDER_LENGTH = Quantity.parse("120 m")
FEEDER_AREA = Quantity.parse("6 mm**2")
COPPER_RESISTIVITY = Quantity.parse("1.68e-8 ohm*m")
DROP_LIMIT_PERCENT = 3.0


def _suction_velocity() -> Quantity:
    """The mean water velocity in the suction pipe, v = Q/A."""
    q = FLOW.to("m**3/s").magnitude
    d = SUCTION_ID.to("m").magnitude
    return Quantity(magnitude=q / (pi / 4.0 * d**2), unit="m/s")


def screen_station() -> Scorecard:
    """Screen the station across cavitation, inlet reliability, motor sizing, and feeder drop."""
    velocity = _suction_velocity()
    reynolds = reynolds_number(
        velocity=velocity, diameter=SUCTION_ID, kinematic_viscosity=KINEMATIC_VISCOSITY
    )
    friction = darcy_friction_factor(reynolds=reynolds, relative_roughness=SUCTION_ROUGHNESS)
    suction_loss = darcy_weisbach_head_loss(
        friction_factor=friction, length=SUCTION_LENGTH, diameter=SUCTION_ID, velocity=velocity
    )

    npsha = npsh_available(
        atmospheric_pressure=ATMOSPHERIC,
        vapor_pressure=VAPOR_PRESSURE,
        density=DENSITY,
        static_suction_head=STATIC_SUCTION_HEAD,
        suction_friction_loss=suction_loss,
    )
    nss = pump_suction_specific_speed(
        rotational_speed=PUMP_SPEED, flow_rate=FLOW, npsh_required=NPSH_REQUIRED
    )
    shaft = pump_shaft_power(
        hydraulic_power=pump_hydraulic_power(flow_rate=FLOW, head=TOTAL_HEAD, density=DENSITY),
        efficiency=PUMP_EFFICIENCY,
    )
    current = line_current_for_power(
        real_power=MOTOR_RATING, line_voltage=LINE_VOLTAGE, power_factor=POWER_FACTOR
    )
    feeder_resistance = conductor_resistance(
        resistivity=COPPER_RESISTIVITY, length=FEEDER_LENGTH, cross_section_area=FEEDER_AREA
    )
    feeder_drop = voltage_drop_three_phase(
        line_current=current, resistance=feeder_resistance, power_factor=POWER_FACTOR
    )
    feeder_drop_percent = feeder_drop.to("V").magnitude / LINE_VOLTAGE.to("V").magnitude * 100.0

    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "cavitation margin (NPSHa vs NPSHr)",
                computed=npsha.to("m").magnitude / NPSH_REQUIRED.to("m").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "inlet reliability (suction specific speed)",
                computed=NSS_RELIABILITY_CAP / nss,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "motor rating vs shaft power",
                computed=MOTOR_RATING.to("kW").magnitude / shaft.to("kW").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "feeder voltage drop vs 3% limit",
                computed=DROP_LIMIT_PERCENT / feeder_drop_percent,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(screen_station())
    print("  -> the pump is fine; the 6 mm2 feeder over 120 m is the binding constraint")


if __name__ == "__main__":
    main()
