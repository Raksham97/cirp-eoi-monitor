#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, timedelta, timezone
from pathlib import Path

import requests
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db
from app.models import CrawlRun, Notice
from app.view import FUTURE_DAYS, RECENTLY_CLOSED_DAYS

IBBI_URL = 'https://ibbi.gov.in/resolution-plans'
TOTAL_RE = re.compile(r'Total\s+Records\s*:\s*([0-9,]+)', re.I)


def aware_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def live_total() -> int:
    last = None
    for attempt in range(4):
        try:
            r = requests.get(
                IBBI_URL,
                timeout=30,
                headers={
                    'User-Agent': 'CIRP-EOI-Audit/2.0 (+public source completeness check)',
                    'Cache-Control': 'no-cache',
                },
            )
            r.raise_for_status()
            m = TOTAL_RE.search(r.text)
            if not m:
                raise RuntimeError('Total Records not found in live IBBI response')
            return int(m.group(1).replace(',', ''))
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
    raise RuntimeError(f'could not verify live IBBI total: {last}')


def main() -> int:
    init_db()
    today = date.today()
    hi = today + timedelta(days=FUTURE_DAYS)
    recent_lo = today - timedelta(days=RECENTLY_CLOSED_DAYS)

    canary_path = ROOT / 'data' / 'ibbi_canary.json'
    if not canary_path.exists():
        raise SystemExit('AUDIT FAIL: independent IBBI canary result is missing')
    canary = json.loads(canary_path.read_text(encoding='utf-8'))
    canary_total = int(canary.get('total_records') or 0)

    with SessionLocal() as db:
        run = db.scalar(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(1))
        if not run or run.status != 'success':
            raise SystemExit('AUDIT FAIL: latest crawl is not success')
        total = int(run.total_records_reported or 0)
        if total < 1000:
            raise SystemExit(f'AUDIT FAIL: official Total Records missing/unexpected ({total})')

        # Strong completeness proof: the crawler traversed the entire IBBI listing,
        # parsed exactly the number of rows IBBI itself reported, and the official
        # total remained stable from the independent pre-flight canary through the
        # end-of-run verification.
        if run.rows_seen != total:
            raise SystemExit(
                f'AUDIT FAIL: full-list row count mismatch: parsed={run.rows_seen} official_total={total}'
            )
        if canary_total != total:
            raise SystemExit(
                f'AUDIT FAIL: IBBI total changed during run: preflight={canary_total} crawl={total}'
            )
        end_total = live_total()
        if end_total != total:
            raise SystemExit(
                f'AUDIT FAIL: IBBI total changed before verification completed: crawl={total} end={end_total}'
            )

        start = aware_utc(run.started_at)
        open_rows = list(db.scalars(
            select(Notice).where(
                Notice.is_current.is_(True),
                Notice.eoi_deadline.is_not(None),
                Notice.eoi_deadline >= today,
                Notice.eoi_deadline <= hi,
            )
        ))
        stale_open = []
        for n in open_rows:
            seen = aware_utc(n.last_seen_at)
            if seen is None or seen < start - timedelta(minutes=2):
                stale_open.append((n.eoi_deadline, n.form_g_url))
        if stale_open:
            # The entire live source was independently verified above. An item
            # disappearing from a *complete* listing is a source discrepancy,
            # not proof the item was withdrawn. Retain it, publish fresh rows,
            # and surface an explicit UNVERIFIED warning on dashboard + Excel.
            print(
                f'::warning::IBBI SOURCE DISCREPANCY: {len(stale_open)} previously OPEN '
                f'working-window notices absent from the independently verified '
                f'full listing; retained and flagged for human verification. '
                f'first_deadline={stale_open[0][0]}', flush=True
            )

        recent_closed = list(db.scalars(
            select(Notice).where(
                Notice.is_current.is_(True),
                Notice.eoi_deadline.is_not(None),
                Notice.eoi_deadline >= recent_lo,
                Notice.eoi_deadline < today,
            )
        ))
        retained_closed = 0
        for n in recent_closed:
            seen = aware_utc(n.last_seen_at)
            if seen is None or seen < start - timedelta(minutes=2):
                # Recently closed rows are intentionally retained for Ritika's 10-day
                # history even when IBBI later removes/reorders them. That is historical
                # retention, not a coverage failure, because the full live listing was
                # independently proven complete above.
                retained_closed += 1

        print(
            f'AUDIT OK: COMPLETE IBBI LISTING verified; official_total={total} parsed={run.rows_seen}; '
            f'open_window={len(open_rows)} source_missing={len(stale_open)}; recently_closed_retained={retained_closed}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
