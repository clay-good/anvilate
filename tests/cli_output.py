"""Run the CLI as a test does, holding every JSON document it prints to the published schema.

Checking output against `docs/api/schemas/cli-output.schema.json` was something a test opted
into, so the schema was held only for the commands and inputs somebody thought to check.
`build --format json` printed a timber beam's pattern the schema refused while five tests of
build JSON passed, each on another pattern. Every runner that asks for `--format json` goes
through here instead, and the schema is checked for whatever the test happened to run.
"""

from __future__ import annotations

import io
import json
from functools import cache
from pathlib import Path

from anvilate.cli import run

_SCHEMA = Path(__file__).resolve().parents[1] / "docs/api/schemas/cli-output.schema.json"


@cache
def _published():
    import jsonschema

    return jsonschema.Draft202012Validator(json.loads(_SCHEMA.read_text(encoding="utf-8")))


def run_cli(*argv: str) -> tuple[int, str, str]:
    """``(exit code, stdout, stderr)``; a JSON stdout that breaks the schema fails the test."""
    out, err = io.StringIO(), io.StringIO()
    code = run(list(argv), stdout=out, stderr=err)
    if "json" in argv and argv[argv.index("json") - 1] == "--format" and out.getvalue():
        from jsonschema.exceptions import best_match

        # The output is a union, so the top error is "not valid under any"; the best match
        # names the field inside the branch that came closest.
        problem = best_match(_published().iter_errors(json.loads(out.getvalue())))
        assert problem is None, (
            f"{argv[0]} --format json broke cli-output at "
            f"{'/'.join(map(str, problem.absolute_path))}: {problem.message[:200]}"
        )
    return code, out.getvalue(), err.getvalue()
