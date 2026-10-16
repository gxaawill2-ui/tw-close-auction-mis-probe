"""Same-session journal -> research -> per-security queue -> safe isolated outbox."""
from datetime import datetime, timedelta
import json
import time
from pathlib import Path
import freshness as f
import close_research
import convergence
from fast_selection import Engine, atomic, stamp, safe_output
from stage3_selection import Pipeline
from stage3_run import saved_version
from stage3_publication import BackgroundPublisher
from stage5_runtime import FairQueue, public_view
from stage5_audit import audit


def pending_delayed_reviews(engine):
    """Private queue only: a single delayed print never becomes a public row."""
    cache=getattr(engine,'_stage5_pending_cache',{})
    position=getattr(engine,'_stage5_pending_position',0)
    changed=set()
    for record in engine.records[position:]:
        changed.update((s.get('ex'),s.get('code')) for s in record.get('symbols',[]))
        changed.update((s.get('ex'),s.get('c')) for s in (record.get('response') or {}).get('msgArray',[]))
    admitted={(r['ex'],r['code']) for r in engine.priority()}
    for key in changed:
        cache.pop(key,None)
        if key not in engine.universe:continue
        series=engine.series[key]
        if key in admitted:continue
        pre=convergence.pre_with_c(series,engine.date)
        close=close_research.assess(series,engine.date)
        selected=close.get('selected')
        if not pre['converged'] or close['classification']!='delayed_close_candidate' or not selected:continue
        if any(r.get('phase','').startswith('close_') and r['received_at']>selected['received_at']
               and f.fresh_candidate(r,engine.date,convergence.MAX_AGE_MS)
               and (f.identity(r)!=f.identity(selected) or r['server_time']<selected['server_time'])
               for r in series):continue
        if any(convergence.probe_comparison(engine.probes[key],ev,engine.date,kind)['status']=='PROBE_CONFLICT'
               for ev,kind in ((pre,'pre'),({'converged':True,'B':selected},'close'))):continue
        before=f.decimal_value(pre['B'].get('trade_z'));last=f.decimal_value(selected.get('trade_z'))
        if not before or before<=0 or not last or last<=0 or abs(last/before-1)<f.Decimal('.03'):continue
        cache[key]={**engine.universe[key],'P_before':str(before),'P_close':str(last),
            'P_before_trade_time':pre['B']['trade_t'],'P_close_trade_time':selected['trade_t'],
            'P_close_convergence_type':'delayed_close_candidate','verification_status':'UNKNOWN',
            'validated':False,'private_review_only':True,
            'review_reason':'SINGLE_DELAYED_CLOSE_NEEDS_INDEPENDENT_EVIDENCE'}
    engine._stage5_pending_cache=cache
    engine._stage5_pending_position=len(engine.records)
    return sorted(cache.values(),key=lambda r:r['code'])


