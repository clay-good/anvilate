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
| `dock_edge_overhang.py` | A pallet on a dock edge (`Support.OVERHANG`): bending clears at SF 2.86, but at a short overhang the governing movement is the back span bowing UPWARD past the deck flatness limit — 4.20 mm of mid-span uplift beats the 3.77 mm tip drop, in the direction nobody instinctively checks. |
| `davit_sheave_overhang.py` | A davit boom whose hoist sheave sticks out 300 mm past the tip: idealized at the tip both screens pass, but the bracket's couple F·e (`cantilever_end_moment`, superposed exactly with the tip load) grows the wall moment 25% and the tip deflection 37% — both flip to FAIL on geometry the tip-point screen silently drops. |
| `lifting_padeye.py` | A welded lifting padeye assembly (lug + fillet weld) screened together; flags an under-sized pin against the rigging safety factor. |
| `lug_drawing.py` | The full white-space vertical: code-check a lifting lug (ASME BTH-1), then export its plan outline to a fabrication DXF. |

## Mechanical — T1 analytical screens

| Example | What it shows |
|---|---|
| `access_cover_sizing.py` | A 600 × 400 mm access cover under 50 kPa, solved by the exact Navier plate series: 6 mm passes strength (SF 2.31) but bows past b/250 — stress falls with t² and deflection with t³, so plate sizing lands on stiffness and the strength-sized cover is a gauge too thin. |
| `bolted_joint_check.py` | A bolted lap joint: preload from torque, plate bearing, and bolt shear, all from the materials DB. |
| `machine_foot_on_panel.py` | A 5 kN machine foot on a 500 × 500 panel screened both ways: smeared it is comfortably green (SF 6.26), on its true 100 mm pad the two-way concentration is 4.4× — SF 1.41 and 3.4 mm, both FAIL. Plates forgive smearing even less than beams. |
| `manway_lid_fixity.py` | A Ø500 manway blank screened under both honest edge models: welded (clamped) it passes everything, but on a gasket (simply supported) the same lid deflects 4.08× more and busts the sealing flatness limit while strength still passes — the edge-fixity assumption is the design. |
| `test_blind_sizing.py` | The industrial pack's declare-and-screen pattern: a Ø400 gasketed hydro-test blind (`CoverPlate`, honestly simply supported) sized 12 → 16 mm — 12 mm fails strength and gasket flatness, 16 mm passes both, every entry citing the plate theory it ran. |
| `plenum_access_panel.py` | A 600 × 400 × 5 plenum panel that is statically bulletproof (SF 16, a third of the flatness limit) yet rings at 108.3 Hz — inside the blower's blade-pass band. One `CoverPlate` `min_frequency` floor catches it (the mass comes from the material density), and welding the rim lifts the mode 1.9× to 205.5 Hz for zero added steel. |
| `sight_port_blind.py` | The 16 mm hydro blind that passed grows a Ø80 sight port: the port sheds its share of the pressure, but the free hole edge concentrates hoop bending 1.77× — SF 2.15 → 1.22, FAIL — recovered at 20 mm. A hole is not a relief: shrinking it toward zero still leaves 2× the solid stress at its edge. |
| `flood_barrier_stiffener.py` | A flood-barrier stiffener under hydrostatic pressure: smearing the peak as a uniform load fails bending and deflection, while the actual triangular load (w₀·L²/(9·√3)) passes both — margin the lazy screen throws away. |
| `genset_on_two_rails.py` | A 10 kN genset on a floor beam, lumped at mid-span vs declared on its two skid rails (four-point bending): the rails carry a constant M = F·a, 2/3 of the lumped moment, flipping both the strength and L/240 screens from FAIL to PASS. |
| `fan_deck_resonance.py` | A fan-deck stringer screened with the exact distributed-mass first mode: simply supported it resonates below the 1450 rpm fan (17.0 Hz), welding both ends swaps the eigenvalue π² → 22.37 and clears the floor at 38.6 Hz — a 2.27× jump for zero added steel. |
| `pump_mezzanine_beam.py` | One `BeamMember` declaration, three check dimensions: a pump beam that is statically bulletproof (bending SF 9.27, deflection well inside L/360) yet FAILs on resonance alone (23.9 Hz vs the 1450 rpm × 1.2 floor) — the dimension a static hand calc never sees. |
| `flywheel_torsional_mode.py` | A flywheel on a stub shaft whose torsional mode sits dead on the 3000 rpm torque ripple (50.5 Hz): upsizing the shaft Ø20 → Ø25 multiplies J by 2.44 and moves the twist mode 56% to 78.8 Hz — the drivetrain dimension a lateral screen never sees. |
| `motor_mount_resonance.py` | A cantilevered motor mount whose fundamental frequency falls below the running speed — a resonance FAIL. |
| `cam_return_spring.py` | A cam return spring whose wire stress (Wahl, SF 2.0) never changes with machine speed — but its own 99 g of coil surges at ½√(k/m) = 139.7 Hz, 28 cam orders up at 300 rpm and only 7 at 1200: the speed-up fails on surge alone, and thicker wire isn't the fix. |
| `shrink_fit_check.py` | An ISO 286 interference fit (Ø40 H7/s6) turned into a thick-wall contact pressure and hub bore hoop stress, screened against yield. Ties the tolerance, analysis, and materials layers together. |
| `off_center_post_load.py` | A slender strut with its 37 kN pad 5 mm off-centroid: superposition (P/A + P·e·c/I) passes SF 2.03, but at 60% of Euler the P-δ feedback amplifies the bending 2.88× — the exact secant formula reads 239.6 MPa, SF 1.04. Slender + eccentric is a feedback problem, not an addition problem. |
| `hydraulic_cylinder_wall.py` | A Ø50 × 10 mm hydraulic barrel at 600 bar: the thin-wall membrane formula (misused at r/t = 2.5) reads 150 MPa and passes SF 2.78, while the exact Lamé bore — 185 MPa hoop on −60 MPa radial pinch — works at 245 MPa Tresca and FAILs. Both thin-wall blind spots err non-conservative. |
| `hub_heating_for_assembly.py` | The same Ø40 H7/s6 fit, asked how it gets assembled: ΔT = (δ + slip)/(α·d) says a ~199 °C setpoint. A 150 °C bench oven opens the bore 61 µm — 2 µm past the raw interference, which is exactly how hubs seize half-way on; the 250 °C furnace clears it with the slip allowance intact. |
| `wheel_rail_contact.py` | A crane wheel on a rail screened for Hertzian line-contact surface pressure — annealed steel fails, the lesson that rolling-contact parts must be surface-hardened. |
| `beam_section_sizing.py` | A platform beam whose required section modulus Z_min = n·M/σ ≈ 72,700 mm³ is named before a section is picked: an 80×120×5 box (62,600 mm³) misses at 128 MPa while a 100×140×6 (107,000 mm³) passes at 75 MPa — the section modulus, not the overall size, is what the moment asks for. |
| `bolt_tension_thread_area.py` | An M12 bolt that passes on the nominal shank area (336 MPa, SF 1.7) but fails on the ISO 898 tensile stress area it actually breaks through (451 MPa, 1.29) — the shank-area screen is not conservative, it is wrong. |
| `tapped_hole_engagement.py` | An M12 bolt at full 48.9 kN proof load: one diameter of thread is enough into a steel nut but strips a 6061-T6 tapped boss at 1×d (SF 1.29), recovered at 2×d — steel into aluminium wants two diameters. |
| `bracket_weld_sizing.py` | A 100 kN bracket weld where the shop's habitual 5 mm fillet runs 236 MPa (SF 1.23 against a wanted 2.0); inverting the throat-shear check calls for ~8 mm, so a 10 mm fillet carries it (2.46) — a fillet is sized, not defaulted. |
| `coupling_key_sizing.py` | A coupling key that clears shear at 10 mm but brinells the hub: the same force bears on only h/2×L, so bearing governs at 296 MPa (past yield) and the key actually needs ~18 mm — sizing a key on shear is the wrong failure mode. |
| `drive_shaft_sizing.py` | A compressor drive shaft sized on the average torque (31 mm, SF 1.08) that fails once a 2.0 service factor covers the reciprocating peaks — 40 mm carries the peak at 2.32; a shaft is sized for the peak torque, not the average. |
| `drivetrain_shaft_twist.py` | An indexing shaft strong enough to turn (31 MPa, SF 2.9) but too soft to place: it winds up 1.69° over 1.5 m against a 1.23° stiffness rule (0.73), so it indexes to the wrong place — torsional wind-up wants a stiffer shaft, not a stronger one. |
| `geared_shaft_sizing.py` | A line shaft that passes on torsion alone (30 mm, SF 2.14) but fails once the gear's bending is added: the von Mises combination σ' = √(σ²+3τ²) reads 199 MPa (1.76), and the shaft needs ~31.3 mm — bending and torsion yield the surface together. |
| `frame_member_torsion.py` | A subframe cross-member detailed as a closed box (23 MPa, SF 4.3) whose seam is left unwelded to save a pass: an open thin section has no Bredt shear flow, so τ = 3T/(b·t²) multiplies the wall shear ~20× to 480 MPa (past yield) — the seam weld carries the torsion. |
| `floor_beam_serviceability.py` | An office floor beam strong in bending (97 MPa, SF 1.7) that still fails L/360: it deflects ~18 mm past the 16.7 mm limit — floors are governed by stiffness, so the fix is a deeper section, not a stronger one. |
| `fixture_clamp_washers.py` | A machining clamp losing 0.4 mm of grip per shift against a 10 % force-constancy spec: a shallow disc washer dumps 52 % of the clamp force (SF 0.19) while a disc coned to the Almen-Laszlo h/t = √2 plateau loses 2.3 % (4.34) — Bellevilles hold force while position drifts. |
| `guide_spring_buckling.py` | A return spring restretched to a 280 mm free length for more stroke: the wire stress is fine (338 MPa, SF 2.0) but the coil is now a slender column that buckles past ~45 mm, so the 60 mm stroke folds it sideways — a longer stroke wants a guided or squatter spring. |

