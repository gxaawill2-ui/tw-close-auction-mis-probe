import unittest
from probe import TableParser, analyze, FetchResult


class ProbeTests(unittest.TestCase):
    def test_universe_parser_shape(self):
        parser = TableParser()
        parser.feed("<table><tr><td>2330　TSMC</td><td>TW0002330008</td><td>ESVUFR</td></tr></table>")
        self.assertEqual(parser.rows[0][0], "2330 TSMC")

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
