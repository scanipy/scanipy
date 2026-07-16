"""SLSA provenance predicate builder — AC-DEPLOY-04c (DOC-CMP-DEPLOY-04 §3.6).

Produces the SLSA v0.2 provenance predicate that ``deploy.yml:build-images``
attaches to each worker image via ``cosign attest --type slsaprovenance``
(keyless). Per DOC-CMP-DEPLOY-04 §3.6 the predicate links:

* the image digest (the attestation SUBJECT; also echoed in
  ``invocation.parameters`` so the predicate is self-describing),
* the build commit sha,
* the build inputs — content hashes of ``workers/pins.json``, the image's
  Dockerfile, and its ``requirements.txt``,
* the pinned tool digests from ``pins.json`` (joern / codeql / git),
* the builder identity (the GHA workflow ref),
* the build timestamp.

Starting from a ``findings.env_digest`` an auditor can pull the ECR image,
fetch this attestation, and recover the exact build inputs that produced the
image — closing the INV-2 loop.

Implemented as an importable module (not inline workflow shell) so
``TST-AC-DEPLOY-04c`` can assert the predicate content hermetically against a
fixture: the workflow and the test call the same :func:`build_predicate`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

#: cosign ``--type slsaprovenance`` binds this predicate type.
PREDICATE_TYPE = "https://slsa.dev/provenance/v0.2"

BUILD_TYPE = "https://github.com/scanipy/scanipy-v3.2/worker-image-build@v1"

_WORKFLOW_ENTRYPOINT = ".github/workflows/deploy.yml"


def file_sha256(path: Path) -> str:
    """Hex sha256 of a file's content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_predicate(
    *,
    image_digest: str,
    build_commit: str,
    source_ref: str,
    repository: str,
    builder_id: str,
    pins_path: Path,
    dockerfile_path: Path,
    requirements_path: Path,
    build_started_on: str,
    build_finished_on: str,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Assemble the SLSA v0.2 provenance predicate (DOC-CMP-DEPLOY-04 §3.6).

    ``repo_root`` anchors the repo-relative material URIs; it defaults to the
    common parent so fixture trees work unchanged.
    """
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    tools = pins.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise ValueError(f"{pins_path}: no tools section — refusing to attest unpinned inputs")

    def _rel(path: Path) -> str:
        if repo_root is not None:
            try:
                return path.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                pass
        return path.name

    source_uri = f"git+https://github.com/{repository}@{source_ref}"
    materials: list[dict[str, object]] = [
        {"uri": source_uri, "digest": {"sha1": build_commit}},
        {"uri": f"scanipy:{_rel(pins_path)}", "digest": {"sha256": file_sha256(pins_path)}},
        {
            "uri": f"scanipy:{_rel(dockerfile_path)}",
            "digest": {"sha256": file_sha256(dockerfile_path)},
        },
        {
            "uri": f"scanipy:{_rel(requirements_path)}",
            "digest": {"sha256": file_sha256(requirements_path)},
        },
    ]
    for tool_name in sorted(tools):
        tool = tools[tool_name]
        if not isinstance(tool, dict) or not tool.get("version") or not tool.get("sha256"):
            raise ValueError(
                f"{pins_path}: tools.{tool_name} lacks version/sha256 — refusing to attest "
                "unpinned inputs (AC-DEPLOY-02c upstream gate should have caught this)"
            )
        materials.append(
            {
                "uri": f"scanipy:tool/{tool_name}@{tool['version']}",
                "digest": {"sha256": str(tool["sha256"])},
            }
        )

    return {
        "builder": {"id": builder_id},
        "buildType": BUILD_TYPE,
        "invocation": {
            "configSource": {
                "uri": source_uri,
                "digest": {"sha1": build_commit},
                "entryPoint": _WORKFLOW_ENTRYPOINT,
            },
            "parameters": {
                "image_digest": image_digest,
                "dockerfile": _rel(dockerfile_path),
            },
        },
        "metadata": {
            "buildStartedOn": build_started_on,
            "buildFinishedOn": build_finished_on,
            "completeness": {"parameters": True, "environment": False, "materials": True},
            "reproducible": False,
        },
        "materials": materials,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI used by ``deploy.yml:build-images`` to emit one predicate per image."""
    parser = argparse.ArgumentParser(prog="slsa_predicate")
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--build-commit", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--builder-id", required=True)
    parser.add_argument("--pins", default="workers/pins.json")
    parser.add_argument("--dockerfile", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: UP017
    try:
        predicate = build_predicate(
            image_digest=args.image_digest,
            build_commit=args.build_commit,
            source_ref=args.source_ref,
            repository=args.repository,
            builder_id=args.builder_id,
            pins_path=Path(args.pins),
            dockerfile_path=Path(args.dockerfile),
            requirements_path=Path(args.requirements),
            build_started_on=now,
            build_finished_on=now,
            repo_root=Path.cwd(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR (AC-DEPLOY-04c): cannot build SLSA predicate: {exc}", file=sys.stderr)
        return 1
    Path(args.out).write_text(json.dumps(predicate, indent=2) + "\n", encoding="utf-8")
    print(f"SLSA v0.2 predicate written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
