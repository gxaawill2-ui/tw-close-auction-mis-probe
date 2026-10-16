"""Isolated bounded source/vault clients, fair queue, durable versions and safe views.

No MIS requests, no production writes. Raw Fugle evidence never enters public views.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from datetime import datetime
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import freshness as f
from fast_selection import atomic, safe_output
from stage3_publication import Publisher, BackgroundPublisher, envelope
from stage3_ticks import canonical, trade_time, identity

BASE = 'https://tw-tail-stage4-20261015-test.gxaawill2.workers.dev'


class LocalVault:
    """Private runner-only fallback. Never claim this survives runner destruction."""
    def save(self, event, date):
        return {'id':hashlib.sha256(canonical(event).encode()).hexdigest(),'sha256':event['sha256'],
            'private_written_at':event['persisted_at'],'storage_kind':'RUNNER_PRIVATE_TEMPORARY',
            'recoverable_after_job':False}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Vault:
    def __init__(self, token, key, *, base=BASE, opener=None):
        if base != BASE:
            raise ValueError('EXACT_ISOLATED_VAULT_REQUIRED')
        if not all(isinstance(s, str) and re.fullmatch(r'[a-f0-9]{64}', s) for s in (token, key)):
            raise ValueError('ISOLATED_WRITER_NOT_CONFIGURED')
        self.token, self.key, self.base = token, key, base
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open

    def save(self, event, date):
        ident = hashlib.sha256(canonical(event).encode()).hexdigest()
        body = {'scope': 'PRIVATE_FUGLE_EVIDENCE', 'id': ident, 'trade_date': date, 'event': event}
        raw = canonical(envelope(body, self.key)).encode()
        if len(raw) > 98304:
            raise ValueError('PRIVATE_EVENT_TOO_LARGE')
        req = urllib.request.Request(self.base + '/private-evidence/' + date + '/' + ident,
            method='POST', data=raw, headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        for attempt in range(3):
            try:
                with self.opener(req, timeout=6) as response:
                    receipt = json.loads(response.read(4097))
                    if response.status != 200 or receipt.get('id') != ident or receipt.get('sha256') != event['sha256'] or not f.parsed_time(receipt.get('private_written_at')):
                        raise ValueError('PRIVATE_WRITE_RECEIPT_MISMATCH')
                return {**receipt,'storage_kind':'ISOLATED_PRIVATE_CLOUDFLARE','recoverable_after_job':True}
            except urllib.error.HTTPError as exc:
                if exc.code not in (408, 425, 429, 500, 502, 503, 504) or attempt == 2:
                    raise ValueError('PRIVATE_WRITE_HTTP_' + str(exc.code)) from None
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise ValueError('PRIVATE_WRITE_UNAVAILABLE') from None
            time.sleep(attempt + 1)

    def read(self, date, ident):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) or not re.fullmatch(r'index|[a-f0-9]{64}', ident):
            raise ValueError('INVALID_PRIVATE_READ')
        req = urllib.request.Request(self.base + '/private-evidence/' + date + '/' + ident,
            headers={'Authorization': 'Bearer ' + self.token})
        with self.opener(req, timeout=6) as response:
            return json.loads(response.read(200000))


class Source:
    def __init__(self, key, directory, vault, *, max_requests=160, opener=None, clock=None, wait=time.sleep):
        if not isinstance(key, str) or len(key) < 20 or not re.fullmatch(r'[A-Za-z0-9+/_=-]+', key):
            raise ValueError('FUGLE_KEY_NOT_CONFIGURED')
        self.key, self.vault = key, vault
        self.directory = safe_output(directory)
        os.chmod(self.directory, 0o700)
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open
        self.clock = clock or (lambda: datetime.now(f.TZ))
        self.wait, self.max_requests = wait, max_requests
        self.lock = threading.Lock()
        self.count, self.last, self.stopped = 0, None, False

    def request(self, candidate, kind, query, deadline):
        if candidate.get('ex') not in ('tse', 'otc') or not re.fullmatch(r'[1-9]\d{3}', candidate.get('code', '')) or kind not in ('quote', 'trades'):
            raise ValueError('INVALID_SOURCE_SCOPE')
        date = self.clock().date().isoformat()
        params = dict(query)
        if kind == 'trades':
            if not 1 <= params.get('limit', 0) <= 200 or params.get('sort') not in ('desc', 'asc') or params.get('isTrial') is not False:
                raise ValueError('ACTUAL_BOUNDED_TRADES_REQUIRED')
            params['isTrial'] = 'false'
        url = 'https://api.fugle.tw/marketdata/v1.0/stock/intraday/' + kind + '/' + candidate['code']
        if params:
            url += '?' + urllib.parse.urlencode(params)
        for attempt in range(2):
            # One shared start-time limiter across all candidate workers, <=47/min.
            with self.lock:
                if self.stopped or self.count >= self.max_requests:
                    raise ValueError('SOURCE_REQUEST_BUDGET_EXHAUSTED')
                if self.last:
                    gap = 1.3 - (self.clock() - self.last).total_seconds()
                    if gap > 0:
                        self.wait(gap)
                if (deadline - self.clock()).total_seconds() < 14:
                    raise ValueError('SOURCE_DEADLINE_EXHAUSTED')
                self.count += 1
                self.last = self.clock()
                began = self.last.isoformat()
            req = urllib.request.Request(url, headers={'X-API-KEY': self.key, 'Accept': 'application/json', 'Cache-Control': 'no-cache'})
            try:
                with self.opener(req, timeout=6) as response:
                    status, raw = response.status, response.read(80001)
                    headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in ('date', 'age', 'cache-control')}
                if status != 200 or len(raw) > 80000:
                    raise ValueError('SOURCE_HTTP_OR_SIZE_REJECTED')
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403, 429):
                    with self.lock:
                        self.stopped = True
                if exc.code not in (408, 500, 502, 503, 504) or attempt:
                    raise ValueError('SOURCE_HTTP_' + str(exc.code)) from None
            except (OSError, TimeoutError):
                if attempt:
                    raise ValueError('SOURCE_NETWORK_UNAVAILABLE') from None
        received = self.clock().isoformat()
        # Save bytes before parsing. Local copy is private and is never an artifact.
        digest = hashlib.sha256(raw).hexdigest()
        path = self.directory / (digest + '.json')
        if not path.exists():
            with path.open('xb') as out:
                os.chmod(path, 0o600)
                out.write(raw); out.flush(); os.fsync(out.fileno())
        event = {'source': 'FUGLE', 'raw': raw.decode('utf8'), 'sha256': digest,
            'requested_at': began, 'received_at': received, 'persisted_at': self.clock().isoformat(),
            'http_status': status, 'query': query, 'headers': headers, 'symbol': candidate['code'], 'kind': kind}
        receipt = self.vault.save(event, date)
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get('date') != date or payload.get('symbol') != candidate['code'] or payload.get('exchange') != {'tse':'TWSE','otc':'TPEx'}[candidate['ex']] or payload.get('type') != 'EQUITY':
            raise ValueError('SOURCE_IDENTITY_OR_DATE_MISMATCH')
        event['private_receipt'] = receipt
        return event, payload

    def collect(self, candidate, date, deadline, *, max_pages=24, tail_only=False):
        if self.clock().date().isoformat() != date:
            raise ValueError('NO_HISTORICAL_LIVE_CAPTURE')
        bundle = {'source':'FUGLE', 'origin_kind':'AUTHENTICATED_HTTP', 'trade_date':date, 'pages':[]}
        try:
            bundle['quote_before'], _ = self.request(candidate, 'quote', {}, deadline)
            offset = 0
            for _ in range(max_pages):
                query = {'offset':offset, 'limit':200, 'sort':'desc', 'isTrial':False}
                event, data = self.request(candidate, 'trades', query, deadline)
                rows = data.get('data')
                if not isinstance(rows, list) or len(rows) > 200:
                    raise ValueError('SOURCE_MALFORMED_PAGE')
                bundle['pages'].append(event); offset += len(rows)
                if len(rows) < 200:
                    bundle['terminal_page'] = True; break
                if tail_only and any(trade_time(t['time']) < f.parsed_time(date+'T13:25:00+08:00') for t in rows):
                    bundle['terminal_page'] = False; break
            else:
                bundle['terminal_page'] = False
            bundle['quote_after'], _ = self.request(candidate, 'quote', {}, deadline)
            bundle['status'] = 'COLLECTED_NOT_VALIDATED'
        except Exception as exc:
            bundle.update(status='SOURCE_INCOMPLETE', error=str(exc) if isinstance(exc, ValueError) and str(exc).startswith(('SOURCE_', 'PRIVATE_')) else type(exc).__name__)
        if all(k in bundle for k in ('quote_before','quote_after')) and bundle['pages']:
            manifest={k:bundle[k] for k in ('source','origin_kind','trade_date','status')}
            manifest['quote_before_id']=bundle['quote_before']['private_receipt']['id']
            manifest['quote_after_id']=bundle['quote_after']['private_receipt']['id']
            manifest['page_ids']=[p['private_receipt']['id'] for p in bundle['pages']]
            manifest['terminal_page']=bundle.get('terminal_page',False)
            raw=canonical(manifest);at=self.clock().isoformat()
            event={'source':'FUGLE','kind':'bundle_manifest','origin_kind':'PRIVATE_MANIFEST_NOT_PROVIDER_RESPONSE',
                'raw':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'requested_at':at,'received_at':at,
                'persisted_at':at,'http_status':200,'symbol':candidate['code']}
            try:bundle['private_manifest_receipt']=self.vault.save(event,date)
            except Exception:bundle['manifest_persistence_error']='PRIVATE_MANIFEST_NOT_SAVED'
        return bundle


def restore_bundle(vault, date, manifest_id):
    """Recover from private immutable objects; supplied verdicts are never restored."""
    saved=vault.read(date,manifest_id);event=saved['event']
    if event.get('kind')!='bundle_manifest' or hashlib.sha256(event['raw'].encode()).hexdigest()!=event['sha256']:
        raise ValueError('INVALID_PRIVATE_MANIFEST')
    bundle=json.loads(event['raw']);bundle['pages']=[]
    if bundle.get('trade_date')!=date:raise ValueError('PRIVATE_MANIFEST_DATE_MISMATCH')
    def read(ident):
        saved=vault.read(date,ident);e=saved['event']
        if saved.get('id')!=ident or hashlib.sha256(canonical(e).encode()).hexdigest()!=ident or hashlib.sha256(e['raw'].encode()).hexdigest()!=e['sha256']:
            raise ValueError('PRIVATE_RECOVERY_HASH_MISMATCH')
        e['private_receipt']={'id':ident,'sha256':e['sha256'],'private_written_at':saved['private_written_at'],
            'storage_kind':'ISOLATED_PRIVATE_CLOUDFLARE','recoverable_after_job':True}
        return e
    bundle['quote_before']=read(bundle.pop('quote_before_id'))
    bundle['quote_after']=read(bundle.pop('quote_after_id'))
    bundle['pages']=[read(ident) for ident in bundle.pop('page_ids')]
    return bundle


PUBLIC_FIELDS = ('code','name','ex','market','P_before','P_close','P_before_trade_time','P_close_trade_time',
    'tail_return_pct','closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct',
    'volume_status','volume_unit','first_seen_at','pre_received_at','pre_saved_at','close_received_at',
    'verification_status','validated','checks','missing_requirements','updated_at','evaluated_at',
    'evidence_as_of','source_acquired_at','public_observed_at','simulated_only','simulation_passed')


def public_view(view):
    """Allowlist MIS-derived values; never return a provider tick or provider prices."""
    if view.get('mode') != 'LIVE':
        raise ValueError('PUBLIC_REAL_VIEW_REQUIRES_LIVE_MODE')
    keys = ('schema_version','trade_date','mode','is_synthetic','generated_at','assessment_as_of','version',
        'verified_count','research_count','unknown_candidate_count','universe_count','screening_calculable_count',
        'screening_unresolved_count','full_market_no_false_negative_claim','metrics')
    result = {k: copy.deepcopy(view[k]) for k in keys if k in view}
    result['public_data_policy'] = 'MIS_DERIVED_RESEARCH_NO_FUGLE_RAW'
    result['research_candidate_count'] = len(view['rows'])
    result['rows'] = []
    for row in view['rows']:
        safe = {k: copy.deepcopy(row[k]) for k in PUBLIC_FIELDS if k in row}
        proof = row.get('independent_evidence') or {}
        safe['independent_evidence'] = {k: copy.deepcopy(proof[k]) for k in ('source','contract','mode',
            'P_before_independently_verified','P_close_verified','pre_evidence_complete','close_evidence_complete',
            'source_contract_live_released','validated','reasons','acquired_at','evidence_digest') if k in proof}
        safe['price_source'] = 'MIS'
        result['rows'].append(safe)
    result['retracted'] = [{'ex':r.get('ex'),'code':r.get('code'),'reason':'RESEARCH_EVIDENCE_CHANGED'} for r in view.get('retracted',[]) if isinstance(r,dict)]
    return result


class FairQueue:
    """One task per security; max two bounded calls, stale results discarded."""
    def __init__(self, collect, *, workers=2, max_candidates=12, max_attempts=2):
        self.collect, self.max_candidates, self.max_attempts = collect, max_candidates, max_attempts
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.workers, self.tasks, self.pending, self.attempts, self.current = workers, {}, OrderedDict(), {}, {}

    @staticmethod
    def fingerprint(row):
        return hashlib.sha256(canonical({k:row.get(k) for k in ('P_before','P_close','P_before_trade_time','P_close_trade_time','closing_auction_volume','intraday_total_volume')}).encode()).hexdigest()

    def offer(self, rows):
        active = {(r['ex'],r['code']) for r in rows}
        for key in list(self.pending):
            if key not in active: self.pending.pop(key)
        for key in list(self.current):
            if key not in active: self.current.pop(key)
        for row in rows:
            key = row['ex'], row['code']
            if key not in self.current and len(self.current) >= self.max_candidates: continue
            fingerprint = self.fingerprint(row)
            changed = self.current.get(key) != fingerprint
            self.current[key] = fingerprint
            if changed or self.attempts.get((key,fingerprint),0) < self.max_attempts:
                if key not in self.tasks: self.pending[key] = (copy.deepcopy(row),fingerprint)

    def tick(self):
        completed = []
        for key,(fingerprint,task) in list(self.tasks.items()):
            if not task.done(): continue
            self.tasks.pop(key)
            try: result = task.result()
            except Exception: result = {'source':'FUGLE','status':'SOURCE_INCOMPLETE','error':'SOURCE_TASK_FAILED'}
            if self.current.get(key) == fingerprint: completed.append((key,result))
        while self.pending and len(self.tasks) < self.workers:
            key,(row,fingerprint) = self.pending.popitem(last=False)
            attempt_key = key,fingerprint
            if self.current.get(key) != fingerprint or self.attempts.get(attempt_key,0) >= self.max_attempts: continue
            self.attempts[attempt_key] = self.attempts.get(attempt_key,0)+1
            self.tasks[key] = fingerprint,self.pool.submit(self.collect,row)
        return completed

    def close(self):
        self.pool.shutdown(wait=True,cancel_futures=True)
