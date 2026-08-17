"""T1 analytical RF noise-figure (Friis cascade) checks (closed-form).

Every amplifier and mixer adds noise, degrading the signal-to-noise ratio that passes through it.
The noise figure quantifies that degradation, and Friis's cascade formula shows how the stages of a
receiver chain combine — with the striking result that the first stage dominates, which is why a
low-noise amplifier goes right at the antenna. This sits on the thermal-noise floor of
:mod:`anvilate.analysis.thermal_noise` and feeds the received SNR that
:mod:`anvilate.analysis.channel_capacity` turns into data rate.

The noise factor F is the linear form of the noise figure (F = 10^(NF_dB/10)); a 3 dB figure is a
factor of about 2. For a chain of stages, Friis gives the total noise factor
F = F1 + (F2-1)/G1 + (F3-1)/(G1*G2) + ..., so each later stage's contribution is divided by the gain
ahead of it — a high-gain first stage swamps the rest. The equivalent noise temperature
T_e = (F - 1) * T0 (with T0 = 290 K by convention) expresses the same noise as an added source
temperature, the form used for antennas and low-noise receivers.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..units import Quantity
from ..units.rotation import count_rate_per_second

_REFERENCE_TEMPERATURE = 290.0  # K (IEEE standard reference)

__all__ = [
    "cascade_noise_factor",
    "equivalent_noise_temperature",
    "noise_factor_from_figure",
    "receiver_minimum_detectable_signal",
]

BOLTZMANN_J_PER_K = 1.380649e-23


def noise_factor_from_figure(*, noise_figure_db: float) -> float:
    """The linear noise factor from a noise figure, F = 10^(NF/10).

    Converts a ``noise_figure_db`` NF (the decibel form quoted on datasheets) to the linear noise
    factor F = 10^(NF/10) used in the cascade and temperature relations. A 0 dB figure is F = 1
    (noiseless); 3 dB is about 2 (the noise doubles). Returns the noise factor as a plain float
    (>= 1 for NF >= 0). NF must be non-negative (a passive-gain exception aside).
    """
    if noise_figure_db < 0:
        raise ValueError("noise_figure_db must be non-negative")
    return 10.0 ** (noise_figure_db / 10.0)


def cascade_noise_factor(
    *, stage_noise_factors: Sequence[float], stage_gains: Sequence[float]
) -> float:
    """The Friis cascade noise factor, F = F1 + (F2-1)/G1 + (F3-1)/(G1*G2) + ...

    The overall noise factor of a chain of stages, from their linear ``stage_noise_factors`` (F per
    stage) and ``stage_gains`` (linear gain per stage; the last stage's gain is unused). Friis's
    formula divides each later stage's excess noise by the gain ahead of it, so the first stage
    dominates — the reason a low-noise amplifier goes first. Returns the total noise factor as a
    float. Requires one gain per noise factor and at least one stage.
    """
    if len(stage_noise_factors) == 0:
        raise ValueError("stage_noise_factors must not be empty")
    if len(stage_gains) != len(stage_noise_factors):
        raise ValueError("stage_gains must have one gain per stage (same length as noise factors)")
    for f in stage_noise_factors:
        if f < 1.0:
            raise ValueError("each stage noise factor must be at least 1")
    for g in stage_gains:
        if g <= 0.0:
            raise ValueError("each stage gain must be positive")
    total = stage_noise_factors[0]
    gain_product = 1.0
    for i in range(1, len(stage_noise_factors)):
        gain_product *= stage_gains[i - 1]
        total += (stage_noise_factors[i] - 1.0) / gain_product
    return total


def equivalent_noise_temperature(
    *, noise_factor: float, reference_temperature: Quantity | None = None
) -> Quantity:
    """The equivalent noise temperature, T_e = (F - 1) * T0.

    Expresses a ``noise_factor`` F as an added source temperature: T_e = (F - 1) * T0, with the
    ``reference_temperature`` T0 defaulting to the 290 K IEEE standard. It is the form used for
    antennas and cryogenic low-noise receivers, where noise is naturally spoken of as a temperature
    (a 1 dB figure is about 75 K). Returns the equivalent noise temperature in K.
    """
    if noise_factor < 1.0:
        raise ValueError("noise_factor must be at least 1")
    if reference_temperature is None:
        t0 = _REFERENCE_TEMPERATURE
    else:
        _check(reference_temperature, "[temperature]", "reference_temperature")
        t0 = reference_temperature.to("K").magnitude
        if t0 <= 0:
            raise ValueError("reference_temperature must be positive (absolute temperature)")
    return Quantity(magnitude=(noise_factor - 1.0) * t0, unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def receiver_minimum_detectable_signal(
    *,
    noise_factor: float,
    bandwidth: Quantity,
    required_snr: float,
    noise_temperature: Quantity | None = None,
) -> Quantity:
    """The receiver sensitivity floor, P_min = k·T₀·B·F·SNR_min.

    :func:`anvilate.analysis.radar.radar_max_range` requires a minimum detectable power and
    nothing in the library computed one, so the user had to hand-derive kTBF·SNR — where a
    forgotten noise figure or a dB/linear mix-up moves the range by the fourth root of a large
    factor.

    The thermal noise floor in a bandwidth B is k·T₀·B; the receiver's own ``noise_factor`` F (the
    linear form, from :func:`noise_factor_from_figure` or :func:`cascade_noise_factor`) raises it,
    and detection needs the signal a factor ``required_snr`` above what is left. T₀ is the IEEE
    290 K reference unless a ``noise_temperature`` is given — pass the real antenna temperature
    for a sky-noise-limited system, where 290 K is pessimistic.

    A 3 dB receiver over 1 MHz needing 13 dB of SNR floors at 1.594e-13 W, or −98.0 dBm. Note
    both dimensionless arguments are LINEAR ratios, not decibels. Passing 3 and 13 directly is a
    small error here only by coincidence — 3·13 = 39 against the correct 2·20 = 40, so the floor
    comes out 0.089 dB low — but the coincidence does not survive other numbers: a 10 dB noise
    figure entered as 10 rather than 10.0 linear understates the floor by 10 dB.

    Returns the minimum detectable power in W.
    """
    _check(bandwidth, "1/[time]", "bandwidth")
    t0 = _REFERENCE_TEMPERATURE
    if noise_temperature is not None:
        _check(noise_temperature, "[temperature]", "noise_temperature")
        t0 = noise_temperature.to("K").magnitude
    b = count_rate_per_second(bandwidth, name="bandwidth")
    if noise_factor < 1.0:
        raise ValueError(
            f"noise_factor is a LINEAR factor and cannot be below 1 (0 dB); got {noise_factor}"
        )
    if b <= 0:
        raise ValueError(f"bandwidth must be positive; got {bandwidth}")
    if required_snr <= 0:
        raise ValueError(f"required_snr must be positive; got {required_snr}")
    if t0 <= 0:
        raise ValueError("noise_temperature must be above absolute zero")
    return Quantity(magnitude=BOLTZMANN_J_PER_K * t0 * b * noise_factor * required_snr, unit="W")
