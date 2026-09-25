CREATE TABLE scanipy_execution.scan_requests (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, lineage_id uuid NOT NULL,
  predecessor_request_id uuid, idempotency_key text NOT NULL CHECK (idempotency_key<>''),
  request_schema text NOT NULL CHECK(request_schema='scanipy-execution/request/1'),
  request_bytes bytea NOT NULL CHECK(octet_length(request_bytes)<=1048576),
  request_digest bytea NOT NULL CHECK(octet_length(request_digest)=32),
  planned_policy_schema text NOT NULL CHECK(planned_policy_schema='scanipy-execution/planned-policy/1'),
  planned_policy_bytes bytea NOT NULL CHECK(octet_length(planned_policy_bytes)<=1048576),
  planned_policy_digest bytea NOT NULL CHECK(octet_length(planned_policy_digest)=32),
  created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
  capture_state text NOT NULL DEFAULT 'pending' CHECK(capture_state IN ('pending','running','completed','failed','cancelled')),
  detection_state text NOT NULL DEFAULT 'pending' CHECK(detection_state IN ('pending','running','completed','failed','cancelled')),
  identity_state text NOT NULL DEFAULT 'pending' CHECK(identity_state IN ('pending','running','completed','failed','cancelled')),
  finalization_state text NOT NULL DEFAULT 'pending' CHECK(finalization_state='pending'),
  lifecycle_state text NOT NULL DEFAULT 'pending' CHECK(lifecycle_state='pending'),
  active_detection_work_id uuid, error_reference jsonb, cancellation_bytes bytea,
  UNIQUE(org_id,idempotency_key), UNIQUE(org_id,codebase_id,id),
  UNIQUE(org_id,codebase_id,lineage_id,id),
  FOREIGN KEY(org_id,codebase_id) REFERENCES public.codebases(org_id,id),
  FOREIGN KEY(org_id,codebase_id,lineage_id,predecessor_request_id)
    REFERENCES scanipy_execution.scan_requests(org_id,codebase_id,lineage_id,id),
  CHECK(predecessor_request_id IS NULL OR predecessor_request_id<>id)
);
CREATE TABLE scanipy_execution.source_captures (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, owner_request_id uuid NOT NULL UNIQUE,
  resolved_commit text NOT NULL CHECK(resolved_commit ~ '^[0-9a-f]{40}$' AND resolved_commit<>repeat('0',40)),
  commit_algorithm text NOT NULL CHECK(commit_algorithm='git-sha1'),
  tree_algorithm text NOT NULL CHECK(tree_algorithm='sha256-length-prefixed-path-and-content-v1'),
  tree_digest bytea NOT NULL CHECK(octet_length(tree_digest)=32),
  inventory_schema text NOT NULL CHECK(inventory_schema='scanipy-execution/source-inventory/1'),
  inventory_bytes bytea NOT NULL CHECK(octet_length(inventory_bytes)<=1048576),
  inventory_digest bytea NOT NULL CHECK(octet_length(inventory_digest)=32),
  storage_object_id uuid NOT NULL UNIQUE, storage_reference text NOT NULL UNIQUE CHECK(storage_reference<>''),
  created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  retain_seconds integer NOT NULL CHECK(retain_seconds BETWEEN 0 AND 315360000),
  retain_until timestamptz NOT NULL,
  retention_state text NOT NULL DEFAULT 'active' CHECK(retention_state IN ('active','retiring','retired')),
  cleanup_token bigint NOT NULL DEFAULT 0 CHECK(cleanup_token>=0),
  cleanup_expires_at timestamptz, retirement_bytes bytea, retirement_digest bytea,
  revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
  UNIQUE(org_id,codebase_id,owner_request_id,id),
  FOREIGN KEY(org_id,codebase_id,owner_request_id) REFERENCES scanipy_execution.scan_requests(org_id,codebase_id,id),
  CHECK(retirement_digest IS NULL OR octet_length(retirement_digest)=32),
  CHECK((retention_state='active' AND cleanup_token=0 AND cleanup_expires_at IS NULL AND retirement_bytes IS NULL)
     OR (retention_state='retiring' AND cleanup_token>0 AND cleanup_expires_at IS NOT NULL AND retirement_bytes IS NULL)
     OR (retention_state='retired' AND cleanup_token>0 AND cleanup_expires_at IS NULL AND retirement_bytes IS NOT NULL))
);
CREATE TABLE scanipy_execution.scan_seals (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, request_id uuid NOT NULL UNIQUE, capture_id uuid NOT NULL,
  seal_schema text NOT NULL CHECK(seal_schema='scanipy-execution/seal/1'),
  seal_bytes bytea NOT NULL CHECK(octet_length(seal_bytes)<=1048576),
  seal_digest bytea NOT NULL CHECK(octet_length(seal_digest)=32),
  s_version text NOT NULL CHECK(s_version<>''),
  accepted_content_bytes bytea NOT NULL CHECK(octet_length(accepted_content_bytes)<=1048576),
  accepted_content_digest bytea NOT NULL CHECK(octet_length(accepted_content_digest)=32),
  accepted_spec_bytes bytea NOT NULL,
  accepted_detector_bytes bytea[] NOT NULL, accepted_rule_bytes bytea[] NOT NULL,
  acceptance_evidence_bytes bytea NOT NULL CHECK(octet_length(acceptance_evidence_bytes)<=1048576),
  acceptance_evidence_digest bytea NOT NULL CHECK(octet_length(acceptance_evidence_digest)=32),
  created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  UNIQUE(org_id,codebase_id,request_id,capture_id,id),
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id)
    REFERENCES scanipy_execution.source_captures(org_id,codebase_id,owner_request_id,id)
);
CREATE TABLE scanipy_execution.work_items (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, request_id uuid NOT NULL,
  kind text NOT NULL CHECK(kind IN ('capture_detection','identity')),
  occurrence_id uuid, capture_id uuid,
  idempotency_key text NOT NULL CHECK(idempotency_key<>''),
  payload_schema text NOT NULL CHECK(payload_schema='scanipy-execution/work-payload/1'),
  payload_bytes bytea NOT NULL CHECK(octet_length(payload_bytes)<=1048576),
  payload_digest bytea NOT NULL CHECK(octet_length(payload_digest)=32),
  retry_policy_bytes bytea NOT NULL CHECK(octet_length(retry_policy_bytes)<=1048576),
  max_attempts integer NOT NULL CHECK(max_attempts BETWEEN 1 AND 16),
  lease_seconds integer NOT NULL CHECK(lease_seconds BETWEEN 1 AND 900),
  initial_backoff_seconds integer NOT NULL CHECK(initial_backoff_seconds BETWEEN 0 AND 3600),
  max_backoff_seconds integer NOT NULL CHECK(max_backoff_seconds BETWEEN initial_backoff_seconds AND 86400),
  created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','completed','failed','cancelled')),
  active_attempt_id uuid, fencing_token bigint NOT NULL DEFAULT 0 CHECK(fencing_token>=0),
  next_attempt_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  revision bigint NOT NULL DEFAULT 0 CHECK(revision>=0),
  terminal_bytes bytea, terminal_digest bytea,
  UNIQUE(org_id,idempotency_key), UNIQUE(org_id,codebase_id,request_id,id),
  UNIQUE(org_id,codebase_id,request_id,kind,id), UNIQUE(occurrence_id),
  FOREIGN KEY(org_id,codebase_id,request_id) REFERENCES scanipy_execution.scan_requests(org_id,codebase_id,id),
  CHECK((kind='capture_detection' AND occurrence_id IS NULL AND capture_id IS NULL)
     OR (kind='identity' AND occurrence_id IS NOT NULL AND capture_id IS NOT NULL)),
  CHECK((state='running')=(active_attempt_id IS NOT NULL)),
  CHECK((state IN ('completed','failed','cancelled'))=(terminal_bytes IS NOT NULL)),
  CHECK(terminal_digest IS NULL OR octet_length(terminal_digest)=32)
);
CREATE UNIQUE INDEX execution_one_detection_work ON scanipy_execution.work_items(request_id) WHERE kind='capture_detection';
CREATE INDEX execution_eligible_work ON scanipy_execution.work_items(org_id,kind,next_attempt_at,created_at,id) WHERE state='pending';
CREATE TABLE scanipy_execution.work_attempts (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, request_id uuid NOT NULL, work_item_id uuid NOT NULL,
  kind text NOT NULL CHECK(kind IN ('capture_detection','identity')),
  attempt_number integer NOT NULL CHECK(attempt_number BETWEEN 1 AND 16),
  fencing_token bigint NOT NULL CHECK(fencing_token>0),
  assignment_id text NOT NULL CHECK(assignment_id<>''),
  policy_schema text NOT NULL CHECK(policy_schema='scanipy-execution/attempt-policy/1'),
  policy_bytes bytea NOT NULL CHECK(octet_length(policy_bytes)<=1048576),
  policy_digest bytea NOT NULL CHECK(octet_length(policy_digest)=32),
  started_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  lease_expires_at timestamptz NOT NULL,
  state text NOT NULL DEFAULT 'running' CHECK(state IN ('running','completed','failed','interrupted','cancelled')),
  terminal_at timestamptz, result_schema text, result_bytes bytea, result_digest bytea,
  UNIQUE(work_item_id,attempt_number), UNIQUE(work_item_id,fencing_token),
  UNIQUE(org_id,codebase_id,request_id,work_item_id,id),
  UNIQUE(org_id,codebase_id,request_id,work_item_id,fencing_token,id),
  FOREIGN KEY(org_id,codebase_id,request_id,kind,work_item_id)
    REFERENCES scanipy_execution.work_items(org_id,codebase_id,request_id,kind,id),
  CHECK((state='running')=(terminal_at IS NULL)),
  CHECK((state='running')=(result_bytes IS NULL)),
  CHECK(result_bytes IS NULL OR octet_length(result_bytes)<=1048576),
  CHECK(result_digest IS NULL OR octet_length(result_digest)=32)
);
ALTER TABLE scanipy_execution.work_items ADD CONSTRAINT execution_active_attempt_fk
  FOREIGN KEY(org_id,codebase_id,request_id,id,active_attempt_id)
  REFERENCES scanipy_execution.work_attempts(org_id,codebase_id,request_id,work_item_id,id);
