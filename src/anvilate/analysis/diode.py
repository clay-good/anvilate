"""T1 analytical semiconductor-diode (Shockley) checks (closed-form).

A pn-junction diode passes current that rises exponentially with the voltage across it, following
the Shockley ideal-diode equation. This governs every rectifier, LED, and diode-based reference: a
small change in forward voltage swings the current by orders of magnitude, which is why a diode
clamps to a roughly fixed drop and why its current must be set by an external resistor, not by fine
voltage control. It is a distinct nonlinearity from the linear R-L-C elements of
:mod:`anvilate.analysis.reactive_circuit`.

The exponential is scaled by the thermal voltage V_T = k*T/q (about 25.85 mV at 300 K), the natural
voltage scale of carriers at temperature T. The current is then I = I_s * (exp(V/(n*V_T)) - 1), from
the saturation current I_s (the tiny reverse leakage), the applied voltage V, and the ideality
factor n (1 for an ideal junction, up to ~2 with recombination). Inverting it, the forward voltage
at a target current is V = n*V_T*ln(I/I_s + 1) — how the operating point of a diode or LED is found.

Temperature is taken as an absolute temperature (kelvin); V_T is proportional to it.

Sources: Sedra & Smith, *Microelectronic Circuits* (diodes) — the thermal voltage kT/q, the
Shockley diode equation and its inverse, and the series resistor an LED needs with the power it
dissipates.
"""

from __future__ import annotations

from math import expm1, log

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_DEVICE_SOURCE = "the diode datasheet (saturation current and ideality factor)"
_STATE_SOURCE = "the junction's absolute operating temperature"
_OPERATING_SOURCE = "the circuit's bias voltage or current"
_LED_SOURCE = "the LED datasheet's forward voltage and current and the supply rail"


class _DiodeInputError(RefusalError, ValueError):
    """A diode input that cannot be used without correction."""


def _diode_refusal(message: str, *, subject: str, source: str) -> _DiodeInputError:
    return _DiodeInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _diode_input_source(name: str) -> str:
    if name in {"ideality_factor", "saturation_current"}:
        return _DEVICE_SOURCE
    if name == "temperature":
        return _STATE_SOURCE
    if name in {"forward_current", "forward_voltage", "supply_voltage"}:
        return _LED_SOURCE
    return _OPERATING_SOURCE


_BOLTZMANN = 1.380649e-23  # J/K
_ELEMENTARY_CHARGE = 1.602176634e-19  # C

__all__ = [
    "diode_current",
    "diode_voltage",
    "led_resistor_power",
    "led_series_resistor",
    "thermal_voltage",
]


def thermal_voltage(*, temperature: Quantity) -> Quantity:
    """The thermal voltage, V_T = k*T/q.

    The natural voltage scale of charge carriers at an absolute ``temperature`` T: V_T = k*T/q,
    about 25.85 mV at 300 K. It sets how much forward voltage raises the diode current by a factor
    of e, and it rises with temperature. Returns the thermal voltage in V.
    """
    _check(temperature, "[temperature]", "temperature")
    t = temperature.to("K").magnitude
    if t <= 0:
        raise _diode_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_STATE_SOURCE,
        )
    return Quantity(magnitude=_BOLTZMANN * t / _ELEMENTARY_CHARGE, unit="V")


def diode_current(
    *,
    saturation_current: Quantity,
    voltage: Quantity,
    temperature: Quantity,
    ideality_factor: float = 1.0,
) -> Quantity:
    """The diode current, I = I_s * (exp(V/(n*V_T)) - 1).

    The Shockley ideal-diode current: the ``saturation_current`` I_s (reverse leakage) times the
    exponential of the applied ``voltage`` V over n times the thermal voltage (set by the absolute
    ``temperature`` T), less one, with ``ideality_factor`` n (1 ideal, up to ~2 with recombination).
    Forward voltage swings this by orders of magnitude; reverse voltage floors it at -I_s. Returns
    the current in A.
    """
    require_finite(ideality_factor, name="ideality_factor")
    _check(saturation_current, "[current]", "saturation_current")
    _check(voltage, "[electric_potential]", "voltage")
    _check(temperature, "[temperature]", "temperature")
    i_s = saturation_current.to("A").magnitude
    v = voltage.to("V").magnitude
    t = temperature.to("K").magnitude
    if i_s <= 0:
        raise _diode_refusal(
            "saturation_current must be positive",
            subject="saturation_current",
            source=_DEVICE_SOURCE,
        )
    if t <= 0:
        raise _diode_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_STATE_SOURCE,
        )
    if ideality_factor <= 0:
        raise _diode_refusal(
            "ideality_factor must be positive", subject="ideality_factor", source=_DEVICE_SOURCE
        )
    v_t = _BOLTZMANN * t / _ELEMENTARY_CHARGE
    return Quantity(magnitude=i_s * expm1(v / (ideality_factor * v_t)), unit="A")


