"""Session-wide hooks: two ratchets that only a running suite can measure.

The first catches assertions ``pytest.approx`` has disarmed. The second — at the foot of
this file — is the derivation-coverage ratchet, which records which cited clauses ship a
worked calculation and which do not.

THE DISARMED-APPROX RATCHET.

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


@pytest.fixture(autouse=True)
def _subject_store_stays_out_of_the_users_cache(tmp_path, monkeypatch):
    """The MCP subject store defaults to the user's cache directory, and a test that publishes
    a handle would write there.

    The dataset cache has the same shape and the fetch tests pass a temporary directory for
    exactly this reason; an autouse fixture is the version that cannot be forgotten, since a
    test three files away can publish a subject by calling a tool.
    """
    monkeypatch.setenv("ANVILATE_SUBJECT_STORE", str(tmp_path / "subjects"))


def pytest_configure(config: pytest.Config) -> None:
    pytest.approx = _recording_approx
    _install_the_coverage_collector()


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

    coverage = _observed_coverage()
    registry = _read_registry()
    uncovered = _coverage_failures(coverage, registry)
    if uncovered:
        print(
            "\nDERIVATION COVERAGE: these checks do not agree with "
            "docs/api/underived-checks.txt:\n  " + "\n  ".join(uncovered)
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

    paid = _paid_off_debts(coverage, registry)
    if paid:
        print(
            "\nDERIVATION COVERAGE: every entry of these now carries a derivation, so "
            "they are no longer debt. Strike them from [debt] in "
            "docs/api/underived-checks.txt:\n  " + "\n  ".join(paid)
        )
        session.exitstatus = 1

    worked, cited = _derivation_coverage_ratio(coverage)
    print(f"\nderivation coverage: {worked}/{cited} cited clauses fully worked")

    # A registered clause nothing produces any more is a line that can never be paid off
    # and can never fail, which is how a ratchet stops meaning anything. Only a full run
    # can tell a retired check from one this selection did not reach.
    stale = _stale_registry_lines(coverage, registry)
    if stale:
        print(
            "\nDERIVATION COVERAGE: these clauses are registered in "
            "docs/api/underived-checks.txt but no check cites them any more. Strike "
            "them:\n  " + "\n  ".join(stale)
        )
        session.exitstatus = 1


# ---------------------------------------------------------------------------
# The derivation-coverage ratchet.
#
# `calculation-report` requires CI to report the worked/total ratio and to fail when a new
# check ships without derivation metadata. A check is keyed by the clause it cites — the
# same key docs/api/editionless-citations.txt uses, and the thing a reviewer reads — and a
# clause counts as covered only when EVERY library-produced entry citing it carries a
# Derivation. Half a clause renders a worked formula for some parts and a bare table for
# others, which reads as though all of it was derived.
#
# The registry has two sections and they are not interchangeable; see the header of
# docs/api/underived-checks.txt. The gate enforces the distinction from the data rather
# than from the honesty of the reason: an entry carrying a computed safety factor is a
# quotient, a quotient is a formula, and a formula is not a lookup. So a debt cannot be
# retired by being relabelled.
# ---------------------------------------------------------------------------

_REGISTRY = _REPO / "docs" / "api" / "underived-checks.txt"

# The entry and derivation machinery is never the check that produced an entry — every
# pack reaches ScorecardEntry through `from_safety_factor`, so the nearest source frame is
# scorecard.py for library and test callers alike, and reading it would count every entry a
# test hand-builds as one of the library's own checks.
_ENTRY_MACHINERY = frozenset({"scorecard.py", "derivation.py", "_models.py"})

_SRC = _REPO / "src" / "anvilate"

# Surviving library-built entries, by id. Kept as strong references for the whole run so no
# id is reused, and superseded when the library copies an entry to attach its citation or
# its derivation — the pre-copy value is a half-built entry, not a check that shipped.
_library_entries: dict[int, object] = {}


def _built_by_the_library() -> bool:
    """Whether the call being made now comes from a check inside ``src/anvilate``."""
    frame = inspect.currentframe()
    while frame is not None:
        path = Path(frame.f_code.co_filename)
        if path.name not in _ENTRY_MACHINERY:
            try:
                path.relative_to(_SRC)
            except ValueError:
                pass
            else:
                return True
        frame = frame.f_back
    return False


def _install_the_coverage_collector() -> None:
    from anvilate.scorecard import ScorecardEntry

    original_init = ScorecardEntry.__init__
    original_copy = ScorecardEntry.model_copy

    def recording_init(self, **data):
        original_init(self, **data)
        if _built_by_the_library():
            _library_entries[id(self)] = self

    def recording_copy(self, **kwargs):
        copied = original_copy(self, **kwargs)
        if _built_by_the_library():
            _library_entries.pop(id(self), None)
            _library_entries[id(copied)] = copied
        return copied

    ScorecardEntry.__init__ = recording_init
    ScorecardEntry.model_copy = recording_copy


def _observed_coverage() -> dict[str, tuple[int, int, int]]:
    """Per cited clause: how many entries carry a derivation, how many were evaluated, and
    how many carry a computed safety factor."""
    from anvilate.scorecard import CheckStatus

    coverage: dict[str, list[int]] = {}
    for entry in _library_entries.values():
        if not entry.reference:
            continue
        # A check that could not run has no result, so it has no worked calculation to
        # render and asking it for one is asking it to invent the number it just refused
        # to produce. NOT_EVALUATED entries are outside the denominator; a clause that
        # only ever refuses leaves the census altogether.
        if entry.status is CheckStatus.NOT_EVALUATED:
            continue
        counts = coverage.setdefault(str(entry.reference), [0, 0, 0])
        counts[1] += 1
        if entry.derivation is not None:
            counts[0] += 1
        if entry.safety_factor is not None:
            counts[2] += 1
    return {clause: tuple(counts) for clause, counts in coverage.items()}


def _read_registry() -> dict[str, tuple[str, str]]:
    """The registry as ``clause -> (section, reason)``."""
    registry: dict[str, tuple[str, str]] = {}
    section = ""
    for line in _REGISTRY.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1]
            continue
        clause, separator, reason = text.partition(" :: ")
        registry[clause] = (section, reason if separator else "")
    return registry


def _coverage_failures(
    coverage: dict[str, tuple[int, int, int]],
    registry: dict[str, tuple[str, str]],
) -> list[str]:
    """Everything the ratchet can conclude from the clauses this run actually observed.

    Every rule here fires on positive evidence — an underived entry that exists, a
    derivation that exists, a safety factor that exists — so it is correct on a filtered
    run too: a subset of the suite observes a subset of the clauses and never a clause
    that is not there.

    The two rules that read an ABSENCE need the whole suite and live below: a debt with no
    underived entry left, and a registered clause nothing produced at all. On a filtered
    run both are indistinguishable from a test that simply did not run — `pytest
    tests/test_contract.py` alone reaches the derived half of the plate checks and none of
    the rest, and reported the plate clause as paid off.
    """
    failures: list[str] = []
    for clause in sorted(coverage):
        derived, total, safety_factors = coverage[clause]
        section, reason = registry.get(clause, ("", ""))
        if derived < total and clause not in registry:
            failures.append(
                f"{clause}: {total - derived} of {total} entries carry no derivation, and "
                f"the clause is on neither list in docs/api/underived-checks.txt. Attach a "
                f"Derivation to the check — a new check ships with one"
            )
        elif section == "lookup" and derived:
            failures.append(
                f"{clause}: registered as a lookup — {reason} — but {derived} of its "
                f"entries carry a derivation, so it had a formula to render after all"
            )
        elif section == "lookup" and safety_factors:
            failures.append(
                f"{clause}: registered as a lookup, but {safety_factors} of its entries "
                f"carry a computed safety factor. A safety factor is a quotient and a "
                f"quotient is a formula; this is debt filed as a lookup"
            )
    return failures


def _paid_off_debts(
    coverage: dict[str, tuple[int, int, int]],
    registry: dict[str, tuple[str, str]],
) -> list[str]:
    """Debts whose every evaluated entry now carries a derivation — only on a full run."""
    return sorted(
        clause
        for clause, (derived, total, _) in coverage.items()
        if registry.get(clause, ("", ""))[0] == "debt" and derived == total
    )


def _stale_registry_lines(
    coverage: dict[str, tuple[int, int, int]],
    registry: dict[str, tuple[str, str]],
) -> list[str]:
    """Registered clauses no check produced at all — only meaningful on a full run."""
    return sorted(set(registry) - set(coverage))


def _derivation_coverage_ratio(coverage: dict[str, tuple[int, int, int]]) -> tuple[int, int]:
    """Clauses every entry of which is derived, over clauses cited."""
    return sum(1 for derived, total, _ in coverage.values() if derived == total), len(coverage)
