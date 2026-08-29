"""T1 analytical modal screening (fundamental frequency, closed-form).

Resonance is a screening concern: a part whose fundamental natural frequency sits
near an operating excitation amplifies vibration. The closed forms cover the
common cases:

* a single-degree-of-freedom system (a mass ``m`` on a support of stiffness
  ``k``) resonates at ``f_n = (1/2π)·√(k/m)``;
* a structure that deflects ``δ`` under its own weight has a fundamental frequency
  estimated by the Rayleigh relation ``f_n = (1/2π)·√(g/δ)`` — no separate mass or
  stiffness needed;
* a prismatic beam with distributed mass has the exact Euler-Bernoulli
  fundamental ``f₁ = (λ₁²/2π)·√(E·I/(m̄·L⁴))``, one eigenvalue λ₁ per support
  condition (Blevins/Roark);
* a thin flat plate has the Kirchhoff fundamental ``f₁ = (γ/2π)·√(D/(μ·L⁴))``
  on the plate rigidity D and mass per area μ — γ exact for the
  simply-supported rectangle, solved at runtime from the Bessel
  characteristic equations for circles, and from finite-difference-verified
  tables for the clamped rectangle and the free-holed annulus.

Inputs are dimension-checked :class:`~anvilate.units.Quantity` values; results are
returned in hertz.
"""

from __future__ import annotations

from enum import StrEnum
from math import atan2, cos, degrees, exp, pi, radians, sin, sqrt, tan

from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity, decimals_distinguishing, require_finite
from ..units.rotation import angular_speed_rad_per_s, count_rate_per_second
from .plate import DEFAULT_POISSON_RATIO

__all__ = [
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
    "cantilever_tip_mass_frequency",
    "simply_supported_center_mass_frequency",
    "fixed_fixed_center_mass_frequency",
    "string_natural_frequency",
    "damped_natural_frequency",
    "step_response_percent_overshoot",
    "step_response_settling_time",
    "step_response_peak_time",
    "logarithmic_decrement",
    "damping_ratio_from_log_decrement",
    "quality_factor",
    "quality_factor_from_half_power_bandwidth",
    "damping_ratio_from_half_power_bandwidth",
    "critical_damping_coefficient",
    "transmissibility",
    "isolation_scorecard",
    "isolator_natural_frequency_for_transmissibility",
    "isolator_static_deflection_for_transmissibility",
    "isolator_selection_scorecard",
    "ShockRegime",
    "half_sine_shock_amplification",
    "half_sine_shock_regime",
    "half_sine_shock_scorecard",
    "dynamic_magnification_factor",
    "resonance_phase_angle",
    "base_excitation_relative_transmissibility",
    "floor_vibration_peak_acceleration_ratio",
    "simple_pendulum_period",
    "physical_pendulum_period",
    "conical_pendulum_period",
    "conical_pendulum_speed",
    "tuned_mass_damper_optimal_frequency_ratio",
    "tuned_mass_damper_optimal_damping",
    "dunkerley_fundamental_frequency",
    "cantilever_fundamental_frequency",
    "simply_supported_fundamental_frequency",
    "fixed_fixed_fundamental_frequency",
    "fixed_pinned_fundamental_frequency",
    "simply_supported_plate_fundamental_frequency",
    "clamped_plate_fundamental_frequency",
    "simply_supported_circular_plate_fundamental_frequency",
    "clamped_circular_plate_fundamental_frequency",
    "simply_supported_annular_plate_fundamental_frequency",
    "clamped_annular_plate_fundamental_frequency",
    "torsional_natural_frequency",
    "two_rotor_torsional_natural_frequency",
    "angular_acceleration_from_torque",
    "solid_disc_polar_mass_moment",
    "annular_disc_polar_mass_moment",
    "parallel_axis_mass_moment",
    "spring_surge_frequency",
    "rotating_unbalance_force",
    "balance_correction_mass",
    "balance_quality_permissible_eccentricity",
    "frequency_scorecard",
]

# Standard gravitational acceleration (m/s²), for the Rayleigh self-weight estimate.
STANDARD_GRAVITY = Quantity(magnitude=9.80665, unit="m/s**2")

# First-mode Euler-Bernoulli eigenvalues λ₁², one per support condition, each the
# first root of the characteristic transcendental equation (verified by bisection
# to machine precision): cantilever cos·cosh = −1, simply supported sin = 0 (π),
# fixed-fixed cos·cosh = 1, fixed-pinned tan = tanh.
_LAMBDA_SQ_CANTILEVER = 3.5160152685
_LAMBDA_SQ_SIMPLY_SUPPORTED = pi**2
_LAMBDA_SQ_FIXED_FIXED = 22.3732854481
_LAMBDA_SQ_FIXED_PINNED = 15.4182057170


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


def natural_frequency(*, stiffness: Quantity, mass: Quantity) -> Quantity:
    """The undamped natural frequency f_n = (1/2π)·√(k/m) of a mass-on-spring system.

    ``stiffness`` is the support stiffness k (force per unit length, e.g. a beam's
    load over its deflection); ``mass`` the supported mass m. Both must be
    positive. Returns the frequency in hertz.
    """
    _require(stiffness, "[force] / [length]", "stiffness")
    _require(mass, "[mass]", "mass")
    k = stiffness.to("N/m").magnitude
    m = mass.to("kg").magnitude
    if k <= 0 or m <= 0:
        raise ValueError("stiffness and mass must be positive")
    return Quantity(magnitude=sqrt(k / m) / (2 * pi), unit="Hz")


def natural_frequency_from_deflection(
    static_deflection: Quantity,
    *,
    gravity: Quantity = STANDARD_GRAVITY,
) -> Quantity:
    """The Rayleigh fundamental-frequency estimate f_n = (1/2π)·√(g/δ).

    ``static_deflection`` δ is the deflection the structure takes under its own
    weight; ``gravity`` defaults to standard g. Returns the frequency in hertz.
    The deflection must be positive.
    """
    _require(static_deflection, "[length]", "static_deflection")
    _require(gravity, "[acceleration]", "gravity")
    delta = static_deflection.to("m").magnitude
    g = gravity.to("m/s**2").magnitude
    if delta <= 0:
        raise ValueError(f"static_deflection must be positive; got {static_deflection}")
    return Quantity(magnitude=sqrt(g / delta) / (2 * pi), unit="Hz")


def cantilever_tip_mass_frequency(
    *,
    elastic_modulus: Quantity,
    second_moment: Quantity,
    length: Quantity,
    tip_mass: Quantity,
    beam_mass: Quantity | None = None,
) -> Quantity:
    """The fundamental frequency of a cantilever carrying a concentrated tip mass.

    A mass on the end of a cantilever beam — an accelerometer proof mass, a valve on
    a reed, an antenna on a mast — bounces on the beam's bending stiffness
    k = 3·E·I/L³ at f = (1/2π)·√(k/m_eff). The effective mass includes the tip mass
    plus the Rayleigh share of the beam's own mass, m_eff = m_tip + (33/140)·m_beam
    (the 33/140 ≈ 0.236 factor is the exact integral of the static cantilever
    deflection shape). ``elastic_modulus`` E, ``second_moment`` I, and ``length`` L
    set the stiffness, ``tip_mass`` m_tip is the end load, and ``beam_mass`` m_beam
    (default 0, the massless-beam limit) the beam's own mass. The positive quantities
    must be positive. Returns the fundamental frequency in hertz.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(second_moment, "[length]**4", "second_moment")
    _require(length, "[length]", "length")
    _require(tip_mass, "[mass]", "tip_mass")
    e = elastic_modulus.to("MPa").magnitude  # N/mm^2
    i = second_moment.to("mm**4").magnitude
    ell = length.to("mm").magnitude
    m_tip = tip_mass.to("kg").magnitude
    if e <= 0 or i <= 0 or ell <= 0:
        raise ValueError("elastic_modulus, second_moment, and length must be positive")
    if m_tip <= 0:
        raise ValueError(f"tip_mass must be positive; got {tip_mass}")
    m_beam = 0.0
    if beam_mass is not None:
        _require(beam_mass, "[mass]", "beam_mass")
        m_beam = beam_mass.to("kg").magnitude
        if m_beam < 0:
            raise ValueError(f"beam_mass must be non-negative; got {beam_mass}")
    stiffness = 3.0 * e * i / ell**3  # N/mm
    stiffness_si = stiffness * 1000.0  # N/m
    m_eff = m_tip + (33.0 / 140.0) * m_beam
    return Quantity(magnitude=sqrt(stiffness_si / m_eff) / (2 * pi), unit="Hz")


def simply_supported_center_mass_frequency(
    *,
    elastic_modulus: Quantity,
    second_moment: Quantity,
    length: Quantity,
    center_mass: Quantity,
    beam_mass: Quantity | None = None,
) -> Quantity:
    """The fundamental frequency of a simply-supported beam with a central point mass.

    A mass mounted at the middle of a simply-supported span — a motor on a beam, a
    pump on a bearer — bounces on the beam's central bending stiffness
    k = 48·E·I/L³ at f = (1/2π)·√(k/m_eff). The effective mass adds the Rayleigh share
    of the beam's own mass, m_eff = m_center + (17/35)·m_beam (the 17/35 ≈ 0.486
    factor is the exact integral of the static central-load deflection shape — a
    larger share than a cantilever's 33/140 because a simply-supported beam moves more
    of its length). ``elastic_modulus`` E, ``second_moment`` I, and ``length`` L set
    the stiffness, ``center_mass`` m_center is the mounted mass, and ``beam_mass``
    m_beam (default 0) the beam's own mass. The positive quantities must be positive.
    Returns the fundamental frequency in hertz.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(second_moment, "[length]**4", "second_moment")
    _require(length, "[length]", "length")
    _require(center_mass, "[mass]", "center_mass")
    e = elastic_modulus.to("MPa").magnitude  # N/mm^2
    i = second_moment.to("mm**4").magnitude
    ell = length.to("mm").magnitude
    m_center = center_mass.to("kg").magnitude
    if e <= 0 or i <= 0 or ell <= 0:
        raise ValueError("elastic_modulus, second_moment, and length must be positive")
    if m_center <= 0:
        raise ValueError(f"center_mass must be positive; got {center_mass}")
    m_beam = 0.0
    if beam_mass is not None:
        _require(beam_mass, "[mass]", "beam_mass")
        m_beam = beam_mass.to("kg").magnitude
        if m_beam < 0:
            raise ValueError(f"beam_mass must be non-negative; got {beam_mass}")
    stiffness_si = 48.0 * e * i / ell**3 * 1000.0  # N/m
    m_eff = m_center + (17.0 / 35.0) * m_beam
    return Quantity(magnitude=sqrt(stiffness_si / m_eff) / (2 * pi), unit="Hz")


