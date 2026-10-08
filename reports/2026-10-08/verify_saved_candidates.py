#!/usr/bin/env python3
"""Offline audit: saved capture + saved official raw tables, never network/MIS.

Uses original immutable raw observations to replay selection, then independently
recalculates every research-calculable return with Decimal. Official comparisons
read raw same-date tables, NOT formal MATCH flags (which omit BC-only closes).
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import capture_completion
import convergence
import freshness
import official_quotes
import official_retry
import probe


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def verify(capture_zip,capture,official,output,code_sha):
    protected={p:sha(p) for parent in (capture,official) for p in parent.iterdir() if p.is_file()}
    zip_before=sha(capture_zip)
    summary,universe,snapshots,probes=official_retry.load_capture(capture_zip.read_bytes())
    date=summary['trade_date']
    assert date=='2026-10-08'
    validation=load(official/'validation_summary.json')
    assert validation['source_capture_run_id']=='37730234383'
    assert validation['source_capture_artifact_id']==11530906396
    assert validation['status']=='SAME_DATE_COMPARISON_ONLY'
    markets={};source_info=[]
    for ex in ('tse','otc'):
        path=official/f'official_close_{ex}.json'
        raw=load(path);quotes,state=official_quotes.parse_quotes(ex,date,raw)
        assert state=='AVAILABLE_SAME_DATE'
        markets[ex]=quotes
        source_info.append({'ex':ex,'file':path.name,'url':official_quotes.quote_url(ex,date),
                            'sha256':sha(path),'response_date':raw['date'],'status':state,'row_count':len(quotes)})
    provenance={'trade_date':date,'verified_at':probe.iso(),
        'capture_run_id':37730234383,'capture_artifact_id':11530906396,
        'capture_artifact_name':'mis-probe-37730234383','capture_archive_sha256':zip_before,
        'official_validation_run_id':37742790398,'official_validation_artifact_id':11534034875,
        'official_validation_checked_at':validation['checked_at'],
        'research_candidate_version':'DUAL_SNAPSHOT_RESEARCH_V1 + live close hierarchy (2026-10-08)',
        'capture_commit_sha':'2dd62b249a181d7045c957f0c33501cc574723cd',
        'verification_code_commit_sha':code_sha,'commit_sha':code_sha,
        'data_sources':source_info,'status':'RESEARCH_ONLY','validated':False}
    replay=convergence.build_report(date,snapshots,probes,universe,{'checks':[]})
    original=load(capture/'research_candidates.json')
    replay_candidates=convergence.research_candidates(replay)
    assert replay_candidates==original, 'Saved candidate output differs from immutable replay'
    securities=replay['securities'];by_key={(s['ex'],s['code']):s for s in securities}
    assert len(securities)==len(universe)==1968
    generated=original['candidates'];keys=[(s['ex'],s['code']) for s in generated]
    assert len(set(keys))==len(keys), 'Duplicate candidate'
    calculated={}
    for s in securities:
        if s['research_calculable']:
            assert s['P_close_convergence_type'] in ('AB_converged','AC_converged','BC_converged','A_1330_fresh_candidate')
            assert s['pre_pair_evidence']['converged']
            before=Decimal(s['p_before']);close=Decimal(s['research_p_close'])
            assert before>0 and close>0
            value=close/before-1
            if abs(value)>=Decimal('.03'):calculated[(s['ex'],s['code'])]=value
    assert set(calculated)==set(keys),'Missed or false ±3% candidate'
    rows=[]
    for saved in generated:
        s=by_key[(saved['ex'],saved['code'])]
        before,close=Decimal(saved['P_before']),Decimal(saved['P_close'])
        value=close/before-1
        assert value==Decimal(saved['tail_return'])==calculated[(saved['ex'],saved['code'])]
        assert saved['validated'] is False and saved['confidence_level']=='HIGH_RESEARCH'
        assert saved['P_before_trade_time']<'13:25:00'
        pre=saved['pre_pair_evidence'];close_e=saved['close_research_evidence']
        assert Decimal(pre['A']['trade_z'])==before==Decimal(pre['B']['trade_z'])
        assert pre['A']['trade_t']==pre['B']['trade_t']==saved['P_before_trade_time']
        pair=close_e['pair']
        assert len(pair)==2
        assert all(Decimal(e['trade_z'])==close and e['trade_t']==saved['P_close_trade_time'] for e in pair)
        assert pair[1]['server_time']>pair[0]['server_time']
        assert pair[1]['received_at']>pair[0]['received_at']
        kind=saved['P_close_convergence_type'];letters=kind.split('_')[0]
        assert [e['phase'] for e in pair]==['close_reference_'+letters[0],'close_reference_'+letters[1]]
        raw_matches=[]
        for e in (pre['A'],pre['B'],*pair):
            found=[]
            for snapshot in snapshots:
                for record in snapshot['records']:
                    if record.get('phase')!=e['phase'] or record.get('requested_at')!=e['requested_at'] or record.get('received_at')!=e['received_at']:continue
                    for item in (record.get('response') or {}).get('msgArray',[]):
                        if (item.get('ex'),item.get('c'))==(saved['ex'],saved['code']):
                            trade=item.get('trade') or {}
                            if trade.get('t')==e['trade_t'] and Decimal(str(trade.get('z')))==Decimal(e['trade_z']):
                                assert item['d']=='20261008'
                                assert record['http_status']==200 and not record.get('error')
                                found.append({'phase':e['phase'],'request_started_at':record['requested_at'],
                                    'received_at':record['received_at'],'trade':trade,
                                    'queryTime':record['response'].get('queryTime'),'cachedAlive':record['response'].get('cachedAlive'),
                                    'total_v':item.get('v'),'source':'nested trade.z, not top-level simulation z'})
            assert found,'Selected evidence absent from saved raw'
            raw_matches.append(found[0])
        off=markets[saved['ex']].get(saved['code'],{})
        official_price=freshness.decimal_value(off.get('official_close'))
        result='UNAVAILABLE' if official_price is None else 'MATCH' if close==official_price else 'MISMATCH'
        rows.append({**{k:saved[k] for k in ('code','name','market','P_before','P_before_trade_time','P_before_convergence_type',
            'P_close','P_close_trade_time','P_close_convergence_type','confidence_level')},
            'official_close':str(official_price) if official_price is not None else None,
            'tail_return':str(value),'tail_return_pct':str(value*100),
            'official_comparison':result,'difference':str(close-official_price) if official_price is not None else None,
            'threshold_passed':abs(value)>=Decimal('.03'),'pre_1325_trade_candidate':True,
            'close_trade_classification':'DELAYED_TRADE_CONFIRMED_TWO_FRESH_OBSERVATIONS' if saved['P_close_trade_time']>'13:30:00' else 'NORMAL_1330_TRADE',
            'source_evidence':raw_matches,'official_row':off.get('official_row'),
            **provenance})
    counts=Counter(r['official_comparison'] for r in rows)
    unknown=[{'code':s['code'],'name':s['name'],'market':s['market'],'classification':'UNVERIFIED / UNKNOWN',
              'pre_reason':s['pre_pair_evidence'].get('reason'),
              'close_reason':s['close_research_evidence'].get('reason'),
              'P_before_converged':s['pre_pair_evidence']['converged'],
              'P_close_convergence_type':s['P_close_convergence_type']} for s in securities if not s['research_calculable']]
    assert len(unknown)==25
    completion=capture_completion.classify(capture,summary)
    assert completion['capture_outcome']=='CAPTURE_PARTIAL' and completion['exit_code']==0
    audit={**provenance,'tradable_universe':1968,'research_calculable':sum(s['research_calculable'] for s in securities),
        'uncalculable_count':len(unknown),'uncalculable_symbols':unknown,
        'candidate_count':len(rows),'official_MATCH':counts['MATCH'],'official_MISMATCH':counts['MISMATCH'],
        'official_UNAVAILABLE':counts['UNAVAILABLE'],'missed_candidate_count':0,'duplicate_candidate_count':0,
        'false_threshold_candidate_count':0,'unresolved_in_candidates_count':0,
        'capture_outcome_replay':completion['capture_outcome'],'capture_exit_code_after_fix':completion['exit_code'],
        'formal_official_comparison':{k:validation[k] for k in ('matches','mismatches','unavailable')},
        'research_P_close_counts':load(capture/'live_research_summary.json')['P_close'],
        'artifact_unchanged':True,
        'limitations':'P_before is converged MIS evidence, not independent official last-pre-13:25 validation. Unknown stocks cannot be classified as missed ±3% candidates. All candidates remain RESEARCH_ONLY, validated=false.'}
    assert zip_before==sha(capture_zip)
    assert all(sha(p)==value for p,value in protected.items())
    output.mkdir(parents=True,exist_ok=True)
    write(output/'candidate_official_verification.json',{'provenance':provenance,'candidates':rows})
    write(output/'candidate_verification_summary.json',audit)
    write(output/'capture_completion_replay.json',{'provenance':provenance,'completion':completion})
    fields=[k for k in rows[0] if k not in ('source_evidence','official_row','data_sources')]
    with (output/'candidate_official_verification.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in audit.items() if k not in ('uncalculable_symbols','data_sources')},ensure_ascii=False,indent=2))
    return audit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture-zip',type=Path,required=True)
    p.add_argument('--capture-dir',type=Path,required=True);p.add_argument('--official-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--code-sha',required=True)
    a=p.parse_args();verify(a.capture_zip,a.capture_dir,a.official_dir,a.output,a.code_sha)
