"""Safe diagnostics from already-private evidence, never a live release policy."""
import hashlib
import json
from datetime import datetime, timedelta
import freshness as f
from stage3_ticks import last_pre_group, trade_time, identity, canonical
from stage5_audit import audit


def diagnose(bundle, reference, date, as_of):
    result = audit(bundle, reference, date, as_of)
    result['scope'] = 'STAGE6_PRIVATE_BOUNDARY_DIAGNOSTICS_NOT_VERIFIED'
    result['analysis_performed_at'] = datetime.now(f.TZ).isoformat()
    result['historical_publication_time_inferred'] = False
    events = [bundle['quote_before'], *bundle['pages'], bundle['quote_after']]
    if any(hashlib.sha256(e['raw'].encode()).hexdigest() != e['sha256'] for e in events):
        raise ValueError('RAW_EVIDENCE_HASH_MISMATCH')
    ticks = [t for e in bundle['pages'] for t in json.loads(e['raw'])['data']]
    quote = json.loads(bundle['quote_after']['raw'])
    cutoff = f.parsed_time(date+'T13:25:00+08:00')
    group = last_pre_group(ticks, cutoff)
    prices = {f.decimal_value(t['price']) for t in group}
    result['latest_pre_group_count'] = len(group)
    result['latest_pre_group_price_unique'] = len(prices) == 1
    result['latest_pre_group_all_prices_match_mis'] = bool(prices) and prices == {f.decimal_value(reference['P_before'])}
    result['latest_pre_group_time_matches_mis'] = bool(group) and trade_time(group[0]['time']).strftime('%H:%M:%S') == reference['P_before_trade_time']
    result['serial_used_to_resolve_ambiguous_price'] = False
    result['earlier_ties_do_not_determine_cutoff_price'] = bool(group) and any(
        a['time'] == b['time'] < group[0]['time'] and a['price'] != b['price']
        for a,b in zip(ticks,ticks[1:]))
    last = quote['lastTrade']
    close_ticks = [t for t in ticks if trade_time(t['time']).strftime('%H:%M:%S') == reference['P_close_trade_time']
                   and f.decimal_value(t['price']) == f.decimal_value(reference['P_close'])]
    result['trades_contain_mis_close'] = bool(close_ticks)
    result['quote_close_price_matches_mis'] = f.decimal_value(quote.get('closePrice')) == f.decimal_value(reference['P_close'])
    result['quote_last_time_matches_mis'] = trade_time(last['time']).strftime('%H:%M:%S') == reference['P_close_trade_time']
    result['quote_three_minutes_earlier_than_matching_close_tick'] = bool(close_ticks) and any(
        trade_time(t['time'])-trade_time(last['time']) == timedelta(minutes=3) for t in close_ticks)
    result['same_serial_quote_trade_time_conflict'] = any(t['serial'] == last['serial'] and t['time'] != last['time'] for t in ticks)
    result['cumulative_volume_selects_last_pre_empirically'] = bool(group) and all(
        isinstance(t.get('volume'), int) and not isinstance(t['volume'],bool) for t in group) and len({t['volume'] for t in group}) == len(group)
    # Cumulative-volume/serial correlations are observations, not tie-break rules.
    result['provider_completeness_proven'] = False
    result['raw_provider_values_exported'] = False
    result['verified_count'] = 0
    return result
