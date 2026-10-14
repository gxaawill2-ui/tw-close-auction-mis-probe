"""Clearly synthetic evidence. Never imported by a live collector."""
from datetime import datetime
from decimal import Decimal
import copy
import freshness as f
from stage3_ticks import packet

DAY='2026-10-14'

def micros(clock,date=DAY):
    return int(datetime.fromisoformat(date+'T'+clock+'+08:00').timestamp()*1_000_000)

def example(code='2330',date=DAY,delayed=False,page_size=2):
    before=micros('13:24:59.900000',date);closing=micros('13:33:00' if delayed else '13:30:00',date)
    ticks=[{'time':closing,'serial':1200,'price':104,'size':5},
       {'time':before,'serial':1100,'price':100,'size':2},
       {'time':micros('13:24:59.100000',date),'serial':1090,'price':99,'size':3},
       {'time':micros('13:24:30',date),'serial':1000,'price':98,'size':10}]
    quote={'date':date,'symbol':code,'type':'EQUITY','exchange':'TWSE','market':'TSE',
      'isClose':True,'isTrial':False,'isDelayedClose':delayed,'lastUpdated':closing,
      'closePrice':104,'closeTime':closing,'lastTrade':{k:ticks[0][k] for k in ('time','serial','price')},
      'total':{'transaction':4,'tradeVolume':20,'time':closing}}
    at=date+'T13:35:00+08:00'
    bundle={'source':'FUGLE','origin_kind':'SYNTHETIC','quote_before':packet(quote,at),
        'pages':[],'quote_after':packet(quote,date+'T13:35:03+08:00')}
    for offset in range(0,len(ticks)+1,page_size):
        data={'date':date,'symbol':code,'type':'EQUITY','exchange':'TWSE','data':ticks[offset:offset+page_size]}
        bundle['pages'].append(packet(data,date+'T13:35:01+08:00',query={'offset':offset,'limit':page_size,'sort':'desc','isTrial':False}))
    row={'code':code,'name':'合成測試','ex':'tse','market':'TWSE','P_before':'100','P_close':'104',
        'P_before_trade_time':'13:24:59','P_close_trade_time':'13:33:00' if delayed else '13:30:00',
        'tail_return_pct':'4','closing_auction_volume':'5','intraday_total_volume':'20',
        'closing_volume_ratio_pct':'25','volume_status':'MIS_EVIDENCE_CONFIRMED','volume_unit':'張',
        'first_seen_at':date+'T13:32:00+08:00','close_received_at':date+'T13:34:00+08:00'}
    return row,bundle

def mutate(event,change):
    import json
    value=json.loads(event['raw']);change(value)
    from stage3_ticks import canonical
    import hashlib
    event['raw']=canonical(value);event['sha256']=hashlib.sha256(event['raw'].encode()).hexdigest()
