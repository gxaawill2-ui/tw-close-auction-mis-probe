"""Finite C2 controller. Transport injection only; no live endpoint/credentials.

Persist the ledger before starting each bounded batch. One controller per date;
parent collector must serialize calls. Process isolation kills a stalled callback.
"""
import copy,json,os,tempfile,multiprocessing,time
from pathlib import Path
from datetime import timedelta
import close_research as close
import convergence as c
import freshness as f


def atomic(path,body):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out:
            json.dump(body,out,ensure_ascii=False);out.flush();os.fsync(out.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


class C2:
    def __init__(self,date,ledger):
        self.date=date;self.path=Path(ledger)
        self.state=json.loads(self.path.read_text()) if self.path.exists() else {'date':date,'symbols':{},'batches':0}
        if self.state.get('date')!=date or type(self.state.get('batches')) is not int or not 0<=self.state['batches']<=2:raise ValueError('INVALID_C2_LEDGER')
        if not isinstance(self.state.get('symbols'),dict) or len(self.state['symbols'])>12:raise ValueError('INVALID_C2_LEDGER')
        for key,item in self.state['symbols'].items():
            if type(item.get('attempts')) is not int or not 0<=item['attempts']<=self.state['batches'] or not f.parsed_time(item.get('at')) or f.parsed_time(item['at']).astimezone(f.TZ).date().isoformat()!=date:raise ValueError('INVALID_C2_LEDGER')

    def reserve(self,snapshots,universe,now):
        now=f.parsed_time(now);end=f.parsed_time(self.date+'T13:34:50+08:00')
        if not now or now.astimezone(f.TZ).date().isoformat()!=self.date or not f.parsed_time(self.date+'T13:34:10+08:00')<=now<end-timedelta(seconds=8):return None
        if self.state.get('blocked') or self.state['batches']>=2:return None
        if any(r.get('http_status') in (403,429) for s in snapshots for r in s['records']):return None
        grouped=c.grouped(snapshots,self.date);eligible=[]
        for symbol in universe:
            key=symbol['ex'],symbol['code'];series=grouped[key]
            if not c.pre_with_c(series,self.date)['converged']:continue
            assessed=close.assess(series,self.date)
            if assessed['converged']:continue
            valid=[r for r in series if r.get('phase','').startswith('close_') and not c.rejection(r,self.date,'close') and r.get('trade_t') in ('13:30:00','13:33:00')]
            if not valid:continue
            name=symbol['ex']+':'+symbol['code'];prior=self.state['symbols'].get(name)
            if prior and (prior['attempts']>=2 or (now-f.parsed_time(prior['at'])).total_seconds()<3):continue
            eligible.append((not any(r['trade_t']=='13:33:00' for r in valid),name,symbol))
        eligible.sort(key=lambda x:(x[0],x[1]))
        # A fixed 12-symbol daily roster, never round-robin through the market.
        prior_keys=set(self.state['symbols'])
        chosen=[]
        for _,name,symbol in eligible:
            if name not in prior_keys and len(prior_keys)>=12:continue
            chosen.append(copy.deepcopy(symbol));prior_keys.add(name)
        if not chosen:return None
        for symbol in chosen:
            name=symbol['ex']+':'+symbol['code'];prior=self.state['symbols'].get(name,{'attempts':0})
            self.state['symbols'][name]={'attempts':prior['attempts']+1,'at':now.isoformat()}
        self.state['batches']+=1;atomic(self.path,self.state)
        return {'phase':'close_targeted_retry','planned_at':now.isoformat(),'symbols':chosen,
                'batch_no':self.state['batches'],'timeout_seconds':5,'deadline':min(end,now+timedelta(seconds=5)).isoformat()}

    def accept(self,request,response,received):
        if response.get('http_status') in (403,429):
            self.state['blocked']=True;atomic(self.path,self.state)
        now=f.parsed_time(received);limit=f.parsed_time(request['deadline'])
        if not now or now>limit:return {'status':'TIMEOUT_OR_LATE_DISCARDED','records':[]}
        row={**response,'phase':'close_targeted_retry','planned_at':request['planned_at'],
             'symbols':request['symbols'],'batch_no':request['batch_no']}
        body=row.get('response')
        if row.get('http_status')==200 and not row.get('error') and (not isinstance(body,dict) or body.get('rtcode')!='0000'):
            row['error']='MIS_INVALID_RTCODE'
        if isinstance(body,dict):
            identities=[str(x.get('ex'))+':'+str(x.get('c')) for x in body.get('msgArray',[]) if isinstance(x,dict)]
            row['duplicate']=sorted({x for x in identities if identities.count(x)>1})
        sent=f.parsed_time(row.get('requested_at'));got=f.parsed_time(row.get('received_at'))
        if not sent or not got or not f.parsed_time(request['planned_at'])<=sent<=got<=now:
            return {'status':'INVALID_RESPONSE_TIMING','records':[]}
        return {'status':'RECEIVED_EVIDENCE_NOT_AUTOMATIC_CONFIRMATION','records':[row]}



C2_ENABLED = True  # Explicitly approved activation is a separate one-line patch.


def _http_child(symbols,deadline,path):
    # Existing HTTP implementation, exactly one attempt and the same MIS endpoint.
    from dataclasses import asdict
    import probe
    try:
        result=probe.fetch_mis(symbols,retry=0,timeout=5,deadline=f.parsed_time(deadline))
        atomic(path,asdict(result))
    except Exception:
        atomic(path,{'error':'C2_TRANSPORT_FAILED','response':None,'raw_body':None})


def http_record(request,output,*,clock,ctx=None,child_target=None):
    from datetime import datetime
    import probe
    directory=Path(output);directory.mkdir(parents=True,exist_ok=True)
    ctx=ctx or multiprocessing.get_context('spawn')
    sent=clock();limit=min(5,max(0,(f.parsed_time(request['deadline'])-sent).total_seconds()))
    with tempfile.TemporaryDirectory(prefix='c2-http-',dir=directory) as tmp:
        path=Path(tmp)/'response.json'
        child=ctx.Process(target=child_target or _http_child,args=(request['symbols'],request['deadline'],path))
        child.start();child.join(limit)
        timed_out=child.is_alive()
        if timed_out:child.terminate();child.join(.1)
        if child.is_alive():child.kill();child.join(.1)
        if path.exists() and path.stat().st_size<=2_000_000:
            try:result=json.loads(path.read_text())
            except (OSError,ValueError):result={'error':'C2_CORRUPT_CHILD_RESULT'}
        else:result={'error':'C2_BOUNDED_TIMEOUT' if timed_out else 'C2_NO_CHILD_RESULT'}
    received=clock()
    result.setdefault('requested_at',sent.isoformat());result.setdefault('received_at',received.isoformat())
    for key,value in {'http_status':None,'response':None,'raw_body':None,'latency_ms':0,'retry':0,'error':None,'attempts':[]}.items():result.setdefault(key,value)
    if timed_out or received>f.parsed_time(request['deadline']):result['error']='RESPONSE_AFTER_CAPTURE_DEADLINE'
    return result


def capture(date,snapshots,universe,output,*,clock=None,wait=None,transport=None,enabled=False):
    from datetime import datetime
    import probe
    clock=clock or (lambda:datetime.now(f.TZ));wait=wait or time.sleep
    if not enabled:return {'status':'DISABLED','records':[],'requests':0,'deadline_reached':False}
    # A rerun on a fresh runner cannot reset the daily request budget.
    attempt=os.getenv('GITHUB_RUN_ATTEMPT','1')
    output=Path(output);ledger=output/('c2-ledger-'+date+'.json')
    if attempt!='1' and not ledger.exists():return {'status':'RESTART_LEDGER_REQUIRED','records':[],'requests':0}
    controller=C2(date,ledger);records=[];requests=0
    transport=transport or (lambda request:http_record(request,output,clock=clock))
    for _ in range(2):
        now=clock();request=controller.reserve(snapshots+[{'records':records}],universe,now.isoformat())
        if not request:break
        requests+=1
        result=transport(request)
        accepted=controller.accept(request,result,clock().isoformat())
        record={**result,'phase':'close_targeted_retry','planned_at':request['planned_at'],
                'symbols':request['symbols'],'batch_no':request['batch_no'],'expected_count':len(request['symbols'])}
        for key,value in {'http_status':None,'response':None,'latency_ms':0,'retry':0,'error':None,'raw_body':None}.items():record.setdefault(key,value)
        record.setdefault('requested_at',request['planned_at']);record.setdefault('received_at',clock().isoformat())
        if not accepted['records']:record['error']=accepted['status']
        else:record=accepted['records'][0]
        record['expected_count']=len(request['symbols'])
        for key,value in {'http_status':None,'response':None,'latency_ms':0,'retry':0,'error':None,'raw_body':None,'attempts':[]}.items():record.setdefault(key,value)
        record.update(probe.analyze(request['symbols'],probe.FetchResult(**{k:record.get(k) for k in ('requested_at','received_at','latency_ms','http_status','retry','error','raw_body','response','attempts')})))
        # Append actual response and error before deriving any candidate. Never
        # discard a failed attempt or relabel it as the scheduled C observation.
        with (output/'close_targeted_retry_raw.jsonl').open('a',encoding='utf-8') as file:
            file.write(json.dumps(record,ensure_ascii=False)+'\n');file.flush();os.fsync(file.fileno())
        records.append(record)
        if result.get('http_status') in (403,429):break
        remaining=(f.parsed_time(date+'T13:34:42+08:00')-clock()).total_seconds()
        if remaining<=3:break
        wait(min(3,remaining))
    report={'status':'CAPTURED' if records else 'NO_ELIGIBLE_RETRY_OR_TIME','records':records,'requests':requests,
            'symbols':sorted(controller.state['symbols']),'last_finished_at':clock().isoformat()}
    atomic(output/'c2-report.json',{k:v for k,v in report.items() if k!='records'})
    return report


def refresh_saved(output,date,clock):
    import probe,official_retry,convergence,capture_completion,io,zipfile,shutil
    output=Path(output)
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer,'w') as archive:
            for path in output.iterdir():
                if path.is_file() and (path.name.endswith('_raw.jsonl') or path.name in ('run_summary.json','universe.json')):archive.writestr(path.name,path.read_bytes())
        summary,universe,snapshots,probes=official_retry.load_capture(buffer.getvalue())
    if summary.get('trade_date')!=date:raise ValueError('C2_CAPTURE_DATE_CONFLICT')
    pending={'checks':[],'status':'PENDING_SCHEDULED_POSTMARKET','sources':[]}
    report=convergence.write_report(date,snapshots,probes,universe,pending,output)
    live=json.loads((output/'live_research_summary.json').read_text());live['generated_at']=clock().isoformat();atomic(output/'live_research_summary.json',live)
    summary.update(candidate_count=live['candidate_count'],research_calculable_count=report['research_calculable_count'],live_research_summary=live)
    summary['convergence']={k:v for k,v in report.items() if k.endswith('_count') or k in ('status','version','validated')}
    summary['c2']={'completed_at':clock().isoformat(),'supplemental':True}
    c2_rows=[r for shot in snapshots for r in shot['records'] if r.get('phase')=='close_targeted_retry']
    summary['snapshots']['c2_supplement']={'batch_count':len(c2_rows),'symbol_requests':sum(len(r['symbols']) for r in c2_rows),'last_response_received_at':max((r['received_at'] for r in c2_rows),default=None)}
    atomic(output/'run_summary.json',summary)
    completion=capture_completion.classify(output,summary)
    summary.update(status=completion['status'],capture_outcome=completion['capture_outcome'],capture_completion=completion)
    atomic(output/'capture_completion.json',completion);atomic(output/'run_summary.json',summary)
    probe.package(output,date)
    return summary


