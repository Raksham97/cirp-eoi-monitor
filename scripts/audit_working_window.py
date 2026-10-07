#!/usr/bin/env python3
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import CrawlRun, Notice
from app.view import FUTURE_DAYS, RECENTLY_CLOSED_DAYS


def aware_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def main() -> int:
    init_db()
    today = date.today()
    lo = today - timedelta(days=RECENTLY_CLOSED_DAYS)
    hi = today + timedelta(days=FUTURE_DAYS)
    with SessionLocal() as db:
        run = db.scalar(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(1))
        if not run or run.status != 'success':
            raise SystemExit('AUDIT FAIL: latest crawl is not success')
        if not run.total_records_reported or run.total_records_reported < 1000:
            raise SystemExit('AUDIT FAIL: official Total Records missing/unexpected')
        rows = list(db.scalars(
            select(Notice).where(
                Notice.is_current.is_(True),
                Notice.eoi_deadline.is_not(None),
                Notice.eoi_deadline >= lo,
                Notice.eoi_deadline <= hi,
            )
        ))
        start = aware_utc(run.started_at)
        stale = []
        for n in rows:
            seen = aware_utc(n.last_seen_at)
            if seen is None or seen < start - timedelta(minutes=2):
                stale.append((n.eoi_deadline, n.form_g_url))
        if stale:
            raise SystemExit(
                f'AUDIT FAIL: {len(stale)} current working-window notices were not re-observed in latest crawl; '
                f'first={stale[0]}'
            )
        if run.rows_seen < 20:
            raise SystemExit(f'AUDIT FAIL: suspiciously low rows_seen={run.rows_seen}')
        print(
            f'AUDIT OK: {len(rows)} working-window notices all re-observed; '
            f'pages={run.pages_fetched} rows={run.rows_seen} official_total={run.total_records_reported}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
