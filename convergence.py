"""Dual MIS observations for research. Clock freshness is not final-trade truth."""
from collections import defaultdict
import csv
import json
import re

import freshness as f
import close_research

VERSION = 'DUAL_SNAPSHOT_RESEARCH_V1'
REFERENCE_TIMES = {
    'pre_reference_A': '13:27:00', 'pre_reference_B': '13:28:15',
    'close_reference_A': '13:32:30', 'close_reference_B': '13:33:20',
}
DEADLINES = {'pre': '13:29:30', 'close': '13:35:00'}
MAX_AGE_MS = 15000  # Research threshold, not a proven MIS cache guarantee.
PRE_C_START_DATE = '2026-10-07'
PRE_C_TIME = '13:29:00'


def reference_times(date):
    if date < PRE_C_START_DATE:
        return dict(REFERENCE_TIMES)
    return {**{k:v for k,v in REFERENCE_TIMES.items() if k.startswith('pre_')},
            'pre_reference_C': PRE_C_TIME,
            **{k:v for k,v in REFERENCE_TIMES.items() if k.startswith('close_')},
            **({'close_reference_C':close_research.C_TIME} if date>=close_research.START_DATE else {})}


def plan(date):
    return {'version': VERSION, 'trade_date': date, 'reference_times': reference_times(date),
            'targeted_retry_deadlines': DEADLINES, 'batch_size': 50, 'concurrency': 5,
            'max_receive_server_age_ms': MAX_AGE_MS, 'cachedAlive_unit': 'UNVERIFIED',
            'validated': False, 'note': 'Plan only. Absent reference phases are NOT_SAMPLED.'}


def clock(value):
    return isinstance(value, str) and bool(re.fullmatch(r'\d{2}:\d{2}:\d{2}', value))


def rejection(row, date, kind):
    if row.get('error') or row.get('http_status') != 200:
        return row.get('error') or 'HTTP_ERROR'
    if row.get('duplicate'):
        return 'DUPLICATE_SYMBOL'
    if not f.fresh_candidate(row, date, MAX_AGE_MS):
        return 'stale_cache' if row.get('server_time') else 'unknown_server_time'
    server = f.parsed_time(row.get('server_time'))
    received = f.parsed_time(row.get('received_at'))
    requested = f.parsed_time(row.get('requested_at'))
    planned = f.parsed_time(row.get('planned_at'))
    if not received or received.date().isoformat() != date or not requested or requested.date().isoformat() != date:
        return 'WRONG_OBSERVATION_DATE'
    if not planned or planned.date().isoformat() != date or requested < planned:
        return 'INVALID_REFERENCE_SCHEDULE'
    if received.strftime('%H:%M:%S.%f') > DEADLINES[kind]+'.000000':
        return 'AFTER_REFERENCE_DEADLINE'
    minimum = '13:25:00' if kind == 'pre' else (
        '13:30:00' if row['phase'] == 'close_reference_A' else '13:33:00')
    if server.strftime('%H:%M:%S') < minimum:
        return 'stale_cache'
    trade_time = row.get('trade_t')
    price, volume = f.decimal_value(row.get('trade_z')), f.decimal_value(row.get('v'))
    if not clock(trade_time) or price is None or price <= 0 or volume is None or volume < 0:
        return 'no_trade_or_incomplete_identity'
    if not ('09:00:00' <= trade_time <= server.strftime('%H:%M:%S')):
        return 'INVALID_TRADE_TIME'
    if kind == 'pre' and trade_time >= '13:25:00':
        return 'NOT_PRE_1325_TRADE'
    if kind == 'close' and not (trade_time < '13:25:00' or trade_time == '13:30:00'
                                 or '13:33:00' <= trade_time <= '13:33:15'):
        return 'UNEXPLAINED_CLOSE_TRADE_TIME'
    return None


