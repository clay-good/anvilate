"""The quickstart, held to what it actually prints.

`documentation` asks for "a quickstart (install → first validated part) ... completable by
a new user in under 10 minutes of reading", and names it the front door. It is the one page
where a wrong line costs the most: a reader who cannot get the first example to run does not
reach the second.

So the page's own code is executed and its output compared, and the claims it makes about
that output are asserted rather than described.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_PAGE = (_REPO / "docs" / "quickstart.md").read_text(encoding="utf-8")


def _fenced(language: str, index: int = 0) -> str:
    blocks = re.findall(rf"```{language}\n((?:.|\n)*?)```", _PAGE)
    assert len(blocks) > index, f"the quickstart has {len(blocks)} {language} blocks"
    return blocks[index]


def test_the_first_example_prints_what_the_page_shows():
    """Run as a real subprocess, because the claim is about what a reader sees when they
    paste it — not about what the library returns."""
    source = _fenced("python")
    shown = _fenced("text")
    # The page shows the card; the snippet builds it. Print it the way the page does.
    program = source + (
        "\nprint(card.status.value.upper())\n"
        "for entry in card.entries:\n"
        "    print(f'  {entry.status.value:<6} {entry.name}: {entry.detail}')\n"
        "    print(f'         {entry.reference}')\n"
        "governing = card.governing()\n"
        "print('governing:', governing.name if governing else 'none')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        cwd=_REPO,
        env={"PYTHONPATH": str(_REPO / "src"), "PATH": "/usr/bin:/bin"},
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == shown, (
        f"the quickstart shows:\n{shown}\nthe example prints:\n{completed.stdout}"
    )


def test_the_four_claims_the_page_makes_about_that_card():
    """Each bullet under the output, asserted. They are the design of the library stated as
    facts about one card, so a bullet that stopped being true would be the worst kind of
    wrong page: convincing."""
    namespace: dict[str, object] = {}
    exec(compile(_fenced("python"), "<quickstart>", "exec"), namespace)  # noqa: S102
    card = namespace["card"]

    # "The material came from a table" — with a citation behind it.
    from anvilate.standards import default_materials_db

    material = default_materials_db().get("ASTM-A36")
    assert material.name and "A36" in material.name

    # "Both checks ran and both are reported."
    assert len(card.entries) == 2, [e.name for e in card.entries]
    statuses = {entry.name: entry.status.value for entry in card.entries}
    assert set(statuses.values()) == {"pass", "fail"}, statuses

    # "Every entry cites its clause" — and the page shows the clause it cites.
    for entry in card.entries:
        assert entry.reference, f"{entry.name} cites nothing"
        assert entry.reference in _PAGE, f"{entry.reference!r} is absent from the page"

    # "The card is FAIL because its worst entry is", and `governing()` names which.
    assert card.status.value == "fail"
    governing = card.governing()
    assert governing is not None
    assert governing.status.value == "fail"
    assert f"governing: {governing.name}" in _PAGE


def test_the_page_states_the_exit_code_rule_the_cli_actually_uses():
    """The one rule the page asks a reader to carry into CI, so it has to be the real one."""
    from anvilate.cli import EXIT_CODES, EXIT_FAILED, EXIT_NOT_EVALUATED, EXIT_OK
    from anvilate.scorecard import CheckStatus

    assert "2 is not a pass" in _PAGE
    assert EXIT_CODES[CheckStatus.PASS] == EXIT_OK == 0
    assert EXIT_CODES[CheckStatus.FAIL] == EXIT_FAILED == 1
    assert EXIT_CODES[CheckStatus.NOT_EVALUATED] == EXIT_NOT_EVALUATED == 2
    for phrase in ("0 only when every check passed", "1 when one failed", "2 when"):
        assert phrase in _PAGE, phrase


def test_the_install_line_is_the_distribution_that_is_published():
    """A quickstart whose first command installs the wrong name is a page nobody gets past."""
    import tomllib

    config = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    name = config["project"]["name"]
    # The *token*, not a substring: "pip install anvilate" is contained in
    # "pip install anvilate-lib", so a page installing the wrong distribution passed.
    installed = {
        token.strip("\"'").split("[")[0] for token in re.findall(r"pip install (\S+)", _PAGE)
    }
    assert installed == {name}, f"the quickstart installs {sorted(installed)}, not {name!r}"

    extras = set(config["project"]["optional-dependencies"])
    mentioned = set(re.findall(rf"{name}\[(\w+)\]", _PAGE))
    assert mentioned <= extras, f"the page offers extras that do not exist: {mentioned - extras}"
    assert mentioned, "the page mentions no extra, so this gate checked nothing"


def test_the_quickstart_is_short_enough_to_be_a_quickstart():
    """ "completable by a new user in under 10 minutes of reading" is a length claim as much
    as a content one. Prose words only — code blocks are read differently."""
    prose = re.sub(r"```(?:.|\n)*?```", "", _PAGE)
    words = len(prose.split())
    assert words < 700, f"the quickstart runs to {words} words of prose"
    assert words > 150, f"the quickstart is {words} words; it explains nothing"
