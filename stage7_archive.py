"""Same isolated Worker: fixed 30-day private copy and independent recovery.

No provider requests. Public reports contain hashes/counts only, never raw quotes.
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
from fast_selection import atomic
from stage3_ticks import canonical
from stage3_publication import envelope, CLOUD_CLIENT
from stage5_archive import checked
from stage5_runtime import Vault, restore_bundle
from stage7_evidence import review


class ArchiveVault(Vault):
    def _request(self,date,ident,body=None):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date) or not re.fullmatch(r'index|[a-f0-9]{64}',ident):
            raise ValueError('INVALID_ARCHIVE_REFERENCE')
        headers={'Authorization':'Bearer '+self.token,'User-Agent':CLOUD_CLIENT,'Accept':'application/json'}
        data=None
        if body is not None:
            data=canonical(envelope(body,self.key)).encode();headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+'/private-archive/'+date+'/'+ident,headers=headers,data=data)
        with self.opener(req,timeout=15) as r:
            if r.status!=200:raise ValueError('ARCHIVE_HTTP_REJECTED')
            raw=r.read(200001)
            if len(raw)>200000:raise ValueError('ARCHIVE_READ_TOO_LARGE')
            return json.loads(raw)

    def read(self,date,ident):
        return self._request(date,ident)

    def copy(self,date,ident):
        return self._request(date,ident,{'scope':'PRIVATE_FUGLE_ARCHIVE_COPY','trade_date':date,'id':ident})


def validate_index(index):
    entries=index.get('entries')
    if not isinstance(entries,list) or not 1<=len(entries)<=600:raise ValueError('ARCHIVE_INDEX_BUDGET')
    if any(not isinstance(e,dict) or set(e)!={'id','sha256'} or any(not isinstance(e[k],str) or not re.fullmatch('[a-f0-9]{64}',e[k]) for k in e) for e in entries):raise ValueError('ARCHIVE_INDEX_HASHES')
    if len({e['id'] for e in entries})!=len(entries):raise ValueError('ARCHIVE_INDEX_DUPLICATE')
    return sorted(entries,key=lambda e:e['id'])


def snapshot_digest(entries):
    return hashlib.sha256(canonical(entries).encode()).hexdigest()


def copy_snapshot(source,archive,date):
    entries=validate_index(source.read(date,'index'))
    receipts=[]
    for e in entries:
        r=archive.copy(date,e['id'])
        if r.get('id')!=e['id'] or r.get('sha256')!=e['sha256'] or not f.parsed_time(r.get('archive_expires_at')):raise ValueError('ARCHIVE_COPY_RECEIPT_MISMATCH')
        receipts.append(r);time.sleep(.15)
    if validate_index(source.read(date,'index'))!=entries:raise ValueError('SOURCE_CHANGED_REPEAT_EXPORT')
    expiries={r['archive_expires_at'] for r in receipts}
    if len(expiries)!=1:raise ValueError('ARCHIVE_EXPIRY_INCONSISTENT')
    return {'scope':'REAL_PRIVATE_ARCHIVE_COPY_NOT_MARKET_VERIFICATION','trade_date':date,
        'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'object_count':len(entries),'entries':entries,'manifest_sha256':snapshot_digest(entries),
        'archive_expires_at':expiries.pop(),'copied_at':datetime.now(f.TZ).isoformat(),
        'new_service':False,'provider_requests':0,'raw_exported_publicly':False,'status':'COPY_COMPLETE'}


def recover_snapshot(archive,date,expected):
    entries=validate_index(archive.read(date,'index'))
    if expected.get('trade_date')!=date or entries!=expected.get('entries') or snapshot_digest(entries)!=expected.get('manifest_sha256'):raise ValueError('INDEPENDENT_ARCHIVE_MANIFEST_MISMATCH')
    size=0;manifests=0
    for e in entries:
        saved=checked(archive.read(date,e['id']),date,e['id'])
        if saved['event']['sha256']!=e['sha256'] or saved.get('archive_expires_at')!=expected['archive_expires_at'] or not f.parsed_time(saved.get('source_private_written_at')):raise ValueError('ARCHIVE_OBJECT_MISMATCH')
        size+=len(saved['event']['raw'].encode())
        if saved['event'].get('kind')=='bundle_manifest':
            restore_bundle(archive,date,e['id']);manifests+=1
    return {'scope':'REAL_INDEPENDENT_ARCHIVE_RECOVERY_NOT_MARKET_VERIFICATION','trade_date':date,
        'run_id':os.getenv('GITHUB_RUN_ID'),'source_commit':os.getenv('GITHUB_SHA'),
        'object_count':len(entries),'raw_bytes_verified':size,'bundles_restored':manifests,
        'manifest_sha256':snapshot_digest(entries),'archive_expires_at':expected['archive_expires_at'],
        'recovered_at':datetime.now(f.TZ).isoformat(),'source_namespace_reads':0,
        'provider_requests':0,'raw_exported_publicly':False,'physical_phone_tested':False,'status':'PASS'}


def diagnostics(archive,date):
    root=Path('reports/2026-10-16-stage5');ids={}
    for name in ('real-candidate-private-audit.json','real-remaining-candidate-audit.json'):
        for a in json.loads((root/name).read_text())['audits']:ids[a['symbol']]=a['private_manifest_id']
    ids['5546']=json.loads((root/'real-delayed-private-audit.json').read_text())['diagnostic']['private_manifest_id']
    refs=json.loads((root/'mis-comparison-references.json').read_text())['rows']
    return {'scope':'ARCHIVED_REAL_EVIDENCE_REANALYSIS_NOT_LIVE','provider_requests':0,
        'verified_count':0,'results':[review(restore_bundle(archive,date,ids[r['code']]),r,date,datetime.now(f.TZ).isoformat()) for r in refs]}


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['copy','recover','review']);p.add_argument('--date',default='2026-10-16');p.add_argument('--manifest',default='stage7-copy-report/copy.json');a=p.parse_args()
    if os.getenv('GITHUB_REPOSITORY')!='gxaawill2-ui/tw-close-auction-mis-probe' or os.getenv('GITHUB_REF')!='refs/heads/stage4/20261016-fugle-probe':raise ValueError('REFUSE_OTHER_ENVIRONMENT')
    vault=Vault(os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY'));archive=ArchiveVault(vault.token,vault.key)
    out=Path('stage7-'+a.mode+'-report');out.mkdir(exist_ok=True)
    if a.mode=='copy':report=copy_snapshot(vault,archive,a.date)
    elif a.mode=='review':
        if a.date!='2026-10-16':raise ValueError('SAVED_REFERENCE_DATE_MISMATCH')
        proof=json.loads(Path('reports/2026-10-16-stage7/real-private-archive-proof.json').read_text())['proofs'][0]
        entries=validate_index(archive.read(a.date,'index'))
        if len(entries)!=proof['object_count'] or snapshot_digest(entries)!=proof['manifest_sha256']:raise ValueError('ARCHIVE_SNAPSHOT_CHANGED')
        report=diagnostics(archive,a.date)
        report.update(archive_manifest_sha256=proof['manifest_sha256'],run_id=os.getenv('GITHUB_RUN_ID'),source_commit=os.getenv('GITHUB_SHA'),archive_expires_at=proof['archive_expires_at'])
        for row in report['results']:print(json.dumps({'safe_field_review':row}),flush=True)
    else:
        report=recover_snapshot(archive,a.date,json.loads(Path(a.manifest).read_text()))
        if a.date=='2026-10-16':atomic(out/'diagnostics.json',diagnostics(archive,a.date))
    atomic(out/(a.mode+'.json'),report)
    print(json.dumps({k:v for k,v in report.items() if k!='entries'}),flush=True)

if __name__=='__main__':main()
