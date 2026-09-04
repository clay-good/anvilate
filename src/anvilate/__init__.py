"""Anvilate: local-first analytical screening for mechanical engineers.

A part described as a typed Design Spec is screened by closed-form checks that each cite the
clause they came from, and the results roll up into one scorecard that never reports a silent
green. The natural-language front end and the geometry pipeline the Design Spec is meant to
drive are still being built; see "Where this is going" in the README.

The implemented layers everything else builds on:

- :mod:`anvilate.units` — SI and US customary as first-class citizens.
- :mod:`anvilate.spec` — the typed, versioned, diffable Design Spec IR.
- :mod:`anvilate.standards` — cited, provenance-tagged reference data
  (materials, standard components, metric threads and clearance holes).
- :mod:`anvilate.tolerance` — ISO 2768 general tolerances and ISO 286 fits.
- :mod:`anvilate.analysis` — T1 closed-form analytical checks (beam, column,
  torsion, pressure vessel, bolted joint, von Mises).
- :mod:`anvilate.scorecard` — the check-result vocabulary: ``pass``, ``fail``,
  ``not_evaluated`` and ``over_margin``. Called tri-state throughout, because those are
  three *answers* and ``over_margin`` is a qualified pass — but it is a fourth value a
  caller will see, and this line used to enumerate only three of them.
- :mod:`anvilate.specbench` — an external structured-spec suite read case by case,
  with the cases nothing could compile named rather than counted as failures.
- :mod:`anvilate.store` — the content-addressed store an MCP tool resolves its
  subject from, with its location, reach and retention stated rather than assumed.

On top of the scorecard sit the cross-cutting layers, each of which takes checks
that already ran and does one more thing with them:

- :mod:`anvilate.agenteval` — scoring an agent driving the tool surface:
  completion, iterations and tool-call errors kept apart, because a model that
  abandons the hard tasks improves two of the three.
- :mod:`anvilate.attestation` — the evidence bundle as a content-addressed,
  envelope-wrapped claim: in-toto subjects, a versioned predicate, an environment
  BOM, and a verification that never calls an unchecked signature good.
- :mod:`anvilate.bundle` — every layer's output assembled into one evidence
  document, with one roll-up that is never better than its worst section.
- :mod:`anvilate.callouts` — typed MBD callouts: finish, coating, and heat treat
  as check inputs with persistent characteristic identity, not annotations.
- :mod:`anvilate.compilation` — scoring a compiled spec, with schema validity and
  field correctness kept as separate numbers because constraint moves them in
  opposite directions.
- :mod:`anvilate.contracts` — the Spec IR and the scorecard published as versioned
  JSON Schema 2020-12 artifacts, generated from the models and held against them.
- :mod:`anvilate.dcc` — Digital Calibration Certificates read as measured inputs,
  with the instrument's identity, its stated uncertainty, and an honest signature
  status attached to every value.
- :mod:`anvilate.derivation` — a check's worked calculation: formula, substituted
  values, result, and the clause it came from.
- :mod:`anvilate.evidence` — the provenance roll-up: where every standards number
  a spec references came from.
- :mod:`anvilate.fetch` — fetch-on-first-use for data this library may read and must
  not redistribute: consent, checksum, cached provenance, offline after.
- :mod:`anvilate.explore` — design-space sweeps and exact Pareto fronts over the
  designs that actually pass.
- :mod:`anvilate.gdt` — semantic GD&T: a feature control frame as data, with
  Y14.5's grammar enforced at construction.
- :mod:`anvilate.ingest` — requirement documents read into a draft spec, where an
  extracted value stays a draft until a named person confirms it.
- :mod:`anvilate.interop` — the typed doorway for member forces and section
  properties computed by some other tool.
- :mod:`anvilate.loads` — typed load combinations and the governing one, named.
- :mod:`anvilate.mcp` — the pipeline as MCP tool contracts, and the rule that
  decides which operations are tasks rather than synchronous calls.
- :mod:`anvilate.cli` — the headless command line: one command that is
  backed, three refused by name with what each is waiting on.
- :mod:`anvilate._models` — the base class that makes a model's invariants
  survive ``model_copy``, which runs no validators. A **field** validator counts
  as an invariant here exactly as an after-validator does: a rule stated per
  field is still a rule an update can break, and five models sat in the gap
  where the census read only the second kind.
- :mod:`anvilate.review` — the dossier a licensed engineer needs before sealing.
- :mod:`anvilate.screening` — a Design Spec screened on the checks the document
  itself supports, with the tier no spec can run named rather than dropped.
- :mod:`anvilate.uncertainty` — input scatter propagated to a shortfall
  probability and a sensitivity ranking.
- :mod:`anvilate.verification` — the physical test each analytical check implies,
  and the rule that a plan is never evidence.
"""

from __future__ import annotations

__version__ = "0.0.1"
