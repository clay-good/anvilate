"""The reusable CI action, held against the CLI it drives.

`headless-automation` asks for "revalidating all specs in a repository on push — via a
documented container image and a reusable CI action". The action is that half. The
container is not shipped and the reason is written down on the docs page rather than left
as a gap somebody has to notice.

An action's shell script is the least-tested code in most repositories: nothing imports it,
nothing type-checks it, and it runs for the first time on somebody else's pull request. So
the commands it issues are resolved against the real CLI here — every flag it passes must
exist, and every exit code it reasons about must be one the CLI can actually return.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from anvilate.cli import EXIT_CODES, EXIT_NOT_EVALUATED, EXIT_OK, _build_parser

_ACTION = Path(__file__).resolve().parent.parent / ".github" / "actions" / "check" / "action.yml"


@pytest.fixture(scope="module")
def action() -> dict:
    return yaml.safe_load(_ACTION.read_text(encoding="utf-8"))


def _script(action: dict) -> str:
    steps = action["runs"]["steps"]
    return "\n".join(step.get("run", "") for step in steps)


def test_the_action_is_a_composite_that_declares_every_input_it_uses(action):
    assert action["runs"]["using"] == "composite"
    script = _script(action)
    # Every ANVILATE_* variable the script reads is bound by an `env:` block above it.
    read = set(re.findall(r"\$\{?(ANVILATE_\w+)", script))
    bound = {name for step in action["runs"]["steps"] for name in (step.get("env") or {})}
    assert read <= bound, f"the script reads {sorted(read - bound)}, which nothing binds"
    assert read, "the script reads no inputs, so this gate checked nothing"


def test_every_flag_the_action_passes_exists_on_the_cli(action):
    """A flag renamed in the CLI leaves the action passing one the parser will refuse — on
    somebody else's pull request, in a shell script nothing type-checks."""
    parser = _build_parser()
    flags = set(re.findall(r"anvilate check [^\n]*?(--[a-z-]+)", _script(action)))
    assert flags, "the action passes no flags, so this gate checked nothing"
    for flag in flags:
        completed = subprocess.run(
            [sys.executable, "-m", "anvilate.cli", "check", "--help"],
            capture_output=True,
            text=True,
            cwd=_ACTION.parents[3],
            env={"PYTHONPATH": str(_ACTION.parents[3] / "src"), "PATH": "/usr/bin:/bin"},
            check=False,
        )
        assert flag in completed.stdout, f"the action passes {flag}, which `check` does not take"
    assert parser is not None


def test_the_action_forgives_exactly_one_exit_code_and_says_which(action):
    """`allow-not-evaluated` is off by default and the description says why.

    A merge gate that treats "could not run" as a pass is the silent green the whole tool
    exists to avoid, so the default is asserted here rather than trusted to stay.
    """
    inputs = action["inputs"]
    assert inputs["allow-not-evaluated"]["default"] == "false"
    assert "not a screen that passed" in inputs["allow-not-evaluated"]["description"]

    script = _script(action)
    forgiven = set(re.findall(r'"\$status" -eq (\d+)', script))
    assert forgiven == {str(EXIT_NOT_EVALUATED)}, (
        f"the action forgives exit codes {sorted(forgiven)}; only "
        f"{EXIT_NOT_EVALUATED} is ever forgivable, and only when asked"
    )
    assert str(EXIT_OK) not in forgiven


def test_the_exit_codes_the_action_documents_are_the_cli_s_own(action):
    """The script's comment lists what each code means. A comment is where drift hides, so
    the mapping is compared to `EXIT_CODES` rather than read."""
    script = _script(action)
    documented = {
        int(code): meaning.strip()
        for code, meaning in re.findall(r"^\s*#\s+(\d) (.+)$", script, re.MULTILINE)
    }
    assert len(documented) >= 5, f"read only {documented} out of the action's comment"
    assert documented[EXIT_OK].startswith("passed")
    assert documented[EXIT_NOT_EVALUATED] == "a card could not be evaluated"
    for code in EXIT_CODES.values():
        assert code in documented, f"exit code {code} is undocumented in the action"


def test_the_action_runs_the_check_before_deciding_anything(action):
    """The report is written first so a failing run still produces one — a CI job that
    fails and leaves no artifact is a job somebody has to re-run to understand."""
    script = _script(action)
    assert script.index("--format json") < script.index("status=$?")
    assert "set -uo pipefail" in script, "an unset variable must not silently become empty"


def test_the_docs_page_documents_the_action_and_says_what_is_not_shipped():
    page = (_ACTION.parents[3] / "docs" / "headless-cli.md").read_text(encoding="utf-8")
    assert ".github/actions/check" in page
    for name in yaml.safe_load(_ACTION.read_text(encoding="utf-8"))["inputs"]:
        assert f"`{name}`" in page, f"the action takes {name} and the page does not say so"
    assert "container image" in page, "the half that is not shipped has to say so"


def test_every_input_the_action_declares_is_wired_into_a_step(action):
    """An input declared and never read is a promise the action does not keep.

    Removing the step that writes the evidence bundles left `bundles` declared, documented
    and inert, and every other gate in this file still passed: the env block still bound it,
    and a subset check cannot see a binding nothing reads.
    """
    import yaml as yaml_module

    rendered = yaml_module.dump(action["runs"])
    for name in action["inputs"]:
        assert f"inputs.{name}" in rendered, f"the action declares {name!r} and no step reads it"


def test_each_optional_output_file_is_written_by_its_own_command(action):
    """`report` and `bundles` are different artifacts and must come from different commands
    — writing the scorecard twice under two names would satisfy a mention check."""
    script = _script(action)
    assert 'anvilate check "$ANVILATE_PATH" --format json > "$ANVILATE_REPORT"' in script
    assert 'anvilate export "$ANVILATE_PATH" --format json > "$ANVILATE_BUNDLES"' in script
