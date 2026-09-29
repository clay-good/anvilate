# Tasks: Interaction quality

## 1. Progress and cancellation

- [x] 1.1 Progress channel: current activity, completed and total units, indeterminate flag
      — MCP task responses carry all four under `_meta["dev.anvilate/progress"]`; queued
      and running work is explicitly indeterminate with no invented total, terminal success
      is 1/1, and cancellation or failure ends at 0/1 without claiming completion
- [x] 1.2 Threshold rule — any operation that can exceed it reports progress — a declared
      two-second threshold; check, export and build report through one helper, and a test
      fails any sweep over specs that does not
- [x] 1.3 Estimates derived from completed same-kind work only, and labeled estimates —
      the check sweep's time left, from specs already screened, none before the first
- [x] 1.4 Cancellation at any point; partial artifacts removed or marked partial — the CLI
      reports a cancelled run as its own outcome (exit 130) with what it completed, and
      exports write atomically, so an interrupt leaves no partial artifact
- [x] 1.5 Cancellation terminates subprocess solvers and sandboxes, verified — the MCP task
      worker's whole process group gets SIGTERM, then SIGKILL after a 2 s grace; verified
      with a stand-in worker whose solver child exits politely and one that ignores SIGTERM
      (tests/test_mcp_tasks.py). No sandbox exists yet to terminate

## 2. Message quality

