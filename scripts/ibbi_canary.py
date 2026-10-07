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

URL = 'https://ibbi.gov.in/resolution-plans'
TOTAL_RE = re.compile(r'Total\s+Records\s*:\s*([0-9,]+)', re.I)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='data/ibbi_canary.json')
    args = p.parse_args()
    last = None
    for attempt in range(4):
        try:
            r = requests.get(URL, timeout=30, headers={
                'User-Agent': 'CIRP-EOI-Canary/1.0 (+public source health check)',
                'Cache-Control': 'no-cache',
            })
            r.raise_for_status()
            if not r.content:
                raise RuntimeError('empty upstream response')
            break
        except Exception as exc:
            last = exc
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
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
