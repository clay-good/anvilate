"""Keepouts declared in a Design Spec: typed, anchored, explained, never a vacuous pass."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.scorecard import CheckStatus
from anvilate.screening import screen_spec
from anvilate.spec import dump_spec_yaml, load_spec_yaml
from anvilate.spec.validate import SpecValidationError

_ENCLOSURE = """
anvilate_spec: "1.15.0"
name: sensor_enclosure
description: An enclosure with a connector that must mate and a corridor for service.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}
interfaces:
  - {type: standard_component, ref: ISO4014-M12, tag: connector_j1}
dimensions:
  - tag: service_door
    nominal: {magnitude: 80.0, unit: mm}
    tolerance: {type: symmetric, plus_minus: {magnitude: 0.2, unit: mm}}
keepouts:
  - tag: j1_mating_envelope
    anchor: connector_j1
    rule:
      {rule: cylinder, diameter: {magnitude: 24.0, unit: mm}, height: {magnitude: 30.0, unit: mm}}
    clearance_margin: {magnitude: 0.5, unit: mm}
    reason: the J1 plug and its latch must seat without touching the housing
  - tag: service_corridor
    anchor: service_door
    rule:
      rule: swept_profile
      profile_width: {magnitude: 60.0, unit: mm}
      profile_height: {magnitude: 40.0, unit: mm}
      path_length: {magnitude: 120.0, unit: mm}
    clearance_margin: {magnitude: 2.0, unit: mm}
    reason: a technician's hand reaches the fuse through the service door
    owner: service engineering
"""


def test_a_keepout_round_trips_with_its_reason_owner_and_anchor() -> None:
    spec = load_spec_yaml(_ENCLOSURE)
    again = load_spec_yaml(dump_spec_yaml(spec))
    assert again.keepouts == spec.keepouts
    corridor = again.keepouts[1]
    assert corridor.owner == "service engineering"
    assert corridor.anchor == "service_door"
    assert corridor.rule.rule == "swept_profile"
    assert spec.keepouts[0].owner == "user"


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (("height: {magnitude: 30.0", "height: {magnitude: 0.0"), "height must be positive"),
        (
            ("diameter: {magnitude: 24.0", "diameter: {magnitude: -24.0"),
            "diameter must be positive",
        ),
        (
            (
                "reason: the J1 plug and its latch must seat without touching the housing",
                "reason: ' '",
            ),
            "reason",
        ),
        (("anchor: connector_j1", "anchor: ''"), "anchor"),
        (("magnitude: 0.5, unit: mm}", "magnitude: -0.5, unit: mm}"), "clearance_margin"),
        (("tag: service_corridor", "tag: j1_mating_envelope"), "more than once"),
        (("rule: cylinder", "rule: sphere"), "rule"),
    ],
)
def test_a_degenerate_unexplained_or_unanchored_keepout_is_refused(
    change: tuple[str, str], match: str
) -> None:
    before, after = change
    assert before in _ENCLOSURE
    with pytest.raises(SpecValidationError, match=match):
        load_spec_yaml(_ENCLOSURE.replace(before, after, 1))


def test_a_cone_is_a_frustum_with_no_top_and_an_imported_body_needs_a_volume() -> None:
    from anvilate.spec import FrustumKeepout, ImportedBodyKeepout
    from anvilate.units import Quantity

    q = Quantity.parse
    cone = FrustumKeepout(base_diameter=q("20 mm"), top_diameter=q("0 mm"), height=q("50 mm"))
    assert cone.rule == "frustum"
    with pytest.raises(ValidationError, match="volume must be positive"):
        ImportedBodyKeepout(
            source="beam envelope from the optical design", sha256="a" * 64, volume=q("0 mm**3")
        )
    with pytest.raises(ValidationError, match="sha256"):
        ImportedBodyKeepout(source="x", sha256="not a digest", volume=q("1 mm**3"))


def test_a_declared_keepout_is_not_evaluated_never_a_pass() -> None:
    card = screen_spec(load_spec_yaml(_ENCLOSURE))
    entries = {entry.name: entry for entry in card.entries}
    for tag in ("j1_mating_envelope", "service_corridor"):
        entry = entries[f"keepout {tag}"]
        assert entry.status is CheckStatus.NOT_EVALUATED
        assert "was not checked" in entry.detail
    assert "the J1 plug and its latch" in entries["keepout j1_mating_envelope"].detail
    assert not card.passed


def test_a_broken_anchor_is_named_rather_than_silently_protecting_nothing() -> None:
    moved = _ENCLOSURE.replace("tag: connector_j1}", "tag: connector_j2}")
    entry = {e.name: e for e in screen_spec(load_spec_yaml(moved)).entries}[
        "keepout j1_mating_envelope"
    ]
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "which this document no longer tags" in entry.detail


def test_a_moved_keepout_reads_as_its_own_line_in_a_diff() -> None:
    import difflib

    before = dump_spec_yaml(load_spec_yaml(_ENCLOSURE)).splitlines()
    after = dump_spec_yaml(
        load_spec_yaml(_ENCLOSURE.replace("magnitude: 2.0, unit: mm}", "magnitude: 5.0, unit: mm}"))
    ).splitlines()
    changed = [
        line
        for line in difflib.unified_diff(before, after, lineterm="", n=0)
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    assert len(changed) == 2 and all("5.0" in line or "2.0" in line for line in changed)


def test_the_evidence_bundle_records_each_keepout_with_its_reason() -> None:
    """Both the bundle's spec and its card name the keepout, its reason and its anchor."""
    import json

    from anvilate.bundle import BundleSections

    spec = load_spec_yaml(_ENCLOSURE)
    sections = BundleSections(scorecard=screen_spec(spec), spec=spec)
    exported = json.dumps(sections.to_document_dict())
    rendered = sections.render_document()
    for text in (exported, rendered):
        assert "service_corridor" in text
        assert "a technician's hand reaches the fuse through the service door" in text
        assert "service_door" in text