- [ ] 2.1 Remedy field on every refusal: the action, its concrete subject, and where a
      value may come from — progress: every gap the library builds through
      `ScorecardEntry.from_safety_factor` states its reason and the field to declare
      (`unavailable=`, 34 call sites, held by a gate in tests/conftest.py). Raised
      refusals carry their remedy in the message text (2.2). MCP `tools/call` refusals also
      carry `error.data.remedies`; invalid arguments carry `error.data.issues`, and nested
      Design Spec failures preserve their exact per-field remedies through synchronous and
      task-dispatched calls. Other Python ValueErrors have no structured field yet. The
      structured field is `ScorecardEntry.needs` (add-declaration-completeness): 61 of the
      library's 111 not-evaluated sites carry it (nine in screening, and every screen
      elsewhere that stops for a value), and so do all 34 `from_safety_factor` calls that
      state an `unavailable=` reason. tests/test_needs.py sweeps every module; the other 50
      are excused by cause in docs/api/refusals-without-needs.txt, and the backlog is empty.
      Left open because the task says "every refusal": a *raised* refusal (a ValueError)
      still carries its remedy in its message only. The exception, since 2026-09-25, is
      the refusal met most often. A spec that fails validation carries a structured
      remedy per error: `SpecValidationError.errors[].remedy` and `.remedies`. A missing
      required field gets a line of YAML that validates, and a test builds a Design Spec
      from those lines. An unknown field gets the nearest real field name, and a provenanced
      value written bare (`min_safety_factor: 1.5`) gets the `{value, origin}` line, which a
      test pastes back in and validates. So do a bare one-field mapping (`material: ASTM-A36`),
      a scalar where a list belongs, and a near-miss of an allowed value (`si`, `CNC milling`,
      `T1`), in documents and element parameters alike. At the shell, every ordinary mistake in
      a held list (a missing or mistyped path, an empty directory, a UTF-16 file, a YAML
      syntax error, a missing or unknown argument, a mistyped command, an export past a
      failing card, a missing optional dependency) gets its own `remedy` rather than the
      generic sentence, derived from the CLI's own diagnostic forms. The CLI's JSON
      refusal carries those remedies in `remedy` instead of its generic sentence.
      Gas-compression refusals now identify the operating case, gas property record, or
      compressor specification needed to repair invalid inputs. Stage counts require positive
      integers, and non-finite scalar inputs carry the same structured remedies.
      **Raised-refusal migration has started:** `anvilate.refusal.Remedy` requires an action,
      concrete subject, and source, while `RefusalError` refuses an empty remedy set.
      `ExportRefused`, the artifact gate exposed directly to Python callers, carries that
      structure without changing its message. MCP handler-level argument refusals now do the
      same; both the synchronous and task transports render their records to the established
      JSON-RPC strings, including exact nested Design Spec corrections. The fetch-on-first-use
      boundary now carries typed remedies too: consent refusals identify the dataset and the
      user as authority, while integrity refusals identify the corrupt download or cache and
      the publisher recipe used to recover it. Intent-compilation candidate and retry-exhaustion
      refusals name the rejected backend/model output and point to the Design Spec schema and
      recorded validation errors, while retaining their `ValueError` ancestry. Unsupported
      Spec IR versions now point to a supporting release or reviewed current schema, and
      unknown material/component references point to the injected live registry and nearest
      identifiers. Design Spec validation now exposes typed remedies for every schema or YAML
      issue while retaining its existing per-field repair strings at CLI and MCP surfaces.
      The cited-data validity gates now structure their repairs too: insufficient
      material basis names the required property record or explicit basis decision, profile
      applicability names a profile covering the stated contexts, and optical range refusal
      names a catalogue range covering the requested temperatures. The complete tolerance
      range family now follows the same contract: ISO 2768/286, fit-clearance, and process
      capability refusals name the concrete input and the governing table, declaration, or
      dataset while retaining `ValueError` compatibility. The complete unit-refusal family
      now does too: quantity parsing, dimensional validators, and D-SI calibration expressions
      name the rejected input and the originating document, field dimension, unit registry,
      or PTB mapping that can repair it, again retaining `ValueError` compatibility. Geometry
      migration now covers the complete family: optional runtime and unsupported patterns,
      STEP/3MF exchange artifacts, measured-interface confirmation and checks, audited-pattern
      construction, viewport/query arguments, and CLI adapters all name the rejected subject
      and its schema, CAD source, cited requirement, audited pattern, or supported grammar.
      The complete lifting-mechanics analytical-input family now does too: sling angles and
      leg counts, tackle rope parts, sheave efficiency, winch drum and spooling inputs, drive
      torque, and wire-rope/sheave properties point to the rigging plan, measured geometry,
      drum or reeving drawing, manufacturer data, or load case. The shared boolean branch
      selector is migrated across all 25 callers as well: a truthy string or numeric stand-in
      names the exact flag and the boundary condition, load case, drawing, service record,
      manufacturer configuration, or governing design basis that decides it. The complete
      belt, roller-chain, worm-drive, and gear families add 130 structured refusal sites for
      forces, speeds, geometry, tooth counts, material/traction properties, rating factors,
      train layouts, and operating duties, sourced to drive or gearset drawings, catalogues,
      load cases, shaft-speed declarations, rating records, or the governing equations. The
      complete compressible-flow family adds another 27 structured sites for flow states, gas
      properties, nozzle geometry, discharge coefficients, and shock conditions, sourced to the
      operating case, cited thermodynamic data, nozzle drawing, or flow-test record. The
      complete shaft-torsion family adds 39 structured sites for duty, speed, section geometry,
      material properties, fatigue factors, and margins, sourced to the operating case,
      dynamometer record, shaft drawing, material certificate, or governing calculation. The
      complete spring-analysis family adds 37 structured sites for coil, leaf, Belleville, and
      spiral-spring load, travel, rate, geometry, material, and end-condition inputs, sourced to
      operating cases, drawings, catalogues, material records, or the spring design basis. The
      complete combustion-analysis family adds 37 structured sites for fuel composition, air and
      flue-gas conditions, heating values, thermochemical properties, and loss assumptions,
      sourced to ultimate analyses, calibrated measurements, certificates, or the combustion
      model. The complete geometric-optics family adds 36 structured sites for imaging distances,
      apertures, wavelengths, refractive indices, dispersion data, and focus criteria, sourced to
      optical drawings, calibrated setups, catalogues, glass or spectral records, or the governing
      optical design basis. The complete universal-joint family adds three structured sites for
      shaft misalignment, sourced to the driveline drawing or measured operating geometry. The
      complete acid-base and chemical-equilibrium families add 10 structured sites for buffer
      concentrations, thermochemical properties, and absolute temperatures, sourced to
      formulation, calibrated concentration, property, or reactor operating records. The
      complete Geneva and Scotch-yoke families add 10 structured sites for station counts, center
      distances, crank radii, and drive speeds, sourced to mechanism drawings, indexing
      requirements, operating cases, or calibrated measurements. The
      complete piezoelectric and strain-gauge families add nine structured sites for material
      coefficients, sensor geometry, measured loads, gauge factors, and bridge-arm choices,
      sourced to datasheets, certificates, drawings, calibrated records, or wiring configurations.
      The complete photon, Compton-scattering, and atomic-spectra families add 21 structured sites
      for wavelengths, energies, optical power, scattering geometry, ion species, and quantum
      levels, sourced to spectral requirements, calibrated sources or setups, and transition
      definitions.
      The complete polarization and Fresnel families add 14 structured sites for optical
      intensities, refractive indices, incidence angles, and total-internal-reflection conditions,
      sourced to attenuation requirements, photometer records, glass certificates, layouts, or
      calibrated setups.
      The complete adhesive-joint and coating families add 11 structured sites for joint geometry,
      loads, bond strength, film thickness, and volume solids, sourced to drawings, load cases,
      product or qualification records, coating specifications, and calibrated gage records.
      The complete process-capability and tolerance-stack families add nine structured sites for
      specification limits, statistical spread, and dimension-chain contributors, sourced to
      drawings, control plans, qualified capability studies, and approved tolerance worksheets.
      The complete accumulator and tank-flow families add 15 structured sites for vessel volume,
      pressures, duty models, tank geometry, liquid levels, and discharge coefficients, sourced to
      catalogues, operating cases, drawings, calibrated measurements, or orifice records.
      The complete riveted-joint and O-ring families add 11 structured sites for joint geometry,
      rivet counts, material allowables, seal sizes, and gland dimensions, sourced to drawings,
      material specifications, approved stress records, manufacturer catalogues, or gland tables.
      The complete mass-energy, gravitation, and circular-motion families add 21 structured sites
      for masses, reaction energies, nuclide identity, body and curve geometry, speeds, traction,
      and gravity, sourced to inventories, calibrated records, models, drawings, or test data.
      The complete work-energy, impact, and friction families add 20 structured sites for mass
      properties, loads, motion, travel, gravity, drop cases, elastic response, interface properties,
      and ramp geometry, sourced to records, drawings, analyses, specifications, or calibrated tests.
      The complete living-hinge, ball-screw, and governor families add 18 structured sites for hinge
      geometry and material strain, screw load, lead and efficiency, and governor speed, height, and
      masses, sourced to drawings, catalogues, requirements, datasheets, load cases, or records.
      The complete ASCE load-combination, AISC compactness, and beam-foundation families add 19
      structured sites for load effects, steel properties and limits, foundation response, beam
      properties, and reactions, sourced to models, records, specifications, tables, or reports.
      The complete casting, shear-spinning, and thermoforming families add 24 structured sites for
      foundry geometry and trials, spinning stock and tooling, and formed-part areas, sheet gauges,
      walls, and draw ratios, sourced to drawings, CAD, process plans, or calibrated records.
      The complete extrusion, forging, and rolling families add 32 structured sites for billet and
      pass geometry, material flow properties, efficiencies, friction, press loads, and mill speeds,
      sourced to drawings, certified tests, qualified trials, process plans, or calibrated records.
      The complete injection-molding, centrifugal-casting, and casting-gating families add 30 sites
      for mold and gating geometry, machine setup, thermal and melt properties, temperatures, spin
      speed, fill time, and discharge data, sourced to drawings, plans, or calibrated trials.
      The complete broaching, grinding, and EDM families add 29 structured sites for tool and cut
      geometry, material allowables, removal rates, wheel and feed speeds, spindle power, electrical
      settings, pulse timing, and erosion data, sourced to drawings, schedules, or calibrated trials.
      The complete drilling, electrochemical-machining, and laser-cutting families add 40 structured
      sites for tool and kerf geometry, workpiece cutting and thermal properties, spindle limits,
      electrical and electrolyte settings, feed schedules, and laser setup, sourced to drawings,
      material records, datasheets, qualified plans, or calibrated trials.
      The complete conventional-machining family adds 18 structured sites for part and tool
      geometry, cutting parameters, finish requirements, workpiece cutting properties, spindle
      settings, and Taylor tool-life data, sourced to drawings, setup schedules, datasheets, or
      qualified trials.
      The complete weld-design, arc-welding heat-input, and resistance-welding families add 40
      structured sites for joint and nugget geometry, loads, electrode and base-metal properties,
      code factors, electrical settings, heat input, chemical composition, and spot-weld schedules,
      sourced to drawings, governing analyses, certificates, qualified procedures, or calibrated
      equipment records.
      The complete sheet-metal and wire-drawing families add 39 structured sites for flat-pattern,
      bend, blank, punch, die, and wire geometry; material formability and strength; press, drawing,
      stripping, lubrication, and springback factors; and drawing stress, sourced to part drawings,
      certificates, qualified trials, bend tables, or approved process schedules.
      The complete electroplating and shot-peening families add 24 structured sites for coating
      thickness and plated area, bath chemistry and coating-metal properties, electrical cycles,
      peening media and impact flow, exposure time, and target coverage, sourced to coating
      specifications, drawings, qualified process records, calibrated equipment, or verified
      coverage tests.
      The complete wear and corrosion families add 33 structured sites for contact load, sliding
      duty, wear allowances, tribology data, coupon exposures, electrochemical tests, material and
      alloy properties, wall inspections and retirement limits, and cathodic-protection inputs,
      sourced to operating records, drawings, test reports, certificates, integrity assessments, or
      approved designs.
      The complete Hall–Petch and creep families add 20 structured sites for grain size, friction
      stress, strengthening coefficients, target yield, service temperature and duration,
      Larson–Miller master-curve data, operating spectra, and rupture-life blocks, sourced to
      metallography, material certificates, creep tests, cited curves, approved service records, or
      integrity assessments.
      The complete elastic-constant, axial-response, and stress-combination families add 32
      structured sites for elastic properties, section geometry, design factors, load-case stresses,
      stress-concentration data, and allowable strengths, sourced to material certificates,
      drawings, verified load cases, or cited property and concentration references.
      The complete reinforced-concrete family adds 41 structured sites for concrete and reinforcing
      properties, section geometry, bar layouts, factored actions, service-load crack-control
      inputs, and ACI factors, sourced to batch reports, certificates, structural drawings,
      reinforcement schedules, verified load cases, or the governing ACI 318 criteria.
      The complete cold-formed-steel family adds 21 structured sites for plate geometry, material
      properties, AISI coefficients, gross-section yield values, elastic buckling results, and DSM
      strength objects, sourced to profile drawings, mill certificates, the governing AISI S100
      criteria, approved yield calculations, or cited finite-strip analyses.
      The complete masonry and prestressed-concrete families add 21 structured sites for masonry
      geometry, prism strength, reinforcement, applied and allowable stresses, prestressed-section
      geometry, tendon force and profile, transfer or service actions, and rupture strength, sourced
      to structural drawings, test reports, reinforcement and stressing records, governing analyses,
      or the cited TMS 402 criteria.
      The complete aluminum family adds 55 structured sites for section geometry, alloy and temper
      properties, buckling constants, ADM factors, member demands, heat-affected properties, and
      completed strength screens, sourced to drawings, mill certificates, cited ADM tables, project
      and welding specifications, load analyses, or the governing Aluminum Design Manual criteria.
      The complete NDS timber-analysis family adds 57 structured sites for member and bearing
      geometry, reference and adjusted design values, factor selections, applied forces and
      stresses, stability inputs, and completed interaction screens, sourced to timber drawings,
      grade or material records, cited NDS Supplement tables, verified load analyses, or the
      governing NDS criteria.
      The timber reference-record and beam-pack layers add 19 more structured sites for provenance,
      property values, factor applicability, beam geometry and loading, record consistency, creep
      and bearing declarations, and factor chains; the pack wrapper preserves the structured repair
      from a refused record instead of flattening it into plain text.
      The remaining ordinary `ValueError` inventory keeps this task open
