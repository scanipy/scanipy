-- Exactly five AL-03 tables. Ordered membership arrays are validated under the
-- namespace lock; they are deliberately not described as element foreign keys.
CREATE TABLE scanipy_accepted_inputs.registry_namespaces (
  id uuid PRIMARY KEY,
  registry_id uuid NOT NULL,
  scope text NOT NULL CHECK(scope IN ('global','customer')),
  org_id uuid,
  installation_bytes bytea NOT NULL CHECK(octet_length(installation_bytes) BETWEEN 1 AND 4096),
  installation_sha256 bytea NOT NULL CHECK(octet_length(installation_sha256)=32),
  deployment_id uuid NOT NULL, administrator_actor_id uuid NOT NULL,
  root_spki_sha256 bytea NOT NULL CHECK(octet_length(root_spki_sha256)=32),
  installation_length integer GENERATED ALWAYS AS (octet_length(installation_bytes)) STORED,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  policy_event_id uuid, policy_digest bytea,
  policy_revision bigint NOT NULL DEFAULT 0 CHECK(policy_revision>=0),
  admission_event_id uuid, checkpoint_digest bytea,
  checkpoint_generation bigint NOT NULL DEFAULT 0 CHECK(checkpoint_generation>=0),
  admission_epoch uuid,
  coordination_revision bigint NOT NULL DEFAULT 0 CHECK(coordination_revision>=0),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  policy_kind text GENERATED ALWAYS AS (CASE WHEN policy_event_id IS NOT NULL THEN 'policy' END) STORED,
  admission_kind text GENERATED ALWAYS AS (CASE WHEN admission_event_id IS NOT NULL THEN 'admission' END) STORED,
  UNIQUE NULLS NOT DISTINCT(registry_id,scope,org_id),
  UNIQUE(id,registry_id,scope,org_id),
  CHECK((scope='global')=(org_id IS NULL)),
  CHECK((policy_event_id IS NULL AND policy_digest IS NULL AND policy_revision=0)
    OR (policy_event_id IS NOT NULL AND octet_length(policy_digest)=32 AND policy_revision>0)),
  CHECK((admission_event_id IS NULL AND checkpoint_digest IS NULL AND checkpoint_generation=0 AND admission_epoch IS NULL)
    OR (admission_event_id IS NOT NULL AND octet_length(checkpoint_digest)=32 AND checkpoint_generation>0 AND admission_epoch IS NOT NULL))
);

CREATE TABLE scanipy_accepted_inputs.artifact_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), namespace_id uuid NOT NULL,
  kind text NOT NULL CHECK(kind IN ('detector','rule-set','operation-model')),
  artifact_id text NOT NULL, version text NOT NULL, artifact_schema text NOT NULL,
  raw_bytes bytea NOT NULL CHECK(octet_length(raw_bytes) BETWEEN 1 AND 1048576),
  raw_length integer NOT NULL CHECK(raw_length BETWEEN 1 AND 1048576),
  raw_sha256 bytea NOT NULL CHECK(octet_length(raw_sha256)=32),
  metadata_length integer GENERATED ALWAYS AS
    (64+octet_length(kind)+octet_length(artifact_id)+octet_length(version)+octet_length(artifact_schema)) STORED,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(namespace_id,id), UNIQUE(namespace_id,kind,artifact_id,version),
  FOREIGN KEY(namespace_id) REFERENCES scanipy_accepted_inputs.registry_namespaces(id),
  CHECK(raw_length=octet_length(raw_bytes)),
  CHECK(artifact_schema=CASE kind WHEN 'detector' THEN 'scanipy-accepted-detector/1'
    WHEN 'rule-set' THEN 'scanipy-bound-rule-set/1' ELSE 'scanipy-operation-models/1' END)
);