def pair(series, date, kind):
    """Only reference/retry rows count. A rejection breaks the stable sequence.

    The original A and B attempts must exist. Retry pairs replace failed reference
    evidence explicitly; probe ticks can contradict a pair but never substitute A/B.
    A server timestamp regression does not overwrite the high-water mark.
    """
    phases = (kind+'_reference_A', kind+'_reference_B', kind+'_targeted_retry')
    rows = sorted((r for r in series if r.get('phase') in phases),
                  key=lambda r: r.get('received_at') or r.get('planned_at') or '')
    original = {p: next((r for r in rows if r['phase'] == p), None) for p in phases[:2]}
    result = {'status': 'unknown', 'converged': False, 'validated': False,
              'A': None, 'B': None, 'original_A': original[phases[0]],
              'original_B': original[phases[1]], 'reason': 'not_converged',
              'rejections': [], 'delayed_transition_candidate': False}
    if not all(original.values()):
        return dict(result, reason='NOT_SAMPLED')
    for p, row in original.items():
        # A payload relabelled to a reference at an earlier time is not evidence.
        planned = f.parsed_time(row.get('planned_at'))
        if not planned or planned.date().isoformat() != date or planned.strftime('%H:%M:%S') != REFERENCE_TIMES[p]:
            return dict(result, reason='INVALID_REFERENCE_SCHEDULE')
    pending = None
    high_server = None
    for row in rows:
        server = f.parsed_time(row.get('server_time'))
        reason = rejection(row, date, kind)
        if server and high_server and server < high_server:
            reason = 'server_time_regression'
        if server and row.get('server_clock_plausible') and not reason:
            high_server = max(high_server, server) if high_server else server
        if reason:
            result['rejections'].append({'observed_at': row.get('received_at'),
                                         'server_time': row.get('server_time'), 'reason': reason,
                                         'phase': row.get('phase'), 'batch_no': row.get('batch_no')})
            pending = None
            result.update(converged=False, A=None, B=None, reason=reason)
            continue
        if pending:
            same = f.identity(row) == f.identity(pending)
            distinct = row['server_time'] > pending['server_time']
            if kind == 'close' and not same and '13:33:00' <= row['trade_t'] <= '13:33:15':
                result['delayed_transition_candidate'] = True
            if same and distinct:
                result.update(converged=True, A=pending, B=row, reason=None)
            else:
                result.update(converged=False, A=None, B=None,
                              reason='not_converged' if distinct else 'same_server_observation')
        pending = row
    if result['converged']:
        # At least the B phase must be past 13:33; two A responses cannot certify a close.
        if kind == 'close' and result['B']['phase'] == 'close_reference_A':
            return dict(result, converged=False, reason='NO_POST_1333_OBSERVATION')
        result['status'] = 'p_before_converged_candidate' if kind == 'pre' else 'p_close_converged_candidate'
    return result


