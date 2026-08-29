"""Screening a Design Spec on its own terms, and the tier it has to name rather than run.

The load-bearing property here is not that the passing checks pass. It is that a tier the
spec *demanded* always produces an entry — including when the document carries nothing to
run it against — because a demanded tier that quietly produced no entries would leave
`Scorecard.passed` green on the strength of whatever checks happened to exist.
"""

from __future__ import annotations

import pytest

from anvilate.scorecard import CheckStatus
from anvilate.screening import screen_spec
from anvilate.spec import (
    AcceptanceCriteria,
    ChainLink,
    DesignSpec,
    DimensionChain,
    LoadCase,
    LoadKind,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Provenanced,
    StandardComponentInterface,
    ToleranceDimension,
    ValidationTier,
)
from anvilate.tolerance import SymmetricTolerance
from anvilate.units import Quantity, UnitSystem


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _spec(**overrides) -> DesignSpec:
    base = {
        "name": "deck_plate",
        "description": "A mezzanine deck plate.",
        "units": Provenanced.stated(UnitSystem.SI),
        "material": MaterialRef(ref="ASTM-A36"),
        "manufacturing": Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        "acceptance": AcceptanceCriteria(tiers=[ValidationTier.T2_DFM]),
    }
    base.update(overrides)
    return DesignSpec(**base)


def _dimension(tag: str, nominal: str, band: str) -> ToleranceDimension:
    return ToleranceDimension(
        tag=tag, nominal=_q(nominal), tolerance=SymmetricTolerance(plus_minus=_q(band))
    )


def _by_name(spec: DesignSpec) -> dict[str, CheckStatus]:
    return {entry.name: entry.status for entry in screen_spec(spec).entries}


# ------------------------------------------------------------------ the demanded tiers


@pytest.mark.parametrize(
    ("tier", "name"),
    [
        (ValidationTier.T0_GEOMETRY, "T0 geometry"),
        (ValidationTier.T1_ANALYTICAL, "T1 analytical"),
        (ValidationTier.T3_FEA, "T3 FEA"),
    ],
)
def test_a_demanded_tier_this_screen_cannot_run_is_named_not_dropped(tier, name):
    card = screen_spec(_spec(acceptance=AcceptanceCriteria(tiers=[tier])))
    # The material entry is not tier-gated: a spec declares a material whatever tiers it
    # asks for, so it rides alongside every one of these.
    assert [entry.name for entry in card.entries] == [name, "material resolution"]
    assert card.status is CheckStatus.NOT_EVALUATED
    assert not card.passed


def test_the_analytical_gap_says_what_is_missing_from_the_document():
    """Not "unimplemented" — the reason is a field the IR does not have.

    Anyone reading this scorecard has to be able to tell an unbuilt feature from a spec
    that cannot express what the screen needs, because only one of those is fixed by
    writing more analysis code.
    """
    card = screen_spec(_spec(acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL])))
    detail = next(e for e in card.entries if e.name == "T1 analytical").detail
    assert "declares no structural element type" in detail
    assert "discipline-pack" in detail


def test_a_tier_the_spec_does_not_demand_produces_nothing():
    """The acceptance criteria are the contract for which tiers must run."""
    card = screen_spec(_spec(acceptance=AcceptanceCriteria(tiers=[ValidationTier.T2_DFM])))
    assert not any(entry.name.startswith("T1") for entry in card.entries)


# ----------------------------------------------------------------------------- T2 DFM


def test_a_tolerance_the_process_cannot_hold_fails_with_its_source():
    card = screen_spec(_spec(dimensions=[_dimension("bore", "25 mm", "0.001 mm")]))
    entry = card.entries[0]  # the T2 entries come first, before the document-level ones
    assert entry.status is CheckStatus.FAIL
    assert "UNACHIEVABLE" in entry.detail
    # A screening floor stated without its source reads as a hard limit.
    assert entry.reference


def test_a_tolerance_the_process_can_hold_passes():
    card = screen_spec(_spec(dimensions=[_dimension("bore", "25 mm", "0.5 mm")]))
    assert card.entries[0].status is CheckStatus.PASS
    assert card.passed


def test_a_demanded_dfm_tier_with_nothing_toleranced_is_a_gap_not_a_pass():
    """The case the whole module is shaped around.

    A spec that demands T2 and declares no toleranced dimension has asked a question the
    document cannot answer. Returning an empty card here would make `passed` True — a part
    green on zero checks.
    """
    card = screen_spec(_spec())
    assert [entry.name for entry in card.entries] == [
        "tolerance achievability",
        "material resolution",
    ]
    assert card.entries[0].status is CheckStatus.NOT_EVALUATED
    assert "nothing to screen" in card.entries[0].detail
    assert not card.passed


