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

All ten headings above appear in all 106 cases; two more do (`Adjustable Parameters`,
`Component Details`) and one appears in 105 (`Component Assembly Graph (Textual)`), so an
adapter may rely on the first twelve and must not require the last.

## The scope census, and it is the important half

Every one of the 106 descriptions was fetched and parsed on 2026-08-27. This is a census,
not a sample:

| Field | Distribution |
| --- | --- |
| Material | Timber 69, PLA 28, ABS 3, Resin 2, Acrylic 2, Sheet Metal 1, Aluminum 1 |
| Manufacturing Method | CNC Milling 65, 3D Printing 28, Laser Cutting 8, FDM 3D Printing 5 |
| Planned Component Quantity | 1 for 37 cases; 2–36 for the other 69 (the `bookshelf` case names 44 parts in its component list) |

A `DesignSpec` is a typed statement of intent for **one part**, so the 69 assemblies are
out of scope by construction — and the rubric grades assembly readiness, joint design and
manufacturability, which are not margins against an allowable.

Of the 37 single-part cases: PLA 27, Timber 6, Resin 2, Sheet Metal 1, ABS 1. **None of
those materials is in the bundled materials database** (seventeen aluminium, steel,
stainless, titanium and bronze grades). So today the count is **0 of 106 compilable**, and
the binding constraint is the material path rather than the format: the format parses,
the geometry is stated, and the material has nowhere to resolve to.

The nearest family is the six single-part timber cases: timber is screened here through
NDS reference design values rather than the materials database, so those become reachable
the moment a spec can name a timber design value instead of a database key. The polymers
need a materials-database entry that does not exist and should not be invented — a PLA
modulus recalled rather than cited is the failure this library is built to refuse.

So the comparison this change promises is **not** "Anvilate scores MUSE". It is the
funnel's first stages over the subset that is in scope at all, with the out-of-scope count
published beside it — which is what task 1.3 means by out-of-scope accounting, and why the
first number to publish is 0 of 106 with the reason, not a percentage. A single scalar
over the whole set would be the same mistake this change already refuses in its
agent-driving half.

## What is still open

The census above answers the subset question by hand; the adapter's job is to keep
answering it — attempting every case and reporting each refusal with its reason, so the
count moves on its own when a material path lands rather than going stale in this file.
Until then there is nothing to score, and a benchmark comparison published against zero
compilable cases would be a number about the benchmark rather than about Anvilate.
