"""Tests for the machinery pack: TransmissionShaft and its three-check Shigley screen."""

from __future__ import annotations

import pytest

from anvilate.analysis import shaft_diameter_de_goodman
from anvilate.packs.machinery import TransmissionShaft, screen_shaft
from anvilate.scorecard import CheckStatus, Direction
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _shaft(**overrides) -> TransmissionShaft:
    fields = {
        "diameter": _q("40 mm"),
        "bending_moment": _q("250 N*m"),
        "torque": _q("400 N*m"),
        "yield_strength": _q("370 MPa"),
        "length": _q("600 mm"),
        "shear_modulus": _q("79.3 GPa"),
        "allowable_twist": _q("0.5 degree"),
        "endurance_limit": _q("200 MPa"),
        "ultimate_strength": _q("690 MPa"),
    }
    fields.update(overrides)
    return TransmissionShaft(**fields)


def _named(card):
    return {entry.name: entry for entry in card.entries}


def test_the_three_checks_disagree_and_twist_governs_this_shaft():
    """The reason the screen is one card: static, fatigue and twist give three answers.

    A 40 mm shaft at these loads is comfortable on yield (5.4) and on fatigue (3.6) and
    fails on windup (0.72). Sized on the static check alone it would have shipped.
    """
    card = screen_shaft(_shaft())
    assert card.status is CheckStatus.FAIL
    names = _named(card)
    assert set(names) == {
        "combined bending and torsion",
        "torsional twist",
        "rotating-shaft fatigue",
    }
    assert names["combined bending and torsion"].status is CheckStatus.PASS
    assert names["rotating-shaft fatigue"].status is CheckStatus.PASS
    assert names["torsional twist"].status is CheckStatus.FAIL
    assert all(e.reference is not None and "Shigley" in e.reference for e in card.entries)

    # Absolute pins, so a moved constant is caught by more than a verdict. σ' =
    # 32·√(250000² + 0.75·400000²)/(π·40³) = 67.99102 MPa against S_y = 370; θ =
    # 32·400000·600/(π·79300·40⁴) rad = 0.6899551°; the fatigue factor is (40/d₁)³.
    assert names["combined bending and torsion"].safety_factor == pytest.approx(
        5.441895001346463, rel=1e-9
    )
    assert names["torsional twist"].safety_factor == pytest.approx(0.7246848416725796, rel=1e-9)
    assert names["rotating-shaft fatigue"].safety_factor == pytest.approx(
        3.586203507897734, rel=1e-9
    )


def test_a_comfortable_shaft_passes_every_check():
    card = screen_shaft(_shaft(diameter=_q("60 mm")))
    assert card.status is CheckStatus.PASS
    assert card.passed


@pytest.mark.parametrize(
    ("check", "shaft"),
    [
        # Each shaft is built to fail ONE of the three, so every lever is reached: a short
        # stubby shaft fails on stress, a long slender one on windup, and a soft-surfaced
        # one on fatigue while yielding is still comfortable.
        ("combined bending and torsion", _shaft(diameter=_q("22 mm"), length=_q("60 mm"))),
        ("torsional twist", _shaft()),
        (
            "rotating-shaft fatigue",
            _shaft(diameter=_q("32 mm"), length=_q("60 mm"), endurance_limit=_q("90 MPa")),
        ),
    ],
)
def test_screen_shaft_names_the_diameter_that_clears_each_failing_check(check, shaft):
    """The lever's value is re-screened, not just asserted — the base plate's lesson.

    A solved hint that lands exactly on the boundary comes back FAIL when the screen
    recomputes the safety factor down a different arithmetic path, so the only assertion
    worth making about a corrective value is that the part rebuilt at it passes.
    """
    entry = _named(screen_shaft(shaft))[check]
    assert entry.status is CheckStatus.FAIL
    hint = entry.repair_hint
    assert hint is not None
    assert hint.parameter == "diameter"
    assert hint.direction is Direction.INCREASE
    assert hint.unit == "mm"
    assert hint.corrective_value is not None

    repaired = _named(
        screen_shaft(
            shaft.model_copy(
                update={"diameter": Quantity(magnitude=hint.corrective_value, unit="mm")}
            )
        )
    )[check]
    assert repaired.status is CheckStatus.PASS
    # And it is the LEAST such diameter: a hair under it fails. Without this the hint could
    # name any large number and still pass the line above.
    under = _named(
        screen_shaft(
            shaft.model_copy(
                update={"diameter": Quantity(magnitude=hint.corrective_value * 0.999, unit="mm")}
            )
        )
    )[check]
    assert under.status is CheckStatus.FAIL