def test_every_declared_process_has_a_capability_record():
    """The ratchet that keeps the gap branch below unreachable.

    A new ``ManufacturingProcess`` with no capability record would not crash anything — it
    would turn every T2 verdict for that process into NOT_EVALUATED, quietly, for as long
    as nobody read one. This fails instead.
    """
    from anvilate.tolerance.process import process_capability

    for process in ManufacturingProcess:
        assert process_capability(process.value).finest_tolerance.magnitude > 0


def test_a_process_with_no_capability_record_is_a_gap_naming_it(monkeypatch):
    """The unreachable branch, exercised anyway.

    No process reaches it today — the ratchet above is why — but a guard nothing ever runs
    is one whose behavior is a guess, and the whole point of this branch is that one
    missing table row must not take the tolerance and load verdicts down with it.
    """
    from anvilate import screening
    from anvilate.tolerance.general import ToleranceRangeError

    def absent(process, width):
        raise ToleranceRangeError(f"no tolerance-capability record for process {process!r}")

    monkeypatch.setattr(screening, "tolerance_is_achievable", absent)
    spec = _spec(
        dimensions=[_dimension("bore", "25 mm", "0.5 mm")],
        load_cases=[_load(nature=None)],
    )
    statuses = _by_name(spec)
    assert statuses["tolerance achievability: bore"] is CheckStatus.NOT_EVALUATED
    assert "cnc_milling" in screen_spec(spec).entries[0].detail
    # The other layers still reported.
    assert "load classification" in statuses


# ------------------------------------------------------------------------ stack-up chains


def _chained_spec(required_min: str, required_max: str, **overrides) -> DesignSpec:
    return _spec(
        dimensions=[
            _dimension("shaft", "20 mm", "0.05 mm"),
            _dimension("bore", "20.2 mm", "0.05 mm"),
        ],
        chains=[
            DimensionChain(
                name="running clearance",
                links=[ChainLink(dimension="bore"), ChainLink(dimension="shaft", direction=-1)],
                required_min=_q(required_min),
                required_max=_q(required_max),
            )
        ],
        **overrides,
    )


def test_a_chain_is_judged_on_its_worst_case():
    tight = _chained_spec("0.19 mm", "0.21 mm")
    loose = _chained_spec("0.0 mm", "1.0 mm")
    assert _by_name(tight)["stack-up: running clearance"] is CheckStatus.FAIL
    assert _by_name(loose)["stack-up: running clearance"] is CheckStatus.PASS


def test_the_worst_case_is_the_gate_and_not_the_statistical_spread():
    """The band where the two answers differ, which is the only place the rule is testable.

    Two +/-0.05 mm dimensions on a 0.2 mm nominal gap: worst case spans 0.1..0.3 mm, RSS
    spans about 0.129..0.271 mm. A required band of 0.12..0.28 mm therefore *passes* on
    RSS and *fails* on the worst case — and a part that can be built out of tolerance is
    one that will be. Without this case, judging the chain on `rss_passes` passed every
    other test in this file.
    """
    spec = _chained_spec("0.12 mm", "0.28 mm")
    analysis = spec.analyze_chains()[0]
    assert analysis.rss_passes
    assert not analysis.worst_case_passes
    assert _by_name(spec)["stack-up: running clearance"] is CheckStatus.FAIL


def test_a_chain_naming_an_undeclared_dimension_is_a_gap_in_one_layer_only():
    """Refusing the whole screen would lose the tolerance verdicts with it."""
    spec = _spec(
        dimensions=[_dimension("bore", "25 mm", "0.5 mm")],
        chains=[
            DimensionChain(
                name="broken",
                links=[ChainLink(dimension="nonexistent")],
                required_min=_q("0 mm"),
                required_max=_q("1 mm"),
            )
        ],
    )
    statuses = _by_name(spec)
    assert statuses["stack-up chains"] is CheckStatus.NOT_EVALUATED
    assert statuses["tolerance achievability: bore"] is CheckStatus.PASS


def test_chains_are_screened_whatever_tiers_the_spec_names():
    """A declared chain is the document asking for it, not a tier flag."""
    spec = _chained_spec(
        "0.0 mm", "1.0 mm", acceptance=AcceptanceCriteria(tiers=[ValidationTier.T0_GEOMETRY])
    )
    assert "stack-up: running clearance" in _by_name(spec)


# ------------------------------------------------------------------- load classification


