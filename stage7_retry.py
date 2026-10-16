"""Review-only C2 plan: sparse uncertain closes, symbol-wide attempts, no HTTP."""
from datetime import timedelta
import close_research
import convergence
import freshness as f
from stage5_runtime import FairQueue


def plan(engine,as_of,ledger=None,*,max_symbols=12):
    now=f.parsed_time(as_of);end=f.parsed_time(engine.date+'T13:34:50+08:00');ledger=ledger or {}
    if not 1<=max_symbols<=12:raise ValueError('UNSAFE_RETRY_BUDGET')
    if not now or now.date().isoformat()!=engine.date or now<f.parsed_time(engine.date+'T13:34:10+08:00') or now>=end-timedelta(seconds=8):
        return {'status':'OUTSIDE_C2_REQUEST_WINDOW','symbols':[],'mis_requests':0}
    eligible=[];exhausted=[];cooldown=[]
    for key,symbol in engine.universe.items():
        series=engine.series[key];before=convergence.pre_with_c(series,engine.date)
        if not before['converged']:continue
        close=close_research.assess(series,engine.date)
        if close['converged']:continue
        # Only known real close prints can justify narrow retry. No last-close
        # substitute, zero fill or market-wide retry of all missing observations.
        possible=[r for r in series if r.get('phase','').startswith('close_') and f.fresh_candidate(r,engine.date,convergence.MAX_AGE_MS) and '13:30:00'<=r.get('trade_t','')<='13:33:00' and f.decimal_value(r.get('trade_z'))]
        if not possible:continue
        pre=f.decimal_value(before['B'].get('trade_z'))
        if not pre or pre<=0 or not any(abs(f.decimal_value(r['trade_z'])/pre-1)>=f.Decimal('.03') for r in possible):continue
        name=symbol['ex']+':'+symbol['code'];state=ledger.get(name,{})
        count=state.get('attempts',0)
        if not isinstance(count,int) or isinstance(count,bool) or count<0:raise ValueError('INVALID_SYMBOL_RETRY_LEDGER')
        if count>=2:exhausted.append(name);continue
        last=f.parsed_time(state.get('last_attempt_at'))
        if state.get('last_attempt_at') is not None and (not last or last.date().isoformat()!=engine.date or last>now):raise ValueError('INVALID_RETRY_CLOCK')
        if last and (now-last).total_seconds()<3:cooldown.append(name);continue
        delayed=any(r['trade_t']>'13:30:00' for r in possible)
        eligible.append({**symbol,'attempt_key':name,'next_symbol_attempt':count+1,
            'reason':'DELAYED_CLOSE_NEEDS_DISTINCT_EVIDENCE' if delayed else 'C_CLOSE_UNCONVERGED_OR_CONFLICTING',
            'private_review_only':True,'validated':False,'delayed_priority':delayed})
    eligible.sort(key=lambda r:(not r['delayed_priority'],r['code']))
    return {'scope':'ISOLATED_OFFLINE_C2_PLAN_ONLY','status':'REQUIRES_SEPARATE_FORMAL_APPROVAL',
        'symbols':eligible[:max_symbols],'eligible_count':len(eligible),'deferred_count':max(0,len(eligible)-max_symbols),
        'exhausted':exhausted,'cooldown':cooldown,'max_symbols':max_symbols,'max_attempts_per_symbol_per_day':2,
        'timeout_seconds':5,'cooldown_seconds':3,'latest_receive_at':end.isoformat(),
        'no_request_after':(end-timedelta(seconds=8)).isoformat(),'mis_requests':0,'public_admission_unchanged':True}
