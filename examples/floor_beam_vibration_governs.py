"""Capstone: an over-strong floor beam that fails on the wobble, not the load.

A floor beam has to clear three separate limit states, and on a long span they do not fail in the
order intuition expects. This capstone runs all three for a 9 m simply-supported W610×101 floor beam
on a 3.5 m tributary, composing four verified functions across three modules:

1. **Strength** (``beam``) — the service bending stress against the steel's yield.
2. **Deflection** (``beam`` + ``span_deflection_limit``) — the live-load mid-span deflection against
   the L/360 serviceability limit.
3. **Walking vibration** (``dynamics``) — the floor's fundamental frequency, estimated from its
   deflection under the vibrating weight, feeds the Design Guide 11 acceleration ratio against the
   0.5% g office comfort limit. The reduced live load (``building_loads``) sets the demand.

The result inverts the usual worry. The beam is wildly comfortable on strength (safety factor 4.3)
and on deflection (6.4) — a first instinct that "it's way over-designed" would be right about the
load and wrong about the floor. It fails the vibration check at 0.47, because a long, light span is
springy: at a 5.6 Hz fundamental it lets a footstep push the acceleration past the comfort limit. No
amount of the strength margin it already has fixes that; the cure is mass, composite action, or
tuning — a different lever entirely. The lesson is that walking vibration is an independent limit
state, and on modern long-span floors it is usually the one that governs.

Run it directly (``python examples/floor_beam_vibration_governs.py``);
:func:`screen_floor_beam` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    floor_vibration_peak_acceleration_ratio,
    natural_frequency_from_deflection,
    reduced_live_load,
    simply_supported_uniform_load,
    span_deflection_limit,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

# Framing.
SPAN = Quantity.parse("9 m")
TRIBUTARY_WIDTH = 3.5  # m
DEAD_PRESSURE = 3.8  # kPa
UNREDUCED_LIVE = Quantity.parse("2.4 kPa")

# Beam: W610x101, A992 steel.
SECOND_MOMENT = Quantity.parse("762e6 mm**4")
EXTREME_FIBRE = Quantity.parse("301.5 mm")  # d/2
ELASTIC_MODULUS = Quantity.parse("200 GPa")
YIELD_STRENGTH = 345.0  # MPa

# Serviceability limits.
DEFLECTION_RATIO = 360.0
VIBRATION_LIMIT = 0.005  # 0.5% g, office
DAMPING_RATIO = 0.03
WALKING_FORCE = Quantity.parse("0.29 kN")


def _beam(load_kn_per_m: float):
    return simply_supported_uniform_load(
        distributed_load=Quantity(magnitude=load_kn_per_m, unit="kN/m"),
        length=SPAN,
        second_moment=SECOND_MOMENT,
        extreme_fibre=EXTREME_FIBRE,
        elastic_modulus=ELASTIC_MODULUS,
    )


def screen_floor_beam() -> Scorecard:
    """Screen the floor beam on strength, deflection, and walking vibration."""
    span_m = SPAN.to("m").magnitude
    reduced_live = (
        reduced_live_load(
            unreduced_live_load=UNREDUCED_LIVE,
            live_load_element_factor=2.0,
            tributary_area=Quantity(magnitude=span_m * TRIBUTARY_WIDTH, unit="m**2"),
        )
        .to("kPa")
        .magnitude
    )

    service_udl = (DEAD_PRESSURE + reduced_live) * TRIBUTARY_WIDTH
    live_udl = reduced_live * TRIBUTARY_WIDTH
    vibration_udl = (DEAD_PRESSURE + 0.1 * reduced_live) * TRIBUTARY_WIDTH

    strength_sf = YIELD_STRENGTH / _beam(service_udl).max_bending_stress.to("MPa").magnitude

    live_deflection = _beam(live_udl).max_deflection.to("mm").magnitude
    deflection_limit = span_deflection_limit(span=SPAN, ratio=DEFLECTION_RATIO).to("mm").magnitude
    deflection_sf = deflection_limit / live_deflection

    frequency = natural_frequency_from_deflection(
        static_deflection=_beam(vibration_udl).max_deflection
    )
    panel_weight = vibration_udl * span_m
    vibration_ratio = floor_vibration_peak_acceleration_ratio(
        fundamental_frequency=frequency,
        effective_panel_weight=Quantity(magnitude=panel_weight, unit="kN"),
        damping_ratio=DAMPING_RATIO,
        constant_force=WALKING_FORCE,
    )
    vibration_sf = VIBRATION_LIMIT / vibration_ratio

    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "bending strength", computed=strength_sf, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "live-load deflection (L/360)", computed=deflection_sf, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "walking vibration (DG11)", computed=vibration_sf, required=1.0
            ),
        )
    )


def main() -> None:
    print(screen_floor_beam().report())
    print("  -> strength and deflection are comfortable; the floor fails on vibration alone")


if __name__ == "__main__":
    main()
