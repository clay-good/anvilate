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
    Constraints,
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


# --- The tier a document can now reach ----------------------------------------------------
#
# Until `element_type` landed, T1 reported NOT_EVALUATED on **every** spec and would have
# gone on doing so however much analysis was written: 236 closed-form modules unreachable
# from the front door, because the IR had no way to say what kind of element the part was.


def _lug_spec(**overrides) -> DesignSpec:
    """A spec that names its element — the whole point of the field."""
    params = {
        "name": "padeye",
        "material": "ASTM-A36",
        "width": _q("120 mm"),
        "hole_diameter": _q("40 mm"),
        "thickness": _q("20 mm"),
        "load": _q("60 kN"),
    }
    base = {
        "element_type": "lifting_lug",
        "element_params": params,
        "constraints": Constraints(min_safety_factor=Provenanced.stated(2.0)),
        "acceptance": AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    }
    base.update(overrides)
    return _spec(**base)


def test_a_spec_that_names_its_element_reaches_the_pack_that_screens_it():
    """The main path, end to end from a document.

    Two ASME BTH-1 checks, selected from the tag, judged against the safety factor the
    document itself states — and no `T1 analytical` gap entry, because there is no longer a
    gap to name.
    """
    card = screen_spec(_lug_spec())
    names = [entry.name for entry in card.entries]
    assert "T1 analytical" not in names, "the gap is still reported on a spec that closes it"
    assert "padeye net tension" in names and "padeye pin bearing" in names
    for entry in card.entries:
        if entry.name.startswith("padeye"):
            assert entry.status is CheckStatus.PASS
            assert "required minimum 2.00" in entry.detail
    assert card.status is CheckStatus.PASS


def test_the_required_safety_factor_comes_from_the_document_and_is_never_invented():
    """A screen judged against a number nobody stated is the assumption least worth making.

    Thirteen of the twenty-four screens take a required safety factor and have no
    default. The spec already states one, so it is read from there — and a spec that states
    none reports NOT_EVALUATED saying so rather than screening against a house figure.
    """
    stated = screen_spec(_lug_spec())
    assert all(
        "required minimum 2.00" in entry.detail
        for entry in stated.entries
        if entry.name.startswith("padeye")
    )

    # The same element, judged against a different declared minimum, moves the verdict.
    tight = screen_spec(
        _lug_spec(constraints=Constraints(min_safety_factor=Provenanced.stated(5.0)))
    )
    bearing = next(e for e in tight.entries if e.name == "padeye pin bearing")
    assert bearing.status is CheckStatus.FAIL, bearing.detail
    assert "required minimum 5.00" in bearing.detail

    # And with none stated at all, the tier is named rather than run.
    silent = screen_spec(_lug_spec(constraints=Constraints()))
    gap = next(e for e in silent.entries if e.name == "T1 analytical")
    assert gap.status is CheckStatus.NOT_EVALUATED
    assert "states none" in gap.detail and "min_safety_factor" in gap.detail


def test_an_element_type_no_pack_screens_is_named_rather_than_ignored():
    """An unknown tag is a document that asked for a screen this library does not have. The
    refusal counts the elements it does have and suggests the near miss, because the
    likeliest cause is a spelling."""
    card = screen_spec(_lug_spec(element_type="lifting_lugs"))
    gap = next(e for e in card.entries if e.name == "T1 analytical")
    assert gap.status is CheckStatus.NOT_EVALUATED
    assert "'lifting_lugs' is not one of the" in gap.detail
    assert "did you mean 'lifting_lug'?" in gap.detail


def test_element_params_the_pack_refuses_are_reported_as_the_gap_they_are():
    """The cost of a tag-and-map rather than a typed union is that a malformed element is
    caught at screening rather than at parse. It is paid here: the pack model's own refusal
    is quoted, naming the field, so the answer is as specific as a parse error would be."""
    broken = dict(_lug_spec().element_params)
    del broken["hole_diameter"]
    card = screen_spec(_lug_spec(element_params=broken))
    gap = next(e for e in card.entries if e.name == "T1 analytical")
    assert gap.status is CheckStatus.NOT_EVALUATED
    assert "do not build a LiftingLug" in gap.detail
    assert "hole_diameter" in gap.detail

    # A field of the right name and the wrong dimension is the pack's own message too.
    wrong = dict(_lug_spec().element_params)
    wrong["load"] = _q("60 mm")
    detail = next(
        e for e in screen_spec(_lug_spec(element_params=wrong)).entries if e.name == "T1 analytical"
    ).detail
    assert "load" in detail


