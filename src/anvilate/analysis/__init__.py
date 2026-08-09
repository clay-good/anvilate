"""Anvilate T1 analytical checks: closed-form, deterministic, no solver.

The T1 validation tier screens a design with handbook closed-form solutions
(Roark, Shigley) before any FEA — fast, deterministic, and unit-checked. The
modules:

- :mod:`~anvilate.analysis.accumulator` — gas-charged hydraulic accumulators: the usable
  fluid volume delivered between two pressures, and its inverse (the size a duty needs)
- :mod:`~anvilate.analysis.acoustics` — machinery-noise arithmetic (for plant/industrial
  work): the decibel sum of several sources and the inverse-square distance attenuation;
  plus acoustic resonance — the Helmholtz resonator f = (c/2π)·√(A/(V·L)) and the open-
  (n·c/2L) and closed-pipe ((2n−1)·c/4L) resonant modes; and moving-source acoustics — the
  Doppler-shifted frequency f' = f·(c + v_o)/(c − v_s), the source speed a shift implies, and
  the Mach cone half-angle μ = arcsin(1/M) of a supersonic source
- :mod:`~anvilate.analysis.adhesive` — bonded joints: the lap-joint average shear
  stress against the datasheet lap-shear strength, and the axial and torque
  capacity of a cylindrical retaining-compound bond
- :mod:`~anvilate.analysis.antenna` — free-space RF link (Friis) and aperture antennas: the
  free-space path loss (4π·d/λ)², the received power P_t·G_t·G_r·(λ/4π·d)², the maximum
  line-of-sight range, plus the aperture gain η·4π·A/λ², the beamwidth ≈70·λ/D, and the dish
  diameter a target gain needs (gains as linear ratios, not dBi)
- :mod:`~anvilate.analysis.channel_capacity` — information-theory link capacity: the Shannon-Hartley
  limit C = B·log2(1+SNR), the bandwidth a target capacity needs B = C/log2(1+SNR), and the
  noiseless Nyquist M-level capacity 2·B·log2(M) (bits per second)
- :mod:`~anvilate.analysis.data_converter` — ADC quantization: the ideal SNR = 6.02·N + 1.76 dB
  ("6 dB per bit"), the quantization step LSB = V_FS/2^N, and the effective number of bits
  ENOB = (SNR−1.76)/6.02 a measured SNR implies
- :mod:`~anvilate.analysis.chemical_equilibrium` — reaction thermodynamics: the Gibbs free energy
  ΔG = ΔH − T·ΔS (spontaneity), the equilibrium constant K = exp(−ΔG/RT), and the van 't Hoff shift
  K₂/K₁ = exp(−(ΔH/R)(1/T₂−1/T₁)) of K with temperature
- :mod:`~anvilate.analysis.circular_motion` — uniform circular motion: the centripetal acceleration
  v²/r, the centripetal force m·v²/r, and the maximum no-slip cornering speed √(µ·g·r) on a flat
  curve
- :mod:`~anvilate.analysis.noise_figure` — RF receiver noise: the linear noise factor from a dB
  figure, the Friis cascade F = F1 + (F2−1)/G1 + … (why the first stage dominates), and the
  equivalent noise temperature T_e = (F−1)·T0
- :mod:`~anvilate.analysis.transmission_line` — RF impedance matching: the reflection coefficient
  Γ = (Z_L−Z_0)/(Z_L+Z_0), the voltage standing-wave ratio (1+|Γ|)/(1−|Γ|), and the return loss
  −20·log10|Γ| — how well a load is matched to a line
- :mod:`~anvilate.analysis.wave` — the universal wave relation v = f·λ solved each way: the wave
  speed f·λ, the wavelength v/f a frequency produces, and the frequency v/λ a wavelength gives
- :mod:`~anvilate.analysis.waveguide` — rectangular-waveguide dispersion (TE10): the cutoff
  f_c = c/(2a), the guide wavelength λ_g = (c/f)/√(1−(f_c/f)²), and the phase velocity
  v_p = c/√(1−(f_c/f)²) (which exceeds c) above cutoff
- :mod:`~anvilate.analysis.plasma` — plasma physics: the electron plasma frequency f_p (the radio
  cutoff of the ionosphere), the Debye screening length λ_D = √(ε₀·k·T/(n·e²)), and the plasma
  parameter N_D (particles in a Debye sphere; ≫1 for a true collective plasma)
- :mod:`~anvilate.analysis.cyclotron` — charged-particle motion in a magnetic field: the cyclotron
  frequency f_c = q·B/(2π·m) (speed-independent), the Larmor orbit radius r = m·v/(q·B), and the
  mass-spectrometry inverse m = q·B/(2π·f_c)
- :mod:`~anvilate.analysis.arrhenius` — thermally-activated reaction rates: the rate constant
  k = A·e^(−Ea/RT), the acceleration factor k2/k1 = e^((Ea/R)(1/T1−1/T2)) between two temperatures
  (accelerated life testing), and the activation energy Ea extracted from two measured rates
- :mod:`~anvilate.analysis.atmosphere` — barometric (isothermal-atmosphere) law: the pressure
  p = p0·exp(−h/H) that decays exponentially with altitude, the scale height H = R·T/(M·g)
  (~8.4 km for air), and the altimeter inverse h = H·ln(p0/p) recovering altitude from pressure
- :mod:`~anvilate.analysis.atomic_spectra` — hydrogen-like Bohr model: the energy level
  E_n = −13.606·Z²/n² eV, the orbit radius r_n = n²·a₀/Z, and the Rydberg transition wavelength
  1/λ = R·Z²·(1/n₁²−1/n₂²) (hydrogen's 656 nm Balmer line)
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
- :mod:`~anvilate.analysis.work_energy` — classical work-energy basics: the kinetic energy
  ½·m·v², the gravitational potential energy m·g·h, and the work W = F·d a constant force does
  (the low-speed, energy-method companion to relativity and impact)
- :mod:`~anvilate.analysis.momentum` — classical momentum-impulse basics: the linear momentum
  p = m·v, the impulse J = F·Δt (= Δp), and the average collision force m·Δv/Δt behind crumple
  zones and airbags
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
  breathing-zone outdoor air, air changes per hour and the airflow a target rate
  needs, and contaminant dilution airflow
- :mod:`~anvilate.analysis.vortex_shedding` — flow-induced vibration: the Strouhal
  shedding frequency f_s = St·V/D, the lock-in velocity that resonates a structure,
  and the reduced velocity that screens the risk
- :mod:`~anvilate.analysis.wear` — Archard sliding-wear law: the worn volume and wear
  depth of a sliding contact, the sliding distance (wear life) a depth limit allows, and
  the plain-bearing PV (pressure × velocity) factor against its overheating limit
- :mod:`~anvilate.analysis.corrosion` — electrochemical metal loss: the ASTM G1
  weight-loss penetration rate, the Faraday rate from a corrosion current density,
  and the remaining wall life above a retirement thickness
- :mod:`~anvilate.analysis.nernst` — Nernst electrochemistry: the cell potential
  E = E0 − (RT/nF)·ln Q away from standard conditions, the ~59 mV/decade Nernst slope
  2.303·RT/(nF) of a potentiometric sensor, and the reaction quotient a measured potential implies
- :mod:`~anvilate.analysis.colligative` — colligative properties (particle-count only): the osmotic
  pressure π = i·c·R·T (reverse-osmosis floor), the freezing-point depression ΔTf = i·Kf·b (road
  salt, antifreeze), and the boiling-point elevation ΔTb = i·Kb·b
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
- :mod:`~anvilate.analysis.calorimetry` — sensible and latent heat: the sensible heat Q = m·c·ΔT to
  change a temperature, the latent heat Q = m·L of a phase change, and the mixing equilibrium
  temperature (m₁c₁T₁ + m₂c₂T₂)/(m₁c₁ + m₂c₂) two bodies settle at
- :mod:`~anvilate.analysis.cam` — cam-follower rise kinematics (SHM, cycloidal,
  parabolic, and 3-4-5 polynomial profiles): follower displacement, velocity, and
  acceleration at a cam angle, the translating roller-follower pressure angle, and
  the minimum base circle a maximum pressure angle allows
- :mod:`~anvilate.analysis.capillary_flow` — capillary imbibition (Washburn): the Young-Laplace
  suction Δp = 2σ·cosθ/r, the wicking penetration L = √(σ·r·cosθ·t/(2μ)) that grows as √t, and the
  time t = 2μL²/(σ·r·cosθ) to reach a distance (the dynamic partner to static capillary rise)
- :mod:`~anvilate.analysis.geneva` — external Geneva (intermittent-indexing)
  mechanism geometry: index angle, crank and driven engagement radii, and the
  advance/dwell fraction of the cycle
- :mod:`~anvilate.analysis.hydraulic_cylinder` — fluid-cylinder actuator sizing:
  the extend and retract force (bore vs annular area), the extend and retract speed
  from the supply flow, and the rod-side pressure intensification of a blocked stroke
- :mod:`~anvilate.analysis.hydraulic_motor` — rotary positive-displacement pump/motor:
  the pump flow Q = D·N·η_v a displacement delivers, the motor torque T = D·Δp/(2π)·η_m
  a pressure drop produces, and the motor speed N = Q·η_v/D a supply flow drives — the
  rotary complement of hydraulic_cylinder, distinct from the centrifugal pump module
- :mod:`~anvilate.analysis.hydraulic_press` — Pascal hydraulic press (the fluid lever): the
  transmitted pressure F_in/A_in, the multiplied output force F_in·(A_out/A_in), and the input
  stroke s_out·(A_out/A_in) — force gained, stroke paid, work conserved
- :mod:`~anvilate.analysis.pneumatics` — compressed-air systems: the receiver hold-up
  time V·Δp/(Q·p_atm) and the receiver volume a required hold-up needs
- :mod:`~anvilate.analysis.polarization` — light polarization (Malus's law): the transmitted
  intensity I = I₀·cos²θ through an analyzer, the analyzer angle arccos(√(I/I₀)) for a target
  attenuation, and the I₀/2 an ideal polarizer passes of unpolarized light
- :mod:`~anvilate.analysis.compressible_flow` — gas dynamics: the speed of sound √(γRT),
  the Mach number, the stagnation-to-static temperature ratio, the critical pressure
  ratio and choked mass flow that size a relief valve, the isentropic area ratio A/A*
  that sets a converging-diverging nozzle's exit Mach, the normal-shock (Rankine-
  Hugoniot) downstream Mach, pressure jump, and irreversible stagnation-pressure loss,
  and the supersonic-expansion Prandtl-Meyer angle ν(M), the Mach angle asin(1/M), and
  the maximum turning angle ν(∞) an attached expansion fan can negotiate
- :mod:`~anvilate.analysis.gas_compression` — gas compression: the ideal-gas density,
  the isothermal and adiabatic compression power that bracket a compressor's duty, the
  adiabatic discharge temperature that sets intercooling, and the optimal per-stage ratio
  and power of a multi-stage machine
- :mod:`~anvilate.analysis.gas_transport` — temperature-dependent gas transport properties: the
  Sutherland-law dynamic viscosity µ_ref·(T/T_ref)^1.5·(T_ref+S)/(T+S) and thermal conductivity
  that both climb with temperature, and the Prandtl number Pr = µ·c_p/k that feeds the convection
  correlations
- :mod:`~anvilate.analysis.ideal_gas` — the ideal gas law PV = nRT solved for each variable: the
  pressure nRT/V, the volume nRT/P, and the amount PV/(RT) a cylinder holds (moles form, distinct
  from gas_compression's mass-density ρ = PM/RT)
- :mod:`~anvilate.analysis.kinetic_theory` — kinetic theory of gases: the rms molecular speed
  √(3RT/M), the mean molecular speed √(8RT/(πM)), and the mean free path k·T/(√2·π·d²·P)
  between collisions — the molecular picture behind effusion, diffusion, and rarefied flow
- :mod:`~anvilate.analysis.rocket_propulsion` — ideal rocket nozzle and mission: the exhaust
  velocity v_e = √(2γ/(γ−1)·R·T_c·(1 − (p_e/p_c)^((γ−1)/γ))), the thrust
  F = ṁ·v_e + (p_e − p_a)·A_e and specific impulse I_sp = F/(ṁ·g₀), and the Tsiolkovsky
  Δv = I_sp·g₀·ln(m₀/m_f) with the propellant fraction ζ = 1 − exp(−Δv/(I_sp·g₀)) it needs; and
  the performance split — characteristic velocity c* = p_c·A_t/ṁ (chamber), thrust coefficient
  C_F = F/(p_c·A_t) (nozzle), and the thrust F = C_F·p_c·A_t a throat sizes to
- :mod:`~anvilate.analysis.gravitation` — Newtonian gravitation: the force F = G·m₁·m₂/r², the
  surface gravity g = G·M/R², and the standard gravitational parameter μ = G·M that feeds the
  orbital-mechanics relations (turning a body's mass into the motion around it)
- :mod:`~anvilate.analysis.orbital_mechanics` — two-body coasting and transfers: the circular
  orbital speed v = √(μ/r), the Kepler period T = 2π·√(r³/μ), the escape velocity
  v_esc = √(2μ/r) = √2·v_circ, the Hohmann two-burn transfer Δv's and coast time t = π·√(a³/μ),
  and the elliptical vis-viva speed v = √(μ(2/r − 1/a)), specific energy ε = −μ/(2a), and
  semi-major axis a = (r_p + r_a)/2
- :mod:`~anvilate.analysis.combustion` — furnace/boiler combustion: the stoichiometric
  air-fuel ratio from an ultimate analysis, the excess air read from flue-gas oxygen
  (EA = O₂/(20.9−O₂)), the actual air-fuel ratio a burner runs at, the equivalence ratio
  φ = AFR_stoich/AFR_actual = 1/(1+EA) that grades lean/rich, and the Siegert dry flue-gas
  loss and the combustion efficiency it leaves
- :mod:`~anvilate.analysis.power_cycles` — air-standard power-cycle efficiencies: the
  Otto (η = 1 − 1/r^(γ−1)), Diesel (with a cutoff ratio), and Brayton gas-turbine
  (η = 1 − 1/r_p^((γ−1)/γ)) ideal thermal efficiencies, the Carnot ceiling
  η = 1 − T_c/T_h no engine can beat, and the second-law efficiency η/η_Carnot
  that grades a real engine against it
- :mod:`~anvilate.analysis.isentropic_efficiency` — turbomachinery isentropic and polytropic
  efficiency: the compressor η_c = (T₂ₛ − T₁)/(T₂ₐ − T₁) and turbine η_t = (T₁ − T₂ₐ)/(T₁ − T₂ₛ)
  that bridge the reversible ideal to a real stage, the actual discharge temperature
  T₂ₐ = T₁ + (T₂ₛ − T₁)/η_c a real compressor reaches, and the polytropic (small-stage) efficiency
  with its isentropic conversion (η_c < η_p on compression, η_t > η_p on expansion)
- :mod:`~anvilate.analysis.flow_measurement` — differential-pressure flow metering: the
  orifice/venturi/nozzle discharge Q = C_d·A/√(1−β⁴)·√(2Δp/ρ), its pressure-drop sizing
  inverse, the pitot-tube point velocity √(2Δp/ρ), and its forward dynamic pressure ½ρV²
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
  valve-closure time, the cavitation number σ = (p−p_v)/(½·ρ·V²) that screens a
  valve or orifice for cavitation, the laminar Hagen-Poiseuille flow Q = π·ΔP·r⁴/(8·μ·L)
  with its pressure- and radius-sizing inverses (microchannels, capillaries, viscometry), and the
  hydrodynamic (0.05·Re·D) and thermal (0.05·Re·Pr·D) entry lengths — with the ≈10·D turbulent
  estimate — that say where the fully-developed friction and heat-transfer correlations start
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
  work): three-phase real and apparent power, the line current a load draws, the motor
  full-load current (input over efficiency) and its NEC 125% branch-circuit ampacity,
  the motor synchronous speed (120·f/p) and slip, the locked-rotor starting current
  from the NEMA code letter, conductor resistance ρ·L/A, the
  three-phase voltage drop along a feeder, the capacitor kVAR to
  correct a poor power factor, the transformer full-load and available fault current
  (the AIC rating downstream gear must interrupt), the ideal-transformer voltage/current/
  impedance transformation (V_s = V_p/n, I_s = I_p·n, Z_p = n²·Z_s), the transformer efficiency
  and copper/core-loss split with the √(P_fe/P_cu) load of peak efficiency and the voltage
  regulation (V_nl−V_fl)/V_fl, the Dwight earthing
  resistance of a driven ground rod and of rods in parallel, and the AC skin depth √(ρ/(π·f·μ))
- :mod:`~anvilate.analysis.electromagnetic_induction` — Faraday induction: the motional EMF = B·L·v
  of a moving conductor, the Faraday EMF = N·ΔΦ/Δt from a changing flux, and the self-induced
  back-EMF = L·ΔI/Δt that opposes a current change
- :mod:`~anvilate.analysis.reactive_circuit` — reactive components: the energy a
  capacitor (½·C·V²) and an inductor (½·L·I²) store, the RC/RL first-order time
  constants and the RC filter cutoff f_c = 1/(2π·R·C), the LC resonant frequency
  f₀ = 1/(2π·√(L·C)), and the parallel-plate capacitor — capacitance ε₀·ε_r·A/d, charge
  Q = C·V, and plate field E = V/d
- :mod:`~anvilate.analysis.diode` — semiconductor-diode (Shockley) behavior: the thermal voltage
  V_T = k·T/q, the ideal-diode current I = I_s·(e^(V/(n·V_T)) − 1), and the forward voltage at a
  target current V = n·V_T·ln(I/I_s + 1) — the operating point of a rectifier or LED
- :mod:`~anvilate.analysis.pn_junction` — pn-junction electrostatics (abrupt): the built-in
  potential V_bi = (kT/q)·ln(N_A·N_D/n_i²), the depletion width W = √(2ε·V_bi/q·(1/N_A+1/N_D)), and
  the junction capacitance ε/W per area (the varactor's tunable capacitance)
- :mod:`~anvilate.analysis.dc_circuit` — DC resistive basics: Ohm's law V = I·R, the resistive
  (Joule) power P = I²·R a resistor dissipates, and the parallel equivalent R = 1/Σ(1/Rᵢ)
- :mod:`~anvilate.analysis.dc_dc_converter` — switching-regulator transfer functions (ideal, CCM):
  the buck V_out = D·V_in (step-down), the boost V_out = V_in/(1−D) (step-up), and the buck-boost
  V_out = V_in·D/(1−D) (either), all set by the duty cycle D
- :mod:`~anvilate.analysis.thermal_noise` — Johnson-Nyquist thermal noise: the noise voltage
  V = √(4·k·T·R·B), the available noise power k·T·B (the −174 dBm/Hz floor at 290 K), and the noise
  current √(4·k·T·B/R) — the electrical noise floor every amplifier and sensor sits on
- :mod:`~anvilate.analysis.op_amp` — ideal op-amp stages: the non-inverting gain 1 + Rf/Rg, the
  inverting gain −Rf/Rin, and the gain-bandwidth tradeoff f = GBW/|A| that caps a stage's bandwidth
  as its gain rises
- :mod:`~anvilate.analysis.diffusion` — Fickian mass transport: the steady flux J = D·ΔC/L through
  a barrier (Fick's first law), the penetration length x = √(D·t) a diffusion front reaches, and the
  time t = x²/D to diffuse a distance — the mass-transport analog of heat conduction
- :mod:`~anvilate.analysis.diffraction` — wave diffraction: the Bragg reflection angle
  θ = arcsin(n·λ/2d) and its crystal-plane-spacing inverse d = n·λ/(2·sinθ) (X-ray diffraction), and
  the grating diffraction angle θ = arcsin(m·λ/D) that disperses a spectrum
- :mod:`~anvilate.analysis.thin_film` — anti-reflection coatings: the quarter-wave thickness
  t = λ/(4n) that cancels a reflection, the ideal coating index n = √(n_medium·n_substrate), and the
  wavelength λ = 4·n·t a given coating is tuned to
- :mod:`~anvilate.analysis.fresnel` — surface reflection: the normal-incidence reflectance
  R = ((n1−n2)/(n1+n2))² (4% at an air-glass face), the two-surface slab transmittance (1−R)², and
  the Brewster polarizing angle arctan(n2/n1) — the bare reflection AR coatings fight
- :mod:`~anvilate.analysis.friction` — dry (Coulomb) friction: the friction force F = µ·N, the
  angle of repose θ = arctan(µ) a slope or stockpile stands at, and the force W·(sin θ + µ·cos θ)
  to drag a load up an incline
- :mod:`~anvilate.analysis.magnetics` — magnetic actuators and circuits: the solenoid field
  B = μ₀·n·I, the Maxwell magnetic pressure p = B²/(2·μ₀), the electromagnet holding force
  F = B²·A/(2·μ₀), and the magnetic circuit (Hopkinson's law) — MMF = N·I, reluctance
  R = l/(μ·A), and flux Φ = MMF/R
- :mod:`~anvilate.analysis.hall_effect` — Hall-effect sensing: the transverse Hall voltage
  V_H = I·B/(n·q·t) a field induces across a biased sample, the field a Hall sensor reports
  from it (B = V_H·n·q·t/I), and the semiconductor carrier density a Hall measurement reveals
  (n = I·B/(q·t·V_H))
- :mod:`~anvilate.analysis.energy_storage` — battery/UPS backup sizing: the bank
  capacity a load needs (C = P·t/(V·DoD·η)), a bank's usable energy, the runtime
  a given bank delivers, and the round-trip efficiency and the delivered energy
  it yields (E_out = E_stored·η)
- :mod:`~anvilate.analysis.engineering_economics` — time value of money for economic screening: the
  present value F/(1+i)^n of a future amount, the future value P·(1+i)^n of a present one, the
  present and future value of a uniform payment series, the level loan payment (capital recovery),
  the simple payback period C/A, the net present value ΣCFₜ/(1+i)^t of a cash-flow stream, the
  benefit-cost ratio, and straight-line depreciation (C−S)/n
- :mod:`~anvilate.analysis.battery_peukert` — Peukert discharge-rate derating: the runtime at a
  high current t = (C/I_r)·(I_r/I)^k, the capacity actually delivered C·(I_r/I)^(k−1), and the
  Peukert exponent fitted from two discharge tests — the fast-drain penalty energy_storage ignores
- :mod:`~anvilate.analysis.solar_cell` — photovoltaic cell I-V characterization: the fill factor
  FF = (V_mp·I_mp)/(V_oc·I_sc), the maximum power P_max = FF·V_oc·I_sc, and the conversion
  efficiency η = P_max/(G·A) — the cell-level metrics behind the array power of solar_pv
- :mod:`~anvilate.analysis.solar_geometry` — solar position geometry: the declination
  δ = 23.45°·sin(360·(284+n)/365) (Cooper), the solar-noon altitude α = 90° − |φ − δ|, and the
  atmospheric air mass AM = 1/sin(α) (the AM1.5 rating point) — the resource behind solar_pv
- :mod:`~anvilate.analysis.solar_pv` — photovoltaic array sizing: a module's power
  (P = G·A·η), the daily energy an array yields (E = P·PSH·D), the array rating
  a daily load needs, and the cell-temperature (NOCT) and its power derating
  (P = P_stc·[1 + γ·(T_cell − 25)]) — pairs with energy_storage for off-grid design
- :mod:`~anvilate.analysis.solar_thermal` — flat-plate collector performance: the
  instantaneous efficiency η = η₀ − a₁·ΔT/G − a₂·ΔT²/G from the collector test curve,
  the useful heat it delivers (Q = η·G·A), and the no-flow stagnation temperature
  (η → 0) that sets the loop's material and pressure-relief limits
- :mod:`~anvilate.analysis.wind_power` — wind-turbine power: the ½·ρ·V³ power density
  in the wind (cube law), the P = ½·ρ·A·V³·C_p a rotor delivers, the Betz limit
  16/27 ceiling on the power coefficient, the tip speed ratio λ = ω·R/V, and the
  capacity factor CF = E/(P·t)
- :mod:`~anvilate.analysis.wing_aerodynamics` — finite-wing aerodynamics: the lift force
  L = ½·ρ·V²·S·C_L, the induced-drag coefficient C_Di = C_L²/(π·e·AR) that a lifting finite-span
  wing pays, and the stall speed V = √(2·W/(ρ·S·C_L,max)) below which the wing cannot hold weight
- :mod:`~anvilate.analysis.hydro_power` — hydro-turbine power: the net head a
  turbine sees after penstock loss (H_net = H_gross − h_loss), the P = ρ·g·Q·H·η
  a plant delivers (linear in flow and head), and the flow a target output needs
  (Q = P/(ρ·g·H·η)) — completes the renewable set with solar_pv/solar_thermal/wind_power
- :mod:`~anvilate.analysis.drag` — fluid-dynamic forces: the drag force ½·ρ·V²·C_d·A (wind
  load on a sign, current on a member), the terminal (settling) velocity where drag balances
  weight, the jet impact force ρ·Q·V·(1−cos θ) a stream delivers to a surface, and the
  low-Reynolds Stokes settling velocity and drag on a small sphere
- :mod:`~anvilate.analysis.coriolis` — rotating-frame / geophysical effects: the Coriolis
  acceleration a = 2·Ω·v on a moving body, the Coriolis parameter f = 2·Ω·sin(lat) that sets
  geophysical flow, and the Rossby number Ro = U/(f·L) that says whether rotation dominates
- :mod:`~anvilate.analysis.hvac_duct` — air-duct sizing: the ASHRAE circular equivalent
  diameter of a rectangular duct (equal friction), the fan total pressure Pt = Ps + Pv,
  and the fan shaft power P = Q·Δp/η
- :mod:`~anvilate.analysis.refrigeration` — refrigeration and heat-pump cycle performance:
  the Carnot cooling and heating COP ceilings, the actual COP = Q/W, the
  second-law efficiency (COP over Carnot) that grades the machine itself, and the
  vapor-compression cycle from state enthalpies — the refrigeration effect q_L, the compressor
  work w_c, and the refrigerant mass flow ṁ = Q_L/q_L a cooling load circulates
- :mod:`~anvilate.analysis.psychrometrics` — moist-air properties for HVAC and drying: the
  Magnus saturation vapor pressure, the humidity ratio and relative humidity, the dew-point
  temperature, the moist-air enthalpy and cooling-coil load for capacity sizing, the
  sensible/latent split with the sensible heat ratio SHR = Q_s/(Q_s + Q_l), the
  adiabatic mixing of two air streams (mass-weighted temperature and humidity ratio),
  the cooling-coil bypass factor against its apparent dew point, and the direct
  evaporative-cooler saturation effectiveness toward the wet-bulb
- :mod:`~anvilate.analysis.cooling_tower` — cooling-tower performance against the
  wet-bulb floor: the range R = T_hot − T_cold it cools the water, the approach
  A = T_cold − T_wb that measures tower capability, and the effectiveness
  ε = R/(R + A) — the fraction of the available cooling achieved
- :mod:`~anvilate.analysis.conveyor` — belt-conveyor (bulk-material) sizing: the
  mass flow ṁ = ρ·A·v it carries, the belt speed a target throughput needs
  (v = ṁ/(ρ·A)), and the irreducible lift power P = ṁ·g·H to raise the material —
  distinct from the power-transmission belts of :mod:`~anvilate.analysis.belt`
- :mod:`~anvilate.analysis.bulk_solids` — granular handling: the Beverloo hopper discharge
  rate W = C·ρ·√g·(D − k·d)^2.5 and its orifice-sizing inverse, and the conical stockpile
  volume V = (π/3)·R³·tan φ
- :mod:`~anvilate.analysis.screw_conveyor` — screw-conveyor (auger) capacity: the volumetric
  throughput Q = (π/4)(D²−d²)·P·N·f swept by the flight, the mass rate ṁ = Q·ρ it feeds, and
  the screw speed a target capacity needs (N = Q/[(π/4)(D²−d²)·P·f])
- :mod:`~anvilate.analysis.pump` — pump sizing: the hydraulic power ρ·g·Q·H, the shaft
  power P/η the driver must supply, the dimensionless specific speed that picks the
  impeller type, the affinity laws that scale flow, head, and power (∝ N, N², N³)
  when the same pump runs at a new speed, and the available NPSH and cavitation margin
  at the suction
- :mod:`~anvilate.analysis.turbomachinery` — impeller Euler head: the blade tip speed
  U = π·D·N, the outlet swirl velocity c_θ = U − c_m/tan β from the vane-angle velocity
  triangle (backward/radial/forward-curved), and the Euler head H = (U₂·c_θ2 − U₁·c_θ1)/g —
  the loss-free ceiling the delivered head of :mod:`~anvilate.analysis.pump` falls below
- :mod:`~anvilate.analysis.vacuum_electronics` — vacuum electron emission: the Richardson-Dushman
  saturation current J = A·T²·exp(−W/kT), the Schottky field lowering ΔW = √(e³·E/(4π·ε₀)) of the
  work function, and the Child-Langmuir space-charge-limited current J = (4/9)·ε₀·√(2e/m)·V^{3/2}/d²
- :mod:`~anvilate.analysis.slider_crank` — slider-crank (piston) exact
  displacement from top dead centre, slider velocity, slider acceleration, the
  connecting-rod obliquity side thrust on the piston, and the crank torque a piston
  force makes (T = F·dx/dθ)
- :mod:`~anvilate.analysis.scotch_yoke` — scotch-yoke pure simple-harmonic
  displacement, velocity, and acceleration (the infinite-rod slider-crank limit)
- :mod:`~anvilate.analysis.universal_joint` — Cardan (Hooke) universal-joint kinematics: the
  instantaneous speed ratio cosβ/(1−sin²β·cos²θ), the maximum ratio 1/cosβ, and the peak-to-peak
  speed fluctuation 1/cosβ − cosβ that a single joint's angle produces
- :mod:`~anvilate.analysis.fourbar` — four-bar linkage Grashof rotatability
  criterion, mechanism-type classification, and the transmission angle at a given
  input angle
- :mod:`~anvilate.analysis.brake` — band-brake torque, the tight-side tension a
  torque requires, the peak lining pressure, and the simple/differential lever
  force; short-shoe (block) brake lever statics; the self-energizing /
  self-locking distinction for both
- :mod:`~anvilate.analysis.building_loads` — ASCE 7 environmental design loads:
  the wind velocity pressure (0.613·Kz·Kzt·Kd·Ke·V²), the MWFRS surface design
  pressure it drives, and the components-and-cladding net pressure
  (p = qh·(GCp − GCpi)); the seismic response coefficient (Cs = SDS·Ie/R), its
  long-period cap (Cs_max = SD1·Ie/(T·R)) and the approximate fundamental period
  (Ta = Ct·hn^x) that sets it, the equivalent-lateral-force base shear V = Cs·W
  and its vertical distribution to
  each floor (Fx = V·wx·hx^k/Σwi·hi^k), the bounded diaphragm design force Fpx,
  the accidental torsional moment (Mta = Vx·0.05·L·Ax) and its amplification
  factor Ax, the Cd-amplified design story drift
  (Δ = Cd·δxe/Ie) and the allowable drift it is checked against, the P-delta
  stability coefficient (θ = Pₓ·Δ/(Vₓ·hsx·Cd)) and its stability ceiling, the
  combined seismic load effect E = ρ·Q_E ± 0.2·SDS·D fed to the combinations, the
  flat- and sloped-roof snow loads
  (pf = 0.7·Ce·Ct·Is·pg, ps = Cs·pf), the snow density and leeward drift height
  (hd = 0.416·lu^⅓·(pg+0.479)^¼ − 0.457) for a drift surcharge, the
  tributary-area live-load reduction
  (L = L0·(0.25 + 4.57/√(KLL·AT))), and the ponded-water rain load
  (R = 0.0098·(ds + dh))
- :mod:`~anvilate.analysis.curved_beam` — Winkler curved-beam bending
  (rectangular, trapezoidal, circular, and composite T/I/box/stepped sections):
  shifted neutral axis and the unequal inner/outer fibre stresses of hooks,
  clamps, and links; and the thin circular ring's diametral deflection, peak
  moment under opposing loads, and external-pressure buckling load
- :mod:`~anvilate.analysis.illumination` — lighting design: point-source
  inverse-square cosine illuminance, the lumen method (room illuminance and
  its luminaire-count inverse), the room cavity ratio that sets the coefficient
  of utilization, and installed lighting power density
- :mod:`~anvilate.analysis.photometry` — luminous efficacy: the lamp efficacy Φ_v/P (lm/W), the
  luminous flux P·efficacy a lamp emits, and the overall luminous efficiency efficacy/683 (fraction
  of the 555 nm ideal) — the source-side efficiency feeding the lumen method
- :mod:`~anvilate.analysis.optical_instruments` — visual-instrument angular magnification: the
  telescope M = f_o/f_e, the simple magnifier M = D/f (D the 250 mm near point), and the compound
  microscope M = (L/f_o)·(D/f_e) — distinct from the single-lens imaging of optics
- :mod:`~anvilate.analysis.optics` — geometric optics for optomechanical design: the thin-lens
  image distance d_i = f·d_o/(d_o − f), the transverse magnification m = −d_i/d_o, the Rayleigh
  diffraction limit θ = 1.22·λ/D on resolving power, the lens speed side — the f-number
  N = f/D, the focused Airy spot d = 2.44·λ·N, and the hyperfocal distance H = f²/(N·c);
  refraction — Snell's law, the total-internal-reflection critical angle, and fibre NA; and lens
  design — the lensmaker's f from (n−1)(1/R₁−1/R₂), the diopter power 1/f, and two thin lenses in
  contact combining as 1/f = 1/f₁ + 1/f₂
- :mod:`~anvilate.analysis.fiber_optics` — fiber chromatic dispersion: the pulse broadening
  Δτ = D·L·Δλ over a link, the dispersion-limited bit rate B = 1/(4·Δτ), and the reach
  L = 1/(4·B·D·Δλ) a target bit rate allows before dispersion compensation is needed
- :mod:`~anvilate.analysis.photon` — photon (Planck) quanta: the photon energy E = h·c/λ, the
  wavelength matching an energy λ = h·c/E (e.g. a semiconductor band gap), and the photon flux
  Φ = P·λ/(h·c) a beam of a given optical power delivers — for detectors, solar cells, and LEDs
- :mod:`~anvilate.analysis.radiation_pressure` — light momentum and radiation pressure: the photon
  momentum p = h/λ, the radiation pressure P = (1+R)·I/c on a surface of reflectivity R, and the
  radiation force (1+R)·I·A/c that drives a solar sail
- :mod:`~anvilate.analysis.spectroscopy` — Beer-Lambert absorption: the absorbance A = ε·c·l, the
  transmittance T = 10^(−A) a sample passes, and the concentration a measured absorbance implies
  c = A/(ε·l) — the working equation of UV-Vis colorimetry
- :mod:`~anvilate.analysis.quantum` — photoelectric, matter-wave, and uncertainty quanta: the
  photoelectron energy KE = h·f − φ, the threshold frequency f0 = φ/h, the de Broglie wavelength
  λ = h/(m·v), and the Heisenberg minima Δp = ℏ/(2·Δx), Δx = ℏ/(2·Δp), and ΔE = ℏ/(2·Δt)
- :mod:`~anvilate.analysis.relativity` — special relativity: the Lorentz factor γ = 1/√(1−(v/c)²),
  the time dilation t = γ·t0 of a moving clock (GPS, muons), the relativistic kinetic energy
  (γ−1)·m·c², the length contraction L0/γ, the relativistic momentum γ·m·v, and the relativistic
  Doppler shift f0·√((1±β)/(1∓β)) (redshift/blueshift)
- :mod:`~anvilate.analysis.reliability` — Weibull reliability: the survival R(t) = exp(−(t/η)^β),
  the hazard rate h(t) = (β/η)·(t/η)^(β−1) (infant-mortality/constant/wear-out as β ≷ 1), and the
  mean time to failure η·Γ(1+1/β)
- :mod:`~anvilate.analysis.radar` — radar Doppler and range equation: the two-way Doppler shift
  f_d = 2·v·f0/c and the speed-gun inverse, the maximum unambiguous velocity PRF·c/(4·f0) and range
  c/(2·PRF), and the range equation — echo power P_t·G²·λ²·σ/((4π)³·R⁴) and detection range R_max
- :mod:`~anvilate.analysis.impact` — drop / suddenly-applied shock-load
  amplification factor and the horizontal (kinetic-energy) impact force
  (energy method)
- :mod:`~anvilate.analysis.projectile` — drag-free launch trajectory (conveyor discharge,
  jet/spray throw, safe fragment distance): the range R = v²·sin(2θ)/g, the peak height
  H = v²·sin²θ/(2g), and the time of flight t = 2·v·sin θ/g
- :mod:`~anvilate.analysis.process_capability` — SPC process capability: the potential index
  Cp = (USL−LSL)/(6σ), the centering-adjusted Cpk = min(USL−µ, µ−LSL)/(3σ), and the expected defect
  rate 10⁶·Φ(−3·Cpk) ppm a normal process yields
- :mod:`~anvilate.analysis.flywheel` — flywheel energy fluctuation, coefficient
  of fluctuation, the inertia a speed-smoothing target requires and the thin-rim
  mass that inertia needs, the rotating
  thin-rim hoop (bursting) stress, burst speed, and radial growth, the solid
  spinning disc's peak centre stress and its full radial/tangential stress
  distribution at any radius, and the annular (bored) disc's bore stress and full
  radial/tangential distribution
- :mod:`~anvilate.analysis.governor` — centrifugal (flyball) governor: the Watt height h = g/ω²
  that sets an engine speed, the running speed ω = √(g/h) a measured height implies, and the Porter
  height h = (g/ω²)·(m+M)/m that a central load raises
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
- :mod:`~anvilate.analysis.load_combinations` — the governing ASCE 7 factored load
  combination (§2.3 LRFD strength and §2.4 ASD) from the dead, live, roof/snow/rain,
  wind, and seismic load effects — dimension-general (force, moment, or stress)
- :mod:`~anvilate.analysis.weld` — fillet-weld throat shear, the weld leg a
  load requires, the peak throat stress of an eccentrically-loaded weld group
  (AISC elastic method), and the AISC 360 fillet-weld design strengths — the base
  §J2.4 weld-metal strength, the directional (sin θ) increase, and the companion
  §J4.2 base-metal shear rupture
- :mod:`~anvilate.analysis.welding_heat` — arc-welding process heat input: the arc
  power P = U·I, the heat input Q = η·U·I/v per unit length that sets the cooling
  rate and HAZ, and the travel speed a target heat input needs (v = η·U·I/Q)
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
  scorecard, straight-fin efficiency with its effectiveness ε_fin = η·A_f/A_c go/no-go metric and
  single-fin resistance 1/(η·h·A_f), the fin-array count a target resistance
  needs, and the flat-plate forced (laminar and turbulent) and vertical-plate natural
  convection coefficients with their validity ranges; plus heat-exchanger sizing — the LMTD,
  duty Q = U·A·ΔT_lm and its area/NTU inverses, the effectiveness-NTU relations, and now the
  overall coefficient U = 1/(1/h_i + R″_f,i + t/k + R″_f,o + 1/h_o) built from the film, wall, and
  fouling resistances, with the fouling factor and cleanliness factor a drop in U implies; plus
  radiation exchange — the two-surface gray-body network, the Hottel crossed-strings view factor,
  the view-factor reciprocity relation, and the 1/(N+1) radiation-shield reduction factor
- :mod:`~anvilate.analysis.condensation` — Nusselt filmwise condensation (phase-change
  heat transfer): the vertical-plate coefficient h = 0.943·[…/(μ·ΔT·L)]^¼ and the
  horizontal-tube form (0.729/D), and the condensate rate ṁ = h·A·ΔT/h_fg they drive
- :mod:`~anvilate.analysis.boiling` — nucleate boiling: the Rohsenow flux
  q″ = μ_l·h_fg·√(g·Δρ/σ)·[c_pl·ΔT_e/(C_sf·h_fg·Pr^n)]³, its ΔT_e inverse, and Zuber's
  critical-heat-flux burnout limit q″_max = 0.149·h_fg·√ρ_v·[σ·g·Δρ]^¼
- :mod:`~anvilate.analysis.boundary_layer` — laminar flat-plate (Blasius) boundary layer: the
  thickness δ = 5·x/√Re_x, the local skin-friction coefficient C_f = 0.664/√Re_x, and the average
  plate drag coefficient C_D = 1.328/√Re_L (all for Re below the ~5e5 laminar-turbulent transition)
- :mod:`~anvilate.analysis.thermoelectric` — solid-state Peltier/Seebeck devices: the
  Seebeck voltage V = α·ΔT, the net cooling Q_c = α·I·T_c − ½·I²·R − K·ΔT, and the
  single-stage cooling limit ΔT_max = ½·(α²/(R·K))·T_c²
- :mod:`~anvilate.analysis.strain_gauge` — strain-gauge instrumentation: the strain from a
  gauge's fractional resistance change ε = (ΔR/R)/GF, the Wheatstone-bridge output ratio
  V_o/V_ex = n·GF·ε/4 (n = 1/2/4 for quarter/half/full bridge), and the inverse that turns a
  bridge reading back into strain (and, via E, the stress the part carries)
- :mod:`~anvilate.analysis.piezoelectric` — piezoelectric transducers: the charge a force
  generates Q = d33·F (direct effect — sensors, harvesters), the open-circuit voltage a stress
  produces V = g33·σ·t, and the force behind a measured charge F = Q/d33 (piezo load-washer readout)
- :mod:`~anvilate.analysis.radioactivity` — radioactive decay: the decay constant λ = ln2/T½ a
  half-life fixes, the activity remaining after a time A = A0·2^(−t/T½), and the storage time to
  decay to a target activity t = T½·log2(A0/A)
- :mod:`~anvilate.analysis.radiation_shielding` — gamma/x-ray shielding (narrow-beam Beer-Lambert):
  the transmitted fraction T = e^(−μ·x), the half-value layer HVL = ln2/μ that halves the beam, and
  the shield thickness for a target transmission x = −ln(T)/μ
- :mod:`~anvilate.analysis.mass_energy` — mass-energy equivalence: the rest energy E = m·c² (≈90 TJ
  per gram, the nuclear-yield accounting), its mass-from-energy inverse m = E/c², and the binding
  energy per nucleon B/A (peaks near iron — fusion and fission both release energy toward it)
- :mod:`~anvilate.analysis.mass_transfer` — convective mass transfer and the heat-mass-momentum
  analogy: the Schmidt number Sc = ν/D_AB (the Prandtl twin), the Sherwood number Sh = k_c·L/D_AB
  (the Nusselt twin), the Lewis number Le = α/D_AB = Sc/Pr behind the air-water wet-bulb
  coincidence, the Stanton number St = Nu/(Re·Pr) and Colburn j-factor j_H = St·Pr^(2/3), and the
  Chilton-Colburn recovery of k_c = h/(ρ·c_p·Le^(2/3)) from a heat-transfer coefficient
- :mod:`~anvilate.analysis.compton` — Compton scattering: the wavelength shift Δλ = λ_C·(1−cos θ)
  (λ_C = 2.426 pm, angle-only), the scattered photon wavelength λ + Δλ, and the recoil electron
  energy h·c·(1/λ − 1/λ′) — the dominant medium-energy gamma interaction
- :mod:`~anvilate.analysis.dynamics` — modal screens: SDOF and Rayleigh
  estimates, the mass-on-beam frequencies (cantilever tip, simply-supported and
  fixed-fixed central, with the Rayleigh beam-mass correction), the Dunkerley
  multi-mass combination, distributed-mass beam
  fundamentals, taut-string/cable transverse modes, disc-on-shaft and two-rotor
  drivetrain torsional modes,
  and damped-vibration measures (damped frequency, the second-order step-response
  percent overshoot / settling time / peak time, log decrement, quality factor,
  critical damping coefficient, isolator transmissibility and its design inverse
  (the mount natural frequency and static deflection a target isolation needs),
  forced-response dynamic
  magnification and phase, and the base-excitation seismic-instrument response);
  the Design Guide 11 walking-vibration acceleration ratio a floor is judged by;
  simple and physical (rigid-body) pendulum periods; the solid-disc and annular
  (hollow-cylinder) polar mass moments of inertia; the rotating-unbalance
  centrifugal force, the counterweight that balances it, and the ISO 1940
  balance-grade permissible eccentricity;
  and the Den Hartog tuned-mass-damper optimal tuning
- :mod:`~anvilate.analysis.elastic_constants` — isotropic elastic-constant conversions: the bulk
  modulus K = E/(3(1−2ν)), the Lamé first parameter λ = Eν/((1+ν)(1−2ν)), and Young's modulus from
  bulk and shear E = 9KG/(3K+G) — the constants an FEA solver or the wave-speed relations need
- :mod:`~anvilate.analysis.elastic_waves` — elastic wave speeds in solids: the thin-bar longitudinal
  speed √(E/ρ), the shear (transverse) speed √(G/ρ), and the bulk P-wave speed √((K+4G/3)/ρ) — the
  velocities behind ultrasonic NDT and P/S-wave seismology
- :mod:`~anvilate.analysis.gyroscope` — rigid-rotor gyroscopic effects: the spin angular
  momentum L = I·ω, the precession rate Ω = M/(I·ω) an applied moment produces, and the
  reaction couple M = I·ω·Ω a forced precession puts on the bearings
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
  the deep-drawing cup blank diameter, draw ratio, and drawing force, and the elastic
  springback of a bend — the factor K_s = R_i/R_f, the sprung radius, and the sprung
  angle a press brake must overbend to beat
- :mod:`~anvilate.analysis.machining` — metal-cutting parameters: the surface cutting
  speed V = π·D·N and its spindle-speed inverse N = V/(π·D), the material removal rate
  MRR = V·f·d, the Taylor tool life T = (C/V)^(1/n) that trades speed for edge life, and the
  theoretical turned-surface roughness Ra ≈ f²/(32·r) and peak-to-valley Rt ≈ f²/(8·r) with the
  feed f = √(32·r·Ra) that meets a finish target
- :mod:`~anvilate.analysis.casting` — metal-casting solidification: the casting modulus
  M = V/A that governs freezing, Chvorinov's solidification time t = B·M², and the
  riser modulus M_r ≈ 1.2·M that makes the riser freeze last and take the shrinkage
- :mod:`~anvilate.analysis.centrifugal_casting` — casting in a spinning mold: the G-factor
  G = ω²·r/g that sets quality, the spin speed ω = √(G·g/r) to reach it, and the
  metallostatic wall pressure p = ½·ρ·ω²·(r_o² − r_i²) that packs the outer skin
- :mod:`~anvilate.analysis.centrifuge` — centrifugal separation: the Stokes sedimentation
  velocity in a centrifugal field v = d²·Δρ·ω²·r/(18·μ), and the settling time for a particle
  to reach the wall t = 18·μ·ln(r_o/r_i)/(ω²·d²·Δρ) — the radius-integrated tubular/decanter
  sizing relation (the field itself is the G-factor of
  :mod:`~anvilate.analysis.centrifugal_casting`)
- :mod:`~anvilate.analysis.casting_gating` — gating-system flow: the mold fill time
  t = V/(C_d·A·√(2gh)), the choke area A = V/(C_d·t·√(2gh)) for a target time, and the
  anti-aspiration sprue taper A_top/A_bottom = √(h_bottom/h_top)
- :mod:`~anvilate.analysis.forging` — open-die (bulk-deformation) forging: the true
  strain ε = ln(h₀/h₁) of an upset, the Hollomon flow stress σ = K·εⁿ that work-
  hardening sets, and the press load F = σ·π·r²·(1 + 2μr/(3h)) with its friction hill
- :mod:`~anvilate.analysis.rolling` — flat rolling: the maximum draft Δh_max = μ²·R
  the rolls can bite, the roll-strip contact length L = √(R·Δh), and the roll
  separating force F = Y_avg·w·L the mill stand must carry
- :mod:`~anvilate.analysis.rotor_momentum` — rotor hover (actuator-disk momentum theory): the
  induced downwash v_h = √(T/(2·ρ·A)), the ideal hover power P = T^{3/2}/√(2·ρ·A), and the figure
  of merit FM = P_ideal/P_actual that rates a real rotor's hover efficiency
- :mod:`~anvilate.analysis.extrusion` — direct extrusion: the extrusion ratio
  R = A₀/A_f, the ram pressure p = Y_avg·ln(R)/η (ideal work over a deformation
  efficiency), and the ram force F = p·A₀ that sizes the press
- :mod:`~anvilate.analysis.wire_drawing` — wire/rod drawing: the draw stress
  σ_d = Y·ln(A₀/A_f)·(1 + μ/tan α), the draw force F = σ_d·A_f, and the maximum
  area reduction per pass r_max = 1 − exp(−1/(1 + μ/tan α)) before the wire snaps
- :mod:`~anvilate.analysis.shear_spinning` — metal spinning by the sine law: the spun wall
  t_f = t₀·sin α, the thickness reduction r = 1 − sin α, and the cone half-angle a target
  wall needs α = arcsin(t_f/t₀) — steep cones exceed one-pass spinnability
- :mod:`~anvilate.analysis.grinding` — surface-grinding process signature: the specific
  removal rate Q′_w = a_e·v_w, the equivalent chip thickness h_eq = Q′_w/v_s that tracks
  grain force and burn, and the specific energy u = P/(b·Q′_w) that sets the surface heat
- :mod:`~anvilate.analysis.broaching` — broaching in a single stroke: the teeth in cut
  n = ⌊L/p⌋, the cutting force F = k_s·n·w·t, and the pull-broach tensile capacity
  F_max = σ_allow·A_root that caps the load before the bar snaps
- :mod:`~anvilate.analysis.drilling` — twist drilling sized on torque: the removal rate
  MRR = (π/4)·d²·f·N, the spindle torque M = u·f·d²/8, and the feed a torque limit allows
  f_max = 8·M_limit/(u·d²) before the drill stalls
- :mod:`~anvilate.analysis.ecm` — electrochemical machining by Faraday dissolution: the
  removal rate Q = I·EW/(ρ·F), the feed rate f = J·EW/(ρ·F), and the self-regulating gap
  g = κ·U·EW/(ρ·F·f) that shorts out if the feed is pushed too fast
- :mod:`~anvilate.analysis.laser_cutting` — laser cutting as a power balance: the specific
  removal energy e_m = c·ΔT + L_f, the cutting speed v = η·P/(ρ·t·w·e_m), and the greatest
  thickness a laser can sever t_max = η·P/(ρ·v·w·e_m)
- :mod:`~anvilate.analysis.edm` — electrical discharge machining by spark erosion: the
  discharge energy per pulse E = U·I·t_on, the duty factor τ = t_on/(t_on + t_off), and the
  removal rate MRR = k·I·τ — the roughing-versus-finishing trade made numerical
- :mod:`~anvilate.analysis.shot_peening` — shot-peening coverage by Avrami statistics: the
  coverage rate λ = (π·d²/4)·φ, the coverage C = 1 − exp(−λ·t), and the exposure a target
  coverage needs t = −ln(1 − C)/λ (100% unreachable, so 98% is "full coverage")
- :mod:`~anvilate.analysis.electroplating` — electroplating by Faraday deposition: the mass
  plated m = EW·I·t·η/F, the coating thickness δ = EW·I·t·η/(F·ρ·A), and the run time a
  target thickness needs t = δ·F·ρ·A/(EW·I·η) — the deposition mirror of ecm/corrosion
- :mod:`~anvilate.analysis.electrostatics` — Coulomb electrostatics: the force k·q₁·q₂/r² between
  point charges, the field E = k·q/r² a charge sets up, and the potential V = k·q/r — the
  charge-based mirror of gravitation
- :mod:`~anvilate.analysis.resistance_welding` — resistance spot welding by Joule heating:
  the heat Q = I²·R·t, the current a schedule needs I = √(Q/(R·t)), and the nugget melting
  energy E = ρ·V·(c·ΔT + L_f) whose ratio to Q is the low thermal efficiency
- :mod:`~anvilate.analysis.snapfit` — constant-section cantilever snap-fit design by
  strain: the permissible deflection a material allowable permits, the peak root strain
  a required undercut imposes, the finger deflection (spring) force, and the mating
  (assembly) force over the lead-in ramp
- :mod:`~anvilate.analysis.injection_molding` — injection-moulding process: the clamp
  force F = A·p a mould needs (and the inverse max projected area a machine's tonnage
  allows), and the cooling time t = (s²/π²α)·ln[…] that dominates the cycle (goes as
  wall thickness squared) — the process side of snapfit/living_hinge part design
- :mod:`~anvilate.analysis.thermoforming` — vacuum-forming by conservation of volume: the
  areal draw ratio S = A_part/A_sheet, the average wall t_avg = t_sheet/S it thins to, and
  the starting sheet gauge t_sheet = t_min·S a target wall needs
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
  a rectangular embedded footing under an inclined load), the allowable pressure from the
  ultimate over a factor of safety and the required spread-footing area it sizes (net of
  overburden),
  Terzaghi 1D consolidation settlement with its time-rate factor, retaining-wall
  external stability (overturning, sliding, and eccentric base-pressure) checks, the
  infinite-slope factor of safety, the 2:1 vertical stress increase under a footing, the
  α-method pile capacity (shaft skin friction plus end bearing) for deep foundations, and
  groundwater seepage (Darcy flow, seepage velocity, and the critical gradient and piping
  factor of safety), and the Janssen silo pressure of stored granular material
- :mod:`~anvilate.analysis.road_curve` — highway/rail curve superelevation and sight
  distance (AASHTO): the minimum curve radius a design speed needs (R = v²/(g·(e+f))),
  the friction-free ideal superelevation rate, the maximum speed a banked curve can be
  taken at, and the stopping sight distance SSD = v·t + v²/(2·(a+g·G)) — reaction plus
  braking, grade-adjusted — that a curve must keep clear
- :mod:`~anvilate.analysis.vehicle` — vehicle road load for drivetrain/EV sizing: the rolling
  resistance F = C_rr·m·g, the grade resistance F = m·g·sin θ, and the tractive power P = F·v
  a steady speed demands (aerodynamic drag from :mod:`~anvilate.analysis.drag`)
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
    closed_pipe_resonance_frequency,
    doppler_shifted_frequency,
    doppler_velocity_from_shift,
    helmholtz_resonator_frequency,
    inverse_square_attenuation,
    mach_cone_angle,
    mass_law_transmission_loss,
    noise_dose_fraction,
    open_pipe_resonance_frequency,
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
from .antenna import (
    aperture_antenna_gain,
    dish_diameter_for_gain,
    free_space_path_loss,
    max_line_of_sight_range,
    parabolic_beamwidth,
    received_power,
)
from .arrhenius import (
    arrhenius_activation_energy,
    arrhenius_rate_constant,
    arrhenius_rate_ratio,
)
from .atmosphere import (
    barometric_altitude,
    barometric_pressure,
    scale_height,
)
from .atomic_spectra import (
    bohr_energy_level,
    bohr_orbit_radius,
    rydberg_transition_wavelength,
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
from .battery_peukert import (
    peukert_effective_capacity,
    peukert_exponent_from_two_rates,
    peukert_runtime,
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
from .boiling import (
    critical_heat_flux,
    nucleate_boiling_excess_temperature,
    nucleate_boiling_heat_flux,
)
from .boundary_layer import (
    laminar_boundary_layer_thickness,
    laminar_plate_drag_coefficient,
    laminar_skin_friction_coefficient,
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
from .broaching import (
    broaching_cutting_force,
    broaching_pull_capacity,
    broaching_teeth_in_cut,
)
from .building_loads import (
    allowable_story_drift,
    approximate_fundamental_period,
    components_cladding_net_pressure,
    flat_roof_snow_load,
    leeward_snow_drift_height,
    rain_load,
    reduced_live_load,
    seismic_accidental_torsional_moment,
    seismic_base_shear,
    seismic_design_story_drift,
    seismic_diaphragm_force,
    seismic_load_effect,
    seismic_response_coefficient,
    seismic_response_coefficient_upper_limit,
    seismic_stability_coefficient,
    seismic_stability_coefficient_limit,
    seismic_torsional_amplification_factor,
    seismic_vertical_force_distribution,
    sloped_roof_snow_load,
    snow_density,
    wind_design_pressure,
    wind_velocity_pressure,
)
from .bulk_solids import (
    beverloo_discharge_rate,
    beverloo_orifice_for_rate,
    conical_stockpile_volume,
)
from .cable import (
    catenary_arc_length,
    catenary_max_tension,
    catenary_sag,
    parabolic_cable_length,
    parabolic_cable_max_tension,
    parabolic_cable_sag,
)
from .calorimetry import (
    latent_heat,
    mixing_equilibrium_temperature,
    sensible_heat,
)
from .cam import (
    CamMotion,
    cam_base_circle_for_pressure_angle,
    cam_follower_motion,
    cam_pressure_angle,
)
from .capillary_flow import (
    washburn_capillary_pressure,
    washburn_penetration_length,
    washburn_penetration_time,
)
from .casting import (
    casting_modulus,
    chvorinov_solidification_time,
    riser_modulus_for_feeding,
)
from .casting_gating import (
    gating_choke_area,
    gating_fill_time,
    sprue_taper_ratio,
)
from .centrifugal_casting import (
    centrifugal_g_factor,
    centrifugal_speed_for_g_factor,
    centrifugal_wall_pressure,
)
from .centrifuge import (
    centrifugal_sedimentation_velocity,
    centrifuge_settling_time,
)
from .chain import (
    chain_length_in_pitches,
    chain_speed,
    chain_working_tension,
    chordal_speed_variation,
    minimum_sprocket_teeth_for_chordal_variation,
)
from .channel_capacity import (
    nyquist_channel_capacity,
    shannon_capacity,
    shannon_required_bandwidth,
)
from .chemical_equilibrium import (
    equilibrium_constant,
    gibbs_free_energy_change,
    vant_hoff_constant_ratio,
)
from .circular_motion import (
    centripetal_acceleration,
    centripetal_force,
    maximum_cornering_speed,
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
from .colligative import (
    boiling_point_elevation,
    freezing_point_depression,
    osmotic_pressure,
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
    combustion_efficiency,
    equivalence_ratio,
    equivalence_ratio_from_excess_air,
    excess_air_from_flue_oxygen,
    siegert_dry_flue_gas_loss,
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
    mach_angle,
    mach_number,
    maximum_turning_angle,
    normal_shock_downstream_mach,
    normal_shock_pressure_ratio,
    normal_shock_stagnation_pressure_ratio,
    prandtl_meyer_angle,
    speed_of_sound,
    stagnation_density_ratio,
    stagnation_pressure_ratio,
    stagnation_temperature_ratio,
)
from .compton import (
    compton_electron_energy,
    compton_scattered_wavelength,
    compton_wavelength_shift,
)
from .condensation import (
    condensation_rate,
    film_condensation_horizontal_tube_coefficient,
    film_condensation_vertical_plate_coefficient,
)
from .contact import (
    HertzContact,
    HertzLineContact,
    hertz_cylinder_contact,
    hertz_effective_modulus,
    hertz_sphere_approach,
    hertz_sphere_contact,
)
from .conveyor import (
    belt_speed_for_capacity,
    conveyor_lift_power,
    conveyor_mass_flow,
)
from .cooling_tower import (
    cooling_tower_approach,
    cooling_tower_effectiveness,
    cooling_tower_range,
)
from .coriolis import (
    coriolis_acceleration,
    coriolis_parameter,
    rossby_number,
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
from .cyclotron import (
    cyclotron_frequency,
    cyclotron_mass_from_frequency,
    larmor_radius,
)
from .data_converter import (
    effective_number_of_bits,
    quantization_snr,
    quantization_step,
)
from .dc_circuit import (
    ohms_law_voltage,
    parallel_resistance,
    resistive_power,
)
from .dc_dc_converter import (
    boost_output_voltage,
    buck_boost_output_voltage,
    buck_output_voltage,
)
from .diffraction import (
    bragg_angle,
    bragg_plane_spacing,
    grating_diffraction_angle,
)
from .diffusion import (
    diffusion_length,
    diffusion_time,
    steady_diffusion_flux,
)
from .diode import (
    diode_current,
    diode_voltage,
    thermal_voltage,
)
from .drag import (
    drag_force,
    jet_impact_force,
    stokes_drag_force,
    stokes_settling_velocity,
    terminal_velocity,
)
from .drilling import (
    drilling_feed_for_torque_limit,
    drilling_material_removal_rate,
    drilling_torque,
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
    floor_vibration_peak_acceleration_ratio,
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
    step_response_peak_time,
    step_response_percent_overshoot,
    step_response_settling_time,
    string_natural_frequency,
    torsional_natural_frequency,
    transmissibility,
    tuned_mass_damper_optimal_damping,
    tuned_mass_damper_optimal_frequency_ratio,
    two_rotor_torsional_natural_frequency,
)
from .ecm import (
    ecm_equilibrium_gap,
    ecm_feed_rate,
    ecm_material_removal_rate,
)
from .edm import (
    edm_discharge_energy,
    edm_duty_factor,
    edm_material_removal_rate,
)
from .elastic_constants import (
    bulk_modulus_from_youngs_poisson,
    lame_first_parameter,
    youngs_modulus_from_bulk_shear,
)
from .elastic_waves import (
    bar_wave_speed,
    bulk_longitudinal_wave_speed,
    shear_wave_speed,
)
from .electrical import (
    apparent_power_three_phase,
    conductor_resistance,
    ground_rod_resistance,
    line_current_for_power,
    motor_branch_circuit_ampacity,
    motor_full_load_current,
    motor_locked_rotor_current,
    motor_slip,
    motor_synchronous_speed,
    parallel_ground_electrodes_resistance,
    power_factor_correction_kvar,
    skin_depth,
    three_phase_power,
    transformer_available_fault_current,
    transformer_efficiency,
    transformer_full_load_current,
    transformer_maximum_efficiency_load_fraction,
    transformer_reflected_impedance,
    transformer_secondary_current,
    transformer_secondary_voltage,
    transformer_voltage_regulation,
    voltage_drop_single_phase,
    voltage_drop_three_phase,
)
from .electromagnetic_induction import (
    faraday_induced_emf,
    motional_emf,
    self_induced_emf,
)
from .electroplating import (
    electroplating_deposition_thickness,
    electroplating_mass_deposited,
    electroplating_time_for_thickness,
)
from .electrostatics import (
    coulomb_force,
    electric_field_point_charge,
    electric_potential_point_charge,
)
from .energy_storage import (
    battery_backup_time,
    battery_bank_capacity,
    battery_delivered_energy,
    battery_round_trip_efficiency,
    usable_battery_energy,
)
from .engineering_economics import (
    annuity_future_value,
    annuity_present_value,
    benefit_cost_ratio,
    future_value,
    loan_payment,
    net_present_value,
    present_value,
    simple_payback_period,
    straight_line_depreciation,
)
from .extrusion import (
    extrusion_force,
    extrusion_pressure,
    extrusion_ratio,
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
from .fiber_optics import (
    chromatic_dispersion_broadening,
    dispersion_limited_bit_rate,
    dispersion_limited_distance,
)
from .flow_measurement import (
    differential_pressure_for_flow,
    dynamic_pressure,
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
from .forging import (
    flow_stress_power_law,
    forging_true_strain,
    open_die_forging_load,
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
from .fresnel import (
    brewster_angle,
    fresnel_normal_reflectance,
    slab_transmittance,
)
from .friction import (
    angle_of_repose,
    force_to_slide_up_incline,
    friction_force,
)
from .gas_compression import (
    adiabatic_compression_power,
    adiabatic_discharge_temperature,
    ideal_gas_density,
    isothermal_compression_power,
    multistage_compression_power,
    optimal_stage_pressure_ratio,
)
from .gas_transport import (
    prandtl_number,
    sutherland_thermal_conductivity,
    sutherland_viscosity,
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
    allowable_bearing_from_ultimate,
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
    required_spread_footing_area,
    retaining_wall_overturning_factor,
    retaining_wall_sliding_factor,
    seepage_velocity,
    tension_crack_depth,
    terzaghi_bearing_capacity,
    vertical_stress_increase_2to1,
)
from .governor import (
    porter_governor_height,
    watt_governor_height,
    watt_governor_speed,
)
from .gravitation import (
    gravitational_force,
    gravitational_parameter,
    surface_gravity,
)
from .grinding import (
    grinding_equivalent_chip_thickness,
    grinding_specific_energy,
    grinding_specific_removal_rate,
)
from .gyroscope import (
    gyroscopic_precession_rate,
    gyroscopic_reaction_moment,
    gyroscopic_spin_angular_momentum,
)
from .hall_effect import (
    hall_carrier_density,
    hall_flux_density_from_voltage,
    hall_voltage,
)
from .hvac_duct import (
    circular_equivalent_diameter,
    fan_power,
    fan_total_pressure,
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
from .hydraulic_motor import (
    hydraulic_motor_speed,
    hydraulic_motor_torque,
    hydraulic_pump_flow_rate,
)
from .hydraulic_press import (
    hydraulic_press_input_stroke,
    hydraulic_press_output_force,
    hydraulic_press_transmitted_pressure,
)
from .hydro_power import (
    hydro_flow_for_power,
    hydro_net_head,
    hydro_turbine_power,
)
from .ideal_gas import (
    ideal_gas_moles,
    ideal_gas_pressure,
    ideal_gas_volume,
)
from .illumination import (
    lighting_power_density,
    lumen_method_illuminance,
    lumen_method_luminaire_count,
    point_source_illuminance,
    room_cavity_ratio,
)
from .impact import (
    SUDDENLY_APPLIED_FACTOR,
    horizontal_impact_force,
    impact_factor,
    impact_stress,
)
from .injection_molding import (
    injection_clamp_force,
    injection_cooling_time,
    max_projected_area_for_clamp,
)
from .interference import (
    InterferenceFit,
    interference_axial_capacity,
    interference_fit,
    interference_for_contact_pressure,
    interference_torque_capacity,
)
from .isentropic_efficiency import (
    compressor_actual_discharge_temperature,
    compressor_isentropic_efficiency,
    compressor_isentropic_from_polytropic,
    compressor_polytropic_efficiency,
    turbine_isentropic_efficiency,
    turbine_isentropic_from_polytropic,
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
from .kinetic_theory import (
    mean_free_path,
    mean_molecular_speed,
    rms_molecular_speed,
)
from .laser_cutting import (
    laser_cutting_speed,
    laser_max_cut_thickness,
    laser_specific_removal_energy,
)
from .living_hinge import (
    living_hinge_fold_strain,
    living_hinge_web_length_for_strain,
)
from .load_combinations import (
    asce7_asd_factored_load,
    asce7_lrfd_factored_load,
)
from .machining import (
    cutting_speed,
    feed_for_surface_roughness,
    material_removal_rate,
    peak_to_valley_roughness,
    spindle_speed_for_cutting_speed,
    taylor_tool_life,
    theoretical_surface_roughness,
)
from .magnetics import (
    electromagnet_holding_force,
    magnetic_flux,
    magnetic_pressure,
    magnetic_reluctance,
    magnetomotive_force,
    solenoid_magnetic_field,
)
from .masonry import (
    masonry_allowable_axial_stress,
    masonry_allowable_flexural_stress,
    masonry_column_axial_capacity,
    masonry_combined_stress_ratio,
)
from .mass_energy import (
    binding_energy_per_nucleon,
    mass_energy,
    mass_from_energy,
)
from .mass_transfer import (
    chilton_colburn_mass_transfer_coefficient,
    colburn_j_factor,
    lewis_number,
    schmidt_number,
    sherwood_number,
    stanton_number,
)
from .momentum import (
    average_impact_force,
    impulse,
    linear_momentum,
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
from .nernst import (
    nernst_potential,
    nernst_reaction_quotient,
    nernst_slope,
)
from .noise_figure import (
    cascade_noise_factor,
    equivalent_noise_temperature,
    noise_factor_from_figure,
)
from .o_ring import (
    o_ring_gland_fill_fraction,
    o_ring_squeeze_fraction,
    o_ring_stretch_fraction,
)
from .op_amp import (
    gain_bandwidth_limited_bandwidth,
    inverting_gain,
    noninverting_gain,
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
from .optical_instruments import (
    magnifier_angular_magnification,
    microscope_magnification,
    telescope_angular_magnification,
)
from .optics import (
    combined_thin_lens_focal_length,
    critical_angle,
    diffraction_limited_angular_resolution,
    diffraction_limited_spot_diameter,
    fiber_numerical_aperture,
    hyperfocal_distance,
    lens_f_number,
    lens_power,
    lens_transverse_magnification,
    lensmaker_focal_length,
    snell_refraction_angle,
    thin_lens_image_distance,
)
from .orbital_mechanics import (
    circular_orbit_velocity,
    escape_velocity,
    hohmann_first_burn_delta_v,
    hohmann_second_burn_delta_v,
    hohmann_transfer_time,
    orbit_specific_energy,
    orbital_period,
    semi_major_axis_from_apsides,
    vis_viva_velocity,
)
from .photometry import (
    luminous_efficacy,
    luminous_efficiency,
    luminous_flux_from_power,
)
from .photon import (
    photon_energy,
    photon_flux,
    photon_wavelength_from_energy,
)
from .piezoelectric import (
    piezoelectric_charge,
    piezoelectric_force_from_charge,
    piezoelectric_open_circuit_voltage,
)
from .pipe_flow import (
    cavitation_number,
    darcy_friction_factor,
    darcy_weisbach_head_loss,
    hagen_poiseuille_flow_rate,
    hagen_poiseuille_pressure_drop,
    hagen_poiseuille_radius_for_flow,
    hazen_williams_flow_capacity,
    hazen_williams_head_loss,
    hydraulic_diameter,
    joukowsky_surge_pressure,
    laminar_hydrodynamic_entry_length,
    laminar_thermal_entry_length,
    minor_loss_head,
    pipe_pressure_drop,
    pressure_wave_speed,
    reynolds_number,
    surge_wave_period,
    turbulent_entry_length,
)
from .plasma import (
    debye_length,
    plasma_frequency,
    plasma_parameter,
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
from .pn_junction import (
    built_in_potential,
    depletion_width,
    junction_capacitance_per_area,
)
from .pneumatics import (
    air_receiver_holdup_time,
    air_receiver_volume_for_demand,
)
from .polarization import (
    malus_angle_for_intensity,
    malus_transmitted_intensity,
    unpolarized_transmitted_intensity,
)
from .power_cycles import (
    brayton_cycle_efficiency,
    carnot_efficiency,
    diesel_cycle_efficiency,
    heat_engine_second_law_efficiency,
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
from .process_capability import (
    expected_defect_rate_ppm,
    process_capability_index,
    process_capability_ratio,
)
from .projectile import (
    projectile_max_height,
    projectile_range,
    projectile_time_of_flight,
)
from .psychrometrics import (
    adiabatic_mixing_humidity_ratio,
    adiabatic_mixing_temperature,
    coil_bypass_factor,
    cooling_coil_load,
    dew_point_temperature,
    evaporative_cooler_effectiveness,
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
from .quantum import (
    de_broglie_wavelength,
    minimum_energy_uncertainty,
    minimum_momentum_uncertainty,
    minimum_position_uncertainty,
    photoelectric_max_kinetic_energy,
    photoelectric_threshold_frequency,
)
from .radar import (
    max_unambiguous_range,
    max_unambiguous_velocity,
    radar_doppler_shift,
    radar_max_range,
    radar_received_power,
    radial_velocity_from_doppler,
)
from .radiation_pressure import (
    photon_momentum,
    radiation_force,
    radiation_pressure,
)
from .radiation_shielding import (
    half_value_layer,
    radiation_transmission_fraction,
    shield_thickness_for_transmission,
)
from .radioactivity import (
    decay_constant_from_half_life,
    remaining_activity,
    time_for_activity_decay,
)
from .reactive_circuit import (
    capacitor_charge,
    capacitor_stored_energy,
    inductor_stored_energy,
    lc_resonant_frequency,
    parallel_plate_capacitance,
    parallel_plate_field,
    rc_cutoff_frequency,
    rc_time_constant,
    rl_time_constant,
)
from .refrigeration import (
    carnot_cop_cooling,
    carnot_cop_heating,
    coefficient_of_performance,
    compressor_work_of_compression,
    refrigerant_mass_flow_rate,
    refrigeration_effect,
    second_law_efficiency,
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
from .relativity import (
    length_contraction,
    lorentz_factor,
    relativistic_doppler_frequency,
    relativistic_kinetic_energy,
    relativistic_momentum,
    time_dilation,
)
from .reliability import (
    weibull_hazard_rate,
    weibull_mean_life,
    weibull_reliability,
)
from .resistance_welding import (
    spot_weld_current_for_heat,
    spot_weld_heat_generated,
    spot_weld_nugget_melting_energy,
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
    braking_distance,
    ideal_superelevation_rate,
    minimum_curve_radius,
    perception_reaction_distance,
    stopping_sight_distance,
)
from .rocket_propulsion import (
    characteristic_velocity,
    rocket_delta_v,
    rocket_exhaust_velocity,
    rocket_propellant_mass_fraction,
    rocket_specific_impulse,
    rocket_thrust,
    thrust_coefficient,
    thrust_from_coefficient,
)
from .rolling import (
    maximum_draft,
    rolling_contact_length,
    rolling_force,
)
from .rotor_momentum import (
    figure_of_merit,
    hover_induced_velocity,
    ideal_hover_power,
)
from .scotch_yoke import (
    scotch_yoke_acceleration,
    scotch_yoke_displacement,
    scotch_yoke_velocity,
)
from .screw_conveyor import (
    screw_conveyor_mass_capacity,
    screw_conveyor_speed_for_capacity,
    screw_conveyor_volumetric_capacity,
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
from .shear_spinning import (
    shear_spinning_half_angle_for_thickness,
    shear_spinning_reduction,
    shear_spinning_wall_thickness,
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
    springback_factor,
    sprung_bend_angle,
    sprung_bend_radius,
    stripping_force,
)
from .shot_peening import (
    peening_coverage,
    peening_impact_coverage_rate,
    peening_time_for_coverage,
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
from .solar_cell import (
    fill_factor,
    solar_cell_efficiency,
    solar_cell_max_power,
)
from .solar_geometry import (
    air_mass,
    solar_altitude_at_noon,
    solar_declination,
)
from .solar_pv import (
    pv_array_power,
    pv_array_size_for_load,
    pv_cell_temperature,
    pv_daily_energy,
    pv_temperature_derated_power,
)
from .solar_thermal import (
    collector_stagnation_temperature,
    collector_useful_heat,
    flat_plate_collector_efficiency,
)
from .spectroscopy import (
    absorbance,
    concentration_from_absorbance,
    transmittance_from_absorbance,
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
from .strain_gauge import (
    gauge_strain_from_resistance,
    strain_from_bridge_output,
    wheatstone_bridge_output,
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
    cleanliness_factor,
    conduction_thermal_resistance,
    confined_liquid_thermal_pressure,
    constrained_thermal_stress,
    convection_thermal_resistance,
    counterflow_effectiveness,
    counterflow_ntu_for_effectiveness,
    critical_insulation_radius,
    crossed_strings_view_factor,
    crossflow_both_unmixed_effectiveness,
    cylindrical_conduction_resistance,
    degree_day_cooling_energy,
    degree_day_heating_energy,
    differential_thermal_stress,
    dittus_boelter_convection_coefficient,
    fin_array_count_for_resistance,
    fin_effectiveness,
    fin_efficiency,
    fin_thermal_resistance,
    flat_plate_forced_convection_coefficient,
    flat_plate_turbulent_convection_coefficient,
    fouling_factor_from_coefficients,
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
    overall_heat_transfer_coefficient,
    parallel_flow_effectiveness,
    parallel_flow_ntu_for_effectiveness,
    parallel_thermal_resistance,
    radiation_heat_transfer,
    radiation_heat_transfer_coefficient,
    radiation_shield_reduction_factor,
    radiation_two_surface_exchange,
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
    view_factor_reciprocity,
    wien_peak_wavelength,
    wien_temperature_from_peak,
)
from .thermal_noise import (
    johnson_noise_current,
    johnson_noise_power,
    johnson_noise_voltage,
)
from .thermoelectric import (
    peltier_cooling_rate,
    seebeck_voltage,
    thermoelectric_max_temperature_difference,
)
from .thermoforming import (
    thermoforming_areal_draw_ratio,
    thermoforming_average_wall_thickness,
    thermoforming_sheet_gauge_for_wall,
)
from .thin_film import (
    optimal_ar_coating_index,
    quarter_wave_thickness,
    thin_film_tuned_wavelength,
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
from .transmission_line import (
    reflection_coefficient,
    return_loss,
    voltage_standing_wave_ratio,
)
from .turbomachinery import (
    blade_tip_speed,
    euler_head,
    impeller_outlet_swirl_velocity,
)
from .universal_joint import (
    universal_joint_max_speed_ratio,
    universal_joint_speed_fluctuation,
    universal_joint_speed_ratio,
)
from .vacuum_electronics import (
    child_langmuir_current_density,
    schottky_barrier_lowering,
    thermionic_current_density,
)
from .vehicle import (
    grade_resistance_force,
    rolling_resistance_force,
    tractive_power,
)
from .ventilation import (
    air_changes_per_hour,
    airflow_for_air_changes,
    breathing_zone_outdoor_airflow,
    dilution_airflow,
)
from .vortex_shedding import (
    lock_in_velocity,
    reduced_velocity,
    vortex_shedding_frequency,
)
from .wave import (
    frequency_from_wavelength,
    wave_speed,
    wavelength_from_frequency,
)
from .waveguide import (
    rectangular_waveguide_cutoff_frequency,
    waveguide_guide_wavelength,
    waveguide_phase_velocity,
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
from .welding_heat import (
    weld_arc_power,
    weld_heat_input,
    weld_travel_speed_for_heat_input,
)
from .winch import (
    drum_line_pull,
    drum_rope_capacity,
    drum_working_radius,
)
from .wind_power import (
    BETZ_LIMIT,
    capacity_factor,
    wind_power_density,
    wind_turbine_power,
    wind_turbine_tip_speed_ratio,
)
from .wing_aerodynamics import (
    induced_drag_coefficient,
    lift_force,
    stall_speed,
)
from .wire_drawing import (
    wire_drawing_force,
    wire_drawing_max_reduction,
    wire_drawing_stress,
)
from .wire_rope import (
    minimum_sheave_diameter_for_bending_stress,
    wire_rope_bending_stress,
    wire_rope_equivalent_bending_load,
    wire_rope_sheave_pressure,
)
from .work_energy import (
    gravitational_potential_energy,
    kinetic_energy,
    work_done,
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
    "allowable_bearing_from_ultimate",
    "required_spread_footing_area",
    "retaining_wall_overturning_factor",
    "retaining_wall_sliding_factor",
    "seepage_velocity",
    "tension_crack_depth",
    "terzaghi_bearing_capacity",
    "vertical_stress_increase_2to1",
    "watt_governor_height",
    "watt_governor_speed",
    "porter_governor_height",
    "gravitational_force",
    "surface_gravity",
    "gravitational_parameter",
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
    "blade_tip_speed",
    "impeller_outlet_swirl_velocity",
    "euler_head",
    "universal_joint_speed_ratio",
    "universal_joint_max_speed_ratio",
    "universal_joint_speed_fluctuation",
    "thermionic_current_density",
    "schottky_barrier_lowering",
    "child_langmuir_current_density",
    "capacitor_stored_energy",
    "inductor_stored_energy",
    "lc_resonant_frequency",
    "rc_time_constant",
    "rl_time_constant",
    "rc_cutoff_frequency",
    "parallel_plate_capacitance",
    "capacitor_charge",
    "parallel_plate_field",
    "thermal_voltage",
    "diode_current",
    "diode_voltage",
    "built_in_potential",
    "depletion_width",
    "junction_capacitance_per_area",
    "buck_output_voltage",
    "boost_output_voltage",
    "buck_boost_output_voltage",
    "johnson_noise_voltage",
    "johnson_noise_power",
    "johnson_noise_current",
    "noninverting_gain",
    "inverting_gain",
    "gain_bandwidth_limited_bandwidth",
    "steady_diffusion_flux",
    "diffusion_length",
    "diffusion_time",
    "bragg_angle",
    "bragg_plane_spacing",
    "grating_diffraction_angle",
    "quarter_wave_thickness",
    "optimal_ar_coating_index",
    "thin_film_tuned_wavelength",
    "fresnel_normal_reflectance",
    "slab_transmittance",
    "brewster_angle",
    "friction_force",
    "angle_of_repose",
    "force_to_slide_up_incline",
    "manning_flow_velocity",
    "broad_crested_weir_flow",
    "minimum_specific_energy_rectangular",
    "rational_method_peak_runoff",
    "rectangular_weir_flow",
    "specific_energy",
    "trapezoidal_channel_properties",
    "triangular_weir_flow",
    "circular_orbit_velocity",
    "orbital_period",
    "escape_velocity",
    "hohmann_first_burn_delta_v",
    "hohmann_second_burn_delta_v",
    "hohmann_transfer_time",
    "vis_viva_velocity",
    "orbit_specific_energy",
    "semi_major_axis_from_apsides",
    "cavitation_number",
    "darcy_friction_factor",
    "darcy_weisbach_head_loss",
    "hagen_poiseuille_flow_rate",
    "hagen_poiseuille_pressure_drop",
    "hagen_poiseuille_radius_for_flow",
    "hazen_williams_flow_capacity",
    "hazen_williams_head_loss",
    "hydraulic_diameter",
    "joukowsky_surge_pressure",
    "laminar_hydrodynamic_entry_length",
    "laminar_thermal_entry_length",
    "turbulent_entry_length",
    "minor_loss_head",
    "pipe_pressure_drop",
    "pressure_wave_speed",
    "reynolds_number",
    "surge_wave_period",
    "differential_pressure_for_flow",
    "obstruction_meter_flow_rate",
    "pitot_velocity",
    "dynamic_pressure",
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
    "sutherland_viscosity",
    "sutherland_thermal_conductivity",
    "prandtl_number",
    "rms_molecular_speed",
    "mean_molecular_speed",
    "mean_free_path",
    "air_receiver_holdup_time",
    "air_receiver_volume_for_demand",
    "malus_transmitted_intensity",
    "malus_angle_for_intensity",
    "unpolarized_transmitted_intensity",
    "adiabatic_mixing_temperature",
    "adiabatic_mixing_humidity_ratio",
    "coil_bypass_factor",
    "cooling_coil_load",
    "evaporative_cooler_effectiveness",
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
    "second_law_efficiency",
    "refrigeration_effect",
    "compressor_work_of_compression",
    "refrigerant_mass_flow_rate",
    "cooling_tower_range",
    "cooling_tower_approach",
    "cooling_tower_effectiveness",
    "coriolis_acceleration",
    "coriolis_parameter",
    "rossby_number",
    "conveyor_mass_flow",
    "belt_speed_for_capacity",
    "conveyor_lift_power",
    "drag_force",
    "jet_impact_force",
    "stokes_settling_velocity",
    "stokes_drag_force",
    "terminal_velocity",
    "drilling_material_removal_rate",
    "drilling_torque",
    "drilling_feed_for_torque_limit",
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
    "normal_shock_downstream_mach",
    "normal_shock_pressure_ratio",
    "normal_shock_stagnation_pressure_ratio",
    "prandtl_meyer_angle",
    "mach_angle",
    "maximum_turning_angle",
    "film_condensation_vertical_plate_coefficient",
    "film_condensation_horizontal_tube_coefficient",
    "condensation_rate",
    "apparent_power_three_phase",
    "conductor_resistance",
    "line_current_for_power",
    "motor_full_load_current",
    "motor_branch_circuit_ampacity",
    "motor_synchronous_speed",
    "motor_slip",
    "motor_locked_rotor_current",
    "power_factor_correction_kvar",
    "skin_depth",
    "three_phase_power",
    "transformer_full_load_current",
    "transformer_available_fault_current",
    "transformer_secondary_voltage",
    "transformer_secondary_current",
    "transformer_reflected_impedance",
    "transformer_efficiency",
    "transformer_maximum_efficiency_load_fraction",
    "transformer_voltage_regulation",
    "ground_rod_resistance",
    "parallel_ground_electrodes_resistance",
    "voltage_drop_single_phase",
    "voltage_drop_three_phase",
    "motional_emf",
    "faraday_induced_emf",
    "self_induced_emf",
    "electroplating_mass_deposited",
    "electroplating_deposition_thickness",
    "electroplating_time_for_thickness",
    "coulomb_force",
    "electric_field_point_charge",
    "electric_potential_point_charge",
    "battery_bank_capacity",
    "usable_battery_energy",
    "battery_backup_time",
    "battery_round_trip_efficiency",
    "battery_delivered_energy",
    "present_value",
    "future_value",
    "annuity_present_value",
    "annuity_future_value",
    "loan_payment",
    "simple_payback_period",
    "net_present_value",
    "benefit_cost_ratio",
    "straight_line_depreciation",
    "peukert_runtime",
    "peukert_effective_capacity",
    "peukert_exponent_from_two_rates",
    "extrusion_ratio",
    "extrusion_pressure",
    "extrusion_force",
    "fill_factor",
    "solar_cell_max_power",
    "solar_cell_efficiency",
    "solar_declination",
    "solar_altitude_at_noon",
    "air_mass",
    "pv_array_power",
    "pv_daily_energy",
    "pv_array_size_for_load",
    "pv_cell_temperature",
    "pv_temperature_derated_power",
    "flat_plate_collector_efficiency",
    "collector_useful_heat",
    "collector_stagnation_temperature",
    "hydro_net_head",
    "hydro_turbine_power",
    "hydro_flow_for_power",
    "ideal_gas_pressure",
    "ideal_gas_volume",
    "ideal_gas_moles",
    "hydraulic_pump_flow_rate",
    "hydraulic_motor_torque",
    "hydraulic_motor_speed",
    "hydraulic_press_transmitted_pressure",
    "hydraulic_press_output_force",
    "hydraulic_press_input_stroke",
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
    "helmholtz_resonator_frequency",
    "open_pipe_resonance_frequency",
    "closed_pipe_resonance_frequency",
    "doppler_shifted_frequency",
    "doppler_velocity_from_shift",
    "mach_cone_angle",
    "masonry_allowable_axial_stress",
    "masonry_allowable_flexural_stress",
    "masonry_column_axial_capacity",
    "masonry_combined_stress_ratio",
    "lap_joint_average_shear_stress",
    "cylindrical_bond_axial_capacity",
    "cylindrical_bond_torque_capacity",
    "free_space_path_loss",
    "received_power",
    "max_line_of_sight_range",
    "aperture_antenna_gain",
    "parabolic_beamwidth",
    "dish_diameter_for_gain",
    "shannon_capacity",
    "shannon_required_bandwidth",
    "nyquist_channel_capacity",
    "gibbs_free_energy_change",
    "equilibrium_constant",
    "vant_hoff_constant_ratio",
    "centripetal_acceleration",
    "centripetal_force",
    "maximum_cornering_speed",
    "noise_factor_from_figure",
    "cascade_noise_factor",
    "equivalent_noise_temperature",
    "reflection_coefficient",
    "voltage_standing_wave_ratio",
    "return_loss",
    "rectangular_waveguide_cutoff_frequency",
    "waveguide_guide_wavelength",
    "waveguide_phase_velocity",
    "plasma_frequency",
    "debye_length",
    "plasma_parameter",
    "cyclotron_frequency",
    "larmor_radius",
    "cyclotron_mass_from_frequency",
    "quantization_snr",
    "quantization_step",
    "effective_number_of_bits",
    "ohms_law_voltage",
    "resistive_power",
    "parallel_resistance",
    "arrhenius_rate_constant",
    "arrhenius_rate_ratio",
    "arrhenius_activation_energy",
    "barometric_altitude",
    "barometric_pressure",
    "scale_height",
    "bohr_energy_level",
    "bohr_orbit_radius",
    "rydberg_transition_wavelength",
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
    "peening_impact_coverage_rate",
    "peening_coverage",
    "peening_time_for_coverage",
    "cup_blank_diameter",
    "draw_ratio",
    "deep_draw_force",
    "springback_factor",
    "sprung_bend_radius",
    "sprung_bend_angle",
    "RivetedJointStrength",
    "riveted_joint_efficiency",
    "minimum_curve_radius",
    "ideal_superelevation_rate",
    "banked_curve_max_speed",
    "braking_distance",
    "perception_reaction_distance",
    "stopping_sight_distance",
    "rocket_exhaust_velocity",
    "rocket_thrust",
    "rocket_specific_impulse",
    "rocket_delta_v",
    "rocket_propellant_mass_fraction",
    "characteristic_velocity",
    "thrust_coefficient",
    "thrust_from_coefficient",
    "maximum_draft",
    "rolling_contact_length",
    "rolling_force",
    "hover_induced_velocity",
    "ideal_hover_power",
    "figure_of_merit",
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
    "spot_weld_heat_generated",
    "spot_weld_current_for_heat",
    "spot_weld_nugget_melting_energy",
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
    "shear_spinning_wall_thickness",
    "shear_spinning_reduction",
    "shear_spinning_half_angle_for_thickness",
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
    "nucleate_boiling_heat_flux",
    "nucleate_boiling_excess_temperature",
    "critical_heat_flux",
    "laminar_boundary_layer_thickness",
    "laminar_skin_friction_coefficient",
    "laminar_plate_drag_coefficient",
    "seebeck_voltage",
    "peltier_cooling_rate",
    "thermoelectric_max_temperature_difference",
    "gauge_strain_from_resistance",
    "wheatstone_bridge_output",
    "strain_from_bridge_output",
    "piezoelectric_charge",
    "piezoelectric_open_circuit_voltage",
    "piezoelectric_force_from_charge",
    "decay_constant_from_half_life",
    "remaining_activity",
    "time_for_activity_decay",
    "photon_momentum",
    "radiation_pressure",
    "radiation_force",
    "radiation_transmission_fraction",
    "half_value_layer",
    "shield_thickness_for_transmission",
    "mass_energy",
    "mass_from_energy",
    "binding_energy_per_nucleon",
    "schmidt_number",
    "sherwood_number",
    "lewis_number",
    "stanton_number",
    "colburn_j_factor",
    "chilton_colburn_mass_transfer_coefficient",
    "linear_momentum",
    "impulse",
    "average_impact_force",
    "compton_wavelength_shift",
    "compton_scattered_wavelength",
    "compton_electron_energy",
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
    "sensible_heat",
    "latent_heat",
    "mixing_equilibrium_temperature",
    "CamMotion",
    "cam_follower_motion",
    "cam_pressure_angle",
    "cam_base_circle_for_pressure_angle",
    "washburn_capillary_pressure",
    "washburn_penetration_length",
    "washburn_penetration_time",
    "casting_modulus",
    "chvorinov_solidification_time",
    "riser_modulus_for_feeding",
    "centrifugal_g_factor",
    "centrifugal_speed_for_g_factor",
    "centrifugal_wall_pressure",
    "centrifugal_sedimentation_velocity",
    "centrifuge_settling_time",
    "gating_fill_time",
    "gating_choke_area",
    "sprue_taper_ratio",
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
    "fan_total_pressure",
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
    "broaching_teeth_in_cut",
    "broaching_cutting_force",
    "broaching_pull_capacity",
    "wind_velocity_pressure",
    "wind_design_pressure",
    "beverloo_discharge_rate",
    "beverloo_orifice_for_rate",
    "conical_stockpile_volume",
    "screw_conveyor_volumetric_capacity",
    "screw_conveyor_mass_capacity",
    "screw_conveyor_speed_for_capacity",
    "components_cladding_net_pressure",
    "seismic_response_coefficient",
    "seismic_response_coefficient_upper_limit",
    "approximate_fundamental_period",
    "seismic_base_shear",
    "seismic_vertical_force_distribution",
    "seismic_diaphragm_force",
    "seismic_torsional_amplification_factor",
    "seismic_accidental_torsional_moment",
    "seismic_design_story_drift",
    "allowable_story_drift",
    "seismic_stability_coefficient",
    "seismic_stability_coefficient_limit",
    "seismic_load_effect",
    "flat_roof_snow_load",
    "sloped_roof_snow_load",
    "snow_density",
    "leeward_snow_drift_height",
    "reduced_live_load",
    "rain_load",
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
    "equivalence_ratio",
    "equivalence_ratio_from_excess_air",
    "siegert_dry_flue_gas_loss",
    "combustion_efficiency",
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
    "step_response_percent_overshoot",
    "step_response_settling_time",
    "step_response_peak_time",
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
    "floor_vibration_peak_acceleration_ratio",
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
    "ecm_material_removal_rate",
    "ecm_feed_rate",
    "ecm_equilibrium_gap",
    "edm_discharge_energy",
    "edm_duty_factor",
    "edm_material_removal_rate",
    "bulk_modulus_from_youngs_poisson",
    "lame_first_parameter",
    "youngs_modulus_from_bulk_shear",
    "bar_wave_speed",
    "shear_wave_speed",
    "bulk_longitudinal_wave_speed",
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
    "forging_true_strain",
    "flow_stress_power_law",
    "open_die_forging_load",
    "point_source_illuminance",
    "lumen_method_illuminance",
    "lumen_method_luminaire_count",
    "room_cavity_ratio",
    "lighting_power_density",
    "luminous_efficacy",
    "luminous_flux_from_power",
    "luminous_efficiency",
    "telescope_angular_magnification",
    "magnifier_angular_magnification",
    "microscope_magnification",
    "thin_lens_image_distance",
    "lens_transverse_magnification",
    "diffraction_limited_angular_resolution",
    "lens_f_number",
    "diffraction_limited_spot_diameter",
    "hyperfocal_distance",
    "snell_refraction_angle",
    "critical_angle",
    "fiber_numerical_aperture",
    "lensmaker_focal_length",
    "lens_power",
    "combined_thin_lens_focal_length",
    "chromatic_dispersion_broadening",
    "dispersion_limited_bit_rate",
    "dispersion_limited_distance",
    "photon_energy",
    "photon_wavelength_from_energy",
    "photon_flux",
    "absorbance",
    "transmittance_from_absorbance",
    "concentration_from_absorbance",
    "photoelectric_max_kinetic_energy",
    "photoelectric_threshold_frequency",
    "de_broglie_wavelength",
    "minimum_momentum_uncertainty",
    "minimum_position_uncertainty",
    "minimum_energy_uncertainty",
    "lorentz_factor",
    "time_dilation",
    "relativistic_kinetic_energy",
    "length_contraction",
    "relativistic_momentum",
    "relativistic_doppler_frequency",
    "weibull_reliability",
    "weibull_hazard_rate",
    "weibull_mean_life",
    "radar_doppler_shift",
    "radial_velocity_from_doppler",
    "max_unambiguous_velocity",
    "max_unambiguous_range",
    "radar_received_power",
    "radar_max_range",
    "SUDDENLY_APPLIED_FACTOR",
    "impact_factor",
    "impact_stress",
    "horizontal_impact_force",
    "injection_clamp_force",
    "max_projected_area_for_clamp",
    "injection_cooling_time",
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
    "grinding_specific_removal_rate",
    "grinding_equivalent_chip_thickness",
    "grinding_specific_energy",
    "gyroscopic_spin_angular_momentum",
    "gyroscopic_precession_rate",
    "gyroscopic_reaction_moment",
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
    "laser_specific_removal_energy",
    "laser_cutting_speed",
    "laser_max_cut_thickness",
    "living_hinge_fold_strain",
    "living_hinge_web_length_for_strain",
    "asce7_lrfd_factored_load",
    "asce7_asd_factored_load",
    "cutting_speed",
    "spindle_speed_for_cutting_speed",
    "material_removal_rate",
    "taylor_tool_life",
    "theoretical_surface_roughness",
    "peak_to_valley_roughness",
    "feed_for_surface_roughness",
    "solenoid_magnetic_field",
    "magnetic_pressure",
    "electromagnet_holding_force",
    "magnetomotive_force",
    "magnetic_reluctance",
    "magnetic_flux",
    "hall_voltage",
    "hall_flux_density_from_voltage",
    "hall_carrier_density",
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
    "rolling_resistance_force",
    "grade_resistance_force",
    "tractive_power",
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
    "carnot_efficiency",
    "heat_engine_second_law_efficiency",
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
    "process_capability_index",
    "process_capability_ratio",
    "expected_defect_rate_ppm",
    "projectile_range",
    "projectile_max_height",
    "projectile_time_of_flight",
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
    "compressor_isentropic_efficiency",
    "turbine_isentropic_efficiency",
    "compressor_actual_discharge_temperature",
    "compressor_polytropic_efficiency",
    "compressor_isentropic_from_polytropic",
    "turbine_isentropic_from_polytropic",
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
    "nernst_potential",
    "nernst_slope",
    "nernst_reaction_quotient",
    "osmotic_pressure",
    "freezing_point_depression",
    "boiling_point_elevation",
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
    "fin_effectiveness",
    "fin_thermal_resistance",
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
    "overall_heat_transfer_coefficient",
    "fouling_factor_from_coefficients",
    "cleanliness_factor",
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
    "radiation_two_surface_exchange",
    "radiation_heat_transfer_coefficient",
    "crossed_strings_view_factor",
    "view_factor_reciprocity",
    "radiation_shield_reduction_factor",
    "wien_peak_wavelength",
    "wien_temperature_from_peak",
    "thermoforming_areal_draw_ratio",
    "thermoforming_average_wall_thickness",
    "thermoforming_sheet_gauge_for_wall",
    "archard_wear_volume",
    "archard_wear_depth",
    "sliding_distance_for_wear_depth",
    "sliding_contact_pv",
    "breathing_zone_outdoor_airflow",
    "air_changes_per_hour",
    "airflow_for_air_changes",
    "dilution_airflow",
    "vortex_shedding_frequency",
    "lock_in_velocity",
    "reduced_velocity",
    "wave_speed",
    "wavelength_from_frequency",
    "frequency_from_wavelength",
    "FILLET_THROAT_FACTOR",
    "fillet_weld_throat_stress",
    "fillet_weld_leg_for_load",
    "fillet_weld_design_strength",
    "fillet_weld_directional_strength",
    "weld_base_metal_shear_strength",
    "eccentric_weld_group_peak_stress",
    "weld_arc_power",
    "weld_heat_input",
    "weld_travel_speed_for_heat_input",
    "wire_rope_bending_stress",
    "minimum_sheave_diameter_for_bending_stress",
    "wire_rope_equivalent_bending_load",
    "wire_rope_sheave_pressure",
    "kinetic_energy",
    "gravitational_potential_energy",
    "work_done",
    "drum_working_radius",
    "drum_line_pull",
    "drum_rope_capacity",
    "BETZ_LIMIT",
    "wind_power_density",
    "wind_turbine_power",
    "wind_turbine_tip_speed_ratio",
    "capacity_factor",
    "lift_force",
    "induced_drag_coefficient",
    "stall_speed",
    "wire_drawing_stress",
    "wire_drawing_force",
    "wire_drawing_max_reduction",
]
