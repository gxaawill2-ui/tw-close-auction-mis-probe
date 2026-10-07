import copy
import http.client
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import official_quotes as official

DATE = '2026-10-07'


def payload(ex='otc', date='20261007', data=None):
    fields = ['證券代號', '收盤價'] if ex == 'tse' else ['代號', '收盤']
    return json.dumps({'date': date, 'stat': 'ok', 'tables': [
        {'fields': fields, 'data': [['1234', '100']] if data is None else data}
    ]}).encode()


class OfficialRetryTests(unittest.TestCase):
    def validate_with(self, responses, snapshots=None):
        otc = Mock(side_effect=responses)
        twse = Mock(return_value=(200, payload('tse')))

        def get_bytes(url, timeout):
            return (otc if 'tpex.org.tw' in url else twse)(url, timeout)

        with tempfile.TemporaryDirectory() as d, patch.object(official.time, 'sleep') as sleep:
            result = official.validate(DATE, [], snapshots or [], Path(d), get_bytes)
            self.assertEqual(twse.call_count, 1)
            return result, otc, sleep.call_args_list

    def test_incomplete_read_then_success(self):
        result, otc, sleeps = self.validate_with([
            http.client.IncompleteRead(b'partial'), (200, payload())])
        self.assertEqual(result['sources'][1]['status'], 'AVAILABLE_SAME_DATE')
        self.assertEqual(otc.call_count, 2)
        self.assertEqual([c.args[0] for c in sleeps], [1])

    def test_exhausted_incomplete_reads_remain_pending(self):
        result, otc, sleeps = self.validate_with([http.client.IncompleteRead(b'partial')] * 5)
        self.assertEqual(result['status'], 'PENDING')
        self.assertEqual(result['sources'][1]['status'], 'PENDING_SOURCE_ERROR')
        self.assertEqual(otc.call_count, 5)
        self.assertEqual([c.args[0] for c in sleeps], [1, 2, 4, 8])

    def test_http_200_wrong_date_stays_pending(self):
        result, otc, _ = self.validate_with([(200, payload(date='20261006'))])
        self.assertEqual(result['status'], 'PENDING')
        self.assertEqual(result['sources'][1]['status'], 'PENDING_WRONG_OR_MISSING_DATE')
        self.assertEqual(otc.call_count, 1)

    def test_incomplete_json_retries_then_success_or_pending(self):
        for responses, expected in [([(200, b'{'), (200, payload())], 'AVAILABLE_SAME_DATE'),
                                    ([(200, b'{')] * 5, 'PENDING_SOURCE_ERROR')]:
            with self.subTest(expected=expected):
                result, _, _ = self.validate_with(responses)
                self.assertEqual(result['sources'][1]['status'], expected)

    def test_empty_table_stays_pending(self):
        result, _, _ = self.validate_with([(200, payload(data=[]))])
        self.assertEqual(result['sources'][1]['status'], 'PENDING_EMPTY_TABLE')

    def test_transport_failures_and_server_errors_retry(self):
        for failure in [http.client.RemoteDisconnected('closed'), ConnectionResetError('reset'),
                        TimeoutError('timeout'), urllib.error.URLError(TimeoutError('timeout')),
                        (503, b'unavailable'),
                        urllib.error.HTTPError('https://www.tpex.org.tw', 502, 'bad gateway', None, None)]:
            with self.subTest(failure=str(failure)):
                result, otc, _ = self.validate_with([failure, (200, payload())])
                self.assertEqual(result['sources'][1]['status'], 'AVAILABLE_SAME_DATE')
                self.assertEqual(otc.call_count, 2)

    def test_retry_preserves_saved_evidence(self):
        evidence = [{'records': [{'received_at': DATE+'T13:32:30+08:00',
            'response': {'msgArray': [{'ex': 'otc', 'c': '1234',
                                     'trade': {'z': '100', 't': '13:30:00'}}]}}]}]
        original = copy.deepcopy(evidence)
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d)/'close_reference_A_raw.jsonl'
            raw.write_bytes(json.dumps(evidence).encode())
            before = raw.read_bytes()
            self.validate_with([http.client.IncompleteRead(b'x'), (200, payload())], evidence)
            self.assertEqual(evidence, original)
            self.assertEqual(raw.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
