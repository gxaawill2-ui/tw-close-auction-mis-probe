"""Signed candidate-view publication with local outbox, bounded retry and receipts."""
import hashlib
import hmac
import json
from pathlib import Path
import time
import concurrent.futures
import copy
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
import freshness as f
from fast_selection import safe_output,atomic
from stage3_ticks import canonical

CLOUD_CLIENT='tw-close-auction-isolated/5.0 (+https://github.com/gxaawill2-ui/tw-close-auction-mis-probe)'


def envelope(body,decision_key):
    return {'body':body,'signature':hmac.new(decision_key.encode(),canonical(body).encode(),hashlib.sha256).hexdigest()}


class Publisher:
    def __init__(self,base_url,directory,*,publish_token,decision_key,
                 opener=urllib.request.urlopen,wait=time.sleep,clock=None):
        url=urllib.parse.urlparse(base_url)
        if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('localhost','127.0.0.1')):
            raise ValueError('PUBLICATION_REQUIRES_HTTPS_OR_LOOPBACK')
        if url.username or url.password or url.query or url.fragment:
            raise ValueError('INVALID_PUBLICATION_URL')
        self.base=base_url.rstrip('/');self.directory=safe_output(directory)
        self.token=publish_token;self.key=decision_key;self.opener=opener;self.wait=wait
        self.clock=clock or (lambda:datetime.now(f.TZ))
        log=self.directory/'publication-receipts.json'
        self.receipts=json.loads(log.read_text()) if log.exists() else []
        if not isinstance(self.receipts,list):raise ValueError('INVALID_SAVED_PUBLICATION_RECEIPTS')

    def publish(self,view,deadline,max_attempts=3):
        encoded=canonical(envelope(view,self.key)).encode()
        sha=hashlib.sha256(canonical(view).encode()).hexdigest()
        atomic(self.directory/'publication-outbox.json',{'body':view,'sha256':sha,'status':'QUEUED'})
        attempts=[];receipt=None
        for index in range(max_attempts):
            if (deadline-self.clock()).total_seconds()<7:break
            began=self.clock().isoformat()
            try:
                req=urllib.request.Request(self.base+'/publish',data=encoded,method='POST',
                    headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','User-Agent':CLOUD_CLIENT,'Accept':'application/json'})
                with self.opener(req,timeout=6) as response:
                    status=response.status;result=json.loads(response.read(4097))
                if status!=200 or result.get('sha256')!=sha or result.get('version')!=view['version']:
                    raise ValueError('PUBLICATION_RECEIPT_MISMATCH')
                if not f.parsed_time(result.get('public_written_at')):raise ValueError('MISSING_PUBLIC_WRITE_TIME')
                receipt=result;attempts.append({'started_at':began,'finished_at':self.clock().isoformat(),'http_status':status});break
            except urllib.error.HTTPError as exc:
                attempts.append({'started_at':began,'finished_at':self.clock().isoformat(),'http_status':exc.code,'error':'HTTP_'+str(exc.code)})
                if exc.code not in (408,425,429,500,502,503,504):break
            except Exception as exc:
                attempts.append({'started_at':began,'finished_at':self.clock().isoformat(),'error':type(exc).__name__})
            if index+1<max_attempts and (deadline-self.clock()).total_seconds()>8:
                self.wait(min(2**index,4))
        result={'version':view['version'],'sha256':sha,'attempts':attempts,'receipt':receipt,
                'status':'WRITTEN' if receipt else 'PUBLICATION_PENDING','public_observed_at':None}
        self.receipts.append(result);atomic(self.directory/'publication-receipts.json',self.receipts)
        atomic(self.directory/'publication-outbox.json',{'body':view,'sha256':sha,'status':result['status']})
        return result


class BackgroundPublisher:
    """Coalesce waiting views; at most one in-flight request never blocks capture."""
    def __init__(self,publisher,deadline):
        self.publisher=publisher;self.deadline=deadline;self.pending=None;self.future=None
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1);self.latest_version=0

    def submit(self,view):
        if view['version']<=self.latest_version:return
        self.latest_version=view['version'];self.pending=copy.deepcopy(view);self.tick()

    def tick(self):
        if self.future and self.future.done():self.future.result();self.future=None
        if not self.future and self.pending:
            view=self.pending;self.pending=None
            self.future=self.pool.submit(self.publisher.publish,view,self.deadline)

    def close(self):
        if self.future:self.future.result();self.future=None
        if self.pending:self.tick()
        self.pool.shutdown(wait=True)
