# Service-Life Planning Specification

## Purpose

The inspection or replacement each life-limited check implies, derived from the life the
check computed and an interval rule the document declares, with the spare it needs and
an honest list of the items no check gave a life. The plan is a schedule, not evidence:
nothing performed reports not evaluated, and only a recorded task is a record.

## ADDED Requirements

### Requirement: Maintenance items derive from life-limited checks and declared rules

The system SHALL derive, from every check that publishes a typed life quantity, a
maintenance item naming the item path, the driving check and its life, the task type
(time-directed replacement or restoration, on-condition inspection, failure-finding, or
accepted run-to-failure), the interval, and the interval rule that produced it with its
source. Interval rules SHALL be declared by the document with a citation; the system
MUST NOT apply a default rule, life factor or reliability target. A life with no
applicable declared rule SHALL appear as an item with its life and "interval not set".

#### Scenario: A bearing with a declared rule

- **WHEN** a gearbox bearing's rating life is 23,000 h at 90% reliability and the document
  declares "replace at 50% of rating life" with its source
- **THEN** the plan carries a time-directed replacement at 11,500 h naming the bearing's
  path, the check, the life and the rule

#### Scenario: A life without a rule

- **WHEN** a seal's compression-set life is computed and no interval rule covers seals
- **THEN** the plan lists the seal with its life and "interval not set", and the schedule
  does not read as complete

### Requirement: On-condition tasks are held to a declared P-F interval

An on-condition inspection item SHALL carry the declared P-F interval for the failure
mode it watches, with its source, and its inspection interval SHALL be held to the
declared fraction of that interval. An on-condition item with no declared P-F interval
SHALL be listed with "interval not set" naming the P-F interval it needs.

#### Scenario: Wear inspection

- **WHEN** a wear screen reports an allowance consumed in 4,000 h, the document declares a
  P-F interval of 800 h for measurable wear and an inspection fraction of one half
- **THEN** the plan carries an on-condition inspection every 400 h naming the P-F interval
  and its source

### Requirement: Spares follow the plan into the buy list

The system SHALL list the replaceable items the plan implies, each with the quantity over
the declared service life and the BOM line it corresponds to, and SHALL make the list
available to the release package as a spares list, labeled as derived from the
maintenance plan and from declared rules.

#### Scenario: Spares over ten years

- **WHEN** a product declares a ten-year service life and the plan replaces a bearing
  every 11,500 h of a declared 4,000 h per year duty
- **THEN** the spares list carries three of that bearing with the arithmetic shown

### Requirement: Items with no life basis are named

The plan SHALL list, by name and with a count, every item in the product that no
life-limited check covers, beside the count of items with a plan entry, so that a plan is
never presented as covering a product it covers in part.

#### Scenario: Three of thirty

- **WHEN** a thirty-item product has life-limited checks on three items
- **THEN** the plan states three planned and twenty-seven without a life basis, naming them

### Requirement: A plan is not a record until tasks are performed

Plan items SHALL carry no result. A user SHALL be able to record a performed task — date,
performer, and any measured condition with its unit — against an item, and a measured
condition SHALL be available to the model-credibility correlation as a referent for the
driving check. A plan with no recorded tasks SHALL render as planned, never as
maintained, and a recorded task MUST NOT alter any analytical verdict.

#### Scenario: A measured wear depth

- **WHEN** an inspection records 0.3 mm of wear at 420 h against a predicted allowance
  consumption
- **THEN** the task shows as performed with its value, the correlation receives the
  measured value, and the wear check's verdict is unchanged