def after_initial_publish(output,date,run_id,control,probe,*,enabled=None,clock=None,wait=None,transport=None):
    from datetime import datetime
    import candidate_publication,official_retry,io,zipfile,shutil
    enabled=C2_ENABLED if enabled is None else enabled
    if not enabled:return {'status':'DISABLED','requests':0}
    if not getattr(candidate_publication,'REVISIONS_ENABLED',False):return {'status':'REVISION_PUBLISHER_REQUIRED','requests':0}
    clock=clock or (lambda:datetime.now(f.TZ));output=Path(output)
    if clock()>=f.parsed_time(date+'T13:34:42+08:00'):return {'status':'NO_TIME_AFTER_INITIAL_PUBLICATION','requests':0}
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer,'w') as archive:
            for path in output.iterdir():
                if path.is_file() and (path.name.endswith('_raw.jsonl') or path.name in ('run_summary.json','universe.json')):archive.writestr(path.name,path.read_bytes())
        summary,universe,snapshots,probes=official_retry.load_capture(buffer.getvalue())
    if summary.get('trade_date')!=date:raise ValueError('C2_WRONG_SOURCE_DATE')
    for name in ('research_candidates.json','live_research_summary.json','candidate_publication.json'):
        if (output/name).exists():shutil.copyfile(output/name,output/('initial-'+name))
    result=capture(date,snapshots,universe,output,clock=clock,wait=wait,transport=transport,enabled=True)
    if not result['records']:return result
    refresh_saved(output,date,clock)
    result['publication']=candidate_publication.publish_live(output,date,run_id,control,probe)
    return {k:v for k,v in result.items() if k!='records'}
