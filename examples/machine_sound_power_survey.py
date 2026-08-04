"""Worked example: measuring a machine's sound power on a noisy floor, then predicting the exposure.

To rate a machine you need its sound *power* — a property of the source alone — but a plant floor is
too noisy and too reverberant for the classic pressure method, which an anechoic room would fix but
a factory cannot. The sound-intensity method (ISO 9614) gets around it: because intensity is a
vector,
steady background noise flowing through a measurement surface cancels out, so scanning an intensity
probe over a box around the machine gives its true radiated power even amid other running equipment.
This example takes an average intensity level of 85 dB measured over a 10 m² enclosing surface,
converts it to the machine's sound power level, and then closes the loop — feeding that power level
back through the free-field spreading law to predict the pressure level an operator standing 3 m
away on the reflecting floor is exposed to. The survey rates the machine; the prediction sizes the
risk.

Run it directly (``python examples/machine_sound_power_survey.py``);
:func:`survey_and_predict` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import sound_power_level_from_intensity, sound_pressure_from_power_level
from anvilate.units import Quantity

INTENSITY_LEVEL = 85.0  # dB re 1 pW/m², averaged over the measurement box
MEASUREMENT_AREA = Quantity.parse("10 m**2")
OPERATOR_DISTANCE = Quantity.parse("3 m")


def survey_and_predict() -> dict[str, float]:
    """Return the machine's sound power level and the predicted operator pressure level."""
    power_level = sound_power_level_from_intensity(
        intensity_level=INTENSITY_LEVEL, measurement_area=MEASUREMENT_AREA
    )
    operator_level = sound_pressure_from_power_level(
        sound_power_level=power_level, distance=OPERATOR_DISTANCE, directivity_factor=2.0
    )
    return {
        "sound_power_level_db": power_level,
        "operator_pressure_level_db": operator_level,
    }


def main() -> None:
    s = survey_and_predict()
    print(f"measured sound power level : {s['sound_power_level_db']:.0f} dB (intensity method)")
    print(f"predicted operator level   : {s['operator_pressure_level_db']:.0f} dB(A) at 3 m")
    print("  -> intensity rejects background noise; the rated power then predicts the exposure")


if __name__ == "__main__":
    main()
