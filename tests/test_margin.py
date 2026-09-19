"""The margin ledger: conservatism recorded, attributed, multiplied out and never removed."""

from __future__ import annotations

import inspect
import types
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvilate import margin
from anvilate.margin import (
    MarginAction,
    MarginEntry,
    MarginKind,
    MarginLedger,
    MarginStack,
    ledger_for,
    physics_limited,
)
from anvilate.spec import load_spec_yaml, parse_spec

_BENDING = "bracket bending stress"


def _entry(label: str, kind: MarginKind, value: float, /, **overrides: object) -> MarginEntry:
    fields: dict[str, object] = {
        "label": label,
        "kind": kind,
        "value": value,
        "quantity": _BENDING,
        "action": MarginAction.LOWERS_CAPACITY,
        "origin": "check: bracket bending",
        "authority": "AISC 360-22 §F1",
    }
    fields.update(overrides)
    return MarginEntry(**fields)  # type: ignore[arg-type]


def _five_factor_bracket() -> MarginLedger:
    return MarginLedger(
        entries=(
            _entry("ASD factor", MarginKind.CODE_REQUIRED, 1.67),
            _entry(
                "project factor",
                MarginKind.USER_ELECTED,
                1.2,
                authority="user election: engineering judgment",
            ),
            _entry(
                "A-basis allowable",
                MarginKind.STATISTICAL_BASIS,
                1.15,
                origin="materials record 6061-T6",
                authority="MMPDS-17 A-basis",
            ),
            _entry(
                "load growth",
                MarginKind.CONTINGENCY,
                1.1,
                action=MarginAction.RAISES_DEMAND,
                origin="spec: loads.growth",
                authority="company practice DP-104",
            ),
            MarginEntry.rounding(
                label="plate thickness",
                nominal=9.1,
                delivered=9.525,
                quantity=_BENDING,
                origin="stock snap",
                authority="ASTM B209 stock gauge list",
            ),
        )
    )


def test_five_defensible_factors_report_their_product() -> None:
    # The defect class the ledger exists to expose: each factor alone is fine, the product
    # is the number nobody states. It must be the product, itemized.
    stack = _five_factor_bracket().stack(_BENDING)
    expected = 1.67 * 1.2 * 1.15 * 1.1 * (9.525 / 9.1)
    assert stack.cumulative == pytest.approx(expected, rel=1e-12)
    assert stack.physics_limited == pytest.approx(1.67, rel=1e-12)
    assert stack.cumulative == pytest.approx(stack.physics_limited * stack.elected, rel=1e-12)
    assert stack.multiplication() == f"1.67 x 1.2 x 1.15 x 1.1 x 1.047 = {expected:.4g}"
    assert f"x{expected:.4g}" in str(stack)


def test_removing_a_factor_changes_the_ledger_not_only_the_verdict() -> None:
    full = _five_factor_bracket()
    fewer = MarginLedger(entries=full.entries[:-1])
    assert fewer.stack(_BENDING).cumulative < full.stack(_BENDING).cumulative
    assert len(fewer.stack(_BENDING).entries) == 4


def test_physics_limited_utilization_removes_only_elected_factors() -> None:
    stack = _five_factor_bracket().stack(_BENDING)
    delivered = 0.9
    limited = stack.physics_limited_utilization(delivered)
    assert limited == pytest.approx(delivered / (1.2 * 1.15 * 1.1), rel=1e-12)
    assert limited < delivered
    assert {e.kind for e in stack.elected_entries()} == set(MarginKind) - {
        MarginKind.CODE_REQUIRED,
        MarginKind.DERATING,
    }
    with pytest.raises(ValueError, match="finite non-negative"):
        stack.physics_limited_utilization(float("nan"))


@pytest.mark.parametrize("field", ["origin", "authority", "label", "quantity"])
@pytest.mark.parametrize("blank", ["", "   "])
def test_an_unattributed_factor_is_refused(field: str, blank: str) -> None:
    with pytest.raises(ValidationError, match="must state"):
        _entry("factor", MarginKind.USER_ELECTED, 1.5, **{field: blank})


