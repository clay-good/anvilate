"""T1 analytical photodetector / optical-receiver checks (closed-form).

A photodiode turns light into current, and an optical receiver's reach is set by how efficiently it
does that and how much noise the conversion adds. This module gives the three quantities behind a
receiver link budget — the responsivity, the photocurrent, and the fundamental shot noise — the
detection-side companion to the photon energy and flux of :mod:`anvilate.analysis.photon`, the
fiber loss and dispersion of :mod:`anvilate.analysis.fiber_optics`, and the Johnson noise of
:mod:`anvilate.analysis.thermal_noise`.

The responsivity R = η·q·λ/(h·c) is how many amperes the diode makes per watt of light, from its
``quantum_efficiency`` η and the ``wavelength`` λ — it rises with wavelength (each longer-wavelength
photon carries less energy, so a given optical power delivers more photons and more electrons) up to
the material's cutoff. The photocurrent is then simply I = R·P_opt, linear in the received optical
power. The noise floor that current fights against is the shot noise i_n = √(2·q·I·B) over a
``bandwidth`` B — the unavoidable Poisson graininess of counting discrete charges, which sets the
best signal-to-noise a shot-noise-limited receiver can reach. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Sze & Ng, *Physics of Semiconductor Devices* (photodetectors) — the responsivity of a
photodiode at a quantum efficiency and wavelength, the photocurrent an optical power gives, the
shot-noise current, and the noise-equivalent power and specific detectivity those define.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.rotation import count_rate_per_second

_ELEMENTARY_CHARGE = 1.602176634e-19  # C
_PLANCK = 6.62607015e-34  # J*s
_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "specific_detectivity",
    "photodiode_responsivity",
    "photodiode_current",
    "shot_noise_current",
    "noise_equivalent_power",
]


def photodiode_responsivity(*, quantum_efficiency: float, wavelength: Quantity) -> Quantity:
    """A photodiode's responsivity, R = η·q·λ/(h·c).

    The current a photodiode produces per unit of incident optical power: R = ``quantum_efficiency``
    η · q · ``wavelength`` λ / (h·c). Because it scales with λ, the same quantum efficiency gives
    amps per watt at longer wavelengths (a 1550 nm InGaAs diode at η = 0.8 sits near 1 A/W). η must
    lie in (0, 1] and the wavelength be positive. Returns the responsivity in A/W.
    """
    _check(wavelength, "[length]", "wavelength")
    lam = wavelength.to("m").magnitude
    if not 0.0 < quantum_efficiency <= 1.0:
        raise ValueError("quantum_efficiency must be in (0, 1]")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    r = quantum_efficiency * _ELEMENTARY_CHARGE * lam / (_PLANCK * _SPEED_OF_LIGHT)
    return Quantity(magnitude=r, unit="A/W")


def photodiode_current(*, responsivity: Quantity, optical_power: Quantity) -> Quantity:
    """The photocurrent, I = R·P_opt.

    The current a photodiode delivers under illumination: I = ``responsivity`` R · ``optical_power``
    P_opt, linear in the received power (from :func:`photodiode_responsivity`). This is the signal
    a trans-impedance amplifier turns into a voltage, so it sets the receiver sensitivity floor.
    Returns the photocurrent in amperes.
    """
    _check(responsivity, "[current]/[power]", "responsivity")
    _check(optical_power, "[power]", "optical_power")
    r = responsivity.to("A/W").magnitude
    p = optical_power.to("W").magnitude
    if r < 0:
        raise ValueError("responsivity must be non-negative")
    if p < 0:
        raise ValueError("optical_power must be non-negative")
    return Quantity(magnitude=r * p, unit="A")


def shot_noise_current(*, current: Quantity, bandwidth: Quantity) -> Quantity:
    """The shot-noise current, i_n = √(2·q·I·B).

    The rms noise current from the discrete, Poisson-random arrival of charge carriers: i_n =
    √(2·q·``current`` I·``bandwidth`` B), over the receiver ``bandwidth`` B. It grows only with the
    square root of the current and the bandwidth, and is the fundamental floor a shot-noise-limited
    detector cannot beat — distinct from the thermal (Johnson) noise of the load resistor. Returns
    the noise current in amperes.
    """
    _check(current, "[current]", "current")
    _check(bandwidth, "[frequency]", "bandwidth")
    i = current.to("A").magnitude
    b = count_rate_per_second(bandwidth, name="bandwidth")
    if i < 0:
        raise ValueError("current must be non-negative")
    if b < 0:
        raise ValueError("bandwidth must be non-negative")
    return Quantity(magnitude=(2.0 * _ELEMENTARY_CHARGE * i * b) ** 0.5, unit="A")


def noise_equivalent_power(*, noise_current: Quantity, responsivity: Quantity) -> Quantity:
    """A detector's noise-equivalent power, NEP = i_n/R.

    The optical power that would produce a signal exactly equal to the noise — the detector's
    sensitivity floor, and the figure of merit datasheets are compared on. Both inputs are already
    computed here: the ``noise_current`` i_n of :func:`shot_noise_current` and the ``responsivity``
    R of :func:`photodiode_responsivity`. Since :func:`photodiode_current` is I = R·P, the power
    that makes I equal the noise is simply NEP = i_n/R.

    It is the point where the link budget stops: any received power below NEP is buried, so NEP
    sets the maximum reach of an optical link and the minimum detectable signal of an instrument.
    Because shot noise grows as √B, NEP does too, which is why a slower receiver sees further —
    and why the figure is usually quoted normalized as W/√Hz, obtained by dividing by √B (or by
    passing a 1 Hz bandwidth to :func:`shot_noise_current`). Returns the noise-equivalent power in
    W.
    """
    _check(noise_current, "[current]", "noise_current")
    _check(responsivity, "[current]/[power]", "responsivity")
    i_n = noise_current.to("A").magnitude
    r = responsivity.to("A/W").magnitude
    if i_n < 0:
        raise ValueError("noise_current must be non-negative")
    if r <= 0:
        raise ValueError("responsivity must be positive")
    return Quantity(magnitude=i_n / r, unit="W")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def specific_detectivity(
    *, noise_equivalent_power: Quantity, active_area: Quantity, bandwidth: Quantity
) -> Quantity:
    """The specific detectivity, D* = sqrt(A·B)/NEP.

    The area- and bandwidth-normalised sensitivity of a detector, in Jones (cm·sqrt(Hz)/W). It is
    the figure that makes two detectors comparable when :func:`noise_equivalent_power` alone
    cannot: NEP grows as the square root of both the active area and the measurement bandwidth, so
    a large slow detector always looks worse than a small fast one on NEP even when the material
    is identical. Dividing that scaling out leaves a property of the detector technology rather
    than of the part number.

    From the ``noise_equivalent_power`` NEP, the ``active_area`` A, and the ``bandwidth`` B:
    D* = sqrt(A·B)/NEP, and higher is better. A shot-noise-limited InGaAs photodiode at 1550 nm
    over a 1 mm² area comes out near 1.8×10¹¹ Jones; cooled HgCdTe reaches 10¹¹ and above in the
    infrared, while a room-temperature thermal detector sits orders of magnitude below.

    The unit is conventionally cm·sqrt(Hz)/W rather than SI, which is why the numbers match the
    ones quoted on datasheets. Use the same bandwidth the NEP was measured over — mixing a 1 Hz
    NEP with a system bandwidth inflates D* by the square root of the ratio. Returns the specific
    detectivity in cm·Hz**0.5/W.
    """
    _check(noise_equivalent_power, "[power]", "noise_equivalent_power")
    _check(active_area, "[area]", "active_area")
    _check(bandwidth, "[frequency]", "bandwidth")
    nep = noise_equivalent_power.to("W").magnitude
    area_cm2 = active_area.to("cm**2").magnitude
    b = count_rate_per_second(bandwidth, name="bandwidth")
    if nep <= 0:
        raise ValueError("noise_equivalent_power must be positive")
    if area_cm2 <= 0:
        raise ValueError("active_area must be positive")
    if b <= 0:
        raise ValueError("bandwidth must be positive")
    return Quantity(magnitude=sqrt(area_cm2 * b) / nep, unit="cm*Hz**0.5/W")
