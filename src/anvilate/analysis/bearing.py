"""T1 analytical rolling-bearing life (ISO 281 basic rating life, closed-form).

A rolling bearing does not have a static strength limit so much as a *life*: run
long enough under load and its raceways spall by rolling-contact fatigue. The
ISO 281 basic rating life L10 — the life 90% of a population reaches before the
first spall — follows a simple power law in the load,

    L10 = (C/P)^p   [millions of revolutions]

where C is the bearing's *dynamic load rating* (the load giving one million
revolutions of L10, a catalogue value), P the equivalent dynamic load actually
carried, and p the life exponent: 3 for ball bearings, 10/3 for roller bearings.
Expressed as running hours at a shaft speed n, L10h = (10⁶/60·n)·(C/P)^p.

The dynamic load rating C is manufacturer- and design-specific, so — like a
material allowable — it is supplied as an argument, not read from the standards
:class:`~anvilate.standards.Bearing` table (which carries only ISO 15 boundary
dimensions). As with the other checks, force and speed inputs are dimension-checked
:class:`~anvilate.units.Quantity` values through Pint.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log

from ..units import Quantity, require_finite
from ..units.rotation import revolutions_per_minute, revolutions_per_second

# ISO 281 life exponents: the load-life power law L10 = (C/P)^p.
BALL_BEARING_LIFE_EXPONENT = 3.0
ROLLER_BEARING_LIFE_EXPONENT = 10.0 / 3.0

# Weibull dispersion exponent for rolling-bearing life scatter (ISO 281): the
# reliability-adjustment a1 = (ln(1/R)/ln(1/0.90))^(1/e) with e ≈ 1.5 reproduces the
# standard a1 table (0.62 at 95%, 0.21 at 99%).
BEARING_WEIBULL_SLOPE = 1.5

__all__ = [
    "BALL_BEARING_LIFE_EXPONENT",
    "ROLLER_BEARING_LIFE_EXPONENT",
    "bearing_cubic_mean_load",
    "BEARING_WEIBULL_SLOPE",
    "bearing_basic_rating_life",
    "bearing_rating_for_life",
    "bearing_life_hours",
    "bearing_static_safety_factor",
    "bearing_equivalent_dynamic_load",
    "bearing_equivalent_static_load",
    "bearing_reliability_life_factor",
    "bearing_ball_pass_frequency_outer",
    "bearing_ball_pass_frequency_inner",
    "bearing_fundamental_train_frequency",
    "bearing_ball_spin_frequency",
]


def bearing_cubic_mean_load(
    *,
    duty_cycle: Sequence[tuple[float, Quantity]],
    life_exponent: float = BALL_BEARING_LIFE_EXPONENT,
) -> Quantity:
    """The equivalent constant load of a varying duty, P_m = (Σ f_i·P_iᵖ)^(1/p).

    :func:`bearing_life_hours` and :func:`bearing_basic_rating_life` take a single equivalent
    load, but real machines run a duty cycle — a press that idles, forms, and returns. The
    natural shortcut is to average the loads, and it is wrong in the unsafe direction.

    Life goes as P^−p, so damage accumulates with the p-th power of load and the heavy blocks
    dominate far beyond their share of the time. Weighting by time in that same power gives the
    constant load that does equal damage. For a duty of 50% at 4 kN, 30% at 8 kN and 20% at
    12 kN, the cubic mean is 8.099 kN against a linear mean of 6.800 kN — and since life goes as
    the cube, the linear mean predicts **1.69× the true L10 life**. The gap widens as the load
    spread grows.

    ``duty_cycle`` is a sequence of (time_fraction, load) pairs whose fractions sum to 1.
    ``life_exponent`` p is 3 for ball bearings (the default) and 10/3 for roller bearings — use
    :data:`ROLLER_BEARING_LIFE_EXPONENT`. Returns the equivalent load as a force.
    """
    if not isinstance(duty_cycle, Sequence):
        raise ValueError(f"duty_cycle must be a sequence, not a single value; got {duty_cycle!r}")
    if len(duty_cycle) == 0:
        raise ValueError("duty_cycle must contain at least one block")
    if life_exponent <= 0:
        raise ValueError(f"life_exponent must be positive; got {life_exponent}")
    total_fraction = 0.0
    accumulated = 0.0
    for index, block in enumerate(duty_cycle):
        if not isinstance(block, Sequence) or len(block) != 2:
            raise ValueError(
                f"duty_cycle[{index}] must be a (time fraction, load) pair; got {block!r}"
            )
        fraction, load = block
        _require(load, "[force]", "duty_cycle load")
        newtons = load.to("N").magnitude
        if fraction < 0:
            raise ValueError(f"duty_cycle time fractions must be non-negative; got {fraction}")
        if newtons < 0:
            raise ValueError(f"duty_cycle loads must be non-negative; got {load}")
        total_fraction += fraction
        accumulated += fraction * newtons**life_exponent
    if abs(total_fraction - 1.0) > 1.0e-9:
        raise ValueError(f"duty_cycle time fractions must sum to 1; they sum to {total_fraction}")
    return Quantity(magnitude=accumulated ** (1.0 / life_exponent), unit="N")


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


def _defect_frequency_inputs(
    rotational_frequency: Quantity,
    number_of_rolling_elements: int,
    rolling_element_diameter: Quantity,
    pitch_diameter: Quantity,
    contact_angle: float,
) -> tuple[float, int, float]:
    """Validate the shared inputs and return (f_r in rev/s, N_b, ratio (d/D)·cos φ)."""
    from math import cos, radians

    _require(rotational_frequency, "[frequency]", "rotational_frequency")
    _require(rolling_element_diameter, "[length]", "rolling_element_diameter")
    _require(pitch_diameter, "[length]", "pitch_diameter")
    fr = revolutions_per_second(rotational_frequency, name="rotational_frequency")
    d = rolling_element_diameter.to("mm").magnitude
    pd = pitch_diameter.to("mm").magnitude
    if fr < 0:
        raise ValueError("rotational_frequency must be non-negative")
    if number_of_rolling_elements < 1:
        raise ValueError("number_of_rolling_elements must be at least 1")
    if d <= 0 or pd <= 0:
        raise ValueError("rolling_element_diameter and pitch_diameter must be positive")
    if d >= pd:
        raise ValueError("rolling_element_diameter must be smaller than pitch_diameter")
    if not -90.0 < contact_angle < 90.0:
        raise ValueError(f"contact_angle must be in (-90, 90) degrees; got {contact_angle}")
    return fr, number_of_rolling_elements, (d / pd) * cos(radians(contact_angle))


def bearing_basic_rating_life(
    *,
    dynamic_load_rating: Quantity,
    equivalent_load: Quantity,
    life_exponent: float = BALL_BEARING_LIFE_EXPONENT,
) -> float:
    """The ISO 281 basic rating life L10 = (C/P)^p, in **millions of revolutions**.

    ``dynamic_load_rating`` C is the bearing's catalogue dynamic capacity and
    ``equivalent_load`` P the equivalent dynamic radial load it carries (both
    forces); ``life_exponent`` p is 3 for ball bearings
    (:data:`BALL_BEARING_LIFE_EXPONENT`) or 10/3 for roller bearings
    (:data:`ROLLER_BEARING_LIFE_EXPONENT`). The load-life law is steep — halving the
    load raises a ball bearing's life eightfold. Returns the dimensionless L10 in
    millions of revolutions; both loads must be positive and ``life_exponent``
    positive.
    """
    _require(dynamic_load_rating, "[force]", "dynamic_load_rating")
    _require(equivalent_load, "[force]", "equivalent_load")
    c = dynamic_load_rating.to("N").magnitude
    p = equivalent_load.to("N").magnitude
    if c <= 0:
        raise ValueError(f"dynamic_load_rating must be positive; got {dynamic_load_rating}")
    if p <= 0:
        raise ValueError(f"equivalent_load must be positive; got {equivalent_load}")
    if life_exponent <= 0:
        raise ValueError(f"life_exponent must be positive; got {life_exponent}")
    return (c / p) ** life_exponent


def bearing_rating_for_life(
    *,
    equivalent_load: Quantity,
    required_life_millions: float,
    life_exponent: float = BALL_BEARING_LIFE_EXPONENT,
) -> Quantity:
    """The dynamic rating C = P·L10^(1/p) a target rating life requires — the selection step.

    The bearing-selection inverse of :func:`bearing_basic_rating_life`: to reach a
    ``required_life_millions`` L10 (millions of revolutions) under an ``equivalent_load`` P,
    the catalogue dynamic capacity must be at least C = P·L10^(1/p), with ``life_exponent`` p
    = 3 for ball or 10/3 for roller bearings. Pick the smallest catalogue bearing whose C
    meets this. The steep 1/p exponent means a long life demands only a modestly bigger C
    (tenfold life needs about 2.15× the rating for a ball bearing) — but it climbs fast if the
    load is high. P must be positive, L10 and p positive. Returns the required rating in N.
    """
    _require(equivalent_load, "[force]", "equivalent_load")
    p_load = equivalent_load.to("N").magnitude
    if p_load <= 0:
        raise ValueError(f"equivalent_load must be positive; got {equivalent_load}")
    if required_life_millions <= 0:
        raise ValueError(f"required_life_millions must be positive; got {required_life_millions}")
    if life_exponent <= 0:
        raise ValueError(f"life_exponent must be positive; got {life_exponent}")
    return Quantity(magnitude=p_load * required_life_millions ** (1.0 / life_exponent), unit="N")


def bearing_life_hours(
    *,
    dynamic_load_rating: Quantity,
    equivalent_load: Quantity,
    speed: Quantity,
    life_exponent: float = BALL_BEARING_LIFE_EXPONENT,
) -> Quantity:
    """The ISO 281 basic rating life expressed in running **hours** at a speed.

    L10h = (10⁶/(60·n))·(C/P)^p converts the basic rating life
    (:func:`bearing_basic_rating_life`, in millions of revolutions) to service
    hours at shaft speed ``speed`` n. The load and exponent arguments are as there;
    ``speed`` must be a positive rotational frequency (rpm or rad/s). Returns the
    life in hours.
    """
    life_mrev = bearing_basic_rating_life(
        dynamic_load_rating=dynamic_load_rating,
        equivalent_load=equivalent_load,
        life_exponent=life_exponent,
    )
    _require(speed, "[frequency]", "speed")
    rpm = revolutions_per_minute(speed, name="speed")
    if rpm <= 0:
        raise ValueError(f"speed must be positive; got {speed}")
    hours = life_mrev * 1.0e6 / (60.0 * rpm)
    return Quantity(magnitude=hours, unit="hour")


def bearing_static_safety_factor(
    *,
    static_load_rating: Quantity,
    equivalent_static_load: Quantity,
) -> float:
    """The static load safety factor s₀ = C₀/P₀ of a rolling bearing.

    Alongside the L10 dynamic life, a bearing must survive its heaviest *static*
    (or slow, shock) load without brinelling the raceways. The static safety factor
    is the basic static load rating ``static_load_rating`` C₀ (a catalogue value)
    over the equivalent static load ``equivalent_static_load`` P₀ actually applied.
    Typical minimums are s₀ ≈ 1–2 for smooth-running bearings and up to 3+ where
    shock or quiet running matters. Both loads must be positive forces. Returns the
    dimensionless s₀.
    """
    _require(static_load_rating, "[force]", "static_load_rating")
    _require(equivalent_static_load, "[force]", "equivalent_static_load")
    c0 = static_load_rating.to("N").magnitude
    p0 = equivalent_static_load.to("N").magnitude
    if c0 <= 0:
        raise ValueError(f"static_load_rating must be positive; got {static_load_rating}")
    if p0 <= 0:
        raise ValueError(f"equivalent_static_load must be positive; got {equivalent_static_load}")
    return c0 / p0


def bearing_equivalent_dynamic_load(
    *,
    radial_load: Quantity,
    axial_load: Quantity,
    radial_factor: float,
    axial_factor: float,
) -> Quantity:
    """The ISO 281 equivalent dynamic bearing load P = X·F_r + Y·F_a.

    A rolling bearing under *combined* radial and thrust load feels an equivalent
    pure-radial load P = X·F_r + Y·F_a that does the same fatigue damage — the value
    to feed :func:`bearing_basic_rating_life`. ``radial_load`` F_r and ``axial_load``
    F_a are the two load components, and ``radial_factor`` X and ``axial_factor`` Y
    the dimensionless ISO 281 combination factors, read from the bearing's table by
    the axial-to-radial ratio against its e value (supplied like any catalogue
    datum; a common pair is X = 0.56, Y ≈ 1.4–2). For pure radial load below the e
    threshold X = 1, Y = 0 and P = F_r. Both loads must be non-negative, X positive,
    and Y non-negative — Y = 0 is the pure-radial row of the table, not a bad input.
    Returns the equivalent load in newtons.
    """
    _require(radial_load, "[force]", "radial_load")
    _require(axial_load, "[force]", "axial_load")
    fr = radial_load.to("N").magnitude
    fa = axial_load.to("N").magnitude
    if fr < 0 or fa < 0:
        raise ValueError("radial_load and axial_load must be non-negative")
    if radial_factor <= 0:
        raise ValueError("radial_factor must be positive")
    if axial_factor < 0:
        raise ValueError("axial_factor must be non-negative")
    return Quantity(magnitude=radial_factor * fr + axial_factor * fa, unit="N")


def bearing_equivalent_static_load(
    *,
    radial_load: Quantity,
    axial_load: Quantity,
    radial_factor: float,
    axial_factor: float,
) -> Quantity:
    """The ISO 76 equivalent static bearing load P₀ = max(F_r, X₀·F_r + Y₀·F_a).

    The static counterpart of :func:`bearing_equivalent_dynamic_load`: the constant
    radial load that would brinell the raceways as much as the actual combined
    radial + thrust load a stationary (or slow, shock-loaded) bearing carries — the
    value to feed :func:`bearing_static_safety_factor`. It is X₀·F_r + Y₀·F_a, but
    ISO 76 floors it at the radial load itself (a combined load can never be less
    damaging than the pure radial), so P₀ = max(F_r, X₀·F_r + Y₀·F_a).
    ``radial_load`` F_r and ``axial_load`` F_a are the components, and
    ``radial_factor`` X₀ and ``axial_factor`` Y₀ the static combination factors
    (0.6 and 0.5 for a deep-groove ball bearing). Both loads must be non-negative and
    the factors positive. Returns the equivalent static load in newtons.
    """
    _require(radial_load, "[force]", "radial_load")
    _require(axial_load, "[force]", "axial_load")
    fr = radial_load.to("N").magnitude
    fa = axial_load.to("N").magnitude
    if fr < 0 or fa < 0:
        raise ValueError("radial_load and axial_load must be non-negative")
    # `max(fr, X*fr + Y*fa)` drops the combined term when either factor is NaN, so the
    # equivalent load came back as the bare radial load: 1000 N where the answer is 3100 N,
    # a 3.1x understated demand and therefore a 3.1x overstated static capacity ratio.
    require_finite(radial_factor, name="radial_factor")
    require_finite(axial_factor, name="axial_factor")
    if radial_factor <= 0 or axial_factor <= 0:
        raise ValueError("radial_factor and axial_factor must be positive")
    return Quantity(magnitude=max(fr, radial_factor * fr + axial_factor * fa), unit="N")


def bearing_reliability_life_factor(
    *, reliability: float, weibull_slope: float = BEARING_WEIBULL_SLOPE
) -> float:
    """The ISO 281 life-adjustment factor a₁ = (ln(1/R)/ln(1/0.90))^(1/e) for a
    reliability above 90%.

    The basic rating life L10 (:func:`bearing_basic_rating_life`) is the life 90% of
    bearings reach — a 10% failure probability. To design for a higher reliability R
    the life is scaled down by a₁, which follows from the Weibull scatter of bearing
    life: a₁ = (ln(1/R)/ln(1/0.90))^(1/e), with ``weibull_slope`` e ≈ 1.5. This
    reproduces the standard ISO 281 a₁ table — 1.0 at 90%, 0.62 at 95%, 0.33 at 98%,
    0.21 at 99% — so the reliability-adjusted life is L_R = a₁·L10 (multiply the
    output of :func:`bearing_basic_rating_life` or :func:`bearing_life_hours` by it).
    ``reliability`` R must lie in (0, 1); at R = 0.90 a₁ = 1. A higher reliability
    buys a shorter usable life. Returns the dimensionless a₁ (≤ 1 for R ≥ 0.90).
    """
    if not 0.0 < reliability < 1.0:
        raise ValueError(f"reliability must lie in (0, 1); got {reliability}")
    if weibull_slope <= 0:
        raise ValueError(f"weibull_slope must be positive; got {weibull_slope}")
    return (log(1.0 / reliability) / log(1.0 / 0.90)) ** (1.0 / weibull_slope)


def bearing_ball_pass_frequency_outer(
    *,
    rotational_frequency: Quantity,
    number_of_rolling_elements: int,
    rolling_element_diameter: Quantity,
    pitch_diameter: Quantity,
    contact_angle: float = 0.0,
) -> Quantity:
    """The ball-pass frequency, outer race (BPFO), (N_b/2)·f_r·(1 − (d/D)·cos φ).

    The rate at which rolling elements pass a single defect on the stationary outer race, from the
    shaft ``rotational_frequency`` f_r, the ``number_of_rolling_elements`` N_b, the
    ``rolling_element_diameter`` d, the ``pitch_diameter`` D, and the ``contact_angle`` φ (degrees):
    BPFO = (N_b/2)·f_r·(1 − (d/D)·cos φ). A spectral peak here (and its harmonics) is the signature
    of outer-race spalling in vibration condition monitoring. Returns the frequency in Hz.
    """
    fr, nb, ratio = _defect_frequency_inputs(
        rotational_frequency,
        number_of_rolling_elements,
        rolling_element_diameter,
        pitch_diameter,
        contact_angle,
    )
    return Quantity(magnitude=(nb / 2.0) * fr * (1.0 - ratio), unit="Hz")


def bearing_ball_pass_frequency_inner(
    *,
    rotational_frequency: Quantity,
    number_of_rolling_elements: int,
    rolling_element_diameter: Quantity,
    pitch_diameter: Quantity,
    contact_angle: float = 0.0,
) -> Quantity:
    """The ball-pass frequency, inner race (BPFI), (N_b/2)·f_r·(1 + (d/D)·cos φ).

    The rate at which rolling elements pass a defect on the rotating inner race: BPFI =
    (N_b/2)·f_r·(1 + (d/D)·cos φ), from the same inputs as
    :func:`bearing_ball_pass_frequency_outer`. It is always higher than the BPFO, and their sum
    equals N_b·f_r. A BPFI peak — usually modulated by the shaft speed because the defect moves in
    and out of the load zone — signals inner-race spalling. Returns the frequency in Hz.
    """
    fr, nb, ratio = _defect_frequency_inputs(
        rotational_frequency,
        number_of_rolling_elements,
        rolling_element_diameter,
        pitch_diameter,
        contact_angle,
    )
    return Quantity(magnitude=(nb / 2.0) * fr * (1.0 + ratio), unit="Hz")


def bearing_fundamental_train_frequency(
    *,
    rotational_frequency: Quantity,
    number_of_rolling_elements: int,
    rolling_element_diameter: Quantity,
    pitch_diameter: Quantity,
    contact_angle: float = 0.0,
) -> Quantity:
    """The fundamental train (cage) frequency (FTF), (f_r/2)·(1 − (d/D)·cos φ).

    The rotation rate of the cage carrying the rolling elements: FTF = (f_r/2)·(1 − (d/D)·cos φ),
    a little under half the shaft speed. A peak at the FTF (or its sidebands around the ball-pass
    frequencies) points to a cage fault or looseness. It equals the BPFO divided by the number of
    rolling elements. The cage turns at one rate however many elements it carries, so
    ``number_of_rolling_elements`` does *not* enter this formula: it is taken because the four
    defect frequencies share one set of bearing inputs and one validation, and a caller reading
    an answer back should know which of the numbers they supplied produced it. Returns the
    frequency in Hz.
    """
    fr, _nb, ratio = _defect_frequency_inputs(
        rotational_frequency,
        number_of_rolling_elements,
        rolling_element_diameter,
        pitch_diameter,
        contact_angle,
    )
    return Quantity(magnitude=(fr / 2.0) * (1.0 - ratio), unit="Hz")


def bearing_ball_spin_frequency(
    *,
    rotational_frequency: Quantity,
    number_of_rolling_elements: int,
    rolling_element_diameter: Quantity,
    pitch_diameter: Quantity,
    contact_angle: float = 0.0,
) -> Quantity:
    """The ball (roller) spin frequency (BSF), (D/2d)·f_r·(1 − ((d/D)·cos φ)²).

    The rate at which a rolling element turns about its own axis: BSF =
    (D/2d)·f_r·(1 − ((d/D)·cos φ)²), from the shaft ``rotational_frequency`` f_r, the
    ``rolling_element_diameter`` d, the ``pitch_diameter`` D, and the ``contact_angle`` φ. A defect
    on a rolling element strikes each race once per revolution, so 2·BSF (often modulated by the
    cage frequency) is the tell-tale of a ball or roller fault. One element's spin is set by the
    geometry it rolls on, so ``number_of_rolling_elements`` does *not* enter this formula — it is
    taken and validated for the same reason as in :func:`bearing_fundamental_train_frequency`.
    Returns the frequency in Hz.
    """
    _require(rolling_element_diameter, "[length]", "rolling_element_diameter")
    _require(pitch_diameter, "[length]", "pitch_diameter")
    fr, _nb, ratio = _defect_frequency_inputs(
        rotational_frequency,
        number_of_rolling_elements,
        rolling_element_diameter,
        pitch_diameter,
        contact_angle,
    )
    d = rolling_element_diameter.to("mm").magnitude
    pd = pitch_diameter.to("mm").magnitude
    return Quantity(magnitude=(pd / (2.0 * d)) * fr * (1.0 - ratio * ratio), unit="Hz")
