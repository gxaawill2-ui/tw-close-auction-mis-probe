"""Offline review of an already-extracted official MIS Artifact. No HTTP."""
from datetime import datetime
import argparse
import json
from pathlib import Path
import tempfile
import time
import freshness as f
from fast_selection import Engine
from stage3_selection import Pipeline
from stage7_retry import plan


def review(root):
    date='2026-10-16';universe=json.loads((root/'universe.json').read_text())
    paths=[*root.glob('*reference_*_raw.jsonl'),root/'preclose_raw.jsonl',root/'pre_targeted_retry_raw.jsonl',root/'probe_raw.jsonl']
    records=[json.loads(line) for p in paths if p.exists() for line in p.read_text().splitlines() if line]
    records.sort(key=lambda r:r.get('received_at') or '')
    with tempfile.TemporaryDirectory() as tmp:
        engine=Engine(date,universe,tmp,'SAVED_CAPTURE_ANALYSIS');began=time.perf_counter()
        for record in records:engine.feed(record)
        before=engine.view();proposal=plan(engine,date+'T13:34:20+08:00');after=engine.view()
        pipeline=Pipeline(engine,mode='OFFLINE_REPLAY');view=pipeline.compile(datetime.now(f.TZ).isoformat())
        return {'scope':'OFFLINE_REAL_SAVED_MIS_C2_PLAN_NOT_A_NEW_CAPTURE','analyzed_at':datetime.now(f.TZ).isoformat(),
            'records_replayed':len(records),'batch_count':engine.batch_count,'elapsed_seconds':time.perf_counter()-began,
            'universe_count':len(universe),'screening_calculable_count':view['screening_calculable_count'],
            'screening_unresolved_count':view['screening_unresolved_count'],
            'research_codes_before':[r['code'] for r in before['rows']],'research_codes_after':[r['code'] for r in after['rows']],
            'full_market_no_false_negative_claim':False,'verified_count':0,'mis_requests':0,'fugle_requests':0,'proposal':proposal}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('saved_capture_directory',type=Path);a=p.parse_args()
    result=review(a.saved_capture_directory)
    Path('reports/2026-10-16-stage7/real-saved-c2-plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
