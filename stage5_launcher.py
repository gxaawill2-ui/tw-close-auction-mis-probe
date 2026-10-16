"""Prepared co-located shadow launcher. Not wired into any formal workflow.

Waits for the formal collector's own universe and journal. No MIS calls.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time
import urllib.request
import freshness as f
from stage5_runtime import Source, Vault, BASE, NoRedirect
from stage5_session import watch
from stage3_publication import Publisher
from stage5_archive import probe


def launch(journal,universe_file,date,directory,*,wait=time.sleep,clock=None):
    clock=clock or (lambda:datetime.now(f.TZ))
    if clock().date().isoformat()!=date or clock()>=f.parsed_time(date+'T13:24:45+08:00'):
        raise ValueError('NO_HISTORICAL_OR_LATE_SHADOW_START')
    token,key=os.getenv('STAGE5_PUBLISH_TOKEN'),os.getenv('STAGE5_DECISION_KEY')
    vault=Vault(token,key)
    probe(vault,date,clock=clock)
    root=Path(directory).resolve()
    workspace=Path(os.getenv('GITHUB_WORKSPACE',Path(__file__).parent)).resolve()
    if root==workspace or workspace in root.parents:raise ValueError('PRIVATE_SOURCE_MUST_BE_OUTSIDE_PUBLIC_CHECKOUT_ARTIFACTS')
    source=Source(os.getenv('FUGLE_API_KEY'),root/'private-fugle',vault,max_requests=160,require_durable=True)
    # This dedicated directory survives a process restart on the same runner.
    # A new runner must recompute evidence and use the remote monotonic version.
    publisher=Publisher(BASE,root/'session'/'publication',publish_token=token,decision_key=key,
        opener=urllib.request.build_opener(NoRedirect()).open)
    deadline=f.parsed_time(date+'T13:24:45+08:00')
    while not Path(universe_file).exists():
        if clock()>=deadline:raise ValueError('FORMAL_UNIVERSE_NOT_AVAILABLE_BEFORE_CUTOFF')
        wait(.5)
    universe=json.loads(Path(universe_file).read_text())
    if not isinstance(universe,list) or not universe or len({(s['ex'],s['code']) for s in universe})!=len(universe):
        raise ValueError('FORMAL_UNIVERSE_INVALID')
    return watch(journal,universe,date,root/'session',source,publisher)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('journal',type=Path);p.add_argument('universe',type=Path);p.add_argument('date');p.add_argument('private_directory',type=Path);a=p.parse_args()
    try:
        result=launch(a.journal,a.universe,a.date,a.private_directory)
        print(json.dumps({'status':'ISOLATED_SHADOW_WINDOW_ENDED','research_candidate_count':len(result['rows']) if result else None,
            'verified_count':result['verified_count'] if result else None,'physical_phone_verified':False}))
    except Exception as exc:
        print(json.dumps({'status':'ISOLATED_SHADOW_STOPPED_FORMAL_CAPTURE_UNAFFECTED','error_type':type(exc).__name__}))
        raise SystemExit(1)
