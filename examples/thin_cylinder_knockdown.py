"""Worked example: a thin aluminium tank wall buckles at a third of its classical stress.

A launch-vehicle propellant tank wall, 1.6 m in radius and 3.2 mm thick (r/t = 500), is
2219-T87 aluminium (E = 73.8 GPa, ν = 0.33). The classical axial buckling stress of that
wall is 90.3 MPa. It is not the answer: real cylinders buckle on dimples a fraction of the
wall thick, and NASA SP-8007's knockdown at r/t = 500 is γ = 0.322, so the design buckling
stress is 29.0 MPa. In bending the knockdown is milder, γ = 0.450, for 40.6 MPa at the
compressive fibre.

Halving the wall to 1.6 mm (r/t = 1000) halves the classical stress and also lowers γ to
0.224, so the design stress falls to 10.1 MPa, about a third of the thicker wall's rather
than the half the classical formula suggests. The knockdown is a lower bound to tests from
the 1930s to the 1960s, not a statistical basis; a real program also checks column
buckling of the whole tank.

Run it directly (``python examples/thin_cylinder_knockdown.py``);
:func:`thin_cylinder_knockdown` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CylinderLoading,
    cylinder_axial_buckling_stress,
    cylinder_design_buckling_stress,
    sp8007_knockdown_factor,
)
from anvilate.units import Quantity

MODULUS = Quantity(magnitude=73.8, unit="GPa")
POISSON = 0.33
RADIUS = Quantity(magnitude=1600.0, unit="mm")


def _wall(thickness_mm: float, loading: CylinderLoading) -> float:
    return (
        cylinder_design_buckling_stress(
            elastic_modulus=MODULUS,
            wall_thickness=Quantity(magnitude=thickness_mm, unit="mm"),
            mean_radius=RADIUS,
            poisson=POISSON,
            loading=loading,
        )
        .to("MPa")
        .magnitude
    )


def thin_cylinder_knockdown() -> dict[str, float]:
    """Return the classical and knocked-down stresses for the 3.2 mm and 1.6 mm walls."""
    axial, bending = CylinderLoading.AXIAL_COMPRESSION, CylinderLoading.BENDING
    classical = cylinder_axial_buckling_stress(
        elastic_modulus=MODULUS,
        wall_thickness=Quantity(magnitude=3.2, unit="mm"),
        mean_radius=RADIUS,
        poisson=POISSON,
    )
    return {
        "classical_mpa": classical.to("MPa").magnitude,
        "gamma": sp8007_knockdown_factor(radius_to_thickness=500, loading=axial),
        "design_mpa": _wall(3.2, axial),
        "gamma_bending": sp8007_knockdown_factor(radius_to_thickness=500, loading=bending),
        "design_bending_mpa": _wall(3.2, bending),
        "gamma_thin": sp8007_knockdown_factor(radius_to_thickness=1000, loading=axial),
        "design_thin_mpa": _wall(1.6, axial),
    }


def main() -> None:
    d = thin_cylinder_knockdown()
    print(f"classical: {d['classical_mpa']:.1f} MPa")
    print(f"SP-8007 axial: gamma {d['gamma']:.3f}, {d['design_mpa']:.1f} MPa")
    print(f"SP-8007 bending: gamma {d['gamma_bending']:.3f}, {d['design_bending_mpa']:.1f} MPa")
    print(f"half the wall: gamma {d['gamma_thin']:.3f}, {d['design_thin_mpa']:.1f} MPa")


if __name__ == "__main__":
    main()
