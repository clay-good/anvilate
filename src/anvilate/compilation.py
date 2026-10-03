"""Compile prose into validated Spec IR, and measure validity separately from correctness.

The compiler orchestration is backend-independent and makes no network call itself. A backend
is injected by the caller. If it supports two passes, reasoning is unconstrained and packaging
receives the Design Spec JSON Schema; otherwise the recorded fallback is one constrained pass.
Only a :class:`~anvilate.spec.DesignSpec` that passes the normal front-door validation is
returned. Reasoning is retained beside it as provenance, never inserted into the spec.

The reason it is worth building first is a specific, measured failure. Constraining every
token of a small model's output to a schema takes schema validity from about 62% to 100% —
and takes answer accuracy *down* from about 20% to 11%, while the wrong-but-schema-valid
share rises from roughly half to nearly nine in ten ("The Constraint Tax", May 2026,
arXiv:2605.26128). A confidently well-formed spec with the wrong load in it is worse than a
malformed one, because schema validation cannot catch it and everything downstream will
treat it as an input somebody meant.

So the vocabulary here refuses the summary that hides it:

**There is no success rate.** :class:`CompilationReport` reports schema validity, field
correctness and the wrong-but-valid rate as three separate numbers and offers no scalar to
collapse them into. A single "success" figure over a constrained decoder is dominated by
validity — the number constraint makes go up — and moves the *wrong* way from the number a
user cares about. A contract test asserts no such scalar exists on the model.

**A field nobody could compare is not a field that matched.** A reference that names a field
the candidate does not carry counts against correctness and says so, rather than being
skipped. Skipping is how a compiler that omits half the spec scores well.

**An unparseable candidate has no correct fields, not zero fields.** Its outcomes are
recorded as not compared, and they count in the denominator: a compiler that fails to
produce anything must not score better than one that produces something wrong.

Quantity comparison is dimensional, so "50 kN" and "50000 N" are the same answer and "50 kN"
and "50 kip" are not — which is the whole point of comparing against a reference rather than
against a string.

The task corpus is still separate. The scoring vocabulary below is the shape a result has to
have for compiler configurations to be judged honestly.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from math import isclose
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator, model_validator

from ._models import (
    FrozenMap,
    Named,
    Provenance,
    RevalidatedModel,
    StatableModel,
    parse_json,
    rebuilt_quantities,
)
from .contracts import element_json_schemas, spec_json_schema
from .refusal import RefusalError, Remedy
from .spec import SCHEMA_VERSION, DesignSpec, SpecValidationError, parse_spec
from .units import Quantity, UnitError

_BACKEND_SOURCE = "the local model server's configuration: model, loopback endpoint, timeout"
_PROMPT_SOURCE = "the design intent statement for the part being compiled"
_TASK_SET_SOURCE = "the versioned compilation task-set file and its reference fields"
_RUN_SOURCE = "the evaluation run record: attempts, provenance, and scored outcomes"
_POLICY_SOURCE = "the release policy's thresholds for this task-set version"


class _CompilationInputError(RefusalError, ValueError):
    """An intent-compilation input that cannot be used without correction."""


def _compilation_input_refusal(
    message: str, *, subject: str, source: str
) -> _CompilationInputError:
    return _CompilationInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


__all__ = [
    "CONSTRAINT_TAX_CITATION",
    "CompilationBackend",
    "CompilationAttempt",
    "CompilationEvaluation",
    "CompilationCandidateError",
    "CompilationFailure",
    "CompilationMode",
    "CompilationOutcome",
    "CompilationProvenance",
    "CompilationRecommendation",
    "CompilationRecommendationPolicy",
    "CompilationReport",
    "CompilationResult",
    "CompilationTask",
    "CompilationTaskSet",
    "COMPILATION_TASK_SET_VERSION",
    "DecodingConfiguration",
    "FieldOutcome",
    "LlamaCppBackend",
    "LlamaCppError",
    "OllamaBackend",
    "OllamaError",
    "compile_intent",
    "assess_compilation_recommendation",
    "default_compilation_task_set",
    "evaluate_task_set",
    "field_value",
    "score_candidate",
    "score_task_set",
    "task_set_issues",
]

CONSTRAINT_TAX_CITATION = (
    "Schema-constrained decoding raises validity and lowers accuracy on small models; "
    "validity and correctness are reported separately for that reason "
    "(arXiv:2605.26128, May 2026). Screening measurement, not a certified benchmark."
)

# How close two magnitudes must be, once converted to a common unit, to count as the same
# answer. A compiler is being scored on whether it read "50 kN" out of a sentence, not on
# float formatting — but the tolerance is tight enough that 50 and 51 are different answers.
_AGREEMENT = 1e-9
COMPILATION_TASK_SET_VERSION = "1.0.0"
_SEMVER = re.compile(r"\d+\.\d+\.\d+")


class CompilationMode(StrEnum):
    """Whether reasoning and constrained packaging were separate passes."""

    TWO_PASS = "two_pass"
    SINGLE_PASS_FALLBACK = "single_pass_fallback"


class CompilationBackend(Protocol):
    """The model-specific operations required by :func:`compile_intent`.

    ``package_spec`` must apply structured-output enforcement using the supplied schema.
    Anvilate still validates the returned mapping through the ordinary Spec IR front door;
    the backend's constraint is not trusted as validation.
    """

    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def supports_two_pass(self) -> bool: ...

    def reason(self, prompt: str) -> str: ...

    def package_spec(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        reasoning: str | None,
        validation_error: str | None,
    ) -> Mapping[str, Any]: ...


class CompilationCandidateError(RefusalError, ValueError):
    """A model response that constrained packaging could not turn into a candidate."""

    def __init__(self, message: str, *, backend: str = "the compilation backend") -> None:
        super().__init__(
            message,
            remedies=(
                Remedy(
                    action="replace",
                    subject=f"the rejected constrained response from {backend}",
                    source="the Design Spec JSON Schema supplied to package_spec",
                ),
            ),
        )


class OllamaError(RuntimeError):
    """The configured local Ollama service failed or returned an invalid API response."""


class LlamaCppError(RuntimeError):
    """The configured local llama.cpp service failed or returned an invalid API response."""


_LOCAL_RESPONSE_LIMIT = 4 * 1024 * 1024
_LocalTransport = Callable[[str, bytes, float], bytes]


class _LocalHTTPError(RuntimeError):
    """The standard-library loopback transport failed before a response was available."""


def _local_http_post(url: str, body: bytes, timeout: float) -> bytes:
    """POST one bounded request to a caller-configured loopback model service."""
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback is validated
            return response.read(_LOCAL_RESPONSE_LIMIT + 1)
    except HTTPError as error:
        detail = error.read(1025)[:1024].decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise _LocalHTTPError(f"returned HTTP {error.code}{suffix}") from None
    except (TimeoutError, URLError, OSError) as error:
        raise _LocalHTTPError(f"could not reach {url}: {error}") from None


def _validate_local_backend(
    *, model: object, endpoint: object, timeout: object, transport: object, backend: str
) -> None:
    if not isinstance(model, str) or not model.strip():
        raise _compilation_input_refusal(
            f"{backend} model must be a nonblank local model name",
            subject="model",
            source=_BACKEND_SOURCE,
        )
    if len(model) > 1_024:
        raise _compilation_input_refusal(
            f"{backend} model must be no longer than 1,024 characters",
            subject="model",
            source=_BACKEND_SOURCE,
        )
    if not isinstance(timeout, int | float) or isinstance(timeout, bool):
        raise TypeError(f"{backend} timeout must be a number of seconds")
    if not 0 < timeout <= 600:
        raise _compilation_input_refusal(
            f"{backend} timeout must be greater than 0 and at most 600 seconds",
            subject="timeout",
            source=_BACKEND_SOURCE,
        )
    if not callable(transport):
        raise TypeError(f"{backend} transport must be callable")
    if not isinstance(endpoint, str):
        raise TypeError(f"{backend} endpoint must be a string")

    parsed = urlsplit(endpoint)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise _compilation_input_refusal(
            f"{backend} endpoint must be an http(s) loopback origin such as http://127.0.0.1:8080",
            subject="endpoint",
            source=_BACKEND_SOURCE,
        )
    try:
        _ = parsed.port
    except ValueError as error:
        raise _compilation_input_refusal(
            f"{backend} endpoint has an invalid port: {error}",
            subject="endpoint",
            source=_BACKEND_SOURCE,
        ) from None


def _reasoning_messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Reason through the engineering description before it is packaged as "
                "Anvilate Spec IR. Identify only stated facts, units, and missing "
                "information. Do not invent requirements."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def _packaging_messages(
    prompt: str,
    *,
    schema: dict[str, Any],
    reasoning: str | None,
    validation_error: str | None,
) -> list[dict[str, str]]:
    context = [f"Design request:\n{prompt}"]
    if reasoning is not None:
        context.append(f"Prior unconstrained analysis:\n{reasoning}")
    if validation_error is not None:
        context.append(
            "The previous candidate was rejected by Anvilate validation. Correct this "
            f"error:\n{validation_error}"
        )
    context.append(
        "Return only one JSON object conforming to this exact schema:\n"
        + json.dumps(schema, separators=(",", ":"), sort_keys=True)
    )
    return [
        {
            "role": "system",
            "content": (
                "Package the supplied facts as Anvilate Spec IR. Preserve units and do not "
                "invent engineering requirements. Return JSON only."
            ),
        },
        {"role": "user", "content": "\n\n".join(context)},
    ]


def _candidate_from_content(content: str, *, backend: str) -> Mapping[str, Any]:
    try:
        candidate = parse_json(content)
    except ValueError as error:
        raise CompilationCandidateError(
            f"{backend} constrained response was not JSON: {error}", backend=backend
        ) from None
    if not isinstance(candidate, Mapping):
        raise CompilationCandidateError(
            f"{backend} constrained response must be a JSON object; got {type(candidate).__name__}",
            backend=backend,
        )
    return dict(candidate)


def _chat_envelope(
    transport: _LocalTransport,
    url: str,
    payload: Mapping[str, Any],
    timeout: float,
    *,
    backend: str,
    error_type: type[RuntimeError],
) -> Mapping[str, Any]:
    try:
        body = json.dumps(payload, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise error_type(f"could not encode the {backend} request: {error}") from None
    try:
        response = transport(url, body, timeout)
    except _LocalHTTPError as error:
        raise error_type(f"{backend} {error}") from None
    if not isinstance(response, bytes):
        raise error_type(f"{backend} transport must return bytes; got {type(response).__name__}")
    if len(response) > _LOCAL_RESPONSE_LIMIT:
        raise error_type(f"{backend} response exceeds the {_LOCAL_RESPONSE_LIMIT:,}-byte limit")
    try:
        envelope = parse_json(response)
    except (UnicodeDecodeError, ValueError) as error:
        raise error_type(f"{backend} returned an invalid JSON response: {error}") from None
    if not isinstance(envelope, Mapping):
        raise error_type(f"{backend} response must be a JSON object")
    service_error = envelope.get("error")
    if isinstance(service_error, Mapping):
        service_error = service_error.get("message")
    if isinstance(service_error, str) and service_error.strip():
        raise error_type(f"{backend} refused the request: {service_error}")
    return envelope


@dataclass(frozen=True)
class OllamaBackend:
    """A local-only Ollama adapter for :func:`compile_intent`.

    Construction is offline. The first request occurs only when ``reason`` or
    ``package_spec`` is called. ``transport`` replaces the standard-library HTTP client,
    which keeps contract tests and air-gapped evaluation independent of a running server.
    """

    model: str
    endpoint: str = "http://127.0.0.1:11434"
    timeout: float = 120.0
    transport: _LocalTransport = field(default=_local_http_post, repr=False, compare=False)
    name: str = field(default="ollama", init=False)
    supports_two_pass: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        _validate_local_backend(
            model=self.model,
            endpoint=self.endpoint,
            timeout=self.timeout,
            transport=self.transport,
            backend="Ollama",
        )

    @property
    def chat_url(self) -> str:
        """The configured loopback chat endpoint."""
        return f"{self.endpoint.rstrip('/')}/api/chat"

    def reason(self, prompt: str) -> str:
        """Run the unconstrained first pass and return its ordinary text content."""
        reasoning = self._chat(
            {
                "model": self.model,
                "messages": _reasoning_messages(prompt),
                "stream": False,
            }
        )
        if len(reasoning) > 4_096:
            raise OllamaError(
                "Ollama reasoning response exceeds the 4,096-character provenance limit"
            )
        return reasoning

    def package_spec(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        reasoning: str | None,
        validation_error: str | None,
    ) -> Mapping[str, Any]:
        """Package one candidate under Ollama's JSON-Schema output constraint."""
        content = self._chat(
            {
                "model": self.model,
                "messages": _packaging_messages(
                    prompt,
                    schema=schema,
                    reasoning=reasoning,
                    validation_error=validation_error,
                ),
                "stream": False,
                "format": deepcopy(schema),
                "options": {"temperature": 0},
            }
        )
        return _candidate_from_content(content, backend="Ollama")

    def _chat(self, payload: Mapping[str, Any]) -> str:
        envelope = _chat_envelope(
            self.transport,
            self.chat_url,
            payload,
            float(self.timeout),
            backend="Ollama",
            error_type=OllamaError,
        )
        message = envelope.get("message")
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama response has no nonblank message.content")
        return content


