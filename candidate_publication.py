"""Permanent public daily research JSON. No MIS calls; immutable live prices.

Publish only completed saved captures. Contents API CAS, bounded retries and
price fingerprints make repeated publication idempotent and date isolated.
Postmarket checks annotate the original list; they never remove/reprice it.
"""
import base64
import copy
import hashlib
import io
import json
import os
import re
import tempfile
import time
import urllib.error
import zipfile
from decimal import Decimal
from pathlib import Path

import capture_completion
import convergence
import freshness
import official_quotes
import official_retry
import volume_evidence

VERSION = 'DAILY_RESEARCH_PUBLICATION_V1'
PRICE_FIELDS = ('code','name','market','P_before','P_close','P_before_trade_time','P_close_trade_time',
                'tail_return_pct','P_before_convergence_type','P_close_convergence_type','confidence_level','validated')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(payload):
    value = {'trade_date': payload['trade_date'], 'generated_at': payload['generated_at'],
             'capture_run_id': payload['capture_run_id'], 'source_artifact': payload['source_artifact'],
             'coverage': payload['coverage'], 'candidates': [{k: r[k] for k in PRICE_FIELDS} for r in payload['candidate_list']]}
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate(payload, date):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) or payload.get('trade_date') != date:
        raise ValueError('PUBLICATION_WRONG_DATE')
    generated = freshness.parsed_time(payload.get('generated_at'))
    if not generated or generated.astimezone(freshness.TZ).date().isoformat() != date:
        raise ValueError('PUBLICATION_INVALID_GENERATED_AT')
    if payload.get('status') != 'RESEARCH_ONLY' or payload.get('validated') is not False or payload.get('completion_status') not in ('COMPLETE','PARTIAL'):
        raise ValueError('PUBLICATION_INCOMPLETE_RESEARCH')
    coverage = payload.get('coverage') or {}
    total, calculable, unknown = (coverage.get(k) for k in ('tradable_universe','research_calculable','unknown'))
    if any(type(x) is not int or x < 0 for x in (total,calculable,unknown)) or total <= 0 or calculable+unknown != total:
        raise ValueError('PUBLICATION_INVALID_COVERAGE')
    rows = payload.get('candidate_list')
    if not isinstance(rows, list) or payload.get('candidate_count') != len(rows) or len(rows) > calculable:
        raise ValueError('PUBLICATION_COUNT_MISMATCH')
    keys = set()
    for row in rows:
        key = (row.get('market'),row.get('code'))
        if key in keys or row.get('validated') is not False or row.get('P_close_convergence_type') not in ('AB_converged','AC_converged','BC_converged','A_1330_fresh_candidate'):
            raise ValueError('PUBLICATION_INVALID_OR_DUPLICATE_CANDIDATE')
        keys.add(key)
        pre, close = (freshness.decimal_value(row.get(k)) for k in ('P_before','P_close'))
        if pre is None or close is None or pre <= 0 or close <= 0:
            raise ValueError('PUBLICATION_INVALID_PRICE')
        percentage = (close/pre-1)*100
        if abs(percentage) < 3 or percentage != freshness.decimal_value(row.get('tail_return_pct')):
            raise ValueError('PUBLICATION_INVALID_TAIL_RETURN')
        if not isinstance(row.get('P_before_trade_time'),str) or not ('09:00:00' <= row['P_before_trade_time'] < '13:25:00'):
            raise ValueError('PUBLICATION_INVALID_PRE_TIME')
        if row.get('volume_unit') != '張':
            raise ValueError('PUBLICATION_INVALID_VOLUME_UNIT')
        volume_keys = ('closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct')
        if row.get('volume_status') == 'MIS_EVIDENCE_CONFIRMED':
            closing,total_volume,ratio = (freshness.decimal_value(row.get(k)) for k in volume_keys)
            if closing is None or total_volume is None or total_volume <= 0 or not 0 < closing <= total_volume or ratio != closing/total_volume*100:
                raise ValueError('PUBLICATION_INVALID_VOLUME_RATIO')
        elif any(row.get(k) is not None for k in volume_keys):
            raise ValueError('PUBLICATION_UNVERIFIED_VOLUME_MUST_BE_NULL')
    if payload.get('price_fingerprint') != fingerprint(payload):
        raise ValueError('PUBLICATION_PRICE_FINGERPRINT_MISMATCH')


