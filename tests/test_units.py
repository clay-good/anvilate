"""Tests for the units layer, tracking the units-and-quantities spec scenarios."""

from __future__ import annotations

import math
from typing import Annotated

import pytest
from pydantic import AfterValidator, BaseModel

from anvilate.units import (
    DimensionError,
    MissingUnitError,
    Quantity,
    UnitError,
    UnitSystem,
    render,
    render_dual,
    require_dimension,
)
from anvilate.units.rotation import (
    AmbiguousRotationalSpeedError,
    angular_speed_rad_per_s,
    revolutions_per_minute,
    revolutions_per_second,
)
from anvilate.units.temperature import (
    OffsetTemperatureError,
    temperature_difference_kelvin,
)

# --- Requirement: Mixed-unit input is accepted everywhere ---


@pytest.mark.parametrize(
    "text,mag,dim",
    [
        ("75 kip", 75.0, "[force]"),
        ("3 mm", 3.0, "[length]"),
        ("50 ksi", 50.0, "[pressure]"),
        ("1.1 kg", 1.1, "[mass]"),
        ("10 kip*ft", 10.0, "[force] * [length]"),
    ],
)
def test_parse_accepts_both_systems(text, mag, dim):
    q = Quantity.parse(text)
    assert q.magnitude == mag
    assert q.has_dimension(dim)


def test_unit_as_entered_is_preserved():
    # Stored canonically for computation, but the entered unit round-trips for
    # display and diffing.
    q = Quantity.parse("75 kip")
    assert q.unit == "kip"
    assert q.to("N").magnitude == pytest.approx(75 * 4448.2216, rel=1e-4)


# --- Requirement: Derived engineering units are first-class (plf/klf added) ---


def test_distributed_line_loads_defined():
    assert Quantity.parse("2 klf").has_dimension("[force] / [length]")
    assert Quantity.parse("500 plf").to("klf").magnitude == pytest.approx(0.5)


# --- Requirement: Dimensional consistency checked (Scenario: dimensional error rejected) ---


class _StressField(BaseModel):
    fy: Annotated[Quantity, AfterValidator(require_dimension("[pressure]", name="fy"))]


def test_dimensional_error_names_field_and_dimensions():
    _StressField(fy=Quantity.parse("50 ksi"))  # ok
    with pytest.raises(Exception) as exc:
        _StressField(fy=Quantity.parse("75 kip"))  # force where stress expected
    msg = str(exc.value)
    assert "fy" in msg
    assert "pressure" in msg  # expected dimension named
    assert "force" in msg or "[force]" in msg  # received dimension named


# --- Requirement: Unitless physical quantities are never assumed ---


def test_bare_number_rejected():
    with pytest.raises(MissingUnitError):
        Quantity.parse("75")
    with pytest.raises(MissingUnitError):
        Quantity.parse("1.5")


def test_unknown_unit_rejected():
    with pytest.raises(UnitError):
        Quantity.parse("5 flurbs")


def test_plausible_units_offered_for_bare_load():
    # The compiler offers candidates rather than guessing.
    us = UnitSystem.US.plausible_units("force")
    assert us[:2] == ["lbf", "kip"]  # project-system units lead
    assert "N" in us and "kN" in us  # cross-system still offered


# --- Requirement: Code-conventional precision; stable round-trip ---


def test_conventional_precision():
    assert render(Quantity.parse("1.234 ksi")) == "1.23 ksi"
    assert render(Quantity.parse("3.14159 mm")) == "3.14 mm"
    assert render(Quantity.parse("2.0 in")) == "2.000 in"


def test_render_in_project_system():
    # An SI stress rendered into a US report converts and rounds conventionally.
    q = Quantity.parse("344.7 MPa")
    assert render(q, system=UnitSystem.US) == "50.0 ksi"


def test_stable_round_trip():
    q = Quantity.parse("49.9992 ksi")
    first = render(q)
    second = render(Quantity.parse("49.9992 ksi"))
    assert first == second  # character-identical, no jitter


def test_render_dual_dimensioning():
    # Scenario: dual dimensioning — the primary-system value with the secondary
    # bracketed, each in its conventional unit and precision.
    q = Quantity.parse("1 in")
    assert render_dual(q, primary=UnitSystem.SI) == "25.40 mm [1.000 in]"
    assert render_dual(q, primary=UnitSystem.US) == "1.000 in [25.40 mm]"


def test_dimension_error_is_raised_directly_by_validator():
    checker = require_dimension("[pressure]", name="stress")
    with pytest.raises(DimensionError):
        checker(Quantity.parse("10 mm"))


