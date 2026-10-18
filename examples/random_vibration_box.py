"""Worked example: an electronics box on the GEVS qualification random-vibration profile.

GSFC-STD-7000B Table 2.4-3 gives the component qualification spectrum as breakpoints:
0.026 g²/Hz at 20 Hz rising to 0.16 g²/Hz at 50 Hz, flat to 800 Hz, falling to 0.026 g²/Hz
at 2000 Hz. Integrated on log-log segments it is 14.14 Grms, the 14.1 the table prints.

A box whose first mode is at 100 Hz with Q of 10 sits on the plateau. Miles' equation
gives a response of 15.85 Grms, so its 3σ design load is 47.56 g, more than three
times the overall input level. With a 6 g quasi-static launch load combined
root-sum-square the design load is 47.94 g; combined as an absolute sum it would be
53.56 g. The rule is the program's to declare, and the result carries it.

The same box at Q of 25, a lightly damped bolted mount, reaches 75.20 g 3σ: the load
grows with √Q, which is why Q is never defaulted. Miles' equation assumes one mode
responding to an input flat across it, and every result says so.

Run it directly (``python examples/random_vibration_box.py``);
:func:`random_vibration_box` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import LoadCombinationRule, psd_overall_grms, random_vibration_load
from anvilate.units import Quantity

BREAKPOINTS = ((20.0, 0.026), (50.0, 0.16), (800.0, 0.16), (2000.0, 0.026))
FREQUENCIES = [Quantity(magnitude=f, unit="Hz") for f, _ in BREAKPOINTS]
ASD = [Quantity(magnitude=a, unit="1/Hz") for _, a in BREAKPOINTS]
NATURAL_FREQUENCY = Quantity(magnitude=100.0, unit="Hz")
QUASI_STATIC_G = 6.0


def random_vibration_box() -> dict[str, float]:
    """Return the input Grms, the 3σ load at Q 10 and 25, and both combinations."""

    def load(quality: float, rule: LoadCombinationRule):
        return random_vibration_load(
            frequencies=FREQUENCIES, asd=ASD, natural_frequency=NATURAL_FREQUENCY,
            quality_factor=quality, quasi_static=QUASI_STATIC_G, rule=rule,
        )  # fmt: skip

    rss = load(10.0, LoadCombinationRule.ROOT_SUM_SQUARE)
    return {
        "input_grms": psd_overall_grms(frequencies=FREQUENCIES, asd=ASD),
        "response_grms": rss.response_grms,
        "peak_3_sigma": rss.peak_3_sigma,
        "combined_rss": rss.design_load,
        "combined_absolute": load(10.0, LoadCombinationRule.ABSOLUTE_SUM).design_load,
        "peak_3_sigma_q25": load(25.0, LoadCombinationRule.ROOT_SUM_SQUARE).peak_3_sigma,
    }


def main() -> None:
    d = random_vibration_box()
    print(f"input: {d['input_grms']:.2f} Grms")
    print(f"response at 100 Hz, Q 10: {d['response_grms']:.2f} Grms")
    print(f"3-sigma: {d['peak_3_sigma']:.2f} g")
    print(f"with 6 g quasi-static: {d['combined_rss']:.2f} g RSS")
    print(f"as an absolute sum: {d['combined_absolute']:.2f} g")
    print(f"at Q 25: 3-sigma {d['peak_3_sigma_q25']:.2f} g")


if __name__ == "__main__":
    main()
