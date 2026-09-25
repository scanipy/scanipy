# Snapshot Python lock: correction and reproducibility

Scope: issue #381, a CMP-DEPLOY-02 prerequisite for #366 / #374. This is a
dependency lock and build-gate correction, not a built-image acceptance report.

## Reviewed inputs and generator

`requirements.in` freezes all 11 previously listed versions, including
SQLAlchemy 2.0.50. It adds PyYAML 6.0.3, cryptography 50.0.1, cffi 2.1.1 and
pycparser 3.0. These four versions were observed in the tested Python 3.11.16
reference environment on 2026-09-25; they are not described as latest.
No base, Joern, CodeQL, Git or Temurin JRE pin changes in this correction.

The committed generator is `workers/build/compile_snapshot_lock.py`. It uses
the observed `uv` distribution version **0.12.19**, confirmed by both its
`uv-0.12.19.dist-info/METADATA` and actual `--version` output:

```text
uv 0.12.19 (x86_64-unknown-linux-gnu)
binary SHA256: 242e462a63f5a3c0421d68557006193ecbfb61321cba0fe8542213ac62d92563
target Python: 3.11
target platform: x86_64-unknown-linux-gnu
public index: https://pypi.org/simple
exclude-newer: 2026-09-25T09:49:02Z
requirements.in SHA256: a87675732a9efadafaf823e0e4f1a545df0f47ee7851a780e092955f7c6b39ec
requirements.txt SHA256: a3c384ca85126c5712b7124b035f0754d4da4e484b401383a85690f03868b581
```

The executable bytes and version are checked **before** resolution. Run the
wrapper with Python 3.11. It clears inherited resolver/index/build options,
disables config discovery and Python downloads, uses a private temporary
cache/output, and accepts only exact registry package pins. `--only-binary
:all:` forbids package source builds during resolution and is emitted into the
lock so the Dockerfile's existing `pip --require-hashes` install also selects
wheels only. Distribution hashes may include other published artifacts; the
wheel-only directive governs artifact selection. The wrapper intentionally
does not install dependencies or update `pins.json` automatically.

The observed generator rejects combining `--no-build` with `--only-binary`;
the final command uses only the latter. The first contradictory invocation
failed before resolution and did not change the lock. The corrected invocation
resolved exactly 15 distributions in 3.11 seconds. A fresh-cache `--check`
resolved the same 15 distributions in 2.91 seconds and reproduced identical
bytes. No package build backend,
Docker build, Joern process or scanned fixture was executed.

## Reproduction and byte verification

From the reviewed checkout, with the verified uv executable already available:

```sh
python3.11 workers/build/compile_snapshot_lock.py --uv /path/to/verified/uv
python3.11 workers/build/compile_snapshot_lock.py --uv /path/to/verified/uv --check
python3.11 workers/build/verify_pins.py
```

Exact initial local invocation (temporary tool paths are reference-host
observations, not portable deployment paths):

```sh
PYTHONPATH=/tmp/scanipy-snapshot-lock-HZMVOrGM /tmp/scanipy-runtime-366-testenv-Wv50QT/venv/bin/python workers/build/compile_snapshot_lock.py --uv /tmp/scanipy-canonical-tools.B74lKo/bin/uv
```

`compile_argv()` in the committed wrapper is the complete subprocess argv
contract, including target, cutoff, public index and build restrictions.
`--check` independently resolves into a fresh temporary file and refuses any
byte drift; it does not rewrite the committed lock. Network/index availability
is required for regeneration, not for `verify_pins.py` or unit tests. Future
index/artifact changes are detected as drift rather than silently accepted.
The committed input, generator revision, lock bytes and this generator identity
must travel together through review.

Before this correction, actual lock SHA256 was
`4be500a607f3312352a93f0365e6e11e0dff44735c456bc4b6221191103eea30`, while
`pins.json` declared
`aad38638969e79d16db3ee3d55f605fb08119f35a1ae6d34309e29f8ea341add`.
The old gate returned 0 despite that mismatch. The corrected gate requires
the exact `workers/snapshot/requirements.txt` path copied by the Dockerfile,
not an arbitrary same-content file. It refuses malformed hashes, missing or
non-regular files, symlink components, duplicate JSON fields and changed bytes.
The generator also refuses symlinked input/output parents before invoking uv.
An alternate manifest
still uses this tool's checkout unless `--repo-root` explicitly selects another
trusted checkout. It never derives the repository root from JSON or the cwd.

## Remaining work, explicitly not earned here

- Canonical review and green CI precede merge. The PR title includes
  `env_digest rollover` because `pins.json` changes. No active registry mapping,
  published image, historical snapshot identity or deployment is changed here.
- After separate resource approval, build/inspect the corrected snapshot image
  and verify `pip check`, exact distributions and native imports (`yaml`,
  cryptography Rust/cffi, SQLAlchemy/psycopg2, boto3). A resolver success alone
  does not establish wheel installation or native-loader success.
- Check the actual `services.snapshot.worker` entrypoint: missing env must
  produce the intended INV-2 refusal, not an import failure. A controlled
  empty-queue startup smoke is not full environment/signature proof.
- Verify trusted mounted source/import identity with an empty private Python
  cache prefix and bytecode writes disabled. Preserve the actual launcher,
  exporter and JRE identities. The current JRE pin does not prove a JDK exists;
  any demonstrated `javac` requirement needs a separate tool-pin decision.
- Run one bounded sequential Java and Python two-side production-frontend
  probe only after explicit launch/resource approval. The full 844-side
  campaign remains separate; neither G0 nor full R05/C18 is complete here.
- Preserve existing app/DB containers. Capture fresh reference-host resources
  before any image build/probe; the reference host is not confirmed stage
  hardware. Report a Docker local image/config ID separately from an OCI
  registry manifest/RepoDigest. An empty `RepoDigests` list stays empty; no
  registry identity or signature may be inferred from a local image ID.
