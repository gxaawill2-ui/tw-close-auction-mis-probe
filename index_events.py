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
    announced = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', clean)
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
        item['related_etf_codes'] = sorted({r['etf_code'] for r in mappings
            if r.get('mapping_status') == 'CONFIRMED' and r.get('management_type') == 'PASSIVE'
            and compact(r.get('index_name', '')) == compact(item['index_name'])})
    return events


def merge_events(old, incoming, seen):
    merged = {x['event_id']: copy.deepcopy(x) for x in old}
    volatile = {'first_seen_at', 'last_checked_at', 'updated_at', 'change_history', 'information_available_as_of'}
    for fresh in incoming:
        prior = merged.get(fresh['event_id'])
        if not prior:
            prior = next((x for x in merged.values() if x['source_organization'] == fresh['source_organization']
                and compact(x['index_name']) == compact(fresh['index_name'])
                and (x.get('effective_date') == fresh.get('effective_date')
                     or x['source_organization'] == 'TIP' and x['source_url'] == fresh['source_url'])), None)
            if prior: fresh = {**fresh, 'event_id': prior['event_id']}
        if prior:
            # A timetable must not downgrade a later explicit result notice.
            if prior['evidence_level'] == 'OFFICIAL_IMPLEMENTATION' and fresh['evidence_level'] == 'OFFICIAL_SCHEDULE':
                continue
            changed = {k: {'old': prior.get(k), 'new': v} for k, v in fresh.items()
                       if k not in volatile and prior.get(k) != v}
            fresh = copy.deepcopy(fresh)
            fresh['first_seen_at'] = prior['first_seen_at']
            fresh['change_history'] = prior['change_history'] + ([{'observed_at': seen, 'changes': changed,
                'previous_version': {k: v for k, v in prior.items() if k != 'change_history'}}] if changed else [])
            fresh['updated_at'] = seen if changed else prior['updated_at']
            fresh['information_available_as_of'] = seen if changed else prior['information_available_as_of']
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
    on_day = [x for x in known if x.get('closing_impact_date') == day or
              day in (x.get('implementation_window') or {}).get('dates', [])]
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
    from pypdf import PdfReader
    if not raw.startswith(b'%PDF'): raise ValueError('Expected a PDF, received a login/error page')
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
    for spec in sources:
        sid = spec['source_id']; prior = health_lookup.get(sid, {})
        entry = {'source_id': sid, 'last_checked_at': seen, 'last_success_at': prior.get('last_success_at'),
                 'status': 'UNKNOWN', 'error': None, 'coverage': spec.get('coverage', 'PARTIAL')}
        if not spec.get('enabled'):
            entry.update(status='RESTRICTED' if spec.get('restricted') else 'NOT_IMPLEMENTED', error=spec['limitation'])
            health.append(entry); continue
        try:
            url = spec['url']; raw = client.get(url)
            kind = spec['parser']; found = []
            if kind == 'msci_schedule': found = parse_msci_schedule(pdf_text(raw), url, seen)
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
                if kind == 'map_html': result = parse_etf_map_html(raw.decode('utf-8'), url, seen)
                else:
                    doc = HTML(raw.decode('utf-8'))
                    links = sorted({urljoin(url, href) for href, _ in doc.links if re.search(r'/news/\d+$', href)}, reverse=True)[:5]
                    result = []
                    for link in links: result.extend(parse_etf_map_html(client.get(link).decode('utf-8'), link, seen))
                if not result: raise ValueError('Mapping table unavailable; not an empty ETF universe')
                by_code = {m['etf_code']: m for m in mappings}
                for row in result:
                    old_map = by_code.get(row['etf_code'])
                    if old_map:
                        row['first_seen_at'] = old_map['first_seen_at']
                        row['change_history'] = old_map.get('change_history', [])
                        if compact(old_map['index_name']) != compact(row['index_name']):
                            row['change_history'] += [{'observed_at': seen, 'previous': old_map}]
                    by_code[row['etf_code']] = row
                mappings = sorted(by_code.values(), key=lambda x: x['etf_code'])
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
        except Exception as error:
            entry.update(status='STALE' if entry['last_success_at'] else 'UNKNOWN', error=str(error)[:300])
        health.append(entry)
    # Mapping refresh can amend relationships but never supplies constituent lists.
    incoming = attach_mapping(incoming, mappings)
    # Renormalize previously observed future dates only when calendars arrive.
    # Preserve as-of lineage and never fabricate a fresh source check.
    for prior in old['events']:
        normalized = normalize_dates(prior, calendars)
        if normalized != prior: incoming.insert(0, normalized)
    events = merge_events(old['events'], incoming, seen)
    write(base / 'events-index.json', {'schema_version': 1, 'timezone': 'Asia/Taipei', 'range': [START, END],
          'generated_at': seen, 'coverage_status': 'PARTIAL', 'events': events,
          'limitations': '未公布、受限或解析失敗的來源不等於沒有事件。2027交易日曆未取得時不推算收盤日。'})
    write(base / 'source-health.json', {'last_attempt_at': seen,
          'last_successful_scan_at': seen if any(s['status'] == 'SUCCESS' for s in health) else health_old.get('last_successful_scan_at'),
          'coverage_status': 'PARTIAL', 'request_attempts': getattr(client, 'attempts', None), 'sources': health})
    write(base / 'document-registry.json', registry)
    existing_queue = load(base / 'review-queue.json', [])
    keyed = {(q['url'], q['sha256']): q for q in existing_queue + queue}
    write(base / 'review-queue.json', list(keyed.values()))
    write(base / 'etf-index-map.json', {'updated_at': seen, 'coverage_status': 'PARTIAL', 'mappings': mappings})
    rebuild_sidecars(root, events, seen)
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
