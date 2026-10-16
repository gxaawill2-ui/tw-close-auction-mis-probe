import copy
from dataclasses import replace
import hashlib
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from stage3_fixtures import DAY,example,mutate,micros
from stage3_ticks import inspect,LIVE_CONTRACT,TEST_CONTRACT,canonical,last_pre_group
from stage5_remote_journal import consume
from fast_capture_journal import Journal
import freshness as f


class BoundaryTests(unittest.TestCase):
    def test_unknown_serial_contract_never_picks_max_serial_price(self):
        row,b=example()
        mutate(b['pages'][1],lambda d:d['data'][0].update(time=micros('13:24:59.900000')))
        policy=replace(TEST_CONTRACT,same_timestamp_order='UNSPECIFIED')
        r=inspect(b,row,DAY,DAY+'T13:35:05+08:00',mode='SYNTHETIC',contract=policy)
        self.assertIn('PRE_CUTOFF_SAME_MICROSECOND_PRICE_AMBIGUOUS',r['reasons'])
        self.assertIsNone(r['pre_tick']);self.assertFalse(r['synthetic_pre_passed'])

    def test_same_price_ties_do_not_require_invented_serial_order(self):
        row,b=example()
        mutate(b['pages'][1],lambda d:d['data'][0].update(time=micros('13:24:59.900000'),price=100,serial=1199))
        policy=replace(TEST_CONTRACT,same_timestamp_order='UNSPECIFIED')
        r=inspect(b,row,DAY,DAY+'T13:35:05+08:00',mode='SYNTHETIC',contract=policy)
        self.assertTrue(r['pre_group_price_unique']);self.assertTrue(r['synthetic_pre_passed'])
        self.assertFalse(r['validated']);self.assertFalse(LIVE_CONTRACT.live_release)

    def test_earlier_price_tie_does_not_decide_latest_pre_group(self):
        row,b=example()
        mutate(b['pages'][1],lambda d:d['data'][1].update(time=micros('13:24:59.100000')))
        policy=replace(TEST_CONTRACT,same_timestamp_order='UNSPECIFIED')
        r=inspect(b,row,DAY,DAY+'T13:35:05+08:00',mode='SYNTHETIC',contract=policy)
        self.assertTrue(r['synthetic_pre_passed']);self.assertEqual(r['pre_tick']['price'],100)

    def test_exact_cutoff_excluded_and_missing_pre_never_filled(self):
        ticks=[{'time':micros('13:25:00'),'price':999,'serial':99}]
        self.assertEqual(last_pre_group(ticks,f.parsed_time(DAY+'T13:25:00+08:00')),[])