def fixed_fixed_center_mass_frequency(
    *,
    elastic_modulus: Quantity,
    second_moment: Quantity,
    length: Quantity,
    center_mass: Quantity,
    beam_mass: Quantity | None = None,
) -> Quantity:
    """The fundamental frequency of a fixed-fixed beam with a central point mass.

    The built-in-ends counterpart of :func:`simply_supported_center_mass_frequency`:
    clamping both ends stiffens the central bending to k = 192·E·I/L³ (four times the
    simply-supported value), raising f = (1/2π)·√(k/m_eff). The effective mass adds
    the Rayleigh share m_eff = m_center + (13/35)·m_beam (the 13/35 ≈ 0.371 factor is
    the exact integral of the static fixed-fixed central-load deflection shape — a
    smaller share than the simply-supported 17/35 because the clamped ends hold more
    of the beam still). ``elastic_modulus`` E, ``second_moment`` I, ``length`` L,
    ``center_mass`` m_center, and optional ``beam_mass`` m_beam are as in
    :func:`simply_supported_center_mass_frequency`. Returns the fundamental frequency
    in hertz.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(second_moment, "[length]**4", "second_moment")
    _require(length, "[length]", "length")
    _require(center_mass, "[mass]", "center_mass")
    e = elastic_modulus.to("MPa").magnitude  # N/mm^2
    i = second_moment.to("mm**4").magnitude
    ell = length.to("mm").magnitude
    m_center = center_mass.to("kg").magnitude
    if e <= 0 or i <= 0 or ell <= 0:
        raise ValueError("elastic_modulus, second_moment, and length must be positive")
    if m_center <= 0:
        raise ValueError(f"center_mass must be positive; got {center_mass}")
    m_beam = 0.0
    if beam_mass is not None:
        _require(beam_mass, "[mass]", "beam_mass")
        m_beam = beam_mass.to("kg").magnitude
        if m_beam < 0:
            raise ValueError(f"beam_mass must be non-negative; got {beam_mass}")
    stiffness_si = 192.0 * e * i / ell**3 * 1000.0  # N/m
    m_eff = m_center + (13.0 / 35.0) * m_beam
    return Quantity(magnitude=sqrt(stiffness_si / m_eff) / (2 * pi), unit="Hz")


def string_natural_frequency(
    *,
    tension: Quantity,
    length: Quantity,
    mass_per_length: Quantity,
    mode: int = 1,
) -> Quantity:
    """The transverse natural frequency f_n = (n/2L)·√(T/μ) of a taut string.

    A stretched string or cable — a guitar string, a guyed cable, a transmission
    line — vibrates laterally at frequencies set by its tension, not its bending
    stiffness: f_n = (n/2L)·√(T/μ). ``tension`` T is the axial pull, ``length`` L the
    span between the fixed ends, ``mass_per_length`` μ the mass per unit length, and
    ``mode`` n the harmonic (1 for the fundamental, 2, 3, … for the overtones). The
    wave speed √(T/μ) rises with tension, so tightening a string sharpens its pitch;
    the overtones are exact integer multiples of the fundamental. All quantities must
    be positive and ``mode`` a positive whole number. Returns the frequency in hertz.
    """
    _require(tension, "[force]", "tension")
    _require(length, "[length]", "length")
    _require(mass_per_length, "[mass] / [length]", "mass_per_length")
    n = int(mode)
    if n != mode or n <= 0:
        raise ValueError(f"mode must be a positive whole number; got {mode}")
    t = tension.to("N").magnitude
    ell = length.to("m").magnitude
    mu = mass_per_length.to("kg/m").magnitude
    if t <= 0:
        raise ValueError(f"tension must be positive; got {tension}")
    if ell <= 0:
        raise ValueError(f"length must be positive; got {length}")
    if mu <= 0:
        raise ValueError(f"mass_per_length must be positive; got {mass_per_length}")
    return Quantity(magnitude=n / (2.0 * ell) * sqrt(t / mu), unit="Hz")


def _check_damping_ratio(damping_ratio: float) -> float:
    if not 0 <= damping_ratio < 1:
        raise ValueError(
            f"damping_ratio must lie in [0, 1) (an underdamped system); got {damping_ratio}"
        )
    return damping_ratio


def critical_damping_coefficient(*, stiffness: Quantity, mass: Quantity) -> Quantity:
    """The critical damping coefficient c_c = 2·√(k·m) of a mass-spring system.

    Critical damping is the least damping that returns a disturbed system to rest
    without overshooting — the boundary between the oscillating (underdamped) and
    creeping (overdamped) regimes. It is c_c = 2·√(k·m) = 2·m·ω_n, and every damping
    ratio is a fraction of it (ζ = c/c_c), so this is the coefficient that turns a
    target ζ into the actual dashpot rating to specify. ``stiffness`` k and ``mass``
    m must be positive. Returns c_c in newton-seconds per metre (N·s/m).
    """
    _require(stiffness, "[force] / [length]", "stiffness")
    _require(mass, "[mass]", "mass")
    k = stiffness.to("N/m").magnitude
    m = mass.to("kg").magnitude
    if k <= 0 or m <= 0:
        raise ValueError("stiffness and mass must be positive")
    return Quantity(magnitude=2.0 * sqrt(k * m), unit="N*s/m")


def damped_natural_frequency(*, natural_frequency: Quantity, damping_ratio: float) -> Quantity:
    """The damped natural frequency f_d = f_n·√(1 − ζ²) of a viscously damped system.

    A damped system oscillates a little slower than its undamped natural frequency:
    f_d = f_n·√(1 − ζ²). ``natural_frequency`` f_n is the undamped frequency (from
    :func:`natural_frequency`) and ``damping_ratio`` ζ the fraction of critical
    damping (0 ≤ ζ < 1 for the underdamped case that still oscillates). Light damping
    (ζ ≲ 0.1) barely shifts the frequency; near critical the oscillation slows toward
    zero. Returns the damped frequency in hertz.
    """
    _require(natural_frequency, "[frequency]", "natural_frequency")
    zeta = _check_damping_ratio(damping_ratio)
    fn = count_rate_per_second(natural_frequency, name="natural_frequency")
    if fn <= 0:
        raise ValueError(f"natural_frequency must be positive; got {natural_frequency}")
    return Quantity(magnitude=fn * sqrt(1.0 - zeta**2), unit="Hz")


def step_response_percent_overshoot(*, damping_ratio: float) -> float:
    """The step-response percent overshoot PO = 100·exp(−ζπ/√(1 − ζ²)).

    How far an underdamped second-order system's step response shoots past its final value, as a
    percentage, from the ``damping_ratio`` ζ: PO = 100·exp(−ζπ/√(1 − ζ²)). It depends only on ζ —
    about 16% at ζ = 0.5, under 5% by ζ = 0.7 — so ζ is chosen to trade responsiveness against
    overshoot. Returns the percent overshoot as a plain float.
    """
    zeta = _check_damping_ratio(damping_ratio)
    if zeta == 0.0:
        raise ValueError("damping_ratio must be positive for a finite overshoot")
    return 100.0 * exp(-zeta * pi / sqrt(1.0 - zeta**2))


def step_response_settling_time(*, natural_frequency: Quantity, damping_ratio: float) -> Quantity:
    """The 2% settling time t_s = 4/(ζ·ω_n) of a second-order step response.

    The time for an underdamped system's step response to settle within 2% of its final value, from
    the undamped ``natural_frequency`` f_n (ω_n = 2π·f_n) and the ``damping_ratio`` ζ:
    t_s ≈ 4/(ζ·ω_n). More damping or a higher natural frequency settles it faster. Returns the
    settling time in s.
    """
    _require(natural_frequency, "[frequency]", "natural_frequency")
    zeta = _check_damping_ratio(damping_ratio)
    fn = count_rate_per_second(natural_frequency, name="natural_frequency")
    if fn <= 0:
        raise ValueError(f"natural_frequency must be positive; got {natural_frequency}")
    if zeta == 0.0:
        raise ValueError("damping_ratio must be positive for a finite settling time")
    omega_n = 2.0 * pi * fn
    return Quantity(magnitude=4.0 / (zeta * omega_n), unit="s")


def step_response_peak_time(*, natural_frequency: Quantity, damping_ratio: float) -> Quantity:
    """The peak time t_p = π/(ω_n·√(1 − ζ²)) of a second-order step response.

    The time an underdamped system's step response takes to reach its first (highest) peak, from the
    undamped ``natural_frequency`` f_n (ω_n = 2π·f_n) and the ``damping_ratio`` ζ:
    t_p = π/(ω_n·√(1 − ζ²)) = π/ω_d, one half-period of the damped oscillation. Returns t_p in s.
    """
    _require(natural_frequency, "[frequency]", "natural_frequency")
    zeta = _check_damping_ratio(damping_ratio)
    fn = count_rate_per_second(natural_frequency, name="natural_frequency")
    if fn <= 0:
        raise ValueError(f"natural_frequency must be positive; got {natural_frequency}")
    omega_n = 2.0 * pi * fn
    return Quantity(magnitude=pi / (omega_n * sqrt(1.0 - zeta**2)), unit="s")


def logarithmic_decrement(*, damping_ratio: float) -> float:
    """The logarithmic decrement δ = 2π·ζ/√(1 − ζ²) of a damped free vibration.

    The natural log of the ratio of successive oscillation peaks — the standard way
    damping is measured from a decay trace, since ζ is hard to read directly.
    ``damping_ratio`` ζ is the fraction of critical damping (0 ≤ ζ < 1). For light
    damping δ ≈ 2π·ζ, so a decay record gives ζ ≈ δ/(2π). Returns the dimensionless
    decrement.
    """
    zeta = _check_damping_ratio(damping_ratio)
    return 2.0 * pi * zeta / sqrt(1.0 - zeta**2)


def damping_ratio_from_log_decrement(*, log_decrement: float) -> float:
    """The damping ratio ζ = δ/√(4π² + δ²) from a measured logarithmic decrement.

    The exact inverse of :func:`logarithmic_decrement`: given the ``log_decrement`` δ read from a
    free-vibration decay trace (the natural log of the ratio of two successive peaks, or 1/n times
    the log over n cycles), the fraction of critical damping is ζ = δ/√(4π² + δ²). It is the value a
    ring-down (log-decrement) test actually reports — the companion to
    :func:`damping_ratio_from_half_power_bandwidth` for the time-domain method. For light damping it
    reduces to the familiar ζ ≈ δ/(2π), but this exact form stays valid up to heavy damping.
    ``log_decrement`` must be non-negative. Returns the dimensionless damping ratio in [0, 1).
    """
    if log_decrement < 0:
        raise ValueError(f"log_decrement must be non-negative; got {log_decrement}")
    return log_decrement / sqrt(4.0 * pi**2 + log_decrement**2)


def quality_factor(*, damping_ratio: float) -> float:
    """The resonance quality factor Q = 1/(2·ζ) of a lightly damped system.

    Q measures how sharply a system resonates: it is very nearly the amplification
    of the response at resonance over the static response, and equals the resonant
    frequency divided by the −3 dB (half-power) bandwidth. For a viscously damped
    system Q = 1/(2·ζ), so light damping (small ζ) gives a tall, narrow resonance
    peak — a Q of 50 at ζ = 0.01 amplifies fiftyfold. ``damping_ratio`` ζ is the
    fraction of critical damping and must be positive (an undamped system has
    infinite Q). Returns the dimensionless quality factor.
    """
    zeta = _check_damping_ratio(damping_ratio)
    if zeta <= 0:
        raise ValueError(f"damping_ratio must be positive for a finite Q; got {zeta}")
    return 1.0 / (2.0 * zeta)


def quality_factor_from_half_power_bandwidth(
    *, resonant_frequency: Quantity, half_power_bandwidth: Quantity
) -> float:
    """The quality factor Q = f_n/Δf measured from a resonance peak.

    The experimental companion to :func:`quality_factor`: instead of a known damping ratio, it reads
    Q straight off a measured frequency response as the ``resonant_frequency`` f_n divided by the
    ``half_power_bandwidth`` Δf — the width between the two −3 dB (half-power) points either side of
    the peak. A tall, narrow resonance (small Δf) gives a high Q. It is the standard way to identify
    the sharpness of a mode from a swept-sine or FRF test. Both frequencies must be positive.
    Returns the dimensionless quality factor.
    """
    _require(resonant_frequency, "[frequency]", "resonant_frequency")
    _require(half_power_bandwidth, "[frequency]", "half_power_bandwidth")
    f_n = count_rate_per_second(resonant_frequency, name="resonant_frequency")
    delta_f = count_rate_per_second(half_power_bandwidth, name="half_power_bandwidth")
    if f_n <= 0:
        raise ValueError("resonant_frequency must be positive")
    if delta_f <= 0:
        raise ValueError("half_power_bandwidth must be positive")
    return f_n / delta_f


# The scope of the Δf/(2·f_n) half-power approximation, as its own docstring states it.
_HALF_POWER_DAMPING_LIMIT = 0.10


def damping_ratio_from_half_power_bandwidth(
    *, resonant_frequency: Quantity, half_power_bandwidth: Quantity
) -> float:
    """The damping ratio ζ = Δf/(2·f_n) from the half-power bandwidth of a resonance.

    The half-power (−3 dB) bandwidth method for identifying modal damping from a measured response:
    the fraction of critical damping is ζ = Δf/(2·f_n), from the ``half_power_bandwidth`` Δf (the
    width between the two points where the response power halves) and the ``resonant_frequency``.
    It is the inverse of the whole forward chain — the reciprocal of twice :func:`quality_factor`
    (ζ = 1/(2·Q)) — and the value a modal test reports. Valid for the light damping (ζ ≲ 0.1) where
    the half-power approximation holds. Both frequencies must be positive. Returns the dimensionless
    damping ratio.
    """
    _require(resonant_frequency, "[frequency]", "resonant_frequency")
    _require(half_power_bandwidth, "[frequency]", "half_power_bandwidth")
    f_n = count_rate_per_second(resonant_frequency, name="resonant_frequency")
    delta_f = count_rate_per_second(half_power_bandwidth, name="half_power_bandwidth")
    if f_n <= 0:
        raise ValueError("resonant_frequency must be positive")
    if delta_f <= 0:
        raise ValueError("half_power_bandwidth must be positive")
    zeta = delta_f / (2.0 * f_n)
    # This function PRODUCES a damping ratio that the rest of the module then consumes through
    # _check_damping_ratio, which requires an underdamped [0, 1). Unguarded it could hand back
    # zeta = 5.0 -- a bandwidth wider than the resonance it is measuring, which every sibling
    # refuses. The half-power approximation itself only holds for zeta <~ 0.1.
    if zeta >= 1.0:
        raise ValueError(
            f"half_power_bandwidth {half_power_bandwidth} against resonant_frequency "
            f"{resonant_frequency} gives a damping ratio of {zeta:.4f}, not the underdamped "
            f"[0, 1) the rest of this module accepts. The half-power method assumes a lightly "
            f"damped peak (zeta <~ 0.1); check that the bandwidth is the -3 dB width."
        )
    # And the approximation's OWN limit, which the docstring states and nothing enforced.
    # Δf/(2·f_n) is only the damping ratio while ζ is small: the exact half-power points sit
    # at r² = (1 − 2ζ²) ± 2ζ√(1 − ζ²), so past ζ ≈ 0.1 this OVERSTATES the damping, and
    # overstated damping understates resonant demand everywhere it is consumed. At a true
    # ζ = 0.30 it returns 0.341 and the implied peak magnification is 16% low; past
    # ζ ≈ 0.3827 the lower half-power point does not exist at all, so no measurement can
    # produce such a width.
    if zeta > _HALF_POWER_DAMPING_LIMIT:
        raise ValueError(
            f"the half-power width gives zeta = {zeta:.4f}, past the zeta <= "
            f"{_HALF_POWER_DAMPING_LIMIT:g} the approximation Δf/(2·f_n) holds for. Above it "
            f"the estimate runs high — and an overstated damping understates the resonant "
            f"response every consumer of it computes. Fit the exact half-power points, or "
            f"measure the damping another way (log decrement, free decay)."
        )
    return zeta


def _steady_state_denominator(frequency_ratio: float, damping_ratio: float, formula: str) -> float:
    """√((1 − r²)² + (2ζr)²) — the denominator every steady-state SDOF response shares.

    It is exactly zero at undamped resonance (r = 1, ζ = 0), and both values are
    in-domain: ζ = 0 is accepted, r only has to be non-negative, and r = 1 with ζ = 0 is
    the single most likely pair an engineer types when screening a mount they suspect is
    tuned into resonance. Left unguarded this was a bare ``ZeroDivisionError`` escaping
    through :func:`isolation_scorecard`, a user-facing entry point. The response really is
    unbounded there, so this refuses with the reason rather than inventing a number —
    an undamped system at resonance has no steady state to report.
    """
    r = frequency_ratio
    denominator = (1.0 - r**2) ** 2 + (2.0 * damping_ratio * r) ** 2
    if denominator == 0.0:
        raise ValueError(
            f"{formula} is unbounded at undamped resonance (frequency_ratio = "
            f"{frequency_ratio}, damping_ratio = {damping_ratio}): with no damping the "
            f"amplitude grows without limit and there is no steady-state response to "
            f"report. Supply the real damping ratio, however small."
        )
    return sqrt(denominator)


def transmissibility(*, frequency_ratio: float, damping_ratio: float) -> float:
    """The vibration transmissibility TR of a single-degree-of-freedom isolator.

    The fraction of a harmonic force (or base motion) that passes through a spring-
    and-damper isolator to (or from) the mass:

        TR = √(1 + (2·ζ·r)²) / √((1 − r²)² + (2·ζ·r)²),

    where ``frequency_ratio`` r = ω/ω_n is the forcing frequency over the mount's
    natural frequency and ``damping_ratio`` ζ the fraction of critical damping
    (0 ≤ ζ < 1). Isolation (TR < 1) only begins past r = √2 — below it the mount
    amplifies — so a soft mount (low ω_n, high r) isolates, and adding damping tames
    the resonant peak at r ≈ 1 but *worsens* the isolation at high r. r must be
    non-negative. Returns the dimensionless transmissibility.
    """
    zeta = _check_damping_ratio(damping_ratio)
    if frequency_ratio < 0:
        raise ValueError(f"frequency_ratio must be non-negative; got {frequency_ratio}")
    r = frequency_ratio
    numerator = sqrt(1.0 + (2.0 * zeta * r) ** 2)
    return numerator / _steady_state_denominator(r, zeta, "transmissibility")


def isolation_scorecard(
    name: str,
    *,
    frequency_ratio: float,
    damping_ratio: float,
    required_transmissibility: float,
) -> ScorecardEntry:
    """Screen a vibration isolator's transmissibility → a :class:`ScorecardEntry`.

    Computes :func:`transmissibility` TR at the ``frequency_ratio`` r and
    ``damping_ratio`` ζ and judges it against a target ``required_transmissibility``
    (< 1): since a lower TR is better isolation, the safety factor is
    target/TR, passing when TR is at or below the target. A mount below the isolation
    onset (r < √2) *amplifies* the disturbance — TR > 1 — and the entry says so
    explicitly rather than reporting a bare number, catching the classic error of a
    mount tuned into resonance instead of out of it. ``required_transmissibility``
    must be in (0, 1).
    """
    if not 0 < required_transmissibility < 1:
        raise ValueError(
            f"required_transmissibility must be in (0, 1); got {required_transmissibility}"
        )
    # Undamped resonance is the very error this screen exists to catch, so it is reported
    # as the worst possible verdict rather than raised: a mount at r = 1 with no damping
    # has an unbounded response, which is a FAIL with a reason, not an exception a caller
    # has to catch to find out their mount is the textbook mistake.
    if frequency_ratio == 1.0 and damping_ratio == 0.0:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.FAIL,
            detail=(
                "mount is AT undamped resonance (r = 1.00, ζ = 0): the response is "
                "unbounded, there is no transmissibility to report. Supply the real "
                "damping ratio, however small, or move the mount off the forcing frequency."
            ),
        )
    tr = transmissibility(frequency_ratio=frequency_ratio, damping_ratio=damping_ratio)
    computed = float("inf") if tr == 0 else required_transmissibility / tr
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=1.0)
    if frequency_ratio == 0.0:
        # TR is exactly 1 at r = 0 and the mount does nothing: a static load passes
        # straight through. Calling that amplification is false, and it is the one point
        # in r < √2 where it is.
        detail = (
            f"mount neither isolates nor amplifies (r = 0): transmissibility "
            f"{tr:.3f} — a static disturbance passes through undiminished, target "
            f"{required_transmissibility:.2f}"
        )
    elif frequency_ratio < sqrt(2.0):
        detail = (
            f"mount amplifies (r = {frequency_ratio:.2f} < √2): transmissibility "
            f"{tr:.{decimals_distinguishing(tr, 1.0, minimum=3)}f} > 1, "
            f"target {required_transmissibility:.2f}"
        )
    else:
        detail = f"transmissibility {tr:.3f} vs target {required_transmissibility:.2f}"
    return entry.model_copy(update={"detail": detail})


def isolator_natural_frequency_for_transmissibility(
    *, forcing_frequency: Quantity, transmissibility: float
) -> Quantity:
    """The mount natural frequency f_n = f/√(1 + 1/TR) for a target isolation.

    The design inverse of :func:`transmissibility` in the undamped isolation region:
    to pass only a fraction ``transmissibility`` TR (< 1) of a disturbance at
    ``forcing_frequency`` f, the isolator must be soft enough that its natural
    frequency is f_n = f/√(1 + 1/TR) — since undamped TR = 1/(r² − 1) with r = f/f_n.
    A smaller TR (better isolation) demands a lower f_n (a softer mount). TR must be in
    (0, 1); f_n always comes out below f/√2, the onset of isolation. Returns f_n in hertz.
    """
    if not forcing_frequency.has_dimension("[frequency]"):
        raise ValueError(
            f"forcing_frequency must be a [frequency] quantity; got "
            f"{forcing_frequency.dimensionality} ({forcing_frequency})"
        )
    if not 0 < transmissibility < 1:
        raise ValueError(
            f"transmissibility must be in (0, 1) for isolation; got {transmissibility}"
        )
    f = count_rate_per_second(forcing_frequency, name="forcing_frequency")
    if f <= 0:
        raise ValueError(f"forcing_frequency must be positive; got {forcing_frequency}")
    ratio = sqrt(1.0 + 1.0 / transmissibility)
    return Quantity(magnitude=f / ratio, unit="Hz")


def isolator_static_deflection_for_transmissibility(
    *,
    forcing_frequency: Quantity,
    transmissibility: float,
    gravity: Quantity = STANDARD_GRAVITY,
) -> Quantity:
    """The isolator static deflection δ = g/(2π·f_n)² for a target transmissibility.

    How soft a mount to pick, expressed as its static (self-weight) deflection — the
    number an isolator is chosen by. Combining
    :func:`isolator_natural_frequency_for_transmissibility` (f_n for the target ``transmissibility``
    TR at the ``forcing_frequency`` f) with the mass-on-spring relation f_n = (1/2π)·√(g/δ)
    gives δ = g/(2π·f_n)². Softer mounts (larger δ) isolate better; a stiff mount cannot.
    ``gravity`` defaults to standard g. Returns the static deflection in mm.
    """
    natural_frequency = isolator_natural_frequency_for_transmissibility(
        forcing_frequency=forcing_frequency, transmissibility=transmissibility
    )
    if not gravity.has_dimension("[acceleration]"):
        raise ValueError(
            f"gravity must be an [acceleration] quantity; got {gravity.dimensionality} ({gravity})"
        )
    fn = count_rate_per_second(natural_frequency, name="natural_frequency")
    g = gravity.to("m/s**2").magnitude
    omega_n = 2.0 * pi * fn
    deflection_m = g / omega_n**2
    return Quantity(magnitude=deflection_m, unit="m").to("mm")


def isolator_selection_scorecard(
    name: str,
    *,
    forcing_frequency: Quantity,
    target_transmissibility: float,
    selected_static_deflection: Quantity | None,
    gravity: Quantity = STANDARD_GRAVITY,
) -> ScorecardEntry:
    """Screen a *selected* isolator against the softness its target isolation demands.

    :func:`isolator_static_deflection_for_transmissibility` says how soft a mount has to
    be; this says whether the one on the shelf is soft enough. ``selected_static_deflection``
    δ is the mount's rated deflection under its share of the load — the number an isolator
    is bought by — and the check is δ against δ_required for ``target_transmissibility`` TR
    at ``forcing_frequency`` f. The safety factor is δ/δ_required, so a mount at exactly the
    required softness reads 1.00.

    Softness is the whole lever: f_n = (1/2π)·√(g/δ) falls as δ rises, and TR falls with
    f_n. A mount half as soft as required does not deliver "half the isolation" — it can sit
    the machine back inside the amplification region, which is why the detail reports the
    natural frequency the selection actually buys alongside the transmissibility it reaches.

    ``selected_static_deflection`` of ``None`` — no isolator picked yet — is
    ``NOT_EVALUATED``, never a silent pass.
    """
    if selected_static_deflection is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no isolator selected",
        )
    _require(selected_static_deflection, "[length]", "selected_static_deflection")
    delta = selected_static_deflection.to("mm").magnitude
    if delta <= 0:
        raise ValueError(
            f"selected_static_deflection must be positive; got {selected_static_deflection}"
        )
    required = isolator_static_deflection_for_transmissibility(
        forcing_frequency=forcing_frequency,
        transmissibility=target_transmissibility,
        gravity=gravity,
    ).to("mm")
    achieved_fn = natural_frequency_from_deflection(selected_static_deflection, gravity=gravity)
    f = count_rate_per_second(forcing_frequency, name="forcing_frequency")
    fn = count_rate_per_second(achieved_fn, name="natural_frequency")
    # The undamped TR below is unbounded when the mount lands exactly on the forcing
    # frequency — a real selection outcome, and the worst one, so it is reported rather
    # than raised. The deflection margin is still meaningful and still says FAIL.
    if f == fn:
        return ScorecardEntry.from_safety_factor(
            name, computed=delta / required.magnitude, required=1.0
        ).model_copy(
            update={
                "detail": (
                    f"selected {delta:.1f} mm against {required.magnitude:.1f} mm required "
                    f"(f_n {fn:.1f} Hz): the mount is tuned EXACTLY to the forcing "
                    f"frequency — undamped, its response is unbounded"
                )
            }
        )
    achieved_tr = transmissibility(frequency_ratio=f / fn, damping_ratio=0.0)
    entry = ScorecardEntry.from_safety_factor(
        name, computed=delta / required.magnitude, required=1.0
    )
    if f / fn < sqrt(2.0):
        reached = (
            f"the mount AMPLIFIES (f/f_n = {f / fn:.2f} < √2, TR = {achieved_tr:.2f}) — "
            f"it is not an isolator at this speed"
        )
    else:
        reached = f"reaching TR {achieved_tr:.3f} against a target of {target_transmissibility:.2f}"
    return entry.model_copy(
        update={
            "detail": (
                f"selected {delta:.1f} mm against {required.magnitude:.1f} mm required "
                f"(f_n {fn:.1f} Hz), {reached}"
            )
        }
    )


class ShockRegime(StrEnum):
    """Which part of the shock spectrum a pulse-to-period ratio τ/T falls in.

    The half-sine shock response spectrum has three recognizable stretches, and which one
    a mount sits in decides what a stiffer or softer mount would do to it — which is the
    opposite thing in two of the three.
    """

    IMPULSIVE = "impulsive"  # τ/T < 0.25: pulse over before the mass responds; A < 1
    AMPLIFYING = "amplifying"  # 0.25 ≤ τ/T ≤ 2: A > 1, peaking at 1.77 near τ/T = 0.8
    QUASI_STATIC = "quasi_static"  # τ/T > 2: the mass follows the pulse, A → 1


# The regime seams, in τ/T. Both are conventions on a smooth curve, not physical
# discontinuities: the amplification passes 1.0 at τ/T ≈ 0.27 and decays as 1 + 1/(2·τ/T)
# past the peak, reaching 1.27 at τ/T = 2 and 1.05 at τ/T = 10.
_SHOCK_IMPULSIVE_LIMIT = 0.25
_SHOCK_QUASI_STATIC_LIMIT = 2.0


def half_sine_shock_regime(*, pulse_duration: Quantity, natural_frequency: Quantity) -> ShockRegime:
    """Which shock regime a half-sine pulse of ``pulse_duration`` puts a mount in.

    The ratio that decides everything is τ/T = τ·f_n — the pulse duration over the mount's
    natural period. Below 0.25 the pulse is finished before the mass has moved and the mount
    attenuates it; past 2 the mass simply follows the pulse; in between it amplifies. See
    :func:`half_sine_shock_amplification` for the number, and :class:`ShockRegime` for what
    each label means. Both arguments must be positive.
    """
    ratio = _shock_pulse_ratio(pulse_duration, natural_frequency)
    if ratio < _SHOCK_IMPULSIVE_LIMIT:
        return ShockRegime.IMPULSIVE
    if ratio > _SHOCK_QUASI_STATIC_LIMIT:
        return ShockRegime.QUASI_STATIC
    return ShockRegime.AMPLIFYING


def _shock_pulse_ratio(pulse_duration: Quantity, natural_frequency: Quantity) -> float:
    """τ/T = τ·f_n, the one ratio the half-sine shock spectrum depends on."""
    _require(pulse_duration, "[time]", "pulse_duration")
    _require(natural_frequency, "[frequency]", "natural_frequency")
    tau = pulse_duration.to("s").magnitude
    # count_rate_per_second, not .to("Hz"): a natural frequency is a count rate, and the
    # 2π between it and an angular rate is the trap this helper exists to close.
    fn = count_rate_per_second(natural_frequency, name="natural_frequency")
    if tau <= 0:
        raise ValueError(f"pulse_duration must be positive; got {pulse_duration}")
    if fn <= 0:
        raise ValueError(f"natural_frequency must be positive; got {natural_frequency}")
    return tau * fn


def half_sine_shock_amplification(
    *, pulse_duration: Quantity, natural_frequency: Quantity
) -> float:
    """The undamped maximax shock amplification A of a half-sine pulse (the SRS ordinate).

    A drop test, a slam, a transport shock: the base delivers a half-sine acceleration pulse
    of peak a₀ over ``pulse_duration`` τ, and an undamped mount of ``natural_frequency`` f_n
    sees a peak response of A·a₀. Everything depends on the single ratio ρ = τ·f_n = τ/T:

        residual (after the pulse)   A_res = 4ρ·|cos(πρ)| / |4ρ² − 1|
        primary  (during the pulse)  A_pri = max_n |sin(2πn/(1 + β))| / (1 − β),  β = 1/(2ρ),
                                     over the integers 1 ≤ n ≤ (1 + β)/(2β)

    and A is the larger of the two (the primary branch is empty for ρ ≤ 0.5, where the pulse
    ends before the response turns over, and ρ = 0.5 is the removable singularity at which
    both branches meet at π/2). Both come from the exact Duhamel solution, not a table.

    The shape is the useful part. A rises roughly as 4ρ through the impulsive regime, peaks at
    **1.77 near ρ = 0.8**, and decays toward 1 — so softening a mount is the right move only
    on the far side of the peak. Move a mount from ρ = 3 to ρ = 0.8 in the name of "more
    isolation" and the shock it passes goes *up* by half. Undamped, which is the conservative
    reading for a shock: damping trims the peak by a few percent and does nothing impulsive.

    Returns the dimensionless amplification A (a factor on the pulse's peak, not a stress).
    """
    rho = _shock_pulse_ratio(pulse_duration, natural_frequency)
    beta = 1.0 / (2.0 * rho)
    # ρ = 1/2 is the resonant coincidence p = ω_n: both closed forms have a removable
    # singularity there, and the limit — reached by L'Hôpital on either — is exactly π/2.
    if abs(beta - 1.0) < 1e-12:
        return pi / 2.0
    residual = 4.0 * rho * abs(cos(pi * rho)) / abs(4.0 * rho**2 - 1.0)
    if beta >= 1.0:
        # ρ < 1/2: the pulse ends before the first stationary point, so nothing during it
        # can exceed what rings out after — the residual branch is the whole spectrum.
        return residual
    turns = int((1.0 + beta) / (2.0 * beta))
    primary = 0.0
    if turns >= 1:
        primary = max(abs(sin(2.0 * pi * n / (1.0 + beta))) for n in range(1, turns + 1)) / (
            1.0 - beta
        )
    return max(primary, residual)


def half_sine_shock_scorecard(
    name: str,
    *,
    peak_acceleration: Quantity,
    pulse_duration: Quantity,
    natural_frequency: Quantity,
    allowable_acceleration: Quantity | None,
) -> ScorecardEntry:
    """Screen a half-sine shock pulse against a mount's allowable acceleration → an entry.

    Multiplies the pulse's ``peak_acceleration`` a₀ by the amplification A from
    :func:`half_sine_shock_amplification` and screens the response A·a₀ against
    ``allowable_acceleration``. The detail names the :class:`ShockRegime` alongside the
    numbers, because the regime is what tells a reader which way to move the mount — the
    same "make it softer" that fixes a quasi-static shock makes an amplifying one worse.

    ``allowable_acceleration`` of ``None`` — no shock rating supplied — is ``NOT_EVALUATED``
    rather than a silent pass.
    """
    if allowable_acceleration is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no allowable shock acceleration supplied",
            reference="half-sine shock response spectrum",
        )
    _require(peak_acceleration, "[acceleration]", "peak_acceleration")
    _require(allowable_acceleration, "[acceleration]", "allowable_acceleration")
    a0 = abs(peak_acceleration.to("m/s**2").magnitude)
    allowable = allowable_acceleration.to("m/s**2").magnitude
    if allowable <= 0:
        raise ValueError(f"allowable_acceleration must be positive; got {allowable_acceleration}")
    amplification = half_sine_shock_amplification(
        pulse_duration=pulse_duration, natural_frequency=natural_frequency
    )
    regime = half_sine_shock_regime(
        pulse_duration=pulse_duration, natural_frequency=natural_frequency
    )
    response = amplification * a0
    # A zero pulse is a check with nothing to evaluate, not one that passed.
    computed = None if response == 0 else allowable / response
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=1.0)
    ratio = _shock_pulse_ratio(pulse_duration, natural_frequency)
    return entry.model_copy(
        update={
            "detail": (
                f"{regime.value} (τ/T = {ratio:.2f}), amplification {amplification:.2f}: "
                f"response {response / STANDARD_GRAVITY.to('m/s**2').magnitude:.1f} g "
                f"vs allowable "
                f"{allowable / STANDARD_GRAVITY.to('m/s**2').magnitude:.1f} g"
            ),
            "reference": "half-sine shock response spectrum",
        }
    )


def dynamic_magnification_factor(*, frequency_ratio: float, damping_ratio: float) -> float:
    """The steady-state dynamic magnification factor of a forced SDOF system.

    How much a harmonic force of amplitude F₀ amplifies the static deflection F₀/k it
    would make if applied slowly:

        M = 1 / √((1 − r²)² + (2·ζ·r)²),

    with ``frequency_ratio`` r = ω/ω_n the forcing frequency over the natural
    frequency and ``damping_ratio`` ζ the fraction of critical damping (0 ≤ ζ < 1).
    Well below resonance (r → 0) M → 1 (the load acts quasi-statically); at resonance
    (r ≈ 1) it peaks near 1/(2ζ) = the :func:`quality_factor`; well above (r ≫ 1) the
    mass cannot follow the force and M → 0. Unlike :func:`transmissibility` (what a
    mount passes on) this is the response *of* the driven mass itself. r must be
    non-negative. Returns the dimensionless magnification factor.
    """
    zeta = _check_damping_ratio(damping_ratio)
    if frequency_ratio < 0:
        raise ValueError(f"frequency_ratio must be non-negative; got {frequency_ratio}")
    r = frequency_ratio
    return 1.0 / _steady_state_denominator(r, zeta, "dynamic_magnification_factor")


def resonance_phase_angle(*, frequency_ratio: float, damping_ratio: float) -> float:
    """The steady-state phase lag of a forced SDOF response behind the driving force.

    A harmonically driven mass does not move in step with the force: it lags by

        φ = atan2(2·ζ·r, 1 − r²),

    with ``frequency_ratio`` r = ω/ω_n and ``damping_ratio`` ζ (0 ≤ ζ < 1). Well
    below resonance (r → 0) the response is in phase (φ → 0°); at resonance (r = 1)
    it lags exactly 90° whatever the damping — the tell-tale of resonance; well above
    (r ≫ 1) it is 180° out of phase, moving opposite the force. The quadrant-aware
    atan2 keeps φ climbing smoothly through 90° past r = 1 (rather than wrapping). r
    must be non-negative. Returns the phase lag in degrees (0 to 180).
    """
    zeta = _check_damping_ratio(damping_ratio)
    if frequency_ratio < 0:
        raise ValueError(f"frequency_ratio must be non-negative; got {frequency_ratio}")
    r = frequency_ratio
    return degrees(atan2(2.0 * zeta * r, 1.0 - r**2))


def base_excitation_relative_transmissibility(
    *, frequency_ratio: float, damping_ratio: float
) -> float:
    """The relative-motion response of a base-excited SDOF — the seismic-instrument ratio.

    When the *base* of a spring-mass-damper is shaken by a harmonic motion of
    amplitude Y, the mass's motion *relative to the base* has amplitude

        |X_rel / Y| = r² / √((1 − r²)² + (2·ζ·r)²),

    with ``frequency_ratio`` r = ω/ω_n and ``damping_ratio`` ζ (0 ≤ ζ < 1). This is
    the transfer function a seismic instrument reads with its relative-displacement
    pickup, and it has two useful regimes: well below resonance (r ≪ 1) it tends to
    r², so the reading is proportional to the base *acceleration* (the accelerometer
    regime), while well above (r ≫ 1) it tends to 1, reading the base *displacement*
    directly (the seismometer/vibrometer regime). At resonance (r = 1) it peaks at
    1/(2ζ). Distinct from :func:`transmissibility`, which is the *absolute* motion the
    mass takes on. r must be non-negative. Returns the dimensionless ratio.
    """
    zeta = _check_damping_ratio(damping_ratio)
    if frequency_ratio < 0:
        raise ValueError(f"frequency_ratio must be non-negative; got {frequency_ratio}")
    r = frequency_ratio
    return r**2 / _steady_state_denominator(r, zeta, "base_excitation_relative_transmissibility")


def floor_vibration_peak_acceleration_ratio(
    *,
    fundamental_frequency: Quantity,
    effective_panel_weight: Quantity,
    damping_ratio: float,
    constant_force: Quantity,
) -> float:
    """The AISC/CISC Design Guide 11 walking-vibration ratio a_p/g = P₀·e^(−0.35·fₙ)/(β·W).

    The serviceability check that governs most long-span steel floors: a person walking excites the
    floor's fundamental mode, and the resulting peak acceleration (as a fraction of g) is compared
    to a comfort limit (~0.005 for offices and residences, ~0.015 for shopping malls and
    footbridges). ``fundamental_frequency`` fₙ is the floor system's first natural frequency (from
    :func:`simply_supported_fundamental_frequency` or a modal estimate), ``effective_panel_weight``
    W the weight of the vibrating floor panel (dead plus a fraction of live), ``damping_ratio`` β
    the modal damping (0.02 bare, up to ~0.05 with partitions and fit-out), and ``constant_force``
    P₀ the DG11 walking-force constant for the occupancy. A stiff, heavy, well-damped floor keeps
    the ratio low; a light, springy one fails even when it is plenty strong. Returns the a_p/g.
    """
    _require(fundamental_frequency, "1/[time]", "fundamental_frequency")
    _require(effective_panel_weight, "[force]", "effective_panel_weight")
    _require(constant_force, "[force]", "constant_force")
    fn = count_rate_per_second(fundamental_frequency, name="fundamental_frequency")
    w = effective_panel_weight.to("kN").magnitude
    p0 = constant_force.to("kN").magnitude
    if fn <= 0:
        raise ValueError("fundamental_frequency must be positive")
    if w <= 0 or p0 <= 0:
        raise ValueError("effective_panel_weight and constant_force must be positive")
    beta = _check_damping_ratio(damping_ratio)
    if beta <= 0:
        raise ValueError("damping_ratio must be positive (an undamped floor never settles)")
    return p0 * exp(-0.35 * fn) / (beta * w)


def simple_pendulum_period(*, length: Quantity, gravity: Quantity = STANDARD_GRAVITY) -> Quantity:
    """The small-swing period T = 2π·√(L/g) of a simple pendulum.

    A point mass on a light cord swings at a period set only by its length, not its
    mass or its amplitude (in the small-angle limit): T = 2π·√(L/g). ``length`` L is
    the cord length and ``gravity`` g defaults to standard g. This is the metronome /
    escapement / seconds-pendulum relation — a 1 m pendulum swings in about 2 s.
    ``length`` must be positive. Returns the period in seconds.
    """
    _require(length, "[length]", "length")
    _require(gravity, "[acceleration]", "gravity")
    ell = length.to("m").magnitude
    g = gravity.to("m/s**2").magnitude
    if ell <= 0:
        raise ValueError(f"length must be positive; got {length}")
    return Quantity(magnitude=2.0 * pi * sqrt(ell / g), unit="s")


def physical_pendulum_period(
    *,
    moment_of_inertia: Quantity,
    mass: Quantity,
    pivot_distance: Quantity,
    gravity: Quantity = STANDARD_GRAVITY,
) -> Quantity:
    """The small-swing period T = 2π·√(I/(m·g·d)) of a physical (rigid-body) pendulum.

    A rigid body pivoted off its centre of mass swings at T = 2π·√(I/(m·g·d)), where
    ``moment_of_inertia`` I is the mass moment of inertia *about the pivot*, ``mass``
    m the body mass, ``pivot_distance`` d the distance from the pivot to the centre of
    mass, and ``gravity`` g. A compound pendulum, a swinging linkage, or a tilt gauge
    follows this; it reduces to the simple pendulum when the mass concentrates at the
    end (I = m·d²). All quantities must be positive. Returns the period in seconds.
    """
    _require(moment_of_inertia, "[mass] * [length]**2", "moment_of_inertia")
    _require(mass, "[mass]", "mass")
    _require(pivot_distance, "[length]", "pivot_distance")
    _require(gravity, "[acceleration]", "gravity")
    inertia = moment_of_inertia.to("kg*m**2").magnitude
    m = mass.to("kg").magnitude
    d = pivot_distance.to("m").magnitude
    g = gravity.to("m/s**2").magnitude
    if min(inertia, m, d) <= 0:
        raise ValueError("moment_of_inertia, mass, and pivot_distance must be positive")
    return Quantity(magnitude=2.0 * pi * sqrt(inertia / (m * g * d)), unit="s")


def conical_pendulum_period(
    *, string_length: Quantity, half_angle: float, gravity: Quantity = STANDARD_GRAVITY
) -> Quantity:
    """The period of a conical pendulum, T = 2π·√(L·cos θ/g).

    Unlike a plane pendulum, a conical pendulum sweeps a horizontal circle at a fixed angle to the
    vertical — a governor fly-ball, a tetherball, a swing-ride. Its period is T = 2π·√(L·cos θ/g),
    from the ``string_length`` L, the cone ``half_angle`` θ (degrees from vertical), and ``gravity``
    g. Only the *vertical* projection L·cos θ sets the period, so a wider swing (larger θ) speeds it
    up, and as θ → 90° the period collapses toward zero. ``half_angle`` is in [0, 90). Returns the
    period in seconds.
    """
    _require(string_length, "[length]", "string_length")
    _require(gravity, "[acceleration]", "gravity")
    ell = string_length.to("m").magnitude
    g = gravity.to("m/s**2").magnitude
    if ell <= 0:
        raise ValueError("string_length must be positive")
    if not 0.0 <= half_angle < 90.0:
        raise ValueError("half_angle must be in [0, 90) degrees")
    return Quantity(magnitude=2.0 * pi * sqrt(ell * cos(radians(half_angle)) / g), unit="s")


def conical_pendulum_speed(
    *, string_length: Quantity, half_angle: float, gravity: Quantity = STANDARD_GRAVITY
) -> Quantity:
    """The orbital speed of a conical pendulum, v = √(g·L·sin θ·tan θ).

    How fast the bob travels around its horizontal circle of radius r = L·sin θ: balancing the
    string tension's horizontal component against the centripetal demand gives
    v = √(g·L·sin θ·tan θ), from the ``string_length`` L, the ``half_angle`` θ (degrees), and
    ``gravity``
    g. A steeper cone (larger θ) both widens the circle and demands more speed to hold it — which is
    how a centrifugal governor converts speed into fly-ball angle. ``half_angle`` is in [0, 90).
    Returns the orbital speed in m/s.
    """
    _require(string_length, "[length]", "string_length")
    _require(gravity, "[acceleration]", "gravity")
    ell = string_length.to("m").magnitude
    g = gravity.to("m/s**2").magnitude
    if ell <= 0:
        raise ValueError("string_length must be positive")
    if not 0.0 <= half_angle < 90.0:
        raise ValueError("half_angle must be in [0, 90) degrees")
    theta = radians(half_angle)
    return Quantity(magnitude=sqrt(g * ell * sin(theta) * tan(theta)), unit="m/s")


def _check_mass_ratio(mass_ratio: float) -> float:
    if mass_ratio <= 0:
        raise ValueError(f"mass_ratio must be positive; got {mass_ratio}")
    return mass_ratio


def tuned_mass_damper_optimal_frequency_ratio(*, mass_ratio: float) -> float:
    """The Den Hartog optimal tuning f = 1/(1 + μ) of a tuned mass damper.

    A tuned mass damper (vibration absorber) is a small mass-spring-damper hung on a
    resonating structure to soak up its motion — the pendulum in a skyscraper, the
    absorber on an engine. Den Hartog's optimum tunes the absorber's natural
    frequency slightly *below* the main system's: the ratio of absorber to main
    natural frequency is f_opt = 1/(1 + μ), where ``mass_ratio`` μ is the absorber
    mass over the main (modal) mass. A heavier absorber (larger μ) tunes lower and
    suppresses more. ``mass_ratio`` must be positive. Returns the dimensionless
    optimal frequency ratio.
    """
    mu = _check_mass_ratio(mass_ratio)
    return 1.0 / (1.0 + mu)


def tuned_mass_damper_optimal_damping(*, mass_ratio: float) -> float:
    """The Den Hartog optimal damping ζ = √(3μ / (8·(1 + μ)³)) of a tuned mass damper.

    The absorber's own damping ratio that, paired with the optimal tuning
    (:func:`tuned_mass_damper_optimal_frequency_ratio`), flattens the main system's
    resonant response to its lowest peak: ζ_opt = √(3·μ / (8·(1 + μ)³)), where
    ``mass_ratio`` μ is the absorber-to-main mass ratio. Too little damping leaves
    two sharp peaks; too much locks the absorber to the structure — this value sits
    at the minimum. A 5% mass ratio wants about 13% damping. ``mass_ratio`` must be
    positive. Returns the dimensionless optimal damping ratio.
    """
    mu = _check_mass_ratio(mass_ratio)
    return sqrt(3.0 * mu / (8.0 * (1.0 + mu) ** 3))


def dunkerley_fundamental_frequency(individual_frequencies: list[Quantity]) -> Quantity:
    """The Dunkerley fundamental-frequency estimate for a multi-mass system,
    1/f² = Σ 1/fᵢ².

    A shaft or beam carrying several masses vibrates slower than any single mass
    would alone. Dunkerley's method combines each mass's stand-alone frequency fᵢ
    (the frequency the system would have with only that mass present, from
    :func:`natural_frequency` or :func:`natural_frequency_from_deflection`) into a
    lower-bound estimate of the true fundamental — the standard hand estimate for a
    shaft's first critical (whirl) speed with multiple discs. ``individual_
    frequencies`` is the non-empty list of the fᵢ, each a positive frequency.
    Returns the combined frequency in hertz; it always falls below the lowest fᵢ.
    """
    if not individual_frequencies:
        raise ValueError("individual_frequencies must be a non-empty list")
    inverse_squares = 0.0
    for i, freq in enumerate(individual_frequencies):
        _require(freq, "[frequency]", f"individual_frequencies[{i}]")
        f = count_rate_per_second(freq, name=f"individual_frequencies[{i}]")
        if f <= 0:
            raise ValueError(f"each individual frequency must be positive; got {freq}")
        inverse_squares += 1.0 / f**2
    return Quantity(magnitude=1.0 / sqrt(inverse_squares), unit="Hz")


def _beam_fundamental(
    lambda_sq: float,
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    _require(mass_per_length, "[mass] / [length]", "mass_per_length")
    _require(length, "[length]", "length")
    _require(second_moment, "[length]**4", "second_moment")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    m = mass_per_length.to("kg/m").magnitude
    length_m = length.to("m").magnitude
    inertia = second_moment.to("m**4").magnitude
    e = elastic_modulus.to("Pa").magnitude
    if m <= 0 or length_m <= 0 or inertia <= 0 or e <= 0:
        raise ValueError("mass_per_length, length, second_moment, and E must be positive")
    return Quantity(
        magnitude=lambda_sq * sqrt(e * inertia / (m * length_m**4)) / (2 * pi), unit="Hz"
    )


def cantilever_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a cantilever with distributed mass (Blevins).

    Exact Euler-Bernoulli first mode f₁ = (λ₁²/2π)·√(E·I/(m̄·L⁴)) with
    λ₁² = 3.51602 (the first root of cos λ·cosh λ = −1). ``mass_per_length``
    m̄ is the beam's mass per unit length, self-weight plus any smeared
    attachments. Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_CANTILEVER,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def simply_supported_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a simply-supported beam with distributed mass.

    Exact Euler-Bernoulli first mode f₁ = (π²/2π)·√(E·I/(m̄·L⁴)) — the one
    support with a clean closed-form eigenvalue (λ₁ = π). Exceeds the Rayleigh
    self-weight estimate from the mid-span deflection by exactly
    π²/√(384/5) ≈ 1.126. Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_SIMPLY_SUPPORTED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def fixed_fixed_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a fixed-fixed beam with distributed mass.

    Exact Euler-Bernoulli first mode with λ₁² = 22.37329 (the first root of
    cos λ·cosh λ = 1) — building in both ends raises the fundamental 2.27×
    over the simply-supported span. Returns hertz; every argument is
    dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_FIXED_FIXED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


def fixed_pinned_fundamental_frequency(
    *,
    mass_per_length: Quantity,
    length: Quantity,
    second_moment: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a propped cantilever with distributed mass.

    Exact Euler-Bernoulli first mode with λ₁² = 15.41821 (the first root of
    tan λ = tanh λ), between the simply-supported and fixed-fixed values.
    Returns hertz; every argument is dimension-checked.
    """
    return _beam_fundamental(
        _LAMBDA_SQ_FIXED_PINNED,
        mass_per_length=mass_per_length,
        length=length,
        second_moment=second_moment,
        elastic_modulus=elastic_modulus,
    )


