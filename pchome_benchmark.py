#!/usr/bin/env python3
"""One full-market PChome connectivity benchmark; never a MIS snapshot or signal."""
import concurrent.futures
import csv
import gzip
import hashlib
import html
import http.cookiejar
import json
import math
import re
import socket
import statistics
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from probe import fetch_universe, get_bytes, TWSE_CLOSE, TPEX_CLOSE

TZ = ZoneInfo('Asia/Taipei')
OUT = Path('pchome-results')
CONCURRENCY = 5
TIMEOUT = 20
LOCAL = threading.local()
STOP = threading.Event()
LOCK = threading.Lock()
LIMIT_ERRORS = 0
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html',
           'Referer': 'https://stock.pchome.com.tw/'}


def stamp():
    return datetime.now(TZ).isoformat(timespec='milliseconds')


def number(value):
    try:
        n = float(value.replace(',', '').strip())
        return n if math.isfinite(n) else None
    except (ValueError, AttributeError):
        return None


def parse_page(page, code):
    title = re.search(r'<title[^>]*>(.*?)</title>', page, re.S | re.I)
    title = html.unescape(title.group(1)).strip() if title else ''
    # Restrict parsing to the actual seven-column price/volume table.
    header = page.find('累計量(張)')
    table_end = page.find('</table', header) if header >= 0 else -1
    section = page[header:table_end] if table_end >= 0 else ''
    records = []
    invalid = []
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr\s*>', section, re.S | re.I):
        cells = [html.unescape(re.sub(r'<[^>]*>', '', x)).strip()
                 for x in re.findall(r'<td\b[^>]*>(.*?)</td\s*>', row, re.S | re.I)]
        if len(cells) != 7 or not re.fullmatch(r'\d{2}:\d{2}:\d{2}', cells[0]):
            continue
        item = {'time': cells[0], 'price': number(cells[3]),
                'size': number(cells[5]), 'cumulative_volume': number(cells[6]),
                'source_row_index': len(records), 'raw_cells': cells}
        if item['price'] is None or item['price'] <= 0 or item['cumulative_volume'] is None:
            invalid.append(item)
        records.append(item)
    valid = [r for r in records if r['price'] is not None and r['price'] > 0
             and r['cumulative_volume'] is not None]
    # Cumulative volume resolves same-second ordering; do not fabricate subsecond times.
    before = [r for r in valid if r['time'] < '13:25:00']
    pre = max(before, key=lambda r: (r['time'], r['cumulative_volume']), default=None)
    closing = [r for r in valid if '13:30:00' <= r['time'] <= '13:33:15']
    close = max(closing, key=lambda r: (r['time'], r['cumulative_volume']), default=None)
    dates = sorted(set(re.findall(r'20\d{2}[-/]\d{1,2}[-/]\d{1,2}', section)))
    return {'title': title, 'code_match': f'({code})' in title,
            'trade_row_count': len(records), 'invalid_row_count': len(invalid),
            'before_cutoff_observation': pre, 'close_time_observation': close,
            'trade_table_date_literals': dates, 'trade_date_verified': False,
            'trial_exclusion_verified': False, 'full_tick_completeness_verified': False,
            'records': records}


def opener():
    if not hasattr(LOCAL, 'opener'):
        LOCAL.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    return LOCAL.opener


