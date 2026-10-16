"""Safe field semantics review over privately restored raw; no market access."""
import json
from collections import defaultdict
from stage3_ticks import trade_time,last_pre_group
from stage6_evidence import diagnose
import freshness as f


def review(bundle,reference,date,as_of):
    result=diagnose(bundle,reference,date,as_of)
    quotes=[json.loads(bundle[k]['raw']) for k in ('quote_before','quote_after')]
    ticks=[t for p in bundle['pages'] for t in json.loads(p['raw'])['data']]
    last=quotes[-1]['lastTrade'];matching=[t for t in ticks if t['serial']==last['serial']]
    clock=lambda value:trade_time(value).isoformat() if value is not None else None
    result.update(scope='STAGE7_ARCHIVED_REAL_FIELD_REVIEW_NOT_VERIFIED',
        field_times={
            'quote.lastTrade.time':clock(last.get('time')),
            'quote.closeTime':clock(quotes[-1].get('closeTime')),
            'quote.lastUpdated':clock(quotes[-1].get('lastUpdated')),
            'quote.total.time':clock(quotes[-1].get('total',{}).get('time')),
            'trades.same_serial.time':[clock(t['time']) for t in matching]},
        same_serial_time_deltas_seconds=[(trade_time(t['time'])-trade_time(last['time'])).total_seconds() for t in matching],
        quote_flags={key:quotes[-1].get(key) for key in ('isTrial','isClose','isDelayedClose')},
        http_cache_age=[e.get('headers',{}).get('age') for e in [bundle['quote_before'],*bundle['pages'],bundle['quote_after']]],
        original_request_times=[e['requested_at'] for e in [bundle['quote_before'],*bundle['pages'],bundle['quote_after']]],
        original_response_times=[e['received_at'] for e in [bundle['quote_before'],*bundle['pages'],bundle['quote_after']]],
        time_offset_applied=False,serial_used_as_order=False,
        root_cause='UNCONFIRMED_PROVIDER_CONTRACT_OR_IMPLEMENTATION',
        official_close_match_is_not_pre_cutoff_completeness=True)
    groups=defaultdict(list)
    for t in ticks:groups[t['time']].append(t)
    result['multiple_price_timestamp_groups']=sum(len({f.decimal_value(t['price']) for t in group})>1 for group in groups.values())
    result['latest_pre_price_count']=len({f.decimal_value(t['price']) for t in last_pre_group(ticks,f.parsed_time(date+'T13:25:00+08:00'))})
    return result
