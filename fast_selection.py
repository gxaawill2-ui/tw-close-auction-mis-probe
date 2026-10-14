"""Incremental local publication from saved batch evidence; never writes GitHub.

`replay` preserves original observation times but never claims historical public
publication. `watch` tails a new durable journal until 14:30 without recapturing
MIS. Ordinary run_control and its postmarket audit are unchanged.
"""
import argparse
import copy
import hashlib
import json
import os
import time
import concurrent.futures
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import close_research
import convergence
import fast_gate
import freshness as f
import official_retry
import volume_evidence


def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def stamp():return datetime.now(f.TZ).isoformat(timespec='milliseconds')
def seconds(value,date):
    t=f.parsed_time(value)
    return round((t-f.parsed_time(date+'T13:30:00+08:00')).total_seconds(),3) if t else None


def safe_output(path):
    p=Path(path).resolve();root=Path(__file__).parent.resolve()
    if p==root or any(p==root/n or root/n in p.parents for n in ('docs','state','.github','reports/2026-10-14')):
        raise ValueError('OUTPUT_MUST_BE_ISOLATED_FROM_PRODUCTION_AND_PRIOR_EVIDENCE')
    p.mkdir(parents=True,exist_ok=True);return p


def atomic(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False))
    with tmp.open('rb') as file:os.fsync(file.fileno())
    os.replace(tmp,path)


