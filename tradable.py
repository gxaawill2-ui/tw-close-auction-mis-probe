"""Date-effective official exclusions; never exclude a code because MIS missed it."""
import concurrent.futures
import html
import json
import re
from datetime import date as Date, timedelta
from pathlib import Path
from urllib.parse import urlencode


def parse_date(value):
    text=str(value).strip()
    parts=re.findall(r'\d+',text)
    if len(parts)==1:
        digits=parts[0]
        if len(digits)==7:parts=[digits[:3],digits[3:5],digits[5:]]
        elif len(digits)==8:parts=[digits[:4],digits[4:6],digits[6:]]
    if len(parts)!=3:raise ValueError('Unrecognized official date: '+text)
    year,month,day=map(int,parts)
    return Date(year+1911 if year<1911 else year,month,day)


def event(ex,code,reason,start,end,source,row):
    return {'code':str(code).strip(),'market':'TWSE' if ex=='tse' else 'TPEx','ex':ex,
            'reason':reason,'effective_from':parse_date(start).isoformat(),
            'effective_to':parse_date(end).isoformat() if end else None,
            'official_source':source,'official_row':row,
            'effective_to_semantics':'exclusive; resume day is tradable' if end else 'open-ended as reported'}


def active_events(company,events,trade_date):
    day=Date.fromisoformat(trade_date);lookup={(x['ex'],x['code']):x for x in company}
    active=[]
    for item in events:
        symbol=lookup.get((item['ex'],item['code']))
        if not symbol:continue
        start=Date.fromisoformat(item['effective_from'])
        if start>day or item['effective_to'] and day>=Date.fromisoformat(item['effective_to']):continue
        # A historical delisting must not remove a security subsequently relisted.
        listed=symbol.get('listing_date')
        if listed and parse_date(listed)>start:continue
        event_name=item.get('security_name')
        if event_name and event_name.strip() not in (str(symbol.get('name','')).strip(),str(symbol.get('company_name','')).strip()):
            # Code alone is insufficient when an old issuer/security was renamed
            # or a code was reused. Retain it, rather than invent a delisting.
            continue
        active.append(item)
    excluded={(x['ex'],x['code']) for x in active}
    return [x for x in company if (x['ex'],x['code']) not in excluded],active


