"""T1 analytical winch-drum checks (closed-form spooling geometry).

A winch drum is a torque-to-tension converter whose lever arm grows as it spools. Rope
wound in tight layers on a core of diameter ``D`` sits, at layer ``k``, on a centreline
diameter of D + (2k−1)·d for a rope diameter ``d`` — the first layer at D + d, each
further layer two rope diameters bigger. The line pull a drive torque ``T`` can deliver
is T divided by that working radius,

    F_k = 2·T / (D + (2k−1)·d),

so a winch is strongest at the bare drum and *loses* line pull with every layer it
winds: the catalogue line-pull rating is a first-layer number, and the layer that
matters is the one on the drum at the hardest moment of the lift.

The same layer stack sets how much rope the drum stores. With ``w`` wraps per layer
(the flange-to-flange width over the rope diameter) and ``m`` layers, summing the layer
circumferences' arithmetic series gives the tight-wound capacity

    L = π · w · m · (D + m·d),

the ideal geometry; real-world loose spooling stores a few percent less, so treat the
result as an upper bound and leave margin. All three forms are exact closed-form
geometry on dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "drum_working_radius",
    "drum_line_pull",
    "drum_rope_capacity",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _positive_mm(value: Quantity, name: str) -> float:
    _require(value, "[length]", name)
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def _check_layer(layer: int, name: str = "layer") -> int:
    if layer < 1:
        raise ValueError(f"{name} must be at least 1; got {layer}")
    return layer


def drum_working_radius(
    *,
    core_diameter: Quantity,
    rope_diameter: Quantity,
    layer: int,
) -> Quantity:
    """The rope centreline radius (D + (2k−1)·d)/2 at layer k of a winding drum.

    The lever arm the drum presents at ``layer`` k: the ``core_diameter`` D plus one
    rope diameter for the first layer and two more for each layer above it, halved.
    This is the radius both the line pull and the line speed trade against — a fuller
    drum pulls less and pays out faster at the same shaft torque and speed.
    Returns the working radius in mm.
    """
    core = _positive_mm(core_diameter, "core_diameter")
    rope = _positive_mm(rope_diameter, "rope_diameter")
    k = _check_layer(layer)
    return Quantity(magnitude=(core + (2 * k - 1) * rope) / 2, unit="mm")


def drum_line_pull(
    *,
    torque: Quantity,
    core_diameter: Quantity,
    rope_diameter: Quantity,
    layer: int,
) -> Quantity:
    """The line pull F = 2T/(D + (2k−1)·d) a drum torque delivers at layer k.

    The drive ``torque`` T divided by the working radius at ``layer`` k
    (:func:`drum_working_radius`): the tension the winch can actually put in the rope
    with that much rope already on the drum. The first layer is the catalogue rating;
    every layer above it is weaker, so screen the pull at the *highest* layer the lift
    reaches, not at the bare drum. Returns the line pull in N.
    """
    _require(torque, "[force] * [length]", "torque")
    t = torque.to("N*m").magnitude
    if t <= 0:
        raise ValueError(f"torque must be positive; got {torque}")
    radius_m = (
        drum_working_radius(core_diameter=core_diameter, rope_diameter=rope_diameter, layer=layer)
        .to("m")
        .magnitude
    )
    return Quantity(magnitude=t / radius_m, unit="N")


def drum_rope_capacity(
    *,
    core_diameter: Quantity,
    rope_diameter: Quantity,
    wraps_per_layer: int,
    layers: int,
) -> Quantity:
    """The tight-wound rope length L = π·w·m·(D + m·d) a drum stores in m layers.

    ``wraps_per_layer`` w is the flange-to-flange width over the rope diameter and
    ``layers`` m the layer count the flange height allows; summing the layer
    circumferences (an arithmetic series in the layer diameter D + (2k−1)·d) gives the
    stored length in closed form. This is the ideal tight-wound geometry — real
    spooling runs a few percent looser — so treat it as an upper bound and leave
    margin. Returns the rope length in m.
    """
    core = _positive_mm(core_diameter, "core_diameter")
    rope = _positive_mm(rope_diameter, "rope_diameter")
    if wraps_per_layer < 1:
        raise ValueError(f"wraps_per_layer must be at least 1; got {wraps_per_layer}")
    m = _check_layer(layers, "layers")
    length_mm = pi * wraps_per_layer * m * (core + m * rope)
    return Quantity(magnitude=length_mm / 1000.0, unit="m")
