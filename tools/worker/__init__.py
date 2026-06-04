"""CMP-SNAP-05 worker subprocess hardening surface (``tools.worker``).

Hosts :mod:`tools.worker.secure_subprocess` — the argv-allowlist wrapper around
``subprocess.run`` that every pinned-tool invocation in the snapshot worker
(``joern`` / ``codeql`` / ``git``) MUST route through. The wrapper is the
operational discharge of ``AC-SNAP-05a`` (DOC-CMP-SNAP-05 §3.3): any flag not on
the per-tool sanctioned list is rejected fail-closed *before* a subprocess is
ever spawned, and ``shell=True`` is never used.

This package writes NO provenance fields; it is a security wrapper consumed by
the ``services.snapshot.worker`` entrypoint (CMP-SNAP-05) and the detector
worker (DOC-CMP-DEPLOY-02 §3.1). Both Dockerfiles copy it to ``/app/tools/worker``.
"""

from tools.worker.secure_subprocess import (
    CODEQL_ARGV_ALLOWLIST,
    GIT_ARGV_ALLOWLIST,
    JOERN_ARGV_ALLOWLIST,
    ArgvAllowlistViolation,
    UnknownTool,
    secure_run,
)

__all__ = [
    "CODEQL_ARGV_ALLOWLIST",
    "GIT_ARGV_ALLOWLIST",
    "JOERN_ARGV_ALLOWLIST",
    "ArgvAllowlistViolation",
    "UnknownTool",
    "secure_run",
]
