"""EN 1993-1-8 §3 bolted connections, against the JRC report's tables and worked example.

The worked example is used carefully: it disagrees with its own tables in three places, and
each disagreement is pinned here as a disagreement rather than matched.
"""

from __future__ import annotations

import pytest

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
    bolt_tension_resistance,
    category_requirements,
    combined_shear_and_tension,
    preload_force,
    punching_shear_resistance,
    shear_factor,
    shear_resistance_per_plane,
    slip_factor,
    slip_resistance,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

#: The source's worked connection: 2x L80x6 in S355 on an 8 mm gusset, M20 class 6.8,
#: d_0 = 22, e_1 = 40, p_1 = 70, e_2 = 35.
_HOLE, _E1, _P1, _E2 = Q("22 mm"), Q("40 mm"), Q("70 mm"), Q("35 mm")
_PLATE_FU, _BOLT_FU = Q("510 MPa"), Q("600 MPa")


# --- Table 3.1, the bolt strengths ------------------------------------------------------


def test_every_bolt_class_carries_the_tables_two_strengths():
    """All seven classes, both columns, as Table 3.1 prints them."""
    published = {
        BoltClass.C4_6: (240.0, 400.0),
        BoltClass.C4_8: (320.0, 400.0),
        BoltClass.C5_6: (300.0, 500.0),
        BoltClass.C5_8: (400.0, 500.0),
        BoltClass.C6_8: (480.0, 600.0),
        BoltClass.C8_8: (640.0, 800.0),
        BoltClass.C10_9: (900.0, 1000.0),
    }
    assert set(published) == set(BoltClass), "a class was added without its strengths"
    for bolt_class, (yield_strength, ultimate) in published.items():
        f_yb, f_ub = bolt_strengths(bolt_class=bolt_class)
        assert f_yb.to("MPa").magnitude == pytest.approx(yield_strength), bolt_class
        assert f_ub.to("MPa").magnitude == pytest.approx(ultimate), bolt_class


def test_the_class_name_is_the_two_strengths_it_encodes():
    """4.6 means f_ub = 400 and f_yb/f_ub = 0,6 — a check on the table, not a restatement.

    The class designation is not arbitrary: the first number is f_ub/100 and the product of
    the two is f_yb/10. A transcription slip in the table breaks that identity, which is why
    it is worth asserting over a table that was typed in by hand.
    """
    for bolt_class in BoltClass:
        first, second = (float(part) for part in bolt_class.value.split("."))
        f_yb, f_ub = bolt_strengths(bolt_class=bolt_class)
        assert f_ub.to("MPa").magnitude == pytest.approx(first * 100.0), bolt_class
        assert f_yb.to("MPa").magnitude == pytest.approx(first * second * 10.0), bolt_class


# --- Table 3.4's shear factor, and where the example departs from it ---------------------


def test_the_shear_factor_is_the_tables_and_is_not_monotonic_in_strength():
    """0,6 for 4.6, 5.6 and 8.8; 0,5 for 4.8, 5.8, 6.8 and 10.9, through the thread."""
    sixes = (BoltClass.C4_6, BoltClass.C5_6, BoltClass.C8_8)
    for bolt_class in BoltClass:
        expected = 0.6 if bolt_class in sixes else 0.5
        assert shear_factor(bolt_class=bolt_class, plane=BoltShearPlane.THREADED) == expected
        # Through the shank every class takes 0,6.
        assert shear_factor(bolt_class=bolt_class, plane=BoltShearPlane.SHANK) == 0.6
    # Not a rule about class numbers: 8.8 keeps 0,6 while the weaker 6.8 does not.
    assert shear_factor(bolt_class=BoltClass.C8_8, plane=BoltShearPlane.THREADED) > shear_factor(
        bolt_class=BoltClass.C6_8, plane=BoltShearPlane.THREADED
    )


