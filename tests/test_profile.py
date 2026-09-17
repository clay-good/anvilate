"""Profiles: many declarations in one action, each attributed and individually overridable."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.profile import (
    Applicability,
    OutsideApplicability,
    Profile,
    ProfileBinding,
    SuppliedValue,
)
from anvilate.units import Quantity


def _q(magnitude: float, unit: str = "K") -> Quantity:
    return Quantity(magnitude=magnitude, unit=unit)


def _profile(**fields: object) -> Profile:
    declared: dict[str, object] = {
        "id": "ENV-COASTAL",
        "version": "v2.1",
        "citation": "ISO 12944-2 C5-M, company practice EP-3",
        "applicability": (
            Applicability(context="ambient temperature", minimum=_q(253.15), maximum=_q(323.15)),
        ),
        "supplies": (
            SuppliedValue(declaration="environment.corrosivity", value="C5-M"),
            SuppliedValue(declaration="manufacturing.min_wall", value=_q(6.0, "mm")),
            SuppliedValue(declaration="environment.design_life_years", value=25.0),
        ),
    }
    declared.update(fields)
    return Profile(**declared)  # type: ignore[arg-type]


def _bound() -> ProfileBinding:
    return _profile().bind({"ambient temperature": _q(300.0)})


def test_one_binding_supplies_every_declaration_with_the_profiles_identity() -> None:
    binding = _bound()
    assert binding.declarations() == {
        "environment.corrosivity": "C5-M",
        "manufacturing.min_wall": _q(6.0, "mm"),
        "environment.design_life_years": 25.0,
    }
    for source in binding.attribution().values():
        assert source == "profile ENV-COASTAL v2.1 (ISO 12944-2 C5-M, company practice EP-3)"
    assert binding.overrides() == ()
    # The id, version and citation appear wherever the binding renders.
    rendered = str(binding)
    assert "ENV-COASTAL v2.1" in rendered and "ISO 12944-2 C5-M" in rendered


def test_an_override_is_recorded_as_the_users_own_and_keeps_what_the_profile_said() -> None:
    binding = _bound().override("manufacturing.min_wall", _q(8.0, "mm"))
    assert binding.declarations()["manufacturing.min_wall"] == _q(8.0, "mm")
    assert binding.attribution()["manufacturing.min_wall"] == (
        "user override of profile ENV-COASTAL v2.1"
    )
    # The other declarations are untouched, and still the profile's.
    assert "profile ENV-COASTAL" in binding.attribution()["environment.corrosivity"]
    # What the profile said survives beside the override, so the report can say both.
    (overridden,) = binding.overrides()
    assert overridden.value == _q(6.0, "mm") and overridden.overridden == _q(8.0, "mm")
    assert "manufacturing.min_wall = 8 mm (profile said 6 mm)" in str(binding)


def test_overriding_a_declaration_the_profile_never_supplied_is_refused() -> None:
    with pytest.raises(ValueError, match="not 'manufacturing.process'"):
        _bound().override("manufacturing.process", "cnc_milling")


@pytest.mark.parametrize(
    ("context", "match"),
    [
        ({"ambient temperature": _q(400.0)}, "is 400 K, and this profile applies for"),
        ({"ambient temperature": _q(200.0)}, "is 200 K, and this profile applies for"),
        ({}, "the context states no ambient temperature"),
        ({"ambient temperature": _q(300.0, "mm")}, "is 300 mm, and this profile applies for"),
    ],
)
def test_a_binding_outside_the_profiles_own_basis_is_refused(context: dict, match: str) -> None:
    with pytest.raises(OutsideApplicability, match=match):
        _profile().bind(context)


def test_the_bounds_of_the_range_are_inside_it() -> None:
    for edge in (253.15, 323.15):
        assert _profile().bind({"ambient temperature": _q(edge)}).declarations()


def test_a_one_sided_bound_holds_its_one_end() -> None:
    at_least = _profile(
        applicability=(Applicability(context="plate thickness", minimum=_q(6.0, "mm")),)
    )
    assert at_least.bind({"plate thickness": _q(10.0, "mm")}).declarations()
    with pytest.raises(OutsideApplicability, match="at least 6 mm"):
        at_least.bind({"plate thickness": _q(4.0, "mm")})

    at_most = _profile(
        applicability=(Applicability(context="plate thickness", maximum=_q(6.0, "mm")),)
    )
    assert at_most.bind({"plate thickness": _q(4.0, "mm")}).declarations()
    with pytest.raises(OutsideApplicability, match="at most 6 mm"):
        at_most.bind({"plate thickness": _q(10.0, "mm")})


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"minimum": None, "maximum": None}, "neither a minimum nor a maximum"),
        ({"minimum": _q(10.0), "maximum": _q(1.0)}, "maximum .* below its minimum"),
        ({"minimum": _q(10.0), "maximum": _q(1.0, "mm")}, "a range has one dimension"),
    ],
)
def test_a_bound_that_is_not_a_range_is_refused(fields: dict, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        Applicability(context="ambient temperature", **fields)


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"applicability": ()}, "at least 1 item"),
        ({"supplies": ()}, "at least 1 item"),
        ({"citation": "  "}, "must state"),
        ({"version": ""}, "must state"),
        (
            {
                "supplies": (
                    SuppliedValue(declaration="a", value=1.0),
                    SuppliedValue(declaration="a", value=2.0),
                )
            },
            "supplies one declaration twice",
        ),
        (
            {
                "applicability": (
                    Applicability(context="ambient temperature", minimum=_q(1.0)),
                    Applicability(context="ambient temperature", maximum=_q(9.0)),
                )
            },
            "bounds one context twice",
        ),
        (
            {"supplies": (SuppliedValue(declaration="a", value=1.0, overridden=2.0),)},
            "carries an override in its own record",
        ),
    ],
)
def test_a_malformed_profile_is_refused(fields: dict, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _profile(**fields)


def test_a_binding_round_trips_through_its_own_serialization() -> None:
    binding = _bound().override("environment.corrosivity", "C4")
    assert ProfileBinding.model_validate_json(binding.model_dump_json()) == binding


def test_a_profile_supplies_what_the_needs_report_asks_for() -> None:
    # The two halves meet: a need names a declaration, and a profile supplies declarations
    # by that same name, so binding one answers items the report listed.
    from anvilate.needs import needs_report
    from anvilate.scorecard import CheckStatus, Need, Scorecard, ScorecardEntry, ValueSource

    blocked = ScorecardEntry(
        name="corrosion allowance",
        status=CheckStatus.NOT_EVALUATED,
        detail="the spec states no corrosivity category",
        needs=(
            Need(
                declaration="environment.corrosivity",
                takes="the ISO 12944-2 corrosivity category the part lives in",
                sources=(ValueSource.STANDARD, ValueSource.USER),
            ),
        ),
    )
    report = needs_report(Scorecard(entries=(blocked,)))
    asked = {item.need.declaration for item in report.items}
    supplied = set(_bound().declarations())
    assert asked <= supplied
