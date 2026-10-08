"""Offline acceptance; exact saved archives only, no market HTTP requests.

Usage: python reports/2026-10-08/dashboard/verify_saved_capture.py CAPTURE.zip OFFICIAL.zip
Public JSON has a live generation timestamp and distinct present publication /
postmarket verification timestamps. It never claims the later audit was live.
"""
import csv
import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import candidate_publication as publication
import probe


def main(capture_path,official_path):
    out=Path(__file__).parent
    raw=Path(capture_path).read_bytes();official_bytes=Path(official_path).read_bytes()
    before=hashlib.sha256(raw).hexdigest();started=time.monotonic()
    payload=publication.from_archive(raw,'2026-10-08','37730234383')
    live_seconds=time.monotonic()-started
    live_fingerprint=payload['price_fingerprint']
    (out/'live_publication_replay.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(io.BytesIO(official_bytes)) as archive:
        def load(name):
            names=[n for n in archive.namelist() if Path(n).name==name]
            if len(names)!=1:raise ValueError('Ambiguous saved official file '+name)
            return json.loads(archive.read(names[0]))
        official=load('official_validation.json');summary=load('validation_summary.json')
    payload=publication.enrich(payload,official,summary['checked_at'],'37742790398')
    payload.update(capture_artifact_id=11530906396,official_validation_artifact_id=11534034875)
    payload['published_at']=payload['updated_at']=probe.iso()
    dest=ROOT/'state/candidates/2026-10-08.json';dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    fields=['code','name','market','P_before','P_close','P_close_trade_time','tail_return_pct',
            'P_close_convergence_type','closing_auction_volume','intraday_total_volume',
            'closing_volume_ratio_pct','volume_status','official_price_result']
    with (out/'seven_volume_verification.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.DictWriter(file,fields);writer.writeheader()
        writer.writerows({k:r[k] for k in fields} for r in payload['candidate_list'])
    proof={r['code']:r['volume_evidence'] for r in payload['candidate_list']}
    (out/'seven_volume_evidence.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    assert before==hashlib.sha256(Path(capture_path).read_bytes()).hexdigest()
    assert live_fingerprint==payload['price_fingerprint']
    result={'trade_date':'2026-10-08','capture_run_id':'37730234383','capture_artifact':'mis-probe-37730234383',
       'capture_artifact_id':11530906396,'capture_sha256':before,'official_run_id':'37742790398',
       'official_artifact_id':11534034875,'official_sha256':hashlib.sha256(official_bytes).hexdigest(),
       'base_main_sha':'b1d81b10e533ce8afe16b8dde8df4e11e9b6bed4','implementation_version':publication.VERSION,
       'implementation_commit_resolution':'git log -1 --format=%H -- candidate_publication.py volume_evidence.py docs/status.js',
       'verified_at':probe.iso(),'live_generated_at':payload['generated_at'],
       'postmarket_verified_at':payload['postmarket_verified_at'],'publication_started_at':payload['published_at'],
       'as_of':payload['generated_at'],'live_replay_seconds':round(live_seconds,3),
       'candidate_count':7,'volume_evidence_confirmed':7,'official_price_match':7,
       'validated':False,'price_fingerprint':live_fingerprint,'raw_artifact_modified':False,
       'postmarket_used_to_select_candidates':False,'no_market_http_requests':True,
       'coverage':payload['coverage'],'volume_contract':'volume_contract.json',
       'independent_official_volume_validation':False}
    (out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main(*sys.argv[1:])