class Session:
    def __init__(self, date, universe, directory, source, publisher=None, *, clock=None):
        self.date, self.source = date, source
        self.clock = clock or (lambda: datetime.now(f.TZ))
        self.directory = safe_output(directory)
        self.engine = Engine(date, universe, self.directory/'mis-view', 'ISOLATED_STAGE5')
        self.pipeline = Pipeline(self.engine, mode='LIVE')
        # A wall-clock epoch sequence avoids resetting to 1 after ephemeral runner loss.
        self.pipeline.version = max(saved_version(self.directory,date), int(self.clock().timestamp()*1000)*1000)
        self.deadline = f.parsed_time(date+'T14:30:00+08:00')
        self.queue = FairQueue(lambda row:source.collect(row,date,min(self.deadline,self.clock()+timedelta(seconds=90)),max_pages=16))
        self.fingerprints, self.audits, self.first_research, self.last = {}, {}, None, None
        self.publisher = BackgroundPublisher(publisher,self.deadline) if publisher else None
        checkpoint = self.directory/'queue-state.json'
        if checkpoint.exists():
            data=json.loads(checkpoint.read_text())
            if data.get('trade_date')==date:
                for item in data.get('attempts',[]):
                    if item.get('ex') in ('tse','otc') and str(item.get('code','')).isdigit() and isinstance(item.get('count'),int):
                        self.queue.attempts[((item['ex'],item['code']),item['fingerprint'])]=item['count']

    def feed(self, record, persisted_at=None):
        self.engine.feed(record,persisted_at)
        self.update()

    def update(self):
        rows=self.engine.priority()+pending_delayed_reviews(self.engine)
        current={(r['ex'],r['code']):self.queue.fingerprint(r) for r in rows}
        for key in list(self.pipeline.proofs):
            if current.get(key)!=self.fingerprints.get(key):self.pipeline.proofs.pop(key)
        for key in current:
            path=self.source.directory/('proof-'+key[0]+'-'+key[1]+'.json')
            if key not in self.pipeline.proofs and path.exists():
                bundle=json.loads(path.read_text())
                # inspect() rechecks every raw hash, time, identity and MIS comparison.
                self.pipeline.proofs[key]=bundle
        self.fingerprints=current
        self.queue.offer(rows)
        return self.compile()

    def compile(self):
        if self.clock().date().isoformat()!=self.date or self.clock()>=self.deadline:
            raise ValueError('NO_HISTORICAL_OR_LATE_LIVE_PUBLICATION')
        at=self.clock().isoformat();view=self.pipeline.compile(at)
        if view['rows'] and self.first_research is None:self.first_research=at
        view['provenance']={'kind':'ISOLATED_JOURNAL_OR_SAVED_ARTIFACT_RESEARCH',
            'first_research_program_observed_at':self.first_research,
            'first_event_evidence_at':self.engine.first_ready,
            'historical_publication_time_inferred':False}
        view=public_view(view)
        view['provenance']={'kind':'SAME_DAY_SAVED_CAPTURE_ANALYSIS' if self.engine.mode=='SAVED_CAPTURE_ANALYSIS' else 'ISOLATED_STAGE5_JOURNAL',
            'first_research_program_observed_at':self.first_research,'artifact_barrier':self.engine.mode=='SAVED_CAPTURE_ANALYSIS'}
        self.last=view
        atomic(self.directory/'stage3-results.json',view)
        if self.publisher and self.clock()>=f.parsed_time(self.date+'T13:30:00+08:00'):self.publisher.submit(view)
        return view

    def tick(self):
        completed=self.queue.tick()
        by_key={(r['ex'],r['code']):r for r in self.engine.priority()+pending_delayed_reviews(self.engine)}
        for key,bundle in completed:
            if key not in by_key:continue
            self.pipeline.proofs[key]=bundle
            # Full provider evidence lives only in the private source directory.
            atomic(self.source.directory/('proof-'+key[0]+'-'+key[1]+'.json'),bundle)
            self.audits[key]=audit(bundle,by_key[key],self.date,self.clock().isoformat())
            if by_key[key].get('private_review_only'):
                self.audits[key]['private_review_only']=True
            self.compile()
        if completed:self.queue.offer(list(by_key.values()))
        if self.publisher:self.publisher.tick()
        atomic(self.directory/'queue-state.json',{'trade_date':self.date,
            'attempts':[{'ex':key[0],'code':key[1],'fingerprint':fp,'count':n} for (key,fp),n in self.queue.attempts.items()]})
        return completed

    def close(self):
        self.queue.close()
        if self.publisher:self.publisher.close()


def watch(journal, universe, date, directory, source, publisher=None):
    """Tail the existing collector's fsynced journal. Never starts a collector."""
    from fast_capture_journal import verify
    session=Session(date,universe,directory,source,publisher);offset=0
    try:
        while session.clock()<session.deadline:
            if Path(journal).exists():
                with Path(journal).open() as stream:
                    stream.seek(offset)
                    while True:
                        start=stream.tell();line=stream.readline()
                        if not line or not line.endswith('\n'):stream.seek(start);break
                        event=verify(json.loads(line),Path(journal).parent)
                        session.feed(event['record'],event['persisted_at'])
                    offset=stream.tell()
            session.tick();time.sleep(.5)
    finally:session.close()
    return session.last
