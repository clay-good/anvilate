"""Worked example: which clause actually fails a mezzanine guardrail.

A storage mezzanine gets a guardrail along its open edge: circular hollow posts at 1.8 m
centres, a top rail at 1,070 mm, a midrail and a toeboard, all in S355. 29 CFR 1910.29
asks five things of it, and the one a designer worries about is rarely the one that bites.

The run as drawn uses 48.3 x 3.2 tube and passes. Drop to 33.7 x 2.6 — the next size down
in the same family, and a perfectly ordinary handrail tube — and it **fails**, on
(b)(3): the post yields under the 200 lbf the clause applies at the top rail.

What it does *not* fail is (b)(4), the clause that says the loaded rail may not drop below
39 inches. And it cannot. The two clauses cross at one post diameter, and the example
computes it: a 1,070 mm steel post deflects into the 39-inch floor only below about 17 mm
across, which is a rod and not a guardrail. **For a steel post of ordinary height, (b)(3)
always fails first** — so an engineer who sizes for the deflection clause has sized for
the wrong one, and one who sizes for strength gets the deflection clause for free.

That is worth knowing because the two clauses *look* like they guard different things.
They do, at some diameter; just not at any diameter anyone builds a guardrail from.

The example reports both runs' strength factors, the deflected height against the floor,
and the diameter at which the two clauses change places.

Run it directly (``python examples/mezzanine_guardrail.py``);
:func:`mezzanine_guardrail` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.walking_working import (
    DEFLECTED_HEIGHT_FLOOR,
    TOP_RAIL_FORCE,
    GuardrailSystem,
    Regime,
    screen_guardrail,
)
from anvilate.scorecard import CheckStatus, Scorecard
from anvilate.units import Quantity

Q = Quantity.parse

POST_HEIGHT = Q("1070 mm")
POST_SPACING = Q("1800 mm")
STEEL_YIELD = Q("355 MPa")
STEEL_MODULUS = Q("200 GPa")

#: 48.3 x 3.2 CHS, the section a mezzanine guardrail is usually drawn with.
DRAWN_SECTION_MODULUS = Q("4930 mm**3")
DRAWN_SECOND_MOMENT = Q("1.19e5 mm**4")
#: 33.7 x 2.6 CHS, the next size down and an ordinary handrail tube.
LIGHT_SECTION_MODULUS = Q("2140 mm**3")
LIGHT_SECOND_MOMENT = Q("3.60e4 mm**4")


def _guardrail(section_modulus: Quantity, second_moment: Quantity) -> GuardrailSystem:
    return GuardrailSystem(
        regime=Regime.GENERAL_INDUSTRY,
        post_height=POST_HEIGHT,
        post_spacing=POST_SPACING,
        post_section_modulus=section_modulus,
        post_second_moment=second_moment,
        yield_strength=STEEL_YIELD,
        elastic_modulus=STEEL_MODULUS,
        rail_section_modulus=section_modulus,
        midrail_height=Q("530 mm"),
        toeboard_height=Q("100 mm"),
        toeboard_section_modulus=Q("1670 mm**3"),
    )


def drawn_run() -> Scorecard:
    """The run as drawn, on 48.3 x 3.2 tube."""
    return screen_guardrail(_guardrail(DRAWN_SECTION_MODULUS, DRAWN_SECOND_MOMENT))


def light_run() -> Scorecard:
    """The same run one size down, on 33.7 x 2.6 tube."""
    return screen_guardrail(_guardrail(LIGHT_SECTION_MODULUS, LIGHT_SECOND_MOMENT))


def crossover_diameter() -> Quantity:
    """The post diameter at which (b)(3) and (b)(4) change places.

    A thin circular tube has ``Z = 2I/D``, so the strength limit ``Z = P·h/F_y`` and the
    deflection limit ``I = P·h³/(3·E·δ)`` meet at exactly one diameter. Above it the
    strength clause fails first; below it the deflection clause does.
    """
    force = TOP_RAIL_FORCE.to("N").magnitude
    height = POST_HEIGHT.to("m").magnitude
    allowed = height - DEFLECTED_HEIGHT_FLOOR.to("m").magnitude
    second_moment = force * height**3 / (3 * STEEL_MODULUS.to("Pa").magnitude * allowed)
    section_modulus = force * height / STEEL_YIELD.to("Pa").magnitude
    return Quantity(magnitude=2 * second_moment / section_modulus, unit="m")


def mezzanine_guardrail() -> dict[str, float]:
    """The figures this example's prose turns on, each read off the same two cards."""
    drawn, light = drawn_run(), light_run()

    def of(card: Scorecard, name: str):
        return next(entry for entry in card.entries if entry.name == name)

    deflection = of(light, "guardrail deflected height").comparison
    return {
        "drawn_strength_factor": of(drawn, "guardrail post under the top rail load").safety_factor,
        "light_strength_factor": of(light, "guardrail post under the top rail load").safety_factor,
        "light_deflected_height_mm": deflection.measured.to("mm").magnitude,
        "floor_mm": deflection.limit.to("mm").magnitude,
        "crossover_diameter_mm": crossover_diameter().to("mm").magnitude,
        "drawn_passes": float(drawn.status is CheckStatus.PASS),
        "light_fails": float(light.status is CheckStatus.FAIL),
    }


def main() -> None:
    for label, card in (("as drawn, 48.3 x 3.2", drawn_run()), ("33.7 x 2.6", light_run())):
        print(f"--- {label}")
        print(card)
        for entry in card.entries:
            print(f"[{entry.status.name}] {entry.name}: {entry.detail}")
        print()
    for name, value in mezzanine_guardrail().items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
