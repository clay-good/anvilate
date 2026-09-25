"""The headless command line: screening, geometry, evidence, verification, and diffing.

`headless-automation` requires the CLI to expose every pipeline capability — "at minimum
``anvilate build``, ``anvilate check``, ``anvilate export``, ``anvilate diff`` — operating on
spec files and producing the same artifacts, scorecards, and **exit codes** deterministically".
Until this module there was no ``anvilate`` command at all; the only console script was the
MCP server.

**Six of the six are backed today**; a seventh command, ``verify``, comes from the
attestation capability. ``doctor`` reports which optional runtimes are present.
``build`` now produces STEP for audited ``base_plate``, ``cover_plate``, and
``transmission_shaft`` patterns. Other element types are refused by name rather than sent
through an unreviewed generic generator.
``check`` compiles a spec document and screens it, which is exactly the path
:func:`anvilate.screening.screen_spec` already serves over MCP.
``export`` serves the evidence bundle and QIF results (ISO 23952) from a screened card, and
builds audited geometry before rendering a DXF cut profile. All three go to stdout.

That split was got wrong twice, the same way each time. First ``export`` was refused whole,
on the reasoning that it "writes a downstream artifact from a built part": true of a DXF,
false of the evidence bundle. Then QIF stayed refused on the same reasoning, and that was
false too — ``export_qif_results`` takes a ``BundleSections`` and touches no geometry, which
is what ``artifact-export`` asks of it and what ``docs/quality-interchange.md`` is written
about. A refusal wide enough to cover something that works is as misleading as a missing
one, and the second time it hid a capability the library had shipped, documented and
exampled.

``diff`` runs — only its mass, volume and centre-of-gravity deltas wait on geometry, and the
output says so where they would be.

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
5    the command itself failed unexpectedly
===  ===========================================================================

Code 2 is the one worth arguing about, and No-silent-green settles it. A screen that could
not run is not a screen that passed, so a CI job gating a merge on ``anvilate check`` must
not go green on it. Making it a distinct code rather than folding it into 1 lets a caller
that genuinely wants "nothing failed" say so, deliberately, in one place.
"""

from __future__ import annotations

import argparse
import codecs
import contextlib
import io
import json
import shutil
import sys
import textwrap
import time
from collections import Counter
from pathlib import Path
from typing import Any, Literal, TextIO

from ._cli_output import cancelled_document, error_document, machine_document, refusal_document
from ._models import _refusal_line
from .evidence import provenance_for
from .failure_modes import CATALOG_IS_A_FLOOR, UNDECLARABLE_FACTS, facts_from_spec
from .failure_modes import coverage as mode_coverage
from .margin import ledger_for, physics_limited
from .needs import LEVERAGE_IS_NOT_IMPORTANCE, needs_report
from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .units import Quantity, UnitSystem

__all__ = ["EXIT_CODES", "main", "run"]

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOT_EVALUATED = 2
EXIT_BAD_REQUEST = 3
EXIT_UNBUILT = 4
EXIT_INTERNAL_ERROR = 5
# A card whose worst entry is a warning: nothing failed and everything ran, and the design
# is inside a band its document asked to hear about. Not 0, because it is not a pass.
EXIT_WARNING = 6
# The user stopped the run: 128 + SIGINT, the shell's own convention. Not a verdict, a
# refusal or a defect, and reported as none of them.
EXIT_CANCELLED = 130


#: How long a command may go quiet on a terminal before a person cannot tell a slow tool from
#: a broken one. Anything that can exceed it says what it is doing through `_progress`: a
#: sweep of specs counts them, and one geometry build names the build without a count it
#: does not have. On a pipe it stays silent, so stdout is the result alone.
RESPONSIVENESS_THRESHOLD_SECONDS = 2.0


def _estimate(durations: list[float], remaining: int) -> str:
    """The time left, from same-kind work already finished, and labelled as an estimate.

    Nothing before the first item finishes: a guess with no completed work behind it is
    an invented number. After that, the mean of the finished items times the ones left,
    saying how many it rests on.
    """
    if not durations or remaining <= 0:
        return ""
    left = sum(durations) / len(durations) * remaining
    shown = f"about {left:.0f} s" if left >= 1 else "under 1 s"
    plural = "s" if len(durations) != 1 else ""
    return f" ({shown} left, estimated from {len(durations)} finished spec{plural})"


def _progress(err, activity: str, *, done: int | None = None, total: int | None = None) -> None:
    """One progress line on a terminal: the activity, with counts only when they are known.

    The count is padded to the width of the total, so a value that updates keeps its width:
    ``[ 9/12]`` then ``[10/12]``, and the activity beside it stays in its column line to line
    rather than stepping right when the count gains a digit.
    """
    if not _is_terminal(err):
        return
    count = (
        f"[{done:>{len(str(total))}}/{total}] " if done is not None and total is not None else ""
    )
    print(f"{count}{activity}", file=err, flush=True)


class _Cancelled(Exception):
    """An interrupt caught where the command knows how far it got."""

    def __init__(self, completed: str) -> None:
        super().__init__(completed)
        self.completed = completed


#: The exit code for each rolled-up scorecard status, and nothing else. Written as a total
#: map over the enumeration rather than an if-chain with an else, so a fifth status is a
#: KeyError at the one place that has to decide rather than a silent 0.
EXIT_CODES: dict[CheckStatus, int] = {
    CheckStatus.PASS: EXIT_OK,
    CheckStatus.OVER_MARGIN: EXIT_OK,
    # A deliberate deferral is not a failure: the engineer asked for a concept screen and
    # got one. The card and every rendering still state the count.
    CheckStatus.OUT_OF_DEPTH: EXIT_OK,
    CheckStatus.WARNING: EXIT_WARNING,
    CheckStatus.FAIL: EXIT_FAILED,
    CheckStatus.NOT_EVALUATED: EXIT_NOT_EVALUATED,
}

#: Statuses and exit codes worst-last, so a run over many specs reports the worst one it
#: found. Written as orders rather than compared with `>`: the exit codes are labels, and
#: "2 is worse than 1" is a fact about this list, not about the integers.
_BLOCKING_ORDER = [
    CheckStatus.PASS,
    # A deferral blocks nothing, so it sits between a clean pass and an over-margin warning
    # — see `_STATUS_RANK`, which this mirrors. How hard a verdict blocks is not how bad it
    # is, which is why `_moved_for_the_worse` does not read this list alone.
    CheckStatus.OUT_OF_DEPTH,
    CheckStatus.OVER_MARGIN,
    CheckStatus.WARNING,
    CheckStatus.NOT_EVALUATED,
    CheckStatus.FAIL,
]

#: The statuses in which a check actually produced a verdict. The two that are not here are
#: the two ways a check does not run: it could not, or the document deferred it.
_RAN = frozenset({CheckStatus.PASS, CheckStatus.OVER_MARGIN, CheckStatus.WARNING, CheckStatus.FAIL})
_EXIT_SEVERITY = [EXIT_OK, EXIT_WARNING, EXIT_NOT_EVALUATED, EXIT_FAILED]

# Where the specification for the missing half lives. A URL rather than `openspec/specs/…`:
# the refusals below are read by somebody who ran `pip install anvilate`, and a bare
# repository path names a directory their environment does not contain. It read as a local
# file that was not there.
_GEOMETRY_SPEC = (
    "https://github.com/clay-good/anvilate/tree/main/openspec/specs/geometry-generation"
)

# The command-level gap list. Empty now that every command has a backed path; kept as the
# declaration the CLI/MCP parity gate reads.
_UNBUILT: dict[str, str] = {}

# The half of `diff` that needs a built part, named where the output would have shown it.
_DIFF_NEEDS_GEOMETRY = (
    "mass, volume and centre-of-gravity deltas need two built parts. See " + _GEOMETRY_SPEC + "."
)

# The artifact-level local gap list. Empty now that DXF builds through the same audited
# registry as `build`; kept as the declaration the surface-parity gate reads.
#
# **QIF used to be on this list, and the reason given for it was not true.** It said "QIF
# results carry measured characteristics against a built part", and
# `anvilate.export.qif.export_qif_results` takes a `BundleSections` and touches no geometry
# at all: `artifact-export` asks the layer to export "a validated part's scorecard and
# evidence" as QIF, `docs/quality-interchange.md` is written about exactly that crossing,
# and `examples/lug_scorecard_as_qif.py` produces a schema-valid document from a scorecard.
# A refusal wide enough to cover something that works is as misleading as a missing one —
# which is the same mistake, one level down, that this module's own docstring records
# `export` being refused whole for.
_NEEDS_GEOMETRY: dict[str, str] = {}

# Served here and not yet over MCP, with the reason it waits on stated as the thing it
# really is. `export_artifact` publishes a result whose payload is the evidence bundle
# *document* — a JSON object with its own schema — and a QIF results file is XML. Serving it
# there is a change to a published tool result, which is a decision to make in a diff about
# the protocol surface rather than one to arrive at by removing a line here.
_NOT_YET_OVER_MCP = {
    "dxf": (
        "the export tool has no approved CAD-content delivery contract: returning a DXF "
        "would disclose built design geometry to the remote caller. "
        "`anvilate export --artifact dxf` produces the document locally today."
    ),
    "qif": (
        "the export tool's published result carries the evidence bundle document, and QIF "
        "results are an XML file, so serving them here is a change to the tool's result "
        "shape. `anvilate export --artifact qif` produces the document at the shell today."
    ),
}

# What each surface refuses. The shell refuses what cannot be produced at all; the tool
# refuses that, plus what its own published result cannot yet carry.
_UNBUILT_ARTIFACTS = _NEEDS_GEOMETRY
_UNSERVED_OVER_MCP = {**_NEEDS_GEOMETRY, **_NOT_YET_OVER_MCP}
_ARTIFACTS = ("evidence-bundle", "dxf", "qif")

_COMMAND_EXAMPLES = {
    "check": "anvilate check parts/bracket.yaml --show-work",
    "export": "anvilate export parts/ --format json",
    "verify": "anvilate verify bundle.dsse.json --artifact scorecard.json=scorecard.json",
    "diff": "anvilate diff before.yaml after.yaml --format json",
    "build": "anvilate build part.yaml --output part.step",
    "doctor": "anvilate doctor --format json",
    "interfaces": "anvilate interfaces mating.step --format json",
}


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


def completion_script(parser: argparse.ArgumentParser, shell: str) -> str:
    """A completion script for ``shell``, read off ``parser`` so it cannot drift from it.

    Every command and every option each command takes comes from the parser itself; a
    hand-written list is the one that falls behind the day a flag is added. zsh loads the
    same function through its bash-completion layer.
    """
    top = sorted(o for a in parser._actions for o in a.option_strings)
    (subparsers,) = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    cases = []
    for name, sub in sorted(subparsers.choices.items()):
        options = sorted(o for a in sub._actions for o in a.option_strings)
        cases.append(f'    {name}) options="{" ".join(options)}" ;;')
    commands = " ".join(sorted(subparsers.choices))
    script = "\n".join(
        [
            "_anvilate() {",
            '  local current="${COMP_WORDS[COMP_CWORD]}" command="${COMP_WORDS[1]}" options=""',
            '  if [ "$COMP_CWORD" -eq 1 ]; then',
            f'    COMPREPLY=( $(compgen -W "{commands} {" ".join(top)}" -- "$current") )',
            "    return",
            "  fi",
            '  case "$command" in',
            *cases,
            "  esac",
            '  if [[ "$current" == -* ]]; then',
            '    COMPREPLY=( $(compgen -W "$options" -- "$current") )',
            "  else",
            '    COMPREPLY=( $(compgen -f -- "$current") )',
            "  fi",
            "}",
            "complete -o filenames -F _anvilate anvilate",
            "",
        ]
    )
    if shell == "zsh":
        return "autoload -U +X bashcompinit && bashcompinit\n" + script
    return script