def fetch_stock(stock):
    global LIMIT_ERRORS
    result = dict(stock, started_at=stamp(), attempts=[], errors=[], retries=0,
                  status='not_attempted', trade_row_count=0)
    if STOP.is_set():
        result['error'] = 'stopped_after_repeated_rate_limit_or_access_denial'
        return result
    url = f'https://stock.pchome.com.tw/stock/sto0/ock3/sid{stock["code"]}.html'
    result['url'] = url
    started = time.monotonic()
    post_form = False
    page = ''
    raw = b''
    for attempt in range(3):
        at, tick = stamp(), time.monotonic()
        req = urllib.request.Request(url, data=b'is_check=1' if post_form else None,
                                     headers=dict(HEADERS, Referer=url))
        request_log = {'started_at': at, 'method': 'POST' if post_form else 'GET',
                       'http_status': None, 'error': None}
        try:
            with opener().open(req, timeout=TIMEOUT) as response:
                raw = response.read()
                request_log['http_status'] = response.status
                request_log['bytes'] = len(raw)
                page = raw.decode(response.headers.get_content_charset() or 'utf-8', 'replace')
            if "name='is_check'" in page and len(raw) < 2000:
                # Follow the public page's ordinary automatic form, without any login.
                request_log['public_auto_form'] = True
                post_form = True
                result['status'] = 'public_auto_form'
            else:
                result['status'] = 'received'
        except urllib.error.HTTPError as exc:
            request_log.update(http_status=exc.code, error=f'HTTP_{exc.code}')
            raw = exc.read()
            page = raw.decode('utf-8', 'replace')
            result['errors'].append(request_log['error'])
            if exc.code in (403, 429):
                with LOCK:
                    LIMIT_ERRORS += 1
                    if LIMIT_ERRORS >= 5:
                        STOP.set()
                result['status'] = 'access_denied_or_rate_limit'
            else:
                result['status'] = 'http_error'
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            request_log['error'] = f'{type(exc).__name__}:{exc}'
            result['errors'].append(request_log['error'])
            result['status'] = 'network_error'
        finally:
            request_log.update(finished_at=stamp(), latency_ms=round((time.monotonic()-tick)*1000, 3))
            result['attempts'].append(request_log)
        if result['status'] in ('received', 'access_denied_or_rate_limit'):
            break
        if attempt >= 1:
            break
        if request_log.get('error'):
            result['retries'] += 1
            time.sleep(0.5)
    parse_start = time.monotonic()
    parsed = parse_page(page, stock['code'])
    records = parsed.pop('records')
    result.update(parsed)
    if result['status'] == 'received':
        result['status'] = ('parsed' if parsed['code_match'] and parsed['trade_row_count']
                            and not parsed['invalid_row_count'] else 'empty_or_invalid_table')
    result.update(finished_at=stamp(), elapsed_ms=round((time.monotonic()-started)*1000, 3),
                  parse_ms=round((time.monotonic()-parse_start)*1000, 3),
                  sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=len(raw))
    key = f'{stock["market"]}-{stock["code"]}'
    (OUT/'raw'/f'{key}.html.gz').write_bytes(gzip.compress(raw))
    (OUT/'trades'/f'{key}.json.gz').write_bytes(gzip.compress(
        json.dumps(records, ensure_ascii=False).encode()))
    return result


def pct(values, percent):
    return values[max(0, math.ceil(len(values)*percent)-1)] if values else None


