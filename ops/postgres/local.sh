#!/usr/bin/env bash
# Project-local PostgreSQL for development and tests. Data lives in var/pg; nothing system-wide changes.
# Usage: ops/postgres/local.sh up | down
# Needs the PostgreSQL binaries (initdb, pg_ctl, psql) on PATH, for example `brew install postgresql@16`.
set -euo pipefail

PG_DIR="${PG_DIR:-var/pg}"
PG_PORT="${PG_PORT:-55432}"

case "${1:-}" in
  up)
    mkdir -p var
    if [ ! -d "$PG_DIR" ]; then
      initdb -D "$PG_DIR" -U postgres --auth=trust -E UTF8 >/dev/null
    fi
    if ! pg_ctl -D "$PG_DIR" status >/dev/null 2>&1; then
      pg_ctl -D "$PG_DIR" -o "-p $PG_PORT -c listen_addresses=127.0.0.1" -l var/pg.log -w start >/dev/null
    fi
    # The cluster's superuser is whatever initdb was run with.
    SU=postgres
    if ! psql -h 127.0.0.1 -p "$PG_PORT" -U "$SU" -d postgres -Atc "select 1" >/dev/null 2>&1; then
      SU=udyam
    fi
    run() { psql -h 127.0.0.1 -p "$PG_PORT" -U "$SU" -d postgres -Atqc "$1"; }
    # The app role is not a superuser and cannot bypass row-level security.
    if [ "$(run "select count(*) from pg_roles where rolname='udyam_app'")" = "0" ]; then
      run "CREATE ROLE udyam_app LOGIN NOSUPERUSER NOBYPASSRLS"
    fi
    for db in udyampulse udyampulse_test; do
      if [ "$(run "select count(*) from pg_database where datname='$db'")" = "0" ]; then
        run "CREATE DATABASE $db OWNER udyam_app"
      fi
    done
    echo "PostgreSQL ready: postgresql+psycopg://udyam_app@127.0.0.1:$PG_PORT/udyampulse"
    ;;
  down)
    pg_ctl -D "$PG_DIR" stop >/dev/null 2>&1 || true
    echo "PostgreSQL stopped"
    ;;
  *)
    echo "usage: $0 up|down" >&2
    exit 2
    ;;
esac
