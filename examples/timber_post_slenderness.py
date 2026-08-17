"""Worked example: the timber post whose length, not its load, decides the design.

A wood post is checked against the compression-parallel value F'_c, and the factor
that gets it there is the column stability factor C_P. C_P is not a modest correction.
It rides on the Euler stress F_cE = 0.822·E'_min/(l_e/d)², which falls with the square
of slenderness, so lengthening a post punishes it far harder than intuition suggests.

The same 4x4 (3.5 x 3.5 in actual) carries the same 4,000 lb, at two lengths. At 8 ft
the slenderness l_e/d is 27.4, C_P is 0.41, and the adjusted value F'_c = 557 psi
clears the applied 327 psi at a safety factor of 1.70. Stretch the identical post to
12 ft and l_e/d goes to 41.1 — half again as slender — and C_P collapses to 0.20. The
adjusted value falls to 268 psi and the post fails at 0.82. Adding 50% to the length
did not cost 50% of the capacity; it cost 52% of it.

Push further and the standard stops answering. NDS §3.7.1.4 caps a column in service
at l_e/d = 50, which for a 4x4 is 14.6 ft. At 16 ft the Ylinen arithmetic would still
hand back a perfectly plausible small number, so Anvilate refuses instead: past the
cap the member is outside the standard and the result is not a design value. That is
the point of the screen — the failure you want is the one that says so.

Run it directly (``python examples/timber_post_slenderness.py``); :func:`screen_post`
and :func:`refuse_over_slender_post` are exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    LoadDuration,
    nds_adjusted_design_value,
    nds_column_stability_factor,
    nds_compression_scorecard,
    nds_euler_buckling_stress,
    nds_load_duration_factor,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

# A 4x4 sawn post: 3.5 x 3.5 in actual, pin-ended (K_e = 1.0, so l_e is the length).
SIDE = Quantity.parse("3.5 inch")
AXIAL_LOAD = Quantity.parse("4000 lbf")

# Reference design values for the species and grade — the caller's, from the NDS tables.
REFERENCE_COMPRESSION = Quantity.parse("1350 psi")  # F_c parallel to grain
MIN_MODULUS = Quantity.parse("580000 psi")  # E_min for stability

_C_D = nds_load_duration_factor(LoadDuration.TEN_YEAR)


def _applied_stress() -> Quantity:
    """The applied compression stress f_c = P/A over the gross section."""
    area = SIDE.to("inch").magnitude ** 2
    return Quantity(magnitude=AXIAL_LOAD.to("lbf").magnitude / area, unit="psi")


def slenderness(length: Quantity) -> float:
    """The column slenderness l_e/d — effective length over the least side."""
    return length.to("inch").magnitude / SIDE.to("inch").magnitude


def stability_factor(length: Quantity) -> float:
    """The NDS §3.7.1 column stability factor C_P at a given post length."""
    f_star = nds_adjusted_design_value(reference_value=REFERENCE_COMPRESSION, factors={"C_D": _C_D})
    return nds_column_stability_factor(
        euler_buckling_stress=nds_euler_buckling_stress(
            min_modulus=MIN_MODULUS, slenderness_ratio=slenderness(length)
        ),
        reference_compression=f_star,
    )


def screen_post(length: Quantity) -> Scorecard:
    """Screen the post's compression at a given length, C_P and all."""
    f_star = nds_adjusted_design_value(reference_value=REFERENCE_COMPRESSION, factors={"C_D": _C_D})
    adjusted = nds_adjusted_design_value(
        reference_value=f_star, factors={"C_P": stability_factor(length)}
    )
    return Scorecard(
        entries=(
            nds_compression_scorecard(
                "post compression",
                compression_stress=_applied_stress(),
                adjusted_compression_value=adjusted,
            ),
        )
    )


def screen_short_post() -> Scorecard:
    """An 8 ft post: l_e/d = 27.4, C_P = 0.41, and it passes at 1.70."""
    return screen_post(Quantity.parse("8 ft"))


def screen_long_post() -> Scorecard:
    """The same post at 12 ft: l_e/d = 41.1, C_P = 0.20, and it fails at 0.82."""
    return screen_post(Quantity.parse("12 ft"))


def refuse_over_slender_post() -> str:
    """A 16 ft 4x4 is past the NDS §3.7.1.4 l_e/d cap of 50 — the screen refuses."""
    try:
        screen_post(Quantity.parse("16 ft"))
    except ValueError as exc:
        return str(exc)
    raise AssertionError("a 16 ft 4x4 exceeds l_e/d = 50 and must be refused")


def main() -> None:
    print(f"applied stress f_c = {_applied_stress().to('psi').magnitude:.0f} psi")
    for label, length in (("8 ft", Quantity.parse("8 ft")), ("12 ft", Quantity.parse("12 ft"))):
        print(f"\n{label}: l_e/d = {slenderness(length):.1f}, C_P = {stability_factor(length):.2f}")
        print(f"  {screen_post(length).entries[0]}")
    print(f"\n16 ft: {refuse_over_slender_post()}")


if __name__ == "__main__":
    main()