def test_angular_speed_accepts_every_spelling_that_names_an_angle():
    # Scenario: 100 rpm written four ways. All four name an angle, so all four
    # must land on the same omega -- 10.4720 rad/s, i.e. 1.66667 rev/s.
    for unit, magnitude in (
        ("rpm", 100.0),
        ("revolution/minute", 100.0),
        ("turn/s", 100.0 / 60.0),
        ("rad/s", 100.0 * 2.0 * math.pi / 60.0),
    ):
        speed = Quantity(magnitude=magnitude, unit=unit)
        assert angular_speed_rad_per_s(speed, name="speed") == pytest.approx(10.47197551, rel=1e-9)
        assert revolutions_per_second(speed, name="speed") == pytest.approx(1.666666667, rel=1e-9)


@pytest.mark.parametrize("unit", ["Hz", "1/s", "1/min", "1/hour"])
def test_angular_speed_refuses_a_bare_inverse_time(unit):
    # Pint's radian is dimensionless, so Hz and rad/s share a dimensionality and
    # differ by 2*pi. Accepting either spelling would silently return one of them
    # 6.28x wrong -- and always unconservative -- so the guard refuses outright.
    with pytest.raises(AmbiguousRotationalSpeedError, match="bare inverse time"):
        angular_speed_rad_per_s(Quantity(magnitude=100.0, unit=unit), name="roll_speed")


def test_ambiguous_rotational_speed_error_names_the_parameter():
    with pytest.raises(AmbiguousRotationalSpeedError, match="roll_speed"):
        revolutions_per_second(Quantity(magnitude=100.0, unit="Hz"), name="roll_speed")


def test_revolutions_per_minute_closes_the_to_rpm_version_of_the_same_trap():
    # Converting straight with .to("rpm") LOOKS like it sidesteps the radian problem, and does
    # not: pint's revolution is 2*pi radian, so .to("rpm") applies exactly the same 2*pi factor
    # as .to("rad/s"). 30 Hz reads as 286.5 rpm rather than 1800 -- and 1800 is what a caller
    # writing "30 Hz" means. The guard refuses rather than guessing.
    assert Quantity(magnitude=30.0, unit="Hz").to("rpm").magnitude == pytest.approx(
        286.4788975654116, rel=1e-9
    )
    with pytest.raises(AmbiguousRotationalSpeedError):
        revolutions_per_minute(Quantity(magnitude=30.0, unit="Hz"), name="speed")

    # Every spelling that names an angle agrees on 1800 rpm.
    for unit, magnitude in (
        ("rpm", 1800.0),
        ("turn/s", 30.0),
        ("rad/s", 1800.0 * 2.0 * math.pi / 60.0),
        ("deg/s", 1800.0 * 360.0 / 60.0),
    ):
        speed = Quantity(magnitude=magnitude, unit=unit)
        assert revolutions_per_minute(speed, name="speed") == pytest.approx(1800.0, rel=1e-9)
    # The three conversions stay mutually consistent: rpm = 60*rev/s = 60*omega/(2*pi).
    speed = Quantity(magnitude=1800.0, unit="rpm")
    assert revolutions_per_minute(speed, name="s") == pytest.approx(
        60.0 * revolutions_per_second(speed, name="s"), rel=1e-12
    )
    assert revolutions_per_minute(speed, name="s") == pytest.approx(
        60.0 * angular_speed_rad_per_s(speed, name="s") / (2.0 * math.pi), rel=1e-12
    )


def test_angle_tokens_match_pints_canonical_spelling_not_the_one_written():
    # The guard matches pint's CANONICAL unit string, which is not always what the caller types:
    # "gradian" canonicalises to "grade" and "rpm" to "revolutions_per_minute". Matching the
    # typed spelling would reject these legitimate angle rates.
    for unit in ("gradian/s", "arcminute/s", "arcsecond/s", "cycle/s", "rps", "rad/min"):
        assert angular_speed_rad_per_s(Quantity(magnitude=1.0, unit=unit), name="s") > 0.0
    # A count per time still names no angle, so it is still refused.
    for unit in ("count/s", "Hz", "1/s"):
        with pytest.raises(AmbiguousRotationalSpeedError):
            angular_speed_rad_per_s(Quantity(magnitude=1.0, unit=unit), name="s")


