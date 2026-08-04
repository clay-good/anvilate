"""Worked example: the current a motor pulls the instant it starts, and why it matters.

A motor's running current is the number everyone knows, but the current that trips breakers, dims
the lights, and sizes the starting gear is the one it pulls at the instant of start. With the rotor
still, a motor is effectively a short-circuited transformer, and it draws a locked-rotor inrush
several times its running current. The NEC reads that inrush off the motor's NEMA code letter, which
lists the locked-rotor kVA per horsepower.

This example takes a 20 hp, 460 V motor with a code letter G (about 6.0 kVA/hp). Its running
full-load current is roughly 24 A, but its locked-rotor current comes out near 151 A — more than six
times as much, for the second or two it takes to come up to speed. That inrush is what the starting
protection must ride through without tripping, and it is what drags the plant's voltage down at
start: on a stiff supply the dip is a flicker, on a weak one it can stall other equipment. The
lesson is that a motor is two very different loads at once: a modest steady draw and a brief, brutal
inrush, and the starting current -- not the running one -- sizes the protection and sets the voltage
dip.

Run it directly (``python examples/motor_starting_inrush.py``);
:func:`starting_currents` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import motor_full_load_current, motor_locked_rotor_current
from anvilate.units import Quantity

RATED_POWER = Quantity.parse("20 hp")
LINE_VOLTAGE = Quantity.parse("460 V")
POWER_FACTOR = 0.88
EFFICIENCY = 0.92
CODE_KVA_PER_HP = 6.0  # NEMA code letter G


def starting_currents() -> dict[str, float]:
    """Return the running full-load current, the locked-rotor current, and their ratio."""
    output = Quantity.parse("14.9 kW")  # ~20 hp of shaft output
    flc = motor_full_load_current(
        output_power=output,
        line_voltage=LINE_VOLTAGE,
        power_factor=POWER_FACTOR,
        efficiency=EFFICIENCY,
    )
    lrc = motor_locked_rotor_current(
        rated_power=RATED_POWER, line_voltage=LINE_VOLTAGE, code_kva_per_hp=CODE_KVA_PER_HP
    )
    return {
        "full_load_a": flc.to("A").magnitude,
        "locked_rotor_a": lrc.to("A").magnitude,
        "inrush_ratio": lrc.to("A").magnitude / flc.to("A").magnitude,
    }


def main() -> None:
    s = starting_currents()
    print(f"running full-load current : {s['full_load_a']:.0f} A")
    print(f"locked-rotor (starting) current : {s['locked_rotor_a']:.0f} A")
    print(f"inrush ratio : {s['inrush_ratio']:.1f}x the running current")
    print(
        "  -> the starting current, not the running one, sizes protection and sets the voltage dip"
    )


if __name__ == "__main__":
    main()
