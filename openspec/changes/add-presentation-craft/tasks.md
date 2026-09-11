# Tasks: Presentation craft

## 1. Numbers

- [ ] 1.1 Tabular/lining figures everywhere a value appears; fixed advance width
- [ ] 1.2 Decimal alignment in every column of values; units in a consistent position
- [ ] 1.3 A value that updates keeps its width and does not move its neighbours
- [ ] 1.4 Significant figures stable across renders of identical input

## 2. Layout

- [ ] 2.1 Reserved space for streaming results; no reflow as checks resolve
- [ ] 2.2 Layout-stability check in CI over a reference corpus
- [ ] 2.3 Designed empty, waiting, and failed states for every pane

## 3. Vocabulary and colour

- [ ] 3.1 Enumerated visual vocabulary; a lint that rejects elements outside it
- [ ] 3.2 One accent, reserved for current focus; status colours only for status
- [ ] 3.3 Light and dark from one token set; contrast checked in CI both ways

## 4. Motion

- [ ] 4.1 Transitions only where one change caused another; bounded duration
- [ ] 4.2 Reduced-motion honoured; nothing animates on a timer

## 5. Print

- [ ] 5.1 Print stylesheet: no derivation split across a page break, repeating table
      headers, no colour dependence
- [ ] 5.2 Byte-identical PDF for identical input, asserted

## 6. Voice

- [ ] 6.1 Voice guide: no jokes, no congratulation, no anthropomorphism, no easter eggs
- [ ] 6.2 CI gate over user-facing strings for the forbidden registers

## 7. Measurement

- [ ] 7.1 Visual-regression corpus spanning every pane state and both themes
- [ ] 7.2 A rendering change fails until acknowledged, with the diff shown