ALTER TABLE scanipy_execution.scan_requests ADD CONSTRAINT execution_detection_work_fk
  FOREIGN KEY(org_id,codebase_id,id,active_detection_work_id)
  REFERENCES scanipy_execution.work_items(org_id,codebase_id,request_id,id);
CREATE TABLE scanipy_execution.detector_runs (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, request_id uuid NOT NULL,
  capture_id uuid NOT NULL, seal_id uuid NOT NULL, work_item_id uuid NOT NULL, work_attempt_id uuid NOT NULL,
  kind text NOT NULL DEFAULT 'capture_detection' CHECK(kind='capture_detection'),
  detector_binding_key text NOT NULL CHECK(detector_binding_key<>''), run_ordinal bigint NOT NULL CHECK(run_ordinal>=0),
  supersedes_run_id uuid,
  input_schema text NOT NULL CHECK(input_schema='scanipy-execution/run-input/1'),
  input_bytes bytea NOT NULL CHECK(octet_length(input_bytes)<=1048576),
  input_digest bytea NOT NULL CHECK(octet_length(input_digest)=32),
  created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  state text NOT NULL DEFAULT 'running' CHECK(state IN ('pending','running','completed','failed','interrupted')),
  terminal_at timestamptz, result_schema text, result_bytes bytea, result_digest bytea,
  stdout bytea, stderr bytea, failure_prefix bytea,
  result_count integer NOT NULL DEFAULT 0 CHECK(result_count BETWEEN 0 AND 10000), inventory_digest bytea,
  UNIQUE(work_attempt_id,detector_binding_key,run_ordinal),
  UNIQUE(org_id,codebase_id,request_id,capture_id,id),
  UNIQUE(org_id,codebase_id,request_id,capture_id,detector_binding_key,id),
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id,detector_binding_key,supersedes_run_id)
    REFERENCES scanipy_execution.detector_runs(org_id,codebase_id,request_id,capture_id,detector_binding_key,id),
  CHECK(supersedes_run_id IS NULL OR supersedes_run_id<>id),
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id,seal_id)
    REFERENCES scanipy_execution.scan_seals(org_id,codebase_id,request_id,capture_id,id),
  FOREIGN KEY(org_id,codebase_id,request_id,kind,work_item_id)
    REFERENCES scanipy_execution.work_items(org_id,codebase_id,request_id,kind,id),
  FOREIGN KEY(org_id,codebase_id,request_id,work_item_id,work_attempt_id)
    REFERENCES scanipy_execution.work_attempts(org_id,codebase_id,request_id,work_item_id,id),
  CHECK((state IN ('pending','running'))=(terminal_at IS NULL)),
  CHECK((state IN ('pending','running'))=(result_bytes IS NULL)),
  CHECK(result_bytes IS NULL OR octet_length(result_bytes)<=1048576),
  CHECK(result_digest IS NULL OR octet_length(result_digest)=32),
  CHECK(inventory_digest IS NULL OR octet_length(inventory_digest)=32),
  CHECK(failure_prefix IS NULL OR octet_length(failure_prefix)<=65536)
);
CREATE UNIQUE INDEX execution_completed_binding ON scanipy_execution.detector_runs(request_id,detector_binding_key) WHERE state='completed';
CREATE UNIQUE INDEX detector_run_supersession_once
  ON scanipy_execution.detector_runs(supersedes_run_id) WHERE supersedes_run_id IS NOT NULL;