CREATE TABLE scanipy_accepted_inputs.bundle_versions (
  id uuid NOT NULL, namespace_id uuid NOT NULL, s_version text NOT NULL,
  spec_bytes bytea NOT NULL CHECK(octet_length(spec_bytes) BETWEEN 1 AND 1048576),
  accepted_content_bytes bytea NOT NULL CHECK(octet_length(accepted_content_bytes) BETWEEN 1 AND 1048576),
  accepted_content_digest bytea NOT NULL CHECK(octet_length(accepted_content_digest)=32),
  detector_ids uuid[] NOT NULL, rule_ids uuid[] NOT NULL, model_ids uuid[] NOT NULL,
  content_length integer NOT NULL CHECK(content_length BETWEEN 1 AND 1048576),
  spec_length integer GENERATED ALWAYS AS (octet_length(spec_bytes)) STORED,
  accepted_content_length integer GENERATED ALWAYS AS (octet_length(accepted_content_bytes)) STORED,
  detector_count integer GENERATED ALWAYS AS (cardinality(detector_ids)) STORED,
  rule_count integer GENERATED ALWAYS AS (cardinality(rule_ids)) STORED,
  model_count integer GENERATED ALWAYS AS (cardinality(model_ids)) STORED,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(namespace_id,id), UNIQUE(namespace_id,s_version),
  UNIQUE(namespace_id,id,accepted_content_digest),
  FOREIGN KEY(namespace_id) REFERENCES scanipy_accepted_inputs.registry_namespaces(id),
  CHECK(array_ndims(detector_ids)=1 AND array_lower(detector_ids,1)=1 AND cardinality(detector_ids) BETWEEN 1 AND 20000
    AND array_position(detector_ids,NULL) IS NULL),
  CHECK(array_ndims(rule_ids)=1 AND array_lower(rule_ids,1)=1 AND cardinality(rule_ids) BETWEEN 1 AND 20000
    AND array_position(rule_ids,NULL) IS NULL),
  CHECK(array_ndims(model_ids)=1 AND array_lower(model_ids,1)=1 AND cardinality(model_ids) BETWEEN 1 AND 20000
    AND array_position(model_ids,NULL) IS NULL)
);

-- Only these two additive composite keys touch existing occurrence tables.
-- Their definitions, configurations, triggers, old ACLs and raw history stay intact.
ALTER TABLE scanipy_execution.detector_runs ADD CONSTRAINT accepted_detector_scope_key
  UNIQUE(org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,work_attempt_id,id);
ALTER TABLE scanipy_execution.capture_leases ADD CONSTRAINT accepted_consumer_scope_key
  UNIQUE(org_id,codebase_id,request_id,capture_id,work_item_id,work_attempt_id,fencing_token,id);

