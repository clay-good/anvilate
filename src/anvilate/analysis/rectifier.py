"""T1 analytical full-wave rectifier capacitor-input filter checks (closed-form).

The workhorse of an unregulated DC supply is a full-wave rectifier feeding a reservoir capacitor:
the capacitor charges to near the transformer peak on each half-cycle and then discharges into the
load between peaks, leaving a sawtooth ripple riding on the DC. A handful of closed-form relations
size that capacitor and predict the ripple, all for the common full-wave case where the ripple
repeats at twice the line frequency.

The peak-to-peak ripple is set by how much charge the load draws between peaks: V_r(pp) = I_load /
(2·f·C), from the load current, the line ``frequency`` f, and the reservoir ``capacitance`` C
(the factor of 2 is the full-wave doubling of the ripple frequency). Inverting it sizes the
capacitor for a target ripple, C = I_load / (2·f·V_r). The mean DC output sits half a ripple below
the peak, V_dc ≈ V_peak − I_load/(4·f·C). The dimensionless ripple factor — the RMS ripple over the
DC level — follows in closed form as γ = 1/(4·√3·f·R_load·C), the number that says how "clean" the
supply is before any regulator.

All are first-order design estimates: they assume a full-wave bridge, a large reservoir capacitor
(ripple small compared with the peak, so the discharge is nearly linear), an ideal transformer and
diodes, and a steady load current.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "capacitor_filter_dc_voltage",
    "capacitor_filter_ripple_factor",
    "capacitor_filter_ripple_voltage",
    "filter_capacitance_for_ripple",
]

_SQRT3 = sqrt(3.0)


def capacitor_filter_ripple_voltage(
    *,
    load_current: Quantity,
    frequency: Quantity,
    capacitance: Quantity,
) -> Quantity:
    """The peak-to-peak ripple of a full-wave capacitor filter, V_r = I_load/(2·f·C).

    Between rectified peaks the reservoir capacitor alone supplies the load, drooping by
    V_r(pp) = I_load/(2·f·C), from the ``load_current`` I_load, the line ``frequency`` f, and the
    reservoir ``capacitance`` C. The 2·f is the full-wave ripple frequency (the capacitor is topped
    up twice per line cycle). Valid while the ripple is small compared with the peak, so the
    discharge is nearly linear. Returns the peak-to-peak ripple voltage in volts.
    """
    _check(load_current, "[current]", "load_current")
    _check(frequency, "1/[time]", "frequency")
    _check(capacitance, "[capacitance]", "capacitance")
    i = load_current.to("A").magnitude
    f = frequency.to("Hz").magnitude
    c = capacitance.to("F").magnitude
    if i <= 0:
        raise ValueError("load_current must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    if c <= 0:
        raise ValueError("capacitance must be positive")
    return Quantity(magnitude=i / (2.0 * f * c), unit="V")


def filter_capacitance_for_ripple(
    *,
    load_current: Quantity,
    frequency: Quantity,
    ripple_voltage: Quantity,
) -> Quantity:
    """The reservoir capacitor for a target ripple, C = I_load/(2·f·V_r).

    Inverting the full-wave ripple relation sizes the reservoir capacitor to hold the peak-to-peak
    ripple down to a chosen ``ripple_voltage`` V_r: C = I_load/(2·f·V_r), from the ``load_current``
    I_load and the line ``frequency`` f. This is the number you actually order the capacitor by;
    tighter ripple or heavier load both push it up fast. Returns the capacitance in farads.
    """
    _check(load_current, "[current]", "load_current")
    _check(frequency, "1/[time]", "frequency")
    _check(ripple_voltage, "[electric_potential]", "ripple_voltage")
    i = load_current.to("A").magnitude
    f = frequency.to("Hz").magnitude
    v_r = ripple_voltage.to("V").magnitude
    if i <= 0:
        raise ValueError("load_current must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    if v_r <= 0:
        raise ValueError("ripple_voltage must be positive")
    return Quantity(magnitude=i / (2.0 * f * v_r), unit="F")


def capacitor_filter_dc_voltage(
    *,
    peak_voltage: Quantity,
    load_current: Quantity,
    frequency: Quantity,
    capacitance: Quantity,
) -> Quantity:
    """The mean DC output of a full-wave capacitor filter, V_dc ≈ V_peak − I_load/(4·f·C).

    The reservoir voltage swings between the rectified peak and one ripple below it, so its average
    sits half a ripple down: V_dc ≈ V_peak − I_load/(4·f·C), from the transformer ``peak_voltage``
    V_peak (its amplitude, less the diode drops), the ``load_current`` I_load, the line
    ``frequency`` f, and the ``capacitance`` C. The correction is half of
    :func:`capacitor_filter_ripple_voltage`. Valid for small ripple; raises if the estimated droop
    exceeds the peak (the large-capacitor assumption has broken down). Returns the DC output in
    volts.
    """
    _check(peak_voltage, "[electric_potential]", "peak_voltage")
    _check(load_current, "[current]", "load_current")
    _check(frequency, "1/[time]", "frequency")
    _check(capacitance, "[capacitance]", "capacitance")
    v_pk = peak_voltage.to("V").magnitude
    i = load_current.to("A").magnitude
    f = frequency.to("Hz").magnitude
    c = capacitance.to("F").magnitude
    if v_pk <= 0:
        raise ValueError("peak_voltage must be positive")
    if i <= 0:
        raise ValueError("load_current must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    if c <= 0:
        raise ValueError("capacitance must be positive")
    droop = i / (4.0 * f * c)
    if droop >= v_pk:
        raise ValueError(
            "estimated ripple droop exceeds the peak voltage; the small-ripple "
            "capacitor-filter approximation does not apply (increase capacitance)"
        )
    return Quantity(magnitude=v_pk - droop, unit="V")


def capacitor_filter_ripple_factor(
    *,
    frequency: Quantity,
    load_resistance: Quantity,
    capacitance: Quantity,
) -> float:
    """The ripple factor of a full-wave capacitor filter, γ = 1/(4·√3·f·R·C).

    The dimensionless "cleanliness" of the supply — the RMS ripple divided by the DC level — for a
    full-wave capacitor-input filter: γ = 1/(4·√3·f·R·C), from the line ``frequency`` f, the
    ``load_resistance`` R, and the reservoir ``capacitance`` C. It falls with the RC time constant
    against the ripple period, so a bigger capacitor or a lighter load (larger R) cleans it up. A
    typical bulk supply lands near a few percent; a regulator downstream then knocks it to
    microvolts. Returns the dimensionless ripple factor.
    """
    _check(frequency, "1/[time]", "frequency")
    _check(load_resistance, "[resistance]", "load_resistance")
    _check(capacitance, "[capacitance]", "capacitance")
    f = frequency.to("Hz").magnitude
    r = load_resistance.to("ohm").magnitude
    c = capacitance.to("F").magnitude
    if f <= 0:
        raise ValueError("frequency must be positive")
    if r <= 0:
        raise ValueError("load_resistance must be positive")
    if c <= 0:
        raise ValueError("capacitance must be positive")
    return 1.0 / (4.0 * _SQRT3 * f * r * c)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
