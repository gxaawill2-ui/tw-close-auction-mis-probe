"""GitHub-runner read-only observer of today's existing formal capture.

No MIS requests, workflow dispatch, contents writes, or production secrets.
Use only this isolated job's short-lived read-only GITHUB_TOKEN.
"""
import argparse
import base64
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import zipfile

import freshness as f
from fast_selection import atomic,safe_output
from stage4_shadow import analyze
from stage4_observation import save

REPO='gxaawill2-ui/tw-close-auction-mis-probe'
ORIGIN='https://api.github.com/repos/'+REPO+'/'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*_,**__):return None


def api(path):
    if path.startswith('/') or '..' in path or not path.startswith(('contents/state/','actions/runs/','actions/runs?','actions/artifacts/')):
        raise ValueError('READ_PATH_NOT_ALLOWED')
    req=urllib.request.Request(ORIGIN+path,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],
        'Accept':'application/vnd.github+json','User-Agent':'isolated-tail-read-only-observer'})
    try:
        with urllib.request.urlopen(req,timeout=10) as response:return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code==404:return None
        raise RuntimeError('GITHUB_HTTP_'+str(exc.code)) from None


def state(path):
    data=api('contents/state/'+path+'?ref=main')
    return json.loads(base64.b64decode(data['content'])) if data else None


