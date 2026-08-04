"""T1 analytical electrical feeder checks (power, current, and voltage drop, closed-form).

The industrial and plant engineers this library serves size motor feeders and heater circuits, and
that comes down to a few crisp relations. Three-phase real power is P = √3·V_LL·I·cosφ, so the line
current a load draws is I = P/(√3·V_LL·cosφ). A conductor's resistance is R = ρ·L/A (copper's
resistivity ρ ≈ 1.68e-8 Ω·m), and the voltage it drops carrying that current is, for a three-phase
run, ΔV = √3·I·(R·cosφ + X·sinφ) — the resistive part plus, on longer AC runs, a reactive part. The
usual acceptance check is that the drop stays under a few percent of the nominal voltage, so a motor
at the end of a long feeder still sees enough voltage to start and run.

This is a wiring-sizing screen, not a protection or arc-flash study. Resistivity, reactance, and
power factor are the caller's; inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "conductor_resistance",
    "line_current_for_power",
    "three_phase_power",
    "voltage_drop_three_phase",
]

_SQRT3 = sqrt(3.0)


def three_phase_power(
    *,
    line_voltage: Quantity,
    line_current: Quantity,
    power_factor: float,
) -> Quantity:
    """The real power of a balanced three-phase load, P = √3·V_LL·I·cosφ.

    The active power a three-phase load actually consumes: P = √3·V_LL·I·cosφ, from the
    ``line_voltage`` V_LL (line-to-line), the ``line_current`` I, and the ``power_factor`` cosφ
    (0 to 1 — the fraction of the apparent power that does real work). Returns the real power in kW.
    """
    _check(line_voltage, "[electric_potential]", "line_voltage")
    _check(line_current, "[current]", "line_current")
    v = line_voltage.to("V").magnitude
    i = line_current.to("A").magnitude
    if v <= 0 or i <= 0:
        raise ValueError("line_voltage and line_current must be positive")
    if not 0.0 < power_factor <= 1.0:
        raise ValueError(f"power_factor must be in (0, 1]; got {power_factor}")
    return Quantity(magnitude=_SQRT3 * v * i * power_factor / 1000.0, unit="kW")


def line_current_for_power(
    *,
    real_power: Quantity,
    line_voltage: Quantity,
    power_factor: float,
) -> Quantity:
    """The line current a three-phase load draws, I = P/(√3·V_LL·cosφ) (the sizing inverse).

    The inverse of :func:`three_phase_power`: the current a load of ``real_power`` P pulls at a
    ``line_voltage`` V_LL and ``power_factor`` cosφ, I = P/(√3·V_LL·cosφ). This is the current a
    conductor and its breaker must be sized to carry. A poor power factor raises the current for the
    same real power, which is why plants correct it. Returns the current in amperes.
    """
    _check(real_power, "[power]", "real_power")
    _check(line_voltage, "[electric_potential]", "line_voltage")
    p = real_power.to("W").magnitude
    v = line_voltage.to("V").magnitude
    if p <= 0 or v <= 0:
        raise ValueError("real_power and line_voltage must be positive")
    if not 0.0 < power_factor <= 1.0:
        raise ValueError(f"power_factor must be in (0, 1]; got {power_factor}")
    return Quantity(magnitude=p / (_SQRT3 * v * power_factor), unit="A")


def conductor_resistance(
    *,
    resistivity: Quantity,
    length: Quantity,
    cross_section_area: Quantity,
) -> Quantity:
    """The DC resistance of a conductor, R = ρ·L/A.

    A wire's resistance grows with its length and shrinks with its cross-section: R = ρ·L/A, from
    the material ``resistivity`` ρ (~1.68e-8 Ω·m for copper, ~2.82e-8 for aluminum), the run
    ``length`` L (one-way), and the conductor ``cross_section_area`` A. Feed it to
    :func:`voltage_drop_three_phase`. Returns the resistance in ohms.
    """
    _check(resistivity, "[resistance]*[length]", "resistivity")
    _check(length, "[length]", "length")
    _check(cross_section_area, "[area]", "cross_section_area")
    rho = resistivity.to("ohm*m").magnitude
    lo = length.to("m").magnitude
    a = cross_section_area.to("m**2").magnitude
    if rho <= 0 or lo <= 0 or a <= 0:
        raise ValueError("resistivity, length, and cross_section_area must be positive")
    return Quantity(magnitude=rho * lo / a, unit="ohm")


def voltage_drop_three_phase(
    *,
    line_current: Quantity,
    resistance: Quantity,
    power_factor: float,
    reactance: Quantity | None = None,
) -> Quantity:
    """The voltage drop along a three-phase feeder, ΔV = √3·I·(R·cosφ + X·sinφ).

    The voltage a feeder loses carrying its current: ΔV = √3·I·(R·cosφ + X·sinφ), from the
    ``line_current`` I, the one-way conductor ``resistance`` R (from :func:`conductor_resistance`),
    the ``power_factor`` cosφ, and any conductor ``reactance`` X (often negligible on small or DC
    runs, significant on long AC feeders). Kept under ~3% of the nominal voltage, it ensures a motor
    at the far end still starts and runs. Returns the line-to-line voltage drop in volts.
    """
    _check(line_current, "[current]", "line_current")
    _check(resistance, "[resistance]", "resistance")
    i = line_current.to("A").magnitude
    r = resistance.to("ohm").magnitude
    if i <= 0 or r <= 0:
        raise ValueError("line_current and resistance must be positive")
    if not 0.0 < power_factor <= 1.0:
        raise ValueError(f"power_factor must be in (0, 1]; got {power_factor}")
    x = 0.0
    if reactance is not None:
        _check(reactance, "[resistance]", "reactance")
        x = reactance.to("ohm").magnitude
        if x < 0:
            raise ValueError("reactance must be non-negative")
    cos_phi = power_factor
    sin_phi = sqrt(max(0.0, 1.0 - power_factor**2))
    return Quantity(magnitude=_SQRT3 * i * (r * cos_phi + x * sin_phi), unit="V")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
