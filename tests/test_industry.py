"""Industry profiles: cited rules, required checks that always appear, layering, no claims.

The spec's scenarios: a profile rule with neither source nor practice label is refused; a
box with no vibration input shows random vibration as not evaluated, naming the PSD; a
company relaxing a factor reports the relaxation and its source; the general profile
changes nothing; every rendering says a profile is not a certification.
"""

from __future__ import annotations

import pytest

from anvilate.industry import (
    GENERAL,
    SCREENING_NOT_CERTIFICATION,
    FactorRule,
    IndustryProfile,
    ProfileRule,
    RequiredArtifact,
    RequiredCheck,
    apply_profile,
    layer,
    load_profile,
    resolve,
)
from anvilate.refusal import RefusalError
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

_DO160 = "RTCA DO-160G §8 vibration, category S curve"

VIBRATION = RequiredCheck(
    id="TA-VIB-1", source=_DO160, item_class="avionics box", check="random vibration",
    satisfied_by=("random vibration",), needs=("input PSD (g²/Hz against Hz)", "duration"),
    analysis="anvilate.analysis.random_vibration.miles_response_grms",
)  # fmt: skip

AIRCRAFT = IndustryProfile(
    urn="urn:example:profile:transport-aircraft", name="Transport aircraft", version="0.1.0",
    item_classes=("avionics box", "primary structure"),
    factors=(FactorRule(id="TA-F-1", name="ultimate", value=1.5,
                        source="14 CFR 25.303 factor of safety"),),
    required_checks=(VIBRATION,),
    required_artifacts=(RequiredArtifact(id="TA-A-1", artifact="margin_table",
                                         practice_default=True),),
)  # fmt: skip


def _card(*names: str) -> Scorecard:
    return Scorecard(
        entries=tuple(
            ScorecardEntry.from_safety_factor(n, computed=2.0, required=1.0) for n in names
        )
    )


def test_a_rule_with_neither_source_nor_practice_label_is_refused():
    text = """
urn: urn:example:profile:loaded
name: Loaded
version: "1"
item_classes: [avionics box]
required_checks:
  - id: TA-VIB-9
    item_class: avionics box
    check: shock
    satisfied_by: [shock]
"""
    with pytest.raises(RefusalError, match="rule 'TA-VIB-9' has neither a source"):
        load_profile(text)
    labeled = load_profile(text.replace("check: shock", "check: shock\n    practice_default: true"))
    assert labeled.required_checks[0].basis == "practice-based default, no source"
    with pytest.raises(RefusalError, match="one mapping"):
        load_profile("- a list")


def test_a_box_with_no_vibration_input_shows_it_not_evaluated_naming_the_psd():
    profiled = apply_profile(_card("box wall bending"), resolve(AIRCRAFT),
                             item_class="avionics box")  # fmt: skip
    entry = profiled.card.entries[-1]
    assert (entry.name, entry.status) == ("random vibration", CheckStatus.NOT_EVALUATED)
    assert "input PSD" in entry.detail and "avionics box" in entry.detail
    assert entry.reference.startswith("required by Transport aircraft 0.1.0")
    assert "TA-VIB-1" in entry.reference and _DO160 in entry.reference
    assert profiled.added == ("random vibration",) and profiled.not_available == ()
    assert SCREENING_NOT_CERTIFICATION in str(profiled)


def test_a_required_check_the_card_already_holds_is_left_as_it_is():
    card = _card("box random vibration")
    profiled = apply_profile(card, resolve(AIRCRAFT), item_class="avionics box")
    assert profiled.card == card and profiled.added == ()


def test_a_check_this_installation_cannot_run_is_not_available_never_dropped():
    absent = VIBRATION.model_copy(
        update={"pack": "anvilate_aerospace_pack", "install": "pip install anvilate-aerospace"}
    )
    profile = AIRCRAFT.model_copy(update={"required_checks": (absent,)})
    profiled = apply_profile(_card(), resolve(profile), item_class="avionics box")
    (entry,) = profiled.card.entries
    assert entry.status is CheckStatus.NOT_EVALUATED and entry.detail.startswith("not available")
    assert (
        "anvilate_aerospace_pack" in entry.detail
        and "pip install anvilate-aerospace" in entry.detail
    )
    assert profiled.not_available == ("random vibration",)
    missing_function = VIBRATION.model_copy(
        update={"analysis": "anvilate.analysis.random_vibration.no_such_function"}
    )
    profile = AIRCRAFT.model_copy(update={"required_checks": (missing_function,)})
    assert apply_profile(_card(), resolve(profile), item_class="avionics box").not_available


