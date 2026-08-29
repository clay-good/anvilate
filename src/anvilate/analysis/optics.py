"""T1 analytical geometric-optics checks (thin lens and diffraction, closed-form).

Optomechanical and machine-vision design rests on a handful of closed-form relations. Where the
photometry of :mod:`anvilate.analysis.illumination` counts the light a space receives, these size
the *imaging*: where a lens forms its image, how large that image is, and the finest detail any
aperture can resolve.

A thin lens obeys 1/f = 1/d_o + 1/d_i, so an object at distance d_o from a lens of focal length f
images at d_i = f·d_o/(d_o − f) — behind the lens for a real image, in front (a negative d_i) for
the virtual image of a magnifier. The image size relative to the object is the transverse
magnification m = −d_i/d_o, negative when the image is inverted. Geometry alone would let detail
shrink without limit, but the wave nature of light sets a floor: an aperture of diameter D cannot
resolve two points closer than the Rayleigh angle θ = 1.22·λ/D at wavelength λ — the diffraction
limit that caps the resolving power of every telescope, microscope, and camera lens.

The focal length itself comes from the lens's shape: the lensmaker's equation
1/f = (n − 1)·(1/R₁ − 1/R₂) fixes f from the refractive index n and the two surface radii, its
reciprocal is the lens power in diopters, and two thin lenses in contact combine as
1/f = 1/f₁ + 1/f₂.
"""

from __future__ import annotations

from math import asin, degrees, inf, radians, sin, sqrt

from ..units import Quantity

RAYLEIGH_CONSTANT = 1.22

__all__ = [
    "abbe_number",
    "combined_thin_lens_focal_length",
    "critical_angle",
    "depth_of_field_far_limit",
    "depth_of_field_near_limit",
    "diffraction_limited_angular_resolution",
    "diffraction_limited_spot_diameter",
    "fiber_numerical_aperture",
    "hyperfocal_distance",
    "lens_f_number",
    "lens_power",
    "lens_transverse_magnification",
    "lensmaker_focal_length",
    "snell_refraction_angle",
    "thin_lens_image_distance",
]


def thin_lens_image_distance(*, focal_length: Quantity, object_distance: Quantity) -> Quantity:
    """The thin-lens image distance, d_i = f·d_o/(d_o − f).

    Where a thin lens forms the image of an object: from the ``focal_length`` f and the
    ``object_distance`` d_o (both from the lens), the thin-lens equation 1/f = 1/d_o + 1/d_i
    gives d_i = f·d_o/(d_o − f). A distant object (d_o ≫ f) images near the focal point; one at the
    focus (d_o = f) images at infinity; one inside the focus (d_o < f) gives a negative d_i, the
    upright virtual image a magnifier or eyepiece produces. Returns the image distance in mm
    (positive behind the lens, negative in front).
    """
    _check(focal_length, "[length]", "focal_length")
    _check(object_distance, "[length]", "object_distance")
    f = focal_length.to("mm").magnitude
    d_o = object_distance.to("mm").magnitude
    if f <= 0:
        raise ValueError("focal_length must be positive")
    if d_o <= 0:
        raise ValueError("object_distance must be positive")
    if d_o == f:
        raise ValueError("object_distance must differ from focal_length (image is at infinity)")
    return Quantity(magnitude=f * d_o / (d_o - f), unit="mm")


def lens_transverse_magnification(*, object_distance: Quantity, image_distance: Quantity) -> float:
    """The transverse magnification, m = −d_i/d_o.

    The height of the image relative to the object: from the ``object_distance`` d_o and the
    ``image_distance`` d_i (from :func:`thin_lens_image_distance`), m = −d_i/d_o. Its magnitude is
    the size ratio and its sign the orientation — negative means the real image is inverted,
    positive an upright (virtual) image. A magnitude above one enlarges, below one reduces, as when
    a camera lens fits a large scene onto a small sensor. Returns the (signed) magnification.
    """
    _check(object_distance, "[length]", "object_distance")
    _check(image_distance, "[length]", "image_distance")
    d_o = object_distance.to("mm").magnitude
    d_i = image_distance.to("mm").magnitude
    if d_o <= 0:
        raise ValueError("object_distance must be positive")
    if d_i == 0:
        raise ValueError("image_distance must be non-zero")
    return -d_i / d_o


