"""Independent public event calendar. Never imports or changes MIS capture logic.

Dates are evidence, not a prediction. PDFs with unknown layouts stay in the
review queue. All joins use market+code and a repository-observed as-of time.
"""
import argparse
import copy
import csv
import hashlib
import io
import json
import re
import time
from datetime import date, datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
ROOT = Path(__file__).resolve().parent
START, END = '2026-10-09', '2027-10-31'
DATE_KEYS = ('announcement_date', 'review_date', 'effective_date', 'closing_impact_date')
CONFIRMED = 'CONFIRMED_CLOSE_IMPLEMENTATION'
EXPECTED = 'EXPECTED_CLOSE_WATCH_DATE'
UNVERIFIED = 'DATE_UNVERIFIED'
MULTIDAY = 'EXPECTED_MULTIDAY_TRANSITION'

# Reviewed bilingual identities, not fuzzy matching. Each pair is printed on
# the issuer's public product page; leverage variants are never aliased here.
INDEX_ALIASES = {
    '臺灣50指數': 'FTSE TWSE Taiwan 50 Index',
    '臺灣中型100指數': 'FTSE TWSE Taiwan Mid-Cap 100 Index',
    '臺灣高股息指數': 'FTSE TWSE Taiwan Dividend+ Index',
}


def index_identity(name):
    normalized = compact(name or '').replace('®','').replace('™','')
    return compact(INDEX_ALIASES.get(normalized, normalized))


def official_date(value):
    value = str(value or '').strip()
    if not value or value in ('不適用', 'NA', '-'): return None
    digits = re.sub(r'[/.-]', '', value)
    if len(digits) == 7 and digits.isdigit():
        return date(int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:])).isoformat()
    if len(digits) == 8 and digits.isdigit():
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])).isoformat()
    raise ValueError('Official date layout unrecognized: ' + value[:40])


def parse_etf_master(raw, source, seen):
    data = json.loads(raw)
    if not isinstance(data, list) or not data: raise ValueError('ETF master empty/unavailable')
    rows, codes = [], set()
    today = datetime.fromisoformat(seen).date().isoformat()
    required = {'基金代號', '基金簡稱', '基金類型', '標的指數/追蹤指數名稱', '是否包含國外成分股', '出表日期', '上市日期'}
    for raw_row in data:
        if not required <= raw_row.keys(): raise ValueError('ETF master schema changed')
        code = str(raw_row['基金代號']).strip()
        if not re.fullmatch(r'00\d{2,4}[A-Z]?', code) or code in codes:
            raise ValueError('Invalid/duplicate ETF identity')
        codes.add(code)
        published = official_date(raw_row['出表日期'])
        if not published or published > today: raise ValueError('ETF master source date missing/future')
        kind, foreign = raw_row['基金類型'].strip(), raw_row['是否包含國外成分股'].strip()
        management = 'ACTIVE' if '主動式交易所交易基金' in kind else 'PASSIVE' if '指數股票型' in kind else 'UNKNOWN'
        domestic = 'YES' if kind.startswith('國內成分證券') and foreign == '否' else 'NO' if foreign == '是' or kind.startswith(('國外', '境外', '連結式')) else 'UNKNOWN'
        leverage = 'LEVERAGED' if code.endswith('L') and '槓桿' in kind else 'INVERSE' if code.endswith('R') and '反向' in kind else 'STANDARD' if '槓桿/反向' not in kind and '期貨' not in kind else 'UNKNOWN'
        tracked = unescape(raw_row['標的指數/追蹤指數名稱'].strip())
        if tracked in ('', '不適用', '無', '-', 'NA'): tracked = None
        if management == 'ACTIVE': tracked = None  # A benchmark is not a tracked index.
        ended = official_date(raw_row.get('下市日期'))
        rows.append({'etf_code': code, 'etf_name': raw_row['基金簡稱'], 'fund_name': raw_row.get('基金中文名稱'),
            'fund_type': kind, 'management_type': management, 'tracks_taiwan_equities': domestic,
            'return_type': leverage, 'index_name': tracked, 'issuer_name': raw_row.get('經理公司名稱') or None,
            'issuer_status': 'OFFICIAL' if raw_row.get('經理公司名稱') else 'UNKNOWN',
            'market': 'TWSE', 'listing_date': official_date(raw_row['上市日期']), 'delisting_date': ended,
            'lifecycle_status': 'DELISTED' if ended and ended <= today else 'IN_OFFICIAL_MASTER',
            'current_listing_status': 'UNKNOWN', 'source_date': published, 'source_url': source,
            'first_seen_at': seen, 'information_available_as_of': seen, 'last_checked_at': seen,
            'calendar_eligible': management == 'PASSIVE' and domestic == 'YES' and leverage == 'STANDARD' and not ended,
            'mapping_status': 'NOT_APPLICABLE' if management == 'ACTIVE' else 'CONFIRMED' if tracked else 'UNKNOWN'})
    return rows


def update_etf_master(previous, fresh, seen):
    prior = {r['etf_code']: copy.deepcopy(r) for r in previous}
    if prior and len(fresh) < len(prior) * .8: raise ValueError('ETF master abnormal shrink; retain previous snapshot')
    incoming = {r['etf_code']: copy.deepcopy(r) for r in fresh}
    changes = 0
    for code, row in incoming.items():
        old = prior.get(code)
        if not old: continue
        row['first_seen_at'] = old['first_seen_at']
        volatile = {'first_seen_at', 'last_checked_at', 'information_available_as_of', 'change_history'}
        changed = {k: {'old': old.get(k), 'new': v} for k, v in row.items() if k not in volatile and old.get(k) != v}
        row['change_history'] = old.get('change_history', []) + ([{'observed_at': seen, 'changes': changed,
            'previous_version': {k: v for k, v in old.items() if k != 'change_history'}}] if changed else [])
        row['information_available_as_of'] = seen if changed else old.get('information_available_as_of', old['first_seen_at'])
        changes += bool(changed)
    for code, row in prior.items():
        if code not in incoming:
            # Absence is not evidence of delisting; never infer a delisting date.
            row['lifecycle_status'] = 'NOT_IN_LATEST_MASTER'
            row['calendar_eligible'] = False
            incoming[code] = row
    return sorted(incoming.values(), key=lambda x: x['etf_code']), {'newly_observed_etfs': len(set(incoming) - set(prior)), 'corrected_etfs': changes}


