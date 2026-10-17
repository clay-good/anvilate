# Interface Contracts Specification

## Purpose

What each item offers to the rest of a product, stated once, typed, and checked wherever
it meets something else.

## ADDED Requirements

### Requirement: Items publish named, typed interfaces

Every product item SHALL be able to publish interfaces. An interface SHALL have a name
unique within its item, a kind from a closed vocabulary, a frame (origin, normal, and spin
reference), and the parameters its kind requires. An interface on a part SHALL be bound to
a tagged feature of that part, and its frame and parameters SHALL be read from the built
feature, not restated.

#### Scenario: A bracket offers its motor face

- **WHEN** a motor bracket publishes `motor_mount` as a bolt pattern bound to its tagged
  four-hole pattern
- **THEN** the interface's frame, pitch, hole count and hole size are read from the built
  bracket, and a change to the holes changes the interface

#### Scenario: An interface bound to nothing

- **WHEN** an interface names a feature tag the part does not have
- **THEN** the item is refused naming the interface and the missing tag

### Requirement: The interface vocabulary is closed and each kind lists its parameters

The interface kinds SHALL include at least: mounting face, bolt pattern, tapped pattern,
shaft, bore, pin and hole, rail and carriage, keyed shaft, and connector envelope. Each
kind SHALL state its required parameters and units. An interface missing a required
parameter SHALL be refused naming it; an unknown kind SHALL be refused with the nearest
known kinds.

#### Scenario: A shaft interface without a diameter

- **WHEN** a placeholder offers a `shaft` interface with no diameter
- **THEN** the placeholder is refused naming `diameter` and its unit

### Requirement: Interfaces are connected by name, and placement follows

A product SHALL be able to declare a connection between two interfaces by item path and
interface name. A connection SHALL place the item it names second against the first by
the frames of the two interfaces, using the existing mates underneath. A connection that
leaves an item free or contradicts another SHALL be refused as the mates are.

#### Scenario: Motor onto bracket by interface names

- **WHEN** a product connects `bracket.motor_mount` to `motor.flange`
- **THEN** the motor is placed on the bracket with its pilot and holes aligned, and no
  feature tag of either item appears in the product document

### Requirement: A compatibility table decides which kinds may meet

A published table SHALL list, for each pair of kinds that may connect, the parameters that
must agree and the checks the pairing runs. A connection between kinds the table does not
pair SHALL be refused before geometry is built, naming both kinds and the kinds the first
interface may meet.

#### Scenario: A shaft offered to a bolt pattern

- **WHEN** a product connects a shaft interface to a bolt-pattern interface
- **THEN** the product is refused, naming both kinds and that a shaft meets a bore or a
  keyed hub

### Requirement: Each connection runs the checks its pairing owns

Every connection SHALL run the checks its pairing lists and report each as an entry on
the card of the product that declares the connection, naming both interfaces by path.
Where the combination layer already implements a check (pattern agreement, clearance
class, bolt engagement, shaft and bore fit, key seating, bolted joint), the connection
SHALL reuse it.

#### Scenario: A flange drawn to an old datasheet

- **WHEN** a motor component's flange pattern is 47.14 mm and the bracket's is 50 mm
- **THEN** the connection's pattern-agreement entry fails, naming both interfaces and the
  difference, through the same check a combination runs

### Requirement: Every interface is connected or declared open

A product build SHALL account for every interface of every item placed: connected, or
declared open with a reason. An interface that is neither SHALL be reported on the
product's card as unconnected. A kind that allows one partner and has two SHALL be
reported naming the three interfaces.

#### Scenario: A mounting face nobody used

- **WHEN** a product places a fan whose `mount` interface is never connected
- **THEN** the card reports `fan.mount` unconnected, and a declared open with the reason
  "held by the grille" clears it

### Requirement: Every build writes an interface control table

Every product build SHALL write an interface control table: one row per connection with
both paths, both kinds, the agreeing parameters on each side, the owner of each item, the
checks run and their verdicts, and one row per declared-open interface with its reason. The
table SHALL be written as CSV and as a section of the product report.

#### Scenario: A table a reviewer can read

- **WHEN** a linear stage is built
- **THEN** its interface table lists every connection with both sides' values and
  verdicts, and every open interface with its reason
