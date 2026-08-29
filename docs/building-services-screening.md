# Building-services screening

Four discipline packs that ship, are tested, and until now appeared in no documentation at
all: a worker's noise dose, a lighting layout, a zone's outdoor air, and a feeder's voltage
drop. Each takes a declared installation and returns the same scorecard every other pack
returns, with the same rules — a check that could not run reports `not_evaluated`, every
entry cites its clause, and nothing here is a certified design.

They share a shape. You declare what you have; the pack computes what the code requires and
divides one by the other. The safety factor is always *capacity over demand*, so a factor
below 1 is a failure whichever direction the underlying quantity runs — a noise **dose** of
133% and an illuminance **shortfall** both come out as a factor under 1.

## Noise dose — OSHA 29 CFR 1910.95

```python
from anvilate.packs.noise_exposure import WorkerNoiseExposure, screen_noise_exposure
from anvilate.units import Quantity

card = screen_noise_exposure(
    WorkerNoiseExposure(
        machine_levels=(92.0, 90.0),          # dBA at the operator's ear
        exposure_duration=Quantity.parse("6 hour"),
    )
)
```

```text
noise dose   FAIL   safety factor 0.75 vs required minimum 1.00
             OSHA 29 CFR 1910.95 / NIOSH REL — 90 dBA criterion, 5 dB exchange rate
```

Two machines at 92 and 90 dBA combine logarithmically, not arithmetically: the pair is
louder than either. Six hours at that combined level is over the permissible dose, and the
factor says so at 0.75.

The criterion is a parameter, because it is a *policy* choice and not a fact. OSHA's 90 dBA
with a 5 dB exchange rate is the default; NIOSH's 85 dBA with a 3 dB exchange is stricter
and is what a hearing-conservation programme is usually written against. Passing under one
and failing under the other is the ordinary case, which is why the reference names which
was applied.

## Lighting — IES illuminance against an energy-code power density

```python
from anvilate.packs.lighting import LightingInstallation, screen_lighting

card = screen_lighting(
    LightingInstallation(
        luminaire_count=20,
        lumens_per_luminaire=Quantity.parse("3400 lumen"),
        input_watts_per_luminaire=Quantity.parse("30 W"),
        coefficient_of_utilization=0.62,
        light_loss_factor=0.8,
        floor_area=Quantity.parse("80 m**2"),
        required_illuminance=Quantity.parse("400 lux"),
        allowable_power_density=Quantity.parse("8.8 W/m**2"),
    )
)
```

```text
task illuminance        PASS   safety factor 1.05 vs required minimum 1.00
                        IES Lighting Handbook — recommended task illuminance
lighting power density  PASS   safety factor 1.17 vs required minimum 1.00
                        ASHRAE 90.1 / IECC — lighting power density allowance
```

**Two checks that pull against each other, which is the point of screening them together.**
Adding luminaires raises the illuminance and the power density at the same time, so a layout
can be fixed for one and broken for the other by the same edit. This one clears both, with
5% and 17% in hand.

The lumen method is a design estimate, not a photometric prediction: the coefficient of
utilisation and the light loss factor are the room and the maintenance schedule, both
supplied by the designer, and neither is something a screen can derive from a floor area.

## Ventilation — ASHRAE 62.1 outdoor air, and air changes

```python
from anvilate.packs.ventilation import VentilationZone, screen_ventilation

card = screen_ventilation(
    VentilationZone(
        people_outdoor_rate=Quantity.parse("5 ft**3/min"),
        occupancy=50.0,
        area_outdoor_rate=Quantity.parse("0.06 ft**3/min/ft**2"),
        floor_area=Quantity.parse("5000 ft**2"),
        zone_air_distribution_effectiveness=0.8,
        provided_outdoor_airflow=Quantity.parse("800 ft**3/min"),
        room_volume=Quantity.parse("50000 ft**3"),
        required_air_changes=0.5,
    )
)
```

```text
outdoor air            PASS   safety factor 1.16 vs required minimum 1.00
                       ASHRAE 62.1 ventilation-rate procedure (Voz)
air changes per hour   PASS   safety factor 1.92 vs required minimum 1.00
                       application minimum air changes per hour
```

62.1's ventilation-rate procedure is two terms added and then divided: a per-person rate
times the occupancy, plus a per-area rate times the floor area, all over the zone air
distribution effectiveness E_z. **E_z is a divisor, so a poorly distributed zone needs
*more* air, not less** — 0.8 here raises the requirement by 25% over a perfectly mixed zone,
and it is the term most often left at 1.0 by accident.

Air changes is the separate, blunter check some applications carry, and it is not implied by
the first: a large volume can meet its outdoor-air requirement and still turn over slowly.

## Feeder — NEC voltage drop and conductor ampacity

```python
from anvilate.packs.electrical import Feeder, screen_feeder

card = screen_feeder(
    Feeder(
        load_power=Quantity.parse("37 kW"),
        power_factor=0.85,
        line_voltage=Quantity.parse("480 V"),
        resistivity=Quantity.parse("1.68e-8 ohm*m"),
        one_way_length=Quantity.parse("100 m"),
        conductor_area=Quantity.parse("35 mm**2"),
        conductor_ampacity=Quantity.parse("115 A"),
    )
)
```

```text
voltage drop         PASS   safety factor 3.89 vs required minimum 1.00
                     NEC 210.19(A)/215.2 informational note — feeder voltage drop
conductor ampacity   PASS   safety factor 2.20 vs required minimum 1.00
                     NEC 310.16 — conductor ampacity
```

The current comes from the power, the voltage and the power factor together — a 37 kW load
at 0.85 pf draws more than the same load at unity, and using the kW figure directly is the
classic undersizing. The drop is over the round trip, not the one-way run, so the length
declared is one way and the calculation doubles it.

NEC's voltage-drop guidance is an informational note rather than a requirement, and the
`drop_limit_percent` is the designer's; ampacity is a requirement, and the ampacity supplied
is the table value after the derations that apply to the installation — the pack does not
apply them, because the conditions that set them are not in the model.

## What these are not

Screening. Every entry carries its clause and the screening label, engineering sign-off
stays with the engineer of record, and none of these replaces a photometric model, an
airflow simulation, or a coordinated study. They exist to catch the layout that was never
going to work before anybody draws it.
