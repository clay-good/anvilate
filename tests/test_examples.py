"""Execute the bundled examples so they stay green in CI (a runnable quickstart)."""

from __future__ import annotations

import runpy
from pathlib import Path

from anvilate.scorecard import CheckStatus

_EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_cantilever_bracket_example_screens_to_a_failing_scorecard():
    # run_path executes the module without triggering its __main__ block.
    namespace = runpy.run_path(str(_EXAMPLES / "cantilever_bracket_check.py"))
    card = namespace["screen_cantilever_bracket"]()
    # The aluminum bracket passes yield but fails deflection -> overall FAIL.
    assert card.status is CheckStatus.FAIL
    by_name = {e.name: e for e in card.entries}
    assert by_name["bending yield"].status is CheckStatus.PASS
    assert by_name["tip deflection"].status is CheckStatus.FAIL
