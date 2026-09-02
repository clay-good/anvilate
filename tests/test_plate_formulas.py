"""Every declared plate formula evaluates to the number it ships with.

The same gate `tests/test_beam_deflection_formulas.py` puts on the beam module, through
the same evaluator. `PlateBendingResult` carries two symbolic strings per case — the peak
surface stress and the centre deflection — and the industrial pack renders both into a
cover-plate calculation report under the theory it cites. The numbers come from the code;
the strings come from a person.

The clamped-rectangle case is the one this most matters for: its formula is written on two
coefficients interpolated out of Roark Table 11.4, so the string and the values are the
only place the reader can see which row of the table the answer rests on.
"""

from __future__ import annotations

import inspect

import pytest

from anvilate.analysis import plate
from anvilate.units import Quantity
from formula_arithmetic import _arithmetic, _si

_COMMON = {
    "pressure": Quantity.parse("0.4 MPa"),
    "thickness": Quantity.parse("12 mm"),
    "elastic_modulus": Quantity.parse("200 GPa"),
}
# Deliberately not square and not a round number of aspect ratio: a 1:1 rectangle sits on
# a tabulated row rather than between two, and would check the interpolation against
# nothing.
_RECTANGLE = {"length": Quantity.parse("900 mm"), "width": Quantity.parse("620 mm")}
_CIRCLE = {"diameter": Quantity.parse("500 mm")}
_HOLE = {"hole_diameter": Quantity.parse("150 mm")}

_CASES = [
    (plate.simply_supported_plate_uniform_load, {**_COMMON, **_RECTANGLE}),
    (plate.clamped_plate_uniform_load, {**_COMMON, **_RECTANGLE}),
    (
        plate.simply_supported_plate_center_patch_load,
        {
            **_COMMON,
            **_RECTANGLE,
            "patch_length": Quantity.parse("200 mm"),
            "patch_width": Quantity.parse("150 mm"),
        },
    ),
    (plate.simply_supported_circular_plate_uniform_load, {**_COMMON, **_CIRCLE}),
    (plate.clamped_circular_plate_uniform_load, {**_COMMON, **_CIRCLE}),
    (plate.simply_supported_annular_plate_uniform_load, {**_COMMON, **_CIRCLE, **_HOLE}),
    (plate.clamped_annular_plate_uniform_load, {**_COMMON, **_CIRCLE, **_HOLE}),
]


def test_the_case_table_covers_every_plate_bending_case_in_the_module():
    """A new case with a wrong formula must not escape by not being listed."""
    returns_a_result = {
        name
        for name, function in vars(plate).items()
        if inspect.isfunction(function)
        and not name.startswith("_")
        and inspect.signature(function).return_annotation == "PlateBendingResult"
    }
    listed = {function.__name__ for function, _ in _CASES}
    assert returns_a_result - listed == set(), sorted(returns_a_result - listed)


@pytest.mark.parametrize(
    ("function", "arguments", "aspect"),
    [
        pytest.param(f, a, aspect, id=f"{f.__name__}-{aspect}")
        for f, a in _CASES
        for aspect in ("stress", "deflection")
    ],
)
def test_a_declared_plate_formula_evaluates_to_the_value_it_ships_with(function, arguments, aspect):
    result = function(**arguments)
    symbolic = getattr(result, f"{aspect}_formula")
    if symbolic is None:
        assert result.underived is not None, "a case with no formula must say why"
        pytest.skip("declares no closed form")
    values = {item.symbol: _si(item.value) for item in getattr(result, f"{aspect}_inputs")}
    computed = _arithmetic(symbolic, values)
    expected = (
        (result.max_bending_stress if aspect == "stress" else result.max_deflection)
        .pint.to_base_units()
        .magnitude
    )
    assert computed == pytest.approx(expected, rel=1e-9), (
        f"{function.__name__} declares {symbolic!r}, which evaluates to {computed:.6g} "
        f"in SI base units; it returned {expected:.6g}"
    )


