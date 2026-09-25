"""The calculation report as a PDF (presentation-craft 5.2 and the print rules of 5.1).

The PDF is read back with pdfminer, an independent PDF parser, rather than inspected as
bytes. The text layer has to say what the text form says, character for character through
the glyphs this package draws itself; each section has to sit on one page; and every page
has to carry its furniture. The byte-identity scenario is asserted as written.
"""

from __future__ import annotations

import ast
import io
import re
import sys
from pathlib import Path

import pytest

from anvilate.report import _glyphs, _pdf
from anvilate.report._pdf import Block, paginate, render, wrap
from conftest import parsed_source

pdfminer = pytest.importorskip("pdfminer")
from pdfminer.fontmetrics import FONT_METRICS  # noqa: E402
from pdfminer.glyphlist import glyphname2unicode  # noqa: E402
from pdfminer.high_level import extract_pages, extract_text  # noqa: E402
from pdfminer.layout import LTTextContainer  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent


def _lug_report():  # type: ignore[no-untyped-def]
    sys.path.insert(0, str(_REPO / "examples"))
    try:
        from lifting_lug_calc_report import build_report
    finally:
        sys.path.pop(0)
    return build_report()


def _long_report():  # type: ignore[no-untyped-def]
    """The worked example with its checks repeated until it runs to several pages."""
    report = _lug_report()
    return report.model_copy(update={"sections": report.sections * 8})


def _pages(pdf: bytes) -> list[str]:
    texts = []
    for layout in extract_pages(io.BytesIO(pdf)):
        texts.append(
            "\n".join(item.get_text() for item in layout if isinstance(item, LTTextContainer))
        )
    return texts


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_an_unchanged_report_regenerates_byte_identically():
    """Scenario: reissue diffs only where the work changed."""
    report = _lug_report()
    first = report.to_pdf()
    assert first == _lug_report().to_pdf()
    assert first.startswith(b"%PDF-1.4") and first.rstrip().endswith(b"%%EOF")
    changed = report.model_copy(update={"date": "2026-07-28"}).to_pdf()
    assert changed != first, "the date is printed, so a new date is new bytes"


def test_the_text_layer_reads_back_as_the_text_form():
    """Every row of the text form is on the page, glyphs drawn here included."""
    report = _lug_report()
    extracted = _squash(extract_text(io.BytesIO(report.to_pdf())))
    rows = [row for line in report.to_text().splitlines() for row in wrap(line) if row.strip()]
    assert len(rows) > 60
    missing = [row for row in rows if _squash(row) not in extracted]
    assert not missing, missing[:5]
    # The characters that make this more than a WinAnsi test.
    assert "σ_p = P / (d · t)" in extracted and "σ ∝ 1/t" in extracted
    assert "(80.00 mm − 25.00 mm)" in extracted


def test_a_section_is_never_split_across_a_page_and_every_page_has_its_furniture():
    """Scenario: a derivation stays whole."""
    report = _long_report()
    pages = _pages(report.to_pdf())
    assert len(pages) >= 4, "the long report should run to several pages"
    for number, text in enumerate(pages, start=1):
        assert f"page {number} of {len(pages)}" in text
        assert "Lifting padeye — screening calculations" in text
        assert "Shop crane padeye, 50 kN" in text
        assert "2026-07-27" in text
    # Each check here ends with exactly one `source:` line, so a section split across a
    # break leaves a page with a heading and no source, and the next with the reverse.
    headings = 0
    for number, text in enumerate(pages, start=1):
        here = len(re.findall(r"^(?:PASS|FAIL)  .+$", text, flags=re.MULTILINE))
        assert here == text.count("source: "), f"page {number} holds part of a section"
        headings += here
    assert headings == len(report.sections)


def test_the_revision_is_on_every_page_and_in_the_header():
    """A page that names no revision cannot be put back in its set."""
    report = _long_report().model_copy(update={"revision": "C"})
    assert "Revision: C" in report.to_text()
    pages = _pages(report.to_pdf())
    assert len(pages) >= 4
    for text in pages:
        assert "Shop crane padeye, 50 kN · rev C" in text


