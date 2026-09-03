"""Attested evidence: a bundle you can re-hash, re-read, and re-verify.

A scorecard is a claim. This module turns it into a claim with an identity: the
screening result, its citations, the environment that produced it, and the digests
of the artifacts it covers, serialised canonically and hashed. Two runs of the same
inputs through the same toolchain produce the same digest, byte for byte; anything
that moves the digest is a real input change, and the provenance in the predicate
says which.

The envelope is not invented here. An :data:`in-toto Statement v1 <STATEMENT_TYPE>`
carries the artifact digests as subjects and Anvilate's own versioned predicate as
the claim, and a `DSSE <https://github.com/secure-systems-lab/dsse>`_ envelope wraps
the statement for signing. Standard attestation tooling can read the subjects and
skip a predicate it does not know; nothing in the shape is Anvilate-specific except
the predicate body.

Three deliberate positions, because each is the kind of thing a verifier would
otherwise have to assume:

* **Unsigned is a state, not a gap.** Air-gapped runs produce bundles with no
  signature at all, and :class:`Attestation` records that plainly. No surface here
  calls an unsigned bundle attested — :attr:`VerificationReport.attested` is False
  for one, and the report says why.
* **The bundled signer is symmetric, and that is a weaker claim than a signature.**
  Anvilate's runtime dependencies are pure-Python and deliberately few, so the
  built-in :class:`LocalHmacSigner` is HMAC-SHA256 over the DSSE pre-authentication
  encoding. Anyone who can verify an HMAC can also forge one: it proves possession
  of the shared secret, not authorship. :class:`SignatureState` distinguishes that
  from an asymmetric verification, and :class:`AttestationSigner` is the seam where
  a real key (Ed25519 through ``cryptography``, a Sigstore keyless flow in CI) plugs
  in without this module growing a dependency.
* **A verification that could not check something reports NOT_EVALUATED.** The same
  no-silent-green rule the scorecard runs on: a signed envelope handed to
  :func:`verify_attestation` with no key comes back unevaluated, never verified.

Timestamps are absent on purpose, everywhere — the CycloneDX BOM's optional
``metadata.timestamp`` included. A wall clock in the payload makes every rebuild a
different bundle and the content address worthless.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from ._models import RevalidatedModel
from .evidence import SourceRecord
from .review import DecisionOrigin
from .scorecard import CheckStatus, Scorecard

#: The `dev` extra's marker, as `importlib.metadata.requires` writes it. Reading the extra's
#: name is not guessing: it is this project's own declaration in its own pyproject.
_DEV_EXTRA = re.compile(r"""extra\s*==\s*['"]dev['"]""")

#: The installed distribution this package ships as. One place, so the BOM's application
#: entry and its dependency lookup cannot name two different things.
_DISTRIBUTION = "anvilate"

__all__ = [
    "STATEMENT_TYPE",
    "PREDICATE_TYPE",
    "DSSE_PAYLOAD_TYPE",
    "CYCLONEDX_SPEC_VERSION",
    "canonical_json",
    "sha256_hex",
    "dsse_pae",
    "Subject",
    "ComponentKind",
    "Component",
    "EnvironmentBOM",
    "AIEvent",
    "ValueOrigin",
    "AIDisclosure",
    "AnvilatePredicate",
    "EvidenceBundle",
    "AttestationSigner",
    "LocalHmacSigner",
    "Signature",
    "Attestation",
    "SignatureState",
    "VerificationReport",
    "verify_attestation",
]

# The in-toto Statement v1 type URI. Fixed by the specification, not by us: tooling
# dispatches on this exact string.
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"

# Anvilate's predicate type, versioned in the URI itself. A consumer pins the version
# it understands; a breaking change to the predicate body takes a new URI rather than
# silently changing the meaning of documents already signed under this one.
#: The keys `AnvilatePredicate.to_json_dict` always writes. Spelled out rather than read
#: back from that method: deriving them from the writer would make the check agree with
#: whatever the writer currently emits, including the version where it stopped emitting one.
#: `test_the_predicate_schema_check_knows_every_key_the_writer_emits` holds the two together
#: in the direction that matters — a new required key must be added here to be checked.
_PREDICATE_REQUIRED_KEYS = (
    "specDigest",
    "status",
    "scorecard",
    "citations",
    "bom",
    "aiDisclosure",
)

PREDICATE_TYPE = "https://anvilate.dev/attestation/screening/v1"

# The DSSE payloadType for an in-toto statement. Part of the signed pre-authentication
# encoding, so it is not cosmetic: changing it invalidates every signature.
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"

# The CycloneDX JSON schema version the BOM declares.
CYCLONEDX_SPEC_VERSION = "1.6"


