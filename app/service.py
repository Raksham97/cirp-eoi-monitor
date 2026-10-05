from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .classifier import classify
from .config import Settings
from .models import CrawlRun, Matter, Notice
from .sources.ibbi import IBBIClient, IBBIRow, stable_json


def normalize_name(name: str) -> str:
    s = re.sub(r'[^A-Z0-9]+', ' ', name.upper())
    suffixes = {'PRIVATE', 'PVT', 'LIMITED', 'LTD', 'LLP', 'INDIA'}
    tokens = [t for t in s.split() if t not in suffixes]
    return ' '.join(tokens).strip() or s.strip()


def canonical_key(cin: str | None, normalized_name: str) -> str:
    return f'cin:{cin.upper()}' if cin else f'name:{normalized_name}'


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _find_matter(db: Session, row: IBBIRow, cin: str | None) -> Matter | None:
    if cin:
        matter = db.scalar(select(Matter).where(Matter.cin == cin.upper()))
        if matter:
            return matter
    normalized = normalize_name(row.debtor_name)
    return db.scalar(select(Matter).where(Matter.normalized_name == normalized).order_by(Matter.created_at.asc()))


def _upsert_matter(db: Session, row: IBBIRow, pdf_text: str, cin: str | None) -> tuple[Matter, bool, bool]:
    normalized = normalize_name(row.debtor_name)
    matter = _find_matter(db, row, cin)
    created = False
    changed = False
    c = classify(row.debtor_name, row.remarks, pdf_text)
    if matter is None:
        matter = Matter(
            canonical_key=canonical_key(cin, normalized),
            debtor_name=row.debtor_name,
            normalized_name=normalized,
            cin=cin.upper() if cin else None,
            industry=c.industry,
            subindustry=c.subindustry,
            classification_method='rules+pdf' if pdf_text else 'rules',
            classification_confidence=c.confidence,
            needs_review=c.confidence < 0.80,
        )
        db.add(matter)
        db.flush()
        created = True
        return matter, created, changed

    if cin and not matter.cin:
        matter.cin = cin.upper()
        proposed = canonical_key(cin, normalized)
        collision = db.scalar(select(Matter.id).where(Matter.canonical_key == proposed, Matter.id != matter.id))
        if not collision:
            matter.canonical_key = proposed
        changed = True
    if row.debtor_name != matter.debtor_name:
        matter.debtor_name = row.debtor_name
        changed = True
    # Never downgrade a human/strong classification with a weaker automatic result.
    if c.confidence > matter.classification_confidence and matter.classification_method != 'human':
        matter.industry = c.industry
        matter.subindustry = c.subindustry
        matter.classification_method = 'rules+pdf' if pdf_text else 'rules'
        matter.classification_confidence = c.confidence
        matter.needs_review = c.confidence < 0.80
        changed = True
    matter.updated_at = datetime.now(timezone.utc)
    return matter, created, changed


def _notice_fingerprint(row: IBBIRow, pdf_sha: str | None) -> str:
    payload = {
        'debtor': normalize_name(row.debtor_name),
        'rp': (row.resolution_professional or '').strip().upper(),
        'eoi_deadline': row.eoi_deadline.isoformat() if row.eoi_deadline else None,
        'prospective': row.prospective_applicants_date.isoformat() if row.prospective_applicants_date else None,
        'objections': row.objections_deadline.isoformat() if row.objections_deadline else None,
        'remarks': re.sub(r'\s+', ' ', row.remarks or '').strip(),
        'pdf_sha': pdf_sha,
        'form_g_url': None if pdf_sha else row.form_g_url,
    }
    return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))


def ingest(settings: Settings, db: Session, pages: int) -> CrawlRun:
    run = CrawlRun(pages_requested=pages)
    db.add(run)
    db.commit()
    client = IBBIClient(settings)
    errors: list[str] = []

    try:
        for page_num, rows, total in client.iter_pages(pages):
            run.pages_fetched += 1
            if total is not None:
                run.total_records_reported = total
            if page_num == 1 and not rows:
                errors.append('IBBI page 1 returned zero parseable rows')
            for row in rows:
                run.rows_seen += 1
                try:
                    existing_by_url = None
                    if row.form_g_url:
                        existing_by_url = db.scalar(
                            select(Notice).where(Notice.source_url_hash == sha256_text(row.form_g_url)).order_by(Notice.first_seen_at.desc())
                        )
                    pdf_info = client.fetch_pdf(row.form_g_url, extract_text=True) if settings.fetch_pdfs and not existing_by_url else None
                    pdf_sha = pdf_info.sha256 if pdf_info else (existing_by_url.pdf_sha256 if existing_by_url else None)
                    pdf_text = pdf_info.text if pdf_info else (existing_by_url.pdf_text_excerpt or '' if existing_by_url else '')
                    cin = row.cin or (pdf_info.cin if pdf_info else None)
                    fp = _notice_fingerprint(row, pdf_sha)
                    existing = db.scalar(select(Notice).where(Notice.fingerprint == fp))
                    if existing:
                        existing.last_seen_at = datetime.now(timezone.utc)
                        run.existing_notices += 1
                        db.flush()
                        continue

                    matter, matter_created, matter_changed = _upsert_matter(db, row, pdf_text, cin)
                    if matter_created:
                        run.new_matters += 1
                    elif matter_changed:
                        run.changed_matters += 1

                    current = list(db.scalars(select(Notice).where(Notice.matter_id == matter.id, Notice.is_current.is_(True))))
                    revision = max([n.revision_number for n in current], default=0) + 1
                    for n in current:
                        n.is_current = False

                    notice = Notice(
                        matter_id=matter.id,
                        crawl_run_id=run.id,
                        fingerprint=fp,
                        source_url_hash=sha256_text(row.form_g_url or row.listing_url),
                        revision_number=revision,
                        is_current=True,
                        resolution_professional=row.resolution_professional,
                        eoi_deadline=row.eoi_deadline,
                        prospective_applicants_date=row.prospective_applicants_date,
                        objections_deadline=row.objections_deadline,
                        form_g_url=row.form_g_url,
                        listing_url=row.listing_url,
                        source_page=row.source_page,
                        remarks=row.remarks,
                        pdf_sha256=pdf_sha,
                        pdf_bytes=pdf_info.size_bytes if pdf_info else (existing_by_url.pdf_bytes if existing_by_url else None),
                        pdf_text_excerpt=(pdf_text[:8000] if pdf_text else None),
                        pdf_extract_status=pdf_info.status if pdf_info else (existing_by_url.pdf_extract_status if existing_by_url else 'not_fetched'),
                        raw_row_json=stable_json(row.raw),
                    )
                    db.add(notice)
                    run.new_notices += 1
                    db.flush()
                except Exception as exc:
                    run.errors += 1
                    errors.append(f'page {page_num} / {row.debtor_name}: {type(exc).__name__}: {exc}')
                    db.rollback()
                    # Re-attach run after rollback and continue.
                    run = db.merge(run)
            db.commit()

        if run.rows_seen == 0:
            run.status = 'anomaly'
        elif run.errors:
            run.status = 'partial'
        else:
            run.status = 'success'
    except Exception as exc:
        run.status = 'failed'
        run.errors += 1
        errors.append(f'run: {type(exc).__name__}: {exc}')
    finally:
        run.finished_at = datetime.now(timezone.utc)
        run.error_summary = '\n'.join(errors[-20:]) if errors else None
        db.add(run)
        db.commit()
    return run
