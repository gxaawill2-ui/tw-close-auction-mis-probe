"""Offline-only evidence audit. Never fetch MIS, GitHub, or official prices.

Usage: python replay_capture.py ARTIFACT.zip OUTPUT_DIRECTORY
The input ZIP is hashed before/after; outputs must be in a new directory.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import zipfile
import io

import candidate_publication
import capture_completion
import convergence
import freshness
import official_retry


def write_csv(path, rows):
    if not rows:
        path.write_text('');return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


def audit(archive, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    digest=hashlib.sha256(archive).hexdigest()
    summary,universe,snapshots,probes=official_retry.load_capture(archive)
    date=summary['trade_date']
    report=convergence.build_report(date,snapshots,probes,universe,{'checks':[]})
    series=convergence.grouped(snapshots,date)
    batch_rows=[];attempt_rows=[];symbol_rows=[]
    b_rows=[r for s in snapshots for r in s['records'] if r.get('phase')=='close_reference_B']
    missing={key for r in b_rows for key in r.get('missing',[])}
    for snap in snapshots:
        for r in snap['records']:
            attempts=r.get('attempts') or ([r] if r.get('error')!='CAPTURE_DEADLINE_NO_REQUEST' else [])
            batch_rows.append({k:r.get(k) for k in ('phase','batch_no','planned_at','requested_at','received_at','http_status','error','expected_count','returned_count')}|
                {'missing_count':len(r.get('missing',[])),'actual_attempts':len(attempts),
                 'attempt_timeout_count':sum(any(t in (a.get('error') or '').lower() for t in ('timeout','timed out')) for a in attempts),
                 'attempt_total_latency_ms':sum(a.get('latency_ms',0) for a in attempts)})
            for i,a in enumerate(attempts):
                attempt_rows.append({'phase':r['phase'],'batch_no':r['batch_no'],'attempt':i+1,
                    **{k:a.get(k) for k in ('requested_at','received_at','http_status','latency_ms','error')},
                    'returned_items':len((a.get('response') or {}).get('msgArray',[]))})
    for x in report['securities']:
        key=x['ex']+':'+x['code'];obs=series[x['ex'],x['code']]
        for kind in ('pre','close'):
            ev=x[kind+'_pair_evidence']
            no_trade=any(o.get('v')=='0' and not o.get('trade_t') and not o.get('trade_z') and not o.get('error') for o in obs if o.get('phase','').startswith(kind+'_reference'))
            x[kind+'_diagnosis']='NO_ACTUAL_TRADE_IN_SAVED_REFERENCE' if no_trade and not ev['converged'] else ev['reason'] or 'CONVERGED_RESEARCH'
        if key in missing:
            b=next(r for r in b_rows if key in r.get('missing',[]))
            symbol_rows.append({'symbol':key,'name':x['name'],'B_batch':b['batch_no'],
                'transport_class':'HTTP_TIMEOUT' if any(any(t in (a.get('error') or '').lower() for t in ('timeout','timed out')) for a in b.get('attempts',[])) else 'UNKNOWN',
                'B_terminal_reason':b.get('error'),'included_in_C':any(o['phase']=='close_reference_C' for o in obs),
                'close_research_class':x['P_close_convergence_type'],'pre_diagnosis':x['pre_diagnosis'],
                'close_diagnosis':x['close_diagnosis'],'formal_validated':False})
    unknown=[{'symbol':x['ex']+':'+x['code'],'name':x['name'],'pre':x['pre_diagnosis'],'close':x['close_diagnosis'],
              'research_close':x['P_close_convergence_type'],'formal_validated':False} for x in report['securities'] if not x['research_calculable']]
    write_csv(output/'batch-report.csv',batch_rows);write_csv(output/'attempt-report.csv',attempt_rows)
    write_csv(output/'missing-50.csv',symbol_rows);write_csv(output/'unknown-prices.csv',unknown)
    # Flat, allowlisted extraction into an isolated temporary directory only.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            for name in z.namelist():
                path=Path(name)
                if path.parent.as_posix() in ('.','results') and path.suffix in ('.json','.jsonl','.csv'):
                    dest=p/path.name;data=z.read(name)
                    if dest.exists() and dest.read_bytes()!=data:raise ValueError('CONFLICTING_ARCHIVE_FILES')
                    dest.write_bytes(data)
        fixed=capture_completion.classify(p,summary)
        published=candidate_publication.build(p,date,summary['artifact'].removeprefix('mis-probe-'),'ISOLATED_REPLAY',digest)
    (output/'research-preview.json').write_text(json.dumps(published,ensure_ascii=False,indent=2))
    metrics={'trade_date':date,'artifact_sha256':digest,'input_unchanged':hashlib.sha256(archive).hexdigest()==digest,
        'original_capture_outcome':summary.get('capture_outcome'),'isolated_reclassification':fixed['capture_outcome'],
        'raw_B_returned_before_and_after':summary['snapshots']['close_reference_B']['success_count'],
        'universe':len(universe),'B_missing':len(missing),'C_includes_all_B_missing':all(x['included_in_C'] for x in symbol_rows),
        'B_missing_research_classifications':dict(collections.Counter(x['close_research_class'] for x in symbol_rows)),
        'research_calculable_before_and_after':report['research_calculable_count'],
        'research_candidate_count_before_and_after':published['candidate_count'],
        'pre_converged':report['p_before_converged_count'],'strict_AB_close_converged':report['p_close_converged_count'],
        'research_close_classifications':dict(collections.Counter(x['P_close_convergence_type'] for x in report['securities'])),
        'unknown_count':len(unknown),'formal_verified_count':0,'formal_signal_count':0,
        'stale_batches':report['stale_batch_count'],'server_regressions':report['server_regression_response_count'],
        'note':'Reclassification is not recovery of historical B. No new observation or official value was fabricated.'}
    (output/'replay-summary.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
    return metrics


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('artifact',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();before=args.artifact.read_bytes();result=audit(before,args.output)
    if args.artifact.read_bytes()!=before:raise AssertionError('INPUT_MUTATED')
    print(json.dumps(result,ensure_ascii=False,indent=2))
