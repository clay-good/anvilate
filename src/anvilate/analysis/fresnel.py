"""T1 analytical Fresnel surface-reflection checks (closed-form).

Whenever light crosses a boundary between two transparent media it partly reflects, by an amount the
Fresnel equations fix from the two refractive indices. This is the glare off a window, the 4% lost
at each air-glass surface of an uncoated lens, and the reason camera optics are coated. It is the
bare surface reflection that the anti-reflection coatings of :mod:`anvilate.analysis.thin_film` are
designed to cancel.

At normal incidence the reflectance is R = ((n1 - n2)/(n1 + n2))^2, from the incident-side index n1
and the transmitted-side index n2 — about 4% for air to ordinary glass, higher for higher-index
media. Light passing through a slab (air-glass-air) loses at both surfaces, so its transmittance is
(1 - R)^2, roughly 92% for a plain glass plate. At an oblique angle the reflection of p-polarized
light vanishes entirely at the Brewster angle theta_B = arctan(n2/n1), the basis of polarizing
filters and Brewster-window laser optics.
"""

from __future__ import annotations

from math import atan, degrees

__all__ = [
    "brewster_angle",
    "fresnel_normal_reflectance",
    "slab_transmittance",
]


def fresnel_normal_reflectance(*, incident_index: float, transmitted_index: float) -> float:
    """The normal-incidence reflectance, R = ((n1 - n2)/(n1 + n2))^2.

    The fraction of light power reflected at a boundary hit head-on, from the ``incident_index`` n1
    (the medium the light comes from) and the ``transmitted_index`` n2: R = ((n1 - n2)/(n1 + n2))^2.
    It is about 0.04 (4%) for air to glass and depends only on the index contrast, not on which side
    the light comes from. Returns the reflectance as a plain float in [0, 1).
    """
    if incident_index <= 0:
        raise ValueError("incident_index must be positive")
    if transmitted_index <= 0:
        raise ValueError("transmitted_index must be positive")
    return ((incident_index - transmitted_index) / (incident_index + transmitted_index)) ** 2


def slab_transmittance(*, incident_index: float, slab_index: float) -> float:
    """The two-surface slab transmittance, T = (1 - R)^2.

    The fraction of light that passes through a slab (e.g. air-glass-air), losing a Fresnel
    reflection at each face: T = (1 - R)^2, where R is the single-surface reflectance between the
    ``incident_index`` and the ``slab_index``. A plain glass plate passes about 92%, which is why
    multi-element uncoated lenses lose so much light. Returns the transmittance as a float (0, 1].
    """
    r = fresnel_normal_reflectance(incident_index=incident_index, transmitted_index=slab_index)
    return (1.0 - r) ** 2


def brewster_angle(*, incident_index: float, transmitted_index: float) -> float:
    """The Brewster (polarizing) angle, theta_B = arctan(n2/n1).

    The angle of incidence at which p-polarized light reflects not at all, so the reflection is
    completely polarized: theta_B = arctan(n2/n1), from the ``incident_index`` n1 and the
    ``transmitted_index`` n2 (about 56 degrees for air to glass). It is the basis of polarizing
    sunglasses and the Brewster windows of gas lasers. Returns the Brewster angle in degrees.
    """
    if incident_index <= 0:
        raise ValueError("incident_index must be positive")
    if transmitted_index <= 0:
        raise ValueError("transmitted_index must be positive")
    return degrees(atan(transmitted_index / incident_index))
