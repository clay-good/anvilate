"""The headless command line: ``anvilate check``, and the three commands it refuses.

`headless-automation` requires the CLI to expose every pipeline capability — "at minimum
``anvilate build``, ``anvilate check``, ``anvilate export``, ``anvilate diff`` — operating on
spec files and producing the same artifacts, scorecards, and **exit codes** deterministically".
Until this module there was no ``anvilate`` command at all; the only console script was the
MCP server.

**Two of the four are backed today**, and a fifth command the attestation capability names
is backed as well. ``check`` compiles a spec document and screens it,
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
    "diff": (
        "diff compares two builds and reports mass, dimension and verdict deltas; two "
        "builds is what it does not have. See openspec/specs/geometry-generation."
    ),
}

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
    parser = _Parser(
        prog="anvilate",
        description="Screen a Design Spec without a UI. Exit code 0 only when every "
        "check passed; 2 means the card could not be evaluated, which is not a pass.",
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
        "check", help="compile a spec document and screen it, printing the scorecard"
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
    verify = commands.add_parser(
        "verify", help="verify an attestation envelope and report what was checked"
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

    export = commands.add_parser("export", help="write a downstream artifact from a screened spec")
    export.add_argument("spec", type=Path, help="a Design Spec document, YAML or JSON")
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
        commands.add_parser(name, help=f"specified, unbuilt — {reason.split('.')[0]}")
    return parser


def run(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
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
    return _check(args, out=out, err=err)


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
    if args.format == "json":
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True), file=out)
    else:
        print(_render_verification(report, attestation.statement()), file=out)
    for problem in report.problems:
        print(f"anvilate verify: {problem}", file=err)
    return EXIT_CODES[report.status]


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
    bom = (statement.get("predicate") or {}).get("bom") or {}
    components = bom.get("components") or []
    metadata = (bom.get("metadata") or {}).get("component") or {}
    if metadata:
        lines.append(f"  produced by {metadata.get('name')} {metadata.get('version')}")
    # Always rendered, `none` included: a bundle attesting no toolchain and one whose
    # toolchain nobody printed must not read the same.
    listed = ", ".join(
        f"{component.get('name')} {component.get('version')}" for component in components
    )
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
    loaded = _load(args.spec, err=err, command="export")
    if isinstance(loaded, int):
        return loaded
    from .screening import screen_spec

    sections = BundleSections(scorecard=screen_spec(loaded))
    if args.format == "json":
        print(json.dumps(sections.to_json_dict(), indent=2, sort_keys=True), file=out)
    else:
        print(sections.render(), file=out)
    return EXIT_CODES[sections.status]


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
        payload = {
            "specs": [
                {
                    "path": str(path),
                    "name": spec.name,
                    "scorecard": card.model_dump(mode="json"),
                }
                for path, spec, card in results
            ]
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
            print(_render(heading, card), file=out)
        if len(results) > 1:
            worst = max((card.status for _p, _s, card in results), key=_BLOCKING_ORDER.index)
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


def _resolve(paths: list[Path], *, err) -> list[Path] | int:
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
                    print(f"anvilate check: {candidate}: not a Design Spec, skipped", file=err)
            continue
        found.append(path)
    if not found:
        print(
            "anvilate check: no Design Spec found in " + ", ".join(str(p) for p in paths), file=err
        )
        return EXIT_BAD_REQUEST
    return found


def _render(name: str, card: Scorecard) -> str:
    lines = [f"{name}: {card.status.value.upper()}"]
    for entry in card.entries:
        lines.append(f"  {entry.status.value:<14} {entry.name}")
        if entry.detail:
            lines.append(f"                 {entry.detail}")
    return "\n".join(lines)


def main() -> None:
    """The ``anvilate`` console script."""
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in the tests
    main()
