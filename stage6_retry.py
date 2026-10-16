"""Offline plan for narrowly targeted second-close evidence. NEVER sends MIS."""
from datetime import timedelta
from stage5_session import pending_delayed_reviews
from stage5_runtime import FairQueue
import freshness as f


def plan(engine,as_of,attempts=None,*,max_symbols=12,max_rounds=2):
    now=f.parsed_time(as_of);attempts=attempts or {}
    end=f.parsed_time(engine.date+'T13:34:50+08:00')
    if not now or now.date().isoformat()!=engine.date or now>=end-timedelta(seconds=8):
        return {'status':'CUTOFF_NO_NEW_REQUEST','symbols':[],'mis_requests':0}
    if not 1<=max_symbols<=12 or not 1<=max_rounds<=2:raise ValueError('UNSAFE_RETRY_PLAN')
    pending=pending_delayed_reviews(engine);eligible=[];exhausted=0
    for row in pending:
        fingerprint=FairQueue.fingerprint(row);key=row['ex']+':'+row['code']+':'+fingerprint
        if attempts.get(key,0)>=max_rounds:exhausted+=1;continue
        eligible.append({'ex':row['ex'],'code':row['code'],'fingerprint':fingerprint,
            'attempt_key':key,'reason':'SINGLE_DELAYED_CLOSE_NEEDS_SECOND_OBSERVATION'})
    return {'status':'PROPOSED_ONLY_REQUIRES_FORMAL_APPROVAL','symbols':eligible[:max_symbols],
        'eligible_count':len(eligible),'deferred_by_symbol_budget':max(0,len(eligible)-max_symbols),
        'attempts_exhausted':exhausted,'latest_receive_at':end.isoformat(),'timeout_seconds':5,
        'max_http_rounds':max_rounds,'cooldown_seconds':3,'mis_requests':0,
        'same_date_saved_p_before_required':True,'public_candidate_admission_unchanged':True}
