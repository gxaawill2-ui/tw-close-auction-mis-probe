import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path('/workspace/scratch/ffdbcc9b958b/mis-evidence-20261001')
OUT = ROOT / 'review'
OUT.mkdir(exist_ok=True)

def read_rows(name):
    return [json.loads(x) for x in (ROOT/name).read_text().splitlines()]

probe = read_rows('probe_raw.jsonl')
records = {p:read_rows(p+'_raw.jsonl') for p in ('preclose','close','delayed_close')}
snap = {p:{(x.get('ex'),x.get('c')):x for r in rs for x in (r.get('response') or {}).get('msgArray',[]) if x.get('c')} for p,rs in records.items()}
universe = json.loads((ROOT/'universe.json').read_text())
summary = json.loads((ROOT/'run_summary.json').read_text())
official = json.loads((ROOT/'TWSE_official_20261001.json').read_text())
assert official['date']=='20261001'
table = next(t for t in official['tables'] if '證券代號' in (t.get('fields') or []))
daily = {r[0]:dict(zip(table['fields'],r)) for r in table['data']}
checks=[]
for (market,code),item in snap['delayed_close'].items():
    if market!='tse':continue
    source=daily.get(code)
    tr=item.get('trade') or {}
    check={'market':market,'code':code,'name':item['n'],'trade':tr,'mis_outer_z':item.get('z'),'mis_total_v':item.get('v'),'official_date':'20261001','official_close':source.get('收盤價') if source else None,'official_volume_shares':source.get('成交股數') if source else None,'price_result':'UNAVAILABLE','volume_result':'UNAVAILABLE'}
    if source:
        try:check['price_result']='MATCH' if Decimal(tr['z'])==Decimal(source['收盤價'].replace(',','')) else 'MISMATCH'
        except (KeyError,ValueError,ArithmeticError):pass
        try:check['volume_result']='MATCH_X1000' if Decimal(item['v'])*1000==Decimal(source['成交股數'].replace(',','')) else 'MISMATCH'
        except (KeyError,ValueError,ArithmeticError):pass
    checks.append(check)

timeline=[]
for row in probe:
    body=row.get('response') or {}
    for item in body.get('msgArray',[]):
        tr=item.get('trade') or {}
        timeline.append({'window':row['window'],'planned_at':row['planned_at'],'requested_at':row.get('requested_at'),'received_at':row.get('received_at'),'server_sys_date':body.get('queryTime',{}).get('sysDate'),'server_sys_time':body.get('queryTime',{}).get('sysTime'),'cached_alive':body.get('cachedAlive'),'market':item.get('ex'),'code':item.get('c'),'name':item.get('n'),'d':item.get('d'),**{k:item.get(k) for k in ('z','pz','t','v','tv','s')},**{'trade_'+k:tr.get(k) for k in ('t','z','v','ft')},'http_status':row.get('http_status'),'error':row.get('error')})