def test_the_roark_coefficients_are_the_interpolated_ones_and_are_glossed_as_such():
    """The two numbers a reviewer looks up, and the only place the report shows them.

    Folding α and β into the expression would render "0.0284·q·b⁴/(E·t³)" — a number with
    no table row behind it. The gloss has to name the ratio it was read at, because the
    table is interpolated and the row is not one of the printed ones.
    """
    result = plate.clamped_plate_uniform_load(**_COMMON, **_RECTANGLE)
    glossary = {item.symbol: item for item in (*result.stress_inputs, *result.deflection_inputs)}
    for symbol in ("α", "β"):
        assert "Table 11.4" in glossary[symbol].description
        assert "b/a = 0.689" in glossary[symbol].description
    # Interpolated, not a tabulated row: the values sit strictly between two of them.
    assert 0 < glossary["α"].value < 0.0284
    assert 0.4 < glossary["β"].value < 0.5


# --- the modal half ----------------------------------------------------------------------
#
# `plate_fundamental_frequency_derivation` is the only dispatch over the six plate modal
# cases, so it is also the only place a case could be paired with the wrong expression or
# the wrong eigenvalue. Every case is called through it and the formula read back.

_MODAL_COMMON = {
    "mass_per_area": Quantity.parse("94.2 kg/m**2"),
    "thickness": Quantity.parse("12 mm"),
    "elastic_modulus": Quantity.parse("200 GPa"),
}
_MODAL_CASES = [
    ("rectangle simply supported", {**_RECTANGLE}),
    ("rectangle clamped", {**_RECTANGLE, "clamped": True}),
    ("circle simply supported", {**_CIRCLE}),
    ("circle clamped", {**_CIRCLE, "clamped": True}),
    ("annulus simply supported", {**_CIRCLE, **_HOLE}),
    ("annulus clamped", {**_CIRCLE, **_HOLE, "clamped": True}),
]


@pytest.mark.parametrize(
    ("label", "geometry"),
    [pytest.param(label, geometry, id=label) for label, geometry in _MODAL_CASES],
)
def test_a_plate_modal_formula_evaluates_to_the_frequency_it_ships_with(label, geometry):
    from anvilate.analysis import plate_fundamental_frequency_derivation

    work = plate_fundamental_frequency_derivation(**_MODAL_COMMON, **geometry)
    assert work.unresolved_symbols() == ()
    values = {item.symbol: _si(item.value) for item in work.inputs}
    computed = _arithmetic(work.symbolic, values)
    expected = work.result.value.pint.to_base_units().magnitude
    assert computed == pytest.approx(expected, rel=1e-9), (
        f"{label} declares {work.symbolic!r}, which evaluates to {computed:.6g} Hz; "
        f"it returned {expected:.6g} Hz"
    )


def test_the_modal_derivation_returns_the_frequency_the_public_check_returns():
    """It has to be the same number, or the report shows work for a different plate.

    The derivation calls the public function rather than re-deriving, and this is the
    assertion that says so: a second implementation of `(λ²/2π)·√(D/(μ·R⁴))` inside the
    derivation builder would agree with itself and drift from the check everyone else uses.
    """
    from anvilate.analysis import (
        clamped_circular_plate_fundamental_frequency,
        plate_fundamental_frequency_derivation,
        simply_supported_plate_fundamental_frequency,
    )

    round_work = plate_fundamental_frequency_derivation(**_MODAL_COMMON, **_CIRCLE, clamped=True)
    assert round_work.result.value == clamped_circular_plate_fundamental_frequency(
        **_MODAL_COMMON, **_CIRCLE
    )
    rect_work = plate_fundamental_frequency_derivation(**_MODAL_COMMON, **_RECTANGLE)
    assert rect_work.result.value == simply_supported_plate_fundamental_frequency(
        **_MODAL_COMMON, **_RECTANGLE
    )


def test_each_modal_case_cites_the_theory_its_eigenvalue_actually_came_from():
    """Three theories over six cases, and the pack used to pick from its own copy of the
    table — then patch the citation by hand for a holed cover, which is where a mismatch
    would have lived.
    """
    from anvilate.analysis import plate_fundamental_frequency_derivation

    cited = {
        label: plate_fundamental_frequency_derivation(**_MODAL_COMMON, **geometry).citation
        for label, geometry in _MODAL_CASES
    }
    assert cited["rectangle simply supported"] == "Kirchhoff plate theory (Navier eigenvalue)"
    assert cited["circle simply supported"] == "Kirchhoff plate theory (Bessel eigenvalue)"
    assert cited["circle clamped"] == "Kirchhoff plate theory (Bessel eigenvalue)"
    for tabulated in ("rectangle clamped", "annulus simply supported", "annulus clamped"):
        assert cited[tabulated] == "Kirchhoff plate theory (FD-verified eigenvalue table)"
