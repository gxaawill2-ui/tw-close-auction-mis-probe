"""Small private observations alongside, never restarting, today's existing task.

Two fixed controls, six outbound Fugle requests per rolling 60 seconds and 30
overall. Combined with the existing source's <=47/min this stays <=53/min.
No MIS capture, dispatch, journal change, public provider data, or VERIFIED.
"""
from collections import deque
from datetime import datetime,timedelta
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request
import freshness as f
from fast_selection import atomic
from stage5_runtime import Source,Vault,NoRedirect,restore_bundle
from stage5_archive import probe
from stage5_audit import audit

DATE='2026-10-16'
CONTROLS=[{'ex':'tse','code':'2330'},{'ex':'otc','code':'6488'}]
PHASES=[('PRE_CUTOFF','13:24:00'),('AFTER_CUTOFF','13:25:15'),
    ('NORMAL_CLOSE','13:30:15'),('DELAYED_CLOSE','13:33:15'),('POST_CLOSE','13:35:15')]


class SmallBudget:
    def __init__(self,opener,*,clock=time.monotonic):
        self.opener,self.clock=opener,clock;self.starts=deque();self.total=0
    def __call__(self,request,timeout):
        # Count actual outbound attempts, including Source's retries.
        if not request.full_url.startswith('https://api.fugle.tw/marketdata/v1.0/stock/intraday/'):
            raise ValueError('SOURCE_CONTROL_DESTINATION_REJECTED')
        now=self.clock()
        while self.starts and now-self.starts[0]>=60:self.starts.popleft()
        if len(self.starts)>=6 or self.total>=30:raise ValueError('SOURCE_SMALL_CONTROL_BUDGET_EXHAUSTED')
        self.starts.append(now);self.total+=1
        return self.opener(request,timeout=timeout)


def now():return datetime.now(f.TZ)


def scope():
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':
        raise ValueError('REFUSE_OTHER_ENVIRONMENT')


def capture():
    scope()
    if now().date().isoformat()!=DATE or now()>=f.parsed_time(DATE+'T13:23:30+08:00'):
        raise ValueError('PRIVATE_CONTROLS_ARMING_WINDOW_MISSED_NO_BACKFILL')
    output=Path('stage5-durable-control-report');output.mkdir(exist_ok=True)
    report={'scope':'TWO_REAL_PRIVATE_CONTROL_OBSERVATIONS_NOT_STRATEGY_CANDIDATES',
        'trade_date':DATE,'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'armed_at':now().isoformat(),'existing_capture_restarted':False,'mis_requests':0,
        'maximum_added_provider_requests_per_rolling_minute':6,'maximum_added_provider_requests':30,
        'original_capture_maximum_requests_per_minute':47,'combined_upper_bound_per_minute':53,
        'private_retention_days':7,'control_symbols':[c['code'] for c in CONTROLS],
        'control_captures':[],'verified_count':0,'raw_market_data_public':False,'production_modified':False}
    vault=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'))
    report['private_canary']=probe(vault,DATE)
    budget=SmallBudget(urllib.request.build_opener(NoRedirect()).open)
    with tempfile.TemporaryDirectory(prefix='stage5-durable-real-private-') as temporary:
        source=Source(os.getenv('FUGLE_API_KEY'),Path(temporary)/'raw',vault,
            opener=budget,max_requests=30,require_durable=True)
        atomic(output/'controls.json',report)
        print(json.dumps({'event':'PRIVATE_CONTROLS_ARMED','armed_at':report['armed_at'],'max_added_per_minute':6,'max_total':30}),flush=True)
        for phase,clock in PHASES:
            target=f.parsed_time(DATE+'T'+clock+'+08:00')
            while now()<target:time.sleep(min(10,(target-now()).total_seconds()))
            if source.stopped:break
            if (now()-target).total_seconds()>15:
                report['control_captures'].append({'phase':phase,'status':'MISSED_REAL_SLOT_NO_BACKFILL','observed_at':now().isoformat()})
                continue
            deadline=now()+timedelta(seconds=45)
            for candidate in CONTROLS:
                if source.stopped:break
                bundle=source.collect(candidate,DATE,deadline,max_pages=1,tail_only=True)
                result=audit(bundle,candidate,DATE,now().isoformat());result['phase']=phase
                result['controls_are_strategy_candidates']=False
                report['control_captures'].append(result)
                atomic(output/'controls.json',report)
                print(json.dumps({'event':'PRIVATE_CONTROL_SAVED','phase':phase,'symbol':candidate['code'],
                    'observed_at':result['observed_at'],'status':result['status'],
                    'private_manifest_id':result.get('private_manifest_id'),
                    'private_evidence_recoverable_after_job':result.get('private_evidence_recoverable_after_job',False),
                    'reasons':result['reasons']}),flush=True)
        report.update(finished_at=now().isoformat(),actual_added_provider_requests=budget.total,
            source_stopped=source.stopped,runner_private_copy_removed_on_exit=True)
        atomic(output/'controls.json',report)
    print(json.dumps({'event':'PRIVATE_CONTROLS_FINISHED','fugle_requests':budget.total,'verified_count':0,'finished_at':report['finished_at']}),flush=True)
    return report


def recover(path):
    scope();prior=json.loads(Path(path).read_text())
    if prior.get('trade_date')!=DATE or prior.get('scope')!='TWO_REAL_PRIVATE_CONTROL_OBSERVATIONS_NOT_STRATEGY_CANDIDATES' or prior.get('run_id')!=os.getenv('GITHUB_RUN_ID'):
        raise ValueError('WRONG_PRIVATE_CONTROL_REPORT')
    vault=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'))
    results=[]
    for item in prior['control_captures']:
        ident=item.get('private_manifest_id')
        if not ident:continue
        candidate=next((c for c in CONTROLS if c['code']==item.get('symbol') and c['ex']==item.get('exchange')),None)
        if candidate is None:raise ValueError('WRONG_PRIVATE_CONTROL_SECURITY')
        bundle=restore_bundle(vault,DATE,ident)
        result=audit(bundle,candidate,DATE,now().isoformat());result.update(phase=item['phase'],private_manifest_id=ident)
        if result.get('private_evidence_recoverable_after_job') is not True:raise ValueError('PRIVATE_CONTROL_RECOVERY_INCOMPLETE')
        results.append(result)
    report={'scope':'REAL_FUGLE_PRIVATE_RAW_RESTORED_ON_DIFFERENT_RUNNER_NO_RAW_PUBLIC',
        'run_id':os.getenv('GITHUB_RUN_ID'),'recovered_at':now().isoformat(),'fugle_requests':0,
        'restored_bundles':len(results),'results':results,'verified_count':0,'raw_market_data_public':False,
        'status':'RECOVERED' if results else 'NO_COMPLETE_PRIVATE_BUNDLES'}
    output=Path('stage5-durable-recovery-report');output.mkdir(exist_ok=True)
    atomic(output/'private-controls-recovered.json',report)
    print(json.dumps(report,indent=2));return report


if __name__=='__main__':
    import sys
    try:
        if len(sys.argv)==3 and sys.argv[1]=='recover':recover(sys.argv[2])
        elif len(sys.argv)==1:capture()
        else:raise ValueError('INVALID_PRIVATE_CONTROL_COMMAND')
    except Exception as exc:
        print(json.dumps({'event':'PRIVATE_CONTROL_TASK_STOPPED_NO_RAW_LOGGED','error_type':type(exc).__name__}),flush=True)
        raise SystemExit(1)
