"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. The
modules:

- :mod:`~anvilate.analysis.accumulator` — gas-charged hydraulic accumulators: the usable
  fluid volume delivered between two pressures, and its inverse (the size a duty needs)
- :mod:`~anvilate.analysis.acoustics` — machinery-noise arithmetic (for plant/industrial
  work): the decibel sum of several sources and the inverse-square distance attenuation
- :mod:`~anvilate.analysis.adhesive` — bonded joints: the lap-joint average shear
  stress against the datasheet lap-shear strength, and the axial and torque
  capacity of a cylindrical retaining-compound bond
- :mod:`~anvilate.analysis.axial` — direct axial stress, section area, the
  minimum area an axial load requires, and the axial elongation and stiffness
- :mod:`~anvilate.analysis.beam` — bending (cantilever / simply-supported /
  fixed-fixed / fixed-pinned; point, distributed, triangular, patch, and
  applied-couple loads), transverse shear, shear flow (VQ/I) and built-up-beam
  fastener spacing, section second moments (rectangular, circular, hollow circle,
  box tube, and I-section), the plastic section modulus / fully-plastic hinge
  moment (solid and hollow rectangle and circle, I-section), the plastic
  collapse load (point and distributed) of a simply-supported, fixed-fixed, and
  propped-cantilever beam, and the bearing-misalignment slope (simply-supported end
  under a central or distributed load, and cantilever tip under an end or
  distributed load); and the AISC 360 design strengths of a steel member — flexure
  of a round HSS (§F8), a rectangular HSS (§F7), and minor-axis I-shapes (§F6); web
  shear of an I-shape (§G2.1), a round HSS (§G4), and a rectangular HSS (§G5); the
  web local yielding, crippling, and compression buckling at a concentrated load
  (§J10) with the bearing length a reaction needs; and slender-web plate girders
  (§F5 R_pg and compression-flange stress, §G2.2 tension-field shear)
- :mod:`~anvilate.analysis.beam_foundation` — beam on a continuous elastic
  foundation (Hetényi): the characteristic parameter β, and the peak deflection and
  bending moment a point load makes on a long (effectively infinite) beam
- :mod:`~anvilate.analysis.plate` — flat-plate bending (simply-supported
  rectangle via the exact Navier series; circular, simply-supported and clamped,
  under uniform pressure or a central point load), the clamped-cover thickness a
  pressure requires, the column base-plate thickness a bearing pressure requires
  (AISC Design Guide 1), elastic plate/web buckling,
  and the compression/shear-buckling coefficients
- :mod:`~anvilate.analysis.section` — ``CrossSection`` bundling area, second
  moment, extreme fibre, section modulus, and radius of gyration; the bending
  stress a moment makes and the minimum section modulus it requires; the channel
  shear centre and the doubly-symmetric warping constant C_w = I_y·h²/4
- :mod:`~anvilate.analysis.aisc_compactness` — AISC 360 Table B4.1b flexural
  classification: the flange and web plastic (λ_p) and noncompact (λ_r) slenderness
  limits, and the compact/noncompact/slender class an element's slenderness falls in
- :mod:`~anvilate.analysis.column` — Euler and Johnson buckling, slenderness,
  the minimum section second moment a load requires, the eccentric-load secant
  stress, the Perry-Robertson imperfect-column stress, the lateral-torsional
  buckling moment of an unbraced beam, and the empirical Rankine-Gordon column
  stress; and the AISC 360 steel checks — the §E3 flexural buckling stress, the
  §F2 lateral-torsional bracing limits L_p and L_r with the inelastic-LTB moment
  between them, the §F3 flange-local-buckling moment (noncompact interpolation and
  slender-flange elastic form), the §H1.1 beam-column interaction (uniaxial or biaxial), and the
  alignment-chart effective-length factor K of a framed column (braced and sway)
  from its joint stiffness ratios, and the §C2 second-order moment amplifiers B₁
  (member P-δ) and B₂ (story P-Δ)
- :mod:`~anvilate.analysis.torsion` — the torque a power/speed makes, solid and
  hollow shaft torsion, twist, torsional stiffness, and the shaft diameter a
  torque requires — the static von Mises size and the DE-Goodman and DE-Gerber
  fatigue sizes for a rotating shaft under reversed bending and steady torque;
  thin-walled
  rectangular (box) tube torsion (Bredt), thin
  open-section (strip) torsion, general closed thin-tube (Bredt) torsion, and
  solid rectangular, elliptical, and equilateral-triangle bar torsion
- :mod:`~anvilate.analysis.power_screw` — square-thread lead-screw raise/lower
  torque, the load a given input torque can raise (jack capacity), efficiency, the
  self-locking condition, and the collar (thrust-bearing) friction torque
- :mod:`~anvilate.analysis.ball_screw` — ball-screw drive torque T = F·L/(2π·η) and
  the back-driving torque T_b = F·L·η_b/(2π) a holding brake must resist (not self-locking)
- :mod:`~anvilate.analysis.worm` — worm-drive reduction ratio, lead angle,
  mesh efficiency, the efficiency-corrected wheel output torque, the self-locking
  condition, and the input tangential and separating (radial) tooth forces
- :mod:`~anvilate.analysis.clutch` — disc and cone clutch / brake friction torque
  (uniform-wear and uniform-pressure), the clamp force a torque requires, and the
  engagement slip energy ½·(I₁I₂/(I₁+I₂))·Δω² and brake absorbed energy ½·I·ω²
  the friction faces must dissipate
- :mod:`~anvilate.analysis.pressure_vessel` — thin-wall cylinder and sphere,
  exact Lamé thick-wall cylinder (closed or open ends) and sphere, the wall
  thickness a pressure requires (membrane and ASME VIII code form) and the ASME
  maximum allowable working pressure (MAWP) a wall gives, and the
  external-pressure collapse (buckling) pressure of a long cylinder and a sphere,
  the classical axial-compression buckling stress of a thin cylindrical shell, and
  the diametral growth a pressurized thin cylinder or sphere breathes
- :mod:`~anvilate.analysis.interference` — thick-wall press/shrink-fit (Lamé)
- :mod:`~anvilate.analysis.journal_bearing` — journal (plain) bearing Petroff
  friction torque and power loss, unit load, Sommerfeld number, the minimum
  oil-film thickness from the eccentricity ratio, and the specific film (lambda)
  ratio that sets the lubrication regime
- :mod:`~anvilate.analysis.contact` — Hertzian point (sphere) and line (cylinder) contact
- :mod:`~anvilate.analysis.ventilation` — indoor-air-quality airflow: ASHRAE 62.1
  breathing-zone outdoor air, air changes per hour, and contaminant dilution airflow
- :mod:`~anvilate.analysis.vortex_shedding` — flow-induced vibration: the Strouhal
  shedding frequency f_s = St·V/D, the lock-in velocity that resonates a structure,
  and the reduced velocity that screens the risk
- :mod:`~anvilate.analysis.wear` — Archard sliding-wear law: the worn volume and wear
  depth of a sliding contact, the sliding distance (wear life) a depth limit allows, and
  the plain-bearing PV (pressure × velocity) factor against its overheating limit
- :mod:`~anvilate.analysis.corrosion` — electrochemical metal loss: the ASTM G1
  weight-loss penetration rate, the Faraday rate from a corrosion current density,
  and the remaining wall life above a retirement thickness
- :mod:`~anvilate.analysis.coupling` — rigid flange-coupling torque, per-bolt
  shear force, and the bolt count a torque requires
- :mod:`~anvilate.analysis.creep` — high-temperature creep-rupture screening by the
  Larson-Miller parameter P = T·(C + log10 t_r): the parameter from a temperature and
  rupture time, its inverses for the rupture life and the limiting service temperature a
  required life allows, and the Robinson life-fraction damage Σ(t_i/t_r,i) of a
  varying-condition service spectrum
- :mod:`~anvilate.analysis.bearing` — rolling-bearing ISO 281 basic rating life
  (millions of revolutions and running hours) and the dynamic rating a target life
  requires, static load safety factor, the
  combined-load equivalent dynamic and static loads, and the reliability
  life-adjustment factor a₁
- :mod:`~anvilate.analysis.belt` — belt / capstan (Euler-Eytelwein) friction:
  tension ratio, slack tension, transmissible force (still and at speed, with
  centrifugal tension and the max-power belt speed), V-belt wedge friction,
  open- and crossed-belt-drive geometry (length and wrap angle), transmitted power
  and the tight-side tension a required power needs, and mean tension
- :mod:`~anvilate.analysis.chain` — roller-chain drive geometry: chain length in
  pitches, mean chain speed, the chordal (polygon-action) speed variation of
  a sprocket (and the fewest teeth a smoothness target allows), and the working
  tension from transmitted power
- :mod:`~anvilate.analysis.cable` — uniformly loaded cable (parabolic) midspan
  sag, peak support tension, and developed arc length, and the exact catenary
  (heavy-cable) sag, arc length, and peak tension
- :mod:`~anvilate.analysis.cam` — cam-follower rise kinematics (SHM, cycloidal,
  parabolic, and 3-4-5 polynomial profiles): follower displacement, velocity, and
  acceleration at a cam angle, the translating roller-follower pressure angle, and
  the minimum base circle a maximum pressure angle allows
- :mod:`~anvilate.analysis.geneva` — external Geneva (intermittent-indexing)
  mechanism geometry: index angle, crank and driven engagement radii, and the
  advance/dwell fraction of the cycle
- :mod:`~anvilate.analysis.hydraulic_cylinder` — fluid-cylinder actuator sizing:
  the extend and retract force (bore vs annular area), the extend and retract speed
  from the supply flow, and the rod-side pressure intensification of a blocked stroke
- :mod:`~anvilate.analysis.pneumatics` — compressed-air systems: the receiver hold-up
  time V·Δp/(Q·p_atm) and the receiver volume a required hold-up needs
- :mod:`~anvilate.analysis.compressible_flow` — gas dynamics: the speed of sound √(γRT),
  the Mach number, the stagnation-to-static temperature ratio, the critical pressure
  ratio and choked mass flow that size a relief valve, and the isentropic area ratio A/A*
  that sets a converging-diverging nozzle's exit Mach
- :mod:`~anvilate.analysis.gas_compression` — gas compression: the ideal-gas density,
  the isothermal and adiabatic compression power that bracket a compressor's duty, the
  adiabatic discharge temperature that sets intercooling, and the optimal per-stage ratio
  and power of a multi-stage machine
- :mod:`~anvilate.analysis.combustion` — furnace/boiler combustion: the stoichiometric
  air-fuel ratio from an ultimate analysis, the excess air read from flue-gas oxygen
  (EA = O₂/(20.9−O₂)), and the actual air-fuel ratio a burner runs at
- :mod:`~anvilate.analysis.power_cycles` — air-standard power-cycle efficiencies: the
  Otto (η = 1 − 1/r^(γ−1)), Diesel (with a cutoff ratio), and Brayton gas-turbine
  (η = 1 − 1/r_p^((γ−1)/γ)) ideal thermal efficiencies
- :mod:`~anvilate.analysis.flow_measurement` — differential-pressure flow metering: the
  orifice/venturi/nozzle discharge Q = C_d·A/√(1−β⁴)·√(2Δp/ρ), its pressure-drop sizing
  inverse, and the pitot-tube point velocity √(2Δp/ρ)
- :mod:`~anvilate.analysis.fluid_statics` — fluid statics: the hydrostatic pressure
  ρ·g·h, the resultant force on a submerged plane surface and its center-of-pressure
  depth, the Archimedes buoyant force on a submerged body, the metacentric height and
  righting moment that decide a floating body's stability, the stack-effect pressure that
  air buoyancy draws over a building or chimney height, the capillary rise of a liquid
  in a fine tube or pore, and the Weber number We = ρ·V²·L/σ that screens a droplet or jet
  for surface-tension breakup
