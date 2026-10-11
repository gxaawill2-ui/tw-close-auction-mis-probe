"""Independent saved-evidence accumulator. Never fetch MIS or publish candidates."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

TZ = timezone(timedelta(hours=8))
SCOPE = 'TWSE_ORDINARY_EQUITY_REGULAR_BOARD_LOT_1330_1333_V1'
THRESHOLD = {'version': 'closing-share-candidate-v1', 'status': 'PROVISIONAL',
             'minimum_share_pct': 20, 'minimum_relative_multiple': 1.5,
             'minimum_sample_count': 20, 'calibration_evidence': None}


def number(value):
    try:
        n = Decimal(str(value).replace(',', ''))
        return n if n.is_finite() and n >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def timestamp(value):
    try:
        t = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return t if t.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def history_as_of(history, trade_date, as_of):
    """Select latest known revision, then validate; a correction can invalidate a day."""
    latest = {}
    cutoff = timestamp(as_of)
    for entry in history:
        for row in [*(entry.get('change_history') or []), entry]:
            t = timestamp(row.get('generated_at'))
            day = row.get('trade_date', '')
            if not t or not cutoff or t > cutoff or not day or day >= trade_date:
                continue
            if day in latest and t == timestamp(latest[day]['generated_at']) and row.get('closing_turnover_share_pct') != latest[day].get('closing_turnover_share_pct'):
                latest[day] = {**row, 'source_quality': 'CONFLICT'}
            elif day not in latest or t > timestamp(latest[day]['generated_at']):
                latest[day] = row
    return [r for _, r in sorted(latest.items()) if r.get('market_scope') == SCOPE
            and r.get('source_quality') == 'VERIFIED_SAME_SCOPE'
            and r.get('coverage_ratio') == 1 and not r.get('missing_stocks')
            and r.get('official_reconciliation', {}).get('status') == 'MATCH_SAME_SCOPE'
            and number(r.get('closing_turnover_share_pct')) is not None
            and number(r['closing_turnover_share_pct']) <= 100
            and number(r.get('closing_auction_turnover_twd')) is not None
            and number(r.get('daily_turnover_twd')) is not None
            and number(r['daily_turnover_twd']) > 0
            and abs(number(r['closing_turnover_share_pct'])-number(r['closing_auction_turnover_twd'])/number(r['daily_turnover_twd'])*100) < Decimal('.00001')]


def percentile(values, p):
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered)-1)*p
    lower = int(position)
    return ordered[lower]+(ordered[min(lower+1, len(ordered)-1)]-ordered[lower])*(position-lower)


def calculate(date, evidence, history, as_of, market_state='TRADING', threshold=THRESHOLD):
    if not timestamp(as_of) or datetime.fromisoformat(date).date() > timestamp(as_of).astimezone(TZ).date():
        raise ValueError('Invalid trade-date/as-of')
    prior = history_as_of(history, date, as_of)
    values = [float(r['closing_turnover_share_pct']) for r in prior]
    last20, last60 = values[-20:], values[-60:]
    base = median(last20) if len(last20) >= 20 else None
    row = {'schema_version': 1, 'timezone': 'Asia/Taipei', 'trade_date': date,
           'market_scope': SCOPE, 'market_state': market_state,
           'closing_auction_turnover_twd': None, 'daily_turnover_twd': None,
           'closing_turnover_share_pct': None, 'historical_median_share_pct': base,
           'historical_median_60_share_pct': median(last60) if len(last60) >= 60 else None,
           'historical_p90_60_share_pct': percentile(last60, .9) if len(last60) >= 60 else None,
           'relative_multiple': None, 'historical_sample_count': len(last20),
           'historical_sample_count_60': len(last60), 'threshold_version': threshold['version'],
           'threshold_status': threshold['status'], 'is_closing_volume_spike': None,
           'provisional_rule_result': None, 'status': 'UNKNOWN',
           'source_quality': evidence.get('source_quality', 'UNVERIFIED'),
           'missing_stocks': evidence.get('missing_stocks', []),
           'coverage_ratio': evidence.get('coverage_ratio'),
           'official_reconciliation': evidence.get('official_reconciliation', {'status': 'UNKNOWN'}),
           'source_evidence': evidence.get('source_evidence', []),
           'research_observations': evidence.get('research_observations', {}),
           'generated_at': as_of, 'information_available_as_of': as_of,
           'reason': evidence.get('reason', 'INSUFFICIENT_EVIDENCE')}
    if market_state == 'HOLIDAY':
        row.update(status='HOLIDAY', reason='OFFICIAL_CALENDAR_CLOSED')
        return row
    cutoff = timestamp(as_of).astimezone(TZ)
    closing, total = number(evidence.get('closing_auction_turnover_twd')), number(evidence.get('daily_turnover_twd'))
    if cutoff.date().isoformat() == date and cutoff.hour*60+cutoff.minute < 813:
        row['reason'] = 'NOT_FINAL_CLOSE_YET'
        return row
    if evidence.get('market_scope') != SCOPE or row['source_quality'] != 'VERIFIED_SAME_SCOPE' or row['coverage_ratio'] != 1 or row['missing_stocks'] or row['official_reconciliation'].get('status') != 'MATCH_SAME_SCOPE':
        return row
    if not evidence.get('source_evidence') or any(not timestamp(x.get('observed_at')) or timestamp(x['observed_at']) > timestamp(as_of) for x in evidence['source_evidence']):
        row['reason'] = 'UNVERIFIED_SOURCE_AS_OF'
        return row
    if closing is None or total is None or total <= 0 or closing > total:
        row['reason'] = 'INVALID_TURNOVER'
        return row
    share = float(closing/total*100)
    relative = share/base if base and base > 0 else None
    row.update(closing_auction_turnover_twd=str(closing), daily_turnover_twd=str(total),
               closing_turnover_share_pct=share, relative_multiple=relative)
    if relative is None:
        row['reason'] = 'INSUFFICIENT_HISTORICAL_BASELINE'
        return row
    decision = share >= threshold['minimum_share_pct'] and relative >= threshold['minimum_relative_multiple']
    row.update(provisional_rule_result=decision, reason='THRESHOLD_NOT_CALIBRATED')
    # Shipping candidate thresholds never creates a formal yes/no classification.
    if threshold['status'] == 'CALIBRATED' and threshold.get('calibration_evidence'):
        row.update(is_closing_volume_spike=decision, status='VERIFIED', reason='CALIBRATED_SAME_SCOPE_RULE')
    return row


def artifact_evidence(archive, date, official_body, as_of):
    """Reuse exact raw full-pool observations and existing freshness/unit gates."""
    import convergence
    import freshness
    import official_quotes
    import official_retry
    import volume_evidence
    summary, universe, snapshots, probes = official_retry.load_capture(archive)
    if summary.get('trade_date') != date:
        raise ValueError('Artifact trade-date mismatch')
    report = convergence.build_report(date, snapshots, probes, universe, {'checks': []}, close_research_enabled=True)
    lookup = {(s['ex'], s['code']): s for s in universe}
    official, state = official_quotes.parse_quotes('tse', date, official_body)
    pool = [s for s in report['securities'] if s['ex'] == 'tse' and len(s['code']) == 4
            and s['code'].isdigit() and not s['code'].startswith(('0', '91'))]
    if len({s['code'] for s in pool}) != len(pool) or not pool:
        raise ValueError('Invalid saved equity universe')
    observations, missing = [], []
    for stock in pool:
        symbol = lookup[('tse', stock['code'])]
        candidate = {**stock, 'P_close': stock.get('research_p_close'),
                     'P_close_trade_time': stock.get('research_close_trade_time')}
        assessed = volume_evidence.assess(candidate, symbol, snapshots, date, as_of)
        amount = None
        price = number(official.get(stock['code'], {}).get('official_close'))
        if assessed['volume_status'] == 'MIS_EVIDENCE_CONFIRMED' and price is not None and price == number(candidate['P_close']):
            amount = number(assessed['closing_auction_volume'])*1000*price
        elif candidate.get('P_close_trade_time') and candidate['P_close_trade_time'] < '13:25:00':
            # Zero requires two adopted fresh close observations after 13:33,
            # unchanged counter since the two pre-auction observations, no simulation.
            pre = stock.get('pre_pair_evidence') or {}
            before = [volume_evidence.locate(pre.get(k), symbol, snapshots, date, as_of) for k in ('A', 'B')]
            after = [volume_evidence.locate(r, symbol, snapshots, date, as_of) for r in (stock.get('close_research_evidence') or {}).get('pair', [])]
            if all(before) and len(after) == 2 and all(after):
                values = [number(r.get('v')) for r in before+after]
                if all(v is not None for v in values) and len(set(values)) == 1 and all(r.get('ts') == '0' and r.get('t') == candidate['P_close_trade_time'] and freshness.parsed_time(r['server_time']).astimezone(TZ).strftime('%H:%M:%S') >= '13:33:00' for r in after) and price is not None and price == number(candidate['P_close']):
                    amount = Decimal(0)
        if amount is None:
            missing.append({'code': stock['code'], 'market': 'TWSE', 'reason': assessed['volume_evidence'].get('reason') or 'OFFICIAL_PRICE_OR_ZERO_UNVERIFIED'})
        else:
            observations.append({'code': stock['code'], 'market': 'TWSE', 'turnover_twd': str(amount),
                                 'official_close': str(price), 'shares_per_trading_unit': 1000,
                                 'auction_time': candidate.get('P_close_trade_time'), 'unit': 'TWD',
                                 'evidence': assessed['volume_evidence']})
    # Saved and current MI_INDEX versions have different block-trade notes; both mix non-regular trades.
    # A price/volume daily table is therefore NOT a same-scope denominator.
    return {'market_scope': SCOPE, 'source_quality': 'PARTIAL_SAVED_MIS; DENOMINATOR_SCOPE_UNVERIFIED',
            'coverage_ratio': len(observations)/len(pool), 'missing_stocks': missing,
            'official_reconciliation': {'status': 'DENOMINATOR_SCOPE_MISMATCH', 'official_close_table_status': state,
                'note': 'MI_INDEX includes odd-lot and after-hours fixed-price; not a regular-board-lot denominator. Full ordinary-equity identity coverage also requires reconciliation.'},
            'source_evidence': [{'source': 'SAVED_MIS_ARTIFACT', 'sha256': hashlib.sha256(archive).hexdigest(), 'observed_at': as_of}],
            'research_observations': {'saved_twse_pool_count': len(pool), 'verified_closing_stocks': len(observations),
                'verified_closing_subtotal_twd': str(sum((Decimal(r['turnover_twd']) for r in observations), Decimal(0))),
                'is_complete_market_total': False, 'stocks': observations},
            'reason': 'REGULAR_BOARD_LOT_DENOMINATOR_NOT_VERIFIED'}


def save(root, row):
    base = root/'state/market-closing-volume'
    base.mkdir(parents=True, exist_ok=True)
    path = base/(row['trade_date']+'.json')
    row = copy_for_publication(row)
    research = row.get('research_observations', {})
    if research.get('stocks'):
        proof = {'trade_date': row['trade_date'], 'source_evidence': row['source_evidence'],
                 'research_observations': research}
        raw = (json.dumps(proof, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
        digest = hashlib.sha256(raw).hexdigest()
        proof_name = 'evidence/'+row['trade_date']+'-'+digest[:16]+'.json'
        proof_path = base/proof_name
        proof_path.parent.mkdir(exist_ok=True)
        proof_path.write_bytes(raw)
        row['research_observations'] = {k: v for k, v in research.items() if k != 'stocks'}
        row['research_observations'].update(evidence_path='state/market-closing-volume/'+proof_name, evidence_sha256=digest)
    if path.exists():
        old = json.loads(path.read_text())
        if timestamp(old['generated_at']) > timestamp(row['generated_at']):
            raise ValueError('Refuse older overwrite')
        row['change_history'] = old.get('change_history', [])+[{k: v for k, v in old.items() if k != 'change_history'}]
    path.write_text(json.dumps(row, ensure_ascii=False, indent=2)+'\n')


def copy_for_publication(row):
    # No caller mutation; immutable proof versions and compact public daily summary.
    return json.loads(json.dumps(row))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--date', required=True)
    p.add_argument('--archive', type=Path)
    p.add_argument('--official', type=Path)
    p.add_argument('--root', type=Path, default=Path('.'))
    args = p.parse_args()
    as_of = datetime.now(TZ).isoformat()
    calendar_path = args.root/'state/calendars'/(args.date[:4]+'.json')
    cal = json.loads(calendar_path.read_text()) if calendar_path.exists() else {}
    day = datetime.fromisoformat(args.date)
    closed = cal.get('status') == 'OFFICIAL_ANNUAL_CALENDAR' and (day.weekday() >= 5 or args.date in cal.get('closed_dates', []))
    evidence = {'reason': 'SAVED_CAPTURE_OR_OFFICIAL_SAME_SCOPE_DATA_UNAVAILABLE'}
    if args.archive and args.official and not closed:
        evidence = artifact_evidence(args.archive.read_bytes(), args.date, json.loads(args.official.read_text()), as_of)
        evidence['source_evidence'].append({'source_url': 'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date='+args.date.replace('-', '')+'&type=ALLBUT0999&response=json', 'sha256': hashlib.sha256(args.official.read_bytes()).hexdigest(), 'observed_at': as_of, 'retrieval_mode': 'READ_EXISTING_SAVED_OFFICIAL_FILE; NO_NEW_REQUEST'})
    as_of = datetime.now(TZ).isoformat()
    history = [json.loads(f.read_text()) for f in (args.root/'state/market-closing-volume').glob('20??-??-??.json')]
    row = calculate(args.date, evidence, history, as_of, 'HOLIDAY' if closed else 'TRADING' if cal else 'UNKNOWN')
    save(args.root, row)
    print(json.dumps({k: v for k, v in row.items() if k not in ('research_observations', 'change_history')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
