"""Classical lamination theory, anchored to NASA RP-1351 and NASA TM X-73305 worked examples.

RP-1351 (Nettles, 1994) rounds the minor Poisson ratio to 0.02 where the reciprocal
ν₁₂·E₂/E₁ is 0.0195, so its stiffnesses are matched to 2e-4; everything it derives from
three-figure intermediates is matched against the exact recomputation, with the printed
figure beside it. Neither source works a failure criterion, so the criteria are anchored
on their closed-form limits: a uniaxial ply stress fails each one at exactly its strength.
"""

from __future__ import annotations

from math import inf, sqrt

import pytest

from anvilate.analysis.laminate import (
    Lamina,
    Ply,
    first_ply_failure,
    laminate_response,
    laminate_stiffness,
    reduced_stiffness,
    transformed_reduced_stiffness,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _psi(value: float) -> Quantity:
    return Quantity(magnitude=value, unit="psi")


def _as4(**strengths: object) -> Lamina:
    """AS4/3501-6 as RP-1351 states it (p. 31): E1 20.01, E2 1.301, G12 1.001 Msi, ν12 0.3."""
    return Lamina(
        longitudinal_modulus=_psi(20.01e6),
        transverse_modulus=_psi(1.301e6),
        shear_modulus=_psi(1.001e6),
        major_poisson_ratio=0.3,
        thickness=Quantity(magnitude=0.005, unit="inch"),
        **strengths,  # type: ignore[arg-type]
    )


def _stack(lamina: Lamina, *angles: float) -> list[Ply]:
    return [Ply(lamina=lamina, angle=angle) for angle in angles]


def _mag(matrix, unit: str) -> list[list[float]]:
    return [[q.to(unit).magnitude for q in row] for row in matrix]


_PER_INCH = [Quantity(magnitude=0.0, unit="lbf/inch")] * 2


# --- stiffness: RP-1351 Examples 1 and 2 ----------------------------------------------------


def test_rp1351_example_1_reduced_stiffness():
    q = _mag(reduced_stiffness(_as4()), "psi")
    # printed: Q11 20,130,785; Q22 1,308,853; Q12 392,656; Q66 1,001,000 (with ν21 = 0.02)
    assert q[0][0] == pytest.approx(20_130_785, rel=2e-4)
    assert q[1][1] == pytest.approx(1_308_853, rel=2e-4)
    assert q[0][1] == pytest.approx(392_656, rel=2e-4)
    assert q[2][2] == pytest.approx(1_001_000, rel=1e-12)
    assert q[0][2] == q[1][2] == 0.0


def test_rp1351_example_1_off_axis_stiffness_at_plus_45():
    q = _mag(transformed_reduced_stiffness(_as4(), 45), "psi")
    # printed: Q̄11 = Q̄22 6,557,237; Q̄12 4,555,238; Q̄16 = Q̄26 4,705,483; Q̄66 5,163,582
    assert q[0][0] == pytest.approx(6_557_237, rel=2e-4)
    assert q[1][1] == pytest.approx(q[0][0], rel=1e-12)
    assert q[0][1] == pytest.approx(4_555_238, rel=2e-4)
    assert q[0][2] == pytest.approx(4_705_483, rel=2e-4) and q[0][2] > 0
    assert q[2][2] == pytest.approx(5_163_582, rel=2e-4)
    # a -45 ply flips only the couplings
    minus = _mag(transformed_reduced_stiffness(_as4(), -45), "psi")
    assert minus[0][2] == pytest.approx(-q[0][2], rel=1e-12)


def test_rp1351_example_1_a_matrix_and_modulus():
    stiffness = laminate_stiffness(_stack(_as4(), 0, 45, 45, 0))  # [0/+45]s
    a = _mag(stiffness.a, "lbf/inch")
    # printed: A11 266,880; A12 49,479; A22 78,661; A16 = A26 47,055; A66 61,646
    for (i, j), printed in {(0, 0): 266_880, (0, 1): 49_479, (1, 1): 78_661,
                            (0, 2): 47_055, (2, 2): 61_646}.items():  # fmt: skip
        assert a[i][j] == pytest.approx(printed, rel=3e-4), (i, j)
    assert stiffness.is_symmetric
    # printed Ex = 11,333,000 psi
    assert stiffness.effective_longitudinal_modulus.to("psi").magnitude == pytest.approx(
        11_333_000, rel=3e-4
    )
    assert stiffness.thickness.to("inch").magnitude == pytest.approx(0.02, rel=1e-12)


def test_rp1351_example_2_coupling_and_bending_of_an_unsymmetric_pair():
    # RP-1351's [0/+45]T lists from the top; bottom first here, it is [+45, 0].
    stiffness = laminate_stiffness(_stack(_as4(), 45, 0))
    b = _mag(stiffness.b, "lbf")
    d = _mag(stiffness.d, "lbf*inch")
    # printed B: 170, -52, -66, -59, -52 lb; D: 1.112, 0.206, 0.328, 0.196, 0.257 in-lb
    for (i, j), printed in {(0, 0): 170, (0, 1): -52, (1, 1): -66,
                            (0, 2): -59, (2, 2): -52}.items():  # fmt: skip
        assert b[i][j] == pytest.approx(printed, abs=0.6), (i, j)
    for (i, j), printed in {(0, 0): 1.112, (0, 1): 0.206, (1, 1): 0.328,
                            (0, 2): 0.196, (2, 2): 0.257}.items():  # fmt: skip
        assert d[i][j] == pytest.approx(printed, abs=6e-4), (i, j)
    assert not stiffness.is_symmetric


def test_astronautic_structures_manual_f1_example_1():
    """TM X-73305 §F1.2.3 Ex 1: Q = 1e6 [30, 1, 0; 1, 3, 0; 0, 0, 1] psi, [-45/0/+45]."""
    # Back out the engineering constants that give that Q exactly.
    nu12, nu21 = 1 / 3, 1 / 30
    d = 1 - nu12 * nu21

    def ply(thickness: float) -> Lamina:
        return Lamina(
            longitudinal_modulus=_psi(30e6 * d),
            transverse_modulus=_psi(3e6 * d),
            shear_modulus=_psi(1e6),
            major_poisson_ratio=nu12,
            thickness=Quantity(magnitude=thickness, unit="inch"),
        )

    stiffness = laminate_stiffness(
        [Ply(lamina=ply(0.1), angle=-45), Ply(lamina=ply(0.2), angle=0),
         Ply(lamina=ply(0.1), angle=45)]
    )  # fmt: skip
    a = _mag(stiffness.a, "lbf/inch")
    b = _mag(stiffness.b, "lbf")
    dd = _mag(stiffness.d, "lbf*inch")
    assert [a[0][0], a[0][1], a[1][1], a[2][2]] == pytest.approx(
        [7.95e6, 1.75e6, 2.55e6, 1.75e6], rel=1e-9
    )
    assert a[0][2] == pytest.approx(0, abs=1e-3)
    assert b[0][2] == pytest.approx(0.2025e6, rel=1e-9)  # the ply order decides this sign
    assert b[0][0] == pytest.approx(0, abs=1e-6)
    # By hand: the ±45 plies span z³ from 0.001 to 0.008 in³ each, so (2 × 0.007/3) Q̄45 +
    # (0.002/3) Q0: D11 = 9.75e6(0.0046667) + 30e6(0.00066667) = 65,500. The manual prints
    # 0.06522e6, 0.4% low, from a rounded coefficient (as its Ex 2 does, at 0.25%).
    assert [dd[0][0], dd[0][1], dd[1][1]] == pytest.approx([65_500, 36_833.33, 47_500], rel=1e-6)


# --- response: RP-1351 Examples 3 and 6 -----------------------------------------------------


def test_rp1351_example_3_ply_stresses_under_500_lb_per_inch():
    response = laminate_response(
        _stack(_as4(), 0, 45, 45, 0),
        running_load=[Quantity(magnitude=500.0, unit="lbf/inch"), *_PER_INCH],
    )
    # printed ε⁰: 0.00221, -0.0007, -0.00115
    assert response.midplane_strain == pytest.approx((0.00221, -0.0007, -0.00115), rel=3e-3)
    assert response.curvature == pytest.approx((0, 0, 0), abs=1e-12)
    zero = next(p for p in response.plies if p.angle == 0)
    psi = [Quantity(magnitude=v, unit="Pa").to("psi").magnitude for v in zero.stress_xy]
    # exact 44,133 / -50 / -1,151 (printed 44,214 / -48 / -1,151, from rounded strains)
    assert psi == pytest.approx([44_133, -50, -1_151], rel=2e-3, abs=0.5)
    plus = next(p for p in response.plies if p.angle == 45)
    s12 = [Quantity(magnitude=v, unit="Pa").to("psi").magnitude for v in plus.stress_12]
    # exact 4,109 / 1,808 / -2,909 (printed 4,146 / 1,812 / -2,913)
    assert s12 == pytest.approx([4_109, 1_808, -2_909], rel=2e-3)


def test_rp1351_example_6_bending_puts_the_largest_stress_at_the_outer_fibre():
    response = laminate_response(
        _stack(_as4(), 0, 45, 45, 0),
        running_moment=[Quantity(magnitude=5.0, unit="lbf"), Quantity(magnitude=0.0, unit="lbf"),
                        Quantity(magnitude=0.0, unit="lbf")],
    )  # fmt: skip
    per_inch = [k * 0.0254 for k in response.curvature]
    # exact κ 0.41815, -0.16499, -0.09788 /in (printed 0.418, -0.165, -0.0975)
    assert per_inch == pytest.approx([0.41815, -0.16499, -0.09788], rel=1e-3)
    top = next(p for p in response.plies if p.index == 4 and p.surface == "top")
    # the top 0° ply, z = +0.01 in: printed σx 83,500 psi
    assert Quantity(magnitude=top.stress_xy[0], unit="Pa").to("psi").magnitude == pytest.approx(
        83_500, rel=3e-3
    )
    bottom = next(p for p in response.plies if p.index == 1 and p.surface == "bottom")
    assert bottom.stress_xy[0] == pytest.approx(-top.stress_xy[0], rel=1e-9)
    assert response.midplane_strain == pytest.approx((0, 0, 0), abs=1e-15)


# --- first-ply failure: closed-form limits --------------------------------------------------

_XT, _XC, _YT, _YC, _S = 2000.0, 1500.0, 50.0, 200.0, 80.0  # MPa, illustrative


def _strong(**overrides: float) -> Lamina:
    values = {"xt": _XT, "xc": _XC, "yt": _YT, "yc": _YC, "s": _S} | overrides

    def mpa(v: float) -> Quantity:
        return Quantity(magnitude=v, unit="MPa")

    return Lamina(
        longitudinal_modulus=Quantity(magnitude=140.0, unit="GPa"),
        transverse_modulus=Quantity(magnitude=10.0, unit="GPa"),
        shear_modulus=Quantity(magnitude=5.0, unit="GPa"),
        major_poisson_ratio=0.3,
        thickness=Quantity(magnitude=0.125, unit="mm"),
        longitudinal_tensile_strength=mpa(values["xt"]),
        longitudinal_compressive_strength=mpa(values["xc"]),
        transverse_tensile_strength=mpa(values["yt"]),
        transverse_compressive_strength=mpa(values["yc"]),
        shear_strength=mpa(values["s"]),
        strength_basis="B",
    )


def _ply_ratio(lamina: Lamina, angle: float, nx: float, ny: float = 0.0, nxy: float = 0.0):
    """A single ply under running loads (N/mm); its stresses are the load over 0.125 mm."""
    response = laminate_response(
        [Ply(lamina=lamina, angle=angle)],
        running_load=[Quantity(magnitude=v, unit="N/mm") for v in (nx, ny, nxy)],
    )
    return first_ply_failure(response)


@pytest.mark.parametrize(
    ("angle", "nx", "ny", "strength"),
    [(0, 1.0, 0, _XT), (0, -1.0, 0, _XC), (90, 1.0, 0, _YT), (90, -1.0, 0, _YC)],
)
def test_a_uniaxial_ply_stress_fails_every_criterion_at_its_strength(angle, nx, ny, strength):
    """Under one stress component, all three criteria reduce to stress = strength.

    For max stress and max strain this is the definition; for Tsai-Wu it is the root of
    F_i σ + F_ii σ² = 1, which is exactly Xt or -Xc — the check that F₁ and F₁₁ are right.
    A unidirectional ply loaded along or across its fibres is in uniaxial ply stress (the
    Poisson strain is free), so 1 N/mm on 0.125 mm is 8 MPa.
    """
    result = _ply_ratio(_strong(), angle, nx, ny)
    expected = strength / 8.0
    for ply in result.plies:
        assert ply.max_stress == pytest.approx(expected, rel=1e-9)
        assert ply.tsai_wu == pytest.approx(expected, rel=1e-9)
    assert result.strength_ratio == pytest.approx(expected, rel=1e-9)


def test_max_strain_differs_from_max_stress_by_the_poisson_strain():
    # 90° ply, stress across the fibres: ε1 = -ν21 σ2 / E2... the fibre strain stays far from
    # its allowable, and ε2 = σ2/E2 exactly, so max strain still governs on transverse.
    result = _ply_ratio(_strong(), 90, 1.0)
    assert result.plies[0].max_strain_mode == "transverse"
    assert result.plies[0].max_strain == pytest.approx(_YT / 8.0, rel=1e-9)


def test_pure_shear_fails_at_the_shear_strength():
    result = _ply_ratio(_strong(), 0, 0, 0, 1.0)
    assert result.strength_ratio == pytest.approx(_S / 8.0, rel=1e-9)
    assert result.plies[0].max_stress_mode == "shear"


def test_tsai_wu_interaction_lowers_biaxial_tension_strength():
    """σ1 = σ2 = σ: with F12* = -0.5 the interaction term is negative and Tsai-Wu predicts
    more strength than F12* = 0; hand-solve the quadratic for both and compare."""
    lamina = _strong()
    response = laminate_response(
        [Ply(lamina=lamina, angle=0)],
        running_load=[Quantity(magnitude=v, unit="N/mm") for v in (1.0, 1.0, 0.0)],
    )
    s1, s2, _ = response.plies[0].stress_12
    f1, f2 = 1 / _XT - 1 / _XC, 1 / _YT - 1 / _YC
    f11, f22 = 1 / (_XT * _XC), 1 / (_YT * _YC)
    s1, s2 = s1 / 1e6, s2 / 1e6  # MPa

    def root(star: float) -> float:
        a = f11 * s1**2 + f22 * s2**2 + 2 * star * sqrt(f11 * f22) * s1 * s2
        b = f1 * s1 + f2 * s2
        return (-b + sqrt(b * b + 4 * a)) / (2 * a)

    default = first_ply_failure(response)
    zero = first_ply_failure(response, tsai_wu_interaction=0.0)
    assert default.tsai_wu_interaction == -0.5  # Tsai & Hahn
    assert default.plies[0].tsai_wu == pytest.approx(root(-0.5), rel=1e-9)
    assert zero.plies[0].tsai_wu == pytest.approx(root(0.0), rel=1e-9)
    assert default.plies[0].tsai_wu > zero.plies[0].tsai_wu


def test_a_quasi_isotropic_laminate_fails_its_90_ply_first():
    """[0/45/-45/90]s in x tension: the 90° plies crack in transverse tension first."""
    lamina = _strong()
    response = laminate_response(
        _stack(lamina, 0, 45, -45, 90, 90, -45, 45, 0),
        running_load=[Quantity(magnitude=100.0, unit="N/mm"),
                      Quantity(magnitude=0.0, unit="N/mm"),
                      Quantity(magnitude=0.0, unit="N/mm")],
    )  # fmt: skip
    result = first_ply_failure(response)
    governing = response.stack[result.governing_ply - 1]
    assert governing.angle == 90 and result.governing_mode in {"transverse", "interactive"}
    assert result.strength_basis == ("B",)
    assert "Tsai-Wu F12* = -0.5" in str(result)
    # the 90° ply's σ2 at first failure equals Yt under max stress
    ninety = next(p for p in response.plies if p.angle == 90)
    by_stress = min(f.max_stress for f in result.plies if f.angle == 90)
    assert ninety.stress_12[1] / 1e6 * by_stress == pytest.approx(_YT, rel=1e-9)


def test_an_unloaded_laminate_has_an_infinite_ratio():
    response = laminate_response([Ply(lamina=_strong(), angle=0)])
    assert first_ply_failure(response).strength_ratio == inf


def test_no_strengths_means_not_evaluated_not_a_pass():
    response = laminate_response(
        _stack(_as4(), 0, 90),
        running_load=[Quantity(magnitude=10.0, unit="lbf/inch"), *_PER_INCH],
    )
    result = first_ply_failure(response)
    assert not result.evaluated and result.strength_ratio is None
    assert "no strengths" in result.reason and "not evaluated" in str(result)


# --- refusals -------------------------------------------------------------------------------


def test_some_strengths_without_the_rest_are_refused():
    with pytest.raises(ValueError, match="shear_strength"):
        _as4(
            longitudinal_tensile_strength=_psi(1),
            longitudinal_compressive_strength=_psi(1),
            transverse_tensile_strength=_psi(1),
            transverse_compressive_strength=_psi(1),
            strength_basis="A",
        )


def test_strengths_without_a_basis_are_refused():
    mpa = Quantity(magnitude=100.0, unit="MPa")
    with pytest.raises(ValueError, match="strength_basis"):
        _as4(
            longitudinal_tensile_strength=mpa,
            longitudinal_compressive_strength=mpa,
            transverse_tensile_strength=mpa,
            transverse_compressive_strength=mpa,
            shear_strength=mpa,
        )


def test_an_impossible_poisson_ratio_is_refused():
    with pytest.raises(ValueError, match="positive definite"):
        Lamina(
            longitudinal_modulus=_psi(1e6), transverse_modulus=_psi(1e6),
            shear_modulus=_psi(1e5), major_poisson_ratio=1.2,
            thickness=Quantity(magnitude=0.005, unit="inch"),
        )  # fmt: skip


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan")])
def test_a_modulus_must_be_positive_and_finite(value):
    with pytest.raises((RefusalError, ValueError)):
        Lamina(
            longitudinal_modulus=_psi(value), transverse_modulus=_psi(1e6),
            shear_modulus=_psi(1e5), major_poisson_ratio=0.3,
            thickness=Quantity(magnitude=0.005, unit="inch"),
        )  # fmt: skip


def test_a_wrong_dimension_is_refused_by_name():
    with pytest.raises(ValueError, match="thickness"):
        Lamina(
            longitudinal_modulus=_psi(1e6), transverse_modulus=_psi(1e6),
            shear_modulus=_psi(1e5), major_poisson_ratio=0.3,
            thickness=_psi(1.0),
        )  # fmt: skip


def test_an_empty_stack_and_a_bare_ply_are_refused():
    with pytest.raises(RefusalError, match="at least one ply"):
        laminate_stiffness([])
    with pytest.raises(ValueError, match="plies"):
        laminate_stiffness(Ply(lamina=_as4(), angle=0))  # type: ignore[arg-type]


def test_a_load_vector_has_three_components():
    with pytest.raises(RefusalError, match="running_load"):
        laminate_response(_stack(_as4(), 0), running_load=[_PER_INCH[0]])


@pytest.mark.parametrize("star", [-1.5, 2.0, float("nan")])
def test_the_tsai_wu_interaction_is_bounded(star):
    response = laminate_response([Ply(lamina=_strong(), angle=0)])
    with pytest.raises(RefusalError, match="tsai_wu_interaction"):
        first_ply_failure(response, tsai_wu_interaction=star)


@pytest.mark.parametrize("angle", [float("nan"), 400.0])
def test_a_ply_angle_is_a_finite_angle(angle):
    with pytest.raises((RefusalError, ValueError)):
        Ply(lamina=_as4(), angle=angle)
