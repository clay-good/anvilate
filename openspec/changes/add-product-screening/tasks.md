# Tasks: Product screening

Depends on `add-product-structure`, `add-interface-contracts`, `add-purchased-components`;
reuses performance budgets, constraint topology, keepouts and the check dependency graph.

## 1. Load path

- [x] 1.1 Product loads and accelerations on items and interfaces
      (a load names one `item` or one `at` of `item.interface`, at document schema 1.20.0.
      On an item it acts at the middle of it; at an interface it acts where that interface
      is — the centre of its face, or on its axis — which is a different moment about
      whatever the item rests on and so a different share on each support. The interface is
      resolved at parse, and each body's load-path entry now names what arrived on it
      directly and where from. A vertical and a **lateral** acceleration were already built)
- [x] 1.2 Rigid-body equilibrium over determinate paths; connection forces with their
      equilibrium
- [x] 1.3 Indeterminacy named with redundant connections; downstream not evaluated;
      declared splits accepted with basis
- [ ] 1.4 Part screens fed interface loads as dependent entries
      (a caster's and a linear guide's rating read their load-path entry, and a rolling
      bearing's now does too, at document schema 1.21.0: `screening.mountings` says which
      axis an item is mounted on, so the path's vertical force is known to be a RADIAL load
      on a horizontal axis — fed as the equivalent load — and on a vertical one it is a
      thrust, reported not evaluated because combining it needs X and Y factors this does
      not derive. A bearing with no mounting is not screened on a direction nobody stated;
      an envelope is a box and a box has no axis. Being fed is not a verdict: a rating life
      still wants the speed and the life, and the entry now asks for those rather than
      saying the product states no load. Catalog parts' own screens are not fed yet)

- [x] 1.5 These checks reach a user and an agent
      (`product_screening` was called from tests and nothing else: no shipped surface ran
      it, so the mass roll-up, clearances, load path, mobility, cost and every drive-train
      check were reachable from Python and nowhere else. `anvilate check` now prints them
      under the item tree and takes the worse of the two verdicts; `build_combination` over
      MCP returns them as `whole_product` beside `next` and `journey`, and one card carries
      both halves for the verdict and the journey, at cli-output 1.79.0)

## 2. Roll-ups

- [x] 2.1 Mass, center of mass, inertia per node with basis per contribution
- [x] 2.2 Mass and CG limits through the budget mechanism; tip-over angle entry
      (the mass limit is a budget over the bodies with growth by maturity; the CG height
      is a weighted mean, so it is a direct limit, not a budget)
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
- [x] 4.3 A docs page for product screening: each check, its method and its citation
- [x] 4.4 Mass maturity (estimated, calculated, measured) and growth allowance per
      maturity; budgets on predicted mass