def main():
    OUT.mkdir(exist_ok=True)
    (OUT/'raw').mkdir(exist_ok=True)
    (OUT/'trades').mkdir(exist_ok=True)
    universe = fetch_universe()
    (OUT/'universe.json').write_text(json.dumps(universe, ensure_ascii=False, indent=2))
    print(json.dumps({'phase':'universe_ready','count':len(universe),'concurrency':CONCURRENCY,
                      'started_at':stamp()},ensure_ascii=False),flush=True)
    started, tick = stamp(), time.monotonic()
    results = []
    with (OUT/'requests.jsonl').open('w') as log:
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = [pool.submit(fetch_stock, s) for s in universe]
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                results.append(row)
                log.write(json.dumps(row, ensure_ascii=False)+'\n'); log.flush()
                if len(results)%100 == 0 or len(results)==len(universe):
                    print(json.dumps({'done':len(results),'total':len(universe),
                        'parsed':sum(r['status']=='parsed' for r in results),
                        'wall_s':round(time.monotonic()-tick,3),'stopped':STOP.is_set()}),flush=True)
    wall = time.monotonic()-tick
    finished = stamp()
    keys = {f'{s["market"]}:{s["code"]}' for s in universe}
    good = {f'{r["market"]}:{r["code"]}' for r in results if r['status']=='parsed'}
    attempted = [r for r in results if r['attempts']]
    latencies = sorted(a['latency_ms'] for r in results for a in r['attempts'])
    errors = [a for r in results for a in r['attempts'] if a.get('error')]
    summary = {'benchmark_only':True,'capture_kind':'postclose_public_web_fetch',
        'retrieval_date':datetime.now(TZ).date().isoformat(), 'source_trade_date':'unverified',
        'universe_count':len(universe), 'concurrency':CONCURRENCY, 'batch_api':False,
        'started_at':started,'finished_at':finished,'wall_time_seconds':round(wall,3),
        'attempted_stocks':len(attempted),'request_count':len(latencies),
        'parsed_stocks':len(good),'missing_count':len(keys-good), 'missing_codes':sorted(keys-good),
        'successful_code_set_equals_universe':good==keys,
        'http_errors':sum(bool(a.get('http_status') and a['http_status']>=400) for a in errors),
        'timeout':sum('timed out' in a['error'].lower() or 'timeout' in a['error'].lower() for a in errors),
        'retry':sum(r['retries'] for r in results),
        'public_auto_form_count':sum(bool(a.get('public_auto_form')) for r in results for a in r['attempts']),
        'rate_limit_429':sum(a.get('http_status')==429 for a in errors),
        'access_denied_403':sum(a.get('http_status')==403 for a in errors),
        'empty_or_invalid_table':sum(r['status']=='empty_or_invalid_table' for r in results),
        'duplicate_stock_results':len(results)-len({(r['market'],r['code']) for r in results}),
        'stocks_with_before_cutoff_row':sum(bool(r.get('before_cutoff_observation')) for r in results),
        'stocks_with_close_time_row':sum(bool(r.get('close_time_observation')) for r in results),
        'request_latency_ms':{'min':min(latencies) if latencies else None,
            'mean':statistics.mean(latencies) if latencies else None,
            'median':statistics.median(latencies) if latencies else None,
            'p95':pct(latencies,.95),'max':max(latencies) if latencies else None},
        'stop_reason':'repeated_access_denial_or_rate_limit' if STOP.is_set() else None,
        'trial_exclusion_verified':False,'tick_completeness_verified':False,
        'signals_generated':False,
        'note':'Price observations are unvalidated. This is not a missed MIS preclose snapshot.'}
    # Keep complete official daily responses for later date/price/volume comparison.
    official = []
    for market,url in [('TWSE',TWSE_CLOSE),('TPEx',TPEX_CLOSE)]:
        try:
            status,raw = get_bytes(url,35)
            (OUT/f'official-{market}.json').write_bytes(raw)
            data = json.loads(raw.decode('utf-8-sig'))
            official.append({'market':market,'url':url,'status':status,
                'sample':data[:2] if isinstance(data,list) else data})
        except Exception as exc:
            official.append({'market':market,'url':url,'error':str(exc)})
    (OUT/'official_metadata.json').write_text(json.dumps(official,ensure_ascii=False,indent=2))
    (OUT/'performance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    (OUT/'missing_errors.json').write_text(json.dumps(
        [r for r in results if r['status']!='parsed' or r['errors']],ensure_ascii=False,indent=2))
    with (OUT/'observations.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['code','name','market','status','rows','before_time',
            'before_price','close_time','close_price','elapsed_ms','trade_date_verified'])
        writer.writeheader()
        for r in sorted(results,key=lambda r:(r['market'],r['code'])):
            pre,close=r.get('before_cutoff_observation') or {},r.get('close_time_observation') or {}
            writer.writerow({'code':r['code'],'name':r['name'],'market':r['market'],
                'status':r['status'],'rows':r['trade_row_count'],'before_time':pre.get('time'),
                'before_price':pre.get('price'),'close_time':close.get('time'),
                'close_price':close.get('price'),'elapsed_ms':r.get('elapsed_ms'),
                'trade_date_verified':False})
    with zipfile.ZipFile('pchome-benchmark.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in OUT.rglob('*'):
            if path.is_file(): z.write(path,path.as_posix())
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
