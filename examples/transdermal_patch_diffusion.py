"""Worked example: drug diffusion through a transdermal patch membrane.

A transdermal patch delivers a drug by letting it diffuse through a rate-controlling membrane into
the skin. Sizing it means answering two Fickian questions: how fast the drug crosses the membrane at
steady state (which sets the dose rate), and how long the patch takes to reach that steady state
after it is applied (the lag before delivery ramps up). Both follow from the drug's diffusivity in
the membrane.

This example uses a drug of diffusivity 1e-11 m^2/s in a 50 micron membrane, held at a 200 mol/m^3
concentration difference across it. The steady flux is about 4e-5 mol/(m^2·s) — the per-area
delivery rate the patch settles to. The membrane's diffusion lag, the time for the front to cross
its 50 micron thickness, is about 250 s (a few minutes), so delivery ramps up quickly after it goes
on. The example reports the steady flux and the membrane crossing time.

Run it directly (``python examples/transdermal_patch_diffusion.py``);
:func:`patch_delivery` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import diffusion_time, steady_diffusion_flux
from anvilate.units import Quantity

DIFFUSIVITY = Quantity(magnitude=1e-11, unit="m**2/s")
MEMBRANE_THICKNESS = Quantity.parse("50 um")
CONCENTRATION_DIFFERENCE = Quantity(magnitude=200.0, unit="mol/m**3")


def patch_delivery() -> dict[str, float]:
    """Return the steady diffusion flux and the membrane crossing (lag) time."""
    flux = steady_diffusion_flux(
        diffusivity=DIFFUSIVITY,
        concentration_difference=CONCENTRATION_DIFFERENCE,
        thickness=MEMBRANE_THICKNESS,
    )
    lag = diffusion_time(diffusion_length=MEMBRANE_THICKNESS, diffusivity=DIFFUSIVITY)
    return {
        "steady_flux_mol_m2_s": flux.to("mol/(m**2*s)").magnitude,
        "membrane_crossing_time_s": lag.to("s").magnitude,
    }


def main() -> None:
    d = patch_delivery()
    print(f"steady flux: {d['steady_flux_mol_m2_s']:.1e} mol/(m^2*s)")
    print(f"membrane crossing time: {d['membrane_crossing_time_s']:.0f} s")


if __name__ == "__main__":
    main()
