"""Worked example: why the first amplifier sets a receiver's noise figure.

Every stage of a receiver adds noise, but they do not contribute equally: Friis's cascade formula
divides each later stage's noise by the gain ahead of it, so the first stage dominates. This is the
reason a low-noise amplifier is placed right at the antenna, ahead of the lossy cable and the noisy
mixer. This example makes the point with two orderings of the same parts.

The chain is a low-noise amplifier (1 dB noise figure, factor 1.26, with 20 dB = 100x gain) followed
by a mixer (10 dB figure, factor 10). With the LNA first, the total noise factor is 1.26 +
(10-1)/100 = 1.35, only about 1.3 dB — barely worse than the LNA alone, because the LNA's gain
swamps the mixer's noise. Put the mixer first instead and the total jumps to about 10 dB, dominated
by the mixer. The example reports the LNA-first noise figure (dB), the equivalent noise temperature,
and the mixer-first figure — the penalty for the wrong order.

Run it directly (``python examples/receiver_noise_figure.py``);
:func:`receiver_chain` is also exercised in the test suite.
"""

from __future__ import annotations

from math import log10

from anvilate.analysis import (
    cascade_noise_factor,
    equivalent_noise_temperature,
    noise_factor_from_figure,
)

LNA_NOISE_FACTOR = noise_factor_from_figure(noise_figure_db=1.0)
LNA_GAIN = 100.0  # 20 dB
MIXER_NOISE_FACTOR = noise_factor_from_figure(noise_figure_db=10.0)
MIXER_GAIN = 100.0  # 20 dB


def receiver_chain() -> dict[str, float]:
    """Return the LNA-first noise figure (dB), its noise temperature, and the mixer-first figure."""
    lna_first = cascade_noise_factor(
        stage_noise_factors=[LNA_NOISE_FACTOR, MIXER_NOISE_FACTOR],
        stage_gains=[LNA_GAIN, MIXER_GAIN],
    )
    mixer_first = cascade_noise_factor(
        stage_noise_factors=[MIXER_NOISE_FACTOR, LNA_NOISE_FACTOR],
        stage_gains=[MIXER_GAIN, LNA_GAIN],
    )
    temperature = equivalent_noise_temperature(noise_factor=lna_first)
    return {
        "lna_first_nf_db": 10 * log10(lna_first),
        "lna_first_noise_temp_k": temperature.to("K").magnitude,
        "mixer_first_nf_db": 10 * log10(mixer_first),
    }


def main() -> None:
    d = receiver_chain()
    print(f"noise figure, LNA first: {d['lna_first_nf_db']:.1f} dB")
    print(f"equivalent noise temperature: {d['lna_first_noise_temp_k']:.0f} K")
    print(f"noise figure, mixer first: {d['mixer_first_nf_db']:.1f} dB")


if __name__ == "__main__":
    main()