def pre_with_c(series, date):
    """Keep original A/B+retry unchanged; C is optional research evidence only.

    C pairs retain trade.t/trade.z/v identity. Relaxing v stays offline shadow.
    A stale intervening B may be bridged, but fresh contradictions/regressions
    between an adopted A/B and C block adoption.
    """
    original = pair(series, date, 'pre')
    result = dict(original, original_ab_converged=original['converged'],
                  reference_classification='AB_converged_candidate' if original['converged'] else 'unresolved',
                  original_C=None, c_rejection=None)
    if date < PRE_C_START_DATE:
        return result
    refs = {p:next((r for r in series if r.get('phase')==p),None)
            for p in ('pre_reference_A','pre_reference_B','pre_reference_C')}
    third = refs['pre_reference_C'];result['original_C'] = third
    if not third:
        result['c_rejection']='NOT_SAMPLED';return result
    planned=f.parsed_time(third.get('planned_at'))
    reason = rejection(third,date,'pre')
    if not planned or planned.date().isoformat()!=date or planned.strftime('%H:%M:%S')!=PRE_C_TIME:
        reason='INVALID_REFERENCE_SCHEDULE'
    result['c_rejection']=reason
    if reason:
        return result  # A/B success cannot be erased by optional C.
    fresh = {p:r for p,r in refs.items() if r and not rejection(r,date,'pre')
             and f.parsed_time(r.get('planned_at'))
             and f.parsed_time(r['planned_at']).strftime('%H:%M:%S')==reference_times(date)[p]}
    abc = len(fresh)==3 and len({f.identity(r) for r in fresh.values()})==1 and (
            fresh['pre_reference_A']['server_time'] < fresh['pre_reference_B']['server_time'] < third['server_time']) and (
            not original['converged'] or f.identity(original['B'])==f.identity(third))
    if abc:
        result['reference_classification']='ABC_converged_candidate'
    if original['converged']:
        return result  # C never substitutes the already accepted original A/B.
    # No original A or B instant may be fabricated.
    if not refs['pre_reference_A'] or not refs['pre_reference_B']:
        return result
    for phase, label in (('pre_reference_B','BC_converged_candidate'),('pre_reference_A','AC_converged_candidate')):
        prior=fresh.get(phase)
        if not prior or prior['server_time']>=third['server_time'] or f.identity(prior)!=f.identity(third):
            continue
        between=[r for r in series if prior['received_at']<r.get('received_at','')<=third['received_at']
                 and r.get('phase') in ('pre_reference_A','pre_reference_B','pre_reference_C','pre_targeted_retry')
                 and not rejection(r,date,'pre')]
        if any(r['server_time']<prior['server_time'] or f.identity(r)!=f.identity(prior) for r in between):
            result['c_rejection']='FRESH_CONTRADICTION_OR_REGRESSION';continue
        after=[r for r in series if r.get('received_at','')>third['received_at']
               and r.get('phase')=='pre_targeted_retry' and not rejection(r,date,'pre')]
        if any(r['server_time']<third['server_time'] or f.identity(r)!=f.identity(third) for r in after):
            result['c_rejection']='LATER_FRESH_CONTRADICTION_OR_REGRESSION';continue
        result.update(status='p_before_converged_candidate',converged=True,A=prior,B=third,reason=None,
                      reference_classification='ABC_converged_candidate' if abc else label,validated=False)
        return result
    return result


def grouped(snapshots, date):
    by_symbol = defaultdict(list)
    for snap in snapshots:
        for record in snap['records']:
            rows = f.observations([record], date)
            duplicates = set(record.get('duplicate', []))
            for row in rows:
                row['batch_no'] = record.get('batch_no')
                row['duplicate'] = row['ex']+':'+row['code'] in duplicates
                by_symbol[(row['ex'], row['code'])].append(row)
    return by_symbol


def unresolved(date, snapshots, universe, kind, probes=()):
    series = grouped(snapshots, date)
    samples = defaultdict(list)
    for row in f.observations(probes, date):
        samples[(row['ex'], row['code'])].append(row)
    affected = []
    for symbol in universe:
        key = (symbol['ex'], symbol['code'])
        evidence = pre_with_c(series[key], date) if kind=='pre' else pair(series[key], date, kind)
        if not evidence['converged'] or probe_comparison(samples[key], evidence, date, kind)['status'] == 'PROBE_CONFLICT':
            affected.append(symbol)
    return affected


def compact(row):
    if not row:
        return None
    keys = ('phase', 'planned_at', 'requested_at', 'received_at', 'server_time', 'server_age_ms',
            'server_age_at_receive_ms', 'cached_alive', 'trade_t', 'trade_z', 'trade_v', 'v', 'batch_no', 'error')
    return {k: row.get(k) for k in keys}