# Clamped-rectangle fundamental coefficients γ = ω·b²·√(μ/D), keyed by b/a
# (short/long side, so 0 is the infinite strip — exactly the fixed-fixed beam
# eigenvalue, the plate stiffening entering only through D's 1/(1−ν²)).
# Interior values from our own finite-difference biharmonic eigensolve
# (13-point stencil, ghost-point clamped edges, Richardson extrapolation over
# paired grids; two independent grid pairs agree to ≤0.02%, and the square
# matches the published Leissa value 35.992 to 0.03%). The knots are denser
# at the slender end, where the approach to the strip limit is from above and
# curved.
_CLAMPED_PLATE_GAMMA = (
    # (b/a, gamma)
    (0.0, _LAMBDA_SQ_FIXED_FIXED),
    (0.2, 22.632),
    (0.25, 22.798),
    (1 / 3.0, 23.196),
    (0.4, 23.643),
    (0.5, 24.577),
    (1 / 1.8, 25.254),
    (1 / 1.6, 26.282),
    (1 / 1.4, 27.930),
    (1 / 1.2, 30.751),
    (1.0, 35.982),
)


def _bessel_j0_j1_i0_i1(x: float) -> tuple[float, float, float, float]:
    """(J₀, J₁, I₀, I₁) by power series — machine-precision for the x ≲ 4 used here."""
    j0 = j1 = i0 = i1 = 0.0
    half = x / 2
    term0 = 1.0  # (x/2)^(2k) / (k!)² at k = 0
    for k in range(40):
        term1 = term0 * half / (k + 1)  # (x/2)^(2k+1) / (k!·(k+1)!)
        sign = -1.0 if k % 2 else 1.0
        j0 += sign * term0
        i0 += term0
        j1 += sign * term1
        i1 += term1
        term0 *= half * half / (k + 1) ** 2
    return j0, j1, i0, i1