- [x] 2.2 CI gate: every refusal message's remedy names a resolvable subject — an
      imperative with no noun fails — tests/test_remedies.py over every one of the library's 5,000+ refusal messages; the six "delete it" and three "name it"/"state it" remedies now name their file or field
- [x] 2.3 CI gate carries a population floor and enumerated exclusions with causes — floors on the messages read and the remedies recognised, and no exclusions needed
- [x] 2.4 Near-miss suggestions for unknown names, keyed on the real registry — every bundled
      table answers a one-character typo with the entry it nearly named, held by a sweep over
      the discovered tables rather than a list of them

## 3. Output adaptation

- [x] 3.1 TTY detection, `NO_COLOR`, dumb terminals, width awareness, ASCII fallback
      — the ASCII fallback and dumb terminals are done: a stream that cannot encode the
      output gets ASCII spellings (text) or `\u` escapes (JSON) instead of exit 5, and the
      CLI emits no colour, so `NO_COLOR` has nothing to turn off; and on a terminal each text
      line is wrapped to its width, continuation indented, words never broken, while a pipe,
      a file and JSON get exactly the lines written
- [x] 3.2 Machine-readable output on every command with a stable, versioned schema
      — `cli-output` 1.3.0 covers every completed-result path plus parser, bad-input,
      and unbuilt refusals while preserving their exit codes and stderr diagnostics