def probe_comparison(series, evidence, date, kind):
    if not series:
        return {'status': 'NOT_SAMPLED', 'validated': False}
    if not evidence['converged']:
        return {'status': 'PAIR_UNKNOWN', 'validated': False}
    row = evidence['B']
    if kind == 'pre':
        usable = [r for r in series if f.pre_eligible(r, date) and f.decimal_value(r.get('v')) is not None]
    else:
        usable = [r for r in series if f.fresh_candidate(r, date) and clock(r.get('trade_t'))
                  and f.parsed_time(r.get('server_time')).strftime('%H:%M:%S') >= '13:33:00']
    if not usable:
        return {'status': 'NO_FRESH_PROBE_REFERENCE', 'validated': False}
    latest = max(usable, key=lambda r: r['received_at'])
    matches = f.identity(latest) == f.identity(row)
    return {'status': 'AGREES_WITH_LATEST_FRESH_PROBE' if matches else 'PROBE_CONFLICT',
            'probe_observed_at': latest['received_at'], 'probe_server_time': latest['server_time'],
            'probe_trade_t': latest['trade_t'], 'probe_trade_z': latest['trade_z'], 'probe_v': latest['v'],
            'validated': False}


def build_report(date, snapshots, probes, universe, official, close_research_enabled=None):
    live_research = date >= close_research.START_DATE if close_research_enabled is None else close_research_enabled
    full = grouped(snapshots, date)
    sample = defaultdict(list)
    for row in f.observations(probes, date):
        sample[(row['ex'], row['code'])].append(row)
    checks = {(r['ex'], r['code']): r for r in official.get('checks', [])}
    securities = []
    for symbol in universe:
        key = (symbol['ex'], symbol['code'])
        before, closing = pre_with_c(full[key], date), pair(full[key], date, 'close')
        original_pre = pair(full[key],date,'pre')
        original_pre_ok = original_pre['converged'] and probe_comparison(sample[key],original_pre,date,'pre')['status']!='PROBE_CONFLICT'
        pre_probe = probe_comparison(sample[key], before, date, 'pre')
        close_probe = probe_comparison(sample[key], closing, date, 'close')
        for evidence, comparison in ((before, pre_probe), (closing, close_probe)):
            if comparison['status'] == 'PROBE_CONFLICT':
                evidence.update(status='unknown', converged=False, reason='PROBE_CONFLICT')
        # Unknown prices stay null, but do not erase the timestamps of rejected
        # original observations from the CSV. Adopted pairs take precedence.
        pa, pb = (before['A'] or before['original_A'] or {}), (before['B'] or before['original_B'] or {})
        ca, cb = (closing['A'] or closing['original_A'] or {}), (closing['B'] or closing['original_B'] or {})
        pre_ok, close_ok = before['converged'], closing['converged']
        off = checks.get(key, {})
        official_price = f.decimal_value(off.get('official_close'))
        price = f.decimal_value(cb.get('trade_z')) if close_ok else None
        official_result = 'PENDING' if official_price is None else (
            'MATCH' if price is not None and price == official_price else ('MISMATCH' if price is not None else 'UNKNOWN_MIS_CLOSE'))
        t = cb.get('trade_t')
        category = ('normal_close_candidate' if t == '13:30:00' else
                    'delayed_close_candidate' if clock(t) and '13:33:00' <= t <= '13:33:15' else
                    'no_closing_new_trade_candidate' if clock(t) and t < '13:25:00' else 'unknown') if close_ok else 'unknown'
        value = {**symbol, 'p_before': pb.get('trade_z') if pre_ok else None,
                 'p_before_trade_time': pb.get('trade_t') if pre_ok else None,
                 'p_before_observed_A': pa.get('received_at'), 'p_before_observed_B': pb.get('received_at'),
                 'p_before_server_time_A': pa.get('server_time'), 'p_before_server_time_B': pb.get('server_time'),
                 'p_before_convergence_status': before['status'],
                 'pre_reference_classification': before['reference_classification'] if pre_ok else 'unresolved',
                 'original_AB_with_retry_converged':original_pre_ok,
                 'p_close': cb.get('trade_z') if close_ok else None, 'close_trade_time': t if close_ok else None,
                 'close_observed_A': ca.get('received_at'), 'close_observed_B': cb.get('received_at'),
                 'close_server_time_A': ca.get('server_time'), 'close_server_time_B': cb.get('server_time'),
                 'close_convergence_status': closing['status'], 'close_classification': category,
                 'delayed_transition_candidate': closing['delayed_transition_candidate'],
                 'official_close': off.get('official_close'), 'official_price_result': official_result,
                 'official_volume_shares':off.get('official_volume_shares'),
                 'both_converged': pre_ok and close_ok, 'research_calculable': pre_ok and close_ok and official_result != 'MISMATCH',
                 'p_before_validated': False, 'p_close_validated': False, 'both_validated': False,
                 'pre_probe_comparison': pre_probe, 'close_probe_comparison': close_probe,
                 'volume_status': 'UNVERIFIED', 'volume_evidence': f.volume_evidence(full[key]+sample[key], date)}
        value.update(p_before_A_server_time=pa.get('server_time'),p_before_B_server_time=pb.get('server_time'),
                     p_close_A_server_time=ca.get('server_time'),p_close_B_server_time=cb.get('server_time'),
                     p_close_convergence_status=('normal_close_converged_candidate' if category=='normal_close_candidate'
                         else 'delayed_close_candidate' if category=='delayed_close_candidate'
                         else 'no_closing_new_trade_converged_candidate' if category=='no_closing_new_trade_candidate'
                         else 'unknown'),
                     targeted_retry_count=sum(r.get('phase','').endswith('_targeted_retry')
                         and r.get('error')!='CAPTURE_DEADLINE_NO_REQUEST' for r in full[key]),
                     stale_seen=any(r['reason'] in ('stale_cache','server_time_regression')
                                    for ev in (before,closing) for r in ev['rejections']))
        for label, evidence in (('pre', before), ('close', closing)):
            value[label+'_pair_evidence'] = {**evidence, **{k: compact(evidence.get(k)) for k in ('A', 'B', 'original_A', 'original_B','original_C') if k in evidence}}
        if live_research:
            research = close_research.assess(full[key], date)
            research_probe = probe_comparison(sample[key],
                {'converged':bool(research['selected']), 'B':research['selected']}, date, 'close')
            if research_probe['status']=='PROBE_CONFLICT':
                research.update(classification='unresolved',confidence_level=None,p_close=None,
                                trade_time=None,converged=False,reason='PROBE_CONFLICT')
            price = f.decimal_value(research['p_close'])
            research_official = 'PENDING' if official_price is None else (
                'MATCH' if price is not None and price==official_price else
                'MISMATCH' if price is not None else 'UNKNOWN_MIS_CLOSE')
            value.update(research_p_close=research['p_close'],research_close_trade_time=research['trade_time'],
                P_close_convergence_type=research['classification'],confidence_level=research['confidence_level'],
                P_before_convergence_type=before['reference_classification'],
                close_research_evidence={**research,'selected':compact(research['selected']),
                    'pair':[compact(r) for r in research['pair']] if research['pair'] else None},
                research_official_price_result=research_official,
                research_calculable=pre_ok and research['classification'] in close_research.TYPES
                    and research_official!='MISMATCH')
        securities.append(value)
    reference_records = [r for s in snapshots for r in s['records'] if (r.get('phase') or '').startswith(('pre_reference', 'close_reference', 'pre_targeted', 'close_targeted'))]
    stale_batches = []
    regression_batches = []
    for record in reference_records:
        rows = f.observations([record], date)
        if any(rejection(r, date, 'pre' if r['phase'].startswith('pre_') else 'close') == 'stale_cache' for r in rows):
            stale_batches.append({'phase': record['phase'], 'batch_no': record.get('batch_no'), 'requested_at': record.get('requested_at')})
    for value in securities:
        for kind in ('pre', 'close'):
            for r in value[kind+'_pair_evidence']['rejections']:
                if r['reason'] == 'server_time_regression':
                    regression_batches.append((r['phase'], r['batch_no'], r['observed_at'], r['server_time']))
    targeted = [r for r in reference_records if r.get('phase', '').endswith('_targeted_retry')]
    sent_targeted = [r for r in targeted if r.get('attempts') or r.get('error') not in ('CAPTURE_DEADLINE_NO_REQUEST','REFERENCE_NOT_SAMPLED')]
    counts = {'p_before_converged_count': sum(v['p_before_convergence_status'] == 'p_before_converged_candidate' for v in securities),
              'p_close_converged_count': sum(v['close_convergence_status'] == 'p_close_converged_candidate' for v in securities),
              'both_converged_count': sum(v['both_converged'] for v in securities),
              'unknown_count':sum(not v['both_converged'] for v in securities),
              'stale_batch_count': len(stale_batches), 'server_regression_response_count': len(set(regression_batches)),
              'targeted_retry_count': len(sent_targeted),
              'targeted_http_attempt_count': sum(len(r.get('attempts',[])) for r in targeted),
              'targeted_retry_symbol_requests': sum(len(r.get('symbols', [])) for r in reference_records if r.get('phase', '').endswith('_targeted_retry')),
              'true_delayed_close_candidate_count': sum(v['close_classification'] == 'delayed_close_candidate' for v in securities),
              'delayed_transition_candidate_count': sum(v['delayed_transition_candidate'] for v in securities),
              'no_closing_new_trade_count': sum(v['close_classification'] == 'no_closing_new_trade_candidate' for v in securities),
              'research_calculable_count': sum(v['research_calculable'] for v in securities),
              'p_before_validated_count': 0, 'p_close_validated_count': 0, 'both_validated_count': 0}
    original = [{'records':[r for r in s['records'] if not r.get('phase', '').endswith('_targeted_retry')]} for s in snapshots]
    original_series = grouped(original, date)
    for kind, label in (('pre', 'p_before'), ('close', 'p_close')):
        counts[label+'_original_AB_converged_count'] = sum(pair(original_series[(s['ex'],s['code'])], date, kind)['converged'] for s in universe)
        counts[label+'_recovered_by_targeted_retry_count'] = sum(
            v['p_before_convergence_status' if kind == 'pre' else 'close_convergence_status'] == label+'_converged_candidate'
            and (v[('pre' if kind == 'pre' else 'close')+'_pair_evidence']['B'] or {}).get('phase', '').endswith('_targeted_retry')
            for v in securities)
    counts['stale_response_count']=counts['stale_batch_count']
    counts['p_before_original_AB_with_retry_converged_count'] = sum(v['original_AB_with_retry_converged'] for v in securities)
    for label in ('ABC','AB','AC','BC'):
        counts['p_before_'+label+'_converged_count']=sum(v['pre_reference_classification']==label+'_converged_candidate' for v in securities)
    counts['p_before_unresolved_count'] = sum(v['p_before_convergence_status']!='p_before_converged_candidate' for v in securities)
    for ex in ('tse','otc'):
        counts['p_before_unresolved_'+ex+'_count']=sum(v['ex']==ex and v['p_before_convergence_status']!='p_before_converged_candidate' for v in securities)
    reasons={'stale_cache':'stale_cache','server_time_regression':'server_time_regression',
             'no_trade_or_incomplete_identity':'missing_trade_fields','PROBE_CONFLICT':'inconsistent_trade_state',
             'not_converged':'unknown'}
    categories = {k:0 for k in ('stale_cache','server_time_regression','inconsistent_trade_state',
                              'no_trade_or_sparse_trade','missing_trade_fields','freshness_rule_too_strict','other','unknown')}
    for value in securities:
        if value['p_before_convergence_status']=='p_before_converged_candidate':continue
        category=reasons.get(value['pre_pair_evidence'].get('reason'),'unknown')
        if category=='missing_trade_fields' and f.decimal_value(value.get('official_volume_shares'))==0:
            category='no_trade_or_sparse_trade'
        categories[category]+=1
    counts['p_before_unresolved_categories']=categories
    if live_research:
        for label in (*close_research.TYPES,'delayed_close_candidate','unresolved'):
            counts['research_close_'+label+'_count']=sum(v['P_close_convergence_type']==label for v in securities)
    has_references = all(any(r.get('phase') == p for r in reference_records) for p in REFERENCE_TIMES)
    return {'trade_date': date, 'version': VERSION, 'status': 'RESEARCH_ONLY' if has_references else 'NOT_SAMPLED',
            'universe_count': len(universe), 'rule': plan(date), **counts, 'stale_batches': stale_batches,
            'securities': securities, 'formal_signals': 'NOT_GENERATED', 'validated': False,
            'live_close_research_enabled': live_research,
            'note': 'Dual equality is a convergence candidate, not proof of the final exchange trade. Official MATCH does not validate P_before.'}


