"""The needs report: what the build needs next, ordered by leverage and never by severity."""

from __future__ import annotations

import functools

import pytest
from pydantic import ValidationError

from anvilate.needs import LEVERAGE_IS_NOT_IMPORTANCE, NeedsReport, needs_report
from anvilate.scorecard import CheckStatus, Need, Scorecard, ScorecardEntry, ValueSource


def _need(declaration: str, /, **fields: object) -> Need:
    declared: dict[str, object] = {
        "declaration": declaration,
        "takes": f"the value {declaration} states",
        "sources": (ValueSource.USER,),
    }
    declared.update(fields)
    return Need(**declared)  # type: ignore[arg-type]


def _blocked(name: str, *needs: Need) -> ScorecardEntry:
    return ScorecardEntry(
        name=name,
        status=CheckStatus.NOT_EVALUATED,
        detail="could not run",
        needs=needs,
    )


def test_eleven_blocked_checks_behind_four_declarations_are_four_items() -> None:
    # The defect class this report exists to remove: a wall of red with no next move.
    damping = _need("environment.damping")
    orientation = _need("element_params.orientation")
    factor = _need("constraints.min_safety_factor")
    fill = _need("element_params.fill_condition")
    entries = [
        _blocked("check 1", damping, orientation),
        _blocked("check 2", damping),
        _blocked("check 3", damping),
        _blocked("check 4", damping),
        _blocked("check 5", damping),
        _blocked("check 6", orientation),
        _blocked("check 7", orientation),
        _blocked("check 8", factor),
        _blocked("check 9", factor),
        _blocked("check 10", fill),
        _blocked("check 11", fill),
    ]
    report = needs_report(Scorecard(entries=tuple(entries)))
    assert len(report) == 4
    assert [item.need.declaration for item in report.items] == [
        "environment.damping",
        "element_params.orientation",
        "constraints.min_safety_factor",
        "element_params.fill_condition",
    ]
    assert [item.leverage for item in report.items] == [5, 3, 2, 2]
    # The entries each item would resolve are named, not counted.
    damping_item = report.items[0]
    assert damping_item.unblocks == ("check 1", "check 2", "check 3", "check 4", "check 5")


def test_the_order_follows_the_counts_and_says_it_is_not_importance() -> None:
    report = needs_report(
        Scorecard(
            entries=(
                _blocked("secondary a", _need("b.secondary")),
                _blocked("secondary b", _need("b.secondary")),
                _blocked("the governing check", _need("a.critical")),
            )
        )
    )
    # Leverage, not severity: the item behind the governing check is second.
    assert [item.need.declaration for item in report.items] == ["b.secondary", "a.critical"]
    rendered = str(report)
    assert LEVERAGE_IS_NOT_IMPORTANCE in rendered
    assert "unblocks 2: secondary a, secondary b" in rendered
    assert "unblocks 1: the governing check" in rendered


def test_equal_leverage_is_reported_as_a_tie() -> None:
    report = needs_report(
        Scorecard(
            entries=(
                _blocked("one", _need("a.first")),
                _blocked("two", _need("b.second")),
                _blocked("three", _need("c.third"), _need("d.fourth")),
            )
        )
    )
    (group,) = report.tied()
    assert len(group) == 4  # every item unblocks exactly one check
    assert str(report).count("(tied)") == 4

    mixed = needs_report(
        Scorecard(entries=(_blocked("one", _need("a")), _blocked("two", _need("a"), _need("b"))))
    )
    assert [len(group) for group in mixed.tied()] == [1, 1]
    assert "(tied)" not in str(mixed)


def test_a_passing_card_with_a_gap_still_reports_it() -> None:
    card = Scorecard(
        entries=(
            ScorecardEntry(name="ran", status=CheckStatus.PASS, detail="fine"),
            _blocked("did not run", _need("constraints.min_safety_factor")),
        )
    )
    assert card.status is CheckStatus.NOT_EVALUATED  # the card is honest either way
    report = needs_report(card)
    assert len(report) == 1
    assert report.items[0].unblocks == ("did not run",)


def test_a_card_with_nothing_missing_says_so() -> None:
    card = Scorecard(entries=(ScorecardEntry(name="ran", status=CheckStatus.PASS, detail="fine"),))
    report = needs_report(card)
    assert len(report) == 0
    assert str(report) == "needs: every declaration the screens reached for was supplied"
    assert str(NeedsReport()) == str(report)