with (OUT/'mis-probe-timeline-2026-10-01.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(timeline[0]));writer.writeheader();writer.writerows(timeline)

pre = {x['code']:x for x in timeline if x['planned_at'].endswith('13:25:10.000+08:00')}
near = {x['code']:x for x in timeline if x['planned_at'].endswith('13:29:59.000+08:00')}
sample=[]
for code,b in pre.items():
    n=near[code];last=snap['delayed_close'][(b['market'],code)]
    series=[x for x in timeline if x['code']==code]
    first=next((x for x in series if (x['trade_t'] or '')>='13:30:00'),None)
    sample.append({'market':b['market'],'code':code,'name':b['name'],'pre_sample_trade_t':b['trade_t'],'pre_sample_trade_z':b['trade_z'],'pre_sample_v':b['v'],'near_close_trade_t':n['trade_t'],'near_close_trade_z':n['trade_z'],'near_close_v':n['v'],'close_trade':last.get('trade'),'close_v':last.get('v'),'close_tv':last.get('tv'),'close_s':last.get('s'),'first_close_observed_request':first['requested_at'] if first else None,'first_close_observed_response':first['received_at'] if first else None,'v_close_minus_pre':int(last['v'])-int(b['v']),'v_close_minus_near':int(last['v'])-int(n['v']),'semantics_status':'OBSERVED_NOT_FULLY_VERIFIED'})

batch=[]
for phase,rs in records.items():
    for row in rs:
        batch.append({k:row.get(k) for k in ('phase','batch_no','requested_at','received_at','latency_ms','retry','error','expected_count','returned_count')})
with (OUT/'mis-batch-timeline-2026-10-01.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(batch[0]));writer.writeheader();writer.writerows(batch)

result={'trade_date':'2026-10-01','run_id':36712518342,'runner_started_at':summary['runner_started_at'],'artifact_id':11143660552,'capture_summary':summary,'probe_counts':dict(Counter(x['window'] for x in probe)),'valid_probe_responses':sum(not x.get('error') for x in probe),'probe_errors':[{k:x.get(k) for k in ('window','planned_at','requested_at','received_at','http_status','error','missing')} for x in probe if x.get('error')],'cached_probe_responses':sum('cachedAlive' in (x.get('response') or {}) for x in probe),'max_cached_alive':max((x.get('response') or {}).get('cachedAlive',0) for x in probe),'preclose_request_after_1325_batches':[x['batch_no'] for x in records['preclose'] if datetime.fromisoformat(x['requested_at'])>=datetime.fromisoformat('2026-10-01T13:25:00+08:00')],'samples':sample,'twse_price_counts':dict(Counter(x['price_result'] for x in checks)),'twse_volume_counts':dict(Counter(x['volume_result'] for x in checks)),'twse_official_checks':checks,'tpex_validation':'PENDING_SAME_DATE_NONEMPTY_OFFICIAL_DATA','tradable_universe':'UNVERIFIED_DO_NOT_CHANGE_DENOMINATOR','signals':'NOT_GENERATED','raw_file_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('probe_raw.jsonl','preclose_raw.jsonl','close_raw.jsonl','delayed_close_raw.jsonl')}}
excluded=[]
pool={(x['ex'],x['code']) for x in universe}
stops=json.loads((ROOT/'twse_violation_stop.json').read_text())
assert '115年10月01日' in stops['tables'][0]['title']
for row in stops['tables'][0]['data']:
    if ('tse',row[0]) in pool:
        excluded.append({'market':'tse','code':row[0],'name':row[1],'reason':'OFFICIAL_STOP_TRADING','source':'https://www.twse.com.tw/rwd/zh/violation/stop?response=json','source_row':row})
special=json.loads((ROOT/'tpex_chtm_20261001.json').read_text())
assert special['date']=='20261001'
for table in special['tables']:
    for row in table['data']:
        entry=dict(zip(table['fields'],row))
        if ('otc',entry['證券代號']) in pool and entry['停止交易']=='Ｙ':
            excluded.append({'market':'otc','code':entry['證券代號'],'name':entry['證券名稱'],'reason':'OFFICIAL_STOP_TRADING','source':'https://www.tpex.org.tw/www/zh-tw/afterTrading/chtm?date=2026%2F10%2F01&response=json','source_row':entry})
resumptions=json.loads((ROOT/'twse_reduction_legacy.txt').read_text())
for path in ROOT.glob('twse_*_interval.txt'):
    detail=json.loads(path.read_text()); row=detail['data'][0]; code=row[0].strip()
    resume=next(r[0] for r in resumptions['data'] if r[1].strip()==code)
    def roc_date(text):
        parts=list(map(int,text.split('/')))
        return datetime(parts[0]+1911,parts[1],parts[2]).date()
    if roc_date(row[2])<=datetime(2026,10,1).date()<roc_date(resume):
        excluded.append({'market':'tse','code':code,'name':row[1],'reason':'OFFICIAL_CAPITAL_REDUCTION_HALT','stop_date':row[2],'resume_date':resume,'evidence_file':path.name,'source_row':row})
# A dated delisting notice verified separately; a one-day evidence annotation,
# not a blacklist or logic to exclude the symbol on other trading dates.
excluded.append({'market':'otc','code':'8183','reason':'OFFICIAL_DELISTING','effective_date':'2026-10-01','source':'https://www.tpex.org.tw/storage/eb_data/11509/11500054131.html'})
excluded_set={(x['market'],x['code']) for x in excluded}
adjusted=pool-excluded_set
coverage={phase:{'adjusted_expected_count':len(adjusted),'returned_count':len(items),'symbol_set_equal':set(items)==adjusted,'missing':[f'{m}:{c}' for m,c in sorted(adjusted-set(items))],'unexpected':[f'{m}:{c}' for m,c in sorted(set(items)-adjusted)]} for phase,items in snap.items()}
result['tradable_universe']={'status':'ONE_DAY_OFFICIAL_EXCLUSION_AUDIT','original_count':len(pool),'excluded_count':len(excluded_set),'adjusted_count':len(adjusted),'excluded':excluded,'coverage':coverage,'limitation':'General daily universe builder and separate special-trading tags remain to be implemented; successful identity response does not verify last-trade or closing-price validity.'}
result['tpex_official_last_check']={'date':'20261001','quote_rows':0,'status':'PENDING'}
(OUT/'mis-evidence-review-2026-10-01.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'tradable_universe':result['tradable_universe'],'twse_prices':result['twse_price_counts'],'signals':result['signals']},ensure_ascii=False,indent=2))
