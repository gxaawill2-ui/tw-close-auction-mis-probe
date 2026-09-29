import unittest
from probe import FetchResult, analyze, parse_universe_rows


class ProbeTests(unittest.TestCase):
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
