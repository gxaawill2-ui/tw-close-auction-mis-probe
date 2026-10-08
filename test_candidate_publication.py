import base64
import copy
import gzip
import json
import tempfile
import unittest
import urllib.error
from types import SimpleNamespace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, Mock

import candidate_publication as p
import volume_evidence as v
import official_retry
import run_control
import probe
import convergence

ROOT=Path(__file__).parent
DATE='2026-10-08'
ASOF=DATE+'T13:34:12.719+08:00'


class VolumeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads(gzip.decompress((ROOT/'fixtures/oct8_sparse_evidence.json.gz').read_bytes()))
        self.rows=self.fixture['candidates']
        self.snapshots=[{'records':self.fixture['records']}]

    def assess(self,code='3259',snapshots=None,contract=None):
        row=next(r for r in self.rows if r['code']==code)
        symbol=next(s for s in self.fixture['universe'] if s['code']==code)
        return v.assess(row,symbol,snapshots or self.snapshots,DATE,ASOF,contract or v.CONTRACT)

    def mutate(self,code,field,value):
        for r in self.fixture['records']:
            if r['phase'].startswith('close_reference'):
                for item in r.get('response',{}).get('msgArray',[]):
                    if item['c']==code:item[field]=value

    def test_seven_actual_volumes_regular_and_delayed(self):
        expected={'3073':('17','44'),'3259':('1','8'),'3684':('66','1255'),
                  '4706':('36','498'),'5355':('1','121'),'5543':('6','8'),'2024':('7','73')}
        for code,(last,total) in expected.items():
            result=self.assess(code)
            self.assertEqual(result['volume_status'],'MIS_EVIDENCE_CONFIRMED',code)
            self.assertEqual((result['closing_auction_volume'],result['intraday_total_volume']),(last,total))
            self.assertEqual(Decimal(result['closing_volume_ratio_pct']),Decimal(last)/Decimal(total)*100)
            times={r['trade']['t'] for r in result['volume_evidence']['close_observations']}
            self.assertEqual(times,{'13:33:00' if code in ('3073','3259','3684') else '13:30:00'})
            self.assertFalse(result['volume_evidence']['independent_official_volume_validation'])

    def test_units_shares_fractional_lots_without_truncation(self):
        self.assertEqual(v.to_lots('1501','SHARES'),Decimal('1.501'))
        self.assertEqual(v.to_lots('1255','TRADING_UNIT'),Decimal('1255'))
        self.assertIsNone(v.to_lots('1255','UNVERIFIED'))
        self.assertIsNone(v.to_lots('-1','SHARES'))

    def test_tv_disagreement_never_selects_convenient_number(self):
        self.mutate('3259','tv','2')
        result=self.assess()
        self.assertEqual(result['volume_status'],'UNVERIFIED')
        self.assertIsNone(result['closing_auction_volume']);self.assertIsNone(result['closing_volume_ratio_pct'])

    def test_missing_total_keeps_all_null(self):
        self.mutate('3259','v',None)
        result=self.assess()
        self.assertEqual(result['volume_status'],'UNVERIFIED');self.assertIsNone(result['intraday_total_volume'])

    def test_simulated_outer_quote_not_actual_volume(self):
        self.mutate('3259','ts','1');self.assertEqual(self.assess()['volume_status'],'UNVERIFIED')

    def test_unknown_unit_contract_keeps_prices_and_null_volumes(self):
        contract={**v.CONTRACT,'status':'UNVERIFIED'}
        self.assertEqual(self.assess(contract=contract)['volume_status'],'UNVERIFIED')
        self.assertEqual(len(self.rows),7)

    def test_post_asof_raw_never_used(self):
        for r in self.fixture['records']:
            if r['phase']=='close_reference_C':r['received_at']=DATE+'T14:50:00+08:00'
        self.assertEqual(self.assess()['volume_status'],'UNVERIFIED')

    def test_stale_pair_not_volume_confirmed(self):
        for r in self.fixture['records']:
            if r['phase']=='close_reference_C':r['http_status']=503
        self.assertEqual(self.assess()['volume_status'],'UNVERIFIED')

    def test_no_second_fresh_pair_keeps_volume_unknown(self):
        row=next(r for r in self.rows if r['code']=='3259');row['close_research_evidence']['pair']=row['close_research_evidence']['pair'][:1]
        self.assertEqual(self.assess()['volume_status'],'UNVERIFIED')


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.payload=json.loads((ROOT/'state/candidates/2026-10-08.json').read_text())
        self.calls=[];self.stored=None

    def api(self,path,method='GET',body=None):
        self.calls.append((path,method))
        if method=='GET':return self.stored
        self.stored={'content':body['content'],'sha':'stored-sha'}
        return {'commit':{'sha':'commit-sha'}}

    def live_payload(self):
        payload=copy.deepcopy(self.payload)
        payload.pop('postmarket_verified_at',None);payload.pop('official_validation_run_id',None)
        for row in payload['candidate_list']:
            row.update(official_price_result='PENDING',postmarket_verified_at=None)
            row.pop('official_close',None)
            row['volume_evidence'].pop('official_daily_shares',None)
            row['volume_evidence'].pop('official_daily_volume_scope',None)
        return payload

    def test_saved_prices_and_seven_false_validated(self):
        p.validate(self.payload,DATE)
        raw=json.loads(gzip.decompress((ROOT/'fixtures/oct8_sparse_evidence.json.gz').read_bytes()))
        original={r['code']:r for r in raw['candidates']}
        for row in self.payload['candidate_list']:
            for k in p.PRICE_FIELDS:
                if k!='tail_return_pct':self.assertEqual(row[k],original[row['code']][k])
            self.assertFalse(row['validated']);self.assertEqual(row['official_price_result'],'MATCH')
        self.assertEqual(self.payload['coverage'],{'tradable_universe':1968,'research_calculable':1943,'unknown':25})

    def test_zero_candidates_valid_completed_not_missing(self):
        self.payload.update(candidate_list=[],candidate_count=0)
        self.payload['price_fingerprint']=p.fingerprint(self.payload);p.validate(self.payload,DATE)

    def test_date_mismatch_rejected(self):
        with self.assertRaises(ValueError):p.validate(self.payload,'2026-10-12')

    def test_incomplete_data_rejected(self):
        self.payload['completion_status']='RUNNING'
        with self.assertRaises(ValueError):p.validate(self.payload,DATE)

    def test_duplicate_unknown_or_below_threshold_rejected(self):
        for change in ('duplicate','unknown','threshold'):
            payload=copy.deepcopy(self.payload)
            if change=='duplicate':payload['candidate_list'][1]=payload['candidate_list'][0]
            if change=='unknown':payload['candidate_list'][0]['P_close_convergence_type']='unresolved'
            if change=='threshold':payload['candidate_list'][0]['P_close']=payload['candidate_list'][0]['P_before']
            payload['price_fingerprint']=p.fingerprint(payload)
            with self.assertRaises(ValueError):p.validate(payload,DATE)

    def test_publication_idempotent_date_isolated(self):
        first=p.put(self.payload,self.api,lambda:DATE+'T18:30:00+08:00')
        second=p.put(self.payload,self.api,lambda:DATE+'T18:31:00+08:00')
        self.assertFalse(first['idempotent']);self.assertTrue(second['idempotent'])
        self.assertEqual(sum(method=='PUT' for _,method in self.calls),1)
        self.assertTrue(all('2026-10-08.json' in path for path,_ in self.calls))

    def test_conflict_retry_then_success(self):
        attempts=[]
        def api(path,method='GET',body=None):
            if method=='PUT' and not attempts:
                attempts.append(1);raise urllib.error.HTTPError('url',409,'conflict',{},None)
            return self.api(path,method,body)
        with patch.object(p.time,'sleep') as sleep:result=p.put(self.payload,api,lambda:ASOF)
        self.assertEqual(result['status'],'PUBLISHED');sleep.assert_called_once()

    def test_bounded_network_failure_is_explicit(self):
        api=Mock(side_effect=TimeoutError('network'))
        with patch.object(p.time,'sleep'),self.assertRaisesRegex(RuntimeError,'PUBLICATION_FAILED'):
            p.put(self.payload,api,lambda:ASOF)
        self.assertEqual(api.call_count,3)

    def test_wrong_price_cannot_overwrite_previous_live_day(self):
        p.put(self.payload,self.api,lambda:ASOF)
        newer=copy.deepcopy(self.payload);newer['candidate_list'][0]['name']='changed'
        newer['price_fingerprint']=p.fingerprint(newer)
        with self.assertRaisesRegex(ValueError,'IMMUTABLE'):p.put(newer,self.api,lambda:ASOF)

    def test_official_annotation_cannot_change_live_price_or_volume_status(self):
        payload=self.live_payload()
        sources=[{'ex':ex,'status':'AVAILABLE_SAME_DATE','response_date':'20261008'} for ex in ('tse','otc')]
        official={'trade_date':DATE,'sources':sources,'checks':[{'ex':r['ex'],'code':r['code'],'official_date':DATE,'official_close':r['P_close'],'official_volume_shares':'999999'} for r in payload['candidate_list']]}
        out=p.enrich(payload,official,DATE+'T15:20:00+08:00','official')
        self.assertEqual(out['price_fingerprint'],payload['price_fingerprint'])
        self.assertTrue(all(r['official_price_result']=='MATCH' for r in out['candidate_list']))
        self.assertEqual([r['intraday_total_volume'] for r in out['candidate_list']],[r['intraday_total_volume'] for r in payload['candidate_list']])
        self.assertEqual(next(r for r in out['candidate_list'] if r['code']=='3259')['P_close_convergence_type'],'BC_converged')
        official['sources'][1]['response_date']='20261007'
        out=p.enrich(payload,official,DATE+'T15:20:00+08:00','official')
        self.assertTrue(all(r['official_price_result']=='PENDING' for r in out['candidate_list'] if r['ex']=='otc'))

    def test_retry_live_does_not_erase_postmarket_annotations(self):
        p.put(self.payload,self.api,lambda:ASOF)
        p.put(self.live_payload(),self.api,lambda:ASOF)
        stored=json.loads(base64.b64decode(self.stored['content']))
        self.assertTrue(all(r['official_price_result']=='MATCH' for r in stored['candidate_list']))

    def test_build_rejects_incomplete_capture_and_wrong_day_without_http(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);(out/'run_summary.json').write_text(json.dumps({'trade_date':DATE}))
            with patch.object(probe,'get_bytes',side_effect=AssertionError('No MIS')):
                with self.assertRaisesRegex(ValueError,'INCOMPLETE'):p.build(out,DATE,'run')
                with self.assertRaisesRegex(ValueError,'WRONG_DATE'):p.build(out,'2026-10-12','run')

    def test_saved_capture_build_exact_asof_and_future_observation_rejected(self):
        fixture=json.loads(gzip.decompress((ROOT/'fixtures/oct8_sparse_evidence.json.gz').read_bytes()))
        rows=fixture['records'];universe=fixture['universe']
        report=convergence.build_report(DATE,[{'records':rows}],[],universe,{'checks':[]})
        original=convergence.research_candidates(report)
        self.assertEqual(original['candidates'],fixture['candidates'])
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            def write(name,data):(out/name).write_text(json.dumps(data))
            summary={'trade_date':DATE,'runner_started_at':DATE+'T13:00:00+08:00',
               'universe_count':len(universe),'universe_audit_status':'OFFICIAL_SOURCES_DATE_CHECKED',
               'capture_architecture':convergence.VERSION,'pre_reference_C_enabled':True,
               'close_reference_C_enabled':True,'live_close_research_enabled':True,
               'candidate_count':7,'research_calculable_count':7,'snapshots':{}}
            write('run_summary.json',summary);write('universe.json',universe)
            write('research_candidates.json',original);write('convergence_report.json',report)
            write('live_research_summary.json',{'trade_date':DATE,'generated_at':ASOF,'validated':False,'candidate_count':7,'research_calculable_count':7})
            write('error_missing_report.json',{})
            for phase in set(r['phase'] for r in rows):
                (out/(phase+'_raw.jsonl')).write_text('\n'.join(json.dumps(r) for r in rows if r['phase']==phase)+'\n')
            (out/'probe_raw.jsonl').write_text(json.dumps(rows[0])+'\n')
            for name in ('research_candidates.csv','research_candidates_'+DATE+'.csv','research_candidates_'+DATE+'.json'):
                (out/name).write_text('{}')
            with patch.object(probe,'get_bytes',side_effect=AssertionError('No HTTP')):
                built=p.build(out,DATE,'saved-run')
            self.assertEqual(built['candidate_count'],7)
            self.assertTrue(all(r['official_price_result']=='PENDING' for r in built['candidate_list']))
            # Remove the only actual delayed close C observations from the live
            # as-of window; the old saved list may no longer be published.
            late=[{**r,'received_at':DATE+'T14:50:00+08:00'} for r in rows if r['phase']=='close_reference_C']
            (out/'close_reference_C_raw.jsonl').write_text('\n'.join(json.dumps(r) for r in late)+'\n')
            with self.assertRaisesRegex(ValueError,'ASOF_REPLAY'):p.build(out,DATE,'saved-run')

    def test_push_does_not_execute_live_or_upload(self):
        yaml=(ROOT/'.github/workflows/twse-mis-probe.yml').read_text()
        self.assertIn("if: github.event_name != 'push'",yaml)
        self.assertIn("if: always() && github.event_name != 'push'",yaml)
        self.assertNotIn('candidate_publication.py', (ROOT/'.github/workflows/mis-official-validation.yml').read_text())

    def test_official_validation_persists_when_website_publication_fails(self):
        capture={'run_id':'capture','preclose_captured':True}
        control=SimpleNamespace(REPO=run_control.REPO,live_path=lambda date:'live',
             read_state=Mock(side_effect=lambda path:(capture if path=='live' else {},None)),
             api=Mock(return_value={'artifacts':[{'name':'mis-probe-capture','id':1}]}),
             merge_state=Mock(),publish=Mock())
        clock=SimpleNamespace(iso=lambda:DATE+'T15:20:00+08:00',get_bytes=Mock(),package=Mock(),FIXED_PROBE=[])
        validation={'trade_date':DATE,'status':'SAME_DATE_COMPARISON_ONLY','matches':7,'mismatches':0,'unavailable':25,'sources':[]}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(official_retry,'download_archive',return_value=b'saved'), \
             patch.object(official_retry,'load_capture',return_value=({'trade_date':DATE,'live_close_research_enabled':True},[],[],[])), \
             patch.object(official_retry.official_quotes,'validate',return_value=validation), \
             patch.object(p,'from_archive',return_value=self.payload), \
             patch.object(p,'enrich',return_value=self.payload), \
             patch.object(p,'put',side_effect=TimeoutError('website')), \
             patch.object(official_retry.freshness,'write_report',return_value={k:0 for k in ('p_before_validated_count','p_close_validated_count','both_validated_count')}), \
             patch.object(official_retry.convergence,'write_report',return_value={'status':'RESEARCH_ONLY','research_candidate_count':7}):
            code=official_retry.run(DATE,Path(temp),control,clock)
            self.assertEqual(code,4);clock.package.assert_called_once()
            stored=json.loads((Path(temp)/'validation_summary.json').read_text())
            self.assertEqual(stored['matches'],7);self.assertEqual(stored['candidate_publication']['status'],'FAILED')
            control.merge_state.assert_called_once()

if __name__=='__main__':unittest.main()