def canonical_json(value: object) -> str:
    """``value`` as JSON in one canonical form: sorted keys, no incidental whitespace.

    Content addressing needs one serialisation, not one of several. Keys are sorted,
    separators are tight, and non-ASCII characters stay as themselves (the output is
    UTF-8, as JSON is defined to be) — so a citation containing "ø" hashes the same
    on every platform rather than depending on an escaping choice.

    These are Anvilate's canonicalisation rules, not RFC 8785 (JCS): keys sort by Unicode
    code point rather than UTF-16 code unit, and numbers are written by Python's
    shortest-round-trip float repr rather than JCS's number grammar, so ``1.0`` stays
    ``1.0``. Every Anvilate build reproduces the same bytes; a third party re-hashing a
    bundle must apply *these* rules, which is why they are written down here rather than
    named by reference to a standard the output does not actually follow.

    Non-finite floats are refused rather than emitted. ``json.dumps`` writes bare
    ``NaN`` and ``Infinity`` by default, which is not JSON at all: the document parses
    in Python and fails in every conformant reader, so a bundle carrying a NaN margin
    would hash cleanly here and be unreadable to the tooling it was produced for.
    """
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:  # pragma: no cover - message varies by Python build
        raise ValueError(
            "a bundle payload contains a non-finite number (NaN or infinity), which "
            "cannot be represented in JSON; the check that produced it should report "
            f"NOT_EVALUATED rather than a number no reader can parse ({exc})"
        ) from exc


def sha256_hex(data: bytes) -> str:
    """The SHA-256 of ``data`` as lowercase hex — the digest form in-toto subjects use."""
    return hashlib.sha256(data).hexdigest()


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """The DSSE pre-authentication encoding of ``payload`` under ``payload_type``.

    ``PAE(t, b) = "DSSEv1" SP len(t) SP t SP len(b) SP b``, with the lengths written
    as ASCII decimal byte counts. Signing this rather than the bare payload is what
    stops a signature over one payload type from being replayed as a signature over
    another, and what makes the encoding unambiguous regardless of what the payload
    contains.
    """
    type_bytes = payload_type.encode("utf-8")
    return b" ".join(
        [
            b"DSSEv1",
            str(len(type_bytes)).encode("ascii"),
            type_bytes,
            str(len(payload)).encode("ascii"),
            payload,
        ]
    )


class Subject(RevalidatedModel):
    """One artifact an attestation is about: a name and its SHA-256.

    The name is how a verifier finds the file (``drawing.dxf``, ``scorecard.json``);
    the digest is what it actually claims. :func:`verify_attestation` looks the artifact
    up **by name** and then compares digests, so a renamed file is reported as a subject
    nobody supplied rather than silently matched on its bytes — the name is part of the
    claim, not a label on it.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    sha256: str

    @model_validator(mode="after")
    def _well_formed(self) -> Subject:
        if not self.name.strip():
            raise ValueError("a subject needs a name; a digest with nothing to find is not one")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError(
                f"subject {self.name!r} carries {self.sha256!r}, which is not a lowercase "
                "64-character hex SHA-256 digest"
            )
        return self

    @classmethod
    def over(cls, name: str, data: bytes) -> Subject:
        """The subject for ``data`` written as ``name``."""
        return cls(name=name, sha256=sha256_hex(data))

    def as_intoto(self) -> dict[str, object]:
        """The in-toto subject shape: ``{"name": ..., "digest": {"sha256": ...}}``."""
        return {"name": self.name, "digest": {"sha256": self.sha256}}


class ComponentKind(StrEnum):
    """A BOM component's CycloneDX type — the values this module emits."""

    APPLICATION = "application"
    LIBRARY = "library"
    DATA = "data"  # a standards or materials database, versioned like code