def test_the_three_levers_do_not_agree_on_one_diameter():
    """One knob, three answers — which is the whole reason a shaft is screened as a card."""
    shaft = _shaft(diameter=_q("20 mm"), length=_q("900 mm"), endurance_limit=_q("110 MPa"))
    values = {
        entry.name: entry.repair_hint.corrective_value
        for entry in screen_shaft(shaft).entries
        if entry.repair_hint is not None
    }
    assert len(values) == 3, values
    assert len({round(v, 6) for v in values.values()}) == 3, values
    # The largest is the shaft. Stated as an ordering rather than three numbers, because
    # the point is that the governing check is not knowable from the loads alone.
    assert max(values, key=values.__getitem__) == "torsional twist"


def test_the_fatigue_factor_is_the_cube_of_the_diameter_ratio():
    """`n_f = (d/d₁)³` is an identity of the DE-Goodman form, so it is checked against it.

    The criterion ships as an inverse only. Turning it into a safety factor relies on the
    whole bracket going as 1/d³, and that claim is worth holding against the inverse itself
    rather than against a number this test copied from the screen.
    """
    shaft = _shaft()
    entry = _named(screen_shaft(shaft))["rotating-shaft fatigue"]
    factor = entry.safety_factor
    assert factor is not None
    solved = shaft_diameter_de_goodman(
        alternating_bending_moment=shaft.bending_moment,
        mean_torque=shaft.torque,
        endurance_limit=shaft.endurance_limit,
        ultimate_strength=shaft.ultimate_strength,
        required_safety_factor=factor,
    )
    assert solved.to("mm").magnitude == pytest.approx(40.0, rel=1e-9)


@pytest.mark.parametrize(
    ("check", "dropped", "missing"),
    [
        ("torsional twist", "length", "length"),
        ("torsional twist", "shear_modulus", "shear_modulus"),
        ("torsional twist", "allowable_twist", "allowable_twist"),
        ("rotating-shaft fatigue", "endurance_limit", "endurance_limit"),
        ("rotating-shaft fatigue", "ultimate_strength", "ultimate_strength"),
    ],
)
def test_a_check_whose_inputs_are_absent_says_so_and_names_them(check, dropped, missing):
    """An undeclared input is NOT_EVALUATED naming the field, never a quiet pass."""
    entry = _named(screen_shaft(_shaft(**{dropped: None})))[check]
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert missing in entry.detail
    assert entry.safety_factor is None


def test_a_shaft_carrying_nothing_is_not_evaluated_rather_than_infinitely_strong():
    card = screen_shaft(_shaft(bending_moment=_q("0 N*m"), torque=_q("0 N*m")))
    for entry in card.entries:
        assert entry.status is CheckStatus.NOT_EVALUATED, entry.name


def test_a_negative_diameter_is_refused_at_the_door():
    with pytest.raises(ValueError, match="must not be negative"):
        _shaft(diameter=_q("-40 mm"))


def test_a_misspelled_field_is_refused_rather_than_ignored():
    """`extra="forbid"`: a shaft declaring `allowable_twist_deg` would otherwise be screened
    with no twist check at all, and the card would still say what it said."""
    with pytest.raises(ValueError):
        _shaft(allowable_twist_deg=0.5)
