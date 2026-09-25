CREATE FUNCTION scanipy_execution.immutable_history_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE old_row jsonb; new_row jsonb; mutable text[];
BEGIN
  IF TG_OP IN ('DELETE','TRUNCATE') THEN RAISE EXCEPTION 'execution history cannot be deleted'; END IF;
  old_row:=to_jsonb(OLD); new_row:=to_jsonb(NEW);
  IF old_row=new_row THEN RETURN NEW; END IF;
  -- PostgreSQL supplies SQL NULL, not an empty array, for a zero-arg trigger.
  -- NULL subtraction would erase both sides of the immutable comparison.
  mutable:=coalesce(TG_ARGV,ARRAY[]::text[]);
  IF (old_row-mutable) IS DISTINCT FROM (new_row-mutable) THEN
    RAISE EXCEPTION 'immutable execution content';
  END IF;
  IF TG_TABLE_NAME IN ('detector_runs','work_attempts','work_items')
     AND old_row->>'state' IN ('completed','failed','interrupted','cancelled') THEN
    RAISE EXCEPTION 'terminal execution history is immutable';
  END IF;
  IF old_row ? 'revision' AND (new_row->>'revision')::bigint <= (old_row->>'revision')::bigint THEN
    RAISE EXCEPTION 'coordination revision must advance';
  END IF;
  IF TG_TABLE_NAME='source_captures' AND (
    old_row->>'retention_state'='retired' OR
    (old_row->>'retention_state'='retiring' AND new_row->>'retention_state'='active') OR
    (new_row->>'cleanup_token')::bigint < (old_row->>'cleanup_token')::bigint) THEN
    RAISE EXCEPTION 'source retirement is irreversible';
  END IF;
  IF TG_TABLE_NAME='capture_leases' AND old_row->>'released_at' IS NOT NULL THEN
    RAISE EXCEPTION 'released lease is immutable';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION scanipy_execution.immutable_history_guard() FROM PUBLIC;
