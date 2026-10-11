"""Post-close, read-only official/API inputs; writes only a separate market namespace."""
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

import index_events
import market_closing_volume as market

REPO = 'gxaawill2-ui/tw-close-auction-mis-probe'


def api(path):
    if os.getenv('GITHUB_REPOSITORY') != REPO:
        raise RuntimeError('REPOSITORY_MISMATCH')
    request = urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        headers={'Authorization': 'Bearer '+os.environ['GITHUB_TOKEN'],
                 'Accept': 'application/vnd.github+json', 'User-Agent': 'market-closing-saved-evidence'})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read(2*1024*1024+1)
        if len(raw) > 2*1024*1024:
            raise ValueError('API_RESPONSE_TOO_LARGE')
        return json.loads(raw)


def run(root=Path('.')):
    import official_retry
    now = datetime.now(market.TZ)
    date, as_of = now.date().isoformat(), now.isoformat()
    base = root/'state/market-closing-volume'
    base.mkdir(parents=True, exist_ok=True)
    cal_path = root/'state/calendars'/(date[:4]+'.json')
    cal = json.loads(cal_path.read_text()) if cal_path.exists() else {}
    closed = cal.get('status') == 'OFFICIAL_ANNUAL_CALENDAR' and (now.weekday() >= 5 or date in cal.get('closed_dates', []))
    history = [json.loads(f.read_text()) for f in base.glob('20??-??-??.json')]
    evidence = {'reason': 'CAPTURE_NOT_AVAILABLE'}
    status, error = 'SUCCESS', None
    try:
        if not cal or cal.get('status') != 'OFFICIAL_ANNUAL_CALENDAR':
            raise ValueError('OFFICIAL_CALENDAR_UNAVAILABLE')
        if not closed:
            live_path = root/'state/live'/(date+'.json')
            live = json.loads(live_path.read_text()) if live_path.exists() else {}
            run_id = str(live.get('run_id', ''))
            if not run_id.isdigit() or live.get('trade_date') != date or not live.get('preclose_captured'):
                raise ValueError('SAVED_SAME_DATE_CAPTURE_UNAVAILABLE')
            entries = api('actions/runs/'+run_id+'/artifacts?per_page=100')['artifacts']
            selected = [a for a in entries if a['name'] == 'mis-probe-'+run_id and not a.get('expired')]
            if len(selected) != 1 or selected[0]['size_in_bytes'] > 64*1024*1024:
                raise ValueError('SAVED_ARTIFACT_UNAVAILABLE_OR_TOO_LARGE')
            archive = official_retry.download_archive(REPO, selected[0]['id'])
            output = root/'market-evidence'
            output.mkdir(exist_ok=True)
            (output/'saved-capture.zip').write_bytes(archive)
            url = 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date='+date.replace('-', '')+'&type=ALLBUT0999&response=json'
            fetcher = index_events.Fetcher(max_attempts=6)
            raw = fetcher.get_json(url)
            (output/'official-close.json').write_bytes(raw)
            as_of = datetime.now(market.TZ).isoformat()
            evidence = market.artifact_evidence(archive, date, json.loads(raw), as_of)
            evidence['source_evidence'].append({'source_url': url, 'observed_at': as_of,
                'sha256': market.hashlib.sha256(raw).hexdigest(), 'capture_run_id': run_id,
                'capture_artifact_id': selected[0]['id']})
    except Exception as exc:
        status, error = 'FAILED', type(exc).__name__
        evidence = {'reason': 'SOURCE_OR_CAPTURE_UNAVAILABLE; PRIOR_DATA_PRESERVED'}
    as_of = datetime.now(market.TZ).isoformat()
    row = market.calculate(date, evidence, history, as_of, 'HOLIDAY' if closed else 'TRADING' if cal else 'UNKNOWN')
    path = base/(date+'.json')
    # A failed fetch must not erase yesterday or an already verified same-day value.
    if status == 'SUCCESS' or not path.exists():
        market.save(root, row)
    old_health_path = base/'source-health.json'
    prior_health = json.loads(old_health_path.read_text()) if old_health_path.exists() else {}
    health = {'last_attempt_at': as_of, 'result': status, 'error_class': error,
              'trade_date': date, 'scope_status': row['source_quality'],
              'last_successful_attempt_at': as_of if status == 'SUCCESS' else prior_health.get('last_successful_attempt_at'),
              'last_failed_attempt_at': as_of if status == 'FAILED' else prior_health.get('last_failed_attempt_at'),
              'note': 'Retrieval success is separate from complete same-scope data; no MIS requests are made.'}
    old_health_path.write_text(json.dumps(health, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(health, ensure_ascii=False))
    return 0 if status == 'SUCCESS' else 2


if __name__ == '__main__':
    raise SystemExit(run())
