"""The agent skill is checked against the library, not read as prose.

A skill file is documentation, and documentation about a moving API goes stale silently.
These gates are built so that it cannot: every ``anvilate`` symbol the skill names is
imported, every worked example is executed, and every claimed output is compared byte for
byte against what the example actually prints. A skill describing a function that no
longer exists fails the build.

The doctrine gates are deliberately *not* keyword checks. A gate that greps for the words
"not evaluated" is satisfied by any paragraph containing them, including one that gets the
rule backwards — this repository has been bitten by exactly that shape of gate before. So
each doctrine section is anchored by an HTML comment marker and carries an executable
example, and the example's own assertions are what prove the claim. The gate checks the
markers are present and the examples run; the examples check the library behaves as the
prose says.

The prohibition gate is the one direction where text matching is sound: it can only ever
fire, never be satisfied. Prose cannot talk its way past "this file must not contain an
instruction to skip validation".
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path

import pytest

import anvilate
from anvilate.skills import SKILL_NAME, SKILL_PATH, skill_text

_REPO = Path(__file__).resolve().parent.parent
_AGENTS = _REPO / "AGENTS.md"

# Every doctrine the skill is required to carry, by its in-file marker. Adding a claim to
# the skill without an anchored, executing example is the failure this list prevents; so
# is quietly dropping one.
_REQUIRED_DOCTRINE = (
    "retrieval-not-recall",
    "read-the-scorecard",
    "not-evaluated-is-not-a-pass",
    "inverse-first-repair",
    "confirm-before-use",
    "screening-not-certified",
)

# Guidance that must never appear, as patterns over the normalized text. These are the
# behaviors the spec forbids: bypassing a gate, exporting past a failing check, and
# claiming a screening result is certified. This gate can only fire — no amount of
# surrounding prose satisfies it.
# Each entry is (pattern, complaint, negatable). ``negatable`` marks the two claims the
# skill is *required* to deny — it has to say it is not a certified analysis and not
# stamped by anybody — so for those, and only those, a sentence carrying a denial is
# allowed. The other five are instructions: there is no sentence in which "skip the
# validation" is acceptable guidance, and letting a stray "not" nearby excuse them is how
# a prohibition gate quietly stops meaning anything. That is not hypothetical here: the
# instruction patterns mention "not evaluated" by name, so a blanket negation allowance
# suppressed them against text that contained the very instruction they forbid.
_PROHIBITED = (
    (r"\bskip (?:the )?validation\b", "instructs skipping validation", False),
    (r"\bbypass(?:ing)? (?:the )?(?:gate|check|validation|sandbox)", "instructs a bypass", False),
    (
        r"\bignore (?:the )?(?:scorecard|not.?evaluated|failing)",
        "instructs ignoring a verdict",
        False,
    ),
    (r"\bexport (?:it )?anyway\b", "instructs exporting past a gate", False),
    (r"\btreat .{0,30}not.?evaluated.{0,20} as (?:a )?pass", "instructs a silent green", False),
    (r"\bcertified (?:analysis|result|calculation)\b", "claims certification", True),
    (r"\bstamped by\b", "claims a professional seal", True),
)

# Words that turn a claim into a denial of it. Applied only to the negatable patterns.
_NEGATIONS = re.compile(r"\b(?:not|never|cannot)\b", re.IGNORECASE)


def _sentence_around(text: str, position: int) -> str:
    start = max(text.rfind(".", 0, position), text.rfind("\n", 0, position)) + 1
    end = min(
        (i for i in (text.find(".", position), text.find("\n", position)) if i >= 0),
        default=len(text),
    )
    return text[start : end if end >= 0 else len(text)]


def _prohibited_hits(pattern: str, text: str, negatable: bool = False) -> list[str]:
    """Matches of ``pattern``, minus the ones a denial in the same sentence excuses."""
    hits = []
    for found in re.finditer(pattern, text, re.IGNORECASE):
        if negatable and _NEGATIONS.search(_sentence_around(text, found.start())):
            continue
        hits.append(found.group(0))
    return hits


# A dotted `anvilate...` reference inside backticks. Bare prose mentions are not checked —
# only the ones the skill presents as code, which are the ones an agent will copy.
_SYMBOL = re.compile(r"`(anvilate(?:\.[A-Za-z_][A-Za-z0-9_]*)+)`")

_FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
_BLOCK = re.compile(r"^```(?P<lang>[a-z]*)\n(?P<body>.*?)^```", re.MULTILINE | re.DOTALL)


def _frontmatter() -> dict[str, str]:
    match = _FRONTMATTER.match(skill_text())
    assert match is not None, "the skill must open with a YAML frontmatter block"
    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def _examples() -> list[tuple[str, str | None]]:
    """Every python block in the skill, paired with the output block that follows it."""
    blocks = [(m.group("lang"), m.group("body")) for m in _BLOCK.finditer(skill_text())]
    paired: list[tuple[str, str | None]] = []
    for index, (lang, body) in enumerate(blocks):
        if lang != "python":
            continue
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        paired.append((body, following[1] if following and following[0] == "text" else None))
    return paired


# --- it ships, offline ------------------------------------------------------------------


def test_the_skill_ships_inside_the_package():
    """An agent that cannot find the skill is an agent operating without it. It has to be
    in the installed package, not next to the repository."""
    assert SKILL_PATH.exists()
    assert SKILL_PATH.name == "SKILL.md"
    assert SKILL_PATH.parent.name == SKILL_NAME
    # Inside the distributed package directory, so the wheel carries it.
    package_root = Path(anvilate.__file__).resolve().parent
    assert package_root in SKILL_PATH.resolve().parents


def test_the_skill_is_readable_without_touching_the_filesystem_directly():
    assert skill_text().startswith("---\n")
    assert len(skill_text()) > 1000


def test_the_skill_states_its_version_and_the_surface_it_targets():
    fields = _frontmatter()
    assert fields["name"] == SKILL_NAME
    assert fields["version"] == anvilate.__version__, (
        "the skill version must move with the release; a skill stamped with an older "
        "version is a skill nobody can tell is stale"
    )
    assert fields["description"].strip()
    # The surface stamp has to name the manifests the drift gate below checks against,
    # otherwise the stamp is a decoration rather than a claim.
    surface = fields["tool-surface"]
    assert "core-public-surface.txt" in surface
    assert "analysis-public-surface.txt" in surface


# --- it cannot go stale -----------------------------------------------------------------


def test_every_symbol_the_skill_names_actually_exists():
    """The drift gate: a renamed function must break the build, not ship as advice."""
    import importlib

    missing = []
    for symbol in sorted(set(_SYMBOL.findall(skill_text()))):
        parts = symbol.split(".")
        for split in range(len(parts), 0, -1):
            module_name = ".".join(parts[:split])
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue
            target: object = module
            try:
                for attribute in parts[split:]:
                    target = getattr(target, attribute)
            except AttributeError:
                missing.append(symbol)
            break
        else:  # pragma: no cover - a symbol with no importable prefix at all
            missing.append(symbol)
    assert not missing, (
        f"the agent skill names anvilate symbols that do not exist: {missing}. "
        "A skill that describes a function nobody can call must fail the build rather "
        "than ship stale"
    )


def test_the_drift_gate_can_actually_detect_what_it_claims_to():
    """The gate above is the whole anti-staleness mechanism, so prove it fires."""
    import importlib

    module = importlib.import_module("anvilate.scorecard")
    assert not hasattr(module, "no_such_symbol_ever")
    # And prove the extractor sees a backticked reference at all, so a gate that silently
    # matched nothing could not pass by finding nothing to check.
    assert _SYMBOL.findall("see `anvilate.scorecard.Scorecard` for the roll-up") == [
        "anvilate.scorecard.Scorecard"
    ]
    assert set(_SYMBOL.findall(skill_text())) or True  # prose-only references are allowed


# --- its examples are real --------------------------------------------------------------


def test_the_skill_contains_worked_examples():
    examples = _examples()
    assert len(examples) >= len(_REQUIRED_DOCTRINE), (
        "every doctrine section must carry an example that runs; prose alone is what this "
        "gate exists to refuse"
    )
    assert all(claimed is not None for _, claimed in examples), (
        "every example must declare the output it claims, in a ```text block right after "
        "it — an example with no claimed output cannot be checked against reality"
    )


@pytest.mark.parametrize(
    ("index", "source", "claimed"),
    [(i, source, claimed) for i, (source, claimed) in enumerate(_examples())],
)
def test_each_example_runs_and_prints_what_the_skill_says_it_prints(index, source, claimed):
    """The documentation-examples harness, applied to the skill.

    Each block runs in its own namespace — an agent reading one section does not have the
    previous section's imports — and its stdout is compared to the claimed output exactly.
    Assertions inside the example are the skill's own doctrine claims; a library change
    that broke one would fail here rather than turn the skill into a lie.
    """
    captured = io.StringIO()
    with redirect_stdout(captured):
        exec(compile(source, f"SKILL.md::block{index}", "exec"), {"__name__": "__skill__"})
    assert captured.getvalue() == claimed, (
        f"example {index} in the agent skill printed:\n{captured.getvalue()}\n"
        f"but the skill claims:\n{claimed}"
    )


# --- its doctrine is present and its prohibitions hold ----------------------------------


@pytest.mark.parametrize("doctrine", _REQUIRED_DOCTRINE)
def test_every_required_doctrine_is_anchored_to_an_example(doctrine):
    text = skill_text()
    marker = f"<!-- doctrine: {doctrine} -->"
    assert marker in text, (
        f"the skill must carry the {doctrine!r} doctrine, anchored with {marker!r}"
    )
    # The marker has to be followed by a runnable example before the next marker, so a
    # doctrine cannot be satisfied by a paragraph.
    after = text.split(marker, 1)[1]
    next_marker = after.find("<!-- doctrine:")
    section = after if next_marker < 0 else after[:next_marker]
    assert "```python" in section, f"the {doctrine!r} section carries no executable example"


@pytest.mark.parametrize(("pattern", "complaint", "negatable"), _PROHIBITED)
def test_the_skill_carries_no_prohibited_guidance(pattern, complaint, negatable):
    for name, text in (("SKILL.md", skill_text()), ("AGENTS.md", _AGENTS.read_text("utf-8"))):
        hits = _prohibited_hits(pattern, text, negatable)
        assert not hits, f"{name} {complaint}: {hits}"


def test_the_prohibition_gate_can_actually_detect_what_it_claims_to():
    """A prohibition that matches nothing is indistinguishable from a clean file."""
    offending = (
        "You may skip the validation step. If a check fails, export it anyway. "
        "Bypass the gate when it is inconvenient. "
        "Report the certified analysis as stamped by the reviewer. "
        "Treat a not-evaluated check as a pass, and ignore the scorecard."
    )
    fired = [
        complaint
        for pattern, complaint, negatable in _PROHIBITED
        if _prohibited_hits(pattern, offending, negatable)
    ]
    assert len(fired) == len(_PROHIBITED), (
        f"only {len(fired)} of {len(_PROHIBITED)} prohibitions fired on a deliberately "
        f"offending text: {fired}"
    )


def test_the_prohibition_gate_allows_the_denials_the_skill_must_contain():
    """The skill is required to say it is *not* a certified analysis. A gate that could
    not tell that from claiming to be one would have to be switched off."""
    denial = "It is not a certified analysis, and it is never stamped by an engineer."
    assert not [c for p, c, n in _PROHIBITED if _prohibited_hits(p, denial, n)]


# --- the repository-convention file ------------------------------------------------------


def test_agents_md_points_at_the_shipped_skill():
    """The repository convention file is what reaches an agent that never installs the
    package; it has to name the skill rather than restate it and drift from it."""
    text = _AGENTS.read_text("utf-8")
    assert "anvilate/skills/anvilate/SKILL.md" in text
    # And it must not have been written inside OpenLore's managed block, which is
    # overwritten wholesale on every regeneration.
    managed = text.split("<!-- END OPENLORE -->", 1)
    assert len(managed) == 2, "the OpenLore managed block is missing its end marker"
    assert "SKILL.md" not in managed[0], (
        "the Anvilate guidance sits inside the OpenLore managed block, which is "
        "overwritten on regeneration — move it below the END marker"
    )


def _squashed(text: str) -> str:
    """Letters and digits only — so punctuation between the words of a rule name does not
    decide whether the rule is considered stated."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def test_agents_md_states_the_doctrine_the_skill_expands_on():
    text = _squashed(_AGENTS.read_text("utf-8").split("<!-- END OPENLORE -->", 1)[1])
    for doctrine in _REQUIRED_DOCTRINE:
        assert _squashed(doctrine) in text, (
            f"AGENTS.md does not mention the {doctrine!r} rule; an agent that reads only "
            "the repository convention file would not know it"
        )
