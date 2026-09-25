"""CMP-SNAP-05 (CPG-ingest sub-scope, CLAR-SNAP-03) — Joern front-end orchestration.

Implements the plan's Wave-1 track-1A/1B handshake signature:

    parse_source(src_root: Path, language: str, *, env: Mapping[str, str],
                 workdir: Path) -> CPG

Two ``secure_run`` phases (both routed through
``tools.worker.secure_subprocess.secure_run`` — every ``joern`` invocation goes
through the argv allowlist, ``shell=False``, fail-closed):

1. **Parse phase** — ``joern-parse --language <joern-lang> --output <cpg.bin>
   <src_root>``. Java adds the exact R16 suffix ``--frontend-args
   --delombok-mode no-delombok`` and uses the closed Java environment for both
   phases. The original headless command was VALIDATED against real joern v4.0.554 (local docker
   rehearsal, Wave-4): ``DOC-CMP-SNAP-05 §6.3``'s original ``joern ...
   --cpg-only`` example does NOT match the pinned release — the main
   ``joern`` launcher rejects ``--output``/``--cpg-only`` ("Warning: Unknown
   option"), silently drops into interactive REPL mode, and exits 0 without
   producing any ``cpg.bin``; the real headless parse surface is the separate
   ``joern-parse`` binary (source root POSITIONAL, no ``--src``/``--cpg-only``).
   The Scanipy language id is additionally mapped to Joern's frontend
   language name (:data:`JOERN_LANGUAGE_BY_SCANIPY_LANG` — e.g. ``python`` →
   ``pythonsrc``: bare ``python`` selects joern's LEGACY ``py2cpg.sh``
   generator, which is not bundled in the release archive and hard-fails;
   ``pythonsrc`` is the bundled modern ``pysrc2cpg`` frontend).
2. **Export phase (CLAR-SNAP-05)** — ``joern --script <in-image .sc script>``.
   The ``JOERN_ARGV_ALLOWLIST`` (``tools/worker/secure_subprocess.py``) has
   ``--script`` but no ``joern-export`` pair and no generic ``--param``/
   ``--key=value`` flag, so this phase cannot pass the CPG-bin path or the
   output path as CLI flags without widening the allowlist (out of this
   component's scope — the allowlist is CMP-SNAP-05's own security-relevant
   surface, RULE-9). Instead, per CLAR-SNAP-05, the two paths are threaded
   through the ``env`` dict ``secure_run`` already accepts and passes to the
   child process (Java first uses the closed R16 profile) — the fixed in-image script
   (``workers/snapshot/joern-scripts/export_cpg.sc``, COPYed to
   :data:`EXPORT_SCRIPT_PATH` by ``workers/snapshot/Dockerfile``) reads
   :data:`ENV_CPG_BIN_PATH` / :data:`ENV_EXPORT_JSON_PATH` from its own
   process environment and writes a flat JSON node/edge array to the export
   path. That JSON is then handed to :func:`analysis.cpg_ingest.mapper.map_export`.

Boundary discipline (module docstring cross-ref, plan Provenance section):
this module MUST NOT touch ``origin``/``S_version``/``cpg_order_hash``/
``slice_fingerprint`` and must not invent its own notion of ``env_digest`` —
the authoritative ``env_digest`` is bound once, at worker boot, by
``services.snapshot.worker.resolve_env_digest`` from the running container
image digest; this module never derives ``env_digest`` from supplied variables.
Java validates/normalizes an explicit closed child profile; other languages
retain the previous opaque environment behavior. See
``docs/bhmea/JAVA-STATIC-INVOCATION.md`` for scope and remaining safety gates.

Wave-2 (out of THIS track's scope, CLAR-SNAP-03): wiring this into
``services/snapshot/worker.py::run_execute_loop`` is track 1B's job — this
module ships the callable, hermetically tested by monkeypatching the
underlying spawn exactly like ``tests/unit/test_snap_specs.py:541-573``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Final, Literal

from analysis.cpg_ingest.mapper import map_export
from analysis.ordering import CPG
from tools.worker.joern_java_safety import (
    JoernEnvironmentProfile,
    build_java_static_environment,
    observe_java_static_environment,
    validate_java_parse_paths,
)
from tools.worker.secure_subprocess import secure_run

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# Fixed in-image path the export script is COPYed to by
# workers/snapshot/Dockerfile (CLAR-SNAP-05). Never src_root-relative — the
# script is a trusted, versioned, in-image artifact, not tenant-controlled.
EXPORT_SCRIPT_PATH: Final[str] = "/opt/joern/scripts/export_cpg.sc"

# CLAR-SNAP-05 env-var parameterization contract: the export phase reads these
# from its process environment rather than CLI flags (JOERN_ARGV_ALLOWLIST has
# no generic --param flag). Names are namespaced SCANIPY_* to avoid collision
# with any joern/JVM-native env var.
ENV_CPG_BIN_PATH: Final[str] = "SCANIPY_CPG_BIN_PATH"
ENV_EXPORT_JSON_PATH: Final[str] = "SCANIPY_EXPORT_JSON_PATH"

# Provisional per-phase wall-clock ceilings (DOC-CMP-SNAP-05 §6.3 example uses
# 600s for the parse phase verbatim; the export phase is a single CPGQL pass
# over an already-in-memory-loadable cpg.bin and is budgeted shorter). Not a
# CLAR: this is an internal CMP-SNAP-05 orchestration parameter, not a
# cross-component spec question (contrast CLAR-PARAM-01's (B, T) budget).
JOERN_PARSE_TIMEOUT_S: Final[int] = 600
JOERN_EXPORT_TIMEOUT_S: Final[int] = 300

_CPG_BIN_FILENAME: Final[str] = "cpg.bin"
_EXPORT_JSON_FILENAME: Final[str] = "cpg_export.json"

# Scanipy language id (services/snapshot/worker.py::_SOURCE_EXTENSIONS values)
# -> the Joern frontend language name `joern-parse --language` actually
# accepts for the BUNDLED modern source frontends (from `joern-parse
# --list-languages` + the /opt/joern/frontends/ directory of the pinned
# v4.0.554 release). Deliberately NOT identity for python/java/js: joern's
# bare "python"/"java"/"javascript" names select legacy/bytecode generators
# ("python" -> the unbundled py2cpg.sh shell generator, which hard-fails with
# "CPG generator does not exist"; "java" -> jimple bytecode). Fail-closed: an
# unmapped Scanipy language raises rather than passing an unvetted name
# through (UnsupportedParseLanguageError).
JOERN_LANGUAGE_BY_SCANIPY_LANG: Final[dict[str, str]] = {
    "python": "pythonsrc",  # pysrc2cpg (bundled)
    "java": "javasrc",  # javasrc2cpg (bundled; source, not jimple)
    "js": "jssrc",  # jssrc2cpg (bundled)
    "ts": "jssrc",  # jssrc2cpg handles TS too
    "go": "golang",  # gosrc2cpg (bundled)
    "ruby": "rubysrc",  # rubysrc2cpg (bundled)
    "php": "php",  # php2cpg (bundled)
}


class UnsupportedParseLanguageError(Exception):
    """The Scanipy language id has no vetted Joern frontend mapping.

    Fail-closed (INV-4 posture): passing an unmapped name through verbatim
    can silently select a legacy/bytecode generator with different semantics
    (or one that is not bundled at all), so an unknown language refuses
    rather than guesses.
    """


class JoernExportMissingError(Exception):
    """The export phase completed (secure_run did not raise) but no valid
    export JSON was found at :data:`ENV_EXPORT_JSON_PATH` afterwards.

    Fail-closed: rather than let a bare ``FileNotFoundError``/``JSONDecodeError``
    propagate un-named, this names the specific CMP-SNAP-05 contract that was
    violated (the export script is supposed to always write valid JSON on a
    zero exit code).
    """


@dataclass(frozen=True)
class JoernProcessEvent:
    """One observed invocation; no inferred launch or synthetic success.

    ``argv`` comes from the subprocess result/exception and stays unknown when
    validation or launch fails before a command is supplied. Raw byte streams
    are retained without decoding. Only a validated closed Java child mapping
    may be observed, immediately before calling ``secure_run``. That projection
    is not proof a child started or an environment/image attestation. Arbitrary
    unprofiled environments are never captured (they may contain credentials).
    """

    phase: Literal["parse", "export"]
    tool: str
    requested_argv: tuple[str, ...]
    argv: tuple[str, ...] | None
    cwd: str
    timeout_s: int
    started_at: str
    completed_at: str
    elapsed_seconds: float
    returncode: int | None
    stdout: bytes
    stderr: bytes
    error_type: str | None
    error_message: str | None
    environment_observation: dict[str, object] | None = None


def _observed_run(
    tool: str,
    argv: list[str],
    *,
    phase: Literal["parse", "export"],
    timeout_s: int,
    env: dict[str, str],
    cwd: str,
    observer: Callable[[JoernProcessEvent], None] | None,
    environment_profile: JoernEnvironmentProfile | None = None,
) -> None:
    if observer is None:
        secure_run(
            tool,
            argv=argv,
            timeout_s=timeout_s,
            env=env,
            cwd=cwd,
            environment_profile=environment_profile,
        )
        return
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    started = monotonic()
    actual_argv: tuple[str, ...] | None = None
    returncode: int | None = None
    stdout = stderr = b""
    error_type = error_message = None
    run_error: Exception | None = None
    environment_observation: dict[str, object] | None = None
    try:
        if environment_profile is JoernEnvironmentProfile.JAVA_STATIC_V1:
            # Snapshot the actual post-adapter mapping before launch. A failed
            # child may change runtime paths; post-failure inspection must not
            # erase its original exception or invent a successful observation.
            environment_observation = observe_java_static_environment(
                env, cwd=Path(cwd), phase=phase
            )
        result = secure_run(
            tool,
            argv=argv,
            timeout_s=timeout_s,
            env=env,
            cwd=cwd,
            environment_profile=environment_profile,
        )
        actual_argv = tuple(result.args)
        returncode = result.returncode
        stdout, stderr = result.stdout, result.stderr
    except Exception as exc:
        run_error = exc
        error_type, error_message = type(exc).__name__, str(exc)
        if isinstance(exc, subprocess.CalledProcessError | subprocess.TimeoutExpired):
            actual_argv = (exc.cmd,) if isinstance(exc.cmd, str) else tuple(exc.cmd)
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            if isinstance(exc, subprocess.CalledProcessError):
                returncode = exc.returncode
        raise
    finally:
        # Required evidence loss is never success. If both operations fail,
        # retain the original run exception as primary and chain the evidence
        # failure explicitly, preserving timeout/exit classification upstream.
        try:
            observer(
                JoernProcessEvent(
                    phase=phase,
                    tool=tool,
                    requested_argv=tuple(argv),
                    argv=actual_argv,
                    cwd=cwd,
                    timeout_s=timeout_s,
                    started_at=started_at,
                    completed_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    elapsed_seconds=monotonic() - started,
                    returncode=returncode,
                    stdout=stdout,
                    stderr=stderr,
                    error_type=error_type,
                    error_message=error_message,
                    environment_observation=environment_observation,
                )
            )
        except Exception as observation_error:
            if run_error is not None:
                raise run_error from observation_error
            raise


def parse_source(
    src_root: Path,
    language: str,
    *,
    env: Mapping[str, str],
    workdir: Path,
    observer: Callable[[JoernProcessEvent], None] | None = None,
) -> CPG:
    """Parse ``src_root`` with the pinned Joern front-end and return a :class:`CPG`.

    The track-1A/1B handshake signature (plan "Handshakes" section) —
    track 1B (``services/snapshot/worker.py::run_execute_loop``) calls this
    exactly as typed here for the CLAR-SNAP-04 bootstrap (no-parent) path.

    Args:
        src_root: the cloned source tree root to parse (already checked out at
            the target commit by the SCM clone step — this function does no
            cloning of its own).
        language: the SCANIPY language id (e.g. ``"python"``, ``"java"`` —
            the values ``services/snapshot/worker.py::_SOURCE_EXTENSIONS``
            produces), mapped to Joern's frontend language name via
            :data:`JOERN_LANGUAGE_BY_SCANIPY_LANG` before invocation
            (fail-closed on an unmapped id).
        env: the explicit worker env to thread to both ``secure_run`` phases
            (never the host environment — ``secure_run`` never inherits it).
            This function does not read or set ``env_digest`` here.
            Java accepts only the reviewed closed-profile inputs, rejects
            native JVM/loader hooks, and normalizes HOME/TMPDIR to private job
            directories. Other languages retain opaque passthrough behavior.
        workdir: a writable scratch directory for the intermediate
            ``cpg.bin`` and the export JSON (typically an ephemeral per-job
            temp directory the caller owns and cleans up).
        observer: optional evidence consumer for actual subprocess events and
            validated closed Java child profiles. Never captures arbitrary env.
            A failing consumer aborts rather than silently losing evidence.

    Returns:
        The mapped :class:`analysis.ordering.CPG` (see
        :func:`analysis.cpg_ingest.mapper.map_export` for the deterministic
        node-emission-order contract).

    Raises:
        tools.worker.secure_subprocess.ArgvAllowlistViolation: (should be
            unreachable in normal operation — both phases below only ever
            construct allowlisted argv) a defense-in-depth signal if this
            function is ever edited to pass a non-sanctioned flag.
        subprocess.CalledProcessError: either ``joern`` phase exited non-zero.
        subprocess.TimeoutExpired: either phase exceeded its timeout.
        JoernExportMissingError: the export phase produced no readable/valid
            JSON at the expected path.
        analysis.cpg_ingest.mapper.UnknownEdgeKindError: the export JSON
            carried an edge kind outside the CLAR-SNAP-05 vocabulary.
        analysis.cpg_ingest.mapper.UnknownNodeReferenceError: the export JSON
            had a dangling edge reference.
    """
    cpg_bin_path = workdir / _CPG_BIN_FILENAME
    export_json_path = workdir / _EXPORT_JSON_FILENAME

    try:
        joern_language = JOERN_LANGUAGE_BY_SCANIPY_LANG[language]
    except KeyError:
        raise UnsupportedParseLanguageError(
            f"no vetted Joern frontend mapping for Scanipy language {language!r} "
            f"(known: {sorted(JOERN_LANGUAGE_BY_SCANIPY_LANG)}); refusing to pass "
            "an unvetted name through (it can silently select a legacy/bytecode "
            "generator with different semantics)"
        ) from None

    # Both phases need a WRITABLE HOME: the JVM resolves user.home for prefs/
    # logging, and `joern --script`'s console init creates a workspace dir —
    # from an unwritable location it dies with an opaque "Error during
    # compilation: null" (validated live, local docker rehearsal). The
    # container user's /etc/passwd home does not exist in the image, so the
    # per-job writable workdir doubles as HOME unless the caller already set
    # one explicitly.
    environment_profile = None
    if language == "java":
        # Reject source/job overlap before creating any writable runtime path.
        validate_java_parse_paths(source=src_root, output=cpg_bin_path, cwd=workdir)
        base_env = build_java_static_environment(env, workdir=workdir)
        environment_profile = JoernEnvironmentProfile.JAVA_STATIC_V1
    else:
        workdir.mkdir(parents=True, exist_ok=True)
        base_env = dict(env)
        base_env.setdefault("HOME", str(workdir))

    parse_argv = ["--language", joern_language, "--output", str(cpg_bin_path), str(src_root)]
    if language == "java":
        parse_argv.extend(["--frontend-args", "--delombok-mode", "no-delombok"])

    # --- Phase 1: parse (headless joern-parse — see module docstring) ---
    _observed_run(
        "joern-parse",
        argv=parse_argv,
        phase="parse",
        timeout_s=JOERN_PARSE_TIMEOUT_S,
        env=dict(base_env),
        cwd=str(workdir),
        observer=observer,
        environment_profile=environment_profile,
    )

    # --- Phase 2: export (CLAR-SNAP-05) ---
    export_env = dict(base_env)
    export_env[ENV_CPG_BIN_PATH] = str(cpg_bin_path)
    export_env[ENV_EXPORT_JSON_PATH] = str(export_json_path)
    _observed_run(
        "joern",
        argv=["--script", EXPORT_SCRIPT_PATH],
        phase="export",
        timeout_s=JOERN_EXPORT_TIMEOUT_S,
        env=export_env,
        cwd=str(workdir),
        observer=observer,
        environment_profile=environment_profile,
    )

    try:
        raw_text = export_json_path.read_text(encoding="utf-8")
        raw_export = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        raise JoernExportMissingError(
            f"export phase reported success but {export_json_path} was not "
            f"readable/valid JSON afterwards: {exc!r}"
        ) from exc

    return map_export(raw_export)


__all__ = [
    "ENV_CPG_BIN_PATH",
    "ENV_EXPORT_JSON_PATH",
    "EXPORT_SCRIPT_PATH",
    "JOERN_EXPORT_TIMEOUT_S",
    "JOERN_LANGUAGE_BY_SCANIPY_LANG",
    "JOERN_PARSE_TIMEOUT_S",
    "JoernExportMissingError",
    "UnsupportedParseLanguageError",
    "parse_source",
]
