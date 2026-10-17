# Change: Durability and sealing — duty cycles, joints that loosen, seals that leak, plastics that creep

## Why

Vehicles, off-highway machines, appliances and consumer products rarely fail on day one.
They fail at 80,000 km, after a summer in a hot car, or after the hundredth drop. The
checks that catch this are routine in automotive, Tier 1 and consumer-product
engineering. Anvilate has the building blocks but not the routine:

| The routine | What Anvilate has today | What is missing |
| --- | --- | --- |
| Fatigue over a duty cycle: count the cycles in a load history or duty cycle, then sum the damage over the vehicle's life | Fatigue screens that take a stress range | No way to count cycles from a load history, and no duty-cycle declaration |
| Bolted joints that keep their clamp: embedding loss and where the load enters the joint, as the common automotive method treats them | Preload checks | Embedding loss and load introduction |
| Seals that stay sealed: an O-ring squeezed enough, not extruded through the gap at pressure, not set at temperature | Squeeze, gland fill and stretch | Pressure, temperature and fluid. Sealing failures dominate electric-vehicle battery and e-drive warranty |
| Plastics that hold: a snap-fit or boss that still retains after 1,000 hours at 85 °C | Strain at assembly | Creep and stress relaxation |
| A structure that does not resonate: first modes kept clear of the excitation (wheel and engine orders, motor whine) | Modal estimates | Separation margins against declared excitation bands |
| A product that survives a drop: impact energy, peak deceleration, the load on what is mounted inside | Half-sine shock amplification | Drop-height screens |

All of these are closed-form screens that engineers run today in spreadsheets of
uncertain provenance.

## What Changes

New screens in `analysis-library`, under the existing contract:

| Screen | Content |
| --- | --- |
| Duty cycles and rainflow | A typed duty cycle (named events, each with a load history or block and its count over the declared life). Cycles counted by rainflow (ASTM E1049). Damage summed by Miner's rule with the existing stress-life and strain-life curves. Damage reported per event, so the engineer sees which event drives life. |
| Joint loss | Embedding loss and load-introduction factor in preloaded joints. Values from paid method tables are entered by the user with a citation. |
| Seals | O-ring extrusion gap against pressure and hardness limits the user cites, squeeze across the temperature range including thermal growth of seal and gland, compression set over declared life, and fluid compatibility as a declared attribute. |
| Creep and relaxation | Snap-fit retention, boss pull-out and press-fit retention after a declared time at temperature, from creep-modulus records. |
| Modal separation | Estimated first modes against declared excitation bands, reported as a separation ratio against the declared target. |
| Drop and impact | Impact energy from height and mass. Peak deceleration from a declared cushion or contact stiffness. The load on each mounted item. |

## Impact

- Delta: `analysis-library` (ADDED).
- Builds on the existing fatigue, fastener, O-ring, snap-fit, dynamics and thermal
  modules. Uses polymer and elastomer records from `add-material-compliance`, and
  preloaded-joint screening from `add-structural-hand-methods`.
- Excitation bands, separation targets and duty cycles are always the user's: they are
  OEM-internal, and Anvilate does not invent them.
- Explicitly out:
  - Multiaxial critical-plane fatigue.
  - Crash.
  - Acoustic prediction.
  - Mold-flow fiber-orientation effects. A declared knockdown is accepted with its
    source.
