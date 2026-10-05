from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from pypdf import PdfReader

from ..config import Settings


@dataclass
class IBBIRow:
    debtor_name: str
    cin: str | None
    resolution_professional: str | None
    eoi_deadline: date | None
    prospective_applicants_date: date | None
    objections_deadline: date | None
    form_g_url: str | None
    remarks: str | None
    listing_url: str
    source_page: int
    raw: dict


@dataclass
class PDFInfo:
    sha256: str | None
    size_bytes: int | None
    text: str
    status: str
    cin: str | None


CIN_RE = re.compile(r'\b[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b')
TOTAL_RE = re.compile(r'Total\s+Records\s*:\s*([0-9,]+)', re.IGNORECASE)


def parse_date(value: str | None) -> date | None:
    if not value or not value.strip() or value.strip() in {'-', 'NA', 'N/A'}:
        return None
    try:
        return date_parser.parse(value, dayfirst=True, fuzzy=True).date()
    except Exception:
        return None


def _normalize_space(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def _decode_cin_from_href(href: str) -> str | None:
    try:
        q = parse_qs(urlparse(href).query)
        raw = (q.get('cinno') or [None])[0]
        if not raw:
            return None
        raw += '=' * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(raw.encode()).decode(errors='ignore').strip()
        return decoded if CIN_RE.fullmatch(decoded) else None
    except Exception:
        return None


def _find_table(soup: BeautifulSoup):
    for table in soup.find_all('table'):
        text = _normalize_space(table.get_text(' ', strip=True)).lower()
        if 'name of corporate debtor' in text and 'expression of interest' in text:
            return table
    return soup.find('table')


def parse_resolution_page(html: str, listing_url: str, page: int) -> tuple[list[IBBIRow], int | None]:
    soup = BeautifulSoup(html, 'html.parser')
    table = _find_table(soup)
    if table is None:
        return [], None

    rows: list[IBBIRow] = []
    for tr in table.find_all('tr'):
        cells = tr.find_all('td')
        if len(cells) < 6:
            continue
        values = [_normalize_space(c.get_text(' ', strip=True)) for c in cells]
        debtor = values[0]
        if not debtor or 'corporate debtor' in debtor.lower():
            continue
        links = [a.get('href') for a in tr.find_all('a', href=True)]
        cin = next((c for h in links if (c := _decode_cin_from_href(h))), None)
        form_href = None
        if len(cells) >= 6:
            a = cells[5].find('a', href=True)
            form_href = a.get('href') if a else None
        if not form_href:
            form_href = next((h for h in links if h and ('.pdf' in h.lower() or 'resolution_plan' in h.lower())), None)
        form_url = urljoin(listing_url, form_href) if form_href else None
        remarks = values[6] if len(values) > 6 and values[6] else None
        raw = {
            'debtor_name': debtor,
            'resolution_professional': values[1] if len(values) > 1 else None,
            'eoi_deadline': values[2] if len(values) > 2 else None,
            'prospective_applicants_date': values[3] if len(values) > 3 else None,
            'objections_deadline': values[4] if len(values) > 4 else None,
            'form_g_url': form_url,
            'remarks': remarks,
            'links': links,
        }
        rows.append(IBBIRow(
            debtor_name=debtor,
            cin=cin,
            resolution_professional=raw['resolution_professional'],
            eoi_deadline=parse_date(raw['eoi_deadline']),
            prospective_applicants_date=parse_date(raw['prospective_applicants_date']),
            objections_deadline=parse_date(raw['objections_deadline']),
            form_g_url=form_url,
            remarks=remarks,
            listing_url=listing_url,
            source_page=page,
            raw=raw,
        ))
    page_text = soup.get_text(' ', strip=True)
    m = TOTAL_RE.search(page_text)
    total = int(m.group(1).replace(',', '')) if m else None
    return rows, total


class IBBIClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CIRP-EOI-Monitor/1.0 (+public legal-notice monitoring; polite crawler)',
            'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8',
        })

    def _get(self, url: str) -> requests.Response:
        last_exc = None
        for attempt in range(3):
            try:
                r = self.session.get(url, timeout=self.settings.request_timeout_seconds)
                r.raise_for_status()
                return r
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise last_exc

    def fetch_page(self, page: int) -> tuple[list[IBBIRow], int | None]:
        base = urljoin(self.settings.ibbi_base_url, self.settings.ibbi_resolution_plans_path)
        url = f'{base}?page={page}'
        r = self._get(url)
        return parse_resolution_page(r.text, url, page)

    def iter_pages(self, max_pages: int):
        for page in range(1, max_pages + 1):
            rows, total = self.fetch_page(page)
            yield page, rows, total
            if not rows:
                break
            time.sleep(self.settings.request_delay_seconds)

    def fetch_pdf(self, url: str | None, extract_text: bool = True) -> PDFInfo:
        if not url:
            return PDFInfo(None, None, '', 'missing_url', None)
        try:
            r = self._get(url)
            content = r.content
            limit = self.settings.max_pdf_mb * 1024 * 1024
            if len(content) > limit:
                return PDFInfo(hashlib.sha256(content).hexdigest(), len(content), '', 'too_large', None)
            sha = hashlib.sha256(content).hexdigest()
            if not content.startswith(b'%PDF'):
                return PDFInfo(sha, len(content), '', 'not_pdf', None)
            text = ''
            status = 'hashed'
            if extract_text:
                try:
                    reader = PdfReader(io.BytesIO(content))
                    parts = []
                    for page in reader.pages[:8]:
                        parts.append(page.extract_text() or '')
                    text = _normalize_space(' '.join(parts))[:30000]
                    status = 'text_extracted' if len(text) >= 120 else 'scan_or_sparse_text'
                except Exception:
                    status = 'pdf_parse_error'
            cin_m = CIN_RE.search(text.upper()) if text else None
            return PDFInfo(sha, len(content), text, status, cin_m.group(0) if cin_m else None)
        except Exception as exc:
            return PDFInfo(None, None, '', f'fetch_error:{type(exc).__name__}', None)


def stable_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
