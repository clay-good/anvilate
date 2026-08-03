"""Worked example: the governing load combination is not the obvious one.

A light steel canopy beam carries its own dead load and a roof live load, and a
modest floor live load hangs from it. Sizing the beam for bending, an engineer
reaches for the obvious combination — dead plus live — and moves on. But the canopy
is light and the site is windy, and wind on a canopy is an *uplift*: it pulls the
roof up, not down.

Feed the ASCE 7-22 strength combinations the four cases (dead 15, live 10, roof
live 12, wind −40 as a net uplift, all kN) and the surprises come in pairs. The
largest downward demand is not the reflexive 1.2D + 1.6L (that is 40 kN); it is
combination 3 with the roof live as the *principal* variable load, 1.2D + 1.0L +
1.6Lr = 47.2 kN. And the *minimizing* combination, 0.9D + 1.0W, nets 0.9·15 − 40 =
−26.5 kN: a real uplift the gravity combinations never show. The beam's hold-down
and its anchors have to resist 26.5 kN pulling up — a demand that is invisible if
you only check the obvious combination.

The lesson is that "the load" is a set of combinations, and different members and
connections are governed by different ones. A gravity-only check on a light,
wind-exposed member is exactly the silent green that combination bookkeeping
exists to catch: size the beam on the gravity envelope, but size the connection on
the counteracting uplift.

This is combination factoring, not load derivation: the wind magnitude is the
engineer's input (from the maps and site work Anvilate does not do). Run it
directly (``python examples/canopy_beam_load_combinations.py``);
:func:`gravity_envelope` and :func:`uplift_governing` are exercised in the tests.
"""

from __future__ import annotations

from anvilate.loads import LoadCombination, LoadNature, asce7_lrfd_basic

# The four load cases, in kN. Wind is a net uplift on this light canopy, so it is
# supplied as a negative magnitude — the direction is the engineer's to assert.
LOADS = {
    LoadNature.DEAD: 15.0,
    LoadNature.LIVE: 10.0,
    LoadNature.ROOF_LIVE: 12.0,
    LoadNature.WIND: -40.0,
}


def gravity_envelope() -> tuple[LoadCombination, float]:
    """The largest downward demand — what sizes the beam in bending."""
    return asce7_lrfd_basic().governing(LOADS)


def uplift_governing() -> tuple[LoadCombination, float]:
    """The most-upward (counteracting) demand — what sizes the hold-down."""
    return asce7_lrfd_basic().governing(LOADS, minimize=True)


def main() -> None:
    cs = asce7_lrfd_basic()
    print("All ASCE 7-22 LRFD combinations for this canopy (kN):")
    for name, demand in cs.evaluate_all(LOADS):
        print(f"  {name:16s} {demand:+7.1f}")

    down_combo, down = gravity_envelope()
    up_combo, up = uplift_governing()
    print(f"\nBending is sized by the gravity envelope: {down_combo.name} = {down:+.1f} kN")
    print(
        f"But the hold-down sees an uplift the gravity cases hide: {up_combo.name} = {up:+.1f} kN"
    )
    print(f"  ({up_combo})")


if __name__ == "__main__":
    main()