def test_the_worked_example_used_a_shear_factor_its_own_table_refuses():
    """The source takes α_v = 0,6 for a class 6.8 bolt; its Table 3.4 gives 0,5.

    This pack follows the table, so it returns 117,6 kN for the example's double-shear bolt
    where the example prints 141,1 kN. That is a 20% difference on a resistance, far too
    large to leave as an unexplained mismatch — so it is pinned from both sides: the table's
    answer is what the function gives, and the example's printed figure is reproduced here
    only by substituting the factor the example used.

    If a future reading shows 0,6 is right for class 6.8, this test fails and says where to
    look rather than letting the pack quietly disagree with its own source.
    """
    assert shear_factor(bolt_class=BoltClass.C6_8, plane=BoltShearPlane.THREADED) == 0.5
    from_table = shear_resistance_per_plane(
        bolt_class=BoltClass.C6_8,
        plane=BoltShearPlane.THREADED,
        stress_area=Q("245 mm^2"),
        partial_factor_m2=1.25,
    )
    assert 2 * from_table.to("kN").magnitude == pytest.approx(117.6, abs=0.05)
    # The example's own figure, reached only with the factor the example used.
    as_the_example_did = 2 * 0.6 * 245.0 * 600.0 / 1.25 / 1000.0
    assert as_the_example_did == pytest.approx(141.1, abs=0.05)


def test_the_shear_resistance_is_per_plane_so_double_shear_is_the_callers():
    """Per plane, because the number of planes is the joint's geometry, not the bolt's."""
    one = shear_resistance_per_plane(
        bolt_class=BoltClass.C8_8,
        plane=BoltShearPlane.THREADED,
        stress_area=Q("245 mm^2"),
        partial_factor_m2=1.25,
    )
    assert one.to("kN").magnitude == pytest.approx(0.6 * 245 * 800 / 1.25 / 1000, abs=1e-6)


# --- The bearing factors, which the example and the table agree on ----------------------


def test_the_worked_bearing_factors_are_reproduced():
    """α_b = 0,606 at the end bolt and 0,811 at an inner one; k_1 = 2,5."""
    end = bearing_factor_alpha_b(
        position=BoltPosition.END,
        spacing=_E1,
        hole_diameter=_HOLE,
        bolt_ultimate_strength=_BOLT_FU,
        plate_ultimate_strength=_PLATE_FU,
    )
    inner = bearing_factor_alpha_b(
        position=BoltPosition.INNER,
        spacing=_P1,
        hole_diameter=_HOLE,
        bolt_ultimate_strength=_BOLT_FU,
        plate_ultimate_strength=_PLATE_FU,
    )
    assert end == pytest.approx(0.606, abs=0.0005)
    assert inner == pytest.approx(0.811, abs=0.0005)
    assert bearing_factor_k1(
        position=BoltPosition.END, edge_distance=_E2, hole_diameter=_HOLE
    ) == pytest.approx(2.5)


def test_the_strength_ratio_is_the_bolts_over_the_plates():
    """1,176 here, and the source prints its denominator as 360 while computing with 510.

    360 is S235's f_u and this connection is S355, whose 510 the same example uses in its
    net-section check — so the printed denominator is the typo and 1,176 is right. Asserted
    so that the pack's reading of a mis-set equation is recorded where someone re-deriving it
    will meet the same page.
    """
    assert 600.0 / 510.0 == pytest.approx(1.176, abs=0.0005)
    assert 600.0 / 360.0 != pytest.approx(1.176, abs=0.01), "360 does not give the printed value"


def test_inverting_the_strength_ratio_is_invisible_on_this_connection():
    """Which is exactly why it is worth a test: the example cannot catch it.

    Inverted the ratio is 0,85, and both of this connection's α_d values are below that, so
    α_b is unchanged at both bolt positions. It bites on a connection with generous spacing,
    capping α_b at 0,85 where it should reach 1,0.
    """
    for position, spacing, expected in (
        (BoltPosition.END, _E1, 0.606),
        (BoltPosition.INNER, _P1, 0.811),
    ):
        inverted = min(
            spacing.to("mm").magnitude / (3 * 22.0)
            - (0.25 if position is BoltPosition.INNER else 0.0),
            510.0 / 600.0,
            1.0,
        )
        assert inverted == pytest.approx(expected, abs=0.0005), "invisible here"
    # Generous spacing, where the inversion does bite.
    roomy = bearing_factor_alpha_b(
        position=BoltPosition.END,
        spacing=Q("100 mm"),
        hole_diameter=_HOLE,
        bolt_ultimate_strength=_BOLT_FU,
        plate_ultimate_strength=_PLATE_FU,
    )
    assert roomy == pytest.approx(1.0), "the cap, not the ratio, governs the right way up"
    assert min(100.0 / 66.0, 510.0 / 600.0, 1.0) == pytest.approx(0.85), "inverted, it caps"


