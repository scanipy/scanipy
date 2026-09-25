"""Actual local custody/proof integration using raw fixture DATA, no native Git."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from integrations.scm import git_objects as git
from integrations.scm import source_acquisition as acq
from services.scan import source_capture as custody

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_native(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("native execution is not allowed by offline fixture")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def fixtures(
    tmp_path: Path, files: dict[str, bytes] | None = None
) -> tuple[Path, Path, Path, custody.CaptureBinding]:
    objects = tmp_path / "objects"
    store = tmp_path / "store"
    evidence = tmp_path / "evidence"
    for root in (objects, store, evidence):
        root.mkdir(mode=0o700)
    files = files if files is not None else {"a.py": b"not executed\0\xff\n", "empty": b""}

    def add(category: bytes, content: bytes) -> str:
        payload = category + b" " + str(len(content)).encode() + b"\0" + content
        oid = hashlib.sha1(payload, usedforsecurity=False).hexdigest()
        path = objects / (oid + ".object")
        if not path.exists():
            path.write_bytes(payload)
            path.chmod(0o600)
        return oid

    tree = bytearray()
    for name, content in sorted(files.items()):
        tree.extend(b"100755 " + name.encode() + b"\0" + bytes.fromhex(add(b"blob", content)))
    root_oid = add(b"tree", bytes(tree))
    commit = add(b"commit", b"tree " + root_oid.encode() + b"\n\nexact fixture\n")
    return objects, store, evidence, custody.CaptureBinding(uuid4(), uuid4(), uuid4(), commit)


def capture(
    roots: tuple[Path, Path, Path, custody.CaptureBinding], **kwargs: object
) -> acq.GitCaptureResult:
    objects, store, evidence, binding = roots
    return acq.capture_offline_objects(
        objects,
        store_root=store,
        evidence_root=evidence,
        binding=binding,
        limits=git.GitCaptureLimits(),
        **kwargs,
    )


def verify(
    roots: tuple[Path, Path, Path, custody.CaptureBinding], result: acq.GitCaptureResult
) -> acq.GitCaptureResult:
    return acq.verify_offline_capture(
        store_root=roots[1],
        evidence_root=roots[2],
        expected_receipt=result.receipt,
        proof_id=result.proof_id,
        expected_proof_digest=result.proof_digest,
    )


def rewrite(path: Path, data: bytes) -> None:
    path.chmod(0o600)
    path.write_bytes(data)
    path.chmod(0o444)


def test_real_capture_receipt_and_replay(tmp_path: Path) -> None:
    roots = fixtures(tmp_path)
    result = capture(roots, repository_claim=acq.GitHubRepositoryClaim("owner", "project"))
    assert result.operation == "created-offline"
    assert result.receipt.binding == roots[3]
    assert acq.decode_receipt(acq.encode_receipt(result.receipt)) == result.receipt
    source = custody.LocalSourceCaptureStore(roots[1]).verify(result.receipt)
    assert (source / "a.py").read_bytes() == b"not executed\0\xff\n"
    assert stat.S_IMODE((source / "a.py").stat().st_mode) == 0o444
    assert set(source.parent.iterdir()) == {
        source,
        source.parent / "manifest.json",
        source.parent / "SEALED",
    }
    proof_root = roots[2] / str(result.proof_id)
    before = {
        str(path.relative_to(proof_root)): path.read_bytes()
        for path in proof_root.rglob("*")
        if path.is_file()
    }
    proof = json.loads(before["proof.json"])
    assert proof["native_execution"] == "not_performed"
    assert proof["remote_authentication"] == proof["controller_attestation"] == "not_established"
    assert proof["files"][0]["mode"] == "100755"
    producer = json.loads(before["producer.json"])
    assert (
        producer["child_argv"]
        is producer["image_manifest_digest"]
        is producer["code_revision"]
        is None
    )
    assert producer["source_file_binding"] == "observed-file-bytes-only"
    replay = verify(roots, result)
    assert replay.operation == "verified-existing"
    assert replay.receipt == result.receipt and replay.proof_digest == result.proof_digest
    assert before == {
        str(path.relative_to(proof_root)): path.read_bytes()
        for path in proof_root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "bad",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":1.0}',
        b' {"x":1}',
        b'{"x":-0}',
        b'{"x":"\\ud800"}',
        b"{}{}",
        b"[" * 25 + b"]" * 25,
        b'{"x":9223372036854775808}',
    ],
)
def test_canonical_json_refuses(tmp_path: Path, bad: bytes) -> None:
    with pytest.raises((acq.GitCaptureError, UnicodeError)):
        acq.decode_json(bad)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "field", ["unknown", "bool-count", "wrong-scope", "wrong-hash", "base64", "extra-inventory"]
)
def test_receipt_codec_refuses(tmp_path: Path, field: str) -> None:
    result = capture(fixtures(tmp_path))
    data = json.loads(acq.encode_receipt(result.receipt))
    if field == "unknown":
        data["unknown"] = None
    elif field == "bool-count":
        data["file_count"] = True
    elif field == "wrong-scope":
        data["binding"]["extra"] = "no"
    elif field == "wrong-hash":
        data["inventory_digest"] = "0" * 64
    elif field == "base64":
        data["inventory_bytes_b64"] += "="
    else:
        import base64

        raw = json.loads(result.receipt.inventory_bytes)
        raw["extra"] = 1
        raw_bytes = acq.canonical_bytes(raw)
        data["inventory_bytes_b64"] = base64.b64encode(raw_bytes).decode()
        data["inventory_digest"] = hashlib.sha256(
            custody.INVENTORY_SCHEMA.encode() + b"\n" + raw_bytes
        ).hexdigest()
    with pytest.raises((acq.GitCaptureError, ValueError)):
        acq.decode_receipt(acq.canonical_bytes(data))


@pytest.mark.parametrize(
    "artifact",
    [
        "request.json",
        "objects.json",
        "capture-receipt.json",
        "producer.json",
        "commit.object",
        "code/git_objects.py",
        "proof.json",
        "COMPLETE",
    ],
)
def test_any_artifact_tamper_rejects(tmp_path: Path, artifact: str) -> None:
    roots = fixtures(tmp_path)
    result = capture(roots)
    path = roots[2] / str(result.proof_id) / artifact
    rewrite(path, path.read_bytes() + b" ")
    with pytest.raises(acq.GitCaptureError):
        verify(roots, result)


@pytest.mark.parametrize(
    "mutation", ["metadata-mode", "source-hash", "scope", "code", "role", "order", "bool-count"]
)
def test_self_rehashed_proof_is_not_independent_evidence(tmp_path: Path, mutation: str) -> None:
    roots = fixtures(tmp_path)
    result = capture(roots)
    root = roots[2] / str(result.proof_id)
    value = json.loads((root / "proof.json").read_bytes())
    if mutation == "metadata-mode":
        value["files"][0]["mode"] = "100644"
    elif mutation == "source-hash":
        value["files"][0]["payload_sha256"] = "a" * 64
    elif mutation == "scope":
        value["binding"]["request_id"] = str(uuid4())
    elif mutation == "code":
        code = root / "code" / "git_objects.py"
        rewrite(code, b"not the observed code")
        for item in value["artifacts"]:
            if item["path"] == "code/git_objects.py":
                item["sha256"] = hashlib.sha256(code.read_bytes()).hexdigest()
                item["size"] = code.stat().st_size
    elif mutation == "role":
        value["artifacts"][0]["path"] = "../escape"
    elif mutation == "order":
        value["artifacts"].reverse()
    else:
        value["file_count"] = True
    raw = acq.canonical_bytes(value)
    digest = hashlib.sha256(acq.PROOF_SCHEMA.encode() + b"\n" + raw).digest()
    rewrite(root / "proof.json", raw)
    rewrite(root / "COMPLETE", digest.hex().encode() + b"\n")
    with pytest.raises(acq.GitCaptureError):
        verify(roots, result)  # Trusted original digest, not candidate self-hash.
    with pytest.raises(acq.GitCaptureError):
        verify(
            roots, replace(result, proof_digest=digest)
        )  # Raw source/tree/role checks still reject.


def test_source_tamper_cannot_be_hidden_by_git_metadata(tmp_path: Path) -> None:
    roots = fixtures(tmp_path)
    result = capture(roots)
    path = roots[1] / str(result.receipt.object_id) / "source" / "a.py"
    rewrite(path, b"replacement")
    with pytest.raises(acq.GitCaptureError):
        verify(roots, result)


@pytest.mark.parametrize(
    "stage", ["staging", "custody", "capture-verification", "proof-publication"]
)
def test_failures_retain_honest_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    roots = fixtures(tmp_path)

    def failure(*_args: object, **_kwargs: object) -> None:
        raise OSError("private fixture failure")

    if stage == "staging":
        monkeypatch.setattr(acq, "_materialize", failure)
    elif stage == "custody":
        monkeypatch.setattr(custody.LocalSourceCaptureStore, "capture", failure)
    elif stage == "capture-verification":
        monkeypatch.setattr(custody.LocalSourceCaptureStore, "verify", failure)
    else:
        monkeypatch.setattr(acq, "_producer", failure)
    with pytest.raises(acq.GitCaptureError) as caught:
        capture(roots)
    assert caught.value.retained_failure is not None
    value = json.loads(caught.value.retained_failure)
    assert value["stage"] == stage and value["completion_claim"] is False
    assert value["cleanup"] == "not-attempted-retained-for-review"
    expected_state = {
        "staging": "not-started",
        "custody": "unknown",
        "capture-verification": "receipt-returned-unverified",
        "proof-publication": "verified-orphan",
    }[stage]
    assert value["capture_state"] == expected_state
    assert (value["capture_object_id"] is None) == (stage in ("staging", "custody"))
    assert not list(roots[2].glob("*/COMPLETE"))


def test_corrupt_write_rejected_before_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = fixtures(tmp_path)
    original = git.copy_verified_blob

    def corrupt(
        source: int, expected: git.GitObject, destination: int, limits: git.GitCaptureLimits
    ) -> None:
        original(source, expected, destination, limits)
        if expected.size:
            os.lseek(destination, 0, os.SEEK_SET)
            os.write(destination, b"!")

    monkeypatch.setattr(git, "copy_verified_blob", corrupt)
    with pytest.raises(acq.GitCaptureError):
        capture(roots)
    assert list(roots[1].iterdir()) == []


def test_short_writes_and_permissive_umask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    roots = fixtures(tmp_path)
    original = os.write

    def short(fd: int, data: bytes) -> int:
        return original(fd, data[:13])

    monkeypatch.setattr(os, "write", short)
    previous = os.umask(0)
    try:
        result = capture(roots)
    finally:
        os.umask(previous)
    assert verify(roots, result).receipt == result.receipt


def test_online_refuses_without_touching_files(tmp_path: Path) -> None:
    with pytest.raises(acq.GitCaptureError, match="unavailable-online"):
        acq.capture_github_commit()
    assert list(tmp_path.iterdir()) == []


def test_cross_capture_and_scope_not_accepted(tmp_path: Path) -> None:
    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir(mode=0o700)
    second.mkdir(mode=0o700)
    a, b = fixtures(first), fixtures(second)
    result_a, result_b = capture(a), capture(b)
    with pytest.raises(acq.GitCaptureError):
        acq.verify_offline_capture(
            store_root=b[1],
            evidence_root=a[2],
            expected_receipt=result_b.receipt,
            proof_id=result_a.proof_id,
            expected_proof_digest=result_a.proof_digest,
        )


def test_exclusive_attempt_collision_no_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = fixtures(tmp_path)
    identity = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    existing = roots[2] / ("attempt-" + str(identity))
    existing.mkdir(mode=0o700)
    marker = existing / "marker"
    marker.write_bytes(b"preserve")
    monkeypatch.setattr(acq, "uuid4", lambda: identity)
    with pytest.raises(acq.GitCaptureError):
        capture(roots)
    assert marker.read_bytes() == b"preserve" and set(existing.iterdir()) == {marker}
    assert list(roots[1].iterdir()) == []


@pytest.mark.parametrize("target", ["objects", "store", "evidence"])
def test_private_roots_required_before_allocation(tmp_path: Path, target: str) -> None:
    roots = fixtures(tmp_path)
    selected = {"objects": roots[0], "store": roots[1], "evidence": roots[2]}[target]
    selected.chmod(0o755)
    with pytest.raises(acq.GitCaptureError):
        capture(roots)
    assert list(roots[1].iterdir()) == list(roots[2].iterdir()) == []


def test_root_symlink_and_overlap_refused(tmp_path: Path) -> None:
    roots = fixtures(tmp_path)
    alias = tmp_path / "alias"
    alias.symlink_to(roots[0], target_is_directory=True)
    with pytest.raises(acq.GitCaptureError):
        capture((alias, *roots[1:]))
    with pytest.raises(acq.GitCaptureError):
        capture((roots[0], roots[1], roots[1], roots[3]))
    assert list(roots[1].iterdir()) == list(roots[2].iterdir()) == []


@pytest.mark.parametrize("artifact", ["commit.object", "request.json", "code/git_objects.py"])
@pytest.mark.parametrize("kind", ["writable", "symlink", "hardlink"])
def test_published_artifact_permission_and_link_refusal(
    tmp_path: Path, artifact: str, kind: str
) -> None:
    roots = fixtures(tmp_path)
    result = capture(roots)
    path = roots[2] / str(result.proof_id) / artifact
    if kind == "writable":
        path.chmod(0o644)
    elif kind == "symlink":
        copy = tmp_path / "substitute"
        copy.write_bytes(path.read_bytes())
        path.parent.chmod(0o700)
        path.unlink()
        path.symlink_to(copy)
        path.parent.chmod(0o555)
    else:
        os.link(path, tmp_path / "second-link")
    with pytest.raises(acq.GitCaptureError):
        verify(roots, result)


@pytest.mark.parametrize("fault", ["source-observation", "evidence-read", "fsync"])
def test_required_observation_failure_is_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    roots = fixtures(tmp_path)
    active = False
    producer = acq._producer
    reader = acq._read_file
    sync = os.fsync

    def observed_producer() -> tuple[dict[str, object], dict[str, bytes]]:
        nonlocal active
        active = True
        if fault == "source-observation":
            raise OSError("private observed-source read failure")
        return producer()

    def failed_read(
        parent: int, name: str, maximum: int, *, published: bool, tree_remaining: int | None = None
    ) -> bytes:
        if active and fault == "evidence-read" and name == "producer.json":
            raise PermissionError("private evidence read failure")
        return reader(parent, name, maximum, published=published, tree_remaining=tree_remaining)

    def failed_sync(fd: int) -> None:
        nonlocal active
        if active and fault == "fsync":
            active = False
            raise OSError("private flush failure")
        sync(fd)

    monkeypatch.setattr(acq, "_producer", observed_producer)
    monkeypatch.setattr(acq, "_read_file", failed_read)
    monkeypatch.setattr(os, "fsync", failed_sync)
    with pytest.raises(acq.GitCaptureError) as caught:
        capture(roots)
    failure = json.loads(caught.value.retained_failure)
    assert failure["capture_state"] == "verified-orphan"
    assert failure["proof_id"] is not None
    assert not list(roots[2].glob("*/COMPLETE"))


@pytest.mark.parametrize("interrupt", [False, True])
def test_original_failure_and_failure_record_error_both_survive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interrupt: bool
) -> None:
    roots = fixtures(tmp_path)
    original = (
        KeyboardInterrupt("private interruption")
        if interrupt
        else OSError("private staging failure")
    )
    retention = OSError("private diagnostic write failure")

    def fail_staging(*_args: object, **_kwargs: object) -> None:
        raise original

    def fail_record(*_args: object, **_kwargs: object) -> None:
        raise retention

    monkeypatch.setattr(acq, "_materialize", fail_staging)
    monkeypatch.setattr(acq, "_write_file", fail_record)
    with pytest.raises(KeyboardInterrupt if interrupt else acq.GitCaptureError) as caught:
        capture(roots)
    if interrupt:
        assert caught.value is original and original.__cause__ is retention
    else:
        assert caught.value.retained_failure is None
        assert isinstance(caught.value.__cause__, BaseExceptionGroup)
        assert caught.value.__cause__.exceptions == (original, retention)


def test_observed_module_mode_is_not_runtime_authority(tmp_path: Path) -> None:
    path = tmp_path / "observed.py"
    path.write_bytes(b"never execute this")
    path.chmod(0o666)
    assert acq._observed_source(path) == b"never execute this"
    alias = tmp_path / "alias.py"
    alias.symlink_to(path)
    with pytest.raises(OSError):
        acq._observed_source(alias)


def test_proof_collision_retains_orphan_without_claiming_old_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = fixtures(tmp_path)
    attempt, proof = uuid4(), uuid4()
    existing = roots[2] / str(proof)
    existing.mkdir(mode=0o700)
    marker = existing / "preserved"
    marker.write_bytes(b"old unrelated proof")
    identities = iter((attempt, proof))
    monkeypatch.setattr(acq, "uuid4", lambda: next(identities))
    with pytest.raises(acq.GitCaptureError) as caught:
        capture(roots)
    failure = json.loads(caught.value.retained_failure)
    assert failure["proof_id"] is None
    assert failure["capture_state"] == "verified-orphan"
    assert set(existing.iterdir()) == {marker}


def test_proof_size_limit_is_failure_not_partial_success(tmp_path: Path) -> None:
    objects, store, evidence, binding = fixtures(tmp_path)
    with pytest.raises(acq.GitCaptureError) as caught:
        acq.capture_offline_objects(
            objects,
            store_root=store,
            evidence_root=evidence,
            binding=binding,
            limits=git.GitCaptureLimits(objects=git.GitObjectLimits(max_proof_bytes=1)),
        )
    assert caught.value.reason == "limit"
    assert not list(evidence.glob("*/COMPLETE"))


@pytest.mark.parametrize(
    "payload",
    [["x" * 4096] * 100, {"k": "\x01" * 1000}, [[1] * 300] * 300],
    ids=["repeated-strings", "escaped-size", "queued-values"],
)
def test_json_aggregate_preflight_precedes_serialization(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("over-limit data reached json.dumps")

    monkeypatch.setattr(acq.json, "dumps", forbidden)
    with pytest.raises(acq.GitCaptureError, match="limit"):
        acq.canonical_bytes(payload, maximum=4096)


def test_json_exact_escaped_utf8_boundary() -> None:
    value = {"é": "\n\\😀", "n": -4, "t": True, "z": None}
    expected = '{"n":-4,"t":true,"z":null,"é":"\\n\\\\😀"}'.encode()
    assert acq.canonical_bytes(value, maximum=len(expected)) == expected
    assert acq.canonical_bytes(value, maximum=len(expected) + 1) == expected
    with pytest.raises(acq.GitCaptureError, match="limit"):
        acq.canonical_bytes(value, maximum=len(expected) - 1)


def test_json_queued_count_rejects_before_poison_children() -> None:
    poison = object()
    pending = [poison] * 59_999 + [[poison] * 60_000]
    with pytest.raises(acq.GitCaptureError, match="limit"):
        acq.canonical_bytes(pending)


def test_replay_retained_budget_includes_proof_before_more_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("over-limit retained proof reached artifact reads")

    monkeypatch.setattr(acq, "_names", forbidden)
    limits = git.GitCaptureLimits(objects=git.GitObjectLimits(max_proof_bytes=10))
    with pytest.raises(acq.GitCaptureError, match="limit"):
        acq._read_artifacts(-1, limits, already_retained=11)


def test_outer_close_error_does_not_replace_original_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = fixtures(tmp_path)
    original, prior, cleanup = (
        KeyboardInterrupt("original"),
        OSError("prior cause"),
        OSError("close failed"),
    )
    selected: int | None = None
    close = os.close

    def fail_materialize(
        input_directory: int, source: int, tree: git.GitTree, limits: git.GitCaptureLimits
    ) -> None:
        nonlocal selected
        selected = source
        raise original from prior

    def fail_close(descriptor: int) -> None:
        nonlocal selected
        close(descriptor)
        if descriptor == selected:
            selected = None
            raise cleanup

    monkeypatch.setattr(acq, "_materialize", fail_materialize)
    monkeypatch.setattr(os, "close", fail_close)
    with pytest.raises(KeyboardInterrupt) as caught:
        capture(roots)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (prior, cleanup)
    failure = next(roots[2].glob("attempt-*/failure.json"))
    assert json.loads(failure.read_bytes())["completion_claim"] is False


@pytest.mark.parametrize("retention_fails", [False, True])
def test_final_close_prevents_return_and_records_actual_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retention_fails: bool
) -> None:
    roots = fixtures(tmp_path)
    selected: int | None = None
    original_materialize, close, write = acq._materialize, os.close, acq._write_file
    close_error, write_error = OSError("final close"), OSError("failure write")

    def remember_source(
        input_directory: int, source: int, tree: git.GitTree, limits: git.GitCaptureLimits
    ) -> None:
        nonlocal selected
        selected = source
        original_materialize(input_directory, source, tree, limits)

    def final_close(fd: int) -> None:
        nonlocal selected
        close(fd)
        if fd == selected:
            selected = None
            raise close_error

    def maybe_fail_record(parent: int, name: str, payload: bytes) -> None:
        if name == "failure.json" and retention_fails:
            raise write_error
        write(parent, name, payload)

    monkeypatch.setattr(acq, "_materialize", remember_source)
    monkeypatch.setattr(os, "close", final_close)
    monkeypatch.setattr(acq, "_write_file", maybe_fail_record)
    with pytest.raises(acq.GitCaptureError) as caught:
        capture(roots)
    assert len(list(roots[2].glob("*/COMPLETE"))) == 1  # Marker is not return/DB authority.
    if retention_fails:
        assert caught.value.retained_failure is None
        assert isinstance(caught.value.__cause__, BaseExceptionGroup)
        assert caught.value.__cause__.exceptions == (close_error, write_error)
    else:
        failure = json.loads(caught.value.retained_failure)
        assert failure["stage"] == "result" and failure["completion_claim"] is False
        assert failure["proof_id"] is not None and failure["capture_object_id"] is not None
        assert caught.value.__cause__ is close_error


def test_final_cleanup_does_not_adopt_replaced_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roots = fixtures(tmp_path)
    selected: int | None = None
    close = os.close
    materialize = acq._materialize
    error = OSError("close failed after attempt replacement")
    replacement: Path | None = None

    def remember(
        input_directory: int, source: int, tree: git.GitTree, limits: git.GitCaptureLimits
    ) -> None:
        nonlocal selected
        selected = source
        materialize(input_directory, source, tree, limits)

    def swapped_close(fd: int) -> None:
        nonlocal selected, replacement
        close(fd)
        if fd == selected:
            selected = None
            replacement = next(roots[2].glob("attempt-*"))
            replacement.rename(roots[2] / "retained-original-attempt")
            replacement.mkdir(mode=0o700)
            (replacement / "other-task-marker").write_bytes(b"must preserve")
            raise error

    monkeypatch.setattr(acq, "_materialize", remember)
    monkeypatch.setattr(os, "close", swapped_close)
    with pytest.raises(acq.GitCaptureError) as caught:
        capture(roots)
    assert replacement is not None
    assert sorted(path.name for path in replacement.iterdir()) == ["other-task-marker"]
    assert caught.value.retained_failure is None
    assert isinstance(caught.value.__cause__, BaseExceptionGroup)
    assert caught.value.__cause__.exceptions[0] is error


class _PoisonUUIDInteger:
    def __format__(self, _spec: str) -> str:
        pytest.fail("poisoned UUID formatted")

    def __str__(self) -> str:
        pytest.fail("poisoned UUID stringified")


@pytest.mark.parametrize("poison", [_PoisonUUIDInteger(), True, -1, 2**128])
def test_uuid_primitive_snapshot_precedes_formatting(poison: object) -> None:
    identity = uuid4()
    object.__setattr__(identity, "int", poison)
    with pytest.raises(acq.GitCaptureError):
        acq._snapshot_uuid(identity)


@pytest.mark.parametrize("field", ["org_id", "codebase_id", "request_id"])
def test_binding_uuid_poison_cannot_start_capture(tmp_path: Path, field: str) -> None:
    roots = fixtures(tmp_path)
    object.__setattr__(getattr(roots[3], field), "int", _PoisonUUIDInteger())
    with pytest.raises(acq.GitCaptureError):
        capture(roots)
    assert list(roots[1].iterdir()) == list(roots[2].iterdir()) == []


def test_actual_root_clones_are_passed_through_custody_and_replay(tmp_path: Path) -> None:
    roots = fixtures(tmp_path)
    stored = Path(str(roots[1]))
    for path in roots[:3]:
        object.__setattr__(path, "_str", _PoisonUUIDInteger())
    result = capture(roots)
    assert (stored / str(result.receipt.object_id) / "SEALED").is_file()
    assert verify(roots, result).receipt == result.receipt
    assert result.receipt.binding.org_id is not roots[3].org_id


@pytest.mark.parametrize("target", ["receipt-id", "receipt-binding", "proof-id", "result-id"])
def test_replay_and_wire_public_boundaries_snapshot_ids(tmp_path: Path, target: str) -> None:
    roots = fixtures(tmp_path)
    result = capture(roots)
    if target == "receipt-id":
        object.__setattr__(result.receipt.object_id, "int", _PoisonUUIDInteger())
    elif target == "receipt-binding":
        object.__setattr__(result.receipt.binding.org_id, "int", _PoisonUUIDInteger())
    else:
        object.__setattr__(result.proof_id, "int", _PoisonUUIDInteger())
    with pytest.raises(acq.GitCaptureError):
        if target == "result-id":
            acq.result_document(result)
        elif target.startswith("receipt"):
            acq.encode_receipt(result.receipt)
        else:
            verify(roots, result)


@pytest.mark.parametrize("mode", [0o700, 0o755, 0o555])
def test_receipt_parent_mode_comes_only_from_held_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: int
) -> None:
    expected = capture(fixtures(tmp_path)).receipt
    parent = tmp_path / "trusted-receipt"
    parent.mkdir(mode=0o700)
    path = parent / "expected.json"
    path.write_bytes(acq.encode_receipt(expected))
    path.chmod(0o444)
    parent.chmod(mode)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("receipt parent metadata must come from the held no-follow FD")

    with monkeypatch.context() as patched:
        patched.setattr(Path, "stat", forbidden)
        patched.setattr(Path, "lstat", forbidden)
        assert acq.read_expected_receipt(path) == expected


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("missing-parent", "storage"),
        ("parent-symlink", "storage"),
        ("ancestor-symlink", "storage"),
        ("leaf-symlink", "storage"),
        ("unsafe-parent", "invalid-input"),
        ("leaf-directory", "invalid-input"),
        ("leaf-hardlink", "invalid-input"),
    ],
)
def test_expected_receipt_path_refusals_are_fixed_and_do_not_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, reason: str
) -> None:
    parent = tmp_path / "private-receipt-parent"
    parent.mkdir(mode=0o700)
    path = parent / "expected.json"
    path.write_bytes(b"not decoded")
    path.chmod(0o444)
    if kind == "missing-parent":
        path = tmp_path / "private-missing" / "expected.json"
    elif kind in ("parent-symlink", "ancestor-symlink"):
        alias = tmp_path / "private-alias"
        alias.symlink_to(parent if kind == "parent-symlink" else tmp_path, target_is_directory=True)
        path = alias / path.name if kind == "parent-symlink" else alias / parent.name / path.name
    elif kind == "leaf-symlink":
        alias = parent / "alias.json"
        alias.symlink_to(path)
        path = alias
    elif kind == "unsafe-parent":
        parent.chmod(0o770)
    elif kind == "leaf-directory":
        path = parent / "directory.json"
        path.mkdir(mode=0o700)
    else:
        os.link(path, parent / "extra-link.json")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("invalid path reached receipt decoding")

    monkeypatch.setattr(acq, "decode_receipt", forbidden)
    with pytest.raises(acq.GitCaptureError) as caught:
        acq.read_expected_receipt(path)
    assert caught.value.reason == str(caught.value) == reason


def test_expected_receipt_rejects_parent_link_replacement_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "receipt-parent"
    parent.mkdir(mode=0o700)
    replacement = tmp_path / "replacement"
    replacement.mkdir(mode=0o700)
    real_open = os.open
    swapped = False

    def raced_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal swapped
        if path == parent.name and flags == git.DIRECTORY_FLAGS and not swapped:
            swapped = True
            parent.rename(tmp_path / "retained-original")
            parent.symlink_to(replacement, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("receipt decoder reached after symlink substitution")

    monkeypatch.setattr(os, "open", raced_open)
    monkeypatch.setattr(acq, "decode_receipt", forbidden)
    with pytest.raises(acq.GitCaptureError, match="storage"):
        acq.read_expected_receipt(parent / "expected.json")
    assert swapped


@pytest.mark.parametrize("kind", ["interrupt", "exit", "close-only"])
def test_receipt_leaf_cleanup_preserves_primary_and_closes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    tmp_path.chmod(0o700)
    path = tmp_path / "expected.json"
    path.write_bytes(b"{}")
    path.chmod(0o600)
    real_open, real_read, real_close = os.open, os.read, os.close
    primary = KeyboardInterrupt() if kind == "interrupt" else SystemExit(17)
    cleanup = OSError("private leaf cleanup failure")
    leaf: int | None = None
    close_calls = 0

    def observed_open(name: object, flags: int, *args: object, **kwargs: object) -> int:
        nonlocal leaf
        descriptor = real_open(name, flags, *args, **kwargs)
        if name == path.name and kwargs.get("dir_fd") is not None:
            leaf = descriptor
        return descriptor

    def interrupted_read(descriptor: int, count: int) -> bytes:
        if descriptor == leaf and kind != "close-only":
            raise primary
        return real_read(descriptor, count)

    def failed_close(descriptor: int) -> None:
        nonlocal close_calls
        if descriptor == leaf:
            close_calls += 1
            real_close(descriptor)
            raise cleanup
        real_close(descriptor)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("receipt was decoded after a cleanup failure")

    with monkeypatch.context() as patched:
        patched.setattr(os, "open", observed_open)
        patched.setattr(os, "read", interrupted_read)
        patched.setattr(os, "close", failed_close)
        patched.setattr(acq, "decode_receipt", forbidden)
        with pytest.raises(
            acq.GitCaptureError if kind == "close-only" else type(primary)
        ) as caught:
            acq.read_expected_receipt(path)
    assert close_calls == 1
    if kind == "close-only":
        assert str(caught.value) == "storage" and caught.value.__cause__ is cleanup
    else:
        assert caught.value is primary
        assert isinstance(primary.__cause__, BaseExceptionGroup)
        assert primary.__cause__.exceptions == (cleanup,)
