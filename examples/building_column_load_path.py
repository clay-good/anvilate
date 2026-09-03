"""Capstone: a steel column from the code loads all the way to its buckling capacity.

This is the whole load path in one screen — the environmental and gravity loads, the code
combination that stacks them, and the member resistance they are checked against — for an interior
column carrying five office floors on 6 m by 6 m bays. It pulls from three parts of the library:

1. **Live-load reduction** (``building_loads``) — the column gathers 180 m² of floor, so ASCE 7 lets
   it design for a reduced live load, here floored at 40% of the tabulated 2.4 kPa.
2. **Load combination** (``load_combinations``) — the dead, reduced-live, and roof-snow axial
   effects are stacked into the governing LRFD strength demand, 1.2D + 1.6L + 0.5S.
3. **Column capacity** (``column``) — a W250×58's slenderness sets its Euler stress, the AISC
   Chapter E curve turns that into a critical stress F_cr, and φc·F_cr·Ag is the design strength.

The point is what the live-load reduction *decides*. Designed with the code-permitted reduction,
the column carries its 1,219 kN factored demand against a 1,451 kN capacity — a safety factor of
1.19, it works. Take the reduction away and design for the full tabulated live load, and the demand
jumps to 1,620 kN, past the same capacity: a safety factor of 0.90, it fails. Same column, same
steel; the only difference is whether the engineer claimed the reduction the code allows. The lesson
is that the load path is a chain from the rulebook to the rebar, and a single code provision partway
along it can be the difference between a column that stands and one that does not.

Run it directly (``python examples/building_column_load_path.py``);
:func:`screen_column` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    aisc_flexural_buckling_stress,
    asce7_lrfd_factored_load,
    euler_critical_stress,
    reduced_live_load,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

# Framing: interior column, five floors, 6 m x 6 m bays.
TRIBUTARY_PER_FLOOR = Quantity.parse("36 m**2")
NUMBER_OF_FLOORS = 5
DEAD_PRESSURE = Quantity.parse("4.2 kPa")
UNREDUCED_LIVE = Quantity.parse("2.4 kPa")
ROOF_SNOW_PRESSURE = Quantity.parse("1.2 kPa")
LIVE_ELEMENT_FACTOR = 4.0  # interior column

# Column: W250x58, A992 steel, one 4 m story pinned-pinned.
GROSS_AREA = Quantity.parse("7420 mm**2")
RADIUS_OF_GYRATION = Quantity.parse("50.3 mm")
EFFECTIVE_LENGTH = Quantity.parse("4 m")
YIELD_STRENGTH = Quantity.parse("345 MPa")
ELASTIC_MODULUS = Quantity.parse("200000 MPa")
COMPRESSION_PHI = 0.90


def _tributary() -> Quantity:
    a = TRIBUTARY_PER_FLOOR.to("m**2").magnitude * NUMBER_OF_FLOORS
    return Quantity(magnitude=a, unit="m**2")


def _axial(pressure_kpa: float, floors: int) -> float:
    """Axial force (kN) a uniform pressure delivers over the tributary floors."""
    return pressure_kpa * TRIBUTARY_PER_FLOOR.to("m**2").magnitude * floors


def _design_strength_kn() -> float:
    """The AISC Chapter E compression design strength phi*Fcr*Ag (kN)."""
    slenderness = EFFECTIVE_LENGTH.to("mm").magnitude / RADIUS_OF_GYRATION.to("mm").magnitude
    euler = euler_critical_stress(elastic_modulus=ELASTIC_MODULUS, slenderness_ratio=slenderness)
    fcr = aisc_flexural_buckling_stress(yield_strength=YIELD_STRENGTH, euler_stress=euler)
    return COMPRESSION_PHI * fcr.to("MPa").magnitude * GROSS_AREA.to("mm**2").magnitude / 1000.0


def _factored_demand_kn(live_kpa: float) -> float:
    dead = _axial(DEAD_PRESSURE.to("kPa").magnitude, NUMBER_OF_FLOORS)
    live = _axial(live_kpa, NUMBER_OF_FLOORS)
    snow = _axial(ROOF_SNOW_PRESSURE.to("kPa").magnitude, 1)
    return (
        asce7_lrfd_factored_load(
            dead=Quantity(magnitude=dead, unit="kN"),
            live=Quantity(magnitude=live, unit="kN"),
            roof_snow_rain=Quantity(magnitude=snow, unit="kN"),
        )
        .to("kN")
        .magnitude
    )


def screen_column() -> Scorecard:
    """Screen the column with, and without, the code-permitted live-load reduction."""
    capacity = _design_strength_kn()
    reduced = reduced_live_load(
        unreduced_live_load=UNREDUCED_LIVE,
        live_load_element_factor=LIVE_ELEMENT_FACTOR,
        tributary_area=_tributary(),
        supports_multiple_floors=True,
    )
    demand_reduced = _factored_demand_kn(reduced.to("kPa").magnitude)
    demand_unreduced = _factored_demand_kn(UNREDUCED_LIVE.to("kPa").magnitude)
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "column with code live-load reduction",
                computed=capacity / demand_reduced,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "column without the reduction",
                computed=capacity / demand_unreduced,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(f"column design strength phi*Pn : {_design_strength_kn():.0f} kN")
    print(screen_column().report())
    print("  -> the code live-load reduction is the difference between pass and fail here")


if __name__ == "__main__":
    main()
