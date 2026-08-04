"""Worked example: is a beam compact? The AISC classification that picks its strength equation.

Before AISC gives a beam its bending strength, it asks whether the section can actually reach the
plastic moment or whether a flange or web buckles locally first. This example classifies two A992
sections. A standard rolled W18×50 has a stocky flange and web, both well inside the plastic limits,
so it is compact and develops M_p — the ordinary case. A deep welded plate girder with the same
flange but a thin, tall web is the contrast: its flange stays compact, but the web slenderness runs
past the noncompact limit into slender territory, so web local buckling governs and the §F5 plate-
girder rules apply instead of §F2. The section's class is the worse of its two elements, so one
slender web is enough to reclassify the whole girder.

Run it directly (``python examples/beam_flexural_compactness.py``);
:func:`classify_sections` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    classify_flexural_element,
    flexural_flange_slenderness_limits,
    flexural_web_slenderness_limits,
)
from anvilate.units import Quantity

ELASTIC_MODULUS = Quantity.parse("29000 ksi")
YIELD_STRENGTH = Quantity.parse("50 ksi")  # A992


def _worse(flange: str, web: str) -> str:
    order = {"compact": 0, "noncompact": 1, "slender": 2}
    return flange if order[flange] >= order[web] else web


def classify_sections() -> dict[str, str]:
    """Return the overall class of a rolled W18x50 and a slender-web plate girder."""
    flange_p, flange_r = flexural_flange_slenderness_limits(
        elastic_modulus=ELASTIC_MODULUS, yield_strength=YIELD_STRENGTH
    )
    web_p, web_r = flexural_web_slenderness_limits(
        elastic_modulus=ELASTIC_MODULUS, yield_strength=YIELD_STRENGTH
    )

    def classify(flange_slenderness: float, web_slenderness: float) -> str:
        flange = classify_flexural_element(
            slenderness=flange_slenderness, plastic_limit=flange_p, noncompact_limit=flange_r
        )
        web = classify_flexural_element(
            slenderness=web_slenderness, plastic_limit=web_p, noncompact_limit=web_r
        )
        return _worse(flange.value, web.value)

    return {
        "rolled_w18x50": classify(6.57, 43.7),  # b_f/2t_f, h/t_w
        "plate_girder": classify(6.57, 160.0),  # same flange, thin tall web
    }


def main() -> None:
    c = classify_sections()
    print(f"rolled W18x50 : {c['rolled_w18x50'].upper()} (reaches M_p — §F2)")
    print(f"plate girder  : {c['plate_girder'].upper()} (web buckles locally — §F5)")
    print("  -> the section's class is the worse of flange and web; a slender web reclassifies it")


if __name__ == "__main__":
    main()
