"""Unscheduled stage3 journal consumer; never creates MIS requests or GitHub writes.

Example (future controlled test only): watch JOURNAL UNIVERSE DATE NEW_OUTPUT.
Independent collection and isolated publication each require an explicit option.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import time
from datetime import datetime
import freshness as f
from fast_capture_journal import verify
from fast_selection import Engine,atomic,stamp,safe_output
from stage3_selection import Pipeline
from stage3_provider import Collector
from stage3_ticks import load_bundle
from stage3_ticks import inspect
from stage3_publication import Publisher,BackgroundPublisher


def watch(journal,universe,date,output,*,collect=False,endpoint=None):
    deadline=f.parsed_time(date+'T14:30:00+08:00')
    if datetime.now(f.TZ)>=deadline or datetime.now(f.TZ).date().isoformat()!=date:
        raise ValueError('NO_HISTORICAL_LIVE_WATCH_OR_BACKFILL')
    directory=safe_output(output);engine=Engine(date,universe,directory/'mis-view','ISOLATED_WATCH')
    pipeline=Pipeline(engine,mode='LIVE');reader_offset=0;attempts={};next_try={};identities={};future=None
    collector=Collector(directory/'independent-source') if collect else None
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    publisher=None
    if endpoint:
        token=os.getenv('STAGE3_PUBLICATION_TOKEN');key=os.getenv('STAGE3_DECISION_KEY')
        if not token or not key:raise ValueError('ISOLATED_PUBLICATION_KEYS_NOT_CONFIGURED')
        publisher=BackgroundPublisher(Publisher(endpoint,directory/'publication',publish_token=token,decision_key=key),deadline)
    last=None
    try:
        while datetime.now(f.TZ)<deadline:
            changed=False
            if Path(journal).exists():
                with Path(journal).open() as file:
                    file.seek(reader_offset)
                    while True:
                        start=file.tell();line=file.readline()
                        if not line or not line.endswith('\n'):file.seek(start);break
                        event=verify(json.loads(line),Path(journal).parent)
                        engine.feed(event['record'],event['persisted_at']);changed=True
                    reader_offset=file.tell()
            if future and future[1].done():
                key,task=future;manifest=task.result()
                if manifest.get('status')=='COLLECTED_NOT_VALIDATED':
                    pipeline.proofs[key]=load_bundle(collector.directory/manifest['manifest_path'])
                next_try[key]=datetime.now(f.TZ).timestamp()+min(5*attempts[key],15)
                future=None;changed=True
            if collector and collector.key and not collector.stopped and not future and (deadline-datetime.now(f.TZ)).total_seconds()>20:
                for row in engine.priority():
                    key=row['ex'],row['code']
                    fingerprint=(row['P_before'],row['P_close'],row['P_before_trade_time'],row['P_close_trade_time'])
                    prior=pipeline.proofs.get(key)
                    structural_reasons=inspect(prior,row,date,stamp())['reasons'] if prior else ['NO_SOURCE_PROOF']
                    needs_retry=any(r not in ('SOURCE_COUNT_AND_VOLUME_SEMANTICS_NOT_CONFIRMED','LIVE_SOURCE_CONTRACT_NOT_RELEASED') for r in structural_reasons)
                    if (attempts.get(key,0)<3 and datetime.now(f.TZ).timestamp()>=next_try.get(key,0)
                        and (key not in identities or fingerprint!=identities[key] or needs_retry)):
                        identities[key]=fingerprint;attempts[key]=attempts.get(key,0)+1
                        future=(key,pool.submit(collector.collect,row,date,deadline));break
            if changed or last is None:
                last=pipeline.compile(stamp());atomic(directory/'stage3-results.json',last)
                if publisher:publisher.submit(last)
            if publisher:publisher.tick()
            time.sleep(.5)
    finally:
        pool.shutdown(wait=True,cancel_futures=True)
        if publisher:publisher.close()
    return last


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('journal',type=Path);p.add_argument('universe',type=Path)
    p.add_argument('date');p.add_argument('output',type=Path);p.add_argument('--collect-independent',action='store_true')
    p.add_argument('--isolated-endpoint');a=p.parse_args()
    result=watch(a.journal,json.loads(a.universe.read_text()),a.date,a.output,collect=a.collect_independent,endpoint=a.isolated_endpoint)
    print(json.dumps({'verified_count':result['verified_count'],'research_count':result['research_count'],'source_contract_live_released':False}))