def test_inner_bolt_k1_refuses_because_the_source_contradicts_itself():
    """Table says 1,4·e_2/d_0 − 1,7; the worked example applies 2,8·e_2/d_0 − 1,7.

    On this connection they are 0,53 and a capped 2,5 — a factor of five on a bearing
    resistance. Only one can be right and the source does not say which, so neither ships.
    """
    with pytest.raises(RefusalError, match="differ by a factor of five"):
        bearing_factor_k1(position=BoltPosition.INNER, edge_distance=_E2, hole_diameter=_HOLE)
    assert 1.4 * 35.0 / 22.0 - 1.7 == pytest.approx(0.527, abs=0.0005)
    assert min(2.8 * 35.0 / 22.0 - 1.7, 2.5) == pytest.approx(2.5)


def test_the_k1_cap_binds_and_the_slope_is_read_below_it():
    """2,5 is a cap, so a tight edge distance must come back below it."""
    tight = bearing_factor_k1(
        position=BoltPosition.END, edge_distance=Q("25 mm"), hole_diameter=_HOLE
    )
    assert tight == pytest.approx(2.8 * 25.0 / 22.0 - 1.7, abs=1e-9)
    assert tight < 2.5
    generous = bearing_factor_k1(
        position=BoltPosition.END, edge_distance=Q("60 mm"), hole_diameter=_HOLE
    )
    assert generous == pytest.approx(2.5), "the cap"


def test_the_bearing_resistance_multiplies_its_four_factors():
    """F_b,Rd = k_1·α_b·f_u·d·t/γ_M2, on the worked connection's end bolt."""
    resistance = bearing_resistance(
        factor_k1=2.5,
        factor_alpha_b=0.606,
        plate_ultimate_strength=_PLATE_FU,
        bolt_diameter=Q("20 mm"),
        plate_thickness=Q("8 mm"),
        partial_factor_m2=1.25,
    )
    expected = 2.5 * 0.606 * 510.0 * 20.0 * 8.0 / 1.25 / 1000.0
    assert resistance.to("kN").magnitude == pytest.approx(expected, abs=1e-6)
    assert resistance.to("kN").magnitude == pytest.approx(98.9, abs=0.05)


def test_the_bearing_resistance_refuses_factors_past_their_own_caps():
    """α_b above 1,0 and k_1 above 2,5 are not inputs the table admits."""
    common = {
        "plate_ultimate_strength": _PLATE_FU,
        "bolt_diameter": Q("20 mm"),
        "plate_thickness": Q("8 mm"),
        "partial_factor_m2": 1.25,
    }
    with pytest.raises(RefusalError, match="capped at 1,0"):
        bearing_resistance(factor_k1=2.5, factor_alpha_b=1.2, **common)
    with pytest.raises(RefusalError, match="capped at 2.5"):
        bearing_resistance(factor_k1=3.0, factor_alpha_b=0.6, **common)


# --- Tension, punching and the combined check -------------------------------------------


def test_the_tension_resistance_takes_the_countersunk_factor_when_asked():
    """k_2 = 0,9, and 0,63 for a countersunk bolt — a 30% difference."""
    plain = bolt_tension_resistance(
        bolt_class=BoltClass.C8_8, stress_area=Q("245 mm^2"), partial_factor_m2=1.25
    )
    sunk = bolt_tension_resistance(
        bolt_class=BoltClass.C8_8,
        stress_area=Q("245 mm^2"),
        partial_factor_m2=1.25,
        countersunk=True,
    )
    assert plain.to("kN").magnitude == pytest.approx(0.9 * 245 * 800 / 1.25 / 1000)
    assert sunk.to("kN").magnitude == pytest.approx(0.63 * 245 * 800 / 1.25 / 1000)
    assert sunk.to("kN").magnitude / plain.to("kN").magnitude == pytest.approx(0.7)


