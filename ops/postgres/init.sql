-- Runs once when the PostgreSQL container is first created.
-- The application connects as a role that is NOT a superuser and cannot bypass row-level security,
-- so the tenant-isolation policies in migration 0002 always apply to it.
CREATE ROLE udyam_app LOGIN PASSWORD 'udyam_app_local' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE udyampulse OWNER udyam_app;
