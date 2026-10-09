import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from index_events import *

SEEN='2026-10-09T11:00:00+08:00'
URL='https://example.org/official.pdf'
CAL={'2026':load(ROOT/'state/calendars/2026.json')}

class EventTests(unittest.TestCase):
    def event(self):
        x=new_event('MSCI','MSCI Taiwan','November 2026',URL,SEEN)
        x.update(announcement_date='2026-11-11',effective_date='2026-12-01')
        return x

    def test_msci_announcement_effective_and_expected_close(self):
        text='November 2026 Index Review\nAnnouncement date: November 11, 2026\nEffective date: December 01, 2026'
        x=normalize_dates(parse_msci_schedule(text,URL,SEEN)[0],CAL)
        self.assertEqual(x['announcement_date'],'2026-11-11')
        self.assertEqual(x['effective_date'],'2026-12-01')
        self.assertEqual(x['closing_impact_date'],'2026-11-30')
        self.assertEqual(x['close_date_status'],EXPECTED)

    def test_holiday_official_calendar_and_cross_year_unknown(self):
        self.assertFalse(trading_day('2026-10-09',CAL))
        self.assertEqual(offset_trading('2026-10-12',-1,CAL),'2026-10-08')
        self.assertIsNone(offset_trading('2027-01-04',-1,CAL))
        x=self.event();x['effective_date']='2027-03-01'
        self.assertIsNone(normalize_dates(x,CAL)['closing_impact_date'])

    def test_explicit_close_sentence_is_required(self):
        text='「臺灣指數公司測試指數」成分股審核結果\n2026年10月2日\n變動將自2026年10月2日(星期五)交易結束後生效(亦即自2026年10月5日(星期一)起生效)。\n成分股納入（1）:\n2330 台積電\n成分股刪除（0）:\n無\n*註'
        x=parse_tip_notice(text,URL,SEEN,{'2330':'TWSE'})[0]
        self.assertEqual(x['close_date_status'],CONFIRMED)
        self.assertEqual(x['closing_impact_date'],'2026-10-02')
        self.assertEqual(x['affected_stocks'][0]['market'],'TWSE')
        self.assertEqual(x['affected_stocks'][0]['weight_after'],None)
        self.assertEqual(parse_tip_notice(text.replace('交易結束後',''),URL,SEEN),[])

    def test_schedule_after_close_announcement_is_not_close_implementation(self):
        text='2026年11月指數定期審核日程表\n臺灣指數公司測試指數 2026/11/17 2026/11/18'
        x=normalize_dates(parse_tip_schedule(text,URL,SEEN)[0],CAL)
        self.assertEqual(x['announcement_time'],'AFTER_CLOSE')
        self.assertIsNone(x['closing_impact_date'])
        self.assertEqual(x['close_date_status'],UNVERIFIED)

    def test_etf_multiday_window_skips_christmas(self):
        x=self.event();x.update(source_organization='FTSE',effective_date='2026-12-21',
            implementation_window={'start':'2026-12-21','trading_days':5})
        x=normalize_dates(x,CAL)
        self.assertEqual(x['implementation_window']['dates'],['2026-12-21','2026-12-22','2026-12-23','2026-12-24','2026-12-28'])

    def test_mapping_many_etfs_many_events_and_active_excluded(self):
        x=self.event();y=copy.deepcopy(x);y['event_id']='second'
        maps=[{'etf_code':c,'index_name':'MSCI Taiwan','mapping_status':'CONFIRMED','management_type':m} for c,m in [('0050','PASSIVE'),('006208','PASSIVE'),('00981A','ACTIVE')]]
        out=attach_mapping([x,y],maps)
        self.assertEqual(out[0]['related_etf_codes'],['0050','006208'])
        self.assertEqual(out[1]['related_etf_codes'],['0050','006208'])

    def test_correction_idempotency_and_asof_old_version(self):
        x=self.event();fresh=copy.deepcopy(x);fresh['effective_date']='2026-12-02'
        later='2026-11-12T11:00:00+08:00'
        merged=merge_events([x],[fresh],later)
        self.assertEqual(len(merged),1);self.assertEqual(len(merged[0]['change_history']),1)
        self.assertEqual(as_of_version(merged[0],SEEN)['effective_date'],'2026-12-01')
        again=merge_events(merged,[fresh],later)
        self.assertEqual(len(again[0]['change_history']),1)

    def test_announced_notice_not_downgraded_by_schedule(self):
        x=self.event();x['evidence_level']='OFFICIAL_IMPLEMENTATION'
        fresh=copy.deepcopy(x);fresh['evidence_level']='OFFICIAL_SCHEDULE'
        self.assertEqual(merge_events([x],[fresh],SEEN)[0]['evidence_level'],'OFFICIAL_IMPLEMENTATION')

    def test_stock_market_match_and_no_guessing(self):
        x=self.event();x['closing_impact_date']='2026-11-30';x['affected_stocks']=[dict(code='2330',market='TWSE',market_status='OFFICIAL_CONFIRMED',change_type='ADDITION')]
        candidate={'trade_date':'2026-11-30','candidate_list':[dict(code='2330',market='TWSE'),dict(code='2330',market='TPEx'),dict(code='3073',market='TPEx')]}
        rows=annotate(candidate,[x],'2026-11-30T13:35:00+08:00')['candidate_annotations']
        self.assertEqual(rows[0]['stock_event_relation'],'OFFICIAL_MATCH')
        self.assertEqual(rows[1]['stock_event_relation'],'MARKET_DAY_ONLY')
        self.assertEqual(rows[2]['related_index_events'],[])

    def test_late_information_cannot_be_used_in_live_backtest(self):
        x=self.event();x['first_seen_at']='2026-11-30T17:00:00+08:00';x['closing_impact_date']='2026-11-30'
        self.assertIsNone(as_of_version(x,'2026-11-30T13:35:00+08:00'))

    def test_source_timeout_preserves_events_and_never_empty_success(self):
        class Fail:
            attempts=2
            def get(self,url): raise TimeoutError('source timeout')
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);b=r/'state/events'
            write(b/'sources.json',[{'source_id':'msci','enabled':True,'parser':'msci_schedule','url':URL}])
            write(b/'events-index.json',{'events':[self.event()]})
            write(b/'source-health.json',{'sources':[{'source_id':'msci','last_success_at':SEEN}]})
            health=run(r,Fail())
            self.assertEqual(health[0]['status'],'STALE')
            self.assertEqual(len(load(b/'events-index.json')['events']),1)
            self.assertIn('timeout',health[0]['error'])

    def test_official_calendar_rejects_wrong_year_and_empty_response(self):
        raw=json.dumps({'stat':'ok','title':'115 年市場開休市日期','data':[['10月09日','休市','']]})
        self.assertEqual(parse_calendar(raw,2026,URL,SEEN)['closed_dates'],['2026-10-09'])
        with self.assertRaises(ValueError): parse_calendar(raw,2027,URL,SEEN)
        with self.assertRaises(ValueError): parse_calendar('{"stat":"ok","data":[]}',2026,URL,SEEN)

    def test_unknown_market_never_attaches(self):
        x=self.event();x['closing_impact_date']='2026-11-30';x['affected_stocks']=[dict(code='2330',market=None,market_status='UNKNOWN',change_type='ADDITION')]
        c={'trade_date':'2026-11-30','candidate_list':[dict(code='2330',market='TWSE')]}
        self.assertEqual(annotate(c,[x],'2026-11-30T13:35:00+08:00')['candidate_annotations'][0]['related_index_events'],[])

    def test_scan_workflow_isolated_and_never_market_dispatch(self):
        text=(ROOT/'.github/workflows/index-events.yml').read_text()
        self.assertIn("20 0,9 * * *",text)
        self.assertNotIn('probe.py',text);self.assertNotIn('dispatches',text)
        self.assertNotIn('secrets.',text)
        self.assertIn("github.event_name != 'push'",text)

    def test_oct8_candidate_evidence_exactly_preserved(self):
        data=load(ROOT/'state/candidates/2026-10-08.json')
        expected={'3073':(17,44),'3259':(1,8),'3684':(66,1255),'4706':(36,498),'5355':(1,121),'5543':(6,8),'2024':(7,73)}
        for r in data['candidate_list']:
            self.assertEqual((float(r['closing_auction_volume']),float(r['intraday_total_volume'])),expected[r['code']])
            self.assertAlmostEqual(float(r['closing_volume_ratio_pct']),expected[r['code']][0]/expected[r['code']][1]*100)
        sidecar=load(ROOT/'state/events/candidate-annotations/2026-10-08.json')
        self.assertEqual(sidecar['live_as_of']['event_ids'],[])
        self.assertTrue(all(not r['related_index_events'] for r in sidecar['live_as_of']['candidate_annotations']))

if __name__=='__main__': unittest.main()
