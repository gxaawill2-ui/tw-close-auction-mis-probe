"""Read approved private MIS bridge; never issues a MIS market-data request."""
from datetime import datetime
import hashlib
import json
import time
import urllib.request
from stage3_ticks import canonical
from stage5_runtime import BASE, NoRedirect


def follow(session,token,*,opener=None,wait=time.sleep):
    opener=opener or urllib.request.build_opener(NoRedirect()).open
    seen=set();errors=0
    def read(ident):
        request=urllib.request.Request(BASE+'/private-mis-journal/'+session.date+'/'+ident,headers={'Authorization':'Bearer '+token})
        with opener(request,timeout=6) as response:return json.loads(response.read(150000))
    while session.clock()<session.deadline:
        try:
            index=read('index')
            for item in index.get('entries',[]):
                ident=item['id']
                if ident in seen:continue
                saved=read(ident);event=saved['event']
                if event.get('source')!='MIS' or hashlib.sha256(canonical(event).encode()).hexdigest()!=ident or hashlib.sha256(event['raw'].encode()).hexdigest()!=event['sha256']:
                    raise ValueError('PRIVATE_MIS_EVIDENCE_HASH_MISMATCH')
                journal=json.loads(event['raw'])
                session.feed(journal['record'],journal['persisted_at']);seen.add(ident)
            errors=0
        except Exception:
            errors+=1
            if errors>=3:return {'status':'PRIVATE_BRIDGE_UNAVAILABLE','batches_read':len(seen)}
        for _ in range(20):
            if session.clock()>=session.deadline:break
            session.tick();wait(.5)
    return {'status':'PRIVATE_JOURNAL_WINDOW_ENDED','batches_read':len(seen)}
