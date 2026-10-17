"""Views are drawn from the solid, so any solid draws (expand-drawable-parts, group 2).

The first renderer projected each pattern's known corners and refused anything else. These
hold the replacement to what the spec asks of it: a solid no pattern knows about draws in
all four views, hidden edges are dashed, a dimension callout is a measurement of the solid
and not a copy of the request, and the overview is one image.
"""

from __future__ import annotations

import re

import pytest

pytest.importorskip("build123d")

from anvilate import projection  # noqa: E402
from anvilate.raster import svg_to_png  # noqa: E402


def _plate_with_boss():
    """A shape no pattern builds: a plate, four through holes and a boss."""
    from build123d import Align, Box, Cylinder, Pos

    low = (Align.CENTER, Align.CENTER, Align.MIN)
    part = Box(100, 80, 10, align=low)
    for x in (-30, 30):
        for y in (-20, 20):
            part = part - Pos(x, y, 0) * Cylinder(5, 10, align=low)
    return part + Pos(0, 0, 10) * Cylinder(12, 25, align=low)


def _view(view: str, **options) -> str:
    svg, _height = projection.render_view(
        _plate_with_boss(), {}, name="probe", view=view, width_px=640, **options
    )
    return svg.decode("utf-8")


@pytest.mark.parametrize("view", projection.VIEWS)
def test_a_solid_no_pattern_knows_draws_in_every_view(view):
    svg = _view(view)
    assert 'data-edges="visible"' in svg and "<polygon" in svg
    assert svg == _view(view), "the same solid, view and size must give the same bytes"
    assert svg_to_png(svg.encode("utf-8")).startswith(b"\x89PNG")


def test_hidden_edges_are_dashed_and_visible_ones_are_not():
    front = _view("front")
    hidden = re.search(r'<path data-edges="hidden"[^>]*>', front)
    visible = re.search(r'<path data-edges="visible"[^>]*>', front)
    assert hidden and "stroke-dasharray" in hidden.group(0)
    assert visible and "stroke-dasharray" not in visible.group(0)
    # Four holes through the plate, seen from the front, are eight hidden vertical lines.
    assert hidden.group(0).count("M ") >= 8


def test_the_views_are_the_solids_own_proportions():
    """Top is 100 x 80, front is 100 x 35, right is 80 x 35: read from the drawn edges."""

    def extent(view: str) -> tuple[float, float]:
        numbers = [
            float(value)
            for path in re.findall(r'<path data-edges="visible" d="([^"]+)"', _view(view))
            for value in re.findall(r"-?\d+\.\d+", path)
        ]
        xs, ys = numbers[::2], numbers[1::2]
        return max(xs) - min(xs), max(ys) - min(ys)

    for view, ratio in (("top", 100 / 80), ("front", 100 / 35), ("right", 80 / 35)):
        width, height = extent(view)
        assert width / height == pytest.approx(ratio, rel=0.01), view


def test_a_dimension_is_measured_from_the_solid_in_the_unit_asked_for():
    """The callouts come from the projected solid. Nothing here was told 100, 80 or 35."""
    camera = projection._Camera(_plate_with_boss(), "top")
    visible, hidden = projection._hidden_lines(_plate_with_boss(), camera)
    xs = [p[0] for line in visible + hidden for p in line]
    assert max(xs) - min(xs) == pytest.approx(100.0)

    labelled = _view("top", dimensions=True)
    plain = _view("top")
    assert labelled.count("<path") == plain.count("<path") + 5  # two dimensions and the note
    inches = _view("top", dimensions=True, unit="in")
    assert inches != labelled


def test_a_dimensioned_view_says_it_is_not_a_manufacturing_drawing():
    """The note is drawn as strokes like every label; its presence is the extra path."""
    assert _view("front", dimensions=True).count("<path") > _view("front").count("<path")
    assert "<text" not in _view("front", dimensions=True), "text is strokes, so PNG and SVG agree"


def _labels(monkeypatch, shape, view: str, **options) -> list[str]:
    """Every string the view draws, as asked of the stroke font."""
    drawn: list[str] = []
    real = projection._text

    def record(text, *args, **kwargs):
        drawn.append(text)
        return real(text, *args, **kwargs)

    monkeypatch.setattr(projection, "_text", record)
    projection.render_view(shape, {}, name="probe", view=view, width_px=640, **options)
    return drawn


def test_an_isometric_view_carries_no_dimension_because_it_has_no_true_length():
    """The iso view's projected extent is no length of the part. A 100 x 80 x 35 mm plate
    was labelled 127.3 mm across and 71.37 mm up, as though they were its dimensions; the
    overview already left them off its iso view for that reason."""
    from anvilate.geometry import GeometryError

    with pytest.raises(GeometryError, match="isometric.*front, top or right"):
        _view("iso", dimensions=True)
    assert _view("iso")  # drawn, without dimensions


def test_a_long_part_is_dimensioned_in_whole_millimetres_not_an_exponent(monkeypatch):
    """`:.4g` labelled a 12 m bar `1.2E+04 MM`."""
    from build123d import Box

    labels = _labels(monkeypatch, Box(12000, 100, 50), "front", dimensions=True)
    assert "12000 mm" in labels and "50 mm" in labels, labels
    assert not [label for label in labels if "e+" in label.lower()], labels
    inches = _labels(monkeypatch, Box(12000, 100, 50), "front", dimensions=True, unit="in")
    assert "472.4 in" in inches, inches


def test_the_overview_is_one_image_of_all_four_views():
    svg, height = projection.render_overview(
        _plate_with_boss(), {}, name="probe", lines=("100 x 80 x 35 mm", "ASTM-A36", "pass"),
        width_px=1000,
    )  # fmt: skip
    text = svg.decode("utf-8")
    assert height == 750
    assert text.count('data-edges="visible"') == 4
    assert text.count("<svg") == 1
    png = svg_to_png(svg)
    assert png == svg_to_png(svg) and len(png) < 200_000


def test_every_character_a_label_can_carry_has_a_glyph():
    """A part name, a material and a verdict are letters, digits and a little punctuation.
    A character with no glyph is drawn as a box, which is visible, so this names the set."""
    needed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_/:()+ x,")
    missing = sorted(c for c in needed if c != " " and c not in projection._GLYPHS)
    assert not missing, missing


@pytest.mark.parametrize("size", [(100, 4000, 200), (4000, 100, 200), (10, 10, 4000)])
# The iso view is not dimensioned: its extent is no length of the part.
@pytest.mark.parametrize("view", [view for view in projection.VIEWS if view != "iso"])
def test_a_dimension_label_never_leaves_the_view(size, view):
    """On a 4 m beam the right view's "200 MM" ran off the edge and read "200 M".

    Every stroke of a dimensioned view, the labels included, is held inside the image, at
    the narrow width one cell of the overview has.
    """
    from build123d import Box

    width = 360
    svg, height = projection.render_view(
        Box(*size), {}, name="beam", view=view, width_px=width, dimensions=True
    )
    drawn = svg.decode("utf-8")
    assert drawn.count("<path") >= 4  # the edges, two dimension lines and two labels
    for path in re.findall(r'<path[^>]* d="([^"]+)"', drawn):
        points = re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", path)
        assert points
        for x, y in points:
            assert 0 <= float(x) <= width and 0 <= float(y) <= height, (view, size, x, y)