class Engine:
    def __init__(self,date,universe,output,mode='OFFLINE_REPLAY'):
        self.date=date;self.universe={(s['ex'],s['code']):s for s in universe}
        self.output=safe_output(output);self.mode=mode;self.records=[];self.series=defaultdict(list)
        self.probes=defaultdict(list);self.saved={};self.rows={};self.events=[];self.crosschecks={}
        self.first_ready=None;self.first_local=None;self.first_verified=None;self.last_update=None;self.first_complete_research=None
        self.started=time.perf_counter();self.batch_count=0;self.boundary_covered=set()
        self.seen_symbols=set();self.seen_hashes=set();self.replay_persisted=False

    def feed(self,record,persisted_at=None):
        received=f.parsed_time(record.get('received_at'))
        if not received or received.astimezone(f.TZ).date().isoformat()!=self.date:
            raise ValueError('WRONG_OR_MISSING_OBSERVATION_DATE')
        digest=hashlib.sha256(canonical(record).encode()).hexdigest()
        if digest in self.seen_hashes:return
        self.seen_hashes.add(digest);self.records.append(record);self.batch_count+=1
        is_probe=(record.get('phase') or record.get('window')) in ('preclose_window','close_window')
        grouped=convergence.grouped([{'records':[record]}],self.date)
        for key,observations in grouped.items():
            if key not in self.universe:continue
            self.seen_symbols.add(key)
            if is_probe:self.probes[key].extend(observations)
            else:self.series[key].extend(observations)
            # A known save time is required. Legacy requested/received timestamps
            # are NOT evidence that old raw JSON was durably written before 13:25.
            if persisted_at and not record.get('error'):
                saved=f.parsed_time(persisted_at)
                for obs in observations:
                    if saved and received<=saved and saved<f.parsed_time(self.date+'T13:25:00+08:00'):
                        ident=(key,obs.get('trade_t'),obs.get('trade_z'))
                        if f.fresh_candidate(obs,self.date) and obs.get('trade_t') and '09:00:00'<=obs['trade_t']<'13:25:00' and f.decimal_value(obs.get('trade_z')):
                            self.saved.setdefault(ident,persisted_at)
                            self.boundary_covered.add(key)
            self._evaluate(key,record['received_at'])

    def _evaluate(self,key,as_of):
        rows=self.series[key];pre=convergence.pre_with_c(rows,self.date)
        close=close_research.assess(rows,self.date)
        for ev,kind in ((pre,'pre'),({'converged':bool(close['selected']),'B':close['selected']},'close')):
            if convergence.probe_comparison(self.probes[key],ev,self.date,kind)['status']=='PROBE_CONFLICT':
                if kind=='pre':pre={**pre,'converged':False}
                else:close={**close,'classification':'unresolved','selected':None,'p_close':None}
        usable=pre['converged'] and close['classification'] in close_research.TYPES
        value=f.decimal_value(pre['B'].get('trade_z')) if pre['converged'] else None
        last=f.decimal_value(close.get('p_close'))
        qualifies=bool(usable and value and last and abs(last/value-1)>=f.Decimal('.03'))
        prior=self.rows.get(key)
        if not qualifies:
            if prior and prior['verification_status']!='RETRACTED':
                self.rows[key]={**prior,'verification_status':'RETRACTED','validated':False,'updated_at':as_of,
                    'retraction_reason':'LATER_EVIDENCE_UNRESOLVED_CONTRADICTORY_OR_BELOW_THRESHOLD'}
                self._event(key,as_of,'RETRACTED')
            return
        symbol=self.universe[key]
        candidate={**symbol,'P_before':str(value),'P_close':str(last),
            'P_before_trade_time':pre['B']['trade_t'],'P_close_trade_time':close['trade_time'],
            'P_close_convergence_type':close['classification'],
            'pre_pair_evidence':pre,'close_research_evidence':close}
        # Matching uses only the two adopted references for this security. The
        # raw batch identity/timestamp remains available to locate().
        volume=volume_evidence.assess(candidate,symbol,[{'records':self.records}],self.date,as_of)
        saved=self.saved.get((key,pre['B']['trade_t'],pre['B']['trade_z']))
        candidate.update(volume)
        gate=fast_gate.assess(candidate,self.date,saved,self.crosschecks.get(key))
        result={**{k:candidate[k] for k in ('ex','code','name','market','P_before','P_close','P_before_trade_time','P_close_trade_time','P_close_convergence_type')},
            'tail_return_pct':str((last/value-1)*100),**volume,**gate,
            'first_seen_at':prior['first_seen_at'] if prior else as_of,
            'pre_received_at':pre['B']['received_at'],'pre_saved_at':saved,
            'close_received_at':close['selected']['received_at'],'updated_at':as_of,
            'public_observed_at':None,'source_observed_at':as_of}
        comparable=lambda r:{k:v for k,v in r.items() if k not in ('updated_at','source_observed_at','local_published_at')}
        if prior and comparable(prior)==comparable(result):return
        self.rows[key]=result
        if self.first_ready is None:self.first_ready=as_of
        if self.first_complete_research is None and all(gate['checks'][k] for k in ('pre_actual_trade_before_1325','close_research_converged','tail_threshold','required_volume_evidence')):
            self.first_complete_research=as_of
        if result['validated'] and self.first_verified is None:self.first_verified=as_of
        self._event(key,as_of,gate['verification_status'])

    def _event(self,key,as_of,status):
        self.last_update=as_of
        self.events.append({'symbol':':'.join(key),'available_at':as_of,'status':status,
                            'capture_to_ready_seconds':seconds(as_of,self.date)})

    def crosscheck(self,key,proof,as_of):
        if key not in self.universe:raise ValueError('CROSSCHECK_OUTSIDE_UNIVERSE')
        if not f.parsed_time(as_of) or f.parsed_time(as_of).astimezone(f.TZ).date().isoformat()!=self.date:raise ValueError('CROSSCHECK_WRONG_DATE')
        self.crosschecks[key]=proof;self._evaluate(key,as_of)

    def priority(self):
        return sorted((r for r in self.rows.values() if r['verification_status']!='RETRACTED'),
                      key=lambda r:(r['validated'],-abs(f.decimal_value(r['tail_return_pct'])),r['code']))

    def view(self):
        active=self.priority();verified=[r for r in active if r['validated']]
        return {'schema_version':'FAST_SELECTION_V1','trade_date':self.date,'mode':self.mode,
          'scope':'ISOLATED_LOCAL_ONLY','capture_outcome':'PARTIAL_EVIDENCE','verified_count':len(verified),
          'research_count':len(active)-len(verified),'universe_count':len(self.universe),
          'observed_symbols':len(self.seen_symbols),'pending_or_unproven':len(self.universe)-len(verified),
          'pre_boundary_saved_symbols':len(self.boundary_covered),
          'rows':active,'retracted':[r for r in self.rows.values() if r['verification_status']=='RETRACTED'],
          'priority_crosscheck_queue':[r['ex']+':'+r['code'] for r in active if not r['validated']],
          'final_audit':{'status':'SEPARATE_POSTMARKET_AUDIT','scheduled_times':['14:50','15:20','17:50']},
          'metrics':{'first_candidate_evidence_available_at':self.first_ready,'first_local_publication_at':self.first_local,
             'first_public_observed_at':None,'first_verified_at':self.first_verified,'last_evidence_update_at':self.last_update,
             'first_complete_research_evidence_at':self.first_complete_research,
             'close_to_first_candidate_seconds':seconds(self.first_ready,self.date),
             'close_to_first_complete_research_seconds':seconds(self.first_complete_research,self.date),
             'close_to_first_verified_seconds':seconds(self.first_verified,self.date),
             'close_to_last_evidence_seconds':seconds(self.last_update,self.date),
             'processing_wall_seconds':round(time.perf_counter()-self.started,4),'batches_processed':self.batch_count,
             'historical_publication_proven':False},
          'limitation':'No anonymous source contract proves final pre-13:25 trade; formal publication remains blocked. Offline availability is not historical live publication.'}

    def publish_local(self):
        if self.first_ready and self.first_local is None:self.first_local=stamp()
        result=self.view();atomic(self.output/'fast-results.json',result)
        atomic(self.output/'latency.json',result['metrics'])
        return result