class _Completion(argparse.Action):
    """``--completion SHELL``: print the script and exit, before a command is required."""

    def __call__(self, parser, namespace, values, option_string=None):  # type: ignore[no-untyped-def]
        parser._print_message(completion_script(parser, str(values)), sys.stdout)
        parser.exit()


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
        "never a pass — 3 a bad request, 4 an operation that is specified and unbuilt, "
        "5 an unexpected internal error. "
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
    parser.add_argument(
        "--completion",
        choices=("bash", "zsh"),
        action=_Completion,
        help="print a shell completion script built from this parser, and exit; "
        'e.g. `eval "$(anvilate --completion bash)"`',
    )
    commands = parser.add_subparsers(dest="command", required=True)

    interfaces = commands.add_parser(
        "interfaces",
        help="detect planar faces and through-hole patterns in a mating STEP",
        description="Import one local STEP and list measured interface candidates. "
        "No candidate becomes a Design Spec contract until a user confirms it. Exit 0 "
        "means the import and detection completed, and any requested fit check passed; "
        "an out-of-zone fit check exits 1, a bad file exits 3, and a missing geometry "
        "runtime exits 4.",
        epilog=f"Example: {_COMMAND_EXAMPLES['interfaces']}",
    )
    interfaces.add_argument("step", type=Path, help="the local mating-part STEP file to inspect")
    interfaces.add_argument(
        "--format", choices=("text", "json"), default="text", help="how to render the candidates"
    )
    interfaces.add_argument(
        "--solid",
        metavar="SOLID_ID",
        help="only list and accept candidates belonging to this exact detected solid",
    )
    interfaces.add_argument(
        "--accept",
        metavar="PATTERN_ID",
        help="accept this exact detected hole-pattern candidate as an interface contract",
    )
    interfaces.add_argument(
        "--accept-contact",
        metavar="CONTACT_ID",
        help="accept this exact detected planar contact without inventing a hole pattern",
    )
    interfaces.add_argument(
        "--accept-mate",
        metavar="MATE_ID",
        help="accept this exact detected cylindrical mate without judging its fit",
    )
    interfaces.add_argument(
        "--accept-gap",
        metavar="GAP_ID",
        help="accept this exact detected planar gap without inventing an allowable clearance",
    )
    interfaces.add_argument(
        "--fit",
        metavar="HOLE/SHAFT",
        help="check the accepted cylindrical mate against this explicit ISO 286 fit",
    )
    interfaces.add_argument(
        "--basic-size",
        metavar="QUANTITY",
        help="basic size with unit for --fit, for example '10 mm'",
    )
    interfaces.add_argument(
        "--min-contact-area",
        metavar="QUANTITY",
        help="minimum required overlap area with unit for --accept-contact",
    )
    interfaces.add_argument(
        "--min-engagement",
        metavar="QUANTITY",
        help="minimum required axial engagement with unit for --accept-mate",
    )
    interfaces.add_argument(
        "--min-gap",
        metavar="QUANTITY",
        help="minimum allowed gap with unit for --accept-gap",
    )
    interfaces.add_argument(
        "--max-gap",
        metavar="QUANTITY",
        help="maximum allowed gap with unit for --accept-gap",
    )
    interfaces.add_argument(
        "--requirement",
        help="source clause for caller-supplied contact-area or gap limits",
    )
    interfaces.add_argument("--name", help="semantic name for the accepted artifact")
    interfaces.add_argument(
        "--mating-plane", help="semantic mating-face tag to publish in the accepted contract"
    )
    interfaces.add_argument(
        "--confirmed-by", help="name of the person who reviewed and accepts the measured candidate"
    )
    interfaces.add_argument(
        "--locator",
        metavar="FEATURE_ID",
        help="also accept this exact concentric bore, boss, or counterbore candidate",
    )

    check = commands.add_parser(
        "check",
        help="compile a spec document and screen it, printing the scorecard",
        description="Screen every spec given, or every spec under a directory. Exit 0 "
        "only when every check passed, 1 if one failed, 2 if a card could not be fully "
        "evaluated. Blocking checks are listed on stderr with the spec they came from.",
        epilog=f"Example: {_COMMAND_EXAMPLES['check']}",
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
        help="verify an attestation envelope or STEP import integrity",
        description="Check a DSSE envelope's signature, subject digests and predicate schema, "
        "or compare a .step/.stp file's imported geometry with its CAx-IF validation properties, "
        "offline. Exit 0 only when every applicable check passes; 1 on a mismatch; 2 when an "
        "attestation check could not run.",
        epilog=f"Example: {_COMMAND_EXAMPLES['verify']}",
    )
    verify.add_argument("envelope", type=Path, help="a DSSE envelope as JSON, or a STEP file")
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
        epilog=f"Example: {_COMMAND_EXAMPLES['diff']}",
    )
    diff.add_argument("before", type=Path, help="the spec as it was")
    diff.add_argument("after", type=Path, help="the spec as it is")
    diff.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="text for a person, json for the merge gate that has to decide",
    )

    export = commands.add_parser(
        "export",
        help="write a downstream artifact from a screened spec",
        description="Render the chosen artifact for every spec given, or every spec under "
        "a directory. The exit code is the bundle roll-up, which is never better than its "
        "worst section: 0 when every section passed, 1 when one failed, 2 when one could "
        "not be evaluated. QIF and DXF results are gated on the card passing, as "
        "`artifact-export` asks; unsupported geometry is refused with 4.",
        epilog=f"Example: {_COMMAND_EXAMPLES['export']}",
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
        help="which artifact; DXF builds an audited plate profile before rendering",
    )
    export.add_argument(
        "--format", choices=("text", "json"), default="text", help="how to render it"
    )

    doctor = commands.add_parser(
        "doctor",
        help="check which Anvilate runtime capabilities are ready",
        description="Check solvers, geometry, the local model runtime, viewport support, "
        "and bundled database integrity independently. Exit 0 only when every item passes.",
        epilog=f"Example: {_COMMAND_EXAMPLES['doctor']}",
    )
    doctor.add_argument(
        "--format", choices=("text", "json"), default="text", help="how to render the report"
    )

    build = commands.add_parser(
        "build",
        help="build an audited Design Spec geometry pattern as STEP",
        description="Build one Design Spec as a valid B-Rep and write a validation-stamped "
        "STEP. Base plates, cover plates, and transmission shafts are supported; unsupported "
        "patterns exit 4 and name "
        "the missing pattern. A nonpassing card writes nothing unless --unvalidated is "
        "explicit. Exit 0 means the STEP was written; a bad spec or output exits 3, and an "
        "unexpected kernel error exits 5. Existing files are not overwritten unless "
        "--force is given.",
        epilog=f"Example: {_COMMAND_EXAMPLES['build']}",
    )
    build.add_argument("spec", type=Path, help="the Design Spec document to build")
    build.add_argument("--output", type=Path, required=True, help="STEP file to write")
    build.add_argument(
        "--unvalidated",
        action="store_true",
        help="write a conspicuously watermarked STEP when the scorecard does not pass",
    )
    build.add_argument(
        "--ap214",
        action="store_true",
        help="use the explicit AP214 fallback for a legacy receiver (AP242 is the default)",
    )
    build.add_argument(
        "--force", action="store_true", help="replace an existing output file deliberately"
    )
    build.add_argument(
        "--format", choices=("text", "json"), default="text", help="how to render the result"
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
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_requested = _wants_json(arguments)
    parser = _build_parser()
    if json_requested:
        parse_diagnostics = io.StringIO()
        try:
            with contextlib.redirect_stderr(parse_diagnostics):
                args = parser.parse_args(arguments)
        except SystemExit as failure:
            if failure.code == EXIT_OK:
                raise
            diagnostic = parse_diagnostics.getvalue()
            print(diagnostic, end="", file=err)
            _print_refusal(
                command=_requested_command(arguments),
                code=EXIT_BAD_REQUEST,
                diagnostic=diagnostic,
                out=out,
            )
            return EXIT_BAD_REQUEST
        captured = io.StringIO()
        captured_out = io.StringIO()
        command_err = captured
        command_out = captured_out
    else:
        args = parser.parse_args(arguments)
        command_err = err
        command_out = out

    try:
        if args.command == "build":
            code = _build(args, out=command_out, err=command_err)
        elif args.command == "interfaces":
            code = _interfaces(args, out=command_out, err=command_err)
        elif args.command == "export":
            code = _export(args, out=command_out, err=command_err)
        elif args.command == "verify":
            code = _verify(args, out=command_out, err=command_err)
        elif args.command == "diff":
            code = _diff(args, out=command_out, err=command_err)
        elif args.command == "doctor":
            code = _doctor(args, out=command_out)
        else:
            code = _check(args, out=command_out, err=command_err)
    except (KeyboardInterrupt, _Cancelled) as stopped:
        completed = (
            stopped.completed
            if isinstance(stopped, _Cancelled)
            else "the command did not reach a result"
        )
        print(
            f"anvilate {args.command}: cancelled — {completed}; nothing was reported as a "
            "verdict and no partial artifact was left as complete",
            file=err,
        )
        if json_requested:
            print(
                json.dumps(
                    cancelled_document(args.command, completed=completed),
                    indent=2,
                    sort_keys=True,
                ),
                file=out,
            )
        return EXIT_CANCELLED
    except Exception as failure:
        print(
            f"anvilate {args.command}: internal error: {type(failure).__name__}: {failure}",
            file=command_err,
        )
        code = EXIT_INTERNAL_ERROR

    if json_requested:
        diagnostic = captured.getvalue()
        payload = captured_out.getvalue()
        print(diagnostic, end="", file=err)
        if payload:
            print(payload, end="", file=out)
        elif code == EXIT_INTERNAL_ERROR:
            _print_error(command=args.command, diagnostic=diagnostic, out=out)
        elif diagnostic:
            _print_refusal(command=args.command, code=code, diagnostic=diagnostic, out=out)
    return code


def _wants_json(arguments: list[str]) -> bool:
    """Whether an invocation requested JSON, even when the parser will reject it."""
    return "--format=json" in arguments or any(
        option == "--format" and value == "json"
        for option, value in zip(arguments, arguments[1:], strict=False)
    )


def _requested_command(arguments: list[str]) -> str:
    """Best command identity available before a malformed invocation can be parsed."""
    commands = {"build", "check", "verify", "diff", "export", "doctor", "interfaces", *_UNBUILT}
    return next((argument for argument in arguments if argument in commands), "anvilate")


def _print_refusal(*, command: str, code: int, diagnostic: str, out) -> None:
    """Write the JSON refusal corresponding to diagnostics already sent to stderr."""
    lines = tuple(line for line in diagnostic.splitlines() if line)
    remedy = (
        f"Correct the {command} arguments or input document named in diagnostics, then retry."
        if code == EXIT_BAD_REQUEST
        else (
            f"Use a backed command, or implement the capability named by anvilate {command}."
            if code == EXIT_UNBUILT
            else f"Resolve the {command} condition named in diagnostics, then retry."
        )
    )
    print(
        json.dumps(
            refusal_document(
                command,
                exit_code=code,
                diagnostics=lines,
                remedy=remedy,
            ),
            indent=2,
            sort_keys=True,
        ),
        file=out,
    )


def _print_error(*, command: str, diagnostic: str, out) -> None:
    """Write an unexpected defect without making a script parse a traceback."""
    print(
        json.dumps(
            error_document(
                command,
                diagnostic=diagnostic.strip(),
                remedy=(
                    "Retry once; if the error repeats, report this diagnostic as an Anvilate bug."
                ),
            ),
            indent=2,
            sort_keys=True,
        ),
        file=out,
    )


def _doctor(args: argparse.Namespace, *, out) -> int:
    """Report each required runtime capability independently and actionably."""
    from importlib.metadata import PackageNotFoundError, version

    from .standards import default_standards_resolver

    specs = "https://github.com/clay-good/anvilate/tree/main/openspec/specs"
    checks: list[dict[str, Any]] = [
        {
            "name": "FEA solver",
            "status": "fail",
            "detail": "No FEA solver backend is shipped or configured in this release.",
            "remedy": (
                f"Implement and configure the T3 backend specified in {specs}/validation-gauntlet."
            ),
        },
        {
            "name": "local model runtime",
            "status": "fail",
            "detail": "No local intent-compilation model runtime is shipped or configured.",
            "remedy": (
                f"Configure the local runtime selected by {specs}/intent-compilation once "
                "implemented."
            ),
        },
    ]
    try:
        from build123d import Box

        from .geometry import BASE_PLATE_PATTERN, BuiltGeometry, render_viewport

        probe = Box(1, 1, 1)
        if not probe.is_valid or len(probe.solids()) != 1:
            raise RuntimeError("the kernel probe did not produce one valid solid")
        viewport = render_viewport(
            BuiltGeometry(
                name="doctor",
                pattern=BASE_PLATE_PATTERN,
                shape=probe,
                faces={},
                dimensions_mm={"width": 1, "depth": 1, "plate_thickness": 1},
            ),
            width_px=64,
        )
        if not viewport.data.startswith(b'<?xml version="1.0"'):
            raise RuntimeError("the viewport probe did not produce an SVG image")
        build123d_version = version("build123d")
        ocp_version = version("cadquery-ocp-novtk")
    except (ImportError, PackageNotFoundError, RuntimeError) as failure:
        checks.insert(
            1,
            {
                "name": "geometry kernel",
                "status": "fail",
                "detail": f"The build123d/OCCT geometry runtime is not ready: {failure}",
                "remedy": "Install the geometry runtime with `pip install anvilate[geometry]`.",
            },
        )
        checks.insert(
            2,
            {
                "name": "viewport prerequisites",
                "status": "fail",
                "detail": (
                    f"Viewport rendering is not ready because geometry is unavailable: {failure}"
                ),
                "remedy": "Install the geometry runtime with `pip install anvilate[geometry]`.",
            },
        )
    else:
        checks.insert(
            1,
            {
                "name": "geometry kernel",
                "status": "pass",
                "detail": (
                    f"build123d {build123d_version} with cadquery-ocp-novtk {ocp_version} "
                    "produced one valid B-Rep probe solid."
                ),
                "remedy": None,
            },
        )
        checks.insert(
            2,
            {
                "name": "viewport prerequisites",
                "status": "pass",
                "detail": "The deterministic SVG renderer produced a 64 px viewport image.",
                "remedy": None,
            },
        )
    resolver = default_standards_resolver()
    material_count = len(resolver.known_materials())
    component_count = len(resolver.known_components())
    checks.append(
        {
            "name": "database integrity",
            "status": "pass",
            "detail": (
                f"Loaded {material_count} material and {component_count} component designations "
                "from the bundled standards databases."
            ),
            "remedy": None,
        }
    )
    status = "fail" if any(check["status"] == "fail" for check in checks) else "pass"
    if args.format == "json":
        print(
            json.dumps(
                machine_document("doctor", {"status": status, "checks": checks}),
                indent=2,
                sort_keys=True,
            ),
            file=out,
        )
    else:
        print(f"doctor: {status.upper()}", file=out)
        for check in checks:
            print(f"  {check['status']:<4}  {check['name']}: {check['detail']}", file=out)
            if check["remedy"]:
                print(f"        fix: {check['remedy']}", file=out)
    return EXIT_OK if status == "pass" else EXIT_FAILED


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
    document = _diff_document(
        before_spec,
        after_spec,
        before_card,
        after_card,
        before_path=args.before,
        after_path=args.after,
    )
    if args.format == "json":
        print(
            json.dumps(machine_document("diff", document), indent=2, sort_keys=True),
            file=out,
        )
    else:
        print(_render_diff(document), file=out)

    regressions = _regressions(before_card, after_card)
    for name, was, now in regressions:
        print(f"anvilate diff: {name}: {was.value} → {now.value}", file=err)
    # The card's own verdict, which no per-check comparison can see. A revision that renames
    # the element deletes every check by name and adds a not-evaluated gap in their place:
    # nothing "moved for the worse", and the part went from screened to unscreened. A
    # different set of checks is not a worse set — that decision stands — but a different
    # verdict is a worse verdict, and the roll-up is defined for exactly this comparison.
    #
    # `_moved_for_the_worse`, not `_BLOCKING_ORDER` directly: this line used the blocking
    # order, which sorts FAIL above NOT_EVALUATED because a failure is the thing to look at
    # first — so it read `fail → not_evaluated` as an improvement and exited 0 over a change
    # that deleted the failing checks. Deleting the element does it, and so does deleting the
    # constraint they are judged against.
    worse = _moved_for_the_worse(before_card.status, after_card.status)
    if worse:
        print(
            f"anvilate diff: the card: {before_card.status.value} → {after_card.status.value}",
            file=err,
        )
    # Off the document rather than recomputed beside it. `regression.status` is the one
    # conclusion a consumer cannot rebuild from the rest of the payload without
    # reimplementing `_moved_for_the_worse`, and an exit code computed separately from the
    # number the payload publishes is two answers to one question.
    regressed_to = document["regression"]["status"]
    return EXIT_OK if regressed_to is None else EXIT_CODES[CheckStatus(regressed_to)]


def _moved_for_the_worse(was: CheckStatus, now: CheckStatus) -> bool:
    """Did this verdict get worse? Which is not the question ``_BLOCKING_ORDER`` answers.

    That list ranks how hard a verdict *blocks* — a FAIL is the thing to look at before a
    NOT_EVALUATED, so it sorts above it — and the diff read it as an ordering of badness. On
    that reading ``fail → not_evaluated`` is an **improvement**, and `anvilate diff` exited 0,
    "nothing regressed", over a change that deleted two failing checks and left the tier
    unevaluated. Its own rendering said ``- padeye net tension: removed (was fail)`` three
    lines above the exit code that contradicted it. Deleting the thing being checked is the
    way to silence a failing gate, so it is the one change a gate must never call an
    improvement.

    So a verdict that becomes NOT_EVALUATED is a regression from anything else. "A screen that
    could not run is not a screen that passed" is this library's rule, and this is the rest of
    it: nor is it a screen that improved on one that failed. Going from a known failure to not
    knowing loses the check. Everything else is the blocking order, which is right for the
    comparisons that stay inside the screened statuses.

    **FAIL and NOT_EVALUATED are therefore incomparable, and that is the point.** Both
    directions between them are reported: one loses the check, the other reveals a failure, and
    neither is an improvement. No single ordering of the five statuses can say that, which is
    how a list built to rank blocking urgency came to be read as a scale of badness.

    ``OUT_OF_DEPTH`` is the same rule stated once more, for a check that stops running because
    the document deferred it. A deliberate deferral is an honest answer and it is not an
    improvement on a check that ran: `fail → out_of_depth` silences a failing gate exactly as
    `fail → not_evaluated` does, and by declaring a depth rather than by deleting an element.
    Nor is `not_evaluated → out_of_depth` an improvement — the check still does not run, and a
    revision that only relabels why must not report progress. The one ordered pair is
    `out_of_depth → pass`, which is a check that now runs and passes.
    """
    if was is now:
        return False
    if was in _RAN and now not in _RAN:
        return True  # the check stopped producing a verdict, however deliberately
    if was not in _RAN and now not in _RAN:
        return True  # it still does not run; relabelling why is not progress
    return _BLOCKING_ORDER.index(now) > _BLOCKING_ORDER.index(was)


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
        if entry.name in was and _moved_for_the_worse(was[entry.name], entry.status)
    ]


