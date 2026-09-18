"""Worked example: a sealed lens assembly screened across its declared thermal range.

A doublet in an aluminium cell, sealed with an O-ring, is assembled at 20 °C and lives
between −40 °C and +71 °C for 500 cycles. Six entries answer for it:

- an Invar spacer holds focus: 2.9 µm of defocus at the hot extreme, inside 8.6 µm;
- the lens preload stays between 31.6 N hot and 49.9 N cold, never lost and never crushing;
- the O-ring stays in its squeeze, fill and stretch bands at both extremes;
- the sealed volume swings 38.37 kPa every cycle, and with no equalization path, desiccant
  or purge it breathes moist air in past the seal and keeps the water;
- the doublet's cement is rated to 60 °C, and the housing reaches 71 °C;
- and the focus must hold after 500 cycles, which no single-excursion screen can answer,
  so that entry names the thermal-cycling test instead.

Two fail as drawn. The repair is a cement rated to 85 °C and a desiccant in the volume, and
both then pass. The repaired card still reads not evaluated, and that is the point: its
single-excursion screens pass, but the retention after cycling is for the test to show.

Run it directly (``python examples/thermal_range_assembly.py``); :func:`card` and
:func:`repaired_card` are also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis.optomechanics import (
    BreathingMitigation,
    SurfaceLimits,
    SurfaceTreatment,
    athermal_focus_scorecard,
    cycling_retention_scorecard,
    preload_temperature_scorecard,
    seal_breathing_scorecard,
    seal_gland_extremes_scorecard,
    surface_limits_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

q = Quantity.parse
ASSEMBLED, COLD, HOT = q("20 degC"), q("-40 degC"), q("71 degC")
ALUMINIUM_CTE = q("23.6e-6 1/K")


def _card(*, cement_hottest: str, mitigation: BreathingMitigation | None) -> Scorecard:
    surfaces = (
        SurfaceLimits(
            surface="doublet cement",
            treatment=SurfaceTreatment.CEMENT,
            coldest=q("-55 degC"),
            hottest=q(cement_hottest),
        ),
        SurfaceLimits(
            surface="front AR coating",
            treatment=SurfaceTreatment.COATING,
            coldest=q("-62 degC"),
            hottest=q("100 degC"),
        ),
    )
    return Scorecard(
        entries=(
            athermal_focus_scorecard(
                "focus at the hot extreme",
                focal_length=q("50 mm"),
                f_number=2.8,
                wavelength=q("550 nm"),
                refractive_index=1.5168,
                dn_dt=q("2.4e-6 1/K"),
                glass_cte=q("7.1e-6 1/K"),
                housing_cte=q("1.3e-6 1/K"),  # an Invar spacer sets the lens-to-detector length
                housing_length=q("50 mm"),
                temperature_change=q("51 K"),
            ),
            preload_temperature_scorecard(
                "lens preload across the range",
                preload=q("40 N"),
                axial_stiffness=q("2e6 N/m"),
                edge_thickness=q("5 mm"),
                glass_cte=q("7.1e-6 1/K"),
                cell_cte=ALUMINIUM_CTE,
                cold_change=q("-60 K"),
                hot_change=q("51 K"),
                max_preload=q("200 N"),
            ),
            seal_gland_extremes_scorecard(
                "housing O-ring",
                cross_section_diameter=q("1.78 mm"),
                inner_diameter=q("40 mm"),
                gland_depth=q("1.4 mm"),
                groove_width=q("2.4 mm"),
                groove_diameter=q("40 mm"),
                elastomer_cte=q("2.3e-4 1/K"),
                gland_cte=ALUMINIUM_CTE,
                assembly_temperature=ASSEMBLED,
                cold=COLD,
                hot=HOT,
            ),
            seal_breathing_scorecard(
                "sealed volume breathing",
                fill_pressure=q("101.325 kPa"),
                fill_temperature=ASSEMBLED,
                cold=COLD,
                hot=HOT,
                cycles=500,
                mitigation=mitigation,
            ),
            surface_limits_scorecard(
                "cement and coating ratings", surfaces=surfaces, cold=COLD, hot=HOT
            ),
            cycling_retention_scorecard(
                "focus retention after cycling",
                requirement="focus within the 8.6 µm depth of focus",
                cycles=500,
                test_method="a thermal-cycling test with focus measured before and after",
            ),
        )
    )


def card() -> Scorecard:
    """The assembly as drawn: a cement rated to 60 °C, and a seal with nothing behind it."""
    return _card(cement_hottest="60 degC", mitigation=None)


def repaired_card() -> Scorecard:
    """The repair: a cement rated to 85 °C, and a desiccant in the sealed volume."""
    return _card(cement_hottest="85 degC", mitigation=BreathingMitigation.DESICCANT)


def main() -> None:
    for label, scorecard in (("as drawn", card()), ("repaired", repaired_card())):
        print(f"{label}: {scorecard.status.value}")
        for entry in scorecard.entries:
            print(f"  {entry}")


if __name__ == "__main__":
    main()