def merge_mappings(existing, incoming, seen):
    by_code = {r['etf_code']: copy.deepcopy(r) for r in existing}
    for row in incoming:
        old = by_code.get(row['etf_code'])
        row = copy.deepcopy(row)
        if old:
            evidence = old.get('evidence_sources', [{'source_url': old['source_url'], 'index_name': old.get('index_name'), 'first_seen_at': old['first_seen_at']}])
            current = {'source_url': row['source_url'], 'index_name': row.get('index_name'), 'first_seen_at': seen}
            previous_source = next((e for e in evidence if e['source_url']==current['source_url']), None)
            if previous_source: current['first_seen_at'] = previous_source['first_seen_at']
            evidence = [e for e in evidence if e['source_url'] != current['source_url']] + [current]
            row['first_seen_at'] = old['first_seen_at']
            row['evidence_sources'] = evidence
            row['change_history'] = old.get('change_history', [])
            if old.get('index_name') and row.get('index_name') and index_identity(old['index_name']) != index_identity(row['index_name']):
                if old['source_url'] != row['source_url']:
                    row['mapping_status'] = 'CONFLICT'
                    row['conflicting_index_names'] = sorted({old['index_name'], row['index_name']})
                row['change_history'] += [{'observed_at': seen, 'previous_version': {k:v for k,v in old.items() if k != 'change_history'}}]
            names = {e['index_name'] for e in evidence if e.get('index_name')}
            if len({index_identity(n) for n in names})>1:
                row['mapping_status'] = 'CONFLICT'
                row['conflicting_index_names'] = sorted(names)
        by_code[row['etf_code']] = row
    return sorted(by_code.values(), key=lambda x:x['etf_code'])


def parse_yuanta_profile(raw, source, seen, mapping):
    # Parse rendered labels only, never execute Nuxt/JavaScript or use quote data.
    text = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', raw.decode('utf-8'), flags=re.I|re.S)
    plain = ' '.join(''.join(HTML(text).parts).split())
    expected_code = mapping['etf_code']
    if not re.search(r'\(' + re.escape(expected_code) + r'\)', plain): raise ValueError('Issuer product identity mismatch')
    name = re.search(r'指數名稱\s+(.{1,160}?)\s+指數名稱\(英\)', plain)
    effective = re.search(r'成分股審核/調整生效日期\s+(20\d{2}/\d{2}/\d{2})', plain)
    if not name or not effective: raise ValueError('Issuer review-date layout unrecognized')
    if index_identity(name[1]) != index_identity(mapping['index_name']): raise ValueError('Issuer tracked index mismatch')
    ed = iso(effective[1])
    item = new_event('YUANTA', mapping['index_name'], ed[:7], source, seen)
    item.update(effective_date=ed, event_type='ISSUER_INDEX_REVIEW', evidence_level='OFFICIAL_ISSUER_DATE_ONLY',
        event_status='DATE_ONLY', constituent_details_status='COUNTS_ONLY', related_etf_codes=[expected_code],
        date_evidence=['EXPLICIT_ISSUER_EFFECTIVE_DATE_LABEL'], announcement_time=None,
        scope_note='發行商揭露指數調整生效日與檔數，未提供本基金實際下單日期；官方指數公告仍為準。')
    counts = re.search(r'此次新增成分股檔數\s+(\d+).*?此次刪除成分股檔數\s+(\d+)', plain)
    if counts: item['constituent_counts'] = {'additions': int(counts[1]), 'deletions': int(counts[2])}
    return [item]


def parse_tip_public_news(raw, source, seen):
    visible = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', raw.decode('utf-8'), flags=re.I|re.S)
    doc = HTML(visible)
    text = ' '.join(''.join(doc.parts).split())
    clean = compact(text)
    m = re.search(r'將自(20\d{2})年(\d{1,2})月(\d{1,2})日.{0,16}?交易結束後生效.*?亦即自(20\d{2})年(\d{1,2})月(\d{1,2})日', clean)
    if not m: return []
    closing = date(*map(int,m.groups()[:3])).isoformat()
    effective = date(*map(int,m.groups()[3:])).isoformat()
    announced = re.search(r'(20\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})',text)
    rows = parse_etf_map_html(visible, source, seen)
    if not rows: raise ValueError('TIP public review announcement index/ETF table unrecognized')
    items = {}
    for row in rows:
        if row['management_type']!='PASSIVE': continue
        name=row['index_name'];key=index_identity(name)
        if key not in items:
            item=new_event('TIP',name,effective[:7],source,seen)
            item.update(effective_date=effective,closing_impact_date=closing,close_date_status=CONFIRMED,
                evidence_level='OFFICIAL_IMPLEMENTATION',event_status='ANNOUNCED',importance='GENERAL',
                implementation_scope='INDEX_AFTER_CLOSE; ETF_TRADE_TIME_UNKNOWN',
                date_evidence=['EXPLICIT_PUBLIC_INDEX_AFTER_CLOSE_IMPLEMENTATION'],
                scope_note='確認指數收盤後實施，未證實ETF實際下單時點；無公開個股名單不得標記股票。')
            if announced:
                item.update(announcement_date=iso(announced[1]),announcement_time=announced[2],
                    official_announced_at=iso(announced[1])+'T'+announced[2]+':00+08:00')
            items[key]=item
        items[key]['related_etf_codes'].append(row['etf_code'])
    return list(items.values())


def now_iso():
    return datetime.now(TZ).isoformat(timespec='seconds')


def load(path, default=None):
    return json.loads(path.read_text()) if path.exists() else copy.deepcopy(default)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text() == text:
        return
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(text)
    temp.replace(path)


def compact(text):
    return re.sub(r'\s+', '', unescape(text)).replace('台灣', '臺灣')


def iso(value):
    return date.fromisoformat(value.replace('/', '-')).isoformat()


