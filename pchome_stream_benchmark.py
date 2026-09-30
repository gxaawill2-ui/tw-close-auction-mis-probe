#!/usr/bin/env python3
"""Read only an HTML prefix containing the newest pre-13:25 observation.

Postclose connectivity benchmark only. No trade-date/trial validation or signals.
"""
import concurrent.futures
import csv
import gzip
import hashlib
import json
import os
import statistics
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from probe import fetch_universe
from pchome_benchmark import opener, parse_page, stamp, pct

OUT = Path('stream-results')
STOP = threading.Event()
CONCURRENCY = 5
CHUNK = 4096
MAX_BYTES = 2_000_000


def prefix_observation(raw, code):
    page = raw.decode('utf-8', 'replace')
    header = page.find('累計量(張)')
    if header < 0:
        return None, False, None
    end = page.find('</table', header)
    parsed = parse_page(page if end >= 0 else page + '</table>', code)
    rows = parsed.pop('records')
    valid = [r for r in rows if r['price'] is not None and r['price'] > 0
             and r['cumulative_volume'] is not None]
    order_ok = all((a['time'], a['cumulative_volume']) >=
                   (b['time'], b['cumulative_volume']) for a, b in zip(valid, valid[1:]))
    before = [r for r in valid if r['time'] < '13:25:00']
    candidate = parsed['before_cutoff_observation']
    # Read the entire first eligible second to resolve multiple same-second rows.
    boundary_seen = bool(candidate and any(r['time'] < candidate['time'] for r in before))
    done = end >= 0 or (boundary_seen and order_ok)
    parsed.update(prefix_order_descending_observed=order_ok,
                  entire_table_received=end >= 0,
                  same_second_group_boundary_seen=boundary_seen)
    return candidate, done, parsed


def fetch(stock):
    result = dict(stock, status='not_attempted', attempts=[], started_at=stamp())
    if STOP.is_set():
        return result
    url = f'https://stock.pchome.com.tw/stock/sto0/ock3/sid{stock["code"]}.html'
    started = time.monotonic()
    raw = b''
    parsed = None
    candidate = None
    form = False
    for attempt in range(2):
        if STOP.is_set():
            break
        tick = time.monotonic()
        log = {'started_at':stamp(), 'method':'POST' if form else 'GET',
               'http_status':None, 'bytes_read':0}
        try:
            request = urllib.request.Request(url, data=b'is_check=1' if form else None,
                headers={'User-Agent':'Mozilla/5.0','Accept':'text/html',
                         'Accept-Encoding':'identity','Referer':url})
            with opener().open(request, timeout=20) as response:
                raw = b''
                log.update(http_status=response.status,
                    content_length=response.headers.get('Content-Length'),
                    content_encoding=response.headers.get('Content-Encoding'))
                while len(raw) < MAX_BYTES:
                    chunk = response.read1(CHUNK)
                    if not chunk:
                        log['eof'] = True
                        break
                    raw += chunk
                    candidate, done, parsed = prefix_observation(raw, stock['code'])
                    if done:
                        log['stopped_after_target_group'] = True
                        break
                log['bytes_read'] = len(raw)
                log['body_is_complete'] = bool(log.get('eof'))
            if b"name='is_check'" in raw and len(raw) < 2000 and not form:
                form = True
                log['public_auto_form'] = True
            else:
                result['status'] = ('observation_found' if candidate and parsed and
                    parsed['code_match'] and parsed['prefix_order_descending_observed']
                    else 'empty_or_invalid')
                break
        except urllib.error.HTTPError as exc:
            raw = exc.read(4096)
            log.update(http_status=exc.code,bytes_read=len(raw),
                       error=f'HTTP_{exc.code}',retry_after=exc.headers.get('Retry-After'))
            result['status'] = 'http_error'
            if exc.code in (403,429):
                STOP.set()  # No retry, rotation, or follow-up after rate/access limit.
            break
        except Exception as exc:
            log['error'] = f'{type(exc).__name__}:{exc}'
            result['status'] = 'network_error'
            break
        finally:
            log.update(finished_at=stamp(),latency_ms=round((time.monotonic()-tick)*1000,3))
            result['attempts'].append(log)
    result.update(finished_at=stamp(),elapsed_ms=round((time.monotonic()-started)*1000,3),
        bytes_read=sum(a['bytes_read'] for a in result['attempts']),
        observation=candidate, prefix_metadata=parsed,
        trade_date_verified=False,trial_exclusion_verified=False,
        latest_trade_order_verified=False,signals_generated=False,
        raw_prefix_sha256=hashlib.sha256(raw).hexdigest())
    (OUT/'prefix'/f'{stock["market"]}-{stock["code"]}.html.gz').write_bytes(gzip.compress(raw))
    return result


def balanced_order(universe):
    priority = ['2330','2317','2454','1341','1410','1240','1781','1813']
    chosen = [s for code in priority for s in universe if s['code']==code]
    seen = {s['code'] for s in chosen}
    tw = [s for s in universe if s['market']=='TWSE' and s['code'] not in seen]
    tp = [s for s in universe if s['market']=='TPEx' and s['code'] not in seen]
    rest = [s for pair in __import__('itertools').zip_longest(tw,tp) for s in pair if s]
    return chosen + rest


