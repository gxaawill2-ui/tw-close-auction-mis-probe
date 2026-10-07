"""Offline RESEARCH_ONLY comparison; reads saved bytes and never calls MIS."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import convergence
import official_quotes
import official_retry
from freshness import decimal_value


def write_csv(path, rows, columns):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows({k: row.get(k) for k in columns} for row in rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--official-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    date = '2026-10-07'
    archive = args.capture.read_bytes()
    digest = hashlib.sha256(archive).hexdigest()
    capture, universe, snapshots, probes = official_retry.load_capture(archive)
    assert capture['trade_date'] == date
    validation = json.loads((args.official_dir/'official_validation.json').read_text())
    assert validation['trade_date'] == date
    assert all(s['status'] == 'AVAILABLE_SAME_DATE' for s in validation['sources'])
    markets = {}
    source_hashes = {}
    for ex in ('tse', 'otc'):
        raw = (args.official_dir/f'official_close_{ex}.json').read_bytes()
        markets[ex], state = official_quotes.parse_quotes(ex, date, json.loads(raw.decode('utf-8-sig')))
        assert state == 'AVAILABLE_SAME_DATE'
        source_hashes[ex] = hashlib.sha256(raw).hexdigest()
    report = convergence.build_report(date, snapshots, probes, universe, {'checks': []})
    assert report['p_before_converged_count'] == 1947
    assert report['p_close_converged_count'] == 0
    before = {(r['ex'], r['code']): r for r in report['securities']}
    close_a = {}
    for snapshot in snapshots:
        for record in snapshot['records']:
            if record.get('phase') != 'close_reference_A' or record.get('error'):
                continue
            for item in (record.get('response') or {}).get('msgArray', []):
                key = item.get('ex'), item.get('c')
                # A single saved A observation per symbol; conflicting duplicates abort.
                if key in close_a:
                    assert close_a[key][1] == item, f'Conflicting close A duplicates: {key}'
                close_a[key] = record, item
    checks, candidates = [], []
    for symbol in universe:
        key = symbol['ex'], symbol['code']
        record, item = close_a.get(key, ({}, {}))
        trade = item.get('trade') or {}
        mis = decimal_value(trade.get('z'))
        official = decimal_value(markets[symbol['ex']].get(symbol['code'], {}).get('official_close'))
        result = ('UNAVAILABLE' if mis is None or official is None else
                  'MATCH' if mis == official else 'MISMATCH')
        t = trade.get('t')
        classification = ('NO_CLOSE_A_RECORD' if not item else
                          'NO_MIS_NESTED_TRADE_PRICE' if mis is None else
                          'NO_OFFICIAL_CLOSE' if official is None else
                          'NORMAL_CLOSE_TRADE' if t == '13:30:00' else
                          'AFTER_1330_TRADE' if isinstance(t, str) and t > '13:30:00' else
                          'EARLIER_LAST_TRADE')
        row = {**symbol, 'MIS_trade_t': t, 'MIS_trade_z': trade.get('z'),
               'official_close': str(official) if official is not None else None,
               'difference': str(mis-official) if mis is not None and official is not None else None,
               'price_result': result, 'classification': classification,
               'observed_at': record.get('received_at'), 'MIS_date': item.get('d'),
               'status': 'RESEARCH_ONLY', 'p_close_validated': False}
        checks.append(row)
        pre = before[key]
        pb = decimal_value(pre['p_before'])
        if pre['p_before_convergence_status'] != 'p_before_converged_candidate' or result != 'MATCH' or pb is None or pb <= 0:
            continue
        change = official/pb - 1
        if abs(change) >= Decimal('0.03'):
            candidates.append({**symbol, 'P_before': str(pb),
                'P_before_trade_time': pre['p_before_trade_time'], 'close_reference_A': str(mis),
                'official_close': str(official), 'tail_return': str(change),
                'tail_return_pct': str(change*100),
                'P_before_convergence_type': pre['pre_reference_classification'],
                'official_MATCH_status': result, 'status': 'RESEARCH_ONLY', 'p_close_validated': False})
    counts = Counter(r['price_result'] for r in checks)
    comparable = counts['MATCH'] + counts['MISMATCH']
    mismatches = [r for r in checks if r['price_result'] == 'MISMATCH']
    summary = {'trade_date': date, 'status': 'RESEARCH_ONLY', 'capture_run_id': '37574207304',
        'validation_run_id': '37597653369', 'capture_sha256': digest, 'official_sha256': source_hashes,
        'universe': len(universe),
        'close_reference_A_records': sum((s['ex'], s['code']) in close_a for s in universe),
        'extra_close_reference_A_records_outside_universe': len(set(close_a)-set(before)),
        'total_comparable': comparable, 'MATCH': counts['MATCH'], 'MISMATCH': counts['MISMATCH'],
        'UNAVAILABLE': counts['UNAVAILABLE'],
        'match_rate': counts['MATCH']/comparable if comparable else None,
        'match_rate_denominator': 'MATCH + MISMATCH',
        'by_market': {ex: dict(Counter(r['price_result'] for r in checks if r['ex'] == ex)) for ex in ('tse','otc')},
        'unavailable': [r for r in checks if r['price_result'] == 'UNAVAILABLE'],
        'mismatches': mismatches, 'shadow_candidate_count': len(candidates),
        'p_before_converged_count': report['p_before_converged_count'],
        'p_close_converged_count': report['p_close_converged_count'], 'p_close_validated': False}
    args.output.mkdir(parents=True, exist_ok=True)
    columns = ('code','name','market','MIS_trade_t','MIS_trade_z','official_close','difference',
               'price_result','classification','observed_at','MIS_date','status','p_close_validated')
    write_csv(args.output/'close_reference_A_comparison_2026-10-07.csv', checks, columns)
    write_csv(args.output/'close_reference_A_mismatches_2026-10-07.csv', mismatches, columns)
    (args.output/'close_reference_A_comparison_2026-10-07.json').write_text(
        json.dumps({'summary':summary,'checks':checks}, ensure_ascii=False, indent=2))
    (args.output/'close_reference_A_summary_2026-10-07.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    candidate_columns = ('code','name','market','P_before','P_before_trade_time','close_reference_A',
                         'official_close','tail_return','tail_return_pct','P_before_convergence_type',
                         'official_MATCH_status','status','p_close_validated')
    write_csv(args.output/'shadow_candidates_2026-10-07.csv', candidates, candidate_columns)
    (args.output/'shadow_candidates_2026-10-07.json').write_text(json.dumps(
        {'trade_date':date,'status':'RESEARCH_ONLY','count':len(candidates),'candidates':candidates},
        ensure_ascii=False, indent=2))
    assert hashlib.sha256(args.capture.read_bytes()).hexdigest() == digest
    print(json.dumps({'summary':summary, 'candidates':candidates}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
