# Tasks: Timber connections

Builds on `src/anvilate/analysis/nds_timber.py` and `src/anvilate/packs/timber.py`.

## 1. Yield modes

- [x] 1.1 Read AWC TR12 and the connection chapter of the declared NDS edition; record the
      generalized equations and the reduction-term table structure
- [x] 1.2 Single- and double-shear capacity by each mode; governing mode named
- [x] 1.3 Dowel bearing strength as user-supplied or from a cited formula with declared
      specific gravity; load-to-grain angle

## 2. Factors and geometry

- [ ] 2.1 Connection factors in the itemized chain: group action, geometry, end grain,
      toe-nail — C_g (§11.3.6) and C_Delta (§12.5.1) derived, and the Table 11.3.1
      applicability held by `ConnectionDesignValue.adjusted`; what remains is the pack
      screen that renders the chain on a scorecard, each factor with its condition
- [x] 2.2 Edge, end, spacing and row-spacing minimums from user-cited values
- [x] 2.3 Withdrawal from user-cited values

## 3. Proof

- [x] 3.1 Golden test re-derived from a public worked example (a double-shear bolt)
- [x] 3.2 A docs page section for timber connections in the timber screening docs