def download(artifact,directory):
    # Never carry the read-only job token across the storage redirect.
    request=urllib.request.Request(ORIGIN+'actions/artifacts/'+str(artifact['id'])+'/zip',headers={
        'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=15) as response:raw=response.read(100_000_001)
    except urllib.error.HTTPError as exc:
        if exc.code not in (301,302,303,307,308):raise RuntimeError('DOWNLOAD_HTTP_'+str(exc.code)) from None
        location=exc.headers.get('Location','')
        if not location.startswith('https://'):raise ValueError('NON_HTTPS_ARTIFACT_REDIRECT')
        # location is a transient signed URL: do not print or persist it.
        with urllib.request.urlopen(urllib.request.Request(location,headers={'User-Agent':'isolated-tail-reader'}),timeout=30) as response:
            raw=response.read(100_000_001)
    received=datetime.now(f.TZ).isoformat()
    if len(raw)>100_000_000:raise ValueError('ARTIFACT_TOO_LARGE')
    digest=hashlib.sha256(raw).hexdigest();expected=artifact.get('digest')
    if expected and expected!='sha256:'+digest:raise ValueError('GITHUB_ARTIFACT_DIGEST_MISMATCH')
    path=directory/('capture-artifact-'+str(artifact['id'])+'-'+uuid.uuid4().hex+'.zip')
    with path.open('xb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
    persisted=datetime.now(f.TZ).isoformat()
    receipt={'artifact_id':artifact['id'],'name':artifact['name'],'github_created_at':artifact.get('created_at'),
        'github_digest':expected,'sha256':digest,'received_at':received,'persisted_at':persisted,
        'raw_file':path.name,'signed_download_url_saved':False}
    atomic(directory/'download-receipt.json',receipt)
    atomic(directory/(path.stem+'-receipt.json'),receipt)
    return path,receipt


def capture_path(archive,directory):
    # Standard Actions upload includes results/ and a nested capture ZIP. Prefer
    # the original outer raw files; allow exactly one inner ZIP when necessary.
    with zipfile.ZipFile(archive) as z:
        if any(Path(n).name=='preclose_raw.jsonl' for n in z.namelist()):return archive
        nested=[i for i in z.infolist() if Path(i.filename).name.startswith('mis-probe-') and i.filename.endswith('.zip')]
        if len(nested)!=1 or nested[0].file_size>100_000_000:raise ValueError('NO_UNAMBIGUOUS_CAPTURE_ZIP')
        raw=z.read(nested[0]);path=directory/'inner-capture.zip'
        with path.open('xb') as file:file.write(raw);file.flush();os.fsync(file.fileno())
        atomic(directory/'inner-capture-receipt.json',{'sha256':hashlib.sha256(raw).hexdigest(),
            'derived_from_outer':archive.name,'note':'Inner digest is distinct from GitHub outer artifact digest.'})
        return path


def watch(date,output,*,follow=False,clock=None,wait=time.sleep):
    clock=clock or (lambda:datetime.now(f.TZ));directory=safe_output(output)
    if clock().astimezone(f.TZ).date().isoformat()!=date:raise ValueError('NO_HISTORICAL_WATCH')
    deadline=f.parsed_time(date+('T14:30:00+08:00' if follow else 'T13:40:00+08:00'))
    if clock()>=deadline:raise ValueError('WATCH_WINDOW_ALREADY_ENDED')
    attempted={};previous=None;errors=0
    while clock()<deadline:
        try:
            now=clock();at=now.isoformat()
            # Poll slowly before the primary slot; 20s after it. No market API.
            capture=state('live/'+date+'.json')
            signature=json.dumps(capture,sort_keys=True)
            if signature!=previous:
                atomic(directory/('formal-state-'+uuid.uuid4().hex+'.json'),{'observed_at':at,'state':capture})
                previous=signature
            if follow:
                candidate=state('candidates/'+date+'.json')
                atomic(directory/'follow-latest.json',{'observed_at':at,'formal_state':capture,
                    'candidate_publication':candidate,'note':'Formal publication labels are recorded, not adopted as independent VERIFIED.'})
            else:
                if now.strftime('%H:%M:%S')<'13:00:00':
                    wait(min(60,max(0,(deadline-clock()).total_seconds())));continue
                runs=api('actions/runs?per_page=30&created=%3E%3D'+date+'T00%3A00%3A00Z')
                if runs:save(runs,date,directory/'actions',clock().isoformat())
                run_id=(capture or {}).get('run_id')
                if run_id:
                    artifacts=api('actions/runs/'+str(run_id)+'/artifacts?per_page=100') or {}
                    for artifact in artifacts.get('artifacts',[]):
                        if attempted.get(artifact['id'],0)>=3 or artifact.get('expired') or artifact['name']!='mis-probe-'+str(run_id):continue
                        attempted[artifact['id']]=attempted.get(artifact['id'],0)+1
                        path,receipt=download(artifact,directory)
                        source=capture_path(path,directory)
                        result=analyze(source,date,directory/'analysis',artifact_received_at=receipt['received_at'],artifact_persisted_at=receipt['persisted_at'])
                        atomic(directory/'first-capture-result.json',{'observed_at':clock().isoformat(),'source_run_id':run_id,
                            'research_count':result['research_count'],'verified_count':result['verified_count'],
                            'provenance':result['provenance']})
                        print(json.dumps({'event':'SAVED_CAPTURE_ANALYZED','run_id':run_id,
                            'research_count':result['research_count'],'verified_count':result['verified_count'],'at':clock().isoformat()}),flush=True)
                        return result
            errors=0
        except Exception as exc:
            errors+=1
            atomic(directory/('observer-error-'+uuid.uuid4().hex+'.json'),{'observed_at':clock().isoformat(),
                'error_type':type(exc).__name__,'consecutive_errors':errors,'formal_signals':None})
            # No exception URL/header/token goes into logs. Stop an error loop.
            if errors>=3:break
        wait(min(20,max(0,(deadline-clock()).total_seconds())))
    atomic(directory/'watch-ended.json',{'ended_at':clock().isoformat(),'deadline':deadline.isoformat(),
        'status':'FOLLOW_WINDOW_ENDED' if follow else 'NO_VALID_SAVED_CAPTURE_ANALYZED','formal_signals':None})
    return None


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('date');p.add_argument('output',type=Path);p.add_argument('--follow',action='store_true');a=p.parse_args()
    watch(a.date,a.output,follow=a.follow)
