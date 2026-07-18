"""T1 analytical O-ring gland checks (closed-form squeeze, fill, and stretch).

An O-ring seals because its round cross-section is squeezed between a groove bottom and
a sealing face, and the whole design reduces to three geometric ratios that a groove
must land inside. **Squeeze** is how much the cross-section is flattened,
(CS − E)/CS for a free cross-section ``CS`` and a radial gland depth ``E`` — too little
and it leaks, too much and it takes a compression set; static seals aim for roughly
15–30 %. **Gland fill** is the fraction of the groove the rubber occupies,
(π·CS²/4)/(E·G) for a groove width ``G`` — the groove must never fill completely
(target ≈ 60–85 %), because rubber is nearly incompressible and thermal expansion or
fluid swell needs somewhere to go, or it extrudes and blows the seal. **Stretch** is how
far the ring's inner diameter is opened to fit its groove, (D_groove − ID)/ID — a little
(under ~5 %) holds it in place, too much thins the cross-section and shortens its life.

The design screen is simply: does the chosen groove put all three ratios in band? These
are pure geometry — every input is a dimension-checked
:class:`~anvilate.units.Quantity`, and every result is a dimensionless fraction (multiply
by 100 for a percentage).
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "o_ring_squeeze_fraction",
    "o_ring_gland_fill_fraction",
    "o_ring_stretch_fraction",
]


def _positive_mm(value: Quantity, name: str) -> float:
    if not value.has_dimension("[length]"):
        raise ValueError(
            f"{name} must be a [length] quantity; got {value.dimensionality} ({value})"
        )
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def o_ring_squeeze_fraction(*, cross_section_diameter: Quantity, gland_depth: Quantity) -> float:
    """The squeeze fraction (CS − E)/CS of an O-ring in its gland.

    How much the round cross-section is flattened: the free ``cross_section_diameter``
    CS less the radial ``gland_depth`` E (groove bottom to sealing face), over CS. A
    static seal aims for roughly 0.15–0.30; too little leaks, too much sets. The gland
    must be shallower than the cross-section (E < CS) or there is no squeeze. Returns
    the dimensionless fraction.
    """
    cs = _positive_mm(cross_section_diameter, "cross_section_diameter")
    e = _positive_mm(gland_depth, "gland_depth")
    if e >= cs:
        raise ValueError(
            f"gland_depth ({e} mm) must be less than cross_section_diameter ({cs} mm) "
            "for the O-ring to be squeezed"
        )
    return (cs - e) / cs


def o_ring_gland_fill_fraction(
    *, cross_section_diameter: Quantity, gland_depth: Quantity, groove_width: Quantity
) -> float:
    """The gland fill fraction (π·CS²/4)/(E·G) of the groove the O-ring occupies.

    The rubber cross-section area π·CS²/4 over the groove's cross-section area E·G
    (radial ``gland_depth`` E times axial ``groove_width`` G). Rubber is nearly
    incompressible, so the groove must leave room (target ≈ 0.60–0.85) for thermal
    expansion and fluid swell; a fill at or above 1 cannot physically assemble and will
    extrude. ``cross_section_diameter`` is CS. Returns the dimensionless fraction.
    """
    cs = _positive_mm(cross_section_diameter, "cross_section_diameter")
    e = _positive_mm(gland_depth, "gland_depth")
    g = _positive_mm(groove_width, "groove_width")
    return (pi * cs**2 / 4.0) / (e * g)


def o_ring_stretch_fraction(*, inner_diameter: Quantity, groove_diameter: Quantity) -> float:
    """The stretch fraction (D_groove − ID)/ID an O-ring takes to fit its groove.

    How far the ring's free ``inner_diameter`` ID is opened to seat on the
    ``groove_diameter`` D_groove (the groove bottom it stretches around, e.g. a piston
    OD). A little stretch (under ~0.05) keeps the ring seated; too much thins the
    cross-section and shortens life. The groove must be at least as large as the ID.
    Returns the dimensionless fraction (0 when the ring just fits unstretched).
    """
    id_ = _positive_mm(inner_diameter, "inner_diameter")
    groove = _positive_mm(groove_diameter, "groove_diameter")
    if groove < id_:
        raise ValueError(
            f"groove_diameter ({groove} mm) must be at least the O-ring inner_diameter ({id_} mm)"
        )
    return (groove - id_) / id_
