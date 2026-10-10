from __future__ import annotations

from datetime import date, timedelta

from .classifier import Classification, classify
from .models import Matter, Notice

FUTURE_DAYS = 30
RECENTLY_CLOSED_DAYS = 10
REVIEW_THRESHOLD = 0.80


def missing_from_latest_listing(notice: Notice, latest_run) -> bool:
    """Report missing previously-known notices; never infer withdrawal.

    A successful full-source crawl is necessary for meaningful source presence.
    SQLite may return naive datetimes while API timestamps can be aware; compare
    UTC-clock values from the same stored database. The two-minute margin follows
    the existing complete-source audit's tolerance.
    """
    if not latest_run or latest_run.status != 'success' or not latest_run.started_at:
        return False
    if not notice.last_seen_at:
        return True
    started = latest_run.started_at.replace(tzinfo=None)
    seen = notice.last_seen_at.replace(tzinfo=None)
    return seen < started - timedelta(minutes=2)


def days_left(notice: Notice, as_of: date | None = None) -> int | None:
    if not notice.eoi_deadline:
        return None
    as_of = as_of or date.today()
    return (notice.eoi_deadline - as_of).days


def in_working_window(notice: Notice, as_of: date | None = None) -> bool:
    dl = days_left(notice, as_of)
    return dl is not None and -RECENTLY_CLOSED_DAYS <= dl <= FUTURE_DAYS


def status_for(notice: Notice, as_of: date | None = None) -> str:
    dl = days_left(notice, as_of)
    if dl is None:
        return 'Unknown'
    return 'Open' if dl >= 0 else 'Closed recently'


def priority_for(notice: Notice, as_of: date | None = None) -> str:
    dl = days_left(notice, as_of)
    if dl is None:
        return 'Low'
    if 0 <= dl <= 7:
        return 'Urgent'
    if 8 <= dl <= FUTURE_DAYS:
        return 'Open'
    return 'Recently closed'


def working_sort_key(notice: Notice, as_of: date | None = None) -> tuple[int, int]:
    dl = days_left(notice, as_of)
    if dl is None:
        return (2, 9999)
    if dl >= 0:
        return (0, dl)  # open first, nearest deadline first
    return (1, abs(dl))  # then recently closed, most recent first


def effective_classification(matter: Matter, notice: Notice) -> Classification:
    # Re-run current deterministic rules at build time so rule improvements also
    # improve existing stored records without a destructive database backfill.
    return classify(matter.debtor_name, notice.remarks, notice.pdf_text_excerpt)


def needs_review(classification: Classification) -> bool:
    return classification.confidence < REVIEW_THRESHOLD
