# Durability screening

**What a product's life does to it: cycles counted from a load history, modes held clear of
what excites them, and the load a drop puts on what is inside.**

| Function | What it gives you |
| --- | --- |
| `rainflow_count(history, repeating=...)` | The history's cycles by rainflow, with range, mean and count, a range histogram, and the residual of an open count |
| `modal_separation(...)` | Every estimated mode below a ceiling against every declared excitation band, with the separation ratio and the verdict against the program's target |
| `drop_screen(...)` | A drop's energy, landing speed and half-sine pulse, and the peak load on each mounted item |

## Rainflow, open or repeating

A history applied once is counted from its start. A range that contains the starting point
is a half cycle, and what is left unpaired at the end is the residual, counted as half
cycles. A block applied again and again (a flight, a lap) is counted from its most extreme
point, and every count is a full cycle. Declare which with `repeating`; there is no default,
because the two give different damage.

The repeating form reproduces the worked example of [NASA CR-181942](https://ntrs.nasa.gov/citations/19900006166)
(Khosrovaneh and Dowling, 1989). Its history is −2, 1, −3, 5, −1, 3, −4, 4, −2, and it
counts ranges 4, 3, 7 and 9, one cycle each. No public primary document works the open
form numerically. It is held to the result two openly licensed reference implementations
test for the same history, and to invariants: an open count of n reversals is (n − 1)/2
cycles, and the history's whole span is always counted.

Damage over the counted cycles is the library's existing `miner_cumulative_damage`. The
[worked example](../examples/rainflow_block_damage.py) shows the largest cycle of a block
doing 0.99 of the damage. It is the cycle a count of neighbouring swings never sees.

## Modes and drops

A mode inside an excitation band has no separation. Outside it, the separation is
measured from the nearer edge. The bands, the ceiling and the required ratio are the
program's, each with its source: none is bundled.

A drop onto a declared contact stiffness is a half-sine pulse with no rebound loss. Each
mounted item feels the pulse times the half-sine shock amplification at its own natural
frequency, so an item tuned near the worst ratio sees about 1.77 times the peak. The
contact stiffness is the weakest number, and every drop result is labelled an estimate.

Not yet built: duty-cycle declarations with damage by event, joint embedding loss, seals
across temperature, and plastic retention.
