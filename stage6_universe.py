"""Dormant authenticated universe handoff. No market-data requests or schedules."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import base64
import zlib
import os
import freshness as f
from stage3_ticks import canonical
from fast_capture_journal import Journal
from stage3_publication import envelope,CLOUD_CLIENT
from stage5_runtime import BASE,NoRedirect
from stage5_remote_journal import consume
from stage6_journal_codec import decode


def validate_symbols(symbols):
    if (not isinstance(symbols,list) or not 1<=len(symbols)<=2500 or
        any(s.get('ex') not in ('tse','otc') or not re.fullmatch(r'[1-9]\d{3}',str(s.get('code',''))) for s in symbols) or
        len({(s['ex'],s['code']) for s in symbols})!=len(symbols)):
        raise ValueError('FORMAL_UNIVERSE_INVALID')
    return symbols


def send(universe_path,date,run_id,directory,token,*,clock=None,opener=None):
    """After approval, bridge the collector's own saved universe using narrow token."""
    clock=clock or (lambda:datetime.now(f.TZ));opener=opener or urllib.request.build_opener(NoRedirect()).open
    if not re.fullmatch('[a-f0-9]{64}',token or '') or not str(run_id).isdigit():raise ValueError('UNIVERSE_BRIDGE_NOT_CONFIGURED')
    if clock().date().isoformat()!=date:raise ValueError('NO_HISTORICAL_UNIVERSE_BRIDGE')
    symbols=validate_symbols(json.loads(Path(universe_path).read_text()))
    universe_raw=canonical(symbols).encode()
    if len(universe_raw)>2000000:raise ValueError('UNIVERSE_TOO_LARGE')
    record={'phase':'stage6_universe','received_at':clock().isoformat(),'trade_date':date,
        'source_run_id':str(run_id),'symbols_z':base64.b64encode(zlib.compress(universe_raw)).decode(),
        'universe_sha256':hashlib.sha256(universe_raw).hexdigest()}
    j=Journal(directory,clock=lambda:clock().isoformat());journal=j.append(record)
    os.chmod(j.raw,0o600);os.chmod(j.events,0o600)
    raw=canonical(journal);event={'source':'MIS','raw':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}
    ident=hashlib.sha256(canonical(event).encode()).hexdigest()
    body={'scope':'PRIVATE_MIS_JOURNAL','trade_date':date,'id':ident,'event':event}
    data=canonical(envelope(body,token)).encode()
    if len(data)>98304:raise ValueError('UNIVERSE_BRIDGE_PACKET_OVER_BUDGET')
    req=urllib.request.Request(BASE+'/private-mis-journal/'+date+'/'+ident,method='POST',data=data,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','User-Agent':CLOUD_CLIENT})
    with opener(req,timeout=3) as response:
        receipt=json.loads(response.read(4097))
        if response.status!=200 or receipt.get('id')!=ident or receipt.get('sha256')!=event['sha256'] or not f.parsed_time(receipt.get('private_written_at')):
            raise ValueError('UNIVERSE_BRIDGE_RECEIPT_INVALID')
    return receipt


def receive(date,run_id,read,clock):
    """Read only authenticated private bridge objects; no public-artifact barrier."""
    index=read('index');seen=set();found=[]
    class Inspection:
        def feed(self,record,persisted_at):pass
    s=Inspection();s.date=date;s.clock=clock
    def checked_read(ident):
        saved=read(ident)
        # consume verifies this full object before the found list is returned.
        record=decode(saved['event']['raw'])['record']
        if record.get('phase')=='stage6_universe':found.append(record)
        return saved
    consume(s,index,checked_read,seen)
    relevant=[r for r in found if r.get('trade_date')==date and r.get('source_run_id')==str(run_id)]
    if not relevant:return None
    sets={r['universe_sha256'] for r in relevant}
    if len(sets)!=1:raise ValueError('FORMAL_UNIVERSE_CHANGED_WITHIN_RUN')
    selected=relevant[0]
    decoder=zlib.decompressobj();raw=decoder.decompress(base64.b64decode(selected['symbols_z'],validate=True),2000001)
    if len(raw)>2000000 or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
        raise ValueError('UNIVERSE_DECOMPRESSION_BUDGET_OR_TRAILING_DATA')
    symbols=validate_symbols(json.loads(raw))
    if hashlib.sha256(raw).hexdigest()!=selected['universe_sha256'] or raw!=canonical(symbols).encode():
        raise ValueError('FORMAL_UNIVERSE_DIGEST_CONFLICT')
    return symbols
