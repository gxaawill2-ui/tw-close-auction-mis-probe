"""Synthetic journal benchmark: no MIS/Fugle requests, no formal file changes."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import tempfile
import time
from unittest.mock import patch
from datetime import datetime
import freshness as f
from fast_capture_journal import verify
from test_stage5_proposal import load


def main():
    journal=load('stage5_capture_journal','stage5_capture_journal.py')
    collector=load('stage5_benchmark_proposal','probe_with_journal.py')
    universe=[{'ex':'tse','code':str(1000+i),'name':'SYNTHETIC'} for i in range(2000)]
    at=collector.now_tpe();stamp=collector.iso(at)
    def fake(group,*args):
        time.sleep(.06 if group[0]['code']=='1000' else .001)
        payload={'msgArray':[{'ex':s['ex'],'c':s['code'],'n':s['name'],'z':'100','v':'1000','tv':'20','t':'13:30:00'} for s in group]}
        return collector.FetchResult(stamp,stamp,1,200,0,None,json.dumps(payload),payload)
    runs=[];append_times=[];equal=True;rollback=True
    original=journal.Journal.append
    with tempfile.TemporaryDirectory(prefix='stage5-synthetic-benchmark-') as tmp:
        root=Path(tmp)
        for repeat in range(10):
            hashes=[]
            for mode in ('disabled_before','enabled','disabled_after'):
                output=root/f'{repeat}-{mode}';output.mkdir();private=output/'journal';first=[]
                def append(self,record):
                    start=time.perf_counter();event=original(self,record)
                    append_times.append((time.perf_counter()-start)*1000)
                    if not first:first.append({'batch_no':record['batch_no'],'after_ms':(time.perf_counter()-began)*1000})
                    return event
                with patch.dict(os.environ,{'RUNNER_TEMP':tmp,'MIS_FAST_JOURNAL_DIR':str(private) if mode=='enabled' else ''}),patch.object(collector,'fetch_mis',side_effect=fake),patch.object(journal.Journal,'append',append):
                    began=time.perf_counter();result=collector.snapshot('close_reference_A',at,universe,output)
                    elapsed=(time.perf_counter()-began)*1000
                raw=(output/'close_reference_A_raw.jsonl').read_bytes();hashes.append(hashlib.sha256(raw).hexdigest())
                if mode=='enabled':
                    events=[json.loads(line) for line in (private/'fast-capture-journal.jsonl').read_text().splitlines()]
                    for event in events:verify(event,private)
                    assert len(events)==40 and first[0]['batch_no']!=1
                else:rollback=rollback and not private.exists()
                runs.append({'repeat':repeat,'mode':mode,'total_ms':round(elapsed,3),'first_durable_batch':first[0] if first else None})
            equal=equal and len(set(hashes))==1
    assert equal and rollback
    totals={mode:round(statistics.median([r['total_ms'] for r in runs if r['mode']==mode]),3) for mode in ('disabled_before','enabled','disabled_after')}
    ordered=sorted(append_times)
    return {'scope':'SYNTHETIC_LOCAL_FILESYSTEM_NOT_GITHUB_RUNNER_OR_REAL_MARKET',
        'completed_at':datetime.now(f.TZ).isoformat(),'universe_size':2000,'batch_size':50,'batches_per_snapshot':40,
        'repeats':10,'mis_requests':0,'fugle_requests':0,'formal_files_modified':False,
        'legacy_raw_bytes_equal_on_off_on':equal,'disable_restores_no_journal_writes':rollback,
        'snapshot_total_median_ms':totals,'append_fsync_p50_ms':round(statistics.median(ordered),3),
        'append_fsync_p95_ms':round(ordered[int(len(ordered)*.95)-1],3),
        'first_durable_batch_max_ms':round(max(r['first_durable_batch']['after_ms'] for r in runs if r['first_durable_batch']),3),
        'slow_first_batch_simulated_delay_ms':60,'verified_journal_events':400,
        'limitations':['Local filesystem only; GitHub runner fsync latency remains unmeasured.',
            'Snapshot completion is dominated by the simulated slow response; no real market latency claim.'],
        'runs':runs}


if __name__=='__main__':print(json.dumps(main(),indent=2))