#: How many decimals a safety factor is shown to, everywhere this tool prints one.
#:
#: The comparison below is made at this precision rather than on the raw floats, so the
#: command never reports a move a reader cannot see in the figures it is shown — and never
#: stays silent about one they can.
_MARGIN_DECIMALS = 2


def _margin_move(was: ScorecardEntry, now: ScorecardEntry) -> dict[str, Any] | None:
    """The safety factor's movement between two revisions of one check, or ``None``.

    ``None`` for a check that carries no safety factor on either side — a resolution, a
    classification, a tier that did not run — and for one whose figure is the same to the
    decimals it is printed with.
    """
    before, after = was.safety_factor, now.safety_factor
    if before is None and after is None:
        return None
    shown = (
        None if before is None else round(before, _MARGIN_DECIMALS),
        None if after is None else round(after, _MARGIN_DECIMALS),
    )
    if shown[0] == shown[1]:
        return None
    return {"before": before, "after": after, "worse": _margin_is_worse(before, after)}


def _margin_is_worse(before: float | None, after: float | None) -> bool:
    """Whether the margin moved toward its limit. A check that gained or lost one moved.

    Reported rather than graded: it does not reach the exit code. See the `margin` branch in
    :func:`_diff_document` for why.
    """
    if before is None or after is None:
        return True
    return after < before


def _diff_document(
    before_spec,
    after_spec,
    before: Scorecard,
    after: Scorecard,
    *,
    before_path: Path,
    after_path: Path,
) -> dict[str, Any]:
    """The comparison itself, as data, before anybody has decided how to print it.

    Both renderings and the exit code come off this one structure. The text rendering used
    to *be* the comparison — the sections were built as strings, and the exit code was
    computed a second time, separately, from the cards — so a machine-readable diff written
    as a second renderer would have been a second implementation of "what moved", free to
    disagree with the first. A merge gate reads `diff`, and the thing it reads has to be the
    thing the human reviewer is shown.

    Every key is present on every run, including the sections with nothing in them. A shape
    that changes with the content is a shape every caller has to branch on, and the branch is
    wrong the first time a comparison happens to be empty — the same rule `check --format
    json` follows about `governing`, and the reason the text rendering prints ``GEOMETRY``
    even though it has nothing to say under it.
    """
    import difflib

    from .spec import dump_spec_yaml

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

    was = {entry.name: entry for entry in before.entries}
    now = {entry.name: entry for entry in after.entries}
    moved: list[dict[str, Any]] = []
    for name in sorted(set(was) | set(now)):
        if name not in now:
            # Removed and added are `worse: false` deliberately. A different set of checks
            # is not a worse set, and the exit code has never claimed otherwise; what makes
            # a deletion visible is the card's own verdict below, which cannot be deleted.
            moved.append(
                {
                    "name": name,
                    "change": "removed",
                    "before": was[name].status.value,
                    "after": None,
                    "detail": None,
                    "margin": None,
                    "worse": False,
                }
            )
        elif name not in was:
            moved.append(
                {
                    "name": name,
                    "change": "added",
                    "before": None,
                    "after": now[name].status.value,
                    "detail": now[name].detail,
                    "margin": None,
                    "worse": False,
                }
            )
        elif was[name].status is not now[name].status:
            moved.append(
                {
                    "name": name,
                    "change": "moved",
                    "before": was[name].status.value,
                    "after": now[name].status.value,
                    "detail": now[name].detail,
                    "margin": _margin_move(was[name], now[name]),
                    "worse": _moved_for_the_worse(was[name].status, now[name].status),
                }
            )
        elif (margin := _margin_move(was[name], now[name])) is not None:
            # A check whose verdict held and whose margin moved. Cutting a padeye from 20 mm
            # to 12 mm took its pin bearing from 3.33 to exactly its required 2.00, and this
            # command — whose whole job is telling an engineer what a revision did — answered
            # `no verdict changed / (3 unchanged)`. "Unchanged" was true about the verdict
            # and false about the check.
            #
            # `worse` stays False, deliberately. The exit code is a verdict contract a merge
            # gate reads, and a margin that moved inside its band has not regressed; making
            # this exit non-zero would fail every ordinary revision. It is reported, not
            # graded.
            moved.append(
                {
                    "name": name,
                    "change": "margin",
                    "before": was[name].status.value,
                    "after": now[name].status.value,
                    "detail": now[name].detail,
                    "margin": margin,
                    "worse": False,
                }
            )

    verdict_worse = _moved_for_the_worse(before.status, after.status)
    # The worst status anything regressed *to*, which is what the exit code is. `max` over
    # the exit severity rather than over the statuses: `fail` and `not_evaluated` are
    # incomparable as verdicts, but the codes they exit with are ordered, and it is the code
    # this line has to pick.
    regressed_to = [entry["after"] for entry in moved if entry["worse"]]
    if verdict_worse:
        regressed_to.append(after.status.value)
    return {
        "before": {
            "path": str(before_path),
            "name": before_spec.name,
            "status": before.status.value,
        },
        "after": {
            "path": str(after_path),
            "name": after_spec.name,
            "status": after.status.value,
        },
        "spec": {"changed": bool(changed), "lines": changed},
        "verdict": {
            "before": before.status.value,
            "after": after.status.value,
            "worse": verdict_worse,
        },
        "checks": {
            "moved": moved,
            "unchanged": sum(
                1
                for name in set(was) & set(now)
                if was[name].status is now[name].status
                and _margin_move(was[name], now[name]) is None
            ),
        },
        "geometry": {"compared": False, "reason": _DIFF_NEEDS_GEOMETRY},
        "regression": {
            "regressed": bool(regressed_to),
            "status": (
                None
                if not regressed_to
                else max(
                    regressed_to, key=lambda s: _EXIT_SEVERITY.index(EXIT_CODES[CheckStatus(s)])
                )
            ),
        },
    }


def _margin_figure(value: float | None) -> str:
    """A safety factor for the diff line, or the word for a check that carries none."""
    return "none" if value is None else f"{value:.{_MARGIN_DECIMALS}f}"