- :mod:`~anvilate.analysis.pipe_flow` — incompressible pipe hydraulics: the Reynolds
  number, the Darcy friction factor (laminar 64/Re and turbulent Swamee-Jain), the
  Darcy-Weisbach friction head loss and fitting minor losses, the pressure drop ρ·g·h a
  pump must overcome, the empirical Hazen-Williams head loss and flow capacity for
  water mains, the hydraulic diameter that carries the round-pipe relations over to a
  non-circular duct, the Joukowsky water-hammer surge pressure with its critical
  valve-closure time, and the cavitation number σ = (p−p_v)/(½·ρ·V²) that screens a
  valve or orifice for cavitation
- :mod:`~anvilate.analysis.open_channel` — free-surface open-channel flow: the hydraulic
  radius, Manning's velocity and discharge V,Q = (1/n)·R^(2/3)·S^(1/2), the Froude number
  and rectangular critical depth that classify the flow as sub- or supercritical, the
  flow geometry of trapezoidal (canal) and partially-full circular (culvert) sections, the
  hydraulic jump (sequent depth and energy dissipated) below a spillway, the specific
  energy E = y + V²/2g with its critical-depth minimum, rectangular, V-notch, and
  broad-crested weir discharge for gauging channel flow and rating spillway sills, and
  the rational-method peak runoff Q = C·i·A that sets the drainage design flow
- :mod:`~anvilate.analysis.tank_flow` — tank draining: the Torricelli efflux velocity √(2gh)
  and the time to drain a tank between two levels through a bottom orifice
- :mod:`~anvilate.analysis.electrical` — electrical feeder sizing (for plant/industrial
  work): three-phase real and apparent power, the line current a load draws, conductor
  resistance ρ·L/A, the three-phase voltage drop along a feeder, the capacitor kVAR to
  correct a poor power factor, the transformer full-load and available fault current
  (the AIC rating downstream gear must interrupt), the Dwight earthing resistance of
  a driven ground rod and of rods in parallel, and the AC skin depth √(ρ/(π·f·μ))
- :mod:`~anvilate.analysis.reactive_circuit` — reactive components: the energy a
  capacitor (½·C·V²) and an inductor (½·L·I²) store, the RC/RL first-order time
  constants and the RC filter cutoff f_c = 1/(2π·R·C), and the LC resonant frequency
  f₀ = 1/(2π·√(L·C))
- :mod:`~anvilate.analysis.energy_storage` — battery/UPS backup sizing: the bank
  capacity a load needs (C = P·t/(V·DoD·η)), a bank's usable energy, and the runtime
  a given bank delivers
- :mod:`~anvilate.analysis.solar_pv` — photovoltaic array sizing: a module's power
  (P = G·A·η), the daily energy an array yields (E = P·PSH·D), and the array rating
  a daily load needs — pairs with energy_storage for off-grid design
- :mod:`~anvilate.analysis.wind_power` — wind-turbine power: the ½·ρ·V³ power density
  in the wind (cube law), the P = ½·ρ·A·V³·C_p a rotor delivers, and the Betz limit
  16/27 ceiling on the power coefficient
- :mod:`~anvilate.analysis.drag` — fluid-dynamic forces: the drag force ½·ρ·V²·C_d·A (wind
  load on a sign, current on a member), the terminal (settling) velocity where drag balances
  weight, the jet impact force ρ·Q·V·(1−cos θ) a stream delivers to a surface, and the
  low-Reynolds Stokes settling velocity and drag on a small sphere
- :mod:`~anvilate.analysis.hvac_duct` — air-duct sizing: the ASHRAE circular equivalent
  diameter of a rectangular duct (equal friction), and the fan shaft power P = Q·Δp/η
- :mod:`~anvilate.analysis.refrigeration` — refrigeration and heat-pump cycle performance:
  the Carnot cooling and heating COP ceilings and the actual COP = Q/W
- :mod:`~anvilate.analysis.psychrometrics` — moist-air properties for HVAC and drying: the
  Magnus saturation vapor pressure, the humidity ratio and relative humidity, the dew-point
  temperature, the moist-air enthalpy and cooling-coil load for capacity sizing, and the
  sensible/latent split with the sensible heat ratio SHR = Q_s/(Q_s + Q_l)
- :mod:`~anvilate.analysis.pump` — pump sizing: the hydraulic power ρ·g·Q·H, the shaft
  power P/η the driver must supply, the dimensionless specific speed that picks the
  impeller type, the affinity laws that scale flow, head, and power (∝ N, N², N³)
  when the same pump runs at a new speed, and the available NPSH and cavitation margin
  at the suction
- :mod:`~anvilate.analysis.slider_crank` — slider-crank (piston) exact
  displacement from top dead centre, slider velocity, slider acceleration, the
  connecting-rod obliquity side thrust on the piston, and the crank torque a piston
  force makes (T = F·dx/dθ)
- :mod:`~anvilate.analysis.scotch_yoke` — scotch-yoke pure simple-harmonic
  displacement, velocity, and acceleration (the infinite-rod slider-crank limit)
- :mod:`~anvilate.analysis.fourbar` — four-bar linkage Grashof rotatability
  criterion, mechanism-type classification, and the transmission angle at a given
  input angle
- :mod:`~anvilate.analysis.brake` — band-brake torque, the tight-side tension a
  torque requires, the peak lining pressure, and the simple/differential lever
  force; short-shoe (block) brake lever statics; the self-energizing /
  self-locking distinction for both
- :mod:`~anvilate.analysis.curved_beam` — Winkler curved-beam bending
  (rectangular, trapezoidal, circular, and composite T/I/box/stepped sections):
  shifted neutral axis and the unequal inner/outer fibre stresses of hooks,
  clamps, and links; and the thin circular ring's diametral deflection, peak
  moment under opposing loads, and external-pressure buckling load
- :mod:`~anvilate.analysis.illumination` — lighting design: point-source
  inverse-square cosine illuminance, the lumen method (room illuminance and
  its luminaire-count inverse), and installed lighting power density
- :mod:`~anvilate.analysis.impact` — drop / suddenly-applied shock-load
  amplification factor and the horizontal (kinetic-energy) impact force
  (energy method)
- :mod:`~anvilate.analysis.flywheel` — flywheel energy fluctuation, coefficient
  of fluctuation, the inertia a speed-smoothing target requires and the thin-rim
  mass that inertia needs, the rotating
  thin-rim hoop (bursting) stress, burst speed, and radial growth, the solid
  spinning disc's peak centre stress and its full radial/tangential stress
  distribution at any radius, and the annular (bored) disc's bore stress and full
  radial/tangential distribution
- :mod:`~anvilate.analysis.gear` — spur-gear transmitted/radial/normal tooth loads,
  bevel-gear radial/axial (thrust) resolution about the pitch cone, helical-gear
  axial thrust, radial load, and virtual tooth number, pitch-line
  velocity, Barth dynamic factor, Lewis tooth-root bending and the module a bending
  allowable requires, Hertzian surface
  contact stress, the mesh contact ratio, the minimum teeth to avoid undercut,
  the involute function and its Newton inverse, base tangent length (span
  measurement), the arc tooth thickness at any radius (top-land pointed-tooth check),
  the pitch, outside, and root diameters, the standard centre distance and the
  module a fixed centre requires,
  and the operating pressure angle and profile-shift sum for a non-standard centre,
  and train kinematics (signed compound-train value, reverted coaxial constraint,
  planetary Willis-equation speeds and ideal torque split, whole-tooth planet and
  assembly checks)
- :mod:`~anvilate.analysis.fastener` — bolt torque-tension, bearing, shear, the
  ISO 898 tensile stress area / axial stress, the proof load and recommended
  preload, thread-stripping engagement, and
  preloaded-joint load sharing (bolt and member stiffness, stiffness constant,
  bolt/member load, separation), the peak fastener force in an
  eccentrically-loaded shear group (AISC elastic method), and the AISC 360
  connection strengths — bolt shear (§J3.6), bearing/tear-out (§J3.10),
  slip-critical resistance (§J3.8), and block-shear rupture (§J4.3) — with the
  tension-member effective-net-area pieces (the §B4.3b staggered-hole net width
  and the §D3 shear-lag factor)
- :mod:`~anvilate.analysis.keys` — shaft-key shear and bearing stress, the key
  length a torque requires, and the torque a straight spline transmits
- :mod:`~anvilate.analysis.o_ring` — O-ring gland design geometry: the squeeze,
  gland-fill, and stretch fractions a groove must keep in band to seal without
  extruding or over-straining the ring
- :mod:`~anvilate.analysis.living_hinge` — moulded living-hinge fold strain
  ε = θ·t/(2·L) and the minimum web length a permissible flexural strain requires
- :mod:`~anvilate.analysis.weld` — fillet-weld throat shear, the weld leg a
  load requires, the peak throat stress of an eccentrically-loaded weld group
  (AISC elastic method), and the AISC 360 fillet-weld design strengths — the base
  §J2.4 weld-metal strength, the directional (sin θ) increase, and the companion
  §J4.2 base-metal shear rupture
- :mod:`~anvilate.analysis.rivet` — riveted-joint tearing/shearing/crushing
  strength, governing mode, and efficiency
- :mod:`~anvilate.analysis.rigging` — multi-leg sling lifting statics: the
  sling-angle tension multiplier 1/sin θ, each leg's tension, and the inward
  horizontal force at the pick points (the eyebolt/lifting-beam side load); plus
  the block-and-tackle actual mechanical advantage with per-sheave friction and
  the lead-line (winch) tension it implies
- :mod:`~anvilate.analysis.servo` — servo drivetrain sizing: the load inertia
  reflected through a gear ratio (J/i²), the vendor inertia-ratio screen, the
  motor torque an acceleration demands, the inertia-matching optimal ratio, the
  thermal RMS torque of a repeating duty cycle, and the peak velocity and
  acceleration a trapezoidal point-to-point move profile demands
- :mod:`~anvilate.analysis.winch` — winch-drum spooling geometry: the working
  radius and line pull at each rope layer (a fuller drum pulls less) and the
  tight-wound rope length a drum stores
- :mod:`~anvilate.analysis.wire_rope` — wire rope over a sheave: the wire bending
  stress E_r·d_w/D, the minimum sheave a bending allowable permits, the equivalent
  bending load folded into the rope's strength margin, and the rope-on-sheave
  bearing pressure 2F/(d·D)
- :mod:`~anvilate.analysis.spring` — helical-spring shear (Wahl), rate, active
  coils for a rate, solid (fully-compressed) length, stored
  energy, series/parallel combination, lateral (column) buckling, leaf-spring
  stress and rate, the helical torsion spring's angular rate and inner-fibre
  bending stress, the Belleville (disc) washer's Almen-Laszlo load-deflection
  curve and flat load, and the flat spiral (clock) spring's rate and stress
- :mod:`~anvilate.analysis.thermal` — thermal growth, constrained thermal
  stress, thermal-shock (quench) surface stress, the thermal-buckling ("sun kink")
  temperature rise of a held bar, the triaxial (fully-constrained) thermal stress,
  the through-wall linear-gradient bending stress of a restrained wall,
  shrink-fit assembly temperature, CTE-mismatch (differential) joint stress, and the
  Timoshenko bimetallic-strip curvature and cantilever tip deflection; plus
  heat-transfer screening — conduction/convection/spreading thermal resistances and
  their series/parallel network, the temperature rise Q·R and its junction-margin
  scorecard, straight-fin efficiency and the fin-array count a target resistance
  needs, and the flat-plate forced (laminar and turbulent) and vertical-plate natural
  convection coefficients with their validity ranges