CREATE TABLE scanipy_accepted_inputs.authority_events (
  id uuid NOT NULL, namespace_id uuid NOT NULL,
  kind text NOT NULL CHECK(kind IN ('policy','admission','approval','seal-authorization',
    'execution-authorization','execution-denial')),
  record_schema text NOT NULL,
  record_bytes bytea NOT NULL CHECK(octet_length(record_bytes) BETWEEN 1 AND 131072),
  record_digest bytea NOT NULL CHECK(octet_length(record_digest)=32),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  operation_key uuid NOT NULL, action text NOT NULL,
  command_bytes bytea NOT NULL CHECK(octet_length(command_bytes) BETWEEN 1 AND 65536),
  command_digest bytea NOT NULL CHECK(octet_length(command_digest)=32),
  command_parts bytea[] NOT NULL CHECK(scanipy_accepted_inputs.v1_byte_array(command_parts)<=3145728),
  record_length integer GENERATED ALWAYS AS (octet_length(record_bytes)) STORED,
  command_length integer GENERATED ALWAYS AS (octet_length(command_bytes)) STORED,
  command_part_lengths integer[] GENERATED ALWAYS AS (scanipy_accepted_inputs.v1_lengths(command_parts)) STORED,
  registry_id uuid NOT NULL, scope text NOT NULL CHECK(scope IN ('global','customer')), org_id uuid,
  bundle_id uuid, accepted_content_digest bytea, approval_event_id uuid,
  publication_key uuid, publication_receipt_bytes bytea, publication_receipt_digest bytea,
  policy_event_id uuid, policy_digest bytea, policy_revision bigint,
  admission_event_id uuid, checkpoint_digest bytea, checkpoint_generation bigint, admission_epoch uuid,
  previous_event_digest bytea,
  signature_bytes bytea,
  publication_input_bytes bytea,
  publication_input_length integer GENERATED ALWAYS AS (octet_length(publication_input_bytes)) STORED,
  publication_receipt_length integer GENERATED ALWAYS AS (octet_length(publication_receipt_bytes)) STORED,
  codebase_id uuid, request_id uuid, request_binding_digest bytea,
  work_item_id uuid, work_attempt_id uuid, fencing_token bigint, work_revision bigint,
  capture_id uuid, seal_id uuid, capture_lease_id uuid,
  requested_policy_digest bytea, attempt_policy_digest bytea,
  lease_expires_at timestamptz, capture_lease_expires_at timestamptz,
  detector_run_id uuid, run_input_digest bytea, occurrence_id uuid, previous_authorization_id uuid,
  purpose text, execution_action text, resolver_artifact_digest bytea,
  authorized_at timestamptz, observed_at timestamptz, denial_reason text,
  policy_kind text GENERATED ALWAYS AS (CASE WHEN policy_event_id IS NOT NULL THEN 'policy' END) STORED,
  admission_kind text GENERATED ALWAYS AS (CASE WHEN admission_event_id IS NOT NULL THEN 'admission' END) STORED,
  approval_kind text GENERATED ALWAYS AS (CASE WHEN approval_event_id IS NOT NULL THEN 'approval' END) STORED,
  previous_authorization_kind text GENERATED ALWAYS AS
    (CASE WHEN previous_authorization_id IS NOT NULL THEN 'execution-authorization' END) STORED,
  PRIMARY KEY(namespace_id,id), UNIQUE(namespace_id,kind,id),
  UNIQUE(namespace_id,operation_key), UNIQUE(namespace_id,kind,record_digest),
  UNIQUE(namespace_id,kind,id,org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,
    work_attempt_id,detector_run_id,capture_lease_id,record_digest),
  FOREIGN KEY(namespace_id) REFERENCES scanipy_accepted_inputs.registry_namespaces(id),
  FOREIGN KEY(namespace_id,bundle_id,accepted_content_digest)
    REFERENCES scanipy_accepted_inputs.bundle_versions(namespace_id,id,accepted_content_digest),
  FOREIGN KEY(namespace_id,policy_kind,policy_event_id)
    REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id),
  FOREIGN KEY(namespace_id,admission_kind,admission_event_id)
    REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id),
  FOREIGN KEY(namespace_id,approval_kind,approval_event_id)
    REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id),
  FOREIGN KEY(namespace_id,previous_authorization_kind,previous_authorization_id)
    REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id),
  FOREIGN KEY(org_id,codebase_id,request_id)
    REFERENCES scanipy_execution.scan_requests(org_id,codebase_id,id),
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,work_attempt_id,detector_run_id)
    REFERENCES scanipy_execution.detector_runs(org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,work_attempt_id,id),
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id,work_item_id,work_attempt_id,fencing_token,capture_lease_id)
    REFERENCES scanipy_execution.capture_leases(org_id,codebase_id,request_id,capture_id,work_item_id,work_attempt_id,fencing_token,id),
  CHECK((scope='global')=(org_id IS NULL)),
  CHECK(record_schema=CASE kind WHEN 'policy' THEN 'scanipy-accepted-trust-policy/1'
    WHEN 'admission' THEN 'scanipy-registry-admission/1' WHEN 'approval' THEN 'scanipy-accepted-approval/1'
    WHEN 'seal-authorization' THEN 'scanipy-capture-seal-authorization/1'
    WHEN 'execution-authorization' THEN 'scanipy-execution-authorization/1' ELSE 'scanipy-execution-denial/1' END),
  CHECK(action=CASE kind WHEN 'policy' THEN 'install-policy' WHEN 'admission' THEN 'record-admission'
    WHEN 'approval' THEN 'publish-builtin' WHEN 'seal-authorization' THEN 'seal-bound-capture' ELSE action END),
  CHECK(kind NOT IN ('execution-authorization','execution-denial') OR action IN ('authorize-detector','renew-detector')),
  CHECK((signature_bytes IS NOT NULL)=(kind IN ('policy','admission'))),
  CHECK(signature_bytes IS NULL OR octet_length(signature_bytes)=384),
  CHECK((publication_input_bytes IS NOT NULL)=(kind='approval')),
  CHECK(publication_input_bytes IS NULL OR octet_length(publication_input_bytes)<=1048576),
  CHECK((publication_key IS NOT NULL)=(kind='approval')),
  CHECK((publication_receipt_bytes IS NOT NULL)=(kind='approval')),
  CHECK((publication_receipt_digest IS NOT NULL)=(kind='approval')),
  CHECK(publication_receipt_bytes IS NULL OR octet_length(publication_receipt_bytes)<=65536),
  CHECK(publication_receipt_digest IS NULL OR octet_length(publication_receipt_digest)=32),
  CHECK(kind IN ('policy','admission','approval') OR
    (scope='customer' AND codebase_id IS NOT NULL AND request_id IS NOT NULL
      AND bundle_id IS NOT NULL AND accepted_content_digest IS NOT NULL AND approval_event_id IS NOT NULL
      AND policy_event_id IS NOT NULL AND admission_event_id IS NOT NULL AND admission_epoch IS NOT NULL
      AND request_binding_digest IS NOT NULL AND requested_policy_digest IS NOT NULL AND attempt_policy_digest IS NOT NULL
      AND work_item_id IS NOT NULL AND work_attempt_id IS NOT NULL AND fencing_token>0 AND work_revision>=0
      AND capture_id IS NOT NULL AND seal_id IS NOT NULL AND capture_lease_id IS NOT NULL
      AND lease_expires_at IS NOT NULL AND capture_lease_expires_at IS NOT NULL
      AND resolver_artifact_digest IS NOT NULL)),
  CHECK(kind NOT IN ('execution-authorization','execution-denial') OR
    (purpose='detector-run' AND detector_run_id IS NOT NULL AND run_input_digest IS NOT NULL AND occurrence_id IS NULL)),
  CHECK((authorized_at IS NOT NULL)=(kind IN ('seal-authorization','execution-authorization'))),
  CHECK((observed_at IS NOT NULL)=(kind='execution-denial')),
  CHECK((denial_reason IS NOT NULL)=(kind='execution-denial')),
  CHECK(denial_reason IS NULL OR denial_reason IN ('grant-revoked','grant-expired','policy-expired',
    'unsupported-authority','missing-runtime-pin','scope-conflict')),
  CHECK((execution_action IS NOT NULL)=(kind='execution-authorization')),
  CHECK(execution_action IS NULL OR execution_action IN ('initial','renew')),
  CHECK(kind<>'execution-authorization' OR (execution_action='initial')=(previous_authorization_id IS NULL)),
  CHECK(previous_authorization_id IS NULL OR previous_authorization_id<>id)
);
CREATE UNIQUE INDEX accepted_publication_key ON scanipy_accepted_inputs.authority_events(namespace_id,publication_key)
  WHERE kind='approval';
