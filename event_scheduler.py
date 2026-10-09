"""Event-only date/slot receipts. No MIS imports or workflow dispatches.

GitHub supplies a cron expression and run creation time, not the intended
calendar date. Execution scope is an explicit, bounded local policy, recorded
separately from scheduled_for (which remains unknown for native schedule).
Git fast-forward publication is the compare-and-swap; workflow concurrency is
an additional serialization layer, never the sole duplicate guard.
"""
import argparse
import copy
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
SLOTS = {'20 0 * * *': '08:20', '20 9 * * *': '17:20'}
MAX_SCANS = 2
LEASE_SECONDS = 1800


def instant(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None: raise ValueError('Timezone required')
    return d.astimezone(TZ)


def identify(event_name, cron, declared_slot, triggered, run_id):
    created = instant(triggered)
    slot = SLOTS.get(cron) if event_name == 'schedule' else declared_slot
    source = 'GITHUB_SCHEDULE' if event_name == 'schedule' else 'EXTERNAL_BACKUP' if slot in SLOTS.values() else 'ADHOC'
    result = {'schedule_slot': slot or 'ADHOC', 'scheduled_for': None,
        'scheduled_for_evidence': 'NOT_EXPOSED_BY_GITHUB', 'actual_trigger_at': created.isoformat(),
        'trigger_source': source, 'workflow_run_id': str(run_id), 'github_event_schedule': cron or None,
        'delay_seconds': None, 'origin_date_verified': False}
    if source == 'ADHOC':
        result.update(identity='adhoc-' + str(run_id), planned_for=None, execution_scope_date=None, eligible=True)
        return result
    if slot not in SLOTS.values(): raise ValueError('Unknown cron slot')
    hour, minute = map(int, slot.split(':'))
    planned = created.replace(hour=hour, minute=minute, second=0, microsecond=0)
    seconds = (created - planned).total_seconds()
    # Explicit cron/dispatch slot plus bounded same-day execution window.
    # Late native delivery is audited without guessing its missing origin date.
    lower, upper = (0, 900) if source == 'GITHUB_SCHEDULE' else (900, 3600)
    result.update(identity=created.date().isoformat() + '-' + slot.replace(':',''),
        execution_scope_date=created.date().isoformat(), planned_for=planned.isoformat(),
        execution_scope_policy='EXPLICIT_SLOT_AND_SAME_DAY_BOUNDED_WINDOW_V1',
        policy_delay_seconds=seconds, eligible=lower <= seconds <= upper)
    return result


def recovery_scope(identity, last_success):
    """Preserve existing late native refresh while never fabricating its slot date.

    A maximum of one successful recovery per actual six-hour bucket, and a
    two-hour source freshness gate, bound delayed/backlogged native deliveries.
    The recovery does not fulfill any normal morning/evening planned slot.
    """
    out=copy.deepcopy(identity)
    if out['eligible'] or out['trigger_source']!='GITHUB_SCHEDULE': return out
    created=instant(out['actual_trigger_at'])
    if last_success and (created-instant(last_success)).total_seconds()<7200: return out
    out.update(identity='unattributed-'+created.date().isoformat()+'-'+str(created.hour//6),
        eligible=True,execution_scope_date=None,planned_for=None,policy_delay_seconds=None,
        execution_scope_policy='UNATTRIBUTED_NATIVE_RECOVERY_6H_BUCKET; NOT_ORIGINAL_SLOT',
        original_slot_not_fulfilled=True)
    return out


def freshness_blocks_recovery(identity, health, now):
    last=health.get('last_successful_scan_at')
    return bool(identity.get('original_slot_not_fulfilled') and last and
        (instant(now)-instant(last)).total_seconds()<7200)


def claim(previous, identity, now, run_id):
    """Pure CAS proposal; caller must publish against the current git parent."""
    now = instant(now)
    old = copy.deepcopy(previous or {})
    if not identity['eligible']: return old, 'UNATTRIBUTED_DELAYED_NATIVE' if identity['trigger_source']=='GITHUB_SCHEDULE' else 'OUTSIDE_BACKUP_WINDOW'
    if old.get('result') in ('ON_TIME','DELAYED','RECOVERED_BY_BACKUP','ADHOC_PUBLISHED') and old.get('published_at'):
        return old, 'DUPLICATE_SUCCESS'
    if old.get('lease_expires_at') and instant(old['lease_expires_at']) > now:
        return old, 'LEASE_HELD'
    if old.get('scan_attempts',0) >= MAX_SCANS: return old, 'RETRY_LIMIT'
    out = {**old, **identity, 'runner_started_at': identity.get('runner_started_at') or now.isoformat(), 'scan_started_at': None,
        'scan_finished_at': None, 'published_at': None, 'result':'LEASED',
        'lease_owner':str(run_id), 'lease_expires_at':(now+timedelta(seconds=LEASE_SECONDS)).isoformat(),
        'scan_attempts':old.get('scan_attempts',0)+1, 'duplicate_trigger':False,
        'missed_slot':identity['trigger_source']=='EXTERNAL_BACKUP',
        'slot_state_before_claim':'MISSED' if identity['trigger_source']=='EXTERNAL_BACKUP' else 'UNVERIFIED_ORIGIN' if identity.get('original_slot_not_fulfilled') else 'PENDING',
        'missed_slot_definition':'NO_SUCCESS_RECEIPT_BY_BACKUP_CHECK; NOT_PROOF_GITHUB_DROPPED_TRIGGER',
        'source_health':None, 'history':old.get('history',[]) + ([old] if old else [])}
    return out, 'CLAIMED'


def finish(receipt, run_id, now, success, health=None, published_commit=None):
    if receipt.get('lease_owner') != str(run_id): raise ValueError('Lease ownership changed; reject publication')
    out = copy.deepcopy(receipt)
    completed_delay=(instant(now)-instant(out['planned_for'])).total_seconds() if out.get('planned_for') else None
    out['policy_completion_delay_seconds']=completed_delay
    out.update(scan_finished_at=now, lease_expires_at=now, source_health=health,
        published_at=now if success else None, published_commit=published_commit if success else None,
        result='ADHOC_PUBLISHED' if success and out['trigger_source']=='ADHOC' else
            'RECOVERED_BY_BACKUP' if success and out['trigger_source']=='EXTERNAL_BACKUP' else
            'ON_TIME' if success and completed_delay is not None and completed_delay<=900 else 'DELAYED' if success else 'FAILED')
    return out


def git(args, cwd):
    return subprocess.check_output(['git',*args],cwd=cwd,text=True,stderr=subprocess.DEVNULL).strip()


def transaction(update):
    """Three bounded fast-forward CAS attempts, isolated from scan checkout.

    Only state/events/scheduler files may be changed. Authentication is the
    checkout's short-lived GitHub token; it is never read or printed here.
    """
    root = Path.cwd()
    with tempfile.TemporaryDirectory(prefix='event-receipt-') as directory:
        path = Path(directory)/'checkout'
        git(['clone','--shared','--quiet',str(root),str(path)],root)
        # Reuse checkout's HTTP extraheader through git configuration internally.
        # Never serialize the value, print it, or persist it in tracked files.
        for key in git(['config','--name-only','--get-regexp',r'http\..*\.extraheader'],root).splitlines():
            value = git(['config','--get',key],root)
            git(['config',key,value],path)
        git(['remote','set-url','origin',git(['remote','get-url','origin'],root)],path)
        git(['config','user.name','github-actions[bot]'],path)
        git(['config','user.email','41898282+github-actions[bot]@users.noreply.github.com'],path)
        for attempt in range(3):
            git(['fetch','--quiet','origin','main'],path)
            git(['checkout','--detach','--force','origin/main'],path)
            output, changes = update(path)
            if not changes: return output
            for relative, value in changes.items():
                if not relative.startswith('state/events/scheduler/') or '..' in relative: raise ValueError('Receipt path outside allowed scope')
                target=path/relative;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
                git(['add',relative],path)
            if not git(['diff','--cached','--name-only'],path): return output
            git(['commit','--quiet','-m','Record isolated event scan receipt'],path)
            try:
                git(['push','--quiet','origin','HEAD:main'],path)
                return output
            except subprocess.CalledProcessError:
                if attempt==2: raise RuntimeError('RECEIPT_CAS_FAILED_AFTER_3_ATTEMPTS') from None
    raise RuntimeError('RECEIPT_UNAVAILABLE')


def read(path):
    return json.loads(path.read_text()) if path.exists() else {}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['claim','start','finish']);args=parser.parse_args()
    env=os.environ; run_id=env['GITHUB_RUN_ID']; now=datetime.now(TZ).isoformat()
    identity=identify(env.get('GITHUB_EVENT_NAME','workflow_dispatch'),env.get('EVENT_CRON',''),env.get('EVENT_SLOT',''),env['EVENT_CREATED_AT'],run_id)
    identity=recovery_scope(identity,read(Path('state/events/source-health.json')).get('last_successful_scan_at'))
    if args.operation!='claim':
        key=env.get('EVENT_RECEIPT_ID','')
        if not re.fullmatch(r'[a-z0-9-]{1,100}',key): raise ValueError('Explicit claimed receipt identity required')
        identity['identity']=key
    identity['runner_started_at']=env.get('EVENT_RUNNER_STARTED_AT') or now
    relative='state/events/scheduler/slots/'+identity['identity']+'.json'
    audit='state/events/scheduler/attempts/'+run_id+'.json'
    def update(path):
        previous=read(path/relative)
        if args.operation=='claim':
            current_health=read(path/'state/events/source-health.json')
            proposal,decision=(previous,'FRESH_DATA_UNATTRIBUTED_NATIVE') if freshness_blocks_recovery(identity,current_health,now) else claim(previous,identity,now,run_id)
            observation={**identity,'runner_started_at':now,'decision':decision,
                'result':decision,'duplicate_trigger':decision in ('DUPLICATE_SUCCESS','LEASE_HELD'),
                'source_health':{'last_successful_scan_at':current_health.get('last_successful_scan_at'),'metrics':current_health.get('metrics')},'scan_started_at':None,'scan_finished_at':None,'published_at':None}
            changes={audit:observation}
            if decision=='CLAIMED': changes[relative]=proposal
            return decision, changes
        if previous.get('lease_owner')!=run_id: raise ValueError('Receipt owner mismatch')
        if args.operation=='start':
            previous['scan_started_at']=now
            return 'STARTED',{relative:previous}
        health=read(Path('state/events/source-health.json'))
        published=env.get('EVENT_PUBLISHED')=='true'
        success=published and any(s['status']=='SUCCESS' for s in health.get('sources',[]))
        summary={'last_successful_scan_at':health.get('last_successful_scan_at'),
            'metrics':health.get('metrics'), 'sources':[{'source_id':s['source_id'],'status':s['status']} for s in health.get('sources',[])]}
        result=finish(previous,run_id,now,success,summary,env.get('EVENT_DATA_COMMIT'))
        result['scan_finished_at']=env.get('EVENT_SCAN_FINISHED_AT') or now
        result['source_scan_result']='PARTIAL' if success and any(s['status']!='SUCCESS' for s in health.get('sources',[])) else 'SUCCESS' if success else 'FAILED'
        result['data_published_at']=now if published else None
        return result['result'],{relative:result,audit:result}
    result=transaction(update)
    if env.get('GITHUB_OUTPUT'):
        with open(env['GITHUB_OUTPUT'],'a') as output: output.write('decision='+result+'\nreceipt_identity='+identity['identity']+'\n')
    print(json.dumps({'decision':result,'slot':identity['schedule_slot'],'scheduled_for':None,'planned_for':identity.get('planned_for')}))

if __name__=='__main__': main()