@pytest.mark.parametrize("value", [0.99, 0.0, -1.5, float("nan"), float("inf")])
def test_a_factor_that_is_not_conservative_is_refused(value: float) -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        _entry("factor", MarginKind.CODE_REQUIRED, value)


def test_a_unit_factor_is_recorded_honestly() -> None:
    assert _entry("nothing", MarginKind.DERATING, 1.0).value == 1.0


def test_code_required_and_elected_never_render_identically() -> None:
    code = _entry("design factor", MarginKind.CODE_REQUIRED, 1.5)
    elected = _entry("design factor", MarginKind.USER_ELECTED, 1.5)
    assert str(code) != str(elected)
    assert "code-required" in str(code) and "user-elected" in str(elected)


def test_every_kind_renders_distinctly() -> None:
    rendered = {str(_entry("f", kind, 1.5)) for kind in MarginKind}
    assert len(rendered) == len(MarginKind)


def test_a_kind_added_without_a_description_fails_at_import() -> None:
    # Adding a kind must break the consumers loudly. Build the module again from its own
    # source with one more member and require the import itself to refuse.
    source = inspect.getsource(margin)
    anchor = '    DERATING = "derating"\n'
    assert source.count(anchor) == 1
    mutant = source.replace(anchor, anchor + '    SAFETY_STOCK = "safety_stock"\n')
    module = types.ModuleType("anvilate._margin_mutant")
    module.__package__ = "anvilate"
    with pytest.raises(RuntimeError, match="safety_stock"):
        exec(compile(mutant, "margin_mutant", "exec"), module.__dict__)


def test_the_same_kind_from_two_origins_is_a_possible_double_count() -> None:
    ledger = MarginLedger(
        entries=(
            _entry(
                "growth",
                MarginKind.CONTINGENCY,
                1.1,
                origin="spec: loads.growth",
                action=MarginAction.RAISES_DEMAND,
            ),
            # Differently worded, same kind, same quantity: still caught.
            _entry(
                "future-proofing allowance",
                MarginKind.CONTINGENCY,
                1.25,
                origin="module: bracket pack",
                action=MarginAction.RAISES_DEMAND,
            ),
            _entry("ASD", MarginKind.CODE_REQUIRED, 1.67),
        )
    )
    (double,) = ledger.double_counts()
    assert double.kind is MarginKind.CONTINGENCY
    assert double.combined == pytest.approx(1.1 * 1.25, rel=1e-12)
    assert "spec: loads.growth" in str(double) and "module: bracket pack" in str(double)
    # Named, never resolved: both entries stay in the product.
    assert ledger.stack(_BENDING).cumulative == pytest.approx(1.1 * 1.25 * 1.67, rel=1e-12)


def test_same_kind_from_one_origin_or_on_different_quantities_is_not_a_double_count() -> None:
    same_origin = MarginLedger(
        entries=(
            _entry("a", MarginKind.CONTINGENCY, 1.1),
            _entry("b", MarginKind.CONTINGENCY, 1.2),
        )
    )
    other_quantity = MarginLedger(
        entries=(
            _entry("a", MarginKind.CONTINGENCY, 1.1, origin="one"),
            _entry("b", MarginKind.CONTINGENCY, 1.2, origin="two", quantity="weld shear"),
        )
    )
    assert same_origin.double_counts() == ()
    assert other_quantity.double_counts() == ()


def test_the_dominant_entry_is_named_and_ties_are_kept() -> None:
    stack = _five_factor_bracket().stack(_BENDING)
    (dominant,) = stack.dominant()
    assert dominant.label == "ASD factor"

    tied = MarginStack(
        quantity=_BENDING,
        entries=(
            _entry("first", MarginKind.CODE_REQUIRED, 1.5),
            _entry("second", MarginKind.USER_ELECTED, 1.5),
            _entry("small", MarginKind.ROUNDING, 1.05),
        ),
    )
    assert [e.label for e in tied.dominant()] == ["first", "second"]
    assert "dominant (tied): first and second" in str(tied)


