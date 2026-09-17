"""Worked example: one document screened at concept depth and at detailed depth.

The same cover plate, screened twice. At ``depth: concept`` the card is short: the plate's
own pressure checks, the material, and one line per family of drawing work the document
deferred — the toleranced dimensions and the stack-up chain. Nothing is claimed about them,
and nothing is hidden: the card rolls up as ``out_of_depth`` rather than as a pass, and the
count sits beside the verdict.

At ``depth: detailed`` — the default, so this is what a document that says nothing gets —
the deferred families run: two dimensions against the CNC-milling floor and one chain
summed worst-case. That is three more checks with verdicts and no new declarations needed.

The point is that the two cards differ in what they *looked at*, not in how honest they are.
A concept screen is not a weaker gate: it is the same gate over a stated subset, with the
subset reported. An engineer who has not drawn the part yet gets a card they can act on
instead of a wall of red about dimensions that do not exist.

Run it directly (``python examples/concept_and_detailed_depth.py``).
"""

from __future__ import annotations

from anvilate.needs import deepening
from anvilate.scorecard import CheckStatus, Scorecard
from anvilate.screening import screen_spec
from anvilate.spec import ScreeningDepth, load_spec_yaml

_DOCUMENT = """
anvilate_spec: "1.11.0"
name: inspection_cover
description: A bolted inspection cover with two toleranced features and a seat chain.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: cnc_milling, tolerance_class: medium}
acceptance: {tiers: [T1_analytical, T2_dfm], depth: DEPTH}
constraints: {min_safety_factor: {value: 2.0, origin: user_stated}}
element_type: cover_plate
element_params:
  name: cover
  length: {magnitude: 300.0, unit: mm}
  width: {magnitude: 200.0, unit: mm}
  thickness: {magnitude: 10.0, unit: mm}
  material: ASTM-A36
  pressure: {magnitude: 0.2, unit: MPa}
dimensions:
  - tag: bore
    nominal: {magnitude: 25.0, unit: mm}
    tolerance: {type: symmetric, plus_minus: {magnitude: 0.05, unit: mm}}
  - tag: seat
    nominal: {magnitude: 12.0, unit: mm}
    tolerance: {type: symmetric, plus_minus: {magnitude: 0.03, unit: mm}}
chains:
  - name: seat_to_bore
    links: [{dimension: bore, direction: 1}, {dimension: seat, direction: -1}]
    required_min: {magnitude: 12.8, unit: mm}
    required_max: {magnitude: 13.2, unit: mm}
"""


def spec_at(depth: ScreeningDepth):
    """The one document, declaring ``depth``."""
    return load_spec_yaml(_DOCUMENT.replace("DEPTH", depth.value))


def concept_card() -> Scorecard:
    return screen_spec(spec_at(ScreeningDepth.CONCEPT))


def detailed_card() -> Scorecard:
    return screen_spec(spec_at(ScreeningDepth.DETAILED))


def depth_comparison() -> dict[str, object]:
    """Both cards, their completeness counts, and what the raise costs and returns."""
    concept, detailed = concept_card(), detailed_card()
    raise_ = deepening(spec_at(ScreeningDepth.CONCEPT), ScreeningDepth.DETAILED)
    return {
        "concept_checks": len(concept.entries),
        "concept_deferred": len(concept.out_of_depth()),
        "detailed_checks": len(detailed.entries),
        "detailed_deferred": len(detailed.out_of_depth()),
        "newly_run": len(raise_.newly_run),
        "newly_required": len(raise_.newly_required),
        "concept_status": concept.status,
        "detailed_status": detailed.status,
    }


def main() -> None:
    for label, card in (("concept", concept_card()), ("detailed", detailed_card())):
        not_evaluated, out_of_depth = card.completeness()
        print(f"{label}: {card.status.value.upper()}")
        for entry in card.entries:
            print(f"  {entry.status.value:<14} {entry.name}")
        print(f"  not evaluated: {not_evaluated}, out of depth: {out_of_depth}\n")
    print(deepening(spec_at(ScreeningDepth.CONCEPT), ScreeningDepth.DETAILED))
    result = depth_comparison()
    assert result["concept_status"] is CheckStatus.OUT_OF_DEPTH  # not a pass, and not a gap


if __name__ == "__main__":
    main()
