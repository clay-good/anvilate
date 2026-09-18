"""Failure-mode coverage: the modes nobody asked about, named beside their population."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.failure_modes import (
    CATALOG_IS_A_FLOOR,
    DEFAULT_CATALOG,
    Applicability,
    DiscoveryStage,
    FailureMode,
    ModeCatalog,
    coverage,
)
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry


def _mode(identifier: str, **fields: object) -> FailureMode:
    declared: dict[str, object] = {
        "id": identifier,
        "description": f"the way a part fails that {identifier} names",
        "applicability": Applicability(elements=("bolted_connection",)),
        "stage": DiscoveryStage.QUALIFICATION,
        "citation": "a source a reader can go and read",
    }
    declared.update(fields)
    return FailureMode(**declared)  # type: ignore[arg-type]


def _card(*entries: tuple[str, CheckStatus]) -> Scorecard:
    return Scorecard(
        entries=tuple(
            ScorecardEntry(name=name, status=status, detail="as screened")
            for name, status in entries
        )
    )


def test_a_clean_card_with_an_unaddressed_mode_does_not_read_as_complete() -> None:
    """The defect class this capability exists to expose.

    Every check on the card passed. A mode that applies to what the document declares has
    no check and no test, and the card said nothing about it — which is what makes a silent
    card read as a clean one.
    """
    catalog = ModeCatalog(
        modes=(
            _mode("bolt shear", addressed_by=("joint bolt shear",)),
            _mode("crevice corrosion"),  # applicable, no check, no test
        )
    )
    card = _card(("joint bolt shear", CheckStatus.PASS), ("joint bearing", CheckStatus.PASS))
    assert card.status is CheckStatus.PASS

    report = coverage(card, {"element": "bolted_connection"}, catalog=catalog)
    assert not report.complete()
    (missing,) = report.unaddressed()
    assert missing.mode.id == "crevice corrosion"
    assert "crevice corrosion: UNADDRESSED" in str(report)


def test_the_report_states_the_population_and_never_a_bare_percentage() -> None:
    catalog = ModeCatalog(modes=(_mode("a", addressed_by=("ran",)), _mode("b")))
    report = coverage(
        _card(("ran", CheckStatus.PASS)), {"element": "bolted_connection"}, catalog=catalog
    )
    head = str(report).splitlines()[0]
    assert "1 of 2 applicable addressed by a check that ran" in head
    assert "from a catalogue of 2" in head
    assert "%" not in str(report), "a coverage figure with no denominator hides the gap"
    assert report.catalog_size == 2 and report.applicable == 2


def test_the_floor_caveat_is_printed_wherever_coverage_is() -> None:
    report = coverage(_card(), {"element": "bolted_connection"})
    assert CATALOG_IS_A_FLOOR in str(report)
    assert CATALOG_IS_A_FLOOR in str(DEFAULT_CATALOG)


def test_a_mode_left_to_a_physical_test_is_not_addressed() -> None:
    """A plan is never evidence — the rule verification planning already states.

    A mode "left to a fretting test" has had nothing done about it, and counting the
    archetype as coverage is the silent green a coverage number is most likely to produce.
    """
    catalog = ModeCatalog(modes=(_mode("fretting", tested_by=("dwell fretting test",)),))
    report = coverage(
        _card(("anything", CheckStatus.PASS)), {"element": "bolted_connection"}, catalog=catalog
    )
    (entry,) = report.entries
    assert not entry.addressed and entry.planned
    assert report.addressed() == () and report.unaddressed() == ()
    assert report.planned() == (entry,)
    assert not report.complete()
    assert "no check; left to dwell fretting test" in str(report)


def test_a_check_that_did_not_run_addresses_nothing() -> None:
    """Otherwise one gap hides another: the card already says the check did not run."""
    catalog = ModeCatalog(modes=(_mode("bolt shear", addressed_by=("joint bolt shear",)),))
    facts = {"element": "bolted_connection"}
    ran = coverage(_card(("joint bolt shear", CheckStatus.PASS)), facts, catalog=catalog)
    did_not = coverage(
        _card(("joint bolt shear", CheckStatus.NOT_EVALUATED)), facts, catalog=catalog
    )
    assert ran.complete()
    assert not did_not.complete()
    assert did_not.unaddressed()[0].mode.id == "bolt shear"


def test_a_mode_applies_only_on_facts_the_document_states() -> None:
    catalog = ModeCatalog(
        modes=(
            _mode("galvanic", applicability=Applicability(dissimilar_metals=True)),
            _mode("fretting", applicability=Applicability(interfaces=("clamped",))),
            _mode("ratchet", applicability=Applicability(environments=("thermal_cycling",))),
        )
    )
    card = _card(("something", CheckStatus.PASS))
    assert coverage(card, {}, catalog=catalog).entries == ()
    assert len(coverage(card, {"dissimilar_metals": True}, catalog=catalog).entries) == 1
    assert len(coverage(card, {"interfaces": ("clamped", "bonded")}, catalog=catalog).entries) == 1
    both = coverage(
        card, {"dissimilar_metals": True, "environment": "thermal_cycling"}, catalog=catalog
    )
    assert {entry.mode.id for entry in both.entries} == {"galvanic", "ratchet"}


def test_deleting_a_catalog_entry_changes_the_report() -> None:
    """The report reads the catalogue rather than asserting a number of its own."""
    facts = {"element": "bolted_connection"}
    card = _card(("ran", CheckStatus.PASS))
    full = ModeCatalog(modes=(_mode("a"), _mode("b")))
    fewer = ModeCatalog(modes=(_mode("a"),))
    assert coverage(card, facts, catalog=full).applicable == 2
    assert coverage(card, facts, catalog=fewer).applicable == 1
    assert coverage(card, facts, catalog=fewer).catalog_size == 1


def test_a_modules_modes_extend_the_catalogue_and_move_the_denominator() -> None:
    extended = DEFAULT_CATALOG.extended(
        _mode("module-specific mode", applicability=Applicability(elements=("pump_duty",)))
    )
    assert len(extended) == len(DEFAULT_CATALOG) + 1
    card = _card(("ran", CheckStatus.PASS))
    assert coverage(card, {"element": "pump_duty"}, catalog=DEFAULT_CATALOG).applicable == 0
    report = coverage(card, {"element": "pump_duty"}, catalog=extended)
    assert report.applicable == 1 and report.catalog_size == len(DEFAULT_CATALOG) + 1
    with pytest.raises(ValidationError, match="one mode id twice"):
        DEFAULT_CATALOG.extended(_mode("galvanic corrosion"))


def test_the_stage_is_reported_as_a_stage_and_not_as_a_ranking() -> None:
    catalog = ModeCatalog(
        modes=(
            _mode("found late", stage=DiscoveryStage.FIELD),
            _mode("found in qual", stage=DiscoveryStage.QUALIFICATION),
        )
    )
    report = coverage(_card(), {"element": "bolted_connection"}, catalog=catalog)
    assert set(report.by_stage()) == {DiscoveryStage.FIELD, DiscoveryStage.QUALIFICATION}
    rendered = str(report)
    assert "not yet checked, normally found at field: found late" in rendered
    # A stage, never a severity: nothing in the rendering orders the modes against each other.
    for word in ("severity", "critical", "worst", "priority"):
        assert word not in rendered.lower()


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"applicability": {}}, "applies to everything"),
        ({"citation": "   "}, "must state"),
        ({"description": ""}, "must state"),
        ({"id": "  "}, "must state"),
    ],
)
def test_a_malformed_mode_is_refused(fields: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _mode("a mode", **fields)


def test_every_shipped_mode_cites_a_source_and_says_when_it_is_found() -> None:
    assert len(DEFAULT_CATALOG) >= 5, "the shipped catalogue is all but empty"
    for mode in DEFAULT_CATALOG.modes:
        assert len(mode.citation.split()) >= 3, f"{mode.id} cites {mode.citation!r}"
        assert len(mode.description.split()) >= 8, f"{mode.id} describes itself in a phrase"
        assert mode.stage in set(DiscoveryStage)
        # A mode bound to a check this library does not ship would report coverage that
        # does not exist; the shipped ones are all bound to tests, and say so.
        assert mode.addressed_by or mode.tested_by, f"{mode.id} names neither a check nor a test"


def test_the_shipped_catalogue_finds_the_modes_a_bolted_joint_carries() -> None:
    card = _card(("joint bolt shear", CheckStatus.PASS), ("joint bearing", CheckStatus.PASS))
    report = coverage(card, {"element": "bolted_connection", "dissimilar_metals": True})
    assert {entry.mode.id for entry in report.entries} == {
        "bolt self-loosening",
        "galvanic corrosion",
    }
    # Nothing on this card checked either of them, and the report says so rather than
    # reporting a clean pass over two checks that answered neither question.
    assert report.addressed() == ()
    assert not report.complete()
