"""Drawings gathered into one PDF, each page the SVG's own vectors, with the standard library.

A release package hands a reviewer its drawings as one file to open and print. The assembly
drawings this package writes use a small, fixed vocabulary (``rect``, ``polygon``, ``line``,
``circle``, and ``path`` made of ``M``, ``L`` and ``Z``, each with a ``#rrggbb`` fill and
stroke, a stroke width and a dash), and this module writes exactly that as PDF path
operators: the lines stay lines at any zoom, and nothing is rasterized. Anything outside the
vocabulary is refused rather than drawn as a guess.

Each drawing is one landscape US Letter page, scaled to fit and centred. The export's
watermark goes in the document information dictionary, as it goes in a STEP or DXF header.
The output is deterministic: the same drawings give the same bytes.
"""

from __future__ import annotations

import math
import re
import zlib
from collections.abc import Sequence
from xml.etree import ElementTree

from ..refusal import RefusalError, Remedy

__all__ = ["SvgPdfError", "svgs_to_pdf"]

_SVG = "{http://www.w3.org/2000/svg}"
_DRAWN = {"rect", "polygon", "line", "circle", "path"}
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_PAGE = (792.0, 612.0)  # US Letter, landscape, in points
_MARGIN = 24.0
# A quarter circle as one cubic Bézier: the control points sit this fraction of the radius out.
_KAPPA = 4 * (math.sqrt(2) - 1) / 3


class SvgPdfError(RefusalError, ValueError):
    """A drawing this module does not write: anything outside the drawings' vocabulary."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            remedies=(
                Remedy(
                    action="render",
                    subject="pages",
                    source="anvilate.projection.render_assembly, whose SVG this module writes",
                ),
            ),
        )


def _colour(value: str | None, default: str | None) -> tuple[float, float, float] | None:
    value = default if value is None else value
    if value is None or value == "none":
        return None
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise SvgPdfError(f"a drawing's colours are #rrggbb; got {value!r}")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _f(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _numbers(text: str | None) -> list[float]:
    return [float(n) for n in _NUMBER.findall(text or "")]


def _outline(element: ElementTree.Element, tag: str) -> str:
    """The element's outline as PDF path construction operators."""
    get = element.get
    if tag == "rect":
        x, y = float(get("x", "0")), float(get("y", "0"))
        w, h = float(get("width", "0")), float(get("height", "0"))
        return f"{_f(x)} {_f(y)} {_f(w)} {_f(h)} re"
    if tag == "line":
        x1, y1, x2, y2 = (float(get(k, "0")) for k in ("x1", "y1", "x2", "y2"))
        return f"{_f(x1)} {_f(y1)} m {_f(x2)} {_f(y2)} l"
    if tag == "polygon":
        values = _numbers(get("points"))
        if len(values) < 4 or len(values) % 2:
            raise SvgPdfError("a polygon's points are pairs, at least two of them")
        pairs = list(zip(values[::2], values[1::2], strict=True))
        moves = [f"{_f(pairs[0][0])} {_f(pairs[0][1])} m"]
        moves += [f"{_f(x)} {_f(y)} l" for x, y in pairs[1:]]
        return " ".join(moves) + " h"
    if tag == "circle":
        cx, cy, r = (float(get(k, "0")) for k in ("cx", "cy", "r"))
        k = _KAPPA * r
        return (
            f"{_f(cx + r)} {_f(cy)} m "
            f"{_f(cx + r)} {_f(cy + k)} {_f(cx + k)} {_f(cy + r)} {_f(cx)} {_f(cy + r)} c "
            f"{_f(cx - k)} {_f(cy + r)} {_f(cx - r)} {_f(cy + k)} {_f(cx - r)} {_f(cy)} c "
            f"{_f(cx - r)} {_f(cy - k)} {_f(cx - k)} {_f(cy - r)} {_f(cx)} {_f(cy - r)} c "
            f"{_f(cx + k)} {_f(cy - r)} {_f(cx + r)} {_f(cy - k)} {_f(cx + r)} {_f(cy)} c h"
        )
    commands = re.findall(r"([A-Za-z])([^A-Za-z]*)", get("d", ""))
    out = []
    for command, arguments in commands:
        values = _numbers(arguments)
        if command == "Z" or command == "z":
            out.append("h")
            continue
        if command not in ("M", "L") or len(values) % 2:
            raise SvgPdfError(f"a drawing's paths are absolute M, L and Z; got {command!r}")
        for index in range(0, len(values), 2):
            operator = "m" if command == "M" and index == 0 else "l"
            out.append(f"{_f(values[index])} {_f(values[index + 1])} {operator}")
    return " ".join(out)


