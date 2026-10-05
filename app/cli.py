from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from .config import get_settings
from .db import SessionLocal, init_db
from .exporter import build_xlsx
from .models import CrawlRun, Matter, Notice
from .service import ingest


def main():
    parser = argparse.ArgumentParser(prog='cirp-eoi')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init-db')
    p_ingest = sub.add_parser('ingest')
    p_ingest.add_argument('--pages', type=int, default=None)
    p_export = sub.add_parser('export')
    p_export.add_argument('--output', default='cirp-eoi-monitor.xlsx')
    sub.add_parser('stats')
    args = parser.parse_args()
    settings = get_settings()
    init_db()

    if args.cmd == 'init-db':
        print('database initialized')
        return
    with SessionLocal() as db:
        if args.cmd == 'ingest':
            pages = args.pages
            if pages is None:
                pages = settings.monday_deep_pages if datetime.now().weekday() == 0 else settings.daily_pages
            run = ingest(settings, db, pages)
            print(f'run={run.id} status={run.status} pages={run.pages_fetched} rows={run.rows_seen} new={run.new_notices} existing={run.existing_notices} errors={run.errors}')
            if run.status in {'failed','anomaly'}:
                raise SystemExit(2)
        elif args.cmd == 'export':
            payload = build_xlsx(db)
            Path(args.output).write_bytes(payload)
            print(args.output)
        elif args.cmd == 'stats':
            print('matters', db.scalar(select(func.count()).select_from(Matter)))
            print('notice_versions', db.scalar(select(func.count()).select_from(Notice)))
            latest = db.scalar(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(1))
            print('latest_run', latest.status if latest else 'never')


if __name__ == '__main__':
    main()