def build(output, date, run_id, source_mode='LIVE', archive_sha=None):
    summary = json.loads((output/'run_summary.json').read_text())
    if summary.get('trade_date') != date:
        raise ValueError('SAVED_CAPTURE_WRONG_DATE')
    completion = capture_completion.classify(output, summary)
    if not completion['core_capture_complete']:
        raise ValueError('SAVED_CAPTURE_INCOMPLETE_OR_CORRUPT:'+canonical(completion['errors']))
    # Loader only selects the known raw filenames, and validates duplicates.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for path in output.iterdir():
            if path.is_file() and (path.name.endswith('_raw.jsonl') or path.name in ('run_summary.json','universe.json')):
                archive.writestr(path.name, path.read_bytes())
    _, universe, snapshots, probes = official_retry.load_capture(buffer.getvalue())
    live = json.loads((output/'live_research_summary.json').read_text())
    generated = live.get('generated_at')
    stamp = freshness.parsed_time(generated)
    if not stamp or stamp.astimezone(freshness.TZ).date().isoformat() != date:
        raise ValueError('LIVE_GENERATED_AT_MISSING_OR_WRONG_DATE')
    # No future raw observation can enter a historical live publication.
    def at_time(records):
        return [r for r in records if freshness.parsed_time(r.get('received_at'))
                and freshness.parsed_time(r['received_at']) <= stamp]
    snapshots = [{'records': at_time(s['records'])} for s in snapshots]
    probes = at_time(probes)
    selected = convergence.build_report(date, snapshots, probes, universe, {'checks': []})
    original = json.loads((output/'research_candidates.json').read_text())
    replay = convergence.research_candidates(selected)
    if replay != original:
        raise ValueError('SAVED_LIVE_CANDIDATES_DIFFER_FROM_ASOF_REPLAY')
    lookup = {(s['ex'],s['code']):s for s in universe}
    rows = []
    for row in original['candidates']:
        security = lookup[row['ex'],row['code']]
        volume = volume_evidence.assess(row, security, snapshots, date, generated)
        rows.append({**{k: row[k] for k in PRICE_FIELDS if k != 'tail_return_pct'},
             'ex': row['ex'], 'tail_return_pct': str((Decimal(row['P_close'])/Decimal(row['P_before'])-1)*100),
             'price_research_status': 'RESEARCH_ONLY', **volume,
             'official_price_result': 'PENDING', 'postmarket_verified_at': None})
    rows.sort(key=lambda r: (-abs(Decimal(r['tail_return_pct'])),r['market'],r['code']))
    result = {'schema_version': VERSION, 'trade_date': date, 'generated_at': generated,
         'published_at': None, 'updated_at': None, 'publication_mode': source_mode,
         'capture_run_id': str(run_id), 'source_artifact': 'mis-probe-'+str(run_id),
         'source_artifact_sha256': archive_sha, 'status': 'RESEARCH_ONLY','validated': False,
         'completion_status': 'PARTIAL' if completion['capture_outcome']=='CAPTURE_PARTIAL' else 'COMPLETE',
         'capture_outcome': completion['capture_outcome'],
         'coverage': {'tradable_universe': len(universe),'research_calculable': selected['research_calculable_count'],
                      'unknown':len(universe)-selected['research_calculable_count']},
         'candidate_count':len(rows),'candidate_list':rows,
         'publication_code_sha':os.getenv('GITHUB_SHA'),
         'price_limitation':'P_before is converged MIS research evidence, without independent official pre-13:25 validation.'}
    result['price_fingerprint'] = fingerprint(result)
    validate(result,date)
    return result


def from_archive(saved, date, run_id):
    """Safe extraction of whitelisted flat results, never overwrites evidence."""
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        with zipfile.ZipFile(io.BytesIO(saved)) as archive:
            for name in archive.namelist():
                path = Path(name)
                if path.parent.as_posix() not in ('.','results') or path.suffix not in ('.json','.jsonl','.csv'):
                    continue
                dest = output/path.name
                data = archive.read(name)
                if dest.exists() and dest.read_bytes() != data:
                    raise ValueError('CONFLICTING_ARCHIVE_FILES')
                dest.write_bytes(data)
        return build(output,date,run_id,'OFFLINE_SAVED_CAPTURE',hashlib.sha256(saved).hexdigest())


