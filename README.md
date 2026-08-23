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

484 runnable examples, each executed in CI so they stay honest. A few:

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
| `feature_control_frame_legality.py` | Five drawing callouts that do not parse — flatness to a datum, perpendicularity to nothing, Ⓜ on a surface, symmetry on a 2018 drawing, a fourth datum — refused with the reason, plus what a position tolerance contributes to a 1D stack. See [semantic GD&T](docs/semantic-gdt.md). |
| `frame_member_forces_to_checks.py` | A Pynite frame export screened by cited AISC checks: the axis mapping and the axial sign convention are declared, not inferred — unflipped, a 180 kN compression reads as tension and the column is never checked for buckling. See [analysis interop](docs/analysis-interop.md). |
| `lifter_verification_matrix.py` | The calculation is not the evidence: a passing BTH-1 lifter's plan asks for a 125% proof load and a dimensional inspection, counts the check verified by analysis alone, names the one that did not run — and reports `not_evaluated` until a result is actually recorded. See [verification planning](docs/verification-planning.md). |
| `attested_evidence_bundle.py` | A screening result sealed so somebody else can re-check it: the same inputs rebuild the identical bundle digest, a materials-database bump moves it, a one-byte change to the drawing fails verification by name, and a signature nobody checked reports `not_evaluated` rather than pass. See [attested evidence](docs/evidence-attestation.md). |
| `plated_shaft_callouts_change_the_verdict.py` | Three drawing callouts that are check inputs, not annotations: reading the as-forged finish drops a shaft journal from a comfortable SF 2.52 to **1.08 — a FAIL**, plating moves a 60° thread's pitch diameter by *four* times its thickness, and a heat-treat condition no material record backs reports `not_evaluated` instead of screening the untreated row. See [typed callouts](docs/typed-callouts.md). |
| `lug_evidence_bundle_roll_up.py` | One lug in four states, and only one of them is verified: checks-only passes while naming what it does not cover, a written-but-unperformed proof-load plan drops the same scorecard to `not_evaluated`, performing it earns `test-verified`, and a review the design moved under pulls it back down. See [the evidence bundle](docs/evidence-bundle.md). |
| `lug_scorecard_as_qif.py` | The same lug handed to quality software as QIF Results (ISO 23952): five checks cross as five characteristics, the over-margin weld reads `PASS` with the finding in its description, and the tear-out check that never ran crosses as `NOT_ANALYZED` carrying the requirement it would have been judged against — omitting it would have turned a file with one honest gap into a file of four characteristics every one of which was evaluated — a part whose failure mode nobody looked at, reported as one fully examined. A verdict-only deflection check becomes QIF's attribute gauge rather than getting an invented threshold. See [quality interchange](docs/quality-interchange.md). |
| `measured_shaft_from_certificate.py` | The other direction: a Digital Calibration Certificate read as a measured input. A 25 mm shaft called to ISO 286 h6 measures 25.0004 mm and **fails by 0.4 µm** — but the laboratory's own expanded uncertainty is ±1.2 µm at k=2, three times the overshoot, so the measurement is consistent with an in-tolerance shaft a quarter of the time and the screen says so. The certificate's value is a draft until somebody named confirms it, its certificate is unsigned and the provenance says so — had it been signed, it would read *present and not verified*, because there is no third state an offline tool can honestly claim. See [quality interchange](docs/quality-interchange.md). |
| `rfq_sheet_to_confirmed_inputs.py` | A customer sheet that contradicts itself: five quantities taken from eight labelled lines and three recorded as *not* taken, a design load stated as both 50 kN and 45 kN with neither chosen, and a release that stays blocked even after both sides are confirmed — two values for one field is not a field. See [requirements ingestion](docs/requirements-ingestion.md). |
| `lightest_passing_bracket.py` | Eighty-one brackets swept in milliseconds: the lightest one in the box fails, the lightest that *passes* is 3.75x heavier, and a 20-point budget spent on a grid finds nothing where the same budget on a Halton sequence finds seven. See [design-space exploration](docs/design-space-exploration.md). |
| `canopy_beam_load_combinations.py` | A light canopy whose bending is sized by one ASCE 7-22 combination and whose hold-down by another — a wind uplift the gravity cases never show. See [load combinations](docs/load-combinations.md). |
| `braced_frame_column_seismic.py` | A gravity column comfortable in compression whose base connection is governed by the net tension an ASCE 7-22 §2.3.6 seismic reversal produces — a load the gravity cases never reveal. |
| `spec_load_combination_check.py` | A Design Spec whose load cases are classified by nature, aggregated into a demand mapping and screened against the governing ASCE 7-22 combination — load combinations as part of the same validated flow, not a separate spreadsheet. |
| `welded_bracket_fatigue.py` | The same stress spectrum passes on a category-90 weld detail and fails on a category-56 one — the EN 1993-1-9 detail category, not the stress, decides fatigue life. See [weld fatigue](docs/weld-fatigue-screening.md). |
| `isolator_amplifies_at_running_speed.py` | A 1450 rpm pump whose "reassuringly firm" 0.5 mm pad sits at f/f_n = 1.08 and passes 5.7x what a rigid bolt-down would — and whose 11 ms transport shock then inverts the question, since the half-sine shock spectrum peaks at 1.77 and softening a mount helps on one side of that peak and hurts on the other. See [thermal screening](docs/thermal-screening.md). |
| `lipped_channel_dsm.py` | One cold-formed lipped channel, three unbraced lengths, three *different* governing buckling modes — distortional at 1 m (150.8 kN), local at 3 m (82.5 kN), global at 6 m (21.9 kN). A thicker web fixes the first and does nothing for the third. See [cold-formed steel](docs/cold-formed-steel.md). |
| `power_device_heatsink.py` | A 30 W device whose junction cooks in still air (145 K rise) and survives with a fan (44 K) — a thermal resistance network where the convection to air governs. See [thermal screening](docs/thermal-screening.md). |
| `process_pipe_schedule.py` | An ASME B31.3 process line where Schedule 10 fails and Schedule 40 passes the service pressure once mill tolerance and corrosion are taken off the wall — rate the wall you keep, not the one stamped on the pipe. |
| `floor_joist_wet_service.py` | An NDS timber joist that passes dry and fails wet — the wet-service factor C_M in the adjustment chain is the whole difference. See [timber screening](docs/timber-screening.md). |
| `timber_header_bearing_governs.py` | A short header whose bending (SF 1.25) and shear (1.14) both pass while it crushes at its support (0.96) — bending demand falls with L², the bearing stress at the support doesn't fall at all. |
| `timber_post_slenderness.py` | The same 4x4 under the same 4,000 lb passes at 8 ft (SF 1.70) and fails at 12 ft (0.82) as the NDS column stability factor collapses from 0.41 to 0.20 — and at 16 ft the §3.7.1.4 slenderness cap makes the screen refuse rather than quote a plausible number. |
| `cold_formed_stud_flange.py` | A cold-formed flange that is only 59% effective at 1.5 mm and fully effective at 3.5 mm — the AISI Winter effective-width reduction that sets cold-formed design apart. See [cold-formed steel](docs/cold-formed-steel.md). |
| `aluminum_ladder_rail.py` | A 6061-T6 strut whose low modulus makes it buckle (ADM §E.3) at 91 MPa — giving away 62% of the 240 MPa strength it reaches in tension. The 0.85 out-of-straightness knockdown in that branch is 17.6% of the answer. See [aluminum screening](docs/aluminum-screening.md). |
| `spreader_beam_bth1_category.py` | The same 3 m spreader beam at 107.6 MPa in bending: ASME BTH-1 Category A allows 124.0 MPa and Category B allows 82.7 MPa, so it passes at SF 1.15 and fails at 0.77 on identical steel under an identical load — and its 50,000-cycle life is Service Class 1, so the fatigue row is not evaluated rather than passed. See [lifting devices](docs/lifting-devices.md). |
| `pressure_vessel_nozzle_and_flange.py` | The same 800 mm vessel at two wall thicknesses: at 14 mm everything passes, and at 8 mm the shell still passes (SF 1.11) while the 6-inch opening fails at 0.49 — UG-37 credits the wall's *excess* over what pressure alone needs, and the excess vanishes faster than the wall: the shell's own margin falls 1.9x (2.14 to 1.11) while the opening's falls 3.4x (1.66 to 0.49). Its flange shows the second trap: the seating load is larger (400.0 vs 218.7 kN) and the operating condition still governs once each is divided by its own allowable, so the one-allowable shortcut lands 36% short. See [pressure equipment](docs/pressure-equipment.md). |
| `bracket_reviewer_dossier.py` | Four checks reordered for the engineer who has to decide where to look: the **unevaluated** fatigue check sorts ahead of the failing deflection one, and a check passing at SF 3.0 is still surfaced because nobody recorded where its allowable came from. A recorded exception never turns the failure into a pass, and trimming the section invalidates the prior review rather than carrying it across. See [responsible-charge review](docs/responsible-charge-review.md). |
| `retrofit_two_code_editions.py` | A 2018 frame designed to AISC 360-16 with a new mezzanine to -22: the new work alone passes, the combined bundle **fails** naming both editions, and it passes once the engineer of record records who accepted the mix and why. Nothing about the structural checks changed — what failed is the claim the bundle was making about itself. See [standards effectivity](docs/standards-effectivity.md). |
| `bracket_redesign_embodied_carbon.py` | A 12 kg steel bracket machined at a 35% yield starts as a 34.3 kg billet: the swarf carries 65% of the 53.1 kgCO2e cradle-to-gate estimate, and a near-net stamping at 88% yield lands at 16.7 — the lighter part is not automatically the lower-carbon one, the yield is. Mixing EN 15978 module scopes is refused and a material with no factor comes back not evaluated, never zero. See [embodied carbon screening](docs/embodied-carbon-screening.md). |
| `vessel_surface_flaw_fad.py` | A 4 mm x 40 mm surface flaw in a 20 mm vessel shell placed on the BS 7910 failure assessment diagram: K_r 0.367 at service looks like 2.73 in hand and the real load-line margin is 1.71, because L_r rides out with it — and the same flaw on a Charpy-correlated toughness comes back not evaluated rather than passing. See [fitness-for-service screening](docs/fitness-for-service-screening.md). |
| `welded_aluminum_platform_beam.py` | The same 6061-T6 platform beam under the same 100 MPa: passes unwelded (SF 1.79, 178.5 MPa allowed) and fails welded (SF 0.87, 87.4 MPa) — welding halves the temper permanently, and a member declared welded with no weld-affected properties comes back not evaluated rather than falling back to parent metal. See [aluminum screening](docs/aluminum-screening.md). |
| `cfrp_ply_anisotropy.py` | A unidirectional carbon/epoxy ply is 139 GPa along the fibers but only 8.6 GPa across (16:1) — the rule of mixtures that explains why laminates cross-ply. |
| `rc_floor_beam.py` | A reinforced-concrete floor beam whose reinforcement develops 321 kN·m, and the ACI 318 design inverse for the steel a 400 kN·m demand needs. See [reinforced concrete](docs/reinforced-concrete.md). |
| `retaining_wall_stability.py` | One retaining wall, three external-stability checks (TMS/geotech): overturning and sliding both pass, but the resultant leaves the middle third so the heel lifts and the toe pressure climbs to 148 kPa — no single number says the wall stands. |
| `slope_stability_rain.py` | A 35° cut steeper than its friction angle: friction alone can't hold it, cohesion does, and saturation (pore pressure) nearly undoes it — why slopes stand for years then fail in a storm. |
| `pump_selection_from_line.py` | The whole hydraulics chain — Darcy friction + fittings + static lift → total head → hydraulic and shaft power → specific speed → centrifugal — from pipe geometry to a motor nameplate. |
| `vfd_pump_energy_saving.py` | The pump affinity laws: backing a pump to 80% speed with a VFD trades a fifth less flow for nearly half the power — the cube law that is the whole case for variable-speed drives. |
| `masonry_wall_slenderness.py` | A TMS 402 masonry wall its gravity check passes at f_a/F_a = 0.52, but adding out-of-plane wind drives the combined unity ratio past 1.0 — the interaction, not either stress, sizes it. |

