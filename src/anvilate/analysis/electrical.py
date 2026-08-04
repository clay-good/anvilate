"""T1 analytical electrical power-distribution checks (power, current, drop, fault, ground).

The industrial and plant engineers this library serves size motor feeders and heater circuits, and
that comes down to a few crisp relations. Three-phase real power is P = √3·V_LL·I·cosφ, so the line
current a load draws is I = P/(√3·V_LL·cosφ). A conductor's resistance is R = ρ·L/A (copper's
resistivity ρ ≈ 1.68e-8 Ω·m), and the voltage it drops carrying that current is, for a three-phase
run, ΔV = √3·I·(R·cosφ + X·sinφ) — the resistive part plus, on longer AC runs, a reactive part. The
usual acceptance check is that the drop stays under a few percent of the nominal voltage, so a motor
at the end of a long feeder still sees enough voltage to start and run.

Beyond sizing the feeder, the module also gives the transformer full-load and available fault
current that set downstream interrupting ratings, and the Dwight earthing resistance of a driven
ground rod (and rods in parallel). These are first-cut design values, not a full protection-
coordination or arc-flash study. Resistivity, reactance, power factor, and the grounding combining
factor are the caller's; inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import acos, log, pi, sqrt, tan

from ..units import Quantity

__all__ = [
    "apparent_power_three_phase",
    "conductor_resistance",
    "ground_rod_resistance",
    "line_current_for_power",
    "parallel_ground_electrodes_resistance",
    "power_factor_correction_kvar",
    "skin_depth",
    "three_phase_power",
    "transformer_available_fault_current",
    "transformer_full_load_current",
    "voltage_drop_three_phase",
]

_SQRT3 = sqrt(3.0)
_VACUUM_PERMEABILITY = 4.0e-7 * pi  # H/m (μ₀)


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


def apparent_power_three_phase(*, line_voltage: Quantity, line_current: Quantity) -> Quantity:
    """The apparent power of a three-phase load, S = √3·V_LL·I.

    The total volt-amperes a load presents, independent of power factor: S = √3·V_LL·I from the
    ``line_voltage`` V_LL and ``line_current`` I. Transformers and generators are rated in kVA
    because they must carry this full current whether or not it does real work — so apparent power,
    not real power, sizes the supply. It relates to the real power by S = P/cosφ. Returns the
    apparent power in kVA.
    """
    _check(line_voltage, "[electric_potential]", "line_voltage")
    _check(line_current, "[current]", "line_current")
    v = line_voltage.to("V").magnitude
    i = line_current.to("A").magnitude
    if v <= 0 or i <= 0:
        raise ValueError("line_voltage and line_current must be positive")
    return Quantity(magnitude=_SQRT3 * v * i / 1000.0, unit="kVA")


def power_factor_correction_kvar(
    *,
    real_power: Quantity,
    initial_power_factor: float,
    target_power_factor: float,
) -> Quantity:
    """The capacitor reactive power to raise a load's power factor, Q_c = P·(tanφ₁ − tanφ₂).

    A poor power factor makes a load draw more current (and pay demand penalties) than its real
    power warrants; a capacitor bank supplies the reactive power locally to fix it. The rating
    needed to raise the factor from ``initial_power_factor`` cosφ₁ to ``target_power_factor`` cosφ₂
    is Q_c = P·(tanφ₁ − tanφ₂), from the load's ``real_power`` P. The target must be higher than the
    initial (you correct *up* toward unity). Returns the reactive capacitor rating — numerically in
    kVAR — as a kVA-dimensioned quantity (reactive power shares the volt-ampere dimension).
    """
    _check(real_power, "[power]", "real_power")
    p = real_power.to("kW").magnitude
    if p <= 0:
        raise ValueError("real_power must be positive")
    if not 0.0 < initial_power_factor <= 1.0:
        raise ValueError(f"initial_power_factor must be in (0, 1]; got {initial_power_factor}")
    if not 0.0 < target_power_factor <= 1.0:
        raise ValueError(f"target_power_factor must be in (0, 1]; got {target_power_factor}")
    if target_power_factor <= initial_power_factor:
        raise ValueError("target_power_factor must exceed initial_power_factor (correcting upward)")
    q_c = p * (tan(acos(initial_power_factor)) - tan(acos(target_power_factor)))
    return Quantity(magnitude=q_c, unit="kVA")


def transformer_full_load_current(*, apparent_power: Quantity, line_voltage: Quantity) -> Quantity:
    """The rated secondary current of a three-phase transformer, I_FLA = S/(√3·V_LL).

    A transformer's full-load current is set by its apparent-power rating, not the load's power
    factor: I_FLA = S/(√3·V_LL), from the ``apparent_power`` S (its kVA nameplate) and the secondary
    ``line_voltage`` V_LL. It is the base the overcurrent protection is sized around and the number
    the available fault current scales from. Returns the full-load current in amperes.
    """
    _check(apparent_power, "[power]", "apparent_power")
    _check(line_voltage, "[electric_potential]", "line_voltage")
    s = apparent_power.to("VA").magnitude
    v = line_voltage.to("V").magnitude
    if s <= 0 or v <= 0:
        raise ValueError("apparent_power and line_voltage must be positive")
    return Quantity(magnitude=s / (_SQRT3 * v), unit="A")


def transformer_available_fault_current(
    *, full_load_current: Quantity, impedance_percent: float
) -> Quantity:
    """The bolted fault current at a transformer secondary, I_sc = I_FLA·(100/%Z).

    Assuming an infinite (stiff) primary source, the worst-case bolted three-phase fault current a
    transformer can deliver is set by its own impedance: I_sc = I_FLA·(100/%Z), from the
    ``full_load_current`` I_FLA and the nameplate ``impedance_percent`` %Z. This is the available
    fault current downstream equipment must be rated to interrupt — the AIC/withstand number — so a
    lower-impedance transformer (stiffer supply) drives it higher. Ignoring the source and cable
    impedance makes it conservative (an upper bound). Returns the available fault current in amps.
    """
    _check(full_load_current, "[current]", "full_load_current")
    i_fla = full_load_current.to("A").magnitude
    if i_fla <= 0:
        raise ValueError("full_load_current must be positive")
    if impedance_percent <= 0:
        raise ValueError("impedance_percent must be positive")
    return Quantity(magnitude=i_fla * 100.0 / impedance_percent, unit="A")


def ground_rod_resistance(
    *,
    soil_resistivity: Quantity,
    rod_length: Quantity,
    rod_radius: Quantity,
) -> Quantity:
    """The earthing resistance of a driven ground rod, R = ρ/(2πL)·(ln(4L/a) − 1) (Dwight/IEEE 142).

    A single vertical rod's resistance to remote earth is set mostly by the soil, not the metal:
    R = ρ/(2πL)·(ln(4L/a) − 1), from the ``soil_resistivity`` ρ (Ω·m, the dominant and highly
    variable term — ~100 for moist loam, thousands for dry sand or rock), the ``rod_length`` L, and
    the ``rod_radius`` a. Driving a rod deeper helps roughly linearly; making it fatter barely helps
    (it is inside a logarithm), which is why grounding is improved by more or longer rods, not
    fatter ones. Returns the resistance in ohms.
    """
    _check(soil_resistivity, "[resistance]*[length]", "soil_resistivity")
    _check(rod_length, "[length]", "rod_length")
    _check(rod_radius, "[length]", "rod_radius")
    rho = soil_resistivity.to("ohm*m").magnitude
    length = rod_length.to("m").magnitude
    a = rod_radius.to("m").magnitude
    if rho <= 0 or length <= 0 or a <= 0:
        raise ValueError("soil_resistivity, rod_length, and rod_radius must be positive")
    if length <= a:
        raise ValueError("rod_length must exceed rod_radius")
    return Quantity(magnitude=rho / (2.0 * pi * length) * (log(4.0 * length / a) - 1.0), unit="ohm")


def parallel_ground_electrodes_resistance(
    *,
    single_rod_resistance: Quantity,
    rod_count: int,
    arrangement_efficiency: float,
) -> Quantity:
    """The resistance of several ground rods in parallel, R_N = R₁/(N·F).

    Rods driven near each other do not combine as cleanly as ideal parallel resistors, because their
    earth shells overlap and compete for the same soil: R_N = R₁/(N·F), from the
    ``single_rod_resistance`` R₁ (from :func:`ground_rod_resistance`), the ``rod_count`` N, and an
    ``arrangement_efficiency`` F in (0, 1] — the combining factor from IEEE 142 for the spacing and
    geometry (F → 1 only when the rods are spaced several rod-lengths apart). The result is always
    above the ideal R₁/N, which is why grounding grids gain less than proportionally from added
    rods. Returns the combined resistance in ohms.
    """
    _check(single_rod_resistance, "[resistance]", "single_rod_resistance")
    if rod_count <= 0:
        raise ValueError("rod_count must be positive")
    if not 0.0 < arrangement_efficiency <= 1.0:
        raise ValueError(f"arrangement_efficiency must be in (0, 1]; got {arrangement_efficiency}")
    r1 = single_rod_resistance.to("ohm").magnitude
    if r1 <= 0:
        raise ValueError("single_rod_resistance must be positive")
    return Quantity(magnitude=r1 / (rod_count * arrangement_efficiency), unit="ohm")


def skin_depth(
    *,
    resistivity: Quantity,
    frequency: Quantity,
    relative_permeability: float = 1.0,
) -> Quantity:
    """The AC skin depth of a conductor, δ = √(ρ/(π·f·μ)).

    Alternating current does not use a conductor's full section — it crowds toward the surface, and
    the depth at which the current density has fallen to 1/e is δ = √(ρ/(π·f·μ)), from the material
    ``resistivity`` ρ, the ``frequency`` f, and the permeability μ = ``relative_permeability``·μ₀
    (μ_r = 1 for copper and aluminum, hundreds for steel). It shrinks with the square root of
    frequency: copper is ~8.5 mm deep at 60 Hz but only ~65 µm at 1 MHz, which is why high-frequency
    conductors are stranded (litz wire) or hollow, and why induction heating cooks only the surface.
    Returns the skin depth as a length.
    """
    _check(resistivity, "[resistance]*[length]", "resistivity")
    _check(frequency, "1/[time]", "frequency")
    rho = resistivity.to("ohm*m").magnitude
    f = frequency.to("Hz").magnitude
    if rho <= 0:
        raise ValueError("resistivity must be positive")
    if f <= 0:
        raise ValueError("frequency must be positive")
    if relative_permeability <= 0:
        raise ValueError("relative_permeability must be positive")
    mu = relative_permeability * _VACUUM_PERMEABILITY
    return Quantity(magnitude=sqrt(rho / (pi * f * mu)), unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