def _circular_plate_lambda_sq(*, clamped: bool, poisson_ratio: float) -> float:
    """The first eigenvalue λ² = ω·R²·√(μ/D) of a circular plate, by bisection.

    The mode shape A·J₀(λr/R) + B·I₀(λr/R) gives the exact characteristic
    equations J₀(λ)·I₁(λ) + I₀(λ)·J₁(λ) = 0 for a clamped rim (first root
    λ² = 10.2158, ν-independent) and J₁/J₀ + I₁/I₀ = 2λ/(1 − ν) for a simply
    supported one (λ² = 4.935 at ν = 0.3) — solved here rather than read from
    a table.
    """
    if clamped:

        def f(lam: float) -> float:
            j0, j1, i0, i1 = _bessel_j0_j1_i0_i1(lam)
            return j0 * i1 + i0 * j1

        lo, hi = 2.5, 3.5
    else:
        # The root always lies below J₀'s first zero (2.40483), where J₁/J₀
        # blows up positive; at λ → 0⁺ the left side trails 2λ/(1 − ν).
        def f(lam: float) -> float:
            j0, j1, i0, i1 = _bessel_j0_j1_i0_i1(lam)
            return j1 / j0 + i1 / i0 - 2 * lam / (1 - poisson_ratio)

        lo, hi = 1e-6, 2.4048
    f_lo = f(lo)
    for _ in range(100):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return ((lo + hi) / 2) ** 2


