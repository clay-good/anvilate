"""T1 analytical beam-on-elastic-foundation checks (Hetényi, closed-form).

A rail on ballast, a pipeline in soil, a machine bed on grout — a beam that rests
on a continuously yielding support, not on discrete points. The support pushes
back in proportion to how far the beam sinks, a distributed reaction ``k·y`` per
unit length, so the governing equation gains a foundation term,

    E·I·y'''' + k·y = q,

whose whole character is set by one length scale, the characteristic parameter

    β = (k / (4·E·I))^{1/4}   [1/length].

Its reciprocal 1/β is the distance over which a disturbance decays; a "long" beam
(β·L ≳ π) behaves as if infinite. For a single concentrated load P on such a beam
the deflection and bending moment both peak *under the load* and die away in a
damped sine wave, giving the two screening values

    y_max = P·β / (2·k),     M_max = P / (4·β).

The stiffer the foundation (larger k, larger β) the more the load is felt locally:
the deflection shrinks but so does the moment, as the near soil carries more of
the load. As with the other checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values and the arithmetic runs through Pint.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "foundation_characteristic_parameter",
    "beam_on_elastic_foundation_max_deflection",
    "beam_on_elastic_foundation_max_moment",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def foundation_characteristic_parameter(
    *,
    foundation_modulus: Quantity,
    elastic_modulus: Quantity,
    second_moment: Quantity,
) -> Quantity:
    """The characteristic parameter β = (k/(4·E·I))^{1/4} of a beam on an elastic
    foundation.

    The single length scale that governs a beam on a continuous elastic support:
    disturbances decay over a distance ~1/β, and a beam longer than about π/β acts
    as if infinite. ``foundation_modulus`` k is the distributed reaction per unit
    length per unit deflection (a pressure, e.g. the subgrade modulus times the beam
    width — force per length per length), ``elastic_modulus`` E the beam material's,
    and ``second_moment`` I the beam section's. k must be a [pressure], E a
    [pressure], and I a [length]⁴, all positive. Returns β as an inverse length
    (1/mm).
    """
    _require(foundation_modulus, "[pressure]", "foundation_modulus")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(second_moment, "[length]**4", "second_moment")
    if foundation_modulus.to("N/mm**2").magnitude <= 0:
        raise ValueError(f"foundation_modulus must be positive; got {foundation_modulus}")
    if elastic_modulus.to("MPa").magnitude <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    if second_moment.to("mm**4").magnitude <= 0:
        raise ValueError(f"second_moment must be positive; got {second_moment}")
    beta = (foundation_modulus.pint / (4 * elastic_modulus.pint * second_moment.pint)) ** 0.25
    converted = beta.to("1/mm")
    return Quantity(magnitude=float(converted.magnitude), unit="1/mm")


def beam_on_elastic_foundation_max_deflection(
    *,
    load: Quantity,
    foundation_modulus: Quantity,
    elastic_modulus: Quantity,
    second_moment: Quantity,
) -> Quantity:
    """The peak deflection y_max = P·β/(2·k) under a point load on a long beam on an
    elastic foundation.

    The deflection peaks directly under the concentrated ``load`` P and decays in a
    damped sine wave to either side. ``foundation_modulus`` k, ``elastic_modulus`` E,
    and ``second_moment`` I set the characteristic parameter β
    (:func:`foundation_characteristic_parameter`); the deflection then follows as
    y_max = P·β/(2·k). Assumes a beam long enough (β·L ≳ π) to count as infinite. P
    must be a force. Returns the peak deflection in millimetres.
    """
    _require(load, "[force]", "load")
    if load.to("N").magnitude <= 0:
        raise ValueError(f"load must be positive; got {load}")
    beta = foundation_characteristic_parameter(
        foundation_modulus=foundation_modulus,
        elastic_modulus=elastic_modulus,
        second_moment=second_moment,
    )
    deflection = load.pint * beta.pint / (2 * foundation_modulus.pint)
    converted = deflection.to("mm")
    return Quantity(magnitude=float(converted.magnitude), unit="mm")


def beam_on_elastic_foundation_max_moment(
    *,
    load: Quantity,
    foundation_modulus: Quantity,
    elastic_modulus: Quantity,
    second_moment: Quantity,
) -> Quantity:
    """The peak bending moment M_max = P/(4·β) under a point load on a long beam on an
    elastic foundation.

    Like the deflection, the bending moment peaks under the concentrated ``load`` P
    and decays away from it. It depends on the load and the characteristic parameter
    β alone: M_max = P/(4·β), with β from
    :func:`foundation_characteristic_parameter` using ``foundation_modulus`` k,
    ``elastic_modulus`` E, and ``second_moment`` I. A stiffer foundation (larger β)
    localizes the load and *lowers* the peak moment, since the nearby support carries
    more of it. Assumes a beam long enough (β·L ≳ π) to count as infinite. P must be
    a force. Returns the peak moment in newton-metres.
    """
    _require(load, "[force]", "load")
    if load.to("N").magnitude <= 0:
        raise ValueError(f"load must be positive; got {load}")
    beta = foundation_characteristic_parameter(
        foundation_modulus=foundation_modulus,
        elastic_modulus=elastic_modulus,
        second_moment=second_moment,
    )
    moment = load.pint / (4 * beta.pint)
    converted = moment.to("N*m")
    return Quantity(magnitude=float(converted.magnitude), unit="N*m")