def _page(svg: bytes) -> str:
    """One drawing as a page's content stream, scaled to fit and centred."""
    root = ElementTree.fromstring(svg)
    width, height = float(root.get("width", "0")), float(root.get("height", "0"))
    if width <= 0 or height <= 0:
        raise SvgPdfError("a drawing states a positive width and height")
    scale = min((_PAGE[0] - 2 * _MARGIN) / width, (_PAGE[1] - 2 * _MARGIN) / height)
    left = (_PAGE[0] - width * scale) / 2
    top = (_PAGE[1] + height * scale) / 2
    # SVG's y runs down the page and PDF's up: one flip, then the drawing's own units.
    ops = ["q", f"{_f(scale)} 0 0 {_f(-scale)} {_f(left)} {_f(top)} cm", "1 J 1 j"]
    for element in root:
        tag = element.tag.removeprefix(_SVG)
        if tag not in _DRAWN:
            raise SvgPdfError(f"the drawing writer does not draw <{tag}>")
        fill = _colour(element.get("fill"), "#000000")
        stroke = _colour(element.get("stroke"), None)
        if fill is None and stroke is None:
            continue
        ops.append("q")
        if fill is not None:
            ops.append(" ".join(_f(c) for c in fill) + " rg")
        if stroke is not None:
            ops.append(" ".join(_f(c) for c in stroke) + " RG")
            ops.append(f"{_f(float(element.get('stroke-width', '1')))} w")
            dash = _numbers(element.get("stroke-dasharray"))
            ops.append(f"[{' '.join(_f(d) for d in dash)}] 0 d")
        ops.append(_outline(element, tag))
        paint = {(True, True): "B", (True, False): "f", (False, True): "S"}
        ops.append(paint[(fill is not None, stroke is not None)])
        ops.append("Q")
    ops.append("Q")
    return "\n".join(ops)


def _text(value: str) -> str:
    """A PDF literal string, escaped; anything outside printable ASCII becomes '?'."""
    safe = "".join(c if 32 <= ord(c) < 127 else "?" for c in value)
    return "(" + safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def svgs_to_pdf(
    pages: Sequence[bytes], *, title: str, metadata: Sequence[tuple[str, str]] = ()
) -> bytes:
    """The drawings as one PDF, a landscape Letter page each, in the order given.

    ``metadata`` are key/value pairs for the document information dictionary: the export
    watermark (:meth:`~anvilate.export.gate.ExportAuthorization.metadata`), so a draft's
    package says it is unvalidated in the file's own properties.
    """
    if not pages:
        raise SvgPdfError("a drawings package holds at least one drawing")
    streams = [zlib.compress(_page(svg).encode("ascii"), 9) for svg in pages]
    count = len(streams)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            "<< /Type /Pages /Kids ["
            + " ".join(f"{3 + 2 * i} 0 R" for i in range(count))
            + f"] /Count {count} >>"
        ).encode("ascii"),
    ]
    for index, stream in enumerate(streams):
        content = 4 + 2 * index
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_f(_PAGE[0])} {_f(_PAGE[1])}] "
            f"/Resources << >> /Contents {content} 0 R >>".encode("ascii")
        )
        objects.append(
            f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
    info = [("Title", title), ("Producer", "anvilate"), *metadata]
    pairs = " ".join(f"/{re.sub(r'[^A-Za-z0-9_]', '_', k)} {_text(v)}" for k, v in info)
    objects.append(f"<< {pairs} >>".encode("ascii"))
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    out += b"".join(f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {len(objects)} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)
