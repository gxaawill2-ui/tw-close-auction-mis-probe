"""Deterministic synthetic transport scenarios, not historical recovery claims."""
import copy
import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import close_research
import probe
from test_close_research import DAY, ref
from test_convergence import SYMBOL


def batch(phase,symbols,missing=(),stamp=None):
    row=ref(phase);item=row['response']['msgArray'][0]
    row['symbols']=symbols
    row['response']['msgArray']=[{**copy.deepcopy(item),'ex':s['ex'],'c':s['code']} for s in symbols if s['code'] not in missing]
    row['missing']=['tse:'+s['code'] for s in symbols if s['code'] in missing]
    row.update(expected_count=len(symbols),returned_count=len(row['response']['msgArray']),empty=[],duplicate=[])
    if stamp:
        row.update(phase='close_targeted_retry',planned_at=probe.iso(stamp),requested_at=probe.iso(stamp),received_at=probe.iso(stamp+timedelta(seconds=3)))
        row['response']['queryTime']['sysTime']=(stamp+timedelta(seconds=2)).strftime('%H:%M:%S')
    return row


def scenario(mode):
    universe=[{**SYMBOL,'code':str(1000+i)} for i in range(1970)]
    missing=set() if mode=='normal' else {s['code'] for s in (universe[:50] if mode!='scattered_50' else universe[::39][:50])}
    a=[batch('close_reference_A',universe[i:i+50]) for i in range(0,1970,50)]
    b=[batch('close_reference_B',universe[i:i+50],missing) for i in range(0,1970,50)]
    snapshots=[{'records':a},{'records':b}]
    after_b=len(universe)-len(close_research.affected(DAY,snapshots,universe))
    selected=close_research.affected(DAY,snapshots,universe)
    # Model a C transport failure too, forcing the implemented post-C retry path.
    c_missing={s['code'] for s in selected}
    c=[batch('close_reference_C',selected[i:i+50],c_missing) for i in range(0,len(selected),50)]
    snapshots.append({'records':c});current=[probe.target(DAY,'13:34:14')];requests=[]
    def capture(phase,planned,symbols,output,deadline):
        requests.append(len(symbols));unavailable={s['code'] for s in symbols} if mode=='deadline_exhausted' else set()
        rows=[batch('close_reference_C',symbols[i:i+50],unavailable,stamp=planned) for i in range(0,len(symbols),50)]
        current[0]+=timedelta(seconds=3)
        return {'records':rows,'metrics':{'phase':phase,'success_count':len(symbols)-len(unavailable)}}
    with patch.object(probe,'now_tpe',side_effect=lambda:current[0]),patch.object(probe,'wait_until',side_effect=lambda t:current.__setitem__(0,t)),patch.object(probe,'snapshot',side_effect=capture):
        retries=probe.targeted_retries('close',DAY,snapshots,universe,Path('/unused'))
    after=len(universe)-len(close_research.affected(DAY,snapshots+retries,universe))
    return {'scenario':mode,'synthetic':True,'universe':len(universe),'before_B_converged':after_b,'after_retries_converged':after,
        'before_pct':round(after_b/len(universe)*100,4),'after_pct':round(after/len(universe)*100,4),
        'retry_rounds':len(retries),'requested_symbols_per_round':requests,'virtual_additional_elapsed_seconds':(current[0]-probe.target(DAY,'13:34:14')).total_seconds(),
        'deadline_respected':current[0]<=probe.target(DAY,'13:35:00'),'formal_signals':0,
        'latency_assumption':'Each targeted round 3s; backoff 5/10s; deterministic fabricated responses only, never historical evidence.'}


if __name__=='__main__':
    results=[scenario(m) for m in ('normal','concentrated_50','scattered_50','deadline_exhausted')]
    for r in results:
        assert r['deadline_respected'];assert r['formal_signals']==0
        assert r['after_retries_converged']==(1920 if r['scenario']=='deadline_exhausted' else 1970)
    path=Path('reports/2026-10-14/simulation.json');path.write_text(json.dumps(results,indent=2));print(path.read_text())