def test_a_company_relaxing_a_factor_reports_both_values_and_its_source():
    company = IndustryProfile(
        urn="urn:example:profile:acme-aero", name="ACME aero", version="2.0",
        extends=AIRCRAFT.urn,
        factors=(FactorRule(id="ACME-F-1", name="ultimate", value=1.4,
                            source="ACME engineering standard ES-12 §4, test-verified"),),
        required_checks=(RequiredCheck(id="ACME-C-1", source="ACME ES-12 §7",
                                       item_class="avionics box", check="connector retention",
                                       satisfied_by=("connector retention",)),),
    )  # fmt: skip
    resolved = layer(AIRCRAFT, company)
    (relaxed,) = resolved.relaxations
    assert (relaxed.parent_value, relaxed.value) == (1.5, 1.4)
    assert relaxed.source.startswith("ACME engineering standard")
    assert "14 CFR 25.303" in relaxed.parent_basis
    assert any(line.startswith("RELAXED ultimate") for line in resolved.changes())
    profiled = apply_profile(_card(), resolved, item_class="avionics box")
    assert profiled.added == ("random vibration", "connector retention")  # inherited, then added


def test_a_raised_factor_is_not_a_relaxation():
    stricter = IndustryProfile(urn="urn:example:profile:strict", name="Strict", version="1",
                               extends=AIRCRAFT.urn,
                               factors=(FactorRule(id="S-1", name="ultimate", value=2.0,
                                                   source="program plan §3"),))  # fmt: skip
    assert layer(AIRCRAFT, stricter).relaxations == ()


def test_a_layer_must_name_its_parent():
    orphan = IndustryProfile(urn="urn:example:profile:x", name="X", version="1",
                             extends="urn:example:profile:other")  # fmt: skip
    with pytest.raises(RefusalError, match="extends"):
        layer(AIRCRAFT, orphan)
    with pytest.raises(RefusalError, match="layer"):
        resolve(orphan)


def test_the_general_profile_changes_nothing():
    card = _card("plate bending", "bolt bearing")
    profiled = apply_profile(card, resolve(GENERAL))
    assert profiled.card == card and profiled.added == ()
    assert resolve(GENERAL).changes() == ()


def test_what_the_profile_changed_names_each_rule():
    changes = resolve(AIRCRAFT).changes()
    assert "factor ultimate = 1.5: TA-F-1 [14 CFR 25.303 factor of safety]" in changes
    assert any("random vibration: TA-VIB-1" in line for line in changes)
    assert "required artifact: margin_table: TA-A-1 [practice-based default, no source]" in changes
    assert resolve(AIRCRAFT).header().endswith(SCREENING_NOT_CERTIFICATION)


@pytest.mark.parametrize(("update", "said"), [
    ({"item_classes": ()}, "does not declare"),
    ({"factors": (FactorRule(id="a", name="u", value=1.2, practice_default=True),
                  FactorRule(id="b", name="u", value=1.3, practice_default=True))}, "twice"),
    ({"required_artifacts": (RequiredArtifact(id="TA-F-1", artifact="dfmea",
                                              practice_default=True),)}, "rules"),
])  # fmt: skip
def test_an_incoherent_profile_is_refused(update, said):
    with pytest.raises(ValueError, match=said):
        IndustryProfile(**{**AIRCRAFT.model_dump(), **update})


def test_an_item_class_the_profile_does_not_declare_is_refused():
    with pytest.raises(RefusalError, match="patient-contacting"):
        apply_profile(_card(), resolve(AIRCRAFT), item_class="patient-contacting")


def test_a_profile_round_trips_as_json_data():
    again = IndustryProfile.model_validate_json(AIRCRAFT.model_dump_json())
    assert again == AIRCRAFT
    assert ProfileRule(id="x", practice_default=True).basis == "practice-based default, no source"


