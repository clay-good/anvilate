# Anvilate examples

Runnable, self-contained scripts that each exercise one deterministic Anvilate
vertical end to end — no LLM, no network. Every script here is executed by
`tests/test_examples.py` in CI, so they stay green as the library moves.

Run any of them directly:

```bash
python examples/cantilever_bracket_check.py
```

Each script exposes one named function (the one the test calls) so you can import
and reuse it. The DXF example additionally needs the `export` extra
(`pip install 'anvilate[export]'`).

## Structural pack — code-checked members (AISC 360 / ASME BTH-1)

| Example | What it shows |
|---|---|
| `cantilever_bracket_check.py` | A cantilever bracket screened for bending yield *and* deflection — passes yield but fails the deflection limit, so the scorecard is FAIL (no silent green). |
| `machine_on_floor_beam.py` | A 15 kN machine at the quarter point of a floor beam: the conservative assume-mid-span screen fails at SF 1.19, but declaring the actual `load_position` passes at 1.58 — margin a worst-case hand check throws away. |
| `jib_boom_trolley.py` | A 10 kN hoist on a cantilever jib boom: assumed at the tip the boom fails at SF 1.33, but declaring the trolley's actual 750 mm end stop as the `load_position` passes at 1.78. |
| `press_on_clamped_beam.py` | A 22 kN press at the third point of a fixed-fixed crossbeam — the inverse lesson: the wall moment peaks *off* mid-span (4·P·L/27 vs P·L/8), so the mid-span shortcut passes at SF 1.62 while the real position fails at 1.36. |
| `walkway_beam_end_fixity.py` | A 6 kN/m walkway beam with one end in a wall embed: bending is identical either way (w·L²/8), but the pin-pin idealization fails L/360 at 11.6 mm while the propped cantilever it actually is deflects 4.8 mm and passes. |
| `i_beam_same_steel.py` | The same ~3,080 mm² of A36 as a square bar and as an I-shape: the bar fails at SF 0.95, the I-beam passes at 6.99 — a 7.4× section modulus from shape alone, same weight per meter. |
| `monorail_trolley_sweep.py` | A 10 kN trolley swept along a propped runway beam: the governing moment peaks at L/√3 from the prop, so mid-span passes at SF 2.03 while the true worst parking spot fails at 1.98. |
| `flat_bar_strut_weak_axis.py` | A 20 × 60 mm flat-bar strut declared about its strong axis: the column screen buckles it about `least_radius_of_gyration` automatically (r 5.8 vs 17.3 mm — a slender Euler column, honest FAIL at 1.6); only a hand-built raw section with no transverse second moment can still produce the false Johnson 4.6. |
| `mezzanine_structure.py` | A whole structure — a floor beam on two posts — screened into one scorecard via `screen_structure`. |
| `beam_column_check.py` | A round HSS pipe column under combined axial load and bending, screened by the AISC §H1.1 interaction equation (the case pure-beam and pure-column checks can't express). |
| `brace_tie_check.py` | A bolted single-angle tension brace (AISC §D2): gross yielding passes comfortably, but shear lag makes net-section rupture govern. |
| `column_base_plate.py` | A column base plate sized for AISC concrete bearing (§J8) *and* cantilever plate bending (Design Guide 1) — bearing passes but the plate-bending check governs and fails, flagging a too-thin plate. |
| `hanger_bracket_bolt.py` | A bracket bolt under combined tension and shear: every one-axis check clears SF 2.0, but the AISC §J3.7 combined interaction fails — the case one-axis-at-a-time checks miss. |
| `clip_angle_edge_tearout.py` | A clip-angle bolt relocated toward the plate edge: bolt shear and bearing never see the move, but the AISC §J3.10 bolt-hole tear-out check drops from SF 6.4 to 1.28 and fails. |
| `coped_beam_web_shear.py` | A coped beam web at a bolted end connection screened for both AISC §J4.2 shear limit states: bolt-hole deductions make shear rupture — not gross yielding — govern. |
| `retaining_wall_post.py` | A retaining-wall soldier post under triangular soil load: the resultant-at-centroid shortcut nails the wall moment exactly but under-predicts tip deflection by 26% (w₀·L⁴/40.5EI vs /30EI) — a false serviceability green the declared triangle catches. |
| `pallet_bay_floor_beam.py` | Pallets over half a floor beam's span, screened three ways: smearing the intensity over the span fails at SF 1.30, spreading the total reports margin that isn't there (2.61), and the declared `loaded_length` patch gets the true 2.32. |
| `tank_baffle_end_fixity.py` | A tank baffle under hydrostatic triangular load at three end fixities: welding only the floor seam cuts deflection 4.99 → 1.82 mm but *raises* the peak stress (w₀·L²/15 vs the pinned w₀·L²/(9·√3)) — end fixity hands the strength problem to the weld unless both ends are fixed. |
| `machine_skid_end_fixity.py` | A machine skid parked over half a beam's span at three end fixities: welding in the end it parks against cuts deflection 1.40 → 0.45 mm at zero stress cost (the wall moment lands exactly on the pinned sagging peak, 9·w·L²/128) — the counterpoint to the tank baffle, where the same weld raised the stress. |
| `skid_position_on_platform.py` | The same skid on a cantilevered platform, parked at the wall vs rolled out to mid-platform (`patch_centered`): the moment arm doubles the wall moment, halving the stress SF to 1.56 and tripling the tip deflection past L/180 — placement alone flips the screen. |
| `stiffener_weld_end.py` | A propped barrier stiffener under hydrostatic triangle, welded at the sill vs at the top waler (`triangle_mirrored`): peak-at-wall is stiff but overstressed, mirroring the fixity trims the wall moment 12.5% yet grows deflection 28% — the two weld ends fail opposite criteria. |
| `canopy_snow_drift.py` | The same canopy snow surcharge drifted against the building face vs the edge fascia (`triangle_mirrored` on a cantilever): mirroring the triangle moves the resultant to 2·L/3, doubling the wall moment (SF 2.29 → 1.14) and nearly tripling the tip deflection past L/180 — the drift orientation alone flips the screen. |
| `davit_sheave_overhang.py` | A davit boom whose hoist sheave sticks out 300 mm past the tip: idealized at the tip both screens pass, but the bracket's couple F·e (`cantilever_end_moment`, superposed exactly with the tip load) grows the wall moment 25% and the tip deflection 37% — both flip to FAIL on geometry the tip-point screen silently drops. |
| `lifting_padeye.py` | A welded lifting padeye assembly (lug + fillet weld) screened together; flags an under-sized pin against the rigging safety factor. |
| `lug_drawing.py` | The full white-space vertical: code-check a lifting lug (ASME BTH-1), then export its plan outline to a fabrication DXF. |

## Mechanical — T1 analytical screens

| Example | What it shows |
|---|---|
| `bolted_joint_check.py` | A bolted lap joint: preload from torque, plate bearing, and bolt shear, all from the materials DB. |
| `flood_barrier_stiffener.py` | A flood-barrier stiffener under hydrostatic pressure: smearing the peak as a uniform load fails bending and deflection, while the actual triangular load (w₀·L²/(9·√3)) passes both — margin the lazy screen throws away. |
| `genset_on_two_rails.py` | A 10 kN genset on a floor beam, lumped at mid-span vs declared on its two skid rails (four-point bending): the rails carry a constant M = F·a, 2/3 of the lumped moment, flipping both the strength and L/240 screens from FAIL to PASS. |
| `motor_mount_resonance.py` | A cantilevered motor mount whose fundamental frequency falls below the running speed — a resonance FAIL. |
| `shrink_fit_check.py` | An ISO 286 interference fit (Ø40 H7/s6) turned into a thick-wall contact pressure and hub bore hoop stress, screened against yield. Ties the tolerance, analysis, and materials layers together. |
| `wheel_rail_contact.py` | A crane wheel on a rail screened for Hertzian line-contact surface pressure — annealed steel fails, the lesson that rolling-contact parts must be surface-hardened. |

## Tolerance & manufacturability

| Example | What it shows |
|---|---|
| `tolerance_stackup.py` | A 1D assembly stack-up analyzed worst-case, RSS, and Monte Carlo: worst-case rejects the design, yet the predicted assembly yield is 99%+. |
| `dfm_process_check.py` | A tolerance call-out screened against a process's capability floor — flags an unachievable band and suggests processes that can hold it. |

## Provenance

| Example | What it shows |
|---|---|
| `evidence_bundle.py` | Rolls every standards record a spec references (material, standard components, ISO 2768 / ISO 286 / ISO 1101) into an auditable, cited evidence trail. |

## Design Spec IR

| Example | What it shows |
|---|---|
| `load_and_validate_spec.py` | Loads the golden Design Spec from YAML, validates its references and dimension graph against the bundled databases, and proves it round-trips unchanged — the spec is the source of truth. |

`nema23_bracket.spec.yaml` is that golden-path Design Spec IR (schema 1.0.0),
loadable with `anvilate.spec.load_spec_yaml` — the typed, diffable representation a
prompt compiles into.
