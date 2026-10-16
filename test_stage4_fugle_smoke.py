import io
import json
import unittest
import urllib.error
from stage4_fugle_smoke import probe, summarize, NoRedirect


class Reply(io.BytesIO):
    status = 200


class SmokeTests(unittest.TestCase):
    def fake(self, request, timeout):
        code = request.full_url.split('/')[-1].split('?')[0]
        kind = request.full_url.split('/')[-2]
        tick = {'price': 123456.78, 'size': 2, 'time': 1792100000000000, 'serial': 9999999}
        payload = {'date': '2026-10-16', 'symbol': code, 'lastTrade': tick, 'isTrial': False,
                   'isClose': False, 'data': [tick]}
        self.assertEqual(timeout, 12)
        self.assertTrue(request.full_url.startswith('https://api.fugle.tw/'))
        self.assertNotIn(self.key, request.full_url)
        return Reply(json.dumps(payload).encode())

    def setUp(self):
        self.key = 'private-test-key-not-for-logs'

    def test_five_requests_save_only_nonsecret_metadata_and_never_claim_verified(self):
        result = probe(self.key, self.fake, '2026-10-16')
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(len(result['requests']), 5)
        text = json.dumps(result)
        for forbidden in (self.key, '123456.78', '1792100000000000', '9999999'):
            self.assertNotIn(forbidden, text)
        self.assertEqual(result['verified_count'], 0)
        self.assertFalse(result['p_before_proven'])

    def test_auth_or_quota_error_stops_without_echoing_provider_error(self):
        for status in (401, 403, 429):
            def fail(request, timeout):
                raise urllib.error.HTTPError(request.full_url, status, self.key, {}, io.BytesIO(self.key.encode()))
            result = probe(self.key, fail, '2026-10-16')
            self.assertEqual(len(result['requests']), 1)
            self.assertEqual(result['status'], 'FAIL')
            self.assertNotIn(self.key, json.dumps(result))

    def test_stale_date_trial_only_or_empty_trades_do_not_pass(self):
        self.assertFalse(summarize({'date': '2026-10-15', 'symbol': '2330'}, '2330', 'quote', '2026-10-16')['schema_pass'])
        self.assertFalse(summarize({'date': '2026-10-16', 'symbol': '2330', 'lastPrice': 1}, '2330', 'quote', '2026-10-16')['schema_pass'])
        self.assertFalse(summarize({'date': '2026-10-16', 'symbol': '2330', 'data': []}, '2330', 'trades', '2026-10-16')['schema_pass'])

    def test_missing_key_never_requests_and_redirects_never_forward_it(self):
        for bad_key in (None, self.key + '\n', self.key + ' 提醒您', ' ' + self.key):
            with self.assertRaises(ValueError):
                probe(bad_key, lambda *args: self.fail('request made'))
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))


if __name__ == '__main__':
    unittest.main()
