-- Normalize NEW objects only, including hostile ALTER DEFAULT PRIVILEGES.
-- No legacy table/schema ACL is changed. No CASCADE hides existing dependencies.
DO $$
DECLARE object record; permission record; principal text;
BEGIN
  FOR object IN
    SELECT 'SCHEMA' AS kind,format('%I',n.nspname) AS name,n.nspowner AS owner,
      coalesce(n.nspacl,acldefault('n',n.nspowner)) AS permissions
      FROM pg_catalog.pg_namespace n WHERE n.nspname='scanipy_execution'
    UNION ALL
    SELECT 'TABLE',format('%I.%I',n.nspname,c.relname),c.relowner,
      coalesce(c.relacl,acldefault('r',c.relowner))
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='scanipy_execution' AND c.relkind='r'
    UNION ALL
    SELECT 'FUNCTION',format('%I.%I(%s)',n.nspname,p.proname,pg_catalog.pg_get_function_identity_arguments(p.oid)),p.proowner,
      coalesce(p.proacl,acldefault('f',p.proowner))
      FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='scanipy_execution'
  LOOP
    FOR permission IN SELECT DISTINCT grantee FROM pg_catalog.aclexplode(object.permissions) WHERE grantee<>object.owner LOOP
      principal:=CASE WHEN permission.grantee=0 THEN 'PUBLIC' ELSE format('%I',pg_catalog.pg_get_userbyid(permission.grantee)) END;
      EXECUTE format('REVOKE ALL ON %s %s FROM %s',object.kind,object.name,principal);
    END LOOP;
  END LOOP;
END $$;
