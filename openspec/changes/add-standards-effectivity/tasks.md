# Tasks: Standards effectivity

## 1. Contracts

- [ ] 1.1 Citation type gains standard + edition + clause, enforced at registration
- [ ] 1.2 Design-basis type (standard → edition pins) on the spec
- [ ] 1.3 Mixed-edition waiver type; superseded-edition registry with dates

## 2. Implementation

- [ ] 2.1 Basis resolution per check; unsupported-edition → "not evaluated"
- [ ] 2.2 Bundle-level mixed-edition gate
- [ ] 2.3 Edition-difference registry + side-by-side evaluation reporting
- [ ] 2.4 Optional offline jurisdiction mapping with per-entry source and "as of" date

## 3. Tests

- [ ] 3.1 Editionless citation fails registration (CI-enforced across all checks)
- [ ] 3.2 Mixed-edition bundle blocked without waiver, allowed with it
- [ ] 3.3 Superseded label renders without changing the verdict
- [ ] 3.4 Edition comparison reports both results; absent registry entry states so

## 4. Docs & examples

- [ ] 4.1 Example: same beam checked under two editions, difference explained
- [ ] 4.2 Explanation page: why Anvilate will not tell you which code applies to you
