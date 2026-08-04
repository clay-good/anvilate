"""T1 analytical masonry member checks (TMS 402 allowable-stress design, closed-form).

Masonry — concrete block and clay brick, grouted and often reinforced — is designed
to TMS 402 (the Masonry Society code). Its compression members are governed as much
by slenderness as by strength: a wall or pier buckles, so the allowable axial stress
carries a slenderness reduction on the height-to-radius-of-gyration ratio h/r,

    F_a = 0.25·f'm·[1 − (h/140r)²]        for h/r ≤ 99   (stocky)
    F_a = 0.25·f'm·(70·r/h)²             for h/r > 99    (slender),

the two branches meeting exactly at h/r = 99. ``f'm`` is the specified masonry
compressive strength (from the unit-strength or prism method) and r the radius of
gyration of the net section — the caller's inputs, since f'm comes from a table.
Areas are *net* (mortar-bedded and grouted area), which for hollow units is well
below the gross. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "masonry_allowable_axial_stress",
    "masonry_column_axial_capacity",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _slenderness_factor(slenderness_ratio: float) -> float:
    if slenderness_ratio <= 0:
        raise ValueError(f"slenderness_ratio h/r must be positive; got {slenderness_ratio}")
    if slenderness_ratio <= 99.0:
        return 1.0 - (slenderness_ratio / 140.0) ** 2
    return (70.0 / slenderness_ratio) ** 2


def masonry_allowable_axial_stress(
    *,
    masonry_strength: Quantity,
    slenderness_ratio: float,
) -> Quantity:
    """The TMS 402 allowable axial compressive stress F_a of an unreinforced masonry member.

    A masonry wall or pier is slenderness-governed, and TMS 402 §8.2.4 derates the 0.25·f'm
    axial allowable by a factor that falls with the height-to-radius-of-gyration ratio:
    F_a = 0.25·f'm·[1 − (h/140r)²] up to h/r = 99, then 0.25·f'm·(70·r/h)² beyond, the two
    curves meeting there. ``masonry_strength`` f'm is the specified compressive strength and
    ``slenderness_ratio`` h/r the effective height over the net-section radius of gyration.
    Multiply by the net (mortared/grouted) area for the member's allowable axial force — see
    :func:`masonry_column_axial_capacity` when there is longitudinal reinforcement. Returns
    F_a in MPa.
    """
    _require(masonry_strength, "[pressure]", "masonry_strength")
    fm = masonry_strength.to("MPa").magnitude
    if fm <= 0:
        raise ValueError(f"masonry_strength must be positive; got {masonry_strength}")
    return Quantity(magnitude=0.25 * fm * _slenderness_factor(slenderness_ratio), unit="MPa")


def masonry_column_axial_capacity(
    *,
    masonry_strength: Quantity,
    net_area: Quantity,
    slenderness_ratio: float,
    steel_area: Quantity | None = None,
    steel_allowable_stress: Quantity | None = None,
) -> Quantity:
    """The TMS 402 allowable axial force P_a of a masonry column, with or without reinforcement.

    The member-level companion to :func:`masonry_allowable_axial_stress`: TMS 402 §8.3 sizes a
    reinforced masonry column as P_a = (0.25·f'm·A_n + 0.65·A_st·F_s)·[slenderness factor],
    where the masonry acts on its ``net_area`` A_n at 0.25·f'm and the longitudinal steel adds
    0.65·A_st·F_s, both cut by the same h/r slenderness factor as the stress. ``masonry_strength``
    f'm, ``net_area`` A_n, ``slenderness_ratio`` h/r, and — when reinforced — ``steel_area`` A_st
    with its ``steel_allowable_stress`` F_s (0.6·f_y, capped at 165 MPa in the code). Omit the
    steel arguments for a plain masonry column (the 0.65·A_st·F_s term drops out). Returns P_a
    in kN.
    """
    _require(masonry_strength, "[pressure]", "masonry_strength")
    _require(net_area, "[area]", "net_area")
    fm = masonry_strength.to("MPa").magnitude
    an = net_area.to("mm**2").magnitude
    if fm <= 0 or an <= 0:
        raise ValueError("masonry_strength and net_area must be positive")
    steel_term = 0.0
    if steel_area is not None or steel_allowable_stress is not None:
        if steel_area is None or steel_allowable_stress is None:
            raise ValueError(
                "steel_area and steel_allowable_stress must both be given for a reinforced column"
            )
        _require(steel_area, "[area]", "steel_area")
        _require(steel_allowable_stress, "[pressure]", "steel_allowable_stress")
        ast = steel_area.to("mm**2").magnitude
        fs = steel_allowable_stress.to("MPa").magnitude
        if ast <= 0 or fs <= 0:
            raise ValueError("steel_area and steel_allowable_stress must be positive")
        steel_term = 0.65 * ast * fs
    capacity = (0.25 * fm * an + steel_term) * _slenderness_factor(slenderness_ratio)
    return Quantity(magnitude=capacity / 1000.0, unit="kN")
