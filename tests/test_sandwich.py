"""Sandwich local modes, anchored to where NASA's public sources restate one another.

NASA CR-1457 and the Astronautic Structures Manual (NASA TM X-73306 §C3) state the same
modes in different forms: ASM's dimpling coefficient 2.2 is CR-1457's 2.0/(1 − ν²) at
ν = 0.3; ASM's solid-core wrinkling 0.50·(E·E·G)^(1/3) omits CR-1457's (1 − ν²), a factor
of 1.032. CR-1457 says its honeycomb fit at K_δ = 0 sits about 5% below Bartelds and
Mayers' 0.86, and its lower bound 0.33 is a knockdown of about 0.4 on 0.82. The tests hold
the code to each restatement, then to hand calculations.
"""

from __future__ import annotations

from math import sqrt

import pytest

from anvilate.analysis.sandwich import CoreKind, SandwichPanel, sandwich_local_modes
from anvilate.units import Quantity


def _q(v: float, unit: str) -> Quantity:
    return Quantity(magnitude=v, unit=unit)


def _panel(**overrides: object) -> SandwichPanel:
    fields: dict[str, object] = {
        "facing_modulus": _q(70_000, "MPa"), "facing_poisson": 0.3,
        "facing_thickness": _q(0.25, "mm"), "core_thickness": _q(12.7, "mm"),
        "core_kind": CoreKind.HONEYCOMB, "core_normal_modulus": _q(300, "MPa"),
        "core_shear_modulus": _q(150, "MPa"), "cell_size": _q(9.5, "mm"),
    } | overrides  # fmt: skip
    return SandwichPanel(**fields)  # type: ignore[arg-type]


def _mode(screen, name):
    (m,) = [m for m in screen.modes if m.mode == name]
    return m


def test_dimpling_matches_the_astronautic_structures_manuals_2_2():
    screen = sandwich_local_modes(_panel(), facing_stress=_q(50, "MPa"))
    asm = 2.2 * 70_000 * (0.25 / 9.5) ** 2
    assert _mode(screen, "intracell dimpling").allowable == pytest.approx(asm, rel=1e-3)


def test_solid_core_wrinkling_is_the_manuals_form_with_the_poisson_term():
    panel = _panel(core_kind=CoreKind.SOLID_OR_FOAM, core_normal_modulus=_q(80, "MPa"),
                   core_shear_modulus=_q(30, "MPa"))  # fmt: skip
    screen = sandwich_local_modes(panel, facing_stress=_q(50, "MPa"))
    asm = 0.50 * (70_000 * 80 * 30) ** (1 / 3)
    assert _mode(screen, "face wrinkling").allowable == pytest.approx(
        asm / (1 - 0.09) ** (1 / 3), rel=1e-12
    )
    assert [m.mode for m in screen.modes][0] == "face wrinkling"  # no dimpling for a foam


def test_honeycomb_wrinkling_bounds_and_fit():
    stiffness = 70_000 * sqrt(300 * 0.25 / (70_000 * 12.7))
    lower = sandwich_local_modes(_panel(), facing_stress=_q(50, "MPa"))
    assert _mode(lower, "face wrinkling").allowable == pytest.approx(0.33 * stiffness, rel=1e-12)
    assert 0.33 / 0.82 == pytest.approx(0.4, abs=0.003)
    # a flat core, K_δ = 0: the 0.82 fit, about 5% below Bartelds and Mayers' 0.86
    flat = sandwich_local_modes(
        _panel(waviness=_q(1e-9, "mm"), core_flatwise_strength=_q(2.0, "MPa")),
        facing_stress=_q(50, "MPa"),
    )
    fitted = _mode(flat, "face wrinkling").allowable
    assert fitted == pytest.approx(0.82 * stiffness, rel=1e-6)
    assert fitted / (0.86 * stiffness) == pytest.approx(0.953, abs=0.001)


def test_waviness_knocks_the_fit_down_by_one_plus_0_64_k():
    # δ 0.05 mm: K_δ = 0.05 × 300/(12.7 × 2.0) = 0.59055; 1 + 0.64K = 1.37795
    wavy = sandwich_local_modes(
        _panel(waviness=_q(0.05, "mm"), core_flatwise_strength=_q(2.0, "MPa")),
        facing_stress=_q(50, "MPa"),
    )
    stiffness = 70_000 * sqrt(300 * 0.25 / (70_000 * 12.7))
    assert _mode(wavy, "face wrinkling").allowable == pytest.approx(
        0.82 * stiffness / 1.377953, rel=1e-6
    )


def test_thin_faces_on_a_coarse_core_dimple_first():
    """The spec's scenario: dimpling governs on a coarse-celled core."""
    # dimpling 2 × 70,000/0.91 × (0.25/9.5)² = 106.5 MPa; wrinkling 0.33 × 643.0 = 212.2 MPa
    screen = sandwich_local_modes(_panel(), facing_stress=_q(60, "MPa"))
    dimpling = _mode(screen, "intracell dimpling").allowable
    wrinkling = _mode(screen, "face wrinkling").allowable
    assert dimpling == pytest.approx(2 * 70_000 / 0.91 * (0.25 / 9.5) ** 2, rel=1e-12)
    assert dimpling < wrinkling
    assert screen.governing == "intracell dimpling"
    assert "not a lower bound" in _mode(screen, "intracell dimpling").basis


def test_shear_crimping_by_hand():
    # h = 12.7 + 0.25 = 12.95; σ = 12.95²/(0.5 × 12.7) × 150 = 3,961.3 MPa
    screen = sandwich_local_modes(_panel(), facing_stress=_q(60, "MPa"))
    assert _mode(screen, "shear crimping").allowable == pytest.approx(
        12.95**2 / (0.5 * 12.7) * 150, rel=1e-12
    )


def test_core_shear_is_the_shear_per_width_over_h():
    screen = sandwich_local_modes(_panel(core_shear_strength=_q(1.4, "MPa")),
                                  transverse_shear=_q(12.95, "N/mm"))  # fmt: skip
    core = _mode(screen, "core shear")
    assert core.applied == pytest.approx(1.0, rel=1e-12) and core.ratio == pytest.approx(1 / 1.4)


def test_a_mode_missing_its_inputs_is_not_evaluated_and_names_them():
    screen = sandwich_local_modes(_panel(cell_size=None), facing_stress=_q(60, "MPa"),
                                  insert_load=_q(500, "N"))  # fmt: skip
    assert "cell_size" in _mode(screen, "intracell dimpling").reason
    assert "insert_pull_out_allowable" in _mode(screen, "insert pull-out").reason
    assert "not evaluated" in str(screen)


def test_insert_pull_out_against_its_declared_allowable():
    screen = sandwich_local_modes(_panel(insert_pull_out_allowable=_q(2_000, "N")),
                                  insert_load=_q(1_500, "N"))  # fmt: skip
    assert _mode(screen, "insert pull-out").ratio == pytest.approx(0.75)


@pytest.mark.parametrize(("field", "value"), [("facing_thickness", _q(0, "mm")),
                                              ("cell_size", _q(float("nan"), "mm")),
                                              ("core_normal_modulus", _q(1, "mm")),
                                              ("facing_poisson", 0.5)])  # fmt: skip
def test_bad_panel_fields_are_refused_by_name(field, value):
    with pytest.raises(ValueError, match=field):
        _panel(**{field: value})


def test_a_copied_panel_is_revalidated():
    with pytest.raises(ValueError):
        _panel().model_copy(update={"facing_poisson": 0.7})
