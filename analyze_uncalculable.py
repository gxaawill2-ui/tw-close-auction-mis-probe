"""Read-only, offline diagnostics. Official daily data NEVER enters live replay.

Absent raw fields are MISSING; explicit null remains null. Terminal fetch errors
do not erase earlier HTTP attempts. This tool does not import any network client.
"""
import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import convergence
import freshness
import official_quotes
import official_retry

VERSION = 'UNCALCULABLE_EVIDENCE_V1'
DATE = '2026-10-08'
AS_OF = DATE+'T13:35:00+08:00'
CODES = '1583 4581 5906 8488 9937 2073 2718 3332 4183 5276 5520 5703 6198 6212 6236 6242 6661 6662 6680 6762 6904 7820 8067 8455 9949'.split()
MISSING = 'MISSING'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def field(obj, *keys):
    for key in keys:
        if not isinstance(obj, dict) or key not in obj:
            return MISSING
        obj = obj[key]
    return obj


def as_of_records(records, as_of):
    cutoff = freshness.parsed_time(as_of)
    if cutoff is None:
        raise ValueError('as_of must include timezone')
    # Fail closed: undated or cross-date records are not silently replayed.
    result = []
    for record in records:
        request = freshness.parsed_time(record.get('requested_at'))
        received = freshness.parsed_time(record.get('received_at'))
        if request and received and request <= received <= cutoff and request.date() == cutoff.date():
            result.append(record)
    return result


def replay(date, snapshots, probes, universe, as_of):
    saved = [{'records': as_of_records(s['records'], as_of)} for s in snapshots]
    sampled = as_of_records(probes, as_of)
    return convergence.build_report(date, saved, sampled, universe, {'checks': []})


def identity_diagnostic(item):
    """Describe evidence, not a replacement eligibility gate."""
    trade = item.get('trade')
    if not isinstance(trade, dict) or not trade:
        return ('NO_NESTED_TRADE_ZERO_REPORTED_VOLUME' if freshness.decimal_value(item.get('v')) == 0
                else 'NO_NESTED_TRADE_VOLUME_UNKNOWN_OR_POSITIVE')
    if not isinstance(trade.get('t'), str) or not convergence.clock(trade['t']):
        return 'NESTED_TRADE_TIME_MISSING_OR_INVALID'
    price = freshness.decimal_value(trade.get('z'))
    if price is None or price <= 0:
        return 'NESTED_TRADE_PRICE_MISSING_OR_INVALID'
    if trade['t'] >= '13:25:00':
        return 'TRADE_NOT_BEFORE_1325'
    return 'VALID_PRE_IDENTITY_CANDIDATE_REQUIRES_FRESH_CONVERGENCE'


def timeline_entry(record, symbol, provenance, source, line, source_hash, scope='selected_result', index=None):
    body = record.get('response') or {}
    items = [x for x in body.get('msgArray', []) if isinstance(x, dict)
             and (x.get('ex'), x.get('c')) == (symbol['ex'], symbol['code'])]
    item = items[0] if items else {}
    row = freshness.observations([{**record, 'symbols': [symbol]}], DATE)[0]
    row['duplicate'] = len(items) > 1
    kind = 'close' if str(record.get('phase', '')).startswith('close') else 'pre'
    rejection = convergence.rejection(row, DATE, kind)
    attempt_error = record.get('error') or ''
    actually_sent = attempt_error not in ('CAPTURE_DEADLINE_NO_REQUEST', 'REFERENCE_NOT_SAMPLED', 'SCHEDULER_LATE_NO_REQUEST')
    return {**{k: symbol[k] for k in ('code', 'name', 'market', 'ex')},
            'phase': field(record, 'phase'), 'planned_at': field(record, 'planned_at'),
            'request_started_at': field(record, 'requested_at'), 'received_at': field(record, 'received_at'),
            'queryTime.sysTime': field(body, 'queryTime', 'sysTime'),
            'queryTime.sysDate': field(body, 'queryTime', 'sysDate'), 'cachedAlive': field(body, 'cachedAlive'),
            **{'trade.'+k: field(item, 'trade', k) for k in ('t', 'z', 'v', 'ft')},
            **{'outer_'+k: field(item, k) for k in ('t', 'z', 'pz')},
            **{k: field(item, k) for k in ('v', 'tv', 's', 'd', 'io', 'o', 'h', 'l')},
            'HTTP_status': field(record, 'http_status'), 'error': field(record, 'error'),
            'missing': not bool(items), 'nested_trade_present': 'trade' in item,
            'HTTP_request_sent': actually_sent, 'scope': scope, 'attempt_index': index,
            'batch_no': field(record, 'batch_no'), 'expected_count': len(record.get('symbols', [])),
            'batch_cache_key_sha256': digest('|'.join(s['ex']+'_'+s['code']+'.tw' for s in record.get('symbols', [])).encode()),
            'server_age_at_receive_ms': row['server_age_at_receive_ms'],
            'freshness_status': 'FRESH' if freshness.fresh_candidate(row, DATE) else 'NOT_FRESH_OR_UNAVAILABLE',
            'rejection_reason': rejection, 'identity_diagnostic': identity_diagnostic(item) if item else 'NO_RESPONSE_ITEM',
            'source_file': source, 'source_line': line, 'source_line_sha256': source_hash,
            'raw_item': item if item else MISSING, **provenance}


