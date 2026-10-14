"""Opt-in append/fsync raw batch storage; no network and no GitHub writes."""
import hashlib
import json
import os
import threading
from pathlib import Path
from datetime import datetime
import freshness as f


def encoded(record):return json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


class Journal:
    def __init__(self,directory,clock=None):
        from fast_selection import safe_output
        self.path=safe_output(directory);self.lock=threading.Lock()
        self.raw=self.path/'fast-capture-raw.jsonl';self.events=self.path/'fast-capture-journal.jsonl'
        self.clock=clock or (lambda:datetime.now(f.TZ).isoformat(timespec='microseconds'))

    def append(self,record):
        data=encoded(record)
        with self.lock:
            with self.raw.open('ab') as file:
                offset=file.tell();file.write(data+b'\n');file.flush();os.fsync(file.fileno())
            # This timestamp is taken AFTER the actual raw bytes have been fsynced.
            persisted=self.clock()
            event={'record':record,'raw_file':self.raw.name,'raw_offset':offset,'raw_length':len(data),
                   'sha256':hashlib.sha256(data).hexdigest(),'persisted_at':persisted,
                   'origin':'MIS_LOCAL_DURABLE_JOURNAL','pre_finality_proven':False}
            with self.events.open('ab') as file:
                file.write(encoded(event)+b'\n');file.flush();os.fsync(file.fileno())
            return event


def verify(event,directory):
    if event.get('raw_file')!='fast-capture-raw.jsonl':raise ValueError('INVALID_JOURNAL_RAW_PATH')
    with (Path(directory)/event['raw_file']).open('rb') as file:
        file.seek(event['raw_offset']);data=file.read(event['raw_length'])
    if hashlib.sha256(data).hexdigest()!=event.get('sha256') or data!=encoded(event['record']):
        raise ValueError('JOURNAL_EVIDENCE_HASH_MISMATCH')
    received=f.parsed_time(event['record'].get('received_at'));saved=f.parsed_time(event.get('persisted_at'))
    if not received or not saved or received>saved:raise ValueError('INVALID_DURABILITY_TIME')
    return event