def _plate_mass_and_rigidity(
    mass_per_area: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float,
) -> tuple[float, float]:
    """Validate the shared plate-modal arguments -> (μ kg/m², D N·m)."""
    _require(mass_per_area, "[mass] / [length] ** 2", "mass_per_area")
    _require(thickness, "[length]", "thickness")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 < poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in (0, 0.5); got {poisson_ratio}")
    mu = mass_per_area.to("kg/m**2").magnitude
    t = thickness.to("m").magnitude
    e = elastic_modulus.to("Pa").magnitude
    if mu <= 0 or t <= 0 or e <= 0:
        raise ValueError("mass_per_area, thickness, and E must be positive")
    return mu, e * t**3 / (12 * (1 - poisson_ratio**2))


def _rect_plate_sides(length: Quantity, width: Quantity) -> tuple[float, float]:
    """Validate rectangular plan sides -> (a, b) in metres with b the short side."""
    _require(length, "[length]", "length")
    _require(width, "[length]", "width")
    a = length.to("m").magnitude
    b = width.to("m").magnitude
    if a <= 0 or b <= 0:
        raise ValueError("length and width must be positive")
    return (a, b) if a >= b else (b, a)


def simply_supported_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a simply-supported rectangular plate (exact).

    A thin flat plate of plan ``length`` a × ``width`` b, simply supported on
    all edges, with ``mass_per_area`` μ (self-weight ρ·t plus any smeared
    attachments) — the one plate with a clean closed-form eigenvalue:
    f₁ = (π/2)·(1/a² + 1/b²)·√(D/μ) on the rigidity D = E·t³/(12·(1 − ν²)).
    A wide strip recovers the simply-supported beam's π² eigenvalue, stiffened
    by exactly 1/√(1 − ν²) through D. Returns hertz; every quantity argument
    is dimension-checked and ν must lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    a, b = _rect_plate_sides(length, width)
    return Quantity(magnitude=(pi / 2) * (1 / a**2 + 1 / b**2) * sqrt(rigidity / mu), unit="Hz")


