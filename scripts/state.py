from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def restore(db_path: Path, dump_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    if not dump_path.exists() or dump_path.stat().st_size == 0:
        return
    sql = dump_path.read_text(encoding='utf-8')
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def dump(db_path: Path, dump_path: Path) -> None:
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        lines = list(conn.iterdump())
    finally:
        conn.close()
    dump_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('restore', 'dump'):
        sp = sub.add_parser(name)
        sp.add_argument('--db', default='cirp_eoi.sqlite3')
        sp.add_argument('--state', default='data/state.sql')
    args = p.parse_args()
    db_path = Path(args.db)
    state_path = Path(args.state)
    if args.cmd == 'restore':
        restore(db_path, state_path)
    else:
        dump(db_path, state_path)


if __name__ == '__main__':
    main()
