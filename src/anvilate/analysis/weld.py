"""T1 analytical fillet-weld checks (throat shear, closed-form).

A fillet weld carries load on its *effective throat* — the shortest section
through the weld, ``a = 0.707·w`` for a leg size ``w`` (0.707 = 1/√2, the throat
of an equal-leg right triangle). The design stress is the shear on that throat,
``τ = F/(0.707·w·L)`` over a weld of length ``L`` (AISC treats all fillet-weld
stress, whatever the load direction, as shear on the throat). Sizing runs the
other way — :func:`fillet_weld_leg_for_load` inverts it to the leg a load needs.
As with the other checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

# The effective throat of a fillet weld is 0.707 (= 1/√2) of its leg size.
FILLET_THROAT_FACTOR = 0.707

__all__ = [
    "FILLET_THROAT_FACTOR",
    "fillet_weld_throat_stress",
    "fillet_weld_leg_for_load",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def fillet_weld_throat_stress(
    *,
    force: Quantity,
    leg_size: Quantity,
    length: Quantity,
) -> Quantity:
    """The shear stress τ = F/(0.707·w·L) on a fillet weld's effective throat.

    ``force`` is the load the weld carries, ``leg_size`` w the fillet leg (the
    effective throat is 0.707·w), and ``length`` L the weld length. Returns the
    throat shear stress as a pressure; every quantity is dimension-checked and
    ``leg_size`` / ``length`` must be positive.
    """
    _require(force, "[force]", "force")
    _require(leg_size, "[length]", "leg_size")
    _require(length, "[length]", "length")
    w = leg_size.to("mm").magnitude
    length_mm = length.to("mm").magnitude
    if w <= 0 or length_mm <= 0:
        raise ValueError("leg_size and length must be positive")
    throat_area = FILLET_THROAT_FACTOR * w * length_mm  # mm²
    return Quantity(magnitude=force.to("N").magnitude / throat_area, unit="MPa")


def fillet_weld_leg_for_load(
    *,
    force: Quantity,
    length: Quantity,
    allowable_shear: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least fillet-weld leg to carry ``force`` within an allowable throat shear.

    The inverse of :func:`fillet_weld_throat_stress`: demanding F/(0.707·w·L) ≤
    τ_allow/SF gives w_min = SF·F/(0.707·L·τ_allow) — the sizing step for a fillet
    weld (round up to the next standard leg, and mind the minimum leg for the
    thicker plate). ``force`` F is the load, ``length`` L the weld length,
    ``allowable_shear`` τ_allow the weld's allowable throat shear (e.g. 0.6·F_EXX),
    and ``required_safety_factor`` SF the margin on it (default 1.0). Returns the
    minimum leg in mm; the load/length/stress are dimension-checked and ``SF`` /
    ``allowable_shear`` must be positive.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    length_mm = length.to("mm").magnitude
    tau = allowable_shear.to("MPa").magnitude
    if length_mm <= 0:
        raise ValueError(f"length must be positive; got {length}")
    if tau <= 0:
        raise ValueError(f"allowable_shear must be positive; got {allowable_shear}")
    leg = (
        required_safety_factor * force.to("N").magnitude / (FILLET_THROAT_FACTOR * length_mm * tau)
    )
    return Quantity(magnitude=leg, unit="mm")
