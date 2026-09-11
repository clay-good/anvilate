# Tasks: Opto-mechanical screening module

## 0. Prerequisites

- [ ] 0.1 `add-physical-domain-modules` landed — manifest and composition rules exist
- [ ] 0.2 `add-performance-budgets` landed — budgets exist
- [ ] 0.3 `add-keepout-envelopes` landed — the beam envelope has a home
- [ ] 0.4 `add-check-dependency-graph` landed — self-heating can reach the focus screen
- [ ] 0.5 `add-constraint-topology` landed — mount tallies qualify alignment results
- [ ] 0.6 `add-failure-mode-coverage` landed — the module has a catalog to contribute to
- [ ] 0.7 `add-declaration-completeness` landed — profiles and screening depth exist
- [ ] 0.8 `add-assembly-feasibility` landed — post-closure access can be screened

## 1. Units and data

- [ ] 1.1 Angular units first-class: mrad, µrad, arcsec, arcmin, deg, MOA; bare angular
      values refused on input and on render
- [ ] 1.2 Optical material record: index at declared wavelengths, Abbe, dn/dT, CTE over a
      declared range, E, ν, density, Knoop, stress-optic coefficient — all with provenance
- [ ] 1.3 refractiveindex.info (CC0) ingestion path; vendor catalogs user-supplied or
      fetch-on-first-use, never redistributed
- [ ] 1.4 Property-at-temperature contract: a property used outside its declared valid
      range reports not-evaluated naming the range

## 2. Thermal screens

- [ ] 2.1 Athermal focus shift: housing, cell, and element differential expansion plus
      dn/dT, against declared depth of focus
- [ ] 2.2 Depth-of-focus computation from f-number and wavelength, composing existing
      `optics` functions
- [ ] 2.3 Axial preload change with temperature; loss-of-contact and overstress bounds
- [ ] 2.4 Elastomeric annular bond thickness for athermal radial behavior, with Poisson's
      ratio effect stated

## 3. Dynamic screens

- [ ] 3.1 Declared shock environment type: magnitude, pulse shape, duration, axis, cycles
- [ ] 3.2 Equivalent static acceleration from a classical pulse with the amplification
      basis stated; Q or damping required, never defaulted
- [ ] 3.3 Random-vibration 3σ equivalent from a declared PSD and fundamental frequency
- [ ] 3.4 Retention preload required to hold an element against declared acceleration
- [ ] 3.5 Mount-compliance to element tilt and decenter to angular line-of-sight shift

## 4. Optical-interface screens

- [ ] 4.1 Clear aperture and obscuration against a declared beam envelope; beam envelope
      emitted as a keepout
- [ ] 4.2 Glass contact stress at the retention interface by declared interface geometry,
      against user-supplied allowable tensile stress with the Weibull caveat rendered
- [ ] 4.3 Stress birefringence retardance from stress and stress-optic coefficient
- [ ] 4.4 RMS wavefront error budget with the Maréchal criterion as a declared threshold

## 5. Environment and sealing

- [ ] 5.1 Internal dew-point / condensation screen at declared cold soak, composing the
      existing psychrometric and thermal screens
- [ ] 5.2 Seal gland screening composing the existing o-ring set; gland at temperature
      extremes, not only at ambient

## 6. Budgets

- [ ] 6.1 Focus budget, line-of-sight budget, and wavefront budget as declared budgets
      with contributors bound to the screens above
- [ ] 6.2 Worked example proving the defect class: every screen green, budget red

## 7. Drawings

- [ ] 7.1 ISO 10110 indications rendered from the existing tolerance model
- [ ] 7.2 Scratch-dig equivalent rendered only when the user declares that convention

## 8. Interop

- [ ] 8.1 Typed import of prescription and surface-deformation quantities with tool
      identity and version recorded
- [ ] 8.2 Refusal when a screen's prescription inputs are absent — never estimated

## 9. Docs & examples

- [ ] 9.1 Example: a sealed housing holding a lens cell through a declared thermal range
      and shock environment, ending in a line-of-sight budget
- [ ] 9.2 Scope page: what this module screens, what it refuses, and why it is not a ray
      tracer

## 10. Workflow coverage

- [ ] 10.1 Differential boresight between two declared paths, common-mode identified
- [ ] 10.2 Internal dissipation to internal rise, consumed by thermal and condensation
- [ ] 10.3 Thermal-condition kind; soak screen refuses a gradient; dwell versus time
      constant
- [ ] 10.4 Dynamic clearance against shock displacement, distinct from static intrusion
- [ ] 10.5 Adjustment mechanism screens; every mechanism a budget contributor
- [ ] 10.6 Tilted plane-parallel element image displacement into focus and boresight
- [ ] 10.7 Parasitic harness load across a mount interface
- [ ] 10.8 Retention-after-cycling as a verification-only entry, never inferred
- [ ] 10.9 Three end-to-end workflow examples, each exercising a real failure; CI fails a
      claimed workflow with no example and an example that cannot fail

## 11. Environmental and contamination

- [ ] 11.1 Outgassing census over declared non-metallics; condensable fraction governing;
      population size reported
- [ ] 11.2 Seal breathing per thermal cycle; equalization path, desiccant, or purge
      required for a cycling sealed volume; ingress accumulation verification-only
- [ ] 11.3 Window and closure screens under declared differential, both directions, with
      induced bow entering the focus and wavefront budgets
- [ ] 11.4 Coating and cement environmental limits per surface
- [ ] 11.5 Cleanliness level against the declared assembly environment
- [ ] 11.6 Opto-mechanical failure-mode catalog contributions, each check declaring the
      modes it addresses

## 12. Day-one usability

- [ ] 12.1 Five cited environment profiles with applicability statements
- [ ] 12.2 Profile-sourced values marked on every surface; per-value override
- [ ] 12.3 Design-specific properties still refuse by name under any bound profile
