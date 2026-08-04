"""Worked example: a rectangular torsion bar's peak stress, and why a flat bar loses twice.

A round shaft carries torsion with the clean τ = T·r/J, but a rectangular bar does not — the peak
shear sits at the middle of its long side, and the strength follows the Roark fit
τ_max = T·(3a + 1.8b)/(a²·b²). This example carries 200 N·m through two equal-area steel bars: a
compact 31.6 mm square and a wide 100 × 10 mm flat bar. The square is the better torsion member on
both counts a designer cares about — it develops about 30 MPa of shear and twists a degree, while
the flat bar, spreading the same metal into a thin strip that Saint-Venant torsion barely resists,
runs to roughly 64 MPa (twice the stress) and twists more than four degrees (over four times as
much).
Torsion punishes wide, thin sections in strength as well as stiffness, which is why torsion members
want to be compact or, better, closed tubes.

Run it directly (``python examples/rectangular_torsion_bar_stress.py``);
:func:`bar_stresses` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rectangular_bar_torsional_stress, rectangular_bar_twist_angle
from anvilate.units import Quantity

TORQUE = Quantity.parse("200 N*m")
LENGTH = Quantity.parse("1 m")
SHEAR_MODULUS = Quantity.parse("80 GPa")
SECTIONS = {
    "square_31.6mm": (Quantity.parse("31.62 mm"), Quantity.parse("31.62 mm")),
    "flat_100x10mm": (Quantity.parse("100 mm"), Quantity.parse("10 mm")),
}


def bar_stresses() -> dict[str, dict[str, float]]:
    """Return the peak shear stress (MPa) and twist (deg) of each equal-area bar."""
    out: dict[str, dict[str, float]] = {}
    for name, (width, thickness) in SECTIONS.items():
        stress = rectangular_bar_torsional_stress(torque=TORQUE, width=width, thickness=thickness)
        twist = rectangular_bar_twist_angle(
            torque=TORQUE,
            length=LENGTH,
            width=width,
            thickness=thickness,
            shear_modulus=SHEAR_MODULUS,
        )
        out[name] = {
            "stress_mpa": stress.to("MPa").magnitude,
            "twist_deg": twist.to("degree").magnitude,
        }
    return out


def main() -> None:
    b = bar_stresses()
    for name in ("square_31.6mm", "flat_100x10mm"):
        s = b[name]
        print(f"{name:16s}: peak shear {s['stress_mpa']:.0f} MPa, twist {s['twist_deg']:.1f}°")
    print(
        "  -> equal area, but the flat bar carries twice the stress and over four times the twist"
    )


if __name__ == "__main__":
    main()
