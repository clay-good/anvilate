"""Worked example: the pH of an acetate buffer and the recipe to shift it.

Acetic acid has a pKa of 4.76. A buffer is mixed with 0.20 mol/L of acetate (the conjugate base) and
0.10 mol/L of acetic acid — what pH does it hold, and if the target is instead pH 5.00, what
base-to-acid ratio does that need?

The Henderson-Hasselbalch equation gives pH = 4.76 + log₁₀(0.20/0.10) = 5.06. To sit at exactly pH
5.00 the ratio must be [A⁻]/[HA] = 10^(5.00 − 4.76) ≈ 1.74 — a little less base than the first mix.
Both answers stay within one pH unit of the pKa, which is the range where an acetate buffer actually
buffers well.

Run it directly (``python examples/acetate_buffer_ph.py``);
:func:`acetate_buffer` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import buffer_ratio_for_ph, henderson_hasselbalch_ph
from anvilate.units import Quantity

ACETIC_ACID_PKA = 4.76
ACETATE_CONCENTRATION = Quantity.parse("0.20 mol/L")
ACETIC_ACID_CONCENTRATION = Quantity.parse("0.10 mol/L")
TARGET_PH = 5.00


def acetate_buffer() -> dict[str, float]:
    """Return the buffer pH of the mix and the base-to-acid ratio for the target pH."""
    ph = henderson_hasselbalch_ph(
        pka=ACETIC_ACID_PKA,
        conjugate_base_concentration=ACETATE_CONCENTRATION,
        weak_acid_concentration=ACETIC_ACID_CONCENTRATION,
    )
    ratio = buffer_ratio_for_ph(pka=ACETIC_ACID_PKA, ph=TARGET_PH)
    return {
        "buffer_ph": ph,
        "ratio_for_target_ph": ratio,
    }


def main() -> None:
    d = acetate_buffer()
    print("Acetate buffer (pKa 4.76), 0.20 M base / 0.10 M acid:")
    print(f"  buffer pH             : {d['buffer_ph']:.2f}")
    print(f"  base:acid for pH 5.00 : {d['ratio_for_target_ph']:.2f}")


if __name__ == "__main__":
    main()
