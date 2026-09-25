# R16 — closed Java invocation and environment

Status: IMPLEMENTED LOCALLY; required CI/canonical review pending. Corrective issue #386,
under #362. Root coordinator assigned the schema/ingest agent and confirmed the
board In Progress. Authority: [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
Full R16/source-fidelity acceptance remains open.

## Exact boundary

The shared `parse_source(..., language="java")` path uses profile
`scanipy-java-static-env/1` for BOTH parser and fixed v1 exporter. The explicit
`secure_run(..., environment_profile=JoernEnvironmentProfile.JAVA_STATIC_V1)`
keyword selects validation, not authentication. A Java parser call without it
is rejected. Unknown profile values and profile/tool mismatches are rejected
before binary lookup or subprocess creation. Non-Java calls default to `None`.

The only Java parser argv is:

```text
--language javasrc --output <workdir>/cpg.bin <absolute-source-root>
--frontend-args --delombok-mode no-delombok
```

The delimiter is `--frontend-args`, not `--`. The value-aware parser grammar
rejects repeated/reordered flags, equals forms, unknown language selectors,
missing/additional arguments, other modes and arbitrary forwarded options.
Other vetted frontends retain their five-token shared-adapter form, without
frontend forwarding. The main `joern` allowlist is not widened.

Profiled export accepts only `--script /opt/joern/scripts/export_cpg.sc` and the
two existing v1 path parameters. No mapper, graph schema, signature, canonical
namespace, tool pin or image changes are part of this correction.

An unprofiled direct `joern --script` call has no inferable source language.
It remains outside this narrow guarantee, including the original raw-v2 probe
driver retained with #382. Its historical evidence bytes must not be rewritten.
Before any NEW Java probe, its trusted caller must adopt a reviewed compatible
profile; raw-v2 export needs an explicit extension for its distinct parameters.
This change does not certify all other frontends or direct tool callers.

## Closed environment profile

`build_java_static_environment(supplied, workdir=...)` validates the caller's
mapping and returns a new mapping; it never mutates the caller or reads ambient
environment variables. Unknown keys and unsafe values fail closed, with errors
that name the field but do not print supplied values. No arbitrary JVM/loader
hooks or resource-option strings are admitted in version 1.

| Child key | Exact generated value |
| --- | --- |
| `PATH` | `/opt/joern:/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin:/bin` |
| `JAVA_HOME` | `/opt/temurin-jre` |
| `HOME` | `<workdir>/.scanipy-java-home` |
| `TMPDIR` | `<workdir>/.scanipy-java-home/tmp` |
| `LANG`, `LC_ALL` | `C.UTF-8` |
| `JAVASRC_FETCH_DEPENDENCIES` | `no-fetch` |

The worker's existing input PATH
`/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin` and the generated PATH
above are the only accepted supplied PATH profiles; both produce the exact
generated value. Absent keys get the fixed values above. Supplied JAVA_HOME and
locale must match exactly. Supplied HOME may be the caller's workdir (the #380
input convention) or the private generated home; TMPDIR must be the generated
private path. A supplied fetch value must be exactly `no-fetch`; empty, `false`,
`0`, case variants and whitespace are rejected, not silently repaired.

