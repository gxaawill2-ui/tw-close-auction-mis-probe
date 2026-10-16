"""Manual local workerd integration; synthetic records and fake source ONLY.

After 13:35 Taipei, exercise today's private-route date gate without pretending
fixture clocks are live observations. No public/cloud destination is permitted.
"""
from datetime import datetime,timedelta
import copy
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.parse
import urllib.request

import freshness as f
from fast_capture_journal import Journal,verify
from stage5_journal_bridge import bridge
from stage5_remote_journal import consume
from stage5_session import Session
from stage3_publication import Publisher
from stage3_fixtures import example
from test_fast_selection import records
from test_convergence import SYMBOL
from test_close_research import DAY,ref


def run():
    base=os.environ['LOCAL_WORKER_URL'];u=urllib.parse.urlparse(base)
    if u.scheme!='http' or u.hostname!='127.0.0.1' or u.path not in ('','/'):raise ValueError('LOCAL_TEST_ONLY')
    now=datetime.now(f.TZ);date=now.date().isoformat()
    if now.strftime('%H:%M:%S')<'13:35:10':raise ValueError('DATED_LOCAL_FIXTURE_TEST_REQUIRES_AFTER_133510')
    clock=lambda:f.parsed_time(date+'T13:35:10+08:00')
    replace=lambda r:json.loads(json.dumps(r).replace(DAY,date).replace(DAY.replace('-',''),date.replace('-','')))
    token,key,bridge_token=[os.environ[k] for k in ('LOCAL_TOKEN','LOCAL_KEY','LOCAL_BRIDGE_TOKEN')]
    if any(not re.fullmatch('[a-f0-9]{64}',x) for x in (token,key,bridge_token)):raise ValueError('LOCAL_EPHEMERAL_TEST_KEYS_REQUIRED')
    def opener(req,timeout):
        # Explicit injected test transport. Production URL validation is intact.
        target=base+urllib.parse.urlparse(req.full_url).path
        r=urllib.request.Request(target,data=req.data,headers=dict(req.header_items()),method=req.method)
        return urllib.request.urlopen(r,timeout=timeout)
    def read(ident):
        req=urllib.request.Request(base+'/private-mis-journal/'+date+'/'+ident,headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(req,timeout=6) as r:return json.load(r)
    class FakeSource:
        def __init__(self,directory):self.directory=directory;directory.mkdir();self.calls=0
        def collect(self,*a,**kw):
            self.calls+=1
            # A source interruption must downgrade only the candidate.
            raise OSError('SYNTHETIC_SOURCE_INTERRUPTION')
    with tempfile.TemporaryDirectory(prefix='stage7-local-synthetic-') as tmp:
        root=Path(tmp);j=Journal(root/'journal',clock=lambda:date+'T13:35:05+08:00')
        for r in records():j.append(replace(r))
        times=[clock()]
        outcome=bridge(j.events,date,token=bridge_token,opener=opener,clock=lambda:times[0],wait=lambda _:times.__setitem__(0,f.parsed_time(date+'T14:30:00+08:00')))
        assert outcome['written_batches']==4
        source=FakeSource(root/'source');s=Session(date,[SYMBOL],root/'session',source,clock=clock)
        try:
            seen=set();consume(s,read('index'),read,seen);consume(s,read('index'),read,seen)
            assert len(seen)==4 and s.engine.batch_count==4 and s.last['research_count']==1
            initial=copy.deepcopy(s.last)
            publisher=Publisher(base,root/'outbox',publish_token=token,decision_key=key)
            def publish(view):
                body=copy.deepcopy(view);body.update(mode='SYNTHETIC',is_synthetic=True)
                for row in body['rows']:row['simulated_only']=True
                result=publisher.publish(body,datetime.now(f.TZ)+timedelta(seconds=30),max_attempts=1)
                return body,result
            initial_body,receipt=publish(initial);assert receipt['status']=='WRITTEN'
            for _ in range(40):
                s.tick();time.sleep(.01)
                if s.last['unknown_candidate_count']==1:break
            assert s.last['unknown_candidate_count']==1 and s.last['verified_count']==0 and source.calls>0
            _,receipt=publish(s.last);assert receipt['status']=='WRITTEN'
            restarted=Session(date,[SYMBOL],root/'restart',source,clock=clock)
            try:
                restarted.pipeline.version=s.last['version']
                consume(restarted,read('index'),read,set())
                assert restarted.engine.batch_count==4 and restarted.last['verified_count']==0
                restarted.feed(replace(ref('close_reference_C',price='105')))
                assert restarted.last['rows']==[] and restarted.last['retracted']
                _,receipt=publish(restarted.last);assert receipt['status']=='WRITTEN'
            finally:restarted.close()
            stale=publisher.publish(initial_body,datetime.now(f.TZ)+timedelta(seconds=30),max_attempts=1)
            assert stale['attempts'][0]['http_status']==409
            extra=j.append(replace(ref('close_reference_C',price='106')));verify(extra,j.path)
            times=[clock()]
            def broken(*a,**kw):raise OSError('SYNTHETIC_BRIDGE_FAILURE')
            stopped=bridge(j.events,date,token=bridge_token,opener=broken,clock=lambda:times[0],wait=lambda _:None)
            assert stopped['status']=='BRIDGE_STOPPED_FORMAL_CAPTURE_UNAFFECTED'
        finally:s.close()
    return {'scope':'LOCAL_SYNTHETIC_ACTUAL_WORKERD_E2E_NOT_REAL_MARKET','status':'PASS',
        'journal_fsync_bridge_codec_consumer_selection':True,'candidate_to_unknown_to_withdrawn':True,
        'source_failure_does_not_stop_capture':True,'bridge_failure_does_not_stop_capture':True,
        'new_process_replay_deduplicated':True,'stale_public_write_rejected':True,
        'production_modified':False,'cloud_requests':0,'mis_requests':0,'fugle_requests':0,
        'physical_phone_tested':False,'verified_count':0,'completed_at':datetime.now(f.TZ).isoformat()}

if __name__=='__main__':print(json.dumps(run()),flush=True)
