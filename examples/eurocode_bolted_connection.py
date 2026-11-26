"""Worked example: the category is the design decision, and it is yours to declare.

EN 1993-1-8 does not have *a* way to design a bolted connection. It has five, and which one
applies is a declaration — a connection "checked to the Eurocode" without its category named
has not been checked against anything in particular, because the five ask for different sets
of checks. Category C does not even require the shear check that category B does.

**The same M20, two ways of making the joint.** As a category A bearing-type connection with
class 6.8 bolts it carries **117.6 kN** in double shear and **98.9 kN** in bearing, so
bearing governs at 98.9. Preloaded as class 8.8 for category C, the same hole carries a
**137.2 kN** clamp and resists **109.8 kN** before it slips. Not a small difference, and
nothing about the plate changed — only what the connection is allowed to do.

**The friction surface is the design, not the bolt.** Slip resistance reads μ, which belongs
to the *surface preparation*: Table 3.7's four classes run 0.5 down to 0.2, so class A is
worth **2.5x** class D on identical steel and identical bolts. A drawing that specifies
preloaded bolts and says nothing about surface treatment has specified a quarter of the
design.

**And so is the hole.** k_s costs up to **37%** — the worst hole type keeps only **0.63** of
a normal one. The ordering is not intuition's: a *short* slot parallel to the load (0.76) is
worth more than a *long* slot perpendicular to it (0.70), so "how slotted is it" is the wrong
question and "which way does it run" is the right one.

**Tension spends the clamp fast.** Preload is what makes a slip-resistant connection work,
and an applied tension relieves it at 0.8 per unit. 100 kN of tension on a 137.2 kN preload
costs **58.3%** of the slip resistance. Past the preload there is nothing left and the
connection has lost its mechanism, which is a refusal here rather than a zero.

**The combined check is not symmetric.** 60% of shear resistance and 60% of tension
resistance together give **1.0286**, not the **1.2** a linear interaction would say: the 1.4
sits under the tension term only. Reading it as symmetric is conservative, and wrong.

Run it directly (``python examples/eurocode_bolted_connection.py``);
:func:`eurocode_bolted_connection` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.en1993_bolts import (
    BoltCategory,
    BoltClass,
    BoltPosition,
    BoltShearPlane,
    FrictionClass,
    HoleType,
    bearing_factor_alpha_b,
    bearing_factor_k1,
    bearing_resistance,
    bolt_strengths,
    category_requirements,
    combined_shear_and_tension,
    preload_force,
    punching_shear_resistance,
    shear_resistance_per_plane,
    slip_factor,
    slip_resistance,
)
from anvilate.units import Quantity

Q = Quantity.parse
_M2, _M3 = 1.25, 1.25
_AREA = Q("245 mm^2")  # M20 tensile stress area
_HOLE, _PLATE_FU = Q("22 mm"), Q("510 MPa")


def the_same_bolt_three_ways() -> dict[str, float]:
    """One M20 in three categories: what the declared category actually changes."""
    bearing_class, preloaded = BoltClass.C6_8, BoltClass.C8_8
    shear = 2 * shear_resistance_per_plane(
        bolt_class=bearing_class, plane=BoltShearPlane.THREADED,
        stress_area=_AREA, partial_factor_m2=_M2,
    ).to("kN").magnitude  # fmt: skip
    alpha_b = bearing_factor_alpha_b(
        position=BoltPosition.END, spacing=Q("40 mm"), hole_diameter=_HOLE,
        bolt_ultimate_strength=bolt_strengths(bolt_class=bearing_class)[1],
        plate_ultimate_strength=_PLATE_FU,
    )  # fmt: skip
    k_1 = bearing_factor_k1(
        position=BoltPosition.END, edge_distance=Q("35 mm"), hole_diameter=_HOLE
    )
    bearing = bearing_resistance(
        factor_k1=k_1, factor_alpha_b=alpha_b, plate_ultimate_strength=_PLATE_FU,
        bolt_diameter=Q("20 mm"), plate_thickness=Q("8 mm"), partial_factor_m2=_M2,
    ).to("kN").magnitude  # fmt: skip
    preload = preload_force(bolt_class=preloaded, stress_area=_AREA)
    slip = slip_resistance(
        category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE, preload=preload,
        slip_factor_value=slip_factor(friction_class=FrictionClass.A),
        friction_surfaces=2, hole=HoleType.NORMAL, partial_factor_m3=_M3,
    ).to("kN").magnitude  # fmt: skip
    return {
        "category_a_shear_kn": shear,
        "category_a_bearing_kn": bearing,
        "category_a_governing_kn": min(shear, bearing),
        "preload_kn": preload.to("kN").magnitude,
        "category_c_slip_kn": slip,
        "alpha_b": alpha_b,
        "k_1": k_1,
    }


def the_surface_is_the_design() -> list[dict[str, float]]:
    """Slip resistance across the four friction classes: the surface, not the bolt."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=_AREA)
    rows = []
    for friction_class in FrictionClass:
        mu = slip_factor(friction_class=friction_class)
        rows.append({
            "class": friction_class.value, "mu": mu,
            "resistance_kn": slip_resistance(
                category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE, preload=preload,
                slip_factor_value=mu, friction_surfaces=2, hole=HoleType.NORMAL,
                partial_factor_m3=_M3,
            ).to("kN").magnitude,
        })  # fmt: skip
    return rows


