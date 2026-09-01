"""The lighting pack: declare a luminaire layout, get an illuminance-vs-energy scorecard.

Where :mod:`anvilate.packs.noise_exposure` screens what a worker hears, this pack screens what a
space gets lit to — and the two checks a real layout must satisfy at once pull against each other. A
:class:`LightingInstallation` declares the luminaires, their lumen output and input watts, the room,
and two targets: the task illuminance the space needs (an IES-recommended level) and the lighting
power density its energy code allows (ASHRAE 90.1 / IECC). :func:`screen_lighting` runs the lumen
method for the achieved illuminance and the connected power density, and rolls both into a cited
PASS/FAIL scorecard — adding fixtures to clear the illuminance target drives the power density up
toward the code cap, so a layout that lights well can still fail the energy check. The targets are
the caller's cited values; the arithmetic is the pack's.
"""

from __future__ import annotations

from pydantic import ConfigDict

from ..analysis import lighting_power_density, lumen_method_illuminance
from ..derivation import Derivation, SymbolValue
from ..scorecard import Scorecard, ScorecardEntry
from ..units import Quantity
from ._guarded import GuardedInputs

__all__ = [
    "LightingInstallation",
    "screen_lighting",
]

_ILLUMINANCE_REFERENCE = "IES Lighting Handbook — recommended task illuminance"
_LPD_REFERENCE = "ASHRAE 90.1 / IECC — lighting power density allowance"


class LightingInstallation(GuardedInputs):
    """A luminaire layout for one space, with the two targets its screen checks.

    ``luminaire_count`` n fixtures each emit ``lumens_per_luminaire`` Φ and draw
    ``input_watts_per_luminaire`` W (driver included), over ``floor_area`` A. ``coefficient_of_
    utilization`` CU and ``light_loss_factor`` LLF discount the delivered light (both in (0, 1]).
    ``required_illuminance`` is the task level the space must reach; ``allowable_power_density`` is
    the energy-code cap the install must stay under. All are the caller's values.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    luminaire_count: int
    lumens_per_luminaire: Quantity
    input_watts_per_luminaire: Quantity
    coefficient_of_utilization: float
    light_loss_factor: float
    floor_area: Quantity
    required_illuminance: Quantity
    allowable_power_density: Quantity


def screen_lighting(
    installation: LightingInstallation,
    *,
    required_safety_factor: float = 1.0,
) -> Scorecard:
    """Screen a :class:`LightingInstallation` for illuminance and power density; return its card.

    Screens the achieved illuminance against the required task level (safety factor E/E_required,
    PASS when the room is lit enough) and the connected lighting power density against the code
    allowance (safety factor LPD_allowed/LPD, PASS when the install stays under the energy cap),
    each against ``required_safety_factor`` (1.0 — the targets carry their own margins). Returns a
    :class:`~anvilate.scorecard.Scorecard` with a cited PASS/FAIL entry for each; a layout can pass
    the illuminance check and fail the energy check when it reaches the target with too much power.
    """
    achieved = lumen_method_illuminance(
        luminaire_count=installation.luminaire_count,
        lumens_per_luminaire=installation.lumens_per_luminaire,
        coefficient_of_utilization=installation.coefficient_of_utilization,
        light_loss_factor=installation.light_loss_factor,
        area=installation.floor_area,
    )
    required = installation.required_illuminance.to("lux").magnitude
    illuminance_sf = achieved.to("lux").magnitude / required if required > 0 else None
    illuminance_derivation = Derivation(
        symbolic="E = n · Φ · CU · LLF / A",
        inputs=(
            SymbolValue(
                symbol="n", description="luminaire count", value=float(installation.luminaire_count)
            ),
            SymbolValue(
                symbol="Φ",
                description="rated output per luminaire",
                value=installation.lumens_per_luminaire,
                unit="lumen",
            ),
            SymbolValue(
                symbol="CU",
                description="coefficient of utilization — the fraction of emitted lumens "
                "reaching the work plane",
                value=installation.coefficient_of_utilization,
            ),
            SymbolValue(
                symbol="LLF",
                description="light loss factor for dirt and lamp depreciation",
                value=installation.light_loss_factor,
            ),
            SymbolValue(
                symbol="A", description="floor area", value=installation.floor_area, unit="m**2"
            ),
        ),
        result=SymbolValue(
            symbol="E",
            description="average maintained illuminance on the work plane",
            value=achieved,
            unit="lux",
        ),
        citation=_ILLUMINANCE_REFERENCE,
    )
    illuminance_entry = ScorecardEntry.from_safety_factor(
        "task illuminance", computed=illuminance_sf, required=required_safety_factor
    ).model_copy(update={"reference": _ILLUMINANCE_REFERENCE, "derivation": illuminance_derivation})

    lpd = lighting_power_density(
        luminaire_count=installation.luminaire_count,
        input_watts_per_luminaire=installation.input_watts_per_luminaire,
        area=installation.floor_area,
    )
    actual_lpd = lpd.to("W/m**2").magnitude
    allowable_lpd = installation.allowable_power_density.to("W/m**2").magnitude
    lpd_sf = allowable_lpd / actual_lpd if actual_lpd > 0 else None
    # The allowance is tabular — ASHRAE 90.1 or the IECC by space type, the caller's to
    # cite. The installed density it is screened against is this pack's arithmetic.
    lpd_derivation = Derivation(
        symbolic="LPD = n · W / A",
        inputs=(
            SymbolValue(
                symbol="n", description="luminaire count", value=float(installation.luminaire_count)
            ),
            SymbolValue(
                symbol="W",
                description="input power per luminaire, driver losses included",
                value=installation.input_watts_per_luminaire,
                unit="W",
            ),
            SymbolValue(
                symbol="A", description="floor area", value=installation.floor_area, unit="m**2"
            ),
        ),
        result=SymbolValue(
            symbol="LPD",
            description="installed lighting power density",
            value=lpd,
            unit="W/m**2",
        ),
        citation=_LPD_REFERENCE,
    )
    lpd_entry = ScorecardEntry.from_safety_factor(
        "lighting power density", computed=lpd_sf, required=required_safety_factor
    ).model_copy(update={"reference": _LPD_REFERENCE, "derivation": lpd_derivation})
    return Scorecard(entries=(illuminance_entry, lpd_entry))
