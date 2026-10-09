import copy
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch, MagicMock
from index_events import *

SEEN='2026-10-09T16:00:00+08:00'
LATER='2026-10-09T17:20:00+08:00'
MASTER='https://openapi.twse.com.tw/v1/opendata/t187ap47_L'
FIXTURE=ROOT/'fixtures/index-events'

class SourceRecoveryTests(unittest.TestCase):
    def rows(self):
        return parse_etf_master((FIXTURE/'twse-etf-master.json').read_bytes(),MASTER,SEEN)
    def event(self,org='TIP',source='https://example.org/one.pdf',ed='2026-11-18'):
        x=new_event(org,'臺灣指數公司測試指數','2026-11',source,SEEN)
        x.update(effective_date=ed,closing_impact_date='2026-11-17',close_date_status=CONFIRMED,evidence_level='OFFICIAL_IMPLEMENTATION',event_status='ANNOUNCED')
        return x
    def test_official_master_real_response_classification(self):
        rows=self.rows();self.assertEqual(len(rows),271)
        eligible=[r for r in rows if r['calendar_eligible']]
        self.assertEqual(len(eligible),66)
        self.assertTrue(all(r['management_type']=='PASSIVE' and r['tracks_taiwan_equities']=='YES' for r in eligible))
        self.assertEqual(next(r for r in rows if r['etf_code']=='0050')['listing_date'],'2003-06-30')
    def test_new_domestic_passive_etf_discovered_and_mapped(self):
        raw=json.loads((FIXTURE/'twse-etf-master.json').read_text())[0]
        raw.update(基金代號='00499',基金類型='國內成分證券指數股票型基金',基金簡稱='新上市台灣ETF',上市日期='1151008',標的指數追蹤指數名稱='ignored')
        raw['標的指數/追蹤指數名稱']='全新臺灣指數'
        rows=parse_etf_master(json.dumps([raw]),MASTER,SEEN)
        out,stats=update_etf_master([],rows,SEEN)
        self.assertEqual(stats['newly_observed_etfs'],1);self.assertTrue(out[0]['calendar_eligible'])
        self.assertEqual(merge_mappings([],out,SEEN)[0]['index_name'],'全新臺灣指數')
    def test_active_benchmark_not_a_tracking_index(self):
        rows=self.rows();active=[r for r in rows if r['management_type']=='ACTIVE']
        self.assertEqual(len(active),33)
        self.assertTrue(all(r['index_name'] is None and not r['calendar_eligible'] for r in active))
    def test_foreign_and_leverage_not_calendar_eligible(self):
        rows=self.rows()
        self.assertFalse(next(r for r in rows if r['etf_code']=='00632R')['calendar_eligible'])
        self.assertFalse(next(r for r in rows if r['etf_code']=='00646')['calendar_eligible'])
    def test_unknown_type_and_missing_index_fail_closed(self):
        raw=json.loads((FIXTURE/'twse-etf-master.json').read_text())[0]
        raw['基金類型']='尚待分類';raw['標的指數/追蹤指數名稱']='';raw['是否包含國外成分股']=''
        row=parse_etf_master(json.dumps([raw]),MASTER,SEEN)[0]
        self.assertEqual(row['management_type'],'UNKNOWN');self.assertEqual(row['mapping_status'],'UNKNOWN');self.assertFalse(row['calendar_eligible'])
    def test_empty_changed_schema_future_date_and_duplicate_rejected(self):
        raw=json.loads((FIXTURE/'twse-etf-master.json').read_text())[0]
        for payload in [[],[{}],[raw,raw],[{**raw,'出表日期':'1160101'}]]:
            with self.subTest(payload=str(payload)[:60]),self.assertRaises(ValueError):parse_etf_master(json.dumps(payload),MASTER,SEEN)
    def test_api_absence_is_not_delisting(self):
        previous=self.rows();fresh=copy.deepcopy(previous[:-1])
        out,_=update_etf_master(previous,fresh,LATER)
        missing=next(r for r in out if r['etf_code']==previous[-1]['etf_code'])
        self.assertEqual(missing['lifecycle_status'],'NOT_IN_LATEST_MASTER');self.assertIsNone(missing['delisting_date'])
    def test_only_explicit_delisting_date_marks_delisted(self):
        raw=json.loads((FIXTURE/'twse-etf-master.json').read_text())[20];raw['下市日期']='1151008'
        row=parse_etf_master(json.dumps([raw]),MASTER,SEEN)[0]
        self.assertEqual(row['lifecycle_status'],'DELISTED');self.assertFalse(row['calendar_eligible'])
    def test_snapshot_shrink_does_not_destroy_master(self):
        with self.assertRaisesRegex(ValueError,'shrink'):update_etf_master(self.rows(),self.rows()[:10],LATER)
    def test_same_source_index_rename_preserves_history(self):
        x=next(r for r in self.rows() if r['etf_code']=='0050');y={**x,'index_name':'新指數名稱'}
        updated=merge_mappings([x],[y],LATER)[0]
        self.assertEqual(updated['first_seen_at'],SEEN);self.assertEqual(len(updated['change_history']),1)
    def test_different_mapping_sources_conflict_persists(self):
        x=next(r for r in self.rows() if r['etf_code']=='0050');y={**x,'index_name':'另一個指數','source_url':'https://example.org/issuer'}
        out=merge_mappings([x],[y],LATER);self.assertEqual(out[0]['mapping_status'],'CONFLICT')
        self.assertEqual(merge_mappings(out,[y],LATER)[0]['mapping_status'],'CONFLICT')
    def test_reviewed_alias_does_not_merge_different_variants(self):
        self.assertEqual(index_identity('臺灣50指數'),index_identity('FTSE TWSE Taiwan 50 Index'))
        self.assertNotEqual(index_identity('臺灣50正向兩倍指數'),index_identity('臺灣50指數'))
        self.assertNotEqual(index_identity('MSCI Taiwan'),index_identity('MSCI Taiwan ESG'))
    def test_yuanta_real_profiles_effective_dates_only(self):
        expected={'0050':'2026-09-21','0051':'2026-09-21','0056':'2026-06-26','006203':'2026-09-01'}
        for c,ed in expected.items():
            m=next(r for r in self.rows() if r['etf_code']==c)
            event=parse_yuanta_profile((FIXTURE/f'yuanta-{c}.html').read_bytes(),'https://www.yuantaetfs.com/product/detail/'+c+'/Basic_information',SEEN,m)[0]
            self.assertEqual(event['effective_date'],ed);self.assertIsNone(event['closing_impact_date']);self.assertIsNone(event['announcement_date'])
            self.assertEqual(event['close_date_status'],UNVERIFIED);self.assertEqual(event['affected_stocks'],[])
    def test_general_dividend_news_not_review_event(self):
        m=next(r for r in self.rows() if r['etf_code']=='0050')
        with self.assertRaises(ValueError):parse_yuanta_profile(b'<p>(0050) dividend 2026/11/17</p>',MASTER,SEEN,m)
    def test_wrong_product_or_index_rejected(self):
        raw=(FIXTURE/'yuanta-0050.html').read_bytes();m=next(r for r in self.rows() if r['etf_code']=='0051')
        with self.assertRaises(ValueError):parse_yuanta_profile(raw,MASTER,SEEN,m)
    def test_two_official_sources_one_event_preserves_both(self):
        x=self.event();y=self.event('ISSUER','https://example.org/two.pdf')
        out=merge_events([x],[y],LATER)
        self.assertEqual(len(out),1);self.assertEqual(len(out[0]['source_evidence']),2)
        self.assertEqual(out[0]['first_seen_at'],SEEN)
    def test_schedule_cannot_drop_implementation_or_secondary_evidence(self):
        x=self.event();y=self.event('TIP','https://example.org/schedule.pdf')
        y.update(evidence_level='OFFICIAL_SCHEDULE',closing_impact_date=None,close_date_status=UNVERIFIED,event_status='SCHEDULED')
        out=merge_events([x],[y],LATER)[0]
        self.assertEqual(out['close_date_status'],CONFIRMED)
        self.assertEqual(out['evidence_level'],'OFFICIAL_IMPLEMENTATION')
        self.assertEqual({e['source_url'] for e in out['source_evidence']},{x['source_url'],y['source_url']})
        self.assertEqual(merge_events([out],[y],LATER)[0]['change_history'],out['change_history'])
    def test_conflicting_dates_null_out_and_block_stock_annotation(self):
        x=self.event();y=self.event('ISSUER','https://example.org/two.pdf','2026-11-19')
        out=merge_events([x],[y],LATER)[0]
        self.assertEqual(out['event_status'],'CONFLICT');self.assertIsNone(out['effective_date'])
        c={'trade_date':'2026-11-17','candidate_list':[{'code':'2330','market':'TWSE'}]}
        self.assertEqual(annotate(c,[out],LATER)['event_ids'],[])
    def test_cross_source_correction_resolves_and_repeated_merge_idempotent(self):
        x=self.event();y=self.event('ISSUER','https://example.org/two.pdf','2026-11-19')
        out=merge_events([x],[y],LATER);y['effective_date']='2026-11-18'
        resolved=merge_events(out,[y],LATER)
        self.assertNotEqual(resolved[0]['event_status'],'CONFLICT')
        self.assertEqual(merge_events(resolved,[y],LATER)[0]['change_history'],resolved[0]['change_history'])
    def test_correction_asof_keeps_old_fact(self):
        x=self.event();y=copy.deepcopy(x);y['effective_date']='2026-11-19'
        z=merge_events([x],[y],LATER)[0]
        self.assertEqual(as_of_version(z,SEEN)['effective_date'],'2026-11-18')
        self.assertEqual(as_of_version(z,LATER)['effective_date'],'2026-11-19')
    def test_source_400_and_403_not_success_or_data_loss(self):
        class F:
            attempts=1
            def get(self,url):raise HTTPError(url,403,'forbidden',{},None)
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);b=r/'state/events'
            write(b/'sources.json',[{'source_id':'master','enabled':True,'url':MASTER,'parser':'etf_master'}])
            write(b/'events-index.json',{'events':[self.event()]})
            write(b/'etf-master.json',{'etfs':self.rows()})
            health=run(r,F());self.assertEqual(health[0]['classification'],'RESTRICTED')
            self.assertEqual(len(load(b/'etf-master.json')['etfs']),271)
            self.assertEqual(len(load(b/'events-index.json')['events']),1)
    def test_fetcher_403_never_retries_or_changes_identity(self):
        error=HTTPError(MASTER,403,'forbidden',{},None)
        f=Fetcher()
        with patch('index_events.urlopen',side_effect=error) as get:
            with self.assertRaises(HTTPError):f._request(MASTER)
            self.assertEqual(get.call_count,1)
    def test_http400_bounded_retry(self):
        f=Fetcher()
        with patch('index_events.urlopen',side_effect=HTTPError(MASTER,400,'bad',{},None)) as get,patch('index_events.time.sleep'):
            with self.assertRaises(HTTPError):f._request(MASTER)
            self.assertEqual(get.call_count,2)
    def test_robots_disallowed_no_content_request(self):
        f=Fetcher()
        with patch.object(f,'_request',return_value=b'User-agent: *\nDisallow: /v1/') as get:
            with self.assertRaisesRegex(RuntimeError,'ROBOTS_DISALLOWED'):f.get(MASTER)
            self.assertEqual(get.call_count,1)
    def test_pdf_login_or_changed_layout_is_unknown(self):
        with self.assertRaises(ValueError):pdf_text(b'<html>login</html>')
        with self.assertRaises(ValueError):parse_msci_schedule('changed PDF table',MASTER,SEEN)
        with self.assertRaises(ValueError):parse_tip_schedule('changed PDF table',MASTER,SEEN)
    def test_announcement_date_is_not_first_arbitrary_body_date(self):
        txt='「臺灣指數公司測試指數」變動將自2026年11月17日交易結束後生效，亦即自2026年11月18日起生效'
        self.assertIsNone(parse_tip_notice(txt,MASTER,SEEN)[0]['announcement_date'])
    def test_reverse_announcement_effective_order_rejected(self):
        x=self.event();x['announcement_date']='2026-11-20'
        with self.assertRaises(ValueError):normalize_dates(x,{})
    def test_unpublished_weights_are_null(self):
        x=self.event();self.assertEqual(x['affected_stocks'],[])
    def test_multiday_separate_status_and_dates(self):
        x=self.event();x.update(close_date_status=EXPECTED,closing_impact_date=None,implementation_window={'start':'2026-12-21','trading_days':5})
        y=normalize_dates(x,{'2026':load(ROOT/'state/calendars/2026.json')})
        self.assertEqual(y['close_date_status'],MULTIDAY);self.assertEqual(y['implementation_window']['end'],'2026-12-28')

