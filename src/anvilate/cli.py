"""The headless command line: four commands that are backed, and the one that is not.

`headless-automation` requires the CLI to expose every pipeline capability — "at minimum
``anvilate build``, ``anvilate check``, ``anvilate export``, ``anvilate diff`` — operating on
spec files and producing the same artifacts, scorecards, and **exit codes** deterministically".
Until this module there was no ``anvilate`` command at all; the only console script was the
MCP server.

**Three of the four are backed today**, and a fifth command the attestation capability names
is backed as well: only ``build`` is refused, and it is refused by name with what it waits
on. ``check`` compiles a spec document and screens it,
which is exactly the path :func:`anvilate.screening.screen_spec` already serves over MCP.
``export`` serves the one artifact that needs no geometry — the evidence bundle, which is
assembled from a scorecard — and refuses the two that do.

That split was got wrong first: ``export`` was refused whole, on the reasoning that it
"writes a downstream artifact from a built part". True of a DXF and of QIF results, false of
the evidence bundle, which the MCP tool's own format enumeration has always listed beside
them. A refusal wide enough to cover something that works is as misleading as a missing one.

``build`` and ``diff`` do need a built part, so each is refused *by name, with the reason*
rather than left as an unknown command. A CLI that answers "unknown command: build" tells a
script author they typed it wrong; the honest answer is that the operation is specified,
unbuilt, and here is what it is waiting on.

**The bundle goes to stdout, and that is not an oversight.** Every artifact-emitting entry
point in this package takes a mandatory ``ExportAuthorization`` (see
:mod:`anvilate.export.gate`), and there is no bundle *writer* behind that gate. Printing is
not emitting: a caller redirecting the output is doing their own act, the same as
``check --format json``, and the screening disclaimer is a constant on the rendering rather
than something a writer would have had to remember. Adding a file-writing path here would
be the first one outside :mod:`anvilate.export`, which is exactly the bypass the gate
exists to prevent.

## The exit codes are the interface

A script reads the exit code, not the text. So the code follows the scorecard's own rule
rather than collapsing to pass/fail:

===  ===========================================================================
0    every check passed
1    a check failed
2    the card could not be fully evaluated — **not a pass**, and not a failure
3    the request was wrong: a usage error, a missing file, a document that is not a spec
4    the operation is specified but unbuilt
===  ===========================================================================

Code 2 is the one worth arguing about, and No-silent-green settles it. A screen that could
not run is not a screen that passed, so a CI job gating a merge on ``anvilate check`` must
not go green on it. Making it a distinct code rather than folding it into 1 lets a caller
that genuinely wants "nothing failed" say so, deliberately, in one place.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from .scorecard import CheckStatus, Scorecard

__all__ = ["EXIT_CODES", "main", "run"]

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOT_EVALUATED = 2
EXIT_BAD_REQUEST = 3
EXIT_UNBUILT = 4

#: The exit code for each rolled-up scorecard status, and nothing else. Written as a total
#: map over the enumeration rather than an if-chain with an else, so a fifth status is a
#: KeyError at the one place that has to decide rather than a silent 0.
EXIT_CODES: dict[CheckStatus, int] = {
    CheckStatus.PASS: EXIT_OK,
    CheckStatus.OVER_MARGIN: EXIT_OK,
    CheckStatus.FAIL: EXIT_FAILED,
    CheckStatus.NOT_EVALUATED: EXIT_NOT_EVALUATED,
}

#: Statuses and exit codes worst-last, so a run over many specs reports the worst one it
#: found. Written as orders rather than compared with `>`: the exit codes are labels, and
#: "2 is worse than 1" is a fact about this list, not about the integers.
_BLOCKING_ORDER = [
    CheckStatus.PASS,
    CheckStatus.OVER_MARGIN,
    CheckStatus.NOT_EVALUATED,
    CheckStatus.FAIL,
]
_EXIT_SEVERITY = [EXIT_OK, EXIT_NOT_EVALUATED, EXIT_FAILED]

# What each unbuilt command is waiting on. Named individually because "not implemented" is
# not an answer a script author can act on, and because the three are waiting on the same
# thing for three different reasons.
_UNBUILT = {
    "build": (
        "build runs the part's generating program, which needs a geometry kernel this "
        "package does not ship. See openspec/specs/geometry-generation."
    ),
}

# The half of `diff` that needs a built part, named where the output would have shown it.
_DIFF_NEEDS_GEOMETRY = (
    "mass, volume and centre-of-gravity deltas need two built parts. "
    "See openspec/specs/geometry-generation."
)

# The artifacts `export` knows about, and which of them a spec file alone can produce. The
# two that cannot each say what they are waiting on, in the same words `_UNBUILT` uses,
# because a caller asking for a DXF is owed the same answer as one asking for a build.
_UNBUILT_ARTIFACTS = {
    "dxf": (
        "a DXF is drawn from built geometry, and there is no built part to draw. "
        "See openspec/specs/geometry-generation."
    ),
    "qif": (
        "QIF results carry measured characteristics against a built part. "
        "See openspec/specs/geometry-generation."
    ),
}
_ARTIFACTS = ("evidence-bundle", *sorted(_UNBUILT_ARTIFACTS))


class _Parser(argparse.ArgumentParser):
    """An ``ArgumentParser`` whose usage errors are bad requests, not verdicts.

    ``ArgumentParser.error`` exits **2**, hardcoded — and 2 is this CLI's code for "the card
    could not be evaluated". So `anvilate frobnicate`, `anvilate` with no command, and
    `anvilate check` with no file all exited with the code the docs tell a CI job it may
    accept: ``anvilate check part.yaml || [ $? -eq 2 ]`` treated a typo as a successfully
    not-evaluated screen. A silent green produced by the very feature that exists to stop
    silent greens.

    A usage error is a bad request, which is what code 3 already means — the same bucket as
    a missing file or a document that is not a spec. ``--help`` is unaffected: that goes
    through ``exit()`` rather than ``error()`` and still leaves 0.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(EXIT_BAD_REQUEST, f"{self.prog}: error: {message}\n")


