# Assembly & Robotics Specification (delta)

## ADDED Requirements

### Requirement: Joints are declared on interfaces

A typed joint (rigid, revolute, linear, cylindrical, ball) SHALL be declarable on a
connection between two interfaces, with its axis taken from the interface frames and its
declared range. A joint whose axis the two interfaces do not define, such as a revolute
joint on two mounting faces, SHALL be refused naming the connection.

#### Scenario: A pivot on a pin and hole

- **WHEN** a product declares a revolute joint on the connection of `arm.pivot` (pin) and
  `base.pivot` (hole) with a range of 0 to 90 degrees
- **THEN** the joint's axis is the pin's, and the range is carried into the swept-volume
  keepout and the robotics exports
