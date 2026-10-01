"""Observational MIS freshness analysis. No rule here authorizes strategy signals."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
PRECLOSE_CHECKPOINTS = tuple(f'13:25:{s:02d}' for s in range(15, 60, 5)) + ('13:26:00', '13:26:05', '13:26:10')
CLOSE_CHECKPOINTS = ('13:30:20', '13:30:30', '13:30:45', '13:31:00', '13:31:30', '13:32:00', '13:32:30', '13:33:00', '13:33:15')
TIMEZONE_STATUS = 'Asia/Taipei interpretation; MIS queryTime has no offset; NOT_INDEPENDENTLY_VERIFIED'


def planned_ticks(date, start, end, checkpoints=()):
    first = datetime.fromisoformat(date+'T'+start).replace(tzinfo=TZ)
    last = datetime.fromisoformat(date+'T'+end).replace(tzinfo=TZ)
    ticks = [first+timedelta(seconds=s) for s in range(int((last-first).total_seconds())+1)]
    ticks.extend(datetime.fromisoformat(date+'T'+s).replace(tzinfo=TZ) for s in checkpoints)
    return sorted(set(ticks))


def decimal_value(value):
    if value is None or str(value).strip() in ('', '-', '--', '---'): return None
    try:
        number = Decimal(str(value).replace(',', ''))
        return number if number.is_finite() else None
    except InvalidOperation: return None


def parsed_time(value):
    try:
        result = datetime.fromisoformat(value)
        return result if result.tzinfo is not None else None
    except (TypeError, ValueError): return None


def server_evidence(record, date):
    body = record.get('response') or {}
    query = body.get('queryTime') or {}
    server = None
    try:
        server = datetime.strptime(str(query['sysDate'])+' '+str(query['sysTime']), '%Y%m%d %H:%M:%S').replace(tzinfo=TZ)
    except (KeyError, ValueError, TypeError): pass
    request, received = parsed_time(record.get('requested_at')), parsed_time(record.get('received_at'))
    valid_clock = bool(server and request and received and server.date().isoformat() == date
                       and request <= received and server <= received+timedelta(seconds=1))
    return {'server_time':server.isoformat() if server else None,
            'server_sys_date':query.get('sysDate'), 'server_sys_time':query.get('sysTime'),
            'query_time':query, 'cached_alive':body.get('cachedAlive'),
            'server_age_ms':round((request-server).total_seconds()*1000, 3) if server and request else None,
            'server_age_at_receive_ms':round((received-server).total_seconds()*1000, 3) if server and received else None,
            'server_clock_plausible':valid_clock, 'server_timezone_status':TIMEZONE_STATUS,
            'cached_alive_unit':'UNVERIFIED; preserved as reported'}


def observations(records, date):
    rows=[]
    for record in records:
        meta=server_evidence(record,date)
        items=(record.get('response') or {}).get('msgArray') or []
        lookup={(x.get('ex'),x.get('c')):x for x in items if isinstance(x,dict) and x.get('c')}
        expected=record.get('symbols') or [dict(ex=k[0],code=k[1],market=k[0],name=x.get('n')) for k,x in lookup.items()]
        for symbol in expected:
            item=lookup.get((symbol['ex'],symbol['code']),{})
            trade=item.get('trade') or {}
            rows.append({'phase':record.get('phase') or record.get('window'),
                         'planned_at':record.get('planned_at'),'requested_at':record.get('requested_at'),
                         'received_at':record.get('received_at'),'observed_at':record.get('received_at'),
                         'latency_ms':record.get('latency_ms'),'http_status':record.get('http_status'),
                         'error':record.get('error') or ('MISSING_SYMBOL' if not item else None),
                         'market':symbol.get('market'),'ex':symbol['ex'],'code':symbol['code'],'name':symbol.get('name'),
                         **meta,**{k:item.get(k) for k in ('d','t','z','pz','v','tv','s')},
                         **{'trade_'+k:trade.get(k) for k in ('t','z','v','ft')},'trade':trade})
    return rows


def fresh_candidate(row, date, max_age_ms=15000):
    """An explicit research threshold, not a validated exchange freshness rule."""
    age=row.get('server_age_at_receive_ms')
    return bool(not row.get('error') and row.get('server_clock_plausible')
                and row.get('d') == date.replace('-','') and age is not None
                and -1000 <= age <= max_age_ms)


def pre_eligible(row, date, max_age_ms=15000):
    stamp=parsed_time(row.get('server_time'))
    trade_time=row.get('trade_t')
    return bool(fresh_candidate(row,date,max_age_ms) and stamp
                and stamp.strftime('%H:%M:%S') >= '13:25:00'
                and parsed_time(row.get('received_at')).strftime('%H:%M:%S') < '13:30:00'
                and isinstance(trade_time,str) and '09:00:00' <= trade_time < '13:25:00'
                and decimal_value(row.get('trade_z')) is not None)


def identity(row):
    return (row.get('trade_t'),decimal_value(row.get('trade_z')),decimal_value(row.get('v')))


def pre_convergence(series,date,max_age_ms=15000,stable_responses=3):
    ordered=sorted(series,key=lambda x:x.get('received_at') or x.get('planned_at') or '')
    eligible=[r for r in ordered if pre_eligible(r,date,max_age_ms)]
    if not eligible:
        have_trade=any(decimal_value(r.get('trade_z')) is not None for r in ordered)
        stale=any(r.get('server_time') and not fresh_candidate(r,date,max_age_ms) for r in ordered)
        return {'status':'stale_cache' if stale else ('unknown' if have_trade else 'no_trade'),
                'candidate':None,'validated':False,'reference_status':'NO_FRESH_OBSERVED_REFERENCE'}
    reference=eligible[-1]
    ref=identity(reference)
    # Chronological regressions or conflicting prices at identical trade times
    # are retained as contradictions rather than silently taking the largest t.
    conflicts=any(b.get('trade_t') < a.get('trade_t') or
                  (a.get('trade_t') == b.get('trade_t') and identity(a) != identity(b))
                  for a,b in zip(eligible,eligible[1:]))
    changes=[r for i,r in enumerate(eligible) if i==0 or identity(r)!=identity(eligible[i-1])]
    suffix=[]
    for row in reversed(eligible):
        if identity(row)!=ref: break
        suffix.append(row)
    suffix.reverse()
    unique=[];seen=set()
    for row in suffix:
        if row['server_time'] not in seen:
            seen.add(row['server_time']);unique.append(row)
    stable_at=unique[stable_responses-1]['received_at'] if len(unique)>=stable_responses else None
    candidate_status='confirmed_candidate' if stable_at and not conflicts else 'not_converged'
    return {'status':candidate_status,'candidate':reference.get('trade_z'),
            'trade_time':reference.get('trade_t'),'observed_at':reference.get('received_at'),
            'server_time':reference.get('server_time'),'v':reference.get('v'),
            'first_observed_reference_at':suffix[0]['received_at'],
            'last_preclose_change_observed_at':changes[-1]['received_at'],
            'stable_at':stable_at,'distinct_fresh_server_times':len(unique),
            'contradiction':conflicts,'validated':False,
            'reference_status':'LATEST_FRESH_OBSERVED_PRE_CLOSE_NOT_INDEPENDENT_FINAL_TRADE_TRUTH',
            'rule':{'max_receive_server_age_ms':max_age_ms,'stable_distinct_responses':stable_responses,
                    'server_must_reach':'13:25:00','time_zone':'UNVERIFIED_ASIA_TAIPEI_ASSUMPTION'}}


def close_evidence(series,date,official):
    ordered=sorted(series,key=lambda r:r.get('received_at') or '')
    eligible=[r for r in ordered if fresh_candidate(r,date) and decimal_value(r.get('trade_z')) is not None]
    closed=[r for r in eligible if isinstance(r.get('trade_t'),str) and '13:30:00'<=r['trade_t']<='13:33:15'
            and parsed_time(r['server_time']).strftime('%H:%M:%S')>=r['trade_t']]
    last=(closed or eligible or ordered or [{}])[-1]
    official_price=(official or {}).get('official_close')
    match=(decimal_value(last.get('trade_z')) is not None and decimal_value(official_price) is not None
           and decimal_value(last.get('trade_z'))==decimal_value(official_price))
    if closed:
        status='official_matched_candidate' if match else 'pending_official_or_mismatch'
        classification='normal_close_candidate' if last['trade_t']=='13:30:00' else 'delayed_close_candidate'
        first=next(r for r in ordered if r.get('trade_t')==last['trade_t'] and decimal_value(r.get('trade_z'))==decimal_value(last.get('trade_z')))
    else:
        status='unknown' if eligible else 'stale_cache'
        classification='no_close_new_trade_observed';first=None
    return {'p_close':last.get('trade_z'),'close_trade_time':last.get('trade_t'),
            'close_observed_at':last.get('received_at'),'close_server_time':last.get('server_time'),
            'first_close_observed_requested_at':first.get('requested_at') if first else None,
            'first_close_observed_at':first.get('received_at') if first else None,
            'close_freshness_status':status,'close_classification':classification,
            'official_close':official_price,'official_matches':match,'validated':False}


def volume_evidence(series,date):
    pre=[r for r in series if pre_eligible(r,date)]
    closing=[r for r in series if fresh_candidate(r,date) and isinstance(r.get('trade_t'),str)
             and '13:30:00'<=r['trade_t']<='13:33:15'
             and parsed_time(r['server_time']).strftime('%H:%M:%S')>=r['trade_t']]
    before=max(pre,key=lambda r:r['received_at']) if pre else {}
    close=max(closing,key=lambda r:r['received_at']) if closing else {}
    vb,vc=decimal_value(before.get('v')),decimal_value(close.get('v'))
    difference=vc-vb if vb is not None and vc is not None and vc>=vb else None
    return {'status':'UNVERIFIED','v_before':before.get('v'),'v_before_observed_at':before.get('received_at'),
            'v_before_server_time':before.get('server_time'),'v_close':close.get('v'),
            'difference':str(difference) if difference is not None else None,
            'tv':close.get('tv'),'s':close.get('s'),'trade_v':close.get('trade_v'),
            'matches':{key:difference is not None and decimal_value(close.get(key))==difference for key in ('tv','s','trade_v')},
            'independent_auction_volume_verified':False}


def write_report(date,snapshots,probe_rows,universe,official,output):
    probe_observations=observations(probe_rows,date)
    full=observations([r for s in snapshots for r in s['records']],date)
    grouped=defaultdict(list)
    for row in full+probe_observations: grouped[(row['ex'],row['code'])].append(row)
    checks={(r['ex'],r['code']):r for r in official.get('checks',[])}
    values=[]
    for symbol in universe:
        key=(symbol['ex'],symbol['code']);series=grouped[key]
        before=pre_convergence(series,date)
        closing=close_evidence(series,date,checks.get(key))
        values.append({**symbol,'p_before':before.get('candidate'),
                       'p_before_trade_time':before.get('trade_time'),
                       'p_before_observed_at':before.get('observed_at'),
                       'p_before_server_time':before.get('server_time'),
                       'p_before_freshness_status':before['status'],'preclose_convergence':before,
                       **closing,'p_before_validated':False,'p_close_validated':False,'both_validated':False,
                       'volume_status':'UNVERIFIED','volume_evidence':volume_evidence(series,date)})
    for row in probe_observations:
        row['freshness_class']='fresh_candidate' if fresh_candidate(row,date) else ('stale_cache' if row.get('server_time') else 'unknown')
    if probe_observations:
        with (output/'freshness_timeline.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(probe_observations[0]));writer.writeheader()
            for row in probe_observations:
                writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else v for k,v in row.items()})
    sensitivity=[]
    for max_age in (5000,15000,30000):
        for stable in (2,3):
            candidates=[pre_convergence(series,date,max_age,stable) for series in grouped.values()]
            sensitivity.append({'age_threshold_ms':max_age,'distinct_stable_responses':stable,
                                'confirmed_candidate':sum(x['status']=='confirmed_candidate' for x in candidates),
                                'validated':0})
    checkpoints=[]
    samples={(r['ex'],r['code']) for r in probe_observations}
    for clock in ('13:25:10',*PRECLOSE_CHECKPOINTS):
        cutoff=datetime.fromisoformat(date+'T'+clock).replace(tzinfo=TZ)
        checkpoint_records=[r for r in probe_rows if (r.get('planned_at') or '')[:19]==date+'T'+clock]
        checkpoint_status='SAMPLED' if checkpoint_records else 'NOT_SAMPLED'
        measured=available=fresh_seen=0
        for key in samples:
            series=[r for r in grouped[key] if r.get('phase') in ('preclose_window','close_window')]
            reference=pre_convergence(series,date)
            subset=[r for r in series if parsed_time(r.get('received_at')) and parsed_time(r['received_at'])<=cutoff]
            if reference.get('candidate') is None:continue
            available+=1
            matches=[r for r in subset if identity(r)==(reference.get('trade_time'),decimal_value(reference.get('candidate')),decimal_value(reference.get('v')))]
            measured+=bool(matches)
            fresh_seen+=any(pre_eligible(r,date) for r in matches)
        checkpoints.append({'checkpoint':clock,'samples_with_observed_reference':available,
                            'checkpoint_status':checkpoint_status,
                            'valid_checkpoint_responses':sum(not r.get('error') for r in checkpoint_records) if checkpoint_records else None,
                            'observed_reference_seen_by_checkpoint':measured if checkpoint_records else None,
                            'fresh_reference_seen':fresh_seen if checkpoint_records else None,
                            'validated_count':0,'warning':'Retrospective observed convergence only; not final-trade ground truth or reliability percentage'})
    report={'trade_date':date,'status':'RESEARCH_ONLY','timezone_status':TIMEZONE_STATUS,
            'cached_alive_semantics':'UNVERIFIED','p_before_validated_count':0,'p_close_validated_count':0,
            'both_validated_count':0,'universe_count':len(universe),'samples':sorted(f'{e}:{c}' for e,c in samples),
            'sensitivity':sensitivity,'checkpoints':checkpoints,'securities':values,
            'signals':{'status':'NOT_GENERATED','reason':'No cross-day validated freshness rule or independent final preclose trade evidence'},
            'note':'Three unchanged old cached payloads are not three distinct fresh responses.'}
    (output/'freshness_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (output/'freshness_report.md').write_text(render_report(report),encoding='utf-8')
    (output/'pending_close.json').write_text(json.dumps({'trade_date':date,'semantics':'pending evidence, not assumed delayed closing',
        'securities':[{'ex':v['ex'],'code':v['code'],'previous_trade_time':v['p_before_trade_time'],
                       'trade_time':v['close_trade_time'],'observed_at':v['close_observed_at'],'server_time':v['close_server_time'],
                       'freshness_status':v['close_freshness_status'],'classification':v['close_classification'],
                       'official_close':v['official_close']} for v in values if v['close_freshness_status']!='official_matched_candidate']},ensure_ascii=False,indent=2))
    return report


def render_report(report):
    sample_set=set(report['samples'])
    lines=[f"# {report['trade_date']} Freshness / 收斂研究",'',
           'RESEARCH_ONLY。fresh / confirmed_candidate 是可調研究條件，不是已驗證成交資料。',
           'server_age_ms = requested_at − server_time（帶正負號）；另保留 received_at − server_time。',
           TIMEZONE_STATUS,'cachedAlive 單位及定義 UNVERIFIED，不單獨作判斷。','',
           '|代號|pre trade.t|pre trade.z|首次看到參考值|候選穩定時間|狀態|close trade.t|close trade.z|首次看到收盤|官方一致|',
           '|---|---|---|---|---|---|---|---|---|---|']
    for v in report['securities']:
        if v['ex']+':'+v['code'] not in sample_set:continue
        pre=v['preclose_convergence']
        cols=[v['code'],v['p_before_trade_time'],v['p_before'],pre.get('first_observed_reference_at'),pre.get('stable_at'),pre['status'],v['close_trade_time'],v['p_close'],v['first_close_observed_at'],v['official_matches']]
        lines.append('|'+ '|'.join('—' if x is None else str(x) for x in cols)+'|')
    lines.extend(['','|Checkpoint|採樣狀態|有觀察參考值的樣本|已看到相同參考值|其中 fresh 候選|validated|','|---|---|---:|---:|---:|---:|'])
    for x in report['checkpoints']:
        seen=x['observed_reference_seen_by_checkpoint'];fresh=x['fresh_reference_seen']
        lines.append(f"|{x['checkpoint']}|{x['checkpoint_status']}|{x['samples_with_observed_reference']}|{seen if seen is not None else '—'}|{fresh if fresh is not None else '—'}|0|")
    lines.extend(['','P_before validated = 0；P_close validated = 0；both validated = 0。',
                  '這些 0 表示本版仍未啟用正式驗證規則，不表示 MIS 無法使用或沒有 ±3% 股票。',
                  '收盤量 UNVERIFIED；不產生策略名單。',
                  '26–31 秒全市場速度是否足夠：需根據此次實測收斂、新鮮度、缺漏與跨日驗證判斷，不能由 wall time 單獨決定。'])
    lines.extend(['','|代號|近收盤新鮮 V_before|V_close|差額|tv|s|trade.v|驗證|','|---|---|---|---|---|---|---|---|'])
    for v in report['securities']:
        if v['ex']+':'+v['code'] not in sample_set:continue
        volume=v['volume_evidence']
        columns=[v['code'],volume['v_before'],volume['v_close'],volume['difference'],volume['tv'],volume['s'],volume['trade_v'],'UNVERIFIED']
        lines.append('|'+ '|'.join('—' if x is None else str(x) for x in columns)+'|')
    return '\n'.join(lines)+'\n'
