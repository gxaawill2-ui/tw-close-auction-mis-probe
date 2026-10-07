"""Conservative live close research hierarchy; never authorizes validated signals."""
import freshness as f

START_DATE = '2026-10-08'
C_TIME = '13:34:10'
TYPES = ('AB_converged', 'AC_converged', 'BC_converged', 'A_1330_fresh_candidate')


def assess(series, date):
    # Import locally so convergence can attach this independent research layer.
    import convergence as c
    times = {**c.REFERENCE_TIMES, 'close_reference_C': C_TIME}
    phases = tuple('close_reference_'+x for x in 'ABC')
    refs = {p: next((r for r in series if r.get('phase') == p), None) for p in phases}
    result = {'classification': 'unresolved', 'confidence_level': None,
              'p_close': None, 'trade_time': None, 'validated': False,
              'converged': False, 'selected': None, 'pair': None,
              'reason': 'NO_USABLE_CLOSE_REFERENCE', 'rejections': []}

    def reason(row):
        if not row:
            return 'NOT_SAMPLED'
        planned = f.parsed_time(row.get('planned_at'))
        if not planned or planned.date().isoformat() != date or planned.strftime('%H:%M:%S') != times[row['phase']]:
            return 'INVALID_REFERENCE_SCHEDULE'
        why = c.rejection(row, date, 'close')
        # An actual post-13:30 trade stays delayed. It needs a distinct agreeing
        # observation; broadening this classification never makes it normal.
        if why == 'UNEXPLAINED_CLOSE_TRADE_TIME' and c.clock(row.get('trade_t')) and row['trade_t'] > '13:30:00':
            return None
        return why

    usable = {p: r for p, r in refs.items() if r and not reason(r)}
    for p, row in refs.items():
        why = reason(row)
        if why:
            result['rejections'].append({'phase': p, 'reason': why})

    def agrees(prior, last):
        if not prior or not last or prior['received_at'] >= last['received_at']:
            return False
        if prior['server_time'] >= last['server_time'] or f.identity(prior) != f.identity(last):
            return False
        # A stale B can be bridged, but a fresh contradictory or regressing
        # observation between or after the adopted pair cannot be ignored.
        later = [r for r in usable.values() if r['received_at'] > prior['received_at']]
        high = prior['server_time']
        for row in sorted(later, key=lambda r: r['received_at']):
            if row['server_time'] < high or f.identity(row) != f.identity(last):
                return False
            high = row['server_time']
        return True

    for first, second, label in (('A', 'B', 'AB_converged'),
                                  ('A', 'C', 'AC_converged'),
                                  ('B', 'C', 'BC_converged')):
        a, b = usable.get('close_reference_'+first), usable.get('close_reference_'+second)
        if agrees(a, b):
            return {**result, 'classification': label, 'confidence_level': 'HIGH_RESEARCH',
                    'p_close': b['trade_z'], 'trade_time': b['trade_t'],
                    'converged': True, 'selected': b, 'pair': [a, b], 'reason': None}

    a = usable.get('close_reference_A')
    if a and a['trade_t'] == '13:30:00':
        later = [r for p, r in refs.items() if r and r['received_at'] > a['received_at']
                 and f.fresh_candidate(r, date, c.MAX_AGE_MS)]
        if not any(reason(r) or r['server_time'] < a['server_time'] or f.identity(r) != f.identity(a) for r in later):
            return {**result, 'classification': 'A_1330_fresh_candidate',
                    'confidence_level': 'MEDIUM_RESEARCH', 'p_close': a['trade_z'],
                    'trade_time': a['trade_t'], 'selected': a, 'reason': None}
        result['reason'] = 'LATER_FRESH_CONTRADICTION_OR_INCOMPLETE_REFERENCE'

    delayed = [r for r in usable.values() if r['trade_t'] > '13:30:00']
    if delayed:
        last = max(delayed, key=lambda r: r['received_at'])
        result.update(classification='delayed_close_candidate', selected=last,
                      reason='NEEDS_DISTINCT_AGREEMENT_OR_OFFICIAL_VALIDATION')
    return result


def affected(date, snapshots, universe, probes=()):
    import convergence as c
    series = c.grouped(snapshots, date)
    samples = {}
    for row in f.observations(probes, date):
        samples.setdefault((row['ex'], row['code']), []).append(row)
    result = []
    for symbol in universe:
        key = symbol['ex'], symbol['code']
        evidence = assess(series[key], date)
        comparison = c.probe_comparison(samples.get(key, []),
            {'converged': bool(evidence['selected']), 'B': evidence['selected']}, date, 'close')
        if not evidence['converged'] or comparison['status'] == 'PROBE_CONFLICT':
            result.append(symbol)
    return result


def ordered_symbols(universe, label):
    """Change only cache-key grouping/order; fixed batch size/concurrency remain."""
    values = list(universe)
    if label == 'B':
        return list(reversed(values))
    if label == 'C' and values:
        # Rotation changes batch boundaries; reversal changes within-batch keys.
        shift = min(23, len(values)-1)
        values = values[shift:] + values[:shift]
        return list(reversed(values))
    return values
