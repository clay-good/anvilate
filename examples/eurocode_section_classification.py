"""Worked example: what Table 5.2 is for, and the three ways to read it wrong.

Before any Eurocode resistance can be found, the section has to be classified, and the
classification is where a design quietly goes wrong: every limit is a multiple of
ε = √(235/f_y), and every one of them is a ratio measured in a particular way.

The two classifications the JRC report works in full come back **class 1**: an HEB 340 in
S355 under pure compression (web c/t **20.25** against 33ε, flange **5.44** against 9ε) and
an IPE 400 in S355 in bending (web **38.49** against 72ε, flange **4.79** against 9ε). Those
are the anchor, and each one also pins how c is measured.

**The root radius.** On the IPE 400 the web's flat width is 331 mm, not 400: the flanges and
both root radii come out of it. Reading the full depth instead gives **46.51** rather than
38.49 — still class 1 in S355, which is exactly why a worked example alone does not catch
it. Note which way that error runs: a ratio read too large reports a worse class, so this
one is *conservative*. It costs sections, not safety — it rejects as class 3 a section the
code makes class 2, and sends a designer to an effective cross-section they do not need.
The dangerous direction is the same mistake inverted, and the report's published ratios are
the only check either way, which is why they are asserted and not just the verdicts.

**ε against ε² for a tube.** A circular hollow section's limits go as ε², because a tube's
local buckling scales with t/d rather than with (t/c)². At S355 ε² is **0.66** where ε is
**0.81**, so the class 3 limit is d/t ≤ **59.58**, not ≤ **73.23**. The mistake runs one
class optimistic across the whole range — this example prints the two readings side by side
for four tubes, and they disagree about every one of them.

**The flange tip.** An outstand under bending and compression has two limits, not one: 9ε/α
with its tip in compression and 9ε/(α√α) with its tip in tension, because the edge that
yields last is the one holding the flange. At α = 0.5 that is **18.00** against **25.46** —
the tip-in-compression limit is **29.29%** lower, on the same flange.

What the module will not do is guess. α, ψ and k_σ come from the stress distribution, and
asking for a class without them is refused rather than answered from a default — the last
section of the output shows each refusal in its own words.

Run it directly (``python examples/eurocode_section_classification.py``);
:func:`eurocode_section_classification` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.en1993_classification import (
    PartStress,
    SectionClass,
    en1993_epsilon,
    internal_part_class,
    outstand_flange_class,
    rolled_i_section_class,
    tubular_section_class,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

Q = Quantity.parse

#: The JRC report's two worked sections, as (h, b, t_w, t_f, r) in millimetres.
HEB_340 = (340.0, 300.0, 12.0, 21.5, 27.0)
IPE_400 = (400.0, 180.0, 8.6, 13.5, 21.0)
#: S355, the grade both worked examples use.
S355 = Q("355 MPa")
#: The tube diameters-to-thickness the two readings are compared over.
TUBE_RATIOS = (30.0, 40.0, 50.0, 60.0)
#: Table 5.2's tubular coefficients, in class order.
TUBE_COEFFICIENTS = (50.0, 70.0, 90.0)


def _classify(section: tuple[float, ...], stress: PartStress):
    h, b, tw, tf, r = section
    return rolled_i_section_class(
        height=Q(f"{h} mm"),
        width=Q(f"{b} mm"),
        web_thickness=Q(f"{tw} mm"),
        flange_thickness=Q(f"{tf} mm"),
        root_radius=Q(f"{r} mm"),
        yield_strength=S355,
        stress=stress,
    )


def heb_340_in_compression() -> tuple[SectionClass, SectionClass, SectionClass]:
    """The report's first worked classification: pure compression."""
    return _classify(HEB_340, PartStress.COMPRESSION)


def ipe_400_in_bending() -> tuple[SectionClass, SectionClass, SectionClass]:
    """The report's second: pure bending."""
    return _classify(IPE_400, PartStress.BENDING)


def web_ratios() -> dict[str, float]:
    """The IPE 400's web ratio measured correctly, and with the root radius left in."""
    h, _b, tw, tf, r = IPE_400
    return {
        "flat_mm": h - 2 * tf - 2 * r,
        "correct": (h - 2 * tf - 2 * r) / tw,
        "full_depth": h / tw,
    }


