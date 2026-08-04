"""Worked example: the COP that flatters an easy duty, and the number that doesn't.

A chiller's coefficient of performance sounds like a report card, but it is a misleading one: COP
falls as the temperature lift grows even for a flawless machine, so a chiller doing an easy,
low-lift job posts a high COP while a better machine on a hard, high-lift job posts a lower one. The
number that actually grades the *machine* — independent of how hard its duty is — is the second-law
efficiency, the COP divided by the Carnot ceiling for the same reservoirs.

This example compares two chillers. The first has a modest COP of 4.0 but on a gentle lift where
Carnot allows 10.0 — a second-law efficiency of just 0.40. The second posts a lower COP of 3.2,
which looks worse, but it works a steep lift where Carnot allows only 5.8, so its second-law
efficiency is 0.55 — the better machine, wringing more out of a harder job. Ranked by COP the first
chiller wins; ranked by second-law efficiency, the order flips. The lesson is that COP measures the
duty and the machine tangled together, while the second-law efficiency pulls the machine out on its
own, the fair way to compare two units that are not doing the same job.

Run it directly (``python examples/chiller_second_law_efficiency.py``);
:func:`chiller_grades` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import second_law_efficiency

EASY_COP = 4.0
EASY_CARNOT = 10.0
HARD_COP = 3.2
HARD_CARNOT = 5.8


def chiller_grades() -> dict[str, float]:
    """Return the second-law efficiency of an easy-duty and a hard-duty chiller."""
    return {
        "easy_cop": EASY_COP,
        "easy_eta2": second_law_efficiency(actual_cop=EASY_COP, carnot_cop=EASY_CARNOT),
        "hard_cop": HARD_COP,
        "hard_eta2": second_law_efficiency(actual_cop=HARD_COP, carnot_cop=HARD_CARNOT),
    }


def main() -> None:
    g = chiller_grades()
    print(f"easy-duty chiller : COP {g['easy_cop']:.1f}, second-law eff {g['easy_eta2']:.2f}")
    print(f"hard-duty chiller : COP {g['hard_cop']:.1f}, second-law eff {g['hard_eta2']:.2f}")
    cop_winner = "easy" if g["easy_cop"] > g["hard_cop"] else "hard"
    eta_winner = "easy" if g["easy_eta2"] > g["hard_eta2"] else "hard"
    print(f"  -> COP ranks the {cop_winner}-duty unit first, second-law eff the {eta_winner} one")


if __name__ == "__main__":
    main()