def _installed_version() -> str:
    """The version of the installed distribution, or a marker saying it is not installed.

    Never `anvilate.__version__`. A script asking a tool its version is asking what it is
    running, and a module constant answers what somebody last typed — the same defect as a
    hand-written bill of materials, one file over.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("anvilate")
    except PackageNotFoundError:  # pragma: no cover - a source tree with nothing installed
        return "0+not-installed"


def _build_parser() -> argparse.ArgumentParser:
    # The description says what is true of *every* command. An earlier version stated
    # `check`'s rule — "exit 0 only when every check passed" — as though it were the
    # program's, and it is false for `diff`, whose 0 means nothing got worse and which
    # says so on a run where every check fails. The first thing a user reads was
    # contradicted by a command in the same help output.
    parser = _Parser(
        prog="anvilate",
        description="Screen Design Specs without a UI. Exit code 0 is the only success; "
        "1 means something failed, 2 that something could not be evaluated — which is "
        "never a pass — 3 a bad request, 4 an operation that is specified and unbuilt. "
        "What counts as failure differs per command; each says so in its own help.",
        epilog="Run `anvilate <command> --help` for the exit codes that command uses.",
    )
    # Subcommands inherit `_Parser`: `add_subparsers` defaults `parser_class` to the parent's
    # own type, so "check: the following arguments are required: spec" lands on the same code
    # as a top-level usage error. Passing it explicitly changed nothing and killed no
    # mutation, which is how that was established rather than assumed.
    # Read from the installed metadata, not from `anvilate.__version__`: a script asking a
    # tool its version is asking what is installed, and the two are the same only because a
    # gate says so.
    parser.add_argument("--version", action="version", version=f"anvilate {_installed_version()}")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser(
        "check",
        help="compile a spec document and screen it, printing the scorecard",
        description="Screen every spec given, or every spec under a directory. Exit 0 "
        "only when every check passed, 1 if one failed, 2 if a card could not be fully "
        "evaluated. Blocking checks are listed on stderr with the spec they came from.",
    )
    check.add_argument(
        "spec",
        type=Path,
        nargs="+",
        help="Design Spec documents, or directories to search for them",
    )
    check.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="text for a person, json for a script that wants the whole card",
    )
    check.add_argument(
        "--show-work",
        action="store_true",
        help="print each check's worked calculation — the formula, the values put into "
        "it, the result, and the symbol glossary. A check with no derivation says so "
        "rather than being left out",
    )
    verify = commands.add_parser(
        "verify",
        help="verify an attestation envelope and report what was checked",
        description="Check an envelope's signature, its subject digests and its predicate "
        "schema, offline. Exit 0 only when all three checked clean; 2 when something could "
        "not be checked at all — a signature with no key, a subject with no file — which is "
        "not a pass.",
    )
    verify.add_argument("envelope", type=Path, help="a DSSE envelope, as JSON")
    verify.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="an attested subject and the file to hash against it; repeatable. A subject "
        "with no file is reported unchecked, never assumed to match",
    )
    verify.add_argument(
        "--hmac-key-file",
        type=Path,
        help="a local symmetric signing key. Without it the signature is reported "
        "not_checked, which is not a pass",
    )
    verify.add_argument(
        "--format", choices=("text", "json"), default="text", help="how to render the report"
    )

    diff = commands.add_parser(
        "diff",
        help="compare two spec documents and the verdicts they screen to",
        description="Report the spec change and every check whose verdict moved. The exit "
        "code is about what got WORSE, not about the new card: 0 when nothing regressed, "
        "even on a run where every check fails, because a part that was already failing "
        "has not got worse.",
    )
    diff.add_argument("before", type=Path, help="the spec as it was")
    diff.add_argument("after", type=Path, help="the spec as it is")

    export = commands.add_parser(
        "export",
        help="write a downstream artifact from a screened spec",
        description="Render the evidence bundle for every spec given, or every spec under "
        "a directory. The exit code is the bundle roll-up, which is never better than its "
        "worst section: 0 when every section passed, 1 when one failed, 2 when one could "
        "not be evaluated. An artifact needing a built part is refused with 4.",
    )
    export.add_argument(
        "spec",
        type=Path,
        nargs="+",
        help="Design Spec documents, or directories to search for them",
    )
    export.add_argument(
        "--artifact",
        choices=_ARTIFACTS,
        default="evidence-bundle",
        help="which artifact; only the evidence bundle needs no geometry",
    )
    export.add_argument(
        "--format", choices=("text", "json"), default="text", help="how to render it"
    )

    for name, reason in _UNBUILT.items():
        unbuilt = commands.add_parser(
            name, help=f"specified, unbuilt — {reason.split('.')[0]}", description=reason
        )
        # Everything after the name is swallowed, because there is no invocation of an
        # unbuilt operation that would be correct. `anvilate build part.yaml` — the thing a
        # reader of the help above actually types — answered "unrecognized arguments" and
        # exited 3, which this CLI defines as *the request was wrong*. The request was not
        # wrong; the operation is unbuilt, and that is what code 4 is for.
        unbuilt.add_argument(
            "ignored",
            nargs=argparse.REMAINDER,
            help="accepted and ignored — the refusal is about the operation, not the arguments",
        )
    return parser


def run(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run one command and return its exit code, writing nothing to the real streams.

    Split from :func:`main` so the whole surface is exercised in-process: a CLI tested only
    through a subprocess is a CLI whose branches are mostly unvisited.
    """
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command in _UNBUILT:
        print(f"anvilate {args.command}: {_UNBUILT[args.command]}", file=err)
        return EXIT_UNBUILT
    if args.command == "export":
        return _export(args, out=out, err=err)
    if args.command == "verify":
        return _verify(args, out=out, err=err)
    if args.command == "diff":
        return _diff(args, out=out, err=err)
    return _check(args, out=out, err=err)