def clamped_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    length: Quantity,
    width: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a rectangular plate with all edges clamped.

    A thin flat plate of plan ``length`` × ``width`` with all four edges built
    in and ``mass_per_area`` μ: f₁ = (γ/2π)·√(D/(μ·b⁴)) with b the short side
    and γ interpolated from a finite-difference-verified eigenvalue table
    (22.373, the exact fixed-fixed beam value, at the strip limit; 35.98 for
    the square — clamping raises the square's fundamental 1.82× over simply
    supported). Returns hertz; every quantity argument is dimension-checked
    and ν must lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    a, b = _rect_plate_sides(length, width)
    ratio = b / a
    for (r_lo, g_lo), (r_hi, g_hi) in zip(
        _CLAMPED_PLATE_GAMMA, _CLAMPED_PLATE_GAMMA[1:], strict=False
    ):
        if ratio <= r_hi:
            gamma = g_lo + (ratio - r_lo) / (r_hi - r_lo) * (g_hi - g_lo)
            break
    return Quantity(magnitude=gamma / (2 * pi) * sqrt(rigidity / (mu * b**4)), unit="Hz")


def simply_supported_circular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a circular plate simply supported at its rim.

    A round plate of ``diameter`` 2R resting on a gasket or ledge, with
    ``mass_per_area`` μ: f₁ = (λ²/2π)·√(D/(μ·R⁴)), λ² solved at runtime from
    the exact Bessel characteristic equation J₁/J₀ + I₁/I₀ = 2λ/(1 − ν)
    (λ² = 4.935 at ν = 0.3 — some handbooks print 4.977, which our Rayleigh
    bound rules out). Returns hertz; every quantity argument is
    dimension-checked and ν must lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    radius = _positive_radius(diameter)
    lam_sq = _circular_plate_lambda_sq(clamped=False, poisson_ratio=poisson_ratio)
    return Quantity(magnitude=lam_sq / (2 * pi) * sqrt(rigidity / (mu * radius**4)), unit="Hz")


