"""Session-wide hooks. Currently one: catching assertions pytest.approx has disarmed.

``pytest.approx`` applies a DEFAULT ``abs=1e-12`` alongside whatever ``rel=`` is written,
and takes whichever tolerance is *looser*. On a sub-nanoscale quantity that floor is
enormous relative to the value — for a 1.67e-27 kg proton mass it is 1e15 times the
number — so the ``rel=`` does nothing and the assertion degenerates to "the answer is
small". A formula wrong by fifteen orders of magnitude passes. That is a silent green of
exactly the kind this library exists to refuse.

The static gate in ``tests/test_contract.py`` reads the source and catches every form
whose expected value can be folded: a literal, an arithmetic expression, a module-level
constant, the ``expected=`` keyword. It cannot catch the form that matters most in this
suite — ``approx(some_call().magnitude / other)``, where the value only exists at run
time — and an audit found 38 such sites, none of them visible to source reading.

So this records them as they actually happen. The recorded set is held against
``docs/api/disarmed-approx-sites.txt`` as a ratchet, the same shape as the citation and
design-inverse manifests: a new disarmed site fails the run, and a listed site that has
since been armed must be struck off, so the list can only shrink and cannot go stale.

To pay a line off: assert in a scaled unit (pm, ps, pW, uA) so the magnitude is
order-one, or pass an explicit ``abs=`` sized to the value. Comparisons against a literal
zero are exempt — there the absolute floor is the whole point.
"""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_MANIFEST = _REPO / "docs" / "api" / "disarmed-approx-sites.txt"

# The scale below which the 1e-12 default floor swamps a relative tolerance.
_DISARMED_BELOW = 1e-9

_recorded: set[str] = set()
_real_approx = pytest.approx


def _site() -> str | None:
    """The test that called approx, as 'file.py::test_name'.

    Keyed on the test rather than the line, because a line number is invalidated by any
    edit above it — a manifest of line numbers would go stale on the first unrelated
    change and the ratchet would report nonsense. The test is the unit of repair anyway:
    several disarmed assertions in one test are one thing to fix.
    """
    for frame in inspect.stack()[2:]:
        path = Path(frame.filename)
        if path.name.startswith("test_") and path.suffix == ".py":
            if frame.function.startswith("test_"):
                return f"{path.name}::{frame.function}"
            return f"{path.name}::{frame.function} (helper)"
    return None


def _recording_approx(expected=None, rel=None, abs=None, nan_ok=False):  # noqa: A002
    if abs is None and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if 0 < builtins_abs(expected) < _DISARMED_BELOW:
            site = _site()
            if site is not None:
                _recorded.add(site)
    return _real_approx(expected, rel=rel, abs=abs, nan_ok=nan_ok)


builtins_abs = abs  # captured before the parameter named `abs` shadows it


def _manifest() -> set[str]:
    if not _MANIFEST.exists():  # pragma: no cover - the file ships with the repo
        return set()
    return {
        line.strip()
        for line in _MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


# Packages only the scheduled CI jobs install: the interchange-schema job adds lxml, the
# optional-adapter job adds the finite-element packages. Every *other* import a test can
# skip on is promised by the dev extra, and a skip for one of those in CI means the gate
# did not run and the build went green anyway — the quietest silent green there is.
# `lxml.etree` is listed beside `lxml` because that is the name a test imports.
# `tests/test_contract.py` holds this set against what the workflow's scheduled jobs
# actually install, so it cannot quietly grow an entry no job backs.
_SCHEDULED_ONLY_IMPORTS = frozenset({"lxml", "lxml.etree", "sectionproperties", "pycufsm"})

_import_skips: set[str] = set()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record which module each skipped test could not import."""
    if report.skipped and isinstance(report.longrepr, tuple):
        _, _, reason = report.longrepr
        missing = re.search(r"could not import '([^']+)'", reason)
        if missing is not None:
            _import_skips.add(f"{missing.group(1)}|{report.nodeid}")


def pytest_configure(config: pytest.Config) -> None:
    pytest.approx = _recording_approx


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    pytest.approx = _real_approx

    # A gate that skips is a gate that did not run. Locally that is fine — the optional
    # packages are optional. In CI the dev extra is installed, so a skip for anything but
    # the scheduled-job packages means a dependency quietly went missing.
    if os.environ.get("CI"):
        unexpected = sorted(
            entry
            for entry in _import_skips
            if entry.split("|", 1)[0] not in _SCHEDULED_ONLY_IMPORTS
        )
        if unexpected:
            print(
                "\nGATES SKIPPED IN CI: these tests skipped because a package the dev "
                "extra promises is missing, so the checks they carry did not run:\n  "
                + "\n  ".join(unexpected)
            )
            session.exitstatus = 1
            return

    recorded, known = _recorded, _manifest()

    new = sorted(recorded - known)
    if new:
        print(
            "\nDISARMED APPROX ASSERTIONS (new): pytest.approx's default abs=1e-12 swamps "
            "the rel= at these sites, so the tolerance does nothing. Assert in a scaled "
            "unit or pass an explicit abs=:\n  " + "\n  ".join(new)
        )
        session.exitstatus = 1
        return

    # The other direction of the ratchet: a site that has since been armed must come off
    # the list, or the list drifts and stops meaning anything. Only checked on a FULL
    # run — a filtered, path-restricted or failed run simply did not reach the rest of
    # the sites, and failing it would punish `pytest tests/test_contract.py`, which is a
    # thing people do all day.
    filtered = bool(
        session.config.option.keyword
        or session.config.option.markexpr
        or session.config.option.lf
        or list(session.config.args) != list(session.config.getini("testpaths"))
    )
    if exitstatus != 0 or filtered or session.testsfailed:
        return
    armed = sorted(known - recorded)
    if armed:
        print(
            "\nDISARMED APPROX ASSERTIONS (now armed): these are recorded as disarmed but "
            "no longer are. Strike them from docs/api/disarmed-approx-sites.txt so the "
            "list stays honest:\n  " + "\n  ".join(armed)
        )
        session.exitstatus = 1