def _load(nature=None) -> LoadCase:
    return LoadCase(
        name="deck live", kind=LoadKind.STATIC, applied_to="top", force=_q("50 kN"), nature=nature
    )


def test_an_unclassified_load_case_is_a_gap_naming_it():
    card = screen_spec(_spec(load_cases=[_load()]))
    entry = next(e for e in card.entries if e.name == "load classification")
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "deck live" in entry.detail
    # The reason matters more than the flag: a combination reads an unsupplied nature as
    # zero, so the demand silently omits the load rather than refusing to run.
    assert "as zero" in entry.detail


def test_a_spec_with_no_load_cases_says_nothing_about_them():
    """An entry here would be noise: there is nothing to classify, not a gap."""
    assert "load classification" not in _by_name(_spec())


def test_every_classified_case_passes():
    from anvilate.loads import LoadNature

    card = screen_spec(_spec(load_cases=[_load(nature=LoadNature.LIVE)]))
    entry = next(e for e in card.entries if e.name == "load classification")
    assert entry.status is CheckStatus.PASS


# --------------------------------------------------------------------- over the MCP wire


def _call(name: str, arguments: dict) -> dict:
    from anvilate.mcp import handle_request

    return handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )


def test_run_validation_returns_the_same_card_the_library_computes():
    spec = _spec(dimensions=[_dimension("bore", "25 mm", "0.5 mm")])
    result = _call("run_validation", {"spec": spec.model_dump(mode="json")})["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["scorecard"] == screen_spec(spec).model_dump(mode="json")


def test_run_validation_lets_the_caller_ask_for_a_tier_the_spec_did_not_demand():
    """``tiers`` replaces rather than intersects — a caller asking is asking a question."""
    spec = _spec(acceptance=AcceptanceCriteria(tiers=[ValidationTier.T2_DFM]))
    result = _call(
        "run_validation",
        {"spec": spec.model_dump(mode="json"), "tiers": [ValidationTier.T1_ANALYTICAL.value]},
    )["result"]
    names = [entry["name"] for entry in result["structuredContent"]["scorecard"]["entries"]]
    assert names == ["T1 analytical", "material resolution"]


def test_a_document_that_is_not_a_design_spec_is_a_malformed_request_here():
    """Unlike ``compile_spec``, whose input property is "a candidate document".

    This tool's input property is declared as the published Design Spec schema, so a
    document that does not match it fails the contract the client was handed — and
    INVALID_PARAMS with the paths is where a client should look.
    """
    error = _call("run_validation", {"spec": {"name": "nameless"}})["error"]
    assert error["code"] == -32602
    assert "spec.material" in error["message"]


def test_a_failing_screen_is_a_result_and_not_a_transport_error():
    """A part that does not pass is the answer, not a protocol problem."""
    spec = _spec(dimensions=[_dimension("bore", "25 mm", "0.001 mm")])
    result = _call("run_validation", {"spec": spec.model_dump(mode="json")})["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["scorecard"]["entries"][0]["status"] == "fail"


# ------------------------------------------------------ the page that argues from numbers


def test_the_docs_page_quotes_the_bounds_this_module_actually_computes():
    """`docs/spec-screening.md` argues the worst-case rule from four numbers. Here they are.

    The page is where a reader learns that the worst case is the gate, and it earns that
    with a band where the two answers differ. Those bounds are computed here from the same
    chain the page describes — built from the page's *inputs*, never from its outputs — so
    a digit that drifts in the prose fails rather than being read for years.
    """
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "docs" / "spec-screening.md").read_text()
    quoted = " ".join(page.splitlines())
    # The requirement band is read *out of the page* rather than restated here. Quoting
    # the computed bounds back at the page catches a drifting result; only building the
    # chain from the page's own input catches a drifting illustration — and the property
    # asserted at the end is what that input exists to demonstrate.
    stated = re.search(r"two ±([\d.]+) mm\s+dimensions on a ([\d.]+) mm nominal gap", quoted)
    required = re.search(r"requirement of ([\d.]+)\.\.([\d.]+) mm", quoted)
    assert stated, "the page no longer states the dimensions its argument is built from"
    assert required, "the page no longer states the requirement band its argument turns on"
    tolerance, gap = stated.group(1), float(stated.group(2))
    spec = _spec(
        dimensions=[
            _dimension("shaft", "20 mm", f"{tolerance} mm"),
            _dimension("bore", f"{20 + gap} mm", f"{tolerance} mm"),
        ],
        chains=[
            DimensionChain(
                name="running clearance",
                links=[ChainLink(dimension="bore"), ChainLink(dimension="shaft", direction=-1)],
                required_min=_q(f"{required.group(1)} mm"),
                required_max=_q(f"{required.group(2)} mm"),
            )
        ],
    )
    analysis = spec.analyze_chains()[0]
    worst = analysis.worst_case
    rss = analysis.rss

    for value in (
        worst.lower.to("mm").magnitude,
        worst.upper.to("mm").magnitude,
    ):
        assert f"{value:g}" in quoted, f"the page does not quote the worst-case bound {value:g}"
    for value in (rss.lower.to("mm").magnitude, rss.upper.to("mm").magnitude):
        assert f"{value:.3f}" in quoted, f"the page does not quote the RSS bound {value:.3f}"
    # And the property the illustration exists to show, so the numbers cannot be swapped
    # for a pair where the rule does not bite.
    assert analysis.rss_passes and not analysis.worst_case_passes


# ------------------------------------------------------- references resolve, or they fail


def test_a_material_the_databases_do_not_carry_fails_and_names_the_near_misses():
    """The retrieval rule, on the path a user actually takes.

    `validate_references` could always check this and nothing on any shipped path called
    it: a spec naming `NOT-A-REAL-ALLOY` screened *identically* to one naming `ASTM-A36`,
    all the way through `anvilate check`. The two halves — the spec layer's
    `ReferenceResolver` protocol and `anvilate.standards.StandardsResolver`, which was
    written to satisfy it — were wired to nothing.

    The near misses are the half that matters. "Unknown material" invites the reader to
    supply a remembered number, which is the one thing this library exists to stop.
    """
    card = screen_spec(_spec(material=MaterialRef(ref="ASTM-A366")))
    entry = next(e for e in card.entries if e.name == "material resolution")
    assert entry.status is CheckStatus.FAIL
    assert "ASTM-A36" in entry.detail and "did you mean" in entry.detail
    assert not card.passed
    assert card.governing().name == "material resolution"


def test_a_material_with_no_near_miss_says_how_many_it_looked_through():
    """A refusal with no suggestion must still say what it searched, or it reads as a bug."""
    card = screen_spec(_spec(material=MaterialRef(ref="ZZZZZZZZ")))
    entry = next(e for e in card.entries if e.name == "material resolution")
    assert entry.status is CheckStatus.FAIL
    assert "known identifiers" in entry.detail


def test_a_resolvable_material_passes_naming_what_it_resolved():
    card = screen_spec(_spec())
    entry = next(e for e in card.entries if e.name == "material resolution")
    assert entry.status is CheckStatus.PASS
    assert "ASTM-A36" in entry.detail


def test_a_spec_with_no_standard_component_gets_no_interface_entry():
    """Nothing to resolve is not a check that ran, and an entry saying so reads as one."""
    card = screen_spec(_spec())
    assert not any(e.name.startswith("interface resolution") for e in card.entries)


def test_each_standard_component_interface_resolves_on_its_own_tag():
    """One entry per interface, named by tag — two bad refs must not collapse into one."""
    spec = _spec(
        interfaces=[
            StandardComponentInterface(ref="NEMA23", tag="motor_face"),
            StandardComponentInterface(ref="EXT-9999", tag="rail"),
        ]
    )
    card = screen_spec(spec)
    by_name = {e.name: e for e in card.entries}
    assert by_name["interface resolution: motor_face"].status is CheckStatus.PASS
    bad = by_name["interface resolution: rail"]
    assert bad.status is CheckStatus.FAIL
    assert "EXT-9999" in bad.detail


def test_an_injected_resolver_screens_a_team_local_material():
    """A house alloy is an extended database, not a reason to skip the check.

    This is the escape hatch that makes the FAIL above safe to ship: a team whose material
    is not one of the bundled records passes their own resolver rather than losing the
    check, and the check is the same check.
    """

    class _Extended:
        def has_material(self, ref):
            return ref == "HOUSE-ALLOY-1"

        def has_component(self, ref):
            return False

        def known_materials(self):
            return ["HOUSE-ALLOY-1"]

        def known_components(self):
            return []

    spec = _spec(material=MaterialRef(ref="HOUSE-ALLOY-1"))
    entry = next(
        e
        for e in screen_spec(spec, resolver=_Extended()).entries
        if e.name == "material resolution"
    )
    assert entry.status is CheckStatus.PASS
    # And the same spec against the bundled databases is a FAIL, so the injection is what
    # made the difference rather than the identifier happening to be acceptable.
    assert (
        next(e for e in screen_spec(spec).entries if e.name == "material resolution").status
        is CheckStatus.FAIL
    )
