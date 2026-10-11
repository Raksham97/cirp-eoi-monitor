#!/usr/bin/env python3
"""Independent, deliberately simple source canary for the IBBI listing page."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
import time
from bs4 import BeautifulSoup
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.source_errors import is_transient_source_error, SourceTemporarilyUnavailable

URL = 'https://ibbi.gov.in/resolution-plans'
TOTAL_RE = re.compile(r'Total\s+Records\s*:\s*([0-9,]+)', re.I)


def fetch_landing_page(get=requests.get, sleep=time.sleep, attempts: int = 4):
    """Retry only transport/429/5xx errors; schema, 4xx and empty HTML remain fatal."""
    for attempt in range(attempts):
        try:
            response = get(URL, timeout=(8, 25), headers={
                'User-Agent': 'CIRP-EOI-Canary/1.0 (+public source health check)',
                'Cache-Control': 'no-cache',
            })
            response.raise_for_status()
            if not response.content:
                raise RuntimeError('empty upstream response')
            return response
        except Exception as exc:
            if not is_transient_source_error(exc):
                raise
            if attempt == attempts - 1:
                raise SourceTemporarilyUnavailable(
                    f'{type(exc).__name__}: {exc} after {attempts} attempts'
                ) from exc
            print(f'IBBI transient source error, attempt {attempt+1}/{attempts}: '
                  f'{type(exc).__name__}; retrying', flush=True)
            sleep(min(3 * (2 ** attempt), 18))
    raise AssertionError('unreachable')


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='data/ibbi_canary.json')
    args = p.parse_args()
    try:
        r = fetch_landing_page()
    except SourceTemporarilyUnavailable as exc:
        print(f'::warning::IBBI TEMPORARILY UNAVAILABLE: {exc}; verified data remains unchanged.', flush=True)
        return 75  # EX_TEMPFAIL: workflow skips publication unless stale-data guard escalates
    soup = BeautifulSoup(r.text, 'html.parser')
    chosen = None
    for table in soup.find_all('table'):
        txt = ' '.join(table.stripped_strings).lower()
        if 'name of corporate debtor' in txt and 'expression of interest' in txt and 'form g' in txt:
            chosen = table
            break
    if chosen is None:
        raise SystemExit('CANARY FAIL: expected IBBI Form G table/header not found')
    data_rows = [tr for tr in chosen.find_all('tr') if len(tr.find_all('td')) >= 6]
    m = TOTAL_RE.search(soup.get_text(' ', strip=True))
    total = int(m.group(1).replace(',', '')) if m else None
    if len(data_rows) < 5:
        raise SystemExit(f'CANARY FAIL: only {len(data_rows)} parseable rows on landing page')
    if total is None or total < 1000:
        raise SystemExit(f'CANARY FAIL: Total Records missing/unexpected ({total})')
    payload = {
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'status': 'success',
        'landing_rows': len(data_rows),
        'total_records': total,
        'source_url': URL,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(f"IBBI canary OK: landing_rows={len(data_rows)} total_records={total}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
