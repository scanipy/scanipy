#!/usr/bin/env python3
"""Explicit local offline source-capture operator CLI; online mode is unavailable."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn
from uuid import UUID

from integrations.scm import source_acquisition as acquisition
from integrations.scm.git_objects import GitCaptureLimits, GitObjectError
from services.scan.source_capture import CaptureBinding


class _Parser(argparse.ArgumentParser):
    def error(self, _message: str) -> NoReturn:
        raise acquisition.GitCaptureError("invalid-input")


def _arguments() -> tuple[str, ...]:
    # This is the actual current CLI argv, not a caller-provided identity object.
    if type(sys.argv) is not list or not 1 <= len(sys.argv) <= 64:
        raise acquisition.GitCaptureError("invalid-input")
    total = 0
    frozen: list[str] = []
    for value in sys.argv:
        if type(value) is not str or len(value) > 4096 or "\0" in value:
            raise acquisition.GitCaptureError("invalid-input")
        encoded = value.encode("utf-8", "strict")
        total += len(encoded)
        if len(encoded) > 4096 or total > 16384:
            raise acquisition.GitCaptureError("limit")
        frozen.append(value)
    return tuple(frozen)


def _uuid(value: str) -> UUID:
    parsed = UUID(value)
    if str(parsed) != value:
        raise acquisition.GitCaptureError("invalid-input")
    return parsed


def _parser() -> _Parser:
    parser = _Parser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="operation", required=True, parser_class=_Parser)
    offline = commands.add_parser("offline-objects", allow_abbrev=False)
    for name in (
        "objects-dir",
        "store-root",
        "evidence-root",
        "org-id",
        "codebase-id",
        "request-id",
        "commit",
    ):
        offline.add_argument("--" + name, required=True)
    offline.add_argument("--owner")
    offline.add_argument("--repository")
    verify = commands.add_parser("verify-capture", allow_abbrev=False)
    for name in (
        "store-root",
        "evidence-root",
        "proof-id",
        "expected-proof-digest",
        "expected-receipt",
    ):
        verify.add_argument("--" + name, required=True)
    commands.add_parser("github", allow_abbrev=False)
    return parser


def main() -> int:
    try:
        # No parsing, destination/credential staging, or native route can enable
        # github. Even extra proposed profile/allow-network flags remain refused.
        if (
            type(sys.argv) is list
            and len(sys.argv) > 1
            and type(sys.argv[1]) is str
            and sys.argv[1] == "github"
        ):
            acquisition.capture_github_commit()
        argv = _arguments()
        args = _parser().parse_args(argv[1:])
        if args.operation == "offline-objects":
            if (args.owner is None) != (args.repository is None):
                raise acquisition.GitCaptureError("invalid-input")
            claim = (
                None
                if args.owner is None
                else acquisition.GitHubRepositoryClaim(args.owner, args.repository)
            )
            result = acquisition.capture_offline_objects(
                Path(args.objects_dir),
                store_root=Path(args.store_root),
                evidence_root=Path(args.evidence_root),
                binding=CaptureBinding(
                    _uuid(args.org_id), _uuid(args.codebase_id), _uuid(args.request_id), args.commit
                ),
                repository_claim=claim,
                limits=GitCaptureLimits(),
            )
        elif args.operation == "verify-capture":
            expected = acquisition.read_expected_receipt(Path(args.expected_receipt))
            if len(args.expected_proof_digest) != 64 or any(
                char not in "0123456789abcdef" for char in args.expected_proof_digest
            ):
                raise acquisition.GitCaptureError("invalid-input")
            result = acquisition.verify_offline_capture(
                store_root=Path(args.store_root),
                evidence_root=Path(args.evidence_root),
                expected_receipt=expected,
                proof_id=_uuid(args.proof_id),
                expected_proof_digest=bytes.fromhex(args.expected_proof_digest),
            )
        else:
            acquisition.capture_github_commit()
        document = acquisition.result_document(result)
        document["caller"] = {
            "kind": "cli",
            "entrypoint": "scripts/capture_git_source.py",
            "argv": list(argv),
        }
        raw = acquisition.canonical_bytes(document, maximum=32 * 1024)
        sys.stdout.write(raw.decode("utf-8"))
        sys.stdout.flush()
        return 0
    except acquisition.GitCaptureError as error:
        sys.stderr.write(error.reason + "\n")
        return (
            69
            if error.reason == "unavailable-online"
            else 2
            if error.reason == "invalid-input"
            else 1
        )
    except (ValueError, TypeError, UnicodeError, GitObjectError):
        sys.stderr.write("invalid-input\n")
        return 2
    except OSError:
        sys.stderr.write("storage\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
