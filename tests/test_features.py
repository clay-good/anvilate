"""The shared feature library and the pattern registry (expand-drawable-parts, group 1).

A hole is cut one way by every part, so it is tested once here: the volume removed is the
closed form, the feature is tagged where it was cut, and a feature that does not fit is
refused before anything is built. The registry is held to being the one table: what
`build_spec` draws, what the catalog lists and what a refusal names are the same set.
"""

from __future__ import annotations

import math

import pytest

pytest.importorskip("build123d")

from anvilate import features, patterns  # noqa: E402
from anvilate.geometry import GeometryError  # noqa: E402

_W, _H, _T = 100.0, 60.0, 8.0


def _plate():
    from build123d import Align, Box

    return Box(_W, _H, _T, align=(Align.CENTER, Align.CENTER, Align.MIN))


_TOP = features.Host(
    name="top",
    origin=(0.0, 0.0, _T),
    u=(1.0, 0.0, 0.0),
    v=(0.0, 1.0, 0.0),
    normal=(0.0, 0.0, 1.0),
    thickness=_T,
    width=_W,
    height=_H,
)


def _removed(*cuts: features.Cut) -> float:
    shape, _built = features.apply(_plate(), _TOP, cuts)
    return _W * _H * _T - shape.volume


def _disc(diameter: float) -> float:
    return math.pi * diameter**2 / 4


@pytest.mark.parametrize(
    ("cut", "removed"),
    [
        (features.through_hole("h", 10, 5, 8), _disc(8) * _T),
        (features.blind_hole("b", 0, 0, 10, 3), _disc(10) * 3),
        (
            features.counterbore("cb", 0, 0, 6, 11, 4),
            _disc(6) * _T + (_disc(11) - _disc(6)) * 4,
        ),
        (
            # A 90 degree cone from 6 to 12 mm is 3 mm deep: a frustum less the hole in it.
            features.countersink("cs", 0, 0, 6, 12),
            _disc(6) * _T + math.pi * 3 / 3 * (36 + 18 + 9) - _disc(6) * 3,
        ),
        (features.slot("s", 0, 0, 30, 8), (_disc(8) + 22 * 8) * _T),
        (features.slot("s", 0, 0, 30, 8, angle_deg=90), (_disc(8) + 22 * 8) * _T),
    ],
)
def test_a_cut_removes_its_closed_form_volume(cut, removed):
    assert _removed(cut) == pytest.approx(removed, rel=1e-6)


def test_a_feature_is_tagged_and_measured_where_it_was_cut():
    _shape, (hole,) = features.apply(_plate(), _TOP, [features.through_hole("m6", 20, -10, 6.6)])
    assert (hole.tag, hole.kind, hole.thread) == ("m6", "through_hole", None)
    assert hole.position_mm == (20.0, -10.0, _T)
    assert [hole.measure(q) for q in ("diameter", "depth", "x", "y", "z")] == [
        6.6,
        _T,
        20.0,
        -10.0,
        _T,
    ]
    with pytest.raises(GeometryError, match="has no 'length'"):
        hole.measure("length")


def test_a_host_on_another_face_cuts_along_its_own_normal():
    """The same hole from the plate's side face runs through its width, not its thickness."""
    side = features.Host(
        name="side",
        origin=(_W / 2, 0.0, _T / 2),
        u=(0.0, 1.0, 0.0),
        v=(0.0, 0.0, 1.0),
        normal=(1.0, 0.0, 0.0),
        thickness=_W,
        width=_H,
        height=_T,
    )
    shape, (hole,) = features.apply(_plate(), side, [features.through_hole("x", 0, 0, 4)])
    assert _W * _H * _T - shape.volume == pytest.approx(_disc(4) * _W, rel=1e-6)
    assert hole.axis == (1.0, 0.0, 0.0) and hole.position_mm == (_W / 2, 0.0, _T / 2)


def test_patterns_place_their_holes_and_name_each():
    grid = features.rectangular_pattern(
        "g", count_u=3, count_v=2, pitch_u=20, pitch_v=30, diameter=5
    )
    assert [(c.tag, c.u, c.v) for c in grid] == [
        ("g_1_1", -20.0, -15.0),
        ("g_1_2", -20.0, 15.0),
        ("g_2_1", 0.0, -15.0),
        ("g_2_2", 0.0, 15.0),
        ("g_3_1", 20.0, -15.0),
        ("g_3_2", 20.0, 15.0),
    ]
    circle = features.bolt_circle("bc", count=4, circle_diameter=40, diameter=5)
    assert [c.tag for c in circle] == ["bc_1", "bc_2", "bc_3", "bc_4"]
    assert [(round(c.u, 9), round(c.v, 9)) for c in circle] == [
        (20, 0),
        (0, 20),
        (-20, 0),
        (0, -20),
    ]
    assert _removed(*grid) == pytest.approx(6 * _disc(5) * _T, rel=1e-6)