def test_temperature_difference_refuses_an_offset_scale():
    # A difference and a point on a scale share a dimensionality, so [temperature] accepts both
    # and no dimension check separates them. The conversion is where they part: 5 K is a 5 K
    # rise, but "5 degC" converts to 278.15 K -- the same rise multiplied by fifty-five.
    assert Quantity(magnitude=5.0, unit="degC").to("K").magnitude == pytest.approx(278.15)
    for unit in ("degC", "degF", "degree_Celsius", "degree_Fahrenheit"):
        with pytest.raises(OffsetTemperatureError, match="temperature DIFFERENCE"):
            temperature_difference_kelvin(
                Quantity(magnitude=5.0, unit=unit), name="allowable_temperature_rise"
            )

    # The units that genuinely express a difference all pass, and convert by scale alone.
    assert temperature_difference_kelvin(
        Quantity(magnitude=5.0, unit="K"), name="d"
    ) == pytest.approx(5.0, rel=1e-12)
    assert temperature_difference_kelvin(
        Quantity(magnitude=5.0, unit="delta_degC"), name="d"
    ) == pytest.approx(5.0, rel=1e-12)
    # delta_degF and degR are the same size: 5/9 of a kelvin.
    assert temperature_difference_kelvin(
        Quantity(magnitude=9.0, unit="delta_degF"), name="d"
    ) == pytest.approx(5.0, rel=1e-12)
    assert temperature_difference_kelvin(
        Quantity(magnitude=9.0, unit="degR"), name="d"
    ) == pytest.approx(5.0, rel=1e-12)

    # The guard tests the CONVERSION, not a list of unit names, so it catches spellings nobody
    # enumerated -- which is exactly how "degree_Fahrenheit" slipped through an earlier version.
    assert temperature_difference_kelvin(
        Quantity(magnitude=-5.0, unit="K"), name="d"
    ) == pytest.approx(-5.0, rel=1e-12)


def test_a_moment_and_a_second_moment_follow_the_project_unit_system():
    """They were unmapped, so a US derivation mixed inches with N·m and mm⁴ in one line."""
    from anvilate.units.format import render

    moment = Quantity.parse("1500 N*m")
    assert render(moment, system=UnitSystem.SI, pretty=True) == "1500000.00 N·mm"
    assert render(moment, system=UnitSystem.US, pretty=True) == "13.28 kip·in"

    second_moment = Quantity.parse("2.1e6 mm**4")
    assert render(second_moment, system=UnitSystem.SI, pretty=True) == "2100000.00 mm⁴"
    assert render(second_moment, system=UnitSystem.US, pretty=True) == "5.05 in⁴"

    # The point of choosing N·mm over N·m: σ = M·c/I evaluates as printed. The moment's
    # length unit has to match the second moment's, or the substituted line a reviewer is
    # meant to check by hand is out by a factor of a thousand.
    for system, m, c, i, expected in (
        (UnitSystem.SI, 1500000.00, 50.00, 2100000.00, 35.71),
        (UnitSystem.US, 13.28, 1.969, 5.05, 5.18),
    ):
        assert m * c / i == pytest.approx(expected, rel=2e-3), system
    # And both systems land on the same stress, which is the real check.
    assert 5.18 == pytest.approx(Quantity.parse("35.71 MPa").to("ksi").magnitude, rel=2e-3)


def test_compound_unit_labels_read_force_first():
    """Pint sorts factors alphabetically; engineering documents put the force first."""
    from anvilate.units.format import _engineering_order, render

    assert render(Quantity.parse("1500 N*m"), unit="kip*in", pretty=True) == "13.28 kip·in"
    assert render(Quantity.parse("1500 N*m"), unit="N*m", pretty=True) == "1500.00 N·m"
    assert render(Quantity.parse("100 lbf*ft"), unit="lbf*ft", pretty=True) == "100.00 lbf·ft"

    # It reorders factors and never changes, drops, or invents one — a label it cannot
    # place is passed through exactly as Pint wrote it rather than guessed at.
    for label in ("mm", "mm⁴", "N/mm", "m·N/s", "K·W", "kg·m²"):
        assert _engineering_order(label) == label
    assert _engineering_order("m·N") == "N·m"
    assert _engineering_order("in·kip") == "kip·in"
    # Two factors of the same rank keep their given order — there is no convention to
    # appeal to between two lengths.
    assert _engineering_order("in·mm") == "in·mm"
    # Anything with a division is left alone: the numerator/denominator split matters
    # more than the factor order, and a mangled one would be worse than an odd one.
    assert _engineering_order("m·N/s") == "m·N/s"

    # The unpretty (machine-readable) label is untouched — spec cards echo it verbatim,
    # and the reordering is a document-rendering concern, not a data one.
    assert render(Quantity.parse("1500 N*m"), unit="kip*in", pretty=False) == "13.28 in * kip"
