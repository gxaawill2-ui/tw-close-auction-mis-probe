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
