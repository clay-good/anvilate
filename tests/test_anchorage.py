"""Anchor forces under a base moment, against hand calculations.

Every number here is worked out away from the code. The module is statics and cites no
clause, so there is no standard to anchor on: what pins it is arithmetic a reader can
repeat on paper, and the two sign conventions that are easy to get backwards — a centre
of gravity that overhangs the leeward anchors, and an anchor downwind of the tipping axis.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis.anchorage import (
    ANCHORAGE_METHOD,
    AnchorageDemand,
    AnchorDemand,
    AnchorPosition,
    anchor_pattern_demand,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse


def _at(tag: str, x: float, y: float) -> AnchorPosition:
    return AnchorPosition(tag=tag, x=Q(f"{x} mm"), y=Q(f"{y} mm"))


#: Four anchors on a 150 mm square, the pattern under an ordinary guardrail post base.
_SQUARE = (_at("a1", -75, -75), _at("a2", 75, -75), _at("a3", -75, 75), _at("a4", 75, 75))
#: A metre square, for the equipment cases.
_WIDE = (
    _at("a1", -500, -500),
    _at("a2", 500, -500),
    _at("a3", -500, 500),
    _at("a4", 500, 500),
)


def test_a_guardrail_post_base_worked_by_hand():
    """29 CFR 1910.29(b)(3)'s 200 lbf at a 1,070 mm top rail, into a 150 mm pattern.

    H = 200 lbf = 889.64 N. M = H x 1.07 m = 951.92 N*m. The weight, 300 N at the pattern
    centroid, resists about the leeward anchor line with a 75 mm lever: 22.5 N*m. The net
    929.42 N*m divides over the two windward anchors, each 150 mm from that line:

        T = 929.42 x 1000 x 150 / (2 x 150^2) = 3,098 N

    Three kilonewtons of tension in each of two anchors, from a hand load on a rail. The
    two leeward anchors take none, and every anchor takes a quarter of the shear.
    """
    result = anchor_pattern_demand(
        anchors=_SQUARE,
        weight=Q("300 N"),
        lateral_force=Q("200 lbf"),
        height=Q("1070 mm"),
    )
    assert result.overturning.to("N*m").magnitude == pytest.approx(951.92, abs=0.02)
    assert result.resisting.to("N*m").magnitude == pytest.approx(22.5, abs=0.01)
    for tag in ("a1", "a3"):
        assert result.of(tag).tension.to("N").magnitude == pytest.approx(3098.1, abs=0.5)
    for tag in ("a2", "a4"):
        assert result.of(tag).tension.to("N").magnitude == 0.0
    for anchor in result.anchors:
        assert anchor.shear.to("N").magnitude == pytest.approx(889.64 / 4, abs=0.01)
    assert result.uplift and result.governing.tag in {"a1", "a3"}
    assert result.sliding.to("N").magnitude == pytest.approx(889.64, abs=0.01)


def test_an_anchor_downwind_of_the_tipping_axis_reads_zero_and_not_a_negative():
    """A negative tension read as a capacity is a hold-down nobody installed."""
    result = anchor_pattern_demand(
        anchors=_SQUARE, weight=Q("300 N"), lateral_force=Q("200 lbf"), height=Q("1070 mm")
    )
    leeward = [a for a in result.anchors if a.lever_mm == 0.0]
    assert len(leeward) == 2
    for anchor in leeward:
        assert anchor.tension.to("N").magnitude == 0.0


def test_weight_alone_can_hold_it_and_then_no_anchor_is_in_tension():
    """20 kN at a metre-square pattern against 1 kN at 500 mm: 20 to 1, and no uplift."""
    result = anchor_pattern_demand(
        anchors=_WIDE, weight=Q("20 kN"), lateral_force=Q("1 kN"), height=Q("500 mm")
    )
    assert result.stability_ratio == pytest.approx(20.0, rel=1e-9)
    assert not result.uplift
    for anchor in result.anchors:
        assert anchor.tension.to("N").magnitude == 0.0
        # The shear is still the anchors', because no friction is relied on.
        assert anchor.shear.to("N").magnitude == pytest.approx(250.0)
    assert "no uplift" in str(result)


def test_a_centre_of_gravity_that_overhangs_adds_to_the_overturning():
    """The sign that is easy to hide with an abs().

    A centre of gravity downwind of the leeward anchors is past the line the thing tips
    about, so its weight is not resisting — it is helping it over. The resisting moment
    comes back negative, and the anchors carry the overturning *plus* the weight.
    """
    plumb = anchor_pattern_demand(
        anchors=_WIDE, weight=Q("20 kN"), lateral_force=Q("1 kN"), height=Q("500 mm")
    )
    hung = anchor_pattern_demand(
        anchors=_WIDE,
        weight=Q("20 kN"),
        lateral_force=Q("1 kN"),
        height=Q("500 mm"),
        centre_of_gravity=(Q("800 mm"), Q("0 mm")),
    )
    assert plumb.resisting.to("N*m").magnitude > 0 > hung.resisting.to("N*m").magnitude
    # 20 kN x 0.3 m past the line = −6 kN·m, so the net is 0.5 + 6 = 6.5 kN·m.
    assert hung.resisting.to("N*m").magnitude == pytest.approx(-6000.0)
    assert hung.uplift and not plumb.uplift
    # net 6500 N*m over two anchors at 1000 mm: 6500000 x 1000 / (2 x 1000^2)
    assert hung.governing.tension.to("N").magnitude == pytest.approx(3250.0)


def test_the_load_direction_picks_the_tipping_axis():
    """On the diagonal the far corner has the full diagonal as its lever and the near one
    has none, which is the whole of what `direction` does."""
    result = anchor_pattern_demand(
        anchors=_WIDE,
        weight=Q("5 kN"),
        lateral_force=Q("5 kN"),
        height=Q("1 m"),
        direction=(1.0, 1.0),
    )
    levers = {a.tag: a.lever_mm for a in result.anchors}
    assert levers["a1"] == pytest.approx(1000.0 * 2**0.5, rel=1e-9)
    assert levers["a4"] == pytest.approx(0.0, abs=1e-9)
    assert levers["a2"] == pytest.approx(levers["a3"])
    # And the two side anchors share: the tension is proportional to the lever.
    assert result.of("a1").tension.to("N").magnitude == pytest.approx(
        2 * result.of("a2").tension.to("N").magnitude, rel=1e-9
    )


def test_the_direction_is_normalised_so_its_length_changes_nothing():
    """A caller writing (10, 0) means the same thing as (1, 0)."""
    short = anchor_pattern_demand(
        anchors=_WIDE,
        weight=Q("5 kN"),
        lateral_force=Q("5 kN"),
        height=Q("1 m"),
        direction=(1.0, 0.0),
    )
    long = anchor_pattern_demand(
        anchors=_WIDE,
        weight=Q("5 kN"),
        lateral_force=Q("5 kN"),
        height=Q("1 m"),
        direction=(10.0, 0.0),
    )
    assert short.governing.tension.to("N").magnitude == pytest.approx(
        long.governing.tension.to("N").magnitude
    )


def test_a_pattern_that_resists_no_moment_about_the_load_is_refused():
    """Two anchors in a line across the load have the same lever, so neither resists it."""
    in_line = (_at("a", 0.0, -100.0), _at("b", 0.0, 100.0))
    with pytest.raises(RefusalError, match="every anchor lies on one line"):
        anchor_pattern_demand(
            anchors=in_line, weight=Q("5 kN"), lateral_force=Q("1 kN"), height=Q("1 m")
        )
    # Turn the load ninety degrees and the same two anchors do resist it.
    turned = anchor_pattern_demand(
        anchors=in_line,
        weight=Q("5 kN"),
        lateral_force=Q("1 kN"),
        height=Q("1 m"),
        direction=(0.0, 1.0),
    )
    assert turned.uplift


def test_one_anchor_and_a_repeated_anchor_are_both_refused():
    with pytest.raises(RefusalError, match="at least two anchors"):
        anchor_pattern_demand(
            anchors=_SQUARE[:1], weight=Q("1 kN"), lateral_force=Q("1 kN"), height=Q("1 m")
        )
    doubled = (*_SQUARE, _at("a1", 0.0, 0.0))
    with pytest.raises(RefusalError, match="declared more than once"):
        anchor_pattern_demand(
            anchors=doubled, weight=Q("1 kN"), lateral_force=Q("1 kN"), height=Q("1 m")
        )


@pytest.mark.parametrize("bad", [(0.0, 0.0), (1.0,), "x", (float("nan"), 0.0)])
def test_a_force_with_no_direction_is_refused(bad):
    with pytest.raises(RefusalError, match="direction"):
        anchor_pattern_demand(
            anchors=_SQUARE,
            weight=Q("1 kN"),
            lateral_force=Q("1 kN"),
            height=Q("1 m"),
            direction=bad,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("weight", Q("-1 kN"), "magnitude here"),
        ("lateral_force", Q("-1 kN"), "magnitude here"),
        ("height", Q("-1 m"), "measured up from the base plane"),
        ("weight", Q("1 m"), "must be a .force. quantity"),
        ("height", Q("1 kN"), "must be a .length. quantity"),
        ("weight", 1000.0, "must be a .force. quantity"),
        ("lateral_force", Quantity(magnitude=float("nan"), unit="N"), "must be finite"),
    ],
)
def test_each_force_input_is_refused_by_name(field, value, message):
    arguments = {
        "anchors": _SQUARE,
        "weight": Q("1 kN"),
        "lateral_force": Q("1 kN"),
        "height": Q("1 m"),
    }
    arguments[field] = value
    with pytest.raises(RefusalError, match=message):
        anchor_pattern_demand(**arguments)


def test_an_anchor_position_is_a_pair_of_finite_lengths():
    for bad in (Q("1 kN"), Quantity(magnitude=float("inf"), unit="mm")):
        with pytest.raises(ValidationError):
            AnchorPosition(tag="a", x=bad, y=Q("0 mm"))
    assert "a at (1 mm, 2 mm)" == str(AnchorPosition(tag="a", x=Q("1 mm"), y=Q("2 mm")))


def test_the_result_names_its_method_and_finds_its_anchors_by_tag():
    result = anchor_pattern_demand(
        anchors=_SQUARE, weight=Q("300 N"), lateral_force=Q("200 lbf"), height=Q("1070 mm")
    )
    assert isinstance(result, AnchorageDemand)
    assert result.method == ANCHORAGE_METHOD
    assert "no friction relied on" in result.method
    assert isinstance(result.of("a1"), AnchorDemand)
    with pytest.raises(KeyError, match="nope"):
        result.of("nope")
    assert "governs" in str(result)


def test_one_anchor_passed_bare_is_refused_not_read_as_its_fields():
    """A pydantic model iterates over its own (field, value) pairs.

    One `AnchorPosition` passed where a sequence belongs became three "anchors" called
    tag, x and y, and the pattern that came back was a pattern of nothing.
    """
    one = _at("a1", 0.0, 0.0)
    for bad in (one, 1.0, (Q("1 mm"),)):
        with pytest.raises(ValueError, match="anchors is a sequence of AnchorPosition"):
            anchor_pattern_demand(
                anchors=bad, weight=Q("1 kN"), lateral_force=Q("1 kN"), height=Q("1 m")
            )


def test_the_worst_direction_is_across_the_short_side_and_not_the_diagonal():
    """The answer most people guess wrong, so it is pinned both ways.

    On a 400 x 100 mm pattern the tension across the short side is 4.2 times the tension
    along the long one. On a square the two axes are the worst and the diagonal is the
    *mildest*: the diagonal does concentrate the moment on one corner, and it also
    lengthens every lever, and the sum of squares in the denominator grows faster than the
    lever in the numerator.
    """
    from math import cos, radians, sin

    from anvilate.analysis.anchorage import governing_anchor_direction

    def at(pattern, degrees):
        angle = radians(degrees)
        return (
            anchor_pattern_demand(
                anchors=pattern,
                weight=Q("300 N"),
                lateral_force=Q("200 lbf"),
                height=Q("1070 mm"),
                direction=(cos(angle), sin(angle)),
            )
            .governing.tension.to("N")
            .magnitude
        )

    oblong = (
        _at("a", -200, -50),
        _at("b", -200, 50),
        _at("c", 200, -50),
        _at("d", 200, 50),
    )
    assert at(oblong, 90) / at(oblong, 0) == pytest.approx(4.2, abs=0.05)
    assert at(_SQUARE, 45) < at(_SQUARE, 0) == pytest.approx(at(_SQUARE, 90))

    direction, worst = governing_anchor_direction(
        anchors=oblong, weight=Q("300 N"), lateral_force=Q("200 lbf"), height=Q("1070 mm")
    )
    assert abs(direction[0]) == pytest.approx(0.0, abs=1e-9)
    assert worst.governing.tension.to("N").magnitude == pytest.approx(at(oblong, 90))


def test_the_sweep_finds_the_square_patterns_closed_form():
    """The sweep is checked against arithmetic, not against itself.

    A square's worst direction is one of its axes, and along an axis the pattern is two
    anchors at the spacing and two on the tipping line, so

        T = (H.h - W.s/2) x s / (2 x s^2) = (H.h - W.s/2) / (2s)

    with s in metres. At 150 mm: (951.92 - 22.5) / 0.3 = 3,098 N.
    """
    from anvilate.analysis.anchorage import governing_anchor_direction

    spacing_m = 0.150
    force_n = Q("200 lbf").to("N").magnitude
    closed_form = (force_n * 1.070 - 300.0 * spacing_m / 2) / (2 * spacing_m)
    assert closed_form == pytest.approx(3098.1, abs=0.5)

    _direction, worst = governing_anchor_direction(
        anchors=_SQUARE, weight=Q("300 N"), lateral_force=Q("200 lbf"), height=Q("1070 mm")
    )
    assert worst.governing.tension.to("N").magnitude == pytest.approx(closed_form, rel=1e-9)