def test_the_punching_resistance_reads_the_head_and_the_plate():
    """B_p,Rd = 0,6·π·d_m·t_p·f_u/γ_M2."""
    from math import pi

    resistance = punching_shear_resistance(
        mean_head_diameter=Q("32 mm"),
        plate_thickness=Q("8 mm"),
        plate_ultimate_strength=_PLATE_FU,
        partial_factor_m2=1.25,
    )
    expected = 0.6 * pi * 32.0 * 8.0 * 510.0 / 1.25 / 1000.0
    assert resistance.to("kN").magnitude == pytest.approx(expected, abs=1e-6)


def test_the_combined_check_is_not_symmetric_between_its_two_terms():
    """The 1,4 sits under the tension term only, which is the point of the interaction.

    Equal fractions of each resistance do NOT give a utilisation of 2: the tension half is
    divided by 1,4, so a bolt carries more tension alongside its shear than a linear
    interaction would allow. A symmetric reading would be conservative here and wrong.
    """
    full_shear_full_tension = combined_shear_and_tension(
        applied_shear=Q("100 kN"),
        shear_resistance=Q("100 kN"),
        applied_tension=Q("100 kN"),
        tension_resistance_value=Q("100 kN"),
    )
    assert full_shear_full_tension == pytest.approx(1.0 + 1.0 / 1.4)
    assert full_shear_full_tension < 2.0
    # Pure tension reaches 1,00 only at 1,4 times the tension resistance.
    assert combined_shear_and_tension(
        applied_shear=Q("0 kN"),
        shear_resistance=Q("100 kN"),
        applied_tension=Q("140 kN"),
        tension_resistance_value=Q("100 kN"),
    ) == pytest.approx(1.0)


# --- Preload and slip resistance ---------------------------------------------------------


def test_the_preload_is_seven_tenths_of_the_bolts_tensile_capacity():
    """F_p,C = 0,7·A_s·f_ub, for an M20 class 8.8: 137,2 kN."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=Q("245 mm^2"))
    assert preload.to("kN").magnitude == pytest.approx(137.2, abs=0.05)
    assert preload.to("kN").magnitude == pytest.approx(0.7 * 245 * 800 / 1000)


def test_only_the_two_preloadable_classes_have_a_preload():
    """A preload on a class 4.6 bolt is not conservative; it is a connection that is not."""
    for bolt_class in BoltClass:
        if bolt_class in (BoltClass.C8_8, BoltClass.C10_9):
            assert preload_force(bolt_class=bolt_class, stress_area=Q("245 mm^2"))
            continue
        with pytest.raises(RefusalError, match="not preloaded"):
            preload_force(bolt_class=bolt_class, stress_area=Q("245 mm^2"))


def test_the_slip_factor_table_is_the_four_published_classes():
    """0,5, 0,4, 0,3 and 0,2 — and nothing outside the table resolves."""
    published = {
        FrictionClass.A: 0.5,
        FrictionClass.B: 0.4,
        FrictionClass.C: 0.3,
        FrictionClass.D: 0.2,
    }
    assert set(published) == set(FrictionClass), "a class was added without its factor"
    for friction_class, mu in published.items():
        assert slip_factor(friction_class=friction_class) == pytest.approx(mu)
    # The classes are ordered: A is the best-prepared surface and D the least.
    factors = [slip_factor(friction_class=c) for c in FrictionClass]
    assert factors == sorted(factors, reverse=True)


def test_the_slip_resistance_multiplies_its_four_terms():
    """F_s,Rd = k_s·n·μ·F_p,C/γ_M3, two surfaces, class A, normal holes."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=Q("245 mm^2"))
    resistance = slip_resistance(
        category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE,
        preload=preload,
        slip_factor_value=slip_factor(friction_class=FrictionClass.A),
        friction_surfaces=2,
        hole=HoleType.NORMAL,
        partial_factor_m3=1.25,
    )
    assert resistance.to("kN").magnitude == pytest.approx(1.0 * 2 * 0.5 * 137.2 / 1.25, abs=0.01)


