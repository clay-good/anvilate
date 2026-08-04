"""Worked example: why a unidirectional carbon ply is stiff one way and soft the other.

A single carbon-fiber/epoxy ply is not one material but two working together, and how
they share the load depends on the direction. Along the fibers (60% by volume, 230 GPa
carbon in 3.5 GPa epoxy) the two phases stretch together and the stiffness is the
volume-weighted average — about 139 GPa, nearly a structural-steel value at a quarter of
the weight. Across the fibers they carry the load in series through the soft matrix, and
the inverse rule drops the modulus to about 9 GPa — a 16:1 anisotropy. That gap is the
whole reason real laminates stack plies at several angles instead of trusting one
direction.

The example composes the rule-of-mixtures longitudinal modulus and strength with the
inverse-rule transverse modulus for a 60% carbon/epoxy ply.

Run it directly (``python examples/cfrp_ply_anisotropy.py``);
:func:`ply_properties` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    rule_of_mixtures_modulus,
    rule_of_mixtures_strength,
    transverse_modulus_inverse_rule,
)
from anvilate.units import Quantity

FIBER_FRACTION = 0.60
FIBER_MODULUS = Quantity.parse("230 GPa")  # carbon fiber
MATRIX_MODULUS = Quantity.parse("3.5 GPa")  # epoxy
FIBER_STRENGTH = Quantity.parse("4000 MPa")  # carbon fiber tensile
MATRIX_STRESS_AT_FIBER_FAILURE = Quantity.parse("70 MPa")  # epoxy at fiber failure strain


def ply_properties() -> dict[str, float]:
    """Return the longitudinal modulus, transverse modulus, and longitudinal strength (MPa)."""
    e1 = rule_of_mixtures_modulus(
        fiber_fraction=FIBER_FRACTION,
        fiber_modulus=FIBER_MODULUS,
        matrix_modulus=MATRIX_MODULUS,
    )
    e2 = transverse_modulus_inverse_rule(
        fiber_fraction=FIBER_FRACTION,
        fiber_modulus=FIBER_MODULUS,
        matrix_modulus=MATRIX_MODULUS,
    )
    strength = rule_of_mixtures_strength(
        fiber_fraction=FIBER_FRACTION,
        fiber_strength=FIBER_STRENGTH,
        matrix_stress_at_fiber_failure=MATRIX_STRESS_AT_FIBER_FAILURE,
    )
    return {
        "longitudinal_modulus_mpa": e1.to("MPa").magnitude,
        "transverse_modulus_mpa": e2.to("MPa").magnitude,
        "longitudinal_strength_mpa": strength.to("MPa").magnitude,
    }


def main() -> None:
    p = ply_properties()
    e1 = p["longitudinal_modulus_mpa"] / 1000
    e2 = p["transverse_modulus_mpa"] / 1000
    print(f"longitudinal modulus E1 : {e1:.0f} GPa")
    print(f"transverse modulus   E2 : {e2:.1f} GPa  ({e1 / e2:.0f}:1 anisotropy)")
    print(f"longitudinal strength   : {p['longitudinal_strength_mpa']:.0f} MPa")


if __name__ == "__main__":
    main()
