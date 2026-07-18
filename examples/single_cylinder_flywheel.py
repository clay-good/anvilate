"""Capstone: sizing the flywheel a lumpy single-cylinder torque needs.

A single-cylinder two-stroke turns over at 600 rpm. Its crank torque is anything but steady:
the piston pushes only on the power stroke, and even then the torque is zero at both dead
centres (the rod is straight, no lever arm) and peaks near mid-stroke, so the turning moment
swings from nothing to a sharp peak and back every revolution. Left to itself the crankshaft
would surge and stall through each cycle. The flywheel's whole job is to store the excess
energy of the power stroke and give it back through the dead spots, holding the speed nearly
constant.

This walks the crank-angle torque diagram directly: it evaluates the exact crank torque
T = F·(dx/dθ) at every angle (a constant 6 kN cylinder force over the power stroke), averages
it to the mean torque the load actually sees, and integrates the area between the torque curve
and that mean to get the energy fluctuation ΔE -- 399 J here -- the surplus the flywheel must
soak up and return. Holding the speed to a 2 % coefficient of fluctuation at 600 rpm then
takes a flywheel of 5.05 kg·m². A 6.0 kg·m² wheel covers it (safety factor 1.19); a 4.0 kg·m²
wheel does not (0.79), and the engine would hunt more than the mechanism allows.

The lesson is that a single-cylinder machine is defined as much by the *shape* of its torque
curve as by its average power: the flywheel is sized from the energy fluctuation ΔE, the area
between the lumpy torque and its mean, not from the mean itself. Add cylinders (or a smoother
cam) and ΔE falls and the flywheel shrinks; a single cylinder pays for its simplicity in
flywheel inertia.

Run it directly (``python examples/single_cylinder_flywheel.py``);
:func:`screen_flywheel` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import flywheel_inertia_for_fluctuation, slider_crank_torque
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

CRANK_RADIUS = Quantity.parse("60 mm")
ROD_LENGTH = Quantity.parse("240 mm")
POWER_STROKE_FORCE = Quantity.parse("6000 N")
MEAN_SPEED = Quantity.parse("600 rpm")
COEFFICIENT_OF_FLUCTUATION = 0.02
SAMPLES = 720  # crank-angle steps over one revolution

ADEQUATE_INERTIA = Quantity.parse("6.0 kg*m**2")
UNDERSIZED_INERTIA = Quantity.parse("4.0 kg*m**2")


def _torque_curve() -> list[float]:
    """The crank torque (N*m) at each of SAMPLES crank angles over one revolution.

    A constant power-stroke force acts over 0-180 degrees (the expansion stroke) and the
    cylinder is idle over 180-360; the crank torque is the exact T = F*(dx/dtheta)."""
    torques = []
    for i in range(SAMPLES):
        angle = 360.0 * i / SAMPLES
        force = POWER_STROKE_FORCE if angle < 180.0 else Quantity.parse("0 N")
        torques.append(
            slider_crank_torque(
                piston_force=force,
                crank_radius=CRANK_RADIUS,
                rod_length=ROD_LENGTH,
                crank_angle=angle if angle > 0 else 1e-6,
            )
            .to("N*m")
            .magnitude
        )
    return torques


def energy_fluctuation() -> Quantity:
    """The energy fluctuation ΔE: the peak-to-trough area between torque and its mean."""
    torques = _torque_curve()
    mean = sum(torques) / len(torques)
    d_theta = 2.0 * 3.141592653589793 / len(torques)
    cumulative = 0.0
    lo = hi = 0.0
    for t in torques:
        cumulative += (t - mean) * d_theta
        lo = min(lo, cumulative)
        hi = max(hi, cumulative)
    return Quantity(magnitude=hi - lo, unit="J")


def _screen(flywheel_inertia: Quantity) -> Scorecard:
    required = flywheel_inertia_for_fluctuation(
        energy_fluctuation=energy_fluctuation(),
        mean_speed=MEAN_SPEED,
        coefficient_of_fluctuation=COEFFICIENT_OF_FLUCTUATION,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "flywheel inertia vs required",
                computed=flywheel_inertia.to("kg*m**2").magnitude
                / required.to("kg*m**2").magnitude,
                required=1.0,
            ),
        )
    )


def screen_flywheel() -> Scorecard:
    """Screen the 6.0 kg*m^2 flywheel: enough to hold the 2% speed fluctuation."""
    return _screen(ADEQUATE_INERTIA)


def screen_undersized_flywheel() -> Scorecard:
    """Screen the 4.0 kg*m^2 flywheel: too light, the engine hunts."""
    return _screen(UNDERSIZED_INERTIA)


def main() -> None:
    print(f"energy fluctuation ΔE: {energy_fluctuation().to('J').magnitude:.0f} J")
    print("adequate flywheel (6.0 kg*m^2):")
    print(screen_flywheel())
    print("\nundersized flywheel (4.0 kg*m^2):")
    print(screen_undersized_flywheel())


if __name__ == "__main__":
    main()
