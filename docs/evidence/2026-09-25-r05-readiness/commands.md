# Exact R05 readiness diagnostic command record

This records one bounded diagnostic, not a general-purpose release recipe.
No dependency installation, container-image build, corpus rewrite, or scanned
program execution is part of this procedure. The evidence-local driver was
named `probe.py` during execution and is now preserved byte-for-byte as
`raw/executed-probe.py.txt`. It imports the production frontend and mapper
unchanged. Its Python audit hook records subprocess invocation arguments
without substituting a collaborator. The literal historical command below
retains the original path; a future diagnostic must select a new run identity
and point Python at the archived driver text (or an explicitly versioned new
driver), not silently overwrite this bundle. No such rerun is reported here.

## Read-only preflight

```bash
free -m
df -h /tmp /home/test/scanipy-v3.2
docker ps --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}}'
docker image inspect scanipy-t2run:latest --format 'id={{.Id}} size={{.Size}} user={{.Config.User}} entrypoint={{json .Config.Entrypoint}}'
docker info --format 'cpus={{.NCPU}} mem={{.MemTotal}} driver={{.CgroupDriver}} version={{.CgroupVersion}}'
git rev-parse HEAD
git status --short
```

Observed before allocation: 8,984 MiB host memory available, 114 GiB free disk;
32 Docker CPUs and cgroup v2. The existing `scanipy-app`/`scanipy-db` containers
were healthy and left untouched. The selected image reports root as its default
user; the diagnostic overrides it to non-root UID/GID 1000.

## Allocate isolated temporary directories

```bash
mktemp -d /tmp/scanipy-r05-readiness-20260925-XXXXXXXX
```

Returned `/tmp/scanipy-r05-readiness-20260925-Z4ppNJvT`. All later commands use
that exact resolved directory; do not reuse the example path for another run.

```bash
mkdir /tmp/scanipy-r05-readiness-20260925-Z4ppNJvT/out \
  /tmp/scanipy-r05-readiness-20260925-Z4ppNJvT/work \
  /tmp/scanipy-r05-readiness-20260925-Z4ppNJvT/tmp
```

## Create exactly one diagnostic container

```bash
docker create \
  --name scanipy-r05-readiness-20260925-0820 \
  --label scanipy.task=bhmea-r05-readiness \
  --label scanipy.evidence=2026-09-25 \
  --read-only --network none \
  --memory 4g --memory-swap 4g --cpus 2 --pids-limit 256 \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --user 1000:1000 \
  --mount type=bind,src=/home/test/scanipy-v3.2,dst=/repo,readonly \
  --mount type=bind,src=/tmp/scanipy-r05-readiness-20260925-Z4ppNJvT,dst=/job \
  --tmpfs /tmp:rw,nosuid,nodev,size=256m \
  --workdir /job/work \
  --env PYTHONPATH=/repo \
  --env PYTHONDONTWRITEBYTECODE=1 --env PYTHONUNBUFFERED=1 \
  --entrypoint python \
  sha256:911e6f836fcf5e183a0c559e04e1868ba9d1838c35263728fe85dc1e9cce987b \
  /repo/docs/evidence/2026-09-25-r05-readiness/probe.py
```

Returned container ID:
`dde989e91172c4dd8596b81f6f0003362115315ed73a2bc76012c388baac097f`.
The SHA above is the actual local image ID, not an asserted registry manifest
digest or a fabricated production `env_digest`.

```bash
docker inspect scanipy-r05-readiness-20260925-0820 \
  --format 'id={{.Id}} image={{.Image}} status={{.State.Status}} memory={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} nanocpus={{.HostConfig.NanoCpus}} pids={{.HostConfig.PidsLimit}} network={{.HostConfig.NetworkMode}} readonly={{.HostConfig.ReadonlyRootfs}} user={{.Config.User}} mounts={{json .Mounts}} security={{json .HostConfig.SecurityOpt}} capdrop={{json .HostConfig.CapDrop}}'
docker start -a dde989e91172c4dd8596b81f6f0003362115315ed73a2bc76012c388baac097f
```

The inspection confirmed 4,294,967,296-byte RAM and RAM+swap limits (no container
swap), 2,000,000,000 nanoCPUs, 256 PIDs, network `none`, read-only root and `/repo`,
UID/GID 1000, no-new-privileges, and all capabilities dropped. Job-data writes
are isolated to `/job` and a 256 MiB `/tmp` tmpfs; Docker's standard virtual
runtime filesystems remain present. The frontend retains its existing
600-second parse and 300-second export timeouts.

## Explicit Joern child environment

The probe passes this complete non-secret environment to `parse_source`; it
does not change `DEFAULT_JOERN_ENV` or the image:

```json
{
  "PATH": "/opt/joern:/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin:/usr/local/bin",
  "JAVA_HOME": "/opt/temurin-jre",
  "HOME": "/job/work",
  "TMPDIR": "/job/tmp",
  "JAVA_TOOL_OPTIONS": "-Xmx1536m -XX:ActiveProcessorCount=2 -Duser.home=/job/work -Djava.io.tmpdir=/job/tmp"
}
```

`secure_run` resolves Joern using fixed absolute binary paths. A missing
`which joern` under the image's default PATH alone therefore does not prove
that production `parse_source` fails. This diagnostic uses the explicit PATH
requested for readiness verification and records actual subprocess argv.

Successful child stdout/stderr is captured internally by the production
`secure_run` wrapper and not returned by `parse_source`; this diagnostic does
not change that behavior. The probe records invocation audit events, its own
output, resulting artifacts, and any exception streams available on failure.
No invocation of a detector, solver, or fingerprint computation is requested.

## Capture and cleanup after normal completion

The container exited normally with code 0. Capture native tool outputs before
removing it:

```bash
docker inspect dde989e91172c4dd8596b81f6f0003362115315ed73a2bc76012c388baac097f \
  > /tmp/scanipy-r05-readiness-20260925-Z4ppNJvT/out/container-inspect.json
docker logs dde989e91172c4dd8596b81f6f0003362115315ed73a2bc76012c388baac097f \
  > /tmp/scanipy-r05-readiness-20260925-Z4ppNJvT/out/container.log 2>&1
```

The three `out/` files (`diagnostic.json`, `container-inspect.json`,
`container.log`) and the two `work/` files (`cpg_export.json`, `cpg.bin`) were
copied with `cp -n` into this bundle's `raw/` directory. `cmp` confirmed every
source/destination pair, and `sha256sum` produced the manifest's digests.
No raw output was reformatted or edited.

```bash
docker inspect dde989e91172c4dd8596b81f6f0003362115315ed73a2bc76012c388baac097f \
  --format '{{.State.Status}} {{.State.Running}} {{.State.ExitCode}}'
docker rm dde989e91172c4dd8596b81f6f0003362115315ed73a2bc76012c388baac097f
docker ps --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}}'
```

Inspection returned `exited false 0`. Removal targeted that exact stopped
container only; no force flag was used. The existing application/database
containers remained healthy. The isolated temporary directory was retained.
