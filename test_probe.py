import unittest
from unittest.mock import patch
import probe
from probe import FetchResult, analyze, parse_universe_rows


class ProbeTests(unittest.TestCase):
    def test_saved_blank_probe_response_is_missing_not_success(self):
        symbols = [{"ex": "tse", "code": "2330"}]
        # Both saved 2026-10-06 failures contained exactly 22 LF bytes.
        with patch.object(probe, 'get_bytes', return_value=(200, b'\n' * 22)) as get:
            result = probe.fetch_mis(symbols, retry=0)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result.error, 'MIS_EMPTY_BODY')
        self.assertEqual(result.raw_body, '\n' * 22)
        self.assertIsNone(result.response)
        self.assertEqual(result.attempts[0]['raw_body'], result.raw_body)
        self.assertEqual(analyze(symbols, result)['missing'], ['tse:2330'])

    def test_invalid_json_keeps_parse_error_and_missing_rtcode_is_distinct(self):
        for raw, error in ((b'<html>bad gateway</html>', 'JSON_PARSE_ERROR:'),
                           (b'{}', 'MIS_NO_RTCODE')):
            with self.subTest(raw=raw), patch.object(probe, 'get_bytes', return_value=(200, raw)):
                result = probe.fetch_mis([], retry=0)
            self.assertTrue(result.error.startswith(error), result.error)
            self.assertEqual(result.raw_body, raw.decode())

    def test_existing_retry_retains_empty_attempt_evidence(self):
        with patch.object(probe, 'get_bytes', side_effect=[(200, b'\n' * 22),
                      (200, b'{"rtcode":"0000","msgArray":[]}')]), patch.object(probe.time, 'sleep'):
            result = probe.fetch_mis([], retry=1)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.attempts[0]['error'], 'MIS_EMPTY_BODY')
        self.assertEqual(result.attempts[0]['raw_body'], '\n' * 22)

    def test_universe_parser_keeps_normal_stocks_only(self):
        rows = [
            {"code": "2330", "name": "台積電"},
            {"code": "9105", "name": "TDR"},
            {"code": "0050", "name": "ETF"},
            {"code": "12345", "name": "not-four-digits"},
        ]
        parsed = parse_universe_rows(rows, "TWSE", "tse", "code", "name")
        self.assertEqual(parsed, [{"code": "2330", "name": "台積電",
                                   "market": "TWSE", "ex": "tse"}])

    def test_missing_and_duplicate(self):
        symbols = [{"ex": "tse", "code": "2330"}, {"ex": "otc", "code": "1240"}]
        body = {"rtcode": "0000", "msgArray": [
            {"ex": "tse", "c": "2330", "n": "TSMC"},
            {"ex": "tse", "c": "2330", "n": "TSMC"},
        ]}
        result = FetchResult("a", "b", 1, 200, 0, None, "{}", body)
        checked = analyze(symbols, result)
        self.assertEqual(checked["missing"], ["otc:1240"])
        self.assertEqual(checked["duplicate"], ["tse:2330"])


if __name__ == "__main__":
    unittest.main()
