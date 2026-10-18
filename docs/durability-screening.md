# Durability screening

**What a product's life does to it: cycles counted from a load history, modes held clear of
what excites them, and the load a drop puts on what is inside.**

| Function | What it gives you |
| --- | --- |
| `rainflow_count(history, repeating=...)` | The history's cycles by rainflow, with range, mean and count, a range histogram, and the residual of an open count |
| `modal_separation(...)` | Every estimated mode below a ceiling against every declared excitation band, with the separation ratio and the verdict against the program's target |
| `duty_cycle_damage(events, ...)` | Miner damage per pass, per life and in total over named events, each counted by rainflow, with a declared mean-stress correction, naming the event that drives it |
| `o_ring_seal_screen(...)` | An O-ring's squeeze at the cold extreme and fill at the hot one, its extrusion gap against the cited limit, the squeeze left after compression set, and fluid compatibility |
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

## Damage by event

A duty cycle is named events, each with its stress history, how often it occurs per life,
and its source. Each event is counted by rainflow. Each cycle is turned into a fully
reversed amplitude by the declared correction (none, Goodman, or Smith-Watson-Topper) and
read on the declared Basquin curve. Miner's rule then sums it per pass and per life. The
result gives each event's share and names the one with the largest. A history of fewer than
three reversals has no closed cycle, and it is refused naming its event.

The [bracket example](../examples/bracket_duty_cycle.py) shows why the share matters. A
pothole occurring 4,000 times does 0.97 of the damage, against cornering 300,000 times.
Without the mean-stress correction, the same bracket would appear to pass.

## Seals across temperature

An elastomer expands about ten times as fast as a metal gland. So a seal drawn for 18%
squeeze at room temperature has less at the cold extreme, and fills more of its groove at
the hot one. The screen scales the cross-section and the gland from the drawing's
temperature to each extreme. It holds squeeze and fill to the caller's cited limits, and
the extrusion gap to the limit they read for their pressure and hardness. Squeeze left
after compression set is checked at the cold extreme. A condition the caller did not
declare, such as fluid compatibility, is not evaluated and keeps the seal from passing.
The [cold-squeeze example](../examples/o_ring_cold_squeeze.py) passes on day one and fails
at end of life.

## Embedding in preloaded joints

`embedding_preload_loss` turns the settlement of a joint's faying surfaces into lost
preload: the total settlement over the bolt and clamp stiffnesses in series. The
settlement per interface is the caller's to read and cite. The tables for it are not
public, and none is bundled. `preload_bounds(..., embedding=...)` takes the larger of
it and NASA-STD-5020B's 5% short-term relaxation, rather than adding them. Both are the
same loss, and the standard warns 5% may be too little with several faying surfaces.

## Modes and drops

A mode inside an excitation band has no separation. Outside it, the separation is
measured from the nearer edge. The bands, the ceiling and the required ratio are the
program's, each with its source: none is bundled.

A drop onto a declared contact stiffness is a half-sine pulse with no rebound loss. Each
mounted item feels the pulse times the half-sine shock amplification at its own natural
frequency, so an item tuned near the worst ratio sees about 1.77 times the peak. The
contact stiffness is the weakest number, and every drop result is labelled an estimate.

Not yet built: declaring a duty cycle in a Design Spec (the analysis takes events directly
today), and plastic retention.