def test_an_unfactored_quantity_says_so() -> None:
    stack = _five_factor_bracket().stack("anchor bolt tension")
    assert stack.entries == ()
    assert stack.cumulative == 1.0
    assert stack.dominant() == ()
    assert str(stack) == "anchor bolt tension: no conservatism recorded"
    assert stack.multiplication() == "no conservatism recorded on anchor bolt tension"
    assert str(MarginLedger()) == "margin ledger: no conservatism recorded"


def test_rounding_is_recorded_with_nominal_and_delivered() -> None:
    entry = MarginEntry.rounding(
        label="wall",
        nominal=4.0,
        delivered=5.0,
        quantity="hoop stress",
        origin="stock snap",
        authority="ASME B36.10M schedule list",
    )
    assert entry.kind is MarginKind.ROUNDING
    assert entry.value == pytest.approx(1.25, rel=1e-12)
    assert "4 -> 5" in entry.label
    with pytest.raises(ValueError, match="unsafe direction"):
        MarginEntry.rounding(
            label="wall",
            nominal=5.0,
            delivered=4.0,
            quantity="hoop stress",
            origin="o",
            authority="a",
        )
    with pytest.raises(ValueError, match="positive finite nominal"):
        MarginEntry.rounding(
            label="wall", nominal=0.0, delivered=4.0, quantity="q", origin="o", authority="a"
        )


def test_the_ledger_round_trips_and_groups_by_quantity() -> None:
    ledger = _five_factor_bracket().with_entry(
        _entry("weld phi", MarginKind.CODE_REQUIRED, 1.33, quantity="weld shear")
    )
    assert ledger.quantities() == (_BENDING, "weld shear")
    assert len(ledger) == 6
    assert MarginLedger.model_validate_json(ledger.model_dump_json()) == ledger
    assert "weld shear" in str(ledger)


def test_an_entry_refuses_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _entry("f", MarginKind.CODE_REQUIRED, 1.5, authorty="typo")


def test_the_docs_page_prints_what_the_ledger_computes() -> None:
    # docs/margin-ledger.md argues from figures in its comments; run its block and hold
    # every one of them to the ledger it builds.
    page = (Path(__file__).parents[1] / "docs" / "margin-ledger.md").read_text()
    block = page.split("```python\n", 1)[1].split("```", 1)[0]
    scope: dict[str, object] = {}
    exec(block, scope)
    stack = scope["stack"]
    ledger = scope["ledger"]
    assert isinstance(stack, MarginStack) and isinstance(ledger, MarginLedger)
    assert f'"{stack.multiplication()}"' in block
    assert f"# {stack.physics_limited:.3g}  " in block
    assert f"# {stack.elected:.4g} " in block
    assert f"# {stack.physics_limited_utilization(0.62):.2g}  " in block
    assert [e.label for e in stack.dominant()] == ["ASD factor"]
    (double,) = ledger.double_counts()
    assert f"x{double.combined:.4g} combined" in block
    assert f'"{ledger.stack("anchor bolt tension")}"' in block


_PADEYE = Path(__file__).parents[1] / "examples" / "padeye.spec.yaml"
_DECLARED = """constraints:
  min_safety_factor: {value: 2.0, origin: user_stated}
  margins:
    - {label: ASME BTH-1 design category B, kind: code_required, value: 2.0,
       quantity: padeye tension, action: lowers_capacity,
       origin: "spec: constraints.min_safety_factor", authority: "ASME BTH-1-2020 §1-5"}
    - {label: sling angle allowance, kind: contingency_or_growth, value: 1.15,
       quantity: padeye tension, action: raises_demand,
       origin: "spec: loads", authority: "company practice LP-7"}
"""


