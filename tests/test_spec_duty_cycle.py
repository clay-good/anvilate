"""A Design Spec declares its duty cycle, and the card reports damage by event.

The spec's scenario: a suspension bracket's pothole, cornering and braking events. On a
Basquin curve σ_a = 1000 MPa · N^−0.1, so N = (σ_a / 1000 MPa)^−10, worked by hand:

- pothole, range 400 MPa (σ_a 200): N = 9,765,625; 1,000 per life → 1.024e−4
- cornering, range 200 MPa (σ_a 100): N = 1e10; 100,000 per life → 1e−5
- braking, range 300 MPa (σ_a 150): N = 1.7342e8; 20,000 per life → 1.1533e−4

Total 2.2757e−4 per life: it passes, and braking (50.7%) drives it over the pothole (45.0%).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from anvilate._models import parse_yaml
from anvilate.scorecard import CheckStatus
from anvilate.screening import screen_spec
from anvilate.spec import SpecValidationError, parse_spec

_PLATE = parse_yaml(
    (Path(__file__).resolve().parents[1] / "examples" / "parts" / "mounting_plate.spec.yaml")
    .read_text(encoding="utf-8")
)  # fmt: skip


def _mpa(v: float) -> dict:
    return {"magnitude": v, "unit": "MPa"}


def _event(name: str, stress_range: float, per_life: float) -> dict:
    return {"name": name, "blocks": [{"range": _mpa(stress_range), "count": 1}],
            "occurrences_per_life": per_life, "source": f"{name} survey"}  # fmt: skip


def _document(scale: float = 1.0) -> dict:
    document = copy.deepcopy(_PLATE)
    document["duty_cycle"] = {
        "life": {"value": {"magnitude": 240000, "unit": "km"}, "source": "vehicle program"},
        "events": [_event("pothole", 400, 1000 * scale), _event("cornering", 200, 1e5 * scale),
                   _event("braking", 300, 2e4 * scale)],
        "curve": {"coefficient": _mpa(1000), "exponent": -0.1, "source": "coupon S-N fit"},
    }  # fmt: skip
    return document


def _entry(document: dict):
    card = screen_spec(parse_spec(document))
    return next(e for e in card.entries if e.name == "duty-cycle fatigue")


def test_the_entry_names_the_event_that_drives_the_damage():
    entry = _entry(_document())
    assert entry.status is CheckStatus.PASS
    assert entry.derivation is not None
    assert entry.derivation.result.value == pytest.approx(1.024e-4 + 1e-5 + 1.15330e-4, rel=1e-4)
    assert "braking drives it" in entry.detail
    assert "braking 0.000115 (51%)" in entry.detail and "pothole 0.000102 (45%)" in entry.detail
    assert "240000 km (vehicle program)" in entry.detail


def test_a_duty_cycle_that_uses_up_its_life_fails():
    entry = _entry(_document(scale=1e4))  # damage 2.28 per life
    assert entry.status is CheckStatus.FAIL and "braking drives it" in entry.detail


def test_a_measured_history_is_counted_by_rainflow():
    document = _document()
    document["duty_cycle"]["events"][0] = {
        "name": "pothole", "history": [_mpa(v) for v in (0, 200, -200, 200, -200, 0)],
        "occurrences_per_life": 1000, "source": "strain-gauge trace, run 14",
    }  # fmt: skip
    entry = _entry(document)
    assert entry.status is CheckStatus.PASS and "pothole" in entry.detail


def test_a_life_may_be_a_number_of_cycles():
    document = _document()
    document["duty_cycle"]["life"]["value"] = {"magnitude": 1e7, "unit": "dimensionless"}
    assert _entry(document).status is CheckStatus.PASS


def test_a_spec_with_a_duty_cycle_round_trips():
    spec = parse_spec(_document())
    assert parse_spec(spec.model_dump(mode="json")) == spec


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda d: d["events"][0].update(blocks=[], history=[_mpa(0), _mpa(100)]),
            "pothole' has a history of 2 reversals",
        ),
        (lambda d: d["events"][1].update(name="pothole"), "names pothole more than once"),
        (lambda d: d["events"][0].update(history=[_mpa(1)]), "states both of history and blocks"),
        (lambda d: d.update(correction="goodman"), "Goodman's correction and no ultimate_strength"),
        (lambda d: d["life"].update(value={"magnitude": 3, "unit": "MPa"}), "a life is a time"),
        (lambda d: d["events"][0]["blocks"][0].update(count=0), "positive number of cycles"),
    ],
)
def test_a_duty_cycle_that_cannot_be_counted_is_refused(change, message):
    document = _document()
    change(document["duty_cycle"])
    with pytest.raises((SpecValidationError, ValueError), match=message):
        parse_spec(document)
