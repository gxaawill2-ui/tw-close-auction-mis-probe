"""Reproducible observation priority, never a volume/return prediction.

No realized market prices/volumes enter the model. Ratings are fund x event,
with generation-time availability and history, not retroactive trading signals.
"""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

VERSION = 'observation-priority-v1'
# Conservative public availability boundary: creation of the first main rollout
# run 38006035935. Earlier prototype timestamps must not become backtest signals.
MODEL_AVAILABLE_SINCE = '2026-10-10T07:46:14+08:00'
AUM_MAX_AGE_DAYS = 30


def timestamp(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('Timezone required')
    return d


def evaluate(fund, event, metric, as_of):
    result={'importance_level':'DATA_INSUFFICIENT','importance_score':None,
        'importance_reason':[], 'importance_method_version':VERSION,
        'importance_confidence':'DATA_INSUFFICIENT','importance_evidence':[],
        'fund_aum':None,'aum_as_of':None,'affected_stock_count':None,
        'affected_weight_change':None,'estimated_exposure_change':None,
        'expected_execution_pattern':'UNKNOWN'}
    now=timestamp(as_of)
    if fund.get('management_type')!='PASSIVE' or fund.get('mapping_status')!='CONFIRMED':
        result['importance_reason']=['主動／追蹤關係未確認，不套用被動換股模型。'];return result
    if event.get('event_status')=='CONFLICT':
        result['importance_reason']=['來源日期衝突，暫不評級。'];return result
    if timestamp(event['information_available_as_of'])>now or timestamp(fund['information_available_as_of'])>now:
        result['importance_reason']=['事件或追蹤資訊於評級時尚不可得。'];return result
    counts=event.get('constituent_counts')
    stocks=event.get('affected_stocks') or []
    if counts and all(isinstance(counts.get(k),int) and counts[k]>=0 for k in ('additions','deletions')):
        result['affected_stock_count']=sum(counts[k] for k in ('additions','deletions'))
    elif stocks: result['affected_stock_count']=len({(s.get('market'),s.get('code')) for s in stocks})
    pattern='MULTIDAY' if event.get('implementation_window') else 'INDEX_SINGLE_CLOSE_CONFIRMED' if event.get('close_date_status')=='CONFIRMED_CLOSE_IMPLEMENTATION' else 'INDEX_SINGLE_CLOSE_EXPECTED' if event.get('close_date_status')=='EXPECTED_CLOSE_WATCH_DATE' else 'UNKNOWN'
    result['expected_execution_pattern']=pattern
    if not metric or metric.get('currency')!='TWD' or not metric.get('source_url') or not metric.get('aum_as_of') or not metric.get('information_available_as_of'):
        result['importance_reason']=['缺少可核實、具日期的官方新台幣基金淨資產。'];return result
    observed=timestamp(metric['information_available_as_of'])
    dated=timestamp(metric['aum_as_of']+'T00:00:00+08:00')
    age=(now-dated).total_seconds()/86400
    if observed>now or age<0 or age>AUM_MAX_AGE_DAYS:
        result['importance_reason']=['基金規模尚不可得或已超過30日有效期。'];return result
    amount=metric.get('fund_aum')
    if not isinstance(amount,(int,float)) or isinstance(amount,bool) or amount<=0:
        result['importance_reason']=['官方基金規模格式未確認。'];return result
    result.update(fund_aum=amount,aum_as_of=metric['aum_as_of'],importance_evidence=[{k:copy.deepcopy(v) for k,v in metric.items() if k!='last_checked_at'}])
    if pattern=='UNKNOWN':
        result['importance_reason']=['缺少收盤觀察日或多日調整方式；規模不足以單獨評級。'];return result
    # Explicit coarse policy thresholds in TWD; these are priorities, not fitted probabilities.
    size=3 if amount>=100_000_000_000 else 2 if amount>=10_000_000_000 else 1
    concentration=2 if pattern.startswith('INDEX_SINGLE_CLOSE') else 0
    breadth=1 if (result['affected_stock_count'] or 0)>=5 else 0
    score=size+concentration+breadth
    level='HIGH' if score>=5 else 'MEDIUM' if score>=3 else 'LOW'
    result.update(importance_level=level,importance_score=score,importance_confidence='PROVISIONAL',
        importance_reason=[f'官方淨資產規模級距分數{size}（1000億／100億門檻）。',
            f'指數單一收盤觀察分數{concentration}；不代表基金實際委託時間。',
            f'本次已公布異動檔數分數{breadth}；未知不視為零異動。',
            '粗略研究優先順序；未以歷史成交量驗證。'])
    # An exposure estimate is only possible with exact official before/after weights.
    if stocks and all(s.get('weight_unit')=='fraction' and s.get('market_status')=='OFFICIAL_CONFIRMED' and isinstance(s.get('weight_before'),(int,float)) and isinstance(s.get('weight_after'),(int,float)) for s in stocks):
        change=sum(abs(s['weight_after']-s['weight_before']) for s in stocks)
        if 0<=change<=2: result.update(affected_weight_change=change,estimated_exposure_change={'twd':amount*change,'kind':'MODEL_GROSS_EXPOSURE_NOT_ACTUAL_ORDERS','weight_unit':'fraction'})
    return result


def build(events, mappings, metrics, as_of, previous=None):
    prior={r['fund_event_id']:r for r in (previous or [])};metric_lookup={r['fund_code']:r for r in metrics}
    rows=[]
    rating_time=max(timestamp(as_of),timestamp(MODEL_AVAILABLE_SINCE)).isoformat()
    for event in events:
        for code in event['related_etf_codes']:
            fund=next((m for m in mappings if m['etf_code']==code),None)
            if not fund: continue
            key=hashlib.sha256((code+'|'+event['event_id']).encode()).hexdigest()[:20]
            rating=evaluate(fund,event,metric_lookup.get(code),as_of)
            row={'fund_event_id':key,'event_id':event['event_id'],'event_name':event['event_name'],
                'fund_code':code,'fund_name':fund.get('etf_name'), 'fund_type':fund.get('fund_type','UNKNOWN'),
                'management_type':fund.get('management_type','UNKNOWN'),'index_name':event['index_name'],
                **{k:copy.deepcopy(event.get(k)) for k in ('announcement_date','effective_date','closing_impact_date','implementation_window','close_date_status')},
                **rating,'source_urls':list(dict.fromkeys([event['source_url'],fund['source_url']]+([metric_lookup[code]['source_url']] if code in metric_lookup else []))),
                'information_available_as_of':rating_time,'rating_generated_at':rating_time,'first_rated_at':rating_time,
                'last_updated_at':rating_time,'model_available_since':MODEL_AVAILABLE_SINCE,'rating_history':[]}
            old=prior.get(key)
            if old and timestamp(old['first_rated_at'])<timestamp(MODEL_AVAILABLE_SINCE):
                row['as_of_correction']={'corrected_at':rating_time,
                    'reason':'PROTOTYPE_USED_EVENT_SNAPSHOT_TIME; INVALID_FOR_PREOBSERVATION_BACKTEST',
                    'previous_first_rated_at':old['first_rated_at'],
                    'previous_information_available_as_of':old['information_available_as_of']}
                row['rating_history']=old.get('rating_history',[])+[{'superseded_at':rating_time,
                    'invalid_for_asof_backtest':True,'previous_version':{k:v for k,v in old.items() if k!='rating_history'}}]
                for entry in row['rating_history']:
                    if timestamp(entry['previous_version'].get('information_available_as_of',MODEL_AVAILABLE_SINCE))<timestamp(MODEL_AVAILABLE_SINCE):entry['invalid_for_asof_backtest']=True
                rows.append(row)
                continue
            if old:
                if old.get('as_of_correction'):row['as_of_correction']=old['as_of_correction']
                row['first_rated_at']=old['first_rated_at'];row['rating_history']=old.get('rating_history',[])
                keys=['importance_level','importance_score','importance_reason','importance_evidence','expected_execution_pattern','close_date_status','closing_impact_date','effective_date','implementation_window']
                if any(old.get(k)!=row.get(k) for k in keys):
                    row['rating_history'] += [{'superseded_at':as_of,'previous_version':{k:v for k,v in old.items() if k!='rating_history'}}]
                else:
                    row['information_available_as_of']=old['information_available_as_of'];row['last_updated_at']=old['last_updated_at']
            rows.append(row)
    return sorted(rows,key=lambda r:((r.get('closing_impact_date') or r.get('effective_date') or '9999'), {'HIGH':0,'MEDIUM':1,'LOW':2,'DATA_INSUFFICIENT':3}[r['importance_level']],r['fund_code']))


def refresh(root=Path(__file__).resolve().parent, as_of=None):
    base=root/'state/events'
    read=lambda n:json.loads((base/n).read_text())
    events=read('events-index.json');mappings=read('etf-index-map.json')['mappings']
    now=as_of or datetime.now(ZoneInfo('Asia/Taipei')).isoformat()
    metrics=read('fund-metrics.json')['funds'] if (base/'fund-metrics.json').exists() else []
    old=read('fund-events.json')['fund_events'] if (base/'fund-events.json').exists() else []
    rows=build(events['events'],mappings,metrics,now,old)
    report={'schema_version':1,'timezone':'Asia/Taipei','generated_at':now,'method_version':VERSION,
        'coverage_status':'PARTIAL','fund_events':rows,
        'counts':{level:sum(r['importance_level']==level for r in rows) for level in ('HIGH','MEDIUM','LOW','DATA_INSUFFICIENT')},
        'note':'重要程度與日期可信程度分離。PROVISIONAL僅研究優先順序，非成交量預測；同日事件不能當成獨立交易日樣本。'}
    (base/'fund-events.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

if __name__=='__main__': print(json.dumps(refresh()['counts']))
