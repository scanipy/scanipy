-- Frozen storage protocol v1. These helpers are owner-only, not runtime RPCs.
CREATE FUNCTION scanipy_execution.v1_require(ok boolean, reason text) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
BEGIN IF ok IS DISTINCT FROM TRUE THEN RAISE EXCEPTION '%',reason USING ERRCODE='22023'; END IF; END $$;

CREATE FUNCTION scanipy_execution.v1_org(p_org uuid) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
BEGIN
  PERFORM scanipy_execution.v1_require(
    p_org IS NOT NULL AND p_org=NULLIF(pg_catalog.current_setting('app.org_id',true),'')::uuid,
    'missing or mismatched tenant binding');
END $$;

CREATE FUNCTION scanipy_execution.v1_byte_array(v bytea[]) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
BEGIN
  -- JSON/Python lists are one-dimensional and 1-based on the SQL wire.
  -- Cardinality alone is unsafe: out-of-range nullable witness reads are NULL.
  PERFORM scanipy_execution.v1_require(v IS NOT NULL AND
    (cardinality(v)=0 OR (array_ndims(v)=1 AND array_lower(v,1)=1)),
    'byte-array wire requires one dimension with lower bound 1, or empty');
END $$;

CREATE FUNCTION scanipy_execution.v1_canonical(v json, depth integer) RETURNS text
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE kind text; output text; item record; previous_key text; token text;
BEGIN
  PERFORM scanipy_execution.v1_require(depth<=32,'envelope nesting exceeds 32');
  kind:=pg_catalog.json_typeof(v);
  IF kind='object' THEN
    output:='{';
    FOR item IN SELECT key,value FROM pg_catalog.json_each(v) ORDER BY key COLLATE "C" LOOP
      PERFORM scanipy_execution.v1_require(previous_key IS NULL OR item.key<>previous_key,'duplicate JSON key');
      -- json_each/text extraction rejects NUL and lone surrogates before jsonb.
      IF previous_key IS NOT NULL THEN output:=output||','; END IF;
      previous_key:=item.key;
      output:=output||pg_catalog.to_json(item.key)::text||':'||scanipy_execution.v1_canonical(item.value,depth+1);
    END LOOP;
    RETURN output||'}';
  ELSIF kind='array' THEN
    output:='[';
    FOR item IN SELECT value,ordinality FROM pg_catalog.json_array_elements(v) WITH ORDINALITY LOOP
      IF item.ordinality>1 THEN output:=output||','; END IF;
      output:=output||scanipy_execution.v1_canonical(item.value,depth+1);
    END LOOP;
    RETURN output||']';
  ELSIF kind='string' THEN
    RETURN pg_catalog.to_json(v#>>'{}')::text;
  ELSIF kind='number' THEN
    token:=v::text;
    PERFORM scanipy_execution.v1_require(length(token)<=20 AND token ~ '^-?(0|[1-9][0-9]*)$','unsupported integer token');
    RETURN (token::bigint)::text;
  ELSIF kind IN ('boolean','null') THEN RETURN v::text;
  END IF;
  RAISE EXCEPTION 'unsupported JSON value' USING ERRCODE='22023';
END $$;

CREATE FUNCTION scanipy_execution.v1_bytes(v jsonb) RETURNS bytea
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
SELECT pg_catalog.convert_to(scanipy_execution.v1_canonical(v::json,0),'UTF8') $$;

CREATE FUNCTION scanipy_execution.v1_digest(name text, data bytea) RETURNS bytea
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
SELECT pg_catalog.sha256(pg_catalog.convert_to('scanipy-execution/'||name||'/1'||chr(10),'UTF8')||data) $$;

CREATE FUNCTION scanipy_execution.v1_shape(v jsonb, shape jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE spec text; token text; item record; low bigint; high bigint; ok boolean;
BEGIN
  IF jsonb_typeof(shape)='object' THEN
    IF shape ? '$nullable' THEN
      IF v<>'null'::jsonb THEN PERFORM scanipy_execution.v1_shape(v,shape->'$nullable'); END IF;
    ELSIF shape ? '$enum' THEN
      PERFORM scanipy_execution.v1_require((shape->'$enum') @> jsonb_build_array(v),'invalid enum');
    ELSIF shape ? '$array' THEN
      PERFORM scanipy_execution.v1_require(jsonb_typeof(v)='array','expected array');
      FOR item IN SELECT value FROM jsonb_array_elements(v) LOOP
        PERFORM scanipy_execution.v1_shape(item.value,shape->'$array');
      END LOOP;
    ELSE
      PERFORM scanipy_execution.v1_require(jsonb_typeof(v)='object','expected object');
      PERFORM scanipy_execution.v1_require(
        (SELECT array_agg(key ORDER BY key COLLATE "C") FROM jsonb_object_keys(v) key)=
        (SELECT array_agg(key ORDER BY key COLLATE "C") FROM jsonb_object_keys(shape) key),
        'missing or unknown envelope field');
      FOR item IN SELECT key,value FROM jsonb_each(shape) LOOP
        PERFORM scanipy_execution.v1_shape(v->item.key,item.value);
      END LOOP;
    END IF;
    RETURN;
  END IF;
  spec:=shape#>>'{}'; token:=v#>>'{}'; ok:=false;
  IF spec='bool' THEN ok:=jsonb_typeof(v)='boolean';
  ELSIF spec IN ('nat','positive') OR spec LIKE 'int:%' THEN
    PERFORM scanipy_execution.v1_require(jsonb_typeof(v)='number','expected integer');
    low:=CASE WHEN spec='nat' THEN 0 ELSE 1 END; high:=9223372036854775807;
    IF spec LIKE 'int:%' THEN low:=split_part(spec,':',2)::bigint; high:=split_part(spec,':',3)::bigint; END IF;
    ok:=token::bigint BETWEEN low AND high;
  ELSIF jsonb_typeof(v)='string' THEN
    CASE spec
      WHEN 'text' THEN ok:=true;
      WHEN 'nonempty' THEN ok:=token<>'';
      WHEN 'digest' THEN ok:=token ~ '^[0-9a-f]{64}$';
      WHEN 'env' THEN ok:=token ~ '^sha256:[0-9a-f]{64}$';
      WHEN 'commit' THEN ok:=token ~ '^[0-9a-f]{40}$' AND token<>repeat('0',40);
      WHEN 'uuid' THEN ok:=token ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$';
      WHEN 'path' THEN ok:=token<>'' AND position(chr(92) IN token)=0 AND NOT EXISTS(
        SELECT 1 FROM unnest(string_to_array(token,'/')) part WHERE part IN ('','.','..'));
      ELSE RAISE EXCEPTION 'unknown shape validator';
    END CASE;
  END IF;
  PERFORM scanipy_execution.v1_require(ok,'invalid '||spec||' value');
END $$;

CREATE FUNCTION scanipy_execution.v1_unique(v jsonb, label text) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
BEGIN
  PERFORM scanipy_execution.v1_require(
    jsonb_array_length(v)=(SELECT count(DISTINCT value) FROM jsonb_array_elements(v)),
    'duplicate '||label);
END $$;

CREATE FUNCTION scanipy_execution.v1_location(v jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE start_line bigint; start_col bigint; end_line bigint; end_col bigint; expected text;
BEGIN
  start_line:=(v->>'start_line')::bigint; start_col:=(v->>'start_column')::bigint;
  end_line:=(v->>'end_line')::bigint; end_col:=(v->>'end_column')::bigint;
  expected:=CASE WHEN v->>'path' IS NOT NULL AND start_line IS NOT NULL THEN 'known'
    WHEN v->>'path' IS NOT NULL OR start_line IS NOT NULL OR start_col IS NOT NULL OR end_line IS NOT NULL OR end_col IS NOT NULL THEN 'partial'
    ELSE 'unknown' END;
  PERFORM scanipy_execution.v1_require(v->>'status'=expected,'location status contradicts evidence');
  PERFORM scanipy_execution.v1_require((start_col IS NULL OR start_line IS NOT NULL)
    AND (end_col IS NULL OR end_line IS NOT NULL),'column requires observed line');
  PERFORM scanipy_execution.v1_require(end_line IS NULL OR (start_line IS NOT NULL AND end_line>=start_line),'end requires observed ordered start');
  PERFORM scanipy_execution.v1_require(end_line IS DISTINCT FROM start_line OR end_col IS NULL
    OR (start_col IS NOT NULL AND end_col>=start_col),'same-line end requires observed ordered start column');
END $$;

CREATE FUNCTION scanipy_execution.v1_semantic(name text, v jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE retry jsonb; policy jsonb; item record; binding record; descriptor jsonb; names jsonb; canonical_paths jsonb;
BEGIN
  IF name IN ('request','retry-policy') THEN
    retry:=CASE WHEN name='request' THEN v->'retry_policy' ELSE v END;
    PERFORM scanipy_execution.v1_require((retry->>'initial_backoff_seconds')::int <= (retry->>'max_backoff_seconds')::int,'initial backoff exceeds maximum');
  END IF;
  IF name IN ('request','work-payload','planned-policy') THEN
    policy:=CASE WHEN name='work-payload' THEN v->'policy' ELSE v->'identity_policy' END;
    PERFORM scanipy_execution.v1_require(policy->>'mode'<>'not-applicable' OR policy->>'reason' IS NOT NULL,'not-applicable requires policy reason');
  END IF;
  IF name='work-payload' THEN
    PERFORM scanipy_execution.v1_require((v->>'kind'='identity')=(v->>'occurrence_id' IS NOT NULL),'work kind and occurrence disagree');
  ELSIF name='source-inventory' THEN
    SELECT coalesce(jsonb_agg(value->'path'),'[]'::jsonb),coalesce(jsonb_agg(value->'path' ORDER BY value->>'path' COLLATE "C"),'[]'::jsonb)
      INTO names,canonical_paths FROM jsonb_array_elements(v->'files');
    PERFORM scanipy_execution.v1_unique(names,'file path');
    PERFORM scanipy_execution.v1_require(names=canonical_paths,'inventory paths must be sorted');
  ELSIF name IN ('seal','planned-policy') THEN
    IF name='seal' THEN PERFORM scanipy_execution.v1_unique(v->'intended_files','intended file'); END IF;
    SELECT coalesce(jsonb_agg(value->'key'),'[]'::jsonb) INTO names FROM jsonb_array_elements(v->'bindings');
    PERFORM scanipy_execution.v1_unique(names,'binding key');
    FOR binding IN SELECT value FROM jsonb_array_elements(v->'bindings') LOOP
      PERFORM scanipy_execution.v1_require(jsonb_array_length(binding.value->'engines')>0 AND jsonb_array_length(binding.value->'rules')>0,'binding requires engines and rules');
      PERFORM scanipy_execution.v1_unique(binding.value->'engines','engine');
      SELECT jsonb_agg(value->'rule_id') INTO names FROM jsonb_array_elements(binding.value->'rules');
      PERFORM scanipy_execution.v1_unique(names,'rule');
    END LOOP;
  END IF;
  IF name IN ('detection-batch','occurrence-inventory') THEN
    PERFORM scanipy_execution.v1_require(jsonb_array_length(v->'occurrences')<=10000,'occurrence count limit');
    SELECT coalesce(jsonb_agg(jsonb_build_array(value->'result_key',value->'duplicate_ordinal')),'[]'::jsonb)
      INTO names FROM jsonb_array_elements(v->'occurrences');
    PERFORM scanipy_execution.v1_unique(names,'occurrence key');
    FOR item IN SELECT value,ordinality FROM jsonb_array_elements(v->'occurrences') WITH ORDINALITY LOOP
      PERFORM scanipy_execution.v1_require((item.value->>'tool_ordinal')::bigint=item.ordinality-1,'tool ordinal order');
      PERFORM scanipy_execution.v1_location(item.value->'location');
    END LOOP;
  END IF;
  IF name='detection-batch' THEN
    PERFORM scanipy_execution.v1_unique(v->'coverage'->'files','covered file');
    PERFORM scanipy_execution.v1_unique(v->'coverage'->'rules','covered rule');
    PERFORM scanipy_execution.v1_require(v->>'status'<>'completed' OR (
      v->'coverage'->>'status'='complete' AND jsonb_array_length(v->'coverage'->'errors')=0),'completed run requires complete coverage');
    names:=jsonb_build_object('schema','scanipy-execution/occurrence-inventory/1','occurrences',v->'occurrences');
    PERFORM scanipy_execution.v1_require(v->>'inventory_digest'=encode(scanipy_execution.v1_digest('occurrence-inventory',scanipy_execution.v1_bytes(names)),'hex'),'inventory digest mismatch');
  ELSIF name='attempt-result' THEN
    PERFORM scanipy_execution.v1_unique(v->'completed_run_ids','completed run ID');
    IF v->'identity'<>'null'::jsonb THEN
      FOREACH names IN ARRAY ARRAY[v->'identity'->'cpg_order',v->'identity'->'slice'] LOOP
        descriptor:=names;
        IF descriptor->>'status'='completed' THEN
          PERFORM scanipy_execution.v1_require(descriptor->>'digest' IS NOT NULL AND descriptor->>'fingerprint_class' IS NOT NULL AND descriptor->>'namespace' IS NOT NULL,'completed artifact requires independent evidence');
        ELSE
          PERFORM scanipy_execution.v1_require(descriptor->>'digest' IS NULL AND descriptor->>'fingerprint_class' IS NULL AND descriptor->>'namespace' IS NULL,'uncomputed artifact cannot assert evidence');
        END IF;
      END LOOP;
    END IF;
    PERFORM scanipy_execution.v1_require(v->>'status'<>'completed' OR (v->'retryable'='false'::jsonb AND v->'error'='null'::jsonb),'completed attempt cannot retry/error');
    PERFORM scanipy_execution.v1_require(v->>'status'<>'failed' OR v->'error'<>'null'::jsonb,'failed attempt requires error');
  END IF;
END $$;

CREATE FUNCTION scanipy_execution.v1_preserved_shape(v json, shape jsonb) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE item record; kind text:=json_typeof(v); spec text;
BEGIN
  -- Only type/key checks on preserved json. No jsonb projection can discard
  -- duplicate keys, nonportable numeric spellings or unknown nested fields.
  IF jsonb_typeof(shape)='object' THEN
    IF shape ? '$nullable' THEN
      IF kind<>'null' THEN PERFORM scanipy_execution.v1_preserved_shape(v,shape->'$nullable'); END IF;
    ELSIF shape ? '$enum' THEN
      PERFORM scanipy_execution.v1_require(kind IN ('string','number'),'invalid enum type');
    ELSIF shape ? '$array' THEN
      PERFORM scanipy_execution.v1_require(kind='array','expected array');
      FOR item IN SELECT value FROM json_array_elements(v) LOOP
        PERFORM scanipy_execution.v1_preserved_shape(item.value,shape->'$array');
      END LOOP;
    ELSE
      PERFORM scanipy_execution.v1_require(kind='object','expected object');
      PERFORM scanipy_execution.v1_require(
        (SELECT array_agg(key ORDER BY key COLLATE "C") FROM json_object_keys(v) key)=
        (SELECT array_agg(key ORDER BY key COLLATE "C") FROM jsonb_object_keys(shape) key),
        'missing, duplicate or unknown envelope field');
      FOR item IN SELECT key,value FROM json_each(v) LOOP
        PERFORM scanipy_execution.v1_preserved_shape(item.value,shape->item.key);
      END LOOP;
    END IF;
  ELSE
    spec:=shape#>>'{}';
    PERFORM scanipy_execution.v1_require(kind=CASE WHEN spec='bool' THEN 'boolean'
      WHEN spec IN ('nat','positive') OR spec LIKE 'int:%' THEN 'number' ELSE 'string' END,
      'invalid preserved scalar type');
  END IF;
END $$;

CREATE FUNCTION scanipy_execution.v1_envelope(name text, data bytea, digest bytea) RETURNS jsonb
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,scanipy_execution,pg_temp AS $$
DECLARE original text; parsed json; result jsonb; shape jsonb;
BEGIN
  PERFORM scanipy_execution.v1_require(data IS NOT NULL AND octet_length(data)<=1048576,'envelope size');
  shape:=scanipy_execution.v1_shapes()->name;
  PERFORM scanipy_execution.v1_require(shape IS NOT NULL,'unsupported envelope schema');
  original:=convert_from(data,'UTF8'); parsed:=original::json;
  PERFORM scanipy_execution.v1_preserved_shape(parsed,shape);
  PERFORM scanipy_execution.v1_require(scanipy_execution.v1_canonical(parsed,0)=original,'noncanonical envelope bytes');
  PERFORM scanipy_execution.v1_require(digest=scanipy_execution.v1_digest(name,data),'envelope digest mismatch');
  result:=parsed::jsonb;
  PERFORM scanipy_execution.v1_shape(result,shape);
  PERFORM scanipy_execution.v1_semantic(name,result);
  RETURN result;
END $$;