def enrich(payload, official, checked_at, validation_run_id):
    """Only same-date official numbers; candidate prices/list remain immutable."""
    date = payload['trade_date']; validate(payload,date)
    if official.get('trade_date') != date:
        raise ValueError('OFFICIAL_ENRICHMENT_WRONG_DATE')
    checked = freshness.parsed_time(checked_at)
    if not checked or checked.astimezone(freshness.TZ).date().isoformat() != date:
        raise ValueError('OFFICIAL_ENRICHMENT_INVALID_TIME')
    result = copy.deepcopy(payload)
    sources = {s['ex']:s for s in official.get('sources',[])}
    by_key = {(r['ex'],r['code']):r for r in official.get('checks',[])}
    for row in result['candidate_list']:
        source = sources.get(row['ex'],{})
        off = by_key.get((row['ex'],row['code']),{})
        ready = source.get('status') == 'AVAILABLE_SAME_DATE' and source.get('response_date') == date.replace('-','') and off.get('official_date') == date
        price = freshness.decimal_value(off.get('official_close')) if ready else None
        row['official_price_result'] = 'PENDING' if not ready else 'UNAVAILABLE' if price is None else 'MATCH' if price == Decimal(row['P_close']) else 'MISMATCH'
        row['official_close'] = str(price) if price is not None else None
        row['postmarket_verified_at'] = checked_at
        row['volume_evidence']['official_daily_shares'] = off.get('official_volume_shares') if ready else None
        row['volume_evidence']['official_daily_volume_scope'] = 'DIFFERENT_SCOPE; never substituted for MIS intraday volume'
    result['postmarket_verified_at'] = checked_at
    result['official_validation_run_id'] = str(validation_run_id)
    if fingerprint(result) != payload['price_fingerprint']:
        raise AssertionError('Official annotation changed live prices')
    validate(result,date)
    return result


def put(payload, api, now, attempts=3):
    date = payload['trade_date']; validate(payload,date)
    path = 'state/candidates/'+date+'.json'
    last_error = None
    for attempt in range(attempts):
        try:
            stored = api('contents/'+path+'?ref=main')
            current = json.loads(base64.b64decode(stored['content'])) if stored else None
            result = copy.deepcopy(payload)
            if current:
                validate(current,date)
                if current['price_fingerprint'] != result['price_fingerprint']:
                    raise ValueError('IMMUTABLE_LIVE_PRICE_CONFLICT')
                # A retried live publication must not erase postmarket checks.
                if (current.get('postmarket_verified_at') or '') > (result.get('postmarket_verified_at') or ''):
                    for key in ('postmarket_verified_at','official_validation_run_id'):
                        if key in current:result[key]=current[key]
                    prior={(r['ex'],r['code']):r for r in current['candidate_list']}
                    for row in result['candidate_list']:
                        old=prior[row['ex'],row['code']]
                        for key in ('official_price_result','official_close','postmarket_verified_at'):
                            if key in old:row[key]=old[key]
                        for key in ('official_daily_shares','official_daily_volume_scope'):
                            if key in old['volume_evidence']:row['volume_evidence'][key]=old['volume_evidence'][key]
                ignore={'published_at','updated_at','publication_code_sha','source_artifact_sha256','publication_mode'}
                if canonical({k:v for k,v in current.items() if k not in ignore}) == canonical({k:v for k,v in result.items() if k not in ignore}):
                    return {'status':'PUBLISHED','idempotent':True,'path':path,'price_fingerprint':result['price_fingerprint'],'published_at':current['published_at']}
            result['published_at'] = current.get('published_at') if current else now()
            result['updated_at'] = now()
            request={'message':'Publish daily MIS research candidates '+date,'branch':'main',
                     'content':base64.b64encode((json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()).decode()}
            if stored:request['sha']=stored['sha']
            written=api('contents/'+path,'PUT',request)
            return {'status':'PUBLISHED','idempotent':False,'path':path,'price_fingerprint':result['price_fingerprint'],
                    'published_at':result['published_at'],'commit_sha':(written.get('commit') or {}).get('sha')}
        except (urllib.error.URLError,TimeoutError,ConnectionError) as exc:
            if isinstance(exc,urllib.error.HTTPError) and exc.code not in (409,422,429,500,502,503,504):
                raise
            last_error=exc
            if attempt+1<attempts:time.sleep(.3*(2**attempt))
    raise RuntimeError('CANDIDATE_PUBLICATION_FAILED:'+type(last_error).__name__+':'+str(last_error))


def publish_live(output,date,run_id,control,probe):
    payload=build(output,date,run_id)
    result=put(payload,control.api,probe.iso)
    (output/'candidate_publication.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
