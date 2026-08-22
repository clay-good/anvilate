# A valid spec can still be the wrong spec

**Constraining a small model's output to a schema takes validity from ~62% to 100% and takes
accuracy *down* from ~20% to 11%.** The wrong-but-schema-valid share goes from about half to
nearly nine in ten. That is the measured result in "The Constraint Tax"
([arXiv:2605.26128](https://arxiv.org/abs/2605.26128), May 2026), on the 0.5B–1.7B models
Anvilate's local-first promise depends on.

A confidently well-formed spec with the wrong load in it is worse than a malformed one.
Schema validation cannot catch it; every consumer downstream treats it as an input somebody
meant.

## What is built, and what is not

The compiler is not built. [`anvilate.compilation`](../src/anvilate/compilation.py) is the
half that decides whether the compiler will be any good — the **measurement** — and it exists
first on purpose, because a compiler shipped against a metric that hides this failure would
look like it was improving as it got worse.

```python
from anvilate.compilation import CompilationTask, score_task_set

report = score_task_set(tasks, candidates, configuration="single-pass, hard constrained")
print(report.summary())
```

```
4 tasks under single-pass, hard constrained: schema validity 100%, field correctness 75%,
wrong-but-valid 75%
```

## Three numbers, and no fourth

`CompilationReport` has **no `score`, no `success_rate`, no `passed`.** A contract test
asserts none of them can be added.

That is not fastidiousness. A single figure over a constrained decoder is dominated by
schema validity — the number constraint drives to 100% — while field correctness falls and
the wrong-but-valid rate rises. Average them and the compiler appears to improve as the thing
a user cares about gets worse. The three numbers move in different directions, which is
exactly why they cannot be one number.

| Number | What it measures | Which way constraint moves it |
| --- | --- | --- |
| `schema_validity` | the fraction of outputs the schema accepted | up, to 100% |
| `field_correctness` | the fraction of referenced fields found and agreeing | down |
| `wrong_but_valid_rate` | the fraction the schema accepted that are wrong anyway | up |

`wrong_but_valid()` names those candidates rather than only counting them, because a rate is
not something anybody can act on.

## What does not count as correct

**A field the candidate omits.** It counts against correctness and says "the candidate does
not carry this field". Skipping absent fields is how a compiler that omits half the spec
scores well.

**A field nobody could compare.** An output that did not parse has all its fields recorded as
not compared, and they stay in the denominator: a compiler that produces nothing must not
outscore one that produces something wrong.

**A task nobody attempted.** `score_task_set` refuses a task with neither a candidate nor a
parse error. A run that skipped the hard tasks would otherwise publish the easy ones' numbers
as the run's.

**A unit read wrong.** Comparison is dimensional: `50 kN` and `50000 N` are the same answer,
`50 kN` and `50 kip` are not, and `50 kN` against `50 mm` is reported as a wrong answer
rather than an incomparable one — reading a force as a length is precisely the failure a
dimensional comparison exists to catch.

## The configuration is part of the number

A report must state how it was decoded, and refuses to be built without it. Validity and
accuracy both move with the pass structure, so a number without its configuration cannot be
compared against another one — and comparing "reason free, then constrain late" against
"constrain from the first token" is the whole reason to measure.

## This is screening, not a benchmark

Every report carries that caveat in its citation. The numbers are only as good as the
reference fields the task set declares, and a task set is a claim about what the compiler
should have understood.
