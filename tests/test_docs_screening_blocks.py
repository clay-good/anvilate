"""Every docs page that shows a worked card has a test file that names it.

A discipline page teaches by worked example — a ```python block that screens something, then
a ```text block showing what came back:

    noise dose   FAIL   safety factor 0.75 vs required minimum 1.00
                 OSHA 29 CFR 1910.95 / NIOSH REL — 90 dBA criterion, 5 dB exchange rate

Every such page that ships today is held: `tests/test_building_services_docs.py` recomputes
all four of its cards from the packs, `tests/test_industrial.py` reads the covers page's own
declared cover out of its code block and recomputes both edge conditions, `test_quickstart`
compares byte for byte, and the MCP guide runs each example in a subprocess. That is the
right shape — a page's figures should be *recomputed*, and no generic gate can do that,
because only a per-page test knows which pack produced which line.

**What no gate covered is the next page.** Nothing said a page of this shape must be held at
all, so a new discipline page could land with a worked example nobody recomputes, on the day
it is most likely to be wrong. This is that ratchet, and it is deliberately the only thing
in this file: a generic re-check of the numbers would duplicate four hand-written tests and
be weaker than each of them.

**What this proves and what it does not.** It proves a page of this shape is named by a
test. It does not prove that test recomputes anything — naming a page costs one line of
text, which is the standing weakness of any gate that is a set of names. It is a ratchet
against an *unnoticed* page, not evidence that a noticed one is correct, and it is written
down that way so nobody reads more into a green run than is there.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_DOCS = _REPO / "docs"
_TESTS = _REPO / "tests"

# A python block, then the output it produces. Bounded so the non-greedy body cannot run
# from one fence through the prose to a later one — the first draft did, and matched a
# "block" of English that failed to compile.
_PAIR = re.compile(r"```python\n((?:(?!```)[\s\S])*?)```\n\n```text\n((?:(?!```)[\s\S])*?)```")


def _pages_showing_a_card() -> list[Path]:
    """Every docs page pairing a python block with the output it produces."""
    return [
        path
        for path in sorted(_DOCS.rglob("*.md"))
        if _PAIR.search(path.read_text(encoding="utf-8"))
    ]


def test_the_pattern_this_gate_looks_for_still_matches_something():
    """The gate's own non-vacuity, because everything below loops over a discovery.

    A page reformatted so its text block no longer follows its python block immediately
    stops matching, and then this file goes green while looking at nothing — the failure
    mode of every gate that discovers its subjects rather than listing them.
    """
    found = _pages_showing_a_card()
    pages = {path.name for path in found}
    # Named, not counted. A floor absorbs exactly the failure it is there to catch: one page
    # reformatted out of the pattern leaves the count above any floor loose enough to allow
    # a new page in, and the gate goes on reporting clean about a page it no longer reads.
    assert pages == {
        "agent-driving-evals.md",
        "agent-mcp-integration.md",
        "building-services-screening.md",
        "industrial-covers.md",
        "quality-interchange.md",
        "quickstart.md",
    }, (
        f"the set of pages showing a worked card has moved to {sorted(pages)}. A page that "
        f"joined it needs a test naming it — the parametrized case below says so. A page "
        f"that left it either dropped its worked example or reformatted out of the pattern "
        f"this gate matches, and the second is the one worth checking"
    )
    # And the match is a real one: what was captured is Python, page by page rather than in
    # aggregate. A count with a floor survived the mutation that turned one page's block into
    # prose, because the other pages kept the total above it — the same absorption the named
    # set above exists to avoid, one assertion further down.
    #
    # Two pages are exempt and are named with the reason, because an exemption list nobody
    # can read is a way of not having a gate. Both show *fragments*: a snippet that operates
    # on a `sections` or a `markdown` the page built earlier in prose, which is the right way
    # to write those pages and is not runnable on its own.
    fragments = {"quality-interchange.md", "agent-driving-evals.md"}
    for page in found:
        if page.name in fragments:
            continue
        for index, (code, _shown) in enumerate(_PAIR.findall(page.read_text(encoding="utf-8"))):
            try:
                compile(code, "<probe>", "exec")
            except SyntaxError as broken:
                pytest.fail(
                    f"docs/{page.name} block {index} was captured as Python and does not "
                    f"compile: {broken}. Either the block is prose this gate matched by "
                    f"accident, or the page shows a reader something they cannot run"
                )
    assert fragments < pages, f"an exempt page has left the set: {sorted(fragments - pages)}"


@pytest.mark.parametrize("page", _pages_showing_a_card(), ids=lambda p: p.name)
def test_a_page_that_shows_a_card_is_named_by_a_test(page: Path):
    """A worked example nobody recomputes is a number a reader trusts and no one checks."""
    naming = sorted(
        path.name
        for path in _TESTS.glob("test_*.py")
        if page.name in path.read_text(encoding="utf-8")
    )
    assert naming, (
        f"docs/{page.name} shows a worked card and no test file names it. Add one that "
        f"reads the page's own inputs out of its code block and recomputes the figures it "
        f"prints — see tests/test_industrial.py for the shape — rather than asserting the "
        f"numbers a second time, which is a copy that drifts with the page instead of "
        f"against it"
    )