def _interfaces(args: argparse.Namespace, *, out, err) -> int:
    """Inspect one local STEP file for measured, unconfirmed mating interfaces."""
    from .geometry import (
        GeometryError,
        GeometryUnavailable,
        _assembly_interface_scorecard,
        _interference_scorecard,
        check_cylindrical_mate_engagement,
        check_cylindrical_mate_fit,
        check_planar_contact_area,
        check_planar_gap_clearance,
        confirm_cylindrical_mate,
        confirm_planar_contact,
        confirm_planar_gap,
        confirm_step_interface,
        detect_step_interfaces,
    )

    pattern_acceptance = {
        "--accept": args.accept,
        "--name": args.name,
        "--mating-plane": args.mating_plane,
        "--confirmed-by": args.confirmed_by,
    }
    pattern_supplied = {option for option, value in pattern_acceptance.items() if value is not None}
    acceptance_modes = {
        "--accept": args.accept,
        "--accept-contact": args.accept_contact,
        "--accept-mate": args.accept_mate,
        "--accept-gap": args.accept_gap,
    }
    supplied_modes = [option for option, value in acceptance_modes.items() if value is not None]
    if len(supplied_modes) > 1:
        print(
            "anvilate interfaces: --accept, --accept-contact, --accept-mate, and "
            "--accept-gap are mutually exclusive",
            file=err,
        )
        return EXIT_BAD_REQUEST
    if (args.fit is not None or args.basic_size is not None) and args.accept_mate is None:
        print("anvilate interfaces: --fit and --basic-size require --accept-mate", file=err)
        return EXIT_BAD_REQUEST
    if args.accept_contact is not None:
        contact_acceptance = {
            "--accept-contact": args.accept_contact,
            "--name": args.name,
            "--confirmed-by": args.confirmed_by,
        }
        contact_supplied = {
            option for option, value in contact_acceptance.items() if value is not None
        }
        if len(contact_supplied) != len(contact_acceptance):
            missing = ", ".join(
                option for option in contact_acceptance if option not in contact_supplied
            )
            print(
                "anvilate interfaces: accepting a contact requires --accept-contact, --name, "
                f"and --confirmed-by; missing {missing}",
                file=err,
            )
            return EXIT_BAD_REQUEST
        if args.mating_plane is not None:
            print("anvilate interfaces: --mating-plane requires --accept", file=err)
            return EXIT_BAD_REQUEST
    elif args.accept_mate is not None:
        mate_acceptance = {
            "--accept-mate": args.accept_mate,
            "--name": args.name,
            "--confirmed-by": args.confirmed_by,
        }
        mate_supplied = {option for option, value in mate_acceptance.items() if value is not None}
        if len(mate_supplied) != len(mate_acceptance):
            missing = ", ".join(option for option in mate_acceptance if option not in mate_supplied)
            print(
                "anvilate interfaces: accepting a cylindrical mate requires --accept-mate, "
                f"--name, and --confirmed-by; missing {missing}",
                file=err,
            )
            return EXIT_BAD_REQUEST
        if args.mating_plane is not None:
            print("anvilate interfaces: --mating-plane requires --accept", file=err)
            return EXIT_BAD_REQUEST
    elif args.accept_gap is not None:
        gap_acceptance = {
            "--accept-gap": args.accept_gap,
            "--name": args.name,
            "--confirmed-by": args.confirmed_by,
        }
        gap_supplied = {option for option, value in gap_acceptance.items() if value is not None}
        if len(gap_supplied) != len(gap_acceptance):
            missing = ", ".join(option for option in gap_acceptance if option not in gap_supplied)
            print(
                "anvilate interfaces: accepting a planar gap requires --accept-gap, --name, "
                f"and --confirmed-by; missing {missing}",
                file=err,
            )
            return EXIT_BAD_REQUEST
        if args.mating_plane is not None:
            print("anvilate interfaces: --mating-plane requires --accept", file=err)
            return EXIT_BAD_REQUEST
    elif pattern_supplied and len(pattern_supplied) != len(pattern_acceptance):
        missing = ", ".join(
            option for option in pattern_acceptance if option not in pattern_supplied
        )
        print(
            "anvilate interfaces: accepting a candidate requires --accept, --name, "
            f"--mating-plane, and --confirmed-by; missing {missing}",
            file=err,
        )
        return EXIT_BAD_REQUEST
    if args.locator is not None and args.accept is None:
        print("anvilate interfaces: --locator requires --accept", file=err)
        return EXIT_BAD_REQUEST
    fit_acceptance = {"--fit": args.fit, "--basic-size": args.basic_size}
    fit_supplied = {option for option, value in fit_acceptance.items() if value is not None}
    if fit_supplied:
        if len(fit_supplied) != len(fit_acceptance):
            missing = ", ".join(option for option in fit_acceptance if option not in fit_supplied)
            print(
                "anvilate interfaces: a fit check requires --fit and --basic-size; "
                f"missing {missing}",
                file=err,
            )
            return EXIT_BAD_REQUEST
    contact_check_acceptance = {
        "--min-contact-area": args.min_contact_area,
        "--requirement": args.requirement,
    }
    contact_check_supplied = {
        option for option, value in contact_check_acceptance.items() if value is not None
    }
    if args.accept_contact is not None or args.min_contact_area is not None:
        if contact_check_supplied:
            if args.accept_contact is None:
                print(
                    "anvilate interfaces: --min-contact-area and --requirement require "
                    "--accept-contact",
                    file=err,
                )
                return EXIT_BAD_REQUEST
            if len(contact_check_supplied) != len(contact_check_acceptance):
                missing = ", ".join(
                    option
                    for option in contact_check_acceptance
                    if option not in contact_check_supplied
                )
                print(
                    "anvilate interfaces: a contact-area check requires --min-contact-area "
                    f"and --requirement; missing {missing}",
                    file=err,
                )
                return EXIT_BAD_REQUEST
    engagement_check_acceptance = {
        "--min-engagement": args.min_engagement,
        "--requirement": args.requirement,
    }
    engagement_check_supplied = {
        option for option, value in engagement_check_acceptance.items() if value is not None
    }
    if args.accept_mate is not None or args.min_engagement is not None:
        if engagement_check_supplied:
            if args.accept_mate is None:
                print(
                    "anvilate interfaces: --min-engagement and --requirement require --accept-mate",
                    file=err,
                )
                return EXIT_BAD_REQUEST
            if len(engagement_check_supplied) != len(engagement_check_acceptance):
                missing = ", ".join(
                    option
                    for option in engagement_check_acceptance
                    if option not in engagement_check_supplied
                )
                print(
                    "anvilate interfaces: an engagement check requires --min-engagement "
                    f"and --requirement; missing {missing}",
                    file=err,
                )
                return EXIT_BAD_REQUEST
    gap_check_acceptance = {
        "--min-gap": args.min_gap,
        "--max-gap": args.max_gap,
        "--requirement": args.requirement,
    }
    gap_check_supplied = {
        option for option, value in gap_check_acceptance.items() if value is not None
    }
    if args.accept_gap is not None or args.min_gap is not None or args.max_gap is not None:
        if gap_check_supplied:
            if args.accept_gap is None:
                print(
                    "anvilate interfaces: gap limits and --requirement require --accept-gap",
                    file=err,
                )
                return EXIT_BAD_REQUEST
            if len(gap_check_supplied) != len(gap_check_acceptance):
                missing = ", ".join(
                    option for option in gap_check_acceptance if option not in gap_check_supplied
                )
                print(
                    "anvilate interfaces: a gap check requires --min-gap, --max-gap, and "
                    f"--requirement; missing {missing}",
                    file=err,
                )
                return EXIT_BAD_REQUEST
    if (
        args.requirement is not None
        and args.accept_contact is None
        and args.accept_mate is None
        and args.accept_gap is None
    ):
        print(
            "anvilate interfaces: --requirement requires --accept-contact, --accept-mate, "
            "or --accept-gap",
            file=err,
        )
        return EXIT_BAD_REQUEST

    try:
        detected = detect_step_interfaces(args.step)
        if args.solid is not None:
            solid_ids = sorted(
                {face.solid_id for face in detected.planar_faces if face.solid_id is not None}
            )
            if args.solid not in solid_ids:
                if solid_ids:
                    available = ", ".join(solid_ids)
                    raise GeometryError(
                        f"solid candidate {args.solid!r} was not found; available: {available}"
                    )
                raise GeometryError(
                    "this STEP contains one solid and exposes no solid ID; omit --solid"
                )
            related_interferences = tuple(
                candidate
                for candidate in detected.solid_interferences
                if args.solid in {candidate.first_solid_id, candidate.second_solid_id}
            )
            detected = detected.model_copy(
                update={
                    "solids": tuple(solid for solid in detected.solids if solid.id == args.solid),
                    "planar_contacts": tuple(
                        contact
                        for contact in detected.planar_contacts
                        if args.solid in {contact.first_solid_id, contact.second_solid_id}
                    ),
                    "planar_gaps": tuple(
                        gap
                        for gap in detected.planar_gaps
                        if args.solid in {gap.first_solid_id, gap.second_solid_id}
                    ),
                    "cylindrical_mates": tuple(
                        mate
                        for mate in detected.cylindrical_mates
                        if args.solid in {mate.bore_solid_id, mate.shaft_solid_id}
                    ),
                    "solid_interferences": related_interferences,
                    "interference_scorecard": _interference_scorecard(
                        related_interferences, pair_count=len(detected.solids) - 1
                    ),
                    "planar_faces": tuple(
                        face for face in detected.planar_faces if face.solid_id == args.solid
                    ),
                }
            )
        accepted = None
        accepted_contact = None
        accepted_mate = None
        accepted_gap = None
        contact_check = None
        engagement_check = None
        fit_check = None
        gap_check = None
        if args.accept is not None:
            accepted = confirm_step_interface(
                detected,
                pattern_id=args.accept,
                name=args.name,
                mating_plane=args.mating_plane,
                confirmed_by=args.confirmed_by,
                locating_feature_id=args.locator,
            )
        elif args.accept_contact is not None:
            accepted_contact = confirm_planar_contact(
                detected,
                contact_id=args.accept_contact,
                name=args.name,
                confirmed_by=args.confirmed_by,
            )
            if args.min_contact_area is not None:
                try:
                    contact_check = check_planar_contact_area(
                        accepted_contact,
                        minimum_overlap_area=Quantity.parse(args.min_contact_area),
                        reference=args.requirement,
                    )
                except ValueError as failure:
                    raise GeometryError(str(failure)) from failure
        elif args.accept_mate is not None:
            accepted_mate = confirm_cylindrical_mate(
                detected,
                mate_id=args.accept_mate,
                name=args.name,
                confirmed_by=args.confirmed_by,
            )
            if args.min_engagement is not None:
                try:
                    engagement_check = check_cylindrical_mate_engagement(
                        accepted_mate,
                        minimum_engagement=Quantity.parse(args.min_engagement),
                        reference=args.requirement,
                    )
                except ValueError as failure:
                    raise GeometryError(str(failure)) from failure
            if args.fit is not None:
                try:
                    basic_size = Quantity.parse(args.basic_size)
                    fit_check = check_cylindrical_mate_fit(
                        accepted_mate,
                        basic_size=basic_size,
                        designation=args.fit,
                    )
                except ValueError as failure:
                    raise GeometryError(str(failure)) from failure
        elif args.accept_gap is not None:
            accepted_gap = confirm_planar_gap(
                detected,
                gap_id=args.accept_gap,
                name=args.name,
                confirmed_by=args.confirmed_by,
            )
            if args.min_gap is not None:
                try:
                    gap_check = check_planar_gap_clearance(
                        accepted_gap,
                        minimum_gap=Quantity.parse(args.min_gap),
                        maximum_gap=Quantity.parse(args.max_gap),
                        reference=args.requirement,
                    )
                except ValueError as failure:
                    raise GeometryError(str(failure)) from failure
        assembly_scorecard = (
            None
            if detected.interference_scorecard is None
            else _assembly_interface_scorecard(
                detected,
                contact_check=contact_check,
                engagement_check=engagement_check,
                fit_check=fit_check,
                gap_check=gap_check,
            )
        )
    except GeometryUnavailable as failure:
        print(f"anvilate interfaces: {failure}", file=err)
        return EXIT_UNBUILT
    except GeometryError as failure:
        print(f"anvilate interfaces: {failure}", file=err)
        return EXIT_BAD_REQUEST
    result_code = EXIT_OK if assembly_scorecard is None else EXIT_CODES[assembly_scorecard.status]
    if args.format == "json":
        document = {
            "path": str(args.step),
            "candidates": detected.model_dump(mode="json", exclude_unset=True),
        }
        if accepted is not None:
            document["accepted"] = accepted.model_dump(mode="json", exclude_unset=True)
        if accepted_contact is not None:
            document["accepted_contact"] = accepted_contact.model_dump(mode="json")
        if contact_check is not None:
            document["contact_check"] = contact_check.model_dump(mode="json")
        if engagement_check is not None:
            document["engagement_check"] = engagement_check.model_dump(mode="json")
        if accepted_mate is not None:
            document["accepted_mate"] = accepted_mate.model_dump(mode="json")
        if accepted_gap is not None:
            document["accepted_gap"] = accepted_gap.model_dump(mode="json")
        if fit_check is not None:
            document["fit_check"] = fit_check.model_dump(mode="json")
        if gap_check is not None:
            document["gap_check"] = gap_check.model_dump(mode="json")
        if assembly_scorecard is not None:
            document["assembly_scorecard"] = assembly_scorecard.model_dump(mode="json")
        payload = machine_document("interfaces", document)
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
        return result_code

    print(f"{args.step}: {len(detected.planar_faces)} planar interface candidates", file=out)
    if detected.interference_scorecard is not None:
        interference_result = detected.interference_scorecard.status.value.upper()
        if (
            detected.interference_scorecard.status is CheckStatus.FAIL
            and assembly_scorecard is not None
            and assembly_scorecard.passed
        ):
            interference_result = "PASS after declared fit allowance"
        print(
            f"  assembly interference: {interference_result}",
            file=out,
        )
    if assembly_scorecard is not None:
        governing = assembly_scorecard.governing()
        governing_name = "none" if governing is None else governing.name
        print(
            f"  assembly scorecard: {assembly_scorecard.status.value.upper()}  "
            f"governing {governing_name}",
            file=out,
        )
    for solid in detected.solids:
        center = ", ".join(f"{value:g}" for value in solid.center_mm)
        minimum = ", ".join(f"{value:g}" for value in solid.bounds_min_mm)
        maximum = ", ".join(f"{value:g}" for value in solid.bounds_max_mm)
        print(
            f"  {solid.id}  volume {solid.volume_mm3:g} mm³  center ({center}) mm  "
            f"bounds ({minimum})–({maximum}) mm",
            file=out,
        )
    for contact in detected.planar_contacts:
        print(
            f"  {contact.id}  {contact.first_solid_id}/{contact.first_face_candidate_id} ↔ "
            f"{contact.second_solid_id}/{contact.second_face_candidate_id}  "
            f"overlap {contact.overlap_area_mm2:g} mm²",
            file=out,
        )
    for gap in detected.planar_gaps:
        print(
            f"  {gap.id}  {gap.first_solid_id}/{gap.first_face_candidate_id} ↔ "
            f"{gap.second_solid_id}/{gap.second_face_candidate_id}  "
            f"gap {gap.separation_mm:g} mm  projected overlap {gap.overlap_area_mm2:g} mm²",
            file=out,
        )
    for interference in detected.solid_interferences:
        center = ", ".join(f"{value:g}" for value in interference.center_mm)
        print(
            f"  {interference.id}  {interference.first_solid_id} ↔ "
            f"{interference.second_solid_id}  overlap {interference.overlap_volume_mm3:g} mm³  "
            f"center ({center}) mm",
            file=out,
        )
    for mate in detected.cylindrical_mates:
        print(
            f"  {mate.id}  bore {mate.bore_solid_id}/{mate.bore_surface_id} "
            f"⌀{mate.bore_diameter_mm:g} mm ↔ shaft "
            f"{mate.shaft_solid_id}/{mate.shaft_surface_id} ⌀{mate.shaft_diameter_mm:g} mm  "
            f"clearance {mate.diametral_clearance_mm:g} mm  "
            f"engagement {mate.axial_engagement_mm:g} mm",
            file=out,
        )
    for face in detected.planar_faces:
        solid = "" if face.solid_id is None else f"  solid {face.solid_id}"
        center = ", ".join(f"{value:g}" for value in face.center_mm)
        normal = ", ".join(f"{value:g}" for value in face.normal)
        measurements = f"area {face.area_mm2:g} mm²  center ({center}) mm  normal ({normal})"
        print(
            f"  {face.id}{solid}  {measurements}",
            file=out,
        )
        for pattern in face.hole_patterns:
            print(
                f"    {pattern.id}  {pattern.hole_count} × ⌀{pattern.hole_diameter_mm:g} mm "
                f"on ⌀{pattern.pitch_diameter_mm:g} mm pitch circle",
                file=out,
            )
        for feature in face.locating_features:
            through = (
                ""
                if feature.through_diameter_mm is None
                else f", through ⌀{feature.through_diameter_mm:g} mm"
            )
            print(
                f"    {feature.id}  {feature.kind} ⌀{feature.diameter_mm:g} mm × "
                f"{feature.axial_extent_mm:g} mm axial extent{through}",
                file=out,
            )
    for warning in detected.warnings:
        print(f"  note: {warning}", file=out)
    if accepted is not None:
        contract = accepted.contract
        print(
            f"  accepted: {contract.name} on {contract.mating_plane}, confirmed by "
            f"{accepted.confirmed_by}",
            file=out,
        )
    if accepted_contact is not None:
        contact_identity = f"{accepted_contact.name} ({accepted_contact.contact_candidate_id})"
        print(
            f"  accepted contact: {contact_identity}, confirmed by {accepted_contact.confirmed_by}",
            file=out,
        )
    if contact_check is not None:
        print(
            f"  contact-area requirement: {contact_check.status.upper()}  measured "
            f"{contact_check.confirmed_contact.overlap_area_mm2:g} mm²  minimum "
            f"{contact_check.minimum_overlap_area_mm2:g} mm²",
            file=out,
        )
    if accepted_mate is not None:
        mate_identity = f"{accepted_mate.name} ({accepted_mate.mate_candidate_id})"
        print(
            f"  accepted cylindrical mate: {mate_identity}, "
            f"confirmed by {accepted_mate.confirmed_by}",
            file=out,
        )
    if engagement_check is not None:
        print(
            f"  engagement requirement: {engagement_check.status.upper()}  measured "
            f"{engagement_check.confirmed_mate.axial_engagement_mm:g} mm  minimum "
            f"{engagement_check.minimum_axial_engagement_mm:g} mm",
            file=out,
        )
    if accepted_gap is not None:
        gap_identity = f"{accepted_gap.name} ({accepted_gap.gap_candidate_id})"
        print(
            f"  accepted planar gap: {gap_identity}, confirmed by {accepted_gap.confirmed_by}",
            file=out,
        )
    if fit_check is not None:
        print(
            f"  ISO 286 {fit_check.fit_designation}: {fit_check.status.upper()}  "
            f"hole {'PASS' if fit_check.hole.within_zone else 'FAIL'}  "
            f"shaft {'PASS' if fit_check.shaft.within_zone else 'FAIL'}",
            file=out,
        )
    if gap_check is not None:
        print(
            f"  gap requirement: {gap_check.status.upper()}  measured "
            f"{gap_check.confirmed_gap.separation_mm:g} mm  allowed "
            f"{gap_check.minimum_gap_mm:g}–{gap_check.maximum_gap_mm:g} mm",
            file=out,
        )
    return result_code


