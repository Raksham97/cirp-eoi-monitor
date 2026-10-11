#!/usr/bin/env python3
"""Fail-closed publication policy for intermittent external IBBI downtime.

A temporary unavailable result is NOT evidence of a successful crawl. No data is
committed or deployed. Outages older than a bounded age are escalated as errors.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

MAX_GRACE_HOURS = 30
RECOVERY_FRESH_MINUTES = 180


def read_age_hours(path: Path, now: datetime | None = None) -> float | None:
    try:
        raw = path.read_text(encoding='utf-8').strip()
        stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            return None
        current = now or datetime.now(timezone.utc)
        age = (current - stamp.astimezone(timezone.utc)).total_seconds() / 3600
        return age if age >= -0.1 else None
    except (OSError, ValueError, OverflowError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['outage', 'recovery'], required=True)
    parser.add_argument('--heartbeat', default='data/last_successful_run.txt')
    parser.add_argument('--max-hours', type=float, default=MAX_GRACE_HOURS)
    args = parser.parse_args(argv)
    age = read_age_hours(Path(args.heartbeat))
    if args.mode == 'recovery':
        # Normal twice-daily runs always execute. A recovery slot runs only if
        # the latest verified data is already 3h old (or the heartbeat is missing).
        needs_recovery = age is None or age >= RECOVERY_FRESH_MINUTES / 60
        print(f'run={str(needs_recovery).lower()}')
        print(f'RECOVERY_GATE: latest verified age={age!r}h; run={needs_recovery}',file=sys.stderr)
        return 0

    if age is None or age > args.max_hours:
        print(f'::error::IBBI unavailable and last VERIFIED dataset age '
              f'{age if age is not None else "unknown"}h exceeds safe '
              f'{args.max_hours}h. Preserve old dataset and investigate official source.',flush=True)
        return 1

    warning = (f'IBBI official site temporarily unavailable. No new data published; '
               f'last verified dataset age={age:.1f}h, maximum grace={args.max_hours:.1f}h. '
               'Retry at next scheduled/recovery check.')
    print(f'::warning::{warning}',flush=True)
    import os
    if path := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(path,'a',encoding='utf-8') as f:
            f.write('### CIRP source outage — publication safely deferred\n\n'
                    f'{warning}\n\nThe scheduled workflow ended without a fresh crawl; '
                    'this is **not** a verification success. The live dashboard retains '
                    'its prior generated timestamp and turns stale visibly.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
