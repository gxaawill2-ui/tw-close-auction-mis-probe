import copy
import json
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from stage3_fixtures import DAY,example,micros,mutate
import stage3_ticks as t
import stage3_selection as s

AS_OF=DAY+'T13:35:05+08:00'

class IndependentTicksTests(unittest.TestCase):
    def test_long_no_new_pre_trade_can_still_have_last_trade_proof(self):
        row,bundle=example();row['P_before_trade_time']='12:30:00'
        mutate(bundle['pages'][0],lambda d:d['data'][1].update(time=micros('12:30:00')))
        mutate(bundle['pages'][1],lambda d:(d['data'][0].update(time=micros('12:29:00')),d['data'][1].update(time=micros('12:28:00'))))
        self.assertTrue(self.inspect(row,bundle)['synthetic_pre_passed'])

    def test_same_microsecond_uses_serial_tiebreaker(self):
        row,bundle=example()
        mutate(bundle['pages'][1],lambda d:d['data'][0].update(time=micros('13:24:59.900000')))
        self.assertEqual(self.inspect(row,bundle)['pre_tick']['serial'],1100)

    def test_reversed_same_second_order_is_not_sorted_silently(self):
        row,bundle=example()
        mutate(bundle['pages'][0],lambda d:d['data'][1].update(time=micros('13:24:59.100000')))
        mutate(bundle['pages'][1],lambda d:d['data'][0].update(time=micros('13:24:59.900000')))
        self.assertIn('TICK_ORDER_OR_SAME_SECOND_CONFLICT',self.inspect(row,bundle)['reasons'])

    def test_no_new_close_trade_preserves_actual_trade_and_zero_auction_volume(self):
        row,bundle=example(page_size=500)
        mutate(bundle['pages'][0],lambda d:d['data'].pop(0))
        last=json.loads(bundle['pages'][0]['raw'])['data'][0]
        for event in (bundle['quote_before'],bundle['quote_after']):
            mutate(event,lambda d:d.update(lastTrade={k:last[k] for k in ('time','serial','price')},closeTime=last['time'],closePrice=100,total={'transaction':3,'tradeVolume':15,'time':last['time']}))
        row.update(P_close='100',P_close_trade_time='13:24:59',intraday_total_volume='15',closing_auction_volume='0')
        r=self.inspect(row,bundle)
        self.assertEqual(r['close_classification'],'NO_NEW_CLOSE_TRADE');self.assertTrue(r['synthetic_close_passed'])

    def test_independent_volume_conflict_blocks_complete_result(self):
        row,bundle=example();row['intraday_total_volume']='21'
        self.assertIn('MIS_INDEPENDENT_VOLUME_CONFLICT',self.inspect(row,bundle)['reasons'])

    def inspect(self,row=None,bundle=None,**kwargs):
        base,proof=example();return t.inspect(bundle or proof,row or base,DAY,AS_OF,mode='SYNTHETIC',contract=kwargs.pop('contract',t.TEST_CONTRACT),**kwargs)

    def test_complete_tick_history_is_synthetic_success_never_live_verified(self):
        r=self.inspect();self.assertTrue(r['synthetic_pre_passed']);self.assertTrue(r['synthetic_close_passed']);self.assertFalse(r['validated'])

    def test_132459_trade_replaces_earlier_132430_observation(self):
        row,bundle=example();row.update(P_before='98',P_before_trade_time='13:24:30')
        self.assertIn('MIS_INDEPENDENT_PRE_CONFLICT',self.inspect(row,bundle)['reasons'])

    def test_same_second_microseconds_and_serial_are_preserved(self):
        r=self.inspect();self.assertEqual(r['pre_tick']['time'],micros('13:24:59.900000'));self.assertEqual(r['pre_tick']['price'],100)

    def test_exact_132500_is_excluded(self):
        row,bundle=example()
        mutate(bundle['pages'][0],lambda d:d['data'][1].update(time=micros('13:25:00'),price=101))
        row.update(P_before='99',P_before_trade_time='13:24:59')
        r=self.inspect(row,bundle);self.assertTrue(r['synthetic_pre_passed']);self.assertEqual(r['pre_tick']['price'],99)

    def test_new_post_cutoff_trade_is_not_pre_price(self):
        row,bundle=example();mutate(bundle['pages'][0],lambda d:d['data'][1].update(time=micros('13:25:01'),price=101))
        row.update(P_before='99')
        self.assertEqual(self.inspect(row,bundle)['pre_tick']['price'],99)

    def test_duplicate_serial_is_invalid(self):
        row,bundle=example();mutate(bundle['pages'][0],lambda d:d['data'][1].update(serial=1200))
        self.assertIn('INVALID_DUPLICATE_OR_TRIAL_TICK',self.inspect(row,bundle)['reasons'])

    def test_unspecified_serial_gaps_are_not_asserted_packet_loss(self):
        r=self.inspect();self.assertGreater(r['serial_gap_count'],0);self.assertTrue(r['synthetic_pre_passed'])

    def test_confirmed_per_security_sequence_gap_blocks(self):
        policy=replace(t.TEST_CONTRACT,serial_scope='PER_SECURITY_CONTIGUOUS')
        self.assertIn('PER_SECURITY_SERIAL_GAP',self.inspect(contract=policy)['reasons'])

    def test_missing_page_is_detected(self):
        row,bundle=example();bundle['pages'].pop(0)
        self.assertIn('MISSING_PAGE_OR_WRONG_QUERY_SCOPE',self.inspect(row,bundle)['reasons'])

    def test_missing_terminal_page_blocks(self):
        row,bundle=example();bundle['pages'].pop()
        self.assertIn('TICK_HISTORY_TRUNCATED_OR_NO_TERMINAL_PAGE',self.inspect(row,bundle)['reasons'])

    def test_missing_inner_tick_detected_by_independent_count(self):
        row,bundle=example(page_size=500);mutate(bundle['pages'][0],lambda d:d['data'].pop(1))
        self.assertIn('TICK_COUNT_DOES_NOT_MATCH_QUOTE_TRANSACTION',self.inspect(row,bundle)['reasons'])

    def test_same_count_but_changed_volume_blocks(self):
        row,bundle=example();mutate(bundle['pages'][1],lambda d:d['data'][0].update(size=4))
        self.assertIn('TICK_VOLUME_DOES_NOT_MATCH_QUOTE_VOLUME',self.inspect(row,bundle)['reasons'])

    def test_trial_tick_is_not_an_actual_tick(self):
        row,bundle=example();mutate(bundle['pages'][0],lambda d:d['data'][1].update(isTrial=True))
        self.assertIn('INVALID_DUPLICATE_OR_TRIAL_TICK',self.inspect(row,bundle)['reasons'])

    def test_trial_request_scope_is_invalid(self):
        row,bundle=example();bundle['pages'][0]['query']['isTrial']=True
        self.assertIn('MISSING_PAGE_OR_WRONG_QUERY_SCOPE',self.inspect(row,bundle)['reasons'])

    def test_old_http_cache_rejected(self):
        row,bundle=example();bundle['pages'][0]['headers']['age']='60'
        self.assertIn('STALE_HTTP_CACHE',self.inspect(row,bundle)['reasons'])

    def test_slow_network_response_is_not_given_early_time(self):
        row,bundle=example();bundle['pages'][0]['requested_at']=DAY+'T13:34:00+08:00'
        self.assertIn('NETWORK_RESPONSE_EXCEEDS_BUDGET',self.inspect(row,bundle)['reasons'])

    def test_source_update_is_not_a_trade_time_substitute(self):
        row,bundle=example()
        for event in (bundle['quote_before'],bundle['quote_after']):mutate(event,lambda d:d.update(lastUpdated=micros('13:35:00')))
        r=self.inspect(row,bundle);self.assertEqual(r['pre_tick']['time'],micros('13:24:59.900000'))

    def test_changing_quote_during_pagination_blocks(self):
        row,bundle=example();mutate(bundle['quote_after'],lambda d:d['total'].update(transaction=5))
        self.assertIn('QUOTE_CHANGED_DURING_PAGINATION',self.inspect(row,bundle)['reasons'])

    def test_raw_evidence_hash_tamper_rejected(self):
        row,bundle=example();bundle['pages'][0]['raw']+=' '
        self.assertIn('RAW_EVIDENCE_HASH_MISMATCH',self.inspect(row,bundle)['reasons'])

    def test_old_date_rejected(self):
        row,bundle=example();mutate(bundle['pages'][0],lambda d:d.update(date='2026-10-13'))
        self.assertIn('DATE_SYMBOL_OR_MARKET_MISMATCH',self.inspect(row,bundle)['reasons'])

    def test_oddlot_scope_rejected(self):
        row,bundle=example();bundle['pages'][0]['query']['type']='oddlot'
        self.assertIn('MISSING_PAGE_OR_WRONG_QUERY_SCOPE',self.inspect(row,bundle)['reasons'])

    def test_normal_close_and_delayed_close(self):
        for delayed,kind in ((False,'NORMAL_CLOSE'),(True,'DELAYED_CLOSE')):
            row,bundle=example(delayed=delayed);self.assertEqual(self.inspect(row,bundle)['close_classification'],kind)

    def test_close_trial_or_no_close_flag_blocks(self):
        for change in ({'isTrial':True},{'isClose':False}):
            row,bundle=example()
            for event in (bundle['quote_before'],bundle['quote_after']):mutate(event,lambda d:d.update(change))
            self.assertIn('TRIAL_OR_CLOSE_NOT_FINISHED',self.inspect(row,bundle)['reasons'])

    def test_close_price_conflict_keeps_pre_result_separate(self):
        row,bundle=example();row['P_close']='105';r=self.inspect(row,bundle)
        self.assertTrue(r['synthetic_pre_passed']);self.assertFalse(r['synthetic_close_passed'])
        self.assertIn('MIS_INDEPENDENT_CLOSE_CONFLICT',r['reasons'])

    def test_default_real_contract_is_not_released_by_fixture_flags(self):
        row,bundle=example();bundle.update(origin_kind='AUTHENTICATED_HTTP',validated=True)
        r=t.inspect(bundle,row,DAY,AS_OF)
        self.assertFalse(r['validated']);self.assertIn('SOURCE_COUNT_AND_VOLUME_SEMANTICS_NOT_CONFIRMED',r['reasons'])

    def test_synthetic_cannot_enter_live_mode(self):
        row,bundle=example();r=t.inspect(bundle,row,DAY,AS_OF)
        self.assertIn('SYNTHETIC_EVIDENCE_IN_LIVE_MODE',r['reasons'])

    def test_decision_recomputes_instead_of_trusting_external_flag(self):
        row,bundle=example();row.update(validated=True,verification_status='VERIFIED')
        r=s.decide(row,bundle,DAY,AS_OF,mode='SYNTHETIC',contract=t.TEST_CONTRACT)
        self.assertTrue(r['simulation_passed']);self.assertFalse(r['validated']);self.assertEqual(r['verification_status'],'RESEARCH_ONLY')

    def test_mis_conflict_becomes_unknown(self):
        row,bundle=example();row['P_before']='98'
        r=s.decide(row,bundle,DAY,AS_OF,mode='SYNTHETIC',contract=t.TEST_CONTRACT)
        self.assertEqual(r['verification_status'],'UNKNOWN')

    def test_source_missing_pages_becomes_data_insufficient_not_verified(self):
        row,bundle=example();bundle['pages'].pop(0)
        r=s.decide(row,bundle,DAY,AS_OF,mode='SYNTHETIC',contract=t.TEST_CONTRACT)
        self.assertEqual(r['verification_status'],'UNKNOWN');self.assertFalse(r['validated'])

    def test_volume_and_threshold_are_required_per_security(self):
        for values in ({'volume_status':'UNVERIFIED'},{'closing_auction_volume':None},{'P_close':'102'}):
            row,bundle=example();row.update(values)
            r=s.decide(row,bundle,DAY,AS_OF,mode='SYNTHETIC',contract=t.TEST_CONTRACT)
            self.assertFalse(r['simulation_passed']);self.assertFalse(r['validated'])

    def test_microseconds_not_milliseconds(self):
        with self.assertRaisesRegex(ValueError,'MICROSECOND'):t.trade_time(1720000000000)

if __name__=='__main__':unittest.main()