CREATE UNIQUE INDEX accepted_seal_work ON scanipy_accepted_inputs.authority_events(namespace_id,work_item_id)
  WHERE kind='seal-authorization';
CREATE UNIQUE INDEX accepted_initial_target ON scanipy_accepted_inputs.authority_events(namespace_id,work_attempt_id,detector_run_id)
  WHERE kind='execution-authorization' AND execution_action='initial';
CREATE UNIQUE INDEX accepted_successor ON scanipy_accepted_inputs.authority_events(namespace_id,previous_authorization_id)
  WHERE kind='execution-authorization' AND previous_authorization_id IS NOT NULL;
CREATE UNIQUE INDEX accepted_target_revision ON scanipy_accepted_inputs.authority_events(namespace_id,work_attempt_id,detector_run_id,work_revision)
  WHERE kind='execution-authorization';
CREATE INDEX accepted_target_leaf ON scanipy_accepted_inputs.authority_events(namespace_id,work_attempt_id,detector_run_id,work_revision DESC)
  WHERE kind='execution-authorization';

ALTER TABLE scanipy_accepted_inputs.registry_namespaces ADD CONSTRAINT accepted_policy_head_fk
  FOREIGN KEY(id,policy_kind,policy_event_id) REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id);
ALTER TABLE scanipy_accepted_inputs.registry_namespaces ADD CONSTRAINT accepted_admission_head_fk
  FOREIGN KEY(id,admission_kind,admission_event_id) REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id);