def diffraction_limited_angular_resolution(
    *, wavelength: Quantity, aperture_diameter: Quantity
) -> Quantity:
    """The Rayleigh diffraction limit, θ = 1.22·λ/D.

    The smallest angle an optical system can resolve, set not by its geometry but by diffraction at
    its aperture: two point sources are just separable when their angular separation reaches the
    Rayleigh criterion θ = 1.22·λ/D, from the ``wavelength`` λ and the ``aperture_diameter`` D. A
    larger aperture resolves finer detail (the reason telescopes are built big) and a shorter
    wavelength does too (the reason electron and UV microscopes outresolve visible ones). It is the
    hard ceiling on resolving power that no amount of magnification or figure quality can beat.
    Returns the angular resolution in radians.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(aperture_diameter, "[length]", "aperture_diameter")
    lam = wavelength.to("m").magnitude
    d = aperture_diameter.to("m").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if d <= 0:
        raise ValueError("aperture_diameter must be positive")
    return Quantity(magnitude=RAYLEIGH_CONSTANT * lam / d, unit="rad")


def lens_f_number(*, focal_length: Quantity, aperture_diameter: Quantity) -> float:
    """The f-number (focal ratio), N = f/D.

    The relative aperture of a lens, the ratio of its ``focal_length`` f to its
    ``aperture_diameter`` D, N = f/D. A low f-number is a "fast" lens — a wide aperture that gathers
    much light and gives shallow depth of field — while a high f-number is "slow" but deeper in
    focus; each full stop (√2 in N) halves the light. It sets both the focused spot size
    (:func:`diffraction_limited_spot_diameter`) and the depth of field
    (:func:`hyperfocal_distance`). Returns the f-number (dimensionless).
    """
    _check(focal_length, "[length]", "focal_length")
    _check(aperture_diameter, "[length]", "aperture_diameter")
    f = focal_length.to("mm").magnitude
    d = aperture_diameter.to("mm").magnitude
    if f <= 0:
        raise ValueError("focal_length must be positive")
    if d <= 0:
        raise ValueError("aperture_diameter must be positive")
    return f / d


def diffraction_limited_spot_diameter(*, wavelength: Quantity, f_number: float) -> Quantity:
    """The Airy spot diameter at focus, d = 2.44·λ·N.

    The diameter of the central Airy disk a diffraction-limited lens focuses a point to: from the
    ``wavelength`` λ and the ``f_number`` N (from :func:`lens_f_number`), d = 2.44·λ·N. It is the
    smallest spot the lens can make, so it sets the tightest focus of a laser and the pixel size to
    pair a sensor with — stopping down (raising N) blurs the spot even as it deepens the focus.
    Returns the spot diameter in micrometres.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if f_number <= 0:
        raise ValueError("f_number must be positive")
    return Quantity(magnitude=2.44 * lam * f_number, unit="m").to("micrometer")


def hyperfocal_distance(
    *, focal_length: Quantity, f_number: float, circle_of_confusion: Quantity
) -> Quantity:
    """The hyperfocal distance, H = f²/(N·c).

    The focus distance beyond which everything is acceptably sharp, from the near limit at H/2 out
    to infinity: from the ``focal_length`` f, the ``f_number`` N (from :func:`lens_f_number`), and
    the ``circle_of_confusion`` c (the largest blur spot still read as a point on the sensor),
    H = f²/(N·c). Focus there and depth of field is deepest; a longer lens or a wider aperture
    (lower N) pushes H farther out and shrinks that depth. Returns the hyperfocal distance in m.
    """
    _check(focal_length, "[length]", "focal_length")
    _check(circle_of_confusion, "[length]", "circle_of_confusion")
    f = focal_length.to("mm").magnitude
    c = circle_of_confusion.to("mm").magnitude
    if f <= 0:
        raise ValueError("focal_length must be positive")
    if f_number <= 0:
        raise ValueError("f_number must be positive")
    if c <= 0:
        raise ValueError("circle_of_confusion must be positive")
    return Quantity(magnitude=f * f / (f_number * c), unit="mm").to("m")


def depth_of_field_near_limit(
    *, hyperfocal_distance: Quantity, focus_distance: Quantity
) -> Quantity:
    """The near limit of depth of field, D_n = H·s/(H + s).

    The closest distance rendered acceptably sharp when a lens is focused at ``focus_distance`` s:
    from the ``hyperfocal_distance`` H (from :func:`hyperfocal_distance`), D_n = H·s/(H + s) (the
    standard thin-lens form for focus distances well beyond the focal length). Everything from here
    out to the far limit (:func:`depth_of_field_far_limit`) is in focus; focusing at the hyperfocal
    distance pulls this near limit back to H/2, the deepest field a lens gives. Returns the near
    limit in m.
    """
    _check(hyperfocal_distance, "[length]", "hyperfocal_distance")
    _check(focus_distance, "[length]", "focus_distance")
    h = hyperfocal_distance.to("m").magnitude
    s = focus_distance.to("m").magnitude
    if h <= 0 or s <= 0:
        raise ValueError("hyperfocal_distance and focus_distance must be positive")
    return Quantity(magnitude=h * s / (h + s), unit="m")


