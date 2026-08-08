"""Worked example: is a machining process capable of holding a tolerance?

Before a process runs a production lot, its capability indices say whether it can hold the print:
Cp compares the tolerance width to the process spread, Cpk penalizes an off-center process, and the
capability index converts to an expected defect rate.

A shaft diameter is specified 9.5 to 10.5 mm, and the process runs with a standard deviation of
0.1 mm — giving a potential capability Cp of about 1.67, a wide margin. But the process is centered
at 10.1 mm, off the 10.0 mm nominal, so its actual capability Cpk drops to about 1.33 (the upper
limit is the tighter side). At Cpk 1.33 a normal process makes about 32 defective parts per million.
This example reports the Cp, the Cpk, and the expected defect rate.

Run it directly (``python examples/machining_process_capability.py``);
:func:`shaft_capability` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    expected_defect_rate_ppm,
    process_capability_index,
    process_capability_ratio,
)

UPPER_SPEC = 10.5  # mm
LOWER_SPEC = 9.5  # mm
PROCESS_MEAN = 10.1  # mm
PROCESS_STD_DEV = 0.1  # mm


def shaft_capability() -> dict[str, float]:
    """Return the Cp, the Cpk, and the expected defect rate for the shaft process."""
    cp = process_capability_index(
        upper_spec_limit=UPPER_SPEC, lower_spec_limit=LOWER_SPEC, process_std_dev=PROCESS_STD_DEV
    )
    cpk = process_capability_ratio(
        upper_spec_limit=UPPER_SPEC,
        lower_spec_limit=LOWER_SPEC,
        process_mean=PROCESS_MEAN,
        process_std_dev=PROCESS_STD_DEV,
    )
    ppm = expected_defect_rate_ppm(capability_index=cpk)
    return {
        "cp": cp,
        "cpk": cpk,
        "defect_rate_ppm": ppm,
    }


def main() -> None:
    d = shaft_capability()
    print(f"Cp (potential capability): {d['cp']:.2f}")
    print(f"Cpk (actual capability): {d['cpk']:.2f}")
    print(f"expected defect rate: {d['defect_rate_ppm']:.0f} ppm")


if __name__ == "__main__":
    main()
