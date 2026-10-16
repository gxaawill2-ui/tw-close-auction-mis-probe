"""Dormant bridge proposal: existing local MIS journal -> private isolated vault.

Never captures MIS, never reads Fugle, never writes production or public results.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request
import freshness as f
from fast_capture_journal import verify
from stage3_ticks import canonical
from stage3_publication import envelope, CLOUD_CLIENT
from stage5_runtime import BASE, NoRedirect


def bridge(journal,date,*,token=None,opener=None,clock=None,wait=time.sleep):
    token=token or os.getenv('STAGE5_MIS_BRIDGE_TOKEN')
    if not isinstance(token,str) or not re.fullmatch(r'[a-f0-9]{64}',token):raise ValueError('NARROW_MIS_BRIDGE_NOT_CONFIGURED')
    clock=clock or (lambda:datetime.now(f.TZ));opener=opener or urllib.request.build_opener(NoRedirect()).open
    if clock().date().isoformat()!=date:raise ValueError('NO_HISTORICAL_MIS_BRIDGE')
    deadline=f.parsed_time(date+'T14:30:00+08:00');offset=0;written=0;errors=0
    while clock()<deadline:
        if Path(journal).exists():
            with Path(journal).open() as stream:
                stream.seek(offset)
                while clock()<deadline:
                    start=stream.tell();line=stream.readline()
                    if not line or not line.endswith('\n'):break
                    journal_event=verify(json.loads(line),Path(journal).parent)
                    raw=canonical(journal_event)
                    event={'source':'MIS','raw':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
                    ident=hashlib.sha256(canonical(event).encode()).hexdigest()
                    body={'trade_date':date,'id':ident,'scope':'PRIVATE_MIS_JOURNAL','event':event}
                    data=canonical(envelope(body,token)).encode()
                    if len(data)>98304:raise ValueError('MIS_EVENT_TOO_LARGE')
                    request=urllib.request.Request(BASE+'/private-mis-journal/'+date+'/'+ident,method='POST',data=data,
                        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','User-Agent':CLOUD_CLIENT,'Accept':'application/json'})
                    try:
                        with opener(request,timeout=3) as response:receipt=json.loads(response.read(4097))
                        if response.status!=200 or receipt.get('id')!=ident or receipt.get('sha256')!=event['sha256'] or not f.parsed_time(receipt.get('private_written_at')):raise ValueError('MIS_BRIDGE_RECEIPT_MISMATCH')
                        written+=1;offset=stream.tell();errors=0
                    except Exception:
                        errors+=1
                        if errors>=3:return {'status':'BRIDGE_STOPPED_FORMAL_CAPTURE_UNAFFECTED','written_batches':written}
                        break
        wait(.5)
    return {'status':'BRIDGE_WINDOW_ENDED','written_batches':written}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('journal',type=Path);p.add_argument('date');a=p.parse_args()
    try:print(json.dumps(bridge(a.journal,a.date)))
    except Exception:print('{"status":"BRIDGE_FAILED_FORMAL_CAPTURE_UNAFFECTED"}');raise SystemExit(1)