- :mod:`~anvilate.analysis.dynamics` — modal screens: SDOF and Rayleigh
  estimates, the mass-on-beam frequencies (cantilever tip, simply-supported and
  fixed-fixed central, with the Rayleigh beam-mass correction), the Dunkerley
  multi-mass combination, distributed-mass beam
  fundamentals, taut-string/cable transverse modes, disc-on-shaft and two-rotor
  drivetrain torsional modes,
  and damped-vibration measures (damped frequency, log decrement, quality factor,
  critical damping coefficient, isolator transmissibility and its design inverse
  (the mount natural frequency and static deflection a target isolation needs),
  forced-response dynamic
  magnification and phase, and the base-excitation seismic-instrument response);
  simple and physical (rigid-body) pendulum periods; the solid-disc and annular
  (hollow-cylinder) polar mass moments of inertia; the rotating-unbalance
  centrifugal force, the counterweight that balances it, and the ISO 1940
  balance-grade permissible eccentricity;
  and the Den Hartog tuned-mass-damper optimal tuning
- :mod:`~anvilate.analysis.stress` — von Mises and octahedral-shear combination,
  the plane principal stresses and their orientation angle, the maximum shear,
  Tresca, combined axial+bending, and the Inglis elliptical-hole
  stress-concentration factor
- :mod:`~anvilate.analysis.fracture` — linear-elastic fracture mechanics: mode-I
  stress-intensity factor, the critical crack length for fast fracture, the
  Paris-Erdogan fatigue crack-growth rate and integrated propagation life, the
  Irwin crack-tip plastic-zone size, and the ASTM E399 plane-strain thickness a
  valid K_IC requires
- :mod:`~anvilate.analysis.fatigue` — Goodman, Soderberg, and Gerber fatigue,
  the max/min → amplitude/mean cyclic-stress converter, the Goodman and
  Smith-Watson-Topper equivalent reversed stresses, the fatigue notch factor
  (with the Neuber and Peterson notch sensitivities that feed it),
  the steel endurance-limit estimate with its Marin correction to the real
  part, the Basquin S-N finite-life law,
  Palmgren-Miner cumulative damage over a load spectrum, and the EN 1993-1-9 weld
  detail-category fatigue curve (endurance and allowable-range, the thickness
  size-effect, and a spectrum scorecard that will not pass without a chosen category)
- :mod:`~anvilate.analysis.gasket` — bolted-flange gasket bolt loads (ASME VIII
  Appendix 2): the gasket seating load (π·b·G·y), the operating load (hydrostatic
  end force plus the m-factor residual gasket reaction), and the governing (larger)
  bolt load a flange is sized for
- :mod:`~anvilate.analysis.sheetmetal` — sheet-metal bending flat-pattern geometry:
  the neutral-axis radius and bend allowance (K-factor), the outside setback and
  bend deduction, the developed blank length of a multi-bend strip, the minimum
  bend radius a material's ductility allows, the air (V-die) bending force, and the
  shear-cutting / round-hole punching force and the stripping force to clear the punch,
  and the deep-drawing cup blank diameter, draw ratio, and drawing force
- :mod:`~anvilate.analysis.snapfit` — constant-section cantilever snap-fit design by
  strain: the permissible deflection a material allowable permits, the peak root strain
  a required undercut imposes, the finger deflection (spring) force, and the mating
  (assembly) force over the lead-in ramp
- :mod:`~anvilate.analysis.nds_timber` — the NDS wood adjusted design value
  F' = F·∏Cᵢ (the reference value times its visible factor chain, with the Table
  2.3.2 load-duration factor), the bending scorecard (not evaluated without a
  reference value), the column stability factor C_P (Ylinen) and its Euler buckling
  stress, and the §3.9.2 combined bending + axial interaction
- :mod:`~anvilate.analysis.cold_formed_steel` — the AISI S100 effective-width method
  (Winter): the plate slenderness λ that decides whether a thin compression element is
  fully effective, and the reduced effective width above the limit
- :mod:`~anvilate.analysis.aluminum` — Aluminum Design Manual member checks: the
  unified straight-line/Euler buckling stress from the alloy-temper's buckling
  constants (column, beam, or local buckling), and the tension stress F = min(F_ty,
  F_tu/k_t)
- :mod:`~anvilate.analysis.composite` — fiber-composite micromechanics (rule of
  mixtures): the longitudinal (iso-strain) modulus and strength, and the transverse
  (iso-stress inverse-rule) modulus of a unidirectional laminate from its fiber and
  matrix properties and volume fraction
- :mod:`~anvilate.analysis.geotechnical` — soil mechanics closed forms: the Rankine
  active/passive earth-pressure coefficients and resultant thrust on a retaining wall
  (with the cohesive-soil active and passive pressures, the tension-crack depth, and the
  sloped-backfill coefficient for an embankment behind the wall),
  the Terzaghi bearing-capacity factors and ultimate pressure of a strip footing (with
  Vesić shape and depth factors and Meyerhof load-inclination factors that correct it for
  a rectangular embedded footing under an inclined load),
  Terzaghi 1D consolidation settlement with its time-rate factor, retaining-wall
  external stability (overturning, sliding, and eccentric base-pressure) checks, the
  infinite-slope factor of safety, the 2:1 vertical stress increase under a footing, the
  α-method pile capacity (shaft skin friction plus end bearing) for deep foundations, and
  groundwater seepage (Darcy flow, seepage velocity, and the critical gradient and piping
  factor of safety), and the Janssen silo pressure of stored granular material
- :mod:`~anvilate.analysis.road_curve` — highway/rail curve superelevation (AASHTO):
  the minimum curve radius a design speed needs (R = v²/(g·(e+f))), the friction-free
  ideal superelevation rate, and the maximum speed a banked curve can be taken at
- :mod:`~anvilate.analysis.masonry` — TMS 402 masonry allowable-stress design: the
  slenderness-reduced allowable axial stress F_a = 0.25·f'm·[1 − (h/140r)²] of an
  unreinforced member, the axial capacity of a reinforced masonry column, and the
  combined axial-plus-flexure unity check f_a/F_a + f_b/F_b that governs a wall under
  gravity and out-of-plane wind
- :mod:`~anvilate.analysis.prestressed_concrete` — T. Y. Lin load balancing: the
  uniform load a parabolic tendon balances (w_b = 8·P·e/L²), the service bottom-fibre
  stress (which collapses to −P/A under the balanced load), and the cracking moment
  M_cr = f_r·S + P·(S/A + e)

Note: :mod:`~anvilate.analysis.pressure_vessel` also carries the ASME VIII head forms
(ellipsoidal, torispherical, hemispherical/sphere — each sizing and MAWP) and the
ASME B31.3 process-piping checks (straight-pipe wall and rating with the ordered-wall
gross-up, branch reinforcement area, and the displacement stress-range allowable).

