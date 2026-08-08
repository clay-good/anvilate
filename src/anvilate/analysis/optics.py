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
"""

from __future__ import annotations

from ..units import Quantity

RAYLEIGH_CONSTANT = 1.22

__all__ = [
    "diffraction_limited_angular_resolution",
    "diffraction_limited_spot_diameter",
    "hyperfocal_distance",
    "lens_f_number",
    "lens_transverse_magnification",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