class PublicTIPRecoveryTests(unittest.TestCase):
    def test_public_index_implementation_is_confirmed_but_fund_trades_unknown(self):
        rows=parse_tip_public_news((FIXTURE/'tip-452.html').read_bytes(),'https://taiwanindex.com.tw/news/452',SEEN)
        self.assertEqual(len(rows),5)
        self.assertTrue(all(r['close_date_status']==CONFIRMED and not r['affected_stocks'] for r in rows))
        x=next(r for r in rows if r['related_etf_codes']==['00919'])
        self.assertEqual(x['closing_impact_date'],'2026-09-16');self.assertEqual(x['effective_date'],'2026-09-17')
        self.assertEqual(x['official_announced_at'],'2026-09-16T17:13:00+08:00')
        self.assertEqual(x['implementation_scope'],'INDEX_AFTER_CLOSE; ETF_TRADE_TIME_UNKNOWN')
        self.assertIsNone(as_of_version(x,'2026-09-16T13:25:00+08:00'))
    def test_public_review_no_official_stock_list_generated(self):
        rows=parse_tip_public_news((FIXTURE/'tip-454.html').read_bytes(),'https://taiwanindex.com.tw/news/454',SEEN)
        self.assertEqual(len(rows),4)
        self.assertTrue(all(r['affected_stocks']==[] and r['announcement_time']=='17:00' for r in rows))
    def test_effective_date_only_sentence_is_not_close_confirmation(self):
        raw=(FIXTURE/'tip-454.html').read_bytes().replace('交易結束後'.encode(),b'')
        self.assertEqual(parse_tip_public_news(raw,MASTER,SEEN),[])

if __name__=='__main__':unittest.main()
