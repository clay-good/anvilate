"""Worked example: strong enough to turn it, too soft to place it.

A 30 kW motor at 730 rpm drives an indexing shaft — the torque follows straight
from the nameplate, T = P/omega = 392 N.m. Sized on strength against a 90 MPa
shear allowable the shaft comes out around 40 mm, and at that size the torsional
shear is a comfortable 31 MPa (safety factor 2.9). But an indexing drive is not
sold on strength; it is sold on how accurately it stops. Over its 1.5 m run the
40 mm shaft winds up 1.69 deg under the drive torque, and the general
machine-shaft stiffness rule of 0.25 deg per foot allows only 1.23 deg — so the
positioning check fails at 0.73. The shaft would transmit the torque without
complaint and index to the wrong place. The fix for torsional wind-up is a
larger (or hollow, stiffer) shaft, not a stronger material.

Run it directly (``python examples/drivetrain_shaft_twist.py``);
:func:`screen_drivetrain_shaft` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    shaft_torsional_stress,
    shaft_twist_angle,
    strength_scorecard,
    torque_from_power,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

POWER = Quantity.parse("30 kW")
SPEED = Quantity.parse("730 rpm")
DIAMETER = Quantity.parse("40 mm")  # sized on strength
LENGTH = Quantity.parse("1.5 m")
SHEAR_MODULUS = Quantity.parse("79.3 GPa")  # steel
SHEAR_ALLOWABLE = Quantity.parse("90 MPa")
REQUIRED_SF = 1.5
TWIST_LIMIT_PER_FOOT = 0.25  # deg/ft, the general machine-shafting stiffness rule


def screen_drivetrain_shaft() -> Scorecard:
    """Screen the nameplate-driven shaft on both torsional strength and the
    twist (positioning-accuracy) limit; strength passes, stiffness governs."""
    torque = torque_from_power(power=POWER, rotational_speed=SPEED)
    shear = shaft_torsional_stress(torque=torque, diameter=DIAMETER)
    twist = shaft_twist_angle(
        torque=torque, length=LENGTH, diameter=DIAMETER, shear_modulus=SHEAR_MODULUS
    )
    twist_limit_deg = TWIST_LIMIT_PER_FOOT * LENGTH.to("ft").magnitude
    twist_sf = twist_limit_deg / twist.to("degree").magnitude
    return Scorecard(
        entries=(
            strength_scorecard(
                "torsional shear",
                stress=shear,
                allowable=SHEAR_ALLOWABLE,
                required=REQUIRED_SF,
            ),
            ScorecardEntry.from_safety_factor(
                "shaft twist (0.25 deg/ft)", computed=twist_sf, required=1.0
            ),
        )
    )


def main() -> None:
    torque = torque_from_power(power=POWER, rotational_speed=SPEED)
    print(f"nameplate torque: {torque.to('N*m')}")
    card = screen_drivetrain_shaft()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
