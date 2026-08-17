"""Worked example: a surface flaw in a vessel shell, from detection to a FAD margin.

An inspection finds a 4 mm deep, 40 mm long surface flaw in a 20 mm pressure-vessel
shell. The question is not "is K below K_mat" — that is only half of it. A flawed
component fails by brittle fracture at one extreme and by plastic collapse of the
remaining ligament at the other, and near the middle it fails by an interaction that
neither limit predicts on its own. The failure assessment diagram is how the two are
combined: K_r = K_I/K_mat up the axis, L_r = sigma_ref/sigma_y along it, one curve
separating acceptable from not.

Three cases, same flaw:

* **Measured toughness, service load.** K_r 0.367, L_r 0.556 against a curve height of
  0.920 — inside, with a load-line margin of 1.71. Note that margin is *not*
  1/K_r = 2.73: riding the load line out raises L_r as well, and the curve has come down
  by the time you get there. That gap is the whole reason to use a FAD rather than a
  toughness check.
* **The same flaw at an overpressure.** The point walks out along the same ray and
  crosses: margin 0.79, FAIL.
* **The same flaw with a Charpy-correlated toughness.** Identical numbers, and the
  scorecard refuses to call it a pass — the correlation scatters by enough that a pass
  built on it is a reason to commission a toughness test, not a result.

What this produces is a **screening margin**, not a fitness-for-service disposition.
Deciding a flawed component may stay in service is a qualified assessor's call under the
full assessment code, with the residual stresses, weld metal properties and inspection
uncertainty this screen does not have.

Run it directly (``python examples/vessel_surface_flaw_fad.py``);
:func:`screen_shell_flaw` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    SurfaceFlaw,
    charpy_toughness_estimate,
    fad_assessment,
    fad_scorecard,
    newman_raju_surface_flaw_sif,
    surface_flaw_reference_stress,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

FLAW = SurfaceFlaw(
    depth=Quantity.parse("4 mm"),
    half_length=Quantity.parse("20 mm"),
    thickness=Quantity.parse("20 mm"),
    half_width=Quantity.parse("500 mm"),
)
YIELD = Quantity.parse("350 MPa")
ULTIMATE = Quantity.parse("500 MPa")
MODULUS = Quantity.parse("207000 MPa")
TOUGHNESS = Quantity.parse("60 MPa*m**0.5")  # measured K_IC, from a test certificate
SERVICE_HOOP = Quantity.parse("175 MPa")
OVERPRESSURE_HOOP = Quantity.parse("380 MPa")


def _assess(hoop: Quantity, toughness: Quantity, *, estimate: bool):
    k = newman_raju_surface_flaw_sif(flaw=FLAW, membrane_stress=hoop)
    reference = surface_flaw_reference_stress(flaw=FLAW, membrane_stress=hoop)
    return fad_assessment(
        stress_intensity=k,
        fracture_toughness=toughness,
        reference_stress=reference,
        yield_strength=YIELD,
        ultimate_strength=ULTIMATE,
        elastic_modulus=MODULUS,
        toughness_is_estimate=estimate,
    )


def _entry(name: str, hoop: Quantity, toughness: Quantity, *, estimate: bool) -> ScorecardEntry:
    return fad_scorecard(name, assessment=_assess(hoop, toughness, estimate=estimate))


def screen_shell_flaw() -> Scorecard:
    """The same flaw three ways: at service, at overpressure, and on a Charpy estimate."""
    charpy = charpy_toughness_estimate(
        charpy_energy=Quantity.parse("40 foot_pound"), yield_strength=YIELD
    )
    return Scorecard(
        entries=[
            _entry("service pressure, measured K_IC", SERVICE_HOOP, TOUGHNESS, estimate=False),
            _entry("overpressure, measured K_IC", OVERPRESSURE_HOOP, TOUGHNESS, estimate=False),
            _entry("service pressure, Charpy estimate", SERVICE_HOOP, charpy, estimate=True),
        ]
    )


def main() -> None:
    print("20 mm shell, 4 mm x 40 mm surface flaw — FAD screening (not a disposition)")
    for entry in screen_shell_flaw().entries:
        factor = "  —  " if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
        print(f"  {entry.name:<36} {entry.status.value:<14} margin {factor}")
    point = _assess(SERVICE_HOOP, TOUGHNESS, estimate=False)
    print(
        f"\n  at service: K_r {point.fracture_ratio:.3f}, L_r {point.load_ratio:.3f}, "
        f"curve {point.acceptable_fracture_ratio:.3f}, cutoff {point.limit_load_ratio:.3f}"
    )
    print(
        f"  load-line margin {point.load_line_margin:.2f} — not 1/K_r = "
        f"{1 / point.fracture_ratio:.2f}, because L_r rides out with it"
    )


if __name__ == "__main__":
    main()
