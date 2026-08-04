"""Worked example: why a press brake overbends, and why spring steel fights back harder than mild.

When a press brake releases a bent part, the elastic part of the deformation recovers and the bend
springs open — the radius grows and the angle opens toward flat. A part formed to a crisp 90° comes
off the tool a degree or two more, so to land on 90° the brake has to *overbend* by the springback.
How much depends on the material: springback scales with the ratio of yield strength to elastic
modulus (Y/E), the elastic strain the outer fibre stored, so a resilient high-strength alloy springs
back far more than soft mild steel of the same gauge.

This example bends the same section — a 4 mm inner radius in 2 mm sheet, formed to 90° — in two
materials. Mild steel (250 MPa yield) barely moves: its springback factor is about 0.99, the radius
relaxes from 4.0 to 4.03 mm, and the 90° bend opens to about 89.5°, a mere half-degree the brake
absorbs almost without thinking. Spring-tempered steel (1200 MPa yield) is a different animal: the
same bend springs to a 0.965 factor, the radius opens to 4.14 mm, and the angle relaxes to about
87.5° — so the brake must overbend by roughly 2.5° to hit 90°, five times the mild-steel correction.
The example computes the sprung radius and angle for both so the overbend the tool needs is clear.
The lesson is that springback is a material property as much as a geometry one: the same die and the
same nominal bend need different overbend for different alloys, which is why press-brake programs
carry a springback correction per material, not a single fixed angle.

Run it directly (``python examples/press_brake_springback.py``);
:func:`springback_by_material` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import springback_factor, sprung_bend_angle, sprung_bend_radius
from anvilate.units import Quantity

INNER_RADIUS = Quantity.parse("4 mm")
THICKNESS = Quantity.parse("2 mm")
FORMED_ANGLE = 90.0  # degrees the tool bends through


def _material(yield_strength: str, elastic_modulus: str) -> dict[str, float]:
    ks = springback_factor(
        initial_bend_radius=INNER_RADIUS,
        yield_strength=Quantity.parse(yield_strength),
        elastic_modulus=Quantity.parse(elastic_modulus),
        thickness=THICKNESS,
    )
    rf = sprung_bend_radius(initial_bend_radius=INNER_RADIUS, springback_factor=ks)
    theta_f = sprung_bend_angle(
        initial_bend_angle=FORMED_ANGLE,
        initial_bend_radius=INNER_RADIUS,
        sprung_bend_radius=rf,
        thickness=THICKNESS,
    )
    return {
        "springback_factor": ks,
        "sprung_radius_mm": rf.to("mm").magnitude,
        "sprung_angle_deg": theta_f,
        "overbend_deg": FORMED_ANGLE - theta_f,
    }


def springback_by_material() -> dict[str, dict[str, float]]:
    """Return the springback of a 90° bend in mild steel and in spring-tempered steel."""
    return {
        "mild_steel": _material("250 MPa", "200 GPa"),
        "spring_steel": _material("1200 MPa", "207 GPa"),
    }


def main() -> None:
    result = springback_by_material()
    for name, m in result.items():
        print(
            f"{name:12s}: K_s {m['springback_factor']:.3f}, "
            f"radius 4.0 -> {m['sprung_radius_mm']:.2f} mm, "
            f"90 deg -> {m['sprung_angle_deg']:.1f} deg (overbend {m['overbend_deg']:.1f} deg)"
        )
    print("  -> the resilient alloy springs back ~5x more; overbend is per-material, not fixed")


if __name__ == "__main__":
    main()
