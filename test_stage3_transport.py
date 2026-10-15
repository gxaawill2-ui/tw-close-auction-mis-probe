import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
import freshness as f
from stage3_fixtures import DAY,example
from stage3_provider import Collector
from stage3_publication import Publisher,envelope
import stage3_ticks

class Response(io.BytesIO):
    status=200;headers={}

class TransportTests(unittest.TestCase):
    def test_restart_resumes_max_saved_version_without_restoring_verified_flags(self):
        from stage3_run import saved_version
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);(directory/'publication').mkdir()
            saved={'trade_date':DAY,'mode':'LIVE','version':20,'validated':True}
            (directory/'stage3-results.json').write_text(json.dumps(saved))
            (directory/'publication/publication-outbox.json').write_text(json.dumps({'body':{**saved,'version':21}}))
            self.assertEqual(saved_version(directory,DAY),21)
            self.assertEqual(saved_version(directory,'2026-10-15'),0)
            saved['version']=True;(directory/'stage3-results.json').write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError,'SAVED_PUBLICATION_VERSION'):saved_version(directory,DAY)

    def test_restart_preserves_existing_publication_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            prior=[{'version':1,'status':'WRITTEN'}]
            Path(d,'publication-receipts.json').write_text(json.dumps(prior))
            publisher=self.make_publisher(d,lambda *_,**__:Response(b'{}'))
            publisher.publish({'version':2},f.parsed_time(DAY+'T13:40:00+08:00'))
            saved=json.loads(Path(d,'publication-receipts.json').read_text())
            self.assertEqual(saved[0],prior[0]);self.assertEqual(saved[1]['version'],2)

    def test_background_publication_does_not_block_and_coalesces_waiting_views(self):
        from stage3_publication import BackgroundPublisher
        import threading
        release=threading.Event();started=threading.Event();versions=[]
        class Stub:
            def publish(self,view,deadline):
                versions.append(view['version']);started.set()
                if view['version']==1:release.wait(2)
                return {'status':'WRITTEN'}
        queue=BackgroundPublisher(Stub(),f.parsed_time(DAY+'T13:40:00+08:00'))
        try:
            queue.submit({'version':1});self.assertTrue(started.wait(1))
            queue.submit({'version':2});queue.submit({'version':3})
            self.assertFalse(queue.future.done());release.set();queue.close()
            self.assertEqual(versions,[1,3])
        finally:release.set()

    def test_stage3_watch_refuses_historical_backfill(self):
        from stage3_run import watch
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'BACKFILL'):watch('unused',[],'2020-01-01',d)

    def test_no_key_no_network(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{},clear=True):
            collector=Collector(d,opener=lambda *_:self.fail('must not request'))
            self.assertEqual(collector.collect({'code':'2330','ex':'tse'},DAY,f.parsed_time(DAY+'T13:40:00+08:00'))['status'],'NOT_CONFIGURED')

    def test_authenticated_paging_raw_is_saved_and_loaded_without_key(self):
        row,bundle=example(page_size=500);responses=[bundle['quote_before']['raw'],bundle['pages'][0]['raw'],bundle['quote_after']['raw']]
        requests=[]
        def opener(req,timeout):requests.append(req);return Response(responses.pop(0).encode())
        now=f.parsed_time(DAY+'T13:35:00+08:00')
        with tempfile.TemporaryDirectory() as d:
            collector=Collector(d,api_key='fake-private-test-key',opener=opener,clock=lambda:now,wait=lambda _:None)
            result=collector.collect(row,DAY,now+timedelta(minutes=5))
            proof=stage3_ticks.load_bundle(collector.directory/result['manifest_path'])
            self.assertIn('raw',proof['pages'][0]);self.assertNotIn('fake-private-test-key',json.dumps(result))
            for event in [proof['quote_before'],*proof['pages'],proof['quote_after']]:
                self.assertLessEqual(event['received_at'],event['persisted_at'])
            self.assertIn('isTrial=false',requests[1].full_url)
            self.assertEqual(result['status'],'COLLECTED_NOT_VALIDATED')

    def test_source_budget_keeps_partial_evidence(self):
        row,bundle=example(page_size=500);raw=bundle['quote_before']['raw'].encode()
        now=f.parsed_time(DAY+'T13:35:00+08:00')
        with tempfile.TemporaryDirectory() as d:
            collector=Collector(d,api_key='fake',max_requests=1,opener=lambda *_ ,**__:Response(raw),clock=lambda:now)
            result=collector.collect(row,DAY,now+timedelta(minutes=5))
        self.assertEqual(result['status'],'SOURCE_INCOMPLETE');self.assertEqual(result['error'],'SOURCE_REQUEST_BUDGET_EXHAUSTED')

    def test_rate_limit_disables_further_requests(self):
        row,_=example();now=f.parsed_time(DAY+'T13:35:00+08:00')
        def fail(*_,**__):raise urllib.error.HTTPError('safe-url',429,'limited',{},None)
        with tempfile.TemporaryDirectory() as d:
            collector=Collector(d,api_key='fake',opener=fail,clock=lambda:now)
            collector.collect(row,DAY,now+timedelta(minutes=5));self.assertTrue(collector.stopped)

    def test_source_deadline_does_not_make_a_late_request(self):
        row,_=example();now=f.parsed_time(DAY+'T13:39:55+08:00')
        with tempfile.TemporaryDirectory() as d:
            collector=Collector(d,api_key='fake',clock=lambda:now,opener=lambda *_:self.fail('late request'))
            result=collector.collect(row,DAY,now+timedelta(seconds=5))
        self.assertEqual(result['error'],'SOURCE_DEADLINE_INSUFFICIENT_BUDGET')

    def make_publisher(self,d,opener,wait=lambda _:None):
        now=f.parsed_time(DAY+'T13:35:00+08:00')
        return Publisher('http://127.0.0.1:9999',d,publish_token='test-token',decision_key='test-key',opener=opener,wait=wait,clock=lambda:now)

    def test_publication_transient_failure_retries_same_version(self):
        calls=[];view={'version':1}
        def opener(req,timeout):
            calls.append(req.data)
            if len(calls)==1:raise urllib.error.HTTPError('safe-url',503,'retry',{},None)
            import hashlib
            result={'version':1,'sha256':hashlib.sha256(stage3_ticks.canonical(view).encode()).hexdigest(),'public_written_at':DAY+'T13:35:01+08:00'}
            return Response(json.dumps(result).encode())
        with tempfile.TemporaryDirectory() as d:
            p=self.make_publisher(d,opener);result=p.publish(view,f.parsed_time(DAY+'T13:40:00+08:00'))
            self.assertEqual(result['status'],'WRITTEN');self.assertEqual(len(result['attempts']),2)
            self.assertIsNone(result['public_observed_at']);self.assertEqual(calls[0],calls[1])

    def test_publication_auth_failure_does_not_loop(self):
        def fail(*_,**__):raise urllib.error.HTTPError('safe-url',401,'denied',{},None)
        with tempfile.TemporaryDirectory() as d:
            result=self.make_publisher(d,fail).publish({'version':1},f.parsed_time(DAY+'T13:40:00+08:00'))
        self.assertEqual(len(result['attempts']),1);self.assertEqual(result['status'],'PUBLICATION_PENDING')

    def test_wrong_publication_receipt_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            result=self.make_publisher(d,lambda *_,**__:Response(b'{"version":1,"sha256":"wrong"}')).publish({'version':1},f.parsed_time(DAY+'T13:40:00+08:00'))
        self.assertEqual(result['status'],'PUBLICATION_PENDING')

    def test_unsigned_flags_cannot_keep_same_signature(self):
        first=envelope({'version':1,'validated':False},'private-test');second=envelope({'version':1,'validated':True},'private-test')
        self.assertNotEqual(first['signature'],second['signature'])

    def test_non_local_plaintext_endpoint_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'HTTPS'):Publisher('http://example.org',d,publish_token='x',decision_key='y')

if __name__=='__main__':unittest.main()
