"""Read-only interpretation of saved state and GitHub run metadata; no MIS IO."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import candidate_publication

TZ = ZoneInfo('Asia/Taipei')
WORKFLOW = '.github/workflows/twse-mis-probe.yml'


def run_query(now):
    now = now.astimezone(TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stamp = lambda value: value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return 'actions/workflows/twse-mis-probe.yml/runs?per_page=100&created='+stamp(start)+'..'+stamp(now)


def instant(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(TZ) if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def summarize(now, calendar, live, candidates, runs):
    """A GitHub Run is a trigger receipt, never proof of MIS/publication success."""
    now = now.astimezone(TZ)
    date = now.date().isoformat()
    live = live if live.get('trade_date') == date else {}
    known_calendar = (calendar.get('year') == now.year and
                      isinstance(calendar.get('closed_dates'), list))
    trading = (now.weekday() < 5 and date not in calendar['closed_dates']) if known_calendar else None
    observed = []
    valid_runs = (isinstance(runs, dict) and isinstance(runs.get('workflow_runs'), list) and
                  type(runs.get('total_count')) is int and runs['total_count'] >= 0)
    if valid_runs:
        for run in runs.get('workflow_runs', []):
            created = instant(run.get('created_at'))
            if (created and created.date().isoformat() == date and created <= now and
                    run.get('path') == WORKFLOW and run.get('head_branch') == 'main' and
                    run.get('event') in ('workflow_dispatch', 'schedule') and
                    run.get('display_title', '').startswith('MIS live /')):
                observed.append({'run_id': str(run['id']), 'created_at': created.isoformat(),
                                 'status': run.get('status'), 'conclusion': run.get('conclusion'),
                                 'event': run['event']})
    observed.sort(key=lambda r: r['created_at'])
    complete_run_list = valid_runs and runs['total_count'] == len(runs['workflow_runs'])
    cutoff = now.replace(hour=13, minute=2, second=0, microsecond=0)
    on_time = any(instant(r['created_at']) <= cutoff for r in observed)
    trigger = ('RUN_CREATED_BY_1302' if on_time else
               'UNKNOWN_RUN_LOOKUP' if not complete_run_list else
               'WAITING_FOR_1302' if now < cutoff else 'NO_LIVE_RUN_BY_1302')
    publication = 'NOT_PUBLISHED'
    count = None
    if candidates:
        try:
            candidate_publication.validate(candidates, date)
            for key in ('generated_at', 'updated_at', 'published_at'):
                if candidates.get(key):
                    stamp = instant(candidates[key])
                    if not stamp or stamp > now or stamp.date().isoformat() != date:
                        raise ValueError('INVALID_PUBLICATION_TIME')
            if live.get('run_id') and str(live['run_id']) != str(candidates.get('capture_run_id')):
                raise ValueError('CAPTURE_RUN_CONFLICT')
            publication = 'PUBLISHED'
            count = candidates['candidate_count']
        except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            publication = 'INVALID_OR_WRONG_DAY_PUBLICATION'
    if (live.get('candidate_publication') or {}).get('status') == 'FAILED':
        publication = 'PUBLICATION_FAILED'
    failed_capture = (str(live.get('status', '')).startswith('failed') or
                      live.get('capture_outcome') == 'CAPTURE_FAILED')
    if trading is False:
        state = 'NONTRADING_DAY'
        trigger = 'NOT_REQUIRED'
    elif trading is None:
        state = 'UNKNOWN_CALENDAR'
    elif failed_capture:
        state = 'CAPTURE_FAILED'
    elif publication in ('PUBLICATION_FAILED', 'INVALID_OR_WRONG_DAY_PUBLICATION'):
        state = publication
    elif publication == 'PUBLISHED':
        state = 'PUBLISHED_ZERO_CANDIDATES' if count == 0 else 'PUBLISHED_CANDIDATES'
    elif live.get('capture_outcome') in ('CAPTURE_SUCCESS', 'CAPTURE_PARTIAL'):
        state = 'CAPTURE_COMPLETED_PUBLICATION_PENDING'
    elif live.get('preclose_captured') or live.get('reference_progress'):
        state = 'CAPTURING'
    elif live.get('status') == 'running':
        state = 'RUNNER_ARMED_MIS_PENDING'
    elif any(r['status'] == 'in_progress' for r in observed):
        state = 'WORKFLOW_STARTED_MIS_PENDING'
    elif any(r['status'] in ('queued', 'pending', 'waiting', 'requested') for r in observed):
        state = 'WORKFLOW_QUEUED'
    elif observed:
        state = 'WORKFLOW_FINISHED_WITHOUT_CAPTURE_STATE'
    else:
        state = 'NOT_STARTED' if trigger == 'NO_LIVE_RUN_BY_1302' else trigger
    return {'trade_date': date, 'checked_at': now.isoformat(), 'state': state,
            'is_trading_day': trading, 'trigger_status': trigger,
            'primary_check_deadline': cutoff.isoformat(), 'live_runs': observed,
            'capture_status': live.get('capture_outcome') or live.get('status'),
            'publication_status': publication, 'candidate_count': count,
            'mis_requests': 0, 'no_backfill': True,
            'limitations': 'Run creation is not runner start; external HTTP/token status requires provider history. Native health schedule can itself be delayed.'}
