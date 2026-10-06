"""Offline-only replay of saved pre references; never sends network requests."""
import argparse
import csv
import hashlib
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

import convergence as c
import freshness as f
import official_retry

CATEGORIES = ('stale_cache', 'server_time_regression', 'inconsistent_trade_state',
              'no_trade_or_sparse_trade', 'missing_trade_fields',
              'freshness_rule_too_strict', 'other', 'unknown')


def stats(values):
    values = sorted(float(x) for x in values if x is not None)
    return {'count': len(values), 'median': statistics.median(values) if values else None,
            'p95': values[max(0, (len(values)*95+99)//100-1)] if values else None,
            'min': min(values) if values else None, 'max': max(values) if values else None}


def shadow_pair(series, date, rule):
    identity = {'A': lambda r: (r.get('trade_t'), f.decimal_value(r.get('trade_z')), f.decimal_value(r.get('v'))),
                'B': lambda r: (r.get('trade_t'), f.decimal_value(r.get('trade_z'))),
                'C': lambda r: (r.get('trade_t'), f.decimal_value(r.get('trade_z')), f.decimal_value(r.get('trade_v')))}[rule]
    original_rejection = c.rejection
    def reject(row, day, kind):
        reason = original_rejection(row, day, kind)
        if not reason and rule == 'C' and f.decimal_value(row.get('trade_v')) is None:
            return 'MISSING_TRADE_V'
        return reason
    with patch.object(f, 'identity', identity), patch.object(c, 'rejection', reject):
        return c.pair(series, date, 'pre')


def analyze(archive, output, official_path=None):
    output.mkdir(parents=True, exist_ok=True)
    raw = archive.read_bytes()
    summary, universe, snapshots, probes = official_retry.load_capture(raw)
    date = summary['trade_date']
    series = c.grouped(snapshots, date)
    pre = {key: sorted([r for r in rows if r['phase'] in ('pre_reference_A', 'pre_reference_B', 'pre_targeted_retry')],
                       key=lambda r:r.get('received_at') or '') for key, rows in series.items()}
    baseline = c.build_report(date, snapshots, probes, universe, {'checks': []})
    evidence = {(s['ex'],s['code']):s for s in baseline['securities']}
    official = json.loads(official_path.read_text()) if official_path else {}
    off = {(s['ex'],s['code']):s for s in official.get('checks',[])}
    retry_times = sorted({r['planned_at'] for rows in pre.values() for r in rows if r['phase']=='pre_targeted_retry'})
    retry_round = {stamp:i+1 for i,stamp in enumerate(retry_times)}
    shadow = {rule:{key:shadow_pair(rows,date,rule) for key,rows in pre.items()} for rule in ('A','B','C')}
    unresolved = []
    flat = []
    for symbol in universe:
        key = symbol['ex'],symbol['code'];ev=evidence[key]['pre_pair_evidence']
        if ev['converged']:continue
        rows=pre.get(key,[]);fresh=[r for r in rows if c.rejection(r,date,'pre') is None]
        reason=ev['reason'];official_row=off.get(key,{})
        category = 'unknown'
        if reason=='server_time_regression':category='server_time_regression'
        elif reason=='stale_cache':category='stale_cache'
        elif reason=='no_trade_or_incomplete_identity':
            category='no_trade_or_sparse_trade' if f.decimal_value(official_row.get('official_volume_shares'))==0 else 'missing_trade_fields'
        elif reason in ('not_converged','PROBE_CONFLICT'):
            changed=any((a['trade_t'],a['trade_z'])!=(b['trade_t'],b['trade_z']) for a,b in zip(fresh,fresh[1:]))
            if changed:category='inconsistent_trade_state'
            elif shadow['B'][key]['converged'] and not shadow['A'][key]['converged']:category='freshness_rule_too_strict'
        timeline=[]
        for r in rows:
            fields={k:r.get(k) for k in ('phase','requested_at','observed_at','server_time','server_sys_date','server_sys_time',
                       'query_time','cached_alive','server_age_at_receive_ms','trade_t','trade_z','trade_v','v','error','batch_no')}
            fields.update(retry_round=retry_round.get(r['planned_at']) if r['phase']=='pre_targeted_retry' else None,
                          freshness_classification=c.rejection(r,date,'pre') or 'FRESH_ELIGIBLE')
            timeline.append(fields);flat.append({**symbol,**{k:v for k,v in fields.items() if k!='query_time'}})
        valid_times=[r['trade_t'] for r in rows if c.clock(r.get('trade_t'))]
        bridges=[(a,b) for i,a in enumerate(fresh) for b in fresh[i+1:]
                 if a['server_time']<b['server_time'] and f.identity(a)==f.identity(b)]
        prices={f.decimal_value(r['trade_z']) for r in rows if f.decimal_value(r['trade_z']) is not None}
        volumes=[f.decimal_value(r.get('v')) for r in rows if f.decimal_value(r.get('v')) is not None]
        unresolved.append({**symbol,'category':category,'terminal_reason':reason,'validated':False,
            'reason_explanation': {'stale_cache':'Saved pair.reason retains the last rejection. Stale replies reset pending evidence; a later single fresh reply cannot restore a pair. '+
                  ('Two distinct fresh equal observations exist but have stale replies between them; accepting this bridge is an unvalidated shadow.' if bridges else 'No qualifying fresh equal pair is proven.'),
               'missing_trade_fields':'Freshness alone is insufficient: nested time/price or total volume is missing/invalid.',
               'no_trade_or_sparse_trade':'Official daily share volume is zero; no P_before trade can be proven.'}.get(category,'No independently proven terminal cause.'),
            'official_volume_shares':official_row.get('official_volume_shares'),'official_close':official_row.get('official_close'),
            'all_nonmissing_prices_equal':len(prices)==1,'oldest_trade_time':min(valid_times) if valid_times else None,
            'latest_trade_time':max(valid_times) if valid_times else None,'all_trades_before_1300':bool(valid_times) and max(valid_times)<'13:00:00',
            'min_reported_v':str(min(volumes)) if volumes else None,'max_reported_v':str(max(volumes)) if volumes else None,
            'sparse_trade_indicator':bool(volumes) and max(volumes)<=10,'sparse_threshold_note':'v <= 10 is a descriptive indicator, not verified no-trade truth or a gate.',
            'fresh_eligible_count':len(fresh),'distinct_fresh_server_times':len({r['server_time'] for r in fresh}),
            'nonconsecutive_fresh_equal_shadow':bool(bridges),
            'shadow_A':shadow['A'][key]['converged'],'shadow_B':shadow['B'][key]['converged'],'shadow_C':shadow['C'][key]['converged'],
            'timeline':timeline})
    market_stats={}
    for ex,market in (('tse','TWSE'),('otc','TPEx')):
        keys=[(s['ex'],s['code']) for s in universe if s['ex']==ex]
        observations=[r for key in keys for r in pre.get(key,[])]
        records={(r['phase'],r['batch_no'],r['requested_at'],r['received_at']):r for r in observations}
        failed_ab=[k for k in keys if not c.pair([r for r in pre.get(k,[]) if r['phase']!='pre_targeted_retry'],date,'pre')['converged']]
        recovered=[k for k in failed_ab if evidence[k]['pre_pair_evidence']['converged']]
        phase_stats={}
        for phase in ('pre_reference_A','pre_reference_B','pre_targeted_retry'):
            batches=[r for r in records.values() if r['phase']==phase]
            phase_stats[phase]={'server_age_ms':stats(r.get('server_age_at_receive_ms') for r in batches),
                                'cachedAlive':stats(f.decimal_value(r.get('cached_alive')) for r in batches)}
        transitions=Counter()
        for key in keys:
            for a,b in zip(pre[key],pre[key][1:]):
                ta,tb=a.get('trade_t'),b.get('trade_t')
                if ta==tb:transitions['unchanged']+=1
                elif not c.clock(ta) or not c.clock(tb):transitions['missing_field_transition']+=1
                elif tb>ta:transitions['advanced']+=1
                else:transitions['regressed']+=1
        market_stats[market]={'universe':len(keys),'unresolved':sum(not evidence[k]['pre_pair_evidence']['converged'] for k in keys),
            'unresolved_rate':sum(not evidence[k]['pre_pair_evidence']['converged'] for k in keys)/len(keys),
            'metadata_scope':'Distinct HTTP batches involving this market; mixed-market batches may belong to both. cachedAlive unit unverified.',
            'query_time_age_ms':stats(r.get('server_age_at_receive_ms') for r in records.values()),
            'cachedAlive_reported':stats(f.decimal_value(r.get('cached_alive')) for r in records.values()),
            'by_phase':phase_stats,'trade_time_transition_pattern':dict(transitions),
            'raw_server_time_regression_events':sum(sum(b.get('server_time','')<a.get('server_time','')
                for a,b in zip(pre[k],pre[k][1:]) if a.get('server_time') and b.get('server_time')) for k in keys),
            'stale_symbol_observations':sum(c.rejection(r,date,'pre')=='stale_cache' for r in observations),
            'server_regression_symbols':sum(any(x['reason']=='server_time_regression' for x in evidence[k]['pre_pair_evidence']['rejections']) for k in keys),
            'server_regression_events':sum(sum(x['reason']=='server_time_regression' for x in evidence[k]['pre_pair_evidence']['rejections']) for k in keys),
            'trade_time_changed_symbols':sum(any(a.get('trade_t')!=b.get('trade_t') for a,b in zip(pre[k],pre[k][1:])) for k in keys),
            'v_changed_symbols':sum(any(a.get('v')!=b.get('v') for a,b in zip(pre[k],pre[k][1:])) for k in keys),
            'original_AB_unresolved':len(failed_ab),'recovered_by_targeted_retry':len(recovered),
            'targeted_retry_success_rate':len(recovered)/len(failed_ab) if failed_ab else None}
    comparisons=[]
    for rule in ('A','B','C'):
        differences=set()
        for key,rows in pre.items():
            valid=[r for r in rows if c.rejection(r,date,'pre') is None]
            for a,b in zip(valid,valid[1:]):
                if a['server_time']==b['server_time']:continue
                if (a['trade_t'],f.decimal_value(a['trade_z']))==(b['trade_t'],f.decimal_value(b['trade_z'])):
                    if rule=='A' and f.decimal_value(a.get('v'))!=f.decimal_value(b.get('v')):differences.add(key)
                    if rule=='C' and f.decimal_value(a.get('trade_v'))!=f.decimal_value(b.get('trade_v')):differences.add(key)
        converged=sum(shadow[rule][(s['ex'],s['code'])]['converged'] for s in universe)
        comparisons.append({'rule':rule,'identity':{'A':'trade.t + trade.z + v','B':'trade.t + trade.z','C':'trade.t + trade.z + trade.v'}[rule],
            'converged_count':converged,'unresolved_count':len(universe)-converged,
            'rescued_from_74':sum(s['shadow_'+rule] for s in unresolved),'false_conflict_count':len(differences),
            'false_conflict_definition':'Potential volume-only disagreement among fresh distinct observations with equal trade.t/trade.z; NOT proven false by independent trade truth.',
            'proven_false_conflict_count':None})
    result={'trade_date':date,'source_run_id':'37416416998','source_artifact_id':11391549138,'source_sha256':hashlib.sha256(raw).hexdigest(),
        'categories':{k:sum(s['category']==k for s in unresolved) for k in CATEGORIES},'unresolved_count':len(unresolved),'markets':market_stats,
        'shadow_comparison':comparisons,'unchanged_price_unresolved':sum(s['all_nonmissing_prices_equal'] for s in unresolved),
        'sparse_indicator_unresolved':sum(s['sparse_trade_indicator'] for s in unresolved),'all_trades_before_1300_unresolved':sum(s['all_trades_before_1300'] for s in unresolved),
        'nonconsecutive_fresh_equal_shadow_rescued':sum(s['nonconsecutive_fresh_equal_shadow'] for s in unresolved),
        'network_requests':0,'validated':False,'note':'Single-day mixed-batch observational comparison; does not establish intrinsic TWSE/TPEx cache differences.',
        'symbols':unresolved}
    (output/'unresolved_analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (output/'summary.json').write_text(json.dumps({k:v for k,v in result.items() if k!='symbols'},ensure_ascii=False,indent=2))
    columns=list(flat[0]) if flat else ['code']
    with (output/'unresolved_timeline.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=columns);writer.writeheader();writer.writerows(flat)
    lines=[f'# {date} 74 檔 P_before 未收斂離線研究','', '所有結果維持研究用途；cachedAlive 單位未驗證。false conflict 僅指可疑的量欄位衝突，未有獨立成交真值證明。','']
    lines.extend(f'- {category}: {count}' for category,count in result['categories'].items())
    for s in unresolved:
        lines += ['',f'## {s["code"]} {s["name"]} / {s["market"]}',f'分類：{s["category"]}；最後原因：{s["terminal_reason"]}。有效 fresh 次數：{s["fresh_eligible_count"]}。',
            '|phase / round|observed_at|sysTime|cachedAlive|trade.t|trade.z|trade.v|v|classification|','|---|---|---|---|---|---|---|---|---|']
        for r in s['timeline']:
            lines.append('|'+ '|'.join(str(x) if x is not None else '—' for x in [r['phase']+('/'+str(r['retry_round']) if r['retry_round'] else ''),r['observed_at'],r['server_sys_time'],r['cached_alive'],r['trade_t'],r['trade_z'],r['trade_v'],r['v'],r['freshness_classification']])+'|')
    (output/'unresolved_timeline.md').write_text('\n'.join(lines)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--official',type=Path)
    args=parser.parse_args();result=analyze(args.archive,args.output,args.official)
    print(json.dumps({k:v for k,v in result.items() if k!='symbols'},ensure_ascii=False))
