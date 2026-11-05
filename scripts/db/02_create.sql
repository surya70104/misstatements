-- OAK Audit Misstatements Rollup: create the two roles and two databases. Run once, as a
-- superuser, by a person. Never run by the application or by a test.
--
-- It first repeats the checks of 01_check_names.sql and STOPS WITHOUT CHANGING ANYTHING if:
--   * you are not a superuser,
--   * the server is older than PostgreSQL 13, or
--   * a role or database named oak_misstatements_owner, oak_misstatements_app,
--     oak_misstatements or oak_misstatements_test already exists (compared case-insensitively).
-- It never drops anything, never changes anything this run did not create, and never refers
-- to any other project's databases or roles.
--
-- The whole script cannot be one transaction (PostgreSQL cannot run CREATE DATABASE inside
-- one), so it runs in stages and is arranged to fail closed: whatever stage it stops at,
-- nothing it has created can be logged into or connected to by anyone it was not meant for.
--   1. Roles, created NOLOGIN with none of SUPERUSER, CREATEDB, CREATEROLE, REPLICATION,
--      BYPASSRLS or INHERIT, each with a comment marking it as made by this script.
--   2. Database oak_misstatements, created with ALLOW_CONNECTIONS false.
--   3. Its marker comment; every right revoked from PUBLIC; CONNECT and CREATE for the owner;
--      CONNECT for the app role; and, last, ALLOW_CONNECTIONS true.
--   4. and 5. The same for oak_misstatements_test.
--   6. Inside each database: all rights on the public schema revoked from PUBLIC.
--   7. The two roles may log in. Their passwords are still unset.
-- If any statement fails, psql stops there (ON_ERROR_STOP). Recover by hand from the
-- read-only report of 01_check_names.sql; nothing is dropped automatically.
--
-- Passwords are not set here. Afterwards, in psql, run \password oak_misstatements_owner and
-- \password oak_misstatements_app: psql hides what you type and sends only a hash.
--
-- Do not run it with psql -1 / --single-transaction (CREATE DATABASE would fail at once).
--
-- Run (psql asks for the password itself; nothing is stored):
--   & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -p 5432 -U postgres -d postgres -f scripts\db\02_create.sql

\set ON_ERROR_STOP on

SELECT coalesce((SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname = current_user), false)
           AS is_superuser,
       current_setting('server_version_num')::int >= 130000 AS version_ok,
       (SELECT count(*) FROM pg_catalog.pg_roles
         WHERE lower(rolname) IN ('oak_misstatements_owner', 'oak_misstatements_app'))
     + (SELECT count(*) FROM pg_catalog.pg_database
         WHERE lower(datname) IN ('oak_misstatements', 'oak_misstatements_test')) = 0 AS names_free
\gset

\if :is_superuser
\else
    \echo 'STOPPED: connect as a PostgreSQL superuser (for example postgres). Nothing was changed.'
    \quit
\endif
\if :version_ok
\else
    \echo 'STOPPED: PostgreSQL 13 or later is required. Nothing was changed.'
    \quit
\endif
\if :names_free
\else
    \echo 'STOPPED: a role or database named oak_misstatements_owner, oak_misstatements_app, oak_misstatements or oak_misstatements_test already exists.'
    \echo 'Run scripts\db\01_check_names.sql to see which. Nothing was changed.'
    \quit
\endif

\echo 'Stage 1: roles, NOLOGIN until the last stage'
BEGIN;
CREATE ROLE oak_misstatements_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
CREATE ROLE oak_misstatements_app   NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT;
COMMENT ON ROLE oak_misstatements_owner IS 'OAK Misstatements Rollup: runs migrations. Created by scripts/db/02_create.sql.';
COMMENT ON ROLE oak_misstatements_app   IS 'OAK Misstatements Rollup: the API, least privilege. Created by scripts/db/02_create.sql.';
COMMIT;

\echo 'Stage 2: database oak_misstatements, closed to connections'
CREATE DATABASE oak_misstatements ENCODING 'UTF8' ALLOW_CONNECTIONS false;

\echo 'Stage 3: rights on oak_misstatements, then open it'
BEGIN;
COMMENT ON DATABASE oak_misstatements IS 'OAK Misstatements Rollup. Created by scripts/db/02_create.sql.';
REVOKE ALL ON DATABASE oak_misstatements FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE oak_misstatements TO oak_misstatements_owner;
GRANT CONNECT ON DATABASE oak_misstatements TO oak_misstatements_app;
ALTER ROLE oak_misstatements_app IN DATABASE oak_misstatements SET search_path = public;
ALTER DATABASE oak_misstatements ALLOW_CONNECTIONS true;
COMMIT;

\echo 'Stage 4: database oak_misstatements_test, closed to connections'
CREATE DATABASE oak_misstatements_test ENCODING 'UTF8' ALLOW_CONNECTIONS false;

\echo 'Stage 5: rights on oak_misstatements_test, then open it'
BEGIN;
COMMENT ON DATABASE oak_misstatements_test IS 'OAK Misstatements Rollup: automated tests only. Created by scripts/db/02_create.sql.';
REVOKE ALL ON DATABASE oak_misstatements_test FROM PUBLIC;
GRANT CONNECT, CREATE ON DATABASE oak_misstatements_test TO oak_misstatements_owner;
GRANT CONNECT ON DATABASE oak_misstatements_test TO oak_misstatements_app;
ALTER ROLE oak_misstatements_app IN DATABASE oak_misstatements_test SET search_path = public;
ALTER DATABASE oak_misstatements_test ALLOW_CONNECTIONS true;
COMMIT;

\echo 'Stage 6: the public schema inside each database'
\connect oak_misstatements
BEGIN;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO oak_misstatements_owner;
GRANT USAGE ON SCHEMA public TO oak_misstatements_app;
COMMIT;
\connect oak_misstatements_test
BEGIN;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO oak_misstatements_owner;
GRANT USAGE ON SCHEMA public TO oak_misstatements_app;
COMMIT;
\connect postgres

\echo 'Stage 7: the roles may log in (passwords still unset)'
BEGIN;
ALTER ROLE oak_misstatements_owner LOGIN;
ALTER ROLE oak_misstatements_app LOGIN;
COMMIT;

\echo 'Done. Now set the passwords, still in psql:'
\echo '    \password oak_misstatements_owner'
\echo '    \password oak_misstatements_app'
\echo 'Then put them in backend\.env (OAK_DATABASE_URL, OAK_MIGRATION_DATABASE_URL, OAK_TEST_*).'