- [x] 3.3 Exit codes: success, refusal, failed verdict, internal error — distinct and
      documented; unexpected command defects exit 5 and JSON schema 1.2.0 identifies them
- [x] 3.4 Progress to stderr so stdout stays pipeable — `check` over several specs prints
      `[i/n] screening <path>` to stderr when stderr is a terminal, and nothing into a pipe

## 4. Accessibility

- [x] 4.1 No information conveyed by color alone anywhere — status carries a word or mark
      — the terminal emits no colour at all, and every coloured status in the HTML report is
      a status word, held by a test over the rendered spans
- [x] 4.2 Palette safe for common color-vision deficiency, checked in CI — the report's
      status colours clear WCAG AA on the page and stay ΔE ≥ 20 apart, body text included,
      under the Machado 2009 protan, deutan and tritan simulations; the old red and green
      failed it, and the old amber failed contrast
- [x] 4.3 Report structure readable in document order by a screen reader; tables carry
      headers; figures carry text alternatives — the report's headings run in order from one h1, every table is headed,
      and every typeset formula carries a spoken MathML `alttext` ("σ sub b = M · c / I")

## 5. Discoverability

- [x] 5.1 "What applies to this spec" listing of available screens with what each needs —
      `anvilate.needs.what_applies`, in docs/declaration-needs.md