def depth_of_field_far_limit(
    *, hyperfocal_distance: Quantity, focus_distance: Quantity
) -> Quantity:
    """The far limit of depth of field, D_f = H·s/(H − s).

    The farthest distance rendered acceptably sharp when a lens is focused at ``focus_distance`` s:
    from the ``hyperfocal_distance`` H (from :func:`hyperfocal_distance`), D_f = H·s/(H − s) (the
    standard thin-lens form). When the focus reaches the hyperfocal distance (s = H) the denominator
    vanishes and the far limit runs to infinity — so any focus at or beyond H keeps everything sharp
    to the horizon, and this function returns infinity there. Returns the far limit in m (``inf``
    when the depth of field extends to infinity).
    """
    _check(hyperfocal_distance, "[length]", "hyperfocal_distance")
    _check(focus_distance, "[length]", "focus_distance")
    h = hyperfocal_distance.to("m").magnitude
    s = focus_distance.to("m").magnitude
    if h <= 0 or s <= 0:
        raise ValueError("hyperfocal_distance and focus_distance must be positive")
    if s >= h:
        return Quantity(magnitude=inf, unit="m")
    return Quantity(magnitude=h * s / (h - s), unit="m")


def snell_refraction_angle(
    *, incident_angle: float, incident_index: float, refracted_index: float
) -> float:
    """The refracted ray angle by Snell's law, θ₂ = arcsin(n₁·sin θ₁/n₂).

    The angle a ray bends to on crossing between media: from the ``incident_angle`` θ₁ (degrees from
    the surface normal), the ``incident_index`` n₁ of the medium it comes from, and the
    ``refracted_index`` n₂ it enters, n₁·sin θ₁ = n₂·sin θ₂. Entering a denser medium (n₂ > n₁)
    turns the ray toward the normal; leaving one bends it away. If the ray leaving a denser medium
    need sin θ₂ > 1 it cannot refract at all — it totally internally reflects
    (:func:`critical_angle`). Returns the refracted angle in degrees.
    """
    if not 0.0 <= incident_angle < 90.0:
        raise ValueError("incident_angle must be in [0, 90) degrees from the normal")
    if incident_index <= 0:
        raise ValueError("incident_index must be positive")
    if refracted_index <= 0:
        raise ValueError("refracted_index must be positive")
    sin_theta2 = incident_index * sin(radians(incident_angle)) / refracted_index
    if sin_theta2 > 1.0:
        raise ValueError("no refraction: total internal reflection (n1*sin(theta1) exceeds n2)")
    return degrees(asin(sin_theta2))


def critical_angle(*, incident_index: float, transmitted_index: float) -> float:
    """The critical angle for total internal reflection, θ_c = arcsin(n₂/n₁).

    The incidence angle past which a ray in a denser medium can no longer escape into a rarer one
    and is totally internally reflected: from the ``incident_index`` n₁ (the denser medium) and the
    ``transmitted_index`` n₂ (the rarer one, n₂ < n₁), θ_c = arcsin(n₂/n₁). Beyond it all the light
    stays inside — the effect that guides light down an optical fibre and lights a prism periscope.
    Returns the critical angle in degrees.
    """
    if incident_index <= 0:
        raise ValueError("incident_index must be positive")
    if transmitted_index <= 0:
        raise ValueError("transmitted_index must be positive")
    if transmitted_index >= incident_index:
        raise ValueError("incident_index must exceed transmitted_index (need a dense-to-rare step)")
    return degrees(asin(transmitted_index / incident_index))


def fiber_numerical_aperture(*, core_index: float, cladding_index: float) -> float:
    """The optical-fibre numerical aperture, NA = √(n_core² − n_clad²).

    The light-gathering power of a step-index fibre — the sine of the half-angle of the cone it
    accepts — set by total internal reflection at the core-cladding boundary: from the
    ``core_index`` n_core and ``cladding_index`` n_clad (slightly lower), NA = √(n_core² − n_clad²).
    A larger index contrast accepts a wider cone (easier coupling) but spreads pulses more by modal
    dispersion, the trade behind multi-mode versus single-mode fibre. Returns the NA (unitless).
    """
    if core_index <= 0:
        raise ValueError("core_index must be positive")
    if cladding_index <= 0:
        raise ValueError("cladding_index must be positive")
    if cladding_index >= core_index:
        raise ValueError("core_index must exceed cladding_index (light guides in the denser core)")
    return sqrt(core_index * core_index - cladding_index * cladding_index)