def replay(archive,output):
    before=hashlib.sha256(archive).hexdigest()
    summary,universe,snaps,probes=official_retry.load_capture(archive)
    engine=Engine(summary['trade_date'],universe,output)
    records=[r for snap in snaps for r in snap['records']]+probes
    records.sort(key=lambda r:(r.get('received_at') or '',r.get('phase') or ''))
    for record in records:engine.feed(record)
    result=engine.publish_local()
    atomic(engine.output/'timeline.json',engine.events)
    atomic(engine.output/'replay-integrity.json',{'sha256_before':before,'sha256_after':hashlib.sha256(archive).hexdigest(),'input_unchanged':True})
    return result


class CandidateChecks:
    """A separate single-worker queue: slow websites never block journal intake."""
    def __init__(self,engine,fetch=None,max_checks=12):
        from fast_sources import check_pchome,check_fugle
        self.engine=engine;self.fetch=fetch or (check_fugle if os.getenv('FAST_FUGLE_API_KEY') else check_pchome)
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.future=None;self.checked=set();self.max_checks=max_checks;self.stopped=False;self.last_finished=None

    def tick(self,as_of):
        if self.future and self.future[1].done():
            key,future=self.future
            try:proof=future.result()
            except Exception as exc:proof={'status':'SOURCE_ERROR','error':type(exc).__name__,'validated':False}
            self.engine.crosscheck(key,proof,as_of);self.last_finished=f.parsed_time(as_of)
            atomic(self.engine.output/('crosscheck-'+key[0]+'-'+key[1]+'.json'),proof)
            self.stopped=proof.get('http_status') in (401,403,429) or any(r.get('http_status') in (401,403,429) for r in proof.get('errors',[]))
            self.future=None
        current=f.parsed_time(as_of)
        if self.future or self.stopped or len(self.checked)>=self.max_checks:return
        if self.last_finished and (current-self.last_finished).total_seconds()<1.1:return
        for row in self.engine.priority():
            key=row['ex'],row['code']
            if key in self.checked:continue
            self.checked.add(key)
            self.future=(key,self.pool.submit(self.fetch,row,self.engine.output/'candidate-sources'))
            break

    def close(self):
        self.pool.shutdown(wait=True,cancel_futures=True)


def watch(journal,universe,date,output,until='14:30:00',check_sources=False):
    engine=Engine(date,universe,output,'ISOLATED_WATCH');offset=0
    deadline=f.parsed_time(date+'T'+until+'+08:00')
    if datetime.now(f.TZ)>=deadline:raise ValueError('WATCH_DEADLINE_ALREADY_PASSED_NO_HISTORICAL_LIVE_CLAIM')
    checker=CandidateChecks(engine) if check_sources else None
    try:
        while datetime.now(f.TZ)<deadline:
            if journal.exists():
                with journal.open() as file:
                    file.seek(offset)
                    while True:
                        start=file.tell();line=file.readline()
                        if not line or not line.endswith('\n'):file.seek(start);break
                        from fast_capture_journal import verify
                        event=verify(json.loads(line),journal.parent);engine.feed(event['record'],event.get('persisted_at'))
                    offset=file.tell()
            if checker and (deadline-datetime.now(f.TZ)).total_seconds()>20:checker.tick(stamp())
            engine.publish_local()
            time.sleep(1)
    finally:
        if checker:checker.close()
    return engine.publish_local()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    r=sub.add_parser('replay');r.add_argument('archive',type=Path);r.add_argument('output',type=Path)
    w=sub.add_parser('watch');w.add_argument('journal',type=Path);w.add_argument('universe',type=Path);w.add_argument('date');w.add_argument('output',type=Path)
    w.add_argument('--check-sources',action='store_true',help='Opt-in candidate-only secondary checks; no production writes')
    a=p.parse_args()
    result=replay(a.archive.read_bytes(),a.output) if a.mode=='replay' else watch(a.journal,json.loads(a.universe.read_text()),a.date,a.output,check_sources=a.check_sources)
    print(json.dumps({k:result[k] for k in ('trade_date','verified_count','research_count','metrics')},ensure_ascii=False,indent=2))
