from __future__ import annotations

from datetime import date, datetime, timezone
import uuid

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class CrawlRun(Base):
    __tablename__ = 'crawl_runs'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='running', index=True)
    pages_requested: Mapped[int] = mapped_column(Integer, default=0)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    rows_seen: Mapped[int] = mapped_column(Integer, default=0)
    new_notices: Mapped[int] = mapped_column(Integer, default=0)
    existing_notices: Mapped[int] = mapped_column(Integer, default=0)
    new_matters: Mapped[int] = mapped_column(Integer, default=0)
    changed_matters: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    total_records_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class Matter(Base):
    __tablename__ = 'matters'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    canonical_key: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    debtor_name: Mapped[str] = mapped_column(String(300), index=True)
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    cin: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    industry: Mapped[str] = mapped_column(String(80), default='Other / Unclear', index=True)
    subindustry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    classification_method: Mapped[str] = mapped_column(String(40), default='rules')
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    notices: Mapped[list['Notice']] = relationship(back_populates='matter', cascade='all, delete-orphan')


class Notice(Base):
    __tablename__ = 'notices'
    __table_args__ = (
        UniqueConstraint('fingerprint', name='uq_notice_fingerprint'),
        Index('ix_notice_matter_current', 'matter_id', 'is_current'),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    matter_id: Mapped[str] = mapped_column(ForeignKey('matters.id', ondelete='CASCADE'), index=True)
    crawl_run_id: Mapped[str | None] = mapped_column(ForeignKey('crawl_runs.id'), nullable=True, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url_hash: Mapped[str] = mapped_column(String(64), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    resolution_professional: Mapped[str | None] = mapped_column(String(250), nullable=True)
    eoi_deadline: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    prospective_applicants_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    objections_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    form_g_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    listing_url: Mapped[str] = mapped_column(Text)
    source_page: Mapped[int] = mapped_column(Integer, default=1)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    pdf_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pdf_text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_extract_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw_row_json: Mapped[str] = mapped_column(Text)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)

    matter: Mapped[Matter] = relationship(back_populates='notices')
