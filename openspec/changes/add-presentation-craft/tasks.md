# Tasks: Presentation craft

## 1. Numbers

- [x] 1.1 Tabular/lining figures everywhere a value appears; fixed advance width — the calculation report sets every value cell, derivation and status in tabular lining figures
- [x] 1.2 Decimal alignment in every column of values; units in a consistent position — every
      value column in the calculation report is right-aligned in tabular figures, so decimals
      and units line up at the column's end
- [x] 1.3 A value that updates keeps its width and does not move its neighbours — the CLI's progress count is padded to the width of its total (`[ 9/12]`, `[10/12]`), so the activity beside it stays in one column (tests/test_cli.py)
- [x] 1.4 Significant figures stable across renders of identical input — the calculation
      report renders byte-identical from two interpreters with different hash seeds

## 2. Layout

- [ ] 2.1 Reserved space for streaming results; no reflow as checks resolve
- [ ] 2.2 Layout-stability check in CI over a reference corpus
- [ ] 2.3 Designed empty, waiting, and failed states for every pane

## 3. Vocabulary and colour

- [x] 3.1 Enumerated visual vocabulary; a lint that rejects elements outside it
- [x] 3.2 One accent, reserved for current focus; status colours only for status
- [x] 3.3 Light and dark from one token set; contrast checked in CI both ways

## 4. Motion

- [ ] 4.1 Transitions only where one change caused another; bounded duration — nothing
      rendered today transitions at all (see 4.2); this is the design rule for the workbench,
      which is unbuilt
- [x] 4.2 Reduced-motion honoured; nothing animates on a timer — for the surfaces that exist:
      the HTML report carries no script, transition, animation or timer, held over every report
      shape with a planted transition as the gate's own adversary (tests/test_report.py), and the
      CLI prints one line per update with no spinner or cursor control

## 5. Print

- [x] 5.1 Print stylesheet: no derivation split across a page break, repeating table
      headers, no colour dependence — the report's print rules repeat each column-header row (every one now a `<thead>`), keep a derivation, a row and a check section whole, and print status in black because the word carries it
- [ ] 5.2 Byte-identical PDF for identical input, asserted

## 6. Voice

- [x] 6.1 Voice guide: no jokes, no congratulation, no anthropomorphism, no easter eggs — docs/voice.md
- [x] 6.2 CI gate over user-facing strings for the forbidden registers — tests/test_voice.py, with a planted slip per register

## 7. Measurement

- [ ] 7.1 Visual-regression corpus spanning every pane state and both themes
- [ ] 7.2 A rendering change fails until acknowledged, with the diff shown