## Power transmission, mechanisms & machine dynamics

| Example | What it shows |
|---|---|
| `winch_planetary_reducer.py` | A single-stage planetary winch reducer where the ratio is a *tooth-count* choice: 4.5:1 needs a 37.5-tooth planet (uncuttable), 4.7:1 cuts but three planets won't phase in (140 % 3 ≠ 0), and only the buildable 4.6:1 clears 200 N·m — whole teeth and assembly vote before torque. |
| `multistage_reducer_efficiency.py` | A 3-stage 36:1 reducer that clears a 650 N·m demand on ideal torque (688 N·m, SF 1.06) but misses it once the compounded 0.97³ = 91.3 % train efficiency drops the real output to 628 N·m (0.97) — size on delivered torque, not ideal. |
| `helical_gear_thrust_bearing.py` | A 5 kN helical mesh whose axial thrust W_t·tan(ψ) lands on the thrust bearing: a shallow 15° helix passes (SF 2.24) but the smoother 30° (1.04) and 45° (0.60) helices overrun a 3 kN bearing — the helix angle is not a free smoothness dial. |
| `bevel_gear_thrust.py` | A 2:1 bevel pair where the thrust resolves about each member's pitch cone: the pinion throws 651 N but the larger gear throws 1302 N — twice as much (the gear ratio) — overrunning the same 1200 N bearing (0.92); size each shaft's thrust bearing to its own member. |
| `gearbox_output_shaft.py` | One output shaft screened across three independent failure modes — combined bending+torsion (SF 2.98), key shear (2.92), and bearing L10 life (1.13) — all pass, but the bearing life is the governing check a shaft-stress-only analysis would miss. |
| `bolted_cover_flange.py` | A 300 mm bore cover at 16 bar whose pressure end-force p·πD²/4 is a deceptively large 113 kN: four M12 bolts overstress the threads (SF 1.73 against a wanted 2.0), six clear it (2.59) — count the bolts for the end-force, then preload for the seal. |
| `flywheel_speed_limits.py` | A press flywheel screened on its three speed-dependent limits: it stores enough energy (SF 1.22) and its rim is nowhere near bursting (4.84), yet the 49 kg disc on a slender Ø40 shaft whirls at 54 Hz next to the 50 Hz running speed (0.86) — the governing limit is the one a stress or energy check never sees; the fix is a stiffer shaft, not a different flywheel. |
| `fatigue_link_stress_riser.py` | A tension link comfortably safe on its peak static load (SF 2.40 on yield) that fails by fatigue under the same 5→35 kN cycling: the pin-hole stress raiser (K_f 2.8) drives the alternating stress to 210 MPa against a 200 MPa Marin endurance limit, so the modified-Goodman check reads 0.84 — static strength and fatigue life are different questions, and the notch is where they part. |
| `worm_hoist_selflock.py` | A worm-drive hoist that must self-lock to hold its load: only the single-start worm locks (SF 1.30) at 43 % efficiency, while the smoother double/triple-start worms back-drive (0.65, 0.43) — a hoist must self-lock before it is efficient. |
| `cart_drum_brake.py` | A rail-cart drum brake that holds 82 N·m downhill (self-energizing, SF 1.17) but creeps at 61 N·m the other way (0.87): a drum brake has a rotation direction, and it must be checked in the one that de-energizes the shoe. |
| `winch_band_brake.py` | A winch band brake with ample tension margin (830 N·m held, SF 1.66) whose 40 mm strap crushes the lining at 0.80 MPa vs a 0.60 MPa allowable (0.75); a 60 mm band passes — friction sizes the tension, lining pressure sizes the width. |
| `conveyor_bearing_life.py` | A conveyor bearing that fits the shaft but wears out: the (C/P)³ life law means the 6208 lasts 7,500 h against a 30,000 h target, and only the heavy 6310 clears it — life is brutally sensitive to the load-to-capacity margin. |
| `lineshaft_critical_speed.py` | Two pulleys that each pass individually (42, 39 Hz above the 31 Hz floor) but resonate together: Dunkerley's 1/f² = 1/f_A² + 1/f_B² drops the real first critical to 29 Hz — the shaft has one fundamental, not two, and it sits below either mass alone. |
| `high_speed_belt_drive.py` | A belt asked for 5.5 kW: past the max-power speed v* more rpm gives *less* power, so no speed on a 500 N belt works (ceiling SF 0.92) — the fix is a higher-tension belt, not more rpm. |
| `conveyor_chain_drive.py` | A chain drive against a 2 % speed-ripple spec: the cheap 11-tooth driver's chordal action ripples 4 % (SF 0.49) and even 13 teeth fail (2.9 %); only 17 teeth fall to 1.7 % — small sprockets are cheap but rough. |
| `indexing_table_stations.py` | A Geneva indexing table trading stations against dwell: 6 stations dwell 2.0 s (enough for the 1.9 s operation, SF 1.05) but 8 (0.99) and 12 (0.92) stations index too much and dwell too little — station count and dwell pull against each other on a fixed cycle. |
| `highspeed_cam_follower.py` | A cam follower held by a 150 N seating force: comfortable at 600 rpm (SF 3.34) but acceleration scales with speed², so 1200 rpm floats it (0.83), and the smoother cycloidal profile fails harder (0.65) — a cam's acceleration is a speed-squared problem no profile buys out of. |
| `engine_shaking_force.py` | A single-cylinder shaking force m·r·ω²·(1 + r/L) that turns on the connecting-rod ratio: the short rod (L/r 3.5) overloads the 2400 N mounts (SF 0.95) while L/r 5 (1.01) and 6.67 (1.06) clear them — the rod ratio you can't see sets the shake you can feel. |
| `spring_buckling_freelength.py` | Three springs squeezed 50 mm: the squat 120 mm coil is absolutely stable, the 150 mm one buckles only past 63 mm (SF 1.26), and the tall 180 mm coil folds sideways in service (0.92) though its wire is fine — a spring has a column slenderness limit. |
| `fourbar_linkage_design.py` | Two crank-rockers that both rotate, but the long-coupler one's transmission angle collapses to 21° and binds (SF 0.46) while rebalanced lengths hold 48° (1.07) — rotatability is necessary but not sufficient; the transmission angle decides. |
| `machine_vibration_isolation.py` | A 25 Hz machine on isolator mounts: a stiff 20 Hz mount *amplifies* to 175 % transmission (SF 0.11), a 12 Hz mount cuts it to 31 % (0.66), and only the soft 6 Hz mount passes 7 % (3.02) — isolation is won by going soft so the frequency ratio clears √2. |
| `cable_resonance_tuning.py` | A guyed cable under 8 Hz forcing: at 40 kN its fundamental lands on the forcing (8.2 Hz, SF 0.68) and resonates, while tensioning to 90 kN (12.2 Hz, 1.02) and 150 kN (15.8 Hz, 1.32) lifts it clear — tune the fundamental above the forcing, not into it. |
| `spanning_cable_tension.py` | An 80 m cable with no good tension: slack (6 kN) sags too far, taut (12 kN) overloads, and even the balanced 8 kN that just meets clearance is over the tension allowable (0.98) — the sag-vs-tension window is empty; change the cable, not the knob. |
| `shrink_fit_at_speed.py` | A shrink-fitted hub that grips cold (SF 1.67) and at 6000 rpm (1.15) but loses its whole 0.05 mm interference to centrifugal growth at 12000 rpm (−0.40) — check shrink fits at operating speed; the interference rides ω² toward zero. |
| `crane_hook_shank.py` | A crane-hook shank where the straight-beam formula passes (SF 2.20) but the Winkler curved-beam bore stress is 31 % higher and fails (1.68) — deepening the shank recovers it; curvature crowds stress onto the bore, where hooks crack. |
| `imperfect_column_capacity.py` | An S355 column at λ 90 that passes the Euler/perfect-column screen (244 MPa, SF 1.22) but fails once a realistic 0.3 imperfection knocks the Perry-Robertson capacity to 174 MPa (0.87) — design mid-slenderness columns to the real curve, not the ideal. |
| `vacuum_vessel_buckling.py` | A steel tank whose 3 mm wall carries internal pressure with ease but implodes under 1 atm of *vacuum* at 0.012 MPa (SF 0.04); it takes a 12 mm wall (2.53) because external pressure is a buckling problem sized by t³, not a strength one. |
| `jacketed_reactor_vacuum.py` | A 4-bar reactor shell that clears the internal hoop check at every wall (3 mm, SF 2.07) but is buckled by the vacuum forming when its heating jacket cools (3 mm at 0.04, 6 mm at 0.32); only a 12 mm wall — 4× the pressure case — survives it (2.53), so the vessel is sized by the vacuum it isn't named for. |
| `fracture_toughness_screen.py` | A damage-tolerance choice where the high-strength steel's 4.97 mm critical crack barely exceeds the 5 mm inspection floor (SF 0.50) while the tougher steel tolerates 19.9 mm (1.99) — toughness, not strength, decides whether cracks are caught first. |
| `crack_growth_inspection_interval.py` | A welded steel part whose 2 mm flaw takes ~190,000 cycles to grow to failure at 150 MPa (SF 1.91 on a doubled 50k-cycle inspection interval) but only ~60,000 at 220 MPa (0.60) — the Paris cube law means a 50% larger stress range more than halves the propagation life, so the safe schedule turns unsafe. |
| `crane_rail_on_foundation.py` | A crane wheel on a rail where a stiff grout bed (k 100) keeps the peak bending stress to 254 MPa (SF 1.89) but a soft elastomeric pad (k 20) lets the load spread, raising it to 380 MPa (1.26, fails 1.5) — on a beam on an elastic foundation the *softer* support is the more demanding one. |
| `section_shape_factor.py` | The reserve a beam holds between first yield and a plastic hinge is its shape factor: a solid round bar keeps 1.70, a rectangle exactly 1.50, but an I-section only 1.17 (fails a 1.5 ductility reserve) — an efficient elastic shape piles its area at the extreme fibre, leaving little to recruit past yield. |
| `plastic_collapse_reserve.py` | A fixed-fixed steel beam under 100 kN/m that fails a 1.5 safety factor on its elastic first-yield load (SF 1.25) but passes with room to spare on its true plastic collapse load (2.50) — the 2.0x reserve is the shape factor (1.5) times the moment redistribution an indeterminate beam allows (16/12), which elastic design leaves on the table. |
| `support_beam_resonance.py` | A 50 kg machine at 22 Hz on a support beam whose fundamental clears the running speed if the beam is treated as massless (24.7 Hz, SF 1.12) but drops onto it once the beam's own 30 kg is counted (21.7 Hz, 0.99) — a simply-supported beam adds 17/35 of its mass to the mode, so ignoring it is optimistic exactly where it must not be. |
| `fatigue_criteria_compared.py` | One 80±200 MPa cycle screened three ways: Soderberg-to-yield (1.11) and Goodman-to-ultimate (1.36) both fail a 1.5 factor while the data-hugging Gerber parabola (1.70) passes — the verdict turns on the mean-stress line you draw, so a fatigue screen must name the criterion it used. |
| `flywheel_bore_stress.py` | A steel flywheel at 7000 rpm that passes as a solid disc (157 MPa centre stress, SF 2.24) but fails once bored for its shaft (314 MPa bore stress, 1.12) — rotating theory says even a small central hole moves the peak to the bore and doubles it, so a disc sized solid cannot simply be drilled. |
| `bearing_reliability_life.py` | A ball bearing whose 18,500-hour catalogue L10 clears a 10,000-hour target at 90% reliability (SF 1.85) and 95% (1.14) but collapses to 3,900 hours — failing — at 99% (0.39); the ISO 281 a1 factor shows L10 answers "when do 10% fail?", not the reliability a critical design needs. |
| `glass_thermal_shock.py` | The same 150 K quench that shatters a soda-lime tumbler (surface tension 121 MPa vs 50 MPa strength, SF 0.41) is survived by low-expansion borosilicate (40 MPa, 1.26) — thermal-shock resistance is low CTE, not strength. |

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