def tube_readings() -> list[tuple[float, SectionClass, SectionClass]]:
    """Each tube's class on ε², and the class the ε mistake would give it."""
    epsilon = en1993_epsilon(yield_strength=S355)
    out = []
    for ratio in TUBE_RATIOS:
        standard = tubular_section_class(diameter_ratio=ratio, epsilon=epsilon)
        mistaken = next(
            (SectionClass(n) for n, c in enumerate(TUBE_COEFFICIENTS, 1) if ratio <= c * epsilon),
            SectionClass.CLASS_4,
        )
        out.append((ratio, standard, mistaken))
    return out


def flange_tip_limits() -> dict[str, float]:
    """The class 1 outstand limit at α = 0.5, both ways round."""
    alpha = 0.5
    in_compression = 9.0 / alpha
    in_tension = 9.0 / (alpha * alpha**0.5)
    return {
        "in_compression": in_compression,
        "in_tension": in_tension,
        "spread_percent": 100.0 * (1.0 - in_compression / in_tension),
    }


def refusals() -> dict[str, str]:
    """What the module says instead of guessing at a stress distribution."""
    out: dict[str, str] = {}
    try:
        internal_part_class(
            ratio=60.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, psi=0.0
        )
    except RefusalError as refused:
        out["no alpha"] = str(refused)
    try:
        outstand_flange_class(
            ratio=12.0, epsilon=1.0, stress=PartStress.BENDING_AND_COMPRESSION, alpha=0.6
        )
    except RefusalError as refused:
        out["no k_sigma"] = str(refused)
    try:
        outstand_flange_class(ratio=12.0, epsilon=1.0, stress=PartStress.BENDING)
    except RefusalError as refused:
        out["no bending column"] = str(refused)
    if len(out) != 3:
        raise AssertionError("each of these three must be refused")
    return out


def eurocode_section_classification() -> dict[str, float]:
    """The figures this example's prose turns on."""
    h, b, tw, tf, r = IPE_400
    hh, hb, htw, htf, hr = HEB_340
    epsilon = en1993_epsilon(yield_strength=S355)
    web = web_ratios()
    tip = flange_tip_limits()
    return {
        "heb_web_ratio": (hh - 2 * htf - 2 * hr) / htw,
        "heb_flange_ratio": ((hb - htw) / 2 - hr) / htf,
        "ipe_web_ratio": web["correct"],
        "ipe_web_flat_mm": web["flat_mm"],
        "ipe_web_full_depth_ratio": web["full_depth"],
        "ipe_flange_ratio": ((b - tw) / 2 - r) / tf,
        "epsilon": epsilon,
        "epsilon_squared": epsilon * epsilon,
        "tube_class_3_limit": 90.0 * epsilon * epsilon,
        "tube_class_3_limit_mistaken": 90.0 * epsilon,
        "tip_in_compression": tip["in_compression"],
        "tip_in_tension": tip["in_tension"],
        "tip_spread_percent": tip["spread_percent"],
    }


def main() -> None:
    print("--- the two worked classifications, steel S355")
    section, web, flange = heb_340_in_compression()
    print(f"  HEB 340 in pure compression: class {int(section)} "
          f"(web class {int(web)}, flange class {int(flange)})")  # fmt: skip
    section, web, flange = ipe_400_in_bending()
    print(f"  IPE 400 in bending:          class {int(section)} "
          f"(web class {int(web)}, flange class {int(flange)})")  # fmt: skip
    print()
    print("--- the root radius, on the IPE 400's web")
    ratios = web_ratios()
    print(f"  flat width {ratios['flat_mm']:.0f} mm -> c/t {ratios['correct']:.2f}")
    print(f"  full depth            -> c/t {ratios['full_depth']:.2f}  (wrong)")
    print()
    print("--- a tube: the limits go as epsilon squared, not epsilon")
    for ratio, standard, mistaken in tube_readings():
        verdict = "agree" if standard is mistaken else "DISAGREE"
        print(f"  d/t {ratio:>5.1f}: standard class {int(standard)}, "
              f"on epsilon class {int(mistaken)}  ({verdict})")  # fmt: skip
    print()
    print("--- an outstand flange at alpha = 0.5")
    tip = flange_tip_limits()
    print(f"  tip in compression: c/t limit {tip['in_compression']:.2f}")
    print(f"  tip in tension:     c/t limit {tip['in_tension']:.2f}")
    print()
    print("--- and what it refuses rather than assumes")
    for what, message in refusals().items():
        print(f"  {what}: {message}")
    print()
    for name, value in eurocode_section_classification().items():
        print(f"{name}: {value:.4g}")


if __name__ == "__main__":
    main()
