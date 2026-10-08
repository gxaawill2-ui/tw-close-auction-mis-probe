"""Independent volume research gates; never change price/candidate selection."""
import json
from decimal import Decimal
from pathlib import Path

import freshness as f

CONTRACT = json.loads((Path(__file__).parent/'volume_contract.json').read_text())


def to_lots(value, unit, shares_per_lot=1000):
    number = f.decimal_value(value)
    if number is None or number < 0 or shares_per_lot <= 0:
        return None
    if unit == 'SHARES':
        return number / Decimal(shares_per_lot)
    if unit == 'TRADING_UNIT':
        return number if shares_per_lot == 1000 else number*Decimal(shares_per_lot)/1000
    return None


def locate(evidence, symbol, snapshots, date, as_of):
    """Find the actual raw item by adopted timestamps, never the latest cache."""
    if not evidence:
        return None
    cutoff = f.parsed_time(as_of)
    for snapshot in snapshots:
        for record in snapshot['records']:
            if any(record.get(k) != evidence.get(k) for k in ('phase', 'requested_at', 'received_at')):
                continue
            received = f.parsed_time(record.get('received_at'))
            if not cutoff or not received or received > cutoff:
                continue
            items = [i for i in (record.get('response') or {}).get('msgArray', [])
                     if (i.get('ex'), i.get('c')) == (symbol['ex'], symbol['code'])]
            if len(items) != 1:
                return None
            item = items[0]
            row = f.observations([{**record, 'symbols': [symbol]}], date)[0]
            if record.get('http_status') != 200 or not f.fresh_candidate(row, date):
                return None
            trade = item.get('trade') or {}
            if trade.get('t') != evidence.get('trade_t') or f.decimal_value(trade.get('z')) != f.decimal_value(evidence.get('trade_z')):
                return None
            return {'phase': record['phase'], 'request_started_at': record['requested_at'],
                    'received_at': record['received_at'], 'server_time': row['server_time'],
                    'queryTime': (record.get('response') or {}).get('queryTime'),
                    'cachedAlive': (record.get('response') or {}).get('cachedAlive'),
                    'trade': trade, **{k: item.get(k) for k in ('t','z','pz','v','tv','s','ts','d')},
                    'market_channel': symbol['ex']+'_'+symbol['code']+'.tw'}
    return None


def assess(candidate, symbol, snapshots, date, as_of, contract=CONTRACT):
    result = {'closing_auction_volume': None, 'intraday_total_volume': None,
              'closing_volume_ratio_pct': None, 'volume_unit': '張',
              'volume_status': 'UNVERIFIED', 'closing_volume_status': 'UNVERIFIED',
              'intraday_volume_status': 'UNVERIFIED', 'volume_source': 'MIS_REGULAR_SAVED_OBSERVATIONS',
              'volume_verified_at': None,
              'volume_evidence': {'contract_version': contract['version'], 'source_unit': contract['source_unit'],
                    'independent_official_volume_validation': False,
                    'scope': 'General board-lot market, opening to final 13:30/13:33 auction; excludes postmarket/odd-lot',
                    'reason': 'INSUFFICIENT_VOLUME_EVIDENCE'}}
    proof = result['volume_evidence']
    pre = candidate.get('pre_pair_evidence') or {}
    close = candidate.get('close_research_evidence') or {}
    before = [locate(pre.get(k), symbol, snapshots, date, as_of) for k in ('A','B')]
    after = [locate(r, symbol, snapshots, date, as_of) for r in close.get('pair') or []]
    proof.update(pre_observations=before, close_observations=after)
    if len(after) != 2 or not all(before) or not all(after):
        return result
    if any(pair[0]['received_at'] >= pair[1]['received_at'] or pair[0]['server_time'] >= pair[1]['server_time'] for pair in (before,after)):
        proof['reason'] = 'NEEDS_TWO_DISTINCT_FRESH_OBSERVATIONS'
        return result
    code = symbol['code']
    if contract.get('status') != 'OFFICIAL_FRONTEND_MAPPING_CONFIRMED' or symbol['ex'] not in contract['supported_ex'] or len(code) != 4 or not code.isdigit() or code.startswith(('0','91')):
        proof['reason'] = 'UNVERIFIED_UNIT_OR_SECURITY_SCOPE'
        return result
    if candidate['P_close_trade_time'] not in ('13:30:00','13:33:00'):
        proof['reason'] = 'UNVERIFIED_FINAL_AUCTION_TIME'
        return result
    before_values = [f.decimal_value(r['v']) for r in before]
    final_values = [f.decimal_value(r['v']) for r in after]
    last_values = [f.decimal_value(r['trade'].get('v')) for r in after]
    tv_values = [f.decimal_value(r['tv']) for r in after]
    s_values = [f.decimal_value(r['s']) for r in after]
    proof.update(observed_pre_v=[r['v'] for r in before], observed_close_v=[r['v'] for r in after],
                 observed_trade_v=[r['trade'].get('v') for r in after], observed_tv=[r['tv'] for r in after],
                 observed_s=[r['s'] for r in after])
    values = [*before_values, *final_values, *last_values, *tv_values, *s_values]
    if any(v is None or v < 0 or v != v.to_integral_value() for v in values):
        proof['reason'] = 'MISSING_OR_INVALID_VOLUME_FIELD'
        return result
    # Same identity/counter on both pre and both close observations. Actual outer
    # matching fields, not simulation or a nested fallback for an older trade.
    if before_values[0] != before_values[1] or final_values[0] != final_values[1] or any(r['ts'] != '0' or r['t'] != candidate['P_close_trade_time'] or f.decimal_value(r['z']) != f.decimal_value(candidate['P_close']) for r in after):
        proof['reason'] = 'INCONSISTENT_OR_SIMULATED_VOLUME'
        return result
    delta = final_values[1] - before_values[1]
    proof['cumulative_delta_raw'] = str(delta)
    if not (delta > 0 and all(v == delta for v in [*last_values, *tv_values, *s_values]) and final_values[1] > 0):
        proof['reason'] = 'TRADE_TV_S_CUMULATIVE_DELTA_DISAGREE'
        return result
    closing = to_lots(delta, contract['source_unit'], contract['shares_per_trading_unit'])
    total = to_lots(final_values[1], contract['source_unit'], contract['shares_per_trading_unit'])
    if closing is None or total is None or closing > total or total <= 0:
        proof['reason'] = 'INVALID_VOLUME_CONVERSION'
        return result
    proof.update(reason=None, agreement='trade.v = tv = s = V_close - V_pre_auction in two fresh adopted close observations',
                 unit_contract_verified_at=contract['verified_at'])
    result.update(closing_auction_volume=str(closing), intraday_total_volume=str(total),
                  closing_volume_ratio_pct=str(closing/total*100), volume_status='MIS_EVIDENCE_CONFIRMED',
                  closing_volume_status='MIS_EVIDENCE_CONFIRMED', intraday_volume_status='MIS_EVIDENCE_CONFIRMED',
                  volume_verified_at=max(f.parsed_time(as_of),f.parsed_time(contract['verified_at'])).isoformat())
    return result
