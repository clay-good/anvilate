"""A deterministic PDF writer for a report typeset as monospaced text.

The calculation report already has a text form whose columns line up, because every
character in it takes one cell. The PDF keeps that property. It is set in Courier, so a
decimal column aligns on the decimal and a table's columns align without any metrics, and
each block of the report is laid out as whole lines.

Pagination follows the document's structure, not a line count. A block is kept on one page
when it fits on one. A block longer than a page splits at page boundaries, and its heading
is repeated with "(continued)" at the top of the next page, so a table's header row is
never left behind. Every page carries the report's title, and its date and "page N of M".

Identical input gives identical bytes. Nothing reads the clock, object numbers follow
document order, and the streams are left uncompressed, so no compressor version can change
the output. The document has no ``/ID``, which is optional for an unencrypted file.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from . import _glyphs

__all__ = ["BODY_LINES", "COLUMNS", "Block", "paginate", "render", "wrap"]

PAGE_WIDTH = 612  # US Letter, in points
PAGE_HEIGHT = 792
MARGIN = 54
FONT_SIZE = 8
LEADING = 10
CELL_POINTS = FONT_SIZE * _glyphs.CELL / 1000
COLUMNS = int((PAGE_WIDTH - 2 * MARGIN) / CELL_POINTS)
_BODY_TOP = PAGE_HEIGHT - MARGIN - 2 * LEADING  # the first body baseline
_BODY_BOTTOM = MARGIN + 2 * LEADING  # no body baseline goes below this
BODY_LINES = int((_BODY_TOP - _BODY_BOTTOM) / LEADING) + 1
_CONTINUED = " (continued)"


@dataclass(frozen=True)
class Block:
    """Lines that belong together, and how many of them head the block.

    ``heading`` lines are repeated at the top of a page the block continues onto. A check
    section's heading is its status line and underline, and a table's is its title.
    """

    lines: tuple[str, ...]
    heading: int = 0


def _cells(text: str) -> int:
    return sum(_glyphs.width(char) for char in text) // _glyphs.CELL


def wrap(line: str, columns: int = COLUMNS) -> list[str]:
    """``line`` broken into rows of at most ``columns`` cells.

    A break goes at the last space that fits. A continuation row is indented four cells
    past the line's own indent, so a wrapped sentence still reads as one item. A run with
    no space in it is cut at the column.
    """
    indent = len(line) - len(line.lstrip(" "))
    hanging = " " * min(indent + 4, columns // 2)
    rows: list[str] = []
    rest = line
    while _cells(rest) > columns:
        limit = columns
        taken = 0
        cut = 0
        for index, char in enumerate(rest):
            taken += _glyphs.width(char) // _glyphs.CELL
            if taken > limit:
                break
            cut = index + 1
        space = rest.rfind(" ", len(hanging) + 1, cut + 1)
        if space > len(hanging):
            rows.append(rest[:space].rstrip())
            rest = hanging + rest[space + 1 :].lstrip()
        else:
            rows.append(rest[:cut])
            rest = hanging + rest[cut:]
    rows.append(rest)
    return rows


def paginate(blocks: Sequence[Block], lines_per_page: int = BODY_LINES) -> list[list[str]]:
    """The blocks laid out onto pages, one blank line between blocks."""
    if isinstance(blocks, str | bytes) or not all(isinstance(b, Block) for b in blocks):
        raise ValueError(
            f"paginate lays out a sequence of Block objects; got {type(blocks).__name__}"
        )
    pages: list[list[str]] = [[]]
    for block in blocks:
        rows = [row for line in block.lines for row in wrap(line)]
        head = [row for line in block.lines[: block.heading] for row in wrap(line)]
        page = pages[-1]
        gap = 1 if page else 0
        if len(page) + gap + len(rows) <= lines_per_page:
            page.extend([""] * gap + rows)
            continue
        if len(rows) <= lines_per_page:
            pages.append(list(rows))
            continue
        # Longer than a page: start it where at least its heading and a few lines fit.
        if len(page) + gap + len(head) + 3 > lines_per_page:
            pages.append([])
            page, gap = pages[-1], 0
        page.extend([""] * gap)
        remaining = list(rows)
        while remaining:
            room = lines_per_page - len(page)
            page.extend(remaining[:room])
            remaining = remaining[room:]
            if remaining:
                repeat = [f"{head[0]}{_CONTINUED}", *head[1:]] if head else []
                pages.append(repeat)
                page = pages[-1]
    return [page for page in pages if page]


class _Encoder:
    """Text to PDF runs: Courier for WinAnsi, a Type 3 font for everything else."""

    def __init__(self, texts: Sequence[str]) -> None:
        extras = sorted({char for text in texts for char in text if not self._winansi(char)})
        self.extras = extras
        self.codes = {char: (index // 256, index % 256) for index, char in enumerate(extras)}
        self.fonts = (len(extras) + 255) // 256

    @staticmethod
    def _winansi(char: str) -> bool:
        if unicodedata.category(char) == "Cc":
            return False
        try:
            encoded = char.encode("cp1252")
        except UnicodeEncodeError:
            return False
        return encoded not in (b"\x81", b"\x8d", b"\x8f", b"\x90", b"\x9d")

    def runs(self, text: str) -> list[tuple[str, bytes]]:
        runs: list[tuple[str, bytes]] = []
        for char in text:
            if self._winansi(char):
                font, code = "F1", char.encode("cp1252")
            else:
                number, byte = self.codes[char]
                font, code = f"T{number}", bytes([byte])
            if runs and runs[-1][0] == font:
                runs[-1] = (font, runs[-1][1] + code)
            else:
                runs.append((font, code))
        return runs


def _show(encoder: _Encoder, text: str, x: float, y: float) -> str:
    parts = [f"BT {x:g} {y:g} Td"]
    for font, code in encoder.runs(text):
        parts.append(f"/{font} {FONT_SIZE} Tf <{code.hex().upper()}> Tj")
    parts.append("ET")
    return " ".join(parts)


def _utf16(text: str) -> str:
    return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


def _fit(text: str, columns: int) -> str:
    """``text`` cut to ``columns`` cells, marked with an ellipsis when cut."""
    if _cells(text) <= columns:
        return text
    kept = ""
    for char in text:
        if _cells(kept + char) > columns - 1:
            break
        kept += char
    return kept + "…"


def render(
    blocks: Sequence[Block], *, title: str, identity: str | None, dated: str | None, producer: str
) -> bytes:
    """The PDF for ``blocks``, with ``title`` and ``identity`` atop every page.

    ``identity`` is the project or part the report is for, printed at the top right, and
    ``dated`` is the date printed at the foot of every page beside its number.
    """
    pages = paginate(blocks)
    total = len(pages)
    header_left = _fit(title, COLUMNS - 30 if identity else COLUMNS)
    header_right = _fit(identity, COLUMNS - _cells(header_left) - 2) if identity else ""
    footers = [f"page {number} of {total}" for number in range(1, total + 1)]
    furniture = [header_left, header_right, dated or "", *footers]
    encoder = _Encoder([line for page in pages for line in page] + furniture)

    objects: list[bytes] = []

    def add(body: str | bytes) -> int:
        objects.append(body.encode("latin-1") if isinstance(body, str) else body)
        return len(objects)

    def stream(content: str) -> int:
        data = content.encode("latin-1")
        return add(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")

    catalog = add("")  # filled in once the page tree exists
    page_tree = add("")
    courier = add("<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    type3 = []
    if encoder.extras:
        differences = " ".join(f"/{name}" for name in _glyphs.COURIER_EXTRA)
        inner_courier = add(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding << /Type /Encoding "
            f"/BaseEncoding /WinAnsiEncoding /Differences [1 {differences}] >> >>"
        )
        oblique = add(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Oblique "
            "/Encoding /WinAnsiEncoding >>"
        )
        symbol_names = " ".join(f"/{name}" for name in _glyphs.SYMBOL_ORDER)
        symbol = add(
            "<< /Type /Font /Subtype /Type1 /BaseFont /Symbol /Encoding << /Type /Encoding "
            f"/Differences [1 {symbol_names}] >> >>"
        )
        resources = f"<< /Font << /C {inner_courier} 0 R /O {oblique} 0 R /S {symbol} 0 R >> >>"
        for number in range(encoder.fonts):
            chars = encoder.extras[number * 256 : (number + 1) * 256]
            procs = []
            for index, char in enumerate(chars):
                drawn, _real = _glyphs.drawing(char)
                advance = _glyphs.width(char)
                procs.append((index, stream(f"{advance} 0 d0\n{drawn}")))
            mapping = "\n".join(
                f"<{index:02X}> <{char.encode('utf-16-be').hex().upper()}>"
                for index, char in enumerate(chars)
            )
            cmap = stream(
                "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
                "/CMapName /Anvilate-UCS def\n/CMapType 2 def\n"
                "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
                f"{len(chars)} beginbfchar\n{mapping}\nendbfchar\n"
                "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
            )
            char_procs = " ".join(f"/g{index} {obj} 0 R" for index, obj in procs)
            names = " ".join(f"/g{index}" for index, _obj in procs)
            widths = " ".join(str(_glyphs.width(char)) for char in chars)
            type3.append(
                add(
                    "<< /Type /Font /Subtype /Type3 /FontBBox [-700 -300 1100 1000] "
                    "/FontMatrix [0.001 0 0 0.001 0 0] "
                    f"/CharProcs << {char_procs} >> "
                    f"/Encoding << /Type /Encoding /Differences [0 {names}] >> "
                    f"/FirstChar 0 /LastChar {len(chars) - 1} /Widths [{widths}] "
                    f"/Resources {resources} /ToUnicode {cmap} 0 R >>"
                )
            )
    fonts = " ".join([f"/F1 {courier} 0 R", *(f"/T{n} {obj} 0 R" for n, obj in enumerate(type3))])

    left = MARGIN
    right_edge = PAGE_WIDTH - MARGIN
    kids = []
    for number, page in enumerate(pages):
        content = [
            _show(encoder, header_left, left, PAGE_HEIGHT - MARGIN),
            f"0.5 w {left} {PAGE_HEIGHT - MARGIN - 4} m {right_edge} "
            f"{PAGE_HEIGHT - MARGIN - 4} l S",
        ]
        if header_right:
            x = right_edge - _cells(header_right) * CELL_POINTS
            content.append(_show(encoder, header_right, x, PAGE_HEIGHT - MARGIN))
        for row, line in enumerate(page):
            if line:
                content.append(_show(encoder, line, left, _BODY_TOP - row * LEADING))
        content.append(f"0.5 w {left} {MARGIN + LEADING} m {right_edge} {MARGIN + LEADING} l S")
        if dated:
            content.append(_show(encoder, dated, left, MARGIN))
        footer = footers[number]
        content.append(_show(encoder, footer, right_edge - _cells(footer) * CELL_POINTS, MARGIN))
        contents = stream("\n".join(content))
        kids.append(
            add(
                f"<< /Type /Page /Parent {page_tree} 0 R /MediaBox [0 0 {PAGE_WIDTH} "
                f"{PAGE_HEIGHT}] /Resources << /Font << {fonts} >> >> /Contents {contents} 0 R >>"
            )
        )
    info = add(f"<< /Title {_utf16(title)} /Producer {_utf16(producer)} >>")
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {page_tree} 0 R >>".encode()
    objects[page_tree - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{kid} 0 R' for kid in kids)}] /Count {total} >>"
    ).encode()

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        info,
        xref,
    )
    return bytes(out)
