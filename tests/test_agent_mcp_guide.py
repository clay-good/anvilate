"""The agent-integration guide, held to what the server actually does.

`docs/agent-mcp-integration.md` is the page a client author reads before writing anything,
so every claim on it that a test *can* hold is held: each worked example runs in its own
process and its printed output is compared byte for byte, the tools it names are resolved
against the live catalog, and the two lists it makes about the surface — which operations
cannot be served statelessly and which are task-dispatched — are derived from the code
rather than transcribed.

A documentation page is where drift goes to hide. Every gate below exists because the same
sentence would otherwise stay on the page after the thing it describes moved.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from anvilate.mcp import Dispatch, stateless_gaps, tool_catalog

_REPO = Path(__file__).resolve().parent.parent
_SRC = _REPO / "src"
_PAGE = _REPO / "docs/agent-mcp-integration.md"
_TEXT = _PAGE.read_text(encoding="utf-8")

# ```py renders identically to ```python and was silently skipped by a sibling gate once,
# so the languages this file knows are named and anything else fails rather than passing
# unexecuted. `bash` is here because the connect section shows a command, not a claim.
_KNOWN_FENCES = {"python", "text", "bash"}
_FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.MULTILINE | re.DOTALL)


def _fences() -> list[tuple[str, str]]:
    return [(match.group(1), match.group(2)) for match in _FENCE.finditer(_TEXT)]


def _examples() -> list[tuple[str, str]]:
    """Each ```python block paired with the ```text block that follows it.

    A python block with no text block after it is *not* silently skipped — it is returned
    with an empty claim, which the runner then fails on. An example nobody compares is the
    thing this file exists to prevent.
    """
    fences = _fences()
    pairs: list[tuple[str, str]] = []
    for index, (language, body) in enumerate(fences):
        if language != "python":
            continue
        following = fences[index + 1] if index + 1 < len(fences) else ("", "")
        pairs.append((body, following[1] if following[0] == "text" else ""))
    return pairs


def test_every_code_fence_is_one_this_file_knows():
    unknown = sorted({language for language, _ in _fences()} - _KNOWN_FENCES)
    assert not unknown, f"the guide uses fences this file does not handle: {unknown}"


def test_the_extractor_finds_the_examples_that_are_there():
    """Without this the whole file passes on a regex that matched nothing."""
    assert len(_examples()) == 6, [source[:40] for source, _ in _examples()]
    assert all(claimed.strip() for _source, claimed in _examples())


@pytest.mark.parametrize(
    ("index", "source", "claimed"),
    [(i, source, claimed) for i, (source, claimed) in enumerate(_examples())],
)
def test_each_example_prints_what_the_guide_says_it_prints(index, source, claimed, tmp_path):
    """Its own process each time, so one example cannot rebind a library attribute and make
    a later one print a sentence the library never says."""
    assert claimed.strip(), f"example {index} claims no output, so nothing is compared"
    completed = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        cwd=_REPO,
        # The subject store defaults to the user's cache, and an example that publishes a
        # handle would write there. The suite's autouse fixture cannot reach a subprocess
        # with a fixed environment, so the path is passed in.
        env={
            "PYTHONPATH": str(_SRC),
            "PATH": "/usr/bin:/bin",
            "ANVILATE_SUBJECT_STORE": str(tmp_path / "subjects"),
        },
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, f"example {index} failed:\n{completed.stderr}"
    assert completed.stdout == claimed, (
        f"example {index} printed:\n{completed.stdout}\nbut the guide claims:\n{claimed}"
    )


def test_the_unservable_list_is_the_servers_own():
    """The page prints this list from `stateless_gaps()` in an example, and *also* states it
    in a table and a bullet. The example cannot drift; the prose can, so it is checked too.
    """
    for name in stateless_gaps():
        assert f"`{name}`" in _TEXT, f"{name} cannot be served and the guide does not say so"
    servable = {tool.name for tool in tool_catalog()} - set(stateless_gaps())
    assert servable, "the gate is comparing against an empty set"


def test_the_task_dispatched_list_is_the_catalogs_own():
    dispatched = [tool.name for tool in tool_catalog() if tool.dispatch is Dispatch.TASK]
    assert dispatched, "the gate is comparing against an empty set"
    for name in dispatched:
        assert f"`{name}`" in _TEXT


def test_every_tool_the_guide_names_is_in_the_catalog():
    """A renamed tool leaves its old name in the prose, where it reads exactly as right as
    the new one. Backticked snake_case that looks like a tool name is resolved."""
    known = {tool.name for tool in tool_catalog()}
    # Identifiers the page backticks that are library symbols rather than tool names.
    allowed = known | {
        "handle_request",
        "stateless_gaps",
        "tool_catalog",
        "isError",
        "errors",
        "inputSchema",
        "outputSchema",
        "not_evaluated",
        "anvilate_spec",
        "read_scorecard",
        # The two fields a document uses to say what kind of element it is. Spec-IR field
        # names rather than tool names, like `anvilate_spec` above.
        "element_type",
        "element_params",
        "min_safety_factor",
    }
    # The artifact formats `export_artifact` publishes, read off the schema rather than
    # listed: `evidence_bundle` is snake_case in backticks and is not a tool, and a fourth
    # format added tomorrow should not have to be remembered here.
    allowed |= set(
        {tool.name: tool for tool in tool_catalog()}["export_artifact"].input_schema["properties"][
            "format"
        ]["enum"]
    )
    named = set(re.findall(r"`([a-z_]+_[a-z_]+)`", _TEXT))
    unknown = sorted(named - allowed)
    assert not unknown, f"the guide names {unknown}, which the catalog does not expose"
    assert known & named, "no tool name was found at all, so this gate checked nothing"


def test_the_guide_is_reachable_from_the_contracts_page_and_the_readme():
    """An unlinked page is one nobody reads and nobody notices going stale."""
    for source in ("README.md", "docs/mcp-tool-contracts.md"):
        assert "agent-mcp-integration.md" in (_REPO / source).read_text(encoding="utf-8"), (
            f"{source} does not link the agent-integration guide"
        )


_CONTRACTS = _REPO / "docs/mcp-tool-contracts.md"


def test_the_contracts_page_backing_table_is_the_catalogs_own():
    """The "Backed today by" column, row by row against `tool_catalog()`.

    This table had drifted on three of its eight rows at once — `run_validation` still named
    the bundle assembler it was moved off, `read_scorecard` named `Scorecard` when it reads
    the store, and `export_artifact` named the QIF exporter — and nothing could see it,
    because the page was prose and the column was a claim about code. A reader picking a tool
    to integrate against reads this table.

    The count sentence above it is held too, and separately: "five of the eight run today" is
    a second claim, it moves on a different day from any single row, and a table that agreed
    while the sentence said four would still be a page that misinforms.
    """
    text = _CONTRACTS.read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| `(\w+)` \| \w+ \| [^|]*\| ([^|]+?) \|$", text, re.MULTILINE))
    catalog = {tool.name: tool for tool in tool_catalog()}
    assert set(rows) == set(catalog), "the table lists tools the catalog does not, or misses some"
    for name, claimed in rows.items():
        expected = f"`{catalog[name].backing}`" if catalog[name].backing else "not built"
        assert claimed == expected, f"{name}: page says {claimed}, catalog says {expected}"

    backed = sum(1 for tool in catalog.values() if tool.backing)
    words = {4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight"}
    unbacked = len(catalog) - backed
    assert f"{words[backed]} of the eight run today" in text, backed
    assert f"other {words[unbacked].lower()} say so with `None`" in text, unbacked


def test_the_contracts_page_subject_table_marks_the_dispatched_tools():
    """The second table's "Servable statelessly" column, against the dispatch map.

    Its rows carry more than a yes — they say *why* a servable tool is not answered, and
    that half is what goes stale: `export_artifact`'s row said "waiting on a decision" for as
    long as there was one and would have gone on saying it after the decision was made. So
    the two words that mean "this one answers" are held to the map that decides it.
    """
    from anvilate.mcp import _DISPATCH

    text = _CONTRACTS.read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| `(\w+)` \| `(?:\w+)` \| ([^|]+?) \|$", text, re.MULTILINE))
    catalog = {tool.name: tool for tool in tool_catalog()}
    assert set(rows) == set(catalog)
    for name, claimed in rows.items():
        says_dispatched = "dispatched" in claimed and "task-dispatched" not in claimed
        assert says_dispatched == (name in _DISPATCH), f"{name}: {claimed!r}"
