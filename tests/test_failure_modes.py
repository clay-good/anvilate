"""Failure-mode coverage: the modes nobody asked about, named beside their population."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvilate.analysis.fatigue import weld_fatigue_scorecard
from anvilate.failure_modes import (
    CATALOG_IS_A_FLOOR,
    DEFAULT_CATALOG,
    TEST_ARCHETYPES,
    Applicability,
    DiscoveryStage,
    FailureMode,
    ModeCatalog,
    coverage,
    facts_from_spec,
)
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity
from conftest import library_sources


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
    catalog = ModeCatalog(modes=(_mode("fretting", tested_by=("fretting-fatigue",)),))
    report = coverage(
        _card(("anything", CheckStatus.PASS)), {"element": "bolted_connection"}, catalog=catalog
    )
    (entry,) = report.entries
    assert not entry.addressed and entry.planned
    assert report.addressed() == () and report.unaddressed() == ()
    assert report.planned() == (entry,)
    assert not report.complete()
    assert "no check; left to fretting fatigue test" in str(report)


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


def test_a_mode_renders_its_stage_and_its_citation() -> None:
    mode = _mode(
        "bolt self-loosening",
        stage=DiscoveryStage.QUALIFICATION,
        citation="Junker, SAE 690055 (1969)",
    )
    rendered = str(mode)
    assert rendered.startswith("bolt self-loosening (qualification): ")
    assert rendered.endswith("[Junker, SAE 690055 (1969)]")
    # The description is what a reader acts on, so it is in the line and not just the id.
    assert mode.description in rendered


def test_an_applicability_says_what_it_keys_on() -> None:
    assert str(Applicability(elements=("bolted_connection",))) == "elements bolted_connection"
    assert str(Applicability(dissimilar_metals=True)) == "a declared dissimilar-metal pair"
    both = Applicability(
        interfaces=("clamped",), environments=("thermal_cycling",), dissimilar_metals=True
    )
    assert str(both) == (
        "interfaces clamped; environments thermal_cycling; a declared dissimilar-metal pair"
    )
    # Every shipped mode's applicability renders as something a reader can check.
    for mode in DEFAULT_CATALOG.modes:
        assert str(mode.applicability).strip(), f"{mode.id} renders an empty applicability"


def test_every_key_the_catalogue_uses_is_one_a_document_can_declare() -> None:
    """A mode keyed on a word nothing can state is a mode that can never apply.

    The catalogue and the Spec IR carry two vocabularies — interface kinds and environments
    — and a typo in either would not fail anything: the mode would simply never match, and
    the report would say "does not apply" about a design that is exposed to it.
    """
    from anvilate.screening import element_registry
    from anvilate.spec import Environment, InterfaceKind

    kinds = {kind.value for kind in InterfaceKind}
    environments = {environment.value for environment in Environment}
    elements = set(element_registry())
    for mode in DEFAULT_CATALOG.modes:
        applies = mode.applicability
        assert set(applies.interfaces) <= kinds, f"{mode.id} keys on {applies.interfaces}"
        assert set(applies.environments) <= environments, (
            f"{mode.id} keys on {applies.environments}"
        )
        assert set(applies.elements) <= elements, f"{mode.id} keys on {applies.elements}"
    # And the vocabularies are actually used: a catalogue keyed only on elements would pass
    # the three assertions above while the two new IR facts reached nothing.
    keyed = {
        "interfaces": any(mode.applicability.interfaces for mode in DEFAULT_CATALOG.modes),
        "environments": any(mode.applicability.environments for mode in DEFAULT_CATALOG.modes),
        "dissimilar": any(mode.applicability.dissimilar_metals for mode in DEFAULT_CATALOG.modes),
        "elements": any(mode.applicability.elements for mode in DEFAULT_CATALOG.modes),
    }
    assert all(keyed.values()), f"these applicability keys are unused: {keyed}"


def test_a_document_that_states_its_joint_and_its_environment_reaches_those_modes() -> None:
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    document = """
anvilate_spec: "1.12.0"
name: coastal_bracket
description: A bracket bolted to an aluminium rail beside the sea.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
environment: marine
interfaces:
  - {type: standard_component, ref: "M12", tag: rail_bolts, kind: bolted_face,
     mating_material: {ref: AA-6061-T6}}
constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}
"""
    spec = load_spec_yaml(document)
    facts = facts_from_spec(spec)
    # Dissimilarity is derived from the two material references, not ticked by the author.
    assert facts["dissimilar_metals"] is True
    assert facts["interfaces"] == ("bolted_face",)
    report = coverage(screen_spec(spec), facts)
    assert {entry.mode.id for entry in report.entries} == {
        "galvanic corrosion",
        "fretting at a clamped interface",
        "a fastener no tool reaches in the state it is driven",
    }
    # The same joint in the same material is not a dissimilar pair.
    same = load_spec_yaml(document.replace("AA-6061-T6", "ASTM-A36"))
    assert facts_from_spec(same)["dissimilar_metals"] is False
    assert "galvanic corrosion" not in {
        entry.mode.id for entry in coverage(screen_spec(same), facts_from_spec(same)).entries
    }


def test_a_fact_the_document_omits_is_absent_and_never_false() -> None:
    from anvilate.spec import load_spec_yaml

    spec = load_spec_yaml(
        """
anvilate_spec: "1.12.0"
name: plain
description: A part whose document says nothing about its joints or its environment.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
"""
    )
    facts = facts_from_spec(spec)
    assert "environment" not in facts and "dissimilar_metals" not in facts
    assert facts["interfaces"] == ()


def _weld_check(name: str, **overrides: object) -> ScorecardEntry:
    declared: dict[str, object] = {
        "applied_cycles": [2.0e5],
        "stress_ranges": [Quantity.parse("60 MPa")],
        "detail_category": Quantity.parse("71 MPa"),
    }
    declared.update(overrides)
    return weld_fatigue_scorecard(name, **declared)  # type: ignore[arg-type]


def test_a_shipped_check_addresses_a_mode_by_declaring_it_not_by_its_name() -> None:
    """The weld check's name carries the member's; the binding must not depend on it."""
    facts = {"element": "welded_connection"}
    for name in ("gusset weld toe", "anything a caller calls it"):
        report = coverage(Scorecard(entries=(_weld_check(name),)), facts)
        assert [entry.checks for entry in report.entries] == [(name,)]
        assert report.complete()


def test_a_declared_check_that_did_not_run_still_addresses_nothing() -> None:
    """No detail category: the check declares the mode, and did not run, so it is a gap."""
    entry = _weld_check("gusset weld toe", detail_category=None)
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.addresses == ("weld toe fatigue",)
    report = coverage(Scorecard(entries=(entry,)), {"element": "welded_connection"})
    assert [(item.mode.id, item.checks) for item in report.entries] == [("weld toe fatigue", ())]
    assert not report.complete()


def test_a_check_naming_one_mode_twice_is_refused() -> None:
    with pytest.raises(ValidationError, match="names one failure mode twice"):
        ScorecardEntry(
            name="weld",
            status=CheckStatus.PASS,
            detail="as screened",
            addresses=("weld toe fatigue", "weld toe fatigue"),
        )


_SRC = Path(__file__).resolve().parents[1] / "src" / "anvilate"


def _declared_modes() -> list[tuple[str, str]]:
    """Every mode id a shipped check declares, as (where, id), resolved rather than matched.

    A declaration is an ``addresses=`` keyword or an ``"addresses"`` key in an update dict.
    Its value must be a tuple of string literals, or a module-level name bound to one; any
    other expression fails here rather than being skipped, because a declaration this gate
    cannot read is one it cannot check.
    """
    found: list[tuple[str, str]] = []
    for path, tree in library_sources():
        constants = {
            target.id: node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        values: list[ast.expr] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                values += [kw.value for kw in node.keywords if kw.arg == "addresses"]
            elif isinstance(node, ast.Dict):
                values += [
                    value
                    for key, value in zip(node.keys, node.values, strict=True)
                    if isinstance(key, ast.Constant) and key.value == "addresses"
                ]
        for value in values:
            where = f"{path.relative_to(_SRC)}:{value.lineno}"
            if isinstance(value, ast.Name):
                assert value.id in constants, f"{where}: '{value.id}' is not a module constant"
                value = constants[value.id]
            assert isinstance(value, ast.Tuple), f"{where}: not a literal tuple of mode ids"
            for element in value.elts:
                assert isinstance(element, ast.Constant) and isinstance(element.value, str), (
                    f"{where}: a mode id that is not a string literal"
                )
                found.append((where, element.value))
    return found


def test_every_mode_a_shipped_check_declares_is_one_the_catalogue_carries() -> None:
    """A check claiming a mode nobody catalogues would report coverage of nothing."""
    declared = _declared_modes()
    assert len({where for where, _ in declared}) >= 4, declared  # the weld check's four paths
    known = {mode.id for mode in DEFAULT_CATALOG.modes}
    unknown = sorted((where, mode) for where, mode in declared if mode not in known)
    assert not unknown, f"checks declare modes the catalogue does not carry: {unknown}"


def test_every_shipped_mode_resolves_to_a_check_or_a_test_and_every_test_to_a_mode() -> None:
    """Both directions: a mode reached by nothing is invisible, and a test no mode names is
    an archetype nobody can be sent to."""
    declared = {mode for _, mode in _declared_modes()}
    archetypes = {archetype.key for archetype in TEST_ARCHETYPES}
    for mode in DEFAULT_CATALOG.modes:
        assert mode.id in declared or mode.addressed_by or mode.tested_by, (
            f"{mode.id}: no check declares it and no test reaches it"
        )
        assert set(mode.tested_by) <= archetypes, f"{mode.id} is left to an undefined test"
    named = {key for mode in DEFAULT_CATALOG.modes for key in mode.tested_by}
    assert archetypes <= named, f"archetypes no mode is left to: {sorted(archetypes - named)}"
    assert len(archetypes) == len(TEST_ARCHETYPES), "two archetypes share a key"


def test_a_mode_left_to_a_test_nobody_defined_is_refused() -> None:
    catalog = ModeCatalog(modes=(_mode("loosening", tested_by=("shake it and see",)),))
    with pytest.raises(ValueError, match="shake it and see"):
        coverage(_card(), {"element": "bolted_connection"}, catalog=catalog)


def test_a_caller_can_supply_the_archetype_its_own_mode_is_left_to() -> None:
    from anvilate.verification import VerificationArchetype, VerificationMethod

    rig = VerificationArchetype(
        key="shaker-rig",
        method=VerificationMethod.TEST,
        title="the team's shaker rig",
        citation="the team's own procedure",
    )
    catalog = ModeCatalog(modes=(_mode("loosening", tested_by=("shaker-rig",)),))
    report = coverage(_card(), {"element": "bolted_connection"}, catalog=catalog, archetypes=[rig])
    assert "left to the team's shaker rig" in str(report)


def test_nothing_applying_is_not_complete_coverage() -> None:
    """Vacuously every applicable mode is addressed when none applies — the silent green."""
    card = _card(("joint bolt shear", CheckStatus.PASS))
    empty = coverage(card, {"element": "bolted_connection"}, catalog=ModeCatalog())
    assert not empty.complete()
    assert "catalogue is empty" in str(empty)
    unreached = coverage(card, {"element": "shallow_footing"})
    assert unreached.applicable == 0 and unreached.catalog_size >= 5
    assert not unreached.complete()
    assert "not that this design has no failure modes" in str(unreached)


def _uncatalogued() -> list[str]:
    path = Path(__file__).resolve().parents[1] / "docs" / "api" / "uncatalogued-elements.txt"
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_every_shipped_element_reaches_a_mode_or_is_recorded_as_debt() -> None:
    """Task 4.3: a floor per element class, as a ratchet that only shrinks.

    An element the catalogue knows nothing about reports that no mode applies — true, and
    never complete coverage — but the gap must be written down rather than discovered.
    """
    from anvilate.screening import element_registry

    elements = sorted(element_registry())
    assert len(elements) >= 25, f"the element registry holds only {len(elements)}"
    reached = {e for e in elements if DEFAULT_CATALOG.applicable({"element": e})}
    recorded = _uncatalogued()
    assert len(set(recorded)) == len(recorded), "an element is recorded twice"
    unrecorded = sorted(set(elements) - reached - set(recorded))
    assert not unrecorded, f"elements no mode reaches and nobody recorded: {unrecorded}"
    stale = sorted(set(recorded) & reached)
    assert not stale, f"recorded as uncatalogued and now reached — delete the lines: {stale}"
    gone = sorted(set(recorded) - set(elements))
    assert not gone, f"recorded elements the registry no longer ships: {gone}"
    # The ratchet: this may only go down. Lower it when a mode lands.
    assert len(recorded) <= 23, f"the uncatalogued list grew to {len(recorded)}"
    assert len(reached) >= 6


def test_each_machinery_check_declares_the_mode_it_addresses() -> None:
    """The four modes the machinery pack answers are bound by the checks, not by names."""
    from anvilate.screening import element_registry

    registry = element_registry()
    for element, mode in (
        ("transmission_shaft", "shaft fatigue at a stress raiser"),
        ("spur_gear_mesh", "gear tooth surface pitting"),
        ("rolling_bearing", "rolling-contact fatigue of a bearing"),
        ("helical_compression_spring", "coil spring buckling"),
    ):
        assert element in registry
        (applicable,) = DEFAULT_CATALOG.applicable({"element": element})
        assert applicable.id == mode
    declared_in_machinery = {
        mode for where, mode in _declared_modes() if where.startswith("packs/machinery.py")
    }
    assert declared_in_machinery == {
        "shaft fatigue at a stress raiser",
        "gear tooth surface pitting",
        "rolling-contact fatigue of a bearing",
        "coil spring buckling",
    }


def _declaration_inventory() -> tuple[dict[str, str], list[str]]:
    path = Path(__file__).resolve().parents[1] / "docs" / "api" / "failure-mode-declarations.txt"
    declares: dict[str, str] = {}
    none: list[str] = []
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line == "#" or line.startswith("# "):
            continue
        if line.startswith("## "):
            section = line
            continue
        if section == "## declares":
            screen, _, mode = line.partition(" -> ")
            declares[screen] = mode
        else:
            none.append(line)
    return declares, none


def _declared_in_body(module: str, screen: str) -> set[str]:
    """Mode ids declared through `addresses` inside ``screen``'s own body."""
    source = Path(__file__).resolve().parents[1] / "src" / "anvilate"
    (path,) = [
        p
        for p in (
            source / "analysis" / f"{module}.py",
            source / "packs" / f"{module}.py",
            source / f"{module}.py",
        )
        if p.exists()
    ]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    (function,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == screen]
    found: set[str] = set()
    for node in ast.walk(function):
        values: list[ast.expr] = []
        if isinstance(node, ast.Call):
            values += [kw.value for kw in node.keywords if kw.arg == "addresses"]
        elif isinstance(node, ast.Dict):
            values += [
                v
                for k, v in zip(node.keys, node.values, strict=True)
                if isinstance(k, ast.Constant) and k.value == "addresses"
            ]
        for value in values:
            if isinstance(value, ast.Name):
                value = constants[value.id]
            assert isinstance(value, ast.Tuple)
            found |= {e.value for e in value.elts if isinstance(e, ast.Constant)}
    return found