def _padeye_declaring(constraints: str) -> str:
    text = _PADEYE.read_text()
    (line,) = [ln for ln in text.splitlines() if ln.startswith("constraints:")]
    return text.replace(line + "\n", constraints)


def test_a_spec_declares_its_margins_and_they_read_back_as_a_ledger() -> None:
    spec = load_spec_yaml(_padeye_declaring(_DECLARED))
    ledger = MarginLedger(entries=spec.constraints.margins)
    stack = ledger.stack("padeye tension")
    assert stack.cumulative == pytest.approx(2.0 * 1.15, rel=1e-12)
    assert stack.physics_limited == pytest.approx(2.0, rel=1e-12)
    assert parse_spec(spec.model_dump(mode="json")) == spec


def test_a_spec_without_margins_still_loads_and_declares_none() -> None:
    assert load_spec_yaml(_PADEYE.read_text()).constraints.margins == ()


@pytest.mark.parametrize(
    ("broken", "refusal"),
    [
        ('authority: "company practice LP-7"', 'authority: "  "'),
        ("value: 1.15", "value: 0.9"),
        ("kind: contingency_or_growth", "kind: hunch"),
        ('origin: "spec: loads"', 'origin: "spec: loads", orign: typo'),
    ],
)
def test_a_spec_margin_that_is_not_one_is_refused(broken: str, refusal: str) -> None:
    assert _DECLARED.count(broken) == 1
    with pytest.raises(ValueError):
        load_spec_yaml(_padeye_declaring(_DECLARED.replace(broken, refusal)))


def test_rounding_is_not_divided_out_of_a_utilization_computed_at_the_delivered_size() -> None:
    # A utilization computed on the stock plate already contains the rounding: it is in the
    # geometry, not a multiplier on the demand. Dividing it out would report the delivered
    # plate as less utilized than it is at its own code factors.
    stack = _five_factor_bracket().stack(_BENDING)
    multipliers = 1.2 * 1.15 * 1.1
    assert stack.physics_limited_utilization(0.9) == pytest.approx(0.9 / multipliers, rel=1e-12)
    assert stack.elected == pytest.approx(multipliers * (9.525 / 9.1), rel=1e-12)


def test_a_statistical_basis_below_the_typical_value_is_recorded_as_elected_conservatism() -> None:
    """Margin ledger 2.2: designing to a floor under the scatter is a factor, and says so."""
    from anvilate.margin import MarginEntry, MarginKind, MarginLedger

    entry = MarginEntry.statistical_basis(
        label="6061-T6 yield",
        typical=276.0,
        allowable=240.0,
        basis="specification minimum",
        quantity="bracket bending",
        origin="material record",
        authority="the producer's guaranteed minimum",
    )
    assert entry.kind is MarginKind.STATISTICAL_BASIS
    assert entry.value == pytest.approx(276 / 240)
    assert not entry.code_required
    stack = MarginLedger(entries=(entry,)).stack("bracket bending")
    assert stack.cumulative == pytest.approx(1.15)
    assert stack.physics_limited == pytest.approx(1.0)
    assert "specification minimum: 276 typical, 240 allowable" in str(entry)
    with pytest.raises(ValueError, match="not a margin"):
        MarginEntry.statistical_basis(
            label="x",
            typical=240.0,
            allowable=276.0,
            basis="B-basis",
            quantity="q",
            origin="o",
            authority="a",
        )