def record_timeline(record, symbol, provenance, source, line, source_hash):
    """One final result plus DIFFERENT actual attempts, never double-count success."""
    output = [timeline_entry(record, symbol, provenance, source, line, source_hash)]
    for index, attempt in enumerate(record.get('attempts', [])):
        if all(attempt.get(k) == record.get(k) for k in ('requested_at', 'received_at', 'error', 'http_status')):
            output[0]['attempt_index'] = index
            continue
        merged = {**record, **attempt}
        if not merged.get('response') and attempt.get('raw_body'):
            try:
                merged['response'] = json.loads(attempt['raw_body'])
            except json.JSONDecodeError:
                pass
        output.append(timeline_entry(merged, symbol, provenance, source, line, source_hash, 'HTTP_attempt', index))
    return output


def classify_symbol(symbol, timeline, security, official):
    selected = [r for r in timeline if r['scope'] == 'selected_result']
    pre = [r for r in selected if r['phase'] in ('pre_reference_A', 'pre_reference_B', 'pre_reference_C', 'pre_targeted_retry')
           and r['HTTP_status'] == 200 and not r['error']]
    fresh = [r for r in pre if r['freshness_status'] == 'FRESH']
    daily = official.get('official_row', {})
    volume = freshness.decimal_value(daily.get('成交股數'))
    count = freshness.decimal_value(daily.get('成交筆數'))
    amount = freshness.decimal_value(daily.get('成交金額') if symbol['ex'] == 'tse' else daily.get('成交金額(元)'))
    closes = [r for r in selected if r['phase'] in ('close_reference_A', 'close_reference_B', 'close_reference_C')
              and r['nested_trade_present'] and r['HTTP_status'] == 200 and not r['error']]
    all_absent_zero = bool(fresh) and all(not r['nested_trade_present'] and freshness.decimal_value(r['v']) == 0 for r in fresh)
    if not all_absent_zero:
        cause = 'EVIDENCE_REQUIRES_INDIVIDUAL_REVIEW'
    elif volume == count == amount == 0:
        cause = 'OFFICIAL_ZERO_DAILY_ACTIVITY_NO_PRE_TRADE'
    elif closes:
        cause = 'NO_OBSERVED_PRE_TRADE_FIRST_SAVED_TRADE_AT_CLOSE'
    elif volume is not None and volume > 0:
        cause = 'DAILY_ACTIVITY_WITHOUT_REGULAR_SESSION_TRADE_EVIDENCE'
    else:
        cause = 'PRE_TRADE_ABSENT_OFFICIAL_ACTIVITY_UNKNOWN'
    official_close = freshness.decimal_value(official.get('official_close'))
    return {**{k: symbol[k] for k in ('code', 'name', 'market', 'ex')},
        'primary_root_cause': cause, 'recovery': '無法安全恢復' if cause != 'DAILY_ACTIVITY_WITHOUT_REGULAR_SESSION_TRADE_EVIDENCE' else '資料來源限制',
        'live_as_of_classification': 'NO_OBSERVED_PRE_TRADE / UNKNOWN' if all_absent_zero else 'UNKNOWN',
        'all_saved_pre_responses_missing_nested_trade_and_v_zero': all_absent_zero,
        'MIS_returned': bool(pre), 'successful_pre_observations': len(pre),
        'fresh_pre_observations': len(fresh), 'stale_pre_observations': len(pre)-len(fresh),
        'pre_A_B_C_missing_trade': all(not r['nested_trade_present'] for r in pre if r['phase'] != 'pre_targeted_retry'),
        'trade_t_present': any(r['trade.t'] != MISSING for r in pre),
        'trade_z_present': any(r['trade.z'] != MISSING for r in pre),
        'pre_1325_valid_identity_count': sum(r['identity_diagnostic'].startswith('VALID_PRE_IDENTITY') for r in pre),
        'pre_identity_contradiction': False if all_absent_zero else 'NOT_DETERMINED',
        'parser_false_rejection': False if all_absent_zero else 'NOT_DETERMINED',
        'deadline_affected_secondary': any(r['error'] == 'CAPTURE_DEADLINE_NO_REQUEST' for r in selected),
        'deadline_primary_cause': False if all_absent_zero else 'NOT_DETERMINED',
        'successful_targeted_retries': sum(r['phase'] == 'pre_targeted_retry' for r in pre),
        'failed_HTTP_attempts': sum(r['scope'] == 'HTTP_attempt' and bool(r['error']) for r in timeline),
        'P_before': security['p_before'], 'P_before_converged': security['pre_pair_evidence']['converged'],
        'P_close': security['research_p_close'], 'P_close_convergence_type': security['P_close_convergence_type'],
        'first_saved_regular_trade_time': min((r['trade.t'] for r in closes), default=MISSING),
        'official_daily_shares': str(volume) if volume is not None else MISSING,
        'official_daily_amount': str(amount) if amount is not None else MISSING,
        'official_daily_trade_count': str(count) if count is not None else MISSING,
        'official_close': str(official_close) if official_close is not None else MISSING,
        'official_row': daily, 'official_usage': 'POSTMARKET_DIAGNOSTIC_ONLY_NOT_LIVE_INPUT',
        'special_status': symbol.get('trade_flags', {}),
        'raw_io_values': sorted({r['io'] for r in selected if r['io'] != MISSING}),
        'raw_io_interpretation': 'UNVERIFIED; do not infer halt or RR semantics',
        'research_calculable': security['research_calculable'], 'validated': False,
        'alternative_source_status': 'FUTURE_LIVE_TEST_REQUIRED; no timestamped pre-13:25 alternative saved',
        'limitations': 'Positive daily volume does not locate trades before 13:25. Odd-lot explanation is consistent, not individually proven; do not substitute odd-lot for regular-session baseline.'}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def write_csv(path, rows):
    fields = list(rows[0])
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) or v is None else v
                         for k, v in row.items()} for row in rows)