def main():
    (OUT/'prefix').mkdir(parents=True,exist_ok=True)
    universe_started = stamp()
    universe = fetch_universe()
    (OUT/'universe.json').write_text(json.dumps(universe,ensure_ascii=False,indent=2))
    print(json.dumps({'phase':'universe_ready','count':len(universe),
                      'time':stamp()},ensure_ascii=False),flush=True)
    started, tick = stamp(), time.monotonic()
    results = []
    ordered = balanced_order(universe)
    # Keep only five futures pending, so a stop doesn't queue thousands of calls.
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        stocks = iter(ordered)
        active = {pool.submit(fetch,next(stocks)) for _ in range(min(CONCURRENCY,len(ordered)))}
        with (OUT/'requests.jsonl').open('w') as log:
            while active:
                done,active = concurrent.futures.wait(active,return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    row = future.result()
                    results.append(row)
                    log.write(json.dumps(row,ensure_ascii=False)+'\n'); log.flush()
                    if not STOP.is_set():
                        stock = next(stocks,None)
                        if stock: active.add(pool.submit(fetch,stock))
                if len(results)%25==0 or STOP.is_set():
                    print(json.dumps({'processed':len(results),'wall_s':round(time.monotonic()-tick,3),
                                      'stopped':STOP.is_set()}),flush=True)
    finished = stamp()
    wall = time.monotonic()-tick
    seen = {r['code'] for r in results}
    results.extend(dict(s,status='not_attempted',attempts=[]) for s in universe if s['code'] not in seen)
    attempts = [a for r in results for a in r['attempts']]
    latencies = sorted(a['latency_ms'] for a in attempts)
    good = [r for r in results if r['status']=='observation_found']
    summary = {'benchmark_only':True,'capture_kind':'postclose_streamed_HTML_prefix',
        'universe_count':len(universe),'concurrency':CONCURRENCY,'chunk_bytes':CHUNK,
        'universe_fetch_started_at':universe_started,'started_at':started,'finished_at':finished,
        'wall_time_seconds':round(wall,3),'attempted_stocks':sum(bool(r['attempts']) for r in results),
        'request_count':len(attempts),'observation_found':len(good),
        'market_success':{m:sum(r['market']==m for r in good) for m in ['TWSE','TPEx']},
        'not_attempted':sum(r['status']=='not_attempted' for r in results),
        'empty_or_invalid':sum(r['status']=='empty_or_invalid' for r in results),
        'http_429':sum(a.get('http_status')==429 for a in attempts),
        'http_403':sum(a.get('http_status')==403 for a in attempts),
        'http_errors':sum((a.get('http_status') or 0)>=400 for a in attempts),
        'timeout':sum('timeout' in a.get('error','').lower() or 'timed out' in a.get('error','').lower() for a in attempts),
        'retry':0,'public_auto_form':sum(bool(a.get('public_auto_form')) for a in attempts),
        'total_bytes_read':sum(a['bytes_read'] for a in attempts),
        'successful_bytes_mean':statistics.mean(r['bytes_read'] for r in good) if good else None,
        'successful_bytes_median':statistics.median(r['bytes_read'] for r in good) if good else None,
        'latency_ms':{'min':min(latencies) if latencies else None,
            'mean':statistics.mean(latencies) if latencies else None,
            'median':statistics.median(latencies) if latencies else None,
            'p95':pct(latencies,.95),'max':max(latencies) if latencies else None},
        'full_market_complete':len(good)==len(universe),
        'missing_codes':sorted(s['code'] for s in universe if s['code'] not in {r['code'] for r in good}),
        'stop_reason':'HTTP_403_or_429_stop_first' if STOP.is_set() else None,
        'trade_date_verified':False,'trial_exclusion_verified':False,'signals_generated':False,
        'note':'bytes_read is application consumption, not proven network wire bytes or server work saved. Prefix ordering is observed, not guaranteed by source. No missed MIS snapshot is backfilled.'}
    (OUT/'performance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    (OUT/'all_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    (OUT/'missing_errors.json').write_text(json.dumps([r for r in results if r['status']!='observation_found'],ensure_ascii=False,indent=2))
    with (OUT/'observations.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['code','name','market','status','time','price','cumulative_volume','bytes_read','elapsed_ms'])
        writer.writeheader()
        for r in sorted(results,key=lambda r:r['code']):
            ob=r.get('observation') or {}
            writer.writerow(dict(code=r['code'],name=r['name'],market=r['market'],status=r['status'],
                time=ob.get('time'),price=ob.get('price'),cumulative_volume=ob.get('cumulative_volume'),
                bytes_read=r.get('bytes_read'),elapsed_ms=r.get('elapsed_ms')))
    with zipfile.ZipFile('pchome-stream-benchmark.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in OUT.rglob('*'):
            if path.is_file():z.write(path,path.as_posix())
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
            f.write('## Streaming benchmark (unvalidated observations)\n\n```json\n'+
                json.dumps({k:v for k,v in summary.items() if k!='missing_codes'},indent=2)+'\n```\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='missing_codes'},ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
