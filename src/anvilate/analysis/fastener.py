"""T1 analytical bolted-joint checks (torque-tension, closed-form).

The workhorse relation for a bolted joint is ``T = K·F·d``: the tightening torque
``T`` produces a preload ``F`` in a thread of nominal diameter ``d``, scaled by
the nut factor ``K`` (an empirical coefficient rolling up thread and under-head
friction). It inverts to ``F = T/(K·d)``. Given a fastener's nominal diameter
from the standards tables, these two functions convert between the torque a shop
applies and the preload it develops — a screening estimate, since K varies
widely with lubrication and surface finish.

As with the beam and column checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values and the arithmetic runs through Pint.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
]

# Typical nut factor K for as-received (lightly-oiled) steel fasteners. Dry/rough
# joints run higher (~0.3), well-lubricated or coated ones lower (~0.15); K is the
# dominant uncertainty in torque-tension, so it is exposed as a parameter.
NUT_FACTOR_AS_RECEIVED = 0.2


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _positive_factor(nut_factor: float) -> None:
    if nut_factor <= 0:
        raise ValueError(f"nut_factor must be positive; got {nut_factor}")


def bolt_preload_from_torque(
    *,
    torque: Quantity,
    nominal_diameter: Quantity,
    nut_factor: float = NUT_FACTOR_AS_RECEIVED,
) -> Quantity:
    """The preload F = T/(K·d) a tightening ``torque`` develops in a thread.

    ``nominal_diameter`` is the thread's nominal diameter d (e.g. 8 mm for M8,
    from the standards tables); ``nut_factor`` is K. Returns the preload as a
    force. ``torque`` must be a torque (force·length) and ``nominal_diameter`` a
    length; ``nut_factor`` must be positive.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _positive_factor(nut_factor)
    preload = torque.pint / (nut_factor * nominal_diameter.pint)
    converted = preload.to("N")
    return Quantity(magnitude=float(converted.magnitude), unit="N")


def torque_for_preload(
    *,
    preload: Quantity,
    nominal_diameter: Quantity,
    nut_factor: float = NUT_FACTOR_AS_RECEIVED,
) -> Quantity:
    """The tightening torque T = K·F·d for a target ``preload``.

    The inverse of :func:`bolt_preload_from_torque`. ``preload`` must be a force
    and ``nominal_diameter`` a length; ``nut_factor`` must be positive. Returns the
    torque in newton-metres.
    """
    _require(preload, "[force]", "preload")
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _positive_factor(nut_factor)
    torque = nut_factor * preload.pint * nominal_diameter.pint
    converted = torque.to("N*m")
    return Quantity(magnitude=float(converted.magnitude), unit="N*m")
