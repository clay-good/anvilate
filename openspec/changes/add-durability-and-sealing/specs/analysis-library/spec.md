# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Duty cycles are declared as events over a life

A Design Spec SHALL be able to declare a duty cycle: a declared life (hours, distance or
cycles) and named events, each with a load-time history or a block of ranges and its
count per life. Each event SHALL carry its source. A fatigue check over a duty cycle SHALL
report damage per event and in total.

#### Scenario: Which event drives life

- **WHEN** a suspension bracket's duty cycle has pothole, cornering and braking events
- **THEN** the fatigue entry reports total damage and each event's share, naming the
  event with the largest share

### Requirement: Load histories are counted by rainflow

A load-time history SHALL be reduced to cycles by rainflow counting per ASTM E1049, with
residual half-cycles reported. Damage SHALL be summed by Miner's rule over the counted
cycles with the declared mean-stress correction. A history shorter than three reversals
SHALL be refused naming the event.

#### Scenario: A measured road-load trace

- **WHEN** an event declares a measured strain history
- **THEN** the screen reports the cycle count, the range histogram, the residual, and the
  damage per pass

### Requirement: Preloaded joints include embedding loss and load introduction

A preloaded-joint screen SHALL subtract an embedding loss computed from the declared
number of interfaces and their surface condition. It SHALL apply a declared
load-introduction factor to the joint's load factor. Values taken from paid method tables
SHALL be entered by the user with their citation and SHALL NOT be bundled.

#### Scenario: Four interfaces in a stack

- **WHEN** a joint clamps a bracket, a spacer and a plate, with four interfaces
- **THEN** the screen reports the embedding loss and the residual minimum preload after
  it

### Requirement: Seals are screened across pressure, temperature and life

An O-ring screen SHALL check squeeze and gland fill at the declared temperature extremes,
including thermal growth of seal and gland. It SHALL check the extrusion gap against the
user's cited pressure-and-hardness limit, and the compression set over the declared life
from the elastomer record. A fluid without a declared compatibility attribute SHALL be
not evaluated.

#### Scenario: Squeeze lost in the cold

- **WHEN** a seal's squeeze is 18% at 23 °C and the declared minimum temperature is
  −40 °C
- **THEN** the screen reports squeeze at −40 °C and fails if it falls below the minimum

#### Scenario: Extrusion at pressure

- **WHEN** a 70-durometer O-ring sees 10 MPa with a diametral gap above the user's cited
  limit
- **THEN** the extrusion check fails, naming the gap, the limit and its source

### Requirement: Plastic retention is screened after time at temperature

Snap-fit retention, boss pull-out and press-fit retention SHALL be screenable after a
declared time at a declared temperature, using creep-modulus or relaxation data from the
material record at that temperature and time. Without such data the check SHALL be not
evaluated, and SHALL NOT extrapolate.

#### Scenario: A clip after a hot summer

- **WHEN** a glass-filled clip declares 1,000 hours at 85 °C
- **THEN** the screen reports retention force at end of life from the creep modulus at
  that time and temperature

### Requirement: First modes are separated from declared excitation

A modal-separation screen SHALL compare each estimated natural frequency below a declared
ceiling with every declared excitation band. It SHALL report the separation ratio against
the declared target. Bands and targets SHALL be supplied by the user with their source.

#### Scenario: A mount near motor order

- **WHEN** a mount's first mode is 410 Hz and a declared motor-order band spans
  380–450 Hz
- **THEN** the screen fails, naming the mode, the band and the separation required

### Requirement: Drops are screened to the load on what is inside

A drop screen SHALL compute impact energy from mass and height. It SHALL estimate peak
deceleration from a declared cushion or contact stiffness, and report the resulting
inertial load on each mounted item with that item's check. Contact stiffness that is
estimated rather than measured SHALL be labeled.

#### Scenario: A handheld dropped from 1.2 m

- **WHEN** a 0.4 kg handheld is dropped 1.2 m onto a declared contact stiffness
- **THEN** the screen reports peak deceleration and the load on its internal board mounts,
  each checked