@dataclass(frozen=True)
class LlamaCppBackend:
    """A local-only llama.cpp ``llama-server`` adapter for :func:`compile_intent`."""

    model: str
    endpoint: str = "http://127.0.0.1:8080"
    timeout: float = 120.0
    transport: _LocalTransport = field(default=_local_http_post, repr=False, compare=False)
    name: str = field(default="llama.cpp", init=False)
    supports_two_pass: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        _validate_local_backend(
            model=self.model,
            endpoint=self.endpoint,
            timeout=self.timeout,
            transport=self.transport,
            backend="llama.cpp",
        )

    @property
    def chat_url(self) -> str:
        """The configured loopback OpenAI-compatible chat endpoint."""
        return f"{self.endpoint.rstrip('/')}/v1/chat/completions"

    def reason(self, prompt: str) -> str:
        """Run the unconstrained first pass and return its ordinary text content."""
        reasoning = self._chat(
            {
                "model": self.model,
                "messages": _reasoning_messages(prompt),
                "stream": False,
            }
        )
        if len(reasoning) > 4_096:
            raise LlamaCppError(
                "llama.cpp reasoning response exceeds the 4,096-character provenance limit"
            )
        return reasoning

    def package_spec(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        reasoning: str | None,
        validation_error: str | None,
    ) -> Mapping[str, Any]:
        """Package one candidate under llama.cpp's JSON-Schema output constraint."""
        content = self._chat(
            {
                "model": self.model,
                "messages": _packaging_messages(
                    prompt,
                    schema=schema,
                    reasoning=reasoning,
                    validation_error=validation_error,
                ),
                "stream": False,
                "temperature": 0,
                "response_format": {"type": "json_object", "schema": deepcopy(schema)},
            }
        )
        return _candidate_from_content(content, backend="llama.cpp")

    def _chat(self, payload: Mapping[str, Any]) -> str:
        envelope = _chat_envelope(
            self.transport,
            self.chat_url,
            payload,
            float(self.timeout),
            backend="llama.cpp",
            error_type=LlamaCppError,
        )
        choices = envelope.get("choices")
        first = choices[0] if isinstance(choices, Sequence) and choices else None
        message = first.get("message") if isinstance(first, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str) or not content.strip():
            raise LlamaCppError("llama.cpp response has no nonblank choices[0].message.content")
        return content