def _diff(args: argparse.Namespace, *, out, err) -> int:
    """``diff``, for the half of it a spec change alone can answer.

    `headless-automation` asks `diff` to "compare two builds of a part **(or a spec
    change)** and report mass/volume/CG deltas, changed-dimension summary, and
    validation-verdict changes". The parenthesis is the whole of what is possible without a
    geometry kernel, and it is the half a merge gate actually reads: the scenario is a
    commit that changes a shared pattern and makes a downstream part fail.

    **The exit code is about what got worse, not about the new card.** A part that was
    already failing and still fails has not regressed, and a diff that failed the build for
    it would fail every build until somebody fixed an unrelated part. So the code is the
    worst *new* status among checks that moved for the worse, and zero when none did.

    The geometry half is named in the output rather than omitted, for the same reason the
    unbuilt commands are named rather than left unknown: a reader who sees no mass delta
    should be told there is none to be had, not left to wonder whether the mass was equal.
    """
    from .screening import screen_spec

    cards, names = [], []
    for path in (args.before, args.after):
        spec = _load(path, err=err, command="diff")
        if isinstance(spec, int):
            return spec
        cards.append(screen_spec(spec))
        names.append(spec)

    before_card, after_card = cards
    before_spec, after_spec = names
    print(_render_diff(before_spec, after_spec, before_card, after_card), file=out)

    regressions = _regressions(before_card, after_card)
    for name, was, now in regressions:
        print(f"anvilate diff: {name}: {was.value} → {now.value}", file=err)
    # The card's own verdict, which no per-check comparison can see. A revision that renames
    # the element deletes every check by name and adds a not-evaluated gap in their place:
    # nothing "moved for the worse", and the part went from screened to unscreened. A
    # different set of checks is not a worse set — that decision stands — but a different
    # verdict is a worse verdict, and the roll-up is defined for exactly this comparison.
    worse = _BLOCKING_ORDER.index(after_card.status) > _BLOCKING_ORDER.index(before_card.status)
    if worse:
        print(
            f"anvilate diff: the card: {before_card.status.value} → {after_card.status.value}",
            file=err,
        )
    if not regressions and not worse:
        return EXIT_OK
    codes = [EXIT_CODES[now] for _n, _w, now in regressions]
    if worse:
        codes.append(EXIT_CODES[after_card.status])
    return max(codes, key=_EXIT_SEVERITY.index)