def analyze(capture_zip, official_dir, output, code_sha):
    protected = {p: digest(p.read_bytes()) for p in [capture_zip, *official_dir.glob('*.json')]}
    summary, universe, snapshots, probes = official_retry.load_capture(capture_zip.read_bytes())
    if summary['trade_date'] != DATE:
        raise ValueError('Capture date mismatch')
    validation = json.loads((official_dir/'validation_summary.json').read_text())
    if validation['source_capture_run_id'] != '37730234383' or validation['source_capture_artifact_id'] != 11530906396:
        raise ValueError('Official source provenance mismatch')
    provenance = {'capture_run_id': 37730234383, 'capture_artifact_id': 11530906396,
        'capture_artifact': 'mis-probe-37730234383', 'capture_archive_sha256': protected[capture_zip],
        'trade_date': DATE, 'as_of': AS_OF, 'diagnostic_version': VERSION,
        'code_commit_sha': code_sha, 'code_sha_semantics': 'live/replay implementation base; diagnostic file hash identifies this uncommitted report generator',
        'diagnostic_script_sha256': digest(Path(__file__).read_bytes()),
        'capture_commit_sha': '2dd62b249a181d7045c957f0c33501cc574723cd',
        'official_validation_run_id': 37742790398, 'official_checked_at': validation['checked_at'],
        'analyzed_at': datetime.now(freshness.TZ).isoformat(timespec='milliseconds')}
    # NO official numbers or MATCH flags are passed to the replay.
    report = replay(DATE, snapshots, probes, universe, AS_OF)
    candidates = convergence.research_candidates(report)
    markets = {}; sources = []
    for ex in ('tse', 'otc'):
        path = official_dir/f'official_close_{ex}.json'
        body = json.loads(path.read_text()); quotes, state = official_quotes.parse_quotes(ex, DATE, body)
        if state != 'AVAILABLE_SAME_DATE':
            raise ValueError('Official date/status failed: '+state)
        markets[ex] = quotes
        sources.append({'file': path.name, 'sha256': protected[path], 'url': official_quotes.quote_url(ex, DATE),
                        'response_date': body['date'], 'table_notes': [t.get('notes') for t in body['tables']]})
    securities = {s['code']: s for s in report['securities']}
    symbols = [next(s for s in universe if s['code'] == code) for code in CODES]
    timeline = []
    with zipfile.ZipFile(capture_zip) as archive:
        original = json.loads(archive.read('results/research_candidates.json'))
        for name in archive.namelist():
            if not name.endswith('_raw.jsonl') or not name.startswith('results/'):
                continue
            for line_no, line in enumerate(archive.read(name).splitlines(), 1):
                record = json.loads(line)
                expected = {(s['ex'], s['code']) for s in record.get('symbols', [])}
                for symbol in symbols:
                    if (symbol['ex'], symbol['code']) in expected:
                        timeline += record_timeline(record, symbol, provenance, name, line_no, digest(line))
        if candidates != original:
            raise AssertionError('As-of replay changed saved candidates')
    assert report['p_before_converged_count'] == report['research_calculable_count'] == 1943
    assert len(universe) == 1968 and candidates['candidate_count'] == 7
    assert {s['code'] for s in report['securities'] if not s['research_calculable']} == set(CODES)
    root_rows = []
    for symbol in symbols:
        code = symbol['code']; selected = [r for r in timeline if r['code'] == code]
        root_rows.append({**classify_symbol(symbol, selected, securities[code], markets[symbol['ex']].get(code, {})), **provenance})
        phases = {r['phase'] for r in selected}
        for phase, absence in (('close_reference_C', 'NOT_SCHEDULED'), ('per_second_probe', 'NOT_SAMPLED')):
            if phase not in phases:
                empty = {key: MISSING for key in timeline[0]}
                empty.update({**provenance, **{k: symbol[k] for k in ('code', 'name', 'market', 'ex')},
                              'phase': phase, 'scope': 'coverage_note', 'error': absence,
                              'HTTP_request_sent': False, 'missing': MISSING,
                              'source_file': 'results/'+('probe_raw.jsonl' if phase == 'per_second_probe' else phase+'_raw.jsonl')})
                timeline.append(empty)
    counts = Counter(r['primary_root_cause'] for r in root_rows)
    assert counts == {'OFFICIAL_ZERO_DAILY_ACTIVITY_NO_PRE_TRADE': 9,
                      'NO_OBSERVED_PRE_TRADE_FIRST_SAVED_TRADE_AT_CLOSE': 3,
                      'DAILY_ACTIVITY_WITHOUT_REGULAR_SESSION_TRADE_EVIDENCE': 13}
    recovery = {**provenance, 'data_sources': sources,
        'baseline': {'P_before_converged': 1943, 'calculable': 1943, 'uncalculable': 25, 'candidates': 7},
        'after_safe_analysis': {'P_before_converged': 1943, 'calculable': 1943, 'uncalculable': 25, 'candidates': 7},
        'coverage_percent': str(Decimal(1943)/Decimal(1968)*100), 'recovered_count': 0,
        'recovered_symbols': [], 'future_live_only_not_counted_as_recovered': [],
        'primary_counts': dict(counts), 'deadline_secondary_affected_count': 25,
        'pre_C_stale_secondary_affected_count': sum(r['stale_pre_observations'] > 0 for r in root_rows),
        'retry_round_metrics': summary['snapshots'].get('targeted_retry_rounds', []),
        'original_seven_exactly_unchanged': True, 'future_information_used_for_live': False,
        'official_prices_used_for_live': False, 'original_artifact_modified': False,
        'live_rules_modified': False, 'validated': False,
        'candidate_regression': original['candidates'],
        'decision': 'Do not fabricate a pre-13:25 price; more identical fresh responses cannot create an absent trade.',
        'symbols': [{'code': r['code'], 'as_of_status': 'UNKNOWN', 'safe_recovery': False,
                     'primary_root_cause': r['primary_root_cause']} for r in root_rows]}
    for path, before in protected.items():
        if digest(path.read_bytes()) != before:
            raise AssertionError('Source evidence changed')
    output.mkdir(parents=True, exist_ok=True)
    timeline.sort(key=lambda r: (CODES.index(r['code']), r['request_started_at'] if r['request_started_at'] != MISSING else 'ZZ', r['scope']))
    write_csv(output/'25_symbols_raw_timeline.csv', timeline)
    write_csv(output/'25_symbols_root_cause.csv', root_rows)
    write_json(output/'25_symbols_root_cause.json', {'provenance': provenance, 'data_sources': sources, 'symbols': root_rows})
    write_json(output/'25_symbols_recovery_replay.json', recovery)
    print(json.dumps({k: recovery[k] for k in ('primary_counts', 'recovered_count', 'coverage_percent', 'original_seven_exactly_unchanged')}, ensure_ascii=False))
    return recovery


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-zip', type=Path, required=True)
    parser.add_argument('--official-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--code-sha', required=True)
    args = parser.parse_args()
    analyze(args.capture_zip, args.official_dir, args.output, args.code_sha)
