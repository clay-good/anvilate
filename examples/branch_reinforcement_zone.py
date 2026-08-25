"""Worked example: a branch's reinforcement zone is set by both pipes, not by the run.

An NPS 16 header with a 3/4" weldolet, screened to ASME B31.3 §304.3.3. Cutting the hole
takes pressure-carrying metal out of the run, and the Code wants it back inside a zone
2·d2 wide and L4 tall. Both limits are a "whichever is smaller/larger" **and both mix the
run with the branch**, which is where the accounting is fumbled by hand:

* **L4 is the lesser** of 2.5(T_h − c) and 2.5(T_b − c) + T_r. Taking the run's term
  alone — the obvious reading, since the zone sits on the run — credits a thin branch
  with the run's zone height. Here that is 10.45 mm against the correct 6.275 mm, and A3
  comes out 67% larger than the branch actually earns — a 37.03 mm² available area
  read as 55.90, against a required 81.95 that neither of them meets.
* **d2 is the greater** of d1 and (T_b − c) + (T_h − c) + d1/2. Taking d1 alone
  under-credits a thick-walled small branch, which is conservative but can fail a branch
  that passes.

A reinforcing pad raises L4, so it adds A3 as well as its own A4 — and stops adding once
the run's 2.5(T_h − c) cap binds. That is shown too: a 20 mm pad takes L4 from 6.275 mm to
the run's cap of 10.45 mm and no further.

A4 is taken as declared. The Code credits only metal inside the zone, and an area alone
does not say where the metal is, so the function cannot check it and does not pretend to.

Run it directly (``python examples/branch_reinforcement_zone.py``);
:func:`weldolet`, :func:`padded_weldolet` and :func:`naive_branch_credit` are exercised
in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    BranchReinforcement,
    asme_b313_branch_reinforcement,
    asme_b313_branch_reinforcement_scorecard,
)
from anvilate.scorecard import ScorecardEntry
from anvilate.units import Quantity

# An NPS 16 Schedule 10S header with a 3/4" branch, both Alloy 625, 5.17 MPa at 38 °C.
HEADER = {
    "run_outside_diameter": Quantity.parse("406.40 mm"),
    "run_wall": Quantity.parse("4.18 mm"),
    "run_pressure_design_thickness": Quantity.parse("3.78 mm"),
}
BRANCH = {
    "branch_outside_diameter": Quantity.parse("26.7 mm"),
    "branch_wall": Quantity.parse("2.51 mm"),
    "branch_pressure_design_thickness": Quantity.parse("0.25 mm"),
}
NO_ALLOWANCE = {"mechanical_allowance": Quantity.parse("0 mm")}


def weldolet() -> BranchReinforcement:
    """The bare branch, no pad: the run's excess wall and the branch's, and nothing else."""
    return asme_b313_branch_reinforcement(**HEADER, **BRANCH, **NO_ALLOWANCE)


def padded_weldolet() -> BranchReinforcement:
    """The same branch with a 20 mm pad, which lengthens the branch's zone as well."""
    return asme_b313_branch_reinforcement(
        **HEADER, **BRANCH, **NO_ALLOWANCE, pad_thickness=Quantity.parse("20 mm")
    )


def naive_branch_credit() -> float:
    """A3 as it comes out if L4 is read as 2.5(T_h − c) — the run's term alone, in mm²."""
    run_term = 2.5 * (4.18 - 0.0)
    return 2.0 * run_term * (2.51 - 0.25 - 0.0)


def verdict() -> ScorecardEntry:
    return asme_b313_branch_reinforcement_scorecard(
        "weldolet reinforcement", reinforcement=weldolet()
    )


def main() -> None:
    bare = weldolet()
    print("NPS 16 Sch 10S header, 3/4in weldolet, B31.3 §304.3.3")
    print(f"  zone:      2 x d2 = {2 * bare.half_width.magnitude:.2f} mm wide, ", end="")
    print(f"L4 = {bare.height.magnitude:.2f} mm tall")
    print(f"  required:  A1 = {bare.required.magnitude:.2f} mm²")
    print(f"  available: A2 = {bare.run_excess.magnitude:.2f}, ", end="")
    print(f"A3 = {bare.branch_excess.magnitude:.2f}, A4 = {bare.added.magnitude:.2f}")
    print(f"  verdict:   {verdict()}")

    naive = naive_branch_credit()
    print("\nreading L4 as the run's term alone (2.5(T_h - c)), which it is not:")
    print(f"  L4 {2.5 * 4.18:.2f} mm instead of {bare.height.magnitude:.2f} mm")
    print(
        f"  A3 {naive:.2f} mm² instead of {bare.branch_excess.magnitude:.2f} mm² — "
        f"{naive / bare.branch_excess.magnitude - 1:.0%} more area than the branch earns"
    )

    padded = padded_weldolet()
    print("\nwith a 20 mm reinforcing pad:")
    print(
        f"  L4 rises to {padded.height.magnitude:.2f} mm (the run's cap), "
        f"so A3 rises to {padded.branch_excess.magnitude:.2f} mm² before any A4 is counted"
    )


if __name__ == "__main__":
    main()
