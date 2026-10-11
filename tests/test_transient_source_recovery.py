from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import requests
from requests import Response
import pytest

from app.source_errors import is_transient_source_error, SourceTemporarilyUnavailable
from scripts.ibbi_canary import fetch_landing_page
from scripts.source_outage_policy import read_age_hours, main as policy_main


def http_error(status):
    response = Response()
    response.status_code = status
    error = requests.exceptions.HTTPError(f'HTTP {status}', response=response)
    return error


@pytest.mark.parametrize('status,expected', [(429,True),(503,True),(504,True),(404,False),(403,False)])
def test_precise_http_failure_classification(status,expected):
    assert is_transient_source_error(http_error(status)) is expected


def test_all_canary_timeouts_defer_without_creating_false_data():
    calls=[];sleeps=[]
    def down(*args,**kwargs):
        calls.append(kwargs)
        raise requests.exceptions.ReadTimeout('mock IBBI timed out')
    with pytest.raises(SourceTemporarilyUnavailable):
        fetch_landing_page(get=down,sleep=sleeps.append,attempts=4)
    assert len(calls)==4 and sleeps == [3,6,12]
    assert all(c['timeout'] == (8,25) for c in calls)


def test_schema_or_permanent_error_remains_a_real_failure():
    def gone(*args,**kwargs):raise http_error(404)
    with pytest.raises(requests.exceptions.HTTPError):
        fetch_landing_page(get=gone,sleep=lambda _: None)


def test_canary_retries_then_recovers():
    from scripts.ibbi_canary import fetch_landing_page
    state={'tries':0}
    def intermittent(*args,**kwargs):
        state['tries']+=1
        if state['tries']<3:raise requests.exceptions.ReadTimeout('temporary')
        return SimpleNamespace(content=b'valid response',text='valid response',raise_for_status=lambda:None)
    r=fetch_landing_page(get=intermittent,sleep=lambda _: None)
    assert r.content==b'valid response' and state['tries']==3


def test_grace_period_does_not_hide_prolonged_outage(tmp_path,capsys):
    hb=tmp_path/'heartbeat.txt'
    now=datetime.now(timezone.utc)
    hb.write_text((now-timedelta(hours=2)).isoformat())
    assert policy_main(['--mode','outage','--heartbeat',str(hb),'--max-hours','30'])==0
    assert 'No new data published' in capsys.readouterr().out
    hb.write_text((now-timedelta(hours=31)).isoformat())
    assert policy_main(['--mode','outage','--heartbeat',str(hb),'--max-hours','30'])==1
    assert '::error::' in capsys.readouterr().out
    hb.unlink()
    assert policy_main(['--mode','outage','--heartbeat',str(hb)])==1


def test_recovery_gate_skips_when_fresh(tmp_path,capsys):
    hb=tmp_path/'heartbeat.txt';now=datetime.now(timezone.utc)
    hb.write_text((now-timedelta(hours=1)).isoformat())
    assert policy_main(['--mode','recovery','--heartbeat',str(hb)])==0
    assert 'run=false' in capsys.readouterr().out
    hb.write_text((now-timedelta(hours=5)).isoformat())
    assert policy_main(['--mode','recovery','--heartbeat',str(hb)])==0
    assert 'run=true' in capsys.readouterr().out


def test_future_heartbeat_must_not_hide_outage(tmp_path):
    hb=tmp_path/'future.txt'
    hb.write_text((datetime.now(timezone.utc)+timedelta(hours=5)).isoformat())
    assert read_age_hours(hb) is None
    assert policy_main(['--mode','outage','--heartbeat',str(hb)])==1


def test_canary_does_not_overwrite_last_success_on_timeout(tmp_path, monkeypatch):
    import sys
    from scripts import ibbi_canary as canary
    existing = tmp_path / 'canary.json'
    existing.write_text('{"status":"success","total_records":3826}')
    monkeypatch.setattr(canary,'fetch_landing_page',
                        lambda: (_ for _ in ()).throw(SourceTemporarilyUnavailable('timed out')))
    monkeypatch.setattr(sys,'argv',['ibbi_canary.py','--output',str(existing)])
    assert canary.main()==75
    assert existing.read_text()=='{"status":"success","total_records":3826}'


def test_canary_fails_closed_when_response_has_wrong_schema(tmp_path, monkeypatch):
    import sys
    from scripts import ibbi_canary as canary
    dest = tmp_path / 'should-not-exist.json'
    monkeypatch.setattr(canary,'fetch_landing_page',
                        lambda: SimpleNamespace(content=b'<html>Wrong content</html>',
                                                text='<html>Wrong content</html>'))
    monkeypatch.setattr(sys,'argv',['ibbi_canary.py','--output',str(dest)])
    with pytest.raises(SystemExit, match='CANARY FAIL'):
        canary.main()
    assert not dest.exists()
