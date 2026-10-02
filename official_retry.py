"""Recheck a saved capture artifact. Never request MIS or reconstruct missing ticks."""
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import freshness
import convergence
import official_quotes


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def download_archive(repo,artifact_id):
    url=f'https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip'
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],
                                              'Accept':'application/vnd.github+json','User-Agent':'independent-mis-probe'})
    # Never forward the GitHub token to the signed storage redirect.
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=25) as response:return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (301,302,303,307,308):raise
        location=exc.headers.get('Location','')
        if not location.startswith('https://'):raise RuntimeError('Invalid artifact download redirect')
        with urllib.request.urlopen(urllib.request.Request(location,headers={'User-Agent':'independent-mis-probe'}),timeout=45) as response:
            return response.read()


def load_capture(archive):
    files={}
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for name in z.namelist():
            base=Path(name).name
            phases = ('preclose','close','delayed_close',*convergence.REFERENCE_TIMES,'pre_targeted_retry','close_targeted_retry')
            if base in tuple(p+'_raw.jsonl' for p in phases)+('probe_raw.jsonl','universe.json','run_summary.json'):
                if base in files and files[base]!=z.read(name):raise RuntimeError('Conflicting artifact files '+base)
                files[base]=z.read(name).decode('utf-8')
    required=('preclose_raw.jsonl','probe_raw.jsonl','universe.json','run_summary.json')
    missing=[name for name in required if name not in files]
    if missing:raise RuntimeError('Capture artifact missing '+','.join(missing))
    summary=json.loads(files['run_summary.json']);universe=json.loads(files['universe.json'])
    capture_phases = ('preclose',*convergence.REFERENCE_TIMES) if summary.get('capture_architecture') == convergence.VERSION else ('preclose','close','delayed_close')
    missing=[p+'_raw.jsonl' for p in capture_phases if p+'_raw.jsonl' not in files]
    if missing:raise RuntimeError('Capture artifact missing '+','.join(missing))
    snapshots=[{'records':[json.loads(s) for s in files[p+'_raw.jsonl'].splitlines()]} for p in (*capture_phases,'pre_targeted_retry','close_targeted_retry') if p+'_raw.jsonl' in files]
    probes=[json.loads(s) for s in files['probe_raw.jsonl'].splitlines()]
    return summary,universe,snapshots,probes


def run(date,output,control,probe):
    output.mkdir(parents=True,exist_ok=True)
    capture,_=control.read_state(control.live_path(date))
    result={'trade_date':date,'checked_at':probe.iso(),'run_id':os.getenv('GITHUB_RUN_ID'),'status':'PENDING_NO_CAPTURE'}
    capture_id=capture.get('run_id')
    if capture_id and capture.get('preclose_captured'):
        artifacts=control.api(f'actions/runs/{capture_id}/artifacts?per_page=100')
        matching=[a for a in artifacts.get('artifacts',[]) if a['name']=='mis-probe-'+str(capture_id) and not a.get('expired')]
        if not matching:raise RuntimeError('Saved capture Artifact unavailable; no MIS backfill permitted')
        saved=download_archive(control.REPO,matching[0]['id'])
        summary,universe,snapshots,probes=load_capture(saved)
        if summary.get('trade_date')!=date:raise RuntimeError('Saved capture trade date mismatch')
        # Old 10/1 files have no symbols on probe rows. Use the saved company pool,
        # not a current-day reconstructed identity list.
        lookup={(s['ex'],s['code']):s for s in universe}
        for row in probes:
            if 'symbols' not in row:row['symbols']=[lookup[k] for k in probe.FIXED_PROBE if k in lookup]
        selected = convergence.build_report(date,snapshots,probes,universe,{'checks':[]}) if summary.get('capture_architecture') == convergence.VERSION else None
        validation=official_quotes.validate(date,universe,snapshots,output,probe.get_bytes,
                                            selected_closes=selected['securities'] if selected else None)
        review=freshness.write_report(date,snapshots,probes,universe,validation,output)
        dual=convergence.write_report(date,snapshots,probes,universe,validation,output)
        result.update({'status':validation['status'],'source_capture_run_id':capture_id,
                       'source_capture_artifact_id':matching[0]['id'],'official_validation':validation['status'],
                       'matches':validation['matches'],'mismatches':validation['mismatches'],'unavailable':validation['unavailable'],
                       'official_sources':validation['sources'],'freshness':{k:review[k] for k in ('p_before_validated_count','p_close_validated_count','both_validated_count')},
                       'convergence':{k:v for k,v in dual.items() if k.endswith('_count') or k in ('status','version','validated')},
                       'candidate_status':dual['status'],'candidate_count':dual['research_candidate_count'],
                       'artifact':'mis-validation-'+str(os.getenv('GITHUB_RUN_ID'))})
    path='state/validation/'+date+'.json'
    previous,_=control.read_state(path)
    history=previous.get('publication_observations',[])
    history.append({'checked_at':result['checked_at'],'status':result['status'],
                    'sources':result.get('official_sources',[])})
    result['publication_observations']=history[-12:]
    result['publication_timing_note']='Only observed checks bound availability; exact release time is not assumed.'
    (output/'validation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    control.merge_state(path,result)
    control.publish()
    probe.package(output,date)
    return 0