class RemoteJournalTests(unittest.TestCase):
    def setup_batch(self,tmp):
        now=f.parsed_time(DAY+'T13:35:00+08:00')
        j=Journal(tmp,clock=lambda:now.isoformat())
        record={'received_at':(now-timedelta(seconds=1)).isoformat(),'phase':'close_reference_C'}
        journal=j.append(record);raw=canonical(journal)
        event={'source':'MIS','raw':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
        ident=hashlib.sha256(canonical(event).encode()).hexdigest()
        saved={'id':ident,'trade_date':DAY,'scope':'PRIVATE_MIS_JOURNAL','event':event}
        index={'entries':[{'id':ident,'sha256':event['sha256']}]}
        class Session:
            date=DAY
            def __init__(self):self.fed=[]
            def clock(self):return now
            def feed(self,*args):self.fed.append(args)
        return Session(),index,saved

    def test_duplicate_index_resume_and_new_process_replays_original_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            s,index,saved=self.setup_batch(tmp);seen=set()
            consume(s,index,lambda _:saved,seen);consume(s,index,lambda _:saved,seen)
            self.assertEqual(len(s.fed),1)
            consume(s,index,lambda _:saved,set())
            self.assertEqual(s.fed[0],s.fed[1])

    def test_outer_scope_date_index_hash_and_inner_provenance_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            for field,value in [('trade_date','1999-01-01'),('scope','PRIVATE_FUGLE_EVIDENCE'),('id','a'*64)]:
                s,index,saved=self.setup_batch(tmp);saved[field]=value
                with self.assertRaises(ValueError):consume(s,index,lambda _:saved,set())
                self.assertEqual(s.fed,[])
            s,index,saved=self.setup_batch(tmp);index['entries'][0]['sha256']='b'*64
            with self.assertRaises(ValueError):consume(s,index,lambda _:saved,set())
            s,index,saved=self.setup_batch(tmp)
            inner=json.loads(saved['event']['raw']);inner['sha256']='c'*64
            raw=canonical(inner);saved['event'].update(raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())
            ident=hashlib.sha256(canonical(saved['event']).encode()).hexdigest();saved['id']=ident
            index={'entries':[{'id':ident,'sha256':saved['event']['sha256']}]}
            with self.assertRaisesRegex(ValueError,'PROVENANCE'):consume(s,index,lambda _:saved,set())
            self.assertEqual(s.fed,[])

if __name__=='__main__':unittest.main()

class DurableBudgetTests(unittest.TestCase):
    def test_reserved_before_http_and_restored_after_runner_loss(self):
        from test_stage5_archive import MemoryVault
        from stage6_daily import DurableBudget
        from stage5_runtime import Source
        from test_stage5_runtime import Response
        v=MemoryVault();clock=lambda:f.parsed_time(DAY+'T13:35:00+08:00')
        budget=DurableBudget(v,DAY,clock);budget.reserve(1,DAY)
        recovered=DurableBudget(v,DAY,clock);self.assertEqual(recovered.count,1)
        row,b=example(page_size=200);calls=[]
        def open(*args,**kwargs):
            calls.append(1);self.assertEqual(DurableBudget(v,DAY,clock).count,2)
            return Response(b['quote_before']['raw'].encode())
        with tempfile.TemporaryDirectory() as tmp:
            s=Source('K'*30,tmp,v,clock=clock,opener=open,require_durable=True,reservation=recovered,max_requests=2)
            s.request(row,'quote',{},clock()+timedelta(minutes=1))
            with self.assertRaises(ValueError):s.request(row,'quote',{},clock()+timedelta(minutes=1))
        self.assertEqual(calls,[1]);self.assertEqual(DurableBudget(v,DAY,clock).count,2)

    def test_failed_reservation_never_calls_provider(self):
        from test_stage5_archive import MemoryVault
        from stage5_runtime import Source
        class Broken:
            count=0
            def reserve(self,*args):raise OSError('private-error-do-not-export')
        calls=[];clock=lambda:f.parsed_time(DAY+'T13:35:00+08:00');row,_=example()
        with tempfile.TemporaryDirectory() as tmp:
            s=Source('K'*30,tmp,MemoryVault(),clock=clock,opener=lambda *a,**k:calls.append(1),reservation=Broken())
            for _ in range(2):
                with self.assertRaises(ValueError):s.request(row,'quote',{},clock()+timedelta(minutes=1))
            self.assertTrue(s.stopped);self.assertEqual(calls,[])

    def test_stale_inflight_candidate_requeues_without_another_mis_batch(self):
        from stage5_session import Session
        from test_fast_selection import records
        from test_close_research import DAY as day
        from test_convergence import SYMBOL
        import threading,time
        gate=threading.Event();calls=[]
        class Source:
            def collect(self,row,*args,**kwargs):
                calls.append(row['P_close'])
                if len(calls)==1:gate.wait(1)
                return {'source':'FUGLE','status':'SOURCE_INCOMPLETE','error':'SOURCE_TEST_ONLY'}
        with tempfile.TemporaryDirectory() as tmp:
            source=Source();source.directory=Path(tmp)/'private';source.directory.mkdir()
            s=Session(day,[SYMBOL],Path(tmp)/'session',source,clock=lambda:f.parsed_time(day+'T13:35:00+08:00'))
            try:
                for r in records()[:3]:s.feed(r)
                s.tick()
                for _ in range(100):
                    if calls:break
                    time.sleep(.001)
                # Change only the current fingerprint while an old result is in flight.
                row=s.engine.priority()[0];changed={**row,'P_close':'105'}
                s.engine.priority=lambda:[changed]
                s.update();gate.set()
                for _ in range(100):
                    s.tick()
                    if '105' in calls:break
                    time.sleep(.001)
                self.assertIn('105',calls)
            finally:gate.set();s.close()

class RetryPlanTests(unittest.TestCase):
    def test_targeted_delayed_only_budget_deadline_no_request(self):
        from stage6_retry import plan
        from test_stage5_pending_review import PendingReviewTests
        with tempfile.TemporaryDirectory() as tmp:
            e=PendingReviewTests().engine(tmp)
            p=plan(e,e.date+'T13:34:20+08:00')
            self.assertEqual([s['code'] for s in p['symbols']],['2330'])
            self.assertEqual(p['mis_requests'],0);self.assertEqual(e.view()['rows'],[])
            key=p['symbols'][0]['attempt_key']
            self.assertEqual(plan(e,e.date+'T13:34:20+08:00',{key:2})['symbols'],[])
            self.assertEqual(plan(e,e.date+'T13:34:43+08:00')['symbols'],[])
            e=PendingReviewTests().engine(tmp,valid_pre=False)
            self.assertEqual(plan(e,e.date+'T13:34:20+08:00')['symbols'],[])

class UniverseHandoffTests(unittest.TestCase):
    def test_saved_universe_bridge_roundtrip_matches_run_and_never_feeds_as_market_data(self):
        from stage6_universe import send,receive
        from stage5_remote_journal import consume
        from test_stage5_runtime import Response
        clock=lambda:f.parsed_time(DAY+'T13:20:00+08:00');objects={}
        def opener(req,timeout):
            self.assertIn('/private-mis-journal/',req.full_url)
            body=json.loads(req.data)['body'];objects[body['id']]=body
            return Response(json.dumps({'id':body['id'],'sha256':body['event']['sha256'],'private_written_at':clock().isoformat()}).encode())
        with tempfile.TemporaryDirectory() as tmp:
            u=[{'code':str(1000+i),'ex':'tse','name':'合成測試','market':'TWSE','trade_flags':{}} for i in range(2000)]
            path=Path(tmp)/'universe.json';path.write_text(json.dumps(u))
            send(path,DAY,'123456',Path(tmp)/'journal','a'*64,clock=clock,opener=opener)
            index={'entries':[{'id':i,'sha256':v['event']['sha256']} for i,v in objects.items()]}
            read=lambda ident:index if ident=='index' else objects[ident]
            self.assertEqual(receive(DAY,'123456',read,clock),u)
            self.assertIsNone(receive(DAY,'7890',read,clock))
            class S:
                date=DAY
                def clock(self):return clock()
                def feed(self,*args):raise AssertionError('universe metadata is not a market tick')
            seen=set();consume(S(),index,read,seen);self.assertEqual(len(seen),1)

class CatchupTests(unittest.TestCase):
    def test_restart_catches_up_before_any_new_publication(self):
        from stage5_remote_journal import follow
        from test_stage5_runtime import Response
        from urllib.parse import urlsplit
        with tempfile.TemporaryDirectory() as tmp:
            s,index,saved=RemoteJournalTests().setup_batch(tmp)
            marker=object();s.publisher=marker;s.deadline=f.parsed_time(DAY+'T14:30:00+08:00')
            now=[s.clock()];s.clock=lambda:now[0];seen_publishers=[];compiled=[]
            s.feed=lambda *args:seen_publishers.append(s.publisher)
            s.compile=lambda:compiled.append(s.publisher)
            s.tick=lambda:None
            def opener(req,timeout):
                data=index if req.full_url.endswith('/index') else saved
                return Response(json.dumps(data).encode())
            def wait(_):now[0]+=timedelta(hours=2)
            follow(s,'token',opener=opener,wait=wait)
            self.assertEqual(seen_publishers,[None]);self.assertEqual(compiled,[marker])

class PrivateProofResumeTests(unittest.TestCase):
    def test_new_runner_recovers_raw_proofs_for_revalidation_without_provider_call(self):
        from test_stage5_archive import MemoryVault
        from stage6_daily import DurableBudget
        from stage5_runtime import Source
        from test_stage5_runtime import Response
        v=MemoryVault();row,b=example(page_size=200);at=[f.parsed_time(DAY+'T13:35:00+08:00')]
        responses=[b['quote_before']['raw'],b['pages'][0]['raw'],b['quote_after']['raw']]
        def wait(seconds):at[0]+=timedelta(seconds=seconds)
        with tempfile.TemporaryDirectory() as tmp:
            src=Source('K'*30,Path(tmp)/'original',v,opener=lambda *a,**k:Response(responses.pop(0).encode()),clock=lambda:at[0],wait=wait)
            captured=src.collect(row,DAY,at[0]+timedelta(minutes=2))
            self.assertEqual(captured['status'],'COLLECTED_NOT_VALIDATED')
            target=Path(tmp)/'restored';target.mkdir()
            budget=DurableBudget(v,DAY,lambda:at[0])
            self.assertEqual(budget.restore_proofs(target,[row]),1)
            proof=target/('proof-'+row['ex']+'-'+row['code']+'.json')
            restored=json.loads(proof.read_text())
            self.assertEqual(restored['pages'][0]['sha256'],captured['pages'][0]['sha256'])
            self.assertEqual(proof.stat().st_mode&0o777,0o600)
            self.assertNotIn('validated',restored)