class Component(RevalidatedModel):
    """One entry in the environment BOM: what it is, what it is called, what version.

    ``version`` is required and must be non-empty. A BOM listing a component without
    a version answers the auditor's question with the half that does not matter: the
    point of the inventory is which version computed the result.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    kind: ComponentKind = ComponentKind.LIBRARY

    @model_validator(mode="after")
    def _named_and_versioned(self) -> Component:
        if not self.name.strip():
            raise ValueError("a BOM component needs a name")
        if not self.version.strip():
            raise ValueError(
                f"BOM component {self.name!r} has no version; an unversioned inventory "
                "cannot tell two builds apart, which is the only thing it is for"
            )
        return self

    def as_cyclonedx(self) -> dict[str, object]:
        return {"type": self.kind.value, "name": self.name, "version": self.version}


class EnvironmentBOM(RevalidatedModel):
    """The software environment that produced a bundle, as a CycloneDX-shaped inventory.

    ``application`` is Anvilate itself; ``components`` are the libraries, solvers, and
    versioned databases it ran against. Both go into the bundle digest, so the same
    spec screened after a materials-database bump is a different bundle — which is the
    behaviour the provenance chain exists to give.
    """

    model_config = ConfigDict(frozen=True)

    application: Component
    components: tuple[Component, ...] = ()

    @model_validator(mode="after")
    def _application_is_one(self) -> EnvironmentBOM:
        if self.application.kind is not ComponentKind.APPLICATION:
            raise ValueError(
                "the BOM's application entry must be declared as an application, not "
                f"{self.application.kind.value!r}"
            )
        names = [c.name for c in self.components]
        if len(set(names)) != len(names):
            raise ValueError(f"the BOM lists a component twice: {sorted(names)}")
        return self

    @classmethod
    def of_this_environment(cls, *, extra: Iterable[Component] = ()) -> EnvironmentBOM:
        """The BOM of the environment this is running in, **read rather than stated**.

        Every caller in this repository used to hand-write the inventory, and two of them
        attested ``pint 0.24.4`` and ``pydantic 2.9.2`` against an environment running
        0.25.3 and 2.13.5. A bill of materials whose versions are whatever the author last
        typed is the one part of an attestation that cannot be checked by reading it, and it
        is the part the whole provenance chain rests on.

        The component list is derived from Anvilate's own declared dependencies via
        :func:`importlib.metadata.requires`, so a dependency added to the project appears
        here without anybody remembering to add it. A declared dependency that is **not
        installed** is left out rather than recorded at some placeholder version: an
        optional extra nobody installed contributed nothing to this bundle, and saying it
        did would be the same lie in the other direction.

        ``extra`` is for the components no package index knows about — a versioned
        materials or standards database — which the caller does have to state, because
        nothing here can read a version off a table it was not handed.
        """
        from importlib.metadata import PackageNotFoundError, requires, version

        def _installed(name: str) -> str | None:
            try:
                return version(name)
            except PackageNotFoundError:
                return None

        seen: dict[str, Component] = {}
        for requirement in requires(_DISTRIBUTION) or ():
            # Skipped: anything required only by the `dev` extra. pytest and ruff are
            # installed in a contributor's environment and had no part in producing a
            # bundle, and a BOM that lists them is claiming they did. Every other
            # requirement — unconditional, or from an extra like `export` whose package
            # really does write the artifact — is included when it is installed.
            if _DEV_EXTRA.search(requirement):
                continue
            name = re.split(r"[<>=!~;\[ ]", requirement, maxsplit=1)[0].strip()
            if not name or name in seen:
                continue
            found = _installed(name)
            if found is not None:
                seen[name] = Component(name=name, version=found)
        for component in extra:
            seen[component.name] = component
        return cls(
            application=Component(
                name=_DISTRIBUTION,
                version=_installed(_DISTRIBUTION) or "0+unknown",
                kind=ComponentKind.APPLICATION,
            ),
            components=tuple(seen[name] for name in sorted(seen)),
        )

    def to_cyclonedx(self) -> dict[str, object]:
        """The BOM as a CycloneDX JSON document.

        Deliberately without ``serialNumber`` or ``metadata.timestamp``: both are
        optional in CycloneDX and both are unique per emission, so including either
        would make two byte-identical builds produce two different BOMs and destroy
        the content address that the BOM is part of.
        """
        return {
            "bomFormat": "CycloneDX",
            "specVersion": CYCLONEDX_SPEC_VERSION,
            "version": 1,
            "metadata": {"component": self.application.as_cyclonedx()},
            "components": [c.as_cyclonedx() for c in self.components],
        }


class AIEvent(RevalidatedModel):
    """One point where a language model touched the spec, and who confirmed it.

    ``stage`` names what the model did in Anvilate's own vocabulary — ``"intent
    compilation"``, ``"critic edit"``. ``confirmed_by`` is the human who accepted the
    result; ``None`` means nobody did, which is recorded rather than hidden, because
    an unconfirmed model edit is exactly what a reviewer needs to see first.
    """

    model_config = ConfigDict(frozen=True)

    stage: str
    model: str
    backend: str
    confirmed_by: str | None = None

    @model_validator(mode="after")
    def _identified(self) -> AIEvent:
        for field, value in (
            ("stage", self.stage),
            ("model", self.model),
            ("backend", self.backend),
        ):
            if not value.strip():
                raise ValueError(
                    f"an AI-involvement event needs a non-empty {field}; "
                    "'a model was involved somewhere' is not a disclosure"
                )
        return self

    @property
    def confirmed(self) -> bool:
        """Whether a named human accepted this event's output."""
        return bool(self.confirmed_by and self.confirmed_by.strip())


class ValueOrigin(RevalidatedModel):
    """Where one spec field's value came from — one entry of a disclosure's origin map."""

    model_config = ConfigDict(frozen=True)

    field: str
    origin: DecisionOrigin

    @model_validator(mode="after")
    def _named(self) -> ValueOrigin:
        if not self.field.strip():
            raise ValueError("a value origin must name the field it attributes")
        return self


