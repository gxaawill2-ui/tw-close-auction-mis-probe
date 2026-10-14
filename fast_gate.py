"""Per-security early-result gates. No late audit can manufacture pre-cutoff truth.

Current anonymous sources cannot attest last-before-cutoff completeness. This
capability is intentionally false, not an input-supplied `validated` boolean.
"""
from decimal import Decimal
import freshness as f

CAPABILITIES = {
 'MIS': {'actual_trade':True,'pre_finality':False,'independent':False},
 'PCHOME': {'actual_trade':False,'pre_finality':False,'independent':False},
 'FUGLE_DOCUMENTATION_ONLY': {'actual_trade':True,'pre_finality':False,'independent':False},
}


def assess(row, date, pre_saved_at=None, independent=None):
    pre=f.decimal_value(row.get('P_before'));close=f.decimal_value(row.get('P_close'))
    t=row.get('P_before_trade_time') or ''
    saved=f.parsed_time(pre_saved_at)
    cutoff=f.parsed_time(date+'T13:25:00+08:00')
    cross=independent or {}
    checks={
      'pre_actual_trade_before_1325':bool(pre and pre>0 and '09:00:00'<=t<'13:25:00'),
      'pre_durably_saved_before_1325':bool(saved and saved.date().isoformat()==date and saved<cutoff),
      'pre_last_trade_independently_proven':False,
      'close_research_converged':row.get('P_close_convergence_type') in ('AB_converged','AC_converged','BC_converged','TARGETED_converged'),
      'close_independent_finality':False,
      'tail_threshold':bool(pre and close and pre>0 and close>0 and abs(close/pre-1)>=Decimal('.03')),
      'required_volume_evidence':row.get('volume_status')=='MIS_EVIDENCE_CONFIRMED',
    }
    # No configured adapter proves pre finality and independent close finality.
    # A dict saying validated=true cannot promote a row. Price and necessary
    # volume evidence use the existing strategy; no new threshold is introduced.
    reasons=[key for key,value in checks.items() if not value]
    return {'verification_status':'VERIFIED' if not reasons else 'RESEARCH_ONLY',
            'validated':not reasons,'checks':checks,'missing_requirements':reasons,
            'crosscheck_status':cross.get('status','NOT_CHECKED'),
            'crosscheck_note':cross.get('limitation'),'final_audit_status':row.get('official_price_result','PENDING'),
            'capability_status':'BLOCKED_PRE_FINALITY_AND_CLOSE_INDEPENDENCE',
            'note':'Documented adapters and complete stream/finality evidence are required before formal publication can be enabled.'}
