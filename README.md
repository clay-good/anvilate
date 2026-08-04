# Anvilate

*anvil + validate* — describe a mechanical part, get back a physics-validated pass/fail where **every check cites the code it came from**.

![Anvilate screening a cantilever bracket and a lifting lug, then exporting a DXF](docs/demo.gif)

Anvilate is a **local-first, open-source** design tool for mechanical, structural, and industrial engineers. It runs the analytical screens you'd otherwise do by hand in a spreadsheet — bending, deflection, buckling, resonance, bolted and welded connections, contact, thick-wall pressure, tolerance stack-ups — and rolls them into one scorecard that **won't hand you a silent green**. No cloud, no LLM required, no account.

> **Status: pre-alpha (v0.0.1).** The deterministic engineering core is real, tested, and runnable today. The natural-language front end, 3D geometry, FEA, and STEP export described under [Where this is going](#where-this-is-going) are still being built.

## Quickstart

Python 3.11+.

```bash
git clone https://github.com/clay-good/anvilate.git
cd anvilate
python -m venv .venv && source .venv/bin/activate
pip install -e ".[export]"      # drop [export] if you don't need DXF output
```

Run any of the worked examples — each is self-contained, needs no network, and prints a scorecard:

```bash
python examples/cantilever_bracket_check.py
```

```text
[PASS] bending yield: safety factor 1.84 vs required minimum 1.50
[FAIL] tip deflection: deflection 36.284 mm vs limit 15.000 mm
scorecard FAIL (2 checks)
```

The aluminum bracket is strong enough but too bendy — the deflection screen catches what a yield-only hand check would wave through.

## Write your own screen

The whole flow is: pull a material, describe the geometry and load, roll the checks into a `Scorecard`.

```python
from anvilate.analysis import (
    cantilever_end_load, rectangular_second_moment,
    strength_scorecard, deflection_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

al = default_materials_db().get("AA-6061-T6")
I = rectangular_second_moment(Quantity.parse("20 mm"), Quantity.parse("10 mm"))

beam = cantilever_end_load(
    force=Quantity.parse("100 N"),
    length=Quantity.parse("500 mm"),
    second_moment=I,
    extreme_fibre=Quantity.parse("5 mm"),
    elastic_modulus=al.elastic_modulus.quantity,
)

card = Scorecard(entries=(
    strength_scorecard("bending yield", stress=beam.max_bending_stress,
                       allowable=al.yield_strength.quantity, required=1.5),
    deflection_scorecard("tip deflection", deflection=beam.max_deflection,
                         limit=Quantity.parse("15 mm")),
))
print(card)   # scorecard FAIL (2 checks)
```

Units are first-class (SI and US customary — mix `kip`, `ksi`, `in`, `mm`, `MPa` freely); materials come from a provenance-tagged database; safety factors and citations travel with every result.

## What you can do today

Over 150 runnable examples, each executed in CI so they stay honest. A few:

| Run this | What it shows |
|---|---|
| `machine_on_floor_beam.py` | Declaring where a load *actually* sits recovers real margin the worst-case mid-span guess throws away (FAIL 1.19 → PASS 1.58). |
| `beam_bearing_web_checks.py` | A beam's end reaction is checked two ways (AISC §J10.2 web yielding *and* §J10.3 crippling); the thin web buckles at 213 kN before it crushes at 316 kN, so crippling governs. |
| `hss_beam_flexure_shear.py` | A square HSS with a noncompact flange: the naive plastic moment reads 394 kN·m, but AISC §F7 flange local buckling cuts the real capacity to 368 kN·m (7% lower). See [hot-rolled steel](docs/hot-rolled-steel.md). |
| `bolted_tension_splice.py` | Gross yielding (621 kN) and net-section rupture (544 kN) both pass, but AISC §J4.3 block shear tears the end block out first at 450 kN — the limit state a member-only check never sees. |
| `plate_girder_design.py` | A deep welded girder: the slender web docks bending 5.6% (AISC §F5 R_pg) yet, once stiffened, nearly doubles the shear via §G2.2 tension-field action (832 → 1468 kN). |
| `spur_gear_agma_check.py` | An AGMA spur gear checked for both tooth-root bending and surface pitting — pitting runs the higher utilization (0.69 vs 0.39), the mode a Lewis bending-only check never flags. |
| `pipe_expansion_loop.py` | A B31.3 thermal-expansion bend: the elbow's stress-intensification factor makes it work 73% harder than the straight-pipe stress calc predicts (S_E/S_A 0.84 vs 0.48). |
| `gear_shaft_assembly.py` | One gear shaft, three coupled subsystems: DE-Goodman fatigue sets the 28.5 mm diameter, then the key length and bearing L10 life follow from it — no single check is the design. |
| `rc_t_beam_floor.py` | A monolithic RC floor beam: counting the slab as a compression flange (ACI T-beam) adds strength and drives the net tensile strain to 0.024 — far past the 0.005 ductility limit the bare web barely meets. |
| `lug_drawing.py` | Code-check a lifting lug (ASME BTH-1), then export its outline to a fabrication-ready DXF. |
| `column_base_plate.py` | A base plate checked for concrete bearing (AISC J8) *and* plate bending (Design Guide 1) — bearing passes, the thin plate fails. |
| `motor_mount_resonance.py` | A mount that's statically bulletproof but resonates below running speed — the dimension a static hand calc never sees. |
| `hydraulic_cylinder_wall.py` | The thin-wall formula reads a comfortable pass; the exact Lamé solution says the barrel fails. |
| `tolerance_stackup.py` | A 1D stack-up worst-case rejects the design, yet Monte Carlo predicts 99%+ assembly yield. |
| `lifting_lug_calc_report.py` | The same padeye screening rendered as a submittal: formula, substituted values, result, and clause for every check. See [calculation reports](docs/calculation-reports.md). |
| `sheave_repair_from_inverse.py` | A failing bending check that carries its own fix: a design inverse names the sheave diameter that lands the margin in one solve. See [typed repair feedback](docs/repair-feedback.md). |
| `bracket_load_scatter_fragility.py` | A bracket that passes at SF 1.70 nominal but falls below the required 1.5 one run in five once the load scatters ±15% — a shortfall probability no single-point check reports. See [uncertainty margins](docs/uncertainty-margins.md). |
| `canopy_beam_load_combinations.py` | A light canopy whose bending is sized by one ASCE 7-22 combination and whose hold-down by another — a wind uplift the gravity cases never show. See [load combinations](docs/load-combinations.md). |
| `braced_frame_column_seismic.py` | A gravity column comfortable in compression whose base connection is governed by the net tension an ASCE 7-22 §2.3.6 seismic reversal produces — a load the gravity cases never reveal. |
| `spec_load_combination_check.py` | A Design Spec whose load cases are classified by nature, aggregated into a demand mapping and screened against the governing ASCE 7-22 combination — load combinations as part of the same validated flow, not a separate spreadsheet. |
| `welded_bracket_fatigue.py` | The same stress spectrum passes on a category-90 weld detail and fails on a category-56 one — the EN 1993-1-9 detail category, not the stress, decides fatigue life. |
| `power_device_heatsink.py` | A 30 W device whose junction cooks in still air (145 K rise) and survives with a fan (44 K) — a thermal resistance network where the convection to air governs. See [thermal screening](docs/thermal-screening.md). |
| `process_pipe_schedule.py` | An ASME B31.3 process line where Schedule 10 fails and Schedule 40 passes the service pressure once mill tolerance and corrosion are taken off the wall — rate the wall you keep, not the one stamped on the pipe. |
| `floor_joist_wet_service.py` | An NDS timber joist that passes dry and fails wet — the wet-service factor C_M in the adjustment chain is the whole difference. See [timber screening](docs/timber-screening.md). |
| `cold_formed_stud_flange.py` | A cold-formed flange that is only 59% effective at 1.5 mm and fully effective at 3.5 mm — the AISI Winter effective-width reduction that sets cold-formed design apart. See [cold-formed steel](docs/cold-formed-steel.md). |
| `aluminum_ladder_rail.py` | A 6061-T6 strut whose low modulus makes it buckle (ADM curve) at 107 MPa — giving away 55% of the 240 MPa strength it reaches in tension. |
| `cfrp_ply_anisotropy.py` | A unidirectional carbon/epoxy ply is 139 GPa along the fibers but only 9 GPa across (16:1) — the rule of mixtures that explains why laminates cross-ply. |
| `rc_floor_beam.py` | A reinforced-concrete floor beam whose reinforcement develops 321 kN·m, and the ACI 318 design inverse for the steel a 400 kN·m demand needs. See [reinforced concrete](docs/reinforced-concrete.md). |
| `retaining_wall_stability.py` | One retaining wall, three external-stability checks (TMS/geotech): overturning and sliding both pass, but the resultant leaves the middle third so the heel lifts and bearing governs — no single number says the wall stands. |
| `slope_stability_rain.py` | A 35° cut steeper than its friction angle: friction alone can't hold it, cohesion does, and saturation (pore pressure) nearly undoes it — why slopes stand for years then fail in a storm. |
| `pump_selection_from_line.py` | The whole hydraulics chain — Darcy friction + fittings + static lift → total head → hydraulic and shaft power → specific speed → centrifugal — from pipe geometry to a motor nameplate. |
| `vfd_pump_energy_saving.py` | The pump affinity laws: backing a pump to 80% speed with a VFD trades a fifth less flow for nearly half the power — the cube law that is the whole case for variable-speed drives. |
| `masonry_wall_slenderness.py` | A TMS 402 masonry wall its gravity check passes at f_a/F_a = 0.52, but adding out-of-plane wind drives the combined unity ratio past 1.0 — the interaction, not either stress, sizes it. |

Full annotated gallery: [`examples/README.md`](examples/README.md).

What's implemented: a units layer, the typed **Design Spec IR**, a standards/materials database (materials, fasteners, bearings, NEMA, dowels, T-slot), the T1 analytical library above, ISO 286 fits + tolerance stack-ups + DFM process-capability checks, an auditable evidence/provenance roll-up, DXF export, and a structural discipline pack (beams, columns, beam-columns, bolted/welded connections, base plates, lugs, gussets — AISC 360 / ACI 318 / ASME BTH-1, every check citing its clause). The analytical library reaches past the mechanical/structural core into neighboring disciplines the same engineers work in — **geotechnical** (Rankine earth pressure, Terzaghi bearing capacity, consolidation settlement, retaining-wall stability, slope stability), **hydraulics** (Darcy-Weisbach pipe flow, open-channel Manning flow, pump sizing and affinity laws, differential-pressure metering, fluid statics), and **masonry** (TMS 402 allowable-stress design) — each closed-form, dimension-checked, and hand-verified. Every check also renders as a reviewable [calculation report](docs/calculation-reports.md) — formula, substituted values, result, and clause. On top of the scorecard sit three cross-cutting layers that keep a green from being a silent one: [typed repair feedback](docs/repair-feedback.md) (a failing check names the parameter and the value that fixes it; a two-sided band flags over-engineering), [uncertainty-aware margins](docs/uncertainty-margins.md) (input scatter propagated to a shortfall probability and a sensitivity ranking), and [ASCE 7-22 load combinations](docs/load-combinations.md) (the governing combination named, including the counteracting uplift case a gravity-only check misses).

## Where this is going

The screens above are the trustworthy core. The end goal is to wrap them so a plain-English request compiles into that same validated scorecard *and* a parametric solid you can open in CATIA, SolidWorks, or NX:

```
 natural language ──► typed Design Spec ──► parametric B-Rep geometry
        ▲                                          │
        │                                          ▼
   human review ◄── validation report ◄── physics + DFM + FEA checks
        │                                          │
        └───────── agent self-corrects ◄───────────┘  (until checks pass)
                            │
                            ▼
              STEP AP242 · DXF · 2D drawing · source code
```

The LLM is a replaceable component that only writes the spec and proposes edits; the geometry and validation pipeline is deterministic and runs identically with or without any AI. Nothing unvalidated leaves the tool.

The behavioral contract for every subsystem is specified up front in [`openspec/specs/`](openspec/specs/) — that's the authoritative design reference, including the roadmap, non-goals, and risk analysis.

## License

MIT — see [LICENSE](LICENSE). GPL-licensed analysis engines (Gmsh, CalculiX) are invoked as separate subprocesses with file-based interchange, keeping Anvilate's own code MIT.
