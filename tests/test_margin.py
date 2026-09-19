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