class DecodingConfiguration(StatableModel):
    """The backend, model, pass shape, schema, and retry budget behind one compilation."""

    model_config = ConfigDict(frozen=True)

    backend: Named
    model: Named
    mode: CompilationMode
    schema_version: str = SCHEMA_VERSION
    retry_budget: int = Field(ge=0, le=5)


class CompilationProvenance(StatableModel):
    """Reasoning retained for debugging, plus how packaging produced the validated spec."""

    model_config = ConfigDict(frozen=True)

    configuration: DecodingConfiguration
    reasoning: str | None
    attempts: int = Field(ge=1, le=6)
    validation_errors: tuple[str, ...] = ()
    succeeded: bool = True

    @model_validator(mode="after")
    def _reasoning_matches_the_pass_shape(self) -> CompilationProvenance:
        if self.configuration.mode is CompilationMode.TWO_PASS:
            if self.reasoning is None or not self.reasoning.strip():
                raise _compilation_input_refusal(
                    "a two-pass compilation must retain its reasoning output",
                    subject="configuration and reasoning",
                    source=_RUN_SOURCE,
                )
        elif self.reasoning is not None:
            raise _compilation_input_refusal(
                "a single-pass fallback did not run a reasoning pass",
                subject="configuration and reasoning",
                source=_RUN_SOURCE,
            )
        expected_errors = self.attempts - 1 if self.succeeded else self.attempts
        if len(self.validation_errors) != expected_errors:
            raise _compilation_input_refusal(
                "compilation provenance has one validation error per rejected attempt; "
                f"got {len(self.validation_errors)} errors across {self.attempts} attempts",
                subject="attempts, validation_errors, and succeeded",
                source=_RUN_SOURCE,
            )
        return self


class CompilationResult(StatableModel):
    """A validated spec and compiler provenance kept outside that downstream document."""

    model_config = ConfigDict(frozen=True)

    spec: DesignSpec
    provenance: CompilationProvenance


class CompilationFailure(RefusalError, ValueError):
    """Constrained packaging exhausted its retry budget without a valid Design Spec."""

    def __init__(self, message: str, *, provenance: CompilationProvenance) -> None:
        self.provenance = provenance
        configuration = provenance.configuration
        super().__init__(
            message,
            remedies=(
                Remedy(
                    action="correct and recompile",
                    subject=(
                        f"the rejected Spec IR candidate from {configuration.backend} model "
                        f"{configuration.model}"
                    ),
                    source=(
                        "the Design Spec JSON Schema and the rejections recorded in "
                        "provenance.validation_errors"
                    ),
                ),
            ),
        )


