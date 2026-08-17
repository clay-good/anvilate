# Tasks: Below-the-hook lifting device pack

## 1. Contracts

- [x] 1.1 Typed Design Category / Service Class inputs resolving design factor + fatigue
      obligation, with citations
- [ ] 1.2 Lifter device model (rated load, geometry, members, pin plates)

## 2. Implementation

- [ ] 2.1 Member checks in BTH-1 allowable-stress form composing existing beam/column/
      combined-stress functions
- [ ] 2.2 Pin-connected plate checks composing existing lug limit states under BTH-1
      factors
- [x] 2.3 Service-class fatigue screen composing the existing fatigue module
- [ ] 2.4 Rated-load / category / class propagation to evidence bundle and title block

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

Not yet shipped, and left open rather than half-done:

- **1.2 / 2.1 / 2.2, the device model.** A typed `LifterDevice` composing beam, column
  and pin-plate checks at device level. The primitives it would compose all exist
  (`screen_lifting_lug`, `screen_beam_member`, `screen_beam_column`) and each already
  takes a `required_safety_factor`; wiring them to `DesignCategory.design_factor`
  is the remaining work, along with deciding whether the pack re-screens through them or
  wraps them. That is an API-shape decision, not arithmetic.
- **2.4, propagation to the evidence bundle and title block.** Depends on the device
  model above.
- **3.1's published BTH-1 sample calculations.** The allowables are anchored on their own
  definitions and on the exact 2/3 category ratio instead, which pins each coefficient
  independently. A published sample calc would add an end-to-end anchor and is worth
  doing when one can be re-derived rather than redistributed.
