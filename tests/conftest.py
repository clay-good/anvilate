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

    citations = _observed_citations()
    unversioned = sorted(_editionless_citations(citations) - _editionless_manifest())
    if unversioned:
        print(
            "\nEDITIONLESS CITATIONS: these name a normative standard and not its edition. "
            "Add the edition exactly as the standard spells it (AISC 360-16, ACI 318-19, "
            "EN 1993-1-9:2005) — do NOT add the reference to "
            "docs/api/editionless-citations.txt:\n  " + "\n  ".join(unversioned)
        )
        session.exitstatus = 1
        return

    # Unit fidelity, over every entry the suite built rather than over a corpus somebody
    # listed. It fires on positive evidence — a line that carries a unit it should not — so
    # a filtered run checks the subset it reached and is never wrong about it.
    unglossed, glossed = _derivations_with_an_unglossed_symbol()
    if unglossed:
        print(
            "\nSYMBOL GLOSSARY: these derivations use a symbol they do not define, so the "
            "report renders them as a table of inputs instead of the worked calculation "
            "`calculation-report` requires:\n  " + "\n  ".join(unglossed[:20])
        )
        session.exitstatus = 1
        return

    # Positive evidence — it reports the lines that DO say a forbidden thing — so a
    # filtered run checks the subset it reached and is never wrong about it. The floor
    # that keeps it from passing on an empty set reads an absence, so it waits for a full
    # run, below.
    assurance, assurance_swept = _assurance_language_lines()
    if assurance:
        print(
            "\nASSURANCE LANGUAGE: a screening tool must never use the vocabulary of "
            "certification about a user's design, and these renderings do:\n  "
            + "\n  ".join(assurance)
        )
        session.exitstatus = 1
        return

    mixed = _mixed_unit_lines()
    if mixed:
        print(
            "\nUNIT FIDELITY: these lines carry a unit from a system the document did not "
            "declare, so a reviewer is asked to check arithmetic across two systems:\n  "
            + "\n  ".join(mixed)
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

    # The same, for the assurance sweep: a renderer that started returning blank would
    # empty it without failing anything. The library builds thousands of entries on a full
    # run, so a few hundred texts is a floor no honest run comes near.
    if assurance_swept < 500:
        print(
            f"\nASSURANCE LANGUAGE: only {assurance_swept} rendered texts were swept, so "
            f"this gate is passing on an all but empty set"
        )
        session.exitstatus = 1
        return

    # The discoverer has to keep discovering. A parser that stopped RECOGNISING standards
    # would make the editionless set empty and both directions of that ratchet would go
    # green for ever.
    from anvilate.standards.effectivity import names_a_standard

    recognised = sum(1 for text in citations if names_a_standard(text) is not None)
    if recognised < 10:
        print(
            f"\nEDITIONLESS CITATIONS: names_a_standard recognises only {recognised} of "
            f"the {len(citations)} references this suite builds, so the effectivity gate "
            f"is passing on an all but empty set"
        )
        session.exitstatus = 1
        return

    versioned = sorted(_editionless_manifest() - _editionless_citations(citations))
    if versioned:
        print(
            "\nEDITIONLESS CITATIONS: these are recorded as editionless but no longer are, "
            "or are no longer cited. Strike them from "
            "docs/api/editionless-citations.txt:\n  " + "\n  ".join(versioned)
        )
        session.exitstatus = 1
        return

    paid = _paid_off_debts(coverage, registry)
    if paid:
        print(
            "\nDERIVATION COVERAGE: every entry of these now carries a derivation or "
            "states why it has none, so they are no longer debt. Strike them from [debt] in "
            "docs/api/underived-checks.txt:\n  " + "\n  ".join(paid)
        )
        session.exitstatus = 1

    worked, answered, cited = _derivation_coverage_ratio(coverage)
    print(
        f"\nderivation coverage: {worked}/{cited} cited clauses fully worked, "
        f"{answered}/{cited} fully answered"
    )

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
# clause counts as covered only when EVERY library-produced entry citing it has ANSWERED.
# Half a clause renders a worked formula for some parts and a bare table for others, which
# reads as though all of it was derived.
#
# ANSWERED means the entry carries a Derivation, or carries an `Underived` — the check's
# own statement that it has no formula and why. The second is what the clause key could
# not express: a clause cited by a computing check and by an exempt one is one line in the
# registry, and the line has to be right for both. Three debts were nothing but that
# failure and could not be worked off at all — paying off the derivable half of one moved
# the ratio by nothing, which is a meter that stops while the work happens.
#
# So the registry no longer decides the kind; the entry does, and what is left in the file
# is debt. See the header of docs/api/underived-checks.txt. The distinction is still
# enforced from the data rather than from the honesty of the reason: an entry carrying a
# computed safety factor is a quotient, a quotient is a formula, and `ScorecardEntry`
# refuses to let such an entry declare it has none. So a debt cannot be retired by being
# relabelled.
# ---------------------------------------------------------------------------

_REGISTRY = _REPO / "docs" / "api" / "underived-checks.txt"

# The entry and derivation machinery is never the check that produced an entry — every
# pack reaches ScorecardEntry through `from_safety_factor`, so the nearest source frame is
# scorecard.py for library and test callers alike, and reading it would count every entry a
# test hand-builds as one of the library's own checks.
_ENTRY_MACHINERY = frozenset({"scorecard.py", "derivation.py", "_models.py"})

# ---------------------------------------------------------------------------
# Reading a node's source text, for the AST sweeps.
#
# `ast.get_source_segment` re-splits the ENTIRE file on every call, so a sweep over one
# module's 210 raise sites costs 1.6 seconds — and three such gates added 56 seconds to the
# pre-push gate before anybody measured them. Slicing pre-split lines is ~13,000x faster and
# gives whole lines rather than exact columns, which is all a regex over a refusal message
# needs.
# ---------------------------------------------------------------------------

_SOURCE_LINES: dict[Path, list[str]] = {}


def source_text(path: Path, node: object) -> str:
    """The source lines ``node`` spans, from a per-file cache."""
    lines = _SOURCE_LINES.get(path)
    if lines is None:
        lines = _SOURCE_LINES[path] = path.read_text(encoding="utf-8").splitlines()
    start = getattr(node, "lineno", 0) - 1
    end = getattr(node, "end_lineno", None) or (start + 1)
    return "\n".join(lines[start:end])


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


def _counts_as_worked(entry) -> bool:
    """Whether ``entry`` carries a derivation the report will actually render as worked.

    The same condition :meth:`anvilate.report.ReportSection.is_worked` applies, and it has
    to be the same one: a derivation whose formula names a symbol it never declares renders
    with a bare symbol where a number belongs, so the document falls back to the inputs
    table. Counting it here would report a coverage the document does not deliver.
    """
    derivation = getattr(entry, "derivation", None)
    return derivation is not None and not derivation.unresolved_symbols()


def _observed_coverage() -> dict[str, tuple[int, int, int, int]]:
    """Per cited clause: how many entries are worked, how many ANSWERED, how many were
    evaluated, and how many carry a computed safety factor.

    An entry is *answered* when it carries a worked derivation **or** declares, on itself,
    why it has none. The two are the same fact to a reviewer — the check has said what its
    arithmetic is, including when there is not any — and separating them is what made a
    clause cited by one computing check and one exempt check impossible to work off.
    """
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
        counts = coverage.setdefault(str(entry.reference), [0, 0, 0, 0])
        counts[2] += 1
        if _counts_as_worked(entry) or getattr(entry, "underived", None) is not None:
            counts[1] += 1
        # WORKED, not merely present. A derivation whose formula names a symbol it never
        # declares renders with a bare symbol where a number belongs, so `Report` refuses
        # to show it as worked and falls back to the inputs table. Counting it as covered
        # here would report a coverage the document does not deliver — the hidden gap
        # `Derivation.unresolved_symbols` exists to prevent, arrived at from the other side.
        if _counts_as_worked(entry):
            counts[0] += 1
        if entry.safety_factor is not None:
            counts[3] += 1
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
    coverage: dict[str, tuple[int, int, int, int]],
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
        _derived, answered, total, _safety_factors = coverage[clause]
        if answered < total and clause not in registry:
            failures.append(
                f"{clause}: {total - answered} of {total} entries neither carry a "
                f"derivation nor declare why they have none, and the clause is not in "
                f"docs/api/underived-checks.txt. Attach a Derivation to the check — a new "
                f"check ships with one — or, if it has no formula, an Underived"
            )
    return failures


def _paid_off_debts(
    coverage: dict[str, tuple[int, int, int, int]],
    registry: dict[str, tuple[str, str]],
) -> list[str]:
    """Registered clauses whose every evaluated entry has now ANSWERED — full runs only.

    Answered, not derived: the three debts this rule could never clear were clauses whose
    computing entries were fully worked and whose one non-computing entry had nothing to
    render. Paying off the derivable half of such a clause moved the ratio by nothing,
    which is a meter that stops while the work happens.

    It reads an ABSENCE — no unanswered entry left — so a filtered run cannot act on it: a
    selection that happens to reach only a clause's answering entries would report a line
    as strikeable when it is not.
    """
    return sorted(
        clause
        for clause, (_, answered, total, _sf) in coverage.items()
        if clause in registry and answered == total
    )


def _stale_registry_lines(
    coverage: dict[str, tuple[int, int, int, int]],
    registry: dict[str, tuple[str, str]],
) -> list[str]:
    """Registered clauses no check produced at all — only meaningful on a full run."""
    return sorted(set(registry) - set(coverage))


def _derivation_coverage_ratio(
    coverage: dict[str, tuple[int, int, int, int]],
) -> tuple[int, int, int]:
    """Clauses fully worked, clauses fully answered, and clauses cited.

    Both numerators are reported because they measure different things. *Worked* is how
    much of the library renders a substitutable formula. *Answered* is how much of it has
    said anything at all about its arithmetic, and it is the one that reaches 100% — a
    lifter's Class 0 exemption will never acquire a formula, and a clause carrying one is
    finished, not short.
    """
    return (
        sum(1 for derived, _, total, _sf in coverage.values() if derived == total),
        sum(1 for _, answered, total, _sf in coverage.values() if answered == total),
        len(coverage),
    )


# ---------------------------------------------------------------------------
# The unit-fidelity sweep.
#
# `calculation-report`'s "Unit-system fidelity in derivations" says nothing in a document
# may carry a unit from a system the document did not declare. Two fixes made that true —
# a display preference no longer overrides a declared system, and a comparison verdict is
# restated by the report rather than baked by the screen — and both were found by rendering
# a report and reading it, which is not a thing CI does.
#
# So it is swept here, over every entry the suite actually built, in the same way the
# derivation ratchet is: a listed corpus checks the packs somebody remembered.
# ---------------------------------------------------------------------------

# Matched on a WORD boundary, not as a substring. The first version looked for " in" and
# found it in "/ inf" — a Miner sum whose allowable life is infinite below the cutoff — and
# reported two fatigue derivations as mixing unit systems. A gate's own false positive is
# indistinguishable from the defect it hunts until somebody reads the line.
_SI_ONLY = ("mm", "MPa", "GPa", "kPa", "kN·m", "N·mm")
_US_ONLY = ("in", "ft", "kip", "ksi", "psi")


def _mixed_unit_lines() -> list[str]:
    """Every rendered line that carries a unit belonging to the other system."""
    from anvilate.units import UnitSystem

    offenders: list[str] = []
    seen: set[tuple[str, str]] = set()
    for entry in _library_entries.values():
        renderings = []
        if entry.comparison is not None:
            renderings.append(("verdict", entry.comparison.sentence))
        if entry.derivation is not None:
            renderings.append(("derivation", entry.derivation.substituted))
        for what, render_line in renderings:
            for system, forbidden in ((UnitSystem.US, _SI_ONLY), (UnitSystem.SI, _US_ONLY)):
                line = render_line(system=system)
                stray = sorted(
                    {unit for unit in forbidden if re.search(rf"(?<![\w·]){unit}\b", line)}
                )
                if not stray:
                    continue
                key = (system.value, line)
                if key in seen:
                    continue
                seen.add(key)
                offenders.append(
                    f"{entry.name} {what} under {system.value} carries {stray}: {line}"
                )
    return sorted(offenders)


# ---------------------------------------------------------------------------
# The effectivity ratchet, moved here from tests/test_contract.py.
#
# It held the same property it holds now — a reference naming a standards body must name
# an edition or be listed — over a much smaller set: the structural pack's entries plus
# whatever the render-truth sample happened to reach. Every other pack's citations were
# outside it, and the debt read as six references when the library actually builds
# twenty-two. It now reads the same collector the derivation ratchet does, so it cannot
# again be narrower than the library it is auditing.
# ---------------------------------------------------------------------------

_EDITIONLESS = _REPO / "docs" / "api" / "editionless-citations.txt"


def _observed_citations() -> set[str]:
    """Every citation string the library put on an entry or into a derivation.

    These are the references the evidence bundle carries — the ones a reviewer reads —
    rather than the prose in a docstring. Effectivity is a claim about the bundle, so this
    is the surface that has to carry an edition.
    """
    citations: set[str] = set()
    for entry in _library_entries.values():
        if entry.reference:
            citations.add(str(entry.reference))
        if entry.derivation is not None and entry.derivation.citation:
            citations.add(str(entry.derivation.citation))
    return citations


# ---------------------------------------------------------------------------
# Assurance language, over every entry the suite builds.
#
# `test_no_pack_ever_says_certified_about_a_user_s_design` calls itself "the library-wide
# half" and swept the structural pack plus a hand-reached derivation sample — the same
# narrowness the effectivity ratchet carried until it moved here. The risk it names is not
# confined to one pack: every detail line, verdict sentence and derivation the library
# builds is a statement about the user's design, and any one of them can be pasted into an
# email and read as assurance. So it runs off the same collector.
#
# Docstrings stay out of scope, for the reason the review suite gives: prose about the
# policy has to be able to name the thing it prohibits.
# ---------------------------------------------------------------------------


def _assurance_language_lines() -> tuple[list[str], int]:
    """Offending renderings, and how many texts were swept to find them.

    The count comes back because this rule fires on POSITIVE evidence: it reports the
    lines that say a forbidden thing, so a sweep over nothing finds nothing and passes.
    The caller holds it to a floor for the same reason the effectivity ratchet holds
    ``names_a_standard`` to one — a renderer that started returning blank would empty this
    gate and it would go green for ever.
    """
    from anvilate.review import PROHIBITED_ASSURANCE_LANGUAGE

    swept = 0
    offenders: list[str] = []
    seen: set[tuple[str, str]] = set()
    for entry in _library_entries.values():
        texts: list[tuple[str, str]] = [("name", entry.name), ("detail", entry.detail)]
        if entry.reference:
            texts.append(("reference", str(entry.reference)))
        if entry.comparison is not None:
            texts.append(("verdict", entry.comparison.sentence()))
        if entry.derivation is not None:
            texts.append(("derivation", entry.derivation.substituted()))
            if entry.derivation.citation:
                texts.append(("derivation citation", str(entry.derivation.citation)))
        for what, text in texts:
            if not text.strip():
                continue
            swept += 1
            lowered = text.lower()
            for phrase in sorted(PROHIBITED_ASSURANCE_LANGUAGE):
                if phrase not in lowered:
                    continue
                key = (phrase, text)
                if key in seen:
                    continue
                seen.add(key)
                offenders.append(f"{entry.name} {what} says {phrase!r}: {text}")
    return sorted(offenders), swept


# ---------------------------------------------------------------------------
# The symbol glossary, over every derivation the suite builds.
#
# `calculation-report` requires that a derivation "carry the check's citation … and a glossary
# line for **every symbol used**". `Derivation.unresolved_symbols` is the library's own
# scanner for that, and its docstring says what happens when it is non-empty: "the report
# refuses to render such a derivation as worked". So an unglossed symbol does not fail — the
# worked calculation quietly degrades to a table of inputs and outputs, which is the
# derivation-shaped version of a check that reports without saying it could not run.
#
# One hand-built derivation was gated for a universal requirement. This is the corpus.
# ---------------------------------------------------------------------------


def _derivations_with_an_unglossed_symbol() -> tuple[list[str], int]:
    """Offending derivations, and how many carried a formula to check."""
    offenders: list[str] = []
    checked = 0
    for entry in _library_entries.values():
        derivation = entry.derivation
        if derivation is None or not derivation.symbolic:
            continue
        checked += 1
        missing = derivation.unresolved_symbols()
        if missing:
            offenders.append(
                f"{entry.name}: {derivation.symbolic} leaves {list(missing)} unglossed"
            )
    return sorted(set(offenders)), checked


def _editionless_manifest() -> set[str]:
    return {
        line.strip()
        for line in _EDITIONLESS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def _editionless_citations(citations: set[str]) -> set[str]:
    """Those naming a normative standards body and no edition."""
    from anvilate.standards.effectivity import names_a_standard, parse_citation

    return {
        text
        for text in citations
        if names_a_standard(text) is not None and parse_citation(text) is None
    }
