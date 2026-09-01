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


# --- the system units have to compose -----------------------------------------------------


@pytest.mark.parametrize("system", list(UnitSystem))
def test_the_system_units_compose(system):
    """A report's units are chosen so a substituted line checks by hand, not for familiarity.

    That is why `moment_unit` is N·mm rather than N·m and `distributed_load_unit` is N/mm
    rather than kN/m: σ = M/Z only reads right when the moment's length unit matches the
    section modulus's, and M = wL²/8 only reads right when the line load's does too. Stated
    as an assertion rather than a docstring, so "fixing" N/mm to the more familiar kN/m
    fails here instead of quietly making every SI report unverifiable by its reader.

    Each conversion factor must be exactly 1: a factor of 1000 is precisely the defect.
    """
    from anvilate.units.registry import UREG

    length = UREG.Unit(system.length_unit)
    checks = {
        "moment / section modulus = stress": (
            UREG.Unit(system.moment_unit) / UREG.Unit(system.section_modulus_unit),
            UREG.Unit(system.stress_unit),
        ),
        "line load x length^2 = moment": (
            UREG.Unit(system.distributed_load_unit) * length**2,
            UREG.Unit(system.moment_unit),
        ),
        "length^2 = area": (length**2, UREG.Unit(system.area_unit)),
        "length^4 = second moment": (length**4, UREG.Unit(system.second_moment_unit)),
        "length^3 = section modulus": (length**3, UREG.Unit(system.section_modulus_unit)),
    }
    wrong = {}
    for label, (composed, expected) in checks.items():
        factor = (1 * composed).to(expected).magnitude
        if factor != pytest.approx(1.0, rel=1e-12):
            wrong[label] = factor
    # `force_unit x length_unit = moment_unit` is deliberately NOT on this list: SI force is
    # kN and the moment is N·mm, so that product carries a factor of 1000. kN is what a
    # structural document writes a reaction in, and the substituted line spells the factors
    # out, so the reader is not asked to compose those two in their head.
    assert not wrong, (
        f"{system.value} report units do not compose: {wrong}. A reader following a "
        "substituted line has to multiply by these factors to check it"
    )


def test_the_composition_gate_catches_a_spelling_that_does_not_compose():
    """The adversary, and the correction it forced.

    The first version of this asserted that kN/m — the spelling somebody will reach for —
    is out by a factor of 1000. It is not: 1 kN/m *is* 1 N/mm, so either spelling composes
    exactly and the choice between them is legibility, not arithmetic. kN/mm is the one
    that really does not compose, and it is what the gate has to catch.
    """
    from anvilate.units.registry import UREG

    for spelling, factor in (("N/mm", 1.0), ("kN/m", 1.0), ("kN/mm", 1000.0), ("lbf/ft", None)):
        if factor is None:
            continue
        composed = (1 * UREG.Unit(spelling) * UREG.Unit("mm") ** 2).to(UREG.Unit("N*mm"))
        assert composed.magnitude == pytest.approx(factor), spelling


def test_every_dimension_the_units_requirement_names_is_converted_by_system():
    """`units-and-quantities` names the families the layer must support, and the rendering
    scenario says a value entered in one system is *displayed* in the project's.

    A dimension with no system mapping is not an error — it renders in whatever unit it
    arrived in, which is how a section modulus in in³ ended up beside a moment in N·mm in an
    SI report. So each named family is entered in the other system's unit and required to
    come back in this one's.
    """
    from anvilate.units import Quantity, render

    entered_us = {
        "force": ("50 kip", "kN"),
        "stress": ("36 ksi", "MPa"),
        "moment": ("2 kip*in", "N"),
        "distributed load": ("100 lbf/ft", "N / mm"),
        "second moment of area": ("5 in**4", "mm ** 4"),
        "section modulus": ("3 in**3", "mm ** 3"),
        "length": ("12 in", "mm"),
    }
    for family, (entered, expected_unit) in entered_us.items():
        shown = render(Quantity.parse(entered), system=UnitSystem.SI)
        assert shown.endswith(expected_unit), f"{family}: {entered} rendered SI as {shown}"


