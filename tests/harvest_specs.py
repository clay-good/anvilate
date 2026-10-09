"""Regenerate `tests/spec_corpus.jsonl`: every distinct Design Spec the suite screens.

A pytest plugin, not a test. It wraps `screening.screen_spec`, so it records exactly the
documents the suite's own fixtures build, including the optional blocks the six examples
leave out. The patch makes a few identity-checking tests fail during the harvest; that is
expected, since the run collects documents rather than checking anything.

    rm tests/spec_corpus.jsonl
    HARVEST_OUT=tests/spec_corpus.jsonl PYTHONPATH=src:tests python -m pytest -q \\
        -p no:cacheprovider -p harvest_specs tests/test_screening.py tests/test_spec.py \\
        tests/test_cli.py tests/test_surface_parity.py tests/test_bundle.py tests/test_mcp.py
"""

from __future__ import annotations

import json
import os

import anvilate.screening as screening

_OUT = os.environ.get("HARVEST_OUT")
_screen_spec = screening.screen_spec
_seen: set[str] = set()


def _recording(spec, *args, **kwargs):
    document = json.dumps(spec.model_dump(mode="json", exclude_none=True), sort_keys=True)
    if _OUT and document not in _seen:
        _seen.add(document)
        with open(_OUT, "a", encoding="utf-8") as corpus:
            corpus.write(document + "\n")
    return _screen_spec(spec, *args, **kwargs)


if _OUT:
    screening.screen_spec = _recording
