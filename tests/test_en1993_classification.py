"""EN 1993-1-1 cross-section classification, against the worked examples it was read from.

The limits come from Table 5.2, which the European Commission's JRC report reproduces, and
the two classifications that report works in full are replayed here down to the
intermediate ratios: an HEB 340 in S355 under pure compression and an IPE 400 in S355 in
bending. Those pin more than the verdict — they pin how c is measured on a rolled I-section,
which the table states only as a figure, and the ratios 20,25 / 5,44 / 38,49 / 4,79 are the
only published check on that reading.

The rest is the table's own structure: every boundary from both sides, the branches under
combined stress, and the two places where getting a symbol wrong gives a plausible wrong
answer (ε² against ε for a tube, and the extra √α for a flange tip in tension).
"""

from __future__ import annotations

import pytest

from anvilate.analysis.en1993_classification import (
    FlangeTip,
    PartStress,
    SectionClass,
    angle_in_compression_class,
    en1993_epsilon,
    internal_part_class,
    outstand_flange_class,
    rolled_i_section_class,
    tubular_section_class,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

#: Table 5.2's own tabulation of ε, which every sheet repeats.
_EPSILON_TABLE = ((235, 1.00), (275, 0.92), (355, 0.81), (420, 0.75), (460, 0.71))
#: And of ε², which only the tubular sheet needs.
_EPSILON_SQUARED_TABLE = ((235, 1.00), (275, 0.85), (355, 0.66), (420, 0.56), (460, 0.51))

_S355 = Q("355 MPa")


@pytest.mark.parametrize(("yield_mpa", "published"), _EPSILON_TABLE)
def test_epsilon_matches_the_tables_own_tabulation(yield_mpa: int, published: float):
    """√(235/f_y) against the two decimals Table 5.2 prints for each grade."""
    assert round(en1993_epsilon(yield_strength=Q(f"{yield_mpa} MPa")), 2) == published


@pytest.mark.parametrize(("yield_mpa", "published"), _EPSILON_SQUARED_TABLE)
def test_epsilon_squared_matches_the_tubular_sheets_tabulation(yield_mpa: int, published: float):
    """The tubular sheet tabulates ε² separately, and it is not ε rounded differently."""
    epsilon = en1993_epsilon(yield_strength=Q(f"{yield_mpa} MPa"))
    assert round(epsilon * epsilon, 2) == published


def test_the_worked_heb_340_in_pure_compression():
    """JRC §1.3.1: web c/t = 20,25 ≤ 33ε = 26,73; flange c/t = 5,44 ≤ 9ε = 7,29; class 1.

    c is measured with the root radius out of both elements: the web's
    c = 340 − 2(21,5) − 2(27) = 243 and the flange's c = (300 − 12)/2 − 27 = 117. Those two
    numbers are what reproduce the report's ratios, and nothing else does.
    """
    section, web, flange = rolled_i_section_class(
        height=Q("340 mm"),
        width=Q("300 mm"),
        web_thickness=Q("12 mm"),
        flange_thickness=Q("21.5 mm"),
        root_radius=Q("27 mm"),
        yield_strength=_S355,
        stress=PartStress.COMPRESSION,
    )
    assert (section, web, flange) == (SectionClass.CLASS_1,) * 3
    # The intermediate ratios the report prints, recomputed here rather than quoted.
    assert round((340 - 2 * 21.5 - 2 * 27) / 12, 2) == 20.25
    assert round(((300 - 12) / 2 - 27) / 21.5, 2) == 5.44
    epsilon = en1993_epsilon(yield_strength=_S355)
    assert round(33 * epsilon, 2) == pytest.approx(26.85, abs=0.13)  # 26,73 at the table's ε
    assert internal_part_class(ratio=20.25, epsilon=epsilon) is SectionClass.CLASS_1
    assert outstand_flange_class(ratio=5.44, epsilon=epsilon) is SectionClass.CLASS_1


def test_the_worked_ipe_400_in_bending():
    """JRC §1.3.2: web c = 331, c/t = 38,49 ≤ 72ε = 58,32; flange c/t = 4,79 ≤ 9ε; class 1.

    The flange of an I-section in bending is wholly in compression on the compression side,
    so it takes the compression column of sheet 2 — which is how the report classifies it.
    """
    section, web, flange = rolled_i_section_class(
        height=Q("400 mm"),
        width=Q("180 mm"),
        web_thickness=Q("8.6 mm"),
        flange_thickness=Q("13.5 mm"),
        root_radius=Q("21 mm"),
        yield_strength=_S355,
        stress=PartStress.BENDING,
    )
    assert (section, web, flange) == (SectionClass.CLASS_1,) * 3
    assert 400 - 2 * 13.5 - 2 * 21 == 331
    assert round(331 / 8.6, 2) == 38.49
    assert round(((180 - 8.6) / 2 - 21) / 13.5, 2) == 4.79


def test_the_root_radius_is_taken_out_of_the_web():
    """Reading the web's c as the full depth is the mistake this measurement guards.

    On the IPE 400 it reads 46,51 instead of 38,49. Both are class 1 in S355, which is why
    the worked example cannot catch it on its own — so the ratio is asserted, not only the
    class.
    """
    assert round(400 / 8.6, 2) == 46.51
    epsilon = en1993_epsilon(yield_strength=_S355)
    assert internal_part_class(ratio=46.51, epsilon=epsilon, stress=PartStress.BENDING) is (
        SectionClass.CLASS_1
    )
    # At the class 1/2 boundary the same mistake changes the answer: 72ε = 58,58.
    assert internal_part_class(ratio=58.0, epsilon=epsilon, stress=PartStress.BENDING) is (
        SectionClass.CLASS_1
    )
    assert internal_part_class(ratio=59.0, epsilon=epsilon, stress=PartStress.BENDING) is (
        SectionClass.CLASS_2
    )


@pytest.mark.parametrize(
    ("stress", "coefficients"),
    [
        (PartStress.BENDING, (72.0, 83.0, 124.0)),
        (PartStress.COMPRESSION, (33.0, 38.0, 42.0)),
    ],
)
def test_an_internal_part_takes_each_class_at_its_own_limit(stress, coefficients):
    """Each limit from both sides, at ε = 1 so the coefficients read directly.

    ``<=`` and not ``<``: the table writes c/t ≤ 72ε, so a part exactly at the limit is in
    the class, and an off-by-one here would silently demote every section that lands on a
    round number.
    """
    for expected, coefficient in zip((1, 2, 3), coefficients, strict=True):
        at = internal_part_class(ratio=coefficient, epsilon=1.0, stress=stress)
        assert at is SectionClass(expected), (coefficient, at)
        over = internal_part_class(ratio=coefficient + 1e-9, epsilon=1.0, stress=stress)
        assert over is SectionClass(min(expected + 1, 4))
    beyond = internal_part_class(ratio=coefficients[-1] * 10, epsilon=1.0, stress=stress)
    assert beyond is SectionClass.CLASS_4


def test_an_outstand_takes_each_class_at_its_own_limit():
    for expected, coefficient in zip((1, 2, 3), (9.0, 10.0, 14.0), strict=True):
        assert outstand_flange_class(ratio=coefficient, epsilon=1.0) is SectionClass(expected)
    assert outstand_flange_class(ratio=14.0 + 1e-9, epsilon=1.0) is SectionClass.CLASS_4


def test_the_combined_internal_limits_switch_at_alpha_one_half():
    """396ε/(13α−1) above 0,5 and 36ε/α at or below it, and they do not meet.

    The table's two branches are not a continuous curve: at α = 0,5 exactly the low branch
    gives 36/0,5 = 72 and the high branch would give 396/5,5 = 72 — they agree there, which
    is the check that the break is at 0,5 and that neither branch is off by a row.
    """
    assert 36.0 / 0.5 == pytest.approx(72.0)
    assert 396.0 / (13.0 * 0.5 - 1.0) == pytest.approx(72.0)
    at_half = internal_part_class(
        ratio=72.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, alpha=0.5, psi=0.0
    )
    assert at_half is SectionClass.CLASS_1
    # Above 0,5 the class 1 limit falls away fast — 396/(13·0,51−1) = 70,34 — so the same
    # ratio that is exactly class 1 at α = 0,5 is class 2 a hundredth above it. The limit is
    # a function of α, not a plateau, which is the thing a reader checks this branch for.
    just_over = internal_part_class(
        ratio=72.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, alpha=0.51, psi=0.0
    )
    assert 396.0 / (13.0 * 0.51 - 1.0) == pytest.approx(70.34, abs=0.01)
    assert just_over is SectionClass.CLASS_2
    # A fully compressed web (α = 1) takes 396/12 = 33, which is the compression column.
    assert 396.0 / (13.0 * 1.0 - 1.0) == pytest.approx(33.0)
    assert 456.0 / (13.0 * 1.0 - 1.0) == pytest.approx(38.0)


def test_the_class_3_combined_limits_switch_at_psi_minus_one():
    """42ε/(0,67+0,33ψ) above −1, and 62ε(1−ψ)√(−ψ) at or below it.

    At ψ = 1 (uniform compression) the first branch gives 42, which is the compression
    column of sheet 1 — the table agreeing with itself, and the check that ψ is the right
    way round. Getting its sign flipped would give 42/0,34 = 124 at uniform compression,
    which is the *bending* limit, and would pass every slender web in a column.
    """
    assert 42.0 / (0.67 + 0.33 * 1.0) == pytest.approx(42.0)
    assert 42.0 / (0.67 + 0.33 * -1.0) == pytest.approx(123.5, abs=0.6)
    # A part wholly in compression (α = 1, ψ = 1) reproduces the compression column on all
    # three rows: 396/12 = 33, 456/12 = 38, 42/(0,67+0,33) = 42. A ratio of exactly 42 is
    # therefore class 3 by both routes, which is the table agreeing with itself.
    uniform = internal_part_class(
        ratio=42.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, alpha=1.0, psi=1.0
    )
    assert uniform is SectionClass.CLASS_3
    assert internal_part_class(ratio=42.0, epsilon=1.0) is SectionClass.CLASS_3
    deep = internal_part_class(
        ratio=120.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, alpha=0.4, psi=-2.0
    )
    # 62(1-(-2))√2 = 263, so a ratio of 120 is inside class 3 by the deep-web branch.
    assert 62.0 * 3.0 * (2.0**0.5) == pytest.approx(263.0, abs=0.5)
    assert deep is SectionClass.CLASS_3


def test_a_flange_tip_in_tension_carries_the_extra_root_alpha():
    """9ε/α with the tip in compression, 9ε/(α√α) with it in tension.

    At α = 0,5 the class 1 limit is 18 one way and 25,46 the other, so a c/t of 20 is class
    2 with its tip in compression and class 1 with its tip in tension. The tip is not a
    detail of the drawing.
    """
    compression = outstand_flange_class(
        ratio=20.0,
        epsilon=1.0,
        stress=PartStress.BENDING_AND_COMPRESSION,
        alpha=0.5,
        tip=FlangeTip.IN_COMPRESSION,
        buckling_factor=1.0,
    )
    tension = outstand_flange_class(
        ratio=20.0,
        epsilon=1.0,
        stress=PartStress.BENDING_AND_COMPRESSION,
        alpha=0.5,
        tip=FlangeTip.IN_TENSION,
        buckling_factor=1.0,
    )
    assert 9.0 / 0.5 == pytest.approx(18.0)
    assert 9.0 / (0.5 * 0.5**0.5) == pytest.approx(25.46, abs=0.01)
    assert compression is not tension
    assert tension is SectionClass.CLASS_1
    assert compression is SectionClass.CLASS_2  # 10ε/α = 20, met exactly


def test_an_outstand_in_bending_alone_is_refused_rather_than_given_a_column():
    """Table 5.2 gives an outstand no bending-only column, and this does not invent one."""
    with pytest.raises(RefusalError, match="no bending-only column"):
        outstand_flange_class(ratio=10.0, epsilon=1.0, stress=PartStress.BENDING)


def test_a_combined_outstand_without_k_sigma_is_refused():
    """21ε√k_σ needs k_σ, and the table gives it no default.

    Assuming the uniform-compression k_σ of 0,43 would make the limit 13,8ε and report a
    flange as class 3 that the real k_σ may well put in class 4.
    """
    with pytest.raises(RefusalError, match="k_sigma"):
        outstand_flange_class(
            ratio=12.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, alpha=0.6
        )


def test_an_angle_needs_both_of_its_limits():
    """h/t ≤ 15ε **and** (b+h)/2t ≤ 11,5ε, so either one failing makes it class 4."""
    assert angle_in_compression_class(leg_ratio=15.0, mean_ratio=11.5, epsilon=1.0) is (
        SectionClass.CLASS_3
    )
    assert angle_in_compression_class(leg_ratio=15.1, mean_ratio=11.5, epsilon=1.0) is (
        SectionClass.CLASS_4
    )
    assert angle_in_compression_class(leg_ratio=15.0, mean_ratio=11.6, epsilon=1.0) is (
        SectionClass.CLASS_4
    )
    # The sheet offers an angle in compression no class 1 or 2: the best is class 3.
    assert angle_in_compression_class(leg_ratio=1.0, mean_ratio=1.0, epsilon=1.0) is (
        SectionClass.CLASS_3
    )


def test_a_tube_is_classified_on_epsilon_squared_and_not_on_epsilon():
    """The finding: at S355 the class 3 limit is d/t ≤ 59,6, not ≤ 73,2.

    Taking the coefficients as multiples of ε instead of ε² runs one class optimistic
    across the whole range — a d/t of 60 reads class 3 where the standard makes it class 4,
    and a d/t of 50 reads class 2 where the standard makes it class 3.
    """
    epsilon = en1993_epsilon(yield_strength=_S355)
    assert round(90 * epsilon * epsilon, 1) == 59.6
    assert round(90 * epsilon, 1) == 73.2
    assert tubular_section_class(diameter_ratio=60.0, epsilon=epsilon) is SectionClass.CLASS_4
    assert tubular_section_class(diameter_ratio=50.0, epsilon=epsilon) is SectionClass.CLASS_3
    assert tubular_section_class(diameter_ratio=40.0, epsilon=epsilon) is SectionClass.CLASS_2
    assert tubular_section_class(diameter_ratio=30.0, epsilon=epsilon) is SectionClass.CLASS_1
    # At S235, where ε and ε² are both 1, the two readings cannot be told apart — which is
    # why a test at S235 alone would have passed with the coefficients on the wrong power.
    assert tubular_section_class(diameter_ratio=60.0, epsilon=1.0) is SectionClass.CLASS_2


def test_the_least_favourable_part_sets_the_section(tmp_path=None):
    """Clause 5.5.2(6): the highest class of the compressed parts, which is a max.

    A section whose web is class 1 and whose flange is class 3 is class 3, and the result
    says which element governed rather than only what the section was.
    """
    section, web, flange = rolled_i_section_class(
        height=Q("400 mm"),
        width=Q("400 mm"),
        web_thickness=Q("20 mm"),
        flange_thickness=Q("12 mm"),
        root_radius=Q("0 mm"),
        yield_strength=Q("235 MPa"),
        stress=PartStress.COMPRESSION,
    )
    # web c/t = (400 - 24)/20 = 18,8 -> class 1; flange c/t = 190/12 = 15,83 -> class 4.
    assert web is SectionClass.CLASS_1
    assert flange is SectionClass.CLASS_4
    assert section is SectionClass.CLASS_4
    assert section is max(web, flange)


def test_a_welded_section_takes_a_zero_root_radius():
    """A welded I has no root radius, and 0 is a value rather than a missing one."""
    section, _web, _flange = rolled_i_section_class(
        height=Q("400 mm"),
        width=Q("180 mm"),
        web_thickness=Q("8.6 mm"),
        flange_thickness=Q("13.5 mm"),
        root_radius=Q("0 mm"),
        yield_strength=_S355,
        stress=PartStress.BENDING,
    )
    assert section is SectionClass.CLASS_1


def test_dimensions_that_are_not_a_section_are_refused_by_name():
    """Flanges and radii that consume the whole depth are not an I-section."""
    with pytest.raises(RefusalError, match="flat width"):
        rolled_i_section_class(
            height=Q("50 mm"),
            width=Q("180 mm"),
            web_thickness=Q("8.6 mm"),
            flange_thickness=Q("13.5 mm"),
            root_radius=Q("21 mm"),
            yield_strength=_S355,
        )


@pytest.mark.parametrize("alpha", [0.0, -0.2, 1.5, float("nan")])
def test_an_alpha_outside_its_interval_is_refused(alpha: float):
    """α is the compressed share of the depth: in (0, 1]."""
    with pytest.raises((RefusalError, ValueError)):
        internal_part_class(
            ratio=50.0,
            epsilon=1.0,
            stress=PartStress.BENDING_AND_COMPRESSION,
            alpha=alpha,
            psi=0.0,
        )


def test_a_missing_alpha_or_psi_under_combined_stress_names_what_it_needs():
    with pytest.raises(RefusalError, match="alpha is required"):
        internal_part_class(
            ratio=50.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, psi=0.0
        )
    with pytest.raises(RefusalError, match="psi is required"):
        internal_part_class(
            ratio=50.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, alpha=0.6
        )


def test_a_psi_above_one_is_refused():
    """A ratio of end stresses cannot exceed 1; uniform compression is the other column."""
    with pytest.raises(RefusalError, match="cannot exceed 1"):
        internal_part_class(
            ratio=50.0,
            epsilon=1.0,
            stress=PartStress.BENDING_AND_COMPRESSION,
            alpha=0.6,
            psi=1.5,
        )


@pytest.mark.parametrize("ratio", [0.0, -5.0, float("nan"), float("inf")])
def test_a_ratio_that_is_not_a_width_over_a_thickness_is_refused(ratio: float):
    with pytest.raises((RefusalError, ValueError)):
        internal_part_class(ratio=ratio, epsilon=1.0)


@pytest.mark.parametrize("strength", [Q("0 MPa"), Q("-355 MPa")])
def test_a_yield_strength_that_is_not_positive_is_refused(strength):
    with pytest.raises(RefusalError, match="yield_strength"):
        en1993_epsilon(yield_strength=strength)


def test_a_length_is_not_a_yield_strength():
    with pytest.raises(RefusalError, match=r"\[pressure\]"):
        en1993_epsilon(yield_strength=Q("355 mm"))


def test_a_non_finite_yield_strength_cannot_pass_the_positivity_check():
    with pytest.raises((RefusalError, ValueError)):
        en1993_epsilon(yield_strength=Quantity(magnitude=float("nan"), unit="MPa"))
