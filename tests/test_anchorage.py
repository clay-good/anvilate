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
    frame_anchor_demand,
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


@pytest.mark.parametrize(
    ("spacing_mm", "weight", "height"),
    [
        (150, "300 N", "1070 mm"),
        (600, "300 N", "1070 mm"),
        (150, "5 kN", "1070 mm"),
        (150, "300 N", "300 mm"),
        (60, "10 N", "3 m"),
    ],
)
def test_the_square_claim_holds_wherever_the_pattern_lifts(spacing_mm, weight, height):
    """The docstring says the axes are worst and the diagonal mildest on a square.

    A claim about every square is worth checking on more than one. The qualifier matters
    too: at 1,000 mm centres under 20 kN the weight holds the pattern down in **every**
    direction, every tension is zero, and there is no worst direction to find. That is
    why the sentence says "wherever the pattern lifts at all" — the case is covered by
    the test below rather than quietly excluded.
    """
    from math import cos, radians, sin

    half = spacing_mm / 2
    pattern = tuple(
        _at(tag, x, y)
        for tag, (x, y) in zip(
            ("a", "b", "c", "d"),
            ((-half, -half), (-half, half), (half, -half), (half, half)),
            strict=True,
        )
    )

    def at(degrees: float) -> float:
        angle = radians(degrees)
        return (
            anchor_pattern_demand(
                anchors=pattern,
                weight=Q(weight),
                lateral_force=Q("200 lbf"),
                height=Q(height),
                direction=(cos(angle), sin(angle)),
            )
            .governing.tension.to("N")
            .magnitude
        )

    tensions = {degrees: at(degrees) for degrees in (0, 15, 30, 45, 60, 75, 90)}
    assert max(tensions.values()) > 0, "this case does not lift, so it tests nothing"
    assert tensions[0] == pytest.approx(tensions[90], rel=1e-9)
    assert tensions[45] == min(tensions.values())
    assert tensions[0] == max(tensions.values())


def test_a_pattern_the_weight_holds_down_has_no_worst_direction():
    """The qualifier on the claim above, as its own case."""
    from anvilate.analysis.anchorage import governing_anchor_direction

    held = tuple(
        _at(tag, x, y)
        for tag, (x, y) in zip(
            ("a", "b", "c", "d"),
            ((-500, -500), (-500, 500), (500, -500), (500, 500)),
            strict=True,
        )
    )
    _direction, worst = governing_anchor_direction(
        anchors=held, weight=Q("20 kN"), lateral_force=Q("200 lbf"), height=Q("500 mm")
    )
    assert not worst.uplift
    assert worst.governing.tension.to("N").magnitude == 0.0
    assert worst.stability_ratio > 1.0
    assert "no uplift" in str(worst)


# --- the other route: a declared base frame -------------------------------------------
#
# `anchor_pattern_demand` assumes a rigid base because an anchor pattern alone says nothing
# about the stiffness of what is bolted to it. A skid does say, so its solve distributes the
# load and each support reaction already IS that anchor's share.


def _skid(lateral_kn: float, weight_kn: float = 23.5, fixed: bool = False):
    """A 1200 x 600 mm skid on four corner supports, loaded at a post 900 mm up."""
    from anvilate.frame import (
        Frame,
        FrameMaterial,
        FrameMember,
        FrameNode,
        FrameSection,
        Freedom,
        NodeLoad,
        Support,
        solve_frame,
    )

    material = FrameMaterial(
        name="S355",
        elastic_modulus=Q("210 GPa"),
        shear_modulus=Q("81 GPa"),
        density=Q("7850 kg/m^3"),
        source="EN 10025-2 nominal values",
    )
    section = FrameSection(
        name="SHS 100x100x6",
        area=Q("21.9 cm^2"),
        second_moment_y=Q("311 cm^4"),
        second_moment_z=Q("311 cm^4"),
        torsion_constant=Q("502 cm^4"),
        source="the profile table for the declared section",
    )

    def at(name: str, x: float, y: float, z: float = 0.0):
        return FrameNode(name=name, x=Q(f"{x} mm"), y=Q(f"{y} mm"), z=Q(f"{z} mm"))

    held = (Freedom.UX, Freedom.UY, Freedom.UZ)
    if fixed:
        held = (*held, Freedom.RX, Freedom.RY)
    frame = Frame(
        name="skid",
        nodes=(
            at("a", 0, 0),
            at("b", 1200, 0),
            at("c", 1200, 600),
            at("d", 0, 600),
            at("top", 600, 300, 900),
        ),  # fmt: skip
        members=tuple(
            FrameMember(name=f"m{i}", start=s, end=e, section=section, material=material)
            for i, (s, e) in enumerate(
                (
                    ("a", "b"),
                    ("b", "c"),
                    ("c", "d"),
                    ("d", "a"),
                    ("a", "top"),
                    ("b", "top"),
                    ("c", "top"),
                    ("d", "top"),
                )  # fmt: skip
            )
        ),
        supports=tuple(Support(node=n, restrained=held) for n in ("a", "b", "c", "d")),
        node_loads=(NodeLoad(node="top", fz=Q(f"-{weight_kn} kN"), fx=Q(f"{lateral_kn} kN")),),
    )
    return frame, solve_frame(frame)