def the_hole_is_part_of_it() -> list[dict[str, float]]:
    """k_s across the five hole types, which is a second lever on the same connection."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=_AREA)
    return [
        {
            "hole": hole.value,
            "resistance_kn": slip_resistance(
                category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE, preload=preload,
                slip_factor_value=0.5, friction_surfaces=2, hole=hole,
                partial_factor_m3=_M3,
            ).to("kN").magnitude,
        }  # fmt: skip
        for hole in HoleType
    ]


def tension_eats_the_clamp() -> list[dict[str, float]]:
    """How fast an applied tension spends a slip-resistant connection's capacity."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=_AREA)
    rows = []
    for tension_kn in (0.0, 25.0, 50.0, 75.0, 100.0):
        rows.append({
            "tension_kn": tension_kn,
            "resistance_kn": slip_resistance(
                category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE, preload=preload,
                slip_factor_value=0.5, friction_surfaces=2, hole=HoleType.NORMAL,
                partial_factor_m3=_M3,
                applied_tension=Quantity(magnitude=tension_kn, unit="kN"),
            ).to("kN").magnitude,
        })  # fmt: skip
    return rows


def eurocode_bolted_connection() -> dict[str, float]:
    """The figures this example's text quotes."""
    three = the_same_bolt_three_ways()
    surfaces = the_surface_is_the_design()
    holes = the_hole_is_part_of_it()
    tension = tension_eats_the_clamp()
    best = surfaces[0]["resistance_kn"]
    worst = surfaces[-1]["resistance_kn"]
    combined = combined_shear_and_tension(
        applied_shear=Q("60 kN"), shear_resistance=Q("100 kN"),
        applied_tension=Q("60 kN"), tension_resistance_value=Q("100 kN"),
    )  # fmt: skip
    return {
        "shear_kn": three["category_a_shear_kn"],
        "bearing_kn": three["category_a_bearing_kn"],
        "preload_kn": three["preload_kn"],
        "slip_kn": three["category_c_slip_kn"],
        "surface_spread_factor": best / worst,
        "worst_hole_share": min(r["resistance_kn"] for r in holes)
        / max(r["resistance_kn"] for r in holes),
        # The counter-intuitive pair, as shares of a normal hole.
        "short_parallel_share": next(
            r["resistance_kn"] for r in holes if r["hole"] == "short slot parallel"
        )
        / max(r["resistance_kn"] for r in holes),
        "long_perpendicular_share": next(
            r["resistance_kn"] for r in holes if r["hole"] == "long slot perpendicular"
        )
        / max(r["resistance_kn"] for r in holes),
        "tension_cost_percent": 100.0
        * (1.0 - tension[-1]["resistance_kn"] / tension[0]["resistance_kn"]),
        "combined_utilisation": combined,
        "linear_utilisation": 0.60 + 0.60,
        "punching_kn": punching_shear_resistance(
            mean_head_diameter=Q("32 mm"), plate_thickness=Q("8 mm"),
            plate_ultimate_strength=_PLATE_FU, partial_factor_m2=_M2,
        ).to("kN").magnitude,  # fmt: skip
    }


def main() -> None:
    print("--- what each category asks for")
    for category in BoltCategory:
        print(f"  {category.value}: {', '.join(category_requirements(category=category))}")
    print()
    print("--- one M20, two ways of making the joint")
    three = the_same_bolt_three_ways()
    print(f"  category A (6.8, bearing type): shear {three['category_a_shear_kn']:.1f} kN, "
          f"bearing {three['category_a_bearing_kn']:.1f} kN "
          f"-> {three['category_a_governing_kn']:.1f} kN governs")  # fmt: skip
    print(f"  category C (8.8, preloaded):    preload {three['preload_kn']:.1f} kN "
          f"-> slip {three['category_c_slip_kn']:.1f} kN")  # fmt: skip
    print()
    print("--- the friction surface is the design")
    for row in the_surface_is_the_design():
        print(f"  class {row['class']}: mu {row['mu']:.1f} -> {row['resistance_kn']:.1f} kN")
    print()
    print("--- and so is the hole")
    for row in the_hole_is_part_of_it():
        print(f"  {row['hole']:<38} {row['resistance_kn']:.1f} kN")
    print()
    print("--- an applied tension spends the clamp")
    for row in tension_eats_the_clamp():
        print(f"  F_t,Ed {row['tension_kn']:>5.0f} kN -> {row['resistance_kn']:.1f} kN")
    print()
    for name, value in eurocode_bolted_connection().items():
        print(f"{name}: {value:.6g}")


if __name__ == "__main__":
    main()