def test_the_docs_pages_profile_and_relaxation_are_what_the_library_computes():
    """docs/industry-profiles.md argues from its example: the YAML loads as written, its
    required check reaches a card that never ran it, and the relaxation line it prints is
    the one `layer` produces for the factors it names."""
    import re
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "industry-profiles.md").read_text()
    block = re.search(r"```yaml\n(.*?)```", page, re.S).group(1)
    profile = load_profile(block)
    profiled = apply_profile(_card(), resolve(profile), item_class="avionics box")
    assert profiled.added == ("random vibration",) and profiled.not_available == ()
    lower = FactorRule(id="ACME-F-1", name="ultimate", value=1.4,
                       source="ACME ES-12 §4, test-verified")  # fmt: skip
    company = IndustryProfile(urn="urn:acme:profile:acme-aero", name="ACME", version="1",
                              extends=profile.urn, factors=(lower,))  # fmt: skip
    (relaxed,) = layer(profile, company).relaxations
    assert str(relaxed) in page


def test_the_general_profile_leaves_every_examples_card_as_it_was():
    """Industry profiles 2.1: binding the general profile changes no shipped example's card."""
    from pathlib import Path

    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    examples = sorted((Path(__file__).parents[1] / "examples").rglob("*.spec.yaml"))
    assert len(examples) >= 30
    general = resolve(GENERAL)
    for path in examples:
        card = screen_spec(load_spec_yaml(path.read_text(encoding="utf-8")))
        profiled = apply_profile(card, general)
        assert profiled.card == card and profiled.added == (), path.name


def test_binding_the_spaceflight_profile_requires_vibration_and_outgassing_for_a_flight_box():
    from anvilate.industry import industry_profile

    profiled = apply_profile(_card("box wall bending"), resolve(industry_profile("spaceflight")),
                             item_class="flight box")  # fmt: skip
    assert profiled.added == ("random vibration", "outgassing")
    assert profiled.not_available == ()  # both analyses exist in this installation
    vibration, outgassing = profiled.card.entries[-2:]
    assert "Table 2.4-4" in vibration.detail and "§2.4.2.5" in vibration.reference
    assert "ASTM E595" in outgassing.detail and "NASA-STD-6016C" in outgassing.reference


def test_every_shipped_profile_agrees_with_the_bundled_factor_set_it_names():
    """A shipped profile restates factors the bundled factor set already reads from the same
    document; the two may not drift apart, and every analysis a profile names must exist."""
    from anvilate.industry import bundled_profiles, industry_profile
    from anvilate.margin_of_safety import factor_set

    shipped = bundled_profiles()
    assert [p.urn.rpartition(":")[2] for p in shipped][:1] == ["general"] and len(shipped) >= 3
    assert len(shipped) == 7
    for profile in shipped[1:]:
        if profile.factor_set is not None:
            rows = factor_set(profile.factor_set.id).rows
            ultimate = next(f.value for f in profile.factors if f.name == "ultimate")
            assert ultimate in {row.ultimate_factor for row in rows}, profile.urn
        for item_class in profile.item_classes:
            unbuilt = tuple(r.check for r in profile.required_checks
                            if r.item_class == item_class and not r.implemented)  # fmt: skip
            got = apply_profile(Scorecard(), resolve(profile), item_class=item_class)
            assert got.not_available == unbuilt, (profile.urn, item_class)
        assert all(r.source or r.practice_default for r in profile._rules())
        assert industry_profile(profile.urn) is not None
    with pytest.raises(RefusalError, match="no shipped profile"):
        industry_profile("submarine")


def test_a_shipped_profile_names_what_awaits_a_paid_standard():
    from anvilate.industry import industry_profile

    changes = resolve(industry_profile("transport-aircraft")).changes()
    assert any(line.startswith("awaiting your value: material design values") for line in changes)
    assert "factor fitting = 1.15" in " ".join(changes)


def test_a_check_no_screen_implements_is_shown_not_available():
    from anvilate.industry import industry_profile

    profiled = apply_profile(Scorecard(), resolve(industry_profile("consumer-product")),
                             item_class="children's article")  # fmt: skip
    edge, point = profiled.card.entries
    assert edge.detail.startswith("not available") and "16 CFR 1500.49" in edge.reference
    assert profiled.not_available == ("sharp edge", "sharp point")


def test_the_resolved_profile_renders_its_header_then_each_change():
    lines = str(resolve(AIRCRAFT)).splitlines()
    assert lines[0] == resolve(AIRCRAFT).header()
    assert lines[1:] == [f"  {line}" for line in resolve(AIRCRAFT).changes()]
    assert str(resolve(GENERAL)) == resolve(GENERAL).header()