def research_candidates(report):
    values = []
    for v in report['securities']:
        if not v['research_calculable']:
            continue
        research = report.get('live_close_research_enabled',False)
        close = v['research_p_close'] if research else v['p_close']
        change = f.decimal_value(close)/f.decimal_value(v['p_before'])-1
        if abs(change) >= f.Decimal('0.03'):
            row = ({k: v[k] for k in ('ex','code','name','market','p_before','p_before_trade_time',
                'p_close','close_trade_time','official_price_result','p_before_convergence_status','p_close_convergence_status',
                'pre_pair_evidence','close_pair_evidence','targeted_retry_count','stale_seen','pre_reference_classification')} |
                          {'tail_return': str(change), 'tail_return_pct':str(change*100),
                           'validated': False, 'status': 'RESEARCH_ONLY'})
            row.update(P_before=v['p_before'],P_before_trade_time=v['p_before_trade_time'],P_close=close,
                P_close_trade_time=v['research_close_trade_time'] if research else v['close_trade_time'],
                P_before_convergence_type=v['pre_reference_classification'],
                P_close_convergence_type=v.get('P_close_convergence_type','AB_converged'),
                confidence_level=v.get('confidence_level','HIGH_RESEARCH'))
            if research:
                row.update(p_close=close,close_trade_time=v['research_close_trade_time'],
                           official_price_result=v['research_official_price_result'],
                           close_research_evidence=v['close_research_evidence'])
            values.append(row)
    return {'trade_date': report['trade_date'], 'status': 'NOT_SAMPLED' if report['status'] == 'NOT_SAMPLED' else 'RESEARCH_ONLY',
            'calculable_count': report['research_calculable_count'], 'candidate_count': len(values),
            'candidates': values, 'validated': False, 'production_signals': 'NOT_GENERATED',
            'note': 'Existing P_before convergence plus explicit close research hierarchy; all validated=false. Official mismatch excluded; pending official remains unverified research.'}


