"""Worked example: two power plants, the same heat, and the second-law efficiency that ranks them.

A plant's thermal efficiency — work out over heat in — is the number everyone quotes, but on its own
it does not say whether the machine is *good*. A low efficiency can mean a mediocre engine or simply
a hard duty: cool reservoirs leave little to work with even for a perfect machine. Carnot separates
the two. The ceiling η = 1 − T_c/T_h depends on the hot source and cold sink alone, and dividing a
real plant's efficiency by that ceiling — the second-law efficiency — isolates how good the engine
is from how favorable the temperatures are.

This example puts two plants between the *same* reservoirs: a gas-turbine firing temperature of
1400 °C and heat rejected to a 15 °C ambient. Between those, Carnot allows about 83%. A simple-cycle
gas turbine reaches 38% thermal efficiency — respectable, but only about 0.46 of what is possible. A
combined-cycle plant, which recovers the gas turbine's hot exhaust in a bottoming steam cycle,
reaches 60%: against the identical Carnot ceiling that is 0.72, far more of the available work
captured. The thermal efficiencies (38% vs 60%) already favor the combined cycle, but the second-law
efficiencies (0.46 vs 0.72) say *why* it is the better machine — not because its duty is easier (it
is identical) but because it wastes less of what thermodynamics offers. That is the number to
compare engines by, exactly as the second-law COP compares refrigerators.

Run it directly (``python examples/carnot_ceiling_engine_grade.py``);
:func:`grade_engines` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import carnot_efficiency, heat_engine_second_law_efficiency
from anvilate.units import Quantity

FIRING_TEMPERATURE = Quantity.parse("1673.15 K")  # 1400 C turbine inlet
AMBIENT_SINK = Quantity.parse("288.15 K")  # 15 C heat rejection
SIMPLE_CYCLE_EFFICIENCY = 0.38
COMBINED_CYCLE_EFFICIENCY = 0.60


def grade_engines() -> dict[str, float]:
    """Return the Carnot ceiling and the second-law grade of a simple- and combined-cycle plant."""
    ceiling = carnot_efficiency(
        cold_temperature=AMBIENT_SINK,
        hot_temperature=FIRING_TEMPERATURE,
    )
    simple_grade = heat_engine_second_law_efficiency(
        thermal_efficiency=SIMPLE_CYCLE_EFFICIENCY,
        carnot_efficiency=ceiling,
    )
    combined_grade = heat_engine_second_law_efficiency(
        thermal_efficiency=COMBINED_CYCLE_EFFICIENCY,
        carnot_efficiency=ceiling,
    )
    return {
        "carnot_ceiling": ceiling,
        "simple_second_law": simple_grade,
        "combined_second_law": combined_grade,
    }


def main() -> None:
    g = grade_engines()
    print(f"Carnot ceiling (1400 C source, 15 C sink): {g['carnot_ceiling']:.0%}")
    print(
        f"simple-cycle gas turbine : 38% thermal -> {g['simple_second_law']:.0%} "
        "of the Carnot limit"
    )
    print(
        f"combined-cycle plant     : 60% thermal -> {g['combined_second_law']:.0%} "
        "of the same limit"
    )
    print("  -> same duty, so the second-law efficiency ranks the machines, not the temperatures")


if __name__ == "__main__":
    main()