def test_every_factor_a_check_applied_is_in_the_ledger_attributed_by_its_source() -> None:
    """Margin ledger 2.1: a factor cannot be applied without being recorded."""
    from anvilate.margin import MarginKind, ledger_for
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
    from anvilate.spec import Origin, Provenanced

    class _Constraints:
        margins = ()
        min_safety_factor = Provenanced(value=2.0, origin=Origin.USER_STATED)

    class _Spec:
        constraints = _Constraints()

    def check(name: str, required: float, reference: str | None):  # type: ignore[no-untyped-def]
        return ScorecardEntry(
            name=name,
            status=CheckStatus.PASS,
            detail="as screened",
            safety_factor=required * 1.2,
            required_safety_factor=required,
            reference=reference,
        )

    card = Scorecard(
        entries=(
            check("bracket bending", 2.0, "AISC 360-22 F11"),
            check("weld throat", 1.67, "AISC 360-22 J2.4"),
            check("pin bearing", 1.5, None),
            check("buckling", 0.9, "AISC 360-22 E3"),  # below 1 applied nothing
        )
    )
    ledger = ledger_for(card, _Spec())
    by_quantity = {entry.quantity: entry for entry in ledger.entries}
    assert set(by_quantity) == {"bracket bending", "weld throat", "pin bearing"}
    assert by_quantity["bracket bending"].kind is MarginKind.USER_ELECTED
    assert by_quantity["weld throat"].kind is MarginKind.CODE_REQUIRED
    assert by_quantity["weld throat"].authority == "AISC 360-22 J2.4"
    assert by_quantity["pin bearing"].kind is MarginKind.USER_ELECTED
    assert "uncited default" in by_quantity["pin bearing"].authority


def test_across_the_shipped_specs_no_applied_factor_escapes_the_ledger() -> None:
    """Margin ledger 4.1, measured on what the library screens: every applied factor is recorded.

    Read from the cards the shipped example specs screen to, with a floor, so a screen that
    stops carrying its required factor, or a ledger that stops reading it, fails here.
    """
    from pathlib import Path

    from anvilate.margin import ledger_for
    from anvilate.screening import screen_spec
    from anvilate.spec import load_spec_yaml

    applied = 0
    for path in sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.spec.yaml")):
        spec = load_spec_yaml(path.read_text(encoding="utf-8"))
        card = screen_spec(spec)
        recorded = {entry.quantity for entry in ledger_for(card, spec).entries}
        for entry in card.entries:
            if entry.required_safety_factor is not None and entry.required_safety_factor > 1:
                applied += 1
                assert entry.name in recorded, f"{path.name}: {entry.name} applied a factor"
    assert applied >= 5, f"the shipped specs applied only {applied} factors"


def test_a_check_is_re_judged_at_its_code_required_factors_alone() -> None:
    """Margin ledger 3.2: the verdict with only what a code obliges, beside the delivered one."""
    from anvilate.margin import MarginAction, MarginEntry, MarginKind, MarginLedger, physics_limited
    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    card = Scorecard(
        entries=(
            ScorecardEntry(
                name="weld throat",
                status=CheckStatus.FAIL,
                detail="as screened",
                safety_factor=1.8,
                required_safety_factor=2.5,
            ),
            ScorecardEntry(name="bearing", status=CheckStatus.PASS, detail="no factor"),
        )
    )
    ledger = MarginLedger(
        entries=(
            MarginEntry(
                label="AISC weld factor",
                kind=MarginKind.CODE_REQUIRED,
                value=1.67,
                quantity="weld throat",
                action=MarginAction.LOWERS_CAPACITY,
                origin="check: weld throat",
                authority="AISC 360-22 J2.4",
            ),
            MarginEntry(
                label="company practice",
                kind=MarginKind.USER_ELECTED,
                value=1.5,
                quantity="weld throat",
                action=MarginAction.LOWERS_CAPACITY,
                origin="spec: constraints",
                authority="company practice DP-104",
            ),
        )
    )
    (weld,) = physics_limited(card, ledger)
    assert weld.code_required == pytest.approx(1.67)
    assert weld.passes_at_code  # fails with every margin, passes at the code minimum
    assert "at code minimum: 1.8 against x1.67, passes; judged at x2.5" in str(weld)


# --- factors applied inside a capacity (margin-ledger 4.1, 4.2, 6.4) -----------------------

_UNITY_EXCLUSIONS = "docs/api/unity-checks-without-inside-factors.txt"