CREATE TABLE scanipy_execution.detection_occurrences (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, request_id uuid NOT NULL, capture_id uuid NOT NULL, detector_run_id uuid NOT NULL,
  adapter_result_key text NOT NULL CHECK(adapter_result_key<>''), duplicate_ordinal bigint NOT NULL CHECK(duplicate_ordinal>=0),
  tool_ordinal bigint NOT NULL CHECK(tool_ordinal>=0),
  raw_result_bytes bytea NOT NULL, raw_result_digest bytea NOT NULL CHECK(octet_length(raw_result_digest)=32),
  witness_bytes bytea, witness_digest bytea,
  engine text NOT NULL CHECK(engine IN ('ifds','ide','semgrep','cpg-query','external')),
  origin text NOT NULL, determinism_partition text NOT NULL,
  detector_id text NOT NULL CHECK(detector_id<>''), class_id text NOT NULL CHECK(class_id<>''), language text NOT NULL CHECK(language<>''),
  rule_id text NOT NULL CHECK(rule_id<>''), rule_semantic_digest bytea NOT NULL CHECK(octet_length(rule_semantic_digest)=32),
  s_version text NOT NULL CHECK(s_version<>''), env_digest text NOT NULL CHECK(env_digest ~ '^sha256:[0-9a-f]{64}$'),
  full_env_digest text CHECK(full_env_digest ~ '^sha256:[0-9a-f]{64}$'),
  cwe text, severity text NOT NULL CHECK(severity IN ('info','low','medium','high','critical')), message text NOT NULL,
  physical_location jsonb NOT NULL,
  metadata_bytes bytea NOT NULL CHECK(octet_length(metadata_bytes)<=1048576),
  created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  UNIQUE(detector_run_id,adapter_result_key,duplicate_ordinal), UNIQUE(detector_run_id,tool_ordinal),
  UNIQUE(org_id,codebase_id,request_id,capture_id,id),
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id,detector_run_id)
    REFERENCES scanipy_execution.detector_runs(org_id,codebase_id,request_id,capture_id,id),
  CHECK(origin=CASE WHEN engine IN ('ifds','ide') THEN 'deterministic-core' ELSE 'oracle-passthrough' END),
  CHECK(determinism_partition=origin), CHECK((witness_bytes IS NULL)=(witness_digest IS NULL)),
  CHECK(witness_digest IS NULL OR octet_length(witness_digest)=32),
  CHECK(octet_length(raw_result_bytes)+coalesce(octet_length(witness_bytes),0)<=16777216)
);
ALTER TABLE scanipy_execution.work_items ADD CONSTRAINT execution_identity_occurrence_fk
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id,occurrence_id)
  REFERENCES scanipy_execution.detection_occurrences(org_id,codebase_id,request_id,capture_id,id);
CREATE TABLE scanipy_execution.capture_leases (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  org_id uuid NOT NULL, codebase_id uuid NOT NULL, request_id uuid NOT NULL, capture_id uuid NOT NULL,
  work_item_id uuid NOT NULL, work_attempt_id uuid NOT NULL, fencing_token bigint NOT NULL CHECK(fencing_token>0),
  acquired_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(), expires_at timestamptz NOT NULL,
  released_at timestamptz, release_bytes bytea, release_digest bytea,
  UNIQUE(work_attempt_id),
  FOREIGN KEY(org_id,codebase_id,request_id,capture_id)
    REFERENCES scanipy_execution.source_captures(org_id,codebase_id,owner_request_id,id),
  FOREIGN KEY(org_id,codebase_id,request_id,work_item_id,fencing_token,work_attempt_id)
    REFERENCES scanipy_execution.work_attempts(org_id,codebase_id,request_id,work_item_id,fencing_token,id),
  CHECK((released_at IS NULL)=(release_bytes IS NULL)),
  CHECK(release_digest IS NULL OR octet_length(release_digest)=32)
);
