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

    # EVERY occurrence, not the first. The README states this count twice — "1,819 public
    # symbols" in the analysis-library paragraph and "the 1,819 public analysis symbols" in
    # the citations row — and `_claimed` reads whichever the pattern happens to reach. The
    # anchored pattern matched only the first, so the second copy could drift a whole release
    # behind the surface and behind its own twin, which is the failure mode a gate on a
    # duplicated number exists to prevent.
    page = (_REPO / "README.md").read_text(encoding="utf-8")
    stated = re.findall(r"([\d,]+) public (?:analysis )?symbols", page)
    assert len(stated) >= 2, (
        f"the README states the public-symbol count {len(stated)} time(s); this gate reads "
        "every occurrence and needs to know when there is only one left"
    )
    wrong = [count for count in stated if int(count.replace(",", "")) != len(manifest)]
    assert not wrong, (
        f"the README states {stated} public analysis symbols; the manifest holds "
        f"{len(manifest):,}. It read 1,811 against 1,818 before this test existed, and the "
        f"second copy was unread until this gate looked at all of them"
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


def test_every_file_and_symbol_the_readme_names_still_exists():
    """The front page backticks fifty-nine example filenames and a handful of spec fields, and
    a rename leaves the old one reading exactly as right as the new one.

    The packaged skill has had this gate since it shipped — "a renamed function fails the
    build rather than shipping as advice" — and the README, which more people read, had none.

    The first draft of this test filtered to names starting with `anvilate.` and checked
    exactly one thing while reporting clean, which is the failure mode it is written against:
    both halves assert how many names they found before checking any of them.
    """
    import re

    from anvilate.spec import Constraints

    text = (_REPO / "README.md").read_text(encoding="utf-8")

    examples = sorted(set(re.findall(r"`([a-z0-9_]+\.py)`", text)))
    assert len(examples) >= 40, f"only {len(examples)} example filenames found; the regex moved"
    absent = [name for name in examples if not (_REPO / "examples" / name).exists()]
    assert not absent, f"the README names examples that are not in examples/: {absent}"

    fields = sorted(set(re.findall(r"`constraints\.([a-z_]+)`", text)))
    assert fields, "the README no longer names a constraints field"
    unknown = [name for name in fields if name not in Constraints.model_fields]
    assert not unknown, f"the README names constraints fields the model does not have: {unknown}"


def test_the_demo_tapes_narration_is_what_its_commands_print():
    """The README's hero image is a recording, and nothing checked what it says.

    `docs/demo.gif` is the first thing on the front page and it is generated from
    `docs/demo.tape` — a script of typed commands and typed prose. The prose makes claims
    about the output ("the deflection screen fails", "checks pass (ASME BTH-1)"), and an
    example whose verdict changed would leave the GIF asserting a result the library no
    longer produces, with no test between the two. The GIF cannot be regenerated here — it
    needs `vhs` — but everything it records can be run.

    The binding is two-way, and the second direction is the one that matters. Asserting
    only that a failing example prints `[FAIL]` leaves the narration free to say it passed:
    the first version of this test did exactly that, and changing "the deflection screen
    fails" to "passes" did not fail it. So every verdict the output shows has to be
    accounted for in the words beside it, and every verdict the words claim has to be in
    the output.
    """
    import subprocess
    import sys

    from anvilate.standards.effectivity import STANDARDS_BODIES

    tape = (_REPO / "docs" / "demo.tape").read_text(encoding="utf-8")
    typed = re.findall(r'^Type "(.*)"$', tape, re.M)
    assert typed, "the demo tape types nothing; its format has moved"

    def run(script: str) -> str:
        path = _REPO / script
        assert path.exists(), f"the demo tape runs {script}, which does not exist"
        return subprocess.run(  # noqa: S603 - our own examples, fixed argv, no shell
            [sys.executable, str(path)],
            cwd=_REPO,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(_REPO / "src"), "PATH": "/usr/bin:/bin"},
            check=True,
        ).stdout

    # The narration that follows a command is about that command. Walking in order is how
    # the two are paired, because the tape has no other link between them.
    printed: dict[str, str] = {}
    current: str | None = None
    narration: dict[str, list[str]] = {}
    for line in typed:
        if line.startswith("python "):
            current = line.split(" ", 1)[1]
            printed[current] = run(current)
            narration.setdefault(current, [])
        elif line.startswith("#") and current is not None:
            narration[current].append(line)

    assert len(printed) >= 2, f"the tape runs {len(printed)} examples; it used to run two"
    assert any(narration.values()), "no narration follows any command; the pairing broke"

    for script, output in printed.items():
        words = " ".join(narration[script]).lower()
        if not words:
            continue
        failed = "[FAIL]" in output
        claims_failure = "fail" in words
        assert failed == claims_failure, (
            f"the tape says {'a check fails' if claims_failure else 'nothing fails'} after "
            f"{script}, and the run says otherwise:\n{output}"
        )
        if "pass" in words:
            assert "[PASS]" in output, f"the tape claims a pass after {script}; there is none"
        # A standard the narration names has to be one the output actually cites. Matched
        # whole-word and case-sensitively: these are short uppercase acronyms, and a
        # lowercased substring test read the EN in "No silent green" as a Eurocode.
        spoken = " ".join(narration[script])
        for body in STANDARDS_BODIES:
            if re.search(rf"\b{re.escape(body)}\b", spoken):
                assert body in output, (
                    f"the tape names {body} after {script} and the output cites no such "
                    f"clause:\n{output}"
                )

    # And the file the tape then lists is the one an example says it wrote.
    listed = [line.split(" ", 1)[1] for line in typed if line.startswith("ls ")]
    assert listed, "the tape stopped listing the artifact; the last claim is unchecked"
    for name in listed:
        assert any(f"written to {name}" in text for text in printed.values()), (
            f"the tape lists {name}, which no example in it says it wrote"
        )
        assert (_REPO / name).exists(), f"{name} was listed but the run did not produce it"