def clamped_circular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = DEFAULT_POISSON_RATIO,
) -> Quantity:
    """The fundamental frequency of a circular plate clamped at its rim.

    A round plate of ``diameter`` 2R welded or stiffly bolted all around, with
    ``mass_per_area`` μ: f₁ = (λ²/2π)·√(D/(μ·R⁴)), λ² = 10.2158 solved at
    runtime from the exact characteristic equation J₀·I₁ + I₀·J₁ = 0 — the
    eigenvalue is ν-independent (ν enters only through D), and clamping the
    rim raises the fundamental 2.07× over the gasketed plate at ν = 0.3.
    Returns hertz; every quantity argument is dimension-checked and ν must
    lie in (0, 0.5).
    """
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, poisson_ratio
    )
    radius = _positive_radius(diameter)
    lam_sq = _circular_plate_lambda_sq(clamped=True, poisson_ratio=poisson_ratio)
    return Quantity(magnitude=lam_sq / (2 * pi) * sqrt(rigidity / (mu * radius**4)), unit="Hz")


def _positive_radius(diameter: Quantity) -> float:
    """Validate a plate diameter -> radius in metres."""
    _require(diameter, "[length]", "diameter")
    radius = diameter.to("m").magnitude / 2
    if radius <= 0:
        raise ValueError(f"diameter must be positive; got {diameter}")
    return radius


# Annular-plate (free inner edge) fundamental coefficients γ = ω·R²·√(μ/D)
# with R the OUTER radius, keyed by the hole ratio b/a, at ν = 0.3 (the free
# inner edge's moment condition makes the eigenvalue ν-dependent, so the
# table pins the same ν the static tables use). Values from our own
# finite-difference eigensolve of the axisymmetric plate ODE (ghost-point
# BCs, Richardson over paired grids; the n = 150/300 and n = 400/800 pairs
# agree to ≤0.02%, and b/a → 0 approaches the exact solid-plate roots that
# open each table). Both families are NON-monotonic near small holes — a
# mid-size hole removes mass faster than stiffness and LOWERS the
# simply-supported fundamental below the solid plate's.
_ANNULAR_PLATE_GAMMA_SS = (
    # (b/a, gamma)
    (0.0, 4.9351),
    (0.05, 4.912),
    (0.1, 4.853),
    (0.15, 4.782),
    (0.2, 4.718),
    (0.25, 4.675),
    (0.3, 4.664),
    (0.35, 4.692),
    (0.4, 4.764),
    (0.45, 4.889),
    (0.5, 5.076),
    (0.55, 5.344),
    (0.6, 5.710),
    (0.65, 6.220),
    (0.7, 6.930),
    (0.75, 7.962),
    (0.8, 9.548),
)
_ANNULAR_PLATE_GAMMA_CLAMPED = (
    (0.0, 10.2158),
    (0.05, 10.189),
    (0.1, 10.159),
    (0.15, 10.210),
    (0.2, 10.408),
    (0.25, 10.799),
    (0.3, 11.424),
    (0.35, 12.334),
    (0.4, 13.602),
    (0.45, 15.339),
    (0.5, 17.714),
    (0.55, 21.006),
    (0.6, 25.674),
    (0.65, 32.537),
    (0.7, 43.142),
    (0.75, 60.730),
    (0.8, 93.035),
)