def build(trade_date,company,output,get_bytes):
    day=Date.fromisoformat(trade_date)
    start=(day-timedelta(days=90)).strftime('%Y%m%d');end=(day+timedelta(days=90)).strftime('%Y%m%d')
    urls={
        'twse_stopped':'https://www.twse.com.tw/rwd/zh/violation/stop?response=json',
        'tpex_stopped':'https://www.tpex.org.tw/www/zh-tw/afterTrading/chtm?'+urlencode({'date':trade_date.replace('-','/'),'response':'json'}),
        'twse_reduction':'https://www.twse.com.tw/exchangeReport/TWTAUU?'+urlencode({'response':'json','startDate':start,'endDate':end}),
        'tpex_reduction':'https://www.tpex.org.tw/www/zh-tw/bulletin/revivt?'+urlencode({'response':'json','startDate':(day-timedelta(days=90)).strftime('%Y/%m/%d'),'endDate':(day+timedelta(days=90)).strftime('%Y/%m/%d')}),
        'twse_delisted':'https://www.twse.com.tw/rwd/zh/company/suspendListing?response=json',
        'tpex_delisted':'https://www.tpex.org.tw/www/zh-tw/company/deListed?'+urlencode({'date':day.year,'reason':-1,'code':'','response':'json'}),
    }
    results={};errors=[];events=[];flags=[];source_log=[]
    def load(pair):
        key,url=pair
        status,raw=get_bytes(url,25)
        (output/f'universe_status_{key}.json').write_bytes(raw)
        data=json.loads(raw.decode('utf-8-sig'))
        if status!=200:raise RuntimeError('HTTP '+str(status))
        state=str(data.get('stat',data.get('status',''))).lower()
        if state not in ('ok','') or not ('tables' in data or 'data' in data):raise RuntimeError('Invalid official response: '+state)
        return key,data
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(load,pair):pair for pair in urls.items()}
        for future,pair in futures.items():
            key,url=pair
            try:
                _,body=future.result();results[key]=body
                source_log.append({'key':key,'url':url,'status':'received'})
            except Exception as exc:
                errors.append({'source':url,'error':str(exc)});source_log.append({'key':key,'url':url,'status':'unavailable'})
    def process(key,fn):
        if key not in results:return
        try:fn(results[key],urls[key])
        except Exception as exc:errors.append({'source':urls[key],'error':str(exc)})
    def tw_stopped(body,url):
        table=body['tables'][0]
        if f'{day.year-1911}年{day.month:02d}月{day.day:02d}日' not in table['title']:
            raise ValueError('Stop table is not for the execution date')
        for row in table['data']:events.append(event('tse',row[0],'trading_suspended',row[4],None,url,row))
    def tp_stopped(body,url):
        if body.get('date')!=trade_date.replace('-',''):raise ValueError('Wrong TPEx status date')
        for table in body['tables']:
            for values in table['data']:
                row=dict(zip(table['fields'],values));code=row['證券代號']
                if row['停止交易']=='Ｙ':
                    item=event('otc',code,'trading_suspended',trade_date,(day+timedelta(days=1)).isoformat(),url,row)
                    item['effective_range_kind']='official daily snapshot coverage; original halt start not supplied'
                    events.append(item)
                flags.append({'ex':'otc','code':code,'altered_trading':row.get('變更交易'),
                              'periodic_matching':row.get('分盤交易'),'managed':row.get('屬管理股票'),
                              'official_source':url,'note':'These flags alone do not exclude a tradable security.'})
    def tw_delisted(body,url):
        for row in body['data']:
            item=event('tse',row[2],'delisted',row[0],None,url,row);item['security_name']=row[1]
            events.append(item)
    def tp_delisted(body,url):
        if str(body.get('date'))!=str(day.year):raise ValueError('Wrong termination year')
        for table in body['tables']:
            if table.get('totalCount',len(table['data']))>len(table['data']):raise ValueError('Incomplete paginated termination table')
            for values in table['data']:
                row=dict(zip(table['fields'],values));item=event('otc',row['股票代號'],'otc_terminated',row['終止上櫃日期'],None,url,row)
                item['security_name']=row['公司名稱'];events.append(item)
    def tp_reduction(body,url):
        for table in body['tables']:
            for row in table['data']:
                plain=html.unescape(re.sub('<[^>]+>',' ',row[-1]))
                match=re.search(r'停止買賣日期\s*[:：]\s*(\d{2,4}/\d{1,2}/\d{1,2})',plain)
                if not match:raise ValueError('Missing reduction halt start for '+str(row[1]))
                events.append(event('otc',row[1],'capital_reduction_suspension',match.group(1),row[0],url,row))
    process('twse_stopped',tw_stopped);process('tpex_stopped',tp_stopped)
    process('twse_delisted',tw_delisted);process('tpex_delisted',tp_delisted)
    process('tpex_reduction',tp_reduction)
    # TWSE reduction reference rows disclose resume dates; details disclose halt starts.
    body=results.get('twse_reduction',{})
    lookup={(x['ex'],x['code']) for x in company}
    tasks=[]
    for row in body.get('data',[]):
        if ('tse',str(row[1]).strip()) not in lookup or parse_date(row[0])<=day:continue
        code,file_date=map(str.strip,row[-1].split(','))
        url='https://www.twse.com.tw/rwd/zh/reducation/TWTAVUDetail?'+urlencode({'STK_NO':code,'FILE_DATE':file_date,'response':'json'})
        tasks.append((code,url,row))
    def detail(task):
        code,url,row=task;status,raw=get_bytes(url,25)
        (output/f'universe_status_reduction_{code}.json').write_bytes(raw)
        data=json.loads(raw.decode('utf-8-sig'))
        if status!=200 or data.get('stat')!='OK':raise ValueError('Reduction details unavailable')
        detail_row=data['data'][0]
        return event('tse',code,'capital_reduction_suspension',detail_row[2],row[0],url,detail_row)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for task,future in [(task,pool.submit(detail,task)) for task in tasks]:
            try:events.append(future.result())
            except Exception as exc:errors.append({'source':task[1],'error':str(exc)})
    eligible,exclusions=active_events(company,events,trade_date)
    flag_map={(f['ex'],f['code']):f for f in flags}
    eligible=[dict(s,trade_flags=flag_map.get((s['ex'],s['code']),{})) for s in eligible]
    result={'trade_date':trade_date,'status':'OFFICIAL_SOURCES_DATE_CHECKED' if not errors else 'INCOMPLETE_OFFICIAL_SOURCES',
            'company_universe_count':len(company),'tradable_universe_count':len(eligible),
            'excluded_symbol_count':len({(x['ex'],x['code']) for x in exclusions}),
            'exclusions':exclusions,'trade_flags':flags,'source_checks':source_log,'errors':errors,
            'limitations':['Reduction reference window is ±90 calendar days; unannounced resume/other intraday temporary halts may require additional official announcement evidence.',
                           'Missing official evidence never becomes an automatic exclusion; incomplete sources retain unproven symbols and mark the denominator unverified.']}
    (output/'company_universe.json').write_text(json.dumps(company,ensure_ascii=False,indent=2))
    (output/'tradable_universe.json').write_text(json.dumps(eligible,ensure_ascii=False,indent=2))
    (output/'universe_exclusions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return eligible,result