def _unity_checks() -> list[tuple[str, str, bool]]:
    """Every check judged at a literal required factor of 1.0, by `(module, function)`.

    Structural, not by name: a `from_safety_factor` or `strength_scorecard` call whose
    `required` is the constant 1.0 has put any margin it applies inside its capacity. Whether
    the enclosing function records it is read the same way — an `applied_factors` key or
    keyword anywhere in that function.
    """
    import ast

    from conftest import library_sources

    source = Path(__file__).parents[1] / "src" / "anvilate"
    found = []
    for path, tree in library_sources():
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            unity = records = False
            for node in ast.walk(function):
                if isinstance(node, ast.Call):
                    callee = getattr(node.func, "attr", getattr(node.func, "id", None))
                    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
                    required = keywords.get("required")
                    if (
                        callee in ("from_safety_factor", "strength_scorecard")
                        and isinstance(required, ast.Constant)
                        and required.value == 1.0
                    ):
                        unity = True
                    if "applied_factors" in keywords:
                        records = True
                if isinstance(node, ast.Constant) and node.value == "applied_factors":
                    records = True
            if unity:
                found.append((str(path.relative_to(source)), function.name, records))
    return found


def _unity_exclusions() -> dict[tuple[str, str], str]:
    text = (Path(__file__).parents[1] / _UNITY_EXCLUSIONS).read_text()
    excused = {}
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            module, function, cause = (part.strip() for part in line.split("|", 2))
            excused[(module, function)] = cause
    return excused


def test_a_check_judged_at_one_records_the_factor_inside_it_or_says_why_there_is_none():
    """A 1.0 verdict hides its margin in the capacity; the ledger can only see a recorded one."""
    checks = _unity_checks()
    # The floor: a detector that stopped matching would otherwise report a clean library.
    assert len(checks) >= 12, f"the sweep found only {len(checks)} checks judged at 1.0"
    recording = [(module, function) for module, function, records in checks if records]
    assert len(recording) >= 4, recording
    excused = _unity_exclusions()
    assert all(cause for cause in excused.values()), "every exclusion states its cause"
    silent = sorted(
        (module, function)
        for module, function, records in checks
        if not records and (module, function) not in excused
    )
    assert not silent, (
        f"these checks are judged at 1.0 and record no factor applied inside their capacity: "
        f"{silent}. Record it in `applied_factors`, or list the site in {_UNITY_EXCLUSIONS} "
        "with the reason there is none"
    )
    sites = {(module, function) for module, function, _ in checks}
    stale = sorted(set(excused) - sites)
    assert not stale, f"these lines in {_UNITY_EXCLUSIONS} match no check any more: {stale}"
    both = sorted(set(excused) & set(recording))
    assert not both, f"these record a factor and are also excused as having none: {both}"


def _pile(**overrides):
    from anvilate.packs.geotechnical import DrivenPile
    from anvilate.units import Quantity

    fields = {
        "diameter": Quantity(magnitude=0.4, unit="m"),
        "length": Quantity(magnitude=15.0, unit="m"),
        "undrained_shear_strength": Quantity(magnitude=60.0, unit="kPa"),
        "adhesion_factor": 0.8,
        "applied_load": Quantity(magnitude=300.0, unit="kN"),
    }
    return DrivenPile(**{**fields, **overrides})