def test_decimals_distinguishing_widens_until_the_two_values_differ():
    from anvilate.units import decimals_distinguishing

    assert decimals_distinguishing(2.6, 2.5) == 2
    assert decimals_distinguishing(2.5005, 2.5) == 3
    assert decimals_distinguishing(1.00004, 1.0, minimum=3) == 5
    # A value genuinely equal to the reference gets the conventional precision back rather
    # than twelve places: no number of places separates them, and the caller has a
    # different sentence to write.
    assert decimals_distinguishing(1.0, 1.0) == 2
    assert decimals_distinguishing(float("nan"), 1.0) == 2
    assert decimals_distinguishing(float("inf"), 1.0) == 2
    # And it is bounded, so a difference below float resolution cannot loop.
    assert decimals_distinguishing(1.0 + 1e-15, 1.0) <= 12


def test_the_places_it_returns_really_do_separate_the_two():
    """The property, not the numbers: at the returned precision the two must not print the
    same, and one place fewer must not have separated them."""
    from anvilate.units import decimals_distinguishing

    for value, reference in ((2.5005, 2.5), (1.00004, 1.0), (0.10001, 0.1), (3.0, 2.5)):
        places = decimals_distinguishing(value, reference, minimum=1)
        assert f"{value:.{places}f}" != f"{reference:.{places}f}", (value, reference)
        if places > 1:
            assert f"{value:.{places - 1}f}" == f"{reference:.{places - 1}f}"


# --- The operations a Quantity does not support, and what they say --------------------


@pytest.mark.parametrize(
    ("operation", "call"),
    [
        ("<", lambda q: q < 1),
        ("<=", lambda q: q <= 1),
        (">", lambda q: q > 1),
        (">=", lambda q: q >= 1),
        # The reflected forms: `1 < q` falls through int.__lt__ to Quantity.__gt__, and a
        # library that answers `q < 1` and `1 < q` differently is one nobody can reason
        # about.
        ("<", lambda q: 1 > q),
        (">", lambda q: 1 < q),
        ("+", lambda q: q + 1),
        ("+", lambda q: 1 + q),
        ("-", lambda q: q - 1),
        ("*", lambda q: q * 2),
        ("*", lambda q: 2 * q),
        ("/", lambda q: q / 2),
    ],
)
def test_a_quantity_against_a_plain_number_refuses_by_naming_the_mistake(operation, call):
    """213 public analysis functions used to answer this with the interpreter's sentence.

    A caller told that everything in this library is a `Quantity` wraps a *ratio*, a
    *count* or an *angle in degrees* — parameters that take a plain number — and got

        TypeError: '<' not supported between instances of 'Quantity' and 'int'

    which names neither the parameter nor the mistake. `Quantity` defined none of these
    operators, which is why the interpreter was answering; defining them to refuse could
    regress nothing and fixes every one of those functions at once.

    The trade is stated rather than hidden: the operator cannot name the *parameter*,
    because it does not know one. It names the mistake and the number to pass instead,
    which is the half a reader cannot work out for themselves.
    """
    quantity = Quantity(magnitude=2.5, unit="mm")
    with pytest.raises(ValueError, match="not defined") as refusal:
        call(quantity)
    message = str(refusal.value)
    assert operation in message
    # `pass 2.5`, not `2.5` — the quantity renders as "2.5 mm", so asserting the bare
    # number is satisfied by the rendering and passes with the suggestion deleted. That
    # mutation survived the first version of this test.
    assert "pass 2.5" in message, "the refusal must say which number to pass instead"


def test_two_quantities_refuse_with_the_other_reason():
    """Comparing two quantities is not the same mistake, and must not read as it.

    It is a missing conversion, not a wrapped number, and the message says which unit the
    comparison has to be written in.
    """
    with pytest.raises(ValueError, match="between two quantities") as refusal:
        _ = Quantity(magnitude=1.0, unit="mm") < Quantity(magnitude=1.0, unit="m")
    assert "compare the magnitudes" in str(refusal.value)


@pytest.mark.parametrize(
    ("call", "wanted"),
    [
        (abs, "abs()"),
        (int, "int()"),
        (float, "float()"),
    ],
)
def test_the_builtin_conversions_refuse_by_name(call, wanted):
    quantity = Quantity(magnitude=-3.0, unit="mm")
    with pytest.raises(ValueError, match="not defined") as refusal:
        call(quantity)
    assert wanted in str(refusal.value)


