"""Independent tick evidence inspection, with an explicit source release policy.

Fugle documents fields, not the identity between Trades rows, summed size and
Quote.transaction/volume. That contract is deliberately unreleased until tested.
Synthetic fixtures may exercise success; they NEVER authorize live VERIFIED.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import freshness as f


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class SourceContract:
    name: str = 'FUGLE_V1_DOCUMENTED_FIELDS'
    source: str = 'FUGLE'
    rows_equal_transaction_count: bool = False
    size_sum_equal_regular_volume: bool = False
    serial_scope: str = 'UNSPECIFIED'
    time_unit: str = 'MICROSECONDS'
    independently_delivered: bool = False
    live_release: bool = False


LIVE_CONTRACT = SourceContract()
TEST_CONTRACT = SourceContract('SYNTHETIC_FUGLE_V1', rows_equal_transaction_count=True,
    size_sum_equal_regular_volume=True, independently_delivered=True)


def trade_time(value):
    # Reject seconds/ms instead of silently treating them as microseconds.
    if isinstance(value, bool) or not isinstance(value, int) or not 10**15 <= value < 10**17:
        raise ValueError('INVALID_MICROSECOND_TIME')
    seconds, micros = divmod(value, 1_000_000)
    return datetime.fromtimestamp(seconds, f.TZ) + timedelta(microseconds=micros)


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def identity(tick):
    return tick['time'], tick['serial'], f.decimal_value(tick['price'])


def packet(body, received_at, requested_at=None, query=None, headers=None):
    """Canonical fixture/import envelope. An envelope is not a trusted proof."""
    raw = canonical(body)
    return {'raw': raw, 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'received_at': received_at, 'requested_at': requested_at or received_at,
            'query': query or {}, 'headers': headers or {}, 'http_status': 200}


def load_bundle(path):
    """Resolve raw evidence only beneath its manifest directory; verify bytes."""
    path = Path(path).resolve()
    bundle = json.loads(path.read_text())
    for event in [bundle['quote_before'], *bundle['pages'], bundle['quote_after']]:
        raw_path = (path.parent / event['raw_path']).resolve()
        if path.parent not in raw_path.parents:
            raise ValueError('RAW_PATH_OUTSIDE_EVIDENCE_DIRECTORY')
        raw = raw_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != event['sha256']:
            raise ValueError('RAW_EVIDENCE_HASH_MISMATCH')
        event['raw'] = raw.decode('utf8')
    return bundle


def inspect(bundle, candidate, date, as_of, *, mode='LIVE', contract=LIVE_CONTRACT):
    reasons = []
    result = {'source': contract.source, 'contract': contract.name, 'mode': mode,
              'P_before_independently_verified': False, 'P_close_verified': False,
              'pre_evidence_complete': False, 'close_evidence_complete': False,
              'synthetic_pre_passed': False, 'synthetic_close_passed': False,
              'pre_tick': None, 'close_tick': None, 'reasons': reasons,
              'acquired_at': None, 'source_contract_live_released': contract.live_release,
              'serial_gap_count': 0, 'validated': False}
    if mode not in ('LIVE', 'SYNTHETIC', 'OFFLINE_REPLAY'):
        reasons.append('INVALID_MODE'); return result
    if not bundle:
        reasons.append('NO_INDEPENDENT_TICK_EVIDENCE'); return result
    if bundle.get('source') != contract.source:
        reasons.append('WRONG_SOURCE'); return result
    if mode == 'LIVE' and bundle.get('origin_kind') == 'SYNTHETIC':
        reasons.append('SYNTHETIC_EVIDENCE_IN_LIVE_MODE'); return result
    if mode == 'SYNTHETIC' and bundle.get('origin_kind') != 'SYNTHETIC':
        reasons.append('NON_SYNTHETIC_EVIDENCE_IN_TEST_MODE'); return result
    now = f.parsed_time(as_of)
    if not now or now.astimezone(f.TZ).date().isoformat() != date:
        reasons.append('WRONG_ASSESSMENT_DATE'); return result
    acquired = []

    def body(event):
        raw = event['raw']
        if hashlib.sha256(raw.encode()).hexdigest() != event['sha256']:
            raise ValueError('RAW_EVIDENCE_HASH_MISMATCH')
        request, receive = f.parsed_time(event['requested_at']), f.parsed_time(event['received_at'])
        if (not request or not receive or request > receive or receive > now or
                request.astimezone(f.TZ).date().isoformat() != date or event.get('http_status') != 200):
            raise ValueError('INVALID_OBSERVATION_TIME_OR_HTTP')
        if (receive-request).total_seconds() > 10:
            raise ValueError('NETWORK_RESPONSE_EXCEEDS_BUDGET')
        age = event.get('headers', {}).get('age')
        if age is not None and (not str(age).isdigit() or int(age) > 5):
            raise ValueError('STALE_HTTP_CACHE')
        acquired.append(receive)
        data = json.loads(raw)
        if (data.get('date') != date or data.get('symbol') != candidate['code'] or
            data.get('type') != 'EQUITY' or data.get('exchange') != {'tse':'TWSE','otc':'TPEx'}[candidate['ex']]):
            raise ValueError('DATE_SYMBOL_OR_MARKET_MISMATCH')
        return data

    try:
        before = body(bundle['quote_before'])
        ticks = []; offset = 0; ended = False
        for page in bundle['pages']:
            data = body(page); query = page['query']
            if (ended or query.get('offset') != offset or query.get('sort') != 'desc' or
                    query.get('isTrial') is not False or query.get('type') == 'oddlot' or
                    not integer(query.get('limit')) or not 1 <= query['limit'] <= 500):
                raise ValueError('MISSING_PAGE_OR_WRONG_QUERY_SCOPE')
            rows = data['data']
            if not isinstance(rows, list) or len(rows) > query['limit']:
                raise ValueError('INVALID_PAGE_SIZE')
            ended = len(rows) < query['limit']; offset += len(rows); ticks.extend(rows)
        after = body(bundle['quote_after'])
        if not ended:
            raise ValueError('TICK_HISTORY_TRUNCATED_OR_NO_TERMINAL_PAGE')
        if not acquired or acquired != sorted(acquired):
            raise ValueError('OUT_OF_ORDER_OBSERVATION_RECEIPTS')
        result['acquired_at'] = max(acquired).isoformat()
        fields = ('lastTrade','total','isClose','isDelayedClose','isTrial','closePrice','closeTime','lastUpdated')
        if any(before.get(k) != after.get(k) for k in fields):
            raise ValueError('QUOTE_CHANGED_DURING_PAGINATION')
        total = after.get('total') or {}
        if not integer(total.get('transaction')) or not integer(total.get('tradeVolume')):
            raise ValueError('MISSING_INDEPENDENT_COUNT_OR_VOLUME')
        if not ticks:
            raise ValueError('NO_ACTUAL_TRADES')
        serials = set(); times = []; sizes = []
        for tick in ticks:
            when = trade_time(tick['time']); price = f.decimal_value(tick.get('price'))
            if (when.date().isoformat() != date or when.strftime('%H:%M:%S') < '09:00:00' or not integer(tick.get('serial')) or
                    tick['serial'] in serials or not integer(tick.get('size')) or tick['size'] <= 0 or
                    not price or price <= 0 or tick.get('isTrial') is True):
                raise ValueError('INVALID_DUPLICATE_OR_TRIAL_TICK')
            serials.add(tick['serial']); times.append((tick['time'],tick['serial'])); sizes.append(tick['size'])
        if times != sorted(times, reverse=True):
            raise ValueError('TICK_ORDER_OR_SAME_SECOND_CONFLICT')
        ordered_serials = sorted(serials)
        result['serial_gap_count'] = sum(b-a > 1 for a,b in zip(ordered_serials, ordered_serials[1:]))
        if contract.serial_scope == 'PER_SECURITY_CONTIGUOUS' and result['serial_gap_count']:
            raise ValueError('PER_SECURITY_SERIAL_GAP')
        # Do not invent per-security contiguity for global/unspecified serials.
        result['serial_scope'] = contract.serial_scope
        if len(ticks) != total['transaction']:
            raise ValueError('TICK_COUNT_DOES_NOT_MATCH_QUOTE_TRANSACTION')
        if sum(sizes) != total['tradeVolume']:
            raise ValueError('TICK_VOLUME_DOES_NOT_MATCH_QUOTE_VOLUME')
        last = after['lastTrade']
        if identity(last) != identity(ticks[0]):
            raise ValueError('LATEST_TICK_DOES_NOT_MATCH_QUOTE')
        if trade_time(after['lastUpdated']) < trade_time(last['time']):
            raise ValueError('SOURCE_UPDATE_PRECEDES_ACTUAL_TRADE')
        cutoff = f.parsed_time(date+'T13:25:00+08:00')
        pre = next((t for t in ticks if trade_time(t['time']) < cutoff), None)
        if not pre:
            raise ValueError('NO_TRADE_BEFORE_CUTOFF')
        result['pre_tick'] = pre
        if (f.decimal_value(pre['price']) != f.decimal_value(candidate.get('P_before')) or
            trade_time(pre['time']).strftime('%H:%M:%S') != candidate.get('P_before_trade_time')):
            raise ValueError('MIS_INDEPENDENT_PRE_CONFLICT')
        semantic_ok = contract.rows_equal_transaction_count and contract.size_sum_equal_regular_volume
        result['pre_evidence_complete'] = bool(semantic_ok)
        if mode == 'SYNTHETIC':
            result['synthetic_pre_passed'] = result['pre_evidence_complete']
        elif mode == 'LIVE' and contract.live_release and contract.independently_delivered:
            result['P_before_independently_verified'] = result['pre_evidence_complete']
        if not semantic_ok:
            reasons.append('SOURCE_COUNT_AND_VOLUME_SEMANTICS_NOT_CONFIRMED')
        if after.get('isTrial') is True or after.get('isClose') is not True:
            raise ValueError('TRIAL_OR_CLOSE_NOT_FINISHED')
        close_time = trade_time(after['closeTime'])
        if f.decimal_value(after['closePrice']) != f.decimal_value(last['price']) or after['closeTime'] != last['time']:
            raise ValueError('CLOSE_FIELDS_CONFLICT')
        clock = close_time.strftime('%H:%M:%S')
        result['close_classification'] = ('NORMAL_CLOSE' if clock == '13:30:00' else
            'DELAYED_CLOSE' if clock == '13:33:00' and after.get('isDelayedClose') is True else
            'NO_NEW_CLOSE_TRADE' if clock < '13:25:00' else 'UNSUPPORTED_CLOSE_TIME')
        if result['close_classification'] == 'UNSUPPORTED_CLOSE_TIME':
            raise ValueError('UNSUPPORTED_CLOSE_TIME')
        result['close_tick'] = last
        if (f.decimal_value(last['price']) != f.decimal_value(candidate.get('P_close')) or
                clock != candidate.get('P_close_trade_time')):
            raise ValueError('MIS_INDEPENDENT_CLOSE_CONFLICT')
        if semantic_ok and f.decimal_value(candidate.get('intraday_total_volume')) is not None:
            if f.decimal_value(candidate['intraday_total_volume']) != Decimal(total['tradeVolume']):
                raise ValueError('MIS_INDEPENDENT_VOLUME_CONFLICT')
            expected_closing = Decimal(0) if result['close_classification']=='NO_NEW_CLOSE_TRADE' else Decimal(last.get('size',ticks[0]['size']))
            if f.decimal_value(candidate.get('closing_auction_volume')) != expected_closing:
                raise ValueError('MIS_INDEPENDENT_CLOSING_VOLUME_CONFLICT')
        result['close_evidence_complete'] = bool(semantic_ok)
        if mode == 'SYNTHETIC':
            result['synthetic_pre_passed'] = result['pre_evidence_complete']
            result['synthetic_close_passed'] = result['close_evidence_complete']
        elif mode == 'LIVE' and contract.live_release and contract.independently_delivered:
            result['P_before_independently_verified'] = result['pre_evidence_complete']
            result['P_close_verified'] = result['close_evidence_complete']
        else:
            reasons.append('LIVE_SOURCE_CONTRACT_NOT_RELEASED')
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        reasons.append(str(exc) if isinstance(exc, ValueError) else 'MALFORMED_EVIDENCE')
    result['validated'] = result['P_before_independently_verified'] and result['P_close_verified'] and not reasons
    result['evidence_digest'] = hashlib.sha256(canonical(bundle).encode()).hexdigest()
    return result
