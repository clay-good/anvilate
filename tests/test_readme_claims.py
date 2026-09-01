"""What the docs claim, derived from the code rather than trusted.

Named for the README because that is where it started; it now covers any page that states
a number the library can compute.


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


def test_the_example_count_is_the_directorys_own():
    """The sibling of the two counts above, and the one nobody held.

    It read 484 against 490 on disk — six examples written, executed in CI by
    `test_every_example_is_executed_by_this_file`, and absent from the number a reader is
    given. The stronger half of that sentence, that each one runs in CI, was already gated;
    only the count was free to drift.
    """
    examples = sorted((_REPO / "examples").glob("*.py"))
    assert len(examples) > 400, "the examples directory came back implausibly small"
    claimed = int(_claimed(r"([\d,]+) runnable examples").replace(",", ""))
    assert claimed == len(examples), (
        f"the README says {claimed:,} runnable examples; {len(examples):,} are on disk"
    )


def test_every_example_the_index_names_exists():
    """`examples/README.md` is a curated index, not a listing — it names 183 of the 490 and
    that is the point of it. What it may not do is name one that is gone, which is the only
    half of it a reader can be sent wrong by, and nothing held either half before this.
    """
    import re

    index = (_REPO / "examples" / "README.md").read_text(encoding="utf-8")
    named = sorted(set(re.findall(r"`(\w[\w]*\.py)`", index)))
    assert len(named) > 100, f"the index names only {len(named)} examples; it has stopped listing"
    missing = [name for name in named if not (_REPO / "examples" / name).exists()]
    assert not missing, f"the examples index names files that are gone: {missing}"


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


def _basis_split() -> tuple[int, int, int]:
    """(materials, specification-minimum count, typical count), from the database itself."""
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
    return len(materials), minimum, len(materials) - minimum


_WORDS = {
    "Seven": 7,
    "seven": 7,
    "Eight": 8,
    "eight": 8,
    "Nine": 9,
    "nine": 9,
    "Ten": 10,
    "ten": 10,
    "Eleven": 11,
    "eleven": 11,
}


@pytest.mark.parametrize(
    "page,tail",
    [
        ("README.md", r"the other (\w+) report `not_evaluated`"),
        ("docs/citations.md", r"The other (\w+) —"),
    ],
)
def test_the_materials_basis_split_is_not_backwards(page, tail):
    """The one that was actually wrong, and wrong in the direction that matters.

    The README said nine of seventeen materials carry a specification minimum. Eight do —
    so the sentence reversed which half of the database screens unchanged and which half
    reports ``not_evaluated`` until the caller accepts a typical value. A reader counting
    on it would have expected the wrong nine materials to work.

    ``docs/citations.md`` carried the same sentence and **contradicted itself seventy lines
    earlier**, where the summary reads "8 carry specification minima and 9 carry typical
    values". Both pages are gated, because one page holding both answers is what a claim
    with no gate eventually looks like.
    """
    materials, minimum, typical = _basis_split()
    assert minimum and typical, "one side of the split is empty, so the claim is vacuous"

    total = int(
        _claimed(r"of the (seventeen|\d+) bundled materials", page=page).replace("seventeen", "17")
    )
    assert total == materials
    claimed_minimum = _WORDS[
        _claimed(r"(\w+) of the (?:seventeen|\d+) bundled materials", page=page)
    ]
    claimed_typical = _WORDS[_claimed(tail, page=page)]
    assert claimed_minimum == minimum, (
        f"{page} says {claimed_minimum} materials carry a specification minimum; {minimum} do"
    )
    assert claimed_typical == typical


def test_the_citations_page_does_not_state_the_split_twice_with_two_answers():
    """It did: the summary line and the prose sentence disagreed by a swap."""
    _, minimum, typical = _basis_split()
    page = (_REPO / "docs" / "citations.md").read_text()
    summary = re.search(r"(\d+) carry specification minima and (\d+)\s+carry typical values", page)
    assert summary is not None, "the summary line in docs/citations.md has moved or gone"
    assert (int(summary.group(1)), int(summary.group(2))) == (minimum, typical)


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


def test_the_quickstart_block_is_what_the_quickstart_prints():
    """The first thing a reader runs, held against the first thing they are shown.

    The README's quickstart shows three lines of scorecard output for
    ``examples/cantilever_bracket_check.py``. Nothing checked them: the numbers are printed
    inside the example's ``main()``, which ``runpy.run_path`` does not execute, so the
    existing example test asserts the statuses and never sees the text.

    Compared byte for byte and run as a real subprocess, because the claim is about what
    the command prints and not about what the library returns.
    """
    import subprocess
    import sys

    fence = re.search(
        r"python examples/cantilever_bracket_check\.py\n```\n\n```text\n(.*?)```",
        (_REPO / "README.md").read_text(),
        re.S,
    )
    assert fence is not None, (
        "the README's quickstart block has moved; restore it or drop this test with it"
    )
    completed = subprocess.run(  # noqa: S603 - our own example, fixed argv, no shell
        [sys.executable, str(_REPO / "examples" / "cantilever_bracket_check.py")],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(_REPO / "src"), "PATH": "/usr/bin:/bin"},
        check=True,
    )
    assert completed.stdout == fence.group(1), (
        "the README's quickstart output is not what the quickstart prints:\n"
        f"--- README ---\n{fence.group(1)}--- actual ---\n{completed.stdout}"
    )


def test_the_uncertainty_pages_worked_block_reproduces_its_own_comments():
    """The page's code block, run, and its inline comments checked against the result.

    Every figure in it is deterministic — ``sample_margin`` takes a seed and the page
    passes one — so there is no reason for the comments beside the calls to be prose. The
    margin, the shortfall probability, the fragility verdict and the dominant input are all
    quoted there and were checked by nothing.
    """
    from anvilate.uncertainty import Normal, sample_margin

    page = (_REPO / "docs" / "uncertainty-margins.md").read_text()

    def safety_factor(v):
        return (v["yield_strength"] * v["area"] / 1000.0) / v["load"]

    result = sample_margin(
        safety_factor,
        {
            "load": Normal(mean=29.4, std=0.15 * 29.4),
            "yield_strength": Normal(mean=250.0, std=0.05 * 250),
            "area": Normal(mean=200.0, std=0.0),
        },
        required=1.5,
        seed=20260803,
    )

    printed = re.search(
        r"# (margin [\d.]+ ± [\d.]+, P\(below [\d.]+\) = [\d.]+% over \d+ samples)", page
    )
    assert printed is not None, "the page no longer shows what `print(result)` gives"
    assert str(result) == printed.group(1)

    probability = re.search(r"shortfall_probability\s+# ([\d.]+) —", page)
    assert probability is not None
    assert result.shortfall_probability == pytest.approx(float(probability.group(1)), abs=5e-4)

    assert re.search(r"is_fragile\(threshold=0\.05\)\s+# (\w+)", page).group(1) == str(
        result.is_fragile(threshold=0.05)
    )
    assert re.search(r'dominant\(\)\.name\s+# "(\w+)"', page).group(1) == result.dominant().name


# Pages that are records rather than documentation: dated research write-ups, kept for the
# audit trail of what was checked and when. The README indexes what a reader should read,
# and a link to every past investigation would make it a worse index rather than a fuller
# one. Everything else under `docs/` — at any depth — has to be reachable.
_PAGES_THE_README_DOES_NOT_INDEX = frozenset(
    {
        "research/2026-07-27-capability-research.md",
        "research/2026-07-27-capability-research-wave-2.md",
        # The index itself. The README links it, and it links everything else; requiring it
        # to be reachable by the same rule as a content page would be circular.
        "README.md",
    }
)


def test_every_docs_page_is_reachable_from_the_readme():
    """A page nobody links is a page nobody reads.

    Thirty-eight pages under `docs/` carry the arguments the README summarises, and the
    only route to them is a link. This is the ratchet: a new page that nothing points at
    fails here, as does a link to a page that has been renamed or removed — which is the
    other way the set drifts, and the one a reader meets as a 404.
    """
    import re

    root = Path(__file__).resolve().parent.parent
    readme = (root / "README.md").read_text()
    # `rglob`, not `glob`. The non-recursive version could not see `docs/research/`, so two
    # write-ups sat below the level it looked at — neither linked nor excused, which is the
    # state a ratchet exists to make impossible.
    pages = {
        str(page.relative_to(root / "docs"))
        for page in (root / "docs").rglob("*.md")
        if str(page.relative_to(root / "docs")) not in _PAGES_THE_README_DOES_NOT_INDEX
    }
    assert len(pages) > 30, f"the docs directory has only {len(pages)} pages"
    for name in _PAGES_THE_README_DOES_NOT_INDEX:
        assert (root / "docs" / name).exists(), f"the allow-list names {name}, which is gone"

    linked = set(re.findall(r"docs/([a-z0-9-]+\.md)", readme))
    unreachable = sorted(pages - linked)
    assert not unreachable, (
        f"these pages are linked from nowhere in the README: {unreachable}. A reader "
        "meets the README first; a page it does not point at is not in the documentation."
    )
    dangling = sorted(linked - pages)
    assert not dangling, f"the README links pages that do not exist: {dangling}"


def test_every_docs_page_is_in_the_docs_index():
    """`documentation` asks for docs "organized around user tasks, not internal
    architecture". Forty-four pages and no index is an alphabetical file listing, which is
    the architecture the requirement says not to organize around.

    `docs/README.md` is that index, and this is the ratchet: a new page absent from it fails
    here, and an index entry pointing at a page that has moved fails too — which is the way
    the set drifts that a reader meets as a 404.
    """
    import re

    root = Path(__file__).resolve().parent.parent
    index_path = root / "docs" / "README.md"
    index = index_path.read_text(encoding="utf-8")
    pages = {path.name for path in (root / "docs").glob("*.md") if path.name != "README.md"}
    assert len(pages) > 40, f"the docs directory has only {len(pages)} pages"

    # The index opens by saying how many pages it maps, and that sentence went stale the
    # first time somebody added one: it said forty-four while forty-five shipped. It is the
    # count this test already has in its hand, so it is held here rather than proofread.
    words = {
        "Forty-three": 43,
        "Forty-four": 44,
        "Forty-five": 45,
        "Forty-six": 46,
        "Forty-seven": 47,
        "Fifty": 50,
    }
    claimed = re.search(r"^([A-Z][a-z]+(?:-[a-z]+)?) pages,", index, re.M)
    assert claimed is not None, "the index no longer opens by saying how many pages it maps"
    assert words[claimed.group(1)] == len(pages), (
        f"docs/README.md says {claimed.group(1)} pages; {len(pages)} ship"
    )

    linked = set(re.findall(r"\]\(([a-z0-9-]+\.md)\)", index))
    unindexed = sorted(pages - linked)
    assert not unindexed, (
        f"these pages are in no section of docs/README.md: {unindexed}. Put each under the "
        "task it serves, or the index is a file listing with headings on it."
    )
    dangling = sorted(linked - pages)
    assert not dangling, f"the index links pages that do not exist: {dangling}"


def test_the_docs_index_is_sections_not_one_list():
    """An index that is one flat list is the alphabetical listing again with a title.

    The requirement is task organization, so the shape is asserted: several sections, each
    with a heading a reader can scan, and no section holding nearly everything.
    """
    import re

    index = (Path(__file__).resolve().parent.parent / "docs" / "README.md").read_text(
        encoding="utf-8"
    )
    sections = re.split(r"^## ", index, flags=re.MULTILINE)[1:]
    assert len(sections) >= 5, f"the index has {len(sections)} sections"
    counts = [len(re.findall(r"\]\(([a-z0-9-]+\.md)\)", section)) for section in sections]
    assert all(counts), "a section links nothing"
    assert max(counts) <= sum(counts) * 0.5, (
        f"one section holds {max(counts)} of {sum(counts)} pages; that is a list with a "
        "heading on it rather than an organization"
    )


def test_the_docs_index_is_reachable_from_the_readme():
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    assert "docs/README.md" in readme, "the index nothing links is the index nobody finds"


def test_the_readme_document_is_a_document_that_screens_to_what_it_shows():
    """The front page's other front door: a spec file and the card `anvilate check` prints.

    Held the same way as the quickstart above — the YAML is written to a file and the CLI is
    driven as a real subprocess, so what a reader copies is what a reader runs. A block that
    only *looks* like a document is the failure this repository has already had once, on the
    screening page, one `...` at a time.
    """
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    page = (_REPO / "README.md").read_text()
    document = re.search(r"```yaml\n(name: padeye\n.*?)```", page, re.S)
    printed = re.search(
        r"```bash\nanvilate check examples/padeye\.spec\.yaml\n```\n\n```text\n(.*?)```",
        page,
        re.S,
    )
    assert document is not None and printed is not None, "the README's document block has moved"

    # The block is shipped as a file so a reader can run it rather than retype it, and the
    # two are held equal here — one document, not a page and a copy of it that drift.
    shipped = _REPO / "examples" / "padeye.spec.yaml"
    body = shipped.read_text(encoding="utf-8")
    assert body.endswith(document.group(1)), (
        "examples/padeye.spec.yaml is not the document the README shows"
    )
    assert body.startswith("#"), "the shipped copy should say where it comes from"

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "padeye.yaml"
        path.write_text(document.group(1), encoding="utf-8")
        completed = subprocess.run(  # noqa: S603 - our own CLI, fixed argv, no shell
            [
                sys.executable,
                "-c",
                "from anvilate.cli import run; raise SystemExit(run())",
                "check",
                str(path),
            ],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(_REPO / "src"), "PATH": "/usr/bin:/bin"},
            check=False,
        )
    assert completed.returncode == 0, completed.stderr
    # The path differs from the README's, and the first line names it; the rest is the card.
    shown = printed.group(1).splitlines()
    actual = completed.stdout.splitlines()
    assert actual[0] == "padeye: PASS", actual[0]
    assert actual[1:] == shown[1:], (
        "the README's card is not what `anvilate check` prints for its own document:\n"
        + "\n".join(actual[1:])
    )


def test_the_screen_counts_on_the_screening_page_are_the_registrys_own():
    """Two figures in one sentence, and both move on their own.

    `docs/spec-screening.md` says how many screens there are and how many of them are judged
    against a required safety factor. A pack ships an element by existing, so both numbers
    change without anybody editing the page — which is the definition of a sentence that
    needs a gate rather than a proofread.
    """
    import inspect

    from anvilate.screening import element_registry

    words = {
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "twenty-three": 23,
        "twenty-four": 24,
        "twenty-five": 25,
    }
    claimed_judged, claimed_total = re.search(
        r"([\w-]+) of the ([\w-]+) screens\s+are judged against one",
        (_REPO / "docs" / "spec-screening.md").read_text(encoding="utf-8"),
    ).groups()

    registry = element_registry()
    judged = sum(
        1
        for _tag, (_model, screen) in registry.items()
        if (parameter := inspect.signature(screen).parameters.get("required_safety_factor"))
        is not None
        and parameter.default is inspect.Parameter.empty
    )
    assert words[claimed_total.lower()] == len(registry)
    assert words[claimed_judged.lower()] == judged


def test_the_pages_that_count_something_count_the_real_thing():
    """Three prose counts on three pages, each derivable and none of them held.

    The docs index said forty-four pages while forty-five shipped, which is what a count in
    prose does the first time somebody adds one. These are the other two: the number of MCP
    tools, and the split of bundled materials that carry a specification minimum — the figure
    the allowable-basis section is *about*, so it going stale would make the page argue from
    a number it no longer has.
    """
    from anvilate.mcp import tool_catalog
    from anvilate.standards import default_materials_db
    from anvilate.standards.records import AllowableBasis

    words = {
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "Eight": 8,
        "Nine": 9,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
    }

    tools = _claimed(r"says what the (\w+) tools \*are\*", page="docs/agent-mcp-integration.md")
    assert words[tools] == len(tool_catalog())

    page = (_REPO / "docs" / "citations.md").read_text(encoding="utf-8")
    claimed = re.search(r"(\w+) of the (\w+) bundled materials carry a specification", page)
    assert claimed is not None, "the allowable-basis sentence on citations.md has moved"
    database = default_materials_db()
    materials = database.known_materials()
    minima = sum(
        1
        for identifier in materials
        if database.get(identifier).yield_strength.citation.basis
        is AllowableBasis.SPECIFICATION_MINIMUM
    )
    assert words[claimed.group(2)] == len(materials)
    assert words[claimed.group(1)] == minima