def test_every_screen_declares_its_modes_or_is_recorded_as_declaring_none() -> None:
    """Task 4.2: the inventory covers every public screen, and the declared half is true."""
    levers = Path(__file__).resolve().parents[1] / "docs" / "api" / "repair-levers.txt"
    screens = {
        line.split(" ->")[0].strip()
        for line in levers.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    declares, none = _declaration_inventory()
    assert len(screens) >= 60, f"the screen inventory holds only {len(screens)}"
    listed = [*declares, *none]
    assert len(set(listed)) == len(listed), "a screen is recorded twice"
    assert set(listed) == screens, sorted(set(listed) ^ screens)
    known = {mode.id for mode in DEFAULT_CATALOG.modes}
    for screen, mode in declares.items():
        assert mode in known, f"{screen} declares '{mode}', which the catalogue does not carry"
        module, _, function = screen.partition(".")
        assert mode in _declared_in_body(module, function), (
            f"{screen} is recorded as declaring '{mode}' and its body does not"
        )
    for screen in none:
        module, _, function = screen.partition(".")
        try:
            declared = _declared_in_body(module, function)
        except ValueError:  # a screen defined outside analysis/ and packs/
            continue
        assert not declared, f"{screen} declares {declared} and is recorded as declaring none"
    # The ratchet: this may only go down.
    # 59, not 56: keepouts.screen_keepouts and optomechanics.obscuration_scorecard each
    # measure a geometry conflict in the design, and assembly.screen_inspectability a gap in
    # verification, none of them a way the part fails in service, and no applicability key
    # can say "a part declaring a keepout", "a part a beam passes" or "a toleranced
    # dimension". Declaring a mode for any would be one the catalogue invented to shrink this.
    assert len(none) <= 59, f"the declares-none list grew to {len(none)}"
    # The page quotes both counts, and it said "five" while fourteen screens declared one.
    page = (Path(__file__).resolve().parents[1] / "docs" / "failure-mode-coverage.md").read_text()
    stated = f"{len(declares)} screens declare a mode today, and {len(none)} declare none"
    assert stated in " ".join(page.split()), f"docs/failure-mode-coverage.md should say: {stated}"
