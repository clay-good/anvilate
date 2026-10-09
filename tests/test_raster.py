"""The viewport rasterizer draws what the SVG says, and refuses what it cannot read.

`anvilate.raster` exists so an agent can see the part (a model reads PNG, not SVG). A PNG
that misplaced a face or drew a hidden edge solid would show the agent a different part from
the one built, so these hold the picture to the drawing it came from.
"""

from __future__ import annotations

import re
import struct
import zlib

import pytest

from anvilate.raster import svg_to_png

_HEAD = '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'


def _pixels(png: bytes) -> tuple[int, int, list[bytes]]:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    data = b""
    offset = 8
    while offset < len(png):
        (length,) = struct.unpack(">I", png[offset : offset + 4])
        kind = png[offset + 4 : offset + 8]
        if kind == b"IDAT":
            data += png[offset + 8 : offset + 8 + length]
        offset += 12 + length
    raw = zlib.decompress(data)
    stride = 1 + 3 * width
    assert len(raw) == stride * height
    return width, height, [raw[row * stride + 1 : (row + 1) * stride] for row in range(height)]


def _at(rows: list[bytes], x: int, y: int) -> tuple[int, int, int]:
    return tuple(rows[y][x * 3 : x * 3 + 3])


def test_a_filled_polygon_lands_where_the_svg_puts_it():
    svg = (
        _HEAD.format(w=100, h=80)
        + '<rect width="100" height="80" fill="#ffffff"/>'
        + '<polygon points="10,10 60,10 60,50 10,50" fill="#ff0000" stroke="#000000"/>'
        + '<ellipse cx="80" cy="60" rx="10" ry="8" fill="#0000ff"/>'
        + "</svg>"
    ).encode()
    width, height, rows = _pixels(svg_to_png(svg))
    assert (width, height) == (100, 80)
    assert _at(rows, 35, 30) == (255, 0, 0)
    assert _at(rows, 80, 60) == (0, 0, 255)
    assert _at(rows, 90, 10) == (255, 255, 255)
    # A 1 px edge on a pixel boundary covers half of each neighbour: grey, not white.
    assert _at(rows, 10, 30)[0] < 200, "the stroke is drawn on the polygon's edge"


def test_a_dashed_edge_is_drawn_dashed_not_solid():
    svg = (
        _HEAD.format(w=100, h=20)
        + '<path d="M 0 10 H 100" fill="none" stroke="#000000" stroke-width="2" '
        + 'stroke-dasharray="10 10"/>'
        + "</svg>"
    ).encode()
    _width, _height, rows = _pixels(svg_to_png(svg))
    assert _at(rows, 5, 10) == (0, 0, 0)
    assert _at(rows, 15, 10) == (255, 255, 255), "a gap in a hidden edge was filled in"
    assert _at(rows, 25, 10) == (0, 0, 0)


def test_an_arc_path_closes_around_its_ellipse():
    svg = (
        _HEAD.format(w=100, h=100)
        + '<path d="M 10 50 A 40 40 0 0 0 90 50 A 40 40 0 0 0 10 50 Z" fill="#00ff00"/>'
        + "</svg>"
    ).encode()
    _width, _height, rows = _pixels(svg_to_png(svg))
    assert _at(rows, 50, 50) == (0, 255, 0)
    assert _at(rows, 50, 85) == (0, 255, 0)
    assert _at(rows, 5, 5) == (255, 255, 255)


@pytest.mark.parametrize(
    "body",
    [
        '<text x="1" y="1">no</text>',
        '<path d="m 0 0 l 5 5" stroke="#000000"/>',
        '<path d="M 0 0 C 1 1 2 2 3 3" stroke="#000000"/>',
        '<rect width="5" height="5" fill="red"/>',
        '<line x1="0" y1="0" x2="5" y2="5" stroke="#000000" stroke-dasharray="3"/>',
    ],
)
def test_anything_outside_the_vocabulary_is_refused_not_guessed(body):
    with pytest.raises(ValueError, match="viewport rasterizer"):
        svg_to_png((_HEAD.format(w=10, h=10) + body + "</svg>").encode())


def _drawn() -> list:
    pytest.importorskip("build123d")
    from pathlib import Path

    from anvilate.geometry import build_spec
    from anvilate.spec import load_spec_yaml

    root = Path(__file__).resolve().parents[1] / "examples"
    names = ("base_plate", "cover_plate", "transmission_shaft", "timber_joist")
    return [build_spec(load_spec_yaml((root / f"{n}.spec.yaml").read_text())) for n in names]


def _inside(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    crossings = 0
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            crossings += 1
    return crossings % 2 == 1


def test_every_drawn_view_rasterizes_deterministically_with_each_face_in_its_colour():
    """Each sizable face in every view of every drawn example: a point at its centre carries
    its fill, unless a face drawn later covers that point (as in the SVG, later wins). Views
    with curved shapes after the polygons are judged by the faces before them only where
    nothing curved follows."""
    from anvilate.geometry import render_viewport

    checked = 0
    for built in _drawn():
        for view in ("iso", "front", "top", "right"):
            rendered = render_viewport(built, view=view, width_px=400)
            png = render_viewport(built, view=view, width_px=400, format="png")
            assert png.mime_type == "image/png" and png.data == svg_to_png(rendered.data)
            width, height, rows = _pixels(png.data)
            assert (width, height) == (rendered.width_px, rendered.height_px)
            svg = rendered.data.decode()
            faces = []
            for match in re.finditer(r'<polygon[^>]*points="([^"]+)"[^>]*fill="#(\w{6})"', svg):
                values = [float(v) for v in re.findall(r"[-\d.]+", match.group(1))]
                faces.append((list(zip(values[::2], values[1::2], strict=True)), match))
            for index, (polygon, match) in enumerate(faces):
                xs, ys = [x for x, _ in polygon], [y for _, y in polygon]
                edges = list(zip(polygon, polygon[1:] + polygon[:1], strict=True))
                area = abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in edges)) / 2
                perimeter = sum(
                    ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 for (x0, y0), (x1, y1) in edges
                )
                if 2 * area / perimeter < 6:
                    continue  # a sliver, however long: its interior is all outline at this size
                cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
                if any(_inside(cx, cy, later) for later, _ in faces[index + 1 :]):
                    continue
                if re.search(r"<(ellipse|circle|path)", svg[match.end() :]):
                    continue  # a curved shape drawn later may cover it
                fill = tuple(int(match.group(2)[i : i + 2], 16) for i in (0, 2, 4))
                assert _at(rows, round(cx), round(cy)) == fill, (built.pattern, view)
                checked += 1
    assert checked >= 8, f"only {checked} faces were sampled"