Further analytical cases land here as they are built out (see
openspec/specs/validation-gauntlet/).
"""

from __future__ import annotations

from .accumulator import (
    accumulator_size_for_volume,
    accumulator_usable_volume,
)
from .acoustics import (
    inverse_square_attenuation,
    mass_law_transmission_loss,
    noise_dose_fraction,
    permissible_exposure_time,
    sabine_reverberation_time,
    sound_level_sum,
    sound_power_level_from_intensity,
    sound_pressure_from_power_level,
)
from .adhesive import (
    cylindrical_bond_axial_capacity,
    cylindrical_bond_torque_capacity,
    lap_joint_average_shear_stress,
)
from .aisc_compactness import (
    CompactnessClass,
    classify_flexural_element,
    flexural_flange_slenderness_limits,
    flexural_web_slenderness_limits,
)
from .aluminum import (
    aluminum_buckling_stress,
    aluminum_tension_stress,
)
from .axial import (
    axial_elongation,
    axial_stiffness,
    axial_stress,
    circular_area,
    required_axial_area,
)
from .ball_screw import (
    ball_screw_back_drive_torque,
    ball_screw_drive_torque,
)
from .beam import (
    SHEAR_FORM_CIRCULAR,
    SHEAR_FORM_RECTANGULAR,
    BeamBendingResult,
    aisc_bearing_length_for_web_yielding,
    aisc_minor_axis_flexural_strength,
    aisc_plate_girder_bending_factor,
    aisc_plate_girder_flange_stress,
    aisc_rectangular_hss_flexural_strength,
    aisc_rectangular_hss_shear_strength,
    aisc_round_hss_flexural_strength,
    aisc_round_hss_shear_strength,
    aisc_tension_field_shear_strength,
    aisc_web_compression_buckling_strength,
    aisc_web_crippling_strength,
    aisc_web_local_yielding_strength,
    aisc_web_shear_strength,
    cantilever_center_patch_load,
    cantilever_end_load,
    cantilever_end_load_tip_slope,
    cantilever_end_moment,
    cantilever_offset_load,
    cantilever_offset_moment,
    cantilever_partial_uniform_load,
    cantilever_triangular_load,
    cantilever_triangular_load_peak_at_tip,
    cantilever_uniform_load,
    cantilever_uniform_load_tip_slope,
    circular_plastic_section_modulus,
    circular_second_moment,
    deflection_scorecard,
    fastener_spacing_for_shear_flow,
    fixed_fixed_center_load,
    fixed_fixed_center_patch_load,
    fixed_fixed_offset_load,
    fixed_fixed_partial_uniform_load,
    fixed_fixed_plastic_collapse_load,
    fixed_fixed_plastic_collapse_udl,
    fixed_fixed_triangular_load,
    fixed_fixed_uniform_load,
    fixed_pinned_center_load,
    fixed_pinned_center_patch_load,
    fixed_pinned_end_moment,
    fixed_pinned_offset_load,
    fixed_pinned_partial_uniform_load,
    fixed_pinned_triangular_load,
    fixed_pinned_triangular_load_peak_at_prop,
    fixed_pinned_uniform_load,
    hollow_circular_plastic_section_modulus,
    hollow_circular_second_moment,
    i_section_plastic_section_modulus,
    i_section_second_moment,
    max_transverse_shear_stress,
    overhang_tip_load,
    overhang_uniform_load,
    plastic_moment,
    propped_cantilever_plastic_collapse_load,
    propped_cantilever_plastic_collapse_udl,
    rectangular_plastic_section_modulus,
    rectangular_second_moment,
    rectangular_tube_plastic_section_modulus,
    rectangular_tube_second_moment,
    shear_flow,
    simply_supported_center_load,
    simply_supported_center_load_support_slope,
    simply_supported_center_patch_load,
    simply_supported_end_moment,
    simply_supported_offset_load,
    simply_supported_offset_moment,
    simply_supported_partial_uniform_load,
    simply_supported_plastic_collapse_load,
    simply_supported_plastic_collapse_udl,
    simply_supported_symmetric_point_loads,
    simply_supported_triangular_load,
    simply_supported_uniform_load,
    simply_supported_uniform_load_support_slope,
    span_deflection_limit,
    two_span_continuous_interior_reaction,
    two_span_continuous_middle_moment,
)
from .beam_foundation import (
    beam_on_elastic_foundation_max_deflection,
    beam_on_elastic_foundation_max_moment,
    foundation_characteristic_parameter,
)
from .bearing import (
    BALL_BEARING_LIFE_EXPONENT,
    BEARING_WEIBULL_SLOPE,
    ROLLER_BEARING_LIFE_EXPONENT,
    bearing_basic_rating_life,
    bearing_equivalent_dynamic_load,
    bearing_equivalent_static_load,
    bearing_life_hours,
    bearing_rating_for_life,
    bearing_reliability_life_factor,
    bearing_static_safety_factor,
)
from .belt import (
    belt_centrifugal_tension,
    belt_length,
    belt_max_transmissible_force,
    belt_max_transmissible_force_at_speed,
    belt_mean_tension,
    belt_slack_tension,
    belt_speed_for_max_power,
    belt_tight_tension_for_power,
    belt_transmitted_power,
    belt_wrap_angle,
    capstan_tension_ratio,
    crossed_belt_length,
    crossed_belt_wrap_angle,
    vee_belt_effective_friction,
)
from .brake import (
    band_brake_max_lining_pressure,
    band_brake_tight_tension_for_torque,
    band_brake_torque,
    differential_band_brake_actuation_force,
    differential_band_brake_is_self_locking,
    short_shoe_brake_torque,
    short_shoe_is_self_locking,
    short_shoe_normal_force,
)
from .cable import (
    catenary_arc_length,
    catenary_max_tension,
    catenary_sag,
    parabolic_cable_length,
    parabolic_cable_max_tension,
    parabolic_cable_sag,
)
from .cam import (
    CamMotion,
    cam_base_circle_for_pressure_angle,
    cam_follower_motion,
    cam_pressure_angle,
)
from .chain import (
    chain_length_in_pitches,
    chain_speed,
    chain_working_tension,
    chordal_speed_variation,
    minimum_sprocket_teeth_for_chordal_variation,
)
from .clutch import (
    UNIFORM_PRESSURE,
    UNIFORM_WEAR,
    brake_absorbed_energy,
    clutch_engagement_energy,
    cone_clutch_torque,
    disc_clutch_force_for_torque,
    disc_clutch_torque,
)
from .cold_formed_steel import (
    aisi_effective_width,
    aisi_plate_slenderness,
)
from .column import (
    ColumnEnd,
    aisc_beam_column_interaction,
    aisc_effective_length_factor_braced,
    aisc_effective_length_factor_sway,
    aisc_effective_radius_of_gyration,
    aisc_elastic_ltb_stress,
    aisc_flange_local_buckling_moment,
    aisc_flexural_buckling_stress,
    aisc_inelastic_ltb_limit,
    aisc_inelastic_ltb_moment,
    aisc_moment_amplifier_b1,
    aisc_moment_amplifier_b2,
    aisc_plastic_bracing_limit,
    aisc_slender_flange_moment,
    euler_buckling_load,
    euler_critical_stress,
    euler_second_moment_for_load,
    johnson_critical_stress,
    lateral_torsional_buckling_moment,
    perry_robertson_stress,
    radius_of_gyration,
    rankine_gordon_stress,
    secant_column_max_stress,
    slenderness_ratio,
    transition_slenderness,
)
from .combustion import (
    actual_air_fuel_ratio,
    excess_air_from_flue_oxygen,
    stoichiometric_air_fuel_ratio,
)
from .composite import (
    composite_longitudinal_cte,
    composite_major_poisson_ratio,
    composite_shear_modulus_inverse_rule,
    critical_fiber_length,
    off_axis_modulus,
    rule_of_mixtures_modulus,
    rule_of_mixtures_strength,
    transverse_modulus_inverse_rule,
    tsai_hill_failure_index,
)
from .compressible_flow import (
    choked_mass_flow_rate,
    critical_pressure_ratio,
    isentropic_area_ratio,
    mach_number,
    speed_of_sound,
    stagnation_density_ratio,
    stagnation_pressure_ratio,
    stagnation_temperature_ratio,
)
from .contact import (
    HertzContact,
    HertzLineContact,
    hertz_cylinder_contact,
    hertz_effective_modulus,
    hertz_sphere_approach,
    hertz_sphere_contact,
)
from .corrosion import (
    corrosion_penetration_rate,
    faraday_corrosion_rate,
    remaining_wall_life,
)
from .coupling import (
    flange_coupling_bolt_count,
    flange_coupling_bolt_force,
    flange_coupling_torque,
)
from .creep import (
    LARSON_MILLER_CONSTANT,
    creep_life_fraction_damage,
    larson_miller_parameter,
    larson_miller_rupture_life,
    larson_miller_temperature_limit,
)
from .curved_beam import (
    CurvedBeamStress,
    circular_curved_beam_stress,
    composite_curved_beam_stress,
    rectangular_curved_beam_stress,
    thin_ring_buckling_pressure,
    thin_ring_diametral_deflection,
    thin_ring_max_moment,
    trapezoidal_curved_beam_stress,
)
from .drag import (
    drag_force,
    jet_impact_force,
    stokes_drag_force,
    stokes_settling_velocity,
    terminal_velocity,
)
from .dynamics import (
    STANDARD_GRAVITY,
    annular_disc_polar_mass_moment,
    balance_correction_mass,
    balance_quality_permissible_eccentricity,
    base_excitation_relative_transmissibility,
    cantilever_fundamental_frequency,
    cantilever_tip_mass_frequency,
    clamped_annular_plate_fundamental_frequency,
    clamped_circular_plate_fundamental_frequency,
    clamped_plate_fundamental_frequency,
    critical_damping_coefficient,
    damped_natural_frequency,
    dunkerley_fundamental_frequency,
    dynamic_magnification_factor,
    fixed_fixed_center_mass_frequency,
    fixed_fixed_fundamental_frequency,
    fixed_pinned_fundamental_frequency,
    frequency_scorecard,
    isolation_scorecard,
    isolator_natural_frequency_for_transmissibility,
    isolator_static_deflection_for_transmissibility,
    logarithmic_decrement,
    natural_frequency,
    natural_frequency_from_deflection,
    physical_pendulum_period,
    quality_factor,
    resonance_phase_angle,
    rotating_unbalance_force,
    simple_pendulum_period,
    simply_supported_annular_plate_fundamental_frequency,
    simply_supported_center_mass_frequency,
    simply_supported_circular_plate_fundamental_frequency,
    simply_supported_fundamental_frequency,
    simply_supported_plate_fundamental_frequency,
    solid_disc_polar_mass_moment,
    spring_surge_frequency,
    string_natural_frequency,
    torsional_natural_frequency,
    transmissibility,
    tuned_mass_damper_optimal_damping,
    tuned_mass_damper_optimal_frequency_ratio,
    two_rotor_torsional_natural_frequency,
)
from .electrical import (
    apparent_power_three_phase,
    conductor_resistance,
    ground_rod_resistance,
    line_current_for_power,
    parallel_ground_electrodes_resistance,
    power_factor_correction_kvar,
    skin_depth,
    three_phase_power,
    transformer_available_fault_current,
    transformer_full_load_current,
    voltage_drop_three_phase,
)
from .energy_storage import (
    battery_backup_time,
    battery_bank_capacity,
    usable_battery_energy,
)
from .fastener import (
    NUT_FACTOR_AS_RECEIVED,
    aisc_tension_member_design_strength,
    bearing_stress,
    block_shear_strength,
    bolt_axial_stiffness,
    bolt_axial_stress,
    bolt_bearing_strength,
    bolt_diameter_for_shear,
    bolt_load_in_joint,
    bolt_preload_from_torque,
    bolt_proof_load,
    bolt_shear_strength,
    bolt_shear_stress,
    bolt_tensile_stress_area,
    eccentric_shear_group_peak_force,
    joint_separation_load,
    joint_stiffness_factor,
    member_clamp_load_in_joint,
    member_stiffness_frustum,
    net_width_staggered_holes,
    preloaded_bolt_cyclic_stress,
    recommended_bolt_preload,
    shear_lag_factor,
    slip_critical_resistance,
    thread_engagement_for_load,
    thread_stripping_shear_area,
    thread_stripping_stress,
    torque_for_preload,
)
from .fatigue import (
    CyclicStress,
    basquin_cycles_to_failure,
    basquin_stress_for_life,
    coffin_manson_reversals,
    cyclic_stress_components,
    estimated_endurance_limit,
    fatigue_notch_factor,
    gerber_safety_factor,
    gerber_scorecard,
    goodman_equivalent_reversed_stress,
    goodman_safety_factor,
    goodman_scorecard,
    marin_endurance_limit,
    miner_cumulative_damage,
    miner_spectrum_repeats_to_failure,
    morrow_equivalent_reversed_stress,
    neuber_notch_sensitivity,
    peterson_notch_sensitivity,
    smith_watson_topper_stress,
    soderberg_safety_factor,
    soderberg_scorecard,
    strain_life_total_amplitude,
    weld_constant_amplitude_fatigue_limit,
    weld_cutoff_limit,
    weld_detail_allowable_stress_range,
    weld_detail_endurance_cycles,
    weld_fatigue_scorecard,
    weld_size_corrected_detail_category,
    weld_size_effect_factor,
)
from .flow_measurement import (
    differential_pressure_for_flow,
    obstruction_meter_flow_rate,
    pitot_velocity,
)
from .fluid_statics import (
    buoyant_force,
    capillary_rise,
    center_of_pressure_depth,
    hydrostatic_force_on_plane,
    hydrostatic_pressure,
    metacentric_height,
    righting_moment,
    stack_effect_pressure,
    weber_number,
)
from .flywheel import (
    coefficient_of_fluctuation,
    flywheel_energy_fluctuation,
    flywheel_inertia_for_fluctuation,
    rim_flywheel_mass,
    rotating_annular_disc_bore_stress,
    rotating_annular_disc_radial_stress,
    rotating_annular_disc_tangential_stress,
    rotating_rim_burst_speed,
    rotating_rim_hoop_stress,
    rotating_rim_radial_growth,
    rotating_solid_disc_max_stress,
    rotating_solid_disc_radial_stress,
    rotating_solid_disc_tangential_stress,
)
from .fourbar import (
    fourbar_transmission_angle,
    fourbar_type,
    is_grashof,
)
from .fracture import (
    crack_tip_plastic_zone_size,
    critical_crack_length,
    paris_law_crack_growth_rate,
    paris_law_cycles_to_failure,
    plane_strain_thickness_requirement,
    stress_intensity_factor,
)
from .gas_compression import (
    adiabatic_compression_power,
    adiabatic_discharge_temperature,
    ideal_gas_density,
    isothermal_compression_power,
    multistage_compression_power,
    optimal_stage_pressure_ratio,
)
from .gasket import (
    gasket_operating_load,
    gasket_seating_load,
    governing_gasket_bolt_load,
)
from .gear import (
    PlanetaryTorques,
    agma_bending_stress,
    agma_contact_stress,
    agma_module_for_bending_stress,
    barth_velocity_factor,
    base_tangent_length,
    bevel_gear_axial_load,
    bevel_gear_radial_load,
    bevel_pitch_cone_angle,
    gear_center_distance,
    gear_contact_stress,
    gear_module_for_center_distance,
    gear_normal_load,
    gear_outside_diameter,
    gear_pitch_diameter,
    gear_radial_load,
    gear_root_diameter,
    gear_tangential_load,
    gear_tooth_thickness_at_radius,
    gear_train_efficiency,
    gear_train_value,
    helical_gear_axial_thrust,
    helical_gear_radial_load,
    helical_virtual_teeth,
    involute_angle,
    involute_function,
    lewis_bending_stress,
    lewis_module_for_bending_stress,
    minimum_teeth_to_avoid_undercut,
    operating_pressure_angle,
    pitch_line_velocity,
    planetary_can_assemble,
    planetary_planet_teeth,
    planetary_speed,
    planetary_torques,
    profile_shift_sum_for_center_distance,
    reverted_train_is_coaxial,
    spur_gear_contact_ratio,
)
from .geneva import (
    geneva_advance_fraction,
    geneva_crank_radius,
    geneva_driven_radius,
    geneva_dwell_fraction,
    geneva_index_angle,
)
from .geotechnical import (
    bearing_capacity_factors,
    bearing_depth_factors,
    bearing_inclination_factors,
    bearing_shape_factors,
    consolidation_settlement,
    consolidation_time,
    consolidation_time_factor,
    critical_hydraulic_gradient,
    darcy_seepage_flow,
    eccentric_base_pressure,
    infinite_slope_factor_of_safety,
    janssen_silo_pressure,
    pile_allowable_capacity,
    pile_end_bearing_capacity,
    pile_skin_friction_capacity,
    piping_factor_of_safety,
    rankine_active_pressure_cohesive,
    rankine_earth_pressure_coefficient,
    rankine_lateral_thrust,
    rankine_passive_pressure_cohesive,
    rankine_sloped_backfill_coefficient,
    retaining_wall_overturning_factor,
    retaining_wall_sliding_factor,
    seepage_velocity,
    tension_crack_depth,
    terzaghi_bearing_capacity,
    vertical_stress_increase_2to1,
)
from .hvac_duct import (
    circular_equivalent_diameter,
    fan_power,
)
from .hydraulic_cylinder import (
    cylinder_extend_force,
    cylinder_extend_speed,
    cylinder_regen_extend_force,
    cylinder_regen_extend_speed,
    cylinder_retract_force,
    cylinder_retract_speed,
    cylinder_rodside_intensified_pressure,
)
from .illumination import (
    lighting_power_density,
    lumen_method_illuminance,
    lumen_method_luminaire_count,
    point_source_illuminance,
)
from .impact import (
    SUDDENLY_APPLIED_FACTOR,
    horizontal_impact_force,
    impact_factor,
    impact_stress,
)
from .interference import (
    InterferenceFit,
    interference_axial_capacity,
    interference_fit,
    interference_for_contact_pressure,
    interference_torque_capacity,
)
from .journal_bearing import (
    journal_bearing_minimum_film_thickness,
    journal_bearing_unit_load,
    petroff_friction_power,
    petroff_friction_torque,
    sommerfeld_number,
    specific_film_ratio,
)
from .keys import (
    KeyLengthRequirement,
    key_bearing_stress,
    key_length_for_torque,
    key_shear_stress,
    key_tangential_force,
    spline_torque_capacity,
)
from .living_hinge import (
    living_hinge_fold_strain,
    living_hinge_web_length_for_strain,
)
from .masonry import (
    masonry_allowable_axial_stress,
    masonry_allowable_flexural_stress,
    masonry_column_axial_capacity,
    masonry_combined_stress_ratio,
)
from .nds_timber import (
    LoadDuration,
    nds_adjusted_design_value,
    nds_bearing_area_factor,
    nds_bending_scorecard,
    nds_column_stability_factor,
    nds_combined_bending_compression,
    nds_euler_buckling_stress,
    nds_load_duration_factor,
    nds_shear_scorecard,
    nds_shear_stress,
)
from .o_ring import (
    o_ring_gland_fill_fraction,
    o_ring_squeeze_fraction,
    o_ring_stretch_fraction,
)
from .open_channel import (
    broad_crested_weir_flow,
    circular_channel_properties,
    critical_depth_rectangular,
    froude_number,
    hydraulic_jump_downstream_depth,
    hydraulic_jump_energy_loss,
    hydraulic_radius,
    manning_flow_rate,
    manning_flow_velocity,
    minimum_specific_energy_rectangular,
    rational_method_peak_runoff,
    rectangular_weir_flow,
    specific_energy,
    trapezoidal_channel_properties,
    triangular_weir_flow,
)
from .pipe_flow import (
    cavitation_number,
    darcy_friction_factor,
    darcy_weisbach_head_loss,
    hazen_williams_flow_capacity,
    hazen_williams_head_loss,
    hydraulic_diameter,
    joukowsky_surge_pressure,
    minor_loss_head,
    pipe_pressure_drop,
    pressure_wave_speed,
    reynolds_number,
    surge_wave_period,
)
from .plate import (
    DEFAULT_POISSON_RATIO,
    PlateBendingResult,
    base_plate_thickness_for_bearing,
    clamped_annular_plate_uniform_load,
    clamped_circular_plate_center_load_deflection,
    clamped_circular_plate_thickness_for_pressure,
    clamped_circular_plate_uniform_load,
    clamped_plate_uniform_load,
    plate_buckling_stress,
    plate_compression_buckling_coefficient,
    plate_shear_buckling_coefficient,
    simply_supported_annular_plate_uniform_load,
    simply_supported_circular_plate_center_load_deflection,
    simply_supported_circular_plate_uniform_load,
    simply_supported_plate_center_patch_load,
    simply_supported_plate_uniform_load,
)
from .pneumatics import (
    air_receiver_holdup_time,
    air_receiver_volume_for_demand,
)
from .power_cycles import (
    brayton_cycle_efficiency,
    diesel_cycle_efficiency,
    otto_cycle_efficiency,
)
from .power_screw import (
    lead_angle,
    power_screw_collar_torque,
    power_screw_efficiency,
    power_screw_is_self_locking,
    power_screw_lower_torque,
    power_screw_raise_load,
    power_screw_raise_torque,
)
from .pressure_vessel import (
    ThickWallSphereStress,
    ThickWallStress,
    ThinWallStress,
    asme_b313_allowable_displacement_stress_range,
    asme_b313_bend_stress_intensification,
    asme_b313_branch_required_reinforcement_area,
    asme_b313_displacement_stress,
    asme_b313_minimum_ordered_wall,
    asme_b313_pipe_pressure,
    asme_b313_pipe_wall_thickness,
    asme_conical_head_mawp,
    asme_conical_head_thickness,
    asme_cylinder_mawp,
    asme_cylinder_thickness,
    asme_ellipsoidal_head_mawp,
    asme_ellipsoidal_head_thickness,
    asme_spherical_shell_mawp,
    asme_spherical_shell_thickness,
    asme_torispherical_head_mawp,
    asme_torispherical_head_thickness,
    cylinder_axial_buckling_stress,
    cylinder_external_pressure_buckling,
    sphere_external_pressure_buckling,
    thick_wall_cylinder,
    thick_wall_sphere,
    thin_wall_cylinder,
    thin_wall_cylinder_diametral_growth,
    thin_wall_sphere_diametral_growth,
    thin_wall_sphere_stress,
    thin_wall_thickness_for_pressure,
)
from .prestressed_concrete import (
    prestress_balanced_load,
    prestress_bottom_fiber_stress,
    prestress_cracking_moment,
)
from .psychrometrics import (
    cooling_coil_load,
    dew_point_temperature,
    humidity_ratio,
    latent_heat_load,
    moist_air_enthalpy,
    relative_humidity,
    saturation_vapor_pressure,
    sensible_heat_load,
    sensible_heat_ratio,
)
from .pump import (
    affinity_flow_rate,
    affinity_head,
    affinity_power,
    npsh_available,
    npsh_margin,
    pump_hydraulic_power,
    pump_shaft_power,
    pump_specific_speed,
    pump_suction_specific_speed,
)
from .reactive_circuit import (
    capacitor_stored_energy,
    inductor_stored_energy,
    lc_resonant_frequency,
    rc_cutoff_frequency,
    rc_time_constant,
    rl_time_constant,
)
from .refrigeration import (
    carnot_cop_cooling,
    carnot_cop_heating,
    coefficient_of_performance,
)
from .reinforced_concrete import (
    rc_beam_nominal_moment,
    rc_beta1,
    rc_column_axial_strength,
    rc_column_balanced_point,
    rc_concrete_shear_strength,
    rc_cracking_moment,
    rc_development_length,
    rc_doubly_reinforced_moment,
    rc_effective_moment_of_inertia,
    rc_max_bar_spacing_crack_control,
    rc_maximum_tension_controlled_steel,
    rc_minimum_flexural_steel,
    rc_net_tensile_strain,
    rc_shear_reinforcement_strength,
    rc_stirrup_spacing_for_shear,
    rc_strength_reduction_factor,
    rc_stress_block_depth,
    rc_t_beam_moment,
    rc_tension_steel_for_moment,
    rc_two_way_shear_strength,
)
from .rigging import (
    sling_horizontal_force,
    sling_leg_tension,
    sling_tension_factor,
    tackle_lead_line_tension,
    tackle_mechanical_advantage,
)
from .rivet import (
    RivetedJointStrength,
    riveted_joint_efficiency,
)
from .road_curve import (
    banked_curve_max_speed,
    ideal_superelevation_rate,
    minimum_curve_radius,
)
from .scotch_yoke import (
    scotch_yoke_acceleration,
    scotch_yoke_displacement,
    scotch_yoke_velocity,
)
from .section import (
    CompositeBeamStresses,
    CompoundSection,
    CrossSection,
    bending_stress,
    channel_shear_center,
    composite_beam_bending_stresses,
    compound_plastic_section_modulus,
    compound_section_properties,
    required_section_modulus,
    warping_constant_doubly_symmetric,
)
from .servo import (
    inertia_matching_gear_ratio,
    motor_acceleration_torque,
    reflected_inertia_ratio,
    reflected_load_inertia,
    rms_torque_over_cycle,
    trapezoidal_move_acceleration,
    trapezoidal_move_peak_velocity,
)
from .sheetmetal import (
    air_bending_force,
    bend_allowance,
    bend_deduction,
    cup_blank_diameter,
    deep_draw_force,
    draw_ratio,
    flat_pattern_length,
    minimum_bend_radius,
    neutral_axis_radius,
    outside_setback,
    round_hole_punching_force,
    shear_cutting_force,
    stripping_force,
)
from .slider_crank import (
    slider_crank_acceleration,
    slider_crank_displacement,
    slider_crank_piston_side_thrust,
    slider_crank_torque,
    slider_crank_velocity,
)
from .snapfit import (
    snap_fit_deflection_force,
    snap_fit_mating_force,
    snap_fit_permissible_deflection,
    snap_fit_strain,
)
from .solar_pv import (
    pv_array_power,
    pv_array_size_for_load,
    pv_daily_energy,
)
from .spring import (
    BELLEVILLE_PLATEAU_RATIO,
    SPRING_END_CLAMPED_FREE,
    SPRING_END_FIXED_HINGED,
    SPRING_END_HINGED_HINGED,
    SPRING_END_PARALLEL_PLATES,
    SpringBucklingResult,
    belleville_flat_load,
    belleville_washer_force,
    helical_spring_active_coils_for_rate,
    helical_spring_buckling,
    helical_spring_rate,
    helical_spring_solid_length,
    helical_torsion_spring_rate,
    helical_torsion_spring_stress,
    leaf_spring_rate,
    leaf_spring_stress,
    spiral_spring_rate,
    spiral_spring_stress,
    spring_index,
    spring_shear_stress,
    spring_stored_energy,
    springs_in_parallel,
    springs_in_series,
    wahl_factor,
)
from .stress import (
    CombinedNormalStress,
    combine_axial_bending,
    concentrated_stress,
    elliptical_hole_stress_concentration,
    max_shear_stress_plane,
    octahedral_shear_stress,
    plane_stress_at_angle,
    principal_angle_plane,
    principal_stresses_3d,
    principal_stresses_plane,
    strength_scorecard,
    tresca_equivalent_stress,
    tresca_principal,
    von_mises_bending_torsion,
    von_mises_plane_stress,
    von_mises_principal,
    yield_safety_factor,
)
from .tank_flow import (
    tank_drain_time,
    torricelli_efflux_velocity,
)
from .thermal import (
    DifferentialThermalStress,
    bimetallic_strip_curvature,
    bimetallic_strip_tip_deflection,
    biot_number,
    circular_source_spreading_resistance,
    conduction_thermal_resistance,
    confined_liquid_thermal_pressure,
    constrained_thermal_stress,
    convection_thermal_resistance,
    counterflow_effectiveness,
    counterflow_ntu_for_effectiveness,
    critical_insulation_radius,
    crossflow_both_unmixed_effectiveness,
    cylindrical_conduction_resistance,
    degree_day_cooling_energy,
    degree_day_heating_energy,
    differential_thermal_stress,
    dittus_boelter_convection_coefficient,
    fin_array_count_for_resistance,
    fin_efficiency,
    flat_plate_forced_convection_coefficient,
    flat_plate_turbulent_convection_coefficient,
    fourier_number,
    free_thermal_expansion,
    grashof_number,
    guided_cantilever_leg_length,
    heat_exchanger_area_for_duty,
    heat_exchanger_duty,
    heat_exchanger_ntu,
    horizontal_cylinder_natural_convection_coefficient,
    horizontal_plate_natural_convection_coefficient,
    junction_temperature_scorecard,
    laminar_tube_convection_coefficient,
    log_mean_temperature_difference,
    lumped_capacitance_cooling_time,
    lumped_capacitance_time_constant,
    parallel_flow_effectiveness,
    parallel_flow_ntu_for_effectiveness,
    parallel_thermal_resistance,
    radiation_heat_transfer,
    radiation_heat_transfer_coefficient,
    rayleigh_number,
    semi_infinite_solid_surface_flux,
    semi_infinite_solid_temperature_rise,
    series_thermal_resistance,
    shrink_fit_assembly_temperature,
    temperature_rise,
    thermal_buckling_temperature_rise,
    thermal_shock_stress,
    thermal_shock_temperature_limit,
    through_wall_gradient_thermal_stress,
    triaxial_constrained_thermal_stress,
    vertical_plate_natural_convection_coefficient,
    wien_peak_wavelength,
    wien_temperature_from_peak,
)
from .torsion import (
    elliptical_bar_torsional_stress,
    elliptical_bar_twist_angle,
    hollow_shaft_diameter_for_bending_torsion,
    hollow_shaft_torsional_stress,
    hollow_shaft_twist_angle,
    open_section_torsion_constant,
    polar_second_moment_hollow,
    polar_second_moment_solid,
    rectangular_bar_torsion_constant,
    rectangular_bar_torsional_stress,
    rectangular_bar_twist_angle,
    rectangular_tube_enclosed_area,
    rectangular_tube_torsional_stress,
    rectangular_tube_twist_angle,
    shaft_diameter_de_gerber,
    shaft_diameter_de_goodman,
    shaft_diameter_for_bending_torsion,
    shaft_diameter_for_torque,
    shaft_torsional_stiffness,
    shaft_torsional_stress,
    shaft_twist_angle,
    shaft_von_mises_stress,
    thin_closed_tube_torsional_stress,
    thin_open_strip_torsion_constant,
    thin_open_strip_torsional_stress,
    thin_open_strip_twist_angle,
    torque_from_power,
    triangular_bar_torsional_stress,
    triangular_bar_twist_angle,
)
from .ventilation import (
    air_changes_per_hour,
    breathing_zone_outdoor_airflow,
    dilution_airflow,
)
from .vortex_shedding import (
    lock_in_velocity,
    reduced_velocity,
    vortex_shedding_frequency,
)
from .wear import (
    archard_wear_depth,
    archard_wear_volume,
    sliding_contact_pv,
    sliding_distance_for_wear_depth,
)
from .weld import (
    FILLET_THROAT_FACTOR,
    eccentric_weld_group_peak_stress,
    fillet_weld_design_strength,
    fillet_weld_directional_strength,
    fillet_weld_leg_for_load,
    fillet_weld_throat_stress,
    weld_base_metal_shear_strength,
)
from .winch import (
    drum_line_pull,
    drum_rope_capacity,
    drum_working_radius,
)
from .wind_power import (
    BETZ_LIMIT,
    wind_power_density,
    wind_turbine_power,
)
from .wire_rope import (
    minimum_sheave_diameter_for_bending_stress,
    wire_rope_bending_stress,
    wire_rope_equivalent_bending_load,
    wire_rope_sheave_pressure,
)
from .worm import (
    worm_gear_efficiency,
    worm_gear_ratio,
    worm_is_self_locking,
    worm_lead_angle,
    worm_output_torque,
    worm_separating_force,
    worm_tangential_force,
)

__all__ = [
    "DEFAULT_POISSON_RATIO",
    "aluminum_buckling_stress",
    "aluminum_tension_stress",
    "rule_of_mixtures_modulus",
    "rule_of_mixtures_strength",
    "transverse_modulus_inverse_rule",
    "composite_major_poisson_ratio",
    "composite_shear_modulus_inverse_rule",
    "composite_longitudinal_cte",
    "critical_fiber_length",
    "tsai_hill_failure_index",
    "off_axis_modulus",
    "bearing_capacity_factors",
    "bearing_depth_factors",
    "bearing_inclination_factors",
    "bearing_shape_factors",
    "consolidation_settlement",
    "consolidation_time",
    "consolidation_time_factor",
    "critical_hydraulic_gradient",
    "darcy_seepage_flow",
    "eccentric_base_pressure",
    "infinite_slope_factor_of_safety",
    "janssen_silo_pressure",
    "piping_factor_of_safety",
    "pile_allowable_capacity",
    "pile_end_bearing_capacity",
    "pile_skin_friction_capacity",
    "rankine_active_pressure_cohesive",
    "rankine_earth_pressure_coefficient",
    "rankine_lateral_thrust",
    "rankine_passive_pressure_cohesive",
    "rankine_sloped_backfill_coefficient",
    "retaining_wall_overturning_factor",
    "retaining_wall_sliding_factor",
    "seepage_velocity",
    "tension_crack_depth",
    "terzaghi_bearing_capacity",
    "vertical_stress_increase_2to1",
    "circular_channel_properties",
    "critical_depth_rectangular",
    "froude_number",
    "hydraulic_jump_downstream_depth",
    "hydraulic_jump_energy_loss",
    "hydraulic_radius",
    "manning_flow_rate",
    "affinity_flow_rate",
    "affinity_head",
    "affinity_power",
    "npsh_available",
    "npsh_margin",
    "pump_hydraulic_power",
    "pump_shaft_power",
    "pump_specific_speed",
    "pump_suction_specific_speed",
    "capacitor_stored_energy",
    "inductor_stored_energy",
    "lc_resonant_frequency",
    "rc_time_constant",
    "rl_time_constant",
    "rc_cutoff_frequency",
    "manning_flow_velocity",
    "broad_crested_weir_flow",
    "minimum_specific_energy_rectangular",
    "rational_method_peak_runoff",
    "rectangular_weir_flow",
    "specific_energy",
    "trapezoidal_channel_properties",
    "triangular_weir_flow",
    "cavitation_number",
    "darcy_friction_factor",
    "darcy_weisbach_head_loss",
    "hazen_williams_flow_capacity",
    "hazen_williams_head_loss",
    "hydraulic_diameter",
    "joukowsky_surge_pressure",
    "minor_loss_head",
    "pipe_pressure_drop",
    "pressure_wave_speed",
    "reynolds_number",
    "surge_wave_period",
    "differential_pressure_for_flow",
    "obstruction_meter_flow_rate",
    "pitot_velocity",
    "buoyant_force",
    "capillary_rise",
    "center_of_pressure_depth",
    "hydrostatic_force_on_plane",
    "hydrostatic_pressure",
    "metacentric_height",
    "righting_moment",
    "stack_effect_pressure",
    "weber_number",
    "adiabatic_compression_power",
    "adiabatic_discharge_temperature",
    "ideal_gas_density",
    "isothermal_compression_power",
    "multistage_compression_power",
    "optimal_stage_pressure_ratio",
    "air_receiver_holdup_time",
    "air_receiver_volume_for_demand",
    "cooling_coil_load",
    "dew_point_temperature",
    "humidity_ratio",
    "sensible_heat_load",
    "latent_heat_load",
    "sensible_heat_ratio",
    "moist_air_enthalpy",
    "relative_humidity",
    "saturation_vapor_pressure",
    "carnot_cop_cooling",
    "carnot_cop_heating",
    "coefficient_of_performance",
    "drag_force",
    "jet_impact_force",
    "stokes_settling_velocity",
    "stokes_drag_force",
    "terminal_velocity",
    "tank_drain_time",
    "torricelli_efflux_velocity",
    "choked_mass_flow_rate",
    "critical_pressure_ratio",
    "isentropic_area_ratio",
    "stagnation_pressure_ratio",
    "stagnation_density_ratio",
    "mach_number",
    "speed_of_sound",
    "stagnation_temperature_ratio",
    "apparent_power_three_phase",
    "conductor_resistance",
    "line_current_for_power",
    "power_factor_correction_kvar",
    "skin_depth",
    "three_phase_power",
    "transformer_full_load_current",
    "transformer_available_fault_current",
    "ground_rod_resistance",
    "parallel_ground_electrodes_resistance",
    "voltage_drop_three_phase",
    "battery_bank_capacity",
    "usable_battery_energy",
    "battery_backup_time",
    "pv_array_power",
    "pv_daily_energy",
    "pv_array_size_for_load",
    "accumulator_size_for_volume",
    "accumulator_usable_volume",
    "inverse_square_attenuation",
    "mass_law_transmission_loss",
    "noise_dose_fraction",
    "permissible_exposure_time",
    "sabine_reverberation_time",
    "sound_level_sum",
    "sound_power_level_from_intensity",
    "sound_pressure_from_power_level",
    "masonry_allowable_axial_stress",
    "masonry_allowable_flexural_stress",
    "masonry_column_axial_capacity",
    "masonry_combined_stress_ratio",
    "lap_joint_average_shear_stress",
    "cylindrical_bond_axial_capacity",
    "cylindrical_bond_torque_capacity",
    "CompactnessClass",
    "classify_flexural_element",
    "flexural_flange_slenderness_limits",
    "flexural_web_slenderness_limits",
    "axial_stress",
    "axial_elongation",
    "axial_stiffness",
    "circular_area",
    "required_axial_area",
    "ball_screw_drive_torque",
    "ball_screw_back_drive_torque",
    "BeamBendingResult",
    "cantilever_center_patch_load",
    "cantilever_end_load",
    "cantilever_end_moment",
    "cantilever_offset_load",
    "cantilever_offset_moment",
    "cantilever_partial_uniform_load",
    "cantilever_triangular_load",
    "cantilever_triangular_load_peak_at_tip",
    "cantilever_uniform_load",
    "simply_supported_center_load",
    "simply_supported_center_patch_load",
    "simply_supported_end_moment",
    "simply_supported_offset_load",
    "simply_supported_offset_moment",
    "simply_supported_partial_uniform_load",
    "simply_supported_symmetric_point_loads",
    "simply_supported_triangular_load",
    "simply_supported_uniform_load",
    "fixed_fixed_center_load",
    "fixed_fixed_center_patch_load",
    "fixed_fixed_offset_load",
    "fixed_fixed_partial_uniform_load",
    "fixed_fixed_triangular_load",
    "fixed_fixed_uniform_load",
    "fixed_pinned_center_load",
    "fixed_pinned_center_patch_load",
    "fixed_pinned_end_moment",
    "fixed_pinned_offset_load",
    "fixed_pinned_partial_uniform_load",
    "fixed_pinned_triangular_load",
    "fixed_pinned_triangular_load_peak_at_prop",
    "fixed_pinned_uniform_load",
    "overhang_tip_load",
    "overhang_uniform_load",
    "rectangular_second_moment",
    "circular_second_moment",
    "hollow_circular_second_moment",
    "rectangular_tube_second_moment",
    "i_section_second_moment",
    "rectangular_plastic_section_modulus",
    "circular_plastic_section_modulus",
    "hollow_circular_plastic_section_modulus",
    "rectangular_tube_plastic_section_modulus",
    "i_section_plastic_section_modulus",
    "plastic_moment",
    "simply_supported_plastic_collapse_load",
    "fixed_fixed_plastic_collapse_load",
    "simply_supported_center_load_support_slope",
    "simply_supported_uniform_load_support_slope",
    "cantilever_end_load_tip_slope",
    "cantilever_uniform_load_tip_slope",
    "simply_supported_plastic_collapse_udl",
    "fixed_fixed_plastic_collapse_udl",
    "propped_cantilever_plastic_collapse_load",
    "propped_cantilever_plastic_collapse_udl",
    "CrossSection",
    "bending_stress",
    "required_section_modulus",
    "CompositeBeamStresses",
    "composite_beam_bending_stresses",
    "channel_shear_center",
    "warping_constant_doubly_symmetric",
    "CompoundSection",
    "compound_section_properties",
    "compound_plastic_section_modulus",
    "neutral_axis_radius",
    "bend_allowance",
    "outside_setback",
    "bend_deduction",
    "flat_pattern_length",
    "minimum_bend_radius",
    "air_bending_force",
    "shear_cutting_force",
    "round_hole_punching_force",
    "stripping_force",
    "cup_blank_diameter",
    "draw_ratio",
    "deep_draw_force",
    "RivetedJointStrength",
    "riveted_joint_efficiency",
    "minimum_curve_radius",
    "ideal_superelevation_rate",
    "banked_curve_max_speed",
    "rc_stress_block_depth",
    "rc_beam_nominal_moment",
    "rc_doubly_reinforced_moment",
    "rc_t_beam_moment",
    "rc_tension_steel_for_moment",
    "rc_concrete_shear_strength",
    "rc_shear_reinforcement_strength",
    "rc_stirrup_spacing_for_shear",
    "rc_column_axial_strength",
    "rc_column_balanced_point",
    "rc_beta1",
    "rc_net_tensile_strain",
    "rc_strength_reduction_factor",
    "rc_development_length",
    "rc_max_bar_spacing_crack_control",
    "rc_minimum_flexural_steel",
    "rc_maximum_tension_controlled_steel",
    "rc_two_way_shear_strength",
    "rc_cracking_moment",
    "rc_effective_moment_of_inertia",
    "sling_tension_factor",
    "sling_leg_tension",
    "sling_horizontal_force",
    "tackle_mechanical_advantage",
    "tackle_lead_line_tension",
    "reflected_load_inertia",
    "reflected_inertia_ratio",
    "motor_acceleration_torque",
    "inertia_matching_gear_ratio",
    "rms_torque_over_cycle",
    "trapezoidal_move_peak_velocity",
    "trapezoidal_move_acceleration",
    "max_transverse_shear_stress",
    "aisc_bearing_length_for_web_yielding",
    "aisc_round_hss_flexural_strength",
    "aisc_minor_axis_flexural_strength",
    "aisc_plate_girder_bending_factor",
    "aisc_plate_girder_flange_stress",
    "aisc_tension_field_shear_strength",
    "aisc_rectangular_hss_flexural_strength",
    "aisc_rectangular_hss_shear_strength",
    "aisc_round_hss_shear_strength",
    "aisc_web_compression_buckling_strength",
    "aisc_web_crippling_strength",
    "aisc_web_local_yielding_strength",
    "aisc_web_shear_strength",
    "two_span_continuous_middle_moment",
    "two_span_continuous_interior_reaction",
    "shear_flow",
    "fastener_spacing_for_shear_flow",
    "deflection_scorecard",
    "span_deflection_limit",
    "SHEAR_FORM_RECTANGULAR",
    "SHEAR_FORM_CIRCULAR",
    "foundation_characteristic_parameter",
    "beam_on_elastic_foundation_max_deflection",
    "beam_on_elastic_foundation_max_moment",
    "BALL_BEARING_LIFE_EXPONENT",
    "BEARING_WEIBULL_SLOPE",
    "ROLLER_BEARING_LIFE_EXPONENT",
    "bearing_basic_rating_life",
    "bearing_rating_for_life",
    "bearing_life_hours",
    "bearing_static_safety_factor",
    "bearing_equivalent_dynamic_load",
    "bearing_equivalent_static_load",
    "bearing_reliability_life_factor",
    "capstan_tension_ratio",
    "belt_slack_tension",
    "belt_max_transmissible_force",
    "belt_centrifugal_tension",
    "belt_max_transmissible_force_at_speed",
    "belt_speed_for_max_power",
    "vee_belt_effective_friction",
    "belt_length",
    "belt_wrap_angle",
    "crossed_belt_length",
    "crossed_belt_wrap_angle",
    "belt_transmitted_power",
    "belt_tight_tension_for_power",
    "belt_mean_tension",
    "chain_length_in_pitches",
    "chordal_speed_variation",
    "minimum_sprocket_teeth_for_chordal_variation",
    "chain_speed",
    "chain_working_tension",
    "CamMotion",
    "cam_follower_motion",
    "cam_pressure_angle",
    "cam_base_circle_for_pressure_angle",
    "parabolic_cable_sag",
    "parabolic_cable_max_tension",
    "parabolic_cable_length",
    "catenary_sag",
    "catenary_arc_length",
    "catenary_max_tension",
    "geneva_index_angle",
    "geneva_crank_radius",
    "geneva_driven_radius",
    "geneva_advance_fraction",
    "geneva_dwell_fraction",
    "circular_equivalent_diameter",
    "fan_power",
    "cylinder_extend_force",
    "cylinder_retract_force",
    "cylinder_extend_speed",
    "cylinder_retract_speed",
    "cylinder_regen_extend_force",
    "cylinder_regen_extend_speed",
    "cylinder_rodside_intensified_pressure",
    "slider_crank_displacement",
    "slider_crank_velocity",
    "slider_crank_acceleration",
    "slider_crank_piston_side_thrust",
    "slider_crank_torque",
    "snap_fit_permissible_deflection",
    "snap_fit_strain",
    "snap_fit_deflection_force",
    "snap_fit_mating_force",
    "scotch_yoke_displacement",
    "scotch_yoke_velocity",
    "scotch_yoke_acceleration",
    "is_grashof",
    "fourbar_type",
    "fourbar_transmission_angle",
    "band_brake_torque",
    "band_brake_tight_tension_for_torque",
    "band_brake_max_lining_pressure",
    "differential_band_brake_actuation_force",
    "differential_band_brake_is_self_locking",
    "short_shoe_normal_force",
    "short_shoe_brake_torque",
    "short_shoe_is_self_locking",
    "CurvedBeamStress",
    "rectangular_curved_beam_stress",
    "trapezoidal_curved_beam_stress",
    "circular_curved_beam_stress",
    "composite_curved_beam_stress",
    "thin_ring_diametral_deflection",
    "thin_ring_max_moment",
    "thin_ring_buckling_pressure",
    "ColumnEnd",
    "euler_buckling_load",
    "euler_second_moment_for_load",
    "radius_of_gyration",
    "slenderness_ratio",
    "euler_critical_stress",
    "aisc_flexural_buckling_stress",
    "aisc_plastic_bracing_limit",
    "aisc_beam_column_interaction",
    "aisc_effective_length_factor_braced",
    "aisc_effective_length_factor_sway",
    "aisc_moment_amplifier_b1",
    "aisc_moment_amplifier_b2",
    "aisc_effective_radius_of_gyration",
    "aisc_elastic_ltb_stress",
    "aisc_inelastic_ltb_limit",
    "aisc_inelastic_ltb_moment",
    "aisc_flange_local_buckling_moment",
    "aisc_slender_flange_moment",
    "transition_slenderness",
    "stoichiometric_air_fuel_ratio",
    "excess_air_from_flue_oxygen",
    "actual_air_fuel_ratio",
    "johnson_critical_stress",
    "secant_column_max_stress",
    "perry_robertson_stress",
    "lateral_torsional_buckling_moment",
    "rankine_gordon_stress",
    "UNIFORM_WEAR",
    "UNIFORM_PRESSURE",
    "disc_clutch_torque",
    "disc_clutch_force_for_torque",
    "cone_clutch_torque",
    "clutch_engagement_energy",
    "brake_absorbed_energy",
    "STANDARD_GRAVITY",
    "natural_frequency",
    "natural_frequency_from_deflection",
    "cantilever_tip_mass_frequency",
    "simply_supported_center_mass_frequency",
    "fixed_fixed_center_mass_frequency",
    "string_natural_frequency",
    "damped_natural_frequency",
    "logarithmic_decrement",
    "quality_factor",
    "critical_damping_coefficient",
    "transmissibility",
    "isolation_scorecard",
    "isolator_natural_frequency_for_transmissibility",
    "isolator_static_deflection_for_transmissibility",
    "dynamic_magnification_factor",
    "resonance_phase_angle",
    "base_excitation_relative_transmissibility",
    "simple_pendulum_period",
    "physical_pendulum_period",
    "tuned_mass_damper_optimal_frequency_ratio",
    "tuned_mass_damper_optimal_damping",
    "dunkerley_fundamental_frequency",
    "cantilever_fundamental_frequency",
    "simply_supported_fundamental_frequency",
    "fixed_fixed_fundamental_frequency",
    "fixed_pinned_fundamental_frequency",
    "simply_supported_plate_fundamental_frequency",
    "clamped_plate_fundamental_frequency",
    "simply_supported_circular_plate_fundamental_frequency",
    "clamped_circular_plate_fundamental_frequency",
    "simply_supported_annular_plate_fundamental_frequency",
    "clamped_annular_plate_fundamental_frequency",
    "torsional_natural_frequency",
    "two_rotor_torsional_natural_frequency",
    "solid_disc_polar_mass_moment",
    "annular_disc_polar_mass_moment",
    "frequency_scorecard",
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "bearing_stress",
    "bolt_shear_stress",
    "bolt_diameter_for_shear",
    "bolt_tensile_stress_area",
    "bolt_axial_stress",
    "bolt_proof_load",
    "recommended_bolt_preload",
    "thread_stripping_shear_area",
    "thread_stripping_stress",
    "thread_engagement_for_load",
    "bolt_axial_stiffness",
    "bolt_bearing_strength",
    "bolt_shear_strength",
    "member_stiffness_frustum",
    "joint_stiffness_factor",
    "bolt_load_in_joint",
    "member_clamp_load_in_joint",
    "joint_separation_load",
    "preloaded_bolt_cyclic_stress",
    "eccentric_shear_group_peak_force",
    "slip_critical_resistance",
    "block_shear_strength",
    "aisc_tension_member_design_strength",
    "shear_lag_factor",
    "net_width_staggered_holes",
    "goodman_safety_factor",
    "goodman_scorecard",
    "smith_watson_topper_stress",
    "goodman_equivalent_reversed_stress",
    "morrow_equivalent_reversed_stress",
    "soderberg_safety_factor",
    "soderberg_scorecard",
    "gerber_safety_factor",
    "gerber_scorecard",
    "miner_cumulative_damage",
    "miner_spectrum_repeats_to_failure",
    "basquin_cycles_to_failure",
    "basquin_stress_for_life",
    "coffin_manson_reversals",
    "strain_life_total_amplitude",
    "weld_constant_amplitude_fatigue_limit",
    "weld_cutoff_limit",
    "weld_detail_endurance_cycles",
    "weld_detail_allowable_stress_range",
    "weld_size_effect_factor",
    "weld_size_corrected_detail_category",
    "weld_fatigue_scorecard",
    "CyclicStress",
    "cyclic_stress_components",
    "estimated_endurance_limit",
    "marin_endurance_limit",
    "fatigue_notch_factor",
    "neuber_notch_sensitivity",
    "peterson_notch_sensitivity",
    "coefficient_of_fluctuation",
    "flywheel_energy_fluctuation",
    "flywheel_inertia_for_fluctuation",
    "rim_flywheel_mass",
    "rotating_rim_hoop_stress",
    "rotating_rim_burst_speed",
    "rotating_rim_radial_growth",
    "rotating_solid_disc_max_stress",
    "rotating_solid_disc_radial_stress",
    "rotating_solid_disc_tangential_stress",
    "rotating_annular_disc_bore_stress",
    "rotating_annular_disc_radial_stress",
    "rotating_annular_disc_tangential_stress",
    "point_source_illuminance",
    "lumen_method_illuminance",
    "lumen_method_luminaire_count",
    "lighting_power_density",
    "SUDDENLY_APPLIED_FACTOR",
    "impact_factor",
    "impact_stress",
    "horizontal_impact_force",
    "gear_tangential_load",
    "gear_radial_load",
    "gear_normal_load",
    "bevel_pitch_cone_angle",
    "bevel_gear_radial_load",
    "bevel_gear_axial_load",
    "helical_gear_axial_thrust",
    "helical_gear_radial_load",
    "helical_virtual_teeth",
    "pitch_line_velocity",
    "barth_velocity_factor",
    "lewis_bending_stress",
    "lewis_module_for_bending_stress",
    "agma_bending_stress",
    "agma_contact_stress",
    "agma_module_for_bending_stress",
    "gear_contact_stress",
    "spur_gear_contact_ratio",
    "minimum_teeth_to_avoid_undercut",
    "involute_function",
    "involute_angle",
    "base_tangent_length",
    "gear_tooth_thickness_at_radius",
    "gear_pitch_diameter",
    "gear_outside_diameter",
    "gear_root_diameter",
    "gear_center_distance",
    "gear_module_for_center_distance",
    "operating_pressure_angle",
    "profile_shift_sum_for_center_distance",
    "gear_train_value",
    "gear_train_efficiency",
    "reverted_train_is_coaxial",
    "planetary_planet_teeth",
    "planetary_can_assemble",
    "planetary_speed",
    "PlanetaryTorques",
    "planetary_torques",
    "key_tangential_force",
    "key_shear_stress",
    "key_bearing_stress",
    "KeyLengthRequirement",
    "key_length_for_torque",
    "spline_torque_capacity",
    "living_hinge_fold_strain",
    "living_hinge_web_length_for_strain",
    "LoadDuration",
    "nds_load_duration_factor",
    "nds_adjusted_design_value",
    "nds_bending_scorecard",
    "nds_euler_buckling_stress",
    "nds_column_stability_factor",
    "nds_combined_bending_compression",
    "nds_shear_stress",
    "nds_shear_scorecard",
    "nds_bearing_area_factor",
    "o_ring_squeeze_fraction",
    "o_ring_gland_fill_fraction",
    "o_ring_stretch_fraction",
    "polar_second_moment_solid",
    "polar_second_moment_hollow",
    "shaft_torsional_stress",
    "shaft_von_mises_stress",
    "shaft_diameter_for_torque",
    "shaft_diameter_for_bending_torsion",
    "shaft_diameter_de_goodman",
    "shaft_diameter_de_gerber",
    "hollow_shaft_diameter_for_bending_torsion",
    "hollow_shaft_torsional_stress",
    "torque_from_power",
    "shaft_twist_angle",
    "hollow_shaft_twist_angle",
    "shaft_torsional_stiffness",
    "rectangular_tube_enclosed_area",
    "rectangular_tube_torsional_stress",
    "rectangular_tube_twist_angle",
    "thin_open_strip_torsion_constant",
    "open_section_torsion_constant",
    "thin_open_strip_torsional_stress",
    "thin_open_strip_twist_angle",
    "rectangular_bar_torsion_constant",
    "rectangular_bar_torsional_stress",
    "rectangular_bar_twist_angle",
    "elliptical_bar_torsional_stress",
    "elliptical_bar_twist_angle",
    "triangular_bar_torsional_stress",
    "triangular_bar_twist_angle",
    "thin_closed_tube_torsional_stress",
    "PlateBendingResult",
    "simply_supported_plate_uniform_load",
    "simply_supported_plate_center_patch_load",
    "clamped_plate_uniform_load",
    "simply_supported_circular_plate_uniform_load",
    "clamped_circular_plate_uniform_load",
    "simply_supported_circular_plate_center_load_deflection",
    "clamped_circular_plate_center_load_deflection",
    "simply_supported_annular_plate_uniform_load",
    "clamped_annular_plate_uniform_load",
    "clamped_circular_plate_thickness_for_pressure",
    "base_plate_thickness_for_bearing",
    "plate_buckling_stress",
    "plate_shear_buckling_coefficient",
    "plate_compression_buckling_coefficient",
    "otto_cycle_efficiency",
    "diesel_cycle_efficiency",
    "brayton_cycle_efficiency",
    "lead_angle",
    "power_screw_raise_torque",
    "power_screw_raise_load",
    "power_screw_lower_torque",
    "power_screw_efficiency",
    "power_screw_is_self_locking",
    "power_screw_collar_torque",
    "prestress_balanced_load",
    "prestress_bottom_fiber_stress",
    "prestress_cracking_moment",
    "worm_gear_ratio",
    "worm_lead_angle",
    "worm_gear_efficiency",
    "worm_output_torque",
    "worm_is_self_locking",
    "worm_tangential_force",
    "worm_separating_force",
    "ThinWallStress",
    "ThickWallStress",
    "ThickWallSphereStress",
    "thin_wall_cylinder",
    "thin_wall_cylinder_diametral_growth",
    "thin_wall_thickness_for_pressure",
    "asme_cylinder_thickness",
    "asme_ellipsoidal_head_thickness",
    "asme_torispherical_head_thickness",
    "asme_ellipsoidal_head_mawp",
    "asme_torispherical_head_mawp",
    "asme_spherical_shell_thickness",
    "asme_spherical_shell_mawp",
    "asme_conical_head_thickness",
    "asme_conical_head_mawp",
    "asme_cylinder_mawp",
    "asme_b313_pipe_wall_thickness",
    "asme_b313_pipe_pressure",
    "asme_b313_minimum_ordered_wall",
    "asme_b313_branch_required_reinforcement_area",
    "asme_b313_allowable_displacement_stress_range",
    "asme_b313_bend_stress_intensification",
    "asme_b313_displacement_stress",
    "thick_wall_cylinder",
    "thin_wall_sphere_stress",
    "thin_wall_sphere_diametral_growth",
    "thick_wall_sphere",
    "cylinder_external_pressure_buckling",
    "sphere_external_pressure_buckling",
    "cylinder_axial_buckling_stress",
    "InterferenceFit",
    "interference_fit",
    "interference_for_contact_pressure",
    "interference_axial_capacity",
    "interference_torque_capacity",
    "petroff_friction_torque",
    "petroff_friction_power",
    "journal_bearing_unit_load",
    "sommerfeld_number",
    "journal_bearing_minimum_film_thickness",
    "specific_film_ratio",
    "hertz_effective_modulus",
    "aisi_plate_slenderness",
    "aisi_effective_width",
    "HertzContact",
    "hertz_sphere_contact",
    "hertz_sphere_approach",
    "HertzLineContact",
    "hertz_cylinder_contact",
    "flange_coupling_torque",
    "flange_coupling_bolt_force",
    "flange_coupling_bolt_count",
    "corrosion_penetration_rate",
    "faraday_corrosion_rate",
    "remaining_wall_life",
    "LARSON_MILLER_CONSTANT",
    "larson_miller_parameter",
    "larson_miller_rupture_life",
    "larson_miller_temperature_limit",
    "creep_life_fraction_damage",
    "spring_index",
    "wahl_factor",
    "spring_shear_stress",
    "helical_spring_rate",
    "helical_spring_active_coils_for_rate",
    "helical_spring_solid_length",
    "SPRING_END_PARALLEL_PLATES",
    "SPRING_END_FIXED_HINGED",
    "SPRING_END_HINGED_HINGED",
    "SPRING_END_CLAMPED_FREE",
    "SpringBucklingResult",
    "helical_spring_buckling",
    "spring_stored_energy",
    "springs_in_series",
    "springs_in_parallel",
    "BELLEVILLE_PLATEAU_RATIO",
    "belleville_washer_force",
    "belleville_flat_load",
    "spiral_spring_rate",
    "spiral_spring_stress",
    "helical_torsion_spring_rate",
    "helical_torsion_spring_stress",
    "leaf_spring_stress",
    "leaf_spring_rate",
    "spring_surge_frequency",
    "rotating_unbalance_force",
    "balance_correction_mass",
    "balance_quality_permissible_eccentricity",
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "von_mises_principal",
    "octahedral_shear_stress",
    "principal_stresses_plane",
    "principal_angle_plane",
    "max_shear_stress_plane",
    "plane_stress_at_angle",
    "principal_stresses_3d",
    "tresca_equivalent_stress",
    "tresca_principal",
    "yield_safety_factor",
    "strength_scorecard",
    "CombinedNormalStress",
    "combine_axial_bending",
    "concentrated_stress",
    "elliptical_hole_stress_concentration",
    "stress_intensity_factor",
    "critical_crack_length",
    "paris_law_crack_growth_rate",
    "paris_law_cycles_to_failure",
    "crack_tip_plastic_zone_size",
    "plane_strain_thickness_requirement",
    "gasket_seating_load",
    "gasket_operating_load",
    "governing_gasket_bolt_load",
    "confined_liquid_thermal_pressure",
    "constrained_thermal_stress",
    "thermal_shock_stress",
    "thermal_shock_temperature_limit",
    "triaxial_constrained_thermal_stress",
    "through_wall_gradient_thermal_stress",
    "thermal_buckling_temperature_rise",
    "free_thermal_expansion",
    "guided_cantilever_leg_length",
    "shrink_fit_assembly_temperature",
    "DifferentialThermalStress",
    "differential_thermal_stress",
    "bimetallic_strip_curvature",
    "bimetallic_strip_tip_deflection",
    "conduction_thermal_resistance",
    "cylindrical_conduction_resistance",
    "critical_insulation_radius",
    "convection_thermal_resistance",
    "degree_day_heating_energy",
    "degree_day_cooling_energy",
    "series_thermal_resistance",
    "parallel_thermal_resistance",
    "temperature_rise",
    "fin_efficiency",
    "junction_temperature_scorecard",
    "dittus_boelter_convection_coefficient",
    "laminar_tube_convection_coefficient",
    "flat_plate_forced_convection_coefficient",
    "flat_plate_turbulent_convection_coefficient",
    "grashof_number",
    "rayleigh_number",
    "vertical_plate_natural_convection_coefficient",
    "horizontal_cylinder_natural_convection_coefficient",
    "horizontal_plate_natural_convection_coefficient",
    "circular_source_spreading_resistance",
    "fin_array_count_for_resistance",
    "log_mean_temperature_difference",
    "heat_exchanger_area_for_duty",
    "heat_exchanger_duty",
    "heat_exchanger_ntu",
    "counterflow_effectiveness",
    "parallel_flow_effectiveness",
    "crossflow_both_unmixed_effectiveness",
    "counterflow_ntu_for_effectiveness",
    "parallel_flow_ntu_for_effectiveness",
    "biot_number",
    "fourier_number",
    "lumped_capacitance_time_constant",
    "lumped_capacitance_cooling_time",
    "semi_infinite_solid_temperature_rise",
    "semi_infinite_solid_surface_flux",
    "radiation_heat_transfer",
    "radiation_heat_transfer_coefficient",
    "wien_peak_wavelength",
    "wien_temperature_from_peak",
    "archard_wear_volume",
    "archard_wear_depth",
    "sliding_distance_for_wear_depth",
    "sliding_contact_pv",
    "breathing_zone_outdoor_airflow",
    "air_changes_per_hour",
    "dilution_airflow",
    "vortex_shedding_frequency",
    "lock_in_velocity",
    "reduced_velocity",
    "FILLET_THROAT_FACTOR",
    "fillet_weld_throat_stress",
    "fillet_weld_leg_for_load",
    "fillet_weld_design_strength",
    "fillet_weld_directional_strength",
    "weld_base_metal_shear_strength",
    "eccentric_weld_group_peak_stress",
    "wire_rope_bending_stress",
    "minimum_sheave_diameter_for_bending_stress",
    "wire_rope_equivalent_bending_load",
    "wire_rope_sheave_pressure",
    "drum_working_radius",
    "drum_line_pull",
    "drum_rope_capacity",
    "BETZ_LIMIT",
    "wind_power_density",
    "wind_turbine_power",
]
