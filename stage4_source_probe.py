"""Bounded, read-only research proof. Respect robots; never request live MIS."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from index_events import Fetcher, TZ


def main():
    client = Fetcher(max_attempts=10)
    urls = ['https://openapi.twse.com.tw/v1/swagger.json',
            'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20261008&type=ALLBUT0999&response=json',
            'https://www.twse.com.tw/rwd/zh/afterTrading/MI_5MINS?date=20261008&response=json']
    results = []
    for url in urls:
        entry = {'source_url': url, 'checked_at': datetime.now(TZ).isoformat(),
                 'method': 'ANONYMOUS_GET_WITH_ROBOTS_AND_LIMITS'}
        try:
            raw = client.get_json(url)
            data = json.loads(raw)
            entry.update(http_status=200, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), response_date=data.get('date') if isinstance(data, dict) else None)
            if 'swagger' in url:
                entry['relevant_endpoints'] = {p: v.get('get', {}).get('summary') for p, v in data.get('paths', {}).items() if any(w in json.dumps(v, ensure_ascii=False) for w in ('零股', '定價', '五秒', '5秒'))}
            else:
                entry.update(stat=data.get('stat'), fields=data.get('fields'), notes=data.get('notes'),
                    tables=[{'title': t.get('title'), 'fields': t.get('fields'), 'notes': t.get('notes'), 'rows': len(t.get('data', []))} for t in data.get('tables', [])])
            entry['result'] = 'FETCHED; SCOPE_AND_USAGE_REVIEW_STILL_REQUIRED'
        except Exception as exc:
            entry.update(result='UNAVAILABLE_OR_RESTRICTED; NOT_NO_DATA', error=str(exc)[:200])
        results.append(entry)
    output = Path('reports/market-closing-volume')
    output.mkdir(parents=True, exist_ok=True)
    (output/'official-source-probe.json').write_text(json.dumps({'checked_at': datetime.now(TZ).isoformat(), 'request_attempts': client.attempts, 'results': results}, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'source_count': len(results), 'successful_reads': sum(r.get('http_status') == 200 for r in results), 'request_attempts': client.attempts}))


if __name__ == '__main__':
    main()
