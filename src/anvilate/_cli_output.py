"""The versioned wire contract for machine-readable CLI results.

The CLI builds ordinary dictionaries because the same structures also feed the text
renderers.  These models describe those dictionaries exactly, so the published schema can
be generated and every real command result can be held against it without making a second
implementation of the command.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, TypeAdapter

from ._models import FrozenMap, Named, RevalidatedModel
from .attestation import SignatureState
from .bundle import BundleDocument
from .scorecard import CheckStatus, Scorecard

__all__: list[str] = []

CLI_OUTPUT_SCHEMA_VERSION = "1.4.3"
CLI_OUTPUT_SCHEMA_ID = f"https://anvilate.dev/schemas/cli-output/{CLI_OUTPUT_SCHEMA_VERSION}.json"
SchemaId = Literal["https://anvilate.dev/schemas/cli-output/1.4.3.json"]
SchemaVersion = Literal["1.4.3"]


class _WireModel(RevalidatedModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GoverningCheck(_WireModel):
    name: Named
    status: CheckStatus


class CheckedSpec(_WireModel):
    path: str
    name: Named
    status: CheckStatus
    governing: GoverningCheck | None
    scorecard: Scorecard


class CheckOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Literal["check"]
    status: CheckStatus
    specs: tuple[CheckedSpec, ...]


class BuildArtifact(_WireModel):
    path: str
    format: Literal["step"]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    pattern: Literal["base_plate/1"]
    volume_mm3: Annotated[float, Field(gt=0)]
    dimensions_mm: FrozenMap[str, Annotated[float, Field(gt=0)]] = Field(
        json_schema_extra={
            "additionalProperties": {"type": "number", "exclusiveMinimum": 0}
        }
    )
    face_tags: tuple[Named, ...]


class BuildOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Literal["build"]
    name: Named
    source: Named
    artifact: BuildArtifact


class EvidenceBundleOutputEntry(_WireModel):
    path: str
    name: Named
    bundle: BundleDocument


class EvidenceBundleOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Literal["export"]
    artifact: Literal["evidence-bundle"]
    status: CheckStatus
    bundles: tuple[EvidenceBundleOutputEntry, ...]


class QifOutputEntry(_WireModel):
    path: str
    name: Named
    format: Literal["qif"]
    qif: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class QifOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Literal["export"]
    artifact: Literal["qif"]
    status: CheckStatus
    documents: tuple[QifOutputEntry, ...]


class ToolComponent(_WireModel):
    name: str | None
    version: str | None


class VerifyOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Literal["verify"]
    bundle_digest: str
    signature_state: SignatureState
    predicate_type: str
    checked_subjects: tuple[str, ...]
    unchecked_subjects: tuple[str, ...]
    unverified_signatures: tuple[str, ...]
    unread_predicate_keys: tuple[str, ...]
    problems: tuple[str, ...]
    status: CheckStatus
    attested: bool
    producer: ToolComponent | None
    toolchain: tuple[ToolComponent, ...]


class DiffEndpoint(_WireModel):
    path: str
    name: Named
    status: CheckStatus


class SpecDifference(_WireModel):
    changed: bool
    lines: tuple[str, ...]


class VerdictDifference(_WireModel):
    before: CheckStatus
    after: CheckStatus
    worse: bool


class MarginDifference(_WireModel):
    before: float | None
    after: float | None
    worse: bool


class CheckDifference(_WireModel):
    name: Named
    change: Literal["added", "removed", "moved", "margin"]
    before: CheckStatus | None
    after: CheckStatus | None
    detail: str | None
    margin: MarginDifference | None
    worse: bool


class CheckDifferences(_WireModel):
    moved: tuple[CheckDifference, ...]
    unchanged: Annotated[int, Field(ge=0)]


class GeometryDifference(_WireModel):
    compared: Literal[False]
    reason: str


class Regression(_WireModel):
    regressed: bool
    status: CheckStatus | None


class DiffOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Literal["diff"]
    before: DiffEndpoint
    after: DiffEndpoint
    spec: SpecDifference
    verdict: VerdictDifference
    checks: CheckDifferences
    geometry: GeometryDifference
    regression: Regression


class RefusalOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Named
    outcome: Literal["refused"]
    exit_code: Literal[1, 2, 3, 4]
    diagnostics: Annotated[tuple[Named, ...], Field(min_length=1)]
    remedy: Named


class ErrorOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Named
    outcome: Literal["error"]
    exit_code: Literal[5]
    diagnostic: Named
    remedy: Named


class DoctorCheck(_WireModel):
    name: Named
    status: Literal["pass", "fail"]
    detail: Named
    remedy: Named | None


class DoctorOutput(_WireModel):
    schema_: SchemaId = Field(alias="schema")
    schema_version: SchemaVersion
    command: Literal["doctor"]
    status: Literal["pass", "fail"]
    checks: tuple[DoctorCheck, ...]


CliOutput = (
    BuildOutput
    | CheckOutput
    | EvidenceBundleOutput
    | QifOutput
    | VerifyOutput
    | DiffOutput
    | RefusalOutput
    | ErrorOutput
    | DoctorOutput
)


def cli_output_json_schema() -> dict:
    """JSON Schema for every completed machine-readable CLI document."""
    return TypeAdapter(CliOutput).json_schema(mode="serialization")


def machine_document(command: str, payload: dict, *, artifact: str | None = None) -> dict:
    """Attach the common contract identity to one command payload."""
    metadata = {
        "schema": CLI_OUTPUT_SCHEMA_ID,
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": command,
    }
    if artifact is not None:
        metadata["artifact"] = artifact
    return {**metadata, **payload}


def refusal_document(
    command: str, *, exit_code: int, diagnostics: tuple[str, ...], remedy: str
) -> dict:
    """One rejected invocation, preserving the exact human diagnostics as data."""
    return machine_document(
        command,
        {
            "outcome": "refused",
            "exit_code": exit_code,
            "diagnostics": diagnostics,
            "remedy": remedy,
        },
    )


def error_document(command: str, *, diagnostic: str, remedy: str) -> dict:
    """One unexpected tool defect as a stable machine-readable result."""
    return machine_document(
        command,
        {"outcome": "error", "exit_code": 5, "diagnostic": diagnostic, "remedy": remedy},
    )