def _render_diff(document: dict[str, Any]) -> str:
    """The three sections, each present even when it has nothing in it.

    **The header names the files as well as the specs.** Two revisions of one spec is what
    `diff` is *for*, and a spec keeps its name across a revision — so the ordinary case
    printed `nema23_bracket → nema23_bracket` and said nothing about which two documents had
    been compared. The payload has carried `path` for both sides since it was published, for
    the same reason `check --format json` carries it: two specs sharing a name have to be
    distinguishable. Rendered unconditionally rather than only when the names collide,
    following the rule the rest of this function already follows — a section that is
    sometimes absent is a branch every reader has to make, and it is wrong the first time.
    """
    before, after = document["before"], document["after"]
    lines = [
        f"{before['name']} ({before['path']}) → {after['name']} ({after['path']})",
        "",
        "SPEC",
    ]
    lines.extend(f"  {line}" for line in document["spec"]["lines"] or ("no change",))

    verdict = document["verdict"]
    lines.extend(["", f"VERDICT  {verdict['before']} → {verdict['after']}", "", "CHECKS"])
    moved = []
    for entry in document["checks"]["moved"]:
        if entry["change"] == "removed":
            moved.append(f"  - {entry['name']}: removed (was {entry['before']})")
        elif entry["change"] == "added":
            moved.append(f"  + {entry['name']}: added ({entry['after']})")
        elif entry["change"] == "margin":
            margin = entry["margin"]
            moved.append(
                f"  ~ {entry['name']}: {entry['after']}, safety factor "
                f"{_margin_figure(margin['before'])} → {_margin_figure(margin['after'])}"
            )
            moved.append(f"      {entry['detail']}")
        else:
            moved.append(f"  ! {entry['name']}: {entry['before']} → {entry['after']}")
            if entry["margin"] is not None:
                moved[-1] += (
                    f", safety factor {_margin_figure(entry['margin']['before'])} → "
                    f"{_margin_figure(entry['margin']['after'])}"
                )
            moved.append(f"      {entry['detail']}")
    lines.extend(moved or ["  no verdict changed and no margin moved"])
    lines.append(f"  ({document['checks']['unchanged']} unchanged)")

    lines.extend(["", "GEOMETRY", f"  not compared: {document['geometry']['reason']}"])
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
    if args.envelope.suffix.lower() in {".step", ".stp"}:
        return _verify_step(args, out=out, err=err)

    from .attestation import Attestation, LocalHmacSigner, verify_attestation

    try:
        envelope = json.loads(args.envelope.read_text(encoding="utf-8"))
    except IsADirectoryError:
        print(f"anvilate verify: {_is_a_directory(args.envelope, command='verify')}", file=err)
        return EXIT_BAD_REQUEST
    except OSError as failure:
        print(f"anvilate verify: {failure}", file=err)
        return EXIT_BAD_REQUEST
    except UnicodeDecodeError as failure:
        # Before `json.JSONDecodeError`, because it is not one: the decode fails on the way
        # from bytes to text and never reaches the parser. An envelope arrives from somewhere
        # else, so this is the input most likely to be the wrong file entirely.
        print(f"anvilate verify: {_not_utf8(args.envelope, failure)}", file=err)
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
    if not isinstance(statement, dict):
        # And JSON that parses is not JSON shaped like a statement. `verify_attestation` was
        # hardened for exactly this and names the case in its own comment — a payload of
        # `[1,2,3]` comes back as "the envelope payload is a JSON list, not a statement
        # object" — and the shell then called `.get` on that list while *rendering* the
        # report, so the one input the library had already been taught about was the one
        # that answered with an AttributeError traceback. The guard above covered the
        # exception and not the value.
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
        payload = machine_document(
            "verify",
            {
                **report.model_dump(mode="json"),
                "status": report.status.value,
                "attested": report.attested,
                **_attested_toolchain(statement),
            },
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        print(_render_verification(report, statement), file=out)
    for problem in report.problems:
        print(f"anvilate verify: {problem}", file=err)
    return EXIT_CODES[report.status]


def _verify_step(args: argparse.Namespace, *, out, err) -> int:
    """Verify a received STEP solid against its embedded CAx-IF properties."""
    from .geometry import (
        GeometryError,
        GeometryUnavailable,
        read_step_validation_properties,
        verify_step_integrity,
    )

    if args.artifact or args.hmac_key_file is not None:
        print(
            "anvilate verify: --artifact and --hmac-key-file apply to DSSE envelopes, not STEP",
            file=err,
        )
        return EXIT_BAD_REQUEST
    properties = None
    problems = []
    try:
        properties = read_step_validation_properties(args.envelope)
        verify_step_integrity(args.envelope)
    except GeometryUnavailable as failure:
        print(f"anvilate verify: {failure}", file=err)
        return EXIT_UNBUILT
    except (GeometryError, OSError) as failure:
        problems.append(str(failure))

    status = "pass" if not problems else "fail"
    property_document = (
        {
            "volume_mm3": properties.volume_mm3,
            "surface_area_mm2": properties.surface_area_mm2,
            "centroid_mm": properties.centroid_mm,
        }
        if properties is not None
        else None
    )
    if args.format == "json":
        payload = machine_document(
            "verify",
            {
                "artifact": "step",
                "path": str(args.envelope),
                "status": status,
                "properties": property_document,
                "problems": problems,
            },
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        print(f"{status.upper()}  STEP integrity {args.envelope}", file=out)
        if properties is not None:
            centroid = ", ".join(f"{value:g}" for value in properties.centroid_mm)
            print(f"  volume       {properties.volume_mm3:g} mm³", file=out)
            print(f"  surface area {properties.surface_area_mm2:g} mm²", file=out)
            print(f"  centroid     ({centroid}) mm", file=out)
        for problem in problems:
            print(f"  problem      {problem}", file=out)
    for problem in problems:
        print(f"anvilate verify: {problem}", file=err)
    return EXIT_OK if status == "pass" else EXIT_FAILED


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

    **Everything the verdict is computed from is on the page.** `status` reads four fields —
    the signature state, the unchecked subjects, the signatures under keys this run did not
    hold, and the predicate keys this verifier does not read — and this rendering showed the
    first two. A bundle stating one unread key came back `NOT_EVALUATED` with every subject
    checked, nothing unchecked and no problem on stderr: a non-pass with nothing on the page
    saying why. `test_the_human_rendering_shows_everything_the_verdict_is_computed_from`
    moves each field and requires the rendering to move with it.

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
    for label, listed in (
        ("checked", report.checked_subjects),
        ("unchecked", report.unchecked_subjects),
        # The other two things that make a verdict NOT_EVALUATED, and neither reached this
        # rendering. A signed bundle stating one key this verifier does not read came back
        # `NOT_EVALUATED` with every subject checked, nothing unchecked and no problem on
        # stderr — a non-pass with nothing on the page saying why, which is the worst answer
        # a report can give. `report.status` reads four things; this printed two of them.
        ("unverified", report.unverified_signatures),
        ("unread", report.unread_predicate_keys),
    ):
        # All four always render. A run that checked nothing and one whose subjects all
        # matched must not look the same.
        lines.append(f"  {label:11} {', '.join(listed) or 'none'}")
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


def _qif(results, *, worst, fmt: str, out, err) -> int:
    """``export --artifact qif``: the same sections, in ISO 23952 rather than in the bundle.

    **The export gate applies here and it does not at the bundle.** `artifact-export` gates
    CAD artifacts on the acceptance checks passing, and a QIF results file is one — it is
    the document a quality system measures a part against. The evidence bundle is the
    evidence *including* the evidence that a part failed, which is why it is printed for any
    verdict; a characteristic list is a statement about a part that may be built from it.
    So a card that does not pass is refused here, in the gate's own words, and the exit code
    is the card's — the same code the same spec gets from the same command asking for the
    bundle, because the exit code is about the screening either way.

    There is no ``--override``. `authorize_export(card, override=True)` exists so that
    exporting past a failing card is a deliberate act by somebody who has read the card, and
    a flag on a CI-facing command is the opposite of that. Adding one is a decision to make
    with `artifact-export` open, not a convenience to fall into.
    """
    from .attestation import EnvironmentBOM, canonical_json, sha256_hex
    from .export.gate import ExportRefused, authorize_export
    from .export.qif import export_qif_results

    # One BOM for the run: it describes the environment that produced the documents, and
    # rebuilding it per spec would let two documents from one invocation disagree about it.
    bom = EnvironmentBOM.of_this_environment()
    documents: list[tuple[Path, Any, str]] = []
    for path, spec, sections in results:
        try:
            authorization = authorize_export(sections.scorecard)
        except ExportRefused as refused:
            # `ExportRefused` ends with "Pass override=True to export anyway", which is a
            # remedy for somebody holding the library and none at all for somebody holding a
            # shell — this command has no override, deliberately. So the refusal keeps the
            # part that says what is unmet and gains the part a caller here can act on.
            print(
                f"anvilate export --artifact qif: {path}: {refused}\n"
                f"anvilate export has no override: exporting past a failing card is a "
                f"deliberate act by somebody who has read it. "
                f"`--artifact evidence-bundle` is served whatever the verdict and carries "
                f"the failure.",
                file=err,
            )
            return EXIT_CODES[worst]
        documents.append(
            (
                path,
                spec,
                export_qif_results(
                    sections,
                    part_name=spec.name,
                    # The digest of the spec's own canonical JSON, not of the file's bytes:
                    # two YAML files that differ only in whitespace are the same revision,
                    # and the MCP surface holds the document rather than the file it came
                    # from. One definition, so the two surfaces cannot disagree.
                    spec_digest="sha256:"
                    + sha256_hex(canonical_json(spec.model_dump(mode="json")).encode("utf-8")),
                    bom=bom,
                    authorization=authorization,
                ),
            )
        )

    if fmt == "json":
        payload = machine_document(
            "export",
            {
                "status": worst.value,
                "documents": [
                    {
                        "path": str(path),
                        "name": spec.name,
                        "format": "qif",
                        "qif": document,
                        "sha256": sha256_hex(document.encode("utf-8")),
                    }
                    for path, spec, document in documents
                ],
            },
            artifact="qif",
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        for index, (path, _spec, document) in enumerate(documents):
            if index:
                print("", file=out)
            if len(documents) > 1:
                # An XML comment, because the run separator has to survive being redirected
                # into a file a QIF reader opens.
                print(f"<!-- {path} -->", file=out)
            print(document, end="" if document.endswith("\n") else "\n", file=out)
    return EXIT_CODES[worst]


def _dxf(results, *, worst, fmt: str, out, err) -> int:
    """Build and render validated plate profiles through the audited geometry registry."""
    from .attestation import sha256_hex
    from .export.dxf import render_geometry_dxf
    from .export.gate import ExportRefused, authorize_export
    from .geometry import GeometryError, GeometryUnavailable, UnsupportedGeometry, build_spec

    documents: list[tuple[Path, Any, bytes]] = []
    for path, spec, sections in results:
        try:
            authorization = authorize_export(sections.scorecard)
        except ExportRefused as refused:
            print(
                f"anvilate export --artifact dxf: {path}: {refused}\n"
                f"anvilate export has no override: exporting past a failing card is a "
                f"deliberate act by somebody who has read it. "
                f"`--artifact evidence-bundle` is served whatever the verdict and carries "
                f"the failure.",
                file=err,
            )
            return EXIT_CODES[worst]
        try:
            geometry = build_spec(spec)
            document = render_geometry_dxf(geometry=geometry, authorization=authorization)
        except ImportError as failure:
            print(f"anvilate export --artifact dxf: {path}: {failure}", file=err)
            return EXIT_UNBUILT
        except (GeometryUnavailable, UnsupportedGeometry) as failure:
            print(
                f"anvilate export --artifact dxf: {path}: {failure}. See {_GEOMETRY_SPEC}.",
                file=err,
            )
            return EXIT_UNBUILT
        except GeometryError as failure:
            print(f"anvilate export --artifact dxf: {path}: {failure}", file=err)
            return EXIT_BAD_REQUEST
        documents.append((path, spec, document))

    if fmt == "json":
        payload = machine_document(
            "export",
            {
                "status": worst.value,
                "documents": [
                    {
                        "path": str(path),
                        "name": spec.name,
                        "format": "dxf",
                        "dxf": document.decode("utf-8"),
                        "sha256": sha256_hex(document),
                    }
                    for path, spec, document in documents
                ],
            },
            artifact="dxf",
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        for index, (path, _spec, document) in enumerate(documents):
            if index:
                print("", file=out)
            if len(documents) > 1:
                print(f"999\n{path}", file=out)
            print(document.decode("utf-8"), end="", file=out)
    return EXIT_CODES[worst]


def _export(args: argparse.Namespace, *, out, err) -> int:
    """``export``, for the artifacts a spec file alone can produce."""
    from .bundle import BundleSections, combinations_for

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
    for index, path in enumerate(paths, start=1):
        if len(paths) > 1:
            _progress(err, f"assembling the bundle for {path}", done=index, total=len(paths))
        spec = _load(path, err=err, command="export")
        if isinstance(spec, int):
            return spec
        # The spec goes in the bundle, not only through it. `artifact-export`'s scenario is
        # a reviewer holding only this document and re-running the analysis, and until the
        # spec was carried they were holding verdicts with no inputs behind them.
        results.append(
            (
                path,
                spec,
                BundleSections(
                    scorecard=screen_spec(spec),
                    spec=spec,
                    # Where every number came from, which the bundle has had a place for
                    # since it was published and nothing filled in: `collect_provenance`
                    # takes its databases explicitly, so every caller it had was a test.
                    citations=provenance_for(spec),
                    # And the layer whose result was already on the card while the roll-up
                    # above it said the layer was not covered.
                    combinations=combinations_for(spec),
                ),
            )
        )

    # One roll-up, read by the exit code and by both renderings. `check` prints its
    # run-level verdict in each; this printed it in neither, so a CI job publishing bundles
    # for a repository got N blocks and had to find the worst by scanning them. The exit
    # code carried it, and a verdict only an exit code carries is one nobody reads in a log.
    worst = _worst_status(sections for _p, _s, sections in results)

    if args.artifact == "qif":
        return _qif(results, worst=worst, fmt=args.format, out=out, err=err)
    if args.artifact == "dxf":
        return _dxf(results, worst=worst, fmt=args.format, out=out, err=err)

    if args.format == "json":
        payload = machine_document(
            "export",
            {
                "status": worst.value,
                "bundles": [
                    {"path": str(path), "name": spec.name, "bundle": sections.to_document_dict()}
                    for path, spec, sections in results
                ],
            },
            artifact="evidence-bundle",
        )
        print(json.dumps(payload, indent=2, sort_keys=True), file=out)
    else:
        for index, (path, _spec, sections) in enumerate(results):
            if index:
                print("", file=out)
            if len(results) > 1:
                print(f"# {path}", file=out)
            print(sections.render_document(), file=out)
        if len(results) > 1:
            statuses = [sections.status for _p, _s, sections in results]
            print("\n" + _run_summary("bundles", statuses, worst), file=out)
    return EXIT_CODES[worst]


# The byte-order marks a text editor writes ahead of a non-UTF-8 save. Named because the
# remedy is the same for all of them and saying which one it is turns "invalid start byte"
# into a sentence about what the caller did.
_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "UTF-32 (little-endian)"),
    (b"\x00\x00\xfe\xff", "UTF-32 (big-endian)"),
    (b"\xff\xfe", "UTF-16 (little-endian)"),
    (b"\xfe\xff", "UTF-16 (big-endian)"),
)


def _candidates(directory: Path, *, err, command: str) -> list[Path] | int:
    """Every document under ``directory`` that could be a spec, or the code saying why not.

    This was ``rglob``, and ``rglob`` swallows the error from a directory it cannot look
    inside: a specs subdirectory the sweep had no permission to read yielded nothing, with no
    line anywhere in the output, and the run went green over every part in it. That is the
    worst version of the silent green this command exists to refuse — not a misdescription
    but silence — and it is invisible from the outside, because a directory that is empty and
    one that cannot be opened look identical in the result.

    So the walk is this function's own, and ``onerror`` is the whole reason for it: a
    directory the sweep could not enter is a bad request naming it, because the caller asked
    for every part under here and the answer would not be about all of them.
    """
    import os

    unreadable: list[str] = []

    def _cannot_enter(failure: OSError) -> None:
        unreadable.append(
            f"{failure.filename}: could not be searched "
            f"({failure.strerror or failure}), so the parts in it were not screened"
        )

    found: list[Path] = []
    # `followlinks` stays off, which is what `rglob` did: a `latest -> .` symlink inside a
    # specs directory is an ordinary thing to find and must not be walked into forever.
    for parent, _dirs, files in os.walk(directory, onerror=_cannot_enter):
        for name in files:
            if name.endswith((".yaml", ".yml", ".json")):
                found.append(Path(parent) / name)
    if unreadable:
        for problem in sorted(unreadable):
            print(f"anvilate {command}: {problem}", file=err)
        return EXIT_BAD_REQUEST
    return sorted(found)


def _is_a_spec(document: dict) -> bool:
    """Is a document found by searching a Design Spec?

    Two surfaces used to disagree about what one is. A file the caller *names* is a spec if
    :class:`~anvilate.spec.DesignSpec` validates it, and ``anvilate_spec`` is optional there
    on purpose — `spec-screening` calls it "a record, not an assertion", the version a
    document actually reached, so a document that declares none is a current one. The sweep
    recognised a spec by that key alone. So a spec written without it was screened when named
    and reported ``not a Design Spec, skipped`` when found, and ``anvilate check specs/`` —
    the merge-gate form — exited over a part nobody screened. The repository's own
    ``examples/padeye.spec.yaml``, the document the README tells a reader to run, is one.

    So the sweep asks the loader. The key is still enough on its own, because a document that
    claims to be a spec is treated as one whatever its state; validating is what recognises
    the rest. Nothing else is at risk of being mistaken for a spec: ``DesignSpec`` forbids
    unknown keys and requires five, so a CI config or a lockfile fails it. What remains, and
    is documented rather than papered over, is that a *broken* spec declaring no version is
    still indistinguishable from a stray file — declaring ``anvilate_spec`` is what makes a
    sweep's refusal unconditional.
    """
    if "anvilate_spec" in document:
        return True
    from .spec import parse_spec

    try:
        parse_spec(document)
    except Exception:
        # `except Exception`, not `SpecValidationError`: the question here is only whether
        # this file is somebody's part, and anything at all going wrong answers "no". A file
        # that *is* a spec and fails to load is the named-file case, and `_load` reports it
        # with every path in the document.
        return False
    return True


# The commands that take a directory and search it. Named in the refusal below, because the
# reason somebody hands a directory to `diff` is that they learned it works for `check`.
_SEARCHING_COMMANDS = ("check", "export")


def _is_a_directory(path: Path, *, command: str) -> str:
    """Why a directory is not the argument, and which command does take one.

    `[Errno 21] Is a directory: 'specs'` is true, names the path, and says nothing a caller
    can act on — least of all that they were not simply wrong to try, since ``check`` and
    ``export`` search a directory and this command does not. That asymmetry is the whole
    reason the mistake gets made, so the refusal states it.
    """
    searching = " and ".join(f"`anvilate {name}`" for name in _SEARCHING_COMMANDS)
    return (
        f"{path} is a directory, and {command} takes a file. {searching} are the commands "
        f"that search a directory for the specs in it."
    )


def _claims_a_spec(path: Path) -> bool:
    """Does an undecodable file still say ``anvilate_spec`` somewhere in its bytes?

    The directory sweep decides "somebody's broken spec" from "a stray file" on whether the
    document names the key, and a file that will not decode has no text to search. Decoding
    with ``errors="replace"`` would not answer it either: UTF-16 interleaves a NUL after
    every ASCII byte, so the token comes back as ``a?n?v?…`` and the substring never matches.
    So the token is encoded instead — the three encodings a text editor actually writes — and
    looked for in the raw bytes.
    """
    try:
        raw = path.read_bytes()
    except OSError:  # pragma: no cover - the read that raised got this far
        return False
    return any(
        "anvilate_spec".encode(encoding) in raw for encoding in ("utf-8", "utf-16-le", "utf-16-be")
    )


def _not_utf8(path: Path, failure: UnicodeDecodeError) -> str:
    """Why a file that opened cannot be read, and what to do about it.

    Every door here reads its input as UTF-8, and ``UnicodeDecodeError`` descends from
    ``ValueError`` rather than from ``OSError`` — so it fell through the ``except OSError``
    that guards the open and reached the top as a traceback with exit 1, the code that means
    a part *failed*. The commonest way to arrive at one is not a hostile file: it is a spec
    saved as "Unicode" from Notepad, which writes UTF-16 with a byte-order mark. So when the
    first bytes are a mark, this says which encoding wrote it and what to re-save it as, and
    otherwise it reports the offending byte and its offset.
    """
    try:
        head = path.read_bytes()[:4]
    except OSError:  # pragma: no cover - the read that raised got this far
        head = b""
    for mark, encoding in _BOMS:
        if head.startswith(mark):
            return (
                f"{path}: is {encoding}, not UTF-8 — every document this tool reads is "
                f"UTF-8. Re-save it as UTF-8 (in Notepad, 'UTF-8' rather than 'Unicode')."
            )
    return (
        f"{path}: is not valid UTF-8 text — byte {failure.object[failure.start]:#04x} at "
        f"offset {failure.start} cannot be decoded. Every document this tool reads is UTF-8; "
        f"if this is a binary file, it is not the file you meant to name."
    )


def _load(path: Path, *, err, command: str):
    """The spec at ``path``, or the exit code that says why not.

    Shared by every command that takes a spec file, so a second one cannot report a missing
    file differently from the first.
    """
    from .spec import SpecValidationError, load_spec_yaml

    try:
        document = path.read_text(encoding="utf-8")
    except IsADirectoryError:
        print(f"anvilate {command}: {_is_a_directory(path, command=command)}", file=err)
        return EXIT_BAD_REQUEST
    except OSError as failure:
        print(f"anvilate {command}: {failure}", file=err)
        return EXIT_BAD_REQUEST
    except UnicodeDecodeError as failure:
        print(f"anvilate {command}: {_not_utf8(path, failure)}", file=err)
        return EXIT_BAD_REQUEST
    try:
        return load_spec_yaml(document)
    except SpecValidationError as failure:
        # Every path, not the first one: a script author fixing a spec one error per run is
        # the experience this avoids, and the paths are what the loader already produced.
        for problem in failure.errors:
            print(f"anvilate {command}: {_refusal_line(problem['loc'], problem['msg'])}", file=err)
        return EXIT_BAD_REQUEST
    except (ValueError, TypeError, KeyError) as failure:
        print(f"anvilate {command}: {failure}", file=err)
        return EXIT_BAD_REQUEST


def _build(args: argparse.Namespace, *, out, err) -> int:
    """Build one supported Design Spec pattern and write a valid STEP solid."""
    import hashlib

    from .geometry import (
        GeometryError,
        GeometryUnavailable,
        UnsupportedGeometry,
        build_spec,
        write_step,
    )

    if args.output.suffix.lower() not in {".step", ".stp"}:
        print("anvilate build: --output must end in .step or .stp", file=err)
        return EXIT_BAD_REQUEST
    if not args.output.parent.is_dir():
        print(f"anvilate build: output directory does not exist: {args.output.parent}", file=err)
        return EXIT_BAD_REQUEST
    if args.output.exists() and not args.force:
        print(
            f"anvilate build: output already exists: {args.output}; pass --force to replace it",
            file=err,
        )
        return EXIT_BAD_REQUEST

    spec = _load(args.spec, err=err, command="build")
    if isinstance(spec, int):
        return spec
    # One build, so no count: the line names what is running rather than a percentage the
    # kernel cannot report.
    _progress(err, f"building geometry for {args.spec}")
    try:
        built = build_spec(spec)
    except (GeometryUnavailable, UnsupportedGeometry) as failure:
        print(f"anvilate build: {failure}. See {_GEOMETRY_SPEC}.", file=err)
        return EXIT_UNBUILT
    except GeometryError as failure:
        print(f"anvilate build: {failure}", file=err)
        return EXIT_BAD_REQUEST

    from .export.gate import ExportRefused, authorize_export
    from .screening import screen_spec

    card = screen_spec(spec)
    try:
        authorization = authorize_export(card, override=args.unvalidated)
    except ExportRefused as refused:
        print(
            f"anvilate build: {refused}\n"
            "Pass --unvalidated only after reviewing the scorecard; the STEP will be "
            "watermarked and is not released for fabrication.",
            file=err,
        )
        return EXIT_CODES[card.status]
    except ValueError as failure:
        print(f"anvilate build: {failure}. Remove --unvalidated.", file=err)
        return EXIT_BAD_REQUEST

    try:
        step_schema: Literal["ap242", "ap214"] = "ap214" if args.ap214 else "ap242"
        write_step(built, args.output, authorization=authorization, schema=step_schema)
        digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    except OSError as failure:
        print(f"anvilate build: {failure}", file=err)
        return EXIT_BAD_REQUEST

    result = {
        "name": spec.name,
        "source": str(args.spec),
        "artifact": {
            "path": str(args.output),
            "format": "step",
            "sha256": digest,
            "pattern": built.pattern,
            "volume_mm3": built.volume_mm3,
            "dimensions_mm": dict(built.dimensions_mm),
            "face_tags": sorted(built.faces),
            "authorization": authorization.status.lower(),
        },
    }
    if args.format == "json":
        print(json.dumps(machine_document("build", result), indent=2, sort_keys=True), file=out)
    else:
        print(f"{spec.name}: BUILT", file=out)
        print(f"  STEP          {args.output}", file=out)
        print(f"  schema        {step_schema.upper()}", file=out)
        print(f"  pattern       {built.pattern}", file=out)
        print(f"  volume        {built.volume_mm3:g} mm³", file=out)
        print(f"  semantic faces {', '.join(sorted(built.faces))}", file=out)
        print(f"  authorization  {authorization.status}", file=out)
        print(f"  sha256        {digest}", file=out)
    return EXIT_OK


def _mode_summary(card: Scorecard, spec) -> dict[str, Any]:
    """The failure-mode coverage as `_cli_output.ModeSummary` describes it."""
    report = mode_coverage(card, facts_from_spec(spec))
    return {
        "catalog_size": report.catalog_size,
        "applicable": report.applicable,
        "caveats": [CATALOG_IS_A_FLOOR, UNDECLARABLE_FACTS],
        "modes": [
            {
                "id": entry.mode.id,
                "stage": entry.mode.stage.value,
                "citation": entry.mode.citation,
                "checks": list(entry.checks),
                "tests": list(entry.tests),
                "state": (
                    "addressed"
                    if entry.addressed
                    else ("left_to_a_test" if entry.planned else "unaddressed")
                ),
            }
            for entry in report.entries
        ],
    }


def _needs_summary(card: Scorecard) -> dict[str, Any]:
    """The consolidated needs report as `_cli_output.NeedsSummary` describes it."""
    report = needs_report(card)
    not_evaluated, out_of_depth = card.completeness()
    return {
        "not_evaluated": not_evaluated,
        "out_of_depth": out_of_depth,
        "ordering": LEVERAGE_IS_NOT_IMPORTANCE,
        "items": [
            {
                "declaration": item.need.declaration,
                "takes": item.need.takes,
                "dimension": item.need.dimension,
                "units": list(item.need.units),
                "sources": [source.value for source in item.need.sources],
                "leverage": item.leverage,
                "unblocks": list(item.unblocks),
            }
            for item in report.items
        ],
    }


def _margin_summary(spec, card: Scorecard) -> dict[str, Any]:
    """The declared margins as `_cli_output.MarginSummary` describes them."""
    ledger = ledger_for(card, spec)
    return {
        "entries": [entry.model_dump(mode="json") for entry in ledger.entries],
        "stacks": [
            {
                "quantity": stack.quantity,
                "cumulative": stack.cumulative,
                "physics_limited": stack.physics_limited,
                "elected": stack.elected,
                "multiplication": stack.multiplication(),
                "dominant": [entry.label for entry in stack.dominant()],
            }
            for stack in ledger.stacks()
        ],
        "double_counts": [
            {
                "quantity": double.quantity,
                "kind": double.kind.value,
                "combined": double.combined,
                "origins": sorted({entry.origin for entry in double.entries}),
            }
            for double in ledger.double_counts()
        ],
    }


def _is_terminal(stream: object) -> bool:
    """Whether ``stream`` is an interactive terminal; a file, a pipe or a buffer is not."""
    isatty = getattr(stream, "isatty", None)
    return bool(isatty()) if callable(isatty) else False


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

    # Progress on stderr, and only for a person watching: a directory of specs can take
    # long enough to look hung, and stdout must stay the result alone so it still pipes.
    results = []
    durations: list[float] = []
    for index, path in enumerate(paths, start=1):
        started = time.monotonic()
        if len(paths) > 1:
            _progress(
                err,
                f"screening {path}{_estimate(durations, len(paths) - index + 1)}",
                done=index,
                total=len(paths),
            )
        try:
            spec = _load(path, err=err, command="check")
            if isinstance(spec, int):
                return spec
            results.append((path, spec, screen_spec(spec)))
            durations.append(time.monotonic() - started)
        except KeyboardInterrupt:
            raise _Cancelled(
                f"{len(results)} of {len(paths)} spec{'s' if len(paths) != 1 else ''} screened"
            ) from None

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
        payload = machine_document(
            "check",
            {
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
                        "margins": _margin_summary(spec, card),
                        "needs": _needs_summary(card),
                        "failure_modes": _mode_summary(card, spec),
                    }
                    for path, spec, card in results
                ],
            },
        )
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
            print(
                _render(
                    heading,
                    card,
                    show_work=args.show_work,
                    system=spec.units.value if spec.units else None,
                    spec=spec,
                ),
                file=out,
            )
            # Only when the spec declares margins: the quickstart's card is byte-for-byte what
            # the README shows, and a spec that states no conservatism has no ledger to print.
            # The JSON payload carries the empty summary either way.
            if spec.constraints.margins:
                ledger = ledger_for(card, spec)
                print("\n" + str(ledger), file=out)
                for result in physics_limited(card, ledger):
                    print(f"  {result}", file=out)
        if len(results) > 1:
            worst = _worst_status(card for _p, _s, card in results)
            statuses = [card.status for _p, _s, card in results]
            print("\n" + _run_summary("specs", statuses, worst), file=out)

    # Every blocking check on stderr, which is what the requirement asks for and what a CI
    # log actually shows. A check that could not run is listed too, labelled as such: it
    # blocks exactly as hard and calling it a failure would be a different claim.
    from .report import ReportSection

    for path, spec, card in results:
        system = spec.units.value if spec.units else None
        for entry in card.entries:
            if entry.status in (CheckStatus.FAIL, CheckStatus.WARNING, CheckStatus.NOT_EVALUATED):
                # The spec's units here too. This line is what a CI log shows, and it is
                # the one place a failing check is reported to somebody who never opens the
                # card — so it printing millimetres for a US document is the same defect
                # with the widest reach.
                verdict = ReportSection(entry=entry).verdict(system=system)
                print(
                    f"anvilate check: {path}: {entry.status.value}: {entry.name} — {verdict}",
                    file=err,
                )
    return max(
        (EXIT_CODES[card.status] for _p, _s, card in results),
        key=_EXIT_SEVERITY.index,
    )