def test_equality_still_works_because_it_always_did():
    """The refusals are for operators that did not exist. Equality did, and is untouched:
    turning a working comparison into a refusal would be a regression dressed as a fix."""
    assert Quantity(magnitude=1.0, unit="mm") == Quantity(magnitude=1.0, unit="mm")
    assert Quantity(magnitude=1.0, unit="mm") != Quantity(magnitude=2.0, unit="mm")
    assert Quantity(magnitude=1.0, unit="mm") != 1.0


# --- The unit typo a dimension guard cannot see ---------------------------------------


@pytest.mark.parametrize(
    ("text", "trap"),
    [
        ("80 Mm", "Mm"),
        ("2 Mm**4", "Mm"),
        ("3 Mm/s", "Mm"),
        ("5 ML", "Ml"),
        # Written out in full, pint canonicalises it straight back to the short form, so
        # the escape hatch the first draft of this message offered did not exist.
        ("80 megameter", "Mm"),
    ],
)
def test_a_case_variant_that_keeps_the_dimension_and_changes_the_scale_is_refused(text, trap):
    """`Quantity.parse("80 Mm")` is 80 *megametres*: 1e9 times the millimetres meant.

    This is the one unit typo the library's guards structurally cannot catch. Every other
    mis-casing changes dimension — "80 MM" is megamolar, "3 PA" is petaamperes — and the
    dimension check on every function refuses those by name. `Mm` keeps `[length]`, so it
    passes every guard and screens a beam 80,000 km deep as comfortably passing.
    """
    with pytest.raises(ValueError, match=trap):
        Quantity.parse(text)


@pytest.mark.parametrize("trap", ["Mm", "ML", "Ml"])
def test_the_remedy_the_refusal_names_is_arithmetic_it_can_check(trap):
    """A refusal naming a remedy that does not work is worse than one naming none.

    The first version told the reader to write the unit out in full. `megameter`
    canonicalises to `Mm` and lands on the same check, so the sentence was false.

    And the first version of *this test* executed two conversions with the numbers typed
    into it, which is not the same as checking the message: changing the message to claim
    `1 Mm is 1e9 m` left it passing. The factor is now read back out of the refusal and
    held against the registry, so the sentence is checked rather than accompanied.
    """
    import re as _re

    from anvilate.units import UREG

    with pytest.raises(ValueError) as refusal:
        Quantity(magnitude=1.0, unit=trap)
    # No $ anchor: pydantic appends its documentation URL to a validator's message.
    stated = _re.search(rf"1 {trap} is ([\d.e+]+) (\S+)", str(refusal.value))
    assert stated is not None, f"the refusal no longer names a conversion: {refusal.value}"
    factor, unit = float(stated.group(1)), stated.group(2)
    assert UREG.Quantity(1.0, trap).to(unit).magnitude == pytest.approx(factor, rel=1e-12)


def test_the_ordinary_spellings_are_untouched():
    """The guard is on three tokens, and a false refusal here is worse than the trap."""
    for text in ("80 mm", "5 mL", "3 mmHg", "80 m", "2 mm**4", "1 Mg", "1 MPa", "1 mm/s"):
        assert Quantity.parse(text) is not None, text


def test_no_other_case_collision_hides_in_the_units_this_library_converts_to():
    """The probe that makes `_CASE_TRAPS` a derived set rather than a remembered one.

    Every unit the package converts to, against its own case variants: a variant pint
    accepts, at the *same dimension*, with a different scale is exactly the trap. Any one
    the guard does not already refuse fails here — including one pint grows later.
    """
    import re as _re
    from pathlib import Path

    from anvilate.units import UREG

    units = set()
    for path in (Path(__file__).resolve().parent.parent / "src" / "anvilate").rglob("*.py"):
        units |= set(_re.findall(r'\.to\("([^"]{1,24})"\)', path.read_text(encoding="utf-8")))
    assert len(units) > 100, (
        f"only {len(units)} conversion targets found; the scan stopped matching the way "
        "this library converts, and a probe over nothing reports green"
    )

    unguarded = []
    for unit in sorted(units):
        try:
            base = UREG.Unit(unit)
        except Exception:  # pragma: no cover - every literal in the tree parses today
            continue
        for variant in {unit.upper(), unit.lower(), unit.capitalize(), unit.swapcase()} - {unit}:
            try:
                parsed = UREG.Unit(variant)
                if parsed.dimensionality != base.dimensionality:
                    continue
                ratio = UREG.Quantity(1.0, parsed).to(base).magnitude
            except Exception:
                continue
            if abs(ratio - 1.0) <= 1e-12:
                continue
            try:
                Quantity(magnitude=1.0, unit=variant)
            except ValueError:
                continue  # refused, which is the point
            unguarded.append(f"{variant!r} is {ratio:g}x {unit!r} at the same dimension")
    assert not unguarded, (
        "case variants that keep the dimension and change the scale, and are accepted:\n  "
        + "\n  ".join(sorted(set(unguarded)))
    )


