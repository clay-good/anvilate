"""Worked example: a clean card beside the failure modes nobody checked.

A steel bracket is bolted to an aluminium rail on a sea wall with an ISO 4014 M12 bolt.
The bolted-connection screen passes every check it runs. Read on its own, the card says the
joint is fine.

The document also says three things the checks never read: the part lives in a **marine**
environment, the joint is a **bolted face**, and the other side of it is **AA-6061-T6**.
From those, the failure-mode catalogue finds three ways this joint is known to fail that no
check on the card addresses — self-loosening under vibration, galvanic corrosion of the
aluminium against the steel, and fretting at the clamped faces. Each is named with the
stage it is normally found at and the test that would reach it.

Nothing here is a failed check. It is the list of questions the analysis did not ask, which
is what a clean card is silent about.

Run it directly (``python examples/clean_card_failure_modes.py``); :func:`screen_rail_joint`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.failure_modes import CoverageReport, coverage, facts_from_spec
from anvilate.scorecard import Scorecard
from anvilate.screening import screen_spec
from anvilate.spec import load_spec_yaml

DOCUMENT = """
anvilate_spec: "1.12.0"
name: sea_wall_rail_bracket
description: A steel bracket bolted to an aluminium handrail post on a sea wall.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}
environment: marine
interfaces:
  - {type: standard_component, ref: ISO4014-M12, tag: rail_bolts, kind: bolted_face,
     mating_material: {ref: AA-6061-T6}}
element_type: bolted_connection
element_params:
  name: rail
  bolt_diameter: {magnitude: 12.0, unit: mm}
  plate_thickness: {magnitude: 10.0, unit: mm}
  load: {magnitude: 8.0, unit: kN}
  bolt_material: AISI-1045-CD
  plate_material: ASTM-A36
"""


def screen_rail_joint() -> tuple[Scorecard, CoverageReport]:
    """Screen the joint and report the failure modes its declared facts reach."""
    spec = load_spec_yaml(DOCUMENT)
    card = screen_spec(spec)
    return card, coverage(card, facts_from_spec(spec))


def main() -> None:
    card, report = screen_rail_joint()
    for entry in card.entries:
        print(entry)
    print(card)
    print()
    print(report)


if __name__ == "__main__":
    main()
