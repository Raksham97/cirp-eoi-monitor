from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.view import missing_from_latest_listing


def test_previously_seen_current_notice_missing_from_full_listing():
    started = datetime(2026, 10, 9, 18, 26, tzinfo=timezone.utc)
    run = SimpleNamespace(status='success', started_at=started)
    notice = SimpleNamespace(last_seen_at=started - timedelta(days=1))
    assert missing_from_latest_listing(notice, run)


def test_present_notice_and_failed_run_are_not_false_source_discrepancies():
    started = datetime(2026, 10, 9, 18, 26, tzinfo=timezone.utc)
    run = SimpleNamespace(status='success', started_at=started)
    fresh = SimpleNamespace(last_seen_at=started + timedelta(minutes=1))
    assert not missing_from_latest_listing(fresh, run)
    old = SimpleNamespace(last_seen_at=started - timedelta(days=1))
    assert not missing_from_latest_listing(old, SimpleNamespace(status='failed', started_at=started))


def test_sqlite_naive_utc_timestamps_and_margin():
    started = datetime(2026, 10, 9, 18, 26)
    run = SimpleNamespace(status='success', started_at=started)
    recent = SimpleNamespace(last_seen_at=started - timedelta(seconds=30))
    old = SimpleNamespace(last_seen_at=started - timedelta(minutes=3))
    assert not missing_from_latest_listing(recent, run)
    assert missing_from_latest_listing(old, run)