def test_each_support_of_a_solved_skid_is_one_anchors_demand():
    frame, solution = _skid(lateral_kn=7.5)
    result = frame_anchor_demand(frame, solution)

    assert [a.tag for a in result.anchors] == ["a", "b", "c", "d"]
    # The whole horizontal load arrives, and the whole weight.
    assert result.horizontal.to("kN").magnitude == pytest.approx(7.5, rel=1e-9)
    assert result.vertical.to("kN").magnitude == pytest.approx(23.5, rel=1e-9)
    # Pushed along +x, the two supports it leans towards take the larger shear.
    assert result.of("b").shear.to("N").magnitude > result.of("a").shear.to("N").magnitude
    assert result.of("b").shear.to("N").magnitude == pytest.approx(
        result.of("c").shear.to("N").magnitude, rel=1e-9
    ), "the skid is symmetric about y, so b and c are the same"
    # 23,5 kN down over a 1,2 m lever beats 7,5 kN at 900 mm, so nothing lifts.
    assert not result.uplift
    assert all(a.tension.to("N").magnitude == 0.0 for a in result.anchors)
    assert "no uplift" in str(result)


def test_a_big_enough_lateral_force_lifts_the_windward_supports():
    """The case the anchors exist for, and the sign convention that decides it.

    A support's fz is positive when it pushes the frame up; uplift is a NEGATIVE fz, the
    support holding the frame down, and that is what becomes tension. Reading the sign the
    other way would report tension on the leeward anchors, which are in bearing.
    """
    frame, solution = _skid(lateral_kn=60.0)
    result = frame_anchor_demand(frame, solution)

    assert result.uplift
    lifted = [a.tag for a in result.anchors if a.tension.to("N").magnitude > 0]
    # Pushed along +x, the frame tips about the b-c edge, so a and d lift.
    assert sorted(lifted) == ["a", "d"]
    assert result.governing.tag in ("a", "d")
    assert result.of("b").tension.to("N").magnitude == 0.0
    assert "governs" in str(result)


def test_a_pinned_support_carries_no_moment_however_the_solver_rounds():
    """The defect this guards: a pinned skid came back with 8e-15 N*m at every corner.

    A support that declares no rotational restraint cannot carry moment by construction, so
    whatever the solve returns there is arithmetic noise. Taking the fact from the
    declaration rather than from the magnitude is what makes `restrained` mean anything —
    a magnitude test named all four corners of a frame that holds no rotation at all.
    """
    frame, solution = _skid(lateral_kn=7.5)
    result = frame_anchor_demand(frame, solution)
    assert result.restrained == ()
    assert all(a.moment.to("N*m").magnitude == 0.0 for a in result.anchors)
    assert all(not a.rotational_restraint for a in result.anchors)
    # The solver did return a non-zero moment at those pinned nodes; it is just not real.
    assert any(abs(r.mx) + abs(r.my) > 0 for r in solution.reactions)


def test_a_support_that_holds_a_rotation_is_named():
    """Where the declaration does restrain rotation, the moment is real and reported.

    A single anchor bolt is a pin and does not take it, so naming the support is the useful
    answer — the base plate there spreads it into a group of bolts, which this does not
    model, or the support should have been released.
    """
    frame, solution = _skid(lateral_kn=7.5, fixed=True)
    result = frame_anchor_demand(frame, solution)
    assert sorted(result.restrained) == ["a", "b", "c", "d"]
    assert all(a.rotational_restraint for a in result.anchors)
    assert result.of("a").moment.to("N*m").magnitude > 0.0


