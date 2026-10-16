"""Approved-use entry point ONLY: saved formal universe and local journal -> vault.

Never wired to production by this stage. Any failure exits this process alone.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import time
import freshness as f
from stage6_universe import send
from stage5_journal_bridge import bridge


def launch(journal,universe,date,run_id,private_dir):
    deadline=f.parsed_time(date+'T13:24:45+08:00')
    while not Path(universe).exists():
        now=datetime.now(f.TZ)
        if now.date().isoformat()!=date or now>=deadline:raise ValueError('FORMAL_UNIVERSE_NOT_AVAILABLE')
        time.sleep(.5)
    private=Path(private_dir).resolve();repo=Path(__file__).parent.resolve()
    workspace=Path(os.getenv('GITHUB_WORKSPACE',repo)).resolve()
    if any(private==p or p in private.parents for p in (repo,workspace)):raise ValueError('PRIVATE_BRIDGE_ROOT_INVALID')
    private.mkdir(parents=True,exist_ok=True);os.chmod(private,0o700)
    token=os.getenv('STAGE5_MIS_BRIDGE_TOKEN')
    send(universe,date,run_id,private,token)
    return bridge(journal,date,token=token)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('journal','universe','date','formal_run_id','private_directory'):p.add_argument(name)
    a=p.parse_args()
    try:print(json.dumps(launch(a.journal,a.universe,a.date,a.formal_run_id,a.private_directory)))
    except Exception as exc:
        print(json.dumps({'status':'BRIDGE_STOPPED_FORMAL_CAPTURE_UNAFFECTED','error_type':type(exc).__name__}));raise SystemExit(1)