class AIDisclosure(RevalidatedModel):
    """Whether, where, and how a language model participated in producing the spec.

    ``origins`` maps a spec field's stable name to where its value came from, using
    the same :class:`~anvilate.review.DecisionOrigin` vocabulary the reviewer dossier
    sorts on — so model-drafted, user-stated, and database-resolved values are
    distinguishable in the bundle rather than only in the UI that produced it.

    The invariant enforced here is the one the disclosure exists for: a bundle whose
    origins name a model-drafted value cannot declare that no model participated.
    Omission is the failure mode being designed against, so it is a construction
    error rather than a lint.
    """

    model_config = ConfigDict(frozen=True)

    participated: bool
    events: tuple[AIEvent, ...] = ()
    # A tuple of frozen pairs rather than a dict, because ``frozen=True`` does not reach
    # inside a mutable field: a plain dict here could be written to after validation, which
    # would defeat the participated/MODEL invariant below *and* move the bundle digest of an
    # already-signed statement. A Mapping passed in is converted, so callers still write
    # ``origins={"span": DecisionOrigin.USER}``.
    origins: tuple[ValueOrigin, ...] = ()

    @field_validator("origins", mode="before")
    @classmethod
    def _accept_a_mapping(cls, value: object) -> object:
        if isinstance(value, Mapping):
            return tuple(ValueOrigin(field=str(k), origin=v) for k, v in value.items())
        return value

    @property
    def origin_map(self) -> dict[str, DecisionOrigin]:
        """The origins as a fresh mapping — a copy, so mutating it changes nothing."""
        return {o.field: o.origin for o in self.origins}

    @model_validator(mode="after")
    def _consistent(self) -> AIDisclosure:
        # Sorted HERE rather than in the mapping converter, because the tuple form is the
        # declared type and a caller may pass it directly. A dict field used to make the
        # digest order-independent for free (canonical_json sorts keys); moving to a tuple
        # to get immutability handed that responsibility back, and sorting only the Mapping
        # path meant two disclosures with the same origin_map hashed differently — which
        # contradicts the whole content-address claim.
        ordered = tuple(sorted(self.origins, key=lambda o: o.field))
        if ordered != self.origins:
            object.__setattr__(self, "origins", ordered)
        seen = [o.field for o in self.origins]
        if len(set(seen)) != len(seen):
            raise ValueError(f"a field is attributed twice in the origin map: {sorted(seen)}")
        model_drafted = sorted(o.field for o in self.origins if o.origin is DecisionOrigin.MODEL)
        if not self.participated:
            if self.events:
                raise ValueError(
                    "the disclosure says no model participated but lists "
                    f"{len(self.events)} model event(s)"
                )
            if model_drafted:
                raise ValueError(
                    "the disclosure says no model participated, but these values are "
                    f"attributed to a model: {model_drafted}"
                )
        elif not self.events:
            raise ValueError(
                "a disclosure that a model participated must say where: name at least "
                "one event (stage, model, backend)"
            )
        return self

    @classmethod
    def none(cls, *, origins: Mapping[str, DecisionOrigin] | None = None) -> AIDisclosure:
        """The disclosure for a spec authored entirely by hand: says so, explicitly."""
        return cls(participated=False, origins=dict(origins or {}))

    @property
    def unconfirmed_events(self) -> tuple[AIEvent, ...]:
        """The model events no human is recorded as having accepted."""
        return tuple(e for e in self.events if not e.confirmed)

    def __str__(self) -> str:
        if not self.participated:
            return "no language model participated in producing this spec"
        models = sorted({e.model for e in self.events})
        unconfirmed = len(self.unconfirmed_events)
        tail = "" if not unconfirmed else f", {unconfirmed} unconfirmed"
        return f"{len(self.events)} model event(s) by {', '.join(models)}{tail}"


def _disclosure_body(disclosure: AIDisclosure) -> dict[str, object]:
    """The disclosure in the predicate's v1 wire shape.

    ``origins`` is written as a JSON object keyed by field name, which is what v1 has
    always emitted. The in-memory representation moved to a tuple of frozen pairs to stop
    a dict field from being mutated after validation, and that is an internal choice: a
    consumer pinned to ``.../screening/v1`` must not see the shape change under an
    unbumped URI, which is exactly what this module's own comment on
    :data:`PREDICATE_TYPE` promises.
    """
    return {
        "participated": disclosure.participated,
        "events": [event.model_dump(mode="json") for event in disclosure.events],
        "origins": {origin.field: origin.origin.value for origin in disclosure.origins},
    }


