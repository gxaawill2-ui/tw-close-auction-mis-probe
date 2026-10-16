"""Private tick audit; export counts/booleans/timestamps, never raw prices or ticks.

Empirical equalities do not release a provider contract or manufacture VERIFIED.
"""
from decimal import Decimal
import hashlib
import json
import freshness as f
from stage3_ticks import canonical, trade_time, identity, integer


def audit(bundle, candidate, date, as_of):
    result = {'symbol':candidate['code'],'exchange':candidate['ex'],'trade_date':date,
        'observed_at':as_of,'scope':'PRIVATE_REAL_TICK_COMPLETENESS_DIAGNOSTICS_ONLY',
        'status':'UNKNOWN','verified_count':0,'p_before_independently_proven':False,
        'p_close_independently_proven':False,'source_contract_released':False,
        'raw_market_data_public':False,'private_evidence_ids':[], 'reasons':[]}
    result['private_manifest_id']=bundle.get('private_manifest_receipt',{}).get('id')
    try:
        if bundle.get('status') != 'COLLECTED_NOT_VALIDATED':
            raise ValueError(bundle.get('error') or 'SOURCE_INCOMPLETE')
        now = f.parsed_time(as_of)
        if not now or now.date().isoformat() != date:
            raise ValueError('AUDIT_DATE_INVALID')
        events = [bundle['quote_before'],*bundle['pages'],bundle['quote_after']]
        result['private_evidence_recoverable_after_job']=all(e.get('private_receipt',{}).get('recoverable_after_job') is True for e in events)
        if not result['private_evidence_recoverable_after_job']:result['reasons'].append('PRIVATE_ARCHIVE_UNAVAILABLE_RUNNER_COPY_ONLY')
        bodies=[]; received=[]
        for event in events:
            if hashlib.sha256(event['raw'].encode()).hexdigest() != event['sha256']:
                raise ValueError('RAW_HASH_MISMATCH')
            began=f.parsed_time(event['requested_at']); got=f.parsed_time(event['received_at']); saved=f.parsed_time(event['persisted_at'])
            if not all((began,got,saved)) or not began<=got<=saved<=now or (got-began).total_seconds()>10:
                raise ValueError('INVALID_OBSERVATION_TIME')
            if event.get('http_status') != 200 or event.get('headers',{}).get('age','0') not in ('0','1','2','3','4','5'):
                raise ValueError('HTTP_STATUS_OR_CACHE_AGE')
            receipt=event.get('private_receipt') or {}
            if receipt.get('sha256')!=event['sha256'] or not f.parsed_time(receipt.get('private_written_at')):
                raise ValueError('PRIVATE_DURABILITY_NOT_PROVEN')
            result['private_evidence_ids'].append(receipt['id'])
            data=json.loads(event['raw'])
            if data.get('date')!=date or data.get('symbol')!=candidate['code'] or data.get('type')!='EQUITY' or data.get('exchange')!={'tse':'TWSE','otc':'TPEx'}[candidate['ex']]:
                raise ValueError('WRONG_DATE_OR_SECURITY')
            bodies.append(data);received.append(got)
        if received!=sorted(received):raise ValueError('RECEIPT_ORDER_INVALID')
        before,after=bodies[0],bodies[-1]
        quote_fields=('lastTrade','total','closePrice','closeTime','lastUpdated','isClose','isTrial','isDelayedClose')
        stable=all(before.get(k)==after.get(k) for k in quote_fields)
        result['quote_bracket_stable']=stable
        offset=0;ticks=[];ended=False
        for event,body in zip(bundle['pages'],bodies[1:-1]):
            q=event['query']; rows=body['data']
            if ended or q.get('offset')!=offset or q.get('sort')!='desc' or q.get('isTrial') is not False or q.get('type') or not integer(q.get('limit')) or not 1<=q['limit']<=200 or not isinstance(rows,list) or len(rows)>q['limit']:
                raise ValueError('PAGE_MISSING_OR_WRONG_SCOPE')
            ended=len(rows)<q['limit']; offset+=len(rows);ticks.extend(rows)
        result['page_count']=len(bundle['pages']); result['row_count']=len(ticks); result['terminal_page_seen']=ended
        if not ticks: raise ValueError('NO_ACTUAL_TICKS')
        serials=set();order=[];same_micros_conflicts=0
        for i,t in enumerate(ticks):
            when=trade_time(t['time']);price=f.decimal_value(t.get('price'))
            if when.date().isoformat()!=date or not '09:00:00'<=when.strftime('%H:%M:%S')<='13:33:00' or not integer(t.get('serial')) or t['serial'] in serials or not integer(t.get('size')) or t['size']<=0 or not price or price<=0 or t.get('isTrial') is True:
                raise ValueError('INVALID_DUPLICATE_TRIAL_OR_OUTSIDE_REGULAR_TICK')
            if when>received[-1]:raise ValueError('FUTURE_TICK')
            serials.add(t['serial']);order.append(t['time'])
            if i and ticks[i-1]['time']==t['time'] and ticks[i-1]['price']!=t['price']:same_micros_conflicts+=1
        result['descending_time_order']=order==sorted(order,reverse=True)
        result['same_microsecond_price_conflicts']=same_micros_conflicts
        sorted_serials=sorted(serials)
        result['serial_noncontiguous_pairs']=sum(b-a>1 for a,b in zip(sorted_serials,sorted_serials[1:]))
        result['serial_scope']='UNSPECIFIED_DO_NOT_ASSUME_PER_SECURITY_CONTIGUOUS'
        total=after.get('total',{}); last=after.get('lastTrade',{})
        result['quote_last_trade_matches_page_head']=identity(last)==identity(ticks[0])
        result['rows_equal_quote_transaction']=ended and len(ticks)==total.get('transaction')
        result['size_sum_equal_quote_volume']=ended and sum(t['size'] for t in ticks)==total.get('tradeVolume')
        pairs=[(new,old) for new,old in zip(ticks,ticks[1:]) if integer(new.get('volume')) and integer(old.get('volume'))]
        result['cumulative_volume_pairs']=len(pairs)
        result['cumulative_volume_chain_matches']=bool(pairs) and all(new['volume']-old['volume']==new['size'] for new,old in pairs)
        cutoff=f.parsed_time(date+'T13:25:00+08:00')
        pre=next((t for t in ticks if trade_time(t['time'])<cutoff),None)
        result['pre_cutoff_tick_present']=pre is not None
        result['pre_tick_time']=trade_time(pre['time']).isoformat() if pre else None
        result['pre_quote_requested_after_cutoff']=f.parsed_time(events[0]['requested_at'])>=cutoff
        result['source_update_after_cutoff']=trade_time(after['lastUpdated'])>=cutoff
        result['source_update_not_after_receipt']=trade_time(after['lastUpdated'])<=received[-1]
        close_clock=trade_time(last['time']).strftime('%H:%M:%S')
        result['close_signal_present']=after.get('isClose') is True
        result['trial_signal_present']=after.get('isTrial') is True
        result['delayed_signal_present']=after.get('isDelayedClose') is True
        result['close_fields_match_actual']=after.get('closeTime')==last['time'] and f.decimal_value(after.get('closePrice'))==f.decimal_value(last.get('price'))
        result['close_classification']=('NORMAL_CLOSE' if close_clock=='13:30:00' and result['close_signal_present'] else
            'DELAYED_CLOSE' if close_clock=='13:33:00' and result['close_signal_present'] and result['delayed_signal_present'] else
            'NO_NEW_CLOSE_TRADE' if close_clock<'13:25:00' and result['close_signal_present'] else 'UNCONFIRMED_CLOSE')
        if not stable:result['reasons'].append('QUOTE_CHANGED_DURING_PAGINATION')
        if not result['descending_time_order']:result['reasons'].append('TICK_TIME_ORDER_INVALID')
        if same_micros_conflicts:result['reasons'].append('SAME_MICROSECOND_ORDER_NOT_DOCUMENTED')
        if not ended:result['reasons'].append('FULL_DAY_COUNT_AND_VOLUME_NOT_PROVEN')
        if ended and not result['rows_equal_quote_transaction']:result['reasons'].append('ROWS_DO_NOT_MATCH_QUOTE_TRANSACTION')
        if ended and not result['size_sum_equal_quote_volume']:result['reasons'].append('SIZE_SUM_DOES_NOT_MATCH_QUOTE_VOLUME')
        if not result['quote_last_trade_matches_page_head']:result['reasons'].append('QUOTE_HEAD_CONFLICT')
        if not pre:result['reasons'].append('PRE_CUTOFF_TICK_NOT_REACHED')
        if result['close_classification']=='UNCONFIRMED_CLOSE':result['reasons'].append('CLOSE_FINALITY_NOT_PROVEN')
        result['reasons'].append('PROVIDER_COMPLETENESS_AND_ORDER_CONTRACT_NOT_RELEASED')
        result['status']='RESEARCH_ONLY' if len(result['reasons'])==1 else 'UNKNOWN'
    except (KeyError,TypeError,ValueError,OverflowError) as exc:
        result['reasons'].append(str(exc) if isinstance(exc,ValueError) and re_safe(str(exc)) else 'MALFORMED_PRIVATE_EVIDENCE')
    return result


def re_safe(value):
    return len(value)<100 and all(c.isupper() or c.isdigit() or c=='_' for c in value)
