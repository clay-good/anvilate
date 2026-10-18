"""Worked example: a bracket's stress block counted by rainflow, then damaged by Miner.

A suspension bracket sees the stress block 50, 450, 150, 350, -100, 300, 0, 500, 50 MPa
once per kilometre of rough road, over and over. Counted as a repeating block, rainflow
pairs it into 4 cycles, the largest a 600 MPa range from the block's two extremes. Read
as a sequence of ranges between neighbouring points instead, the block's largest swing
would never be seen, because no two neighbouring points span it.

With an illustrative steel S-N curve (Basquin, σ_a = 900·N^-0.09 MPa, amplitudes taken as
half the range and means ignored), Miner's rule gives the bracket 197,869 blocks, about
that many kilometres of rough road. The largest cycle alone does 0.99 of the damage: it is
the one cycle a count of neighbouring swings misses, whose largest is 500 MPa.

Run it directly (``python examples/rainflow_block_damage.py``);
:func:`rainflow_block_damage` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import basquin_cycles_to_failure, miner_cumulative_damage, rainflow_count
from anvilate.units import Quantity

BLOCK_MPA = (50.0, 450.0, 150.0, 350.0, -100.0, 300.0, 0.0, 500.0, 50.0)


def _life(stress_range: float) -> float:
    return basquin_cycles_to_failure(
        stress_amplitude=Quantity(magnitude=stress_range / 2, unit="MPa"),
        coefficient=Quantity(magnitude=900.0, unit="MPa"),
        exponent=-0.09,
    )


def rainflow_block_damage() -> dict[str, float]:
    """Return the block's cycle count, largest range, damage per block and life."""
    count = rainflow_count([Quantity(magnitude=s, unit="MPa") for s in BLOCK_MPA], repeating=True)
    ranges = [c.range for c in count.cycles]
    lives = [_life(r) for r in ranges]
    damage = miner_cumulative_damage(applied_cycles=[c.count for c in count.cycles],
                                     cycles_to_failure=lives)  # fmt: skip
    largest = max(ranges)
    return {
        "cycles": count.total_cycles,
        "largest_range_mpa": largest,
        "naive_largest_mpa": max(
            abs(b - a) for a, b in zip(BLOCK_MPA, BLOCK_MPA[1:], strict=False)
        ),
        "damage_per_block": damage,
        "blocks_to_failure": 1 / damage,
        "km_to_failure": 1 / damage,
        "largest_share": (1 / _life(largest)) / damage,
    }


def main() -> None:
    d = rainflow_block_damage()
    print(f"{d['cycles']:g} cycles; largest range {d['largest_range_mpa']:g} MPa")
    print(f"largest neighbouring swing: {d['naive_largest_mpa']:g} MPa")
    print(
        f"damage per block {d['damage_per_block']:.3e}; life {d['blocks_to_failure']:,.0f} blocks"
    )
    print(f"largest cycle's share of the damage: {d['largest_share']:.2f}")


if __name__ == "__main__":
    main()
