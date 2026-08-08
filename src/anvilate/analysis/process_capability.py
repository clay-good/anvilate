"""T1 analytical process-capability (SPC) checks (closed-form).

Whether a manufacturing process can hold a tolerance is a statistics question: how the spread of the
output compares to the width of the specification. The capability indices Cp and Cpk quantify that,
and — assuming a normal distribution — translate directly into an expected defect rate. These screen
whether a process is capable before it runs, complementing the dimensional stackups of
:mod:`anvilate.analysis.tolerance`.

The potential capability Cp = (USL − LSL)/(6σ) compares the spec width to the natural ±3σ spread of
a process of standard deviation σ; Cp = 1 just fits, and the usual target is 1.33 or better. But Cp
ignores where the process is centered, so the actual capability is Cpk = min(USL − µ, µ − LSL)/(3σ),
which drops as the mean µ drifts off center. For a normal process the fraction beyond the nearer
limit is Φ(−3·Cpk), so the expected defect rate is 10⁶·Φ(−3·Cpk) parts per million — Cpk = 1.33
gives about 33 ppm. The characteristic and its limits are plain numbers in any consistent unit; the
indices and rates are dimensionless plain floats.
"""

from __future__ import annotations

from math import erf, sqrt

__all__ = [
    "expected_defect_rate_ppm",
    "process_capability_index",
    "process_capability_ratio",
]


def process_capability_index(
    *, upper_spec_limit: float, lower_spec_limit: float, process_std_dev: float
) -> float:
    """The potential capability index, Cp = (USL − LSL)/(6σ).

    The ratio of the specification width to the process's natural ±3σ spread, from the
    ``upper_spec_limit`` USL, ``lower_spec_limit`` LSL (same units), and ``process_std_dev`` σ:
    Cp = (USL − LSL)/(6σ). Cp = 1 exactly fills the tolerance; 1.33 leaves a comfortable margin. It
    assumes the process is perfectly centered. Returns the index as a plain float.
    """
    if upper_spec_limit <= lower_spec_limit:
        raise ValueError("upper_spec_limit must exceed lower_spec_limit")
    if process_std_dev <= 0:
        raise ValueError("process_std_dev must be positive")
    return (upper_spec_limit - lower_spec_limit) / (6.0 * process_std_dev)


def process_capability_ratio(
    *,
    upper_spec_limit: float,
    lower_spec_limit: float,
    process_mean: float,
    process_std_dev: float,
) -> float:
    """The actual capability index, Cpk = min(USL − µ, µ − LSL)/(3σ).

    The capability that accounts for how far the process is off center, from the
    ``upper_spec_limit`` USL, ``lower_spec_limit`` LSL, ``process_mean`` µ, and ``process_std_dev``
    σ: Cpk = min(USL − µ, µ − LSL)/(3σ). It equals Cp only when the process is centered and falls as
    the mean drifts toward a limit. Returns the index as a plain float.
    """
    if upper_spec_limit <= lower_spec_limit:
        raise ValueError("upper_spec_limit must exceed lower_spec_limit")
    if process_std_dev <= 0:
        raise ValueError("process_std_dev must be positive")
    upper = upper_spec_limit - process_mean
    lower = process_mean - lower_spec_limit
    return min(upper, lower) / (3.0 * process_std_dev)


def expected_defect_rate_ppm(*, capability_index: float) -> float:
    """The expected defect rate, PPM = 10⁶·Φ(−3·Cpk).

    The parts-per-million beyond the nearer specification limit for a normal process of capability
    ``capability_index`` Cpk: PPM = 10⁶·Φ(−3·Cpk), where Φ is the standard-normal CDF. Cpk = 1 gives
    about 1350 ppm, 1.33 about 33 ppm, 1.5 about 3.4 ppm (short-term, no mean-shift assumption).
    Returns the defect rate in parts per million as a plain float.
    """
    z = 3.0 * capability_index
    phi = 0.5 * (1.0 + erf(-z / sqrt(2.0)))
    return 1.0e6 * phi
