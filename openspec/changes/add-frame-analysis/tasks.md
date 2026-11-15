# Tasks: Frame analysis

Builds on the member-force ingestion in `src/anvilate/interop.py` and the load path in
`src/anvilate/product_screening.py`.

## 1. Declaration

- [x] 1.1 Frame schema: nodes, members (section, material, orientation), supports by
      restrained freedom, end releases, loads, self-weight
- [x] 1.2 A frame over a frame-of-members combination; a frame over a product's connections
- [x] 1.3 Refusals: an unreferenced node, a member with no section, a support on no node

## 2. Solve

- [x] 2.1 Direct stiffness, 3D, first order; mechanism detection naming the free mode
- [x] 2.2 Equilibrium residual on reactions
- [x] 2.3 Declared second-order (P-Δ) analysis with the method named
- [x] 2.4 Member force records produced with Anvilate's declared convention; station forces

## 3. Downstream

- [x] 3.1 Member checks run on solved forces as dependent entries
- [x] 3.2 Product load path resolved from a declared frame; attribution on every downstream
      entry; placeholders with declared stiffness or refused
- [x] 3.3 Deflection checks against declared limits

## 4. Proof

- [x] 4.1 Closed-form verification cases pinned; Pynite as optional referee in tests
- [x] 4.2 The skid frame example (`examples/skid_frame_document.py`) declares a frame and
      its members are screened on solved forces
- [x] 4.3 A docs page for frame analysis: what is solved, what is declared, what the
      external doorway is still for
