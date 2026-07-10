"""Worked example: how hot is hot enough for a shrink fit.

``shrink_fit_check.py`` screens whether the Ø40 H7/s6 hub survives being on
the shaft; this one asks how it gets there. The tolerance layer resolves the
fit's tightest diametral interference (59 µm), the shop adds a 25 µm slip
allowance so the hub doesn't seize half-way down the bore, and the thermal
layer inverts the bore's free growth: ΔT = (δ + c)/(α·d) = 179.5 K, an oven
setpoint just under 200 °C. The screen then checks real equipment against
that requirement: a 150 °C bench oven opens the bore only 61 µm — it clears
the raw interference by 2 µm, which is exactly how hubs end up stuck at
half-engagement — while a 250 °C-rated furnace opens 108 µm and passes with
the slip allowance intact.

Run it directly (``python examples/hub_heating_for_assembly.py``);
:func:`screen_hub_heating` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import free_thermal_expansion, shrink_fit_assembly_temperature
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.tolerance.iso286 import fit
from anvilate.units import Quantity

SHAFT_DIAMETER = Quantity.parse("40 mm")
FIT_DESIGNATION = "H7/s6"
SLIP_ALLOWANCE = Quantity.parse("25 um")  # working clearance during the drop
ALPHA_STEEL = Quantity.parse("11.7e-6 / K")
AMBIENT_C = 20.0

# (name, oven temperature in degC)
OVENS = (
    ("bench oven at 150 degC", 150.0),
    ("furnace at 250 degC", 250.0),
)


def screen_hub_heating() -> Scorecard:
    """Resolve the fit, invert the bore growth, screen each oven against it."""
    press = fit(FIT_DESIGNATION, SHAFT_DIAMETER)
    # Tightest fit = the most negative clearance, as a positive interference.
    interference = Quantity(magnitude=abs(press.min_clearance.to("mm").magnitude), unit="mm")
    required_rise = shrink_fit_assembly_temperature(
        interface_diameter=SHAFT_DIAMETER,
        diametral_interference=interference,
        assembly_clearance=SLIP_ALLOWANCE,
        thermal_expansion_coefficient=ALPHA_STEEL,
    )
    needed_um = (interference.to("mm").magnitude + SLIP_ALLOWANCE.to("mm").magnitude) * 1000

    entries = []
    for name, oven_c in OVENS:
        rise = Quantity(magnitude=oven_c - AMBIENT_C, unit="delta_degC")
        opening = free_thermal_expansion(
            length=SHAFT_DIAMETER,
            thermal_expansion_coefficient=ALPHA_STEEL,
            temperature_change=rise,
        )
        opening_um = opening.to("mm").magnitude * 1000
        status = CheckStatus.PASS if opening_um >= needed_um else CheckStatus.FAIL
        entries.append(
            ScorecardEntry(
                name=f"{name} bore opening",
                status=status,
                detail=(
                    f"opens {opening_um:.0f} um vs required {needed_um:.0f} um "
                    f"(interference {interference.to('mm').magnitude * 1000:.0f} um "
                    f"+ slip {SLIP_ALLOWANCE.to('mm').magnitude * 1000:.0f} um; "
                    f"setpoint needed {AMBIENT_C + required_rise.to('K').magnitude:.0f} degC)"
                ),
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_hub_heating()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
