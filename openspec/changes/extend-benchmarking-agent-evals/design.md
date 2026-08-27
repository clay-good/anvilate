# Design: the MUSE licence review, and what it decides

Task 1.1 asks one question with two answers available: does MUSE-class benchmark data
ship *in* this repository, or is it referenced and fetched? This is the record of what was
checked and what it decides. Every claim below is marked with how it was verified, in the
shape `docs/export-targets.md` uses, because a licence recalled is a licence nobody
checked.

## What was verified, 2026-08-27

| Claim | Status | How it was checked |
| --- | --- | --- |
| MUSE is a text-to-CAD benchmark over structured design specifications | confirmed | The paper, *MUSE: Benchmarking Manufacturable, Functional, and Assemblable Text-to-CAD Generation* (arXiv:2605.28579) |
| The paper is CC BY 4.0 | confirmed | The arXiv listing's own licence line |
| The **code** is MIT | confirmed | `github.com/dong7313/muse` README's Licence section, which names `LICENSE` |
| The **dataset** is CC BY 4.0 | confirmed, twice | The project site (`dong7313.github.io/muse-benchmark/`) and the Hugging Face card (`huggingface.co/datasets/dongxiaoyu/MUSE`) state it independently |
| The dataset is 106 design cases | confirmed | The Hugging Face card |
| Each case is a bundle of *paths* — a description, a four-view dimensioned drawing, a render, and a rubric | confirmed | The Hugging Face card's field list |

Nothing here is non-commercially licensed, so the `Dataset licensing discipline`
requirement's exclusion does not bite: both halves are redistribution-compatible with an
MIT package, given attribution.

## The decision: reference-only, fetched, never bundled

Legally we may bundle. We will not, for three reasons that outlive the licence:

1. **The dataset is not values, it is artefacts.** The bundled tables in this repository
   are numbers — a wall thickness, a tolerance grade — small, diffable, and meaningful in
   isolation. MUSE's cases are drawings, renders and rubric prose. Committing binary
   artefacts to hold a benchmark's *inputs* makes the repository heavier at every clone
   for a file nothing in `src/` reads.
2. **A benchmark with a leaderboard moves.** A vendored snapshot is a claim about a
   version, and the version is exactly what a published score has to name. Fetching it
   pins the version in the provenance record instead of in a directory nobody re-reads.
3. **It is the rule already written.** License-restricted or heavy external data goes
   through fetch-on-first-use with a checksum and a provenance record — the AISC-shapes
   rule in `standards-data`. MUSE is the same shape; it needs no new mechanism, and the
   attribution CC BY 4.0 requires is a field in the record that flow already writes.

So: the fetch recipe records the source URL, the retrieval date, the dataset version, the
checksum, and the attribution line CC BY 4.0 requires; the adapter (task 1.2) reads from
the cache; and a run that has not fetched reports *not evaluated* rather than a score.

**What may be vendored** is the code path, not the data: MUSE's own harness is MIT, so a
thin adapter may depend on or copy from it with attribution if that turns out cheaper than
re-implementing the funnel's three stages.

## The layout, fetched and read (the anchor for task 1.2)

`metadata.jsonl` is one JSON object per line, 106 of them, each naming four paths:

```
{"case_id": "bookshelf",
 "design_description": "cases/bookshelf/design_description.md",
 "svg_png":            "cases/bookshelf/bookshelf.png",
 "stp_render":         "cases/bookshelf/bookshelf_stp_render.png",
 "evaluation_rubric":  "cases/bookshelf/evaluation_rubric.md", ...}
```

The specification itself is **Markdown under fixed headings** — `Design Goal`, `Geometry
and Dimensions`, `Material`, `Manufacturing Method`, `Connection Method (Joint Type)`,
`Mechanical Condition`, `Structural Features`, `Special Requirements`, `Planned Component
Quantity`, `Component Names`. So the adapter is a heading-to-field mapping and a quantity
parser, not a parser of prose; the rubric beside it is judge instructions in Markdown, for
a model, and nothing Anvilate evaluates.

**What that means for scope, and it is the important half.** A sample of fourteen cases
read in full (2026-08-27) splits two ways: PLA parts for 3D printing with a *Planned
Component Quantity* of 1, and timber parts for CNC milling with quantities of 2 to 23 —
the `bookshelf` case names 44. Anvilate screens a declared element against a cited clause;
it does not compile a 44-part joined assembly, and the rubric's own criteria are assembly
readiness, joint design and manufacturability rather than a margin against an allowable.

So the comparison this change promises is **not** "Anvilate scores MUSE". It is the
funnel's first stages over the subset that is in scope at all, with the out-of-scope count
published beside it — which is what task 1.3 means by out-of-scope accounting, and why the
number that matters is how many of the 106 a spec-compiled pipeline can even accept. A
single scalar over the whole set would be the same mistake this change already refuses in
its agent-driving half.

## What is still open

The subset question is a measurement, not an opinion: task 1.2's adapter answers it by
attempting all 106 and reporting what it refuses, with the reason. Nothing about the
in-scope count should be published before that runs.
