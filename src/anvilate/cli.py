"""The headless command line: ``anvilate check``, and the three commands it refuses.

`headless-automation` requires the CLI to expose every pipeline capability — "at minimum
``anvilate build``, ``anvilate check``, ``anvilate export``, ``anvilate diff`` — operating on
spec files and producing the same artifacts, scorecards, and **exit codes** deterministically".
Until this module there was no ``anvilate`` command at all; the only console script was the
MCP server.

**One of the four is backed today and it is the one shipped.** ``check`` compiles a spec
document and screens it, which is exactly the path :func:`anvilate.screening.screen_spec`
already serves over MCP. ``build``, ``export`` and ``diff`` all need a built part — a
geometry kernel that is not in this package — so each is refused *by name, with the reason*
rather than left as an unknown command. A CLI that answers "unknown command: build" tells a
script author they typed it wrong; the honest answer is that the operation is specified,
unbuilt, and here is what it is waiting on.

## The exit codes are the interface

A script reads the exit code, not the text. So the code follows the scorecard's own rule
rather than collapsing to pass/fail:

===  ===========================================================================
0    every check passed
1    a check failed
2    the card could not be fully evaluated — **not a pass**, and not a failure
3    the request was wrong: a missing file, a document that is not a valid spec
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

# What each unbuilt command is waiting on. Named individually because "not implemented" is
# not an answer a script author can act on, and because the three are waiting on the same
# thing for three different reasons.
_UNBUILT = {
    "build": (
        "build runs the part's generating program, which needs a geometry kernel this "
        "package does not ship. See openspec/specs/geometry-generation."
    ),
    "export": (
        "export writes a downstream artifact from a built part. The export gate and the "
        "writers exist (anvilate.export), but there is no built part to hand them from a "
        "spec file alone. See openspec/specs/geometry-generation."
    ),
    "diff": (
        "diff compares two builds and reports mass, dimension and verdict deltas; two "
        "builds is what it does not have. See openspec/specs/geometry-generation."
    ),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anvilate",
        description="Screen a Design Spec without a UI. Exit code 0 only when every "
        "check passed; 2 means the card could not be evaluated, which is not a pass.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser(
        "check", help="compile a spec document and screen it, printing the scorecard"
    )
    check.add_argument("spec", type=Path, help="a Design Spec document, YAML or JSON")
    check.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="text for a person, json for a script that wants the whole card",
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

    return _check(args, out=out, err=err)


def _check(args: argparse.Namespace, *, out, err) -> int:
    from .screening import screen_spec
    from .spec import SpecValidationError, load_spec_yaml

    try:
        document = args.spec.read_text(encoding="utf-8")
    except OSError as failure:
        print(f"anvilate check: {failure}", file=err)
        return EXIT_BAD_REQUEST
    try:
        spec = load_spec_yaml(document)
    except SpecValidationError as failure:
        # Every path, not the first one: a script author fixing a spec one error per run is
        # the experience this avoids, and the paths are what the loader already produced.
        for problem in failure.errors:
            print(f"anvilate check: {problem['loc']}: {problem['msg']}", file=err)
        return EXIT_BAD_REQUEST
    except (ValueError, TypeError, KeyError) as failure:
        print(f"anvilate check: {failure}", file=err)
        return EXIT_BAD_REQUEST

    card = screen_spec(spec)
    if args.format == "json":
        print(json.dumps(card.model_dump(mode="json"), indent=2, sort_keys=True), file=out)
    else:
        print(_render(spec.name, card), file=out)
    return EXIT_CODES[card.status]


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
