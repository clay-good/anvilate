# Change: Below-the-hook lifting device pack (ASME BTH-1)

## Why

Every custom lifter — spreader beam, lifting beam, plate clamp frame — legally needs
BTH-1-compliant design under OSHA/ASME B30.20, and the practice is near-totally
spreadsheet-bound: sample calcs circulate as Excel (e.g.
https://www.pveng.com/wp-content/uploads/2016/06/ASME_SpreaderBar_Calcs.pdf), commercial
coverage is a niche FEA add-on (SDC Verifier), and no open-source implementation exists at
all (verified July 2026). Anvilate already ships the verified primitives — lug limit
states, spreader-beam buckling capstone, rigging slings, weld checks — so this pack is
mostly composing existing cited functions under BTH-1's design factors. It is the best
effort-to-value vertical surveyed: total OSS gap, closed-form throughout, and the
competition is the in-house spreadsheet.

## What Changes

- One ADDED requirement to `discipline-packs`: a below-the-hook lifting device pack —
  Design Category and Service Class as typed spec inputs resolving the design factor,
  member checks in BTH-1's allowable-stress forms, pin-connected plate checks composing
  the existing lug limit states under BTH-1 factors, service-class-driven fatigue
  screening, and rated-load documentation.
- Follows every existing pack convention: clause citations, user-supplied allowables
  doctrine, optional/lazy/invisible when disabled.

## Impact

- Affected specs: `discipline-packs` (one ADDED requirement; existing requirements
  including the structural pack's BTH-1 lug limit states are unchanged — this pack
  composes them at device level rather than re-specifying them).
- Affected code (when implemented): a `lifting` pack module composing existing
  `analysis` functions (lug, beam, column, weld, rigging, spreader-beam buckling) under
  BTH-1 design factors; no new analysis primitives expected.
- Interacts with `add-verification-test-plans` (a lifter's proof-test emission) without
  depending on it.
