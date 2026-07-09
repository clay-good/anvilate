"""Worked example: can the chosen process actually hold this tolerance?

A design-for-manufacturing screen with no LLM: an engineer draws a bearing bore
and calls out a ±0.01 mm tolerance (a 0.02 mm total band), intending to 3D-print
the part on an FDM machine. FDM's finest achievable band is ~0.20 mm, so the
call-out is an order of magnitude tighter than the process can hold — a silent
scrap-parts trap that only surfaces on the shop floor.

:func:`screen_manufacturability` flags that mismatch up front and, because a flag
alone is not actionable, lists the processes that *can* hold the band (finest-
capable first) so the engineer can either open up the tolerance or move the part
to a tighter process.

Run it directly (``python examples/dfm_process_check.py``); :func:`screen_manufacturability`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.tolerance.process import (
    processes_that_can_hold,
    tolerance_is_achievable,
)
from anvilate.units import Quantity

CHOSEN_PROCESS = "fdm"
DEMANDED_BAND = Quantity.parse("0.02 mm")  # a ±0.01 mm bearing-bore call-out


def screen_manufacturability() -> dict[str, object]:
    """Screen the demanded tolerance against the chosen process, with alternatives."""
    check = tolerance_is_achievable(CHOSEN_PROCESS, DEMANDED_BAND)
    # Only bother suggesting alternatives when the chosen process can't hold it.
    alternatives = [] if check.achievable else processes_that_can_hold(DEMANDED_BAND)
    return {"check": check, "alternatives": alternatives}


def main() -> None:
    result = screen_manufacturability()
    print(result["check"])
    if result["alternatives"]:
        print("processes that can hold it: " + ", ".join(result["alternatives"]))


if __name__ == "__main__":
    main()