def test_every_gate_the_security_page_names_is_a_gate_that_exists():
    """`SECURITY.md` is a table of properties, each with the test that holds it.

    That shape is only worth anything if the names resolve. A security page naming a test
    nobody wrote is worse than a page with no table at all: it reads as evidence, and the
    reader has no way to tell. The first draft of that page named two sweeps that did not
    exist — this is the gate that found them, and they were written rather than the claims
    dropped.

    Both halves. A named test that has gone tells the reader a property is held when it is
    not; a test file named in the table that has moved is the same failure one level up.
    """
    import re

    page = (_REPO / "SECURITY.md").read_text(encoding="utf-8")
    suite = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((_REPO / "tests").glob("*.py"))
    )

    named = sorted(set(re.findall(r"`(test_[a-z0-9_]+)`", page)))
    assert len(named) >= 5, f"SECURITY.md names only {named}; the table has lost its citations"
    missing = [name for name in named if f"def {name}(" not in suite]
    assert not missing, (
        f"SECURITY.md says these tests hold its security properties and they do not exist: "
        f"{missing}"
    )

    files = sorted(set(re.findall(r"`(tests/[a-z0-9_]+\.py)`", page)))
    assert files, "SECURITY.md names no test file, so the sweeps it cites cannot be found"
    absent = [name for name in files if not (_REPO / name).exists()]
    assert not absent, f"SECURITY.md names test files that are gone: {absent}"


