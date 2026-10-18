# Tasks: Product screening

Depends on `add-product-structure`, `add-interface-contracts`, `add-purchased-components`;
reuses performance budgets, constraint topology, keepouts and the check dependency graph.

## 1. Load path

- [ ] 1.1 Product loads and accelerations on items and interfaces
      (loads on items are built; accelerations and loads on interfaces are not)
- [x] 1.2 Rigid-body equilibrium over determinate paths; connection forces with their
      equilibrium
- [x] 1.3 Indeterminacy named with redundant connections; downstream not evaluated;
      declared splits accepted with basis
- [ ] 1.4 Part screens fed interface loads as dependent entries
      (a caster's rating reads its load-path entry; other part screens do not yet)

## 2. Roll-ups

- [x] 2.1 Mass, center of mass, inertia per node with basis per contribution
- [ ] 2.2 Mass and CG limits through the budget mechanism; tip-over angle entry
      (a mass limit on predicted mass and the tip-over entry are built; the budget
      mechanism is not used yet)
- [x] 2.3 Cost roll-up; incomplete totals labeled

## 3. Geometry across items

- [x] 3.1 Pairwise minimum clearance with location; swept clearance over joint ranges
- [x] 3.2 Cross-item 1D tolerance chains (worst-case, RSS, seeded Monte Carlo)
- [x] 3.3 Thermal mismatch across dissimilar connections

## 4. Mechanism and economy

- [x] 4.1 Grübler–Kutzbach count with axis caveats
- [ ] 4.2 Part count, unique fasteners, tool count, merge candidates (advisory)
      (part count, bought designations and merge candidates are built; fasteners and tools
      wait on fastener hardware in products)
- [ ] 4.3 A docs page for product screening: each check, its method and its citation
- [x] 4.4 Mass maturity (estimated, calculated, measured) and growth allowance per
      maturity; budgets on predicted mass