class HTML(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.rows, self.parts = [], [], []
        self.row = self.cell = self.anchor = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a': self.anchor = [attrs.get('href', ''), []]
        if tag == 'tr': self.row = []
        if tag in ('td', 'th'): self.cell = []
        if tag in ('p', 'div', 'br', 'tr'): self.parts.append('\n')

    def handle_data(self, text):
        self.parts.append(text)
        if self.anchor is not None: self.anchor[1].append(text)
        if self.cell is not None: self.cell.append(text)

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor is not None:
            self.links.append((self.anchor[0], ''.join(self.anchor[1]).strip()))
            self.anchor = None
        if tag in ('td', 'th') and self.cell is not None:
            if self.row is not None: self.row.append(''.join(self.cell).strip())
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def trading_day(day, calendars):
    d = date.fromisoformat(day)
    cal = calendars.get(str(d.year))
    if not cal or cal.get('status') != 'OFFICIAL_ANNUAL_CALENDAR': return None
    if cal.get('year') != d.year or not isinstance(cal.get('closed_dates'), list): return None
    return d.weekday() < 5 and day not in cal['closed_dates']


def offset_trading(day, step, calendars):
    d = date.fromisoformat(day)
    for _ in range(20):
        d += timedelta(days=step)
        state = trading_day(d.isoformat(), calendars)
        if state is None: return None
        if state: return d.isoformat()
    return None


def new_event(org, index, cycle, source, seen):
    key = compact(org + ':' + index + ':' + cycle)
    return dict(event_id=hashlib.sha256(key.encode()).hexdigest()[:20],
                event_name=index + ' · ' + cycle, review_cycle=cycle, event_type='INDEX_REVIEW',
                source_organization=org, index_name=index, related_etf_codes=[],
                announcement_date=None, announcement_time=None, review_date=None,
                effective_date=None, closing_impact_date=None, implementation_window=None,
                affected_stocks=[], constituent_details_status='NOT_PUBLISHED',
                event_status='SCHEDULE_ONLY', evidence_level='OFFICIAL_SCHEDULE',
                close_date_status=UNVERIFIED, importance='PENDING',
                source_url=source, source_document=source, first_seen_at=seen,
                information_available_as_of=seen, last_checked_at=seen, updated_at=seen,
                change_history=[], date_evidence=[], original_dates={})


def parse_tip_schedule(text, source, seen):
    """Only table rows with an explicit index name and two YYYY/MM/DD dates."""
    result = []
    cycle = re.search(r'(20\d{2})年(\d{1,2})月指數定期審核日程表', compact(text))
    pattern = r'(臺灣指數公司(?:(?!臺灣指數公司).){1,140}?指數)\s+(20\d{2}/\d{2}/\d{2})\s+(20\d{2}/\d{2}/\d{2})'
    for m in re.finditer(pattern, text, re.S):
        name, announcement, effective = m.groups()
        month = '%s-%02d' % (cycle[1], int(cycle[2])) if cycle else iso(effective)[:7]
        item = new_event('TIP', re.sub(r'\s+', ' ', name).strip(), month, source, seen)
        item.update(announcement_date=iso(announcement), announcement_time='AFTER_CLOSE',
                    effective_date=iso(effective), date_evidence=['OFFICIAL_TABLE_ANNOUNCEMENT_AND_EFFECTIVE'])
        result.append(item)
    if not result: raise ValueError('TIP schedule layout not recognized')
    return result


def parse_msci_schedule(text, source, seen):
    pattern = r'((?:November|February|May|August)\s+20\d{2})\s+Index Review.*?Announcement date:\s*([A-Za-z]+\s+\d{1,2},\s*20\d{2}).*?Effective date:\s*([A-Za-z]+\s+\d{1,2},\s*20\d{2})'
    rows = []
    for cycle, a, e in re.findall(pattern, text, re.S):
        ad = datetime.strptime(a, '%B %d, %Y').date().isoformat()
        ed = datetime.strptime(e, '%B %d, %Y').date().isoformat()
        item = new_event('MSCI', 'MSCI Global Standard / Small Cap（含臺灣）', cycle, source, seen)
        item.update(event_name='MSCI ' + cycle + ' 定審', announcement_date=ad,
                    effective_date=ed, importance='IMPORTANT',
                    announcement_timezone='SOURCE_DATE_TIME_UNPUBLISHED',
                    date_evidence=['OFFICIAL_TIMETABLE'], scope_note='日期為全球定審，00878等客製指數未確認適用；臺灣個股名單另行確認。')
        rows.append(item)
    if not rows: raise ValueError('MSCI timetable layout not recognized')
    return rows


def parse_tip_notice(text, source, seen, markets=None):
    title = re.search(r'「([^」]+指數)」', text)
    if not title: return []
    # Explicit implementation sentence only, never an arbitrary pair of dates.
    clean = compact(text)
    m = re.search(r'將自(20\d{2})年(\d{1,2})月(\d{1,2})日.{0,16}?交易結束後生效.*?亦即自(20\d{2})年(\d{1,2})月(\d{1,2})日', clean)
    if not m: return []
    y, mo, d, ey, em, ed = map(int, m.groups())
    closing, effective = date(y, mo, d).isoformat(), date(ey, em, ed).isoformat()
    item = new_event('TIP', title.group(1), effective[:7], source, seen)
    item.update(closing_impact_date=closing, effective_date=effective,
                close_date_status=CONFIRMED, event_status='ANNOUNCED',
                evidence_level='OFFICIAL_IMPLEMENTATION', importance='GENERAL',
                date_evidence=['EXPLICIT_AFTER_CLOSE_IMPLEMENTATION'])
    announced = re.search(r'(?:公告日期\s*[:：]?\s*|發布日期\s*[:：]?\s*|^\s*)(20\d{2})年(\d{1,2})月(\d{1,2})日(?:\s*$|\s*公告)', text, re.M)
    if announced: item['announcement_date'] = date(*map(int, announced.groups())).isoformat()
    changes = []
    sections = re.findall(r'成分股(納入|刪除)[（(](\d+)[）)]\s*[:：]?(.*?)(?=成分股(?:納入|刪除)|\*註|如欲|$)', text, re.S)
    for action, count, section in sections:
        found = re.findall(r'\b(\d{4})\s+([^\s、，,]+)', section)
        if len(found) != int(count):
            item['constituent_details_status'] = 'LAYOUT_UNVERIFIED'
            return [item]
        for code, name in found:
            metadata = (markets or {}).get(code)
            market = metadata if isinstance(metadata, str) else metadata.get('market') if metadata and compact(metadata.get('name', '')) == compact(name) else None
            changes.append({'code': code, 'name': name, 'market': market,
                            'market_status': 'OFFICIAL_CONFIRMED' if market else 'UNKNOWN',
                            'change_type': 'ADDITION' if action == '納入' else 'DELETION',
                            'weight_before': None, 'weight_after': None})
    if len(sections) == 2:
        item.update(affected_stocks=changes, constituent_details_status='OFFICIAL_LIST')
    return [item]


def normalize_dates(item, calendars):
    item = copy.deepcopy(item)
    for key in DATE_KEYS:
        if item.get(key): iso(item[key])
    if item.get('announcement_date') and item.get('effective_date') and item['announcement_date'] > item['effective_date']:
        raise ValueError('Announcement is after the effective date; date semantics unverified')
    if item.get('effective_date') and not item.get('closing_impact_date'):
        # A TIP after-close announcement can be learned after that day's close.
        # Do not infer same-day concentration when no implementation rule exists.
        if item['source_organization'] == 'MSCI':
            previous = offset_trading(item['effective_date'], -1, calendars)
            if previous:
                item.update(closing_impact_date=previous, close_date_status=EXPECTED)
                item['date_evidence'] = sorted(set(item['date_evidence'] + ['PREVIOUS_OFFICIAL_TRADING_DAY_INFERENCE']))
    closing = item.get('closing_impact_date')
    if closing and trading_day(closing, calendars) is not True:
        item['original_dates']['closing_impact_date'] = closing
        item.update(closing_impact_date=None, close_date_status=UNVERIFIED,
                    calendar_note='官方交易日曆不足或遇休市，待更正通知／官方順延規則確認')
    window = item.get('implementation_window')
    if window and item['close_date_status'] == EXPECTED:
        item['close_date_status'] = MULTIDAY
    if window and window.get('trading_days') and window.get('start'):
        days, current = [], window['start']
        for _ in range(window['trading_days']):
            if trading_day(current, calendars) is not True: break
            days.append(current)
            current = offset_trading(current, 1, calendars)
            if not current: break
        window['dates'] = days if len(days) == window['trading_days'] else []
        window['end'] = days[-1] if len(days) == window['trading_days'] else None
    return item


def attach_mapping(events, mappings):
    for item in events:
        item['related_etf_codes'] = sorted(set(item.get('related_etf_codes', [])) | {r['etf_code'] for r in mappings
            if r.get('mapping_status') == 'CONFIRMED' and r.get('management_type') == 'PASSIVE'
            and r.get('calendar_eligible', True) and r.get('return_type', 'STANDARD') == 'STANDARD'
            and index_identity(r.get('index_name', '')) == index_identity(item['index_name'])})
    return events


def event_evidence(item, seen):
    return {'source_url': item['source_url'], 'source_organization': item['source_organization'],
        'evidence_level': item['evidence_level'], 'observed_at': seen,
        **{k: item.get(k) for k in DATE_KEYS}, 'announcement_time': item.get('announcement_time'),
        'close_date_status': item['close_date_status'], 'implementation_window': item.get('implementation_window')}


def reconcile_evidence(prior, fresh, seen):
    prior_evidence = prior.get('source_evidence', [event_evidence(prior, prior['information_available_as_of'])])
    evidence = {e['source_url']: copy.deepcopy(e) for e in prior_evidence}
    current = event_evidence(fresh, seen)
    previous = evidence.get(current['source_url'])
    if previous and {k:v for k,v in previous.items() if k!='observed_at'} == {k:v for k,v in current.items() if k!='observed_at'}:
        current['observed_at'] = previous['observed_at']
    evidence[current['source_url']] = current
    # Keep implementation metadata, while retaining the newly observed schedule evidence.
    if prior['evidence_level'] == 'OFFICIAL_IMPLEMENTATION' and fresh['evidence_level'] == 'OFFICIAL_SCHEDULE':
        fresh = copy.deepcopy(prior)
    fresh['source_evidence'] = sorted(evidence.values(), key=lambda x:x['source_url'])
    fresh['related_etf_codes'] = sorted(set(prior.get('related_etf_codes', [])) | set(fresh.get('related_etf_codes', [])))
    if prior.get('constituent_details_status') == 'OFFICIAL_LIST' and fresh.get('constituent_details_status') != 'OFFICIAL_LIST':
        fresh['affected_stocks'] = copy.deepcopy(prior['affected_stocks'])
        fresh['constituent_details_status'] = 'OFFICIAL_LIST'
    conflict = {}
    for field in (*DATE_KEYS, 'implementation_window'):
        # Rules-derived guesses are not competing official announcements.
        values = [e[field] for e in evidence.values() if e.get(field) is not None and e['evidence_level'] != 'OFFICIAL_RULE_DERIVED']
        distinct = {json.dumps(v,sort_keys=True,ensure_ascii=False):v for v in values}
        if len(distinct)>1:
            conflict[field] = list(distinct.values()); fresh[field] = None
        elif values: fresh[field] = values[0]
        elif fresh.get(field) is None and prior.get(field) is not None and field not in prior.get('date_conflicts', {}):
            fresh[field] = prior[field]
    fresh['date_conflicts'] = conflict
    if conflict:
        fresh.update(event_status='CONFLICT', close_date_status=UNVERIFIED)
    elif fresh.get('closing_impact_date'):
        explicit = [e for e in evidence.values() if e.get('closing_impact_date') == fresh['closing_impact_date'] and e.get('close_date_status') == CONFIRMED]
        if explicit: fresh.update(close_date_status=CONFIRMED, evidence_level='OFFICIAL_IMPLEMENTATION', event_status='ANNOUNCED')
        else: fresh['close_date_status'] = EXPECTED
    return fresh


def merge_events(old, incoming, seen):
    merged = {x['event_id']: copy.deepcopy(x) for x in old}
    volatile = {'first_seen_at', 'last_checked_at', 'updated_at', 'change_history', 'information_available_as_of'}
    for fresh in incoming:
        prior = merged.get(fresh['event_id'])
        if not prior:
            prior = next((x for x in merged.values() if index_identity(x['index_name']) == index_identity(fresh['index_name'])
                and ((fresh.get('effective_date') and x.get('effective_date') == fresh['effective_date'])
                     or x.get('review_cycle') == fresh.get('review_cycle')
                     or x['source_organization'] == 'TIP' and x['source_url'] == fresh['source_url'])), None)
            if prior: fresh = {**fresh, 'event_id': prior['event_id']}
        if prior:
            fresh = reconcile_evidence(prior, copy.deepcopy(fresh), seen)
            changed = {k: {'old': prior.get(k), 'new': v} for k, v in fresh.items()
                       if k not in volatile and prior.get(k) != v}
            fresh = copy.deepcopy(fresh)
            fresh['first_seen_at'] = prior['first_seen_at']
            fresh['change_history'] = prior['change_history'] + ([{'observed_at': seen, 'changes': changed,
                'previous_version': {k: v for k, v in prior.items() if k != 'change_history'}}] if changed else [])
            fresh['updated_at'] = seen if changed else prior['updated_at']
            fresh['information_available_as_of'] = seen if changed else prior['information_available_as_of']
        else:
            fresh = copy.deepcopy(fresh)
            fresh['source_evidence'] = [event_evidence(fresh, seen)]
        merged[fresh['event_id']] = fresh
    return sorted(merged.values(), key=lambda x: (x.get('effective_date') or '9999', x['event_id']))


def as_of_version(item, as_of):
    cutoff = datetime.fromisoformat(as_of)
    if datetime.fromisoformat(item['first_seen_at']) > cutoff: return None
    versions = [h['previous_version'] for h in item.get('change_history', []) if h.get('previous_version')] + [item]
    eligible = [v for v in versions if datetime.fromisoformat(v['information_available_as_of']) <= cutoff]
    return max(eligible, key=lambda v: v['information_available_as_of']) if eligible else None


def annotate(candidate, events, as_of):
    """Returns an additive sidecar. Does not mutate the public candidate JSON."""
    day = candidate['trade_date']
    known = [v for x in events if (v := as_of_version(x, as_of))]
    on_day = [x for x in known if x.get('event_status') != 'CONFLICT' and (x.get('closing_impact_date') == day or
              day in (x.get('implementation_window') or {}).get('dates', []))]
    rows = []
    for stock in candidate['candidate_list']:
        links = []
        for event in on_day:
            for change in event.get('affected_stocks', []):
                if change.get('code') == stock['code'] and change.get('market') == stock['market'] and change.get('market_status') == 'OFFICIAL_CONFIRMED':
                    links.append({'event_id': event['event_id'], 'event_name': event['event_name'],
                                  'change_type': change['change_type'], 'source_url': event['source_url'],
                                  'related_etf_codes': event['related_etf_codes']})
        rows.append({'code': stock['code'], 'market': stock['market'], 'related_index_events': links,
                     'related_etf_events': [x for x in links if x['related_etf_codes']],
                     'constituent_change_type': sorted({x['change_type'] for x in links}),
                     'event_confidence': 'OFFICIAL_STOCK_MATCH' if links else 'UNCONFIRMED',
                     'event_source_url': sorted({x['source_url'] for x in links}),
                     'stock_event_relation': 'OFFICIAL_MATCH' if links else 'MARKET_DAY_ONLY' if on_day else 'UNKNOWN'})
    return {'trade_date': day, 'is_major_index_event_day': True if on_day else None,
            'event_types': sorted({x['event_type'] for x in on_day}), 'event_ids': [x['event_id'] for x in on_day],
            'event_information_available_as_of': as_of, 'candidate_annotations': rows,
            'note': '事件未取得不代表沒有事件；不推斷因果或交易方向。'}


class Fetcher:
    """At most 60 HTTP attempts/run, two attempts/URL, 10s timeout, 6MiB limit.

    Robots, access walls and explicit 401/403 are respected; no browser bypass.
    """
    def __init__(self, max_attempts=60):
        self.attempts, self.max_attempts = 0, max_attempts
        self.cache, self.robots = {}, {}

    def get(self, url):
        if url in self.cache: return self.cache[url]
        if urlparse(url).scheme != 'https': raise ValueError('HTTPS required')
        from urllib.robotparser import RobotFileParser
        host = urlparse(url).netloc
        if host not in self.robots:
            robot_url = 'https://' + host + '/robots.txt'
            try:
                raw = self._request(robot_url)
                robot = RobotFileParser(); robot.parse(raw.decode('utf-8', 'replace').splitlines())
                self.robots[host] = robot
            except HTTPError as error:
                if error.code in (401, 403): raise RuntimeError('Robots/access restriction HTTP ' + str(error.code))
                if error.code != 404: raise
                self.robots[host] = None
        robot = self.robots[host]
        if robot and not robot.can_fetch('IndexEventCalendar', url): raise RuntimeError('ROBOTS_DISALLOWED')
        raw = self._request(url)
        self.cache[url] = raw
        return raw

    def _request(self, url):
        for attempt in range(2):
            if self.attempts >= self.max_attempts: raise RuntimeError('REQUEST_BUDGET_EXCEEDED')
            self.attempts += 1
            try:
                with urlopen(Request(url, headers={'User-Agent': 'IndexEventCalendar/1.0 (public research; twice daily)', 'Accept': '*/*'}), timeout=10) as response:
                    if any(s in response.url.lower() for s in ('/login', '/loggedout', '/signin')): raise RuntimeError('ACCESS_RESTRICTED')
                    raw = response.read(6 * 1024 * 1024 + 1)
                    if len(raw) > 6 * 1024 * 1024: raise ValueError('SOURCE_TOO_LARGE')
                    return raw
            except HTTPError as error:
                if error.code in (401, 403, 404) or attempt == 1: raise
            except (TimeoutError, OSError):
                if attempt == 1: raise
            time.sleep(1)


def pdf_text(raw):
    if not raw.startswith(b'%PDF'): raise ValueError('Expected a PDF, received a login/error page')
    from pypdf import PdfReader
    return '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(raw)).pages)


def parse_etf_map_html(text, source, seen):
    mappings = []
    for row in HTML(text).rows:
        if len(row) < 3 or '指數' not in row[0]: continue
        code = row[2].strip()
        if not re.fullmatch(r'00\d{3,4}[A-Z]?', code): continue
        management = 'ACTIVE' if '主動' in row[1] or code.endswith('A') else 'PASSIVE'
        mappings.append({'etf_code': code, 'etf_name': row[1], 'index_name': row[0],
                         'management_type': management, 'mapping_status': 'CONFIRMED' if management == 'PASSIVE' else 'NOT_APPLICABLE',
                         'source_url': source, 'first_seen_at': seen, 'last_checked_at': seen})
    return mappings


def parse_calendar(raw, year, url, seen):
    data = json.loads(raw)
    if data.get('stat') != 'ok' or not data.get('data') or str(year - 1911) not in data.get('title', ''):
        raise ValueError('Official annual calendar not published for requested year')
    closed = []
    for row in data['data']:
        if '最後交易' in ''.join(str(x) for x in row[1:]) or '開始交易' in ''.join(str(x) for x in row[1:]): continue
        text = row[0]
        match = re.search(r'(\d{1,2})月(\d{1,2})日', text)
        if match: closed.append(date(year, *map(int, match.groups())).isoformat())
        else:
            for found in re.findall(r'20\d{2}-\d{2}-\d{2}', text):
                if int(found[:4]) == year: closed.append(found)
    if not closed: raise ValueError('Calendar date layout unrecognized')
    return {'year': year, 'status': 'OFFICIAL_ANNUAL_CALENDAR', 'source': url,
            'verified_at': seen, 'closed_dates': sorted(set(closed))}


def run(root=ROOT, fetcher=None):
    seen = now_iso(); base = root / 'state/events'
    sources = load(base / 'sources.json', [])
    old = load(base / 'events-index.json', {'events': []})
    mappings = load(base / 'etf-index-map.json', {'mappings': []})['mappings']
    calendars = {p.stem: load(p) for p in (root / 'state/calendars').glob('*.json')}
    calendars.update({p.stem: load(p) for p in (base / 'calendars').glob('*.json')})
    health_old = load(base / 'source-health.json', {'sources': []})
    health_lookup = {s['source_id']: s for s in health_old['sources']}
    client = fetcher or Fetcher()
    incoming, health, queue = [], [], []
    registry = load(base / 'document-registry.json', {})
    markets = load(base / 'market-metadata.json', {})
    master_old = load(base / 'etf-master.json', {'etfs': []})
    master_rows, discovery = master_old['etfs'], {'newly_observed_etfs': 0, 'corrected_etfs': 0}
    mapping_count_before = sum(m.get('mapping_status') == 'CONFIRMED' for m in mappings)
    for spec in sources:
        sid = spec['source_id']; prior = health_lookup.get(sid, {})
        entry = {'source_id': sid, 'last_checked_at': seen, 'last_success_at': prior.get('last_success_at'),
                 'last_failure_at': prior.get('last_failure_at'), 'status': 'UNKNOWN', 'error': None,
                 'coverage': spec.get('coverage', 'PARTIAL'), 'source_url': spec['url'],
                 'capability': spec.get('capability', 'MONITOR_ONLY' if spec.get('parser', '').startswith('monitor') else 'DATE_ONLY' if spec.get('parser') == 'msci_schedule' else 'VERIFIED_AUTOMATIC')}
        if not spec.get('enabled'):
            entry.update(status='RESTRICTED' if spec.get('restricted') else 'NOT_IMPLEMENTED', error=spec['limitation'])
            health.append(entry); continue
        try:
            url = spec['url']; raw = client.get(url)
            kind = spec['parser']; found = []
            if kind == 'msci_schedule': found = parse_msci_schedule(pdf_text(raw), url, seen)
            elif kind == 'etf_master':
                fresh_master = parse_etf_master(raw, url, seen)
                master_rows, discovery = update_etf_master(master_rows, fresh_master, seen)
                eligible = [x for x in master_rows if x['calendar_eligible']]
                mappings = merge_mappings(mappings, eligible, seen)
                entry.update(parsed_etf_count=len(fresh_master), eligible_etf_count=len(eligible), source_date=max(x['source_date'] for x in fresh_master))
            elif kind == 'yuanta_profile':
                mapping = next((r for r in mappings if r['etf_code'] == spec['etf_code'] and r.get('mapping_status') == 'CONFIRMED'), None)
                if not mapping: raise ValueError('Issuer profile tracked index unavailable/conflicting')
                found = parse_yuanta_profile(raw, url, seen, mapping)
            elif kind == 'market_metadata':
                data = json.loads(raw)
                if not isinstance(data, list) or not data: raise ValueError('Official market metadata unavailable')
                for row in data:
                    code = str(row.get('公司代號', row.get('SecuritiesCompanyCode', '')))
                    name = row.get('公司簡稱', row.get('公司名稱', ''))
                    if re.fullmatch(r'\d{4}', code) and name:
                        markets[code] = {'market': spec['market'], 'name': name, 'source_url': url, 'last_checked_at': seen}
                write(base / 'market-metadata.json', markets)
            elif kind == 'calendar':
                calendar = parse_calendar(raw, spec['year'], url, seen)
                write(base / 'calendars' / (str(spec['year']) + '.json'), calendar)
                calendars[str(spec['year'])] = calendar
            elif kind == 'tip_feed':
                doc = HTML(raw.decode('utf-8')); links = sorted({urljoin(url, href) for href, _ in doc.links
                    if '/downloadFile/TechnicalNotices/' in href})
                if not links: raise ValueError('No official notice links; source layout unrecognized')
                # Cache *hash*, not just URL: corrections can replace the same PDF.
                for link in links[:12]:
                    body = client.get(link); digest = hashlib.sha256(body).hexdigest()
                    text = pdf_text(body)
                    if '指數定期審核日程表' in compact(text): parsed = parse_tip_schedule(text, link, seen)
                    else: parsed = parse_tip_notice(text, link, seen, markets)
                    found.extend(parsed)
                    if not parsed: queue.append({'url': link, 'sha256': digest, 'status': 'UNPARSED_NOTICE', 'seen_at': seen})
                    registry[link] = {'sha256': digest, 'last_checked_at': seen, 'parsed_event_count': len(parsed)}
            elif kind in ('map_html', 'map_feed'):
                if kind == 'map_html':
                    result = parse_etf_map_html(raw.decode('utf-8'), url, seen)
                    found = parse_tip_public_news(raw, url, seen)
                else:
                    doc = HTML(raw.decode('utf-8'))
                    links = sorted({urljoin(url, href) for href, _ in doc.links if re.search(r'/news/\d+$', href)}, reverse=True)[:5]
                    result = []
                    for link in links: result.extend(parse_etf_map_html(client.get(link).decode('utf-8'), link, seen))
                if not result: raise ValueError('Mapping table unavailable; not an empty ETF universe')
                mappings = merge_mappings(mappings, result, seen)
            elif kind in ('monitor_html', 'monitor_pdf'):
                text = pdf_text(raw) if kind == 'monitor_pdf' else raw.decode('utf-8')
                if any(s in text.lower() for s in ('please register', 'loggedout', '帳號登入')): raise ValueError('ACCESS_RESTRICTED')
                digest = hashlib.sha256(raw).hexdigest()
                prior_doc = registry.get(url, {})
                if prior_doc.get('sha256') != digest:
                    queue.append({'url': url, 'sha256': digest, 'status': 'ISSUER_NOTICE_REQUIRES_DATE_REVIEW', 'seen_at': seen})
                registry[url] = {'sha256': digest, 'last_checked_at': seen}
                entry['status'] = 'MONITOR_ONLY'
            else: raise ValueError('Unsupported parser ' + kind)
            incoming.extend(normalize_dates(x, calendars) for x in found)
            if entry['status'] == 'UNKNOWN': entry['status'] = 'SUCCESS'
            entry.update(last_success_at=seen, parsed_event_count=len(found))
            entry['scan_outcome'] = 'FETCHED_AND_PARSED'
        except Exception as error:
            restriction = 'ROBOTS_DISALLOWED' in str(error) or 'ACCESS_RESTRICTED' in str(error) or isinstance(error, HTTPError) and error.code in (401,403)
            entry.update(status='RESTRICTED' if restriction else 'STALE' if entry['last_success_at'] else 'UNKNOWN',
                error=str(error)[:300], last_failure_at=seen, scan_outcome='FETCH_FAILED_NOT_NO_ANNOUNCEMENTS')
        health.append(entry)
    # Mapping refresh can amend relationships but never supplies constituent lists.
    # A scan can start before the close and finish afterwards. Observations are
    # available only after retrieval/processing, never at the scan start time.
    finished = now_iso()
    for item in incoming:
        for key in ('first_seen_at', 'information_available_as_of', 'last_checked_at', 'updated_at'):
            item[key] = finished
    for entry in health:
        entry['last_checked_at'] = finished
        if entry['status'] in ('SUCCESS', 'MONITOR_ONLY'): entry['last_success_at'] = finished
        if entry.get('last_failure_at') == seen: entry['last_failure_at'] = finished
        entry['classification'] = entry['capability'] if entry['status'] == 'SUCCESS' else 'MONITOR_ONLY' if entry['status'] == 'MONITOR_ONLY' else 'RESTRICTED' if entry['status'] == 'RESTRICTED' else 'UNAVAILABLE'
    for mapping in mappings:
        if mapping.get('first_seen_at') == seen: mapping['first_seen_at'] = finished
        if mapping.get('last_checked_at') == seen: mapping['last_checked_at'] = finished
        if mapping.get('information_available_as_of') == seen: mapping['information_available_as_of'] = finished
        for change in mapping.get('change_history', []):
            if change.get('observed_at') == seen: change['observed_at'] = finished
        for evidence in mapping.get('evidence_sources', []):
            if evidence.get('first_seen_at') == seen: evidence['first_seen_at'] = finished
    for row in master_rows:
        for key in ('first_seen_at','information_available_as_of','last_checked_at'):
            if row.get(key) == seen: row[key] = finished
        for change in row.get('change_history', []):
            if change.get('observed_at') == seen: change['observed_at'] = finished
    for record in queue:
        if record.get('seen_at') == seen: record['seen_at'] = finished
    incoming = attach_mapping(incoming, mappings)
    # Renormalize previously observed future dates only when calendars arrive.
    # Preserve as-of lineage and never fabricate a fresh source check.
    for prior in old['events']:
        normalized = normalize_dates(prior, calendars)
        if normalized != prior: incoming.insert(0, normalized)
    events = merge_events(old['events'], incoming, finished)
    write(base / 'events-index.json', {'schema_version': 1, 'timezone': 'Asia/Taipei', 'range': [START, END],
          'generated_at': finished, 'coverage_status': 'PARTIAL', 'events': events,
          'limitations': '未公布、受限或解析失敗的來源不等於沒有事件。2027交易日曆未取得時不推算收盤日。'})
    existing_queue = load(base / 'review-queue.json', [])
    keyed = {(q['url'], q['sha256']): q for q in existing_queue + queue}
    old_by_id = {x['event_id']:x for x in old['events']}
    new_count = sum(x['event_id'] not in old_by_id for x in events)
    corrected = sum(x['event_id'] in old_by_id and any(set(h.get('changes', {})) & set((*DATE_KEYS,'implementation_window','affected_stocks'))
        for h in x.get('change_history', [])[len(old_by_id[x['event_id']].get('change_history', [])):]) for x in events)
    for entry in health:
        if entry['status']=='SUCCESS':
            entry['scan_outcome'] = 'FETCHED_PARSED_EVENTS' if entry.get('parsed_event_count') else 'FETCHED_METADATA_ONLY'
            entry['new_event_count'] = sum(x['event_id'] not in old_by_id and any(e['source_url']==entry['source_url'] for e in x.get('source_evidence', [])) for x in events)
            entry['announcement_state'] = 'NEW_PARSED_EVENTS' if entry['new_event_count'] else 'NO_NEW_PARSED_EVENTS; NOT_FULL_ANNOUNCEMENT_COVERAGE'
        elif entry['status']=='MONITOR_ONLY': entry['announcement_state']='CONTENT_MONITORED; ANNOUNCEMENT_CONTENT_UNVERIFIED'
        else: entry['announcement_state']='UNKNOWN; NOT_NO_ANNOUNCEMENTS'
    counts = {c: sum(s['classification'] == c for s in health) for c in ('VERIFIED_AUTOMATIC','DATE_ONLY','MONITOR_ONLY','RESTRICTED','UNAVAILABLE')}
    metrics = {'source_total':len(health),'source_classes':counts,'new_events':new_count,'corrected_events':corrected,
        'conflicting_events':sum(x['event_status']=='CONFLICT' for x in events),'pending_review_documents':len(keyed),
        **discovery, 'confirmed_etf_mappings':sum(x.get('mapping_status')=='CONFIRMED' for x in mappings),
        'new_confirmed_etf_mappings':max(0,sum(x.get('mapping_status')=='CONFIRMED' for x in mappings)-mapping_count_before),
        'unconfirmed_etf_mappings':sum(x.get('mapping_status') in ('UNKNOWN','CONFLICT') for x in mappings),
        'etf_master_total':len(master_rows),'issuer_unknown_etfs':sum(x.get('issuer_status')=='UNKNOWN' for x in master_rows),
        'listing_status_unknown_etfs':sum(x.get('current_listing_status')=='UNKNOWN' for x in master_rows),
        'etf_discovery_coverage':'TWSE_OPEN_MASTER_ONLY; TPEx full master not verified'}
    write(base / 'source-health.json', {'last_attempt_at': seen,
          'last_successful_scan_at': finished if any(s['status'] == 'SUCCESS' for s in health) else health_old.get('last_successful_scan_at'),
          'last_failure_at': max((s['last_failure_at'] for s in health if s.get('last_failure_at')),default=None),
          'coverage_status': 'PARTIAL', 'request_attempts': getattr(client, 'attempts', None), 'sources': health,'metrics':metrics})
    write(base / 'document-registry.json', registry)
    write(base / 'review-queue.json', list(keyed.values()))
    write(base / 'etf-index-map.json', {'updated_at': finished, 'coverage_status': 'PARTIAL', 'mappings': mappings})
    write(base / 'etf-master.json', {'updated_at':finished,'coverage_status':'PARTIAL','etfs':master_rows,
        'note':'基金主檔不等於當日掛牌清單；缺漏不推定下市。主動、境外及槓反均不套普通被動換股假設。'})
    write(base / 'source-coverage.json', {'generated_at':finished,'coverage_status':'PARTIAL',**metrics})
    baseline = load(root / 'reports/index-events/source-coverage-before.json', {'sources':[]})
    comparison = {'generated_at':finished, 'coverage_status':'PARTIAL',
        'before':{'source_total':len(baseline['sources']), 'successful_fetch_parse_sources':sum(x['status']=='SUCCESS' for x in baseline['sources']),
                  'monitors':sum(x['status']=='MONITOR_ONLY' for x in baseline['sources']), 'etf_mappings':14},
        'after':{**metrics, 'successful_fetch_parse_sources':sum(x['status']=='SUCCESS' for x in health)},
        'sources':[{'source_id':x['source_id'],'source_url':x['source_url'],'classification':x['classification'],
                    'status':x['status'],'last_success_at':x['last_success_at'],'last_failure_at':x['last_failure_at'],
                    'error':x['error'],'announcement_state':x['announcement_state']} for x in health],
        'note':'SUCCESS包含DATE_ONLY，不等於能解析基金實際交易時間。來源數與全市場事件涵蓋率不同。'}
    write(root / 'reports/index-events/source-coverage-comparison.json', comparison)
    rebuild_sidecars(root, events, finished)
    return health


def rebuild_sidecars(root, events, seen):
    base = root / 'state/events'
    grouped = {}
    for event in events:
        for key in DATE_KEYS:
            day = event.get(key)
            if day: grouped.setdefault(day, []).append({'event_id': event['event_id'], 'date_type': key})
        for day in (event.get('implementation_window') or {}).get('dates', []):
            grouped.setdefault(day, []).append({'event_id': event['event_id'], 'date_type': 'implementation_window'})
    # Superseded day buckets are rewritten, never silently left showing old dates.
    for path in base.glob('20??-??-??.json'): grouped.setdefault(path.stem, [])
    for day, items in grouped.items():
        write(base / (day + '.json'), {'date': day, 'as_of': seen,
              'references': sorted({(r['event_id'], r['date_type']) for r in items})})
    for path in (root / 'state/candidates').glob('*.json'):
        candidate = load(path)
        # Repository observation is conservative; also preserve the live as-of.
        write(base / 'candidate-annotations' / path.name, {
            'live_as_of': annotate(candidate, events, candidate['generated_at']),
            'latest_as_of': annotate(candidate, events, seen), 'updated_at': seen})
    report = root / 'reports/index-events'; report.mkdir(parents=True, exist_ok=True)
    fields = ['event_id', 'event_name', 'source_organization', 'index_name', 'announcement_date',
              'effective_date', 'closing_impact_date', 'close_date_status', 'event_status', 'first_seen_at', 'source_url']
    with (report / 'event-calendar-2026-2027.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fields, extrasaction='ignore'); writer.writeheader()
        writer.writerows(x for x in events if any(START <= (x.get(k) or '') <= END for k in DATE_KEYS))
    maps = load(base / 'etf-index-map.json', {'mappings': []})['mappings']
    fields = ['etf_code', 'etf_name', 'index_name', 'management_type', 'mapping_status', 'source_url', 'first_seen_at']
    with (report / 'etf-index-mapping.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(maps)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(run(args.root), ensure_ascii=False, indent=2))
