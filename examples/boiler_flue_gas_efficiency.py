"""Worked example: reading a boiler's efficiency off its flue gas.

The biggest loss in a fuel-fired boiler is the heat that goes straight up the stack in the hot,
oxygen-rich flue gas, and a technician can read it off a two-number combustion analysis — the flue
temperature and the flue oxygen — with the Siegert formula, qA = f·(T_flue − T_air)/(21 − O₂%). The
efficiency is what is left after that loss: η ≈ 100 − qA.

This example tunes one gas boiler (Siegert factor 0.66) two ways. Run well, it exhausts at 180 °C
with 3% flue oxygen: the stack loss is 5.9% and the efficiency 94%. Let it drift out of tune — the
stack climbs to 240 °C and the excess air pushes the flue oxygen to 7% — and the same formula gives
a 10.4% stack loss and a 90% efficiency. Four points of efficiency, worth real money on a fuel
bill, have vanished into a hotter, more dilute exhaust, and the flue-gas analyzer saw
it without opening the boiler. The lesson is that combustion efficiency lives in the flue gas: a low
stack temperature and just enough excess air to burn clean is the whole game, and the Siegert loss
is how you put a number on it.

Run it directly (``python examples/boiler_flue_gas_efficiency.py``);
:func:`boiler_efficiency` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import combustion_efficiency, siegert_dry_flue_gas_loss
from anvilate.units import Quantity

COMBUSTION_AIR = Quantity(magnitude=20.0, unit="degC")
SIEGERT_FACTOR = 0.66  # natural gas


def boiler_efficiency() -> dict[str, float]:
    """Return the stack loss and efficiency of a well-tuned and an out-of-tune boiler."""

    def tune(flue_c: float, flue_oxygen: float) -> dict[str, float]:
        loss = siegert_dry_flue_gas_loss(
            flue_temperature=Quantity(magnitude=flue_c, unit="degC"),
            combustion_air_temperature=COMBUSTION_AIR,
            flue_oxygen_percent=flue_oxygen,
            siegert_factor=SIEGERT_FACTOR,
        )
        return {"loss": loss, "efficiency": combustion_efficiency(dry_flue_gas_loss_percent=loss)}

    tuned = tune(180.0, 3.0)
    drifted = tune(240.0, 7.0)
    return {
        "tuned_loss": tuned["loss"],
        "tuned_efficiency": tuned["efficiency"],
        "drifted_loss": drifted["loss"],
        "drifted_efficiency": drifted["efficiency"],
    }


def main() -> None:
    b = boiler_efficiency()
    tl, te = b["tuned_loss"], b["tuned_efficiency"]
    dl, de = b["drifted_loss"], b["drifted_efficiency"]
    print(f"well-tuned (180 C, 3% O2)  : stack loss {tl:.1f}% -> {te:.0f}%")
    print(f"out of tune (240 C, 7% O2) : stack loss {dl:.1f}% -> {de:.0f}%")
    print(
        "  -> combustion efficiency lives in the flue gas: low stack temp, just enough excess air"
    )


if __name__ == "__main__":
    main()
