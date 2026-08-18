# Tasks: Below-the-hook lifting device pack

## 1. Contracts

- [x] 1.1 Typed Design Category / Service Class inputs resolving design factor + fatigue
      obligation, with citations
- [x] 1.2 Lifter device model (rated load, geometry, members, pin plates)

## 2. Implementation

- [x] 2.1 Member checks in BTH-1 allowable-stress form composing existing beam/column/
      combined-stress functions
- [x] 2.2 Pin-connected plate checks composing existing lug limit states under BTH-1
      factors
- [x] 2.3 Service-class fatigue screen composing the existing fatigue module
- [x] 2.4 Rated-load / category / class propagation to evidence bundle and title block

## 3. Tests

- [x] 3.1 Worked-example anchoring against published BTH-1 sample calculations
      (re-derived, never redistributed)
- [x] 3.2 Category A vs B factor difference visible in margins
- [x] 3.3 Missing cycle data → fatigue "not evaluated"

## 4. Docs & examples

- [x] 4.1 Example: spreader beam from prose to validated BTH-1 scorecard
- [x] 4.2 Explanation page: what BTH-1 screening covers and what stamped design still
      requires

## Scope as shipped

Shipped: the typed Design Category and Service Class (1.1), the §3-2/§3-3 allowables they
resolve, the member and fatigue screens, the worked example and the doc page. The
category is now a typed input that travels into every scorecard detail, which was the
whole point — a BTH-1 margin without its category cannot be checked.

Also shipped: the device model (1.2), the member and pin-plate checks under BTH-1
factors (2.1 / 2.2) and the rated-load/category/class propagation (2.4).

The API-shape question the earlier note left open was resolved by **routing, not
wrapping**. `LifterMemberStress` carries a `BTH1LimitState` rather than an allowable or
a `required_safety_factor`, so the design factor reaches every check from the device's
declared category through the standard's own routing; `screen_lifter_device` refuses
allowables built for a different category outright. Stresses still come from the
existing beam/column/combined-stress functions — the pack screens them, it does not
re-derive them.

Two things this surfaced that were worth the chunk on their own:

- **`self_weight` is a required field with no default.** BTH-1 §3-1.2 has the design
  consider the lifter's own weight, and the worked example shows an 8% load increase
  turning a 1.06 pass into a 0.98 fail. A default of zero would have made the most
  common omission in lifter design invisible.
- **The generic `screen_lifting_lug` is not the BTH-1 check.** It screens both lug
  limit states against *yield*; BTH-1 puts the net section against *ultimate* over
  1.20·N_d. `bth1_pin_plate_scorecard` is the BTH-1 form, and the doc page says which
  to reach for.

2.4's "title block" half is propagation into the scorecard: the rated load, design load,
category and service class lead every device screen as an identification entry. There is
no drawing title block to propagate into yet — drawing generation is unbuilt — so that
half lands when it exists.

Still open:

- **3.1's published BTH-1 sample calculations.** The allowables are anchored on their own
  definitions and on the exact 2/3 category ratio instead, which pins each coefficient
  independently. A published sample calc would add an end-to-end anchor and is worth
  doing when one can be re-derived rather than redistributed.
