"""NASA SP-8007 knockdown, anchored to hand evaluations of its own equations.

Neither edition works a numerical example (NASA/SP-8007-2020/REV 2's "Example
Application" gives no reproducible inputs), so each value is evaluated by hand from the
printed equations with its intermediates stated, and the 2020 Figure 4-2 form
0.606γ = 0.606 − 0.546(1 − e^−φ) is held as an independent restatement of 1968 Eq. 5.
"""

from __future__ import annotations

from math import exp, sqrt

import pytest

from anvilate.analysis.pressure_vessel import cylinder_axial_buckling_stress
from anvilate.analysis.shell_buckling import (
    CylinderLoading,
    cylinder_design_buckling_stress,
    sp8007_knockdown_factor,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

_AXIAL = CylinderLoading.AXIAL_COMPRESSION
_BENDING = CylinderLoading.BENDING


def test_axial_knockdown_at_r_over_t_100():
    # φ = √100/16 = 0.625; e^−0.625 = 0.5352614; γ = 1 − 0.901(0.4647386) = 0.5812705
    assert sp8007_knockdown_factor(radius_to_thickness=100, loading=_AXIAL) == pytest.approx(
        0.5812705, abs=5e-8
    )


def test_bending_knockdown_at_r_over_t_500():
    # φ = √500/16 = 1.397542; e^−φ = 0.247206; γ = 1 − 0.731(0.752794) = 0.449708
    assert sp8007_knockdown_factor(radius_to_thickness=500, loading=_BENDING) == pytest.approx(
        0.449706, abs=5e-6
    )


@pytest.mark.parametrize("ratio", [80, 300, 1000, 1499])
def test_the_2020_figure_4_2_form_agrees(ratio):
    """Rev 2 plots 0.606γ = 0.606 − 0.546(1 − e^−φ); 0.546/0.606 is 0.901 to three places."""
    phi = sqrt(ratio) / 16
    figure = (0.606 - 0.546 * (1 - exp(-phi))) / 0.606
    assert sp8007_knockdown_factor(radius_to_thickness=ratio, loading=_AXIAL) == pytest.approx(
        figure, abs=2e-4
    )


def test_bending_is_knocked_down_less_than_compression():
    for ratio in (50, 200, 800, 1400):
        axial = sp8007_knockdown_factor(radius_to_thickness=ratio, loading=_AXIAL)
        bending = sp8007_knockdown_factor(radius_to_thickness=ratio, loading=_BENDING)
        assert 0 < axial < bending < 1


def test_the_design_stress_is_gamma_times_the_classical_stress():
    args = {
        "elastic_modulus": Quantity(magnitude=70.0, unit="GPa"),
        "wall_thickness": Quantity(magnitude=2.0, unit="mm"),
        "mean_radius": Quantity(magnitude=400.0, unit="mm"),
        "poisson": 0.33,
    }
    # classical: 70,000 × (2/400)/√(3(1 − 0.1089)) = 350/1.635031 = 214.06 MPa
    classical = cylinder_axial_buckling_stress(**args).to("MPa").magnitude
    assert classical == pytest.approx(350 / sqrt(3 * (1 - 0.33**2)), rel=1e-12)
    design = cylinder_design_buckling_stress(**args, loading=_AXIAL).to("MPa").magnitude
    gamma = 1 - 0.901 * (1 - exp(-sqrt(200) / 16))
    assert design == pytest.approx(gamma * classical, rel=1e-12)
    # r/t = 200: φ = 0.883883, e^−φ = 0.413217, γ = 1 − 0.901(0.586783) = 0.471309
    assert design == pytest.approx(0.471309 * 214.06, abs=0.01)


@pytest.mark.parametrize("ratio", [1500, 2000, 0, -5, float("nan"), float("inf")])
def test_r_over_t_outside_the_fit_is_refused(ratio):
    with pytest.raises(ValueError, match="radius_to_thickness|r/t"):
        sp8007_knockdown_factor(radius_to_thickness=ratio, loading=_AXIAL)


def test_a_thick_wall_is_refused_by_the_classical_formula_first():
    with pytest.raises(RefusalError, match="thin-shell"):
        cylinder_design_buckling_stress(
            elastic_modulus=Quantity(magnitude=200.0, unit="GPa"),
            wall_thickness=Quantity(magnitude=20.0, unit="mm"),
            mean_radius=Quantity(magnitude=100.0, unit="mm"),
            poisson=0.3,
            loading=_AXIAL,
        )


def test_a_loading_must_be_named_as_one():
    with pytest.raises(RefusalError, match="loading"):
        sp8007_knockdown_factor(radius_to_thickness=100, loading="axial")  # type: ignore[arg-type]
