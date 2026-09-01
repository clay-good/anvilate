# Tasks: The card answers every declaration

## 1. The declarations

- [x] 1.1 `constraints.max_mass`, `envelope` and `max_cost` — reported as unscreened, each
      naming what checking it would take. `min_safety_factor` is the one that is consumed,
      by the pack screen the element selects, and it is the one exemption.
- [x] 1.2 A declared `element_type` under acceptance criteria that do not demand T1, and
      declared `dimensions` under criteria that do not demand T2 — both reported rather than
      dropped. The tier is not forced: the acceptance criteria remain the contract.
- [x] 1.3 `acceptance.max_displacement` — reported, and the entry says where the limit does
      belong, since the pack screens take it from the element itself.
- [x] 1.4 `manufacturing.tolerance_class` — resolved on the card with near misses named,
      because the evidence bundle already resolved it and the two surfaces disagreed.
      `manufacturing.min_wall` — reported as unscreened.
- [x] 1.5 `combination_basis` — resolved rather than noted. The card names the governing
      combination, its factored demand and its clause; an unclassified force case makes it
      not evaluated, and a seismic basis with no S_DS lands on the card rather than raising.
- [x] 1.6 `geometric_tolerances` and an *imported* interface — both reported as unscreened
      with their reasons.

## 2. The gate

- [x] 2.1 A census over `DesignSpec`'s fields: each is either answered by a named check or
      listed as not being a claim about the part. A field that is neither fails the build.
- [x] 2.2 The same census one level down, over the two sub-models that carry bounds of their
      own — `AcceptanceCriteria` and `Manufacturing` — where three of the six findings were.
