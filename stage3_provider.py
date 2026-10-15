"""Opt-in candidate-only Fugle collection with a shared, bounded request budget.

No key discovery, no MIS recapture, no scheduled execution. Save raw bytes before
parsing. Quote -> descending pages -> quote; exhausted budget is UNKNOWN.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import freshness as f
from fast_selection import safe_output


class Collector:
    def __init__(self, directory, *, api_key=None, max_requests=50, max_pages=12,
                 opener=urllib.request.urlopen, clock=None, wait=time.sleep, page_size=500):
        self.directory = safe_output(directory)
        self.key = api_key or os.getenv('FAST_FUGLE_API_KEY')
        self.max_requests = max_requests; self.max_pages = max_pages; self.page_size = page_size
        self.opener = opener; self.clock = clock or (lambda: datetime.now(f.TZ))
        self.wait = wait; self.count = 0; self.last_request = None; self.stopped = False

    def request(self, candidate, kind, query, deadline):
        if self.stopped or self.count >= self.max_requests:
            raise ValueError('SOURCE_REQUEST_BUDGET_EXHAUSTED')
        if self.last_request:
            delay = 1.1-(self.clock()-self.last_request).total_seconds()
            if delay > 0:self.wait(delay)
        if (deadline-self.clock()).total_seconds() < 9:
            raise ValueError('SOURCE_DEADLINE_INSUFFICIENT_BUDGET')
        code = candidate['code']
        url = f'https://api.fugle.tw/marketdata/v1.0/stock/intraday/{kind}/{code}'
        if kind == 'trades':
            params = {**query, 'isTrial':'false'}
            url += '?'+urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={'X-API-KEY':self.key,'Accept':'application/json'})
        self.last_request = self.clock(); requested = self.last_request.isoformat(); self.count += 1
        try:
            with self.opener(request,timeout=8) as response:
                status=response.status; raw=response.read(2_000_001)
                headers={k.lower():v for k,v in response.headers.items() if k.lower() in ('date','age','cache-control')}
        except urllib.error.HTTPError as exc:
            if exc.code in (401,403,429):self.stopped=True
            raise ValueError('SOURCE_HTTP_'+str(exc.code)) from None
        if len(raw)>2_000_000:raise ValueError('SOURCE_BODY_TOO_LARGE')
        received=self.clock()
        path=self.directory/f'{candidate["ex"]}-{code}-{self.count:03d}-{kind}-{uuid.uuid4().hex[:12]}.json'
        with path.open('xb') as file:
            file.write(raw);file.flush();os.fsync(file.fileno())
        persisted=self.clock()
        if persisted > deadline:raise ValueError('SOURCE_RECEIVED_AFTER_DEADLINE')
        event={'raw_path':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'requested_at':requested,
               'received_at':received.isoformat(),'persisted_at':persisted.isoformat(),'http_status':status,'query':query,'headers':headers}
        return event,json.loads(raw)

    def collect(self,candidate,date,deadline):
        if not self.key:return {'source':'FUGLE','status':'NOT_CONFIGURED','pages':[]}
        if candidate.get('ex') not in ('tse','otc') or not re.fullmatch(r'[1-9]\d{3}',candidate.get('code','')):
            raise ValueError('INVALID_CANDIDATE')
        if self.clock().date().isoformat()!=date:raise ValueError('NO_HISTORICAL_SOURCE_CAPTURE')
        bundle={'source':'FUGLE','origin_kind':'AUTHENTICATED_HTTP','trade_date':date,'pages':[]}
        try:
            bundle['quote_before'],_=self.request(candidate,'quote',{},deadline)
            offset=0
            for _ in range(self.max_pages):
                query={'offset':offset,'limit':self.page_size,'sort':'desc','isTrial':False}
                event,data=self.request(candidate,'trades',query,deadline)
                bundle['pages'].append(event)
                count=len(data['data']);offset+=count
                if count<self.page_size:break
            else:raise ValueError('SOURCE_PAGE_BUDGET_EXHAUSTED')
            bundle['quote_after'],_=self.request(candidate,'quote',{},deadline)
            bundle['status']='COLLECTED_NOT_VALIDATED'
        except Exception as exc:
            # Do not serialize headers, tokens or arbitrary exception URLs.
            bundle['status']='SOURCE_INCOMPLETE'
            bundle['error']=str(exc) if isinstance(exc,ValueError) and str(exc).startswith('SOURCE_') else type(exc).__name__
        path=self.directory/f'{candidate["ex"]}-{candidate["code"]}-manifest-{uuid.uuid4().hex[:12]}.json'
        bundle['manifest_path']=path.name
        with path.open('x') as file:
            json.dump(bundle,file,ensure_ascii=False,indent=2);file.flush();os.fsync(file.fileno())
        return bundle
