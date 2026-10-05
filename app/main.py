from __future__ import annotations

import secrets
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, init_db
from .exporter import build_xlsx
from .models import CrawlRun, Matter, Notice

settings = get_settings()
app = FastAPI(title='CIRP EOI Monitor', version='1.0.0')
security = HTTPBasic(auto_error=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def auth(credentials: HTTPBasicCredentials | None = Depends(security)):
    if not settings.app_password:
        return True
    ok = credentials and secrets.compare_digest(credentials.username, settings.app_username) and secrets.compare_digest(credentials.password, settings.app_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={'WWW-Authenticate': 'Basic'}, detail='Authentication required')
    return True


@app.on_event('startup')
def startup():
    init_db()


@app.get('/healthz')
def healthz(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    latest = db.scalar(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(1))
    return {'ok': True, 'latest_run_status': latest.status if latest else 'never-run', 'latest_run_started_at': latest.started_at if latest else None}


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request, q: str = '', industry: str = '', review: bool = False, _: bool = Depends(auth), db: Session = Depends(get_db)):
    stmt = select(Notice, Matter).join(Matter, Notice.matter_id == Matter.id).where(Notice.is_current.is_(True))
    if q:
        stmt = stmt.where(func.upper(Matter.debtor_name).contains(q.upper()))
    if industry:
        stmt = stmt.where(Matter.industry == industry)
    if review:
        stmt = stmt.where(Matter.needs_review.is_(True))
    stmt = stmt.order_by(Notice.eoi_deadline.desc().nullslast(), Notice.last_seen_at.desc()).limit(500)
    rows = list(db.execute(stmt).all())
    industries = list(db.scalars(select(Matter.industry).distinct().order_by(Matter.industry)))
    latest = db.scalar(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(1))
    return templates.TemplateResponse('index.html', {'request':request,'rows':rows,'industries':industries,'q':q,'industry':industry,'review':review,'today':date.today(),'latest':latest})


@app.get('/runs', response_class=HTMLResponse)
def runs(request: Request, _: bool = Depends(auth), db: Session = Depends(get_db)):
    items = list(db.scalars(select(CrawlRun).order_by(CrawlRun.started_at.desc()).limit(200)))
    return templates.TemplateResponse('runs.html', {'request':request,'runs':items})


@app.get('/api/notices')
def api_notices(_: bool = Depends(auth), db: Session = Depends(get_db)):
    rows = db.execute(select(Notice, Matter).join(Matter).where(Notice.is_current.is_(True)).order_by(Notice.eoi_deadline.desc().nullslast()).limit(1000)).all()
    return [{'id':n.id,'corporate_debtor':m.debtor_name,'cin':m.cin,'industry':m.industry,'subindustry':m.subindustry,'confidence':m.classification_confidence,'needs_review':m.needs_review,'eoi_deadline':n.eoi_deadline,'rp':n.resolution_professional,'revision':n.revision_number,'remarks':n.remarks,'form_g_url':n.form_g_url,'last_seen_at':n.last_seen_at} for n,m in rows]


@app.get('/export.xlsx')
def export_xlsx(_: bool = Depends(auth), db: Session = Depends(get_db)):
    payload = build_xlsx(db)
    return Response(content=payload, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers={'Content-Disposition':'attachment; filename="cirp-eoi-monitor.xlsx"'})