@pytest.mark.parametrize("status", [CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.OVER_MARGIN])
def test_a_check_that_ran_cannot_name_a_need(status: CheckStatus) -> None:
    # Otherwise the report sends a reader to supply a value that would change nothing.
    with pytest.raises(ValidationError, match="a check that ran had what it needed"):
        ScorecardEntry(
            name="ran",
            status=status,
            detail="fine",
            safety_factor=2.0,
            required_safety_factor=1.5,
            needs=(_need("constraints.min_safety_factor"),),
        )


@pytest.mark.parametrize(
    ("fields", "match"),
    [
        ({"sources": ()}, "at least 1 item"),
        ({"sources": (ValueSource.USER, ValueSource.USER)}, "names a source twice"),
        ({"units": ("mm",)}, "and no dimension"),
        ({"takes": "  "}, "must state"),
        ({"declaration": ""}, "must state"),
    ],
)
def test_a_malformed_need_is_refused(fields: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _need("constraints.min_safety_factor", **fields)


def test_a_need_renders_its_units_and_where_a_value_comes_from() -> None:
    need = _need(
        "constraints.min_safety_factor",
        dimension="dimensionless",
        units=("", "1"),
        sources=(ValueSource.STANDARD, ValueSource.USER),
    )
    assert "from standard, user statement" in str(need)
    length = _need("element_params.thickness", dimension="[length]", units=("mm", "in"))
    assert "in mm or in" in str(length)


def test_the_screens_own_refusals_carry_their_needs() -> None:
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    bare = load_spec_yaml(
        """
anvilate_spec: "1.3.0"
name: bare
description: A part with almost nothing declared.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: cnc_milling}
acceptance: {tiers: [T1_analytical, T2_dfm]}
"""
    )
    report = needs_report(screen_spec(bare))
    assert [item.need.declaration for item in report.items] == [
        "element_type",
        "element_params",
        "dimensions",
    ]
    # Every item names a real field of the document, so the next action is one edit.
    from anvilate.spec.ir import DesignSpec

    for item in report.items:
        root = item.need.declaration.split(".")[0].split("[")[0]
        assert root in DesignSpec.model_fields

    declared = load_spec_yaml(
        """
anvilate_spec: "1.3.0"
name: lug
description: A lifting lug with its element declared and no safety factor.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
element_type: lifting_lug
element_params:
  name: padeye
  material: ASTM-A36
  width: {magnitude: 120.0, unit: mm}
  hole_diameter: {magnitude: 40.0, unit: mm}
  thickness: {magnitude: 20.0, unit: mm}
  load: {magnitude: 60.0, unit: kN}
"""
    )
    # Declaring the element moves the gap on: now it is the factor the screen is judged by.
    factor = needs_report(screen_spec(declared))
    assert [item.need.declaration for item in factor.items] == ["constraints.min_safety_factor"]


# --- the ratchet on refusals that state no need ----------------------------------------

_SCREENING = "src/anvilate/screening.py"
_EXCLUSIONS = "docs/api/refusals-without-needs.txt"


def _refusal_sites(module: str = _SCREENING) -> list[tuple[str, str, int, bool]]:
    """Every NOT_EVALUATED scorecard entry built in ``module``.

    `(function, entry name as written, line, whether it carries needs=)`. Read off the AST
    rather than by grepping: a refusal is a call with a status keyword, and a text search
    for the status would match the enum's every other mention.

    Three spellings of "this entry is not evaluated", because the premise is the entry and
    not one way of writing it: the status as a keyword (`status=CheckStatus.NOT_EVALUATED`,
    or a conditional containing it), a status held in a local the function assigns it to
    (`status = CheckStatus.NOT_EVALUATED` above a single `ScorecardEntry(status=status)`),
    and an update dict (`entry.model_copy(update={"status": ...})`). The first detector saw
    only the keyword, and three optomechanics screens that choose their status in a branch
    were invisible to it.
    """
    import ast
    from pathlib import Path

    from conftest import parsed_source

    # Shared with the suite's other sweeps and only read here.
    tree = parsed_source(Path(__file__).parents[1] / module)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def enclosing(node: ast.AST) -> ast.AST | None:
        current = parents.get(node)
        while current is not None:
            if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
                return current
            current = parents.get(current)
        return None

    def names_refusal(expr: ast.AST) -> bool:
        return any(
            isinstance(node, ast.Attribute) and node.attr == "NOT_EVALUATED"
            for node in ast.walk(expr)
        )

    held: dict[ast.AST | None, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and names_refusal(node.value):
            targets = {
                name.id
                for target in node.targets
                for name in ast.walk(target)
                if isinstance(name, ast.Name)
            }
            held.setdefault(enclosing(node), set()).update(targets)

    def label_of(name: ast.AST | None) -> str:
        if isinstance(name, ast.Constant):
            return str(name.value)
        if isinstance(name, ast.JoinedStr):
            return "".join(
                part.value if isinstance(part, ast.Constant) else f"{{{ast.unparse(part.value)}}}"
                for part in name.values
            )
        return ast.unparse(name) if name is not None else "?"

    def place(node: ast.AST) -> tuple[str, set[str]]:
        function = enclosing(node)
        return (function.name if function is not None else "<module>"), held.get(function, set())

    sites = []
    for node in ast.walk(tree):
        # `cls(...)` is how ScorecardEntry's own constructors build an entry.
        builders = (
            {"ScorecardEntry", "cls"} if module.endswith("scorecard.py") else {"ScorecardEntry"}
        )
        if isinstance(node, ast.Call) and builders & {
            getattr(node.func, "id", None),
            getattr(node.func, "attr", None),
        }:
            keywords = {keyword.arg: keyword.value for keyword in node.keywords}
            status = keywords.get("status")
            if status is None:
                continue
            where, locals_ = place(node)
            refused = names_refusal(status) or any(
                isinstance(name, ast.Name) and name.id in locals_ for name in ast.walk(status)
            )
            if refused:
                sites.append(
                    (where, label_of(keywords.get("name")), node.lineno, "needs" in keywords)
                )
        elif isinstance(node, ast.Dict):
            entries = {
                key.value: value
                for key, value in zip(node.keys, node.values, strict=True)
                if isinstance(key, ast.Constant)
            }
            if "status" in entries and names_refusal(entries["status"]):
                sites.append((place(node)[0], "{update}", node.lineno, "needs" in entries))
    return sites


def _excused() -> dict[tuple[str, str], str]:
    from pathlib import Path

    text = (Path(__file__).parents[1] / _EXCLUSIONS).read_text()
    excused = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        function, name, cause = (part.strip() for part in line.split("|", 2))
        excused[(function, name)] = cause
    return excused


def test_every_refusal_states_its_need_or_says_why_it_cannot() -> None:
    """A refusal that names no declaration leaves a reader with nothing to do next.

    The population floor is what stops this passing by finding nothing: the detector looks
    for one call shape in one module, and a refactor that moved the refusals elsewhere would
    otherwise turn the gate green by emptying it.
    """
    sites = _refusal_sites()
    assert len(sites) >= 30, f"the sweep found only {len(sites)} refusals in {_SCREENING}"
    excused = _excused()
    silent = sorted(
        {(function, name) for function, name, _line, has_needs in sites if not has_needs}
        - set(excused)
    )
    assert not silent, (
        f"these refusals name no declaration and are not excused in {_EXCLUSIONS}: {silent}. "
        "Attach `needs=` naming what the check was waiting on, or add a line stating why no "
        "declaration would resolve it."
    )
    stated = {(function, name) for function, name, _line, _has in sites}
    stale = sorted({site for site in excused if ":" not in site[0]} - stated)
    assert not stale, f"{_EXCLUSIONS} excuses refusals that no longer exist: {stale}"
    for site, cause in excused.items():
        assert len(cause.split()) >= 8, f"{site} is excused without a stated cause"


# Refusals outside the screening module that state no need yet, per module: the backlog, as
# a ceiling that only comes down. A module absent here must state a need at every refusal or
# excuse it by name in the exclusions file. Wiring one lowers the count and this test says to
# lower the ceiling with it, so the number cannot drift back up unobserved.
_UNWIRED_CEILING: dict[str, int] = {}


@functools.cache
def _library_refusals() -> dict[str, list[tuple[str, str, int, bool]]]:
    from pathlib import Path

    root = Path(__file__).parents[1]
    return {
        module: sites
        for path in sorted((root / "src" / "anvilate").rglob("*.py"))
        if (module := path.relative_to(root).as_posix()) != _SCREENING
        and (sites := _refusal_sites(module))
    }


def test_every_refusal_in_the_library_states_its_need_or_is_on_the_backlog() -> None:
    """The screening module's gate, for every other module that builds a refusal.

    The screening gate read one file, so a screen anywhere else could refuse with a sentence
    and nothing for the needs report to rank — 74 of them did, including every optomechanics
    screen an environment profile feeds. Each refusal here either states its need, is excused
    by name with a cause (the same exclusions file, keyed `path:function`), or is counted in
    its module's backlog ceiling, which may only come down.
    """
    refusals = _library_refusals()
    total = sum(len(sites) for sites in refusals.values())
    assert total >= 70, f"the library sweep found only {total} refusals outside screening"
    assert len(refusals) >= 20, f"refusals found in only {len(refusals)} modules"
    excused = _excused()
    counts = {}
    for module, sites in refusals.items():
        prefix = module.removeprefix("src/anvilate/")
        unwired = [
            (function, name)
            for function, name, _line, has_needs in sites
            if not has_needs and (f"{prefix}:{function}", name) not in excused
        ]
        counts[module] = len(unwired)
    over = {
        module: (count, _UNWIRED_CEILING.get(module, 0))
        for module, count in counts.items()
        if count > _UNWIRED_CEILING.get(module, 0)
    }
    assert not over, (
        f"refusals that name no declaration, over each module's backlog ceiling "
        f"(found, allowed): {over}. Attach `needs=` naming what the check was waiting on, or "
        f"excuse the site in {_EXCLUSIONS} with its cause."
    )
    under = {
        module: (counts.get(module, 0), ceiling)
        for module, ceiling in _UNWIRED_CEILING.items()
        if counts.get(module, 0) < ceiling
    }
    assert not under, (
        f"these modules state more needs than their ceiling allows for (found, ceiling): "
        f"{under}. Lower `_UNWIRED_CEILING` to the found count, so the backlog cannot regrow."
    )
    qualified = {
        (f"src/anvilate/{key.partition(':')[0]}", key.partition(":")[2], name)
        for key, name in excused
        if ":" in key
    }
    present = {
        (module, function, name)
        for module, sites in refusals.items()
        for function, name, _line, _has in sites
    }
    stale = sorted(qualified - present)
    assert not stale, f"{_EXCLUSIONS} excuses refusals that no longer exist: {stale}"


def test_every_need_a_module_declares_names_units_of_its_dimension() -> None:
    """A need's units are what the report tells a reader to write, so each must parse, and
    to the dimension the need states — `K/W` for a thermal resistance, not `W/K`."""
    import importlib
    import pkgutil

    import anvilate
    from anvilate.scorecard import Need
    from anvilate.units import Quantity

    needs: list[Need] = []
    for info in pkgutil.walk_packages(anvilate.__path__, "anvilate."):
        try:
            module = importlib.import_module(info.name)
        except ImportError:  # an optional runtime this environment lacks
            continue
        for value in vars(module).values():
            candidates = (
                value.values()
                if isinstance(value, dict)
                else (value if isinstance(value, tuple) else (value,))
            )
            needs.extend(item for item in candidates if isinstance(item, Need))
    with_units = {need.declaration: need for need in needs if need.units}
    assert len(with_units) >= 12, f"only {len(with_units)} declared needs carry units"
    for need in with_units.values():
        for unit in need.units:
            parsed = Quantity(magnitude=1.0, unit=unit)
            # pint carries an angle as dimensionless, and `has_dimension` cannot parse that
            # word, so a dimensionless need is compared by the quantity's own dimensionality.
            matches = (
                parsed.dimensionality == "dimensionless"
                if need.dimension == "dimensionless"
                else parsed.has_dimension(need.dimension)
            )
            assert matches, (
                f"the need for '{need.declaration}' is {need.dimension} and offers {unit!r}"
            )


def test_the_ratchet_only_turns_one_way() -> None:
    """The count of refusals that state a need cannot fall without this failing.

    A floor rather than an equality, so wiring another refusal is an ordinary green change
    and un-wiring one is not.
    """
    wired = sum(1 for *_rest, has_needs in _refusal_sites() if has_needs)
    assert wired >= 9, f"{wired} refusals state their needs; nine did when this was written"


def test_the_page_counts_are_the_sweeps_own() -> None:
    # Counts in prose expire. These two are held against the sweep that produced them.
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "declaration-needs.md").read_text()
    sites = _refusal_sites()
    wired = sum(1 for *_rest, has_needs in sites if has_needs)
    words = {
        4: "Four",
        5: "Five",
        6: "Six",
        7: "Seven",
        8: "Eight",
        9: "Nine",
        10: "Ten",
        11: "Eleven",
        12: "Twelve",
    }
    tens = {30: "thirty", 32: "thirty-two", 33: "thirty-three", 35: "thirty-five", 40: "forty"}
    assert f"{words[wired]} of the screening module's {tens[len(sites)]} refusals" in page
    assert f"the {words[wired].lower()} screening refusals that state a need today" in page


def test_the_library_counts_on_the_page_are_the_sweeps_own() -> None:
    from pathlib import Path

    page = " ".join(
        (Path(__file__).parents[1] / "docs" / "declaration-needs.md").read_text().split()
    )
    refusals = _library_refusals()
    total = sum(len(sites) for sites in refusals.values())
    wired = sum(has_needs for sites in refusals.values() for *_rest, has_needs in sites)
    # Sites, not lines: one line can excuse several refusals in one function.
    excusals = _excused()
    excused = sum(
        1
        for module, sites in refusals.items()
        for function, name, _line, has_needs in sites
        if not has_needs
        and (f"{module.removeprefix('src/anvilate/')}:{function}", name) in excusals
    )
    backlog = sum(_UNWIRED_CEILING.values())
    assert total == wired + excused + backlog, (total, wired, excused, backlog)
    assert f"the library has {total} more, and {wired} state a need today" in page
    assert backlog == 0 and "The backlog is empty" in page, backlog
    assert f"The other {excused} are excused by name" in page


def test_supplying_the_top_item_unblocks_the_checks_it_promised() -> None:
    """The report's claim is asserted, not decorative: it says which checks an item would
    unblock, and supplying that item has to make exactly those checks run."""
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    lug = """
anvilate_spec: "1.3.0"
name: lug
description: A lifting lug with no declared safety factor.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
element_type: lifting_lug
element_params:
  name: padeye
  material: ASTM-A36
  width: {magnitude: 120.0, unit: mm}
  hole_diameter: {magnitude: 40.0, unit: mm}
  thickness: {magnitude: 20.0, unit: mm}
  load: {magnitude: 60.0, unit: kN}
"""
    before = screen_spec(load_spec_yaml(lug))
    report = needs_report(before)
    (top,) = report.items  # one item, and it promises one check
    assert top.need.declaration == "constraints.min_safety_factor"
    promised = set(top.unblocks)
    assert promised == {entry.name for entry in before.not_evaluated()}

    supplied = load_spec_yaml(
        lug + "constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}\n"
    )
    after = screen_spec(supplied)
    # Every check the item promised now produces a verdict, and nothing it promised is
    # still waiting: the number in the report was the number of screens it unblocks.
    still_blocked = {entry.name for entry in after.not_evaluated()}
    assert not (promised & still_blocked)
    assert len(after.entries) > len(before.entries) - len(promised)
    assert needs_report(after).items == ()


def test_what_applies_to_a_partial_spec_says_what_runs_and_what_the_rest_need() -> None:
    """Interaction-quality 5.1: capability discoverable before commitment."""
    from anvilate.needs import ScreenState, what_applies
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    spec = load_spec_yaml(
        """
anvilate_spec: "1.14.0"
name: partial
description: A part with no element declared yet.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
"""
    )
    applies = what_applies(screen_spec(spec))
    (waiting,) = applies.of(ScreenState.NEEDS)
    assert waiting.name == "T1 analytical"
    assert waiting.needs == ("element_type", "element_params")
    assert [s.name for s in applies.of(ScreenState.RUNS_NOW)] == ["material resolution"]
    rendered = str(applies)
    assert rendered.startswith("2 screens apply (1 runs now, 1 needs, 0 deferred)")
    assert "T1 analytical: needs element_type, element_params" in rendered


def test_a_deferred_screen_and_a_reasoned_gap_render_as_themselves() -> None:
    from anvilate.needs import ApplicableScreen, ScreenState, what_applies
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    card = Scorecard(
        entries=(
            ScorecardEntry(name="dfm", status=CheckStatus.OUT_OF_DEPTH, detail="deferred"),
            ScorecardEntry(name="t0", status=CheckStatus.NOT_EVALUATED, detail="no solid built"),
        )
    )
    applies = what_applies(card)
    assert [s.state for s in applies.screens] == [ScreenState.DEFERRED, ScreenState.NEEDS]
    assert str(applies.screens[0]) == "dfm: deferred by the declared screening depth"
    assert str(applies.screens[1]) == "t0: needs no solid built"
    assert str(ApplicableScreen(name="x", state=ScreenState.RUNS_NOW)) == "x: runs now"


def _analysis_refusals():  # type: ignore[no-untyped-def]
    from anvilate import analysis as a
    from anvilate.units import Quantity

    q = Quantity.parse
    return [
        (
            a.nds_bending_scorecard(
                "joist", bending_stress=q("8 MPa"), adjusted_bending_value=None
            ),
            ["adjusted_bending_value"],
        ),
        (
            a.frequency_scorecard("mode", frequency=q("40 Hz"), min_frequency=None),
            ["min_frequency"],
        ),
        (a.deflection_scorecard("sag", deflection=q("3 mm"), limit=None), ["limit"]),
        (
            a.weld_fatigue_scorecard(
                "toe", applied_cycles=[1e6], stress_ranges=[q("60 MPa")], detail_category=None
            ),
            ["detail_category"],
        ),
        (
            a.weld_fatigue_scorecard(
                "toe", applied_cycles=[0], stress_ranges=[q("60 MPa")], detail_category=q("71 MPa")
            ),
            ["applied_cycles"],
        ),
        (a.embodied_carbon_scorecard("carbon", estimate=None), ["estimate"]),
        (a.dsm_scorecard("stud", demand=q("10 kN"), strength=None), ["strength"]),
        (
            a.aluminum_compression_scorecard("strut", demand_stress=q("50 MPa"), strength=None),
            ["strength"],
        ),
        (a.fad_scorecard("flaw", assessment=None), ["assessment"]),
        (
            a.isolator_selection_scorecard(
                "mount",
                forcing_frequency=q("25 Hz"),
                target_transmissibility=0.1,
                selected_static_deflection=None,
            ),
            ["selected_static_deflection"],
        ),
        (
            a.half_sine_shock_scorecard(
                "drop",
                peak_acceleration=q("300 m/s**2"),
                pulse_duration=q("11 ms"),
                natural_frequency=q("60 Hz"),
                allowable_acceleration=None,
            ),
            ["allowable_acceleration"],
        ),
        (
            a.bth1_fatigue_scorecard(
                "hook", service_class=a.ServiceClass.CLASS_2, allowable_stress_range=q("100 MPa")
            ),
            ["stress_range"],
        ),
    ]


def test_an_analysis_screen_that_stops_names_the_argument_it_stopped_for() -> None:
    """The AST gate proves each refusal carries `needs=`; this proves what it carries. Each
    screen is called with exactly one input missing and must name that input and no other —
    the BTH-1 case supplies one of its two ranges and must ask only for the other."""
    from anvilate.scorecard import CheckStatus

    cases = _analysis_refusals()
    assert len(cases) >= 12
    for entry, declarations in cases:
        assert entry.status is CheckStatus.NOT_EVALUATED, entry
        assert [need.declaration for need in entry.needs] == declarations, entry.name


def test_a_design_basis_check_names_the_citation_it_could_not_judge() -> None:
    """The same property as the analysis screens, for a citation list: none at all asks for
    references, and one naming no edition asks for the edition."""
    from anvilate.scorecard import CheckStatus
    from anvilate.standards.effectivity import DesignBasis, design_basis_scorecard

    empty = design_basis_scorecard("basis", basis=DesignBasis(), references=[])
    unversioned = design_basis_scorecard("basis", basis=DesignBasis(), references=["ASCE 7"])
    for entry, declarations in (
        (empty, ["references"]),
        (unversioned, ["references[].edition"]),
    ):
        assert entry.status is CheckStatus.NOT_EVALUATED, entry.detail
        assert [need.declaration for need in entry.needs] == declarations