class AnvilatePredicate(RevalidatedModel):
    """The claim an Anvilate attestation makes, under :data:`PREDICATE_TYPE`.

    Everything a second engineer needs to decide whether the verdict is still theirs:
    the digest of the spec that was screened, the scorecard it produced, the standards
    citations behind it, the environment that computed it, and the AI-involvement
    disclosure. The predicate is data, not prose: it is written machine-readably into the
    signed statement, and `anvilate.report` renders none of it. `AIDisclosure.__str__` is
    the one prose form of the disclosure — "3 model event(s) by ..., 1 unconfirmed" — and
    a caller that wants a reviewer to read it has to print it, as
    `examples/attested_evidence_bundle.py` does. This sentence used to say the report layer
    rendered the predicate, which sent a reader looking in a module that never mentions it.
    """

    model_config = ConfigDict(frozen=True)

    spec_digest: str
    scorecard: Scorecard
    citations: tuple[SourceRecord, ...] = ()
    bom: EnvironmentBOM
    ai_disclosure: AIDisclosure
    # The assembled cross-layer sections, carried as the canonical JSON *text* of
    # :meth:`anvilate.bundle.BundleSections.to_json_dict`. Two reasons for a string rather
    # than the obvious dict. It keeps this module at the bottom of the import graph, so the
    # bundle layer can grow a section without the predicate learning about it. And a dict
    # field on a frozen model is still mutable after validation — the exact trap that made
    # `origins` a tuple of frozen pairs — and this one sits inside the digest, so a write
    # to it would silently move the address of an already-signed statement. A str cannot be
    # written to. Build it with :func:`canonical_json`; :meth:`to_json_dict` parses it back
    # so the predicate body carries structure, not an escaped blob.
    sections_json: str | None = None

    @model_validator(mode="after")
    def _sections_are_readable(self) -> AnvilatePredicate:
        if self.sections_json is not None:
            try:
                parsed = json.loads(self.sections_json)
            except ValueError as exc:
                raise ValueError(f"sections_json is not readable JSON: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValueError(
                    f"sections_json must encode an object; got a JSON {type(parsed).__name__}"
                )
            rolled = parsed.get("status")
            if rolled is not None and rolled not in set(CheckStatus):
                raise ValueError(
                    f"sections_json carries status {rolled!r}, which is not one of "
                    f"{sorted(s.value for s in CheckStatus)}. The statement's headline "
                    f"verdict is read from it, so it cannot be an arbitrary string"
                )
        return self

    @model_validator(mode="after")
    def _identifies_what_was_screened(self) -> AnvilatePredicate:
        if not self.spec_digest.strip():
            raise ValueError(
                "a predicate must name the digest of the spec it screened; a scorecard "
                "with no bound input is a result nobody can reproduce"
            )
        return self

    # A verdict a serialised document does not carry is one its reader has to
    # rebuild. See `Scorecard.status` for what that costs.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        """The verdict this predicate carries — the bundle roll-up when there is one.

        A predicate with assembled sections has two candidate verdicts: the scorecard's,
        and the cross-layer roll-up that is never better than its worst layer. Writing the
        scorecard's as the statement's headline ``status`` put the OPTIMISTIC one on the
        outside — a signed document reading ``"status": "pass"`` at the top and
        ``"sections": {"status": "fail"}`` underneath. Standard tooling reads the top.
        """
        if self.sections_json is not None:
            rolled = json.loads(self.sections_json).get("status")
            if rolled is not None:
                return CheckStatus(rolled)
        return self.scorecard.status

    def to_json_dict(self) -> dict[str, object]:
        """The predicate body as JSON-safe primitives, ready for the statement."""
        body: dict[str, object] = {
            "specDigest": self.spec_digest,
            "status": self.status.value,
            "scorecard": self.scorecard.model_dump(mode="json"),
            "citations": [c.model_dump(mode="json") for c in self.citations],
            "bom": self.bom.to_cyclonedx(),
            "aiDisclosure": _disclosure_body(self.ai_disclosure),
        }
        if self.sections_json is not None:
            body["sections"] = json.loads(self.sections_json)
        return body


class EvidenceBundle(RevalidatedModel):
    """Subjects plus a predicate: the whole claim, and its content address.

    :meth:`statement` is the in-toto document; :attr:`digest` is the SHA-256 of that
    document in :func:`canonical_json` form. The digest covers the artifacts (through
    their subject digests), the spec, the scorecard, the citations, and the BOM — so
    a rebuild that changes any of them changes the address, and a rebuild that changes
    none of them reproduces it exactly.
    """

    model_config = ConfigDict(frozen=True)

    subjects: tuple[Subject, ...]
    predicate: AnvilatePredicate

    @model_validator(mode="after")
    def _has_subjects(self) -> EvidenceBundle:
        if not self.subjects:
            raise ValueError(
                "an attestation with no subject attests to nothing; name at least the "
                "artifact the screening covers"
            )
        names = [s.name for s in self.subjects]
        if len(set(names)) != len(names):
            raise ValueError(f"two subjects share a name: {sorted(names)}")
        return self

    def statement(self) -> dict[str, object]:
        """The in-toto Statement v1 document for this bundle."""
        return {
            "_type": STATEMENT_TYPE,
            "subject": [s.as_intoto() for s in self.subjects],
            "predicateType": PREDICATE_TYPE,
            "predicate": self.predicate.to_json_dict(),
        }

    def payload(self) -> bytes:
        """The canonical UTF-8 bytes of :meth:`statement` — what gets hashed and signed."""
        return canonical_json(self.statement()).encode("utf-8")

    @property
    def digest(self) -> str:
        """The bundle's content address: SHA-256 of :meth:`payload`."""
        return sha256_hex(self.payload())


@runtime_checkable
class AttestationSigner(Protocol):
    """What :func:`verify_attestation` and :meth:`Attestation.signed_by` need from a key.

    Implement it over ``cryptography``'s Ed25519, a hardware token, or a Sigstore
    flow; nothing in this module assumes more than these five members. ``symmetric``
    is not a detail — it decides whether a successful check proves authorship or only
    that the verifier holds the same secret, and :class:`SignatureState` reports which.
    """

    keyid: str
    algorithm: str
    symmetric: bool

    def sign(self, payload: bytes) -> bytes:
        """The signature over ``payload`` (already PAE-encoded by the caller)."""
        ...

    def verify(self, payload: bytes, signature: bytes) -> bool:
        """Whether ``signature`` is valid over ``payload``."""
        ...


class LocalHmacSigner:
    """A local-key signer using HMAC-SHA256 — a shared secret, not a signature.

    Present so that a local-key path exists with no dependency beyond the standard
    library, and honest about what it buys: HMAC is symmetric, so the party who can
    verify is exactly the party who could have produced it. It detects tampering by
    anyone without the secret; it does not establish who authored the bundle. For
    authorship, plug an asymmetric key into :class:`AttestationSigner`.

    ``keyid`` is derived as an HMAC of a fixed label under the secret, so two bundles
    signed with the same key are linkable without the key ever being recoverable from
    the identifier.
    """

    algorithm = "hmac-sha256"
    symmetric = True

    _KEYID_LABEL = b"anvilate-attestation-keyid-v1"

    def __init__(self, secret: bytes) -> None:
        if len(secret) < 16:
            raise ValueError(
                f"a signing secret of {len(secret)} bytes is too short to be one; use at "
                "least 16 bytes of unguessable material"
            )
        self._secret = bytes(secret)
        self.keyid = hmac.new(self._secret, self._KEYID_LABEL, hashlib.sha256).hexdigest()[:32]

    def sign(self, payload: bytes) -> bytes:
        """The HMAC-SHA256 tag over ``payload``."""
        return hmac.new(self._secret, payload, hashlib.sha256).digest()

    def verify(self, payload: bytes, signature: bytes) -> bool:
        """Whether ``signature`` is the tag for ``payload``, compared in constant time."""
        return hmac.compare_digest(self.sign(payload), signature)