def test_every_unit_this_library_writes_can_be_read_back():
    """The round trip, over the unit spellings the package itself emits.

    A value this library renders and cannot re-read is a value a user cannot put in a
    spec, quote in a document, or hand back to `anvilate check` — and two whole families
    were in that state. Offset temperatures: pint refuses `"400 degC"` from text because
    multiplying by an offset unit is ambiguous, while the library converts to it happily.
    Angles: `rad` and `degree` are dimensionless in pint, so the bare-number guard took
    them for bare numbers.

    The scan derives its corpus from the tree rather than listing units here, so a unit
    the library starts writing tomorrow is covered without anyone remembering to add it.
    """
    import re as _re
    from pathlib import Path

    from anvilate.units import Quantity

    root = Path(__file__).resolve().parent.parent / "src" / "anvilate"
    units: set[str] = set()
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        units |= set(_re.findall(r'\.to\("([^"]{1,24})"\)', text))
        units |= set(_re.findall(r'unit="([^"]{1,24})"', text))
    assert len(units) > 150, (
        f"only {len(units)} unit spellings found; the scan stopped matching the way this "
        "library writes units, and a probe over nothing reports green"
    )

    unreadable = []
    for unit in sorted(units):
        try:
            written = Quantity(magnitude=1.5, unit=unit)
        except ValueError:
            continue  # a spelling the guard refuses on construction is not written either
        rendered = str(written)
        try:
            read_back = Quantity.parse(rendered)
        except Exception as error:  # noqa: BLE001 - the failure is the finding
            unreadable.append(f"{rendered!r}: {type(error).__name__}: {error}")
            continue
        # Equality of *value*, not of spelling: the parser normalises `1/H` to `1 / H`,
        # and a rendering that comes back as the same quantity has been read back. What
        # would not be is a different magnitude, a different unit, or a second render that
        # no longer re-reads — so idempotence is checked too.
        if read_back.magnitude != written.magnitude or read_back.pint.units != written.pint.units:
            unreadable.append(f"{rendered!r} read back as {str(read_back)!r}")
            continue
        again = Quantity.parse(str(read_back))
        if str(again) != str(read_back):
            unreadable.append(f"{rendered!r} does not settle: {str(read_back)!r} -> {str(again)!r}")
    assert not unreadable, "rendered quantities this library cannot re-read:\n  " + "\n  ".join(
        unreadable
    )


def test_the_front_door_takes_the_offset_temperatures_and_angles_it_writes():
    """The two families above, named — so the census cannot go quiet by finding nothing.

    A derived scan that stops matching reports green; these are the cases that were
    actually broken, held by hand beside it.
    """
    from anvilate.units import Quantity

    for text, unit in (("400 degC", "°C"), ("400 °C", "°C"), ("-20 °F", "°F")):
        parsed = Quantity.parse(text)
        assert parsed.unit == unit and parsed.magnitude == float(text.split()[0])
        assert parsed.has_dimension("[temperature]")
    # A bare C is the coulomb and stays the coulomb: the degree sign is what disambiguates.
    assert Quantity.parse("20 C").has_dimension("[current] * [time]")

    for text in ("30 degree", "0.5 rad", "12 arcminute"):
        assert Quantity.parse(text).magnitude == float(text.split()[0])
    assert Quantity.parse("30 degree").to("rad").magnitude == pytest.approx(0.5235987755982988)

    # And the guard the angle exception has to leave standing: a ratio states no unit.
    for ratio in ("12 %", "3 dimensionless", "75"):
        with pytest.raises(MissingUnitError):
            Quantity.parse(ratio)
    # As does the refusal that keeps a range from multiplying itself out.
    with pytest.raises(UnitError):
        Quantity.parse("45-50 kN")


