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

_REPO = Path(__file__).resolve().parent.parent
_ACTION = _REPO / ".github" / "actions" / "check" / "action.yml"


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


def test_the_python_classifiers_are_the_versions_ci_actually_proves():
    """PyPI's version filter reads the classifiers, and nothing here read them back.

    They said 3.11 and only 3.11 while the CI matrix ran 3.11, 3.12 and 3.13 — so the
    package told every installer it supported one version of Python and the suite proved
    three. The direction is what makes it worth a gate: an *understated* claim fails no
    test, breaks no build, and simply loses the package to anyone filtering on the version
    they run.

    Both directions are held. A version added to the matrix and not to the classifiers is
    the drift that happened; a classifier added without a matrix row is a support claim
    nothing backs, which is the worse of the two.
    """
    import tomllib

    workflow = yaml.safe_load((_REPO / ".github" / "workflows" / "ci.yml").read_text())
    matrix = {
        str(version)
        for job in workflow["jobs"].values()
        for version in job.get("strategy", {}).get("matrix", {}).get("python-version", [])
    }
    assert len(matrix) >= 2, (
        f"the CI matrix came back as {sorted(matrix)}; this gate reads the wrong key or "
        "the matrix has collapsed to one version, and either way it proves nothing"
    )

    config = tomllib.loads((_REPO / "pyproject.toml").read_text(encoding="utf-8"))
    prefix = "Programming Language :: Python :: "
    claimed = {
        line.removeprefix(prefix)
        for line in config["project"]["classifiers"]
        if line.startswith(prefix)
    }
    assert claimed == matrix, (
        f"the classifiers claim Python {sorted(claimed)} and CI proves {sorted(matrix)}. "
        "PyPI filters on the classifiers, so an unclaimed version is a version nobody can "
        "find the package for, and a claimed one CI does not run is a promise nothing keeps"
    )

    # And the floor has to agree with the lowest version proved, or `pip` refuses an
    # interpreter the suite is green on — or accepts one it never sees.
    assert config["project"]["requires-python"] == f">={min(matrix, key=_version_key)}"


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def test_the_package_ships_the_marker_that_makes_its_annotations_visible():
    """Without `py.typed`, every consumer of the installed package sees `Any`.

    PEP 561: a type checker ignores inline annotations in an *installed* package unless the
    package ships the marker. This library annotates 1,899 public functions and shipped
    none of them — `mypy` on a two-line consumer script reported "module is installed, but
    missing library stubs or py.typed marker" and revealed `Any` for a call whose argument
    was the wrong type. Nothing in this repository could see that, because the suite runs
    against `src/` where the annotations are simply there.

    The file is empty on purpose: its presence is the whole signal, and content in it means
    something else (a partial-stub declaration).
    """
    marker = _REPO / "src" / "anvilate" / "py.typed"
    assert marker.is_file(), (
        "src/anvilate/py.typed is gone. Every downstream type checker will silently fall "
        "back to Any for this library, which is a failure only its users can see"
    )
    assert marker.read_bytes() == b"", (
        "py.typed is not empty. A non-empty marker declares partial stubs, which is a "
        "different claim from the one this package makes"
    )


def test_the_typed_marker_is_not_a_promise_the_package_breaks():
    """A `py.typed` on an unannotated package is worse than no marker at all.

    It tells a consumer's checker to trust what it finds, so a missing annotation stops
    being an unknown and becomes an implicit `Any` the checker will not warn about. The
    marker is therefore gated on the annotations being there — over the *public* surface,
    which is the only part a consumer can reach.
    """
    import importlib
    import inspect

    src = _REPO / "src" / "anvilate"
    unannotated: list[str] = []
    total = 0
    for path in sorted(src.rglob("*.py")):
        name = ".".join(("anvilate", *path.relative_to(src).with_suffix("").parts))
        name = name.removesuffix(".__init__")
        module = importlib.import_module(name)
        for exported in getattr(module, "__all__", ()):
            function = getattr(module, exported, None)
            if not inspect.isfunction(function) or function.__module__ != name:
                continue
            total += 1
            signature = inspect.signature(function)
            complete = signature.return_annotation is not inspect.Signature.empty and all(
                parameter.annotation is not inspect.Parameter.empty
                for parameter in signature.parameters.values()
            )
            if not complete:
                unannotated.append(f"{name}.{exported}")

    assert total > 1000, f"the sweep found only {total} public functions, so it proves little"
    assert not unannotated, (
        "these public functions ship an incomplete signature under a py.typed marker, so a "
        f"consumer's checker will infer Any for them without saying so: {unannotated}"
    )