def compile_intent(
    prompt: str,
    backend: CompilationBackend,
    *,
    retry_budget: int = 2,
) -> CompilationResult:
    """Compile ``prompt`` through an injected backend and return only validated Spec IR.

    A two-pass backend reasons once without a schema, then packages under the exact Design
    Spec schema. A backend that cannot do that uses one constrained pass and records the
    fallback. Invalid packaging is returned to the backend as context for the next attempt;
    it is never exposed as a candidate spec.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise _compilation_input_refusal(
            "prompt must state the part to compile", subject="prompt", source=_PROMPT_SOURCE
        )
    mode = (
        CompilationMode.TWO_PASS
        if backend.supports_two_pass
        else CompilationMode.SINGLE_PASS_FALLBACK
    )
    configuration = DecodingConfiguration(
        backend=backend.name,
        model=backend.model,
        mode=mode,
        retry_budget=retry_budget,
    )
    reasoning = backend.reason(prompt) if mode is CompilationMode.TWO_PASS else None
    if reasoning is not None and not reasoning.strip():
        raise _compilation_input_refusal(
            "the two-pass backend returned no reasoning output to retain",
            subject="backend",
            source=_BACKEND_SOURCE,
        )

    schema = spec_json_schema()
    failures: list[str] = []
    for attempt in range(1, retry_budget + 2):
        try:
            candidate = backend.package_spec(
                prompt,
                schema=deepcopy(schema),
                reasoning=reasoning,
                validation_error=failures[-1] if failures else None,
            )
        except CompilationCandidateError as invalid:
            failures.append(str(invalid))
            continue
        try:
            if not isinstance(candidate, Mapping):
                raise _compilation_input_refusal(
                    "constrained packaging must return a mapping for Spec IR; "
                    f"got {type(candidate).__name__}",
                    subject="backend",
                    source=_BACKEND_SOURCE,
                )
            spec = parse_spec(dict(candidate))
        except (SpecValidationError, TypeError, ValueError) as invalid:
            failures.append(str(invalid))
            continue
        return CompilationResult(
            spec=spec,
            provenance=CompilationProvenance(
                configuration=configuration,
                reasoning=reasoning,
                attempts=attempt,
                validation_errors=tuple(failures),
            ),
        )

    provenance = CompilationProvenance(
        configuration=configuration,
        reasoning=reasoning,
        attempts=retry_budget + 1,
        validation_errors=tuple(failures),
        succeeded=False,
    )
    raise CompilationFailure(
        f"intent compilation failed after {retry_budget + 1} attempts: {failures[-1]}",
        provenance=provenance,
    )


class FieldOutcome(StatableModel):
    """One reference field compared against what the compiler produced.

    ``matched`` is True only when the field was found and agreed. ``detail`` says what
    happened in every other case — absent, wrong, or not comparable — because "did not
    match" and "was never there" are different failures and a compiler that omits fields
    must not look like one that gets them wrong.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    expected: str
    actual: str | None
    matched: bool
    detail: str

    def __str__(self) -> str:
        mark = "match" if self.matched else "MISS"
        line = f"[{mark}] {self.path}: expected {self.expected}"
        # An absent field has nothing to report as "got", and the `got —` it used to print
        # said only that something was missing, not what.
        if self.actual is not None:
            line += f", got {self.actual}"
        # `detail` is the whole of the distinction this class exists to keep. Without it,
        # "not compared — the candidate did not parse" and "the candidate does not carry
        # this field" rendered identically: a compiler that never ran reading exactly like
        # one that omitted the field, which the docstring above says must not happen. A
        # match needs no reason; every other outcome carries its own.
        if not self.matched and self.detail.strip():
            line += f" — {self.detail}"
        return line


class CompilationOutcome(StatableModel):
    """One task's result: whether the output parsed, and how each field fared.

    ``schema_valid`` and the field outcomes are deliberately independent. The combination
    that matters is ``schema_valid`` True with a missed field — that is the wrong-but-valid
    case, the one constrained decoding produces more of, and the one nothing downstream can
    detect.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str
    schema_valid: bool
    fields: tuple[FieldOutcome, ...]
    parse_error: str | None = None

    @model_validator(mode="after")
    def _valid_and_error_disagree(self) -> CompilationOutcome:
        if not self.task_id.strip():
            raise _compilation_input_refusal(
                "a compilation outcome must name the task it came from",
                subject="task_id",
                source=_RUN_SOURCE,
            )
        if self.schema_valid and self.parse_error is not None:
            raise _compilation_input_refusal(
                f"task {self.task_id!r} is recorded as schema-valid and also carries a parse "
                f"error ({self.parse_error!r}); one of the two is wrong, and which one "
                "decides whether the constraint tax is being measured or hidden",
                subject="schema_valid and parse_error",
                source=_RUN_SOURCE,
            )
        if not self.schema_valid and self.parse_error is None:
            raise _compilation_input_refusal(
                f"task {self.task_id!r} is recorded as schema-invalid with no reason. The "
                "reason is what tells a reader whether the compiler produced nothing or "
                "produced something the schema refused",
                subject="schema_valid and parse_error",
                source=_RUN_SOURCE,
            )
        if not self.fields:
            raise _compilation_input_refusal(
                f"task {self.task_id!r} compared no fields; a task whose reference names "
                "nothing cannot distinguish a right answer from a wrong one",
                subject="fields",
                source=_RUN_SOURCE,
            )
        return self

    @property
    def correct_fields(self) -> int:
        return sum(1 for outcome in self.fields if outcome.matched)

    @property
    def fully_correct(self) -> bool:
        """Whether every referenced field was found and agreed."""
        return all(outcome.matched for outcome in self.fields)

    @property
    def wrong_but_valid(self) -> bool:
        """The case this module exists for: the schema accepted it and it is wrong.

        Not detectable downstream — the spec validates, so every consumer treats it as an
        input somebody meant.
        """
        return self.schema_valid and not self.fully_correct

    def __str__(self) -> str:
        state = "valid" if self.schema_valid else f"invalid ({self.parse_error})"
        return f"{self.task_id}: {state}, {self.correct_fields}/{len(self.fields)} fields" + (
            " — WRONG BUT VALID" if self.wrong_but_valid else ""
        )


class CompilationTask(RevalidatedModel):
    """One prompt and the spec fields a correct compilation of it must carry.

    ``reference`` maps a dotted path into the spec to the value expected there. It is
    deliberately a set of *fields* rather than a whole reference spec: two correct
    compilations can differ in the parts nobody stated, and scoring against a full document
    would count a compiler wrong for filling a default differently.
    """

    model_config = ConfigDict(frozen=True)

    task_id: str
    prompt: str
    reference: FrozenMap[str, Any]
    notes: str | None = None

    @field_validator("reference", mode="before")
    @classmethod
    def _a_quantity_survives_a_round_trip(cls, value: Any) -> Any:
        """A task set this library writes, read back, used to hold dictionaries.

        ``reference`` is typed ``Any`` because a spec field can be a string, a number or a
        quantity, and ``Any`` is not told how to rebuild anything. So a task stating
        ``force`` as ``5 kN`` dumped to ``{"magnitude": 5.0, "unit": "kN"}`` and read back as
        exactly that dictionary: the reloaded task no longer compared equal to the one it was
        written from, and every report scored against it rendered its own expected value as
        ``{'magnitude': 5.0, 'unit': 'kN'}`` where the original printed ``5 kN``.

        The verdict was right either way — :func:`_compare` already recognises that shape as
        a quantity — which is what kept this quiet. Only the two-key shape Anvilate's own
        serialiser emits is rebuilt, and a value that does not parse as a quantity is left
        exactly as it was found. Strings are **not** coerced: ``"5 kN"`` stated as a string is
        a string a compiler is expected to produce, and turning it into a quantity here would
        be answering a different question than the task asked.
        """
        return rebuilt_quantities(value)

    @model_validator(mode="after")
    def _has_something_to_check(self) -> CompilationTask:
        if not self.task_id.strip():
            raise _compilation_input_refusal(
                "a compilation task must have an id", subject="task_id", source=_TASK_SET_SOURCE
            )
        if not self.prompt.strip():
            raise _compilation_input_refusal(
                f"task {self.task_id!r} has no prompt", subject="prompt", source=_TASK_SET_SOURCE
            )
        if not self.reference:
            raise _compilation_input_refusal(
                f"task {self.task_id!r} states no reference fields, so every output would "
                "score as fully correct — including an empty one",
                subject="reference",
                source=_TASK_SET_SOURCE,
            )
        return self


class CompilationTaskSet(RevalidatedModel):
    """A versioned corpus of prompts and the fields each prompt actually states."""

    model_config = ConfigDict(frozen=True)

    version: str
    tasks: tuple[CompilationTask, ...]

    @model_validator(mode="after")
    def _is_a_named_nonempty_corpus(self) -> CompilationTaskSet:
        if _SEMVER.fullmatch(self.version) is None:
            raise _compilation_input_refusal(
                f"compilation task-set version must be semantic; got {self.version!r}",
                subject="version",
                source=_TASK_SET_SOURCE,
            )
        if not self.tasks:
            raise _compilation_input_refusal(
                "a compilation task set with no tasks measures nothing",
                subject="tasks",
                source=_TASK_SET_SOURCE,
            )
        task_ids = [task.task_id for task in self.tasks]
        if len(set(task_ids)) != len(task_ids):
            raise _compilation_input_refusal(
                f"the compilation task set repeats task ids: {sorted(task_ids)}",
                subject="tasks",
                source=_TASK_SET_SOURCE,
            )
        return self


def _schema_options(schema: Mapping[str, Any], root: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Expand local references and union branches into schemas a path may traverse."""
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/"):
            return []
        resolved: Any = root
        for token in reference[2:].split("/"):
            if not isinstance(resolved, Mapping) or token not in resolved:
                return []
            resolved = resolved[token]
        return _schema_options(resolved, root) if isinstance(resolved, Mapping) else []
    branches = [
        branch
        for keyword in ("anyOf", "oneOf", "allOf")
        for branch in schema.get(keyword, [])
        if isinstance(branch, Mapping)
    ]
    if branches:
        expanded = [option for branch in branches for option in _schema_options(branch, root)]
        own = {
            key: value for key, value in schema.items() if key not in {"anyOf", "oneOf", "allOf"}
        }
        return ([own] if own else []) + expanded
    return [schema]