def test_the_frame_route_reproduces_the_rigid_base_statics_exactly():
    """Two independent implementations landing on the same number, which checks both.

    A direct-stiffness solve and a lever-arm hand calculation are different models of the
    same hardware, and on a four-support skid they agree to the last digit. The first draft
    of this test asserted they would DISAGREE — the arithmetic refused it, and the
    agreement is the far stronger result.

    What the frame route buys is not accuracy but what has to be declared: the pattern route
    must be told the centre of gravity, and the second case here is the one that shows it.
    Move the post off centre and the frame knows; the pattern has to be told.
    """
    pattern_anchors = (
        _at("a", 0, 0), _at("b", 1200, 0), _at("c", 1200, 600), _at("d", 0, 600),
    )  # fmt: skip
    frame, solution = _skid(lateral_kn=60.0)
    centred_frame = frame_anchor_demand(frame, solution)
    centred_pattern = anchor_pattern_demand(
        anchors=pattern_anchors,
        weight=Q("23.5 kN"),
        lateral_force=Q("60 kN"),
        height=Q("900 mm"),
        direction=(1.0, 0.0),
    )
    assert centred_frame.governing.tension.to("kN").magnitude == pytest.approx(
        centred_pattern.governing.tension.to("kN").magnitude, rel=1e-9
    )
    assert centred_frame.governing.tension.to("kN").magnitude == pytest.approx(16.625)

    # And again with the post moved off centre, where the weight's lever changes.
    from anvilate.frame import solve_frame

    moved = frame.model_copy(
        update={
            "nodes": tuple(
                node.model_copy(update={"x": Q("300 mm")}) if node.name == "top" else node
                for node in frame.nodes
            )
        }
    )
    off_frame = frame_anchor_demand(moved, solve_frame(moved))
    off_pattern = anchor_pattern_demand(
        anchors=pattern_anchors,
        weight=Q("23.5 kN"),
        lateral_force=Q("60 kN"),
        height=Q("900 mm"),
        direction=(1.0, 0.0),
        centre_of_gravity=(Q("300 mm"), Q("300 mm")),
    )
    assert off_frame.governing.tension.to("kN").magnitude == pytest.approx(
        off_pattern.governing.tension.to("kN").magnitude, rel=1e-9
    )
    assert off_frame.governing.tension.to("kN").magnitude == pytest.approx(13.6875)
    # The move matters: it is not the same answer as the centred case.
    assert off_frame.governing.tension.to("kN").magnitude < 16.0


def test_a_solution_from_another_frame_is_refused():
    """Matching reactions to supports by list position would load the wrong anchor.

    The Frame model already refuses a support naming a node it does not have, so the way to
    reach this is a solution genuinely solved from a different frame — here one whose nodes
    are named differently.
    """
    frame, _solution = _skid(lateral_kn=7.5)
    renamed = frame.model_copy(
        update={
            "name": "other skid",
            "nodes": tuple(
                node.model_copy(update={"name": f"z{node.name}"}) for node in frame.nodes
            ),
            "members": tuple(
                member.model_copy(update={"start": f"z{member.start}", "end": f"z{member.end}"})
                for member in frame.members
            ),
            "supports": tuple(
                support.model_copy(update={"node": f"z{support.node}"})
                for support in frame.supports
            ),
            "node_loads": tuple(
                load.model_copy(update={"node": f"z{load.node}"}) for load in frame.node_loads
            ),
        }
    )
    from anvilate.frame import solve_frame

    other_solution = solve_frame(renamed)
    with pytest.raises(RefusalError, match="solved from a different frame"):
        frame_anchor_demand(frame, other_solution)


def test_a_frame_with_no_supports_is_refused():
    frame, solution = _skid(lateral_kn=7.5)
    with pytest.raises(RefusalError, match="declares none"):
        frame_anchor_demand(frame.model_copy(update={"supports": ()}), solution)


@pytest.mark.parametrize("axis", ["fx", "fy", "fz", "mx", "my", "mz"])
def test_a_non_finite_reaction_is_refused_by_name(axis: str):
    """The NaN-drop trap, closed where it starts.

    `max(0.0, -nan)` returns **0.0**: max drops a NaN candidate rather than propagating it,
    so an unconverged solve's fz would have become an anchor with no tension — a bolt nobody
    sizes. The summed `vertical` field catches that one by accident; a NaN in a component
    the sums do not reach would not be caught at all, so each component is checked here.
    """
    frame, solution = _skid(lateral_kn=7.5)
    poisoned = solution.reactions[0].model_copy(update={axis: float("nan")})
    with pytest.raises(RefusalError, match=f"non-finite {axis}"):
        frame_anchor_demand(
            frame, solution.model_copy(update={"reactions": (poisoned, *solution.reactions[1:])})
        )


def test_max_really_does_drop_a_nan_which_is_why_that_guard_exists():
    """The premise, asserted, so the guard above is not protecting against nothing."""
    assert max(0.0, float("nan")) == 0.0
    assert max(0.0, -float("nan")) == 0.0
