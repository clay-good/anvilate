# Tasks: Service-life planning

Builds on the outcome records in `src/anvilate/verification.py` and the life-bearing
screens such as `src/anvilate/analysis/bearing.py`.

## 1. Life quantities

- [ ] 1.1 Typed life quantity (hours, cycles, distance, time at temperature) with basis
      and reliability where the method states one
- [ ] 1.2 Every check that computes a life, a rate or a retention publishes one; CI census
      over the library

## 2. The plan

- [ ] 2.1 Interval rules as declared, cited data: replace-at-fraction-of-life,
      on-condition with P-F interval and fraction, failure-finding, run-to-failure
- [ ] 2.2 Maintenance items derived deterministically from life-limited checks; "interval
      not set" where no rule is declared
- [ ] 2.3 Spares and consumables with quantities over the declared service life; into
      the release package buy list
- [ ] 2.4 Coverage: items with no life basis listed by name with a count

## 3. Execution and rendering

- [ ] 3.1 Performed-task records; measured condition to correlation
- [ ] 3.2 Schedule table as CSV, XLSX and a report section
- [ ] 3.3 Worked example on the conveyor bearing-life example
      (`examples/conveyor_bearing_life.py`); a docs page for service-life planning