def test_neither_half_of_an_element_declaration_stands_alone():
    """A tag with no fields screens nothing, and fields with no tag belong to no element."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="no element_params"):
        _spec(element_type="lifting_lug")
    with pytest.raises(ValidationError, match="no element_type"):
        _spec(element_params={"name": "padeye"})
    with pytest.raises(ValidationError, match="an empty string is not one"):
        _spec(element_type="  ", element_params={"name": "padeye"})


def test_the_element_registry_covers_every_pack_screen_that_takes_one_element():
    """The registry is derived from the packs, so a new pack element registers by existing.

    Held the other way round here: every `screen_*` a pack exports whose first parameter is
    a model must be reachable by a tag, or a pack ships an element no document can name and
    nothing says so. `screen_structure` takes a *list* and is excluded by that rule rather
    than by name; `structure` is registered by the screening module itself in its place, and
    is the one tag the packs do not supply.
    """
    import importlib
    import inspect
    import pkgutil

    from pydantic import BaseModel

    from anvilate import packs
    from anvilate.screening import element_registry

    registry = element_registry()
    reachable = {model for model, _screen in registry.values()}
    missing, total = [], 0
    for info in pkgutil.iter_modules(packs.__path__, "anvilate.packs."):
        module = importlib.import_module(info.name)
        for name in sorted(getattr(module, "__all__", ())):
            if not name.startswith("screen_"):
                continue
            first = next(iter(inspect.signature(getattr(module, name)).parameters.values()), None)
            annotation = first.annotation if first is not None else None
            if isinstance(annotation, str):
                annotation = getattr(module, annotation, None)
            if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
                continue
            total += 1
            if annotation not in reachable:
                missing.append(f"{info.name}.{name} screens {annotation.__name__}")

    assert total > 20, f"only {total} single-element pack screens were found"
    assert not missing, "pack elements no document can name:\n  " + "\n  ".join(missing)
    from anvilate.screening import Structure

    assert registry["structure"][0] is Structure
    assert len(registry) == total + 1, (
        f"the registry holds {len(registry)} tags for {total} pack elements plus the one "
        "composite; anything else in it is unaccounted for"
    )
    # And the tags are distinct, or a document naming one would screen the other.
    assert len(set(registry)) == len(registry)


def test_an_element_declaration_survives_being_written_down():
    """A spec is a *document*, so the element it declares has to come back off disk as the
    element it was. `element_params` is typed `Any`, which pydantic cannot rebuild from, so
    a quantity in it went out as `{"magnitude", "unit"}` and came back as a dictionary the
    pack model refuses."""
    from anvilate.spec import dump_spec_yaml, load_spec_yaml

    spec = _lug_spec()
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    assert reloaded.element_type == "lifting_lug"
    assert isinstance(reloaded.element_params["load"], Quantity)
    assert reloaded.element_params["load"].to("kN").magnitude == pytest.approx(60.0)
    # And it screens to the same card, which is the property that actually matters.
    assert [(e.name, e.status) for e in screen_spec(reloaded).entries] == [
        (e.name, e.status) for e in screen_spec(spec).entries
    ]


def _docs_page_element_blocks() -> list[dict]:
    """Every YAML block on the screening page that a reader would paste into a document."""
    import re
    from pathlib import Path

    import yaml

    page = (Path(__file__).resolve().parent.parent / "docs" / "spec-screening.md").read_text()
    blocks = re.findall(r"```yaml\n(element_type:.*?)```", page, re.S)
    assert len(blocks) >= 2, f"the element blocks on spec-screening.md have moved: {len(blocks)}"
    return [yaml.safe_load(block) for block in blocks]


@pytest.mark.parametrize("shown", _docs_page_element_blocks())
def test_the_docs_page_element_blocks_are_documents_that_screen(shown):
    """The page prints what a reader copies. Every such block is loaded and screened rather
    than read, because a block nobody runs is prose that looks like code — and the second one
    was written with `...` in it, which is prose that looks like code and is not even YAML.

    Parametrised over the blocks the page actually carries, so a third one is gated by
    existing rather than by somebody remembering to add a test.
    """
    assert set(shown) == {"element_type", "element_params", "constraints"}, shown

    card = screen_spec(
        _spec(
            element_type=shown["element_type"],
            element_params=shown["element_params"],
            constraints=Constraints(
                min_safety_factor=Provenanced.stated(
                    shown["constraints"]["min_safety_factor"]["value"]
                )
            ),
            acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
        )
    )
    screened = [entry for entry in card.entries if entry.name != "material resolution"]
    assert screened, f"the page's element screened nothing: {[e.name for e in card.entries]}"
    assert "T1 analytical" not in [entry.name for entry in card.entries]
    # Every check the page's own document produces cites the clause it came from.
    for entry in screened:
        assert entry.reference, f"{entry.name} came back with no citation"


def test_the_docs_page_lug_block_returns_the_two_checks_the_page_claims():
    """The page says two cited ASME BTH-1 checks come back from the lug; that is the claim,
    so it is held on the lug block specifically rather than on whichever block comes first."""
    shown = next(b for b in _docs_page_element_blocks() if b["element_type"] == "lifting_lug")
    card = screen_spec(
        _spec(
            element_type=shown["element_type"],
            element_params=shown["element_params"],
            constraints=Constraints(min_safety_factor=Provenanced.stated(2.0)),
            acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
        )
    )
    named = [entry for entry in card.entries if entry.name.startswith("padeye")]
    assert len(named) == 2
    for entry in named:
        assert entry.reference and "BTH-1" in entry.reference, entry.reference


def _structure_spec(members, **overrides) -> DesignSpec:
    """A spec whose element is a whole structure rather than one part."""
    return _lug_spec(element_type="structure", element_params={"members": members}, **overrides)


def _lug_member(name: str) -> dict:
    return {
        "element_type": "lifting_lug",
        "element_params": {**_lug_spec().element_params, "name": name},
    }


def test_a_spec_can_name_a_whole_structure_and_every_member_is_screened():
    """The gap this element closes: `screen_structure` takes a *list*, so no single tag
    addressed it and a document describing a frame could name only one of its members.

    Every member reaches the screen it would have reached on its own, and the entries carry
    the member that produced them — two lugs in one frame otherwise contribute two checks
    called the same thing and a reader cannot tell which one failed.
    """
    card = screen_spec(_structure_spec([_lug_member("first"), _lug_member("second")]))
    named = [entry.name for entry in card.entries if entry.name.startswith("member")]
    assert named == [
        "member 1 (lifting_lug): first net tension",
        "member 1 (lifting_lug): first pin bearing",
        "member 2 (lifting_lug): second net tension",
        "member 2 (lifting_lug): second pin bearing",
    ]
    assert "T1 analytical" not in [entry.name for entry in card.entries]
    assert card.status is CheckStatus.PASS
    # The citation survives the prefixing, or the member entries are checks with no clause.
    for entry in card.entries:
        if entry.name.startswith("member"):
            assert entry.reference and "BTH-1" in entry.reference


def test_one_unscreenable_member_does_not_un_screen_the_others():
    """A report naming one bad member and one good one is worth more than one naming nothing,
    and NOT_EVALUATED is already what the roll-up refuses to treat as a pass."""
    card = screen_spec(
        _structure_spec(
            [
                _lug_member("first"),
                {"element_type": "lifting_lugg", "element_params": {}},
                {"element_type": "lifting_lug", "element_params": {"name": "bare"}},
            ]
        )
    )
    by_name = {entry.name: entry for entry in card.entries}
    assert by_name["member 1 (lifting_lug): first net tension"].status is CheckStatus.PASS

    unknown = by_name["member 2 (lifting_lugg): T1 analytical"]
    assert unknown.status is CheckStatus.NOT_EVALUATED
    assert "did you mean 'lifting_lug'" in unknown.detail

    refused = by_name["member 3 (lifting_lug): T1 analytical"]
    assert refused.status is CheckStatus.NOT_EVALUATED
    assert "do not build a LiftingLug" in refused.detail
    assert card.status is CheckStatus.NOT_EVALUATED


def test_a_structure_is_not_a_member_of_a_structure():
    """Not a depth limit dressed up as a rule — a nested structure carries nothing the flat
    list does not — but it is also what keeps the member loop from reaching itself."""
    card = screen_spec(
        _structure_spec([{"element_type": "structure", "element_params": {"members": []}}])
    )
    entry = card.entries[0]
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert "a structure cannot be a member of a structure" in entry.detail


def test_a_structure_needs_the_safety_factor_its_members_are_judged_against():
    """The composite is judged by the same rule as the elements inside it: a screen that
    needs a required safety factor and is given none is NOT_EVALUATED, never screened
    against a figure this library made up."""
    card = screen_spec(_structure_spec([_lug_member("first")], constraints=Constraints()))
    assert card.entries[0].status is CheckStatus.NOT_EVALUATED
    assert "the structure screen is judged against a required safety factor" in (
        card.entries[0].detail
    )


def test_a_structure_survives_being_written_down():
    """A member's quantities sit one level deeper than the spec's own round-trip repair
    reaches — inside a list — so a frame written to disk is screened after a reload, not
    only in memory."""
    from anvilate.spec import dump_spec_yaml, load_spec_yaml

    spec = _structure_spec([_lug_member("first"), _lug_member("second")])
    reloaded = load_spec_yaml(dump_spec_yaml(spec))
    assert [(e.name, e.status) for e in screen_spec(reloaded).entries] == [
        (e.name, e.status) for e in screen_spec(spec).entries
    ]