def test_the_ledger_itemizes_the_factor_a_pile_applies_inside_its_capacity():
    from anvilate.analysis.geotechnical import (
        pile_end_bearing_capacity,
        pile_skin_friction_capacity,
    )
    from anvilate.packs.geotechnical import screen_driven_pile

    pile = _pile(factor_of_safety=3.0)
    card = screen_driven_pile(pile)
    (entry,) = card.entries
    ledger = ledger_for(card, None)
    (factor,) = [item for item in ledger if "factor of safety" in item.label]
    assert factor.value == 3.0
    assert factor.kind is MarginKind.USER_ELECTED
    assert factor.origin == "element: factor_of_safety (declared)"
    # 6.4: the recorded factor is the one the capacity used. Put back on the raw basis, the
    # delivered margin is exactly the ultimate capacity over the load, computed here from the
    # analysis functions — so a factor removed from (or changed in) the capacity arithmetic
    # and left in the record, or the reverse, fails this line.
    ultimate = (
        pile_skin_friction_capacity(
            adhesion_factor=pile.adhesion_factor,
            undrained_shear_strength=pile.undrained_shear_strength,
            diameter=pile.diameter,
            length=pile.length,
        )
        .to("kN")
        .magnitude
        + pile_end_bearing_capacity(
            undrained_shear_strength=pile.undrained_shear_strength, diameter=pile.diameter
        )
        .to("kN")
        .magnitude
    )
    (limited,) = physics_limited(card, ledger)
    assert limited.delivered == pytest.approx(ultimate / 300.0, rel=1e-9)
    assert limited.required == pytest.approx(3.0)
    assert entry.safety_factor == pytest.approx(ultimate / 300.0 / 3.0, rel=1e-9)


def test_the_ledger_follows_the_factor_and_a_default_says_it_is_one():
    from anvilate.packs.geotechnical import screen_driven_pile

    card = screen_driven_pile(_pile())
    (factor,) = [item for item in ledger_for(card, None) if "factor of safety" in item.label]
    assert factor.value == 2.5
    assert factor.origin == "element: factor_of_safety (the screen's default)"
    assert "uncited" in factor.authority
    # A factor that moves nothing is not a margin, and nothing is recorded for it.
    bare = screen_driven_pile(_pile(factor_of_safety=1.0))
    assert not [item for item in ledger_for(bare, None) if "factor of safety" in item.label]


def test_a_code_design_factor_inside_an_allowable_is_itemized_as_code_required():
    from anvilate.analysis.lifting_device import DesignCategory, bth1_member_scorecard
    from anvilate.scorecard import Scorecard
    from anvilate.units import Quantity

    entry = bth1_member_scorecard(
        "hook block",
        stress=Quantity(magnitude=80.0, unit="MPa"),
        allowable=Quantity(magnitude=120.0, unit="MPa"),
        category=DesignCategory.B,
    )
    (factor,) = ledger_for(Scorecard(entries=(entry,)), None)
    assert factor.kind is MarginKind.CODE_REQUIRED
    assert factor.value == DesignCategory.B.design_factor
    assert "BTH-1 §3-1.3" in factor.authority


def test_an_applied_factor_renders_its_value_its_authority_and_its_origin():
    from anvilate.scorecard import AppliedFactor

    cited = AppliedFactor(
        label="design factor N_d", value=2.0, origin="design category A", authority="BTH-1 §3-1.3"
    )
    uncited = cited.model_copy(update={"authority": None})
    assert str(cited) == "design factor N_d 2 (BTH-1 §3-1.3; from design category A)"
    assert str(uncited) == "design factor N_d 2 (uncited; from design category A)"
    with pytest.raises(ValidationError, match="at least 1"):
        AppliedFactor(label="relief", value=0.8, origin="element: x")


def test_a_factor_inside_the_capacity_is_printed_wherever_the_verdict_is():
    """ "1.08 vs required minimum 1.00" read as 8% margin on a pile carrying 3.24 on its
    ultimate capacity; the factor was in the JSON and the ledger and on no line a person read."""
    from anvilate.cli import _render
    from anvilate.packs.geotechnical import screen_driven_pile
    from anvilate.report import CalculationReport, ReportSection

    card = screen_driven_pile(_pile(factor_of_safety=3.0))
    (entry,) = card.entries
    inside = "inside the capacity: factor of safety 3"
    assert inside in str(entry)
    assert inside in _render("pile", card)
    report = CalculationReport(title="pile", sections=(ReportSection(entry=entry),))
    assert "1.00 (× 3 inside)" in report.to_html()
    # And nothing is said where nothing is inside.
    bare = screen_driven_pile(_pile(factor_of_safety=1.0))
    assert "inside the capacity" not in str(bare.entries[0]) + _render("pile", bare)
