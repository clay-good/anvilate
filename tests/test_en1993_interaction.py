"""EN 1993-1-1 §6.3.3 beam-columns, against the JRC report's two worked examples."""

from __future__ import annotations

import pytest

from anvilate.analysis.en1993_classification import SectionClass
from anvilate.analysis.en1993_interaction import (
    InteractionMethod,
    TorsionalSusceptibility,
    axial_utilisation,
    beam_column_utilisations,
    equivalent_uniform_moment_factor,
    hollow_section_kzy_allowance,
    interaction_factor_kyy,
    interaction_factor_kzy,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse
M2 = InteractionMethod.METHOD_2
SUSCEPTIBLE = TorsionalSusceptibility.SUSCEPTIBLE
NOT_SUSCEPTIBLE = TorsionalSusceptibility.NOT_SUSCEPTIBLE


# --- Table B.3's equivalent uniform moment factor -------------------------------------


def test_the_moment_factor_is_linear_in_psi_and_floored():
    """0,60 + 0,4ψ, floored at 0,40, on the three points the source works."""
    assert equivalent_uniform_moment_factor(moment_ratio=0.0) == pytest.approx(0.60)
    assert equivalent_uniform_moment_factor(moment_ratio=0.5) == pytest.approx(0.80)
    # The source's second example lands exactly on the floor: 0,60 - 0,20 = 0,40.
    assert equivalent_uniform_moment_factor(moment_ratio=-0.50) == pytest.approx(0.40)


def test_the_floor_binds_below_minus_a_half_rather_than_the_line_continuing():
    """Past ψ = −0,5 the line would fall below 0,40 and the floor is what is returned.

    Without it a member in double curvature would get a smaller C_my, a smaller k_yy and a
    smaller left-hand side — the floor exists to stop exactly that, so it is the half of the
    expression worth a test of its own.
    """
    assert equivalent_uniform_moment_factor(moment_ratio=-1.0) == pytest.approx(0.40)
    assert 0.60 + 0.40 * -1.0 == pytest.approx(0.20), "the unfloored line, for contrast"
    # Just above the floor's corner the line is what governs, so the corner is real.
    assert equivalent_uniform_moment_factor(moment_ratio=-0.4) == pytest.approx(0.44)


def test_a_moment_ratio_outside_its_own_range_refuses():
    """ψ is a ratio of the smaller end moment to the larger, so |ψ| ≤ 1."""
    for psi in (1.5, -2.0):
        with pytest.raises(RefusalError, match="ratio of the smaller end moment"):
            equivalent_uniform_moment_factor(moment_ratio=psi)


# --- The first worked example: IPE 360, susceptible to torsional deformation -----------


@pytest.fixture
def column():
    """The source's Example 6, as the figures its own page prints."""
    axial, resistance, gamma = Q("280 kN"), Q("2581.9 kN"), 1.0
    return {
        "n_y": axial_utilisation(
            axial_force=axial,
            reduction=0.90,
            characteristic_axial_resistance=resistance,
            partial_factor_m1=gamma,
        ),
        "n_z": axial_utilisation(
            axial_force=axial,
            reduction=0.58,
            characteristic_axial_resistance=resistance,
            partial_factor_m1=gamma,
        ),
    }


def test_the_worked_column_reaches_both_interaction_factors(column):
    """k_yy = 0,624 and k_zy = 0,966, from the report's own inputs."""
    c_my = equivalent_uniform_moment_factor(moment_ratio=0.0)
    c_mlt = equivalent_uniform_moment_factor(moment_ratio=0.5)
    k_yy = interaction_factor_kyy(
        moment_factor=c_my,
        slenderness=0.53,
        axial_term=column["n_y"],
        section_class=SectionClass.CLASS_1,
        method=M2,
    )
    k_zy = interaction_factor_kzy(
        moment_factor_lt=c_mlt,
        slenderness=1.04,
        axial_term=column["n_z"],
        section_class=SectionClass.CLASS_1,
        susceptibility=SUSCEPTIBLE,
        method=M2,
    )
    assert k_yy == pytest.approx(0.624, abs=0.0005)
    assert k_zy == pytest.approx(0.966, abs=0.0005)


def test_the_cap_on_kyy_is_a_ceiling_and_does_not_bind_here(column):
    """0,624 against a cap of 0,658: the report prints both, so both are checked."""
    c_my = equivalent_uniform_moment_factor(moment_ratio=0.0)
    cap = c_my * (1.0 + 0.8 * column["n_y"])
    assert cap == pytest.approx(0.658, abs=0.0005)
    k_yy = interaction_factor_kyy(
        moment_factor=c_my,
        slenderness=0.53,
        axial_term=column["n_y"],
        section_class=SectionClass.CLASS_1,
        method=M2,
    )
    assert k_yy < cap, "the unbounded value governs on this member"


def test_the_kyy_cap_binds_above_a_slenderness_of_one_and_is_taken(column):
    """The ceiling is only a ceiling if something is ever cut by it.

    The cap and the line coincide at λ̄_y = 1,0, so past that the cap governs. Neither worked
    example reaches it, which is exactly why this exists — a cap that no test ever reaches is
    a line of code, not a rule.
    """
    c_my = equivalent_uniform_moment_factor(moment_ratio=0.0)
    cap = c_my * (1.0 + 0.8 * column["n_y"])
    slender = interaction_factor_kyy(
        moment_factor=c_my,
        slenderness=3.0,
        axial_term=column["n_y"],
        section_class=SectionClass.CLASS_1,
        method=M2,
    )
    assert slender == pytest.approx(cap)
    at_unity = interaction_factor_kyy(
        moment_factor=c_my,
        slenderness=1.0,
        axial_term=column["n_y"],
        section_class=SectionClass.CLASS_1,
        method=M2,
    )
    assert at_unity == pytest.approx(cap), "the two expressions meet at λ̄_y = 1,0"


def test_the_bound_on_kzy_is_a_floor_and_does_bind_here(column):
    """The reverse of k_yy's cap, and it governs on the source's own column.

    Unbounded this gives 0,9646 and the floor 0,9660, so the floor wins. Reading the bound as
    a ceiling would return 0,9646 — wrong by a sixth of a percent, and entirely plausible
    looking. This asserts the two values and that the larger is what comes back.
    """
    c_mlt = equivalent_uniform_moment_factor(moment_ratio=0.5)
    divisor = c_mlt - 0.25
    unbounded = 1.0 - (0.1 * 1.04) / divisor * column["n_z"]
    floor = 1.0 - 0.1 / divisor * column["n_z"]
    assert unbounded == pytest.approx(0.9646, abs=0.0005)
    assert floor == pytest.approx(0.9660, abs=0.0005)
    assert floor > unbounded, "the floor is the larger here, which is the whole point"
    k_zy = interaction_factor_kzy(
        moment_factor_lt=c_mlt,
        slenderness=1.04,
        axial_term=column["n_z"],
        section_class=SectionClass.CLASS_1,
        susceptibility=SUSCEPTIBLE,
        method=M2,
    )
    assert k_zy == pytest.approx(floor)


def test_the_two_kzy_expressions_coincide_at_unit_slenderness(column):
    """The floor is the same expression with λ̄_z taken out, so they meet at λ̄_z = 1."""
    c_mlt = equivalent_uniform_moment_factor(moment_ratio=0.5)
    at_unity = interaction_factor_kzy(
        moment_factor_lt=c_mlt,
        slenderness=1.0,
        axial_term=column["n_z"],
        section_class=SectionClass.CLASS_1,
        susceptibility=SUSCEPTIBLE,
        method=M2,
    )
    assert at_unity == pytest.approx(1.0 - 0.1 / (c_mlt - 0.25) * column["n_z"])
    # Below it the unbounded expression is the larger, so it is what governs.
    stocky = interaction_factor_kzy(
        moment_factor_lt=c_mlt,
        slenderness=0.5,
        axial_term=column["n_z"],
        section_class=SectionClass.CLASS_1,
        susceptibility=SUSCEPTIBLE,
        method=M2,
    )
    assert stocky > at_unity


def test_the_worked_column_closes_both_inequalities(column):
    """0,56 and 0,88 in the source; 0,567 and 0,878 from its own printed inputs.

    The second matches to the last place. The first does not, and the reason is upstream
    rounding rather than a disagreement: χ_LT is printed as 0,85 and is 0,79/0,93, both of
    those being two-decimal figures themselves. Carrying their intervals through gives a
    left-hand side anywhere in [0,562 , 0,573] — which contains both the report's 0,56 and
    this 0,567 — so the band here is that propagated interval and not a tolerance chosen to
    make the test pass.
    """
    c_my = equivalent_uniform_moment_factor(moment_ratio=0.0)
    c_mlt = equivalent_uniform_moment_factor(moment_ratio=0.5)
    about_y, about_z = beam_column_utilisations(
        axial_term_y=column["n_y"],
        axial_term_z=column["n_z"],
        major_moment=Q("220 kN*m"),
        characteristic_major_moment=Q("361.7 kN*m"),
        lateral_torsional_reduction=0.85,
        partial_factor_m1=1.0,
        factor_kyy=interaction_factor_kyy(
            moment_factor=c_my,
            slenderness=0.53,
            axial_term=column["n_y"],
            section_class=SectionClass.CLASS_1,
            method=M2,
        ),
        factor_kzy=interaction_factor_kzy(
            moment_factor_lt=c_mlt,
            slenderness=1.04,
            axial_term=column["n_z"],
            section_class=SectionClass.CLASS_1,
            susceptibility=SUSCEPTIBLE,
            method=M2,
        ),
    )
    assert 0.562 <= about_y <= 0.573
    assert about_z == pytest.approx(0.88, abs=0.005)
    assert about_y <= 1.0 and about_z <= 1.0, "the source concludes the member is adequate"


def test_the_report_prints_two_kzy_intermediates_that_do_not_reproduce(column):
    """A figure of the source's that this pack does not match, asserted as not matching.

    The report prints k_zy's unbounded value as 0,966 and its floor as 0,947. From the inputs
    printed on the same page they are 0,9646 and 0,9660 — the 0,966 is the floor, not the
    unbounded value, and 0,947 corresponds to no combination of the figures given.

    The governing k_zy is 0,966 either way, so the example's conclusion stands and is anchored
    elsewhere in this file. This test exists so the discrepancy is recorded where someone
    re-deriving the pack will meet it, rather than being discovered again from scratch — and
    so that a future change which *did* make 0,947 reproducible fails here and gets read.
    """
    c_mlt = equivalent_uniform_moment_factor(moment_ratio=0.5)
    divisor = c_mlt - 0.25
    floor = 1.0 - 0.1 / divisor * column["n_z"]
    assert floor != pytest.approx(0.947, abs=0.001), (
        "the report's printed floor has become reproducible; re-read page 71 and rewrite "
        "this test and the module's note"
    )


# --- The second worked example: RHS 200x150x8, not susceptible -------------------------


def test_the_worked_hollow_section_reaches_its_factor_and_both_inequalities():
    """C_my on its floor, k_yy = 0,53 against a cap of 0,60, and 0,90 and 0,72."""
    axial, resistance = Q("965 kN"), Q("1872.6 kN")
    n_y = axial_utilisation(
        axial_force=axial,
        reduction=0.83,
        characteristic_axial_resistance=resistance,
        partial_factor_m1=1.0,
    )
    n_z = axial_utilisation(
        axial_force=axial,
        reduction=0.72,
        characteristic_axial_resistance=resistance,
        partial_factor_m1=1.0,
    )
    c_my = equivalent_uniform_moment_factor(moment_ratio=-0.50)
    assert c_my == pytest.approx(0.40)
    k_yy = interaction_factor_kyy(
        moment_factor=c_my,
        slenderness=0.74,
        axial_term=n_y,
        section_class=SectionClass.CLASS_1,
        method=M2,
    )
    assert k_yy == pytest.approx(0.53, abs=0.005)
    assert c_my * (1.0 + 0.8 * n_y) == pytest.approx(0.60, abs=0.005)
    k_zy = hollow_section_kzy_allowance(susceptibility=NOT_SUSCEPTIBLE, method=M2)
    about_y, about_z = beam_column_utilisations(
        axial_term_y=n_y,
        axial_term_z=n_z,
        major_moment=Q("67.5 kN*m"),
        characteristic_major_moment=Q("127.4 kN*m"),
        # Not susceptible, so lateral-torsional buckling is not checked and χ_LT is 1,0.
        lateral_torsional_reduction=1.0,
        partial_factor_m1=1.0,
        factor_kyy=k_yy,
        factor_kzy=k_zy,
    )
    assert about_y == pytest.approx(0.90, abs=0.005)
    assert about_z == pytest.approx(0.72, abs=0.005)


def test_the_hollow_section_allowance_makes_the_second_check_purely_axial():
    """k_zy = 0 drops the moment term, so Eq. 6.62 becomes the flexural-buckling check.

    Worth asserting as an identity rather than as a number: it is the reason the allowance
    exists, and it is also what makes a zero returned under the wrong conditions dangerous.
    """
    n_z = 0.3
    _, about_z = beam_column_utilisations(
        axial_term_y=0.2,
        axial_term_z=n_z,
        major_moment=Q("500 kN*m"),
        characteristic_major_moment=Q("600 kN*m"),
        lateral_torsional_reduction=1.0,
        partial_factor_m1=1.0,
        factor_kyy=0.5,
        factor_kzy=hollow_section_kzy_allowance(susceptibility=NOT_SUSCEPTIBLE, method=M2),
    )
    assert about_z == pytest.approx(n_z), "a large moment changed it by nothing"


# --- What the module refuses ------------------------------------------------------------


def test_method_one_refuses_rather_than_returning_method_twos_answer():
    """The two methods disagree, so one must not answer under the other's name."""
    with pytest.raises(RefusalError, match="Annex A \\(Method 1\\) are not implemented"):
        interaction_factor_kyy(
            moment_factor=0.6,
            slenderness=0.5,
            axial_term=0.1,
            section_class=SectionClass.CLASS_1,
            method=InteractionMethod.METHOD_1,
        )
    with pytest.raises(RefusalError, match="Annex A"):
        hollow_section_kzy_allowance(
            susceptibility=NOT_SUSCEPTIBLE, method=InteractionMethod.METHOD_1
        )


def test_a_slender_class_refuses_in_both_factors():
    """Tables B.1 and B.2 give classes 3 and 4 different expressions, not carried here."""
    for section_class in (SectionClass.CLASS_3, SectionClass.CLASS_4):
        with pytest.raises(RefusalError, match="class 1 and class 2"):
            interaction_factor_kyy(
                moment_factor=0.6,
                slenderness=0.5,
                axial_term=0.1,
                section_class=section_class,
                method=M2,
            )
        with pytest.raises(RefusalError, match="class 1 and class 2"):
            interaction_factor_kzy(
                moment_factor_lt=0.6,
                slenderness=1.0,
                axial_term=0.1,
                section_class=section_class,
                susceptibility=SUSCEPTIBLE,
                method=M2,
            )


def test_kzy_refuses_below_the_slenderness_where_table_b2_branches():
    """Below λ̄_z = 0,4 Table B.2 takes a branch the source never prints."""
    with pytest.raises(RefusalError, match="separate branch"):
        interaction_factor_kzy(
            moment_factor_lt=0.8,
            slenderness=0.39,
            axial_term=0.1,
            section_class=SectionClass.CLASS_1,
            susceptibility=SUSCEPTIBLE,
            method=M2,
        )
    # And exactly at the boundary it is carried, so the refusal is a floor and not a gap.
    assert (
        interaction_factor_kzy(
            moment_factor_lt=0.8,
            slenderness=0.4,
            axial_term=0.1,
            section_class=SectionClass.CLASS_1,
            susceptibility=SUSCEPTIBLE,
            method=M2,
        )
        > 0
    )


def test_the_two_kzy_routes_each_refuse_the_others_member():
    """Table B.2's k_zy and the hollow-section allowance are not interchangeable."""
    with pytest.raises(RefusalError, match="Table B.1"):
        interaction_factor_kzy(
            moment_factor_lt=0.8,
            slenderness=1.0,
            axial_term=0.1,
            section_class=SectionClass.CLASS_1,
            susceptibility=NOT_SUSCEPTIBLE,
            method=M2,
        )
    with pytest.raises(RefusalError, match="not susceptible"):
        hollow_section_kzy_allowance(susceptibility=SUSCEPTIBLE, method=M2)


def test_a_minor_axis_moment_refuses_instead_of_being_dropped():
    """k_yz and k_zz are not carried, and omitting the term would understate both sides."""
    with pytest.raises(RefusalError, match="k_yz and k_zz are not carried"):
        beam_column_utilisations(
            axial_term_y=0.2,
            axial_term_z=0.3,
            major_moment=Q("100 kN*m"),
            characteristic_major_moment=Q("300 kN*m"),
            lateral_torsional_reduction=1.0,
            partial_factor_m1=1.0,
            factor_kyy=0.6,
            factor_kzy=0.5,
            minor_moment=Q("10 kN*m"),
        )
    # A declared zero is not a minor-axis moment and is allowed through.
    about_y, _ = beam_column_utilisations(
        axial_term_y=0.2,
        axial_term_z=0.3,
        major_moment=Q("100 kN*m"),
        characteristic_major_moment=Q("300 kN*m"),
        lateral_torsional_reduction=1.0,
        partial_factor_m1=1.0,
        factor_kyy=0.6,
        factor_kzy=0.5,
        minor_moment=Q("0 kN*m"),
    )
    assert about_y == pytest.approx(0.2 + 0.6 * (100.0 / 300.0))


def test_a_partial_factor_below_one_refuses_in_both_entry_points():
    """The same rule the sibling modules hold: γ_M1 below 1 raises a resistance."""
    with pytest.raises(RefusalError, match="at least 1"):
        axial_utilisation(
            axial_force=Q("100 kN"),
            reduction=0.9,
            characteristic_axial_resistance=Q("1000 kN"),
            partial_factor_m1=0.9,
        )
    with pytest.raises(RefusalError, match="at least 1"):
        beam_column_utilisations(
            axial_term_y=0.2,
            axial_term_z=0.3,
            major_moment=Q("100 kN*m"),
            characteristic_major_moment=Q("300 kN*m"),
            lateral_torsional_reduction=1.0,
            partial_factor_m1=0.5,
            factor_kyy=0.6,
            factor_kzy=0.5,
        )


def test_a_reduction_factor_outside_its_range_refuses():
    """χ is in (0, 1]: a zero would divide and a value above 1 is not a reduction."""
    for chi in (0.0, 1.5, -0.2):
        with pytest.raises(RefusalError, match="reduction"):
            axial_utilisation(
                axial_force=Q("100 kN"),
                reduction=chi,
                characteristic_axial_resistance=Q("1000 kN"),
                partial_factor_m1=1.0,
            )


def test_a_tension_force_refuses_because_this_is_not_that_check():
    """§6.3.3 is compression and bending; a tie in bending is a different clause."""
    with pytest.raises(RefusalError, match="not a .6.3.3 beam-column"):
        axial_utilisation(
            axial_force=Q("-100 kN"),
            reduction=0.9,
            characteristic_axial_resistance=Q("1000 kN"),
            partial_factor_m1=1.0,
        )


def test_a_non_finite_input_refuses_rather_than_poisoning_a_utilisation():
    """A NaN through these would come back as a NaN left-hand side, which compares False
    against 1,00 and so reads as a member that passed."""
    for bad in (float("nan"), float("inf")):
        with pytest.raises(RefusalError, match="finite"):
            axial_utilisation(
                axial_force=Quantity(magnitude=bad, unit="kN"),
                reduction=0.9,
                characteristic_axial_resistance=Q("1000 kN"),
                partial_factor_m1=1.0,
            )
        with pytest.raises(RefusalError, match="finite"):
            equivalent_uniform_moment_factor(moment_ratio=bad)
        with pytest.raises(RefusalError, match="finite"):
            interaction_factor_kyy(
                moment_factor=0.6,
                slenderness=bad,
                axial_term=0.1,
                section_class=SectionClass.CLASS_1,
                method=M2,
            )


def test_the_axial_term_is_computed_once_and_the_units_are_honoured():
    """N_Ed/(χ·N_Rk/γ_M1) is dimensionless, so the two forces may be in different units."""
    mixed = axial_utilisation(
        axial_force=Q("280000 N"),
        reduction=0.90,
        characteristic_axial_resistance=Q("2581.9 kN"),
        partial_factor_m1=1.0,
    )
    same = axial_utilisation(
        axial_force=Q("280 kN"),
        reduction=0.90,
        characteristic_axial_resistance=Q("2581.9 kN"),
        partial_factor_m1=1.0,
    )
    assert mixed == pytest.approx(same)
    assert mixed == pytest.approx(280.0 / (0.90 * 2581.9))
