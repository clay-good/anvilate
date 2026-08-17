"""Worked example: the mount that isolates the hum and doubles the drop.

A 1450 rpm pump sits on four isolators. The running speed is 24.2 Hz, and the goal is
to pass no more than 10% of its shaking force into the floor. That target sets one
number and one only: the mount has to be soft enough to deflect 4.7 mm under its share
of the load, which puts its natural frequency at 3.5 Hz — well below the 17.1 Hz
isolation onset of f/√2.

Three mounts are on the shelf. The 20 mm and 8 mm pads both clear it. The 0.5 mm pad —
the one that looks reassuringly firm — puts the mount at 22.3 Hz, which is *1.08 times*
the running speed. That is not weak isolation. It is resonance: the pad passes 5.7×
what a rigid bolt-down would, and the screen says so in words rather than reporting a
transmissibility of 5.69 as though it were a number on the same scale as 0.02.

Then the same machine gets shipped, and the softness question inverts. An 11 ms
half-sine drop shock lands on it. Everything about a shock depends on τ/T, the pulse
duration over the mount's natural period:

- the 3.5 Hz vibration mount sits at τ/T = 0.04 — impulsive. The pulse is over before
  the mass has moved, and the mount attenuates it: amplification 0.15, so 30 g arrives
  as 4.6 g;
- a 73 Hz mount sits at τ/T = 0.80 — the peak of the shock spectrum, where the
  amplification is 1.77. The same 30 g drop arrives as 53 g;
- a 300 Hz mount sits at τ/T = 3.3 — quasi-static. The mass just follows the pulse,
  and it arrives as 35 g.

So "stiffen it for shock" is right on one side of the peak and wrong on the other, and
the screen names the regime next to the number precisely so a reader can tell which
side they are on. Here the mount chosen for the hum happens to be the best of the three
for the drop as well — but that is a fact to be checked, not one to assume.

Run it directly (``python examples/isolator_amplifies_at_running_speed.py``); both
screens are exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    half_sine_shock_amplification,
    half_sine_shock_regime,
    half_sine_shock_scorecard,
    isolator_selection_scorecard,
    isolator_static_deflection_for_transmissibility,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

RUNNING_SPEED = Quantity.parse("24.17 Hz")  # 1450 rpm
TARGET_TRANSMISSIBILITY = 0.10  # pass no more than 10% into the floor

# The three pads on the shelf, by rated static deflection under their share of the load.
CANDIDATES = (
    ("20 mm neoprene", Quantity.parse("20 mm")),
    ("8 mm ribbed pad", Quantity.parse("8 mm")),
    ("0.5 mm hard pad", Quantity.parse("0.5 mm")),
)

# The transport shock: a 30 g half-sine over 11 ms, against a 15 g equipment rating.
SHOCK_PEAK = Quantity.parse("294.2 m/s**2")  # 30 g
SHOCK_DURATION = Quantity.parse("11 ms")
SHOCK_ALLOWABLE = Quantity.parse("147.1 m/s**2")  # 15 g

MOUNT_FREQUENCIES = (
    ("3.5 Hz (the vibration mount)", Quantity.parse("3.5 Hz")),
    ("73 Hz (the spectrum peak)", Quantity.parse("73 Hz")),
    ("300 Hz (near-rigid)", Quantity.parse("300 Hz")),
)


def screen_isolator_selection() -> Scorecard:
    """Screen each candidate pad against the softness the 10% target demands."""
    return Scorecard(
        entries=tuple(
            isolator_selection_scorecard(
                label,
                forcing_frequency=RUNNING_SPEED,
                target_transmissibility=TARGET_TRANSMISSIBILITY,
                selected_static_deflection=deflection,
            )
            for label, deflection in CANDIDATES
        )
    )


def screen_transport_shock() -> Scorecard:
    """Screen the 11 ms drop shock on each mount stiffness."""
    return Scorecard(
        entries=tuple(
            half_sine_shock_scorecard(
                label,
                peak_acceleration=SHOCK_PEAK,
                pulse_duration=SHOCK_DURATION,
                natural_frequency=frequency,
                allowable_acceleration=SHOCK_ALLOWABLE,
            )
            for label, frequency in MOUNT_FREQUENCIES
        )
    )


def main() -> None:
    required = isolator_static_deflection_for_transmissibility(
        forcing_frequency=RUNNING_SPEED, transmissibility=TARGET_TRANSMISSIBILITY
    )
    print(
        f"To pass {TARGET_TRANSMISSIBILITY:.0%} at {RUNNING_SPEED.magnitude:.1f} Hz the mount "
        f"must deflect {required.to('mm').magnitude:.1f} mm."
    )
    for entry in screen_isolator_selection().entries:
        print(f"  {entry}")

    print(f"\nTransport shock: 30 g half-sine over {SHOCK_DURATION.magnitude:.0f} ms.")
    for label, frequency in MOUNT_FREQUENCIES:
        amplification = half_sine_shock_amplification(
            pulse_duration=SHOCK_DURATION, natural_frequency=frequency
        )
        regime = half_sine_shock_regime(pulse_duration=SHOCK_DURATION, natural_frequency=frequency)
        print(f"  {label}: {regime.value}, amplification {amplification:.2f}")
    for entry in screen_transport_shock().entries:
        print(f"  {entry}")


if __name__ == "__main__":
    main()