@pytest.mark.parametrize(
    ("cuts", "reason"),
    [
        ([features.through_hole("edge", 47, 0, 8)], "edge"),
        ([features.through_hole("a", 0, 0, 10), features.through_hole("b", 6, 0, 10)], "a"),
        ([features.through_hole("big", 0, 0, 70)], "big"),
        ([features.blind_hole("deep", 0, 0, 5, 8)], "deep"),
        ([features.counterbore("cb", 0, 0, 6, 11, 8)], "cb"),
        # A slot along the long edge fits by its width; turned across the plate it does not.
        ([features.slot("s", 0, 0, 62, 6, angle_deg=90)], "s"),
        (
            [features.through_hole("twice", -20, 0, 5), features.through_hole("twice", 20, 0, 5)],
            "twice",
        ),
    ],
)
def test_a_feature_that_does_not_fit_is_refused_before_anything_is_cut(cuts, reason):
    with pytest.raises(GeometryError, match=reason) as refused:
        features.apply(_plate(), _TOP, cuts)
    assert refused.value.remedies


def test_a_slot_is_measured_as_a_slot_and_not_as_a_circle_around_it():
    """62 mm long and 6 wide fits along a 100 mm plate, 3 mm from its long edge."""
    assert _removed(features.slot("s", 0, 24, 62, 6)) > 0


@pytest.mark.parametrize(
    "make",
    [
        lambda: features.through_hole("h", 0, 0, 0),
        lambda: features.through_hole("h", 0, 0, float("nan")),
        lambda: features.blind_hole("h", 0, 0, 5, -1),
        lambda: features.counterbore("h", 0, 0, 6, 6, 2),
        lambda: features.countersink("h", 0, 0, 6, 5),
        lambda: features.countersink("h", 0, 0, 6, 12, angle_deg=30),
        lambda: features.slot("h", 0, 0, 6, 6),
        lambda: features.rectangular_pattern(
            "h", count_u=0, count_v=1, pitch_u=1, pitch_v=1, diameter=1
        ),
        lambda: features.rectangular_pattern(
            "h", count_u=40, count_v=40, pitch_u=1, pitch_v=1, diameter=1
        ),
        lambda: features.rectangular_pattern(
            "h", count_u=2, count_v=1, pitch_u=0, pitch_v=1, diameter=1
        ),
        lambda: features.bolt_circle("h", count=1, circle_diameter=10, diameter=1),
        lambda: features.bolt_circle("h", count=4, circle_diameter=0, diameter=1),
    ],
)
def test_a_feature_that_is_not_a_feature_is_refused_when_declared(make):
    with pytest.raises(GeometryError):
        make()


def test_plate_corners_round_and_an_oversize_radius_is_refused():
    rounded = features.round_corners(_plate(), 10.0)
    assert _W * _H * _T - rounded.volume == pytest.approx((4 - math.pi) * 100 * _T, rel=1e-6)
    with pytest.raises(GeometryError):
        features.round_corners(_plate(), 40.0)


def test_one_table_says_what_draws():
    from anvilate.geometry import _drawn_element_types
    from anvilate.screening import element_registry

    table = patterns.patterns()
    assert set(_drawn_element_types()) == set(table)
    assert set(table) <= set(element_registry())
    for element_type, pattern in table.items():
        assert pattern.element_type == element_type
        assert pattern.name.startswith(f"{element_type}/")
        assert pattern.model is element_registry()[element_type][0]
        assert patterns.pattern_for(element_type) is pattern
    assert patterns.pattern_for("no_such_part") is None and patterns.pattern_for(None) is None


def test_the_catalog_is_generated_from_the_table():
    catalog = patterns.drawable_catalog()
    assert [entry["element_type"] for entry in catalog] == sorted(patterns.patterns())
    for entry in catalog:
        pattern = patterns.patterns()[entry["element_type"]]
        assert entry["pattern"] == pattern.name and entry["summary"] == pattern.summary
        assert {p["name"] for p in entry["parameters"]} == set(pattern.model.model_fields)
        assert any(p["required"] for p in entry["parameters"])
        assert entry["outputs"] == list(pattern.outputs)


def test_a_pattern_cannot_be_registered_twice_or_misnamed():
    existing = next(iter(patterns.patterns().values()))
    with pytest.raises(ValueError, match="already has a pattern"):
        patterns.register(existing)
    with pytest.raises(ValueError, match="must be named"):
        patterns.Pattern("wrong/1", "spacer", object, lambda e, n: None, "x", "x.yaml")
    with pytest.raises(ValueError, match="nothing produces"):
        patterns.Pattern(
            "spacer/1", "spacer", object, lambda e, n: None, "x", "x.yaml", outputs=("gltf",)
        )
