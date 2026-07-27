"""Worked example: the journal bearing that lives or dies by surface finish.

A 50 mm turbine-auxiliary journal bearing (50 mm long, 20 um radial clearance) carries
5 kN at 3,000 rpm on ISO VG32 oil at 0.018 Pa*s. The film calculation itself is
healthy: 2 MPa of unit load, a Sommerfeld number of 0.70, and -- at the eccentricity
ratio of 0.6 read from the Raimondi-Boyd charts for this operating point (a
user-supplied chart value, like any allowable) -- a minimum oil film of h0 = c*(1 - eps)
= 8 um. Petroff's estimate puts the friction loss around 440 W, a number the oil
cooler was sized for.

But 8 um only counts if the surfaces hiding under it are smaller still. The specific
film ratio lambda = h0 / sqrt(Ra_j^2 + Ra_b^2) is the regime gate: lambda >= 3 is
full-film hydrodynamic operation, 1-3 is mixed lubrication with asperity contact, and
below 1 the bearing runs metal on metal. With the drawing's ground journal (Ra 0.4 um)
against the bored-and-honed bush (Ra 0.8 um), lambda = 8.9 -- comfortably full-film.
A cost-reduction proposal to accept turned finishes (Ra 3.2 um on both) keeps every
other number identical and drops lambda to 1.8: the same bearing, the same oil, the
same 8 um film, now operating in mixed lubrication and wearing from day one.

The lesson is that the film thickness a bearing computes and the film thickness it
*gets to use* are separated by the roughness under it -- the finish callout is a
load-bearing dimension. Protect the grinding operation, or buy back lambda with more
clearance, more viscosity, or less load.

Run it directly (``python examples/journal_bearing_film_regime.py``);
:func:`screen_ground_journal` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    journal_bearing_minimum_film_thickness,
    journal_bearing_unit_load,
    petroff_friction_power,
    sommerfeld_number,
    specific_film_ratio,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

JOURNAL_RADIUS = Quantity.parse("25 mm")
BEARING_LENGTH = Quantity.parse("50 mm")
RADIAL_CLEARANCE = Quantity.parse("20 um")
RADIAL_LOAD = Quantity.parse("5 kN")
SPEED = Quantity.parse("3000 rpm")
VISCOSITY = Quantity.parse("0.018 Pa*s")  # ISO VG32 at operating temperature

# Raimondi-Boyd chart read for this Sommerfeld number and L/D = 1 (user-supplied).
ECCENTRICITY_RATIO = 0.6

GROUND_JOURNAL_RA = Quantity.parse("0.4 um")
HONED_BUSH_RA = Quantity.parse("0.8 um")
TURNED_RA = Quantity.parse("3.2 um")  # the cost-reduction finish, both surfaces

FULL_FILM_LAMBDA = 3.0  # lambda >= 3: full-film (hydrodynamic) regime


def _film_thickness() -> Quantity:
    return journal_bearing_minimum_film_thickness(
        radial_clearance=RADIAL_CLEARANCE,
        eccentricity_ratio=ECCENTRICITY_RATIO,
    )


def _screen(name: str, journal_ra: Quantity, bush_ra: Quantity) -> Scorecard:
    lam = specific_film_ratio(
        minimum_film_thickness=_film_thickness(),
        journal_roughness=journal_ra,
        bush_roughness=bush_ra,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                name,
                computed=lam / FULL_FILM_LAMBDA,
                required=1.0,
            ),
        )
    )


def screen_ground_journal() -> Scorecard:
    """Screen the drawing's finishes: ground journal on honed bush runs full-film."""
    return _screen("film ratio, ground journal / honed bush", GROUND_JOURNAL_RA, HONED_BUSH_RA)


def screen_turned_finishes() -> Scorecard:
    """Screen the cost-cut finishes: the same film is mixed-lubrication over turned surfaces."""
    return _screen("film ratio, turned journal and bush", TURNED_RA, TURNED_RA)


def main() -> None:
    unit_load = journal_bearing_unit_load(
        radial_load=RADIAL_LOAD,
        journal_diameter=Quantity(magnitude=2 * JOURNAL_RADIUS.to("mm").magnitude, unit="mm"),
        bearing_length=BEARING_LENGTH,
    )
    s_number = sommerfeld_number(
        journal_radius=JOURNAL_RADIUS,
        radial_clearance=RADIAL_CLEARANCE,
        viscosity=VISCOSITY,
        speed=SPEED,
        unit_load=unit_load,
    )
    friction = petroff_friction_power(
        viscosity=VISCOSITY,
        speed=SPEED,
        journal_radius=JOURNAL_RADIUS,
        bearing_length=BEARING_LENGTH,
        radial_clearance=RADIAL_CLEARANCE,
    )
    print(f"unit load: {unit_load.to('MPa').magnitude:.1f} MPa")
    print(f"Sommerfeld number: {s_number:.2f}")
    print(f"minimum film: {_film_thickness().to('um').magnitude:.1f} um")
    print(f"Petroff friction loss: {friction.to('W').magnitude:.0f} W")
    print("\nground journal / honed bush:")
    print(screen_ground_journal())
    print("\nturned finishes (cost proposal):")
    print(screen_turned_finishes())


if __name__ == "__main__":
    main()