def diode_voltage(
    *,
    current: Quantity,
    saturation_current: Quantity,
    temperature: Quantity,
    ideality_factor: float = 1.0,
) -> Quantity:
    """The forward voltage at a target current, V = n*V_T*ln(I/I_s + 1).

    The inverse of :func:`diode_current`: the forward voltage that drives a target forward
    ``current`` I through a diode of ``saturation_current`` I_s at absolute ``temperature`` T, with
    ``ideality_factor`` n. It is how the operating point (and the ~0.6-0.7 V drop of a silicon
    diode, or the higher drop of an LED) is found. Returns the voltage in V.
    """
    require_finite(ideality_factor, name="ideality_factor")
    _check(current, "[current]", "current")
    _check(saturation_current, "[current]", "saturation_current")
    _check(temperature, "[temperature]", "temperature")
    i = current.to("A").magnitude
    i_s = saturation_current.to("A").magnitude
    t = temperature.to("K").magnitude
    if i <= 0:
        raise _diode_refusal(
            "current must be positive", subject="current", source=_OPERATING_SOURCE
        )
    if i_s <= 0:
        raise _diode_refusal(
            "saturation_current must be positive",
            subject="saturation_current",
            source=_DEVICE_SOURCE,
        )
    if t <= 0:
        raise _diode_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_STATE_SOURCE,
        )
    if ideality_factor <= 0:
        raise _diode_refusal(
            "ideality_factor must be positive", subject="ideality_factor", source=_DEVICE_SOURCE
        )
    v_t = _BOLTZMANN * t / _ELEMENTARY_CHARGE
    return Quantity(magnitude=ideality_factor * v_t * log(i / i_s + 1.0), unit="V")


def led_series_resistor(
    *,
    supply_voltage: Quantity,
    forward_voltage: Quantity,
    forward_current: Quantity,
) -> Quantity:
    """The current-limiting resistor for an LED, R = (V_supply − V_f)/I_f.

    Because a diode's current rises exponentially with its voltage (see :func:`diode_current`), an
    LED cannot be driven from a fixed voltage — a series resistor sets the current instead. The
    resistor drops the excess supply voltage: R = (V_supply − V_f)/I_f, from the ``supply_voltage``
    V_supply, the LED's ``forward_voltage`` V_f (its roughly fixed drop at the operating current),
    and the desired ``forward_current`` I_f. The supply must exceed the forward drop or there is no
    headroom to set the current. Returns the resistance in ohms.
    """
    _check(supply_voltage, "[electric_potential]", "supply_voltage")
    _check(forward_voltage, "[electric_potential]", "forward_voltage")
    _check(forward_current, "[current]", "forward_current")
    v_s = supply_voltage.to("V").magnitude
    v_f = forward_voltage.to("V").magnitude
    i_f = forward_current.to("A").magnitude
    if i_f <= 0:
        raise _diode_refusal(
            "forward_current must be positive", subject="forward_current", source=_LED_SOURCE
        )
    if v_s <= v_f:
        raise _diode_refusal(
            "supply_voltage must exceed forward_voltage (no headroom to set the LED current)",
            subject="supply_voltage and forward_voltage",
            source=_LED_SOURCE,
        )
    return Quantity(magnitude=(v_s - v_f) / i_f, unit="ohm")


def led_resistor_power(
    *,
    supply_voltage: Quantity,
    forward_voltage: Quantity,
    forward_current: Quantity,
) -> Quantity:
    """The power dissipated in an LED's series resistor, P = (V_supply − V_f)·I_f.

    The heat the current-limiting resistor must handle: P = (V_supply − V_f)·I_f, from the
    ``supply_voltage`` V_supply, the LED ``forward_voltage`` V_f, and the ``forward_current`` I_f.
    It is the number a resistor is rated against — a 1/4 W part is fine for an indicator LED but not
    for a high-current string off a high supply, where the resistor wastes more power than the LED
    uses. Returns the dissipation in watts.
    """
    _check(supply_voltage, "[electric_potential]", "supply_voltage")
    _check(forward_voltage, "[electric_potential]", "forward_voltage")
    _check(forward_current, "[current]", "forward_current")
    v_s = supply_voltage.to("V").magnitude
    v_f = forward_voltage.to("V").magnitude
    i_f = forward_current.to("A").magnitude
    if i_f <= 0:
        raise _diode_refusal(
            "forward_current must be positive", subject="forward_current", source=_LED_SOURCE
        )
    if v_s <= v_f:
        raise _diode_refusal(
            "supply_voltage must exceed forward_voltage (no headroom to set the LED current)",
            subject="supply_voltage and forward_voltage",
            source=_LED_SOURCE,
        )
    return Quantity(magnitude=(v_s - v_f) * i_f, unit="W")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _diode_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_diode_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _diode_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_diode_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