def _schema_has_path(schema: Mapping[str, Any], path: str) -> bool:
    options = [schema]
    for part in path.split("."):
        next_options: list[Mapping[str, Any]] = []
        for option in options:
            for expanded in _schema_options(option, schema):
                if part.isdigit():
                    item = expanded.get("items")
                    if isinstance(item, Mapping):
                        next_options.append(item)
                    continue
                properties = expanded.get("properties")
                if isinstance(properties, Mapping) and isinstance(properties.get(part), Mapping):
                    next_options.append(properties[part])
        if not next_options:
            return False
        options = next_options
    return True


def task_set_issues(task_set: CompilationTaskSet) -> tuple[str, ...]:
    """Return reference paths that no longer exist in the published Design Spec schema."""
    schema = spec_json_schema()
    element_schemas = element_json_schemas()
    issues: list[str] = []
    for task in task_set.tasks:
        element_type = task.reference.get("element_type")
        for path in task.reference:
            if path.startswith("element_params."):
                parameter = path.removeprefix("element_params.")
                element_schema = (
                    element_schemas.get(element_type) if isinstance(element_type, str) else None
                )
                if element_schema is None or not _schema_has_path(element_schema, parameter):
                    issues.append(
                        f"task {task.task_id!r} references no {element_type!r} element field "
                        f"at {path!r}"
                    )
            elif not _schema_has_path(schema, path):
                issues.append(f"task {task.task_id!r} references no Design Spec field at {path!r}")
    return tuple(issues)


@cache
def default_compilation_task_set() -> CompilationTaskSet:
    """The small, versioned corpus used to compare intent-compilation configurations."""
    return CompilationTaskSet(
        version=COMPILATION_TASK_SET_VERSION,
        tasks=(
            CompilationTask(
                task_id="structural-lifting-lug",
                prompt=(
                    "CNC-machine a lifting lug from ASTM A36 steel for a 50 kN static load "
                    "at the pin bore. Require a minimum safety factor of 2.0."
                ),
                reference={
                    "material.ref": "ASTM-A36",
                    "manufacturing.process": "cnc_milling",
                    "load_cases.0.kind": "static",
                    "load_cases.0.force": Quantity.parse("50 kN"),
                    "constraints.min_safety_factor.value": 2.0,
                },
            ),
            CompilationTask(
                task_id="mechanical-stepper-bracket",
                prompt=(
                    "Make a 6061-T6 aluminum bracket joining a NEMA 23 motor to an EXT-4040 "
                    "rail. The cantilevered motor mass is 1.1 kg and the bracket must weigh "
                    "no more than 150 g. CNC mill it."
                ),
                reference={
                    "material.ref": "AA-6061-T6",
                    "manufacturing.process": "cnc_milling",
                    "interfaces.0.ref": "NEMA23",
                    "interfaces.1.ref": "EXT-4040",
                    "load_cases.0.kind": "remote_mass",
                    "load_cases.0.remote_mass": Quantity.parse("1.1 kg"),
                    "constraints.max_mass.value": Quantity.parse("150 g"),
                },
            ),
            CompilationTask(
                task_id="structural-bolted-connection",
                prompt=(
                    "Check a single-shear 12 mm bolt joining a 10 mm ASTM A36 plate under "
                    "a 35 kN transverse load. The bolt material is ASTM-A325."
                ),
                reference={
                    "material.ref": "ASTM-A36",
                    "element_type": "bolted_connection",
                    "element_params.bolt_diameter": Quantity.parse("12 mm"),
                    "element_params.plate_thickness": Quantity.parse("10 mm"),
                    "element_params.load": Quantity.parse("35 kN"),
                    "element_params.bolt_material": "ASTM-A325",
                    "element_params.plate_material": "ASTM-A36",
                    "element_params.shear_planes": 1,
                },
            ),
            CompilationTask(
                task_id="timber-floor-beam",
                prompt=(
                    "Check a Douglas Fir-Larch No. 2 floor beam spanning 12 ft under a "
                    "uniform 40 lbf/ft live load. Use the timber beam analytical screen."
                ),
                reference={
                    "material.ref": "Douglas Fir-Larch No. 2",
                    "element_type": "timber_beam",
                    "element_params.span": Quantity.parse("12 ft"),
                    "element_params.load": Quantity.parse("40 lbf/ft"),
                },
            ),
            CompilationTask(
                task_id="hydraulic-supply-line",
                prompt=(
                    "Check 25 gal/min of water through 80 ft of 2 in pipe. Use 0.00015 ft "
                    "roughness, a summed fitting-loss coefficient of 3.5, water kinematic "
                    "viscosity of 1.1e-5 ft^2/s, and 18 ft of available head."
                ),
                reference={
                    "element_type": "pipe_run",
                    "element_params.flow_rate": Quantity.parse("25 gal/min"),
                    "element_params.diameter": Quantity.parse("2 in"),
                    "element_params.length": Quantity.parse("80 ft"),
                    "element_params.roughness": Quantity.parse("0.00015 ft"),
                    "element_params.fitting_loss_coefficient": 3.5,
                    "element_params.kinematic_viscosity": Quantity.parse("1.1e-5 ft^2/s"),
                    "element_params.available_head": Quantity.parse("18 ft"),
                },
            ),
            CompilationTask(
                task_id="metric-shaft-tolerance",
                prompt=(
                    "Turn a 25 mm steel shaft with an h6 fit. Manufacture it by turning and "
                    "validate the declared dimensional tolerance."
                ),
                reference={
                    "manufacturing.process": "turning",
                    "dimensions.0.nominal": Quantity.parse("25 mm"),
                    "dimensions.0.tolerance.designation": "h6",
                },
            ),
        ),
    )


