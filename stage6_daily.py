"""Dormant independent daily consumer. No scheduler or collector is invoked.

An approved singleton workflow must supply the formal universe and private bridge.
This file is not attached to a production workflow. Never upload its private root.
"""
from datetime import datetime,timedelta
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request
import freshness as f
from stage3_ticks import canonical
from stage3_publication import Publisher
from stage5_runtime import Source,Vault,BASE,NoRedirect
from stage5_runtime import restore_bundle
from stage5_archive import private_write
from stage5_archive import checked,probe
from stage5_remote_journal import follow
from stage5_session import Session
from stage6_universe import receive
from stage3_publication import CLOUD_CLIENT


class DurableBudget:
    """Reserve request ordinals before HTTP; restart cannot regain spent quota.

    Requires ONE consumer across runners (workflow concurrency cancel=false).
    This is not a distributed lock and never claims to coordinate other apps.
    """
    namespace='STAGE6_DAILY_SINGLE_CONSUMER_V1'
    def __init__(self,vault,date,clock=None):
        self.vault,self.date=vault,date
        self.clock=clock or (lambda:datetime.now(f.TZ))
        self.count=0
        self.manifests={}
        entries=vault.read(date,'index').get('entries')
        if not isinstance(entries,list) or len(entries)>600:raise ValueError('BUDGET_INDEX_INVALID')
        ids=[e.get('id') for e in entries]
        if len(ids)!=len(set(ids)):raise ValueError('BUDGET_DUPLICATE_INDEX')
        ordinals=set()
        for item in entries:
            saved=checked(vault.read(date,item['id']),date,item['id'])
            event=saved['event']
            if event['sha256']!=item['sha256']:raise ValueError('BUDGET_INDEX_HASH_MISMATCH')
            if event.get('kind')=='bundle_manifest':
                symbol=event.get('symbol');written=f.parsed_time(saved['private_written_at'])
                if symbol and (symbol not in self.manifests or written>self.manifests[symbol][0]):
                    self.manifests[symbol]=(written,item['id'])
            if event.get('kind')!='REQUEST_RESERVATION':continue
            body=json.loads(event['raw'])
            if body.get('namespace')!=self.namespace:continue
            n=body.get('ordinal')
            if body.get('trade_date')!=date or not isinstance(n,int) or isinstance(n,bool) or not 1<=n<=160:
                raise ValueError('BUDGET_RESERVATION_INVALID')
            ordinals.add(n)
        self.count=max(ordinals,default=0)
        if ordinals!=set(range(1,self.count+1)):raise ValueError('BUDGET_RESERVATION_GAP')

    def reserve(self,count,date):
        if date!=self.date or self.clock().date().isoformat()!=date or count!=self.count+1 or count>160:
            raise ValueError('BUDGET_ORDINAL_OR_DATE_CONFLICT')
        at=self.clock().isoformat()
        raw=canonical({'namespace':self.namespace,'trade_date':date,'ordinal':count})
        event={'source':'FUGLE','kind':'REQUEST_RESERVATION','raw':raw,
            'sha256':hashlib.sha256(raw.encode()).hexdigest(),'requested_at':at,'received_at':at,'persisted_at':at}
        receipt=self.vault.save(event,date)
        if receipt.get('recoverable_after_job') is not True:raise ValueError('BUDGET_NOT_DURABLE')
        self.count=count

    def restore_proofs(self,directory,universe):
        symbols={s['code']:s for s in universe};restored=0
        for code,(_,ident) in self.manifests.items():
            if code not in symbols:continue
            bundle=restore_bundle(self.vault,self.date,ident)
            path=Path(directory)/('proof-'+symbols[code]['ex']+'-'+code+'.json')
            private_write(path,bundle);restored+=1
        return restored


def launch(date,formal_run_id,private_root):
    now=datetime.now(f.TZ)
    if now.date().isoformat()!=date or now>=f.parsed_time(date+'T14:30:00+08:00'):
        raise ValueError('NO_HISTORICAL_OR_LATE_DAILY_CONSUMER')
    root=Path(private_root).resolve();repo=Path(__file__).parent.resolve()
    workspace=Path(os.getenv('GITHUB_WORKSPACE',repo)).resolve()
    if any(root==p or p in root.parents for p in (repo,workspace)):
        raise ValueError('PRIVATE_ROOT_CANNOT_ENTER_CHECKOUT')
    root.mkdir(parents=True,exist_ok=True);os.chmod(root,0o700)
    # Local duplicate process prevention; cross-runner concurrency is in proposal.
    import fcntl
    with (root/'consumer.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        v=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'))
        probe(v,date)
        budget=DurableBudget(v,date)
        source=Source(os.getenv('FUGLE_API_KEY'),root/'private-fugle',v,max_requests=160,
            require_durable=True,min_interval=1.3,reservation=budget)
        def read(ident):
            req=urllib.request.Request(BASE+'/private-mis-journal/'+date+'/'+ident,
                headers={'Authorization':'Bearer '+v.token,'User-Agent':CLOUD_CLIENT,'Accept':'application/json'})
            with v.opener(req,timeout=6) as r:
                raw=r.read(150001)
                if r.status!=200 or len(raw)>150000:raise ValueError('PRIVATE_UNIVERSE_READ_INVALID')
                return json.loads(raw)
        universe=None
        deadline=f.parsed_time(date+'T13:34:50+08:00')
        while universe is None and datetime.now(f.TZ)<deadline:
            try:universe=receive(date,formal_run_id,read,lambda:datetime.now(f.TZ))
            except Exception:
                # No market data may be requested until the trusted universe exists.
                time.sleep(2)
                continue
            if universe is None:time.sleep(2)
        if universe is None:raise ValueError('FORMAL_PRIVATE_UNIVERSE_UNAVAILABLE')
        budget.restore_proofs(source.directory,universe)
        publisher=Publisher(BASE,root/'outbox',publish_token=v.token,decision_key=v.key,opener=v.opener)
        session=Session(date,universe,root/'session',source,publisher)
        try:
            while datetime.now(f.TZ)<session.deadline:
                result=follow(session,v.token)
                if result['status']=='PRIVATE_JOURNAL_WINDOW_ENDED':return result
                # Transient bridge failures do not silently turn into a success.
                time.sleep(5)
            return {'status':'PRIVATE_JOURNAL_WINDOW_ENDED_WITH_INTERRUPTION'}
        finally:session.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('date');p.add_argument('formal_run_id');p.add_argument('private_root',type=Path);a=p.parse_args()
    try:print(json.dumps(launch(a.date,a.formal_run_id,a.private_root)))
    except Exception as exc:
        print(json.dumps({'status':'CONSUMER_STOPPED_FORMAL_CAPTURE_UNAFFECTED','error_type':type(exc).__name__}))
        raise SystemExit(1)
