"""Five fixed Fugle requests; publish only connection/schema metadata, never quotes or keys."""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

BRANCH = 'stage4/20261016-fugle-probe'
REPO = 'gxaawill2-ui/tw-close-auction-mis-probe'
BASE = 'https://api.fugle.tw/marketdata/v1.0/stock/intraday/'
TARGETS = [('2330', 'quote', ''), ('2330', 'trades', '?limit=5&offset=0&sort=desc&isTrial=false'),
           ('2330', 'trades', '?limit=5&offset=5&sort=desc&isTrial=false'),
           ('6488', 'quote', ''), ('6488', 'trades', '?limit=5&offset=0&sort=desc&isTrial=false')]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def positive(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and value > 0


def summarize(payload, code, kind, today):
    """Fixed booleans/counts only; no arbitrary provider strings or market values."""
    result = {'date_matches_today': payload.get('date') == today,
              'symbol_matches': payload.get('symbol') == code}
    if kind == 'quote':
        trade = payload.get('lastTrade')
        result['actual_last_trade_fields'] = isinstance(trade, dict) and all(
            positive(trade.get(k)) for k in ('price', 'time', 'serial'))
        result['trial_flag_present'] = isinstance(payload.get('isTrial'), bool)
        result['close_flag_present'] = isinstance(payload.get('isClose'), bool)
        result['schema_pass'] = all(result[k] for k in ('date_matches_today', 'symbol_matches', 'actual_last_trade_fields'))
    else:
        rows = payload.get('data')
        valid = isinstance(rows, list) and 0 < len(rows) <= 5 and all(
            isinstance(row, dict) and all(positive(row.get(k)) for k in ('price', 'size', 'time', 'serial')) for row in rows)
        result['row_count'] = len(rows) if isinstance(rows, list) else 0
        result['actual_trade_fields'] = valid
        result['schema_pass'] = result['date_matches_today'] and result['symbol_matches'] and valid
    return result


def probe(key, opener=None, today=None):
    if not isinstance(key, str) or len(key) < 20 or not re.fullmatch(r'[A-Za-z0-9+/_=-]+', key):
        raise ValueError('ISOLATED_KEY_NOT_CONFIGURED')
    opener = opener or urllib.request.build_opener(NoRedirect()).open
    today = today or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    report = {'scope': 'AUTHENTICATED_FUGLE_CONNECTION_AND_SCHEMA_ONLY', 'trade_date': today,
              'verified_count': 0, 'p_before_proven': False, 'p_close_proven': False,
              'raw_market_data_saved': False, 'key_expires_at': '2026-11-14T00:00:00+08:00',
              'requests': []}
    for code, kind, query in TARGETS:
        receipt = {'symbol': code, 'endpoint': kind, 'page_offset': 5 if 'offset=5' in query else 0,
                   'requested_at': datetime.now(timezone.utc).isoformat()}
        request = urllib.request.Request(BASE + kind + '/' + code + query,
                                         headers={'X-API-KEY': key, 'Accept': 'application/json'})
        try:
            with opener(request, timeout=12) as response:
                receipt['http_status'] = response.status
                raw = response.read(262145)
            if receipt['http_status'] != 200 or len(raw) > 262144:
                receipt['error'] = 'HTTP_OR_SIZE_REJECTED'
            else:
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError('SCHEMA')
                receipt.update(summarize(payload, code, kind, today))
        except urllib.error.HTTPError as error:
            receipt.update(http_status=error.code, error='HTTP_REJECTED')
        except Exception:
            # Neither exception text, body, headers nor credentials are serialized.
            receipt['error'] = 'NETWORK_OR_SCHEMA_ERROR'
        receipt['received_at'] = datetime.now(timezone.utc).isoformat()
        report['requests'].append(receipt)
        if receipt.get('http_status') in (401, 403, 429):
            break
    report['status'] = 'PASS' if len(report['requests']) == 5 and all(r.get('schema_pass') for r in report['requests']) else 'FAIL'
    return report


def main():
    if os.getenv('GITHUB_REPOSITORY') != REPO or os.getenv('GITHUB_REF') != 'refs/heads/' + BRANCH:
        raise ValueError('REFUSE_NONISOLATED_RUN')
    report = probe(os.getenv('FUGLE_API_KEY'))
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    print(encoded)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text('## Fugle isolated connection test\n\n```json\n' + encoded + '\n```\n')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        print('ISOLATED_FUGLE_PROBE_FAILED_NO_CREDENTIALS_LOGGED')
        raise SystemExit(1)