def _resolve(paths: list[Path], *, err, command: str = "check") -> list[Path] | int:
    """The spec documents behind the arguments, in a stable order.

    A directory is searched; a file named on the command line is taken at its word. The
    difference matters: a document *found* by searching that is not a Design Spec is some
    other YAML file and is skipped — reported, never silently — while one the caller *named*
    is an error, because they said it was a spec and it is not. :func:`_is_a_spec` is what
    that recognition rests on, and it used to be the ``anvilate_spec`` key alone.
    """
    import yaml

    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            candidates = _candidates(path, err=err, command=command)
            if isinstance(candidates, int):
                return candidates
            for candidate in candidates:
                try:
                    text = candidate.read_text(encoding="utf-8")
                except OSError as failure:
                    # Not "not a Design Spec": the sweep does not know what this file is, and
                    # saying it is something else is the misdescription the YAML case above
                    # settled. A `*.yaml` the tool cannot open is either somebody's part or a
                    # broken symlink where one used to be, and `text = ""` reported both as
                    # a stray file and let the run exit 0 over a part nobody screened — with
                    # a spec that *declares* `anvilate_spec` among them, since the byte probe
                    # cannot read an unreadable file either.
                    print(
                        f"anvilate {command}: {candidate}: could not be read "
                        f"({failure.strerror or failure}), so it was not screened",
                        file=err,
                    )
                    return EXIT_BAD_REQUEST
                except UnicodeDecodeError:
                    # A candidate that is not UTF-8 text gets the same treatment as one that
                    # will not parse, and for the same reason: whether it is somebody's spec
                    # or a stray file is decided on whether it *claims* to be one, and the
                    # claim is still legible in the raw bytes even when the text is not.
                    # `text = ""` alone would report a UTF-16 spec — what Notepad writes when
                    # asked for "Unicode" — as "not a Design Spec, skipped", and the sweep
                    # would exit 0 over a part nobody screened.
                    if _claims_a_spec(candidate):
                        print(
                            f"anvilate {command}: {candidate}: names anvilate_spec and is "
                            f"not valid UTF-8 text, so it was not screened",
                            file=err,
                        )
                        return EXIT_BAD_REQUEST
                    text = ""
                try:
                    document = yaml.safe_load(text)
                except yaml.YAMLError:
                    # A file that will not parse cannot be told apart from "some other YAML
                    # file" by its keys, because parsing is what reveals them — but its raw
                    # text still can. One that *says* `anvilate_spec` and will not parse is
                    # somebody's broken spec, and skipping it with "not a Design Spec" both
                    # misdescribes it and lets a repository sweep pass over a part nobody
                    # screened. That is the silent green this tool exists to refuse, so it
                    # is a bad request naming the file. A malformed YAML file that claims
                    # nothing is still just a stray file, and is still skipped.
                    if "anvilate_spec" in text:
                        print(
                            f"anvilate {command}: {candidate}: names anvilate_spec and is "
                            f"not valid YAML, so it was not screened",
                            file=err,
                        )
                        return EXIT_BAD_REQUEST
                    document = None
                if isinstance(document, dict) and _is_a_spec(document):
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


