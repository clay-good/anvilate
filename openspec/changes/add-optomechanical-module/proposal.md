# Change: Opto-mechanical screening module — will it survive, and will it still be aligned

## Why

An opto-mechanical engineer asks two questions a mechanical screening tool has never
answered: after this temperature swing, is the image still in focus; after this shock, is
the line of sight still where it was. Both are arithmetic — differential expansion, mount
compliance, an equivalent static acceleration, an allocated angular budget — and both are
done today in a spreadsheet the engineer does not fully trust.

The market confirms the gap rather than filling it. The open-source optical tools are ray
tracers and nothing else: rayoptics (BSD-3), Optiland, optrace. The tools that do couple
structure to optics — SigFit, and Zemax OpticStudio's STAR module — are five-figure seat
licenses that start from a finished finite-element model and an optical prescription, so
they verify a design that already exists rather than screening one that does not yet. The
square between them is empty, and it is the square Anvilate already occupies for brackets.

Anvilate arrives at this unusually well-equipped. The analysis library already carries
`optics`, `optical_interference`, `photodetector`, `photometry`, `fiber_optics`, an
`o_ring` gland set, a deep `thermal` module including `free_thermal_expansion` and
`differential_thermal_stress`, plus `impact`, `contact`, and `fastener`. The module's work
is largely composition, which is what the module contract asks for.

**Scope language is deliberate.** Shock is declared as an environment — magnitude, pulse
shape, duration, axis, cycle count — never as an application. A 1,000 g half-sine is the
same arithmetic whether it comes from a recoil impulse, a drop test, a launch, or a gimbal
slew, and the module serves all of them identically by refusing to know which. Out of
scope permanently: targeting, fire control, ballistics, and any content specific to
directing a weapon.

**Honest boundary.** This is T1 analytical screening. It is not a ray tracer and will not
become one. Where a screen needs a prescription quantity — marginal ray height, surface
figure, a Zernike fit of a deformed surface — that quantity is a typed input supplied by
the user or imported from an external tool whose identity and version are recorded,
exactly as the cold-formed-steel pack treats finite-strip buckling values.

## What Changes

- New capability spec `optomechanical-screening`, shipped as a physical-domain module
  under the module contract: athermal focus screening, line-of-sight stability under
  declared shock and random-vibration environments, element retention preload and glass
  contact stress, elastomeric bond athermalization, clear-aperture and obscuration
  screening against a declared beam envelope, wavefront-error allocation, stress
  birefringence, and sealing/internal-condensation screening composing the existing gland
  set.
- `standards-data` gains an **optical material property record** — index at declared
  wavelengths, Abbe number, dn/dT, CTE over a declared temperature range, elastic
  properties, Knoop hardness, stress-optic coefficient — under the existing provenance and
  no-redistribution doctrine, with refractiveindex.info (CC0) as the license-clean source
  and vendor catalogs fetched or user-supplied rather than bundled.
- `units-and-quantities` makes **angle a dimensioned first-class quantity**: mrad, µrad,
  arcsec, arcmin, degree, and MOA, with the rule that an angular value never renders or
  arrives bare, because a dimensionless radian is the single most common silent unit error
  in this domain.
- `tolerance-management` gains **ISO 10110 optical tolerance indications rendered from the
  one tolerance model**, joining drawings, STEP PMI, and QIF as a fourth consumer rather
  than a parallel store.

- **REWRITTEN** the application exclusion: it constrains what the module *ships*, checked
  in CI against published symbols and declared coverage, rather than inspecting the words
  a user writes. A text-matching refusal is a gate on vocabulary, not capability — it
  turns away legitimate work sharing a word and passes the same request under another.
- **ADDED** declared orientation and static gravity load with a governing orientation;
  as-built alignment as an input the module cannot compute, named when absent so a partial
  budget never reads as a whole one; and a mapping from every screen to the physical test
  that would confirm it, counted as analysis-only coverage where none exists.

- **ADDED, from walking the three workflows end to end:** boresight evaluated as the
  *difference* between two declared paths with common-mode contributors excluded — the
  drift of one path is not an overlay error; internal dissipating sources raising the
  volume the optics sit in, feeding the thermal and condensation screens; a declared
  thermal-condition kind so a uniform-soak screen refuses a gradient and a short dwell is
  called optimistic against the assembly time constant; dynamic clearance against shock
  displacement, since the intrusion check is computed at rest; adjustment mechanisms
  screened for resolution, range, and holding, and always budget contributors; tilted
  windows and combiners displacing the image they pass; harnesses loading the mount they
  cross; retention after cycling reported as verification-only rather than inferred from
  single-excursion screens; and each claimed workflow shipping as an end-to-end example
  that includes a real failure.

- **ADDED, the environmental modes that end qualification campaigns:** an outgassing
  census over every non-metallic in a sealed optical volume, reporting the condensable
  fraction as the optics-governing figure and stating the population it examined; seal
  breathing under thermal cycling, with cumulative moisture ingress named as
  verification-only and a cycling volume with no equalization path, desiccant, or purge
  reported as a finding; windows and closures screened under the declared pressure
  differential in both directions, with the induced bow entering the focus and wavefront
  budgets; coating and cement environmental limits, since a cement that softens below the
  housing's limit is invisible to every mechanical screen; and cleanliness declared
  together with the assembly environment that has to achieve it.

- **ADDED** shipped environment profiles (benchtop, handheld, vehicle-mounted, airborne,
  sealed-and-purged) so one binding reaches a real scorecard — while a design-specific
  value no profile can supply still refuses by name, because a profile supplies
  environments and never the design's own properties.

## Impact

- Affected specs: new `optomechanical-screening`; `standards-data` (ADDED);
  `units-and-quantities` (ADDED); `tolerance-management` (ADDED).
- Depends on: `add-physical-domain-modules` (the manifest and composition rules),
  `add-performance-budgets` (focus, line-of-sight, and wavefront budgets are budgets),
  `add-keepout-envelopes` (the beam envelope is a keepout), `add-check-dependency-graph`
  (self-heating reaches the focus screen through a declared chain), and
  `add-constraint-topology` (a mount's constraint tally qualifies every alignment number
  computed across it), `add-failure-mode-coverage` (the module contributes the opto-mechanical catalog),
  `add-declaration-completeness` (the module's profiles are profiles), and
  `add-assembly-feasibility` (post-closure adjustment access is the opto-mechanical case
  it exists for). This change should land after all eight.
- Affected code (when implemented): a `packs/optomech` module composing existing thermal,
  contact, impact, o-ring, and optics screens; an optical material record type; angular
  units; ISO 10110 rendering.
- Explicitly out: ray tracing, diffraction propagation, optical design optimization,
  bundled vendor glass catalogs, tolerance-desensitization, straylight analysis, detector
  or display electronics design, and every targeting or fire-control application.
