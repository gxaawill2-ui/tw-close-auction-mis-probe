"""Read-only Oct14 replay plus separate synthetic fixture pages and latency report."""
import argparse
import json
from pathlib import Path
import stage3_ticks as ticks
from stage3_fixtures import DAY,example
from stage3_selection import Pipeline,decide
from fast_selection import replay,atomic,safe_output,stamp
from build_stage3_preview import build

def run(archive,output):
    directory=safe_output(output)
    historical=replay(Path(archive).read_bytes(),directory/'raw-replay')
    rows=[decide(r,None,DAY,stamp(),mode='OFFLINE_REPLAY') for r in historical['rows']]
    actual={'schema_version':'STAGE3_SELECTION_V1','trade_date':DAY,'mode':'OFFLINE_REPLAY','version':1,
        'generated_at':stamp(),'is_synthetic':False,'verified_count':0,'research_count':len(rows),
        'unknown_candidate_count':0,'simulated_verified_count':0,'universe_count':historical['universe_count'],
        'screening_calculable_count':1946,'screening_unresolved_count':24,
        'full_market_no_false_negative_claim':False,'rows':rows,'retracted':historical['retracted'],
        'final_audit':historical['final_audit'],'metrics':{**historical['metrics'],
        'first_independent_pre_at':None,'first_independent_close_at':None,'public_written_at':None,
        'first_public_observed_at':None}}
    # Coverage comes from the saved capture, not a fixed future stock count.
    import official_retry,convergence
    summary,universe,snapshots,probes=official_retry.load_capture(Path(archive).read_bytes())
    report=convergence.build_report(DAY,snapshots,probes,universe,{'checks':[]})
    actual['screening_calculable_count']=report['research_calculable_count']
    actual['screening_unresolved_count']=len(universe)-report['research_calculable_count']
    atomic(directory/'stage3-results.json',actual)
    build(actual,directory/'stage3-preview.html')
    synthetic_rows=[]
    for code in ('2330','2317','2454'):
        row,bundle=example(code=code)
        if code=='2454':row['P_before']='98'
        synthetic_rows.append(decide(row,bundle,DAY,DAY+'T13:35:05+08:00',mode='SYNTHETIC',contract=ticks.TEST_CONTRACT))
    synthetic={**actual,'mode':'SYNTHETIC','is_synthetic':True,'rows':synthetic_rows,
        'universe_count':3,'screening_calculable_count':3,'screening_unresolved_count':0,
        'research_count':2,'unknown_candidate_count':1,'simulated_verified_count':2,'generated_at':stamp()}
    atomic(directory/'synthetic-results.json',synthetic);build(synthetic,directory/'synthetic-preview.html')
    atomic(directory/'stage3-latency.json',{'kind':'HISTORICAL_EVIDENCE_REPLAY_NOT_LIVE_PUBLICATION',
        'research_candidate_evidence_available_at':historical['metrics']['first_candidate_evidence_available_at'],
        'first_independent_pre_at':None,'first_independent_close_at':None,'first_verified_at':None,
        'first_public_written_at':None,'first_external_browser_observed_at':None,
        'all_historical_candidates_evidence_at':historical['metrics']['last_evidence_update_at'],
        'actual_program_generated_at':actual['generated_at'],'synthetic_test_passes':2,'formal_signals':0})
    return actual

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result=run(a.archive,a.output);print(json.dumps({k:result[k] for k in ('verified_count','research_count','screening_calculable_count','screening_unresolved_count')},ensure_ascii=False))
