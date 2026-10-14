"""Experimental local pre-13:25 saver. Never invoked by an existing workflow.

Maximum two full-pool rounds at existing 50/5 limits; deadline responses cannot
be accepted. This saves observations, not an assertion of final tick completeness.
"""
import argparse
import json
import os
from pathlib import Path
import probe
from fast_selection import safe_output


def collect(date,universe,output):
    directory=safe_output(output)
    if probe.now_tpe().date().isoformat()!=date or probe.now_tpe()>probe.target(date,'13:24:45'):
        raise ValueError('NO_LATE_START_OR_HISTORICAL_PRECLOSE_BACKFILL')
    probe.wait_until(probe.target(date,'13:24:30'))
    prior=os.environ.get('MIS_FAST_JOURNAL_DIR');os.environ['MIS_FAST_JOURNAL_DIR']=str(directory)
    metrics=[]
    try:
        for i in range(2):
            if probe.now_tpe()>=probe.target(date,'13:25:00'):break
            result=probe.snapshot('pre_boundary_'+str(i+1),probe.now_tpe(),universe,directory,probe.target(date,'13:25:00'))
            metrics.append(result['metrics'])
            if any(r.get('http_status') in (403,429) for r in result['records']):break
    finally:
        if prior is None:os.environ.pop('MIS_FAST_JOURNAL_DIR',None)
        else:os.environ['MIS_FAST_JOURNAL_DIR']=prior
    (directory/'boundary-plan-result.json').write_text(json.dumps({'trade_date':date,'metrics':metrics,
        'last_trade_finality_proven':False,'formal_signals':0,'note':'New live evidence only, never a historical reconstruction.'},indent=2))
    return metrics


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('date');p.add_argument('universe',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();collect(a.date,json.loads(a.universe.read_text()),a.output)
