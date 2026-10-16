"""Private archive recovery. Never upload its output as a public artifact.

The existing isolated vault retains objects for seven days. Export only into an
explicit private directory outside the repository; no provider request is made.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile

import freshness as f
from stage3_ticks import canonical
from stage5_runtime import Vault


def checked(saved,date,ident):
    event=saved.get('event',{})
    if (saved.get('id')!=ident or saved.get('trade_date')!=date
        or saved.get('scope')!='PRIVATE_FUGLE_EVIDENCE'
        or event.get('source')!='FUGLE' or not isinstance(event.get('raw'),str)
        or hashlib.sha256(canonical(event).encode()).hexdigest()!=ident
        or hashlib.sha256(event['raw'].encode()).hexdigest()!=event.get('sha256')
        or not f.parsed_time(saved.get('private_written_at'))):
        raise ValueError('PRIVATE_ARCHIVE_INTEGRITY_FAILED')
    return saved


def probe(vault,date,*,clock=None):
    """Non-market canary: verify private write AND independent authenticated read."""
    clock=clock or (lambda:datetime.now(f.TZ))
    if clock().date().isoformat()!=date:raise ValueError('NO_HISTORICAL_STORAGE_CANARY')
    raw=canonical({'is_synthetic':True,'purpose':'PRIVATE_STORAGE_CANARY_NOT_MARKET_DATA','nonce':secrets.token_hex(16)})
    at=clock().isoformat()
    event={'source':'FUGLE','kind':'SYNTHETIC_STORAGE_CANARY','origin_kind':'SYNTHETIC_NOT_PROVIDER_RESPONSE',
        'raw':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'persisted_at':at,'received_at':at,'requested_at':at}
    receipt=vault.save(event,date)
    if receipt.get('recoverable_after_job') is not True:raise ValueError('PRIVATE_ARCHIVE_NOT_DURABLE')
    saved=checked(vault.read(date,receipt['id']),date,receipt['id'])
    if saved['event']!=event:raise ValueError('PRIVATE_CANARY_READBACK_MISMATCH')
    return {'scope':'SYNTHETIC_PRIVATE_STORAGE_NOT_MARKET_ACCEPTANCE','id':receipt['id'],
        'private_written_at':saved['private_written_at'],'read_back_at':clock().isoformat()}


def private_write(path,data):
    """0600 before writing, fsync bytes then atomic replacement and directory."""
    fd,name=tempfile.mkstemp(prefix='.archive-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(canonical(data).encode());stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
        directory=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(name):os.unlink(name)


def export(vault,date,directory):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):raise ValueError('INVALID_ARCHIVE_DATE')
    root=Path(directory).resolve();repo=Path(__file__).parent.resolve()
    workspace=Path(os.getenv('GITHUB_WORKSPACE',repo)).resolve()
    if any(root==p or p in root.parents for p in (repo,workspace)):
        raise ValueError('PRIVATE_EXPORT_CANNOT_ENTER_CHECKOUT')
    root.mkdir(parents=True,exist_ok=True);os.chmod(root,0o700)
    downloaded={};last=[];stable=False
    for _ in range(2):
        index=vault.read(date,'index');entries=index.get('entries')
        if not isinstance(entries,list) or len(entries)>600:raise ValueError('PRIVATE_INDEX_INVALID_OR_OVER_BUDGET')
        ids=[item.get('id') for item in entries]
        if any(not isinstance(i,str) or not re.fullmatch('[a-f0-9]{64}',i) for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('PRIVATE_INDEX_ID_INVALID')
        for item in entries:
            ident=item['id']
            if ident in downloaded:
                if downloaded[ident]!=item:raise ValueError('PRIVATE_INDEX_CHANGED_HASH')
                continue
            path=root/(ident+'.json')
            if path.is_symlink():raise ValueError('PRIVATE_EXPORT_SYMLINK_REJECTED')
            saved=checked(json.loads(path.read_text()) if path.exists() else vault.read(date,ident),date,ident)
            if saved['event']['sha256']!=item.get('sha256'):raise ValueError('PRIVATE_INDEX_HASH_MISMATCH')
            private_write(path,saved);downloaded[ident]=item
        stable=ids==last;last=ids
    report={'scope':'PRIVATE_ARCHIVE_EXPORT_NOT_MARKET_VERIFICATION','trade_date':date,
        'completed_at':datetime.now(f.TZ).isoformat(),'object_count':len(downloaded),
        'index_stable_during_export':stable,'status':'SNAPSHOT_COMPLETE' if stable else 'INDEX_CHANGED_EXPORT_AGAIN',
        'manifest_sha256':hashlib.sha256(canonical(sorted(downloaded)).encode()).hexdigest()}
    private_write(root/'private-export-manifest.json',{'report':report,'entries':list(downloaded.values())})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('date');parser.add_argument('private_directory',type=Path);args=parser.parse_args()
    try:
        print(json.dumps(export(Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY')),args.date,args.private_directory)))
    except Exception as exc:
        print(json.dumps({'status':'PRIVATE_EXPORT_FAILED_NO_RAW_LOGGED','error_type':type(exc).__name__}));raise SystemExit(1)