def test_every_angle_unit_pint_defines_is_one_the_rotation_guards_see():
    """The corpus is pint's registry, not a list somebody typed.

    The guards used to match eight substrings against the rendered unit text, and a list of
    names is satisfied by being on the list. It missed the **angular mil**:
    ``str(UREG.Unit("mil/s"))`` is ``"mil / second"``, which contains none of the eight, so a
    slew rate in mil/s was refused as a bare inverse time by one guard and *accepted as a
    plain event count* by the other — 9.8e-5 per second for a rate that names an angle, which
    is the silent half of the pair.

    Adding ``"mil"`` to the substrings would have been worse than the gap, because ``"mil"``
    is a substring of ``"milli"`` and ``millimole / second`` would have started reading as an
    angle. So the classification is pint's own definition chain, and this holds it against
    every dimensionless unit the registry defines rather than against a fixture.
    """
    from anvilate.units.registry import UREG
    from anvilate.units.rotation import (
        AmbiguousCountRateError,
        AmbiguousRotationalSpeedError,
        angular_speed_rad_per_s,
        count_rate_per_second,
    )

    dimensionless = []
    for name in dir(UREG):
        try:
            unit = UREG.Unit(name)
        except Exception:  # noqa: BLE001 - `dir` yields plenty that is not a unit
            continue
        if unit.dimensionality == {}:
            dimensionless.append((name, unit))
    assert len(dimensionless) > 50, f"only {len(dimensionless)} dimensionless units were found"

    angles, scalars = [], []
    for name, _unit in dimensionless:
        try:
            rate = Quantity(magnitude=1.0, unit=f"{name}/second")
        except Exception:  # noqa: BLE001 - a few registry names do not compose
            continue
        try:
            angular_speed_rad_per_s(rate, name="probe")
            names_angle = True
        except AmbiguousRotationalSpeedError:
            names_angle = False
        # The two guards are mirror images and must never both accept, or both refuse, the
        # same unit: every rate is either turns or events, and one of them has to own it.
        try:
            count_rate_per_second(rate, name="probe")
            counts_events = True
        except AmbiguousCountRateError:
            counts_events = False
        except Exception:  # noqa: BLE001 - logarithmic units refuse the conversion itself
            continue
        assert names_angle != counts_events, (
            f"{name}/second is {'accepted' if names_angle else 'refused'} by both guards; "
            "a rate is either turns or events and exactly one of them owns it"
        )
        (angles if names_angle else scalars).append(name)

    # The classification itself, spot-checked in both directions against units whose nature
    # is not in question — the point being that `mil` is on the angle side and `percent`,
    # `decibel` and `tansec` are not, which the substring list got wrong for the first.
    for angle in ("radian", "degree", "turn", "revolution", "grade", "arcminute", "mil"):
        assert angle in angles, f"{angle} is an angle and the guards do not see one"
    for scalar in ("percent", "ppm", "permille", "byte"):
        assert scalar in scalars, f"{scalar} is not an angle and the guards think it is"
    assert len(angles) > 8, f"only {len(angles)} angle units were classified: {angles}"


def test_the_angular_mil_is_a_rotation_and_not_a_count():
    """The unit the substring list missed, in both directions.

    Pint defines `mil` as a multiple of the radian, and that -- not its numeric value, and
    not how it is spelled -- is what decides which of the two guards owns it. The conversion
    is read from pint rather than restated here, because restating it would make this test
    agree with whatever pint currently says.
    """
    from anvilate.units.rotation import (
        AmbiguousCountRateError,
        angular_speed_rad_per_s,
        count_rate_per_second,
    )

    slew = Quantity(magnitude=1000.0, unit="mil/s")
    omega = angular_speed_rad_per_s(slew, name="slew_rate")
    assert omega == pytest.approx(Quantity(magnitude=1000.0, unit="mil").to("rad").magnitude)
    assert omega > 0
    with pytest.raises(AmbiguousCountRateError, match="names an"):
        count_rate_per_second(slew, name="cycles")
    # And the near-miss the substring fix would have created: a millimole rate is not an
    # angle, and "mil" is a substring of "milli".
    assert count_rate_per_second(Quantity(magnitude=5.0, unit="mmol/s/mol"), name="rate") > 0
