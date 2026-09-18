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


_BOLTED_DOCUMENT = """
anvilate_spec: "1.13.0"
name: rail
description: A steel bracket bolted to a rail.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
element_type: bolted_connection
element_params:
  name: rail
  bolt_diameter: {magnitude: 12.0, unit: mm}
  plate_thickness: {magnitude: 10.0, unit: mm}
  load: {magnitude: 8.0, unit: kN}
  bolt_material: AISI-1045-CD
  plate_material: ASTM-A36
"""


def _factor_profile(*supplies: SuppliedValue) -> ProfileBinding:
    return _profile(
        id="SHOP-STRUCT",
        version="1.0.0",
        citation="the shop's structural practice, rev C",
        supplies=supplies
        or (SuppliedValue(declaration="constraints.min_safety_factor", value=2.0),),
    ).bind({"ambient temperature": _q(300.0)})


def _document(extra: str = ""):  # type: ignore[no-untyped-def]
    from anvilate.spec import load_spec_yaml

    return load_spec_yaml(_BOLTED_DOCUMENT + extra)


def test_an_applied_profile_value_is_recorded_as_the_profiles_and_not_the_engineers() -> None:
    from anvilate.spec.provenance import Origin

    applied = _factor_profile().apply(_document())
    stated = applied.constraints.min_safety_factor
    assert stated is not None and stated.value == 2.0
    assert stated.origin is Origin.PROFILE_SUPPLIED
    assert "SHOP-STRUCT 1.0.0" in (stated.rationale or "")
    # It is a document like any other: it survives being written down and read back.
    from anvilate.spec import load_spec_yaml
    from anvilate.spec.validate import dump_spec_yaml

    assert load_spec_yaml(dump_spec_yaml(applied)) == applied


def test_a_verdict_judged_against_a_profile_value_says_so_on_the_rendered_report() -> None:
    """Task 4.3: in the rendered report a reviewer reads, not only in the metadata."""
    from anvilate.report.document import CalculationReport, ReportSection
    from anvilate.screening import screen_spec
    from anvilate.spec.provenance import Origin, Provenanced
    from anvilate.units import UnitSystem

    applied = _factor_profile().apply(_document())
    card = screen_spec(applied)
    judged = [entry for entry in card.entries if entry.required_safety_factor is not None]
    assert judged and card.status.value == "pass"
    for entry in judged:
        assert "the required minimum was supplied by profile SHOP-STRUCT 1.0.0" in entry.detail
    unjudged = [entry for entry in card.entries if entry.required_safety_factor is None]
    assert unjudged and not any("SHOP-STRUCT" in entry.detail for entry in unjudged)
    stated = applied.constraints.min_safety_factor
    assert stated is not None
    report = CalculationReport(
        title="rail",
        project="rail",
        date="2026-09-18",
        unit_system=UnitSystem.SI,
        assumptions=(
            Provenanced(
                value=f"minimum safety factor {stated.value}",
                origin=Origin.PROFILE_SUPPLIED,
                rationale=stated.rationale,
            ),
        ),
        sections=tuple(ReportSection(entry=entry) for entry in card.entries),
    )
    text = report.to_text()
    assert text.count("supplied by profile SHOP-STRUCT 1.0.0") >= len(judged)
    assert "[supplied by a profile: profile SHOP-STRUCT 1.0.0" in text


def test_the_upper_band_a_profile_supplies_is_attributed_too() -> None:
    from anvilate.screening import screen_spec

    binding = _factor_profile(
        SuppliedValue(declaration="constraints.min_safety_factor", value=2.0),
        SuppliedValue(declaration="constraints.max_safety_factor", value=6.0),
    )
    card = screen_spec(binding.apply(_document()))
    banded = [entry for entry in card.entries if entry.upper_safety_factor is not None]
    assert banded
    for entry in banded:
        assert "the upper band was supplied by profile SHOP-STRUCT" in entry.detail


def test_an_override_is_applied_as_the_engineers_own_and_names_what_it_replaced() -> None:
    from anvilate.screening import screen_spec
    from anvilate.spec.provenance import Origin

    binding = _factor_profile().override("constraints.min_safety_factor", 2.5)
    applied = binding.apply(_document())
    stated = applied.constraints.min_safety_factor
    assert stated is not None and stated.value == 2.5
    assert stated.origin is Origin.USER_STATED
    assert "which supplied 2.0" in (stated.rationale or "")
    assert not any("SHOP-STRUCT" in entry.detail for entry in screen_spec(applied).entries)


@pytest.mark.parametrize(
    ("declaration", "extra", "match"),
    [
        ("manufacturing.process", "", "cannot record where its value came from"),
        ("constraints.nothing", "", "has no field 'nothing'"),
        ("name.first", "", "is not a section of the document"),
        (
            "constraints.min_safety_factor",
            "constraints: {min_safety_factor: {value: 3.0, origin: user_stated}}\n",
            "already states 'constraints.min_safety_factor' as 3.0",
        ),
    ],
)
def test_a_profile_value_with_nowhere_honest_to_go_is_refused(
    declaration: str, extra: str, match: str
) -> None:
    binding = _factor_profile(SuppliedValue(declaration=declaration, value=2.0))
    with pytest.raises(ValueError, match=match):
        binding.apply(_document(extra))


def test_a_profile_supplied_origin_must_name_its_profile() -> None:
    from anvilate.spec.provenance import Origin, Provenanced

    with pytest.raises(ValidationError, match="must name the profile"):
        Provenanced[float](value=2.0, origin=Origin.PROFILE_SUPPLIED)


def test_an_element_entry_not_judged_against_the_bound_does_not_credit_the_profile() -> None:
    """An element that could not be screened was judged against nothing the profile gave."""
    from anvilate.screening import screen_spec

    broken = _BOLTED_DOCUMENT.replace("  load: {magnitude: 8.0, unit: kN}\n", "")
    from anvilate.spec import load_spec_yaml

    card = screen_spec(_factor_profile().apply(load_spec_yaml(broken)))
    (tier,) = [entry for entry in card.entries if entry.name == "T1 analytical"]
    assert tier.required_safety_factor is None
    assert "SHOP-STRUCT" not in tier.detail


def test_the_evidence_bundle_carries_the_profile_behind_the_verdict() -> None:
    """Task 2.3: in the exported bundle, both in the checks and in the spec it reproduces."""
    from anvilate.bundle import BundleSections
    from anvilate.screening import screen_spec

    applied = _factor_profile().apply(_document())
    document = BundleSections(scorecard=screen_spec(applied), spec=applied).render_document()
    assert "the required minimum was supplied by profile SHOP-STRUCT 1.0.0" in document
    assert "origin: profile_supplied" in document
    assert "rationale: profile SHOP-STRUCT 1.0.0" in document