The generated parse key set is closed and exact. Export adds only
`SCANIPY_CPG_BIN_PATH=<workdir>/cpg.bin` and
`SCANIPY_EXPORT_JSON_PATH=<workdir>/cpg_export.json`. Both phases are revalidated
at `secure_run`. `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `JDK_JAVA_OPTIONS`,
classpath, loader, Maven/Gradle, shell startup and other unlisted keys are not
part of this profile. This is an allowlist, not a purported complete denylist.
The legacy `--joern-env-json` cannot bypass shared Java validation.

Workdir/source paths must be absolute, lexically normalized and non-overlapping;
their existing path components cannot be symlinks. Workdir must be an owned
directory, owner writable/searchable and not group/world writable. Newly made
workdirs are mode 0700. Existing directories are not chmod-ed. The generated
home and temp directories must be owned mode-0700 directories; symlinks,
non-directories and unsafe existing permissions are rejected. Output parameters
are the exact paths above; existing output targets must be owned single-link
regular files, not symlinks, shared hardlinks or nonregular entries.
These checks do not certify immutable source capture, every source-tree entry,
hostile concurrent filesystem writers, mount isolation or a whole container.
The trusted launcher must retain a private job boundary and prevent such races.

## Observation and integration

`observe_java_static_environment(env, cwd=..., phase=...)` first validates the
ACTUAL child mapping and returns only its closed nonsecret profile, phase,
effective values and observed directory ownership/modes. It is not an env/image
digest or JVM code-source attestation. Never label the controller's pre-adapter
input mapping as the effective child environment.

The optional shared-adapter observer now forwards `environment_profile`
unchanged through `_observed_run`, preserving requested/actual argv and original
subprocess stdout/stderr/return code/exception evidence. Its optional
`JoernProcessEvent.environment_observation` is built from the same post-adapter
mapping immediately before `secure_run`, inside the observed failure boundary.
It records the validated supplied child mapping, not proof that a child started;
missing launch keeps actual argv/return code unknown. It is separate from
arbitrary supplied environment; unprofiled calls yield no such observation.
Actual validation failures remain failures, not empty success. Projection before
launch also prevents a child's later filesystem changes from masking its original
failure with a post-failure inspection error.

Observer-only errors abort. When both the invocation and evidence consumer fail,
the exact original invocation exception remains primary with the evidence error
as its explicit cause; timeout/exit classification and both failures are retained.
The observer-only seam is coordinated with #380; campaign-level serialization,
producer evidence and complete R05 acceptance remain #380 integration work.

## Pinned-source basis and non-claims

The inspected Joern v4.0.554 commit is
`cf59a329bf83063c096e1e803d608e5057d8bb95`. Its
[dependency decision](https://github.com/joernio/joern/blob/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/passes/AstCreationPass.scala)
uses exact `no-fetch` as the explicit environment disable override; other
nonempty env values enable fetching. Absent/empty values defer to configuration,
whose default disables fetching.
The resulting Maven/Gradle resolver invokes project build tooling. Current
worker/#380 defaults omit that env override; this record does not assert they
previously invoked a target build.

The pinned
[source parser](https://github.com/joernio/joern/blob/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/util/SourceParser.scala)
uses a substring Lombok trigger and may select generated source. Its
[Delombok helper](https://github.com/joernio/joern/blob/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/util/Delombok.scala)
starts trusted bundled Lombok; target-method execution was not demonstrated.
Disabling it prevents this implicit transformation but does not synthesize
missing generated declarations or prove type/binding correctness.

## Required tests and remaining TODOs

- [x] Exact Java command/profile reaches mocked subprocess; malformed forms,
  omission, unknown profiles and unsafe env fail before lookup/spawn.
- [x] Caller mapping and hostile ambient environment cannot change the profile.
- [x] Private-path, symlink, ownership and unsafe-permission falsifiers pass.
- [x] Both real shared-adapter phases forward the profile; unchanged Python
  behavior and original exception paths have regression coverage.
- [x] Shared observer observes the actual validated effective environment without
  secrets; hermetic both-phase success/failure and evidence-loss tests pass.
- [ ] #380 campaign integrates the shared seam and persists the optional safe
  profile alongside raw process evidence; full producer/campaign tests pass.
- [ ] Final-head normal hooks, required CI and canonical review pass.
- [ ] Later separately authorized bounded Java probes confirm actual behavior;
  no target build or unsafe positive execution control is permitted.
- [ ] Full R16/R19-B still require per-file inventory/parse coverage, test-path
  exclusion handling, actual JDK/classpath and omitted/generated semantics.
  Zero exit is not coverage proof; unknown capability stays unsupported.

No source/build hooks, real parser probes, image builds, app/DB mutations,
release publication or remote merges are authorized by these hermetic tests.

Independent Security Analyst-style peer review read the applicable role/rules
and the full boundary/tests on 2026-09-25. It found no scoped blocker and
independently passed all 75 focused tests under Python 3.11.16 without any
Joern/source execution. This is not canonical PR approval, integrated #380
acceptance, or a source-fidelity/sandbox certificate.

The coordinated observer delta also received independent read-only review.
Its later dual-failure refinement was separately checked by the observer author
and canonical agent; all 19 observer tests passed, including four combined
invocation/evidence-error cases. Campaign persistence and real-tool safety or
coverage are not inferred from these hermetic mocked-spawn results.