def _render(
    name: str,
    card: Scorecard,
    *,
    show_work: bool = False,
    system: UnitSystem | None = None,
    spec=None,
) -> str:
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

    ``system`` is the spec's own declared unit system, and it was not read. A document
    saying `units: US` had every worked calculation and every comparison printed back to it
    in millimetres and megapascals — the tool ignoring the one line of the document that
    says what the reader works in.
    """
    from .report import ReportSection

    lines = [f"{name}: {card.status.value.upper()}"]
    for entry in card.entries:
        lines.append(f"  {entry.status.value:<14} {entry.name}")
        # Through the report's own renderer, so a comparison verdict is restated in the
        # spec's units rather than the ones it was screened in.
        verdict = ReportSection(entry=entry).verdict(system=system)
        if verdict:
            lines.append(f"                 {verdict}")
        # The clause is what separates this from a spreadsheet, and the shell dropped it.
        # `ScorecardEntry.__str__` has always appended it; this renderer builds its own lines
        # and printed the detail alone, so every cited check read as an uncited one.
        if entry.reference:
            lines.append(f"                 [{entry.reference}]")
        # A verdict at "1.00 required" whose margin sits inside the capacity reads as no
        # margin at all unless the factor is printed beside it.
        inside = entry.inside_capacity()
        if inside:
            lines.append(f"                 {inside}")
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
            worked = section.worked_lines(system=system)
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
    # Completeness beside the verdict, stated in both directions. A reader's question is not
    # only what passed but what nobody looked at, and a card that says nothing about its
    # unevaluated checks reads as complete whether it is or not — so the zero is printed too.
    blocked, deferred = card.not_evaluated(), card.out_of_depth()
    lines.append(f"  not evaluated: {len(blocked)}")
    # Its own line, never folded into the one above: a check the engineer deferred and one
    # that could not run are different facts, and one "incomplete" number would let a
    # reader act on the wrong one.
    lines.append(f"  out of depth:  {len(deferred)}")
    if spec is not None:
        modes = mode_coverage(card, facts_from_spec(spec))
        if modes.entries:
            # Only when a mode applies: the caveats belong beside a finding, and a card that
            # reaches none of the catalogue would otherwise carry two paragraphs saying so.
            lines.extend(f"  {line}" for line in str(modes).splitlines())
    report = needs_report(card)
    if len(report):
        # Indented under the card and with no blank line before it: a run over a directory
        # separates one spec's block from the next with a blank line, and a blank line
        # inside a block would make the needs list read as a spec of its own.
        lines.extend(f"  {line}" for line in str(report).splitlines())
    elif blocked:
        # The counts disagree with the report, and saying so is the honest end of it: these
        # checks could not run and none of them stated a declaration that would let them.
        lines.append(f"                 {len(blocked)} could not run and none states what it needs")
    return "\n".join(lines)


def _run_summary(noun: str, statuses: list[CheckStatus], worst: CheckStatus) -> str:
    """The one line a reader takes away from a multi-spec run, with its counts.

    `Scorecard.__str__` already argues this one level down: "a reader who sees
    `scorecard FAIL (2 checks)` knows something failed and not which check to fix". The run
    summary had the same shape — `60 specs: FAIL` over a run where 58 passed reads as a run
    that failed wholesale, and a reviewer scanning a CI log cannot tell two broken parts
    from sixty.

    The blocking counts are named only when non-zero, like the card's, so an all-passing run
    stays short. The `N specs: WORST` prefix is unchanged, because it is what the page
    documents and what a log filter greps for.
    """
    tally = Counter(statuses)
    parts = []
    for status, word in (
        (CheckStatus.FAIL, "failed"),
        (CheckStatus.NOT_EVALUATED, "not evaluated"),
        (CheckStatus.WARNING, "warning"),
        (CheckStatus.OVER_MARGIN, "over margin"),
    ):
        if tally[status]:
            parts.append(f"{tally[status]} {word}")
    if tally[CheckStatus.PASS]:
        parts.append(f"{tally[CheckStatus.PASS]} passed")
    counts = f" — {', '.join(parts)}" if parts else ""
    return f"{len(statuses)} {noun}: {worst.value.upper()}{counts}"


def _worst_status(cards):
    """The blocking-worst status over a run, which both renderings report.

    One function rather than two, because the text summary and the JSON payload disagreeing
    about the verdict of the same run is the defect that having two of them invites.
    """
    return max((card.status for card in cards), key=_BLOCKING_ORDER.index)


# What a character this library prints becomes on a stream that cannot encode it — a dumb
# terminal, `LANG=C`, a CI log opened as ASCII. Spellings a reader understands, not `?`: a
# clause sign read as "Sec." still sends them to the clause.
_ASCII_SPELLINGS = {
    "§": "Sec.",
    "→": "->",
    "←": "<-",
    "≤": "<=",
    "≥": ">=",
    "≠": "!=",
    "±": "+/-",
    "×": "x",
    "·": "*",
    "−": "-",
    "–": "-",
    "—": "--",
    "µ": "u",
    "μ": "u",
    "°": " deg",
    "²": "^2",
    "³": "^3",
    "√": "sqrt",
    "π": "pi",
    "Δ": "delta ",
    "…": "...",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
}


def _ascii_spelling(error: UnicodeError) -> tuple[str, int]:
    """Transliterate what the stream cannot encode, falling back to `?` for the rest."""
    assert isinstance(error, UnicodeEncodeError)
    text = error.object[error.start : error.end]
    return "".join(_ASCII_SPELLINGS.get(char, "?") for char in text), error.end


def _json_escape(error: UnicodeError) -> tuple[str, int]:
    """Escape what the stream cannot encode as JSON does, so the document is unchanged."""
    assert isinstance(error, UnicodeEncodeError)
    text = error.object[error.start : error.end]
    escaped = "".join(
        f"\\u{ord(char):04x}"
        if ord(char) < 0x10000
        else "".join(f"\\u{unit:04x}" for unit in _surrogates(ord(char)))
        for char in text
    )
    return escaped, error.end


def _surrogates(code: int) -> tuple[int, int]:
    code -= 0x10000
    return 0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)


codecs.register_error("anvilate-ascii", _ascii_spelling)
codecs.register_error("anvilate-json", _json_escape)


def _degrade_gracefully(json_requested: bool) -> None:
    """Keep the real streams writable when they cannot encode what the library prints.

    Only characters the stream cannot encode are touched: a UTF-8 terminal sees exactly what
    it always did. JSON gets `\\u` escapes, which leave the document it describes unchanged;
    text gets ASCII spellings a reader can follow.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            handler = (
                "anvilate-json" if json_requested and stream is sys.stdout else "anvilate-ascii"
            )
            stream.reconfigure(errors=handler)


