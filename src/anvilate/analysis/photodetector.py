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
"""

from __future__ import annotations

from ..units import Quantity

_ELEMENTARY_CHARGE = 1.602176634e-19  # C
_PLANCK = 6.62607015e-34  # J*s
_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "photodiode_responsivity",
    "photodiode_current",
    "shot_noise_current",
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
    b = bandwidth.to("Hz").magnitude
    if i < 0:
        raise ValueError("current must be non-negative")
    if b < 0:
        raise ValueError("bandwidth must be non-negative")
    return Quantity(magnitude=(2.0 * _ELEMENTARY_CHARGE * i * b) ** 0.5, unit="A")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
