"""T1 analytical vapor-liquid equilibrium checks (ideal Raoult's law, closed-form).

Separating a liquid mixture by distillation rests on a simple fact: the vapor in equilibrium with a
boiling liquid is richer in the more volatile component. For an ideal solution that follows Raoult's
law, each component's partial pressure over the liquid is its mole fraction times its pure-component
vapor pressure, p_i = x_i·P_i*, so the total pressure is the mole-fraction-weighted sum of the pure
vapor pressures.

The sharpness of the separation is set by the relative volatility α = P_light*/P_heavy*, the ratio
of the two pure vapor pressures. The larger α is, the more the vapor enriches in the light component
in a single stage; as α approaches 1 the components boil too alike to separate (an α of exactly 1,
or an azeotrope, cannot be split by ordinary distillation). From α the equilibrium vapor composition
follows in closed form for a binary mixture: y = α·x/(1 + (α−1)·x), the x-y equilibrium curve that a
McCabe-Thiele diagram steps off to count distillation stages. Mole fractions and the relative
volatility are plain floats in [0, 1] and > 0; vapor pressures are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import exp, log, sqrt

from ..units import Quantity

__all__ = [
    "equilibrium_vapor_mole_fraction",
    "fenske_minimum_stages",
    "gilliland_actual_stages",
    "raoult_partial_pressure",
    "relative_volatility",
    "underwood_minimum_reflux",
]


def raoult_partial_pressure(
    *, liquid_mole_fraction: float, pure_vapor_pressure: Quantity
) -> Quantity:
    """The Raoult's-law partial pressure, p_i = x_i·P_i*.

    The partial pressure a component exerts over an ideal liquid solution: its
    ``liquid_mole_fraction`` x_i times its ``pure_vapor_pressure`` P_i* (the vapor pressure of the
    pure component at the solution temperature), p_i = x_i·P_i*. Summed over all components it gives
    the total pressure above the liquid, and it is the basis of every ideal-solution VLE calculation
    — a dilute solute contributes little, a nearly pure component almost all of its pure pressure.
    Returns the partial pressure in the same pressure unit family (kPa).
    """
    _check(pure_vapor_pressure, "[pressure]", "pure_vapor_pressure")
    if not 0.0 <= liquid_mole_fraction <= 1.0:
        raise ValueError(f"liquid_mole_fraction must be in [0, 1]; got {liquid_mole_fraction}")
    p_pure = pure_vapor_pressure.to("kPa").magnitude
    if p_pure < 0:
        raise ValueError("pure_vapor_pressure must be non-negative")
    return Quantity(magnitude=liquid_mole_fraction * p_pure, unit="kPa")


def relative_volatility(*, light_vapor_pressure: Quantity, heavy_vapor_pressure: Quantity) -> float:
    """The relative volatility of an ideal binary, α = P_light*/P_heavy*.

    The ratio of the two pure-component vapor pressures, α = P_light*/P_heavy*, from the
    ``light_vapor_pressure`` of the more volatile component and the ``heavy_vapor_pressure`` of the
    less volatile one (both at the mixture temperature). It measures how easily distillation
    separates the pair: α ≫ 1 is an easy split in few stages, while α → 1 means the two boil too
    alike to separate and an α of 1 cannot be distilled at all. Feed it to
    :func:`equilibrium_vapor_mole_fraction`. Returns the dimensionless relative volatility as a
    plain float (≥ 1 when the components are named light/heavy correctly).
    """
    _check(light_vapor_pressure, "[pressure]", "light_vapor_pressure")
    _check(heavy_vapor_pressure, "[pressure]", "heavy_vapor_pressure")
    p_light = light_vapor_pressure.to("kPa").magnitude
    p_heavy = heavy_vapor_pressure.to("kPa").magnitude
    if p_light <= 0 or p_heavy <= 0:
        raise ValueError("vapor pressures must be positive")
    return p_light / p_heavy


def equilibrium_vapor_mole_fraction(
    *, liquid_mole_fraction: float, relative_volatility: float
) -> float:
    """The equilibrium vapor composition of a binary, y = α·x/(1 + (α−1)·x).

    The vapor mole fraction of the light component in equilibrium with a liquid, from the
    ``liquid_mole_fraction`` x of that component and the ``relative_volatility`` α (from
    :func:`relative_volatility`): y = α·x/(1 + (α−1)·x). This is the x-y equilibrium curve of an
    ideal binary — the vapor is always richer in the light component (y > x for α > 1), and it is
    the curve a McCabe-Thiele construction steps between the operating lines to count the stages a
    column needs. At α = 1 the vapor matches the liquid (y = x) and no separation occurs.
    Returns the vapor mole fraction (0 to 1) as a plain float.
    """
    if not 0.0 <= liquid_mole_fraction <= 1.0:
        raise ValueError(f"liquid_mole_fraction must be in [0, 1]; got {liquid_mole_fraction}")
    if relative_volatility <= 0:
        raise ValueError(f"relative_volatility must be positive; got {relative_volatility}")
    x = liquid_mole_fraction
    alpha = relative_volatility
    return alpha * x / (1.0 + (alpha - 1.0) * x)


def fenske_minimum_stages(
    *,
    distillate_light_fraction: float,
    bottoms_light_fraction: float,
    relative_volatility: float,
) -> float:
    """The Fenske minimum number of stages, N_min = ln[(x_D/(1−x_D))·((1−x_B)/x_B)] / ln(α).

    The fewest theoretical stages a binary distillation needs to reach the specified split,
    evaluated at total reflux where separation per stage is greatest: from the light-component mole
    fraction in the ``distillate_light_fraction`` x_D (the top product), the
    ``bottoms_light_fraction`` x_B (the bottom product), and the ``relative_volatility`` α (from
    :func:`relative_volatility`), N_min = ln[(x_D/(1−x_D))·((1−x_B)/x_B)] / ln(α). It is the floor
    on column height — a real column at finite reflux always needs more — and the starting
    point of every short-cut distillation design. The count includes the reboiler as one stage. A
    larger α or a looser split lowers it; α → 1 sends it to infinity (no separation is possible).
    Returns the minimum number of theoretical stages as a plain float.
    """
    if not 0.0 < distillate_light_fraction < 1.0:
        raise ValueError(
            f"distillate_light_fraction must be in (0, 1); got {distillate_light_fraction}"
        )
    if not 0.0 < bottoms_light_fraction < 1.0:
        raise ValueError(f"bottoms_light_fraction must be in (0, 1); got {bottoms_light_fraction}")
    if relative_volatility <= 1.0:
        raise ValueError(
            "relative_volatility must exceed 1 (no separation is possible at α ≤ 1); got "
            f"{relative_volatility}"
        )
    x_d = distillate_light_fraction
    x_b = bottoms_light_fraction
    if x_d <= x_b:
        raise ValueError(
            "distillate_light_fraction must exceed bottoms_light_fraction "
            "(the distillate is the light-enriched product)"
        )
    separation = (x_d / (1.0 - x_d)) * ((1.0 - x_b) / x_b)
    return log(separation) / log(relative_volatility)


def underwood_minimum_reflux(
    *,
    distillate_light_fraction: float,
    feed_light_fraction: float,
    relative_volatility: float,
) -> float:
    """The Underwood minimum reflux for a binary column, R_min = [x_D/x_F − α(1−x_D)/(1−x_F)]/(α−1).

    The reflux ratio below which no column, however tall, can make the specified top product — the
    other limiting case that brackets a real design (the reflux twin of the total-reflux
    :func:`fenske_minimum_stages`). For a saturated-liquid feed of light-component fraction
    ``feed_light_fraction`` x_F, a ``distillate_light_fraction`` x_D, and ``relative_volatility`` α,
    R_min = [x_D/x_F − α·(1 − x_D)/(1 − x_F)]/(α − 1). Real columns run at 1.1–1.5× this; the closer
    to R_min, the taller the column. Returns the minimum reflux ratio L/D as a plain float.
    """
    if not 0.0 < distillate_light_fraction < 1.0:
        raise ValueError(
            f"distillate_light_fraction must be in (0, 1); got {distillate_light_fraction}"
        )
    if not 0.0 < feed_light_fraction < 1.0:
        raise ValueError(f"feed_light_fraction must be in (0, 1); got {feed_light_fraction}")
    if relative_volatility <= 1.0:
        raise ValueError(
            "relative_volatility must exceed 1 (no separation is possible at α ≤ 1); got "
            f"{relative_volatility}"
        )
    x_d = distillate_light_fraction
    x_f = feed_light_fraction
    r_min = (x_d / x_f - relative_volatility * (1.0 - x_d) / (1.0 - x_f)) / (
        relative_volatility - 1.0
    )
    if r_min <= 0.0:
        raise ValueError(
            "the specified split needs no rectification at this feed (R_min ≤ 0); check that the "
            "distillate is enriched in the light component relative to the feed"
        )
    return r_min


def gilliland_actual_stages(
    *, minimum_stages: float, minimum_reflux_ratio: float, reflux_ratio: float
) -> float:
    """The theoretical stages at an operating reflux, via the Gilliland (Molokanov) correlation.

    The third leg of the Fenske-Underwood-Gilliland short-cut method: it interpolates between the
    total-reflux floor N_min (:func:`fenske_minimum_stages`) and the minimum-reflux ceiling R_min
    (:func:`underwood_minimum_reflux`) to the stage count N a real column needs at an operating
    ``reflux_ratio`` R. With X = (R − R_min)/(R + 1), the Molokanov fit gives
    Y = 1 − exp{[(1 + 54.4·X)/(11 + 117.2·X)]·(X − 1)/√X} and N = (N_min + Y)/(1 − Y).
    ``reflux_ratio`` must exceed ``minimum_reflux_ratio`` (below R_min the split is unreachable).
    Returns the number of theoretical stages as a plain float.
    """
    if minimum_stages <= 0.0:
        raise ValueError(f"minimum_stages must be positive; got {minimum_stages}")
    if minimum_reflux_ratio <= 0.0:
        raise ValueError(f"minimum_reflux_ratio must be positive; got {minimum_reflux_ratio}")
    if reflux_ratio <= minimum_reflux_ratio:
        raise ValueError(
            "reflux_ratio must exceed minimum_reflux_ratio (below R_min the split is unreachable); "
            f"got reflux_ratio={reflux_ratio}, minimum_reflux_ratio={minimum_reflux_ratio}"
        )
    x = (reflux_ratio - minimum_reflux_ratio) / (reflux_ratio + 1.0)
    y = 1.0 - exp((1.0 + 54.4 * x) / (11.0 + 117.2 * x) * (x - 1.0) / sqrt(x))
    return (minimum_stages + y) / (1.0 - y)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
