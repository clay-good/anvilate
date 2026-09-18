# Voice

Anvilate is an instrument. It reads like a micrometer, not a companion: it states what it
measured, against what, and what it could not do. The rules below apply to every string a
user reads — scorecard lines, refusals, reports, CLI and MCP output.

| Rule | What it means |
| --- | --- |
| No congratulation | A pass is a result, not an achievement. "PASS: safety factor 2.4 vs required 2.0", never "Great job". A tool that praises a passing check makes a failing one read as a scolding. |
| No jokes, no apologies | "Oops" and "sorry" turn a refusal into a mood. A refusal says what is wrong, what it takes, and where a value can come from. |
| No exclamations | Nothing the library prints ends in an exclamation mark. Urgency comes from the status word, which is FAIL or NOT EVALUATED, not from punctuation. |
| No anthropomorphism | The tool does not think, believe, feel, or become happy. It computed, it compared, and it could not do something. |
| No emoji, no easter eggs | Every mark on the output encodes something a reader needs. Ornament is noise on an instrument. |

The status is always a word. Colour, where a surface has any, repeats the word and never
replaces it.

`tests/test_voice.py` holds every string literal in the library that is not a docstring to
these rules: congratulation, jokes and apologies, a word followed by an exclamation mark,
the tool speaking as a person, and emoji. It reads over 5,000 strings. A second test plants
one ordinary slip per rule and requires each to be caught, and requires a list marker, an
inequality and a Roman numeral to pass. A gate that could catch nothing would pass
everything.
