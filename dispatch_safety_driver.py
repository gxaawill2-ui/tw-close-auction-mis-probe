"""Actually dispatch the workflow twice; no PAT and no market capture.

Uses only this repo's workflow GITHUB_TOKEN (actions:write). This is NOT a
cron-job.org acceptance test, which must be performed by the user there.
"""
import json
import os
import time
from pathlib import Path

import run_control as c


def wait_for(read, predicate, timeout=300):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        value=read()
        if predicate(value):return value
        time.sleep(5)
    raise RuntimeError('Dispatch safety acceptance timed out')


def main():
    test_id=os.environ['GITHUB_RUN_ID']
    title='MIS dispatch-safety / dispatch-safety-test / '+test_id
    payload={'ref':'main','inputs':{'mode':'dispatch-safety','trigger_source':'dispatch-safety-test','dispatch_test_id':test_id}}
    state_path='state/tests/dispatch-'+test_id+'.json'
    c.api('actions/workflows/twse-mis-probe.yml/dispatches','POST',payload)
    claimed,first_sha=wait_for(lambda:c.read_state(state_path),lambda x:bool(x[0].get('capture_claimed')))
    first_id=claimed['capture_owner_run_id']
    # Second dispatch while first workflow holds concurrency; its runner must
    # subsequently see the same immutable CAS claim and skip.
    c.api('actions/workflows/twse-mis-probe.yml/dispatches','POST',payload)
    def children():
        runs=c.api('actions/workflows/twse-mis-probe.yml/runs?event=workflow_dispatch&per_page=30')
        return [r for r in runs.get('workflow_runs',[]) if r.get('display_title')==title]
    runs=wait_for(children,lambda rs:len(rs)==2 and all(r['status']=='completed' for r in rs))
    state,last_sha=c.read_state(state_path)
    if first_sha!=last_sha or state.get('capture_owner_run_id')!=first_id:
        raise RuntimeError('Duplicate dispatch changed the first claim')
    if any(r.get('conclusion')!='success' for r in runs):
        raise RuntimeError('A dispatched guard workflow failed')
    # Read actual child Artifacts, not only HTTP 204 or workflow conclusion.
    import official_retry
    import io
    import zipfile
    decisions=[]
    for r in runs:
        artifacts=c.api('actions/runs/'+str(r['id'])+'/artifacts')
        matching=[a for a in artifacts['artifacts'] if a['name']=='mis-probe-'+str(r['id'])]
        if len(matching)!=1:raise RuntimeError('Guard Artifact missing')
        archive=official_retry.download_archive(c.REPO,matching[0]['id'])
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            names=[n for n in z.namelist() if Path(n).name=='dispatch_safety.json']
            if len(names)!=1:raise RuntimeError('Guard decision missing')
            decision=json.loads(z.read(names[0]))
            if decision['mis_requests']!=0 or decision['daily_live_state_mutated']:
                raise RuntimeError('Guard test touched market execution')
            decisions.append(decision)
    if sorted(d['decision'] for d in decisions)!=['CLAIMED_TEST_ONLY','SKIPPED_EXISTING_CAPTURE']:
        raise RuntimeError('Expected one claim and one skip')
    report={'status':'PASS','test_id':test_id,'scope':'ISOLATED_DAILY_LOCK_TEST_NOT_CRON_JOB_ORG_TEST',
            'child_run_ids':[r['id'] for r in runs],'decisions':decisions,
            'immutable_first_state_sha':first_sha,'market_capture_count':0,
            'external_scheduler_verified':False,'completed_at':c.probe.iso()}
    output=Path('dispatch-safety-results');output.mkdir(exist_ok=True)
    (output/'dispatch_safety_acceptance.json').write_text(json.dumps(report,indent=2))
    c.merge_state('state/tests/dispatch_latest.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
