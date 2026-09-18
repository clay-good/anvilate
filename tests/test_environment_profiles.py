"""The five environment profiles: cited, bounded, environment-only, and marked where used."""

from __future__ import annotations

import pytest

from anvilate.analysis.optomechanics import (
    dynamic_clearance_scorecard,
    glass_contact_stress_scorecard,
    seal_gland_extremes_scorecard,
)
from anvilate.environment_profiles import (
    AIRBORNE,
    BENCHTOP,
    ENVIRONMENT_DECLARATIONS,
    ENVIRONMENT_PROFILES,
    HANDHELD,
    SEALED_AND_PURGED,
    VEHICLE_MOUNTED,
)
from anvilate.profile import OutsideApplicability
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity

q = Quantity.parse


def test_the_five_operating_classes_the_spec_names_each_ship_cited() -> None:
    assert [profile.id for profile in ENVIRONMENT_PROFILES] == [
        "benchtop",
        "handheld",
        "vehicle_mounted",
        "airborne",
        "sealed_and_purged",
    ]
    for profile in ENVIRONMENT_PROFILES:
        assert profile.citation.strip() and profile.applicability


def test_a_profile_supplies_the_environment_and_never_the_design() -> None:
    """The declarations are the screens' environment parameters, and only those."""
    for profile in ENVIRONMENT_PROFILES:
        supplied = {value.declaration for value in profile.supplies}
        assert supplied <= ENVIRONMENT_DECLARATIONS, (profile.id, supplied)
    assert not {"allowable_tensile_stress", "mount_stiffness", "radial_stiffness"} & (
        ENVIRONMENT_DECLARATIONS
    )


def _value(profile, declaration: str):  # type: ignore[no-untyped-def]
    (supplied,) = [v for v in profile.supplies if v.declaration == declaration]
    return supplied.value


def test_the_values_are_the_tables_they_cite() -> None:
    # MIL-STD-810H Table 516.8-IV: 40 G ground, 20 G flight and truck-mounted, all 11 ms.
    assert _value(HANDHELD, "peak_acceleration") == 40.0
    assert _value(VEHICLE_MOUNTED, "peak_acceleration") == 20.0
    assert _value(AIRBORNE, "peak_acceleration") == 20.0
    for profile in (HANDHELD, VEHICLE_MOUNTED, AIRBORNE):
        assert _value(profile, "pulse_duration").to("ms").magnitude == 11
    # Tables 501.7-I and 502.7-I: basic hot 43 °C ambient, 63 °C induced; basic cold
    # -32 °C ambient, -33 °C induced.
    assert _value(HANDHELD, "hot").to("degC").magnitude == pytest.approx(43)
    assert _value(VEHICLE_MOUNTED, "hot").to("degC").magnitude == pytest.approx(63)
    assert _value(HANDHELD, "cold").to("degC").magnitude == pytest.approx(-32)
    assert _value(VEHICLE_MOUNTED, "cold").to("degC").magnitude == pytest.approx(-33)
    # Method 500.6 paragraph 2.3.1: 57.2 kPa at the 4,572 m cargo cabin altitude.
    assert _value(AIRBORNE, "ambient_pressure").to("kPa").magnitude == pytest.approx(57.2)
    assert _value(BENCHTOP, "fill_pressure").to("kPa").magnitude == pytest.approx(101.325)
    assert _value(SEALED_AND_PURGED, "mitigation") == "purge"


def test_one_binding_reaches_a_real_verdict_with_every_profile_value_marked() -> None:
    binding = HANDHELD.bind({"item mass": q("2 kg")})
    declared = binding.declarations()
    clearance = dynamic_clearance_scorecard(
        "cell gap",
        natural_frequency=q("600 Hz"),
        peak_acceleration=declared["peak_acceleration"],
        pulse_duration=declared["pulse_duration"],
        gap=q("25 µm"),
    )
    marked = binding.mark(clearance, "peak_acceleration", "pulse_duration")
    assert marked.status is clearance.status
    assert "peak_acceleration 40.0 from profile handheld 1 (MIL-STD-810H" in marked.detail
    assert marked.detail.count("a class default to confirm") == 2
    gland = binding.mark(
        seal_gland_extremes_scorecard(
            "housing O-ring",
            cross_section_diameter=q("1.78 mm"),
            inner_diameter=q("40 mm"),
            gland_depth=q("1.4 mm"),
            groove_width=q("2.4 mm"),
            groove_diameter=q("40 mm"),
            elastomer_cte=q("2.3e-4 1/K"),
            gland_cte=q("23.6e-6 1/K"),
            assembly_temperature=q("20 degC"),
            cold=declared["cold"],
            hot=declared["hot"],
        ),
        "cold",
        "hot",
    )
    assert gland.status in (CheckStatus.PASS, CheckStatus.FAIL)
    assert "cold -32 °C from profile handheld 1" in gland.detail


def test_an_override_is_marked_as_the_users_own() -> None:
    binding = HANDHELD.bind({"item mass": q("2 kg")}).override("hot", q("55 degC"))
    entry = dynamic_clearance_scorecard(
        "cell gap",
        natural_frequency=q("600 Hz"),
        peak_acceleration=40.0,
        pulse_duration=q("11 ms"),
        gap=q("25 µm"),
    )
    marked = binding.mark(entry, "hot")
    assert "hot 55 °C is the user's, overriding profile handheld's 43 °C" in marked.detail
    with pytest.raises(ValueError, match="and not"):
        binding.mark(entry, "allowable_tensile_stress")


def test_a_bound_profile_does_not_answer_a_design_property() -> None:
    """The glass allowable belongs to the design; no profile supplies it."""
    HANDHELD.bind({"item mass": q("2 kg")})
    entry = glass_contact_stress_scorecard(
        "retainer contact",
        preload=q("20 N"),
        contact_diameter=q("30 mm"),
        glass_radius=q("50 mm"),
        mount_radius=q("3 mm"),
        glass_modulus=q("82 GPa"),
        glass_poisson=0.206,
        mount_modulus=q("69 GPa"),
        mount_poisson=0.33,
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "no declared allowable_tensile_stress" in entry.detail
    assert "no environment profile supplies" in entry.detail


def test_a_profile_outside_its_own_basis_is_refused() -> None:
    with pytest.raises(OutsideApplicability, match="item mass is 60 kg"):
        HANDHELD.bind({"item mass": q("60 kg")})
    with pytest.raises(OutsideApplicability, match="states no operating altitude"):
        SEALED_AND_PURGED.bind({})
