import unittest
from types import SimpleNamespace
from stage5_durable_controls import SmallBudget


class SmallBudgetTests(unittest.TestCase):
    def test_rolling_minute_cap_counts_errors_and_never_retries_more_than_six(self):
        clock=[0.0];calls=[]
        def opener(req,timeout):calls.append(clock[0]);raise OSError('synthetic failure')
        budget=SmallBudget(opener,clock=lambda:clock[0]);req=SimpleNamespace(full_url='https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/2330')
        for i in range(6):
            clock[0]=i
            with self.assertRaises(OSError):budget(req,6)
        for at in (6,59.999):
            clock[0]=at
            with self.assertRaisesRegex(ValueError,'BUDGET'):budget(req,6)
        self.assertEqual(len(calls),6)
        clock[0]=60
        with self.assertRaises(OSError):budget(req,6)
        self.assertEqual(len(calls),7)
        clock[0]=60.1
        with self.assertRaises(ValueError):budget(req,6)

    def test_total_cap_and_wrong_host_before_network(self):
        clock=[0.0];calls=[]
        budget=SmallBudget(lambda *a,**k:calls.append(clock[0]),clock=lambda:clock[0])
        with self.assertRaisesRegex(ValueError,'DESTINATION'):budget(SimpleNamespace(full_url='https://other.invalid/'),6)
        self.assertFalse(calls)
        req=SimpleNamespace(full_url='https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/6488')
        for _ in range(30):budget(req,6);clock[0]+=61
        with self.assertRaisesRegex(ValueError,'BUDGET'):budget(req,6)
        self.assertEqual(len(calls),30)


if __name__=='__main__':unittest.main()
