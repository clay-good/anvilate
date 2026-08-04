"""Worked example: why a tall building rides an earthquake more gently than a squat one.

The seismic response coefficient Cs — the fraction of a building's weight it is designed to resist —
starts as a flat plateau value, Cs = SDS·Ie/R. But the design spectrum does not stay flat: past a
corner period it falls off as 1/T, so ASCE 7 caps Cs for longer-period buildings at
Cs_max = SD1·Ie/(T·R). The period comes from the building's height, Ta = Ct·hn^x, so the taller the
frame, the longer its period and the lower its capped seismic demand.

This example runs the same steel moment frame (SDS = 1.0, SD1 = 0.6, R = 8) at two heights. The
squat 12 m building has a short 0.53 s period; its cap sits well above the plateau, so the plateau
governs and Cs is the full 0.125. The tall 45 m building has a 1.5 s period, and now the 1/T cap
bites: its Cs_max is about 0.05, far below the plateau, so the tall building is designed for well
under half the seismic coefficient of the short one — on the same site, same system. The lesson is
that seismic demand is not a fixed fraction of weight: it drops with period, and the approximate
period plus the Cs cap are how the code hands a tall flexible building its lower coefficient.

Run it directly (``python examples/seismic_cs_period_cap.py``);
:func:`governing_cs` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    approximate_fundamental_period,
    seismic_response_coefficient,
    seismic_response_coefficient_upper_limit,
)
from anvilate.units import Quantity

DESIGN_SPECTRAL_SHORT = 1.0  # SDS, g
DESIGN_SPECTRAL_1S = 0.6  # SD1, g
RESPONSE_MODIFICATION = 8.0  # R, steel moment frame
PERIOD_COEFFICIENT = 0.0724  # Ct, steel moment frame (SI)
HEIGHT_EXPONENT = 0.8  # x, steel moment frame


def _governing(height: Quantity) -> dict[str, float]:
    period = approximate_fundamental_period(
        building_height=height,
        period_coefficient=PERIOD_COEFFICIENT,
        height_exponent=HEIGHT_EXPONENT,
    )
    plateau = seismic_response_coefficient(
        design_spectral_acceleration=DESIGN_SPECTRAL_SHORT,
        response_modification_factor=RESPONSE_MODIFICATION,
    )
    cap = seismic_response_coefficient_upper_limit(
        design_spectral_acceleration_1s=DESIGN_SPECTRAL_1S,
        fundamental_period=period,
        response_modification_factor=RESPONSE_MODIFICATION,
    )
    return {
        "period_s": period.to("s").magnitude,
        "plateau": plateau,
        "cap": cap,
        "governing": min(plateau, cap),
    }


def governing_cs() -> dict[str, dict[str, float]]:
    """Return the governing Cs for a squat and a tall building of the same system."""
    return {
        "squat": _governing(Quantity.parse("12 m")),
        "tall": _governing(Quantity.parse("45 m")),
    }


def main() -> None:
    r = governing_cs()
    for label, d in r.items():
        which = "plateau" if d["governing"] == d["plateau"] else "period cap"
        print(
            f"{label:5s}: T={d['period_s']:.2f}s  plateau={d['plateau']:.3f}  "
            f"cap={d['cap']:.3f}  -> Cs={d['governing']:.3f} ({which})"
        )
    print(
        "  -> the tall building's longer period caps its seismic coefficient far below the plateau"
    )


if __name__ == "__main__":
    main()
