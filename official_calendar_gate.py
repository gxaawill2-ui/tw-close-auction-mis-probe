"""Strict annual TWSE calendar validation; no market-data requests."""
from datetime import date, datetime, timedelta

SOURCE = 'https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule'


def url(year):
    # queryYear is no longer a supported selector: it returns the default year.
    return SOURCE + f'?response=json&date={year}0101'


def closed_dates(data, year):
    if (not isinstance(data, dict) or data.get('stat') != 'ok' or
            type(data.get('queryYear')) is not int or data['queryYear'] != year or
            not isinstance(data.get('data'), list) or not data['data']):
        raise ValueError('INVALID_OFFICIAL_CALENDAR_YEAR_OR_SCHEMA')
    closed = set()
    for row in data['data']:
        if not isinstance(row, list) or len(row) < 2 or not isinstance(row[1], str):
            raise ValueError('INVALID_OFFICIAL_CALENDAR_ROW')
        parsed = date.fromisoformat(row[0])
        if parsed.year != year or parsed.isoformat() != row[0]:
            raise ValueError('INVALID_OFFICIAL_CALENDAR_DATE')
        if '最後交易日' not in row[1] and '開始交易日' not in row[1]:
            closed.add(row[0])
    if not closed:
        raise ValueError('EMPTY_OFFICIAL_CLOSURES')
    return closed


def cached_dates(data, now):
    """Only a recent, same-year, previously official cache can be a fallback.

    Annual calendars do not independently prove absence of emergency closures;
    the persisted result explicitly retains that existing limitation.
    """
    if (not isinstance(data, dict) or type(data.get('year')) is not int or
            data['year'] != now.year or data.get('status') != 'OFFICIAL_ANNUAL_CALENDAR' or
            not isinstance(data.get('source'), str) or
            not data['source'].startswith(SOURCE + '?') or
            not isinstance(data.get('closed_dates'), list) or not data['closed_dates']):
        raise ValueError('UNTRUSTED_CALENDAR_CACHE')
    verified = datetime.fromisoformat(data['verified_at'].replace('Z', '+00:00'))
    if verified.tzinfo is None or not timedelta(0) <= now - verified <= timedelta(days=7):
        raise ValueError('STALE_OR_FUTURE_CALENDAR_CACHE')
    closed = set()
    for value in data['closed_dates']:
        parsed = date.fromisoformat(value)
        if parsed.year != now.year or parsed.isoformat() != value:
            raise ValueError('INVALID_CACHED_CALENDAR_DATE')
        closed.add(value)
    return closed
