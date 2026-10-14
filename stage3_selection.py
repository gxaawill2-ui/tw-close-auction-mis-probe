"""Stage-3 decisions from raw independent evidence, not supplied verdict flags."""
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import freshness as f
import stage3_ticks as ticks


def decide(row,bundle,date,as_of,*,mode='LIVE',contract=ticks.LIVE_CONTRACT):
    evidence=ticks.inspect(bundle,row,date,as_of,mode=mode,contract=contract)
    pre=f.decimal_value(row.get('P_before'));close=f.decimal_value(row.get('P_close'))
    threshold=bool(pre and close and pre>0 and close>0 and abs(close/pre-1)>=Decimal('.03'))
    closing=f.decimal_value(row.get('closing_auction_volume'));total=f.decimal_value(row.get('intraday_total_volume'))
    ratio=f.decimal_value(row.get('closing_volume_ratio_pct'))
    volume=bool(row.get('volume_status')=='MIS_EVIDENCE_CONFIRMED' and closing and total and
        Decimal(0)<closing<=total and ratio==closing/total*100)
    # Respect the original strategy. No new minimum volume is silently added.
    checks={'pre_actual_trade_before_1325':bool(pre and row.get('P_before_trade_time') and
        '09:00:00'<=row['P_before_trade_time']<'13:25:00'),
        'pre_last_trade_independently_proven':evidence['P_before_independently_verified'],
        'close_independent_finality':evidence['P_close_verified'],
        'tail_threshold':threshold,'required_volume_evidence':volume}
    now=f.parsed_time(as_of)
    within_window=bool(now and f.parsed_time(date+'T13:30:00+08:00') <= now < f.parsed_time(date+'T14:30:00+08:00'))
    valid=mode=='LIVE' and within_window and all(checks.values()) and not evidence['reasons']
    conflict=any('CONFLICT' in r or 'HASH_MISMATCH' in r for r in evidence['reasons'])
    status='VERIFIED' if valid else 'UNKNOWN' if conflict or not threshold else 'RESEARCH_ONLY'
    simulation_pass=bool(mode=='SYNTHETIC' and evidence['synthetic_pre_passed'] and
        evidence['synthetic_close_passed'] and threshold and volume and not evidence['reasons'])
    keys=('code','name','ex','market','P_before','P_close','P_before_trade_time','P_close_trade_time',
        'tail_return_pct','closing_auction_volume','intraday_total_volume','closing_volume_ratio_pct',
        'volume_status','volume_unit','first_seen_at','pre_received_at','pre_saved_at','close_received_at')
    return {**{k:row.get(k) for k in keys},'verification_status':status,'validated':valid,
        'checks':checks,'missing_requirements':[k for k,v in checks.items() if not v],
        'independent_evidence':evidence,'simulation_passed':simulation_pass,'updated_at':as_of,
        'evaluated_at':datetime.now(f.TZ).isoformat(),'evidence_as_of':as_of,'source_acquired_at':evidence['acquired_at'],
        'public_observed_at':None,'simulated_only':mode=='SYNTHETIC'}


class Pipeline:
    def __init__(self,engine,*,mode='OFFLINE_REPLAY',contract=ticks.LIVE_CONTRACT):
        self.engine=engine;self.mode=mode;self.contract=contract;self.proofs={};self.assessed={}
        self.first_pre=None;self.first_close=None;self.first_verified=None;self.version=0

    def compile(self,as_of):
        rows=[]
        for row in self.engine.priority():
            key=row['ex'],row['code']
            result=decide(row,self.proofs.get(key),self.engine.date,as_of,mode=self.mode,contract=self.contract)
            for field,attribute in [('P_before_independently_verified','first_pre'),('P_close_verified','first_close')]:
                if result['independent_evidence'][field] and getattr(self,attribute) is None:setattr(self,attribute,as_of)
            if result['validated'] and self.first_verified is None:self.first_verified=as_of
            rows.append(result)
        self.version+=1
        # Independently count screening evidence. An unexamined stock is never
        # claimed absent from the true +/-3% population.
        from convergence import pre_with_c
        from close_research import assess,TYPES
        screenable=0
        for key in self.engine.universe:
            series=self.engine.series[key]
            if pre_with_c(series,self.engine.date)['converged'] and assess(series,self.engine.date)['classification'] in TYPES:
                screenable+=1
        return {'schema_version':'STAGE3_SELECTION_V1','trade_date':self.engine.date,'mode':self.mode,
            'version':self.version,'generated_at':datetime.now(f.TZ).isoformat(),'assessment_as_of':as_of,'is_synthetic':self.mode=='SYNTHETIC',
            'verified_count':sum(r['validated'] for r in rows),'research_count':sum(r['verification_status']=='RESEARCH_ONLY' for r in rows),
            'unknown_candidate_count':sum(r['verification_status']=='UNKNOWN' for r in rows),
            'simulated_verified_count':sum(r['simulation_passed'] for r in rows),
            'universe_count':len(self.engine.universe),'screening_calculable_count':screenable,
            'screening_unresolved_count':len(self.engine.universe)-screenable,
            'full_market_no_false_negative_claim':False,'rows':rows,'retracted':self.engine.view()['retracted'],
            'final_audit':self.engine.view()['final_audit'],
            'metrics':{**self.engine.view()['metrics'],'first_independent_pre_at':self.first_pre,
              'first_independent_close_at':self.first_close,'first_verified_at':self.first_verified,
              'public_written_at':None,'first_public_observed_at':None}}
