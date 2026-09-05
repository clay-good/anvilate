# Values and units

A `Quantity` is a value and a unit, and it refuses every arithmetic and rounding operation
rather than guessing which unit the answer is in. The refusal is the documentation: it
names the mistake and the line to write instead.

| You write | You get |
| --- | --- |
| `stress > allowable` | refused — compare `stress.to("MPa").magnitude` against the other, which is where the unit you compared in gets written down |
| `load * 2`, `a + b`, `d ** 2` | refused — a parameter taking a plain number was handed a `Quantity`; the message says which number to pass |
| `-stress`, `round(load, 2)`, `abs(gap)` | refused — rounding or negating a magnitude without naming its unit is how a value is rounded in metres and read in millimetres |
| `f"{load:.2f}"` | refused — a format spec describes a number, and this is a number with a unit; write `f"{load.to('kN').magnitude:.2f} kN"` |
| `f"{load}"`, `str(load)` | `50 kN` — the library's own rendering, and the one thing the format protocol does answer |
| `a == b` | works, field-wise: `1 m` and `1000 mm` are equal to nothing but themselves |

Real arithmetic goes through `.to(unit).magnitude`, or through `.pint` where the unit
algebra itself is the point.

## Why it refuses rather than converting

A screening library's whole output is numbers with units on them, and the failure that
matters is not a crash — it is a value computed in one unit and read in another. Every
refusal above exists because the operation would have had to *choose* a unit that the
caller never wrote down. So the choice is pushed back to the caller, in the one place a
reviewer can see it: `.to("MPa")`.

The messages are the documentation. Each names the mistake and the line to write instead,
because the same wrong reflex — wrapping a ratio, a count or an angle in degrees in a
`Quantity` because "everything here is a Quantity" — is what produces almost all of them.

`.pint` is the escape hatch where the unit algebra itself is the point: it hands back a
Pint quantity, which multiplies, divides and carries its dimensions properly. Wrap the
result back into a `Quantity` when it re-enters the library.
