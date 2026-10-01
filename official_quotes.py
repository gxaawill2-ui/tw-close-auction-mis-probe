"""Date-gated official close tables. Empty/stale tables are PENDING, never today."""
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from freshness import decimal_value


def quote_url(ex,date):
    if ex=='tse':
        return 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?'+urlencode({'date':date.replace('-',''),'type':'ALLBUT0999','response':'json'})
    return 'https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?'+urlencode({'date':date.replace('-','/'),'id':'','response':'json'})


def parse_quotes(ex,date,body):
    if body.get('date') != date.replace('-',''):
        return {},'PENDING_WRONG_OR_MISSING_DATE'
    if str(body.get('stat','')).lower()!='ok':return {},'PENDING_OFFICIAL_STATUS'
    result={}
    for table in body.get('tables',[]):
        fields=table.get('fields') or []
        code_key='證券代號' if ex=='tse' else '代號'
        close_key='收盤價' if ex=='tse' else '收盤'
        if code_key not in fields or close_key not in fields:continue
        for values in table.get('data',[]):
            row=dict(zip(fields,values));code=str(row[code_key]).strip()
            result[code]={'official_close':row.get(close_key),'official_volume_shares':row.get('成交股數'),
                          'official_date':date,'official_row':row}
    return result,'AVAILABLE_SAME_DATE' if result else 'PENDING_EMPTY_TABLE'


def validate(date,symbols,snapshots,output,get_bytes):
    markets={};sources=[]
    for ex in ('tse','otc'):
        url=quote_url(ex,date);observed=datetime.now().astimezone().isoformat(timespec='milliseconds')
        try:
            status,raw=get_bytes(url,25)
            (output/f'official_close_{ex}.json').write_bytes(raw)
            body=json.loads(raw.decode('utf-8-sig'))
            rows,state=parse_quotes(ex,date,body)
            if status!=200:rows,state={},'PENDING_HTTP_ERROR'
            markets[ex]=rows
            source={'ex':ex,'url':url,'checked_at':observed,'http_status':status,
                    'status':state,'row_count':len(rows),'response_date':body.get('date')}
        except Exception as exc:
            markets[ex]={};source={'ex':ex,'url':url,'checked_at':observed,'status':'PENDING_SOURCE_ERROR',
                                 'error':f'{type(exc).__name__}:{exc}'}
        sources.append(source)
    # Keep the newest observation by response time, not file/submit order.
    latest={}
    for snapshot in snapshots:
        for record in snapshot['records']:
            if record.get('error'):continue
            for item in (record.get('response') or {}).get('msgArray',[]):
                key=(item.get('ex'),item.get('c'))
                if key not in latest or record['received_at']>latest[key][0]:latest[key]=(record['received_at'],item)
    checks=[]
    for symbol in symbols:
        ex,code=symbol['ex'],symbol['code'];stamp,item=latest.get((ex,code),(None,{}))
        trade=item.get('trade') or {};off=markets[ex].get(code,{})
        mis_price,official_price=decimal_value(trade.get('z')),decimal_value(off.get('official_close'))
        state='MATCH' if mis_price is not None and official_price is not None and mis_price==official_price else 'MISMATCH'
        if mis_price is None or official_price is None:state='UNAVAILABLE'
        checks.append({**symbol,'mis_trade':trade,'mis_observed_at':stamp,'mis_total_v':item.get('v'),
                       **off,'price_result':state,'ex':ex,
                       'price_source_semantics':'UNVERIFIED_NESTED_TRADE','validated':False})
    result={'trade_date':date,'status':'PENDING' if any(s['status']!='AVAILABLE_SAME_DATE' for s in sources) else 'SAME_DATE_COMPARISON_ONLY',
            'sources':sources,'checks':checks,'matches':sum(x['price_result']=='MATCH' for x in checks),
            'mismatches':sum(x['price_result']=='MISMATCH' for x in checks),
            'unavailable':sum(x['price_result']=='UNAVAILABLE' for x in checks),
            'note':'Daily official close matching is evidence; it does not validate the final preclose trade or freshness rule.'}
    (output/'official_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
