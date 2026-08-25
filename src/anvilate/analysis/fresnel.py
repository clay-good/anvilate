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

Away from those two special cases the reflectance depends on both the angle and the polarization,
and the two states part company completely: R_s climbs monotonically to 1 at grazing incidence
while R_p first dips to zero at Brewster and only then climbs. That split is the whole reason
polarized sunglasses cut glare off a road or a lake, and why the incidence angle matters when an
AR coating is specified. Angles are plain floats in degrees; indices and reflectances are plain
floats.

Sources: Hecht, *Optics* (the Fresnel equations) — the s- and p-polarised reflectance at an
interface, the normal-incidence limit, Brewster's angle, and the two-surface slab transmittance.
"""

from __future__ import annotations

from math import asin, atan, cos, degrees, radians, sin, sqrt

__all__ = [
    "brewster_angle",
    "fresnel_normal_reflectance",
    "fresnel_p_reflectance",
    "fresnel_s_reflectance",
    "slab_transmittance",
]


def _transmitted_cosine(n_1: float, n_2: float, incidence_angle: float) -> tuple[float, float]:
    """Shared Snell step: validate, then return (cos theta_i, cos theta_t)."""
    if n_1 <= 0 or n_2 <= 0:
        raise ValueError("refractive indices must be positive")
    if not 0.0 <= incidence_angle < 90.0:
        raise ValueError(
            f"incidence_angle must be in 0..90 degrees (measured from the normal); "
            f"got {incidence_angle}"
        )
    theta_i = radians(incidence_angle)
    sin_t = n_1 * sin(theta_i) / n_2
    if sin_t >= 1.0:
        critical = degrees(asin(n_2 / n_1))
        raise ValueError(
            f"total internal reflection: {incidence_angle} degrees is at or beyond the critical "
            f"angle {critical:.4f} degrees for n1 = {n_1} into n2 = {n_2}, so no light is "
            f"transmitted and the Fresnel reflectance is simply 1"
        )
    return cos(theta_i), sqrt(1.0 - sin_t * sin_t)


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


def fresnel_s_reflectance(
    *, incident_index: float, transmitted_index: float, incidence_angle: float
) -> float:
    """The s-polarized reflectance at an oblique boundary.

    R_s = [(n₁cosθ_i − n₂cosθ_t)/(n₁cosθ_i + n₂cosθ_t)]², for light polarized perpendicular to the
    plane of incidence ("s" from *senkrecht*), with θ_t from Snell's law
    sinθ_t = n₁·sinθ_i/n₂. From the ``incident_index`` n₁, the ``transmitted_index`` n₂, and the
    ``incidence_angle`` θ_i in degrees from the normal.

    R_s rises monotonically from the normal-incidence value of
    :func:`fresnel_normal_reflectance` to 1 at grazing incidence — s-polarized light is always
    reflected at least as strongly as p, at every angle, which is exactly why the glare bouncing
    off a road or a lake is s-polarized and why a polarizing filter oriented to block it works.
    Raises beyond the critical angle when n₁ > n₂, where the reflectance is simply 1 and these
    expressions no longer apply. Returns the reflectance as a plain float in [0, 1].
    """
    cos_i, cos_t = _transmitted_cosine(incident_index, transmitted_index, incidence_angle)
    numerator = incident_index * cos_i - transmitted_index * cos_t
    denominator = incident_index * cos_i + transmitted_index * cos_t
    return (numerator / denominator) ** 2


def fresnel_p_reflectance(
    *, incident_index: float, transmitted_index: float, incidence_angle: float
) -> float:
    """The p-polarized reflectance at an oblique boundary.

    R_p = [(n₁cosθ_t − n₂cosθ_i)/(n₁cosθ_t + n₂cosθ_i)]², for light polarized parallel to the plane
    of incidence, with θ_t from Snell's law. From the ``incident_index`` n₁, the
    ``transmitted_index`` n₂, and the ``incidence_angle`` θ_i in degrees from the normal. Note the
    cosines are swapped relative to :func:`fresnel_s_reflectance` — that single exchange is the
    entire difference between the two polarizations.

    It is the one that does something interesting: R_p falls to exactly zero at the Brewster angle
    of :func:`brewster_angle` and climbs to 1 only after, so p-polarized light passes a boundary
    perfectly at one specific angle. That zero is what Brewster windows in laser cavities exploit
    and what makes reflected light polarized. Both functions collapse to
    :func:`fresnel_normal_reflectance` at θ_i = 0, where the plane of incidence is undefined and
    the distinction disappears. Returns the reflectance as a plain float in [0, 1].
    """
    cos_i, cos_t = _transmitted_cosine(incident_index, transmitted_index, incidence_angle)
    numerator = incident_index * cos_t - transmitted_index * cos_i
    denominator = incident_index * cos_t + transmitted_index * cos_i
    return (numerator / denominator) ** 2