def test_a_block_longer_than_a_page_repeats_its_heading():
    """Scenario: a continued table repeats its headers."""
    rows = tuple(f"  row {index}" for index in range(150))
    pages = paginate([Block(("Margin summary", "--------------", *rows), heading=2)], 60)
    assert len(pages) == 3
    for page in pages[1:]:
        assert page[:2] == ["Margin summary (continued)", "--------------"]
    assert [line for page in pages for line in page if line.startswith("  row")] == list(rows)


def test_a_block_that_fits_a_page_moves_whole_rather_than_splitting():
    first = Block(tuple(f"a{index}" for index in range(50)))
    second = Block(("heading", *(f"b{index}" for index in range(20))), heading=1)
    pages = paginate([first, second], 60)
    assert pages[1][0] == "heading" and len(pages[1]) == 21


def test_no_row_is_wider_than_the_page():
    report = _long_report()
    for block in report._text_blocks():
        for line in block.lines:
            for row in wrap(line):
                assert _pdf._cells(row) <= _pdf.COLUMNS, row


def test_nothing_on_the_page_depends_on_colour():
    """Scenario: printed in monochrome, complete. No content stream sets a colour."""
    pdf = _long_report().to_pdf()
    for operator in (b" rg", b" RG", b" k\n", b" K\n", b" sc", b" SC", b" scn", b" SCN"):
        assert operator not in pdf, operator


def _package_characters() -> set[str]:
    found: set[str] = set()
    for path in (_REPO / "src" / "anvilate").rglob("*.py"):
        for node in ast.walk(parsed_source(path)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.update(char for char in node.value if ord(char) > 127)
    return found


def test_every_character_the_package_writes_has_a_real_glyph():
    """The census that made this a design decision, now a gate. 149 characters when it was
    taken; every one outside WinAnsi must draw as itself, not as the box."""
    characters = _package_characters()
    assert len(characters) >= 140
    outside = [char for char in characters if not _pdf._Encoder._winansi(char)]
    assert len(outside) >= 100
    boxed = sorted(char for char in outside if not _glyphs.drawing(char)[1])
    assert not boxed, [f"U+{ord(char):04X}" for char in boxed]


def test_a_character_with_no_recipe_is_a_visible_box_that_still_reads_as_itself():
    snowman = "\u2603"
    assert _glyphs.drawing(snowman) == (_glyphs._BOX, False)
    pdf = render(
        [Block((f"weather {snowman} today",))], title="t", identity=None, dated=None, producer="t"
    )
    assert f"weather {snowman} today" in extract_text(io.BytesIO(pdf))


def test_the_symbol_and_courier_glyphs_named_here_exist_with_these_widths():
    """The names and widths are Adobe's core metrics, as pdfminer ships them."""
    symbol = FONT_METRICS["Symbol"][1]
    for name, width in _glyphs.SYMBOL_GLYPHS.items():
        char = glyphname2unicode[name]
        # Adobe files Omega and mu under the ohm and micro signs.
        char = {"\u03a9": "\u2126", "\u03bc": "\u00b5"}.get(char, char)
        assert symbol.get(char) == width, name
    courier = FONT_METRICS["Courier"][1]
    for name in _glyphs.COURIER_EXTRA:
        assert glyphname2unicode[name] in courier, name


def test_the_revision_travels_in_the_calc_record():
    from anvilate.report import report_from_record

    report = _lug_report().model_copy(update={"revision": "C"})
    record = report.to_record()
    assert record["schema_version"] == "1.5"
    assert report_from_record(record).revision == "C"


def test_more_extra_characters_than_one_type3_font_holds_all_read_back():
    """A Type 3 font has 256 codes. 600 distinct characters take three fonts, and every one
    still reads back as itself."""
    from anvilate.report import CalculationReport

    characters = "".join(chr(code) for code in range(0x4E00, 0x4E00 + 600))
    pdf = CalculationReport(title="T", standards=(characters,)).to_pdf()
    assert b"/T2 " in pdf
    extracted = extract_text(io.BytesIO(pdf))
    assert sum(char in extracted for char in characters) == 600


def test_a_lone_surrogate_from_a_reloaded_record_prints_as_the_replacement_character():
    """JSON can carry `"\\ud800"`, which no UTF-16 encoder accepts. It used to raise."""
    from anvilate.report import CalculationReport

    pdf = CalculationReport(title="T\ud800", standards=("x\ud800y",)).to_pdf()
    assert "x�y" in extract_text(io.BytesIO(pdf))