def write_report(date, snapshots, probes, universe, official, output, close_research_enabled=None):
    report = build_report(date, snapshots, probes, universe, official, close_research_enabled)
    candidates = research_candidates(report)
    report['research_candidate_count'] = candidates['candidate_count']
    (output/'convergence_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (output/'candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    (output/'research_candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
    (output/f'research_candidates_{date}.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
    candidate_columns=('code','name','market','p_before','p_before_trade_time','p_close','close_trade_time',
        'tail_return','tail_return_pct','official_price_result','p_before_convergence_status','p_close_convergence_status',
        'targeted_retry_count','stale_seen','pre_pair_evidence','close_pair_evidence','pre_reference_classification',
        'P_before','P_before_trade_time','P_close','P_close_trade_time','P_before_convergence_type',
        'P_close_convergence_type','confidence_level','close_research_evidence','validated','status')
    with (output/'research_candidates.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=candidate_columns,extrasaction='ignore');writer.writeheader()
        for row in candidates['candidates']:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else v for k,v in row.items()})
    (output/f'research_candidates_{date}.csv').write_bytes((output/'research_candidates.csv').read_bytes())
    (output/'pre_reference_C_summary.json').write_text(json.dumps({
        'trade_date':date,'enabled':date>=PRE_C_START_DATE,'validated':False,
        'original_AB_with_retry_converged':report['p_before_original_AB_with_retry_converged_count'],
        'original_AB_reference_only_converged':report['p_before_original_AB_converged_count'],
        'exclusive_classes':{label:report['p_before_'+label+'_converged_count'] for label in ('ABC','AB','AC','BC')},
        'unresolved':report['p_before_unresolved_count'],
        'unresolved_TWSE':report['p_before_unresolved_tse_count'],'unresolved_TPEx':report['p_before_unresolved_otc_count'],
        'unresolved_categories':report['p_before_unresolved_categories'],
        'rule':'Original AB/targeted-retry rule preserved. C fallback retains trade.t/trade.z/v; missing C never fabricated.',
        'note':'Exclusive AB includes the original targeted-retry cohort; ABC means three raw fresh references agree. No independent P_before truth.'},ensure_ascii=False,indent=2))
    columns = ('ex', 'code', 'name', 'market', 'p_before', 'p_before_trade_time', 'p_before_observed_A', 'p_before_observed_B',
               'p_before_server_time_A', 'p_before_server_time_B', 'p_before_convergence_status',
               'p_close', 'close_trade_time', 'close_observed_A', 'close_observed_B', 'close_server_time_A', 'close_server_time_B',
               'close_convergence_status', 'close_classification', 'official_close', 'official_price_result',
               'p_before_A_server_time','p_before_B_server_time','p_close_A_server_time','p_close_B_server_time',
               'p_close_convergence_status','targeted_retry_count','stale_seen',
               'research_p_close','research_close_trade_time','P_close_convergence_type','confidence_level',
               'both_converged', 'research_calculable', 'p_before_validated', 'p_close_validated', 'both_validated', 'volume_status')
    with (output/'convergence.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction='ignore')
        writer.writeheader(); writer.writerows(report['securities'])
    lines = [f'# {date} 全市場雙快照收斂研究', '', f"狀態：{report['status']}；所有 validated=false；Production 訊號未產生。", '',
             '|項目|數量|', '|---|---:|']
    for key, value in report.items():
        if key.endswith('_count'):
            lines.append(f'|{key}|{value}|')
    lines.extend(['', '15 秒 server age 僅為研究門檻；cachedAlive 單位 UNVERIFIED。',
                  'targeted retry 的兩筆新鮮觀察可替代原 A/B；原始 A/B 與採用的配對證據分別保存。',
                  '延後成交只按 trade.t 約 13:33 分類；晚看到 13:30 成交仍屬正常收盤候選。',
                  '官方 PENDING 不算擷取失敗；research 名單保留 PENDING 標籤，官方 mismatch 排除。',
                  '無新收盤成交保留最後實際成交候選，官方尚未匹配時不升級 validated。',
                  '收盤量保持 UNVERIFIED；沒有 reference 採樣的歷史日期保持 NOT_SAMPLED。'])
    (output/'convergence_report.md').write_text('\n'.join(lines)+'\n')
    (output/'unknown_convergence.json').write_text(json.dumps({'trade_date': date, 'securities': [
        {k: v[k] for k in ('ex', 'code', 'p_before_convergence_status', 'close_convergence_status', 'pre_pair_evidence', 'close_pair_evidence')}
        for v in report['securities'] if not v['both_converged']]}, ensure_ascii=False, indent=2))
    unknown={'trade_date':date,'unknown_count':report['unknown_count'],'securities':[
        {k:v[k] for k in ('ex','code','name','market','p_before','p_close','p_before_convergence_status',
                         'p_close_convergence_status','pre_pair_evidence','close_pair_evidence')}
        for v in report['securities'] if not v['both_converged']]}
    (output/'unknown_symbols.json').write_text(json.dumps(unknown,ensure_ascii=False,indent=2))
    if report['live_close_research_enabled']:
        summary={'trade_date':date,'status':'RESEARCH_ONLY','validated':False,
            'tradable_universe':len(universe),'P_before_converged':report['p_before_converged_count'],
            'P_close':{k:report['research_close_'+k+'_count'] for k in (*close_research.TYPES,'delayed_close_candidate','unresolved')},
            'research_calculable_count':report['research_calculable_count'],
            'candidate_count':candidates['candidate_count'],
            'candidates':[{k:r[k] for k in ('code','name','tail_return','confidence_level','validated')} for r in candidates['candidates']]}
        (output/'live_research_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    return report