class _Wrapped(io.TextIOBase):
    """A text stream that wraps each line it is given to ``width`` columns.

    Continuation lines are indented under the line they continue, words are never broken, and
    a line already within the width passes through untouched. Only a terminal gets one: a
    pipe or a file receives exactly the lines the command wrote.
    """

    def __init__(self, target: TextIO, width: int) -> None:
        self._target = target
        self._width = width
        self._pending = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._pending += text
        *lines, self._pending = self._pending.split("\n")
        for line in lines:
            self._target.write(self._wrap(line) + "\n")
        return len(text)

    def flush(self) -> None:
        if self._pending:
            self._target.write(self._wrap(self._pending))
            self._pending = ""
        self._target.flush()

    def _wrap(self, line: str) -> str:
        if len(line) <= self._width:
            return line
        indent = line[: len(line) - len(line.lstrip())]
        return textwrap.fill(
            line.strip(),
            width=self._width,
            initial_indent=indent,
            subsequent_indent=indent + "    ",
            break_long_words=False,
            break_on_hyphens=False,
        )


def _for_the_terminal(stream: TextIO, json_requested: bool) -> TextIO:
    """``stream`` wrapped to the terminal's width when a person is reading text on it."""
    if json_requested or not _is_terminal(stream):
        return stream
    width = shutil.get_terminal_size(fallback=(100, 24)).columns
    return _Wrapped(stream, max(width, 40))  # type: ignore[return-value]


def main() -> None:
    """The ``anvilate`` console script."""
    json_requested = _wants_json(sys.argv[1:])
    _degrade_gracefully(json_requested)
    out = _for_the_terminal(sys.stdout, json_requested)
    try:
        code = run(stdout=out)
    finally:
        out.flush()
    raise SystemExit(code)


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in the tests
    main()
