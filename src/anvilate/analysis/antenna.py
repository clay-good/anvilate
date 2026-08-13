"""T1 analytical antenna / free-space RF-link checks (closed-form).

A radio signal spreads out as it travels, so the power a receiver captures falls with the square of
distance. The Friis transmission equation sets how much of a transmitter's power reaches a receiver
over a clear line of sight, given the two antenna gains and the wavelength. This is the link budget
behind every wireless range estimate — Wi-Fi, telemetry, satellite downlinks — and it is a distinct
propagation calculation from the acoustic inverse-square attenuation of
:mod:`anvilate.analysis.acoustics` (which carries no wavelength-dependent aperture term).

The free-space path loss is FSPL = (4*pi*d/lambda)^2, the factor by which an isotropic link loses
signal over a ``distance`` d at ``wavelength`` lambda; it grows with the square of both distance and
frequency. The Friis equation then gives the received power P_r = P_t * G_t * G_r *
(lambda/(4*pi*d))^2 from the transmit power and the linear (not dB) transmit and receive gains.
Inverting it for a receiver's minimum usable power gives the maximum line-of-sight range,
d = (lambda/(4*pi)) * sqrt(P_t * G_t * G_r / P_r_min) — the reach a link can be expected to hold.

Gains here are linear power ratios (not dBi); convert a dBi figure with G = 10^(dBi/10) first.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

_PARABOLIC_BEAMWIDTH_CONSTANT = 70.0  # deg, θ ≈ k·λ/D for a typical parabolic dish taper

__all__ = [
    "aperture_antenna_gain",
    "effective_aperture",
    "aperture_efficiency",
    "dish_diameter_for_gain",
    "free_space_path_loss",
    "fresnel_zone_radius",
    "max_line_of_sight_range",
    "parabolic_beamwidth",
    "received_power",
]


def free_space_path_loss(*, distance: Quantity, wavelength: Quantity) -> float:
    """The free-space path loss, FSPL = (4*pi*d/lambda)^2.

    The factor by which an isotropic radio link attenuates over a ``distance`` d at a ``wavelength``
    lambda, FSPL = (4*pi*d/lambda)^2. It rises with the square of distance and of frequency (shorter
    wavelength), so doubling the range or the frequency quadruples the loss. Returns the loss as a
    plain float power ratio (P_transmit/P_receive for isotropic antennas); take 10*log10 for dB.
    """
    _check(distance, "[length]", "distance")
    _check(wavelength, "[length]", "wavelength")
    d = distance.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if d <= 0:
        raise ValueError("distance must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return (4.0 * pi * d / lam) ** 2


def received_power(
    *,
    transmit_power: Quantity,
    transmit_gain: float,
    receive_gain: float,
    distance: Quantity,
    wavelength: Quantity,
) -> Quantity:
    """The Friis received power, P_r = P_t * G_t * G_r * (lambda/(4*pi*d))^2.

    The power a receiver captures over a clear line of sight: the ``transmit_power`` P_t times the
    linear ``transmit_gain`` G_t and ``receive_gain`` G_r, cut by the free-space spreading factor
    (lambda/(4*pi*d))^2 for ``distance`` d and ``wavelength`` lambda. It is the heart of a link
    budget, telling whether the signal clears the receiver's sensitivity. Returns the power in W.
    """
    _check(transmit_power, "[power]", "transmit_power")
    _check(distance, "[length]", "distance")
    _check(wavelength, "[length]", "wavelength")
    p_t = transmit_power.to("W").magnitude
    d = distance.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if p_t < 0:
        raise ValueError("transmit_power must be non-negative")
    if transmit_gain <= 0:
        raise ValueError("transmit_gain must be positive")
    if receive_gain <= 0:
        raise ValueError("receive_gain must be positive")
    if d <= 0:
        raise ValueError("distance must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    p_r = p_t * transmit_gain * receive_gain * (lam / (4.0 * pi * d)) ** 2
    return Quantity(magnitude=p_r, unit="W")


def max_line_of_sight_range(
    *,
    transmit_power: Quantity,
    transmit_gain: float,
    receive_gain: float,
    receiver_sensitivity: Quantity,
    wavelength: Quantity,
) -> Quantity:
    """The maximum range, d = (lambda/(4*pi)) * sqrt(P_t * G_t * G_r / P_r_min).

    The design inverse of :func:`received_power`: the greatest line-of-sight ``distance`` at which
    the received power still meets a receiver's ``receiver_sensitivity`` P_r_min, given the
    ``transmit_power`` P_t, linear ``transmit_gain`` G_t and ``receive_gain`` G_r, and
    ``wavelength`` lambda. It is the reach a free-space link holds before the signal drops. Returns
    the range in m.
    """
    _check(transmit_power, "[power]", "transmit_power")
    _check(receiver_sensitivity, "[power]", "receiver_sensitivity")
    _check(wavelength, "[length]", "wavelength")
    p_t = transmit_power.to("W").magnitude
    p_min = receiver_sensitivity.to("W").magnitude
    lam = wavelength.to("m").magnitude
    if p_t <= 0:
        raise ValueError("transmit_power must be positive")
    if transmit_gain <= 0:
        raise ValueError("transmit_gain must be positive")
    if receive_gain <= 0:
        raise ValueError("receive_gain must be positive")
    if p_min <= 0:
        raise ValueError("receiver_sensitivity must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    d = (lam / (4.0 * pi)) * sqrt(p_t * transmit_gain * receive_gain / p_min)
    return Quantity(magnitude=d, unit="m")


def fresnel_zone_radius(
    *,
    wavelength: Quantity,
    distance_to_near_end: Quantity,
    distance_to_far_end: Quantity,
    zone: int = 1,
) -> Quantity:
    """The Fresnel zone radius at a point on a radio path, r = √(n·λ·d₁·d₂/(d₁+d₂)).

    A radio link is not a pencil ray but an ellipsoid of zones around the line of sight, and
    keeping the first one mostly clear of obstacles is what makes the link behave like free space.
    The radius of the ``zone`` n at a point ``distance_to_near_end`` d₁ from one antenna and
    ``distance_to_far_end`` d₂ from the other is r = √(n·λ·d₁·d₂/(d₁+d₂)), from the ``wavelength``
    λ. It is widest at midpath and grows with wavelength (lower frequencies need more clearance);
    the rule of thumb is to keep 60 % of the first zone (n = 1) clear. ``zone`` is a positive
    integer and the distances positive. Returns the Fresnel radius in metres.
    """
    _check(wavelength, "[length]", "wavelength")
    _check(distance_to_near_end, "[length]", "distance_to_near_end")
    _check(distance_to_far_end, "[length]", "distance_to_far_end")
    lam = wavelength.to("m").magnitude
    d1 = distance_to_near_end.to("m").magnitude
    d2 = distance_to_far_end.to("m").magnitude
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if d1 <= 0 or d2 <= 0:
        raise ValueError("distance_to_near_end and distance_to_far_end must be positive")
    if zone < 1:
        raise ValueError("zone must be a positive integer")
    return Quantity(magnitude=sqrt(zone * lam * d1 * d2 / (d1 + d2)), unit="m")


def aperture_antenna_gain(
    *, aperture_area: Quantity, wavelength: Quantity, efficiency: float = 1.0
) -> float:
    """The aperture-antenna gain, G = efficiency * 4*pi*A/lambda^2.

    The peak gain of an aperture antenna (a dish, horn, or array) of effective ``aperture_area`` A
    at ``wavelength`` lambda, scaled by an aperture ``efficiency`` (typically 0.5-0.7 for a dish):
    G = efficiency * 4*pi*A/lambda^2. Gain rises with area and with frequency (shorter wavelength),
    so a big dish at high frequency is very directive. Returns the linear power gain (10*log10 for
    dBi).
    """
    _check(aperture_area, "[area]", "aperture_area")
    _check(wavelength, "[length]", "wavelength")
    a = aperture_area.to("m**2").magnitude
    lam = wavelength.to("m").magnitude
    if a <= 0:
        raise ValueError("aperture_area must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("efficiency must be in (0, 1]")
    return efficiency * 4.0 * pi * a / (lam * lam)


def parabolic_beamwidth(*, diameter: Quantity, wavelength: Quantity) -> float:
    """The parabolic-dish half-power beamwidth, theta ≈ 70*lambda/D (degrees).

    The approximate -3 dB beamwidth of a parabolic dish of ``diameter`` D at ``wavelength`` lambda,
    theta ≈ 70*lambda/D (the constant depends on the illumination taper; 70 is a common value). A
    larger dish or shorter wavelength narrows the beam, trading coverage for gain and pointing
    tightness. Returns the beamwidth in degrees.
    """
    _check(diameter, "[length]", "diameter")
    _check(wavelength, "[length]", "wavelength")
    d = diameter.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if d <= 0:
        raise ValueError("diameter must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return _PARABOLIC_BEAMWIDTH_CONSTANT * lam / d


def dish_diameter_for_gain(
    *, gain: float, wavelength: Quantity, efficiency: float = 1.0
) -> Quantity:
    """The dish diameter for a target gain, D = (lambda/pi)*sqrt(G/efficiency).

    The sizing inverse of :func:`aperture_antenna_gain` for a circular dish: the ``diameter`` a dish
    needs to reach a target linear ``gain`` G at ``wavelength`` lambda, given the aperture
    ``efficiency``, from G = efficiency*(pi*D/lambda)^2: D = (lambda/pi)*sqrt(G/efficiency). It
    turns a link's required gain into a physical antenna size. Returns the diameter in m.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if gain <= 0:
        raise ValueError("gain must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if not 0.0 < efficiency <= 1.0:
        raise ValueError("efficiency must be in (0, 1]")
    return Quantity(magnitude=(lam / pi) * sqrt(gain / efficiency), unit="m")


def effective_aperture(*, gain: float, wavelength: Quantity) -> Quantity:
    """The effective aperture of an antenna, A_e = G·λ²/(4π).

    The equivalent capture area any antenna presents to an incoming wave, from its linear ``gain`` G
    and the ``wavelength`` λ: A_e = G·λ²/(4π). Unlike :func:`aperture_antenna_gain` (which is for a
    physical aperture), this holds for every antenna — even a wire — and is the quantity the Friis
    equation uses on the receive side (the received power is the incident power density times A_e).
    A higher-gain antenna gathers from a larger effective area. Returns the effective aperture (m²).
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if gain <= 0:
        raise ValueError("gain must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return Quantity(magnitude=gain * lam * lam / (4.0 * pi), unit="m**2")


def aperture_efficiency(*, gain: float, physical_area: Quantity, wavelength: Quantity) -> float:
    """An aperture antenna's efficiency, η_ap = A_e/A_phys = G·λ²/(4π·A_phys).

    How much of a dish or horn's physical area actually works, from its linear ``gain`` G, its
    ``physical_area`` A_phys, and the ``wavelength`` λ: η_ap = G·λ²/(4π·A_phys), the effective
    aperture (:func:`effective_aperture`) over the physical one. It is the design inverse of the
    ``efficiency`` input to :func:`aperture_antenna_gain`; real dishes run 0.5–0.7, the shortfall
    coming from spillover, illumination taper, blockage, and surface error. The result must not
    exceed 1 (the effective area cannot beat the physical area). Returns the dimensionless
    efficiency.
    """
    _check(physical_area, "[area]", "physical_area")
    _check(wavelength, "[length]", "wavelength")
    a_phys = physical_area.to("m**2").magnitude
    lam = wavelength.to("m").magnitude
    if gain <= 0:
        raise ValueError("gain must be positive")
    if a_phys <= 0:
        raise ValueError("physical_area must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    eta = gain * lam * lam / (4.0 * pi * a_phys)
    if eta > 1.0:
        raise ValueError(
            "computed aperture efficiency exceeds 1 (effective area cannot exceed the physical "
            "area — check the gain, area, and wavelength)"
        )
    return eta


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
