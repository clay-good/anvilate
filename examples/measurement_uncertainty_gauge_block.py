"""Worked example: a calibration result stated the way a GUM budget requires.

A length measurement is not a number, it is a number plus an uncertainty — and a lab report that
omits the second half is not traceable. This example builds a small ISO GUM uncertainty budget for a
gauge-block measurement: the repeatability of ten readings (a Type A contribution), plus a
calibration and a thermal-expansion contribution (Type B), combined and expanded to a 95% coverage.

The ten readings scatter with s = 0.30 µm, so the mean is uncertain to s/√10 ≈ 0.095 µm. Adding the
0.12 µm calibration and 0.08 µm temperature contributions in quadrature gives a combined standard
uncertainty of about 0.17 µm — dominated by the largest terms, since they add as squares. Times
the coverage factor k = 2 that is an expanded uncertainty near 0.35 µm, so the result is reported as
"length ± 0.35 µm (k = 2, ~95%)".

Run it directly (``python examples/measurement_uncertainty_gauge_block.py``);
:func:`uncertainty_budget` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    combined_standard_uncertainty,
    expanded_uncertainty,
    standard_uncertainty_of_mean,
)
from anvilate.units import Quantity

REPEATABILITY_STD = Quantity.parse("0.30 um")
READINGS = 10
CALIBRATION_U = Quantity.parse("0.12 um")  # Type B, from the certificate
TEMPERATURE_U = Quantity.parse("0.08 um")  # Type B, thermal expansion
COVERAGE_FACTOR = 2.0  # ~95% for a normal result


def uncertainty_budget() -> dict[str, float]:
    """Return the Type A, combined, and expanded uncertainties (um) for the gauge-block result."""
    u_repeat = standard_uncertainty_of_mean(
        standard_deviation=REPEATABILITY_STD, sample_size=READINGS
    )
    u_c = combined_standard_uncertainty(u_repeat, CALIBRATION_U, TEMPERATURE_U)
    big_u = expanded_uncertainty(combined_standard_uncertainty=u_c, coverage_factor=COVERAGE_FACTOR)
    return {
        "type_a_um": u_repeat.to("um").magnitude,
        "combined_um": u_c.to("um").magnitude,
        "expanded_um": big_u.to("um").magnitude,
    }


def main() -> None:
    b = uncertainty_budget()
    print("gauge-block uncertainty budget:")
    print(f"  Type A (repeatability of mean) : {b['type_a_um']:.3f} um  (s/sqrt(10))")
    print(f"  combined standard uncertainty  : {b['combined_um']:.3f} um  (root-sum-of-squares)")
    print(
        f"  expanded (k = 2, ~95%)          : {b['expanded_um']:.3f} um  -> report length +/- this"
    )


if __name__ == "__main__":
    main()
