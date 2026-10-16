"""Proposed stdlib-only opt-in journal. No network or production directory writes."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import threading
import freshness as f

def encoded(record):
    return json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

class Journal:
    def __init__(self,directory,clock=None):
        temporary=Path(os.environ['RUNNER_TEMP']).resolve()
        self.path=Path(directory).resolve()
        if self.path==temporary or temporary not in self.path.parents:
            raise ValueError('JOURNAL_MUST_BE_WITHIN_DEDICATED_RUNNER_TEMP_SUBDIRECTORY')
        self.path.mkdir(parents=True,exist_ok=True);os.chmod(self.path,0o700)
        self.raw=self.path/'fast-capture-raw.jsonl';self.events=self.path/'fast-capture-journal.jsonl'
        self.clock=clock or (lambda:datetime.now(f.TZ).isoformat(timespec='microseconds'))
        self.lock=threading.Lock()

    def append(self,record):
        data=encoded(record)
        with self.lock:
            with self.raw.open('ab') as stream:
                os.chmod(self.raw,0o600);offset=stream.tell()
                stream.write(data+b'\n');stream.flush();os.fsync(stream.fileno())
            event={'record':record,'raw_file':self.raw.name,'raw_offset':offset,
                'raw_length':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                'persisted_at':self.clock(),'origin':'MIS_LOCAL_DURABLE_JOURNAL','pre_finality_proven':False}
            with self.events.open('ab') as stream:
                os.chmod(self.events,0o600);stream.write(encoded(event)+b'\n');stream.flush();os.fsync(stream.fileno())
            return event

