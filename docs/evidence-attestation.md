# Attested evidence

**A seal you can re-run.** A screening result gets a content address: hash the spec, the
verdict, the citations, the environment, and the artifact digests into one canonical
document, wrap it in a standard envelope, and hand somebody the bytes. They re-hash it.
Either it is the same piece of work or it is not, and the difference is visible without
trusting the person who sent it.

The PE-stamp world signs PDFs. This signs the computation.

```python
from anvilate.attestation import (
    Attestation, EvidenceBundle, LocalHmacSigner, Subject, verify_attestation,
)

bundle = EvidenceBundle(subjects=(Subject.over("lug.dxf", dxf_bytes),), predicate=predicate)
bundle.digest            # the content address — the same for every rebuild of the same inputs
envelope = Attestation.signed_by(bundle, LocalHmacSigner(secret))
verify_attestation(envelope, artifacts={"lug.dxf": dxf_bytes}, signer=signer)
# [PASS] bundle <first 12 hex>: signature symmetric_verified
```

## What the bundle claims

An [in-toto Statement v1](https://github.com/in-toto/attestation) whose **subjects** are
the produced artifacts by SHA-256, and whose **predicate** —
`https://anvilate.dev/attestation/screening/v1`, versioned in the URI so a breaking change
takes a new one — carries six things:

| Field | What it is |
| --- | --- |
| `specDigest` | the digest of the spec that was screened |
| `status` | the rolled-up verdict, in the scorecard's own four-valued status |
| `scorecard` | every check: name, status, detail, margins, derivation |
| `citations` | the standards records behind the numbers, from the provenance roll-up |
| `bom` | a CycloneDX 1.6 inventory of the environment that computed it |
| `aiDisclosure` | whether, where, and by which model an LLM participated |

The envelope is [DSSE](https://github.com/secure-systems-lab/dsse): `payloadType`,
base64 payload, signatures. The canonicalisation is Anvilate's own and is written down in
`canonical_json` — code-point key ordering and Python's shortest-round-trip float repr —
**not** RFC 8785 JCS, so a third party re-hashing a bundle applies those rules rather than
a standard the output does not actually follow. Standard attestation tooling reads the subjects and skips a
predicate it does not recognize, so the bundle is useful to a verifier that has never
heard of Anvilate.

**`payloadType` is read off the wire, and the envelope round-trips.** It had a Python name
and a wire name — `payload_type` and `payloadType` — and only one of them was used on each
side: `to_envelope` wrote the wire spelling and `model_validate` read the Python one, so an
envelope loaded from a file **never saw its own declared type**. It took the default,
silently, and `verify_attestation` then computed the pre-authentication encoding from a
string the envelope had not said. Nothing noticed because today's only payload type is the
default, and the test that proves the signature binds the envelope's *own* type relabels it
in Python rather than through the wire shape, so it never crossed the gap. A payload type
this verifier does not read is now a reported problem, the same rule the predicate type
follows, and every key `to_envelope` writes is held against the fields the model reads.

**And the field is required, which is the other half of that.** The alias made both spellings
*work*; the default made neither of them necessary. An envelope carrying no `payloadType` at
all — or one whose key is misspelled, which is the same thing to a reader that ignores what it
does not recognise — was still read as in-toto, and the verifier still computed the
pre-authentication encoding from a string the envelope had not said. That is word for word the
defect the alias was added to fix, surviving in the one case the alias could not reach. DSSE
requires the field, so nothing valid is refused by requiring it; what is refused is a reader
supplying the answer to its own check. `anvilate verify` reports it as a bad request naming
`payloadType`.

**A key inside the predicate that this verifier does not read is reported too.** Same rule,
one level in: a payload type it cannot read is a problem because a document it cannot read is
not one it can vouch for, and a *key* it does not recognise is the same claim in a smaller
place. It was ignored — `anvilate verify` printed a clean `[PASS]` over a predicate carrying
`"waivers": ["signed off by nobody"]`, a claim inside the signature and so part of what was
attested, and never mentioned it. The report carries `unread_predicate_keys` now, the verdict
moves to `NOT_EVALUATED`, and the line says `predicate states waivers, not read here`.

**And not only at the top.** A key on a scorecard *entry* — `"signed_off_by": "nobody"` beside
a check — is the same claim one level further in, and it is the level a reader actually reads.
The parts backed by a model are found by round-tripping them through it and diffing the keys,
not by a second hand-written list: what the reader could not carry is exactly what does not
come back. Keys only, and in one direction, since the reader legitimately adds keys the
document did not have (`status` is computed) and normalises values. `bom` and `aiDisclosure`
are not swept — a CycloneDX inventory is somebody else's schema, and this verifier is not the
authority on what may appear in one.

**And it is on the page.** `anvilate verify`'s text rendering showed the signature state and
the two subject lists, so the first version of this printed `NOT_EVALUATED` with every subject
checked, nothing unchecked and no problem on stderr — a non-pass with nothing saying why,
which is the worst answer a report can give. `status` is computed from four fields and two of
them were not rendered; all four are now, `none` included, and a test moves each field of the
report and requires the rendering to move with it.

Reported rather than refused, and that is the same distinction `unverified_signatures` draws:
a bundle written by a newer Anvilate is not a broken bundle, and a verifier that failed on
every key it had not been taught would make each release refuse the one before it. What it
must not do is stay silent.

## The predicate is checked against its schema, not only its type label

`verify_attestation` makes three checks, and the third was missing for a release. A
predicate of `{"anything": "at all"}` verified **PASS** whenever the type string matched
and the subject digests did — an envelope carrying no scorecard, no citations and no bill
of materials came back clean, which is the one answer a verifier must never give.

**The same defect had a second home: the headline.** `AnvilatePredicate.status` computes the
verdict on the outside of the document — the sections roll-up when there is one, the
scorecard's own verdict otherwise — so a producer cannot write anything else there. The
reading side never compared them, so a predicate saying `"status": "pass"` over a failing
scorecard, or over `"sections": {"status": "fail"}`, verified with **no problem reported at
all**. It is the one claim standard tooling reads, and it was the one claim nothing checked.
And `sections` — the only key the predicate writes conditionally — had never been looked at,
so it could carry anything. Both are checked now, and every key `to_json_dict` writes is held
against the checker by corrupting each one in turn and requiring a reported problem.

Checked against the **wire** shape rather than the model. `to_json_dict` renames and
reshapes on the way out (`specDigest`, a CycloneDX `bom`, an `aiDisclosure` body), so
handing the wire predicate to `AnvilatePredicate.model_validate` reports every field as
missing — including for an honest envelope, which is how the first draft was caught. Each
part is validated by the model that owns it instead: the scorecard as a `Scorecard`, each
citation as a `SourceRecord`, the digest as sha256 hex, the status as a scorecard status.

Two directions are held. Every key the writer emits must be one the verifier requires —
otherwise a field could be dropped from an envelope unnoticed — and every key the verifier
requires must be one the writer emits, or the list drifts into requiring something nobody
sends. `sections` is optional on the writer's side and exempt.

The check runs only for the predicate type this verifier claims to understand. An unknown
type is already refused, and validating a predicate written to somebody else's schema
against this one would report the wrong thing about it.

## The inventory is read, not typed

`EnvironmentBOM.of_this_environment()` builds the bill of materials from what is actually
installed. Every caller used to hand-write it, and two attested `pint 0.24.4` and
`pydantic 2.9.2` against an environment running 0.25.3 and 2.13.5 — a false toolchain
record inside the document whose entire purpose is provenance, and the one part of an
attestation nobody can catch by reading it.

The component list is derived from Anvilate's own declared dependencies, so a dependency
added to the project appears without anybody remembering. Three rules make it honest:

- **A declared dependency that is not installed is left out**, not recorded at a
  placeholder version. An optional extra nobody installed contributed nothing to this
  bundle, and saying it did is the same lie in the other direction.
- **Dev tooling is excluded.** pytest and ruff are installed in a contributor's environment
  and had no part in producing a bundle. The rule is the `dev` extra rather than a list of
  names, so `export`'s ezdxf — which really does write the DXF — stays in.
- **A versioned dataset is stated by the caller**, because no package index knows a
  materials-database version and nothing here can read one off a table it was not handed.

A test requires every version the BOM reports to equal what `importlib.metadata` says, and
another requires that no example anywhere states a version literal for an installed
package — a stale literal in an example teaches the defect.

### The declaration it is derived from is a snapshot

"Declared dependencies" means the list written into `.dist-info/METADATA` at install time,
not the one in `pyproject.toml` today. An editable install — the shape every contributor
works in — does not rewrite that snapshot when the project's dependencies change, so a new
dependency is invisible to the BOM until somebody reinstalls. This repository sat in exactly
that state: `export = ["ezdxf>=1.1"]` declared, ezdxf installed and importable, and the
attestation for a bundle containing a DXF naming only pint, pydantic and pyyaml.

A gate in `tests/test_contract.py` compares the two lists, requirement by requirement and
per extra, and names the drift and the reinstall that clears it. It does not hold the
environment itself — a declared dependency can still be absent, or at a version outside its
own bound.

### The CycloneDX claim is checked against the published schema

A document that says `"bomFormat": "CycloneDX"` is making a claim about a specification
somebody else wrote, and CycloneDX publishes the JSON Schema, so it is checkable. The
scheduled `interchange-schemas` job fetches `bom-1.6.schema.json` and validates what
`to_cyclonedx()` emits — over every component kind this can produce, including the two the
live environment never yields: a caller-stated versioned database, and an application entry
sitting among the components. Both the document and its component definition are
`additionalProperties: false`, so a key emitted under a name CycloneDX does not define fails
there rather than shipping.

One claim the schema does not hold: `specVersion` is a plain string with `"1.6"` as an
*example*, no enum and no pattern, so a BOM declaring `"1.4"` validates against the 1.6
schema and reports the wrong spec to every reader. It is held instead against the `$id` of
the schema file being validated against, and which file that is comes from what the download
contains rather than from the constant under test — naming the file after the constant made
a wrong version *skip* the check instead of failing it.

## Four things that are deliberate

**No wall clock, anywhere.** CycloneDX's `metadata.timestamp` and `serialNumber` are both
optional and both unique per emission, so both are omitted. One timestamp in the payload
makes every rebuild a different document and the content address worth nothing. A gate in
the suite greps the whole shipped package for wall-clock and random-identifier calls —
`datetime.now`/`utcnow`, `date.today`, `time.time`/`time_ns`/`perf_counter`/`monotonic`,
`uuid1`/`uuid3`/`uuid4`/`uuid5`, any module-level `random.*`, `secrets.*`, and `os.urandom` — and a companion
test proves the pattern fires on each of them, because a gate whose coverage is narrower
than its claim is worse than no gate. The determinism the digest rests on is enforced,
not assumed.

**The environment is inside the address.** Bump `anvilate_materials` from 2026.03 to
2026.09 and the digest moves, even with the spec untouched. The same spec screened against
different data is a different piece of work, and a digest that hid that would be the most
expensive kind of false negative.

**Unsigned is a state, not a gap.** Air-gapped runs produce `Attestation.unsigned(...)`,
and nothing thereafter presents it as attested. Verification still checks what it can —
the artifact digests, the statement type, the predicate type — and reports
`signature unsigned` in plain words.

**A signature nobody checked is not a checked signature.** Hand `verify_attestation` a
signed envelope with no key and the report is `NOT_EVALUATED`, not `PASS`. A DSSE envelope
may legitimately carry several signatures, so one under a key you do not hold is not a
failure — but it is not a check either, and it lands in `unverified_signatures` and pulls
the report to `NOT_EVALUATED` rather than passing unmentioned. It is the
scorecard's no-silent-green rule applied to the seal itself. Same for artifacts: a subject
you did not supply comes back *unchecked*, never assumed intact, and an artifact you
supplied that the bundle never covered is a **failure** — you believed it was covered and
it was not.

## What the bundled signer does and does not prove

`LocalHmacSigner` is HMAC-SHA256 over the DSSE pre-authentication encoding. It is in the
box because Anvilate's runtime dependencies are pure-Python and few, and it is honest
about its ceiling: **HMAC is symmetric.** Whoever can verify the tag could also have
produced it. That makes a bundle tamper-evident against anyone without the secret; it does
not establish authorship.

So the report distinguishes them. `SignatureState.SYMMETRIC_VERIFIED` is a match on a
shared secret; `VERIFIED` is a match on an asymmetric signature; and
`VerificationReport.attested` — the strict flag — is True only for the latter.

`AttestationSigner` is the seam. Five members (`keyid`, `algorithm`, `symmetric`, `sign`,
`verify`) and an Ed25519 key through `cryptography`, a hardware token, or a Sigstore
keyless flow in CI plugs in without this module growing a dependency.

**Not implemented:** the Sigstore keyless path itself (it needs a network round trip to a
transparency log and a dependency Anvilate does not carry), and Rekor inclusion proofs.
The envelope shape is the standard one, so adding a signer later does not change any
document already produced.

## The AI-involvement disclosure

Anvilate's specs are LLM-drafted by design, so the bundle says so machine-readably: the
model, the backend, the stage (`intent compilation`, `critic edit`), and who confirmed it.
`origins` maps each spec field to where its value came from, in the same
`DecisionOrigin` vocabulary the [reviewer dossier](responsible-charge-review.md) sorts on —
so model-drafted, user-stated, and database-resolved values stay distinguishable in the
bundle and not only in the UI that produced it.

The invariant is enforced at construction, because the failure mode is omission: a
disclosure whose origins attribute any value to a model **cannot** declare that no model
participated. A hand-authored spec uses `AIDisclosure.none()` and says so explicitly,
rather than leaving the field empty and letting a reader guess which kind of silence it is.

`AIDisclosure.unconfirmed_events` is the list a reviewer wants first: model output nobody
accepted.

## Worked example

`examples/attested_evidence_bundle.py` — a lifting lug's bundle rebuilt (same digest), its
materials database bumped (different digest), its drawing tampered with (fails, naming
`'lug.dxf'`), and verified without the key (`NOT_EVALUATED`).
