"""Execution outcome only. Never changes price, freshness or candidate rules.

PARTIAL exits zero only when every mandatory phase executed, raw evidence is
readable/same-date and derived research outputs are saved. Missing symbols,
probe errors and unresolved prices remain explicit warnings. No usable response
in a mandatory phase, skipped phases, corrupt files or wrong dates fail closed.
GitHub upload success is a separate workflow step; upload failure fails the job.
"""
import json
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))


def classify(output, summary):
    errors, warnings, phases = [], [], {}
    date = summary.get('trade_date')
    def read(name, lines=False):
        try:
            text = (output/name).read_text(encoding='utf-8')
            return [json.loads(s) for s in text.splitlines() if s.strip()] if lines else json.loads(text)
        except (OSError, ValueError) as exc:
            errors.append({'reason':'MISSING_OR_CORRUPT_FILE','file':name,'error':str(exc)})
            return None
    try:
        datetime.strptime(date, '%Y-%m-%d')
        if datetime.fromisoformat(summary['runner_started_at']).astimezone(TZ).date().isoformat() != date:
            errors.append({'reason':'WRONG_TRADE_DATE'})
    except (KeyError, TypeError, ValueError):
        errors.append({'reason':'INVALID_TRADE_DATE_OR_START'})
    universe = read('universe.json')
    expected = {(s['ex'], s['code']) for s in universe or []}
    if not expected or len(expected) != summary.get('universe_count'):
        errors.append({'reason':'INVALID_UNIVERSE'})
    required = ['preclose','pre_reference_A','pre_reference_B','close_reference_A','close_reference_B']
    if summary.get('pre_reference_C_enabled'): required.append('pre_reference_C')
    if summary.get('close_reference_C_enabled'): required.append('close_reference_C')
    for phase in required:
        rows = read(phase+'_raw.jsonl', True)
        metrics = summary.get('snapshots', {}).get(phase, {})
        if phase == 'close_reference_C' and not rows and metrics.get('status') in ('NOT_REQUIRED','BLOCKED_HTTP_403_429'):
            if metrics['status'].startswith('BLOCKED'):
                warnings.append({'phase':phase,'reason':'TARGETED_C_BLOCKED_HTTP_403_429'})
            continue
        usable, seen, phase_errors = 0, set(), []
        for row in rows or []:
            if row.get('phase') != phase:
                errors.append({'phase':phase,'reason':'RAW_PHASE_MISMATCH'})
            for stamp in ('planned_at','requested_at','received_at'):
                try:
                    stamp_date=datetime.fromisoformat(row[stamp]).astimezone(TZ).date().isoformat()
                    if stamp_date != date: errors.append({'phase':phase,'reason':'RAW_WRONG_DATE','field':stamp})
                except (KeyError, TypeError, ValueError):
                    errors.append({'phase':phase,'reason':'INVALID_RAW_TIMESTAMP','field':stamp})
            if row.get('error') or row.get('http_status') != 200:
                phase_errors.append({'batch':row.get('batch_no'),'error':row.get('error'),'http_status':row.get('http_status')})
            if row.get('error') in ('CAPTURE_DEADLINE_NO_REQUEST','LATE_REFERENCE_START_NO_BACKFILL'):
                errors.append({'phase':phase,'reason':'MANDATORY_CAPTURE_NOT_EXECUTED'})
            response=row.get('response') or {}
            for item in response.get('msgArray', []):
                key=(item.get('ex'),item.get('c'))
                if item.get('d') != str(date).replace('-',''):
                    errors.append({'phase':phase,'reason':'RAW_WRONG_TRADE_DATE','symbol':list(key)})
                if key in expected and not row.get('error') and row.get('http_status') == 200:
                    seen.add(key); usable += 1
        if not rows or not usable or metrics.get('status') == 'NOT_SAMPLED':
            errors.append({'phase':phase,'reason':'MANDATORY_PHASE_NO_USABLE_RESPONSE'})
        wanted = set(tuple(k.split(':',1)) for k in metrics.get('affected_symbols', [])) if phase=='close_reference_C' else expected
        missing=sorted(':'.join(k) for k in wanted-seen)
        phases[phase]={'returned_unique':len(seen),'missing_count':len(missing),'missing_symbols':missing,'http_or_request_errors':phase_errors}
        if missing or phase_errors:
            warnings.append({'phase':phase,'reason':'PARTIAL_RESPONSE',**phases[phase]})
    probes = read('probe_raw.jsonl', True)
    if not probes: errors.append({'reason':'MISSING_PROBE_EXECUTION_EVIDENCE'})
    issue_report=read('error_missing_report.json') or {}
    if issue_report.get('probe_errors'):
        warnings.append({'reason':'RESEARCH_PROBE_ERRORS','count':len(issue_report['probe_errors']),
                         'details':issue_report['probe_errors']})
    if issue_report.get('snapshot_errors'):
        warnings.append({'reason':'SNAPSHOT_OR_TARGETED_RETRY_ERRORS','count':len(issue_report['snapshot_errors']),
                         'details':issue_report['snapshot_errors']})
    candidates=read('research_candidates.json') or {}
    dual=read('convergence_report.json') or {}
    live=read('live_research_summary.json') if summary.get('live_close_research_enabled') else None
    for name, data in [('research_candidates.json',candidates),('convergence_report.json',dual),('live_research_summary.json',live)]:
        if data is not None and (data.get('trade_date') != date or data.get('validated') is not False):
            errors.append({'file':name,'reason':'INVALID_RESEARCH_OUTPUT'})
    if candidates.get('candidate_count') != len(candidates.get('candidates', [])) or candidates.get('candidate_count') != summary.get('candidate_count'):
        errors.append({'reason':'CANDIDATE_COUNT_MISMATCH'})
    if len(dual.get('securities',[])) != len(expected) or dual.get('research_calculable_count') != summary.get('research_calculable_count'):
        errors.append({'reason':'RESEARCH_REPORT_COUNT_MISMATCH'})
    if live is not None and (live.get('candidate_count') != summary.get('candidate_count') or live.get('research_calculable_count') != summary.get('research_calculable_count')):
        errors.append({'reason':'LIVE_SUMMARY_COUNT_MISMATCH'})
    for row in candidates.get('candidates', []):
        if row.get('validated') is not False or row.get('status') != 'RESEARCH_ONLY':
            errors.append({'reason':'INVALID_RESEARCH_CANDIDATE','code':row.get('code')})
    for name in ('research_candidates.csv','research_candidates_'+str(date)+'.csv','research_candidates_'+str(date)+'.json'):
        if not (output/name).is_file(): errors.append({'reason':'MISSING_RESEARCH_FILE','file':name})
    calculable=summary.get('research_calculable_count',0)
    unresolved=max(0,len(expected)-calculable)
    if unresolved: warnings.append({'reason':'RESEARCH_UNRESOLVED','count':unresolved})
    if summary.get('universe_audit_status') != 'OFFICIAL_SOURCES_DATE_CHECKED':
        errors.append({'reason':'UNIVERSE_DATE_NOT_VERIFIED'})
    outcome='CAPTURE_FAILED' if errors else 'CAPTURE_PARTIAL' if warnings else 'CAPTURE_SUCCESS'
    return {'version':'CAPTURE_COMPLETION_V1','capture_outcome':outcome,
            'status':'failed' if errors else 'partial' if warnings else 'success_raw_capture',
            'exit_code':1 if errors else 0,'core_capture_complete':not errors,
            'official_validation':summary.get('official_validation','PENDING'),
            'research_unresolved_count':unresolved,'phases':phases,'warnings':warnings,'errors':errors,
            'artifact_upload_status':'AWAITING_GITHUB_UPLOAD_STEP'}
