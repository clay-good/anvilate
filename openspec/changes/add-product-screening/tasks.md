# Tasks: Product screening

Depends on `add-product-structure`, `add-interface-contracts`, `add-purchased-components`;
reuses performance budgets, constraint topology, keepouts and the check dependency graph.

## 1. Load path

- [ ] 1.1 Product loads and accelerations on items and interfaces
- [ ] 1.2 Rigid-body equilibrium over determinate paths; connection forces with their
      equilibrium
- [ ] 1.3 Indeterminacy named with redundant connections; downstream not evaluated;
      declared splits accepted with basis
- [ ] 1.4 Part screens fed interface loads as dependent entries

## 2. Roll-ups

- [ ] 2.1 Mass, center of mass, inertia per node with basis per contribution
- [ ] 2.2 Mass and CG limits through the budget mechanism; tip-over angle entry
- [ ] 2.3 Cost roll-up; incomplete totals labeled

## 3. Geometry across items

- [ ] 3.1 Pairwise minimum clearance with location; swept clearance over joint ranges
- [ ] 3.2 Cross-item 1D tolerance chains (worst-case, RSS, seeded Monte Carlo)
- [ ] 3.3 Thermal mismatch across dissimilar connections

## 4. Mechanism and economy

- [ ] 4.1 Grübler–Kutzbach count with axis caveats
- [ ] 4.2 Part count, unique fasteners, tool count, merge candidates (advisory)
- [ ] 4.3 A docs page for product screening: each check, its method and its citation
