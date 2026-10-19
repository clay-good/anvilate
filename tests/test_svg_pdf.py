"""The drawings PDF writer: the drawings' vocabulary written as vectors, the rest refused."""

from __future__ import annotations

import zlib

import pytest

from anvilate.export.svg_pdf import SvgPdfError, svgs_to_pdf


def _svg(body: str) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">' + body + "</svg>"
    ).encode()


def _content(pdf: bytes) -> str:
    start = pdf.index(b"stream\n") + len(b"stream\n")
    return zlib.decompress(pdf[start : pdf.index(b"\nendstream", start)]).decode("ascii")


def test_each_element_is_written_as_path_operators():
    pdf = svgs_to_pdf([_svg(
        '<rect x="0" y="0" width="200" height="100" fill="#ffffff"/>'
        '<polygon points="1,1 9,1 9,9" fill="#ff0000" stroke="#000000" stroke-width="2"/>'
        '<path d="M 0 0 L 10 10" fill="none" stroke="#000000" stroke-dasharray="4 2"/>'
        '<circle cx="5" cy="5" r="2" fill="#00ff00"/>'
    )], title="t")  # fmt: skip
    ops = _content(pdf)
    assert "0 0 200 100 re" in ops and "1 1 1 rg" in ops
    assert "1 1 m 9 1 l 9 9 l h" in ops and "\nB\n" in ops and "2 w" in ops
    assert "0 0 m 10 10 l" in ops and "[4 2] 0 d" in ops and "\nS\n" in ops
    assert ops.count(" c") >= 4  # a circle is four Bézier quarters


def test_the_same_drawings_give_the_same_bytes():
    page = _svg('<rect x="0" y="0" width="10" height="10" fill="#123456"/>')
    assert svgs_to_pdf([page, page], title="t") == svgs_to_pdf([page, page], title="t")


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ('<text x="0" y="0">hi</text>', "does not draw <text>"),
        ('<path d="M 0 0 A 5 5 0 0 1 10 10" stroke="#000000"/>', "absolute M, L and Z"),
        ('<rect x="0" y="0" width="1" height="1" fill="red"/>', "#rrggbb"),
        ('<polygon points="1,1 2" fill="#000000"/>', "points are pairs"),
    ],
)
def test_anything_outside_the_vocabulary_is_refused(body, reason):
    with pytest.raises(SvgPdfError, match=reason):
        svgs_to_pdf([_svg(body)], title="t")


def test_a_package_holds_a_drawing():
    with pytest.raises(SvgPdfError, match="at least one drawing"):
        svgs_to_pdf([], title="t")
