from __future__ import annotations

import argparse
import html
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import CrawlRun, Matter, Notice


def _iso(value):
    return value.isoformat() if value else None


def _days_left(value):
    return (value - date.today()).days if value else None


def build(output_dir: Path) -> None:
    init_db()
    output_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        rows = list(db.execute(
            select(Notice, Matter)
            .join(Matter, Notice.matter_id == Matter.id)
            .where(Notice.is_current.is_(True))
            .order_by(Notice.eoi_deadline.asc().nullslast(), Notice.last_seen_at.desc())
        ).all())
        latest = db.scalar(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(1))
        runs = list(db.scalars(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(100)))

    payload = []
    for n, m in rows:
        payload.append({
            'corporate_debtor': m.debtor_name,
            'cin': m.cin,
            'industry': m.industry,
            'subindustry': m.subindustry,
            'confidence': round(float(m.classification_confidence or 0), 2),
            'needs_review': bool(m.needs_review),
            'eoi_deadline': _iso(n.eoi_deadline),
            'days_left': _days_left(n.eoi_deadline),
            'rp': n.resolution_professional,
            'revision': n.revision_number,
            'remarks': n.remarks,
            'form_g_url': n.form_g_url,
            'listing_url': n.listing_url,
            'first_seen_at': _iso(n.first_seen_at),
            'last_seen_at': _iso(n.last_seen_at),
            'pdf_sha256': n.pdf_sha256,
        })

    meta = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'latest_run': {
            'status': latest.status,
            'started_at': _iso(latest.started_at),
            'finished_at': _iso(latest.finished_at),
            'rows_seen': latest.rows_seen,
            'new_notices': latest.new_notices,
            'errors': latest.errors,
        } if latest else None,
        'count': len(payload),
    }
    (output_dir / 'data.json').write_text(json.dumps({'meta': meta, 'rows': payload}, ensure_ascii=False, indent=2), encoding='utf-8')
    (output_dir / 'runs.json').write_text(json.dumps([{
        'started_at': _iso(r.started_at), 'finished_at': _iso(r.finished_at), 'status': r.status,
        'pages_fetched': r.pages_fetched, 'rows_seen': r.rows_seen, 'new_notices': r.new_notices,
        'existing_notices': r.existing_notices, 'errors': r.errors, 'error_summary': r.error_summary,
    } for r in runs], ensure_ascii=False, indent=2), encoding='utf-8')
    (output_dir / '.nojekyll').write_text('', encoding='utf-8')
    (output_dir / 'index.html').write_text(_html(meta), encoding='utf-8')


def _html(meta: dict) -> str:
    generated = html.escape(meta['generated_at'])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CIRP EOI Monitor</title>
