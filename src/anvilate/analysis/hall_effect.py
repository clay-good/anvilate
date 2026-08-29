"""T1 analytical Hall-effect checks (closed-form).

When a current-carrying conductor sits in a magnetic field, the field pushes the moving charges to
one side, building a transverse Hall voltage across the sample. The effect is the basis of the Hall
sensor — the contactless magnetometer in every brushless-motor commutation, current clamp, and
position switch — and of the laboratory Hall measurement that reveals a semiconductor's carrier
type and density. It is distinct from the magnetostatics of :mod:`anvilate.analysis.magnetics`
(which makes and uses a field): here the field is measured by the voltage it induces across a chip.

The Hall voltage is V_H = I * B / (n * q * t), from the bias current I, the perpendicular flux
density B, the charge-carrier density n, the elementary charge q, and the sample thickness t along
the field. A thin, lightly-doped (low-n) sample gives the largest signal, which is why Hall elements
are thin semiconductors rather than metals. Reading the relation the other two ways gives the sensor
and the lab use: the field from a measured voltage (a magnetometer), B = V_H * n * q * t / I, and
the carrier density from a calibration measurement, n = I * B / (q * t * V_H).

Sources: Sze & Ng, *Physics of Semiconductor Devices* — the Hall voltage a current develops
across a conductor in a transverse field, the flux density a measured voltage infers, and the
carrier density it implies.
"""

from __future__ import annotations

from ..units import Quantity

_ELEMENTARY_CHARGE = 1.602176634e-19  # coulomb

__all__ = [
    "hall_carrier_density",
    "hall_flux_density_from_voltage",
    "hall_voltage",
]


def hall_voltage(
    *,
    current: Quantity,
    flux_density: Quantity,
    carrier_density: Quantity,
    thickness: Quantity,
) -> Quantity:
    """The Hall voltage, V_H = I * B / (n * q * t).

    The transverse voltage a magnetic field induces across a biased sample: the bias ``current`` I
    and perpendicular ``flux_density`` B, over the ``carrier_density`` n, the elementary charge, and
    the sample ``thickness`` t. The signal grows as the sample gets thinner and more lightly doped,
    which is why Hall elements are thin semiconductors, not metals. Returns the Hall voltage in V.
    """
    _check(current, "[current]", "current")
    _check(flux_density, "[magnetic_field]", "flux_density")
    _check(carrier_density, "1/[length]**3", "carrier_density")
    _check(thickness, "[length]", "thickness")
    i = current.to("A").magnitude
    b = flux_density.to("T").magnitude
    n = carrier_density.to("1/m**3").magnitude
    t = thickness.to("m").magnitude
    if n <= 0:
        raise ValueError("carrier_density must be positive")
    if t <= 0:
        raise ValueError("thickness must be positive")
    v = i * b / (n * _ELEMENTARY_CHARGE * t)
    return Quantity(magnitude=v, unit="V")


def hall_flux_density_from_voltage(
    *,
    hall_voltage: Quantity,
    current: Quantity,
    carrier_density: Quantity,
    thickness: Quantity,
) -> Quantity:
    """The flux density from a Hall reading, B = V_H * n * q * t / I.

    The magnetometer inverse of :func:`hall_voltage`: the magnetic field a Hall element reports from
    its measured ``hall_voltage`` V_H, given the bias ``current`` I, the ``carrier_density`` n, and
    the ``thickness`` t. This is how a Hall sensor turns a field into a number for motor commutation
    or current sensing. Returns the flux density in tesla.
    """
    _check(hall_voltage, "[electric_potential]", "hall_voltage")
    _check(current, "[current]", "current")
    _check(carrier_density, "1/[length]**3", "carrier_density")
    _check(thickness, "[length]", "thickness")
    v = hall_voltage.to("V").magnitude
    i = current.to("A").magnitude
    n = carrier_density.to("1/m**3").magnitude
    t = thickness.to("m").magnitude
    if i <= 0:
        raise ValueError("current must be positive")
    if n <= 0:
        raise ValueError("carrier_density must be positive")
    if t <= 0:
        raise ValueError("thickness must be positive")
    b = v * n * _ELEMENTARY_CHARGE * t / i
    return Quantity(magnitude=b, unit="T")


def hall_carrier_density(
    *,
    current: Quantity,
    flux_density: Quantity,
    thickness: Quantity,
    hall_voltage: Quantity,
) -> Quantity:
    """The carrier density from a Hall measurement, n = I * B / (q * t * V_H).

    The materials-characterization inverse of :func:`hall_voltage`: the charge-carrier density a
    Hall measurement reveals from the bias ``current`` I, the applied ``flux_density`` B, the sample
    ``thickness`` t, and the measured ``hall_voltage`` V_H. It is how the doping of a semiconductor
    is found (and, from the voltage sign, whether carriers are electrons or holes). Returns n in
    1/m**3.
    """
    _check(current, "[current]", "current")
    _check(flux_density, "[magnetic_field]", "flux_density")
    _check(thickness, "[length]", "thickness")
    _check(hall_voltage, "[electric_potential]", "hall_voltage")
    i = current.to("A").magnitude
    b = flux_density.to("T").magnitude
    t = thickness.to("m").magnitude
    v = hall_voltage.to("V").magnitude
    if t <= 0:
        raise ValueError("thickness must be positive")
    if v == 0:
        raise ValueError("hall_voltage must be non-zero")
    n = i * b / (_ELEMENTARY_CHARGE * t * v)
    return Quantity(magnitude=n, unit="1/m**3")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
