import copy
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error

import freshness as f
from stage3_fixtures import DAY, example, mutate
from stage3_ticks import canonical
from stage5_runtime import Source, LocalVault, Vault, FairQueue, public_view, NoRedirect, restore_bundle
from stage5_audit import audit


class Response(io.BytesIO):
    status=200
    headers={}


class Stage5Tests(unittest.TestCase):
    def test_raw_source_is_private_and_budget_rate_and_real_scope_enforced(self):
        at=[f.parsed_time(DAY+'T13:35:00+08:00')];starts=[]; saved=[]
        row,bundle=example(page_size=200);payload=json.loads(bundle['quote_after']['raw'])
        class Private:
            def save(self,event,date):
                saved.append(copy.deepcopy(event));return {'id':'a'*64,'sha256':event['sha256'],'private_written_at':event['persisted_at'],'recoverable_after_job':True}
        def open(req,timeout):
            starts.append(at[0]);return Response(json.dumps(payload).encode())
        def wait(seconds):at[0]+=timedelta(seconds=seconds)
        with tempfile.TemporaryDirectory() as tmp:
            source=Source('K'*30,tmp,Private(),max_requests=2,opener=open,clock=lambda:at[0],wait=wait)
            for _ in range(2):source.request(row,'quote',{},at[0]+timedelta(minutes=1))
            self.assertGreaterEqual((starts[1]-starts[0]).total_seconds(),1.3)
            self.assertEqual(len(saved),2);self.assertNotIn('K'*30,canonical(saved))
            self.assertEqual(Path(tmp).stat().st_mode&0o777,0o700)
            self.assertEqual(next(Path(tmp).iterdir()).stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):source.request(row,'quote',{},at[0]+timedelta(minutes=1))
            self.assertEqual(len(starts),2)
            with self.assertRaises(ValueError):source.request(row,'trades',{'limit':200,'sort':'desc','isTrial':True},at[0]+timedelta(minutes=1))

    def test_auth_quota_stops_all_workers_and_redirect_never_forwards(self):
        row,_=example();at=f.parsed_time(DAY+'T13:35:00+08:00');calls=[]
        for status in (401,403,429,302):
            def open(req,timeout):calls.append(req.full_url);raise urllib.error.HTTPError(req.full_url,status,'private provider text',{},None)
            with tempfile.TemporaryDirectory() as tmp:
                source=Source('K'*30,tmp,LocalVault(),opener=open,clock=lambda:at,wait=lambda _:None)
                with self.assertRaises(ValueError) as error:source.request(row,'quote',{},at+timedelta(minutes=1))
                self.assertNotIn('private provider text',str(error.exception))
                self.assertEqual(source.stopped,status in (401,403,429))
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid'))

    def test_real_audit_never_releases_from_empirical_equalities_and_detects_holes(self):
        row,bundle=example(page_size=200);bundle.update(status='COLLECTED_NOT_VALIDATED',origin_kind='AUTHENTICATED_HTTP')
        def receipt(event):
            event['persisted_at']=event['received_at']
            event['private_receipt']={'id':hashlib.sha256(canonical(event).encode()).hexdigest(),'sha256':event['sha256'],
                'private_written_at':event['received_at'],'recoverable_after_job':True}
        for event in (bundle['quote_before'],*bundle['pages'],bundle['quote_after']):receipt(event)
        result=audit(bundle,row,DAY,DAY+'T13:35:05+08:00')
        self.assertTrue(result['rows_equal_quote_transaction']);self.assertTrue(result['size_sum_equal_quote_volume'])
        self.assertEqual(result['close_classification'],'NORMAL_CLOSE');self.assertEqual(result['verified_count'],0)
        self.assertFalse(result['p_before_independently_proven']);self.assertNotIn('pre_tick',result)
        self.assertEqual(result['reasons'],['PROVIDER_COMPLETENESS_AND_ORDER_CONTRACT_NOT_RELEASED'])
        missing=copy.deepcopy(bundle);mutate(missing['pages'][0],lambda data:data['data'].pop(1));receipt(missing['pages'][0])
        result=audit(missing,row,DAY,DAY+'T13:35:05+08:00')
        self.assertIn('ROWS_DO_NOT_MATCH_QUOTE_TRANSACTION',result['reasons'])
        self.assertIn('SIZE_SUM_DOES_NOT_MATCH_QUOTE_VOLUME',result['reasons'])
        conflict=copy.deepcopy(bundle);mutate(conflict['quote_after'],lambda data:data.pop('isClose'));receipt(conflict['quote_after'])
        self.assertIn('CLOSE_FINALITY_NOT_PROVEN',audit(conflict,row,DAY,DAY+'T13:35:05+08:00')['reasons'])

    def test_public_allowlist_strips_fugle_prices_ticks_and_paths(self):
        view={'mode':'LIVE','rows':[{'code':'2330','ex':'tse','P_before':'100','P_close':'104',
            'verification_status':'UNKNOWN','validated':False,
            'independent_evidence':{'pre_tick':{'price':'SECRET_MARKET_PRICE'},'raw_path':'private-file',
                'reasons':['LIVE_SOURCE_CONTRACT_NOT_RELEASED'],'source':'FUGLE'}}], 'retracted':[]}
        public=public_view(view)
        self.assertEqual(public['rows'][0]['P_before'],'100');self.assertEqual(public['rows'][0]['price_source'],'MIS')
        self.assertEqual(public['research_candidate_count'],1)
        self.assertNotIn('SECRET_MARKET_PRICE',canonical(public));self.assertNotIn('private-file',canonical(public))
        with self.assertRaises(ValueError):public_view({**view,'mode':'OFFLINE_REPLAY'})

    def test_slow_candidate_cannot_block_fast_one_stale_results_discarded(self):
        gate=threading.Event()
        def collect(row):
            if row['code']=='2330':gate.wait(1)
            return {'code':row['code'],'price':row.get('P_close')}
        queue=FairQueue(collect,max_attempts=1)
        a={'ex':'tse','code':'2330','P_close':'1'};b={'ex':'otc','code':'6488','P_close':'2'}
        try:
            queue.offer([a,b]);queue.tick();completed=[]
            for _ in range(100):
                completed+=queue.tick()
                if completed:break
                time.sleep(.001)
            self.assertEqual(completed[0][0],('otc','6488'))
            queue.offer([{**a,'P_close':'3'},b]);gate.set()
            for _ in range(100):
                done=queue.tick()
                self.assertFalse(any(r[1].get('price')=='1' for r in done))
                if ('tse','2330') not in queue.tasks:break
                time.sleep(.001)
            queue.offer([b]);self.assertNotIn(('tse','2330'),queue.pending)
        finally:gate.set();queue.close()

    def test_private_vault_refuses_any_other_host_before_transmitting_key(self):
        calls=[]
        with self.assertRaises(ValueError):Vault('a'*64,'b'*64,base='https://wrong.invalid',opener=lambda *a,**k:calls.append(a))
        self.assertEqual(calls,[])

    def test_private_manifest_restores_and_rechecks_each_raw_hash(self):
        row,bundle=example(page_size=200);at=[f.parsed_time(DAY+'T13:35:00+08:00')]
        responses=[bundle['quote_before']['raw'],bundle['pages'][0]['raw'],bundle['quote_after']['raw']]
        class MemoryVault:
            def __init__(self):self.objects={}
            def save(self,event,date):
                ident=hashlib.sha256(canonical(event).encode()).hexdigest()
                self.objects[ident]={'id':ident,'event':copy.deepcopy(event),'private_written_at':at[0].isoformat()}
                return {'id':ident,'sha256':event['sha256'],'private_written_at':at[0].isoformat(),'recoverable_after_job':True}
            def read(self,date,ident):return copy.deepcopy(self.objects[ident])
        vault=MemoryVault()
        def wait(seconds):at[0]+=timedelta(seconds=seconds)
        with tempfile.TemporaryDirectory() as tmp:
            source=Source('K'*30,tmp,vault,opener=lambda *_,**__:Response(responses.pop(0).encode()),clock=lambda:at[0],wait=wait)
            captured=source.collect(row,DAY,at[0]+timedelta(minutes=5))
            self.assertEqual(captured['status'],'COLLECTED_NOT_VALIDATED')
            ident=captured['private_manifest_receipt']['id']
            restored=restore_bundle(vault,DAY,ident)
            self.assertEqual(restored['pages'][0]['raw'],captured['pages'][0]['raw'])
            manifest=json.loads(vault.objects[ident]['event']['raw'])
            vault.objects[manifest['page_ids'][0]]['event']['raw']='tampered'
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):restore_bundle(vault,DAY,ident)

    def test_session_publishes_candidate_then_withdrawal_without_waiting_for_source(self):
        from stage5_session import Session
        from test_fast_selection import records
        from test_close_research import DAY as day, ref
        from test_convergence import SYMBOL
        gate=threading.Event();published=[]
        class FakeSource:
            def collect(self,*_,**__):gate.wait(1);return {'source':'FUGLE','status':'SOURCE_INCOMPLETE','error':'SOURCE_TEST_INCOMPLETE'}
        class FakePublisher:
            def publish(self,view,deadline):published.append(copy.deepcopy(view));return {'status':'TEST_ONLY'}
        with tempfile.TemporaryDirectory() as tmp:
            source=FakeSource();source.directory=Path(tmp)/'private';source.directory.mkdir()
            session=Session(day,[SYMBOL],Path(tmp)/'session',source,FakePublisher(),clock=lambda:f.parsed_time(day+'T13:35:00+08:00'))
            try:
                for record in records()[:3]:session.feed(record)
                self.assertEqual(len(session.last['rows']),1);self.assertEqual(session.last['verified_count'],0)
                session.tick();self.assertTrue(session.queue.tasks)
                before=session.last['version']
                session.feed(ref('close_reference_C',price='105'))
                self.assertEqual(session.last['rows'],[]);self.assertGreater(session.last['version'],before)
                self.assertEqual(session.last['retracted'][0]['code'],'2330')
                gate.set();session.close()
                self.assertEqual(published[-1]['rows'],[])
                self.assertTrue(all(v['verified_count']==0 for v in published))
            finally:gate.set();session.queue.close()

    def test_journal_bridge_reads_existing_fsynced_batch_and_never_calls_market_api(self):
        from fast_capture_journal import Journal
        from stage5_journal_bridge import bridge
        at=[f.parsed_time(DAY+'T13:35:00+08:00')];calls=[]
        def wait(_):at[0]+=timedelta(hours=1)
        def open(request,timeout):
            self.assertIn('/private-mis-journal/',request.full_url);self.assertEqual(timeout,3)
            body=json.loads(request.data)['body'];calls.append(body)
            return Response(json.dumps({'id':body['id'],'sha256':body['event']['sha256'],'private_written_at':at[0].isoformat()}).encode())
        with tempfile.TemporaryDirectory() as tmp:
            journal=Journal(tmp,clock=lambda:at[0].isoformat())
            journal.append({'received_at':(at[0]-timedelta(seconds=1)).isoformat(),'phase':'close_reference_A'})
            result=bridge(journal.events,DAY,token='c'*64,opener=open,clock=lambda:at[0],wait=wait)
            self.assertEqual(result['written_batches'],1);self.assertEqual(len(calls),1)
            self.assertNotIn('c'*64,canonical(calls))


if __name__=='__main__':unittest.main()