def field_value(document: Any, path: str) -> tuple[bool, Any]:
    """Follow a dotted ``path`` into ``document``, returning ``(found, value)``.

    Handles attribute access, mapping keys, and list indices written as digits, so a path
    like ``"load_cases.0.force"`` reaches into a spec however it is represented. ``found`` is
    False when any step is missing — which is a distinct outcome from a value of ``None``,
    and the difference is the point: a compiler that omitted the field and one that set it to
    null are not the same compiler.
    """
    current = document
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return False, None
            current = current[part]
        elif isinstance(current, (list, tuple)):
            if not part.isdigit() or int(part) >= len(current):
                return False, None
            current = current[int(part)]
        else:
            if not hasattr(current, part):
                return False, None
            current = getattr(current, part)
    return True, current


def _as_quantity(value: Any) -> Quantity | None:
    """``value`` as a Quantity when it is one, else ``None``."""
    if isinstance(value, Quantity):
        return value
    if isinstance(value, str):
        try:
            return Quantity.parse(value)
        except UnitError:
            return None
    if isinstance(value, dict) and {"magnitude", "unit"} <= set(value):
        try:
            return Quantity(magnitude=float(value["magnitude"]), unit=str(value["unit"]))
        except (UnitError, TypeError, ValueError):
            return None
    return None


def _compare(expected: Any, actual: Any) -> tuple[bool, str]:
    """Whether ``actual`` is the same answer as ``expected``, and why not when it is not."""
    expected_quantity = _as_quantity(expected)
    actual_quantity = _as_quantity(actual)
    if expected_quantity is not None:
        if actual_quantity is None:
            return False, f"expected a quantity, got {actual!r}"
        try:
            converted = actual_quantity.to(expected_quantity.unit)
        except Exception:
            # Incommensurable units are a wrong answer, not an incomparable one: reading
            # kilonewtons as kilopounds is the failure mode a dimensional comparison exists
            # to catch, and reporting it as "could not compare" would hide it.
            return False, (
                f"{actual_quantity} is not commensurable with {expected_quantity} "
                f"({actual_quantity.dimensionality} vs {expected_quantity.dimensionality})"
            )
        if isclose(converted.magnitude, expected_quantity.magnitude, rel_tol=_AGREEMENT):
            return True, "agreed"
        return False, f"{actual_quantity} is not {expected_quantity}"
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        if isclose(float(actual), expected, rel_tol=_AGREEMENT):
            return True, "agreed"
        return False, f"{actual} is not {expected}"
    if expected == actual:
        return True, "agreed"
    return False, f"{actual!r} is not {expected!r}"


def score_candidate(
    task: CompilationTask, candidate: Any, *, parse_error: str | None = None
) -> CompilationOutcome:
    """Score one compiled candidate against its task's reference fields.

    ``candidate`` is the parsed spec — a :class:`~anvilate.spec.DesignSpec`, or any object
    or mapping the reference paths can be followed into. Pass ``parse_error`` (and a
    ``candidate`` of ``None``) when the output did not parse at all: every referenced field
    is then recorded as not compared and counts against correctness, so a compiler that
    produced nothing cannot outscore one that produced something wrong.
    """
    schema_valid = parse_error is None
    outcomes: list[FieldOutcome] = []
    for path, expected in task.reference.items():
        rendered = str(expected)
        if not schema_valid:
            outcomes.append(
                FieldOutcome(
                    path=path,
                    expected=rendered,
                    actual=None,
                    matched=False,
                    detail="not compared — the candidate did not parse",
                )
            )
            continue
        found, actual = field_value(candidate, path)
        if not found:
            outcomes.append(
                FieldOutcome(
                    path=path,
                    expected=rendered,
                    actual=None,
                    matched=False,
                    detail="the candidate does not carry this field",
                )
            )
            continue
        matched, detail = _compare(expected, actual)
        outcomes.append(
            FieldOutcome(
                path=path,
                expected=rendered,
                actual=str(actual),
                matched=matched,
                detail=detail,
            )
        )
    return CompilationOutcome(
        task_id=task.task_id,
        schema_valid=schema_valid,
        fields=tuple(outcomes),
        parse_error=parse_error,
    )


