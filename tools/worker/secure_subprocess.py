"""CMP-SNAP-05 argv-allowlist subprocess wrapper (``secure_run``).

Implementation contract: ``docs/components/DOC-CMP-SNAP-05.md`` §3.3 (argv
allowlist), §3.4 / §7 (error contracts). Cross-cutting: ``.claude/rules/00-global.md``
(RULE-6 is threaded by the worker, not here — this module spawns *tools*, it
never constructs a ``Finding``), ``DOC-INV §4.5`` (the pinned-binary path is what
makes ``env_digest`` actually characterise ``Env``).

This is the **operational discharge of ``AC-SNAP-05a``**: every ``joern`` /
``codeql`` invocation in the snapshot worker MUST route through
:func:`secure_run`, which rejects any flag not on that tool's static, sanctioned
allowlist **fail-closed, before a subprocess is ever spawned**. The check is the
first thing the wrapper does — a non-sanctioned flag never reaches
``subprocess.run`` and never resolves a binary.

Git is unavailable through this generic, unbounded-output API, including for
apparently benign commands. See docs/bhmea/GIT-SOURCE-ACQUISITION.md; a flag
allowlist is not a native acquisition safety profile.

Hardening invariants (DOC §3.3 "Invariants of ``secure_run``"):

* ``shell=False`` always — argv is a list, never a string interpolated into a
  shell command line.
* The host ``PATH`` is never consulted: the tool binary is resolved via
  :func:`resolve_pinned_binary` from a fixed in-image path. This is exactly what
  makes ``env_digest`` characterise ``Env`` (``DOC-INV §4.5`` counter-example).
* ``timeout_s`` is mandatory (keyword-only, no default).
* ``env`` is the explicitly-constructed worker env; the host environment is not
  inherited.
* Java source parsing requires the explicit versioned closed environment
  profile in ``docs/bhmea/JAVA-STATIC-INVOCATION.md``. The shared Java adapter
  applies it to its fixed exporter too; unprofiled direct scripts are outside
  that narrow guarantee.

The module is import-clean with no third-party dependency so the AC-SNAP-05a
negative test runs hermetically (it asserts the *rejection*, which short-circuits
before any binary exists).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

from tools.worker.joern_java_safety import (
    JAVA_STATIC_EXPORT_SCRIPT,
    JavaStaticEnvironmentError,
    JoernEnvironmentProfile,
    validate_java_parse_paths,
    validate_java_static_environment,
)

# --- Per-tool static allowlists (sanctioned flags only) — DOC-CMP-SNAP-05 §3.3 ---
# Verbatim from the contract. A flag is sanctioned iff its option name (the part
# before any ``=``) is a member of the owning tool's frozenset. Subcommands and
# positional verbs (``database``, ``create``, ``analyze`` …) are allowed because
# they do not start with ``-``; Git is separately refused before any traversal.
JOERN_ARGV_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "--language",
        "--output",
        "--script",
        "--src",
        "--cpg-only",
    }
)
# joern-parse — the HEADLESS parse tool. Validated against real joern
# v4.0.554 (local docker rehearsal, Wave-4): the main `joern` launcher does
# NOT accept `--output`/`--cpg-only` in this version ("Warning: Unknown
# option", then it silently drops into interactive REPL mode and exits 0
# without producing any cpg.bin — DOC-CMP-SNAP-05 §6.3's `joern ...
# --cpg-only` example predates this and does not match the pinned release).
# The headless binary has a value-aware grammar, not arbitrary positional or
# frontend forwarding. Java additionally requires one exact no-Delombok suffix;
# other vetted frontends retain the shared adapter's original five-token form.
# The main `joern` allowlist is unchanged (AC-SNAP-05a).
JOERN_PARSE_ARGV_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "--language",
        "--output",
        "--frontend-args",
        "--delombok-mode",
    }
)

_PARSE_LANGUAGES = frozenset({"javasrc", "pythonsrc", "jssrc", "golang", "rubysrc", "php"})
_JAVA_STATIC_SUFFIX = ["--frontend-args", "--delombok-mode", "no-delombok"]


def _enforce_parse_grammar(argv: list[str]) -> None:
    """No generic frontend forwarding: the Java suffix has one exact meaning."""
    if (
        not isinstance(argv, list)
        or len(argv) not in {5, 8}
        or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in argv)
        or argv[0] != "--language"
        or argv[1] not in _PARSE_LANGUAGES
        or argv[2] != "--output"
        or argv[3].startswith("-")
        or argv[4].startswith("-")
        or (argv[1] == "javasrc" and argv[5:] != _JAVA_STATIC_SUFFIX)
        or (argv[1] != "javasrc" and len(argv) != 5)
    ):
        raise ArgvAllowlistViolation("joern-parse requires the exact vetted language grammar")


CODEQL_ARGV_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "database",
        "create",
        "analyze",
        "--source-root",
        "--db",
        "--format",
        "--output",
        "--ram",
        "--threads",
    }
)
# Import compatibility only: neither flags nor bare Git tokens are permitted.
GIT_ARGV_ALLOWLIST: Final[frozenset[str]] = frozenset()

_ALLOWLISTS: Final[dict[str, frozenset[str]]] = {
    "joern": JOERN_ARGV_ALLOWLIST,
    "joern-parse": JOERN_PARSE_ARGV_ALLOWLIST,
    "codeql": CODEQL_ARGV_ALLOWLIST,
    "git": GIT_ARGV_ALLOWLIST,
}

# Fixed in-image binary paths. The host ``PATH`` is NOT consulted — see module
# docstring + DOC-INV §4.5. These mirror the Dockerfile layout (DOC-CMP-DEPLOY-02
# §3.1: joern under /opt/joern, codeql under /opt/codeql, git at /usr/bin/git).
#
# joern's launcher lives at the ARCHIVE ROOT (`/opt/joern/joern`), not under
# `bin/` — verified against the real pinned joern-cli v4.0.554 release layout
# (its `bin/` holds `repl-bridge`/`joern-cli`/`joern-export` etc., no `joern`).
# The previous `/opt/joern/bin/joern` value was a plausible-looking guess that
# survived every hermetic test (they monkeypatch the subprocess call) and was
# only caught by the first real in-container `parse_source` invocation during
# the local docker rehearsal (CLAR-SNAP-05 explicitly flagged the real-Joern
# layer as UNVERIFIED for exactly this reason).
_PINNED_BINARIES: Final[dict[str, str]] = {
    "joern": "/opt/joern/joern",
    "joern-parse": "/opt/joern/joern-parse",
    "codeql": "/opt/codeql/codeql",
    "git": "/usr/bin/git",
}


class ArgvAllowlistViolation(Exception):  # noqa: N818 — name fixed verbatim by DOC-CMP-SNAP-05 §3.4
    """A caller passed a flag not on the tool's sanctioned argv allowlist.

    DOC-CMP-SNAP-05 §3.4: a hard, security-relevant failure (could indicate a
    code-injection attempt). Raised **before** any subprocess is spawned.
    """


class UnknownTool(Exception):  # noqa: N818 — paired with ArgvAllowlistViolation; fail-closed default-deny
    """``secure_run`` was asked to run a tool with no registered allowlist.

    Unknown tools are refused rather than run with an empty/permissive
    allowlist. Git is recognized for compatibility but always unavailable.
    """


def _enforce_allowlist(tool: str, argv: list[str]) -> frozenset[str]:
    """Reject the call fail-closed unless every flag in ``argv`` is sanctioned.

    Returns the resolved allowlist on success (so the caller does not look it up
    twice). Raises :class:`UnknownTool` for an unregistered tool and
    :class:`ArgvAllowlistViolation` for the first non-sanctioned flag — both
    **before** any binary is resolved or any process is spawned. A token is a
    "flag" iff it starts with ``-``; its option name is the part before any
    ``=`` (so ``--language=java`` is gated on ``--language``).
    """
    if tool == "git":
        # Before even argv traversal: no caller input can select a Git profile
        # on this unbounded capture_output API, including the Java profile.
        raise ArgvAllowlistViolation(
            "Unprofiled Git is unavailable; a separately reviewed bounded "
            "source-capture producer is required"
        )
    try:
        allowlist = _ALLOWLISTS[tool]
    except KeyError:
        raise UnknownTool(
            f"tool {tool!r} has no sanctioned argv allowlist; "
            "only 'joern', 'joern-parse', 'codeql', 'git' are permitted (fail-closed)"
        ) from None

    if tool == "joern-parse":
        _enforce_parse_grammar(argv)
    for arg in argv:
        if arg.startswith("-") and arg.split("=", 1)[0] not in allowlist:
            raise ArgvAllowlistViolation(f"flag {arg!r} not in {tool} allowlist")
    return allowlist


def resolve_pinned_binary(tool: str) -> str:
    """Resolve the fixed in-image absolute path of ``tool`` (never the host PATH).

    DOC-CMP-SNAP-05 §3.3: the host ``PATH`` is not consulted; resolving from a
    fixed in-image path is what makes ``env_digest`` characterise ``Env``
    (``DOC-INV §4.5``). An unregistered tool is :class:`UnknownTool` (fail-closed).
    """
    try:
        return _PINNED_BINARIES[tool]
    except KeyError:
        raise UnknownTool(
            f"tool {tool!r} has no pinned in-image binary path (fail-closed)"
        ) from None


def secure_run(
    tool: str,
    argv: list[str],
    *,
    timeout_s: int,
    env: dict[str, str],
    cwd: str,
    environment_profile: JoernEnvironmentProfile | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run a pinned tool under the argv allowlist (DOC-CMP-SNAP-05 §3.3).

    The allowlist is enforced **first** (fail-closed): a non-sanctioned flag
    raises :class:`ArgvAllowlistViolation` and no subprocess is spawned. Only on
    a fully-sanctioned argv is the pinned binary resolved and executed with
    ``shell=False``, a mandatory timeout, and the explicitly-supplied ``env``
    (the host environment is not inherited).

    Args:
        tool: ``joern`` / ``joern-parse`` / ``codeql``. Git always refuses.
        argv: the tool arguments (subcommands + sanctioned flags). Every ``-``/
            ``--`` flag must be on the per-tool allowlist.
        timeout_s: mandatory wall-clock timeout in seconds.
        env: the worker env passed to the child (host env not inherited).
        cwd: the working directory for the child.
        environment_profile: explicit supported closed Java profile. Required
            for javasrc parse, also supplied by the shared Java export adapter.
            None preserves non-Java compatibility, not a claim about arbitrary
            direct scripts' source language or safety.

    Raises:
        ArgvAllowlistViolation: a flag in ``argv`` is not sanctioned.
        UnknownTool: ``tool`` is not one of the three sanctioned tools.
        JavaStaticEnvironmentError: absent/unsupported Java profile or invalid
            Java environment/path; raised before binary lookup/spawn.
        subprocess.CalledProcessError: the tool exited non-zero (``check=True``).
        subprocess.TimeoutExpired: the tool exceeded ``timeout_s``.
    """
    # Allowlist enforcement is the FIRST action — fail-closed before any work.
    _enforce_allowlist(tool, argv)

    java_parse = tool == "joern-parse" and argv[1] == "javasrc"
    if environment_profile is None:
        if java_parse:
            raise JavaStaticEnvironmentError("Java parser requires an explicit environment profile")
    else:
        if environment_profile is not JoernEnvironmentProfile.JAVA_STATIC_V1:
            raise JavaStaticEnvironmentError("unsupported typed Joern environment profile")
        if java_parse:
            validate_java_static_environment(env, cwd=Path(cwd), phase="parse")
            validate_java_parse_paths(source=Path(argv[4]), output=Path(argv[3]), cwd=Path(cwd))
        elif tool == "joern" and argv == ["--script", JAVA_STATIC_EXPORT_SCRIPT]:
            validate_java_static_environment(env, cwd=Path(cwd), phase="export")
        else:
            raise JavaStaticEnvironmentError("Java environment profile/tool mismatch")

    binary = resolve_pinned_binary(tool)
    # argv is allowlist-gated above; shell=False; binary is a pinned in-image path
    # (never the host PATH) — the three properties that make this call auditable.
    return subprocess.run(
        [binary, *argv],
        capture_output=True,
        check=True,
        timeout=timeout_s,
        env=env,
        cwd=cwd,
        shell=False,
    )


__all__ = [
    "CODEQL_ARGV_ALLOWLIST",
    "GIT_ARGV_ALLOWLIST",
    "JOERN_ARGV_ALLOWLIST",
    "ArgvAllowlistViolation",
    "UnknownTool",
    "resolve_pinned_binary",
    "secure_run",
]
