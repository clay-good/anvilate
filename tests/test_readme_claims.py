"""The README's counts, derived from the code rather than trusted.

The README is the artifact a reader meets first and the one with the least gating: every
other manifest in this repository is held against the code, and the page describing them
was held against nothing. It went stale twice in one session — "1,811 public symbols" while
the manifest held 1,818, and, worse, **the materials-basis split written backwards**: nine
materials were said to carry a specification minimum where eight do, which reverses which
half of the database screens and which half reports `not_evaluated`.

A plausible number next to a correct mechanism reads as verified and is not. So the counts
that describe something enumerable are enumerated here.
"""

from __future__ import annotations

import pkgutil
import re
from pathlib import Path

import pytest

import anvilate.analysis as analysis_package
from anvilate.gdt import Characteristic
from anvilate.mcp import REQUIRED_OPERATIONS, tool_catalog
from anvilate.standards import default_materials_db
from anvilate.standards.records import AllowableBasis

_REPO = Path(__file__).resolve().parent.parent


def _claimed(pattern: str, page: str = "README.md") -> str:
    match = re.search(pattern, (_REPO / page).read_text(encoding="utf-8"))
    assert match is not None, (
        f"{page} no longer contains a claim matching {pattern!r}. Either restore the "
        "sentence or delete the assertion with it — a gate on a claim nobody makes is a "
        "gate that passes forever"
    )
    return match.group(1)


def test_the_analysis_module_count_is_the_real_one():
    modules = [m.name for m in pkgutil.iter_modules(analysis_package.__path__) if not m.ispkg]
    assert int(_claimed(r"\(([\d,]+) closed-form modules").replace(",", "")) == len(modules)


def test_the_public_symbol_count_is_the_manifests_own():
    manifest = [
        line
        for line in (_REPO / "docs" / "api" / "analysis-public-surface.txt")
        .read_text()
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(manifest) > 1000, "the manifest came back implausibly small"
    claimed = int(_claimed(r"and ([\d,]+) public symbols").replace(",", ""))
    assert claimed == len(manifest), (
        f"the README says {claimed:,} public analysis symbols; the manifest holds "
        f"{len(manifest):,}. It read 1,811 against 1,818 before this test existed"
    )


def test_the_materials_basis_split_is_not_backwards():
    """The one that was actually wrong, and wrong in the direction that matters.

    The README said nine of seventeen materials carry a specification minimum. Eight do —
    so the sentence reversed which half of the database screens unchanged and which half
    reports ``not_evaluated`` until the caller accepts a typical value. A reader counting
    on it would have expected the wrong nine materials to work.
    """
    db = default_materials_db()
    materials = [db.get(ref) for ref in db.known_materials()]
    bases = []
    for material in materials:
        citations = material.citations()
        for name in ("yield_strength", "ultimate_strength"):
            citation = citations.get(name)
            if citation is not None:
                bases.append(citation.basis)
                break
    assert len(bases) == len(materials), "a material with no strength citation to classify"

    minimum = sum(1 for b in bases if b is AllowableBasis.SPECIFICATION_MINIMUM)
    typical = len(bases) - minimum
    assert minimum and typical, "one side of the split is empty, so the claim is vacuous"

    total = int(_claimed(r"of the (seventeen|\d+) bundled materials").replace("seventeen", "17"))
    assert total == len(materials)
    words = {
        "Eight": 8,
        "Nine": 9,
        "Ten": 10,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "Seven": 7,
        "seven": 7,
        "Eleven": 11,
        "eleven": 11,
    }
    claimed_minimum = words[_claimed(r"(\w+) of the (?:seventeen|\d+) bundled materials")]
    claimed_typical = words[_claimed(r"the other (\w+) report `not_evaluated`")]
    assert claimed_minimum == minimum, (
        f"the README says {claimed_minimum} materials carry a specification minimum; {minimum} do"
    )
    assert claimed_typical == typical


def test_the_tool_surface_count_is_the_catalogs_own():
    claimed = _claimed(r"the pipeline's (\w+) operations")
    words = {"six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    assert words[claimed] == len(tool_catalog()) == len(REQUIRED_OPERATIONS)


def test_the_geometric_characteristic_count_is_the_models_own():
    """This one lives on the GD&T page rather than the README, which is the point of
    passing the page in: the claim is gated wherever it is made."""
    claimed = _claimed(r"(\w+)-characteristic set", page="docs/semantic-gdt.md")
    words = {"twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15}
    assert words[claimed] == len(Characteristic)


def test_the_test_count_is_the_suites_own(request):
    """Only meaningful on a full run, and it says so rather than passing quietly.

    ``testscollected`` is the count of *this* run, so a ``-k`` filter would make the
    comparison nonsense. The skip is reported; CI runs the whole suite.

    **The number is the suite's size, not its passing count.** A test cannot know how many
    of its siblings will pass while it is still running, and the two differ by the handful
    that skip without an optional dependency — so the README quotes what a test can
    actually hold itself to.
    """
    collected = getattr(request.session, "testscollected", 0)
    claimed = int(_claimed(r"([\d,]+) tests\)").replace(",", ""))
    if collected < claimed * 0.9:
        pytest.skip(f"partial run ({collected} collected); the README count needs a full one")
    assert collected == claimed, (
        f"the README says {claimed:,} tests; this run collected {collected:,}"
    )
