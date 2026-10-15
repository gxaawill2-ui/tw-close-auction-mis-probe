"""Classify read-only GitHub observations; an Actions success is not capture proof."""
from datetime import datetime
import json
from pathlib import Path
import freshness as f
from fast_selection import atomic,safe_output


def classify(payload,date,observed_at):
    now=f.parsed_time(observed_at)
    if not now or now.astimezone(f.TZ).date().isoformat()!=date:
        raise ValueError('OBSERVATION_MUST_HAVE_SAME_DAY_AWARE_TIME')
    runs=[]
    for row in payload.get('workflow_runs',[]):
        created=f.parsed_time(row.get('created_at'))
        if not created or created>now or created.astimezone(f.TZ).date().isoformat()!=date:continue
        if row.get('head_branch')!='main' or row.get('path')!='.github/workflows/twse-mis-probe.yml':continue
        if row.get('event') not in ('workflow_dispatch','schedule'):continue
        if not row.get('display_title','').startswith('MIS live /'):continue
        runs.append({k:row.get(k) for k in ('id','html_url','head_sha','display_title','created_at','run_started_at','updated_at','status','conclusion')})
    start=f.parsed_time(date+'T13:00:00+08:00')
    state='RUN_OBSERVED_CAPTURE_UNPROVEN' if runs else 'NOT_DUE' if now<start else 'NO_MATCHING_RUN_OBSERVED'
    return {'trade_date':date,'observed_at':observed_at,'source':'GITHUB_CONNECTOR_READ_ONLY',
        'status':state,'matching_runs':runs,'actual_capture_confirmed':False,
        'formal_signals':None,'research_candidates':None,
        'note':'Run status/conclusion cannot establish capture success. Inspect saved same-day raw and summary; skip/dedup/late-start SUCCESS is not capture.'}


def save(payload,date,output,observed_at=None):
    observed_at=observed_at or datetime.now(f.TZ).isoformat()
    result=classify(payload,date,observed_at);directory=safe_output(output)
    name=datetime.fromisoformat(observed_at).strftime('%H%M%S%f')
    atomic(directory/('actions-'+name+'.json'),{'observation':result,'raw':payload})
    atomic(directory/'actions-latest.json',result)
    return result