def test_every_hole_type_carries_its_own_k_s():
    """Table 3.6's five values, and a slotted hole is worth up to 37% less than a round one."""
    published = {
        HoleType.NORMAL: 1.00,
        HoleType.OVERSIZED_OR_SHORT_SLOT_PERPENDICULAR: 0.85,
        HoleType.LONG_SLOT_PERPENDICULAR: 0.70,
        HoleType.SHORT_SLOT_PARALLEL: 0.76,
        HoleType.LONG_SLOT_PARALLEL: 0.63,
    }
    assert set(published) == set(HoleType), "a hole type was added without its k_s"
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=Q("245 mm^2"))
    base = None
    for hole, k_s in published.items():
        resistance = (
            slip_resistance(
                category=BoltCategory.B_SLIP_RESISTANT_AT_SERVICEABILITY,
                preload=preload,
                slip_factor_value=0.5,
                friction_surfaces=1,
                hole=hole,
                partial_factor_m3=1.25,
            )
            .to("kN")
            .magnitude
        )
        if hole is HoleType.NORMAL:
            base = resistance
        assert resistance == pytest.approx(base * k_s, abs=0.01), hole
    # The parallel short slot is worth MORE than the perpendicular long one, which is the
    # ordering a reader guessing from "how slotted is it" would get wrong.
    assert published[HoleType.SHORT_SLOT_PARALLEL] > published[HoleType.LONG_SLOT_PERPENDICULAR]


def test_an_applied_tension_relieves_four_fifths_of_itself_from_the_preload():
    """Eqs. 3.8 and 3.9: the clamping force is F_p,C − 0,8·F_t,Ed."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=Q("245 mm^2"))
    common = {
        "preload": preload,
        "slip_factor_value": 0.5,
        "friction_surfaces": 2,
        "hole": HoleType.NORMAL,
        "partial_factor_m3": 1.25,
    }
    clamped = (
        slip_resistance(category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE, **common)
        .to("kN")
        .magnitude
    )
    relieved = (
        slip_resistance(
            category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE,
            applied_tension=Q("50 kN"),
            **common,
        )
        .to("kN")
        .magnitude
    )
    assert relieved == pytest.approx(clamped * (137.2 - 0.8 * 50.0) / 137.2, abs=0.01)
    assert relieved < clamped


def test_a_tension_that_undoes_the_whole_preload_refuses():
    """With no clamping force left there is no slip resistance, and zero is not the answer:
    a connection relying on one has lost the mechanism it was designed around."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=Q("245 mm^2"))
    with pytest.raises(RefusalError, match="relieves the whole preload"):
        slip_resistance(
            category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE,
            preload=preload,
            slip_factor_value=0.5,
            friction_surfaces=2,
            hole=HoleType.NORMAL,
            partial_factor_m3=1.25,
            applied_tension=Q("200 kN"),
        )


# --- The categories ----------------------------------------------------------------------


def test_each_category_asks_for_a_different_set_of_checks():
    """Table 3.2. The set is the whole point: B and C are not A with an extra check."""
    assert category_requirements(category=BoltCategory.A_BEARING) == ("shear", "bearing")
    b = category_requirements(category=BoltCategory.B_SLIP_RESISTANT_AT_SERVICEABILITY)
    c = category_requirements(category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE)
    assert "slip at serviceability" in b and "shear" in b
    # C checks slip at the ultimate limit state and adds the net section; it does NOT
    # require the shear check that B does, which is the kind of difference a single
    # "check everything" routine would paper over.
    assert "slip at ultimate" in c and "net section" in c
    assert "shear" not in c
    for category in BoltCategory:
        assert category_requirements(category=category), category
    assert len({category_requirements(category=c) for c in BoltCategory}) >= 4


def test_only_the_slip_resistant_categories_have_a_slip_resistance():
    """A, D and E refuse: they have no slip check to return a number for."""
    preload = preload_force(bolt_class=BoltClass.C8_8, stress_area=Q("245 mm^2"))
    for category in (
        BoltCategory.A_BEARING,
        BoltCategory.D_NON_PRELOADED_TENSION,
        BoltCategory.E_PRELOADED_TENSION,
    ):
        with pytest.raises(RefusalError, match="not slip-resistant"):
            slip_resistance(
                category=category,
                preload=preload,
                slip_factor_value=0.5,
                friction_surfaces=1,
                hole=HoleType.NORMAL,
                partial_factor_m3=1.25,
            )


# --- What the module refuses --------------------------------------------------------------


