#!/usr/bin/env python3
"""One-date unattended relay; starts today instead of waiting for tomorrow's cron."""
import argparse
import json
import os
import time
from datetime import datetime

import probe
import run_control as control

TRADE_DATE='2026-10-02'
STATE_PATH='state/armed/'+TRADE_DATE+'.json'


def hold(until, stage):
    target=datetime.fromisoformat(until).astimezone(probe.TZ)
    if target.date().isoformat()!=TRADE_DATE or probe.now_tpe().date().isoformat() not in ('2026-10-01',TRADE_DATE):
        raise RuntimeError('This pre-armed relay is restricted to 2026-10-02')
    # A single hosted job is bounded below GitHub's six-hour execution limit.
    if target.timestamp()-time.time()>345*60:
        raise RuntimeError('Relay segment exceeds bounded job duration')
    control.merge_state(STATE_PATH,{'trade_date':TRADE_DATE,'status':'armed_running',
        'stage':stage,'run_id':os.getenv('GITHUB_RUN_ID'),
        'runner_started_at':os.getenv('RUNNER_STARTED_AT') or probe.iso(),
        'next_target':until,'stage_started_at':probe.iso()})
    control.merge_state('state/armed_latest.json',{'trade_date':TRADE_DATE,'state_path':STATE_PATH})
    control.publish()
    heartbeat=0
    while time.time()<target.timestamp():
        if time.monotonic()-heartbeat>300:
            print(json.dumps({'relay_date':TRADE_DATE,'stage':stage,'time':probe.iso(),
                'waiting_until':until}),flush=True)
            heartbeat=time.monotonic()
        time.sleep(min(30,max(0,target.timestamp()-time.time())))
    control.merge_state(STATE_PATH,{'stage':stage+'_completed','stage_finished_at':probe.iso()})
    control.publish()


def finish():
    current,_=control.read_state(control.live_path(TRADE_DATE))
    control.merge_state(STATE_PATH,{'stage':'live_job_finished','status':current.get('status','relay_failed'),
        'finished_at':probe.iso(),'capture_run_id':current.get('run_id')})
    control.publish()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--until')
    p.add_argument('--stage')
    p.add_argument('--finish',action='store_true')
    a=p.parse_args()
    if a.finish:finish()
    else:hold(a.until,a.stage)
