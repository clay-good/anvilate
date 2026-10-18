"""Worked example: a four-bolt bracket joint screened to NASA-STD-5020B.

Four M8 bolts hold a bracket, torqued dry to a nominal 12 kN preload with a ±5% torque
tolerance. With no torque-tension tests, NASA-STD-5020B Table 3 gives a 35% default
preload uncertainty, labelled as a default. The maximum preload is then 17,010 N and
the minimum for separation and slip is 8,935 N, after 5% short-term relaxation.

Each bolt carries 2.5 kN of limit tension and 1.2 kN of limit shear. The joint opens at an
applied 19,440 N, long before the bolt would rupture, so the ultimate margin uses
the allowable alone: MS = 8.09, and the separation margin is 1.59.

Slip is another matter. With friction held to the 0.1 the standard credits on coated or
lubricated surfaces, friction covers only 0.43 of the factored slip demand (a negative
margin): the joint slips. Lubricating the threads lowers the default scatter to 25% and
moves that only to 0.45, because friction, not scatter, is what is short. Cleaned,
uncoated metal faying surfaces earn 0.2 and reach 0.73, still short. This is a bearing
joint: carry the shear in the bolts' own shear check, or test the faying surfaces, rather
than credit friction the standard does not grant.

The bolt allowables and factors here are illustrative (an M8 property class 10.9 bolt, a
program's 1.4 ultimate and 1.25 yield factors, a 1.2 separation factor for a critical
hazard); the loads and n, φ are the caller's.

Run it directly (``python examples/preloaded_bracket_joint.py``);
:func:`preloaded_bracket_joint` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    FayingSurface,
    TighteningMethod,
    joint_slip_margin,
    preload_bounds,
    preloaded_joint_margins,
)
from anvilate.units import Quantity


def _n(value: float) -> Quantity:
    return Quantity(magnitude=value, unit="N")


def _bounds(method: TighteningMethod):
    return preload_bounds(
        nominal_preload=_n(12_000.0), method=method, torque_tolerance=0.05,
        separation_critical=False, fastener_count=4, all_metallic_clamp=True,
    )  # fmt: skip


def _slip(method: TighteningMethod, surface: FayingSurface = FayingSurface.OTHER) -> float:
    return joint_slip_margin(
        bounds=_bounds(method), limit_shear=_n(1_200.0), limit_tension=_n(2_500.0),
        surface=surface, factor_of_safety=1.25, fitting_factor=1.15,
    )  # fmt: skip


def preloaded_bracket_joint() -> dict[str, float]:
    """Return the preload bounds and the joint's margins, dry and lubricated."""
    bounds = _bounds(TighteningMethod.TORQUE_DRY)
    margins = preloaded_joint_margins(
        bounds=bounds, limit_tension=_n(2_500.0), ultimate_allowable=_n(36_600.0),
        yield_allowable=_n(32_900.0), load_introduction_factor=0.5, stiffness_factor=0.25,
        fitting_factor=1.15, ultimate_factor=1.4, yield_factor=1.25, separation_factor=1.2,
    )  # fmt: skip
    return {
        "maximum_preload": bounds.maximum,
        "minimum_slip_preload": bounds.minimum_for_slip,
        "separation_load": margins.separation_load,
        "ultimate_margin": margins.ultimate_margin,
        "separation_margin": margins.separation_margin,
        # MS + 1: the share of the factored slip demand friction covers
        "slip_ratio": _slip(TighteningMethod.TORQUE_DRY) + 1,
        "slip_ratio_lubricated": _slip(TighteningMethod.TORQUE_LUBRICATED) + 1,
        "slip_ratio_clean": _slip(TighteningMethod.TORQUE_DRY, FayingSurface.CLEANED_UNCOATED_METAL)
        + 1,
    }


def main() -> None:
    d = preloaded_bracket_joint()
    print(f"preload: {d['minimum_slip_preload']:,.0f} to {d['maximum_preload']:,.0f} N")
    print(f"joint opens at {d['separation_load']:,.0f} N applied")
    print(f"MS ultimate {d['ultimate_margin']:.2f}, separation {d['separation_margin']:.2f}")
    print(f"slip demand covered dry: {d['slip_ratio']:.2f}")
    print(f"slip demand covered lubricated: {d['slip_ratio_lubricated']:.2f}")
    print(f"slip demand covered on cleaned uncoated metal {d['slip_ratio_clean']:.2f}")


if __name__ == "__main__":
    main()
