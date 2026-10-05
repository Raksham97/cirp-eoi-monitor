from __future__ import annotations

from datetime import date
from io import BytesIO

import xlsxwriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CrawlRun, Matter, Notice


def _days_left(d: date | None) -> int | None:
    return (d - date.today()).days if d else None


def build_xlsx(db: Session) -> bytes:
    output = BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    header = wb.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#1F4E78', 'border': 1, 'text_wrap': True})
    date_fmt = wb.add_format({'num_format': 'dd-mmm-yyyy'})
    link_fmt = wb.add_format({'font_color': 'blue', 'underline': True})
    urgent_fmt = wb.add_format({'bg_color': '#F4CCCC'})
    review_fmt = wb.add_format({'bg_color': '#FFF2CC'})

    notices = list(db.execute(
        select(Notice, Matter).join(Matter, Notice.matter_id == Matter.id).order_by(Notice.eoi_deadline.desc().nullslast(), Notice.first_seen_at.desc())
    ).all())

    def write_notice_sheet(name: str, rows, current_only: bool = False, review_only: bool = False):
        ws = wb.add_worksheet(name[:31])
        headers = ['Corporate Debtor','CIN','Industry','Sub-category','Confidence','EOI Deadline','Days Left','RP / IRP','Revision','Current','Remarks','Form G','Listing','First Seen','Last Seen','PDF SHA-256','Verification']
        for c, h in enumerate(headers): ws.write(0, c, h, header)
        out_r = 1
        for notice, matter in rows:
            if current_only and not notice.is_current: continue
            if review_only and not matter.needs_review: continue
            values = [matter.debtor_name,matter.cin,matter.industry,matter.subindustry,matter.classification_confidence,notice.eoi_deadline,_days_left(notice.eoi_deadline),notice.resolution_professional,notice.revision_number,notice.is_current,notice.remarks,notice.form_g_url,notice.listing_url,notice.first_seen_at.replace(tzinfo=None) if notice.first_seen_at else None,notice.last_seen_at.replace(tzinfo=None) if notice.last_seen_at else None,notice.pdf_sha256,'Review' if matter.needs_review else 'Auto-classified']
            for c, v in enumerate(values):
                if c == 5 and v: ws.write_datetime(out_r,c, __import__('datetime').datetime.combine(v,__import__('datetime').time()),date_fmt)
                elif c in (11,12) and v: ws.write_url(out_r,c,v,link_fmt,string='Open')
                elif c in (13,14) and v: ws.write_datetime(out_r,c,v)
                else: ws.write(out_r,c,v)
            dl = values[6]
            if dl is not None and 0 <= dl <= 7: ws.set_row(out_r, None, urgent_fmt)
            if matter.needs_review: ws.write(out_r,16,'Review',review_fmt)
            out_r += 1
        ws.freeze_panes(1,0)
        ws.autofilter(0,0,max(out_r-1,1),len(headers)-1)
        widths=[30,22,22,22,12,15,10,26,9,9,48,12,12,20,20,68,16]
        for c,w in enumerate(widths): ws.set_column(c,c,w)

    write_notice_sheet('Active EOIs', notices, current_only=True)
    write_notice_sheet('All Notice Versions', notices)
    write_notice_sheet('Needs Review', notices, current_only=True, review_only=True)

    ws = wb.add_worksheet('Runs')
    run_headers=['Started','Finished','Status','Pages','Rows','New Notices','Existing','New Matters','Changed Matters','Errors','Total IBBI Records','Error Summary']
    for c,h in enumerate(run_headers): ws.write(0,c,h,header)
    runs=list(db.scalars(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(200)))
    for r,run in enumerate(runs,1):
        vals=[run.started_at.replace(tzinfo=None),run.finished_at.replace(tzinfo=None) if run.finished_at else None,run.status,run.pages_fetched,run.rows_seen,run.new_notices,run.existing_notices,run.new_matters,run.changed_matters,run.errors,run.total_records_reported,run.error_summary]
        for c,v in enumerate(vals): ws.write(r,c,v)
    ws.freeze_panes(1,0); ws.set_column(0,1,20); ws.set_column(2,10,14); ws.set_column(11,11,70)

    wb.close()
    return output.getvalue()
