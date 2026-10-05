from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO

import xlsxwriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CrawlRun, Matter, Notice
from .view import (
    days_left,
    effective_classification,
    in_working_window,
    needs_review,
    priority_for,
    status_for,
    working_sort_key,
)


def build_xlsx(db: Session) -> bytes:
    output = BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    header = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#1F4E78', 'border': 1, 'text_wrap': True})
    date_fmt = wb.add_format({'num_format': 'dd-mmm-yyyy'})
    link_fmt = wb.add_format({'font_color': 'blue', 'underline': True})
    urgent_fmt = wb.add_format({'bg_color': '#F4CCCC'})
    closed_fmt = wb.add_format({'bg_color': '#E7E6E6', 'font_color': '#666666'})
    review_fmt = wb.add_format({'bg_color': '#FFF2CC'})

    today = date.today()
    rows = list(db.execute(
        select(Notice, Matter)
        .join(Matter, Notice.matter_id == Matter.id)
        .where(Notice.is_current.is_(True))
    ).all())
    rows = [(n, m) for n, m in rows if in_working_window(n, today)]
    rows.sort(key=lambda nm: working_sort_key(nm[0], today))

    def write_notice_sheet(name: str, source_rows, review_only: bool = False):
        ws = wb.add_worksheet(name[:31])
        headers = [
            'Priority','Status','Corporate Debtor','CIN','Industry','Sub-category','Confidence',
            'EOI Deadline','Days Left','RP / IRP','Revision','Remarks','Form G','IBBI Listing',
            'First Seen','Last Seen','Verification'
        ]
        for c, h in enumerate(headers):
            ws.write(0, c, h, header)
        out_r = 1
        for notice, matter in source_rows:
            cls = effective_classification(matter, notice)
            review = needs_review(cls)
            if review_only and not review:
                continue
            dl = days_left(notice, today)
            status = status_for(notice, today)
            values = [
                priority_for(notice, today), status, matter.debtor_name, matter.cin,
                cls.industry, cls.subindustry, cls.confidence, notice.eoi_deadline, dl,
                notice.resolution_professional, notice.revision_number, notice.remarks,
                notice.form_g_url, notice.listing_url,
                notice.first_seen_at.replace(tzinfo=None) if notice.first_seen_at else None,
                notice.last_seen_at.replace(tzinfo=None) if notice.last_seen_at else None,
                'Review' if review else 'Auto-classified',
            ]
            row_fmt = closed_fmt if status == 'Closed recently' else None
            for c, v in enumerate(values):
                fmt = row_fmt
                if c == 7 and v:
                    ws.write_datetime(out_r, c, datetime.combine(v, time()), date_fmt if not row_fmt else closed_fmt)
                elif c in (12, 13) and v:
                    ws.write_url(out_r, c, v, link_fmt if not row_fmt else closed_fmt, string='Open')
                elif c in (14, 15) and v:
                    ws.write_datetime(out_r, c, v, row_fmt)
                else:
                    ws.write(out_r, c, v, fmt)
            if status == 'Open' and dl is not None and 0 <= dl <= 7:
                ws.set_row(out_r, None, urgent_fmt)
            if review:
                ws.write(out_r, 16, 'Review', review_fmt)
            out_r += 1
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, max(out_r - 1, 1), len(headers) - 1)
        widths = [14,16,30,22,22,22,12,15,10,26,9,48,12,12,20,20,16]
        for c, w in enumerate(widths):
            ws.set_column(c, c, w)

    write_notice_sheet('30-Day Working List', rows)
    write_notice_sheet('Needs Review', rows, review_only=True)

    ws = wb.add_worksheet('Runs')
    run_headers = ['Started','Finished','Status','Pages','Rows','New Notices','Existing','New Matters','Changed Matters','Errors','Total IBBI Records','Error Summary']
    for c, h in enumerate(run_headers):
        ws.write(0, c, h, header)
    runs = list(db.scalars(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(200)))
    for r, run in enumerate(runs, 1):
        vals = [
            run.started_at.replace(tzinfo=None), run.finished_at.replace(tzinfo=None) if run.finished_at else None,
            run.status, run.pages_fetched, run.rows_seen, run.new_notices, run.existing_notices,
            run.new_matters, run.changed_matters, run.errors, run.total_records_reported, run.error_summary,
        ]
        for c, v in enumerate(vals):
            ws.write(r, c, v)
    ws.freeze_panes(1, 0)
    ws.set_column(0, 1, 20)
    ws.set_column(2, 10, 14)
    ws.set_column(11, 11, 70)

    wb.close()
    return output.getvalue()