<style>
:root{{--bg:#f6f7fb;--card:#fff;--ink:#182230;--muted:#687386;--line:#dfe3e8;--accent:#1f4e78;--warn:#9a6700;--bad:#b42318;--ok:#067647}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
header{{padding:24px 28px;background:#102a43;color:#fff}}header h1{{margin:0 0 6px;font-size:24px}}header p{{margin:0;color:#d9e2ec}}
main{{padding:22px;max-width:1600px;margin:auto}}.stats{{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:12px;margin-bottom:16px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}}.big{{font-size:24px;font-weight:700}}.muted{{color:var(--muted)}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}}input,select{{padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff;min-width:180px}}a.button{{display:inline-block;padding:10px 12px;background:var(--accent);color:#fff;text-decoration:none;border-radius:8px}}
.wrap{{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:10px}}table{{border-collapse:collapse;width:100%;min-width:1200px}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#eef3f8;z-index:1}}tr:hover{{background:#fafcff}}.pill{{display:inline-block;padding:2px 7px;border-radius:999px;background:#edf2f7}}.urgent{{color:var(--bad);font-weight:700}}.review{{color:var(--warn);font-weight:700}}.ok{{color:var(--ok);font-weight:700}}@media(max-width:800px){{.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head>
<body><header><h1>CIRP EOI Monitor</h1><p>Automated public-source monitor for IBBI Form G / Expression of Interest notices. Updated daily.</p></header>
<main>
<div class="stats"><div class="card"><div class="muted">Current records</div><div class="big" id="s-total">—</div></div><div class="card"><div class="muted">Open deadlines</div><div class="big" id="s-open">—</div></div><div class="card"><div class="muted">Due ≤7 days</div><div class="big" id="s-urgent">—</div></div><div class="card"><div class="muted">Needs review</div><div class="big" id="s-review">—</div></div></div>
<div class="card"><b>Last generated:</b> {generated}<span id="run-status"></span></div>
<div class="controls"><input id="q" placeholder="Search debtor / RP / remarks"><select id="industry"><option value="">All industries</option></select><select id="review"><option value="">All verification states</option><option value="yes">Needs review</option><option value="no">Auto-classified</option></select><a class="button" href="cirp-eoi-monitor.xlsx">Download Excel</a></div>
<div class="wrap"><table><thead><tr><th>Corporate Debtor</th><th>Industry</th><th>EOI Deadline</th><th>Days</th><th>RP / IRP</th><th>Revision</th><th>Verification</th><th>Remarks</th><th>Form G</th></tr></thead><tbody id="rows"></tbody></table></div>
</main>
<script>
let DATA=[];
function esc(s){{return String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]))}}
function render(){{let q=document.querySelector('#q').value.toLowerCase(), ind=document.querySelector('#industry').value, rv=document.querySelector('#review').value;let rows=DATA.filter(r=>(!ind||r.industry===ind)&&(!rv||(rv==='yes')===r.needs_review)&&(!q||[r.corporate_debtor,r.rp,r.remarks,r.cin].join(' ').toLowerCase().includes(q)));document.querySelector('#rows').innerHTML=rows.map(r=>`<tr><td><b>${{esc(r.corporate_debtor)}}</b><br><span class="muted">${{esc(r.cin||'')}}</span></td><td><span class="pill">${{esc(r.industry)}}</span><br><span class="muted">${{esc(r.subindustry||'')}}</span></td><td>${{esc(r.eoi_deadline||'—')}}</td><td class="${{r.days_left!==null&&r.days_left>=0&&r.days_left<=7?'urgent':''}}">${{r.days_left??'—'}}</td><td>${{esc(r.rp||'—')}}</td><td>${{r.revision}}</td><td class="${{r.needs_review?'review':'ok'}}">${{r.needs_review?'Review':'Auto'}}</td><td>${{esc(r.remarks||'')}}</td><td>${{r.form_g_url?`<a href="${{esc(r.form_g_url)}}" target="_blank" rel="noopener">Open</a>`:'—'}}</td></tr>`).join('');}}
fetch('data.json',{{cache:'no-store'}}).then(r=>r.json()).then(j=>{{DATA=j.rows;document.querySelector('#s-total').textContent=DATA.length;document.querySelector('#s-open').textContent=DATA.filter(r=>r.days_left!==null&&r.days_left>=0).length;document.querySelector('#s-urgent').textContent=DATA.filter(r=>r.days_left!==null&&r.days_left>=0&&r.days_left<=7).length;document.querySelector('#s-review').textContent=DATA.filter(r=>r.needs_review).length;let inds=[...new Set(DATA.map(r=>r.industry))].sort();document.querySelector('#industry').innerHTML+=[...inds].map(x=>`<option>${{esc(x)}}</option>`).join('');if(j.meta.latest_run)document.querySelector('#run-status').innerHTML=` &nbsp; <b>Last crawl:</b> ${{esc(j.meta.latest_run.status)}} · ${{j.meta.latest_run.rows_seen}} rows · ${{j.meta.latest_run.errors}} errors`;render();}}).catch(e=>{{document.querySelector('#rows').innerHTML='<tr><td colspan="9">No generated dataset yet. Run the workflow once.</td></tr>';}});
['q','industry','review'].forEach(id=>document.querySelector('#'+id).addEventListener(id==='q'?'input':'change',render));
</script></body></html>'''


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='docs')
    args = p.parse_args()
    build(Path(args.output))


if __name__ == '__main__':
    main()
