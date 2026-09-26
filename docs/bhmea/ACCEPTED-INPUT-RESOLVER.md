# Accepted-input resolver and immutable registry binding

Status: approved for scoped local implementation under #399; not operationally accepted.
Date: 2026-09-25. Base inspected: `fe61c9cdcf4ae56cf5c7fd682b3a73c3502f1808`.
Scope owner: root coordinator; schema/ingest agent owns this contract and the
12 new verifier files allocated in §11.1. Other implementation slices require
separate allocation.

This is an additive design under [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
It supplies the missing accepted-input producer for the
[occurrence store](OCCURRENCE-PERSISTENCE-SCHEMA.md) and early real-source G1.
It does not change old `S_version` records, old signatures, occurrence-v1
encodings, the submitted scope, or the current requirements for review/tests.
The occurrence checkpoint stays frozen. On 2026-09-25 the root coordinator
approved this contract and allocated this document plus §11.1's 12 new files
for local implementation under claimed issue #399. This records that explicit
delegation; it does not grant itself authority. It is not operator/model
acceptance, trust/admission installation, native-source execution, a DB/schema
change, deployment, or canonical repository acceptance. Those remain separate.

## 1. Outcome and nonclaims

The runnable target is a resolver that reads an exact, durably published bundle,
verifies its content and scoped acceptance authority against independently
configured trust, and seals those same bytes into an execution request.
Neither `accepted=true`, a Python result type, a version string, a git commit,
nor a successful PR review is acceptance authority.

Keep four questions separate:

| Question | Required evidence | Does not establish |
|---|---|---|
| Are these the admitted configuration bytes? | Immutable byte blobs, ordered manifest, exact digests | Correct detection semantics |
| Who authorized their use, for which scope? | Verified approval signature, scoped key grant, current trust policy | Statistical precision or human authorship inferred from text |
| Did a proposed spec pass a statistical gate? | Bound candidate and immutable adjudication/gate decision evidence | Universal recall, representativeness, or frontend fidelity |
| Did this run use the model correctly? | Actual source/graph association, producer/solver evidence and supported preconditions | Established merely by registry admission |

Registry acceptance creates no finding, graph, slice, canonical strength,
source capture, SCM proof, or suppression permission. R09 independent classes
and R19 semantic/fidelity gates remain independent downstream requirements.

## 2. What the inspected implementation actually proves

The following are code observations, not proposed fixes to historical records.

| Existing surface | Observed behavior | Consequence for the new path |
|---|---|---|
| [`DetectorRegistry`](../../detectors/registry.py), `load_manifests`, `_load_core_spec` | Parses current manifest text; reads the first sorted `*.dsl.yaml`; carries parsed `Spec` or an oracle path. No exact file-byte inventory or accepted-version association is retained. | A frozen process object is not an immutable, accepted content bundle. Never silently ignore additional files in a new importer. |
| [`SqlSpecRegistryPort`](../../services/scan/sql_adapters.py), `resolve_latest`, `is_registered` | Queries global `spec_versions` by creation time or version existence; no org/detector/content/signature join. | Cannot authorize execution of a selected detector or recover exact accepted bytes. |
| [`worker._findings_from_core`](../../services/scan/worker.py) | Solves `detector.spec` from the supplied registry and threads `job.S_version` independently. | Merely stamping the selected version does not prove that its bytes were used. |
| [`evaluate_proposed_spec`](../../services/triage/spec_inference.py) | Computes a verdict from caller-supplied candidate/state. All persistence/signing ports are optional; atomicity is delegated to the caller. Repository searches found only test callers and fake spec-version/proposal stores. | The mathematical component is not a durable accepted-input producer. A returned verdict cannot be imported as authority. |
| Same module, `next_semver_for_class` / `SpecVersionRow` | Allocates versions per class; carries `e_process_detail` in Python. Shipped SQL has a scope-wide version key and no matching detail column. | Do not assume the fake-store allocation/persistence contract matches the real schema. |
| Legacy [`spec_versions` DDL](../../db/migrations/versions/20260524_0001_initial_tenancy_tables.py) | Stores `spec_set` as JSONB, global or customer scope, without original raw bytes or detector-version keys. | JSONB reserialization is a new representation, not recovery of the original accepted file. |
| Same DDL and [RLS](../../db/migrations/versions/20260524_0002_rls_policies.py) | `scanipy_app` has table-level spec-version DML; customer modifications can satisfy tenant RLS. There is no unconditional immutable-body trigger on this table. Global writes are separately limited by RLS. | Historical prose describing all spec versions as immutable is not an adequate new fence. Preserve existing grants/rows; use a new boundary. |
| Legacy `_spec_acceptance_record` | Binds identifiers/version/environment, not a raw spec/detector/rule content digest. Contains documented sentinel source/snapshot fields. | Even a verified old signature cannot authenticate bytes that were never signed. Do not copy these sentinels into the new acceptance domain. |
| [`sign_provenance` / `verify_chain`](../../services/scan/provenance/__init__.py) | Perform real signing/verification through an injected key provider. Verification depends on that provider's key lookup. | Reuse appropriate cryptographic primitives, not the finding-record shape or caller-selected trust. |
| [`SoftwareKMSSigner`](../../services/scan/software_kms_signer.py) | Generates an ephemeral RSA key at construction, is expressly test/dev-only, and resolves by version without independently enforcing a configured key-id trust map. | Suitable for controlled tests, not persistent acceptance identity. It is not the proposed registry issuer. |

Existing unit/statistical tests and the SQL registry test remain useful within
their tested boundaries. The SQL registry test deliberately inserts empty
`spec_set` objects; it does not prove acceptance-content or signing enforcement.

## 3. Smallest vertical delivery and authority lanes

First deliver one explicit, operator-reviewed builtin bundle for one concrete
tenant, one detector, and the bounded early-G1 Python scalar model. Retain both
language diagnostic/model fixtures; the Java syntax producer is a separately
required next extension, not implied by the Python result. Use
the real immutable publication, verification, request binding, and store seal;
do not substitute a fake registry or a hand-authored acceptance receipt.
This is an initial integration slice, not a reduction of the full goal.

Two distinct approval kinds are proposed:

1. `builtin-operator`: an installation-authorized publisher explicitly adopts
   reviewed builtin configuration bytes for the stated scope. Its signed event
   is an administrative/configuration decision. It makes no e-process or
   measured-precision claim. Repository presence, code review, CI, an agent
   role name, and possession of a scan credential do not emit this event.
2. `statistical-spec`: a separately authorized gate service publishes a bound,
   durably accepted candidate after verified adjudication/gate processing.
   Pending/runtime LLM proposals cannot fall back to the builtin lane. A
   builtin publisher's key has no statistical-acceptance capability.

The first implementation must reject `statistical-spec` as unsupported until
the real adapter in §9 exists. Do not issue that label from the current optional
ports or fake stores. Conversely, do not describe an operator-approved builtin
as statistically accepted. The operator lane and its installed publisher trust
require explicit owner adoption before actual publication; they are proposed
here, not inferred from authorization to write this document.

No algorithm can establish a person's authorship or review from a JSON field.
The trusted publisher is accountable for the administrative attestation. Known
proposal lineage is immutable and cannot be deleted/relabelled to bypass the
statistical route; intentional deception by an authorized trust administrator
is outside the scanner-user threat boundary and must remain visible in audit.

## 4. Exact names, scope, version and content identity

Use a new registry identity `registry_id: UUID`, not the legacy version table
as a namespace. A scope is exactly `(scope, org_id)`, with `scope=global` iff
`org_id=null`, or `scope=customer` with an actual tenant UUID. Global visibility
never grants global publication authority. The first delivery uses customer
scope; global publication/explicit composition use the same checked machinery
only after their scoped trust grants exist.
New detector/rule/artifact textual IDs use ASCII
`[A-Za-z][A-Za-z0-9_.:/-]{0,127}`, matching the coordinated G1 `Id` grammar.
They are inert qualified names, not filesystem paths. This is separate from
the narrower authority key-label `Token` type in §6.2.

Required uniqueness:

- Bundle version: `(registry_id, scope, org_id, S_version)`, using separate
  global/customer unique constraints so NULL cannot admit duplicate globals.
- Artifact version: `(registry_id, scope, org_id, kind, artifact_id, version)`.
  Kinds are `detector`, `rule-set`, `operation-model`; this key binds one exact
  schema and byte digest forever. Same key/different bytes is a conflict.
- Within a bundle: detector IDs are unique; each detector has unique logical
  rule IDs. Ordered membership is part of the content, not a query accident.
- An approval event UUID and publication idempotency key identify one exact
  statement/signature/evidence inventory. Changed replay is rejected.
- A request binding is unique by `(org_id, codebase_id, request_id)` and cannot
  later point at another bundle, scope, version, approval, or content digest.

`S_version` and artifact versions are bounded `MAJOR.MINOR.PATCH` ASCII labels
in this initial profile: no implicit aliases, prerelease interpretation or
automatic class-local version allocation. Exact bundle UUID **and** expected
content digest are required by the runnable resolver. There is no `latest`
operation in the first execution path. A future UI may explicitly select a
version, but must resolve it once to an immutable qualified ID/digest before
request creation. Never independently select one version per worker retry.

Initial bundles have a single scope: no implicit global/customer union or
shadowing. Future composed S must list and approve every qualified constituent
and conflict rule as a new bundle; a tenant override cannot silently replace
a global rule with the same textual ID.
The first request/attempt adapter accepts customer bundles for that same org
only. Global signed material may be read/verified as scoped material, but
global-to-customer execution/composition requires an explicit later schema
separating registry org from requesting org; never put a tenant UUID in a field
whose signed global value was null.

### 4.1 Bytes and framing

Reuse the occurrence envelope's portable JSON domain for **new metadata**:
UTF-8 scalar strings excluding NUL/lone surrogates, signed int64, bool distinct
from int, no floats, sorted keys, compact separators, no duplicate/unknown
keys, depth at most 32. Original content blobs are retained byte-for-byte;
do not YAML/JSON-roundtrip a raw artifact to calculate its content digest.
Raw detector/rule/model JSON must satisfy its strict bounded content schema,
but need not use canonical key ordering or whitespace. Canonical equality is
required for control/authority envelopes and S metadata, not imposed by
rewriting raw content into a different supposedly historical representation.

Raw content digests are SHA256 as 64 lowercase hex. Metadata domain digests
are SHA256(`ASCII schema + LF + exact canonical bytes`). Never interchange
these with `sha256:` environment labels, source-tree digests, graph identities,
policy-document digests, or proof of runtime-loaded code.
For a complete binary framed object, its digest is raw SHA256 of the entire
frame including its literal prefix/lengths; `request_binding_digest` specifically
hashes the retained complete `scanipy-sealed-acceptance/1` frame. SQL authority
`record_digest` hashes schema+LF+canonical record bytes. Signature and DER hash
fields are raw-byte digests. These names do not permit an alternate encoding.

Proposed spec blob framing, `scanipy-accepted-spec-set/1`:

```text
ASCII "scanipy-accepted-spec-set/1" + LF
u64-BE byte_length(S_manifest) + exact canonical S_manifest bytes
for each model in S_manifest.models, in that exact order:
    u64-BE byte_length(model_raw_bytes) + exact model_raw_bytes
EOF, with no trailing bytes
```

Lengths/counts are validated against the bounded manifest and remaining input
before reads/allocations. Every model digest/schema/version must match its
manifest descriptor; reject duplicate descriptors, missing/extra frames and
unsupported versions. This is a new aggregate S artifact, not a claim to have
recovered a legacy spec serialization. Model bytes remain exactly recoverable.

Closed S manifest fields: `schema=scanipy-accepted-s-manifest/1`, `registry_id`,
`bundle_id`, `scope`, `org_id`, `S_version`, `detectors`, `models`.

- Each ordered detector member has `detector_id`, `detector_version`,
  `detector_schema`, `detector_sha256`, `class_id`, `language_profiles`, `engine`,
  and ordered `rules`.
- Each rule has `rule_id`, `artifact_id`, `version`, `schema`, `raw_sha256`,
  `semantics`, `projection_profile`, `model_artifact_id`, `model_raw_sha256`,
  `semantic_descriptor_digest`. Every member must resolve exactly once.
- Each ordered model descriptor has `artifact_id`, `version`, `schema`,
  `raw_sha256`. Its actual bytes follow the manifest in the framing above.
- The semantic descriptor is a separately versioned closed metadata object
  binding the exact rule/model raw digests plus semantics/projection IDs.
  Its digest is a content-bound compatibility discriminator, not a proof of
  semantic equivalence, purity, distributivity or source fidelity.

Accepted detector bytes are the exact versioned descriptor/manifest bytes.
The new runnable descriptor schema is `scanipy-accepted-detector/1`, with
`schema`, `id`, `version`, `class_id`, `cwes`, `languages`, `frameworks`,
`engine`, `severity_default`, ordered `rule_ids`, and ordered `profiles`.
Each profile is `{language, projection_profile, source_syntax_schema}`;
duplicates or inconsistent language membership fail. Declared profiles are
supported-format requests, never a `ready` claim or frontend-gate result.
This initial importer accepts the closed new JSON descriptor only. Legacy
manifest adoption needs an explicit future importer preserving the raw file
and describing any new projection; `yaml.safe_load` alone is not that contract.

Its exact initial scalar/array types are:

| Field | Closed type and checks |
|---|---|
| `schema` | Exactly `scanipy-accepted-detector/1` |
| `id` | §4's `Id` grammar; equals the S member's detector_id |
| `version` | §6.2 `Version`; equals detector_version |
| `class_id` | Exactly a §5 `ClassName` value |
| `cwes` | Nonempty ordered unique array, at most 64 strings matching `CWE-[1-9][0-9]{0,6}`; no numeric coercion |
| `languages` | Nonempty ordered unique subset of `python`, `java`; at most 2 |
| `frameworks` | Ordered unique array of 0..32 §4 `Id` strings; inert descriptive labels, not eligibility rules or callbacks |
| `engine` | Exactly `ifds` in this first descriptor profile; other engines are explicitly unsupported here |
| `severity_default` | Exactly `low`, `medium`, `high`, or `critical`, matching the existing registry vocabulary |
| `rule_ids` | Nonempty ordered unique array of §4 `Id`; exact equality with S member rule_id order, bounded by raw/manifest byte limits rather than a new rule-count cap |
| `profiles` | One object per language, in the same order, each exactly `{language, projection_profile, source_syntax_schema}` |

Each profile's language is the corresponding array value;
`projection_profile="scanipy-java-python-scalar-flow/1"` and
`source_syntax_schema="scanipy-source-syntax/1"`. S member `language_profiles`
is that exact profiles array, not an independently interpreted shorthand.
All nested values are exact JSON types; null is forbidden in this descriptor.
CWE spelling validation does not assert that an arbitrary number is a real
taxonomy entry. Framework labels and decodable Java profiles do not confer
runtime support: the first semantic producer permits only its explicitly
implemented Python injection profile. IDE/oracle descriptors, other language
profiles and real framework-specific eligibility require their separately
versioned/reviewed extension; the full submitted scope remains required.

The S manifest's `detectors` is a nonempty ordered array with unique detector
IDs. Each detector's `rules` is nonempty and unique by rule_id/artifact_id;
raw detector/rule order is exactly that traversal. Models are a nonempty ordered
array, unique by artifact_id/version and raw SHA. Each rule descriptor resolves
its model_artifact_id plus model_raw_sha256 to exactly one model descriptor;
the QualifiedRuleKey carries that entry's exact version as well.
Duplicate or unused model entries reject in this initial
profile. `detector_schema`, rule `schema`, model `schema`, `semantics` and
`projection_profile` are exactly the supported literal IDs in §§4–5.
Rule descriptor rule_id equals parsed spec_id; artifact IDs use §4 `Id`,
versions use §6.2 `Version`, and all digest fields use §6.2 `Digest`.

Accepted rule bytes are the exact raw rule-set bytes in detector/rule order.
The existing occurrence `accepted-content/1` manifest hashes the framed S blob
and those two raw arrays. Its digest is the proposed bundle content identity;
the S manifest does not contain that digest, avoiding a circular definition.
The exact semantic descriptor schema is `scanipy-rule-semantics-binding/1`,
with `schema`, `rule_raw_sha256`, `model_raw_sha256`, `semantics`, and
`projection_profile`. Derive its canonical bytes from the validated member,
verify its domain digest, and retain them with the publication inventory.

Combined S/detector/rule bytes must fit the store's existing **1 MiB** cap;
models inside S consume that cap too. Acceptance evidence separately fits
**1 MiB**, including signatures, retained public keys, trust policy and any
statistical evidence inventory. Every metadata envelope also has a 1 MiB cap.
No tighter accepted-rule count is introduced: valid bounded metadata constrains
the array lengths before traversal/hashing. Use exact tuple/bytes inputs and
bounded reads; reject overflow, compression/archive expansion, aliases and
unbounded iterables. Nothing is silently truncated into an accepted bundle.

## 5. Early-G1 coordination: accepted bytes are not a semantic proof

The canonical/solver agent supplied these proposed, not yet accepted, IDs:

- Rule artifact: `scanipy-bound-rule-set/1`; semantics: `scanipy-scalar-ifds/1`.
- API/builtin models: `scanipy-operation-models/1`.
- Semantic projection: `scanipy-java-python-scalar-flow/1`.
- Source supplement: `scanipy-source-syntax/1`.

Rule fields are `schema`, `semantics`, `spec_id`, `class_id`, `engine=ifds`, `languages`,
`projection_profile`, `model_artifact_digest`, ordered `clauses`. Original
clause ordinal is its array index, never renumbered by language/match filtering.
`class_id` uses the existing closed `ClassName` enum: injection,
path-traversal, ssrf, deserialization, xss, crypto-misuse, authn-authz, secrets,
dep-cve, memory-safety. It must equal the detector's class, not be inferred
from `spec_id`. This explicit field is coordinated with the proposed
`SOURCE-BOUND-SCALAR-IFDS.md` contract, not an extension of legacy DSL bytes.
An entry-parameter Source binds a uniquely source-associated declaration and
formal position. Sink/Propagate/Sanitize bind model IDs and typed input/output
positions; they are not arbitrary callbacks or planted graph labels.

Operation-model fields are `schema`, `target_platform_profiles`, and models
ordered uniquely by `model_id`. A model binds language, operation/symbol/
signature, precondition IDs, normal/exceptional result/effect contracts and
transfer authorization. Exact precondition evaluation and native/source
association are the solver/producer contract, not this resolver's invention.
Resolve a model by `(rule.model_artifact_digest, model_id)`. Model IDs are
unique within their exact artifact, not globally; two retained model artifacts
must never overwrite each other's entries in a process-global ID dictionary.
Initial IDE, heap/field, wildcard, ambiguous dispatch, default/star-argument
and unsupported model forms fail closed. A Python annotation alone does not
establish a runtime receiver/API binding.

Logical finding `rule_id` is the whole bound rule-set's `spec_id`, **not** a
generated sink-clause identifier. The raw result preserves source-clause
ordinal and exact matched sink-clause ordinals. Typed sink input positions
remain distinct sites. Multiple matching sink clauses do not invent extra
registry rules. Store these diagnostics in immutable raw/result evidence until
their dedicated wire schema lands; do not alter frozen occurrence columns.

Require detector/rule `engine`, class, language/profile, `spec_id`, model digest
and schema compatibility to agree before dispatch. Parse only these new
versioned bytes for G1. Legacy DSL remains legacy; no silent conversion to
typed selectors. New graph/slice semantic namespaces will be `/3`, not an
in-place reinterpretation of `/2`. Registry resolution never assigns either
artifact a strength or grants baseline suppression.

One semantic invocation receives exactly one qualified detector/rule artifact.
The coordinated closed `QualifiedRuleKey`, schema `scanipy-qualified-rule/1`,
has `schema`, `registry_id`, `bundle_id`, `scope`, `org_id`, `S_version`,
`accepted_content_digest`, `detector_id`, `detector_version`,
`detector_raw_sha256`, `rule_id`, `rule_artifact_id`, `rule_artifact_version`,
`rule_raw_sha256`, `model_artifact_id`, `model_artifact_version`,
`model_raw_sha256`, and `semantic_descriptor_digest`. UUID/version/digest types
are those below; every value is derived from the exact accepted membership,
never first/latest matching. The scalar contract owns its semantic use.
Composition key is `(capture UUID, QualifiedRuleKey, local occurrence key)`;
execution tenant/request/capture remain separate mandatory bindings. Isolate
fact/summary/sanitizer domains between rules and report each attempted rule's
coverage. One rule's completion never certifies unattempted bundle members.
Logical finding `rule_id=spec_id` and the store's ordered inventory are unchanged.

### 5.1 Exact resolver-to-producer public interface

The coordinated public names are exposed from `services.scan.accepted_inputs.models`:

- `QualifiedRuleKey`: the exact class owned by `analysis.ifds.bound_rules`,
  re-exported unchanged. That module has no services import. Its sole metadata
  codecs are `decode_qualified_rule_key(data: bytes) -> QualifiedRuleKey` and
  `encode_qualified_rule_key(key: QualifiedRuleKey) -> bytes`: canonical UTF-8,
  at most 16 KiB, depth 4 and 64 JSON values. Delegate to these codecs; never
  define a second divergent key class or metadata schema in the resolver.
- `AcceptedBundleBytes`: exactly `spec_bytes: bytes`,
  `detector_blobs: tuple[bytes,...]`, `rule_blobs: tuple[bytes,...]`. These are
  the full bounded bundle, not a selected subset pretending to have its digest.
- `ExecutionBinding`: exactly `org_id`, `codebase_id`, `request_id`,
  `capture_id`, `seal_id`, `work_item_id`, `work_attempt_id`, `detector_run_id`,
  `capture_lease_id`, `authorization_event_id` (all UUIDs);
  `fencing_token` (positive int64), `work_revision` (Count);
  `run_input_digest`, `requested_policy_digest`, `attempt_policy_digest`,
  `authorization_digest` (Digests); `lease_expires_at` and
  `capture_lease_expires_at` (UtcInstants). This initial public view is for an
  actual detector run, not an identity attempt or generic job.
- `ResolvedQualifiedRule`: exactly `qualified_rule: QualifiedRuleKey`,
  `bundle: AcceptedBundleBytes`, `sealed_authority_evidence: bytes`,
  `execution_authorization: bytes`, `binding: ExecutionBinding`.
  Read-only `detector_bytes`, `rule_bytes`, `model_bytes` properties select the
  uniquely validated manifest membership; they never independently discover a
  file, choose a first match or replace the complete bundle on the wire.
- `VerifiedQualifiedRule`: exactly `resolved: ResolvedQualifiedRule`,
  `checks: VerificationChecks`; its current-execution fields are non-null.
  It is a checked return value, not a serializable bearer capability.

Models are frozen exact concrete types with exact bytes/tuple members; no
subclasses, arbitrary Mapping/iterables or mutable aliases. New authority and
execution-binding UUID fields are exact `uuid.UUID` values in Python and
canonical UUID strings on the wire. The shared `QualifiedRuleKey` retains its
owner's exact canonical-string UUID fields; it is re-exported, not redefined.
timestamps are exact validated canonical strings, not permissive datetime
coercions. All content is revalidated at the public seam, including a model
that was illicitly modified after construction.

The producer calls this itself, not a caller-supplied verification callback:

```text
services.scan.accepted_inputs.verify.verify_resolved_qualified_rule(
    resolved: ResolvedQualifiedRule,
    *, expected: ExecutionBinding, authority: ExecutionAuthorityReader,
) -> VerifiedQualifiedRule
```

`ExecutionAuthorityReader` is a trusted server-configured port, with exactly:

```text
runtime_profile: VerifierRuntimeProfile  # installed server configuration
read_execution_authority(expected: ExecutionBinding) -> ExecutionVerificationContext
recheck_execution_authority(expected: ExecutionBinding,
                            context: ExecutionVerificationContext) -> None
```

`ExecutionVerificationContext` has exactly `installed_trust: InstalledTrust`,
`admission: AdmissionExpectation`, `ledger: LedgerExpectation`,
`live_authority_evidence: bytes`, `reference_time: UtcInstant`.
Those closed shapes are defined in §6.6. The runtime profile is not loaded
from a registry row, bundle or returned ledger JSON.

The real later SQL/admission adapter reads the exact immutable publication,
request binding and authorization plus current locked policy/work/lease state;
it separately reads the installed trust/checkpoint. It compares every expected
binding field and returns this fresh bounded snapshot, never `accepted=true`.
After bounded crypto/content verification, `recheck_execution_authority`
re-reads the same live fields and external checkpoint, verifies time/lease
validity and rejects any changed head/fence/revision/epoch before returning.
The launcher also performs its §7.3 immediate pre-launch check. A restored or
cached snapshot cannot satisfy these fresh reads merely by matching its own
hashes. These checks do not claim cross-system atomic instantaneous revocation.

Only the trusted production factory may install this port; scan users, source,
model bytes and CLI inputs cannot select a reader, runtime profile or fake.
The first verifier slice tests explicit diagnostic readers, but real execution
stays unavailable until the genuine later repository/admission adapter lands.
The required argument has no default/mock/in-memory production fallback.
Neither the type name nor a caller-constructed `VerifiedQualifiedRule` replaces
the producer's mandatory fresh invocation of this API.

## 6. Trust and signed authority evidence

### 6.1 Bootstrap and cryptography

The installation owner supplies an out-of-band pinned registry trust-root
public-key fingerprint and an immutable local trust configuration. Do not trust
a public key because the bundle carries it, because it has a familiar key ID,
or because a caller supplied a signer object. Missing trust fails closed.
The first closed installed configuration, `scanipy-registry-installed-trust/1`,
has `schema`, `deployment_id: UUID`, `registry_id: UUID`, `scope`, `org_id`,
`root_spki_sha256: Digest`, and `administrator_actor_id: UUID`. It is at most
4096 canonical UTF-8 bytes and uses §6.2 types. Its authority comes from the
owner-controlled installation/read-only service configuration, not its schema
name, a self-signature or presence inside a bundle. One administrator/root per
namespace is the first profile; changes require explicit owner installation.

Proposed new signature profile: `scanipy-registry-rsa-pss-sha256/1`, RSA-3072,
public exponent 65537, SHA256, MGF1-SHA256 and 32-byte salt. A signature is
exactly 384 bytes; public identity is SHA256 of exact DER SubjectPublicKeyInfo.
Require one complete, canonical DER SPKI with no trailing bytes and exact
re-encoding equality. Reject PEM, certificates, private keys, RSA-PSS parameter
variants and algorithm fallback in this public verification interface.
This is a new profile using existing cryptographic
dependencies, not a modification of legacy provenance signing. Its signatures
are not deterministic core outputs; persist the originally issued bytes.

An owner-controlled persistent private key is provisioned outside source trees,
bundles and scan workers; no generated-at-import key or embedded test key.
Private files require bounded no-follow reads, private parent directories,
checked ownership/mode and a trusted nonconcurrent-writer boundary. These checks
do not defend against a hostile host owner. Key creation/installation is an
explicit operation, never an implicit resolver fallback. Readers need public
verification material only and must survive a restart without changing identity.

### 6.2 Closed scalar types, policy and signing grants

All fields listed below are required, all objects are closed, and null is legal
only where stated. `UUID` means canonical lowercase hyphenated UUID, not an
arbitrary label. `Digest` is 64 lowercase hex. `Token` is 1..128 ASCII bytes
matching `[A-Za-z0-9][A-Za-z0-9._:-]*`; it is inert text, never a path or callback.
`Version` is three canonical decimal components, each 0..2147483647, joined by
dots, with no leading zeros except zero itself. `Count` is a nonnegative int64;
revisions/key versions start at 1. None of these integer types accepts bool.
`UtcSecond` is an actual UTC calendar instant formatted
`YYYY-MM-DDTHH:MM:SSZ`; observed SQL/lease instants use `UtcInstant`, exactly
`YYYY-MM-DDTHH:MM:SS.ffffffZ`. Preserve microseconds; never round a lease down
to the signed-policy timestamp format. Scope/org uses §4's exact tagged pair.

`scanipy-accepted-trust-policy/1` fields:

```text
schema, event_id: UUID, registry_id: UUID, scope, org_id,
revision: positive int64, previous_policy_digest: Digest|null,
valid_from: UtcSecond, expires_at: UtcSecond, grants: array<Grant>
```

Revision 1 has null predecessor; every later revision names the exact previous
policy digest and increments by one. Policies are per qualified registry
namespace, not independently advancing copies of one supposed global head.
`valid_from < expires_at`. The independently configured root signs
`ASCII schema + LF + canonical policy bytes`; no grant inside the policy can
authorize that root signature. A policy's event UUID/digest is immutable.

The exact closed `Grant` fields are:

```text
grant_id: UUID, key_id: Token, key_version: positive int64,
spki_sha256: Digest, signature_profile: "scanipy-registry-rsa-pss-sha256/1",
issuer_actor_id: UUID, capability: "publish-builtin",
scope, org_id, not_before: UtcSecond, not_after: UtcSecond,
status: "active"|"retired"|"revoked", status_changed_at: UtcSecond|null
```

The ordered grants array has unique `grant_id` and `(key_id,key_version)`;
grant scope equals the policy namespace. `not_before < not_after` and the
grant's validity is contained in the policy validity at its original admission.
Active has null `status_changed_at`; retired/revoked require that time.
Once admitted, key/actor/capability/scope/validity fields cannot change under
the same grant ID. Carry historical grants into later policies unchanged
except active→retired/revoked or retired→revoked, with nondecreasing change
time. Revoked cannot become active/retired, and retired cannot become active.
Removing a grant does not turn it into an unknown-but-usable legacy grant:
first-profile policy updates retain prior grants, including tombstones.
New keys use new grant IDs/versions; no ID recycling. The finite grant cap in
§6.5 can exhaust this initial namespace; a reviewed successor protocol is then
required, not deletion of tombstones to make room.

The original signed policy must show the exact active grant at publication.
The current signed policy determines new use: active and retired grants permit
previously published approvals only within grant validity; retired additionally
requires `published_at < status_changed_at`. Revoked/absent/expired grants
forbid new use. Current policy itself must be valid now. Original policy expiry
does not erase historical verification, but cannot substitute for a valid
current policy. Policy revision alone does not change the approved bytes.

This first profile supports only `publish-builtin`. Reject statistical, human
triage, ranking, delegation, wildcard scope, threshold/multisig, X.509/PKI and
root-rotation grant forms; do not ignore unknown grants and partially accept
the rest. A database capability role (§7.2) is not a cryptographic issuer grant.

### 6.3 Exact builtin approval, evidence and publication records

`scanipy-accepted-approval/1` fields are `schema`, `event_id: UUID`,
`publication_key: UUID`, `registry_id: UUID`, `bundle_id: UUID`, `scope`, `org_id`,
`S_version: Version`, `accepted_content_digest: Digest`,
`approval_kind="builtin-operator"`, `issuer_actor_id: UUID`, `grant_id: UUID`,
`key_id: Token`, `key_version: positive int64`, `spki_sha256: Digest`,
`signature_profile`, `trust_policy_digest: Digest`, `issued_at: UtcSecond`,
`evidence_inventory_digest: Digest`, and `proposal_id=null`. The signature
covers **all** canonical fields with the statement's schema+LF domain.
Its issuer/key/scope/capability must match exactly one grant, not merely one
key with a matching textual name. Non-null proposal lineage is unsupported
by this lane, not something the importer clears.

`scanipy-accepted-evidence-inventory/1` has `schema`,
`approval_kind="builtin-operator"`, and `objects`. In this first profile the
array has exactly one object, with the closed fields
`role="operator-adoption"`, `schema="scanipy-operator-adoption/1"`,
`length: Count`, `raw_sha256: Digest`. Retain those exact bytes, not a URI.
The inventory's domain digest is signed by the approval; the object's raw
digest covers the entire canonical adoption object, without reserialization.

`scanipy-operator-adoption/1` has `schema`, `decision_id: UUID`,
`actor_id: UUID`, `action="adopt-builtin"`, `registry_id: UUID`,
`bundle_id: UUID`, `scope`, `org_id`, `accepted_content_digest: Digest`,
`decided_at: UtcSecond`, `reason: string`, and `proposal_id=null`.
Actor/scope/bundle/content equal the enclosing approval; `decided_at <= issued_at`
and they differ by at most 300 seconds. Reason is nonempty, at most 4096 UTF-8
bytes, and never evaluated. This is an issuer-attested administrative event,
not proof of human authorship or an e-process decision. Arbitrary attachments,
review URLs as evidence objects and statistical evidence schemas are rejected
by the initial decoder; they require a separately reviewed schema extension.

The same immutable approval row retains
`scanipy-accepted-publication/1`: `schema`, `approval_event_id: UUID`,
`publication_key: UUID`, `registry_id: UUID`, `bundle_id: UUID`, `scope`, `org_id`,
`approval_statement_digest: Digest`, `approval_signature_sha256: Digest`,
`evidence_inventory_digest: Digest`, `accepted_content_digest: Digest`,
`policy_digest: Digest`, `policy_revision: positive int64`,
`checkpoint_digest: Digest`, `checkpoint_generation: positive int64`,
`admission_epoch: UUID`, `published_at: UtcInstant`,
`publisher_actor_id: UUID`, and `publisher_artifact_digest: Digest`.
All copied identities/digests are equality-checked against the actual retained
objects and locked policy/checkpoint. `publisher_actor_id` equals the approved
issuer. The publication time/producer identity is recorded by the trusted
publisher/DB transaction, not provided as a free caller timestamp. This
receipt is an immutable ledger observation, **not another signature** or an
independent attestation that the named executable was loaded.

At locked publication the original policy is the current admitted policy,
the issuer grant is active, and `issued_at` is within DB time minus 300 seconds
through DB time plus 30 seconds. An old signature cannot use a now-retired key
by backdating. Expired drafts require a new explicit publication key/signature;
exact committed replay returns original bytes and never republicates them.
Authenticating a historical receipt also requires its read from the trusted
immutable ledger; a caller-supplied receipt with correct hashes is insufficient.

### 6.4 Sealed authority frame and result types

At request binding retain `scanipy-sealed-acceptance/1` + LF, u64-BE canonical
manifest length and bytes, then u64-BE length plus raw bytes for every ordered
object, with exact EOF. Manifest fields are `schema`, `registry_id: UUID`,
`request_id: UUID`, `org_id: UUID`, `codebase_id: UUID`, `bundle_id: UUID`,
`accepted_content_digest: Digest`, `approval_event_id: UUID`,
`publication_policy_digest: Digest`, `current_policy_digest: Digest`,
`current_policy_revision: positive int64`, `checkpoint_digest: Digest`,
`checkpoint_generation: positive int64`, `admission_epoch: UUID`,
`resolved_at: UtcInstant`, `verifier_artifact_digest: Digest`, and `objects`.
Here `current_*` means **as observed at this immutable request resolution**,
never a field later overwritten to represent the live head.

Each object is `{role, schema, length: Count, raw_sha256: Digest}`. Exactly
these 15 roles occur once, in this order; null schema is allowed only below:

| Role | Exact schema |
|---|---|
| `approval-statement` | `scanipy-accepted-approval/1` |
| `approval-signature` | null; 384 raw bytes |
| `issuer-spki` | null; §6.1 DER |
| `publication-receipt` | `scanipy-accepted-publication/1` |
| `publication-policy` | `scanipy-accepted-trust-policy/1` |
| `publication-policy-signature` | null; 384 raw bytes |
| `publication-checkpoint` | `scanipy-registry-admission/1` |
| `publication-checkpoint-signature` | null; 384 raw bytes |
| `current-policy` | `scanipy-accepted-trust-policy/1` |
| `current-policy-signature` | null; 384 raw bytes |
| `trust-root-spki` | null; independently pinned §6.1 DER |
| `approval-evidence-inventory` | `scanipy-accepted-evidence-inventory/1` |
| `operator-adoption` | `scanipy-operator-adoption/1` |
| `admission-checkpoint` | `scanipy-registry-admission/1` (§8.1) |
| `admission-checkpoint-signature` | null; 384 raw bytes |

Even identical publication/current policies occupy both declared roles. The
publication checkpoint exactly matches the original publication receipt and
original policy; its signature is independently checked, and its historical
validity interval must contain `published_at`. The request-resolution checkpoint
may be newer and is checked at `resolved_at`, without changing the old receipt.
The issuer key and included root are audit material, not self-selected trust.
The root must match independently installed trust, and the included checkpoint
is compared to the independent live checkpoint for current use. Every role,
schema, length, raw hash, metadata domain digest and cross-object binding is
checked; no missing object is repaired with a generated replacement.

The request binding and eventual occurrence seal retain this original frame
unchanged. A later sealing/launch/renewal policy check appends the separate
records in §7.3, not a new value in this old frame. Known verifier artifact
identity is required, separately from any policy digest. The frame establishes
neither that source was captured nor that a process executed.

The first pure verifier returns separate immutable
`VerifiedHistoricalApproval` and `VerifiedCurrentPolicy` evidence results.
It cannot return an `AuthorizedAttempt` from a self-supplied record, signature
or snapshot. Only the later trusted repository/launcher can create and consume
a committed per-attempt authorization with live fencing (§7.3). Historical
verification can succeed while current use is explicitly denied.
The pure result certifies the named signature/material checks, not that a
caller-supplied publication receipt actually came from durable storage. The
production resolver must authenticate that receipt through the immutable
repository read and recheck its exact digest; this is a separate trust input,
not a new `published=true` argument exposed to scan users.

When the live policy advances, do not require the old frame's `current_policy`
to remain current. Independently load the live policy and checkpoint as
`scanipy-registry-current-authority/1`, using the same length framing with a
closed manifest: `schema`, `registry_id`, `scope`, `org_id`, `policy_digest`,
`policy_revision`, `checkpoint_digest`, `checkpoint_generation`,
`admission_epoch`, `objects`. The typed fields use the definitions above.
Exactly four object roles occur in order: `current-policy`,
`current-policy-signature`, `admission-checkpoint`,
`admission-checkpoint-signature`, with the same schemas as the table.
The complete additional frame is at most 262,144 bytes. Verify it against the
independent current checkpoint and the same pinned root, and re-evaluate the
original approval's grant under this policy. Its immutable policy/admission
events are retained separately from the original request frame.

### 6.5 Verifier resource profile and unsupported schemas

Limits apply before parsing/hashing/crypto, and compose with the store's caps.
These are initial protocol ceilings, not measured latency guarantees:

| Input/work | Ceiling and enforcement |
|---|---|
| Accepted S + detector + rule bytes | 1,048,576 total bytes, including model frames |
| Complete sealed authority frame | 1,048,576 bytes including framing/manifest |
| One trust policy | 131,072 bytes; at most 64 grants |
| Other one authority JSON object | 65,536 bytes; adoption reason at most 4096 bytes |
| Authority JSON | depth 32, at most 20,000 scalar/container values per frame, at most 16,384 UTF-8 bytes per string |
| Public key / signature | at most 4096 DER bytes before ASN.1 parsing / exactly 384 bytes |
| Root keys / issuer keys | exactly one independently pinned root and one selected issuer per verification; no key search or chain building |
| Cryptographic verification | at most 5 for the original frame plus 2 for a separately supplied live-policy/checkpoint pair; no retry across algorithms/keys |
| Work isolation | trusted verifier subprocess: 128 MiB address space, 2 s CPU, 3 s wall, no network and no input-directed imports/subprocesses |
| Process transport | stdin at most 2,621,440 bytes including content/authority/live-pair/trusted-expectation framing; stdout 16,384 bytes, stderr 16,384 bytes, combined 32,768 bytes |
| DB transaction | existing 15 s statement / 2 s lock deadlines; crypto preflight occurs outside locks |

Count/depth/string checks are performed by a bounded preflight over the original
UTF-8 bytes, then duplicate-preserving strict decode and canonical comparison.
Do not first expand JSON or DER and check its size afterward. Exact tuples and
bytes exclude generators/subclasses/mutable aliases; revalidate at the facade.
No compression, YAML, glob discovery, DER chain fetch or URI dereference exists.
An inability to enforce the process limit is an explicit unsupported runtime,
not permission for an unbounded in-process fallback. Diagnostic unit tests may
test pure functions; integration must exercise the bounded production wrapper.
The 3-second wall budget includes reserved terminate/drain/reap cleanup time.
Use the independently reviewed shared bounded-process transport; it does not
choose trust, argv, environment or child rlimits for this profile. OS-spawn
blocking and escaped descendants remain subject to the explicit outer
supervisor/isolation boundary, not an absolute process-local termination claim.
The small closed result reports checks/digests and typed failure only, never
echoes private material or whole accepted blobs. The exact domain request/result
codec below is independent of the shared transport's immutable-bytes API;
neither permits pickle, arbitrary object deserialization, executable callbacks
or a permissive CLI.

Limits in this subsection constrain **new authority metadata**, not arbitrary
tool evidence/source bytes or the existing occurrence envelope. The separately
versioned G1 semantic profile may impose its documented stricter rule/model
limits; this resolver does not invent a tighter accepted-rule count.

Initial dispatch recognizes only the schemas fully defined in §§4 and 6–8.
It rejects `statistical-spec`, unknown authority versions, proposed future
statistical gate/adjudication objects, delegation/certificate chains, legacy
YAML imports, composed bundles and root rollover. G1 selector/model nested
schemas remain owned by `SOURCE-BOUND-SCALAR-IFDS.md` and its reviewed decoder:
until that exact decoder is integrated, first-slice byte/trust verification
is explicitly **not execution-ready**. It cannot validate unknown model forms
by treating their raw-content hash as structural or semantic acceptance.

### 6.6 Exact worker request, proof inputs and result protocol

The worker has three closed modes: `publication-preflight`, `historical`,
`execution`. They are different checks, not three ways to obtain a launch
permit. Publication preflight has no invented request/seal/receipt; historical
verification does not assert current permission. Initial execution mode is the
detector-purpose QualifiedRuleKey API in §5.1; an identity-purpose execution
packet is rejected as unsupported until its explicit consumer extension.
The identity authorization record schema itself remains defined/decodable.

Before publication a new proof frame, `scanipy-publication-input/1`, uses the
same prefix+LF/u64-BE canonical-manifest/object framing. Its manifest is exactly
`schema`, `registry_id`, `bundle_id`, `scope`, `org_id`, `S_version`,
`accepted_content_digest`, `objects`. Object descriptors have the §6.4 shape.
Exactly these ten roles occur in order: `approval-statement`,
`approval-signature`, `issuer-spki`, `current-policy`,
`current-policy-signature`, `trust-root-spki`, `approval-evidence-inventory`,
`operator-adoption`, `admission-checkpoint`, `admission-checkpoint-signature`.
Their schemas/types are those in §6.4. Approval trust_policy_digest equals this
current policy; the exact issuer grant is active. There is no publication
receipt in this frame. A verified preflight cannot be replayed as a committed
publication. Its total cap is the same 1 MiB authority cap.

Closed trusted-expectation models, all using the scalar types above:

- `InstalledTrust`: exactly the installed configuration in §6.1, including
  its schema field. It is populated by the trusted factory, not a bundle.
- `BundleExpectation`: `{registry_id, bundle_id, scope, org_id, S_version,
  accepted_content_digest}`; exact selected namespace/content, not `latest`.
- `AdmissionExpectation`: `{checkpoint_digest, checkpoint_generation,
  admission_epoch, policy_digest, policy_revision}`; digests, positive int64
  generations and UUID epoch from the independently installed checkpoint.
- `LedgerExpectation`: `{publication_receipt_digest, request_binding_digest,
  execution_authorization_digest, binding, policy_event_id, admission_event_id}`.
  The first two digests are non-null. Historical mode requires the other four
  fields null. Execution requires all non-null, with `binding: ExecutionBinding`
  and UUID event IDs. Digests are of the exact authentic repository reads;
  request_binding_digest is the full original frame's raw SHA, not its JSON.

The canonical request header has exactly these keys:

```text
schema: "scanipy-accepted-verifier-request/1"
operation_id: UUID
mode: "publication-preflight"|"historical"|"execution"
installed_trust: InstalledTrust
expected_bundle: BundleExpectation
reference_time: UtcInstant
verifier_artifact_digest: Digest
admission: AdmissionExpectation|null
ledger: LedgerExpectation|null
selected_rule: QualifiedRuleKey|null
lengths: {
  spec: Count, detectors: Count[], rules: Count[],
  authority: Count, live_authority: Count, execution_authorization: Count
}
```

Publication-preflight requires admission, null ledger/selected_rule, its
publication-input authority frame, and zero live/authorization lengths.
Historical requires ledger with the null fields above, null admission/selected
rule, the original sealed-acceptance frame, and zero live/authorization lengths.
Execution requires non-null admission/ledger/selected_rule, original sealed
frame, separate live-current-authority frame and canonical execution-
authorization record. This record is at most 65,536 bytes and its domain digest
must match both the ledger and ExecutionBinding. Initial/renewal purpose,
target/run, token, revisions, both leases and every policy/event link must
match the independently read expectations. A pure packet cannot invent the
authenticity of those trusted reads.

Wire bytes are exactly:

```text
ASCII "scanipy-accepted-verifier-request/1" + LF
u64-BE header_length + canonical header bytes       # at most 65,536 bytes
u64-BE spec_length + original spec bytes
for each detector length in header order: u64-BE length + original bytes
for each rule length in header order: u64-BE length + original bytes
u64-BE authority_length + original authority frame
u64-BE live_authority_length + live frame bytes     # zero frame if absent
u64-BE execution_authorization_length + record bytes # zero frame if absent
EOF
```

Each repeated length must equal its header value. Sum before allocation, check
remaining input and exact EOF, then match array counts/order to the actual S
manifest. Content totals remain <=1 MiB, authority <=1 MiB, live frame <=256 KiB,
authorization <=64 KiB; the whole packet, including header/framing, is also
<=2,621,440 bytes. A packet satisfying individual caps can still exceed the
whole cap and must reject without truncation. Stdout never echoes these blobs.

Trust expectations are serialized to a private child only **after** the parent
obtains them from its configured installation and real repository/admission
reader. They cannot be taken from a scan body, accepted artifact, environment
variable or a caller-provided worker packet. A person running the worker with
a self-chosen root can only verify material relative to that supplied root;
the result does not establish this installation's trust or grant DB/native
access. The privileged parent, not a JSON field, establishes that boundary.

The result is one canonical UTF-8 JSON object with exact EOF (no LF suffix),
at most 16,384 bytes, schema `scanipy-accepted-verifier-result/1`:

```text
schema, operation_id: UUID|null, request_sha256: Digest|null,
mode: "publication-preflight"|"historical"|"execution"|null,
status: "verified"|"rejected", failure_code: FailureCode|null,
checks: VerificationChecks|null
```

For verified, failure_code is null, operation/mode match the request and checks
is non-null. For rejected, checks is null and FailureCode is exactly one of
`invalid-input`, `unsupported-schema`, `content-mismatch`, `untrusted-root`,
`signature-invalid`, `grant-denied`, `policy-stale`, `policy-expired`,
`checkpoint-denied`, `scope-mismatch`, `ledger-mismatch`, `fence-stale`,
`runtime-unsupported`, `internal-error`. Operation/mode may be null only when
the header could not be strictly parsed. request_sha256 hashes the exact complete
bytes actually received; it is null only in a rejected result where a complete
bounded input could not be retained/read. Never label a prefix hash as the whole
request hash. Verified requires a non-null exact match with the parent's full
packet hash; input transport failure/truncation cannot yield verification.
No exception text, path, content excerpt,
traceback or arbitrary object is part of this result schema.

`VerificationChecks` is exactly `{accepted_content_digest, approval_event_id,
approval_statement_digest, publication_receipt_digest, qualified_rule_digest,
execution_authorization_digest, current_policy_digest, current_policy_revision,
checkpoint_digest, checkpoint_generation, admission_epoch, verified_at,
permission_expires_at}`. Identity/digest/time types are those above.
The first three fields and verified_at are always non-null. Publication-
preflight has null receipt/qualified-rule/execution/permission fields and
non-null current-policy/checkpoint fields. Historical has a receipt digest but
all qualified-rule/execution/current-policy/checkpoint/permission fields null.
Execution has all fields non-null; its permission deadline is the §7.3 minimum,
not a newly extended lease. verified_at is the checked trusted reference time.
QualifiedRuleKey digest uses its own schema+LF canonical metadata domain.

Exit code 0 accompanies a verified result, 2 a deliberate rejected result.
Any other exit, result/exit disagreement, extra stdout, unknown key/schema,
unexpected stderr on a successful result, digest/operation mismatch, short
stdin, incomplete cleanup or missing EOF is failure, never accepted prefix.
Structured rejection is still failure to authorize. Unexpected worker errors
may produce only bounded stderr/partial outcome; absence of a result cannot
be replaced by an invented empty-success result. Parent preservation of raw
bounded transport outcomes is separate from the closed, nonsecret result.

### 6.7 Closed configured runtime and shared transport invocation

`VerifierRuntimeProfile` is immutable installed server configuration, not part
of a worker packet or a detector. Its exact Python fields are
`profile_path: PosixPath`, `profile_sha256: Digest`,
`document: VerifierRuntimeDocument`. The document is the frozen typed model
of the closed file below (path arrays become exact tuples, not mutable lists).
No request or ledger field supplies/replaces any of these values.
The private canonical profile file has schema
`scanipy-accepted-verifier-runtime/1`, at most 65,536 bytes, and exactly:

```text
schema, implementation: "cpython", python_version: Version,
python_executable: AbsolutePath, python_executable_sha256: Digest,
worker_script: AbsolutePath, worker_script_sha256: Digest,
application_root: AbsolutePath, application_artifact_digest: Digest,
stdlib_roots: AbsolutePath[], dependency_roots: AbsolutePath[],
dependency_artifact_digest: Digest, verifier_artifact_digest: Digest,
work_root: AbsolutePath, resource_profile: "scanipy-verifier-limits/1"
```

Version here records the exact actual CPython 3.11.x runtime; other minors or
implementations are initially unsupported by the production worker profile,
not inferred compatible from project Python>=3.11. AbsolutePath is a normalized
absolute POSIX path, <=4096 UTF-8 bytes, no NUL/control/dot/dot-dot component.
Root arrays are ordered, unique, 1..4 entries, and mutually distinct from the
application root. A configured stdlib root is an actual directory; no zip/PTH
search, empty-path insertion or source-tree fallback. Profile path plus expected
raw profile digest are held by the parent factory outside request data.

The parent resolves/validates the configured executable/script/import roots
against its trusted read-only deployment, checks actual executable/script raw
hashes and retained application/dependency artifact bindings, and refuses an
unknown binding. These are measured deployment artifact identities, not policy
hashes or independent loader attestation. Import roots must be trusted code,
never a source capture, user checkout or temporary dependency install. Current
target code is data only. The first test slice uses explicitly task-owned
trusted code/test runtimes, not production key or deployment installation.
The request's verifier_artifact_digest equals this current installed profile's
binding. Archived publication/resolution artifact digests remain their original
observations; do not require every historical producer to have the same hash
as today's verifier, or rewrite those fields during a software upgrade.

Root-owned #400 supplies the actual shared runtime-artifact measurement and
enforced outer-controller dependency. Merely comparing configured aggregate
hash fields is not measurement. Component digest formulas must be independent
of the profile/inventory digest to avoid circular identity; the installed
inventory can then bind the profile and those actual component digests.
Until that real dependency is integrated, public operational
`run_isolated_verifier` fails closed with runtime-unsupported. It never calls
a diagnostic fallback or accepts a constructed measurement/controller result.
The explicitly approved private `_run_diagnostic_verifier` exercises the fixed
subprocess only in controlled task-owned tests. Its actual executable/script/
profile hashes, argv/env/import/rlimit observations are real; its synthetic
aggregate artifact bindings and test keys are fixture-relative assertions,
not measured deployment closure, installed trust, no-egress proof or permits.
There is no public/CLI switch enabling this diagnostic path operationally.
The test fixture copies only the explicit current executable, stdlib, four
named dependency packages plus the exact cffi extension candidate, and the
three owned application trees into fresh private directories. Before copying,
no-follow preflight enforces shared ceilings of 10,000 files, 20,000 entries,
depth 64, 4,096-byte paths, 32 MiB per file, 128 MiB aggregate and a 30-second
cooperative copy deadline. Reads/writes use 64 KiB chunks and unchanged-file
checks. No recursive symlink traversal, library search or shared/user chmod is
allowed. The stdlib copy also omits only its direct `site-packages` and
`dist-packages` containers, since the four required dependency packages are
copied separately; it must not duplicate the host's complete development
installation. These closed omissions create a fresh diagnostic distribution,
not a complete installed-runtime inventory or production packaging proof.

The exact argv tuple is:

```text
(resolved_python_executable, "-I", "-S", "-B", "-X", "utf8",
 "-X", "pycache_prefix=" + private_empty_cache_path,
 resolved_worker_script, "--profile", resolved_profile_file,
 "--profile-sha256", expected_profile_raw_sha256)
```

The worker rejects any other argument count/flag/value grammar. All paths and
the expected digest come from the installed parent profile, never input JSON,
source, PATH lookup or an arbitrary `--python`/command option. The exact child
environment is `{"LANG":"C.UTF-8","LC_ALL":"C.UTF-8","TZ":"UTC"}`;
no caller/ambient merge, HOME, PATH, PYTHONPATH, PYTHONHOME, PYTHONSTARTUP,
LD_PRELOAD, loader options, certificate/proxy variables or JVM controls.
Unknown requested environment keys fail at this adapter, not silently pass
through the generic process transport.
Model boundaries validate UUID integer storage and take a bounded exact-string
snapshot of CPython 3.11 `_parts` / 3.12 `_raw_paths` path storage before
formatting; unknown layouts fail closed. Cached `_str` and caller iterators are
not trusted. Runtime profile records retain fresh paths, reject backslashes
and C0/C1 controls, and revalidate at use. Supporting model decoding on 3.12
does not expand this initial worker's explicitly pinned CPython 3.11 runtime.
The request operation UUID follows the same primitive snapshot rule before
header formatting or any diagnostic filesystem/process preflight; an exact
UUID class alone is not sufficient if its integer storage was altered.

`-I -S` disables user/site bootstrap and environment-based Python settings.
`-B` prevents bytecode writes, **not loading existing bytecode**. The parent
therefore creates a fresh private empty 0700 `pycache` child of the fresh
private invocation directory and supplies its absolute path in the exact
`-X pycache_prefix=...` argument above. This directory is disjoint from source,
import and profile roots, never a caller/ambient cache. The worker derives
the expected path as its validated invocation cwd / `pycache` and checks actual
`sys.pycache_prefix` equals that exact trusted path
and rejects a nonempty, symlinked, wrong-owner or wrong-mode directory before
application/dependency imports. There is no fallback to adjacent __pycache__,
an ambient prefix or a previous job's cache. Pinned stdlib/runtime extensions
remain part of the trusted artifact closure, not source-selected imports.
Before reading untrusted stdin, the trusted worker sets and
checks Linux rlimits: RLIMIT_AS soft/hard 134,217,728 bytes; RLIMIT_CPU 2/2
seconds; RLIMIT_NOFILE 32/32; RLIMIT_FSIZE 0/0; RLIMIT_CORE 0/0. Unsupported or
failed enforcement yields runtime-unsupported, never an in-process retry.
Read the bounded no-follow profile, check its exact expected hash/runtime,
and set sys.path only to its exact stdlib roots, application root and dependency
roots, in that order. Import the reviewed verifier and cryptography only from
those trusted roots; do not call site.main, process `.pth`, import user modules,
load extensions chosen by input, or discover plugins. Standard-library/binary
extensions needed by that pinned runtime remain trusted deployment code.

Each invocation uses a fresh private 0700 child directory under work_root;
cwd is not an import source because isolated mode has no implicit cwd entry.
Check no-follow ownership/modes and disjointness from source/import roots.
File helpers retain each acquired descriptor before releasing its parent and
remove a descriptor from ownership before attempting its one close. A failed
close may already have released/reused that numeric ID: never retry it.
Read/validation/interruption errors remain primary, with earlier causes and
later cleanup failures retained; final-close-only failure refuses success.
The trusted nonconcurrent host/deployment-writer boundary remains explicit;
path/mode checks are not protection against a privileged concurrent host actor.
The worker has no input-directed filesystem/network/subprocess operation.
This profile does not falsely claim that the generic transport creates a
network namespace or prevents every syscall. Production adversarial use
requires the shared contract's independently enforced resource-limited/no-egress
outer supervisor and descendant isolation; without it, hermetic child tests
prove the local mechanism only and cannot authorize an operational verifier
deployment. No caller boolean can stand in for that controller.

Use the shared API, owned by the bounded-transport workstream, without copying
its implementation:

```text
tools.worker.bounded_process.run_bounded_process(
    exact_argv, stdin=immutable_request_bytes, env=exact_child_dict,
    cwd=private_child_path,
    limits=ProcessLimits(
        stdin_bytes=2621440, stdout_bytes=16384, stderr_bytes=16384,
        combined_output_bytes=32768, wall_ms=3000, cleanup_reserve_ms=500,
    ),
    spool_dir=None,
)
```

Only memory-output mode is used. Check actual FrozenInvocation, full stdin
delivery, `reason="exited"`, expected return code, complete EOF/untruncated
MemoryOutput, and `cleanup="completed"` before domain-result admission.
ProcessTransportError carries its actual partial outcome/original cause;
preserve it, do not replace it with a synthetic process result. Cleaning the
temporary private workspace must also not erase an existing process exception
or interruption: preserve the original exception and explicitly chain any
cleanup failure alongside its earlier cause. A cleanup-only failure after a
completed child retains that actual outcome and cannot return verification
success. Reaping the leader/signalling its group does not prove escaped
descendants are dead, and
OS-spawn/uninterruptible-kernel stalls still require the outer supervisor.
Zero process exit is transport success only; the parent still validates the
entire result and rechecks current authority before exposing a checked view.
The shared API remains an integration dependency pending its final reviewed
implementation. Missing transport is explicitly unsupported, not permission
to use subprocess.run or a permissive in-process production fallback.
`ProcessValidationError` is a prelaunch rejection with no fabricated invocation
outcome. Shared records/limits/errors are imported from their owning module,
not cloned into accepted_inputs.models. The domain translates failures to
bounded typed verification failure while retaining real available evidence.

## 7. Proposed durable boundary and executable operations

Keep legacy tables, grants and signed rows unchanged. Proposed new namespace:
`scanipy_accepted_inputs`, with five logical tables:

| Table | Purpose and hard checks |
|---|---|
| `registry_namespaces` | Immutable registry/scope/org identity plus explicitly guarded mutable coordination fields in §7.1. |
| `artifact_versions` | Exact scoped kind/ID/version, schema, raw bytes/length/SHA256; immutable unique version key. |
| `bundle_versions` | Exact scoped S-version/UUID, framed S bytes, accepted-content bytes/digest, ordered artifact IDs; immutable. |
| `authority_events` | Append-only typed policy, admission, approval/publication, seal-authorization, execution-authorization and denial records; exact bytes and referenced signed evidence. Revocation is a new policy, never an edit to an old approval. |
| `request_bundle_bindings` | Composite occurrence request link and exact bundle/approval/initial policy/checkpoint; original resolution bytes/digest. Entire row is immutable, including policy generation. |

Ordered artifact-ID arrays are not claimed to have SQL array-element FKs.
The only publication functions must resolve and verify every referenced row's
scope/kind/ID/version/hash under the namespace lock before inserting a bundle.
Unconditional history guards and no artifact/bundle deletion preserve those
references thereafter. If implementation chooses a normalized membership table
for native FKs instead, document it before coding; do not omit integrity checks.

### 7.1 Immutable history versus namespace coordination

`artifact_versions`, `bundle_versions`, `authority_events` and
`request_bundle_bindings` are fully immutable: ordinary owner-level
UPDATE/DELETE/TRUNCATE all fail. Trigger handling of zero mutable arguments
must be explicit, not nullable `TG_ARGV` arithmetic. INSERT is function-only.
Rows retain canonical/raw bytes, schema, lengths, hashes and exact typed links;
SQL revalidates them independently of Python constructors.

`registry_namespaces` is **not** fully immutable. Its identity columns
`id`, `registry_id`, `scope`, `org_id`, `created_at` never change. Its only
mutable columns are `policy_event_id`, `policy_digest`, `policy_revision`,
`admission_event_id`, `checkpoint_digest`, `checkpoint_generation`,
`admission_epoch`, `coordination_revision`, and `updated_at`.
Initially no policy/admission is installed: their links/digests/epoch are null,
policy/checkpoint generations are zero, and no execution is permitted.

Only dedicated policy/admission functions can advance these fields. Each
successful changed operation increments coordination revision exactly once;
an exact read-only replay does not. Policy revision advances exactly one and
matches a same-namespace, predecessor-linked signed policy event. Admission
generation strictly increases and matches a retained same-namespace checkpoint;
its epoch/policy must match the independently installed record under §8.1.
Changed admission may temporarily mismatch the policy head, which blocks use.
No other update, deletion or truncation is legal. Ordinary owner DML still
passes these transition guards; hostile superusers able to replace functions
or disable triggers are outside this database capability boundary.

Authority events have a closed common SQL envelope: `id: UUID`,
`registry_id`, `scope`, `org_id`, `kind`, `record_schema`, `record_bytes`,
`record_digest`, `recorded_at: UtcInstant`; kinds are exactly `policy`,
`admission`, `approval`, `seal-authorization`, `execution-authorization`,
`execution-denial`. The record is the corresponding closed schema in §§6–8,
not arbitrary JSON. Approval rows additionally retain the original signature,
issuer DER, evidence inventory/adoption and publication-receipt bytes/digests;
policy/admission rows retain their root signature. Other kinds are explicitly
trusted-ledger records, not signed approvals. Typed columns/FKs carry the
record's bundle/request/attempt/run/policy links where applicable; they must
equal the bytes. Do not leave scope integrity solely inside a JSON field.
Unique operation/event keys reject changed replay. Initial execution history
is addressed through these events, not a sixth mutable "latest permission"
record that could silently replace prior authority.

### 7.2 Closed database capabilities and trusted components

Proposed NEW roles are NOLOGIN, NOINHERIT, NOSUPERUSER, NOCREATEDB, NOCREATEROLE,
NOREPLICATION, NOBYPASSRLS; existing role names are refused, never adopted:

| Role | Sole new capability |
|---|---|
| `scanipy_accepted_owner` | Own new objects; no runtime login or membership grant |
| `scanipy_accepted_policy_admin` | Execute `install_policy_v1`, `record_admission_v1` only |
| `scanipy_accepted_publisher` | `publish_builtin_bundle_v1`, `read_publication_receipt_v1` |
| `scanipy_accepted_resolver` | `read_exact_bundle_v1`, `read_authority_event_v1`, `read_request_binding_v1`, `create_bound_request_v1`, `seal_bound_capture_v1`, `authorize_detector_run_v1`, `claim_authorized_identity_v1`, `renew_authorized_execution_v1` |
| `scanipy_accepted_reader` | `read_exact_bundle_v1`, `read_authority_event_v1`, `read_request_binding_v1`, `read_publication_receipt_v1`; scoped audit only |

All runtime access is through explicitly listed SECURITY DEFINER functions
with fixed search paths; no generic function-name dispatcher exposed to SQL
callers. Normalize ACLs for all NEW schemas/tables/sequences/functions,
including inherited/default grants. No PUBLIC execution, table DML, REFERENCES,
DDL or owner membership; private helpers have no runtime EXECUTE grants.
Scoped RLS and validated authenticated org binding remain required; a GUC is
not authentication. Explicit application login-to-capability assignment is
deployment administration, not a default grant to app/triage/scan principals.

SQL checks canonical bytes, scopes, identities, ordered inventories, raw hashes,
history transitions and live occurrence fences. **SQL does not verify RSA or
read the independently installed checkpoint.** The dedicated publisher and
resolver are trusted services for those checks, using configured trust rather
than caller-supplied verifier objects. Compromise of these privileged service
identities is outside scanner-user isolation; it is not hidden by a signature
field. A future combined-function owner gets only the named occurrence-function
EXECUTE capabilities it needs, never occurrence-owner membership or table DML;
that cross-namespace grant list requires integration review before slice D.
Legacy grants stay unchanged; low-level occurrence writes alone still confer
no accepted-input authorization.

### 7.3 Append-only seal and per-execution authorization

Initial binding is immutable. New policy does not replace its approval, raw
content, initial frame, generation or planned runtime policy. Current-policy
use is recorded in **new `authority_events` rows**, within the same transaction
as the corresponding seal/claim/begin/renew/terminal operation.

The common exact fields of the following three record schemas are:

```text
schema, event_id: UUID, operation_key: UUID,
registry_id: UUID, scope, org_id, codebase_id: UUID, request_id: UUID,
request_binding_digest: Digest, bundle_id: UUID, approval_event_id: UUID,
accepted_content_digest: Digest, requested_policy_digest: Digest,
policy_event_id: UUID, policy_digest: Digest, policy_revision: positive int64,
admission_event_id: UUID, checkpoint_digest: Digest,
checkpoint_generation: positive int64, admission_epoch: UUID,
work_item_id: UUID, work_attempt_id: UUID,
work_kind: "capture_detection"|"identity", fencing_token: positive int64,
work_revision: Count, attempt_policy_digest: Digest,
capture_id: UUID, seal_id: UUID, capture_lease_id: UUID,
authorized_at: UtcInstant, lease_expires_at: UtcInstant,
capture_lease_expires_at: UtcInstant,
resolver_artifact_digest: Digest
```

These are observed/derived by the trusted adapter from locked rows and exact
verified evidence, not accepted from a caller as authorization claims. They
match same-org/codebase/request composite FKs. Requested/runtime policy digest
remains distinct from the acceptance-use policy and actual artifact identity.

1. `scanipy-capture-seal-authorization/1`: the common fields only.
   Kind is capture_detection; capture/seal IDs are those created atomically
   by the sealing call. Exactly one record per seal. `authorized_at` observes
   the live claim/lease and current authority at commit. The occurrence seal
   still stores the original binding frame, not a rewritten current-policy
   frame. Failed authorization leaves neither seal nor successful receipt.
2. `scanipy-execution-authorization/1`: common fields plus
   `purpose="detector-run"|"identity-attempt"`, `action="initial"|"renew"`,
   `detector_run_id: UUID|null`, `run_input_digest: Digest|null`,
   `occurrence_id: UUID|null`, `previous_authorization_id: UUID|null`.
   Detector purpose requires capture_detection, exact non-null run ID/input
   digest and null occurrence; that run belongs to this exact work attempt,
   capture, seal and immutable detector binding. Identity purpose requires
   identity, a non-null immutable occurrence ID, and null run/input fields;
   the occurrence's capture/seal/bundle must match. Initial has null predecessor;
   renew references the last authorization for the **same target and attempt**.
   A new retry/attempt has a new initial record, not a renewal of an old grant.
3. `scanipy-execution-denial/1`: common fields plus
   `purpose="detector-run"|"identity-attempt"`, `detector_run_id: UUID|null`,
   `run_input_digest: Digest|null`, `occurrence_id: UUID|null`,
   `previous_authorization_id: UUID|null`, and `reason` from `grant-revoked`,
   `grant-expired`, `policy-expired`, `unsupported-authority`,
   `missing-runtime-pin`, `scope-conflict`; no `action` field. Target nullability
   and scope rules are the same as authorization. Common time is
   named `observed_at` instead of `authorized_at`, and `lease_expires_at`
   records the observed lease, **not permission**. It is append-only failed
   work evidence and must never be consumable as an execution authorization.

The denial shape applies only when a valid request/bundle, cryptographically
valid current admitted policy and an exact target/fence can be identified;
the grant/policy may be expired or deny use. Missing binding, corrupt
trust, unavailable checkpoint or a stale/foreign fence cannot fabricate these
fields. Those cases retain bounded existing occurrence attempt/run failure
evidence, with an explicit error and no authorization row. Expired/lost fences
use the existing trusted recovery/failure path, never a forged fresh lease.
No native launch occurs while failure persistence is retried.

The capture-lease ID belongs to this same work attempt/token and capture;
both expiry fields are read exactly from their locked rows. Required leases
must be live at positive authorization. The effective permission deadline is
the earliest work-lease, capture-lease, grant, current-policy and checkpoint
expiry; a 900-second work lease cannot extend a grant expiring in 5 seconds.
Claim/seal already create the corresponding lease in the existing store;
never synthesize a lease ID or unobserved expiry.

`work_revision` is the locked revision **at issuance**. It must equal the
claim's current revision when the launch permit is consumed. Later legitimate
store operations can advance the revision without rewriting the record;
terminal ingestion validates its own current revision plus the unchanged
attempt/token and relevant authorization chain. Never keep using an old
revision as if issuance made the row permanently current.

For a detector, claim/capture/seal alone does not authorize detector execution.
After sealing, `begin_detector_run_v1` allocates/returns the actual run ID;
append its authorization in the same transaction, before any native launch.
For identity, claim the exact occurrence work item and append authorization in
the same transaction. A pre-existing completed run is historical replay only:
it does not produce a new launch authorization. A terminal failed run requires
the occurrence store's explicit retry/supersession rules, not reuse of its ID.

Renewal performs the occurrence work/capture-lease renewal and inserts a new
authorization together. Read the actual post-renewal work revision/lease; keep
the same token for the same attempt, since the existing protocol changes tokens
on claims, not every renewal. New attempts get their actual new token. The
current policy/checkpoint may differ from the initial or previous record; each
new record references its own exact immutable policy/admission events.
Allow one active detector launch per capture/detection attempt in this first
adapter; renewal cannot silently cover other detector-run IDs. Identity work
remains independent per occurrence. Lease seconds remain the sealed retry
policy value (at most 900), never extended by an authority statement.

The launcher checks committed record kind/target, live attempt/token/revision,
unexpired work and required capture lease, current external admission epoch
and checkpoint before handing work to the child. A renewal is permission for
that existing run to continue, not another launch. An exact historical replay
only returns the original receipt. Lost/ambiguous launch acknowledgement cannot
prove that a child did not start: stop/reconcile that attempt and allocate an
explicit new permitted attempt/run, rather than launch the same record twice.
This is a trusted-launcher boundary, not exactly-once process execution proved
by a database row. No public bearer-token launch endpoint is introduced.

Revocation/denial never overwrites old records or erases prior raw detections.
Denial with a live target is committed with explicit failed run/attempt status,
not silently left pending. A policy check followed by a failed SQL commit is
not authorization. Consumer proofs must use the actual chain and authoritative
live rows, not a cached boolean or whichever policy was stored in the request.

### 7.4 Proposed operations

Proposed operations, with no public caller-authored acceptance flag:

1. `publish_builtin_bundle`: explicit authenticated operator command reads a
   bounded private artifact inventory once, validates exact supported schemas,
   obtains a scoped approval signature, and atomically publishes content plus
   receipt. No filesystem discovery by glob, target code, subprocess, imports,
   network fetch or callbacks from the bundle.
2. `publish_statistical_bundle`: unavailable until §9's trusted adapter exists;
   never aliases the builtin operation.
3. `resolve_exact_bundle`: accepts qualified UUID/digest and authenticated
   request scope; reads actual durable rows and configured public trust,
   verifies bytes/signatures/policy, and returns immutable bounded content plus
   original authority evidence. It does not accept a caller-built approval
   object as a substitute for this read/verification path.
4. `create_bound_request`: derives the ordered detector/rule bindings from that
   resolved content, combines separately selected exact runtime artifact pins,
   calls occurrence `create_request_v1`, and inserts the immutable request
   binding in **one transaction**. Bind the existing requested policy digest to
   those exact ordered contents; do not overload it with a code/artifact hash.
5. `seal_bound_capture`: independently checks the request binding and current
   authority, then calls `register_capture_and_seal_v1` with the same accepted
   raw blobs/original evidence and separately verified source-capture result;
   append the exact seal-authorization record in that transaction.
6. `authorize_detector_run`, `claim_authorized_identity`,
   `renew_authorized_execution`: perform the exact atomic target/lease/event
   protocol above. SQL function names add `_v1`; no generic policy boolean is
   accepted. Missing binding/current authority is an explicit failed attempt,
   never a native launch or endless pending status.

The initial production factory wires the real SQL reader and trusted verifier;
test doubles are explicit test configuration only. Python model immutability is
not a security boundary: revalidate evidence at each execution/seal seam.
Existing low-level occurrence functions remain the tested storage primitive;
an unbound row they can store is **not** accepted-input authorization. New
dispatchers must reject it. Scan/triage credentials cannot publish approvals or
create trusted registry bindings. No new externally exposed grant/endpoint is
implied by defining an internal facade.

Runtime pins remain independently named expected tool/code/image digests. The
resolver reads actual publication content; it does not assert that a matching
hash proves a future process loaded those artifacts. Unknown pins fail before
native launch and produce explicit failed work under the occurrence contract.

## 8. Admission, restore trust, transactions and rotation

### 8.1 Independent checkpoint and explicit restore admission

A root-valid policy found in the database is not evidence that it is the
**current** policy. Monotonic SQL guards alone do not resist restoring an older
valid database. The proposed first operational profile therefore requires an
independently held, owner-installed signed admission checkpoint, outside the
database and its backup/restore domain. It is mandatory, not an optional cache
or a value discovered from the database being checked.

Closed checkpoint `scanipy-registry-admission/1`:

```text
schema, event_id: UUID, deployment_id: UUID,
registry_id: UUID, scope, org_id,
generation: positive int64, previous_checkpoint_digest: Digest|null,
admission_epoch: UUID, action: "admit"|"block",
policy_revision: positive int64, policy_digest: Digest,
issued_at: UtcSecond, expires_at: UtcSecond,
administrator_actor_id: UUID, reason: string
```

Reason is nonempty and at most 4096 UTF-8 bytes. Generation 1 has null
predecessor; later installations name the exact independently retained prior
checkpoint digest and increment by one. Expiry is after issuance and at most
7 days later. The pinned root signs schema+LF+canonical bytes. Its independent
installation binds the configured deployment/registry namespace and allowed
administrator actor; a root signature obtained from DB content cannot install
it. Administrator identity and initial root are an actual owner choice.

The trusted admission provider retains the last installed generation/digest
and epoch in protected state **not rolled back with database backups**. It
performs bounded no-follow reads and atomic durable replacement under its own
serialization lock, refusing lower/equal-changed generations. Installation
requires an explicitly privileged operator/administrative service, not scan,
publisher, resolver or DB credentials. It cannot self-bootstrap by picking the
largest signed checkpoint found in restored data. Normal services receive
read-only checkpoint access and re-read it at publication, binding, sealing,
authorization, renewal and launch; no indefinitely cached positive decision.

For new use, the external checkpoint must be valid now, `action=admit`, and
match the namespace's exact policy revision/digest, recorded checkpoint
generation/digest and admission epoch. The old request frame is historical;
its old checkpoint does not have to be the live one. A root-valid lower
policy, missing checkpoint, mismatched same-generation digest, wrong deployment
or stale epoch fails closed, even if all archived signatures verify.

Ordinary policy advance is deliberately fail-closed across the DB/filesystem
boundary; these are not falsely claimed to share an atomic commit:

1. Preverify the next root-signed policy and prepare its checkpoint. Under the
   namespace lock, commit the new policy event/head. It now mismatches the old
   external checkpoint, blocking new work until admission catches up.
2. The privileged admission service independently confirms that exact committed
   head and durably installs the next signed external checkpoint, preserving
   the epoch for normal rotation. It then records that same admission event and
   namespace coordination copy. Until both match, normal work remains blocked.
3. Crash/ambiguous commit is reconciled by exact policy/checkpoint keys and the
   privileged operator, never by reverting to a lower policy or trusting a
   database-supplied checkpoint. Policy revocation cannot be "recovered" by
   restoring its predecessor. A prepared but uncommitted signature is not a
   real-time policy publication announcement.

Restore admission is a separate explicit operational procedure:

1. **Before a restore is attached to a live service**, the trusted administrator
   installs an external `block` checkpoint with a new admission epoch and
   stops/fences existing launchers. Restoring the database cannot restore this
   separately held block or resurrect the previous epoch.
2. Restore into a quarantined database endpoint. Compare its head to the
   independently retained minimum/current policy checkpoint and restore the
   missing immutable policy history from trusted recovery material if needed.
   Never select an older valid head just because it is all the backup has.
   Missing trusted recovery material means blocked operation, not downgrade.
3. Inventory and terminally interrupt/reconcile all nonterminal restored work
   and capture leases using reviewed recovery operations; preserve every old
   event and raw result. No prior-epoch authorization is reused. DB-only fencing
   does not stop a still-running child, so launchers/source users must be stopped
   or isolated before any renewed access. This procedure does not infer lost
   source-object custody or SCM verification from restored rows.
4. Only after that reconciliation does the administrator install a new signed
   `admit` checkpoint for the exact recovered current policy/new epoch and
   record it in the namespace. Services may then create **new** attempts under
   current authority. Old receipts remain historical, not launch permits.

An administrator able to roll back both independent admission storage and the
database, replace trusted code, falsify clocks, or silently swap a live DB
outside this restore procedure is outside this trust boundary. Detecting every
such host/admin action would require external hardware/consensus attestation,
which is neither available nor claimed. Within the declared boundary, the
database cannot autonomously re-admit itself after a restore. The operational
launcher/admission implementation and restore falsifiers are required before
production use; a pure signature verifier alone does not implement this.

The trusted DB UTC clock and launcher/admission host clocks must agree within
30 seconds; a detected backward jump or excessive skew blocks new authority
until administrator reconciliation. Compare policy/checkpoint/issuance dates
to those trusted clocks, not a caller time. Map an issued lease to a bounded
monotonic launcher deadline so a wall-clock adjustment cannot extend a running
child's permission. Signed dates prove what the issuer signed, not actual
publication time, accurate clocks or instantaneous revocation.

### 8.2 Atomicity, retries and current-policy changes

- Lock order: registry namespace/policy head, then occurrence request, capture,
  work and attempt in their documented order. Every combined adapter uses this
  order; no helper may acquire the namespace after holding an occurrence lock.
  Validate bounded crypto input before locks, then compare the policy/content
  generation again under lock. Never hold a transaction across operator input,
  remote signing or native analysis.
- Publication is all-or-nothing. Precompute a bounded candidate statement and
  signature, then recheck issuer scope/current policy and persist bytes, unique
  versions and approval atomically. Failure leaves no usable partial bundle.
  Exact retry reuses original issued signature bytes; do not re-sign and replace
  historical bytes under the same idempotency key.
- Request creation, registry binding and initial work scheduling commit together.
  Sealing rechecks this binding in the same transaction as immutable capture/
  seal insertion and the new seal-authorization event. Initial claim/run and
  renewed lease/authorization are similarly atomic under §7.3. A policy or
  independent checkpoint change between preflight and commit forces
  retry/reverification, not acceptance under stale authority. Because external
  admission cannot be locked by a DB transaction, recheck it after commit and
  immediately before launch; a mismatch makes the committed receipt unusable
  for launch and is reconciled as explicit failed/interrupted work.
- Preserve occurrence statement/lock deadlines of 15 s/2 s, bounded crypto/blob
  work and fresh discarded connections. Ambiguous commit means retry exact keys
  on a fresh transaction, never acknowledge success early or overwrite bytes.
- New policy snapshots are monotonic and append-only, root-authorized and
  serialized through the namespace head. Reject rollback/replayed lower
  generations. Key rotation installs a new explicit key/version; old public
  material remains available for historical verification. Root-key rollover is
  not supported by this first verifier: it needs a separately reviewed trust
  installation/admission procedure, never a new root supplied by a bundle.
- Historical signature validity and current execution permission are separate
  results. Revocation blocks new authorizations under that key/policy; it does
  not mutate an old seal, erase occurrences, invent a fix or turn a verified
  historical signature into different bytes.
- An attempt authorization linearizes at its locked commit. A concurrently
  committed revocation prevents later authorizations. Already-issued attempts
  may be in flight until their bounded lease/cancellation is enforced; this
  contract does not promise instantaneous process termination. Renew/retry must
  recheck current authority and append a new target-specific event. A new
  policy does not retroactively make an already retained raw result disappear.
  Preserve late results as scoped failure/historical evidence without granting
  a new successful execution. Where the frozen low-level store cannot admit
  such a late diagnostic under a lost fence, retain it in the trusted bounded
  failure channel; do not bypass the fence or claim raw-retention integration
  is complete until that explicit adapter is implemented.
- Customer quarantine affects future selection/authorization according to the
  exact recorded scope/policy, not old finding visibility. No automatic
  reactivation or inherited approval across changed bytes/key scopes.

## 9. Real statistical acceptance adapter — required remaining work

The current e-process math may be reused as a computation component after its
validation/enablement requirements pass. It must not supply trusted state from
a request body. The real producer must:

1. Read one immutable candidate byte artifact and its proposal lineage under an
   exact tenant/class/profile key; parse/validate its supported model version.
2. Read an append-only, authenticated adjudication stream with unique event IDs,
   exact candidate binding, label semantics, sequence and prior-state digest.
   Reject duplicates, missing events, changed labels and mismatched candidate
   state/parameters. Triage rankings are not adjudication authority.
3. Bind precision-floor/alpha, evaluation-stream and selection/multiplicity
   policy versions, instrument implementation identity and actual eligibility
   evidence. Do not infer stream validity or statistical claims from a number
   above threshold or from the existence of a mathematical primitive.
4. Compute/replay the decision from that durable evidence. Persist exact
   numerical encoding under a new versioned gate-evidence schema; portable
   envelope strings may encode exact validated decimal/float representations,
   but no unversioned float-to-string rewrite of old evidence is allowed.
5. In one transaction, lock candidate/namespace, allocate the **scope-wide** S
   version, publish exact artifacts and signed statistical approval, and mark
   that candidate accepted with the new immutable bundle ID. Roll back all
   writes on signing, validation, uniqueness or commit failure.
6. Bind the approval to the candidate/content/evidence digests, not just
   `spec_id`, `S_version` and mutable foreign JSONB. The gate issuer has the
   explicit statistical capability and cannot borrow a builtin publisher key.

This path still needs its real storage, authenticated label source, statistical
policy, independent review and tests. Existing synthetic label streams and
optional in-memory ports do not complete it. A bundle may be operationally
accepted yet fail G1 semantic/source capability checks; those failures remain
explicit and do not get relabelled as statistically valid findings.

## 10. Safe legacy handling

- Continue old readers/signature verification unchanged. Return explicit
  `legacy-content-unavailable` / `legacy-authority-unbound` for new execution
  when raw bytes or content-bound authority cannot be recovered independently.
- Never hash a fresh JSONB dump and call it the historical accepted raw digest.
  Never match current registry files to a legacy `S_version` by filename/class.
- A legacy row can be referenced as historical context. Adopting its observed
  contents now requires a **new** explicitly labelled artifact/bundle/version
  and a fresh authorized decision over those new bytes. That action does not
  repair or retroactively enlarge the old signature's coverage.
- No migration updates old finding/provenance rows or grants old app/triage
  roles new publication authority. No fake commit, snapshot, CPG, line number,
  environment image or signature fills unavailable acceptance fields.
- Accepted-input signatures use their own domain. Future finding provenance
  needs an explicitly reviewed versioned binding to bundle/approval identity;
  do not add unsigned fields to a historical signed encoding.

## 11. Dependency-ordered work and proposed future file ownership

The root's scoped local allocation is now this document and the 12 files below.
Remaining vertical slices still require separate assignments and acceptance;
none is implied completed by this design/code approval.

### 11.1 Exact proposed first implementation slice

The approved first allocation is the closed byte/trust verifier, **only these
12 new files**, in addition to this document:

```text
services/scan/accepted_inputs/__init__.py
services/scan/accepted_inputs/models.py
services/scan/accepted_inputs/schemas.py
services/scan/accepted_inputs/codec.py
services/scan/accepted_inputs/verify.py
services/scan/accepted_inputs/verifier_worker.py
tests/accepted_input_fixtures.py
tests/unit/test_accepted_input_models.py
tests/unit/test_accepted_input_codec.py
tests/unit/test_accepted_input_schemas.py
tests/unit/test_accepted_input_verifier.py
tests/integration/test_accepted_input_verifier_process.py
```

`schemas.py` owns the exact closed authority shapes above; `codec.py` owns
bounded original-byte/framing validation, not a second general-purpose JSON
library. `verify.py` performs actual fixed-profile cryptography and returns the
separate historical/current evidence results. `verifier_worker.py` is the
bounded data-only worker entry, not a generic shell/executable launcher.
Use the separately reviewed shared process transport coordinated with the
corpus/solver owners; do not implement a competing transport here. If that
dependency is unavailable, process integration is explicitly incomplete and
no production-ready verifier/launch claim is allowed.

These tests generate explicitly test-only key material; they never provision
an operator, persist operational keys, read a real trust store, contact a DB,
launch Joern or execute target source. The first slice has no migration,
repository, publication CLI, private-key file writer, authority-installation
operation, existing production-file edit or dependency change. It rejects
unimplemented schemas and cannot grant executable authority from a pure result.
The doc's later integration obligations remain open rather than being silently
assigned to these 12 files. Changes to this list require explicit coordination.

### 11.2 Remaining vertical slices

| Slice | Proposed files | Required outcome |
|---|---|---|
| A — closed bytes/trust verifier | Exactly §11.1's 12 files | Bounded exact framing, strict schema, real signature verification against externally pinned trust; no permissive fallback |
| B — immutable registry | Later `services/scan/accepted_inputs/repository.py`; additive migration/SQL and dedicated restricted-role/concurrency filenames allocated separately against the approved base | Five-table history/coordination distinction, closed grants, durable raw bytes/authority, hostile-ACL and history fences |
| C — explicit builtin publisher/admission | Later `scripts/publish_accepted_builtin.py`, `services/scan/accepted_inputs/local_issuer.py`, `services/scan/accepted_inputs/admission.py`; separately allocated tests | Real scoped adoption/signing and independently installed checkpoint/restore protocol; no ephemeral default or scan-user publication ability |
| D — request/capture/attempt binding | Later `services/scan/accepted_inputs/resolver.py`; separately allocated root-owned request/launch wiring and tests | Real resolver → atomic request binding → occurrence seal → per-run/attempt authorization/renewal/denial history; no generic existence check or arbitrary content bypass |
| E — bounded early G1 | Canonical/solver-owned typed model/producer files, coordinated interfaces only | Exact accepted rule/model bytes actually drive source-bound analysis; semantic/fidelity negatives remain independent |
| F — statistical publication | TRI-owned real stores/adjudication adapter + new evidence schema and tests | Durable candidate/stream/decision/signature atomicity; no caller-authored e-process state as authority |
| G — later full delivery | Global/customer composition, quarantine/rotation integration, signed finding links and UI/status | Preserve full R07/R08/R09/R19 and submitted scope; no early-G1 completion substitution |

Do not edit the frozen occurrence tree to smuggle these fields into its v1
envelopes. Any necessary low-level change must be an explicit separately
reviewed protocol extension, with original history/readers preserved.

## 12. Acceptance tests and falsifiers

All tests use actual CI markers. Database tests use a dedicated task-owned
cluster/child and restricted principals, never the application database.
Crypto tests use generated test-only keys with explicit trusted/untrusted
fixtures; integration must also demonstrate restart persistence of the actual
publisher key/material, not reuse an in-memory mock as durability evidence.

- `AIR-01`: exact raw spec/detector/rule/model bytes survive publish, restart,
  resolve, request binding and seal; verifier recomputes every digest.
- `AIR-02`: JSONB-only legacy row, global version existence, current registry
  files, fake `accepted=true`, signed-looking JSON and a PR URL each fail as
  standalone authority. No execution is launched.
- `AIR-03`: wrong org/scope/detector/version/content, duplicate global NULL
  key, same artifact version with changed bytes and ambiguous bundle selection
  are rejected; exact retry does not change any signed history.
- `AIR-04`: wrong/missing/revoked/expired key, wrong algorithm/size/salt/profile,
  altered statement/signature/evidence, untrusted included key and issuer-kind
  mismatch fail real verification. A familiar key ID is insufficient.
- `AIR-05`: canonical duplicate/unknown keys, invalid scalars/integers/depth,
  malicious lengths, trailing/missing frames, symlinks/path escapes, compression,
  oversized combined/evidence blobs and poison iterables fail before expansion.
- `AIR-06`: new registry roles cannot directly mutate/truncate history, escalate
  roles, alter schema, leak through default ACLs or cross tenant boundaries.
  Ordinary owner UPDATE of fully immutable rows also fails.
- `AIR-07`: fault between artifact/bundle/approval writes, between request and
  binding, and before seal commit leaves no usable partial state. Ambiguous
  commit/replay and two simultaneous publishers use exact immutable keys.
- `AIR-08`: content replacement, namespace rotation/revocation/quarantine during
  preflight and locked commit, stale policy rollback, renewed/expired attempt
  and pooled connection reuse obey §8 without erasing prior occurrences.
- `AIR-09`: new G1 profiles reject unknown selectors/fields and incompatible
  detector/rule/model IDs. Preserve original clause ordinals and whole-spec
  rule ID; no accidental extra rules or R09 strength claims.
- `AIR-10`: accepted entry model still fails when the actual source declaration,
  formal position, API signature, receiver/type/dispatch or transfer/effect
  preconditions are unproved. Acceptance is not a planted-label bypass.
- `AIR-11`: stateless/foreign/mutated e-process state, reused human label event,
  unsigned candidate, missing stream history and builtin-to-statistical key
  substitution cannot publish statistical acceptance.
- `AIR-12`: historical signed bytes remain verifiable with archived public keys;
  current revocation is reported separately. No new source/graph fields are
  fabricated, and new signed links do not reinterpret old signature domains.
- `AIR-13`: production wiring uses the real resolver, rejects unbound low-level
  occurrence rows, and fails the job explicitly for unavailable authority;
  no default fake, missing-pin native launch or endless pending status.
- `AIR-14`: prove the accepted bytes used by the actual parser/solver are the
  sealed bytes, including a registry-file change after request creation. Native
  probes remain separately gated by the reviewed source/Java safety contracts.
- `AIR-15`: create a request under policy P1, rotate to P2, seal/authorize/renew
  under P2/P3 and verify separate immutable events with exact run/attempt,
  token/revision/lease/current-policy links. Original binding/seal authority
  bytes remain identical. Retry uses a new attempt/token and initial event;
  changed replay, cross-kind/run/occurrence and another tenant's valid token
  cannot gain authority. A completed/failed run's historical receipt never
  permits relaunch. Denials/failures do not erase retained detections.
- `AIR-16`: inject a transaction failure between claim/begin/renew/seal and its
  authorization insertion, then between authorization and commit. No granted
  lease/target transition can escape without its event. Lost acknowledgement
  returns exact history, not a second process launch. Check original/renewed
  authorization chains, actual capture leases, missing pins and stale fences.
- `AIR-17`: ordinary owner UPDATE of every immutable history field fails.
  Namespace guards permit only exact documented policy/admission transitions;
  changed identity, lower policy, reused grant, tombstone deletion, illicit
  mutable column, unchanged revision on mutation and direct runtime DML fail.
  Exercise hostile default schema/table/function ACLs and function shadowing.
- `AIR-18`: restore a previously valid P1 database while the independent
  checkpoint requires P2; archived valid root signatures cannot authorize use.
  Exercise equal-generation changed digest, stale epoch, expired/block/missing
  checkpoint, wrong deployment, stale cached admission and crashes at each
  DB/external-checkpoint transition. Only explicit current-head reconciliation
  and fresh-epoch admission restore service; no autonomous trust bootstrap.
- `AIR-19`: restore with prior running work and a retained live-child record.
  Old permits cannot launch/renew; new admission waits for explicit process/
  lease recovery. A backup that lacks trusted current policy remains blocked.
  Clock skew/backward jump blocks authority and never lengthens a monotonic
  running deadline. Test minimum grant/policy/checkpoint/lease expiry boundaries.
- `AIR-20`: exact closed role/schema/object inventories reject arbitrary
  attachments, extra/missing/duplicate roles, unknown grants, statistically
  labelled operator events, delegation, root substitution and fake receipts.
  Publication uses its active live policy, not an old pre-signed draft; retired
  grants allow only strictly earlier committed approvals and cannot reactivate.
- `AIR-21`: parser and crypto size/count/depth/key/signature boundaries fail
  before expansion or RSA work; test N-1/N/N+1, malformed DER/trailing bytes,
  wrong exponent/PSS salt, poisoned iterables, subprocess timeout/memory failure
  and unsupported isolation. Count actual cryptographic checks; never retry
  attacker-chosen key/algorithm lists. Full authority and live-pair caps compose.
- `AIR-22`: two model artifacts with the same model_id do not collide; two
  rule sets cannot share fact/summary/kill state or raw occurrence keys. Logical
  rule_id remains spec_id. One selected rule's completion cannot certify
  unattempted bundle members, even with a valid content-acceptance signature.
- `AIR-23`: exact three-mode request/result framing, header/inner length parity,
  zero absent frames, individual/whole caps, bool/unknown-key/duplicate rejection,
  missing/trailing bytes, nullable failed-input digest and exit/result agreement.
  A publication preflight cannot impersonate a receipt; historical verification
  cannot acquire current execution fields. No accepted prefix or stderr leak.
- `AIR-24`: actual shared-wrapper forwarding observes the closed argv/env/cwd
  and finite immutable input. Poisoned profile/path/environment, ambient
  PYTHONPATH/sitecustomize/PTH/module shadowing, symlink/writable source roots,
  altered executable/script/profile hash, wrong Python version and failed
  rlimits all reject. Test actual child limits/import roots without running
  target code. Poison stale adjacent .pyc/old-job/ambient caches and prove only
  the fresh empty trusted pycache prefix is used, with actual sys.pycache_prefix
  checked; -B alone is not sufficient. Timeout/cleanup/EOF failures retain the
  original partial outcome.
- `AIR-25`: the public producer API rechecks exact full-bundle membership,
  original publication/request/authorization bytes and fresh policy/fence/epoch
  before and after bounded verification. Caller-made checked models, stale
  contexts, mismatched detector/run and a scan-selected reader/profile cannot
  bypass it. Import/re-export the single QualifiedRuleKey/codec; test metadata
  byte parity, no cross-layer import cycle and no copied transport records.

## 13. Decisions and actual remaining authority

No obsolete CLAR approval is an architecture blocker for this design. These
concrete choices remain before later implementation/publication:

- Root approved this contract and the bounded 13-file local verifier slice
  under #399. Durable registry/publisher/reader and production integration
  still need separate allocation. Design/code approval does not create a real
  publisher or install any trust/admission state.
- The installation owner must name the real accepting operator, approve that
  operator's scope/capability, and provision/pin persistent trust-root/publisher
  public identities. An agent must not invent that identity or silently turn
  a test key into operational authority. This blocks actual publication, not
  implementation with explicit test fixtures.
- The owner must also appoint the independent admission/restore administrator,
  choose the protected checkpoint location outside DB backup rollback, accept
  the proposed 7-day admission renewal and trusted-clock boundaries, and make
  service startup/restore honor the block/admit procedure. Until installed and
  tested, no operational launch is authorized. This administrative dependency
  is not silently satisfied by root's approval to implement the verifier.
- The early-G1 model owner must finish exact selector/model schemas and
  supported-precondition tests. IDs and logical rule mapping in §5 are the
  coordinated proposal, not certification that the semantics are implemented.
- Statistical publication additionally needs the real adjudication authority,
  evaluation/selection policy and gate-enablement evidence. Those omissions
  cannot be resolved by renaming operator approval.

No new cloud service, spend, release, organizer message or native-source
execution is required or authorized here. The result sought is a small real
accepted-input path with explicit limits, followed by the listed remaining
work—not a document-only or caller-asserted substitute for acceptance.

## 14. Local verifier implementation checkpoint

The allocated 13-file slice now implements bounded immutable models, closed
schemas, canonical byte framing, real RSA verification and a private diagnostic
subprocess. The public operational launcher still refuses unconditionally until
the actual installed trust/authority reader, runtime loader and controller are
integrated. A test-built record or diagnostic key never supplies that authority.
No registry migration, operational key, admission checkpoint, source/native
execution, app database mutation, remote publication or full AIR acceptance was
performed by this slice.

The implementation imports the actual shared key/semantic decoder and bounded
transport through normal full dependency merges, not copied implementations:
`34e99f3377e04e12f6bad580ade3dee2571dd418`,
`da0d359a59a0f2bdde01c495f3b219bbd531e31a` and
`62a61583ba340405fde8b30ff636ad50d800ddaf`. These are local dependency
checkpoints; their inclusion does not assert remote acceptance or runtime
permission. Runtime-file inventory/controller integration remains separate.

Final functional verification used staged tree
`a06caee3e2b49543ba93fe4fba7c81d83a8301e2`, before this result record and a
comment-only clarification that the semantic decoder is already integrated:

| Selection | Observed result | Task-local evidence |
|---|---|---|
| Four new unit modules plus diagnostic process integration module | 236 passed, zero skipped/failed; 198 unit and 38 integration cases | `/tmp/scanipy-399-final-boundary.xml` |
| Full configured suite | 2,297 passed, 140 existing optional skips, zero failures/errors; 2,437 total | `/tmp/scanipy-399-final-full.xml` |
| Actual normal pre-push unit/invariant selection | 2,214 passed, 11 existing skips, zero failures/errors; 2,225 total | `/tmp/scanipy-399-final-hook-units.xml` |
| Coverage produced by that normal pre-push run | 89.96%; unchanged required minimum 80% | `/tmp/scanipy-399-final-hook-coverage.xml` |

The declared Python 3.11.16 environment was used with both its CLI `PATH` and
this worktree's explicit `PYTHONPATH`. Whole-repository Ruff/format and the
normal pre-push mypy selection also passed. The first earlier full invocation
omitted the environment's CLI `PATH` and failed the existing yamllint-discovery
test; its 2,285 passes/140 skips/one failure remain recorded at
`/tmp/scanipy-399-full-final-draft.xml`. The corrected invocation and final runs
did not weaken the dependency or hook checks. Earlier pre-refinement results
are not substituted for the final UUID-snapshot and owned-FD cleanup tests.

Root and an independent peer reviewed the complete scoped implementation;
the peer's final approval is tied to the functional tree above. Their approval
is mechanism/code review only. Normal commit hooks, any later dependency-merge
checks, exact-head remote CI and canonical approval must be recorded when
actually completed. These task-local JUnit/coverage files are diagnostic
evidence, not portable signed acceptance artifacts. Remaining durable registry,
publication, restore admission, live reader and controller work in §§11–13 is
still required.

## 15. Pure tenant-local administrative verification allocation

2026-09-26. Root and independent review approved the administration V2 design
(`48cb40b4c8bdcb79e3acb1ccc7c5cd14b0cf3413e8335145f793362c51d056ba`)
plus its V3 amendment
(`5f0e3a971ec7cbf4c3c3f68c265b0542a4a6f3eeee0db235b140e5fab4e03b69`).
The first implementation allocation is only this append, the existing
`services/scan/accepted_inputs/verify.py`, and the new
`tests/unit/test_accepted_administration.py`, based on accepted commit
`0e53e188c37805f95fd1121067c3146149cf735a`. Prior sections and their historical
checkpoints remain unchanged. This allocation is not approval of an installed
operator, private key, admission checkpoint, SQL publication or native launch.

### 15.1 Exact API and result boundary

All five public functions live in the existing verifier module. `Signed` below
is notation for an **exact** two-element `tuple[bytes, bytes]`, not a new model.
All named input and result classes are the existing accepted-input owners.

```python
verify_admin_policy(policy: Signed, *, trust: InstalledTrust,
                    root_spki: bytes, previous: Signed | None) -> None
verify_admin_admission(checkpoint: Signed, *, trust: InstalledTrust,
                       root_spki: bytes, policy: Signed,
                       previous: Signed | None) -> None
verify_admin_current(live: bytes, *, trust: InstalledTrust, root_spki: bytes,
                     expected: AdmissionExpectation,
                     reference_time: str) -> VerifiedCurrentPolicy
verify_admin_publication(bundle: AcceptedBundleBytes, publication_input: bytes,
                         *, trust: InstalledTrust,
                         expected_bundle: BundleExpectation,
                         admission: AdmissionExpectation,
                         reference_time: str) -> VerificationChecks
verify_admin_publication_receipt(bundle: AcceptedBundleBytes,
                                 publication_input: bytes, receipt: bytes,
                                 *, trust: InstalledTrust,
                                 expected_bundle: BundleExpectation,
                                 publisher_artifact_digest: str
                                 ) -> VerificationChecks
```

The new ingress is customer/builtin only. Existing B modes, global structural
support, signature profile and unconditional operational-runner refusal remain
unchanged. No AL-02/03 imports, alternate owner models, fake VerifierRequest or
SEALED frame, callback, filesystem, clock, network, SQL or process is introduced.
The accepted B codec remains the authority for raw framing, canonical metadata,
closed scalar/record shapes, and raw content hashes. The actual semantic decoder
checks every rule/model pair in every declared language, including Java schema
decoding without claiming Java execution support. Original content is not rewritten.

Policy verification checks root signatures, namespace, initial revision 1 or
the exact adjacent predecessor, immutable grant identities, tombstone evolution
and all newly admitted grant intervals. It does not accept skipped revisions as
an administrative successor. Admission checks signed current/previous checkpoints
and policy, deployment/administrator/namespace, exact policy domain/revision,
initial generation 1 or adjacent predecessor, and owning lifetime constraints.
Both admit and block are legal signed structures; verification does not install
them or authorize block-to-admit restore recovery.

Current verification checks the exact four-role LIVE frame, both root signatures,
all five AdmissionExpectation fields and validity at the supplied instant. Its
permission expiry is the minimum policy/checkpoint expiry, not an arbitrarily
selected issuer grant. This is material consistency relative to supplied pins
and time, not proof that those pins were installed or that a supplied head is live.

Publication preflight shares the original bundle, approval, policy and admission
checks, returning the existing publication-preflight-shaped VerificationChecks.
Receipt verification additionally binds every exact PUBLICATION field to the
original input, including actor/artifact, all raw-versus-domain digest meanings,
approval/publication identities and checkpoint generation/epoch. It uses the
original `published_at` as its verification instant, never the current invocation
time. The result has that `verified_at`, the original content/approval fields and
PUBLICATION domain digest; qualified/execution/current-policy/checkpoint/epoch/
permission fields are null. Neither a receipt-shaped record nor this return value
proves a SQL commit, exact-command replay, installed currentness or launch authority.
Only a later actual mutation response can report its own `replayed` boolean.

### 15.2 Fixed logical-work ceilings and helper reservations

Each public call allocates one private V meter, with ceilings of 100,000 explicit
SHA invocations, 134,217,728 SHA input bytes, eight DER public-key loads and twelve
RSA verifications; no signing. Full conservative work is charged before each
delegate, including malformed inputs, nested helper work and repeated reads.
There are no refunds, hidden nested public-call resets or dedup discounts.
Limit exhaustion uses the existing fixed `invalid-input` error. RSA-internal
hashing is separately bounded by the RSA operation/message caps, not mislabeled
as an explicit hashlib invocation or proof of measured CPU/RSS/time behavior.

Let M/D/R be model/detector/rule counts; U the model byte total; T all supplied
spec/detector/rule bytes; W detector+rule bytes; A=1,048,576; O=65,536;
p=37 (the actual accepted-content schema plus LF); and
q=len(`scanipy-rule-semantics-binding/1`)+1. Reservations are:

| Actual owner helper | Explicit SHA calls / input-byte upper bound |
|---|---|
| `decode_spec` count discovery | 20,000 / spec length, before discovering M |
| Fresh `AcceptedBundleBytes` construction or `validate_bundle_layout` | M / U, each invocation |
| `accepted_content_digest` | M+3+D+R / U+T+2(A+p) |
| `qualified_members` | 3M+3+2D+3R / 3U+T+W+2(A+p)+R(O+q) |
| Each actual rule/language `decode_bound_rule` | 2 / rule length+model length |
| Frame decode | Exact owning role count / full bounded frame length |
| `_key` | 1 / exact SPKI length, plus one load |
| `_policy` | One RSA verification |
| `_checkpoint` | One POLICY domain hash plus one RSA verification |
| `_approval` | POLICY and INVENTORY domain hashes, issuer-SPKI and adoption raw hashes; one load/one RSA verification |
| `_admission_expected` | POLICY and ADMISSION domain hashes |
| Adjacent `_policy_evolution` | One predecessor POLICY domain hash |
| Other explicit raw/domain digest | One / exact input length, including schema+LF for domain hashes |

Existing raw byte/count/depth/key/signature limits apply before these delegates.
Original caller model slots are snapshotted with exact class/type/shape checks;
UUID integer storage is validated before formatting a fresh UUID. A poisoned
constructor argument or mutated frozen record cannot invoke a caller formatter
or survive as a retained alias. No installed provenance is inferred from these
data-only snapshots. Missing/invalid slots fail with existing typed errors.

### 15.3 Verification gates and remaining work

The allocated unit tests must exercise actual disposable fixture RSA signatures,
all five APIs and typed results, every historical receipt link, malformed and
poisoned input, adjacent and rejected policy/checkpoint evolution, time and
customer/builtin fences, exact limit boundaries/no refunds, and actual helper
precharge instrumentation including malformed and multi-member/all-language
paths. The existing B unit regressions remain required. Tests do not install keys
or operate the application database or worker runtime.

At this allocation checkpoint no final implementation review, full suite,
remote gate, persistent key/independent highwater provider, privileged CLI,
private custody/restart protocol, AL publication integration, installed identity,
restore procedure or runtime controller acceptance is claimed. Those require
their separately allocated implementations, actual operator choices and tests.

### 15.4 Author checkpoint, pending independent implementation review

The allocated implementation and tests are frozen for root/peer review at raw
source SHA `830bedb2b2428a717fd75cb08b8c071b6383eda2591fdfd5eed2356ce0949460`
and test SHA `0044d84dc4a55642ab998e5dc1eb77f154aacd66d8b08101a278b1712e0ebbce`.
These are local code evidence, not installed or operational authority.

| Bounded configured selection | Actual result | Retained author evidence |
|---|---|---|
| Initial new API cases, before coverage expansion | 128 passed; 0 failed/errors/skipped; 8.501 s | `/tmp/scanipy-admin-verification-first.xml`, SHA `ec502d2b1298ada9ad58b5a67d04241409dda2352e067bf5da9d19b46c768695` |
| Expanded new cases + unchanged verifier module | 207 passed; 0 failed/errors/skipped; 16.349 s | `/tmp/scanipy-admin-verification-expanded.xml`, SHA `dc027b7f801b6a8ed8ed132b61ac7d013cb6fc057d6002b02330050baa0eda7b` |
| Final 164 new cases + 198 unchanged B codec/model/schema/verifier cases | 362 passed; 0 failed/errors/skipped; 19.254 s | `/tmp/scanipy-admin-verification-final-owned.xml`, SHA `df9e17fd520d4f928c0b9ffc7e4458e6881fbe2cbfb38c04330fa615913babd8` |

These selections overlap and must not be summed. No failing functional test
was observed in these runs. Initial Ruff checks reported one, then five C408
test-only literal-style findings; they were corrected without disabling rules.
Final two-file Ruff/format and strict source mypy passed. All runs used the
existing declared Python 3.11 environment with explicit task PYTHONPATH,
`PYTHONDONTWRITEBYTECODE=1`/`python -B` and cleared app/PG/AWS/hook-bypass inputs.
No diagnostic process-verifier selection, broad/full suite, database, network,
installed key, hook, commit, push or runtime launch was performed.

Actual instrumentation checks prepayment before every observed SHA/key load/RSA
on the five success routes, and per-helper allowances on malformed specification,
last model/rule hash and last semantic-member paths. Two models/two detectors/four
bilingual rules exercise every declared language. A valid global B publication
still verifies through its original mode while the new customer-only ingress
rejects it. Statistical/inferred material, block/expired LIVE and receipt-link
tampering fail; historical receipts retain original time and null current fields.
All original top-level verifier function/class ASTs except the explicitly
refactored `_bundle` wrapper are unchanged; model/schema/codec and original test
files retain accepted bytes. The entire pre-§15 document prefix is byte-identical.
Independent code review, broader acceptance and all §15.3 remaining work are open.

### 15.5 Independent pure-slice review — 2026-09-26

Root and the independent reviewer read the complete production delta, all1,011
new test lines and this append against the approved V2/V3 contract and actual B
owners. Both approve this bounded pure slice; no concrete implementation blocker
was found. Source830bedb2 and test0044d84d remain the exact §15.4 bytes. The
other23 original top-level verifier definitions, original model/schema/codec/
bound-rule/fixture/test files and the original1,734-line contract prefix remain
unchanged. This is not canonical remote approval or installed authority.

Independent configured verification passed370 cases, zero skips/errors/failures,
27.607s:164 new +198 unchanged B +8 outside per-reservation controls. Report
`/tmp/scanipy-admin-verification-peer-370.xml`, SHA256
`02b878a075272b810871b8d1128846e610fec5d8585e4f7d131d84ccd2aa5afc`.
The eight independent controls are
`/tmp/scanipy-admin-peer-review-20s71exb/test_admin_peer_precharge.py`, SHA256
`c95d5dc0621c50f7018c847925beb5aaf15e8cd97f402150754dbf9ad0af30a4`.
They reset local SHA/load/RSA allowance at every actual reservation across all
five APIs, adjacent policy/admission and multilingual publication; earlier
discovery slack cannot hide a missing later precharge. One meter is retained.
Root independently read the controls and parsed the complete result counts.
These370 overlap the author362 and are not additive unique coverage.

No functional red, repository edit, PG/process/native/broad run, hook, commit
or publication occurred in that independent check. All full-suite/normal-hook/
exact-head CI/canonical gates and every §15.3 operational TODO remain required.