Full annotated gallery: [`examples/README.md`](examples/README.md).

What's implemented: a units layer, the typed **Design Spec IR**, a standards/materials database (materials, fasteners, bearings, NEMA, dowels, T-slot, ASME B36.10M pipe schedules), the T1 analytical library above (236 closed-form modules and 1,811 public symbols, each dimension-checked and hand-verified, 3,166 tests), ISO 286 fits + tolerance stack-ups + DFM process-capability checks, an auditable evidence/provenance roll-up, DXF export, and discipline packs that turn a declared element into a cited PASS/FAIL scorecard — structural (beams, columns, beam-columns, bolted/welded connections, base plates, lugs, gussets — AISC 360 / ACI 318 / ASME BTH-1), industrial (pressure-loaded covers and panels), geotechnical (shallow footings, retaining walls, slopes, piles), hydraulics (pump duties and pipe runs), and masonry (TMS 402 walls), every check citing its clause. The analytical library reaches past the mechanical/structural core into neighboring disciplines the same engineers work in — **geotechnical** (Rankine earth pressure, Terzaghi bearing capacity, consolidation settlement, retaining-wall stability, slope stability — see [geotechnical screening](docs/geotechnical-screening.md)), **hydraulics** (Darcy-Weisbach pipe flow, open-channel Manning flow, pump sizing and affinity laws, differential-pressure metering, fluid statics — see [hydraulics screening](docs/hydraulics-screening.md)), **masonry** (TMS 402 allowable-stress design — see [masonry screening](docs/masonry-screening.md)), and **process piping** (ASME B31.3 pressure design on the wall you can rely on, and miter bends that rate well below the pipe they are made from — see [process piping](docs/process-piping.md)) — each closed-form, dimension-checked, and hand-verified. Every check also renders as a reviewable [calculation report](docs/calculation-reports.md) — formula, substituted values, result, and clause — and [what a citation means and how to check it](docs/citations.md) says exactly what that clause reference does and does not claim — including, now, the allowable *basis* every bundled strength carries: a handbook mean and a specified minimum were always different numbers, but the difference lived in prose inside a source string, and a check that needs a design allowable can now demand one and be refused. Contributors start at [adding a check](docs/contributing-analysis.md), the seven contract rules — and which of them a gate actually enforces, said plainly rather than implied: rules 1, 5 and 6 carry named gates, rule 2 says outright that it has none beyond review, and 3, 4 and 7 name no gate at all. On top of the scorecard sit three cross-cutting layers that keep a green from being a silent one: [typed repair feedback](docs/repair-feedback.md) (a failing check names the parameter and the value that fixes it; a two-sided band flags over-engineering), [uncertainty-aware margins](docs/uncertainty-margins.md) (input scatter propagated to a shortfall probability and a sensitivity ranking), and [ASCE 7-22 load combinations](docs/load-combinations.md) (the governing combination named, including the counteracting uplift case a gravity-only check misses). Because every check is closed-form and evaluates in microseconds, [design-space exploration](docs/design-space-exploration.md) sweeps them exhaustively and returns an exact Pareto front — the lightest design that *passes*, which in the worked bracket is 3.75x heavier than the lightest one in the box. Drawing callouts are typed too: a [semantic GD&T layer](docs/semantic-gdt.md) holds a feature control frame as data with Y14.5's grammar enforced in the constructor — flatness cannot reference a datum, Ⓜ cannot sit on a surface, and symmetry cannot appear on a 2018 drawing, because the 2018 edition removed it. Externally computed member forces and section properties come in through a typed doorway that makes every convention explicit — [analysis interop](docs/analysis-interop.md), where the axis mapping, the axial sign convention, and every component you chose *not* to screen are declared rather than inferred. And once the physics passes, [verification planning](docs/verification-planning.md) emits the physical test each check implies — a BTH-1 lifter's 125% proof load, a vessel's UG-99 hydrostatic — with the rule that a plan is never evidence: nothing performed reports `not_evaluated`, never a pass. Drawing callouts that are not geometry are typed too — [typed MBD callouts](docs/typed-callouts.md) makes surface finish, plating, and heat treatment the check inputs they always were: the finish derives the Marin surface factor, plating moves a fit by twice its thickness and a 60° thread's pitch diameter by four times it, a declared heat-treat condition no material record backs reports `not_evaluated`, and every callout carries a persistent characteristic identifier derived from what it *is* rather than what it says, so a revision reads as one change rather than a deletion and an addition. Work starts from a document, so [requirements ingestion](docs/requirements-ingestion.md) reads an RFQ sheet into a *draft* spec and refuses to release it while any load-bearing value is unconfirmed: no confidence scores (every value carries the line it came from instead), a bare number recorded as not-extracted rather than guessed at, and a sheet that contradicts itself reported rather than silently resolved. Every layer's output then assembles into [one evidence bundle](docs/evidence-bundle.md) with a single roll-up that is never better than its worst section: an absent layer is named rather than assumed, an unperformed verification plan drops a green scorecard to `not_evaluated` because a plan is not evidence, and a review the artifact moved under counts for less than no review at all. The whole result then seals as [attested evidence](docs/evidence-attestation.md): an in-toto statement whose subjects are the artifact digests and whose predicate carries the scorecard, the citations, a CycloneDX inventory of the environment, and a machine-readable AI-involvement disclosure — content-addressed, so the same inputs rebuild the identical digest and a materials-database bump visibly does not, and honest, because an unsigned bundle says so and a signature nobody checked reports `not_evaluated`. And because a scorecard is structurally a set of characteristics with requirements and actuals, the whole thing exports as [QIF Results](docs/quality-interchange.md) (ISO 23952) for CMM and quality software — with the tri-state carried across rather than flattened: a check that could not run crosses as `NOT_ANALYZED` holding the requirement it would have been judged against, because a format conversion that quietly drops it turns a file with an honest gap into one that reads as fully examined. The same page opens the other direction: a **Digital Calibration Certificate** (the open PTB schema) read as a measured input, so a provenance chain that used to end at a handbook table can end at a calibrated instrument — with the laboratory's stated uncertainty handed to the margin sampler as a typed distribution, a unit outside the declared D-SI table refused rather than guessed at, and a signature reported as present and *unverified* rather than as checked, because there is no third state an offline tool can honestly claim. And because the agents driving all of this need to be taught what correct use looks like, Anvilate ships a [first-party agent skill](docs/agent-skill.md) in the open SKILL.md convention — retrieval not recall, read the scorecard, not-evaluated is not a pass, inverse-first repair, confirm before use, screening not certified — bound to the library by CI rather than by good intentions: every symbol it names is imported, every worked example is executed and its claimed output compared byte for byte, every rule is anchored to an example whose own assertions carry the claim, and guidance that would bypass a gate or overstate a verdict fails the build. Where the export layer is *pointed* — STEP AP242 per the CAx-IF Recommended Practices, 3MF as ISO/IEC 25422, refereed in CI by the free NIST analyzer against the free CAx-IF test models — is written down in [export targets](docs/export-targets.md) — a roadmap page kept as a verification record, with each claim marked confirmed or not and how it was checked, including the two that did not survive checking. None of it is shipped yet: no STEP or 3MF writer exists, which is what made re-aiming free. The two load-bearing data contracts — the Spec IR going in and the scorecard coming out — are [published as JSON Schema 2020-12](docs/published-contracts.md), generated from the models and held against them by a gate with two halves: the artifact must match the model, and a changed artifact must carry a moved version, because a client pinned to `1.1.0` fetching different content under the same identifier is the breaking change nobody can see. The tri-state is in the enumeration, so a consumer cannot model the result as a boolean without noticing what it is dropping. And before the intent compiler exists, its **measurement** does: constraining a small model's output to a schema is measured to take validity from ~62% to 100% while taking accuracy *down* from ~20% to 11%, so [a valid spec can still be the wrong spec](docs/valid-is-not-correct.md) — schema validity, field correctness and the wrong-but-valid rate are three separate numbers with deliberately no fourth that averages them, because a single figure over a constrained decoder rises while the thing a user cares about falls.

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