def test_the_root_community_files_point_at_pages_that_exist():
    """`CONTRIBUTING.md` and `SECURITY.md` are the two files GitHub surfaces by itself.

    Neither is reachable from `docs/`, so the docs ratchet above cannot see them, and both
    exist to send a first-time reader somewhere else — which makes a dead link in them the
    one failure that matters. The commands they tell a contributor to run are checked too:
    a contributing guide naming a lint that is no longer the project's lint teaches the
    wrong thing to exactly the reader with no other source.
    """
    import re

    for name in ("CONTRIBUTING.md", "SECURITY.md"):
        page = _REPO / name
        assert page.exists(), f"{name} is gone; GitHub surfaces it and a reader will meet it"
        text = page.read_text(encoding="utf-8")
        targets = re.findall(r"\]\((?!https?:)([^)#]+)\)", text)
        assert targets, f"{name} links nothing, so it sends its reader nowhere"
        broken = [target for target in targets if not (_REPO / target.rstrip("/")).exists()]
        assert not broken, f"{name} links paths that do not exist: {broken}"

    guide = (_REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
    workflow = (_REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for command in ("ruff check src tests examples", "ruff format --check src tests examples"):
        assert command in guide, f"CONTRIBUTING.md no longer tells a contributor to run {command!r}"
        assert command in workflow, (
            f"CONTRIBUTING.md tells a contributor to run {command!r} and CI does not, so the "
            "guide and the gate have parted company"
        )


# Figures a README example row quotes that the example does not print, each with the
# derivation that makes it a fact about the run rather than a number somebody typed. A row
# may cite an input or a one-step consequence — that is good writing, not a gap — but it may
# not do so silently, which is the whole reason this file exists.
#
# Add a line ONLY after computing the figure. Do not add one to silence a failure: the
# failure means the front page states a result the example does not produce, and that is the
# defect this gate was written to find. It found one on its first run — a row calling a
# measurement "consistent with an in-tolerance shaft" where the screen reports 74.8% of
# samples falling short and 25% consistent, which is the opposite emphasis.
_DERIVED_IN_A_README_ROW: dict[tuple[str, str], str] = {
    ("aluminum_ladder_rail.py", "0.85"): "the ADM §E.3 out-of-straightness factor itself",
    ("aluminum_ladder_rail.py", "17.6"): "1/0.85 - 1 = 17.6%, the overstatement if it is dropped",
    ("spreader_beam_bth1_category.py", "124.0"): "F_y/N_d = 248 MPa / 2.00, Category A bending",
    ("spreader_beam_bth1_category.py", "82.7"): "F_y/N_d = 248 MPa / 3.00 = 82.67, Category B",
    ("bracket_reviewer_dossier.py", "3.0"): "the bending entry's computed safety factor",
    ("bracket_redesign_embodied_carbon.py", "34.3"): "12 kg / 0.35 yield = 34.29 kg of billet",
}


def _readme_example_rows() -> list[tuple[str, str]]:
    """Each README table row that names an example, as (example filename, description)."""
    rows = []
    for line in (_REPO / "README.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `") or ".py`" not in line:
            continue
        match = re.search(r"`([\w./]+\.py)`", line)
        if match is None:  # pragma: no cover - every row of this shape names a file
            continue
        rows.append((Path(match.group(1)).name, line.split("|", 2)[2]))
    return rows


def test_every_number_the_readme_quotes_from_an_example_is_one_the_example_produces():
    """The front page describes 59 examples, and it described them from memory.

    `tests/test_examples.py` already holds an example's own docstring to what the example
    computes — a figure that appears only in prose is a result with no gate. The README rows
    are the same prose about the same runs, living in another file, and nothing read them:
    of the figures quoted there, exactly one was covered by any test.

    Matched with the rounding the figure itself declares, so a row may quote 87.4 for a
    printed 87.38. A figure the example does not print at all must be in
    `_DERIVED_IN_A_README_ROW` with its derivation.
    """
    import contextlib
    import io
    import runpy

    examples = _REPO / "examples"
    quoted = re.compile(r"(?<![\w.§])(\d+\.\d+)(?![\w.])")
    rows = _readme_example_rows()
    assert len(rows) >= 50, (
        f"only {len(rows)} example rows were found; the table's shape changed and this gate "
        "is reading almost nothing"
    )

    unbacked: list[str] = []
    checked: set[tuple[str, str]] = set()
    for name, description in rows:
        path = examples / name
        assert path.exists(), f"the README names {name}, which is not in examples/"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            namespace = runpy.run_path(str(path))
            # `runpy` leaves an `if __name__ == "__main__"` guard unfired, so the figures
            # printed inside `main()` — which is most of them — never reach the buffer
            # unless it is called. Getting this wrong makes the gate pass on empty output.
            if callable(namespace.get("main")):
                namespace["main"]()
        printed = [
            float(token)
            for token in re.findall(r"-?\d+(?:\.\d+)?", buffer.getvalue().replace(",", ""))
        ]
        assert printed, f"{name} printed no numbers, so this row is checked against nothing"
        for figure in quoted.findall(description):
            checked.add((name, figure))
            tolerance = 0.5 * 10 ** -len(figure.partition(".")[2])
            if any(abs(float(figure) - value) <= tolerance * (1 + 1e-9) for value in printed):
                continue
            if (name, figure) in _DERIVED_IN_A_README_ROW:
                continue
            unbacked.append(
                f"{name}: the README quotes {figure} and the run produces no such value"
            )

    assert not unbacked, (
        "these front-page figures are not what the examples produce. Correct the README, or "
        "— if the figure is an input or a one-step consequence — record its derivation in "
        "_DERIVED_IN_A_README_ROW:\n  " + "\n  ".join(unbacked)
    )
    # Named members rather than a floor, because a floor absorbs exactly the drift it was
    # written to catch. These three rows quote a figure each in a different shape — a
    # governing load, an allowable stress, a probability — so a pattern that stops matching
    # one of them fails here instead of quietly checking less.
    canaries = {
        ("lipped_channel_dsm.py", "150.8"),
        ("welded_aluminum_platform_beam.py", "178.5"),
        ("measured_shaft_from_certificate.py", "74.8"),
    }
    assert canaries <= checked, (
        f"these README figures stopped being read: {sorted(canaries - checked)}. The rows "
        "were reworded, or the pattern stopped matching them, and the gate is now checking "
        f"less than it did ({len(checked)} figures over {len(rows)} rows)"
    )


def test_the_derived_readme_figures_are_still_quoted_and_still_underived():
    """The other direction, so the list can only shrink.

    A recorded derivation whose row no longer quotes the figure is a line that stops meaning
    anything and starts hiding the next one.
    """
    rows = dict(_readme_example_rows())
    for (name, figure), derivation in _DERIVED_IN_A_README_ROW.items():
        assert derivation.strip(), f"{name}'s {figure} is listed with no derivation"
        assert name in rows, (
            f"_DERIVED_IN_A_README_ROW names {name}, which the README no longer describes"
        )
        assert figure in rows[name], (
            f"the README row for {name} no longer quotes {figure}; strike it from "
            "_DERIVED_IN_A_README_ROW so the list stays honest"
        )


# Each capability the README's status line calls unbuilt, and the words a one-line
# description would claim it with. A synonym table rather than a substring of the README,
# because "plain English" is how a description claims a "natural-language front end" and
# "STEP/DXF" is how it claims "STEP export" — neither contains the other, and a gate that
# looked for the README's own phrasing would have passed the very sentence that prompted it.
_CLAIMED_BY = {
    "natural-language front end": ("plain english", "natural language", "natural-language"),
    "3D geometry": ("3d ", "geometry kernel", "solid model"),
    "FEA": ("fea", "finite element"),
    "STEP export": ("step/", "step ", " step", "parametric step"),
}


def _unbuilt_capabilities() -> list[str]:
    """The capabilities the README's own status line says are still being built."""
    readme = (_REPO / "README.md").read_text(encoding="utf-8")
    status = re.search(r"\*\*Status:.*?\*\*(.*?)\n\n", readme, re.S)
    assert status is not None, "the README's status line has moved"
    # `[^.]` so the span cannot cross a sentence boundary. The status paragraph opens with a
    # different "The …" sentence — "The deterministic engineering core is real, tested, and
    # runnable today." — and a non-greedy `.+?` starts at the earliest position it can,
    # which swallowed that one and reported "tested" as an unbuilt capability.
    listed = re.search(r"The ([^.]+) described under \[Where this is going\]", status.group(1))
    assert listed is not None, (
        "the README status no longer lists the unbuilt capabilities in the shape this gate "
        "reads; restore the sentence or rewrite the gate with it"
    )
    return [part.strip() for part in re.split(r",\s*(?:and\s*)?", listed.group(1)) if part.strip()]


def test_the_packaged_description_does_not_promise_what_the_readme_calls_unbuilt():
    """The one sentence PyPI and GitHub show, held against the status the README states.

    `pyproject.toml`'s `description` is the whole of what a reader sees before deciding to
    click. It said "plain English to physics-validated, parametric STEP/DXF" while the
    README's own status line says the natural-language front end and STEP export "are still
    being built" — the destination described as the product, in the one field with no room
    for a caveat.

    Same class as the `classifiers` that claimed one Python version while CI proved three:
    a metadata claim nobody gated.
    """
    import tomllib

    unbuilt = _unbuilt_capabilities()
    assert len(unbuilt) >= 3, f"only {unbuilt} parsed out of the README status line"

    with (_REPO / "pyproject.toml").open("rb") as handle:
        described = tomllib.load(handle)["project"]["description"].lower()

    promised = sorted(
        f"{capability} (via {word!r})"
        for capability in unbuilt
        # `.get`, not `[]`: a capability missing from the table is the *other* test's
        # finding, and a KeyError here would report it as a crash in this one.
        for word in _CLAIMED_BY.get(capability, ())
        if word in described
    )
    assert not promised, (
        f"pyproject's description promises {promised}, which the README's own status line "
        "says is still being built. That field has no room for a caveat: say what the "
        "package does today and leave the destination to the README."
    )


def test_the_unbuilt_capability_table_covers_what_the_readme_lists():
    """The other direction. A capability the README calls unbuilt and this table does not
    know is one the description could promise freely."""
    unbuilt = set(_unbuilt_capabilities())
    assert unbuilt == set(_CLAIMED_BY), (
        f"the README's unbuilt list and the synonym table have parted company — only in the "
        f"README {sorted(unbuilt - set(_CLAIMED_BY))}, only in the table "
        f"{sorted(set(_CLAIMED_BY) - unbuilt)}"
    )
    for capability, words in _CLAIMED_BY.items():
        assert words, f"{capability} has no words that would claim it"


# Commands CONTRIBUTING gives a contributor that CI deliberately does not run, each with the
# reason. A command in the guide and not in the workflow is otherwise a claim that something
# is enforced when it is not.
_LOCAL_ONLY_GATE_STEPS = {
    "npx openspec validate --all --strict": (
        "the spec validator is a node package and CI installs no node toolchain, so this is "
        "the step that depends on the contributor running it — and the guide says so"
    ),
    'pip install -e ".[dev]"': (
        "CI installs the dev extra with its own step rather than by copying this line, so "
        "the two say the same thing in different words"
    ),
}


def test_every_command_contributing_gives_is_run_by_ci_or_declared_local():
    """The guide's copyable block, held against the workflow.

    Two commands were already checked by name. `pytest -q` was not, and
    `npx openspec validate --all --strict` sat *outside* the copyable block in a sentence
    calling it "part of the gate" — so a contributor copying the block never ran it, and the
    sentence claimed an enforcement that existed nowhere. It is inside the block now and
    named as local-only.
    """
    guide = (_REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
    workflow = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((_REPO / ".github" / "workflows").glob("*.yml"))
    )
    blocks = re.findall(r"```bash\n(.*?)```", guide, re.S)
    assert blocks, "CONTRIBUTING.md has no command block for a contributor to copy"

    commands = [
        part.strip()
        for block in blocks
        for line in block.splitlines()
        for part in line.split("&&")
        if part.strip()
    ]
    assert len(commands) >= 4, f"only {commands} were read out of the guide"

    unbacked = [
        command
        for command in commands
        if command not in workflow and command not in _LOCAL_ONLY_GATE_STEPS
    ]
    assert not unbacked, (
        f"CONTRIBUTING.md tells a contributor to run these and CI does not, so the guide "
        f"and the gate have parted company: {unbacked}. Add the step to the workflow, or "
        f"record it in _LOCAL_ONLY_GATE_STEPS with the reason CI cannot."
    )
    for command, reason in _LOCAL_ONLY_GATE_STEPS.items():
        assert command in guide, f"{command!r} is excused and the guide no longer gives it"
        assert len(reason.split()) >= 8, f"{command!r} is excused without a stated reason"
    # The guide has to say that some of it is not enforced, or a reader assumes all of it is.
    assert "local check rather than a CI one" in guide


def test_the_package_docstring_enumerates_every_check_status():
    """`help(anvilate)` is the API's front page and it listed three of four statuses.

    It read "the tri-state check-result vocabulary (pass / fail / not-evaluated)". "Tri-state"
    is a deliberate term of art here and stays — those are three *answers*, and `over_margin`
    is a qualified pass, which is how the QIF exporter maps it. Enumerating three of four is a
    different thing: `over_margin` is a value a caller sees in output, and a reader of
    `help()` met it for the first time in a scorecard.

    Derived from `CheckStatus`, so a fifth status has to be added here or this fails. That is
    the whole gate — deliberately. The other fault in this docstring, that it described the
    unbuilt front end as what the package does, is *not* checked here: it is a judgment about
    sixty lines of prose, and the keyword table that works on `pyproject.toml`'s one-line
    description reported "feature control frame" as a promise of FEA when pointed at this.
    """
    import anvilate
    from anvilate.scorecard import CheckStatus

    doc = anvilate.__doc__ or ""
    assert doc, "the package lost its docstring, which is what help(anvilate) shows"
    listed = {status.value for status in CheckStatus if f"``{status.value}``" in doc}
    assert listed == {status.value for status in CheckStatus}, (
        f"the package docstring enumerates {sorted(listed)}; CheckStatus carries "
        f"{sorted(s.value for s in CheckStatus)}"
    )
