# CIRP EOI Monitor

A production-oriented monitor for Indian CIRP Form G / invitation-for-expression-of-interest notices.

## Design

- Canonical discovery source: IBBI Resolution Plans / Form G listing.
- Daily idempotent ingestion.
- De-duplicates repeated rows and preserves later revisions as separate versions.
- Deterministic industry classification first; uncertain matters go to a review queue.
- Postgres is the source of truth. Excel is an export.
- Minimal password-protected web dashboard.
- Raw IBBI row metadata, source URL, PDF URL, PDF SHA-256 and extraction status are retained.
- PDF bytes are not stored by default; add S3/R2 archival before treating this as evidentiary document storage.

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='sqlite+pysqlite:///./cirp_eoi.sqlite3'
export APP_PASSWORD='dev'
python -m app.cli init-db
python -m app.cli ingest --pages 2
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 and sign in as `lawyer` / `dev`.

## CLI

```bash
python -m app.cli init-db
python -m app.cli ingest                 # daily depth, Monday deep scan automatically
python -m app.cli ingest --pages 40      # explicit reconciliation depth
python -m app.cli ingest --pages 200     # historical backfill
python -m app.cli export --output eoi.xlsx
python -m app.cli stats
```

## Production

Use `scripts/bootstrap-macos.sh` from a Mac terminal. It creates a dedicated private GitHub repository, a paid persistent Postgres database, a web service, and a daily cron job on Render.

Render cron schedules are UTC. The included schedule `30 20 * * *` runs at 02:00 Asia/Kolkata the following calendar day.

## Reliability principles

1. Re-running the same ingestion is safe.
2. A changed Form G becomes a new version instead of overwriting history.
3. An empty/failed source fetch is visible in the Runs page and health endpoint.
4. Unknown classification is preferable to a confident guess.
5. The web UI can be rebuilt from Postgres at any time.

## Scope / legal caveat

This system is a monitoring aid. It should not be treated as the legally authoritative copy of a notice. The source URL and hash are retained so a user can verify against IBBI and the underlying Form G.
