"""Worked example: a quasi-isotropic carbon laminate cracks its 90° plies first.

A [0/45/-45/90]s laminate looks the same in every direction, and it is tempting to size it
on its fibres. Pulled along x, the 0° plies carry most of the load, but the 90° plies
stretch with them, across their own fibres, where the ply is weakest. Classical lamination
theory puts the strain at every depth and each ply's stiffness turns it into stress.

At 100 N/mm the 90° plies sit at 16.88 MPa across their fibres against a 50 MPa
transverse strength. First-ply failure comes at a strength ratio of 2.70, by
maximum strain in the 90° plies. The 0° plies would not reach their fibre strength until a
ratio of 7.73, so the matrix cracks first, at about a third of the load the fibres
would take. Maximum strain governs rather than maximum stress because the 90° ply's
transverse strain carries the Poisson contraction its neighbours impose. Whether a
cracked-but-intact laminate is acceptable is a program decision; the screen reports the
first ply, the criterion and the basis.

The ply strengths here are illustrative values for a carbon/epoxy tape, declared on a
B basis for the example. They are not allowables; a real screen uses the qualified
material's own.

Run it directly (``python examples/laminate_first_ply_failure.py``);
:func:`laminate_first_ply_failure` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import Lamina, Ply, first_ply_failure, laminate_response
from anvilate.units import Quantity


def _mpa(value: float) -> Quantity:
    return Quantity(magnitude=value, unit="MPa")


TAPE = Lamina(
    longitudinal_modulus=Quantity(magnitude=140.0, unit="GPa"),
    transverse_modulus=Quantity(magnitude=10.0, unit="GPa"),
    shear_modulus=Quantity(magnitude=5.0, unit="GPa"),
    major_poisson_ratio=0.3,
    thickness=Quantity(magnitude=0.125, unit="mm"),
    longitudinal_tensile_strength=_mpa(2000.0),
    longitudinal_compressive_strength=_mpa(1500.0),
    transverse_tensile_strength=_mpa(50.0),
    transverse_compressive_strength=_mpa(200.0),
    shear_strength=_mpa(80.0),
    strength_basis="B (illustrative)",
)
LAYUP = (0.0, 45.0, -45.0, 90.0, 90.0, -45.0, 45.0, 0.0)
RUNNING_LOAD = Quantity(magnitude=100.0, unit="N/mm")


def laminate_first_ply_failure() -> dict[str, float | str]:
    """Return the 90° ply's transverse stress, the first-ply ratio, and the fibre ratio."""
    zero = Quantity(magnitude=0.0, unit="N/mm")
    response = laminate_response(
        [Ply(lamina=TAPE, angle=angle) for angle in LAYUP],
        running_load=[RUNNING_LOAD, zero, zero],
    )
    result = first_ply_failure(response)
    ninety = next(p for p in response.plies if p.angle == 90.0)
    fibre = min(
        f.max_stress for f in result.plies if f.angle == 0.0 and f.max_stress_mode == "fibre"
    )
    return {
        "transverse_stress_mpa": ninety.stress_12[1] / 1e6,
        "first_ply_ratio": result.strength_ratio or 0.0,
        "criterion": f"{result.governing_criterion} ({result.governing_mode})",
        "fibre_ratio": fibre,
    }


def main() -> None:
    d = laminate_first_ply_failure()
    print(f"90-degree ply transverse stress at 100 N/mm: {d['transverse_stress_mpa']:.2f} MPa")
    print(f"first-ply failure ratio: {d['first_ply_ratio']:.2f} by {d['criterion']}")
    print(f"0-degree fibre failure ratio: {d['fibre_ratio']:.2f}")


if __name__ == "__main__":
    main()