class CompilationReport(StatableModel):
    """Three numbers over a task set, and deliberately not a fourth that averages them.

    There is no ``score``, no ``success_rate``, and no ``passed``. Every one of those would
    be dominated by :attr:`schema_validity` — the number schema constraint drives to 100% —
    while :attr:`field_correctness` falls and :attr:`wrong_but_valid_rate` rises. A reader
    handed one figure would see the compiler improve as it got worse, which is the whole
    finding this vocabulary is built around.
    """

    model_config = ConfigDict(frozen=True)

    outcomes: tuple[CompilationOutcome, ...]
    configuration: str  # how this run was decoded: which pass structure, which backend
    citation: Provenance = CONSTRAINT_TAX_CITATION

    @model_validator(mode="after")
    def _measures_something(self) -> CompilationReport:
        if not self.outcomes:
            raise _compilation_input_refusal(
                "a compilation report over no tasks has no numbers in it; an empty run is "
                "reported as not run, not as a clean sheet",
                subject="outcomes",
                source=_RUN_SOURCE,
            )
        if not self.configuration.strip():
            raise _compilation_input_refusal(
                "a compilation report must state how it was decoded. Validity and accuracy "
                "both move with the pass structure, so a number without its configuration "
                "cannot be compared with another one",
                subject="configuration",
                source=_RUN_SOURCE,
            )
        seen = [outcome.task_id for outcome in self.outcomes]
        if len(set(seen)) != len(seen):
            raise _compilation_input_refusal(
                f"the report scores a task twice: {sorted(seen)}",
                subject="outcomes",
                source=_RUN_SOURCE,
            )
        return self

    @property
    def schema_validity(self) -> float:
        """The fraction of candidates the schema accepted. Constraint drives this up."""
        return sum(1 for o in self.outcomes if o.schema_valid) / len(self.outcomes)

    @property
    def field_correctness(self) -> float:
        """The fraction of referenced fields that were found and agreed.

        Over every field of every task, including the fields of candidates that did not
        parse — a compiler that produces nothing scores zero on them, not nothing.
        """
        total = sum(len(o.fields) for o in self.outcomes)
        return sum(o.correct_fields for o in self.outcomes) / total

    @property
    def wrong_but_valid_rate(self) -> float:
        """The fraction of candidates the schema accepted that are wrong anyway.

        The number nothing downstream can detect, and the one that rises under constraint.
        """
        return sum(1 for o in self.outcomes if o.wrong_but_valid) / len(self.outcomes)

    def wrong_but_valid(self) -> tuple[CompilationOutcome, ...]:
        """The candidates that passed the schema and are wrong — named, not just counted."""
        return tuple(o for o in self.outcomes if o.wrong_but_valid)

    def summary(self) -> str:
        """All three numbers, in one line, with none of them averaged into the others."""
        return (
            f"{len(self.outcomes)} tasks under {self.configuration}: "
            f"schema validity {self.schema_validity:.0%}, "
            f"field correctness {self.field_correctness:.0%}, "
            f"wrong-but-valid {self.wrong_but_valid_rate:.0%}"
        )

    def render(self) -> str:
        """The summary, then every task under it worst first, then the caveat they are under.

        The citation is the argument for the shape of the numbers above it: three figures
        rather than one, because a single score is dominated by schema validity and would
        show the compiler improving as it gets worse. `citation` has carried that source and
        the words "screening measurement, not a certified benchmark" since the model was
        written, and no rendering printed it — so the one reading a person actually sees was
        three percentages with nothing saying what they are or are not.

        On `render` and not on `summary`: the summary is a single line for a report pane, and
        a two-sentence citation in it would push the numbers off the end. The bundle's
        disclaimer sits in the same place for the same reason.
        """
        ranked = sorted(
            self.outcomes,
            key=lambda o: (o.schema_valid, o.correct_fields / len(o.fields)),
        )
        return "\n".join([self.summary(), *(f"  {outcome}" for outcome in ranked), self.citation])


def score_task_set(
    tasks: Sequence[CompilationTask],
    candidates: dict[str, Any],
    *,
    configuration: str,
    parse_errors: dict[str, str] | None = None,
) -> CompilationReport:
    """Score a whole task set, refusing to silently drop a task nobody attempted.

    ``candidates`` maps task id to the parsed spec; ``parse_errors`` maps task id to why the
    output did not parse. A task in neither mapping is an error rather than an omission: a
    run that skipped the hard tasks would otherwise report the easy ones' numbers.
    """
    errors = parse_errors or {}
    missing = [
        task.task_id
        for task in tasks
        if task.task_id not in candidates and task.task_id not in errors
    ]
    if missing:
        raise _compilation_input_refusal(
            f"{len(missing)} task(s) have neither a candidate nor a parse error: {missing}. "
            "A skipped task is not a task that scored zero, and dropping it silently "
            "reports the remaining tasks' numbers as the run's",
            subject="tasks, candidates, and parse_errors",
            source=_RUN_SOURCE,
        )
    return CompilationReport(
        outcomes=tuple(
            score_candidate(
                task,
                candidates.get(task.task_id),
                parse_error=errors.get(task.task_id),
            )
            for task in tasks
        ),
        configuration=configuration,
    )


class CompilationAttempt(StatableModel):
    """One corpus task's validated result or its bounded compilation failure."""

    model_config = ConfigDict(frozen=True)

    task_id: Named
    result: CompilationResult | None = None
    failure: CompilationProvenance | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _is_exactly_one_outcome(self) -> CompilationAttempt:
        if (self.result is None) == (self.failure is None):
            raise _compilation_input_refusal(
                f"compilation attempt {self.task_id!r} must carry exactly one of result or failure",
                subject="result and failure",
                source=_RUN_SOURCE,
            )
        if self.result is not None:
            if self.error is not None or not self.result.provenance.succeeded:
                raise _compilation_input_refusal(
                    f"successful compilation attempt {self.task_id!r} cannot carry a failure",
                    subject="result and error",
                    source=_RUN_SOURCE,
                )
        elif self.error is None or self.failure is None or self.failure.succeeded:
            raise _compilation_input_refusal(
                f"failed compilation attempt {self.task_id!r} needs an unsuccessful "
                "provenance record and its error",
                subject="failure and error",
                source=_RUN_SOURCE,
            )
        return self


class CompilationEvaluation(StatableModel):
    """Every attempt in a versioned corpus and the three-number report derived from them."""

    model_config = ConfigDict(frozen=True)

    task_set_version: str
    attempts: tuple[CompilationAttempt, ...]
    report: CompilationReport

    @model_validator(mode="after")
    def _report_covers_the_attempts(self) -> CompilationEvaluation:
        attempted = tuple(attempt.task_id for attempt in self.attempts)
        reported = tuple(outcome.task_id for outcome in self.report.outcomes)
        if attempted != reported:
            raise _compilation_input_refusal(
                "compilation evaluation attempts and report outcomes differ: "
                f"attempted {attempted}, reported {reported}",
                subject="attempts and report",
                source=_RUN_SOURCE,
            )
        return self


class CompilationRecommendationPolicy(StatableModel):
    """The explicitly declared release thresholds for one compilation task-set version."""

    model_config = ConfigDict(frozen=True)

    task_set_version: str
    minimum_schema_validity: float = Field(ge=0.0, le=1.0)
    minimum_field_correctness: float = Field(ge=0.0, le=1.0)
    maximum_wrong_but_valid_rate: float = Field(ge=0.0, le=1.0)
    reference: Provenance

    @field_validator("task_set_version")
    @classmethod
    def _version_is_semantic(cls, value: str) -> str:
        if _SEMVER.fullmatch(value) is None:
            raise _compilation_input_refusal(
                "recommendation policy task-set version must be semantic (X.Y.Z)",
                subject="task_set_version",
                source=_POLICY_SOURCE,
            )
        return value


