import json
import unittest
import freshness as f
from stage5_source_compare import compare


class CompareTests(unittest.TestCase):
    def test_time_tie_does_not_invent_unique_pre_price(self):
        when=lambda clock:int(f.parsed_time('2026-10-16T'+clock+'+08:00').timestamp()*1000000)
        ticks=[{'time':when('13:33:00'),'serial':3,'price':22},
               {'time':when('13:24:59'),'serial':2,'price':20},
               {'time':when('13:24:59'),'serial':1,'price':19}]
        bundle={'quote_after':{'raw':json.dumps({'closePrice':21,'lastTrade':{'time':when('13:30:00'),'serial':4,'price':21}})},
                'pages':[{'raw':json.dumps({'data':ticks})}]}
        ref={'code':'5546','ex':'tse','admitted_research_candidate':False,'P_before':'20','P_before_trade_time':'13:24:59','P_close':'22','P_close_trade_time':'13:33:00'}
        result=compare(bundle,ref)
        self.assertTrue(result['trades_head_matches_mis_price'])
        self.assertTrue(result['trades_head_after_quote_trade'])
        self.assertFalse(result['quote_close_matches_mis_price'])
        self.assertFalse(result['latest_pre_group_has_unique_price'])
        self.assertFalse(result['latest_pre_all_prices_match_mis'])
        self.assertFalse(result['verified'])
        self.assertTrue(all(isinstance(v,bool) for k,v in result.items() if k not in ('code','ex')))


if __name__=='__main__':unittest.main()