def test_a_partial_factor_below_one_refuses_everywhere_it_is_taken():
    """γ below 1 raises a resistance above its characteristic value."""
    with pytest.raises(RefusalError, match="at least 1"):
        shear_resistance_per_plane(
            bolt_class=BoltClass.C8_8,
            plane=BoltShearPlane.THREADED,
            stress_area=Q("245 mm^2"),
            partial_factor_m2=0.9,
        )
    with pytest.raises(RefusalError, match="at least 1"):
        slip_resistance(
            category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE,
            preload=Q("137 kN"),
            slip_factor_value=0.5,
            friction_surfaces=1,
            hole=HoleType.NORMAL,
            partial_factor_m3=0.5,
        )


def test_a_friction_surface_count_that_is_not_a_whole_number_refuses():
    """Half a friction surface is not a connection, and True is not one either."""
    preload = Q("137 kN")
    common = {
        "category": BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE,
        "preload": preload,
        "slip_factor_value": 0.5,
        "hole": HoleType.NORMAL,
        "partial_factor_m3": 1.25,
    }
    for bad in (1.5, True, "2"):
        with pytest.raises(RefusalError, match="whole number"):
            slip_resistance(friction_surfaces=bad, **common)
    with pytest.raises(RefusalError, match="at least 1"):
        slip_resistance(friction_surfaces=0, **common)


def test_a_slip_factor_outside_its_range_refuses():
    """μ is a coefficient of friction, not a multiplier."""
    common = {
        "category": BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE,
        "preload": Q("137 kN"),
        "friction_surfaces": 1,
        "hole": HoleType.NORMAL,
        "partial_factor_m3": 1.25,
    }
    for bad in (0.0, -0.3, 1.5):
        with pytest.raises(RefusalError, match="coefficient of friction"):
            slip_resistance(slip_factor_value=bad, **common)


def test_a_non_finite_input_refuses_rather_than_returning_a_poisoned_resistance():
    """A NaN resistance compares False against any demand, so it reads as a pass."""
    for bad in (float("nan"), float("inf")):
        with pytest.raises(RefusalError, match="finite"):
            shear_resistance_per_plane(
                bolt_class=BoltClass.C8_8,
                plane=BoltShearPlane.THREADED,
                stress_area=Quantity(magnitude=bad, unit="mm^2"),
                partial_factor_m2=1.25,
            )
        with pytest.raises(RefusalError, match="finite"):
            bearing_resistance(
                factor_k1=bad,
                factor_alpha_b=0.6,
                plate_ultimate_strength=_PLATE_FU,
                bolt_diameter=Q("20 mm"),
                plate_thickness=Q("8 mm"),
                partial_factor_m2=1.25,
            )
        with pytest.raises(RefusalError, match="finite"):
            slip_resistance(
                category=BoltCategory.C_SLIP_RESISTANT_AT_ULTIMATE,
                preload=Q("137 kN"),
                slip_factor_value=bad,
                friction_surfaces=1,
                hole=HoleType.NORMAL,
                partial_factor_m3=1.25,
            )


def test_a_spacing_too_small_to_bear_refuses_rather_than_returning_a_negative_factor():
    """An inner bolt's α_d is p_1/(3d_0) − 0,25, which goes negative at tight pitch."""
    with pytest.raises(RefusalError, match="before it bears at all"):
        bearing_factor_alpha_b(
            position=BoltPosition.INNER,
            spacing=Q("15 mm"),
            hole_diameter=_HOLE,
            bolt_ultimate_strength=_BOLT_FU,
            plate_ultimate_strength=_PLATE_FU,
        )


def test_the_quantities_are_honoured_rather_than_assumed():
    """Inputs in different units give the same answer, which is the unit typing working."""
    metric = shear_resistance_per_plane(
        bolt_class=BoltClass.C8_8,
        plane=BoltShearPlane.THREADED,
        stress_area=Q("245 mm^2"),
        partial_factor_m2=1.25,
    )
    in_cm = shear_resistance_per_plane(
        bolt_class=BoltClass.C8_8,
        plane=BoltShearPlane.THREADED,
        stress_area=Q("2.45 cm^2"),
        partial_factor_m2=1.25,
    )
    assert metric.to("kN").magnitude == pytest.approx(in_cm.to("kN").magnitude)
