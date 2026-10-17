# Industry Profiles Specification

## Purpose

One declaration that configures factors, allowable rules, mandatory checks, records and
drawing conventions for the way an industry or company works, with every rule it adds
attributed to it.

## ADDED Requirements

### Requirement: A profile is a cited, declared bundle of rules

A profile SHALL declare: a factor set; allowable-basis rules by structural class;
required checks by item class; default material needs; required artifacts; and a drawing
and tolerancing standard. Every rule SHALL cite its source or be labeled a practice-based
default. A profile SHALL be data, validated against a published schema.

#### Scenario: A profile without sources

- **WHEN** a user loads a profile whose required-check rule has neither a source nor a
  practice-default label
- **THEN** the profile is refused naming the rule

### Requirement: Shipped profiles cover the major industries

The library SHALL ship profiles for: spaceflight hardware, transport aircraft,
automotive, medical devices, industrial machinery, consumer products, and general. The
general profile SHALL reproduce today's behavior. Each shipped profile's values SHALL be
read from public documents, and each SHALL say which of its rules await user-supplied
values from paid standards.

#### Scenario: Binding the spaceflight profile

- **WHEN** a product binds the spaceflight profile
- **THEN** its margin report uses the profile's factor set, and random vibration and
  outgassing become required for items the profile classes as flight boxes

#### Scenario: General is unchanged

- **WHEN** an existing example binds the general profile
- **THEN** its card is identical to the card it produced before profiles existed

### Requirement: Required checks appear even when nothing triggered them

For each item, every check the bound profile requires for the item's class SHALL appear
on its card. A required check whose inputs are missing SHALL be not evaluated, naming the
inputs. A required check that the installed version does not implement SHALL be shown as
not available, and SHALL NOT be omitted.

#### Scenario: A box with no vibration input

- **WHEN** an avionics box under the transport-aircraft profile declares no vibration
  environment
- **THEN** its card shows random vibration as not evaluated, naming the input PSD it
  needs

### Requirement: Every profile rule is attributed on the card

Each entry, factor or requirement added or changed by a profile SHALL name the profile
and the rule that produced it. A user SHALL be able to list everything a profile changed
relative to the general profile for a given product.

#### Scenario: What did the profile do

- **WHEN** an engineer asks what the automotive profile changed on a bracket's card
- **THEN** they get the added checks, the changed factors and the required artifacts,
  each naming its rule

### Requirement: Company profiles layer on industry profiles

A user SHALL be able to declare a profile that extends another, adding rules and
overriding values with their sources. Where an override relaxes a rule of the profile it
extends, the card SHALL report the relaxation, naming both values and the override's
source.

#### Scenario: A company relaxes a factor

- **WHEN** a company profile lowers an ultimate factor below its parent's value
- **THEN** every affected margin row reports the relaxation and its source

### Requirement: A profile is never a compliance claim

Every card and report produced under a profile SHALL name the profile and its version and
state that it is a screening configuration, not a certification or a regulatory
determination. No profile SHALL be named as satisfying a regulation.

#### Scenario: The report header

- **WHEN** a medical-device product's report is generated
- **THEN** its header names the profile and version, and states that compliance is
  decided by the user's quality system and regulator