- [x] 5.2 Runnable examples in every command's help, held against the parser's command set
- [x] 5.3 Shell completion for the supported shells — `anvilate --completion bash|zsh`,
      built from the live parser and exercised in bash by a test

## 6. Budgets

- [ ] 6.1 Interactive responsiveness budget, measured per release on the reference profile — BLOCKED:
      the reference hardware profile and the release process the onboarding and benchmarking
      specs name are both unbuilt, and a timing gate on shared CI runners measures the machine
- [x] 6.2 Cache repeated loads of bundled data; assert the cache is hit, not just present —
      every discovered loader is cached, and a repeat screen is served with hits up and misses
      flat

## 7. Tests

- [x] 7.1 A long operation piped to a file writes clean stdout and progress to stderr —
      stdout is byte-identical watched or piped (tests/test_cli.py)
- [x] 7.2 Ctrl-C during export leaves no partial artifact presented as complete — DXF writes
      go to a hidden sibling renamed on completion, and the STEP writer removes its file on
      a KeyboardInterrupt as well as on an error
- [ ] 7.3 Every refusal in the suite carries a remedy with a resolvable subject
- [x] 7.4 Rendering with color disabled loses no information — the terminal carries no
      ANSI escape (tests/test_cli.py), and every coloured status in the HTML report is a word
      (tests/test_report.py)