class Signature(RevalidatedModel):
    """One DSSE signature: which key, which algorithm, and the base64 tag."""

    model_config = ConfigDict(frozen=True)

    keyid: str
    algorithm: str
    sig: str  # base64, as DSSE requires

    @model_validator(mode="after")
    def _signature_is_base64(self) -> Signature:
        try:
            base64.b64decode(self.sig, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(
                f"signature for key {self.keyid!r} is not valid base64: {exc}"
            ) from exc
        return self

    @property
    def raw(self) -> bytes:
        """The signature bytes, decoded from base64 (strictly — junk is not skipped)."""
        return base64.b64decode(self.sig, validate=True)


class Attestation(RevalidatedModel):
    """A DSSE envelope around a bundle's statement, signed or plainly not.

    :meth:`unsigned` is a first-class construction, not a degenerate one: an
    air-gapped run without a key produces exactly this, and :attr:`signed` is False
    on it forever after. Nothing in this module upgrades an unsigned envelope's
    standing by omission.
    """

    model_config = ConfigDict(frozen=True)

    payload_type: str = DSSE_PAYLOAD_TYPE
    payload: str  # base64 of the canonical statement bytes, as DSSE requires
    signatures: tuple[Signature, ...] = ()

    @classmethod
    def unsigned(cls, bundle: EvidenceBundle) -> Attestation:
        """The envelope for ``bundle`` with no signature, recorded as such."""
        return cls(payload=base64.b64encode(bundle.payload()).decode("ascii"))

    @classmethod
    def signed_by(cls, bundle: EvidenceBundle, signer: AttestationSigner) -> Attestation:
        """The envelope for ``bundle``, signed over the DSSE pre-authentication encoding.

        The PAE binds the envelope's *own* ``payload_type``, not the module constant, so
        a subclass or a future second payload type cannot end up signed under one string
        and verified under another.
        """
        unsigned = cls.unsigned(bundle)
        sig = signer.sign(dsse_pae(unsigned.payload_type, bundle.payload()))
        return unsigned.model_copy(
            update={
                "signatures": (
                    Signature(
                        keyid=signer.keyid,
                        algorithm=signer.algorithm,
                        sig=base64.b64encode(sig).decode("ascii"),
                    ),
                )
            }
        )

    @property
    def signed(self) -> bool:
        """Whether the envelope carries any signature at all."""
        return bool(self.signatures)

    @model_validator(mode="after")
    def _payload_is_base64(self) -> Attestation:
        # Without ``validate=True`` the decoder silently DISCARDS characters outside the
        # base64 alphabet, so an envelope with junk spliced into its payload string decodes
        # to the same bytes, hashes to the same digest, and keeps a valid signature -- a
        # tampered envelope that verifies. Rejecting it at the door is the only place the
        # check is cheap.
        try:
            base64.b64decode(self.payload, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"the envelope payload is not valid base64: {exc}") from exc
        return self

    def payload_bytes(self) -> bytes:
        """The statement bytes carried by the envelope (strict base64)."""
        return base64.b64decode(self.payload, validate=True)

    def statement(self) -> dict[str, object]:
        """The carried statement, parsed."""
        return json.loads(self.payload_bytes().decode("utf-8"))

    @property
    def bundle_digest(self) -> str:
        """The content address of the carried statement."""
        return sha256_hex(self.payload_bytes())

    def to_envelope(self) -> dict[str, object]:
        """The DSSE envelope as the wire shape standard tooling reads."""
        return {
            "payloadType": self.payload_type,
            "payload": self.payload,
            "signatures": [
                {"keyid": s.keyid, "sig": s.sig, "algorithm": s.algorithm} for s in self.signatures
            ],
        }


class SignatureState(StrEnum):
    """What a verification was able to establish about the envelope's signature."""

    UNSIGNED = "unsigned"  # no signature present; the bundle says so itself
    NOT_CHECKED = "not_checked"  # a signature is present and nothing checked it
    SYMMETRIC_VERIFIED = "symmetric_verified"  # a shared secret matched: tamper-evident only
    VERIFIED = "verified"  # an asymmetric signature matched: authorship established
    INVALID = "invalid"  # a signature is present and did not match


class VerificationReport(BaseModel):
    """What a verification found, in the library's own tri-state.

    :attr:`status` is ``FAIL`` when something did not match, ``NOT_EVALUATED`` when a
    signature went unchecked or an artifact was not supplied to compare, and ``PASS``
    only when everything checkable was checked and matched. :attr:`attested` is
    stricter still: it is True only for a signature that establishes authorship, so an
    unsigned bundle and an HMAC-verified one are both honestly short of attested.
    """

    model_config = ConfigDict(frozen=True)

    bundle_digest: str
    signature_state: SignatureState
    predicate_type: str
    checked_subjects: tuple[str, ...] = ()
    unchecked_subjects: tuple[str, ...] = ()
    # Signatures the envelope carries under a key this verification did not hold. DSSE
    # envelopes are legitimately multi-signer, so one of these is not a failure -- but it
    # is not a check either, and a report that counted only the one it could verify would
    # present a partly-checked envelope as a fully-checked one.
    unverified_signatures: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()

    # A verdict a serialised document does not carry is one its reader has to
    # rebuild. See `Scorecard.status` for what that costs.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> CheckStatus:
        # An INVALID signature is a failure whether or not anyone wrote a sentence about
        # it. The verifier happens to always append a prose problem alongside INVALID, so
        # reading only `problems` was correct in practice and wrong in principle: this is
        # an exported model, and a report constructed anywhere else could print
        # "[PASS] ... signature invalid".
        if self.problems or self.signature_state is SignatureState.INVALID:
            return CheckStatus.FAIL
        unchecked_signature = (
            self.signature_state is SignatureState.NOT_CHECKED or self.unverified_signatures
        )
        if unchecked_signature or self.unchecked_subjects:
            return CheckStatus.NOT_EVALUATED
        return CheckStatus.PASS

    @property
    def attested(self) -> bool:
        """True only for a clean verification of an authorship-establishing signature."""
        return self.status is CheckStatus.PASS and self.signature_state is SignatureState.VERIFIED

    def __str__(self) -> str:
        head = f"[{self.status.value.upper()}] bundle {self.bundle_digest[:12]}"
        detail = f"signature {self.signature_state.value}"
        if self.unchecked_subjects:
            detail += f"; {len(self.unchecked_subjects)} subject(s) not supplied"
        if self.unverified_signatures:
            detail += f"; {len(self.unverified_signatures)} signature(s) under other keys"
        if self.problems:
            detail += "; " + "; ".join(self.problems)
        return f"{head}: {detail}"


def _predicate_schema_problems(predicate: object) -> list[str]:
    """What is wrong with a wire predicate, against the shape ``to_json_dict`` writes.

    The producing side cannot emit a malformed predicate — the model refuses to be built —
    so this is entirely about the half that reads documents it did not write.

    **Checked against the wire form, not against the model.** `to_json_dict` renames and
    reshapes (``specDigest``, a CycloneDX ``bom``, an ``aiDisclosure`` body), so handing the
    wire predicate to ``AnvilatePredicate.model_validate`` reports every field as missing —
    including for an honest envelope, which is how that first draft was caught. Each part is
    validated by the model that owns it instead.
    """
    if not isinstance(predicate, dict):
        return [
            f"the predicate is a JSON {type(predicate).__name__}, not an object; a "
            f"{PREDICATE_TYPE} predicate carries the scorecard, the citations and the "
            "environment this was produced in"
        ]

    problems: list[str] = []
    for key in _PREDICATE_REQUIRED_KEYS:
        if key not in predicate:
            problems.append(f"predicate carries no {key!r}, which its own type requires")
    if problems:
        return problems

    digest = predicate.get("specDigest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        problems.append(f"predicate specDigest is not a sha256 hex digest: {digest!r}")
    status = predicate.get("status")
    if status not in {member.value for member in CheckStatus}:
        problems.append(f"predicate status is {status!r}, which is not a scorecard status")
    try:
        Scorecard.model_validate(predicate["scorecard"])
    except (ValidationError, TypeError) as failure:
        problems.append(f"predicate scorecard does not validate: {_first_paths(failure)}")
    citations = predicate.get("citations")
    if not isinstance(citations, list):
        problems.append(f"predicate citations is a {type(citations).__name__}, not a list")
    else:
        for index, citation in enumerate(citations):
            try:
                SourceRecord.model_validate(citation)
            except (ValidationError, TypeError) as failure:
                problems.append(
                    f"predicate citation {index} does not validate: {_first_paths(failure)}"
                )
                break
    bom = predicate.get("bom")
    if not isinstance(bom, dict) or bom.get("bomFormat") != "CycloneDX":
        problems.append("predicate bom is not a CycloneDX document")
    elif not isinstance(bom.get("components"), list):
        problems.append("predicate bom lists no components array")
    if not isinstance(predicate.get("aiDisclosure"), dict):
        problems.append("predicate aiDisclosure is not an object")
    return problems


def _first_paths(failure: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in failure.errors()[:3]
    )


def verify_attestation(
    attestation: Attestation,
    *,
    artifacts: Mapping[str, bytes] | None = None,
    signer: AttestationSigner | None = None,
) -> VerificationReport:
    """Check an envelope offline: signature, subject digests, and predicate schema.

    Everything needed is in the envelope and the bytes on disk — no network, no
    registry. ``artifacts`` maps subject name to content; a subject with no entry is
    reported as unchecked rather than assumed intact, which is why a report over an
    empty mapping comes back ``NOT_EVALUATED`` and not ``PASS``. ``signer`` supplies
    the key material: without it a signed envelope's signature is
    :attr:`~SignatureState.NOT_CHECKED`, again not assumed good.

    A failure names what did not match — the subject, or the signature, or the predicate —
    rather than returning a bare false.

    **The predicate is checked against its schema, not only against its type label.** Until
    that was added, a predicate of ``{"anything": "at all"}`` verified PASS whenever the
    type string matched and the subject digests did: an envelope carrying no scorecard, no
    citations and no bill of materials came back clean. The requirement has always named
    three checks and this was the third.
    """
    problems: list[str] = []
    # Decode once, and never inside an error path. The first version computed
    # ``attestation.bundle_digest`` while *building* the failure report, which decodes the
    # payload again -- so an envelope whose payload was not decodable raised out of the
    # error handler instead of being reported by it.
    try:
        payload = attestation.payload_bytes()
    except (ValueError, binascii.Error) as exc:
        return VerificationReport(
            bundle_digest="",
            signature_state=SignatureState.NOT_CHECKED,
            predicate_type="",
            problems=(f"the envelope payload is not valid base64: {exc}",),
        )
    digest = sha256_hex(payload)
    try:
        statement = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return VerificationReport(
            bundle_digest=digest,
            signature_state=SignatureState.NOT_CHECKED,
            predicate_type="",
            problems=(f"the envelope payload is not readable JSON: {exc}",),
        )
    # An envelope arriving from somewhere else is untrusted input, and JSON that parses is
    # not JSON that is shaped like a statement. Every field below is read defensively for
    # that reason: a payload of ``[1,2,3]`` or a subject list of bare strings used to raise
    # AttributeError out of a function whose whole contract is to report what did not match.
    if not isinstance(statement, dict):
        return VerificationReport(
            bundle_digest=digest,
            signature_state=SignatureState.NOT_CHECKED,
            predicate_type="",
            problems=(
                f"the envelope payload is a JSON {type(statement).__name__}, not a statement "
                "object",
            ),
        )

    predicate_type = str(statement.get("predicateType", ""))
    if statement.get("_type") != STATEMENT_TYPE:
        problems.append(
            f"statement type is {statement.get('_type')!r}, expected {STATEMENT_TYPE!r}"
        )
    if predicate_type != PREDICATE_TYPE:
        problems.append(
            f"predicate type is {predicate_type!r}, which this verifier does not know "
            f"(it understands {PREDICATE_TYPE!r})"
        )
    else:
        # The predicate's **schema**, not only its type label. Until this was here a
        # predicate of ``{"anything": "at all"}`` verified PASS: the type string matched,
        # the subject digests matched, and nothing looked inside. So an envelope carrying
        # no scorecard, no citations and no bill of materials — no evidence of any kind —
        # came back clean, which is the one answer a verifier must never give.
        #
        # Checked only when the type is the one this verifier claims to understand: an
        # unknown type is already refused above, and validating a predicate written to
        # somebody else's schema against this one would report the wrong thing.
        problems.extend(_predicate_schema_problems(statement.get("predicate")))

    supplied = dict(artifacts or {})
    checked: list[str] = []
    unchecked: list[str] = []
    subject_names: set[str] = set()
    raw_subjects = statement.get("subject")
    # EvidenceBundle refuses a subject-less bundle at construction, but the verifier is the
    # half that reads documents it did not build. Without this the strongest forgery is the
    # simplest one: drop the subject key and the envelope verifies PASS while attesting to
    # nothing at all.
    if not isinstance(raw_subjects, list) or not raw_subjects:
        problems.append(
            "the statement carries no subject list, so it attests to no artifact; an "
            "attestation over nothing cannot verify"
        )
        raw_subjects = []
    for raw in raw_subjects:
        if not isinstance(raw, dict):
            problems.append(f"a subject entry is a JSON {type(raw).__name__}, not an object")
            continue
        name = str(raw.get("name", ""))
        subject_digest = raw.get("digest")
        expected = str(subject_digest.get("sha256", "")) if isinstance(subject_digest, dict) else ""
        subject_names.add(name)
        if not expected:
            problems.append(f"subject {name!r} carries no sha256 digest to check against")
            continue
        if name not in supplied:
            unchecked.append(name)
            continue
        actual = sha256_hex(supplied[name])
        if actual != expected:
            problems.append(f"subject {name!r} digest mismatch: attested {expected}, got {actual}")
        else:
            checked.append(name)
    # An artifact handed in that the attestation never covered is not a mismatch, but it
    # is not covered either -- and the caller almost certainly believed it was.
    for name in sorted(set(supplied) - subject_names):
        problems.append(
            f"{name!r} was supplied for verification but is not a subject of this bundle"
        )

    unverified: list[str] = []
    if not attestation.signatures:
        state = SignatureState.UNSIGNED
    elif signer is None:
        state = SignatureState.NOT_CHECKED
        unverified = [s.keyid for s in attestation.signatures]
    else:
        pae = dsse_pae(attestation.payload_type, payload)
        addressed = [s for s in attestation.signatures if s.keyid == signer.keyid]
        unverified = [s.keyid for s in attestation.signatures if s.keyid != signer.keyid]

        def _valid(signature: Signature) -> bool:
            # `Signature` validates its base64 at construction, but `model_copy` does not
            # re-run validators and this module uses `model_copy` itself. A junk signature
            # reaching `.raw` used to raise binascii.Error straight out of the verifier —
            # the same failure the payload decode above was hardened against, one step
            # further down.
            try:
                return signer.verify(pae, signature.raw)
            except (ValueError, binascii.Error):
                return False

        if addressed and all(_valid(s) for s in addressed):
            state = (
                SignatureState.SYMMETRIC_VERIFIED if signer.symmetric else SignatureState.VERIFIED
            )
        else:
            state = SignatureState.INVALID
            problems.append(
                f"no signature verified under key {signer.keyid!r} "
                f"(envelope carries {[s.keyid for s in attestation.signatures]})"
            )

    return VerificationReport(
        bundle_digest=digest,
        signature_state=state,
        predicate_type=predicate_type,
        checked_subjects=tuple(checked),
        unchecked_subjects=tuple(unchecked),
        unverified_signatures=tuple(unverified),
        problems=tuple(problems),
    )
