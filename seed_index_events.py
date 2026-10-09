"""One-time reviewed public date facts, not a substitute for a successful scan.

Run only for initial provisioning; never part of the scheduled workflow.
The exact source URLs and conservative first-seen timestamp are persisted.
"""
from index_events import *


def seed(root=ROOT):
    base = root / 'state/events'
    if (base / 'events-index.json').exists(): raise RuntimeError('Seed already exists')
    seen = now_iso()
    msci = 'https://www.msci.com/eqb/pressreleases/archive/ir_dates.pdf'
    tip = 'https://taiwanindex.com.tw/downloads/technical_notice?category_id=3&page=1'
    ftse = 'https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-twse-taiwan-index-series-ground-rules.pdf'
    dividend = 'https://www.twse.com.tw/downloads/en/products/indices/IndexSen20.pdf'
    sources = [
        {'source_id': 'msci-calendar', 'url': msci, 'parser': 'msci_schedule', 'enabled': True, 'coverage': 'PUBLIC_DATES_ONLY',
         'limitation': '僅公開審核期程；MSCI授權成分與權重資料不擷取、不重製。'},
        {'source_id': 'msci-constituents', 'url': 'https://www.msci.com/eqb/gimi/stdindex/index_review.html', 'enabled': False,
         'restricted': True, 'coverage': 'UNKNOWN', 'limitation': '成分、權重資料之使用及再散布涉及MSCI授權；本免費公開服務未取得授權。'},
        {'source_id': 'tip-schedule', 'url': tip, 'parser': 'tip_feed', 'enabled': True, 'coverage': 'LATEST_10_DOCUMENTS'},
        {'source_id': 'tip-notices', 'url': 'https://taiwanindex.com.tw/downloads/technical_notice?page=1', 'parser': 'tip_feed', 'enabled': True, 'coverage': 'LATEST_10_DOCUMENTS'},
        {'source_id': 'ftse-notices', 'url': 'https://research.ftserussell.com/Products/index-notices/loggedOut/index/?id=TWSE-TAIWAN',
         'enabled': False, 'restricted': True, 'coverage': 'UNKNOWN', 'limitation': '完整技術公告需要註冊／訂閱；改追蹤TIP公開摘要，無法保證臨時事件完整性。'},
        {'source_id': 'tip-etf-map-452', 'url': 'https://taiwanindex.com.tw/news/452', 'parser': 'map_html', 'enabled': True, 'coverage': 'OFFICIAL_PUBLIC_TABLE'},
        {'source_id': 'tip-etf-map-454', 'url': 'https://taiwanindex.com.tw/news/454', 'parser': 'map_html', 'enabled': True, 'coverage': 'OFFICIAL_PUBLIC_TABLE'},
        {'source_id': 'tip-new-etf-mappings', 'url': 'https://taiwanindex.com.tw/news', 'parser': 'map_feed', 'enabled': True, 'coverage': 'LATEST_PUBLIC_NEWS'},
        {'source_id': 'yuanta-announcements', 'url': 'https://www.yuantaetfs.com/', 'parser': 'monitor_html', 'enabled': True, 'coverage': 'MONITOR_ONLY'},
        {'source_id': 'cathay-announcements', 'url': 'https://www.cathaysite.com.tw/ETF/index-trend?keyword=00878', 'parser': 'monitor_html', 'enabled': True, 'coverage': 'MONITOR_ONLY'},
        {'source_id': 'capital-announcements', 'url': 'https://www.capitalfund.com.tw/etf/product/detail/195', 'parser': 'monitor_html', 'enabled': True, 'coverage': 'MONITOR_ONLY'},
        {'source_id': 'fuhhwa-announcements', 'url': 'https://www.fhtrust.com.tw/ETF/etf_detail/ETF21', 'parser': 'monitor_html', 'enabled': True, 'coverage': 'MONITOR_ONLY'},
        {'source_id': 'fubon-announcements', 'url': 'https://websys.fsit.com.tw/FubonETF/Fund/IndexIntro.aspx?stkId=006208', 'parser': 'monitor_html', 'enabled': True, 'coverage': 'MONITOR_ONLY'},
    ]
    maps = []
    def mapping(code, name, index, url):
        maps.append(dict(etf_code=code, etf_name=name, index_name=index, management_type='PASSIVE',
                         mapping_status='CONFIRMED', source_url=url, first_seen_at=seen, last_checked_at=seen,
                         change_history=[], implementation_status='UNKNOWN_UNTIL_SPECIFIC_NOTICE'))
    mapping('0050', '元大台灣50', 'FTSE TWSE Taiwan 50 Index', 'https://www.yuantaetfs.com/product/detail/0050/Basic_information')
    mapping('006208', '富邦台50', 'FTSE TWSE Taiwan 50 Index', 'https://websys.fsit.com.tw/FubonETF/Fund/IndexIntro.aspx?stkId=006208')
    mapping('0051', '元大中型100', 'FTSE TWSE Taiwan Mid-Cap 100 Index', 'https://www.yuantaetfs.com/product/domestic')
    mapping('0056', '元大高股息', 'FTSE TWSE Taiwan Dividend+ Index', 'https://www.yuantaetfs.com/product/detail/0056/Basic_information')
    mapping('00878', '國泰永續高股息', 'MSCI臺灣ESG永續高股息精選30指數', 'https://www.cathaysite.com.tw/ETF/index-trend?keyword=00878')
    for code, name, index in [
        ('00904', '台新臺灣半導體30', '臺灣指數公司臺灣全市場半導體精選30指數'),
        ('00919', '群益台灣精選高息', '臺灣指數公司特選臺灣上市上櫃精選高息指數'),
        ('00929', '復華台灣科技優息', '臺灣指數公司特選臺灣上市上櫃科技優息指數'),
        ('00934', '中信成長高股息', '臺灣指數公司特選臺灣上市上櫃優選成長高股息指數'),
        ('009802', '富邦旗艦50', '臺灣指數公司台灣上市上櫃旗艦動能50指數')]:
        mapping(code, name, index, 'https://taiwanindex.com.tw/news/452')
    for code, name, index in [
        ('00923', '群益台ESG低碳50', '臺灣指數公司特選臺灣ESG低碳50指數'),
        ('00930', '永豐ESG低碳高息', '臺灣指數公司特選臺灣上市上櫃ESG低碳高息40指數'),
        ('00936', '台新永續高息中小', '臺灣指數公司特選臺灣上市上櫃永續高息中小型股指數'),
        ('00939', '統一台灣高息動能', '臺灣指數公司特選臺灣上市上櫃高息動能指數')]:
        mapping(code, name, index, 'https://taiwanindex.com.tw/news/454')
    events = []
    for cycle, ad, ed in [('November 2026', '2026-11-11', '2026-12-01'),
                           ('February 2027', '2027-02-09', '2027-03-01'),
                           ('May 2027', '2027-05-10', '2027-05-28'),
                           ('August 2027', '2027-08-12', '2027-09-01')]:
        text = f'{cycle} Index Review\nAnnouncement date: {datetime.strptime(ad, "%Y-%m-%d").strftime("%B %d, %Y")}\nEffective date: {datetime.strptime(ed, "%Y-%m-%d").strftime("%B %d, %Y")}'
        events += parse_msci_schedule(text, msci, seen)
    schedules = [
        ('1311', '2026-10', '2026/10/19', '2026/10/20', [
            '特選臺灣上市上櫃 IC 設計報酬指數', '特選臺灣上市上櫃綠色能源報酬指數',
            '特選 Smart 多因子指數', '特選臺灣上市上櫃 FactSet 科技龍頭通訊指數',
            '特選臺灣上市上櫃智慧 50 指數', '特選臺灣上市上櫃 FactSet 創新科技 50 指數',
            '特選臺灣市值菁英 50 指數', '低波動股利精選 30 指數', '中小型 A 級動能 50 指數']),
        ('1311', '2026-10', '2026/11/03', '2026/11/04', ['工業菁英 30 指數', '特選臺灣上市上櫃 ESG 永續高股息等權重指數']),
        ('1325', '2026-11', '2026/11/17', '2026/11/18', [
            '特選臺灣上市上櫃 FactSet 智慧移動與電動車報酬指數', '特選臺灣 TOP 50 報酬指數',
            '臺灣上市上櫃生技醫療股價指數', '特選小資高價 30 指數', '特選臺灣上市上櫃綠能及電動車指數',
            '特選臺灣晶圓製造指數', '特選臺灣價值高息指數', '特選臺灣上市上櫃 IC 設計動能指數',
            '特選臺灣上市上櫃 FactSet 臺灣趨勢動能高股息指數', '特選臺灣上市上櫃 AI 優息動能指數',
            '特選臺灣上市上櫃動能趨勢指數']),
        ('1325', '2026-11', '2026/12/01', '2026/12/02', ['特選臺灣上市上櫃優選多因子 30 指數', '特選臺灣上市上櫃科技高息成長指數']),
        ('1325', '2026-11', '2026/12/03', '2026/12/04', ['特選臺灣上市上櫃 FactSet 優選 AI 50 指數'])]
    for doc, cycle, ad, ed, names in schedules:
        y, m = cycle.split('-')
        text = f'{y}年{int(m)}月指數定期審核日程表\n' + '\n'.join('臺灣指數公司' + n + ' ' + ad + ' ' + ed for n in names)
        events += parse_tip_schedule(text, f'https://backend.taiwanindex.com.tw/api/downloadFile/TechnicalNotices/{doc}/tw', seen)
    # Explicit published methodology, but no dated December announcement yet.
    for index, source in [('FTSE TWSE Taiwan 50 Index', ftse), ('FTSE TWSE Taiwan Mid-Cap 100 Index', ftse)]:
        item = new_event('FTSE', index, '2026-12', source, seen)
        item.update(event_status='EXPECTED', evidence_level='OFFICIAL_RULE_DERIVED',
                    closing_impact_date='2026-12-18', effective_date='2026-12-21',
                    close_date_status=EXPECTED, importance='PENDING',
                    date_evidence=['GROUND_RULE_6.1_THIRD_FRIDAY_PLUS_OFFICIAL_CALENDAR'],
                    scope_note='依官方規則推算，非2026年12月定審公告；ETF實際下單日未確認。')
        events.append(item)
    item = new_event('FTSE', 'FTSE TWSE Taiwan Dividend+ Index', '2026-12', dividend, seen)
    item.update(event_status='EXPECTED', evidence_level='OFFICIAL_RULE_DERIVED',
                effective_date='2026-12-21', close_date_status=EXPECTED,
                implementation_window={'start': '2026-12-21', 'trading_days': 5, 'status': 'EXPECTED_RULE_DERIVED'},
                date_evidence=['GROUND_RULE_4.6_FIVE_CONSECUTIVE_TRADING_DAYS'],
                scope_note='五個交易日過渡；12/25休市，預估延至12/28。不得將0056集中標為12/18單日換股。')
    events.append(item)
    calendars = {p.stem: load(p) for p in (root / 'state/calendars').glob('*.json')}
    events = attach_mapping([normalize_dates(x, calendars) for x in events], maps)
    write(base / 'sources.json', sources)
    write(base / 'events-index.json', {'schema_version': 1, 'timezone': 'Asia/Taipei', 'range': [START, END],
          'generated_at': seen, 'coverage_status': 'PARTIAL', 'events': events,
          'limitations': '初始官方日期核對；自動來源尚待掃描驗收。2027交易日曆未取得。'})
    write(base / 'etf-index-map.json', {'updated_at': seen, 'coverage_status': 'PARTIAL', 'mappings': maps})
    write(base / 'source-health.json', {'last_attempt_at': None, 'last_successful_scan_at': None, 'coverage_status': 'PARTIAL',
          'sources': [{'source_id': s['source_id'], 'status': 'MANUALLY_CHECKED' if s['enabled'] else 'RESTRICTED',
                       'last_checked_at': seen, 'last_success_at': None, 'error': s.get('limitation'), 'coverage': s['coverage']} for s in sources]})
    rebuild_sidecars(root, events, seen)


if __name__ == '__main__': seed()
