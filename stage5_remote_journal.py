"""Read approved private MIS bridge; never issues a MIS market-data request."""
from datetime import datetime
import hashlib
import json
import time
import urllib.request
from stage3_ticks import canonical
from stage5_runtime import BASE, NoRedirect
from stage3_publication import CLOUD_CLIENT
import re
import freshness as f
from stage6_journal_codec import decode


def consume(session,index,read,seen):
    """Replay immutable private batches; verify both outer and inner evidence."""
    entries=index.get('entries')
    if not isinstance(entries,list) or len(entries)>600:
        raise ValueError('PRIVATE_MIS_INDEX_INVALID')
    ids=[item.get('id') for item in entries]
    if any(not isinstance(i,str) or not re.fullmatch('[a-f0-9]{64}',i) for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('PRIVATE_MIS_INDEX_ID_INVALID')
    for item in entries:
        ident=item['id']
        if ident in seen:continue
        saved=read(ident);event=saved.get('event',{})
        if (saved.get('id')!=ident or saved.get('trade_date')!=session.date
            or saved.get('scope')!='PRIVATE_MIS_JOURNAL' or event.get('source')!='MIS'
            or hashlib.sha256(canonical(event).encode()).hexdigest()!=ident
            or hashlib.sha256(event['raw'].encode()).hexdigest()!=event['sha256']
            or item.get('sha256')!=event['sha256']):
            raise ValueError('PRIVATE_MIS_EVIDENCE_HASH_MISMATCH')
        journal=decode(event['raw']);record=journal.get('record',{})
        received=f.parsed_time(record.get('received_at'));saved_at=f.parsed_time(journal.get('persisted_at'))
        record_raw=canonical(record).encode()
        if (journal.get('origin')!='MIS_LOCAL_DURABLE_JOURNAL'
            or hashlib.sha256(record_raw).hexdigest()!=journal.get('sha256')
            or journal.get('raw_length')!=len(record_raw)
            or not received or not saved_at or not received<=saved_at<=session.clock()
            or received.astimezone(f.TZ).date().isoformat()!=session.date):
            raise ValueError('PRIVATE_MIS_JOURNAL_PROVENANCE_INVALID')
        # A private universe manifest is metadata, never a market observation.
        if record.get('phase')!='stage6_universe':session.feed(record,journal['persisted_at'])
        seen.add(ident)


def follow(session,token,*,opener=None,wait=time.sleep):
    opener=opener or urllib.request.build_opener(NoRedirect()).open
    seen=set();errors=0;catching_up=True
    def read(ident):
        request=urllib.request.Request(BASE+'/private-mis-journal/'+session.date+'/'+ident,headers={'Authorization':'Bearer '+token,'User-Agent':CLOUD_CLIENT,'Accept':'application/json'})
        with opener(request,timeout=6) as response:
            raw=response.read(150001)
            if response.status!=200 or len(raw)>150000:raise ValueError('PRIVATE_MIS_READ_INVALID')
            return json.loads(raw)
    while session.clock()<session.deadline:
        try:
            index=read('index')
            if catching_up:
                # A new wall-clock version must not publish an old partial replay
                # over the cloud's newer complete view during process recovery.
                publisher=getattr(session,'publisher',None)
                session.publisher=None
                try:consume(session,index,read,seen)
                finally:session.publisher=publisher
                if seen:
                    session.compile()
                    catching_up=False
            else:consume(session,index,read,seen)
            errors=0
        except Exception:
            errors+=1
            if errors>=3:return {'status':'PRIVATE_BRIDGE_UNAVAILABLE','batches_read':len(seen)}
        for _ in range(20):
            if session.clock()>=session.deadline:break
            session.tick();wait(.5)
    return {'status':'PRIVATE_JOURNAL_WINDOW_ENDED','batches_read':len(seen)}
