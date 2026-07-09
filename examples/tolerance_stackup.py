"""Worked example: will these parts assemble? A 1D tolerance stack-up.

The question a stack-up answers: given the tolerance on every dimension in a
chain, does the assembly gap stay within what the design needs? Here a motor
mounts to a bracket through three stacked features — a mount face (+), a flange
thickness (−), and a pilot seat (−) — leaving a nominal 0.3 mm clearance. The
design needs at least 0.25 mm of clearance (so the seat never binds) and no more
than 0.50 mm.

Three analyses answer it with increasing realism, all deterministic and LLM-free:
worst-case (every tolerance at its limit at once — the guarantee), root-sum-square
(the statistically likely spread), and a Monte Carlo run that predicts the actual
assembly yield — the fraction of parts that will fall in the required band. This
is the classic result that makes statistical tolerancing worth doing: worst-case
rejects the design (its 0.20 mm floor breaks the 0.25 mm minimum), yet almost
every real assembly clears it.

Run it directly (``python examples/tolerance_stackup.py``); :func:`analyze_gap`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.tolerance import StackContributor, StackUp, SymmetricTolerance
from anvilate.units import Quantity

# The required clearance band the assembly must land in.
GAP_MIN = Quantity.parse("0.25 mm")
GAP_MAX = Quantity.parse("0.50 mm")


def _contributor(name: str, nominal: str, plus_minus: str, direction: int) -> StackContributor:
    """A symmetric ± dimension resolved onto a stack contributor."""
    resolved = SymmetricTolerance(plus_minus=Quantity.parse(plus_minus)).resolve(
        Quantity.parse(nominal)
    )
    return StackContributor(name=name, tolerance=resolved, direction=direction)


def _stack() -> StackUp:
    return StackUp(
        contributors=(
            _contributor("mount face", "20 mm", "0.05 mm", direction=1),
            _contributor("flange thickness", "12 mm", "0.03 mm", direction=-1),
            _contributor("pilot seat", "7.7 mm", "0.02 mm", direction=-1),
        )
    )


def analyze_gap() -> dict[str, object]:
    """Analyze the interface gap three ways and predict the assembly yield."""
    stack = _stack()
    worst_case = stack.worst_case()
    rss = stack.rss()
    monte_carlo = stack.monte_carlo(20000, seed=1234)
    return {
        "worst_case": worst_case,
        "rss": rss,
        "monte_carlo": monte_carlo,
        "worst_case_ok": worst_case.satisfies(GAP_MIN, GAP_MAX),
        "predicted_yield": monte_carlo.yield_fraction(GAP_MIN, GAP_MAX),
    }


def main() -> None:
    r = analyze_gap()
    print(r["worst_case"])
    print(r["rss"])
    print(r["monte_carlo"])
    print(f"worst-case fits {GAP_MIN}..{GAP_MAX}: {r['worst_case_ok']}")
    print(f"predicted assembly yield: {r['predicted_yield'] * 100:.2f}%")


if __name__ == "__main__":
    main()