CREATE TABLE scanipy_accepted_inputs.request_bundle_bindings (
  namespace_id uuid NOT NULL, org_id uuid NOT NULL, codebase_id uuid NOT NULL, request_id uuid NOT NULL,
  registry_id uuid NOT NULL, bundle_id uuid NOT NULL, approval_event_id uuid NOT NULL,
  policy_event_id uuid NOT NULL, admission_event_id uuid NOT NULL,
  accepted_content_digest bytea NOT NULL CHECK(octet_length(accepted_content_digest)=32),
  requested_policy_digest bytea NOT NULL CHECK(octet_length(requested_policy_digest)=32),
  sealed_bytes bytea NOT NULL CHECK(octet_length(sealed_bytes) BETWEEN 1 AND 1048576),
  sealed_sha256 bytea NOT NULL CHECK(octet_length(sealed_sha256)=32),
  sealed_length integer GENERATED ALWAYS AS (octet_length(sealed_bytes)) STORED,
  resolved_at timestamptz NOT NULL,
  operation_key uuid NOT NULL, command_bytes bytea NOT NULL CHECK(octet_length(command_bytes) BETWEEN 1 AND 65536),
  command_digest bytea NOT NULL CHECK(octet_length(command_digest)=32),
  command_length integer GENERATED ALWAYS AS (octet_length(command_bytes)) STORED,
  command_part_lengths integer[] GENERATED ALWAYS AS (scanipy_accepted_inputs.v1_lengths(command_parts)) STORED,
  command_parts bytea[] NOT NULL CHECK(scanipy_accepted_inputs.v1_byte_array(command_parts)=
    octet_length(command_parts[1])::bigint+octet_length(command_parts[2]) AND cardinality(command_parts)=2),
  policy_kind text GENERATED ALWAYS AS ('policy'::text) STORED,
  admission_kind text GENERATED ALWAYS AS ('admission'::text) STORED,
  approval_kind text GENERATED ALWAYS AS ('approval'::text) STORED,
  PRIMARY KEY(org_id,request_id), UNIQUE(namespace_id,org_id,codebase_id,request_id),
  UNIQUE(namespace_id,operation_key),
  FOREIGN KEY(namespace_id) REFERENCES scanipy_accepted_inputs.registry_namespaces(id),
  FOREIGN KEY(org_id,codebase_id,request_id) REFERENCES scanipy_execution.scan_requests(org_id,codebase_id,id),
  FOREIGN KEY(namespace_id,bundle_id,accepted_content_digest)
    REFERENCES scanipy_accepted_inputs.bundle_versions(namespace_id,id,accepted_content_digest),
  FOREIGN KEY(namespace_id,policy_kind,policy_event_id)
    REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id),
  FOREIGN KEY(namespace_id,admission_kind,admission_event_id)
    REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id),
  FOREIGN KEY(namespace_id,approval_kind,approval_event_id)
    REFERENCES scanipy_accepted_inputs.authority_events(namespace_id,kind,id)
);
ALTER TABLE scanipy_accepted_inputs.authority_events ADD CONSTRAINT accepted_request_binding_fk
  FOREIGN KEY(namespace_id,org_id,codebase_id,request_id)
    REFERENCES scanipy_accepted_inputs.request_bundle_bindings(namespace_id,org_id,codebase_id,request_id);
