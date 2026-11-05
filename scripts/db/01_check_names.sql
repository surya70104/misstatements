-- OAK Audit Misstatements Rollup: database pre-check and state report. READ-ONLY.
--
-- Run it before 02_create.sql, and again if 02_create.sql ever stops part-way. It reports:
--   1. who you are connected as and the server version;
--   2. whether each name this project would create already exists;
--   3. for any that exist: the setup comment 02_create.sql writes (or none), whether a role
--      can log in, and for databases the owner and whether it accepts connections.
-- It creates, changes and deletes nothing: it runs inside a READ ONLY transaction that is
-- rolled back. It reads only catalogue information; no password or password hash is shown.
--
-- Run (psql asks for the password itself; nothing is stored):
--   & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5432 -U postgres -d postgres -f scripts\db\01_check_names.sql

\set ON_ERROR_STOP on
\echo 'OAK Misstatements Rollup pre-check: read-only, nothing is created or changed.'

BEGIN READ ONLY;

SELECT current_user AS connected_as,
       (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = current_user) AS is_superuser,
       current_setting('server_version') AS server_version,
       current_setting('server_version_num')::int >= 130000 AS version_13_or_later;

SELECT proposed.name AS proposed_name,
       proposed.kind,
       CASE proposed.kind
           WHEN 'role' THEN EXISTS (
               SELECT 1 FROM pg_catalog.pg_roles r WHERE lower(r.rolname) = proposed.name)
           ELSE EXISTS (
               SELECT 1 FROM pg_catalog.pg_database d WHERE lower(d.datname) = proposed.name)
       END AS already_exists
  FROM (VALUES ('oak_misstatements_owner', 'role'),
               ('oak_misstatements_app', 'role'),
               ('oak_misstatements', 'database'),
               ('oak_misstatements_test', 'database')) AS proposed(name, kind)
 ORDER BY proposed.kind DESC, proposed.name;

\echo 'Existing roles with these names (setup_note is empty unless 02_create.sql made them):'
SELECT r.rolname,
       r.rolcanlogin AS can_login,
       r.rolsuper AS is_superuser,
       r.rolcreatedb AS can_create_db,
       r.rolcreaterole AS can_create_role,
       pg_catalog.shobj_description(r.oid, 'pg_authid') AS setup_note
  FROM pg_catalog.pg_roles r
 WHERE lower(r.rolname) IN ('oak_misstatements_owner', 'oak_misstatements_app')
 ORDER BY r.rolname;

\echo 'Existing databases with these names:'
SELECT d.datname,
       pg_catalog.pg_get_userbyid(d.datdba) AS owner,
       pg_catalog.pg_encoding_to_char(d.encoding) AS encoding,
       d.datallowconn AS accepts_connections,
       pg_catalog.shobj_description(d.oid, 'pg_database') AS setup_note
  FROM pg_catalog.pg_database d
 WHERE lower(d.datname) IN ('oak_misstatements', 'oak_misstatements_test')
 ORDER BY d.datname;

ROLLBACK;
\echo 'Pre-check finished. Nothing was changed.'