def _annular_plate_fundamental(
    table: tuple[tuple[float, float], ...],
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    # The table is computed at ν = 0.3, so the rigidity pins the same value.
    mu, rigidity = _plate_mass_and_rigidity(
        mass_per_area, thickness, elastic_modulus, DEFAULT_POISSON_RATIO
    )
    radius = _positive_radius(diameter)
    _require(hole_diameter, "[length]", "hole_diameter")
    hole_radius = hole_diameter.to("m").magnitude / 2
    ratio = hole_radius / radius
    if not 0 < ratio <= table[-1][0]:
        raise ValueError(
            f"the hole ratio {ratio:.2f} must lie in (0, {table[-1][0]}] — "
            "the encoded eigenvalue range"
        )
    for (r_lo, g_lo), (r_hi, g_hi) in zip(table, table[1:], strict=False):
        if ratio <= r_hi:
            gamma = g_lo + (ratio - r_lo) / (r_hi - r_lo) * (g_hi - g_lo)
            break
    return Quantity(magnitude=gamma / (2 * pi) * sqrt(rigidity / (mu * radius**4)), unit="Hz")


def simply_supported_annular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a simply-supported annular plate (free hole).

    A round plate of ``diameter`` 2R with a concentric free-edged hole of
    ``hole_diameter`` 2b, simply supported at its rim, with ``mass_per_area``
    μ: f₁ = (γ/2π)·√(D/(μ·R⁴)), γ interpolated from our
    finite-difference-verified eigenvalue table (ν = 0.3, hole ratio up to
    0.8). Counter-intuitively a mid-size hole LOWERS the fundamental (γ dips
    to 4.66 at b/a = 0.3 against the solid plate's 4.94) — the hole sheds
    mass faster than bending stiffness until it starts crowding the rim.
    Returns hertz; every quantity argument is dimension-checked.
    """
    return _annular_plate_fundamental(
        _ANNULAR_PLATE_GAMMA_SS,
        mass_per_area=mass_per_area,
        diameter=diameter,
        hole_diameter=hole_diameter,
        thickness=thickness,
        elastic_modulus=elastic_modulus,
    )


def clamped_annular_plate_fundamental_frequency(
    *,
    mass_per_area: Quantity,
    diameter: Quantity,
    hole_diameter: Quantity,
    thickness: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The fundamental frequency of a clamped-rim annular plate (free hole).

    A round plate of ``diameter`` 2R with a concentric free-edged hole of
    ``hole_diameter`` 2b, its outer rim built in, with ``mass_per_area`` μ:
    f₁ = (γ/2π)·√(D/(μ·R⁴)), γ interpolated from our
    finite-difference-verified eigenvalue table (ν = 0.3, hole ratio up to
    0.8; 10.2158 at the solid limit, rising steeply once the hole crowds the
    clamped rim — 4.2× the solid eigenvalue at b/a = 0.7). Returns hertz;
    every quantity argument is dimension-checked.
    """
    return _annular_plate_fundamental(
        _ANNULAR_PLATE_GAMMA_CLAMPED,
        mass_per_area=mass_per_area,
        diameter=diameter,
        hole_diameter=hole_diameter,
        thickness=thickness,
        elastic_modulus=elastic_modulus,
    )


def angular_acceleration_from_torque(*, torque: Quantity, moment_of_inertia: Quantity) -> Quantity:
    """The angular acceleration a torque produces, α = τ/I (Newton's second law for rotation).

    The rotational analogue of a = F/m: a net ``torque`` τ on a body of mass ``moment_of_inertia`` I
    spins it up at α = τ/I. It is how a motor's torque and a rotor's inertia set the spin-up rate,
    how long a drive takes to reach speed, and the deceleration a brake torque imposes — the same
    inertia (from :func:`solid_disc_polar_mass_moment` or :func:`parallel_axis_mass_moment`) that
    resists it. Returns the angular acceleration in rad/s².
    """
    _require(torque, "[force] * [length]", "torque")
    _require(moment_of_inertia, "[mass] * [length]**2", "moment_of_inertia")
    t = torque.to("N*m").magnitude
    i = moment_of_inertia.to("kg*m**2").magnitude
    if i <= 0:
        raise ValueError(f"moment_of_inertia must be positive; got {moment_of_inertia}")
    return Quantity(magnitude=t / i, unit="rad/s**2")


def solid_disc_polar_mass_moment(*, mass: Quantity, diameter: Quantity) -> Quantity:
    """The polar mass moment of inertia I = m·d²/8 (= m·r²/2) of a solid disc.

    The rotary inertia of a flywheel, coupling, or brake disc about the shaft
    axis — the mass term of a torsional resonance. ``mass`` and ``diameter``
    must be positive. Returns kg·m²; both arguments are dimension-checked.
    """
    _require(mass, "[mass]", "mass")
    _require(diameter, "[length]", "diameter")
    m = mass.to("kg").magnitude
    d = diameter.to("m").magnitude
    if m <= 0 or d <= 0:
        raise ValueError("mass and diameter must be positive")
    return Quantity(magnitude=m * d**2 / 8, unit="kg*m**2")


def parallel_axis_mass_moment(
    *, centroidal_moment: Quantity, mass: Quantity, axis_distance: Quantity
) -> Quantity:
    """The parallel-axis theorem, I = I_cm + m·d².

    Shifts a mass moment of inertia from a body's own centre of mass to any parallel axis a
    distance away: I = I_cm + m·d², from the ``centroidal_moment`` I_cm (the moment about the
    centroidal axis, e.g. from :func:`solid_disc_polar_mass_moment`), the ``mass`` m, and the
    ``axis_distance`` d between the two axes. The added m·d² term is always positive, so the
    centroidal axis is the one of least inertia and any offset raises it — the reason a disc swung
    about its rim (I = 1.5·m·r²) resists rotation three times as much as about its centre, and the
    step that turns a compound pendulum's or an unbalanced rotor's centroidal inertia into its
    inertia about the actual pivot. Returns the shifted mass moment in kg·m².
    """
    _require(centroidal_moment, "[mass]*[length]**2", "centroidal_moment")
    _require(mass, "[mass]", "mass")
    _require(axis_distance, "[length]", "axis_distance")
    i_cm = centroidal_moment.to("kg*m**2").magnitude
    m = mass.to("kg").magnitude
    d = axis_distance.to("m").magnitude
    if i_cm < 0:
        raise ValueError("centroidal_moment must be non-negative")
    if m <= 0:
        raise ValueError("mass must be positive")
    if d < 0:
        raise ValueError("axis_distance must be non-negative")
    return Quantity(magnitude=i_cm + m * d**2, unit="kg*m**2")


def annular_disc_polar_mass_moment(
    *, mass: Quantity, outer_diameter: Quantity, inner_diameter: Quantity
) -> Quantity:
    """The polar mass moment of inertia I = m·(D² + d²)/8 (= m·(R² + r²)/2) of an
    annular disc or hollow cylinder.

    The rotary inertia of a bored flywheel, a rim, or a pulley about its axis — the
    hollow counterpart of :func:`solid_disc_polar_mass_moment`. It sums the mean-square
    radius of the outer and inner circles: I = m·(D² + d²)/8, which recovers the solid
    disc as the bore vanishes (d → 0) and tends to the thin-rim m·R² as d → D.
    ``mass`` m is the actual (bored) mass, ``outer_diameter`` D, and ``inner_diameter``
    d (non-negative and below D). Because it piles mass at large radius, an annular
    disc of the same mass carries far more inertia than a solid one — the flywheel
    designer's lever. Returns kg·m²; the quantities are dimension-checked.
    """
    _require(mass, "[mass]", "mass")
    _require(outer_diameter, "[length]", "outer_diameter")
    _require(inner_diameter, "[length]", "inner_diameter")
    m = mass.to("kg").magnitude
    do = outer_diameter.to("m").magnitude
    di = inner_diameter.to("m").magnitude
    if m <= 0:
        raise ValueError(f"mass must be positive; got {mass}")
    if not 0 <= di < do:
        raise ValueError(
            f"inner_diameter ({inner_diameter}) must be non-negative and below "
            f"outer_diameter ({outer_diameter})"
        )
    return Quantity(magnitude=m * (do**2 + di**2) / 8, unit="kg*m**2")


def torsional_natural_frequency(
    *,
    torsional_stiffness: Quantity,
    polar_mass_moment: Quantity,
) -> Quantity:
    """The torsional natural frequency f_n = (1/2π)·√(k_t/I) of a disc on a shaft.

    The rotational counterpart of :func:`natural_frequency`: a rotary inertia
    ``polar_mass_moment`` I (e.g. :func:`solid_disc_polar_mass_moment`) on a
    shaft of ``torsional_stiffness`` k_t (torque per radian of twist, e.g.
    :func:`anvilate.analysis.shaft_torsional_stiffness`) resonates in twist at
    f_n — the drivetrain mode that torque pulsation (engine firing, VFD
    ripple) excites. Both must be positive. Returns hertz.
    """
    _require(torsional_stiffness, "[force] * [length]", "torsional_stiffness")
    _require(polar_mass_moment, "[mass] * [length]**2", "polar_mass_moment")
    k = torsional_stiffness.to("N*m").magnitude
    inertia = polar_mass_moment.to("kg*m**2").magnitude
    if k <= 0 or inertia <= 0:
        raise ValueError("torsional_stiffness and polar_mass_moment must be positive")
    return Quantity(magnitude=sqrt(k / inertia) / (2 * pi), unit="Hz")


def two_rotor_torsional_natural_frequency(
    *,
    torsional_stiffness: Quantity,
    polar_mass_moment_1: Quantity,
    polar_mass_moment_2: Quantity,
) -> Quantity:
    """The torsional natural frequency of a two-disc (two-rotor) drivetrain.

    An engine and its flywheel, a motor and its load — two rotary inertias joined by
    a shaft twist against *each other* (a free-free torsional system, no fixed end),
    with a stationary node somewhere along the shaft. The single non-zero mode is

        f_n = (1/2π)·√(k_t·(I₁ + I₂)/(I₁·I₂)),

    equivalently f_n = (1/2π)·√(k_t/I_eq) with the reduced inertia
    I_eq = I₁·I₂/(I₁ + I₂). ``torsional_stiffness`` k_t is the connecting shaft's
    torque-per-radian, ``polar_mass_moment_1`` I₁ and ``polar_mass_moment_2`` I₂ the
    two rotary inertias (e.g. :func:`solid_disc_polar_mass_moment`). As one inertia
    grows without bound I_eq → the smaller, recovering the fixed-end single-disc
    :func:`torsional_natural_frequency`. All three must be positive. Returns hertz.
    """
    _require(torsional_stiffness, "[force] * [length]", "torsional_stiffness")
    _require(polar_mass_moment_1, "[mass] * [length]**2", "polar_mass_moment_1")
    _require(polar_mass_moment_2, "[mass] * [length]**2", "polar_mass_moment_2")
    k = torsional_stiffness.to("N*m").magnitude
    i1 = polar_mass_moment_1.to("kg*m**2").magnitude
    i2 = polar_mass_moment_2.to("kg*m**2").magnitude
    if k <= 0 or i1 <= 0 or i2 <= 0:
        raise ValueError("torsional_stiffness and both polar mass moments must be positive")
    reduced = i1 * i2 / (i1 + i2)
    return Quantity(magnitude=sqrt(k / reduced) / (2 * pi), unit="Hz")


def spring_surge_frequency(*, spring_rate: Quantity, spring_mass: Quantity) -> Quantity:
    """The spring surge (axial resonance) frequency f₁ = (1/2)·√(k/m).

    A helical compression spring between parallel seats is a distributed
    elastic rod fixed at both ends, so its first axial mode is exactly
    f₁ = (1/2)·√(k/m) on its ``spring_rate`` k and its OWN ``spring_mass`` m —
    exactly π× the SDOF (1/2π)·√(k/m) shortcut. A cam lobe or load pulsation
    near f₁ (or a strong harmonic of the drive landing on it) makes the coils
    surge and the spring momentarily lose control of what it holds. Returns
    hertz; both arguments are dimension-checked and must be positive.
    """
    _require(spring_rate, "[force] / [length]", "spring_rate")
    _require(spring_mass, "[mass]", "spring_mass")
    k = spring_rate.to("N/m").magnitude
    m = spring_mass.to("kg").magnitude
    if k <= 0 or m <= 0:
        raise ValueError("spring_rate and spring_mass must be positive")
    return Quantity(magnitude=sqrt(k / m) / 2, unit="Hz")


def rotating_unbalance_force(
    *, unbalance_mass: Quantity, eccentricity: Quantity, rotational_speed: Quantity
) -> Quantity:
    """The centrifugal force F = m·e·ω² a residual rotor unbalance throws.

    An imperfectly balanced rotor carries an effective ``unbalance_mass`` m at an
    ``eccentricity`` e from the spin axis, and it slings that mass outward with a rotating
    force m·e·ω² at the ``rotational_speed`` ω — the force that shakes the bearings and the
    frame, once per revolution. The ω² lever is unforgiving: doubling the speed quadruples
    the shake, which is why high-speed rotors are balanced to a tight residual m·e. All
    positive; ω is a rotational frequency. Returns the force in N.
    """
    _require(unbalance_mass, "[mass]", "unbalance_mass")
    _require(eccentricity, "[length]", "eccentricity")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    m = unbalance_mass.to("kg").magnitude
    e = eccentricity.to("m").magnitude
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    if m <= 0 or e <= 0 or omega <= 0:
        raise ValueError("unbalance_mass, eccentricity, and rotational_speed must be positive")
    return Quantity(magnitude=m * e * omega**2, unit="N")


def balance_correction_mass(
    *, unbalance_mass: Quantity, eccentricity: Quantity, correction_radius: Quantity
) -> Quantity:
    """The counterweight m_c = m·e/r_c that balances a rotor unbalance.

    Balancing nulls the unbalance U = m·e (mass times eccentricity, e.g. g·mm) with an equal
    and opposite one, so a counterweight placed at ``correction_radius`` r_c opposite the
    heavy spot needs mass m_c = ``unbalance_mass``·``eccentricity``/r_c — a small mass far out
    or a large mass close in, the same U either way. This is speed-independent: balance is a
    geometry (m·e) problem, and once U is nulled the centrifugal force
    (:func:`rotating_unbalance_force`) vanishes at every speed. All positive. Returns the
    correction mass in g.
    """
    _require(unbalance_mass, "[mass]", "unbalance_mass")
    _require(eccentricity, "[length]", "eccentricity")
    _require(correction_radius, "[length]", "correction_radius")
    m = unbalance_mass.to("kg").magnitude
    e = eccentricity.to("m").magnitude
    r = correction_radius.to("m").magnitude
    if m <= 0 or e <= 0 or r <= 0:
        raise ValueError("unbalance_mass, eccentricity, and correction_radius must be positive")
    return Quantity(magnitude=m * e / r, unit="kg").to("g")


def balance_quality_permissible_eccentricity(
    *, balance_grade: float, rotational_speed: Quantity
) -> Quantity:
    """The permissible residual eccentricity e_per = G/ω for an ISO 1940 balance grade.

    ISO 1940 grades a rotor's balance by the product of its residual eccentricity and its
    service speed, e·ω = G (a constant rim velocity in mm/s), so the permissible residual
    eccentricity at the ``rotational_speed`` ω is e_per = ``balance_grade`` G / ω. Common
    grades are G6.3 for pumps and general machinery, G2.5 for machine-tool spindles and
    turbines, and G1.0 or finer for high-speed spindles — a smaller G is a finer balance.
    The 1/ω dependence means the *same* grade allows less eccentricity the faster the rotor
    runs, which is why high-speed rotors are balanced so precisely. ``balance_grade`` (the
    G-number in mm/s) must be positive and ω a positive rotational frequency. Returns e_per
    in micrometres.
    """
    if balance_grade <= 0:
        raise ValueError(f"balance_grade must be positive; got {balance_grade}")
    _require(rotational_speed, "[frequency]", "rotational_speed")
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    if omega <= 0:
        raise ValueError(f"rotational_speed must be positive; got {rotational_speed}")
    # G is in mm/s; e_per = G/omega in mm, converted to micrometres.
    return Quantity(magnitude=balance_grade / omega, unit="mm").to("um")


def frequency_scorecard(
    name: str,
    *,
    frequency: Quantity,
    min_frequency: Quantity | None,
) -> ScorecardEntry:
    """Screen a fundamental ``frequency`` against a required minimum for resonance.

    To avoid resonance a part's fundamental frequency should sit above the highest
    operating excitation, so this is ``PASS`` when ``frequency`` is at least
    ``min_frequency`` and ``FAIL`` below it. When ``min_frequency`` is ``None`` — no
    excitation requirement was declared — the entry is ``NOT_EVALUATED`` rather than
    a silent pass. Both quantities must be frequencies.
    """
    _require(frequency, "[frequency]", "frequency")
    if min_frequency is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — minimum frequency unavailable",
        )
    _require(min_frequency, "[frequency]", "min_frequency")
    fn = count_rate_per_second(frequency, name="frequency")
    floor = count_rate_per_second(min_frequency, name="min_frequency")
    status = CheckStatus.PASS if fn >= floor else CheckStatus.FAIL
    return ScorecardEntry(
        name=name,
        status=status,
        detail=f"fundamental {fn:.1f} Hz vs required minimum {floor:.1f} Hz",
    )
