"""Exact immutable verifier inputs; constructing a value grants no authority."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import PosixPath
from typing import Any, Protocol
from uuid import UUID

from analysis.ifds.bound_rules import QualifiedRuleKey, encode_qualified_rule_key

from . import schemas as s


def raw(value: object, maximum: int, *, empty: bool = False) -> bytes:
    s.require(type(value) is bytes)
    assert isinstance(value, bytes)
    s.require((bool(value) or empty) and len(value) <= maximum)
    return value


def _uuid_text(value: UUID) -> str:
    s.require(type(value) is UUID)
    integer = object.__getattribute__(value, "int")
    s.require(type(integer) is int and 0 <= integer < 2**128)
    return str(UUID(int=integer))


def _path_snapshot(value: object) -> PosixPath:
    """Bounded CPython 3.11/3.12 layouts; ignore mutable cached path strings."""
    s.require(type(value) is PosixPath)
    try:
        parts = object.__getattribute__(value, "_raw_paths")  # CPython 3.12.
    except AttributeError:
        try:
            parts = object.__getattribute__(value, "_parts")  # CPython 3.11.
        except AttributeError as error:
            raise s.VerificationError("runtime-unsupported") from error
    s.require(type(parts) is list and 0 < len(parts) <= 4096)
    # A bounded built-in slice also prevents a racing growth from expanding the
    # snapshot without a limit. No caller iterator/string callback is invoked.
    snapshot = tuple(parts[:4097])
    s.require(0 < len(snapshot) <= 4096)
    length = 0
    for part in snapshot:
        s.require(type(part) is str)
        length += len(part) + 1
        s.require(length <= 4098)
        s.text(part, 4096)
    fresh = PosixPath(*snapshot)
    s.shape(str(fresh), "path")
    return fresh


def _wire(value: object, depth: int, budget: list[int]) -> Any:  # noqa: ANN401
    budget[0] += 1
    s.require(depth <= s.MAX_DEPTH and budget[0] <= s.MAX_VALUES)
    if type(value) is UUID:
        return _uuid_text(value)
    if type(value) is PosixPath:
        return str(_path_snapshot(value))
    if type(value) is tuple:
        s.require(len(value) <= s.MAX_VALUES - budget[0])
        return [_wire(item, depth + 1, budget) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) in _RECORDS:
        definitions = fields(value)  # type: ignore[arg-type]
        budget[0] += len(definitions)
        s.require(budget[0] + len(definitions) <= s.MAX_VALUES)
        return {
            field.name: _wire(getattr(value, field.name), depth + 1, budget)
            for field in definitions
        }
    raise s.VerificationError()


def record_dict(value: object) -> dict[str, Any]:
    s.require(type(value) in _RECORDS)
    return _wire(value, 0, [0])  # type: ignore[no-any-return]


def _validate_record(value: object, schema: str | dict[str, Any]) -> None:
    s.require(type(value) in _RECORDS)
    # UUID/path representations on the wire must not hide incorrect model types.
    if isinstance(schema, str):
        rules = s.SHAPES[schema]
    else:
        rules = schema
    for name, rule in rules.items():
        member = getattr(value, name)
        actual_rule = rule[1] if type(rule) is tuple and rule[0] == "nullable" else rule
        if member is not None and actual_rule == "uuid":
            s.require(type(member) is UUID)
        if member is not None and actual_rule == "path":
            s.require(type(member) is PosixPath)
        if member is not None and type(actual_rule) is str:
            if actual_rule in ("count", "positive"):
                s.require(type(member) is int)
            elif actual_rule not in ("uuid", "path"):
                s.require(type(member) is str)
        if type(actual_rule) is tuple and actual_rule[0] == "enum":
            s.shape(member, rule)
    document = record_dict(value)
    if isinstance(schema, str):
        s.validate_document(document, schema)
    else:
        s.shape(document, schema)
        s.scoped(document)


@dataclass(frozen=True, slots=True)
class InstalledTrust:
    deployment_id: UUID
    registry_id: UUID
    scope: str
    org_id: UUID | None
    root_spki_sha256: str
    administrator_actor_id: UUID
    schema: str = s.INSTALLED_TRUST

    def __post_init__(self) -> None:
        _validate_record(self, s.INSTALLED_TRUST)


@dataclass(frozen=True, slots=True)
class BundleExpectation:
    registry_id: UUID
    bundle_id: UUID
    scope: str
    org_id: UUID | None
    S_version: str
    accepted_content_digest: str

    def __post_init__(self) -> None:
        _validate_record(self, s.BUNDLE_EXPECTATION)


@dataclass(frozen=True, slots=True)
class AdmissionExpectation:
    checkpoint_digest: str
    checkpoint_generation: int
    admission_epoch: UUID
    policy_digest: str
    policy_revision: int

    def __post_init__(self) -> None:
        _validate_record(self, s.ADMISSION_EXPECTATION)


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    org_id: UUID
    codebase_id: UUID
    request_id: UUID
    capture_id: UUID
    seal_id: UUID
    work_item_id: UUID
    work_attempt_id: UUID
    detector_run_id: UUID
    capture_lease_id: UUID
    authorization_event_id: UUID
    fencing_token: int
    work_revision: int
    run_input_digest: str
    requested_policy_digest: str
    attempt_policy_digest: str
    authorization_digest: str
    lease_expires_at: str
    capture_lease_expires_at: str

    def __post_init__(self) -> None:
        _validate_record(self, s.EXECUTION_BINDING)


@dataclass(frozen=True, slots=True)
class LedgerExpectation:
    publication_receipt_digest: str
    request_binding_digest: str
    execution_authorization_digest: str | None
    binding: ExecutionBinding | None
    policy_event_id: UUID | None
    admission_event_id: UUID | None

    def __post_init__(self) -> None:
        s.require(self.binding is None or type(self.binding) is ExecutionBinding)
        if self.binding is not None:
            ExecutionBinding.__post_init__(self.binding)
        _validate_record(self, s.LEDGER_EXPECTATION)
        present = self.binding is not None
        for value in (
            self.execution_authorization_digest,
            self.policy_event_id,
            self.admission_event_id,
        ):
            s.require((value is not None) == present)
        if present:
            assert self.binding is not None
            s.require(self.execution_authorization_digest == self.binding.authorization_digest)


@dataclass(frozen=True, slots=True)
class AcceptedBundleBytes:
    spec_bytes: bytes
    detector_blobs: tuple[bytes, ...]
    rule_blobs: tuple[bytes, ...]

    def __post_init__(self) -> None:
        s.require(type(self) is AcceptedBundleBytes)
        raw(self.spec_bytes, s.MAX_CONTENT)
        total = len(self.spec_bytes)
        for values in (self.detector_blobs, self.rule_blobs):
            s.require(type(values) is tuple and 0 < len(values) <= s.MAX_VALUES)
            for value in values:
                raw(value, s.MAX_CONTENT)
                total += len(value)
                s.require(total <= s.MAX_CONTENT)
        from .codec import validate_bundle_layout

        validate_bundle_layout(self)


@dataclass(frozen=True, slots=True)
class VerificationChecks:
    accepted_content_digest: str
    approval_event_id: UUID
    approval_statement_digest: str
    publication_receipt_digest: str | None
    qualified_rule_digest: str | None
    execution_authorization_digest: str | None
    current_policy_digest: str | None
    current_policy_revision: int | None
    checkpoint_digest: str | None
    checkpoint_generation: int | None
    admission_epoch: UUID | None
    verified_at: str
    permission_expires_at: str | None

    def __post_init__(self) -> None:
        _validate_record(self, s.CHECKS)


@dataclass(frozen=True, slots=True)
class ResolvedQualifiedRule:
    qualified_rule: QualifiedRuleKey
    bundle: AcceptedBundleBytes
    sealed_authority_evidence: bytes
    execution_authorization: bytes
    binding: ExecutionBinding

    def __post_init__(self) -> None:
        s.require(type(self) is ResolvedQualifiedRule and type(self.bundle) is AcceptedBundleBytes)
        s.require(type(self.binding) is ExecutionBinding)
        AcceptedBundleBytes.__post_init__(self.bundle)
        ExecutionBinding.__post_init__(self.binding)
        encode_qualified_rule_key(self.qualified_rule)
        raw(self.sealed_authority_evidence, s.MAX_AUTHORITY)
        raw(self.execution_authorization, s.MAX_OBJECT)
        from .codec import selected_content

        selected_content(self.bundle, self.qualified_rule)

    @property
    def detector_bytes(self) -> bytes:
        from .codec import selected_content

        return selected_content(self.bundle, self.qualified_rule)[0]

    @property
    def rule_bytes(self) -> bytes:
        from .codec import selected_content

        return selected_content(self.bundle, self.qualified_rule)[1]

    @property
    def model_bytes(self) -> bytes:
        from .codec import selected_content

        return selected_content(self.bundle, self.qualified_rule)[2]


@dataclass(frozen=True, slots=True)
class VerifiedQualifiedRule:
    resolved: ResolvedQualifiedRule
    checks: VerificationChecks

    def __post_init__(self) -> None:
        s.require(
            type(self) is VerifiedQualifiedRule and type(self.resolved) is ResolvedQualifiedRule
        )
        s.require(type(self.checks) is VerificationChecks)
        ResolvedQualifiedRule.__post_init__(self.resolved)
        VerificationChecks.__post_init__(self.checks)
        s.validate_checks(record_dict(self.checks), "execution")


@dataclass(frozen=True, slots=True)
class VerifiedHistoricalApproval:
    checks: VerificationChecks

    def __post_init__(self) -> None:
        s.require(
            type(self) is VerifiedHistoricalApproval and type(self.checks) is VerificationChecks
        )
        VerificationChecks.__post_init__(self.checks)
        s.validate_checks(record_dict(self.checks), "historical")


@dataclass(frozen=True, slots=True)
class VerifiedCurrentPolicy:
    policy_digest: str
    policy_revision: int
    checkpoint_digest: str
    checkpoint_generation: int
    admission_epoch: UUID
    permission_expires_at: str

    def __post_init__(self) -> None:
        _validate_record(self, {**s.ADMISSION_EXPECTATION, "permission_expires_at": "instant"})


@dataclass(frozen=True, slots=True)
class ExecutionVerificationContext:
    installed_trust: InstalledTrust
    admission: AdmissionExpectation
    ledger: LedgerExpectation
    live_authority_evidence: bytes
    reference_time: str

    def __post_init__(self) -> None:
        s.require(type(self) is ExecutionVerificationContext)
        for value, expected in (
            (self.installed_trust, InstalledTrust),
            (self.admission, AdmissionExpectation),
            (self.ledger, LedgerExpectation),
        ):
            s.require(type(value) is expected)
            expected.__post_init__(value)  # type: ignore[arg-type]
        s.require(self.ledger.binding is not None)
        raw(self.live_authority_evidence, s.MAX_LIVE)
        s.shape(self.reference_time, "instant")


@dataclass(frozen=True, slots=True)
class VerifierRuntimeDocument:
    implementation: str
    python_version: str
    python_executable: PosixPath
    python_executable_sha256: str
    worker_script: PosixPath
    worker_script_sha256: str
    application_root: PosixPath
    application_artifact_digest: str
    stdlib_roots: tuple[PosixPath, ...]
    dependency_roots: tuple[PosixPath, ...]
    dependency_artifact_digest: str
    verifier_artifact_digest: str
    work_root: PosixPath
    resource_profile: str = "scanipy-verifier-limits/1"
    schema: str = s.RUNTIME

    def __post_init__(self) -> None:
        s.require(type(self) is VerifierRuntimeDocument)
        for name in ("python_executable", "worker_script", "application_root", "work_root"):
            object.__setattr__(self, name, _path_snapshot(getattr(self, name)))
        for name in ("stdlib_roots", "dependency_roots"):
            roots = getattr(self, name)
            s.require(type(roots) is tuple and 1 <= len(roots) <= 4)
            object.__setattr__(self, name, tuple(_path_snapshot(root) for root in roots))
        _validate_record(self, s.RUNTIME)


@dataclass(frozen=True, slots=True)
class VerifierRuntimeProfile:
    profile_path: PosixPath
    profile_sha256: str
    document: VerifierRuntimeDocument

    def __post_init__(self) -> None:
        s.require(type(self) is VerifierRuntimeProfile and type(self.profile_path) is PosixPath)
        s.require(type(self.document) is VerifierRuntimeDocument)
        object.__setattr__(self, "profile_path", _path_snapshot(self.profile_path))
        s.shape(self.profile_sha256, "digest")
        VerifierRuntimeDocument.__post_init__(self.document)


class ExecutionAuthorityReader(Protocol):
    """Installed trusted adapter port, never a scan-selected callback registry."""

    runtime_profile: VerifierRuntimeProfile

    def read_execution_authority(
        self, expected: ExecutionBinding
    ) -> ExecutionVerificationContext: ...

    def recheck_execution_authority(
        self, expected: ExecutionBinding, context: ExecutionVerificationContext
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class VerifierRequest:
    operation_id: UUID
    mode: str
    installed_trust: InstalledTrust
    expected_bundle: BundleExpectation
    reference_time: str
    verifier_artifact_digest: str
    admission: AdmissionExpectation | None
    ledger: LedgerExpectation | None
    selected_rule: QualifiedRuleKey | None
    bundle: AcceptedBundleBytes
    authority_evidence: bytes
    live_authority_evidence: bytes = b""
    execution_authorization: bytes = b""

    def __post_init__(self) -> None:
        s.require(type(self) is VerifierRequest and type(self.operation_id) is UUID)
        object.__setattr__(self, "operation_id", UUID(_uuid_text(self.operation_id)))
        s.require(type(self.mode) is str and self.mode in s.MODES)
        for value, expected in (
            (self.installed_trust, InstalledTrust),
            (self.expected_bundle, BundleExpectation),
            (self.bundle, AcceptedBundleBytes),
        ):
            s.require(type(value) is expected)
            expected.__post_init__(value)  # type: ignore[arg-type]
        for optional_value, optional_type in (
            (self.admission, AdmissionExpectation),
            (self.ledger, LedgerExpectation),
        ):
            s.require(optional_value is None or type(optional_value) is optional_type)
            if optional_value is not None:
                optional_type.__post_init__(optional_value)  # type: ignore[arg-type]
        s.shape(self.reference_time, "instant")
        s.shape(self.verifier_artifact_digest, "digest")
        raw(self.authority_evidence, s.MAX_AUTHORITY)
        raw(self.live_authority_evidence, s.MAX_LIVE, empty=True)
        raw(self.execution_authorization, s.MAX_OBJECT, empty=True)
        if self.mode == "publication-preflight":
            s.require(
                self.admission is not None and self.ledger is None and self.selected_rule is None
            )
        elif self.mode == "historical":
            s.require(
                self.admission is None and self.ledger is not None and self.selected_rule is None
            )
            assert self.ledger is not None
            s.require(self.ledger.binding is None)
        else:
            s.require(
                self.admission is not None
                and self.ledger is not None
                and self.selected_rule is not None
            )
            assert self.ledger is not None
            s.require(self.ledger.binding is not None)
            encode_qualified_rule_key(self.selected_rule)  # type: ignore[arg-type]
        s.require(bool(self.live_authority_evidence) == (self.mode == "execution"))
        s.require(bool(self.execution_authorization) == (self.mode == "execution"))


@dataclass(frozen=True, slots=True)
class VerificationResult:
    operation_id: UUID | None
    request_sha256: str | None
    mode: str | None
    status: str
    failure_code: str | None
    checks: VerificationChecks | None
    schema: str = s.RESULT

    def __post_init__(self) -> None:
        s.require(self.checks is None or type(self.checks) is VerificationChecks)
        if self.checks is not None:
            VerificationChecks.__post_init__(self.checks)
        _validate_record(self, s.RESULT)


_RECORDS = frozenset(
    (
        InstalledTrust,
        BundleExpectation,
        AdmissionExpectation,
        ExecutionBinding,
        LedgerExpectation,
        VerificationChecks,
        VerifiedCurrentPolicy,
        VerifierRuntimeDocument,
        VerificationResult,
    )
)