def _regressions(before: Scorecard, after: Scorecard):
    """Checks whose status moved for the worse, by name.

    A check present in only one card is not a regression *or* an improvement — it is a
    different set of checks — and it is reported in the rendering as added or removed
    rather than silently counted as either.
    """
    was = {entry.name: entry.status for entry in before.entries}
    return [
        (entry.name, was[entry.name], entry.status)
        for entry in after.entries
        if entry.name in was
        and _BLOCKING_ORDER.index(entry.status) > _BLOCKING_ORDER.index(was[entry.name])
    ]


def _render_diff(before_spec, after_spec, before: Scorecard, after: Scorecard) -> str:
    """The three sections, each present even when it has nothing in it."""
    import difflib

    from .spec import dump_spec_yaml

    lines = [f"{before_spec.name} → {after_spec.name}", "", "SPEC"]
    changed = [
        line
        for line in difflib.unified_diff(
            dump_spec_yaml(before_spec).splitlines(),
            dump_spec_yaml(after_spec).splitlines(),
            lineterm="",
            n=0,
        )
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    lines.extend(f"  {line}" for line in changed or ("no change",))

    lines.extend(["", f"VERDICT  {before.status.value} → {after.status.value}", "", "CHECKS"])
    was = {entry.name: entry for entry in before.entries}
    now = {entry.name: entry for entry in after.entries}
    moved = []
    for name in sorted(set(was) | set(now)):
        if name not in now:
            moved.append(f"  - {name}: removed (was {was[name].status.value})")
        elif name not in was:
            moved.append(f"  + {name}: added ({now[name].status.value})")
        elif was[name].status is not now[name].status:
            moved.append(f"  ! {name}: {was[name].status.value} → {now[name].status.value}")
            moved.append(f"      {now[name].detail}")
    lines.extend(moved or ["  no verdict changed"])
    unchanged = sum(1 for name in set(was) & set(now) if was[name].status is now[name].status)
    lines.append(f"  ({unchanged} unchanged)")

    lines.extend(["", "GEOMETRY", f"  not compared: {_DIFF_NEEDS_GEOMETRY}"])
    return "\n".join(lines)


def _verify(args: argparse.Namespace, *, out, err) -> int:
    """``verify``, the command `evidence-attestation` names.

    "Anvilate SHALL provide a verification command that checks signature, subject digests,
    and predicate schema." The library has done all three since the attestation layer
    shipped; nothing at the shell called it.

    **Three states, and the middle one is why this is not a boolean.** A signature nobody
    could check is `not_checked` and is *not* a pass — the same rule the whole library
    follows about a check that could not run, and the reason the exit code is 2 rather than
    0 when no key is supplied. An unsigned envelope says unsigned. A subject with no file
    given is reported unchecked rather than assumed to match.

    **Only local symmetric keys.** `LocalHmacSigner` is what this package ships, so
    `--hmac-key-file` is a shared secret and not public material. Keyless and asymmetric
    verification are unimplemented, and saying "verified" for a signature nothing could
    check is exactly the claim this command exists to avoid making.
    """
    from .attestation import Attestation, LocalHmacSigner, verify_attestation

    try:
        envelope = json.loads(args.envelope.read_text(encoding="utf-8"))
    except OSError as failure:
        print(f"anvilate verify: {failure}", file=err)
        return EXIT_BAD_REQUEST
    except json.JSONDecodeError as failure:
        print(f"anvilate verify: {args.envelope}: not JSON: {failure}", file=err)
        return EXIT_BAD_REQUEST
    try:
        attestation = Attestation.model_validate(envelope)
    except ValueError as failure:
        print(f"anvilate verify: {args.envelope}: not a DSSE envelope: {failure}", file=err)
        return EXIT_BAD_REQUEST

    artifacts: dict[str, bytes] = {}
    for pair in args.artifact:
        name, separator, path = pair.partition("=")
        if not separator or not name:
            print(f"anvilate verify: --artifact takes NAME=PATH; got {pair!r}", file=err)
            return EXIT_BAD_REQUEST
        try:
            artifacts[name] = Path(path).read_bytes()
        except OSError as failure:
            print(f"anvilate verify: {failure}", file=err)
            return EXIT_BAD_REQUEST

    signer = None
    if args.hmac_key_file is not None:
        try:
            signer = LocalHmacSigner(args.hmac_key_file.read_bytes())
        except OSError as failure:
            print(f"anvilate verify: {failure}", file=err)
            return EXIT_BAD_REQUEST

    report = verify_attestation(attestation, artifacts=artifacts or None, signer=signer)
    # Both renderings read the carried statement for the toolchain, and `statement()` parses
    # the payload — which `verify_attestation` has just *reported* as unreadable when it is.
    # An envelope whose payload is valid base64 over non-JSON therefore produced the right
    # report and then a JSONDecodeError on the way to printing it. An envelope arriving from
    # somewhere else is untrusted input; a traceback is the one answer this command must not
    # give to it.
    try:
        statement = attestation.statement()
    except (ValueError, UnicodeDecodeError):
        statement = {}
    if args.format == "json":
        # `status`, `attested` and the attested toolchain are computed rather than stored,
        # so `model_dump` left all three out and the payload carried only the fields behind
        # them. `attested` is the consequential one: a consumer reading
        # `signature_state: symmetric_verified` and nothing else concludes the envelope is
        # attested, which is exactly what the text rendering exists to correct — a shared
        # secret proves the envelope was not altered, not who made it. And the requirement
        # asks this command to report the toolchain the envelope attests, which was true of
        # one of its two renderings.
        payload = {
            **report.model_dump(mode="json"),
            "status": report.status.value,
            "attested": report.attested,
            **_attested_toolchain(statement),
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        print(_render_verification(report, statement), file=out)
    for problem in report.problems:
        print(f"anvilate verify: {problem}", file=err)
    return EXIT_CODES[report.status]


def _attested_toolchain(statement: dict) -> dict:
    """``producer`` and ``toolchain`` as the verified statement records them.

    Read out of the statement rather than out of the environment, for the reason the text
    renderer gives: what a verifier wants to know is what produced the artifact, not what is
    installed on the machine reading it. One reader for both renderings, so they cannot come
    to report different toolchains for the same envelope.
    """
    bom = (statement.get("predicate") or {}).get("bom") or {}
    metadata = (bom.get("metadata") or {}).get("component") or {}
    return {
        "producer": (
            None
            if not metadata
            else {"name": metadata.get("name"), "version": metadata.get("version")}
        ),
        "toolchain": [
            {"name": component.get("name"), "version": component.get("version")}
            for component in bom.get("components") or []
        ],
    }


def _render_verification(report, statement: dict) -> str:
    """The report as a person reads it, with `attested` explained where it would mislead.

    The toolchain the envelope attests is printed too, because the requirement's own
    scenario says an engineer running this "confirms the signature, that artifact digests
    match, **and reports the toolchain versions attested**" — and the first version showed
    the first two. It is read out of the verified statement rather than out of the
    environment: what a verifier wants to know is what produced the artifact, not what is
    installed on the machine reading it.

    `attested` is True only for a clean verification of an **authorship-establishing**
    signature. A local HMAC is a shared secret: it proves the envelope was not altered by
    anyone without the key, and it proves nothing about who made it, because everybody
    holding the key could have. So a fully checked symmetric envelope reads PASS with
    `attested=False`, and printing that pair without the reason invites exactly the wrong
    conclusion.
    """
    from .attestation import SignatureState

    lines = [
        f"{report.status.value.upper()}  attested={report.attested}",
        f"  signature   {report.signature_state.value}",
        f"  bundle      {report.bundle_digest}",
        f"  predicate   {report.predicate_type}",
    ]
    for label, subjects in (
        ("checked", report.checked_subjects),
        ("unchecked", report.unchecked_subjects),
    ):
        # Both lists always render. A run that checked nothing and one whose subjects all
        # matched must not look the same.
        lines.append(f"  {label:11} {', '.join(subjects) or 'none'}")
    attested = _attested_toolchain(statement)
    components = attested["toolchain"]
    producer = attested["producer"]
    if producer is not None:
        lines.append(f"  produced by {producer['name']} {producer['version']}")
    # Always rendered, `none` included: a bundle attesting no toolchain and one whose
    # toolchain nobody printed must not read the same.
    listed = ", ".join(f"{component['name']} {component['version']}" for component in components)
    lines.append(f"  toolchain   {listed or 'none attested'}")
    for problem in report.problems:
        lines.append(f"  problem     {problem}")
    if not report.attested and report.signature_state is SignatureState.SYMMETRIC_VERIFIED:
        lines.append(
            "  note        a symmetric key proves the envelope was not altered, not who "
            "made it — anyone holding the key could have, so this is not attestation"
        )
    return "\n".join(lines)


def _export(args: argparse.Namespace, *, out, err) -> int:
    """``export``, for the one artifact a spec file alone can produce."""
    from .bundle import BundleSections

    if args.artifact in _UNBUILT_ARTIFACTS:
        print(
            f"anvilate export --artifact {args.artifact}: {_UNBUILT_ARTIFACTS[args.artifact]}",
            file=err,
        )
        return EXIT_UNBUILT

    from .screening import screen_spec

    # The same path handling `check` has, for the same reason: `headless-automation` asks
    # CI to publish evidence bundles for a repository, and a command taking one file at a
    # time makes that a shell loop in a script nothing type-checks.
    paths = _resolve(args.spec, err=err, command="export")
    if isinstance(paths, int):
        return paths
    results = []
    for path in paths:
        spec = _load(path, err=err, command="export")
        if isinstance(spec, int):
            return spec
        # The spec goes in the bundle, not only through it. `artifact-export`'s scenario is
        # a reviewer holding only this document and re-running the analysis, and until the
        # spec was carried they were holding verdicts with no inputs behind them.
        results.append((path, spec, BundleSections(scorecard=screen_spec(spec), spec=spec)))

    # One roll-up, read by the exit code and by both renderings. `check` prints its
    # run-level verdict in each; this printed it in neither, so a CI job publishing bundles
    # for a repository got N blocks and had to find the worst by scanning them. The exit
    # code carried it, and a verdict only an exit code carries is one nobody reads in a log.
    worst = _worst_status(sections for _p, _s, sections in results)

    if args.format == "json":
        payload = {
            "status": worst.value,
            "bundles": [
                {"path": str(path), "name": spec.name, "bundle": sections.to_document_dict()}
                for path, spec, sections in results
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        for index, (path, _spec, sections) in enumerate(results):
            if index:
                print("", file=out)
            if len(results) > 1:
                print(f"# {path}", file=out)
            print(sections.render_document(), file=out)
        if len(results) > 1:
            print(f"\n{len(results)} bundles: {worst.value.upper()}", file=out)
    return EXIT_CODES[worst]


def _load(path: Path, *, err, command: str):
    """The spec at ``path``, or the exit code that says why not.

    Shared by every command that takes a spec file, so a second one cannot report a missing
    file differently from the first.
    """
    from .spec import SpecValidationError, load_spec_yaml

    try:
        document = path.read_text(encoding="utf-8")
    except OSError as failure:
        print(f"anvilate {command}: {failure}", file=err)
        return EXIT_BAD_REQUEST
    try:
        return load_spec_yaml(document)
    except SpecValidationError as failure:
        # Every path, not the first one: a script author fixing a spec one error per run is
        # the experience this avoids, and the paths are what the loader already produced.
        for problem in failure.errors:
            print(f"anvilate {command}: {problem['loc']}: {problem['msg']}", file=err)
        return EXIT_BAD_REQUEST
    except (ValueError, TypeError, KeyError) as failure:
        print(f"anvilate {command}: {failure}", file=err)
        return EXIT_BAD_REQUEST


def _check(args: argparse.Namespace, *, out, err) -> int:
    """``check``, over one spec or every spec under a directory.

    `headless-automation` asks for "regenerating and revalidating **all specs in a
    repository** on push", so a directory is a valid argument and the exit code is the worst
    verdict across everything found — one failing part fails the run, which is what a merge
    gate needs.
    """
    from .screening import screen_spec

    paths = _resolve(args.spec, err=err)
    if isinstance(paths, int):
        return paths

    results = []
    for path in paths:
        spec = _load(path, err=err, command="check")
        if isinstance(spec, int):
            return spec
        results.append((path, spec, screen_spec(spec)))

    if args.format == "json":
        # A list whatever the count. A shape that changes with the number of arguments is a
        # shape every caller has to branch on, and the branch is wrong the first time a
        # directory happens to hold one spec.
        # `status` and `governing` are the two conclusions the text rendering prints and
        # this payload used to drop. The verdict is recoverable from the exit code, but
        # `governing` is not recoverable at all: it is the worst check by a specific
        # ordering, and a consumer left to recompute it from `entries` is reimplementing
        # `Scorecard.governing()` at every call site. Both are always present, `governing`
        # as null when there is none — a card with nothing to govern and a payload missing
        # the key must not look the same, which is the rule the text line already follows.
        payload = {
            "status": _worst_status(card for _path, _spec, card in results).value,
            "specs": [
                {
                    "path": str(path),
                    "name": spec.name,
                    "status": card.status.value,
                    "governing": (
                        None
                        if (governing := card.governing()) is None
                        else {"name": governing.name, "status": governing.status.value}
                    ),
                    "scorecard": card.model_dump(mode="json"),
                }
                for path, spec, card in results
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        # The path is printed alongside the name whenever more than one spec ran. Two
        # parts in a repository can share a name — a `bracket.yaml` under two assemblies —
        # and the first version printed the name alone, so a repo-wide run produced two
        # identical blocks and no way to tell which was which.
        for index, (path, spec, card) in enumerate(results):
            if index:
                print("", file=out)
            heading = spec.name if len(results) == 1 else f"{spec.name}  ({path})"
            print(_render(heading, card, show_work=args.show_work), file=out)
        if len(results) > 1:
            worst = _worst_status(card for _p, _s, card in results)
            print(f"\n{len(results)} specs: {worst.value.upper()}", file=out)

    # Every blocking check on stderr, which is what the requirement asks for and what a CI
    # log actually shows. A check that could not run is listed too, labelled as such: it
    # blocks exactly as hard and calling it a failure would be a different claim.
    for path, _spec, card in results:
        for entry in card.entries:
            if entry.status in (CheckStatus.FAIL, CheckStatus.NOT_EVALUATED):
                print(
                    f"anvilate check: {path}: {entry.status.value}: {entry.name} — {entry.detail}",
                    file=err,
                )
    return max(
        (EXIT_CODES[card.status] for _p, _s, card in results),
        key=_EXIT_SEVERITY.index,
    )


def _resolve(paths: list[Path], *, err, command: str = "check") -> list[Path] | int:
    """The spec documents behind the arguments, in a stable order.

    A directory is searched; a file named on the command line is taken at its word. The
    difference matters: a document *found* by searching that carries no ``anvilate_spec`` key
    is some other YAML file and is skipped — reported, never silently — while one the caller
    *named* is an error, because they said it was a spec and it is not.
    """
    import yaml

    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            candidates = sorted(
                candidate
                for pattern in ("*.yaml", "*.yml", "*.json")
                for candidate in path.rglob(pattern)
            )
            for candidate in candidates:
                try:
                    document = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                except (OSError, yaml.YAMLError):
                    document = None
                if isinstance(document, dict) and "anvilate_spec" in document:
                    found.append(candidate)
                else:
                    print(
                        f"anvilate {command}: {candidate}: not a Design Spec, skipped",
                        file=err,
                    )
            continue
        found.append(path)
    if not found:
        print(
            f"anvilate {command}: no Design Spec found in " + ", ".join(str(p) for p in paths),
            file=err,
        )
        return EXIT_BAD_REQUEST
    return found


def _render(name: str, card: Scorecard, *, show_work: bool = False) -> str:
    """The card as a person reads it, with the governing check named at the end.

    **The governing check is the line a reviewer reads first and the card did not carry
    it.** `Scorecard.governing()` has always known which check is closest to (or furthest
    past) its limit — blocking status first, then utilization — and the calculation report
    prints it. The shell printed the entries in the order they were produced and left the
    reader to rank them.

    It is printed even when there is none, and the reason matters: `governing()` returns
    None when nothing blocks *and* no check carries a safety factor, which is an ordinary
    card of passing deflection checks rather than an error. A missing line and a card with
    nothing to govern must not look the same.
    """
    from .report import ReportSection

    lines = [f"{name}: {card.status.value.upper()}"]
    for entry in card.entries:
        lines.append(f"  {entry.status.value:<14} {entry.name}")
        if entry.detail:
            lines.append(f"                 {entry.detail}")
        # The clause is what separates this from a spreadsheet, and the shell dropped it.
        # `ScorecardEntry.__str__` has always appended it; this renderer builds its own lines
        # and printed the detail alone, so every cited check read as an uncited one.
        if entry.reference:
            lines.append(f"                 [{entry.reference}]")
        # The repair hint is the most actionable thing a failing entry carries — where a
        # design inverse exists it is the value that lands exactly on the required margin —
        # and it was printed by the calculation report and by nothing at the shell. A reader
        # was told the check failed and left to solve the inverse themselves.
        if entry.repair_hint is not None:
            lines.append(f"                 → {entry.repair_hint}")
        # The library computes a worked calculation for most cited checks and the shell
        # could not show it: a reader at the terminal saw a safety factor and had to open
        # Python, or read the JSON, to find the formula behind it. `--show-work` prints the
        # block the calculation report prints, through the report's own renderer, indented
        # to sit under the entry it belongs to.
        if show_work:
            section = ReportSection(entry=entry)
            worked = section.worked_lines()
            if worked:
                lines.extend(f"{' ' * 15}{line}" for line in worked)
            else:
                # Said out loud. A check silently missing from a --show-work listing reads
                # as one whose formula was not worth showing, and those are different. The
                # label comes from the section so this surface and the report cannot
                # describe one absent derivation two ways.
                lines.append(f"                 [{section.fallback_label}]")
    governing = card.governing()
    if governing is None:
        lines.append("  governing:     none — nothing blocks and no check carries a margin")
    else:
        lines.append(f"  governing:     {governing.name} ({governing.status.value})")
    return "\n".join(lines)


def _worst_status(cards):
    """The blocking-worst status over a run, which both renderings report.

    One function rather than two, because the text summary and the JSON payload disagreeing
    about the verdict of the same run is the defect that having two of them invites.
    """
    return max((card.status for card in cards), key=_BLOCKING_ORDER.index)


def main() -> None:
    """The ``anvilate`` console script."""
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in the tests
    main()