def abbe_number(*, index_d: float, index_F: float, index_C: float) -> float:
    """The Abbe number, V_d = (n_d − 1)/(n_F − n_C).

    How weakly a glass disperses colour, from its refractive index at three Fraunhofer lines: the
    yellow ``index_d`` n_d (587.6 nm), the blue ``index_F`` n_F (486.1 nm), and the red ``index_C``
    n_C (656.3 nm), V_d = (n_d − 1)/(n_F − n_C). A high Abbe number (crown glass, ~60) bends the
    colours nearly together and shows little chromatic fringing; a low one (flint glass, ~30)
    spreads them, and pairing a crown and a flint cancels the dispersion in an achromatic doublet.
    Normal dispersion means n_F > n_C. Returns the Abbe number (unitless).
    """
    if index_d <= 1.0:
        raise ValueError("index_d must exceed 1")
    if index_F <= index_C:
        raise ValueError("index_F must exceed index_C (normal dispersion: blue bends more)")
    return (index_d - 1.0) / (index_F - index_C)


def lensmaker_focal_length(
    *, refractive_index: float, radius1: Quantity, radius2: Quantity
) -> Quantity:
    """The lensmaker's focal length, 1/f = (n − 1)·(1/R₁ − 1/R₂).

    The focal length of a thin lens from its shape: the ``refractive_index`` n and the two surface
    radii ``radius1`` R₁ (front) and ``radius2`` R₂ (back), 1/f = (n − 1)·(1/R₁ − 1/R₂).
    Radii are signed — positive when the centre of curvature is on the outgoing (transmitted) side —
    so a biconvex lens takes R₁ > 0 and R₂ < 0. Returns the focal length in m.
    """
    _check(radius1, "[length]", "radius1")
    _check(radius2, "[length]", "radius2")
    r1 = radius1.to("m").magnitude
    r2 = radius2.to("m").magnitude
    if refractive_index <= 1.0:
        raise ValueError("refractive_index must exceed 1")
    if r1 == 0.0 or r2 == 0.0:
        raise ValueError("surface radii must be nonzero")
    inv_f = (refractive_index - 1.0) * (1.0 / r1 - 1.0 / r2)
    if inv_f == 0.0:
        raise ValueError("the two surfaces give zero net power (flat or afocal lens)")
    return Quantity(magnitude=1.0 / inv_f, unit="m")


def lens_power(*, focal_length: Quantity) -> Quantity:
    """The lens power (in diopters), P = 1/f.

    The optical power of a lens, the reciprocal of its ``focal_length`` f: P = 1/f, in diopters
    (1/m). A converging lens has positive power, a diverging one negative; the eye's prescription is
    quoted this way. Returns the power in 1/m (diopters).
    """
    _check(focal_length, "[length]", "focal_length")
    f = focal_length.to("m").magnitude
    if f == 0.0:
        raise ValueError("focal_length must be nonzero")
    return Quantity(magnitude=1.0 / f, unit="1/m")


def combined_thin_lens_focal_length(
    *, focal_length1: Quantity, focal_length2: Quantity
) -> Quantity:
    """The combined focal length of two thin lenses in contact, 1/f = 1/f₁ + 1/f₂.

    The effective focal length of two thin lenses placed in contact, from ``focal_length1`` f₁ and
    ``focal_length2`` f₂: 1/f = 1/f₁ + 1/f₂ — their powers add. This is how a doublet or a stacked
    pair behaves. Returns the combined focal length in m.
    """
    _check(focal_length1, "[length]", "focal_length1")
    _check(focal_length2, "[length]", "focal_length2")
    f1 = focal_length1.to("m").magnitude
    f2 = focal_length2.to("m").magnitude
    if f1 == 0.0 or f2 == 0.0:
        raise ValueError("focal lengths must be nonzero")
    inv_f = 1.0 / f1 + 1.0 / f2
    if inv_f == 0.0:
        raise ValueError("the two lenses cancel (afocal combination)")
    return Quantity(magnitude=1.0 / inv_f, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