class CompilationRecommendation(StatableModel):
    """A release-gate decision that keeps all three compilation measures visible."""

    model_config = ConfigDict(frozen=True)

    task_set_version: str
    configuration: DecodingConfiguration
    schema_validity: float = Field(ge=0.0, le=1.0)
    field_correctness: float = Field(ge=0.0, le=1.0)
    wrong_but_valid_rate: float = Field(ge=0.0, le=1.0)
    policy: CompilationRecommendationPolicy
    recommended: bool
    reasons: tuple[str, ...]

    @model_validator(mode="after")
    def _decision_matches_its_reasons(self) -> CompilationRecommendation:
        if self.recommended == bool(self.reasons):
            raise _compilation_input_refusal(
                "a recommended model has no failing gates; a refusal names at least one",
                subject="recommended and reasons",
                source=_RUN_SOURCE,
            )
        return self

    def render_markdown(self) -> str:
        """Render release-note-ready evidence without inventing a composite score."""
        decoding = (
            f"{self.configuration.mode.value}; schema {self.configuration.schema_version}; "
            f"retry budget {self.configuration.retry_budget}"
        )
        decision = "recommended" if self.recommended else "not recommended"
        lines = [
            "| Model | Backend | Task set | Decoding | Schema validity | "
            "Field correctness | Wrong-but-valid | Decision |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
            f"| {self.configuration.model} | {self.configuration.backend} | "
            f"{self.task_set_version} | {decoding} | {self.schema_validity:.1%} | "
            f"{self.field_correctness:.1%} | {self.wrong_but_valid_rate:.1%} | "
            f"{decision} |",
            "",
            (
                "Policy: schema validity >= "
                f"{self.policy.minimum_schema_validity:.1%}; field correctness >= "
                f"{self.policy.minimum_field_correctness:.1%}; wrong-but-valid <= "
                f"{self.policy.maximum_wrong_but_valid_rate:.1%}. "
                f"Source: {self.policy.reference}"
            ),
        ]
        if self.reasons:
            lines.extend(("", "Gate failures:", *(f"- {reason}" for reason in self.reasons)))
        return "\n".join(lines)


def assess_compilation_recommendation(
    evaluation: CompilationEvaluation,
    policy: CompilationRecommendationPolicy,
) -> CompilationRecommendation:
    """Apply every declared gate to complete, current evidence for one model configuration."""
    if evaluation.task_set_version != policy.task_set_version:
        raise _compilation_input_refusal(
            "compilation evidence is stale for this recommendation policy: "
            f"run {evaluation.task_set_version}, policy {policy.task_set_version}",
            subject="evaluation and policy",
            source=_POLICY_SOURCE,
        )

    configurations = tuple(
        attempt.result.provenance.configuration
        if attempt.result is not None
        else attempt.failure.configuration  # type: ignore[union-attr]
        for attempt in evaluation.attempts
    )
    configuration = configurations[0]
    if any(candidate != configuration for candidate in configurations[1:]):
        raise _compilation_input_refusal(
            "recommendation evidence contains more than one decoding configuration",
            subject="evaluation",
            source=_RUN_SOURCE,
        )
    if configuration.schema_version != SCHEMA_VERSION:
        raise _compilation_input_refusal(
            "compilation evidence uses stale Spec IR schema "
            f"{configuration.schema_version}; current schema is {SCHEMA_VERSION}",
            subject="evaluation",
            source=_RUN_SOURCE,
        )

    report = evaluation.report
    reasons: list[str] = []
    if report.schema_validity < policy.minimum_schema_validity:
        reasons.append(
            f"schema validity {report.schema_validity:.1%} is below "
            f"{policy.minimum_schema_validity:.1%}"
        )
    if report.field_correctness < policy.minimum_field_correctness:
        reasons.append(
            f"field correctness {report.field_correctness:.1%} is below "
            f"{policy.minimum_field_correctness:.1%}"
        )
    if report.wrong_but_valid_rate > policy.maximum_wrong_but_valid_rate:
        reasons.append(
            f"wrong-but-valid rate {report.wrong_but_valid_rate:.1%} exceeds "
            f"{policy.maximum_wrong_but_valid_rate:.1%}"
        )
    return CompilationRecommendation(
        task_set_version=evaluation.task_set_version,
        configuration=configuration,
        schema_validity=report.schema_validity,
        field_correctness=report.field_correctness,
        wrong_but_valid_rate=report.wrong_but_valid_rate,
        policy=policy,
        recommended=not reasons,
        reasons=tuple(reasons),
    )


def evaluate_task_set(
    task_set: CompilationTaskSet,
    backend: CompilationBackend,
    *,
    retry_budget: int = 2,
) -> CompilationEvaluation:
    """Compile and score every task without dropping bounded compilation failures.

    A backend exception is not a candidate that failed schema validation: it aborts the run
    rather than publishing a partial report as a complete measurement. Only
    :class:`CompilationFailure`, which proves the bounded packaging attempts ran, becomes a
    schema-invalid task outcome.
    """
    issues = task_set_issues(task_set)
    if issues:
        raise _compilation_input_refusal(
            "the compilation task set is stale: " + "; ".join(issues),
            subject="task_set",
            source=_TASK_SET_SOURCE,
        )

    attempts: list[CompilationAttempt] = []
    candidates: dict[str, DesignSpec] = {}
    parse_errors: dict[str, str] = {}
    configurations: list[DecodingConfiguration] = []
    for task in task_set.tasks:
        try:
            result = compile_intent(task.prompt, backend, retry_budget=retry_budget)
        except CompilationFailure as failure:
            message = str(failure)
            attempts.append(
                CompilationAttempt(
                    task_id=task.task_id,
                    failure=failure.provenance,
                    error=message,
                )
            )
            parse_errors[task.task_id] = message
            configurations.append(failure.provenance.configuration)
        else:
            attempts.append(CompilationAttempt(task_id=task.task_id, result=result))
            candidates[task.task_id] = result.spec
            configurations.append(result.provenance.configuration)

    first = configurations[0]
    if any(configuration != first for configuration in configurations[1:]):
        raise _compilation_input_refusal(
            "one evaluation run produced more than one decoding configuration",
            subject="backend",
            source=_BACKEND_SOURCE,
        )
    label = (
        f"task set {task_set.version}; backend {first.backend}; model {first.model}; "
        f"{first.mode.value}; schema {first.schema_version}; retry budget {first.retry_budget}"
    )
    report = score_task_set(
        task_set.tasks,
        candidates,
        parse_errors=parse_errors,
        configuration=label,
    )
    return CompilationEvaluation(
        task_set_version=task_set.version,
        attempts=tuple(attempts),
        report=report,
    )
